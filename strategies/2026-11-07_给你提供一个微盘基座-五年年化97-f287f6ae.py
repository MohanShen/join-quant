# Clone from JoinQuant
# postId: f287f6aef83e32586f08b528c8c7d2d4
# backtestId: 81947cf7f2fc077529085a74654efd33
# title: 给你提供一个微盘基座-五年年化97%

# ==========================================================
# 化繁为简微盘策略 B —— 四段式基底
#
#   每日调仓固定四步（加任何条件都应该挂到对应步骤，不要跨步）：
#     1. 择时   今天做不做      果仁微盘400 指数 vs MA22，三个参数配合：
#                              TIMING_MONTHS（哪几个月判断）
#                              MA_DAYS（均线周期，22）
#                              TIMING_CONFIRM_DAYS（连续 N 日同向才切换，默认 1）
#                              命中月份且 连续 N 日在均线下方 → 清仓买货币ETF
#     2. 筛选   哪些能买        池 → 硬性剔除（ST / 科创688·689 / 北交4·8 / B股9 /
#                              上市不足 250 交易日 / 停牌 / 股价 > MAX_PRICE / 不在全市场证券表）
#                              POOL_INDEX 置空 → 全市场（CANDIDATE_LIMIT=0 不限，或取最小前 N）
#                              这一步只剔除，不带任何偏好，不改变候选之间的相对顺序
#     3. 排序   先买哪些        对**全部候选**打分排序。目前唯一因子 = 总市值（权重 100%）
#                              取前 take = SELL_BUFFER + STOCK_NUM*2 名
#                              加因子只改这一步（_rank_candidates）
#     4. 执行   怎么换手        目标持仓 STOCK_NUM 只等权
#                              排名跌出前 SELL_BUFFER 名才卖（名次翻倍才换手）
#                              当日涨停不卖；昨日涨停、今日开板 → 卖出
#
#   与 A 的差别：持仓 6 → 10 只；新股门槛 60 → 250 交易日。
#   不加：止损、止盈、冷却期、行业分散、避雷包、财务筛选
#
# 口径说明（对不上研究结果时先看这里）：
#   1. 微盘指数直接复用 `果仁微盘指数工具类V1.9.py` 的 GuorenMicroIndex_New
#   2. 择时信号取 T-1 收盘（get_value()），T 日 14:30 执行，不含未来函数
#   3. 399101 取不到成分时不调仓（不静默切全市场，要换池得显式改 POOL_INDEX）
#   4. 全市场模式下排序不走 in_(codes)：4000+ 只塞进 IN 子句会让聚宽静默返回空表
# ==========================================================

from jqdata import *
import numpy as np
import pandas as pd

# ---------------- 参数 ----------------
STOCK_NUM = 10                  # 持仓只数
SELL_BUFFER = max(STOCK_NUM + 1, round(STOCK_NUM * 2.5))   # 缓冲位=N×2，倍数可写小数（自动取整）
POOL_INDEX = '399101.XSHE'      # 股票池指数；置空字符串或 None → 全市场股票
CANDIDATE_LIMIT = 0             # 全市场候选池大小：0=不限（全市场），>0=只取市值最小前 N 只
IDLE_ETF = '511880.XSHG'        # 空仓资产：银华日利
MIN_LIST_DAYS = 250             # 新股过滤（交易日，约一年）

# MAX_PRICE  股价上限（元）。None = 不限。
#   小资金账户才用得上：每只可用金额 = 总资产 / STOCK_NUM，
#   股价 > 该金额/100 时连 1 手都买不进（1 手 = 100 股）。
#   例：1 万 / 6 只 = 1667 元/只，股价 > 16.7 元买不进；设 12.0 可留 30% 余量。
#   代价（五年段实测）：10 万本金约 -2.8pp，1 万本金约 -0.65pp。
MAX_PRICE = None

REBALANCE_TIME = '10:30'        # 调仓时刻

# ============== 择时参数（果仁微盘400 指数）==============
# 三个参数一起决定「今天做不做」，改任何一个都要重新回测验证。
#
# TIMING_MONTHS  哪几个月判断
#   None 或 []          → 不择时，全年满仓（微盘指数完全不参与，省掉预热）
#   [1..12]             → 全年择时
#   [1,4,6,12]          → 只在指定月份检查；非检查月不判断、直接满仓
# [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
TIMING_MONTHS = [1,4]

# MA_DAYS  均线周期。五年段与十年段排名一致：MA18~22 双样本都在前三，MA16 双样本都在谷底
MA_DAYS = 22

# TIMING_CONFIRM_DAYS  连续 N 个交易日同向才切换「持仓/空仓」
#   1 = 当天跌破即清仓（默认，也是双样本最优）
#   2 以上别用：五年段看着更好（2 日 +8.5pp、回撤 -1.9pp），但十年段单调递减
#              （1 日 34.88% > 2 日 30.73% > 3 日 29.12%，回撤 23.31% → 30.57%），
#              属样本内拟合 —— 2021-2026 假跌破多，2016-2021 真跌破多
TIMING_CONFIRM_DAYS = 1

# WARMUP_DAYS  微盘指数预热天数（需 > MA_DAYS）
WARMUP_DAYS = 40


# ==========================================================
# 果仁微盘400 指数 —— 原样取自
#   聚宽研究/微盘/果仁微盘指数工具类/果仁微盘指数工具类V1.9.py
#   class GuorenMicroIndex_New（算法、性能优化、补齐逻辑原样）
#   仅两处适配：① 去掉研究环境用的 matplotlib / warnings 导入
#              ② update() 幂等判断加 Timestamp 兼容（见该方法内注释）
# ==========================================================
class GuorenMicroIndex_New:
    """
    果仁微盘400指数维护类 — 高性能优化版（V1.9）。

    ■ 指数定义（对齐果仁 111001）：全市场A股、上市>60天、排除ST、保留停牌、
      按总市值升序取前400只、每日动态调成分、等权、前复权 close/pre_close 递推。
    ■ 与 V1.9 初版的唯一差异：update() 支持中断后补齐缺失交易日。
    """

    def __init__(self, context, pre_calc_days=30, base_value=1000.0, max_history=250):
        self.index_series = pd.Series(dtype=float)
        self.base_value = base_value
        self.max_history = max_history
        self._ctx = context
        self._initialize_index(context, pre_calc_days)

    def _initialize_index(self, context, days):
        trade_days = get_trade_days(end_date=context.previous_date, count=days + 1)
        current_idx_val = self.base_value
        for i in range(1, len(trade_days)):
            current_idx_val *= (1 + self._calc_daily_return(trade_days[i - 1], trade_days[i]))
            self.index_series.loc[trade_days[i]] = current_idx_val

    def _calc_daily_return(self, calc_date, target_date):
        all_stocks = get_all_securities(['stock'], date=calc_date)
        start_dates = all_stocks['start_date'].values.astype('datetime64[D]')
        listed_days = (np.datetime64(calc_date) - start_dates).astype(int)
        valid_set = set(all_stocks.index[listed_days > 60].tolist())

        df_val = get_fundamentals(query(valuation.code).order_by(
            valuation.market_cap.asc()).limit(1000), date=calc_date)
        if df_val.empty:
            return 0.0
        candidates = [c for c in df_val['code'].tolist() if c in valid_set]
        if candidates:
            st_info = get_extras('is_st', candidates, start_date=calc_date, end_date=calc_date)
            if not st_info.empty:
                candidates = st_info.iloc[0][~st_info.iloc[0]].index.tolist()
        components = candidates[:400]
        if not components:
            return 0.0

        df_price = get_price(components, start_date=target_date, end_date=target_date,
                             fields=['close', 'pre_close'], fq='pre', panel=False)
        df_price = df_price[df_price['pre_close'] > 0] if not df_price.empty else df_price
        if df_price.empty:
            return 0.0
        return float(((df_price['close'] - df_price['pre_close']) / df_price['pre_close']).mean())

    def _check_ctx(self):
        if getattr(self, '_ctx', None) is None:
            raise RuntimeError(
                "微盘指数实例的 context 引用已丢失（对象被持久化/反序列化后恢复导致）。"
                "请调用 rebind_context(context) 重新绑定，或重新创建实例。"
            )

    def rebind_context(self, context):
        self._ctx = context

    def update(self):
        self._check_ctx()
        target_date = self._ctx.previous_date
        # V1.9 原文是 `target_date in self.index_series.index`；pandas 2.x 下
        # datetime.date 与 DatetimeIndex 的成员判断返回 False，幂等守卫会失效，
        # 导致每次 get_value/get_ma 都重复调 get_trade_days。转 Timestamp 后语义不变。
        if pd.Timestamp(target_date) in self.index_series.index:
            return

        if not self.index_series.empty:
            trade_days = get_trade_days(start_date=self.index_series.index[-1], end_date=target_date)
        else:
            trade_days = get_trade_days(end_date=target_date, count=2)

        for i in range(1, len(trade_days)):
            t_date = trade_days[i]
            if t_date in self.index_series.index:
                continue
            base_val = self.index_series.get(trade_days[i - 1], self.base_value)
            self.index_series.loc[t_date] = base_val * (1 + self._calc_daily_return(trade_days[i - 1], t_date))

        if len(self.index_series) > self.max_history:
            self.index_series = self.index_series.iloc[-self.max_history:]

    def get_value(self):
        self.update()
        return float(self.index_series.iloc[-1]) if not self.index_series.empty else None

    def get_ma(self, days):
        self.update()
        return self.index_series.tail(days).mean() if len(self.index_series) >= days else None


def _ensure_index(context):
    """g.idx 会被聚宽持久化，_ctx(context 引用)随之丢失或变成陈旧快照。
    每次取用时无条件 rebind：若 _ctx 指向序列化前的旧 context，update() 会一直
    停在旧 previous_date 上、指数不再更新，这种错比崩更隐蔽。"""
    idx = getattr(g, 'idx', None)
    if idx is None:
        g.idx = GuorenMicroIndex_New(context, pre_calc_days=WARMUP_DAYS, max_history=250)
    else:
        idx.rebind_context(context)      # 只换引用，已算好的 index_series 保留
    return g.idx


# ==========================================================
# 生命周期
# ==========================================================
def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('avoid_future_data', True)
    set_option('use_real_price', True)
    # 滑点直接注释掉用系统默认滑点
    # set_slippage(FixedSlippage(0.002), type="stock")
    # set_slippage(PriceRelatedSlippage(0.00246))
    # set_slippage(PriceRelatedSlippage(0))
    # 手续费统一配置（单点维护）
    # 格式: (资产类型, 卖出印花税, 佣金费率, 最低佣金)
    # 实盘个人使用策略：所以免五
    min_comm = 0
    g.cost_configs = [
        ("stock", 5/10000, 1 / 10000, min_comm),   # 免五
        ("fund",  0,      0.5  / 10000, min_comm),
        ("mmf",   0,      0,            0),
    ]
    for asset_type, close_tax, commission, min_c in g.cost_configs:
        set_order_cost(OrderCost(
            open_tax=0, close_tax=close_tax,
            open_commission=commission, close_commission=commission,
            close_today_commission=0, min_commission=min_c
        ), type=asset_type)    

    # 不开择时就不建微盘指数，省掉 40 天预热
    g.idx = GuorenMicroIndex_New(context, pre_calc_days=WARMUP_DAYS,
                                 max_history=250) if TIMING_MONTHS else None
    g.yesterday_hl = []     # 持仓中昨日收盘涨停的标的

    run_daily(prepare_daily, time='09:05')
    run_daily(rebalance, time=REBALANCE_TIME)

    log.info('[初始化] 化繁为简B | %d股 | 池=%s | 空仓=%s | 择时=%s MA%d 确认%d日'
             % (STOCK_NUM, POOL_INDEX or '全市场', IDLE_ETF,
                ('月份' + str(TIMING_MONTHS)) if TIMING_MONTHS else '关闭',
                MA_DAYS, TIMING_CONFIRM_DAYS))


def prepare_daily(context):
    if TIMING_MONTHS:
        _ensure_index(context).update()
    _mark_yesterday_limit_up(context)


def _mark_yesterday_limit_up(context):
    """记录持仓中昨日收盘涨停的标的（收盘价 == 涨停价）。
    昨日涨停的票，今天不涨停就要卖掉（开板即走），涨停则继续持有。"""
    holds = [s for s in context.portfolio.positions if s != IDLE_ETF]
    if not holds:
        g.yesterday_hl = []
        return
    try:
        df = get_price(holds, end_date=context.previous_date, frequency='daily',
                       fields=['close', 'high_limit'], count=1,
                       panel=False, fill_paused=False)
        if df is None or df.empty:
            g.yesterday_hl = []
            return
        hit = df[df['close'] == df['high_limit']]
        if 'code' in df.columns:
            g.yesterday_hl = list(hit['code'])
        elif len(holds) == 1 and len(hit) == 1:
            g.yesterday_hl = list(holds)      # 单只票未带 code 列时兜底
        else:
            g.yesterday_hl = []
        if g.yesterday_hl:
            log.info('[涨停] 昨日涨停持仓: %s' % g.yesterday_hl)
    except Exception as e:
        log.warn('[涨停] 昨日涨停列表获取失败: %s' % e)
        g.yesterday_hl = []


def _handle_limit_up(context, cd):
    """昨日涨停的持仓：今日仍涨停→继续持有；今日不涨停→卖出（开板即走）。
    返回本轮已卖出的标的集合。"""
    sold = set()
    for s in list(context.portfolio.positions):
        if s == IDLE_ETF or s not in g.yesterday_hl:
            continue
        bar = _bar(cd, s)
        if bar is None or bar.paused or bar.last_price <= bar.low_limit:
            continue
        if bar.last_price >= bar.high_limit:
            log.info('[涨停] %s 仍封涨停，继续持有' % s)
            continue
        order_target_value(s, 0)
        sold.add(s)
        log.info('[涨停] %s 开板，卖出' % s)
    return sold


def _timing_ok(context):
    """返回 True=允许持仓，False=清仓。

    TIMING_MONTHS 为空         → 不择时，永远满仓
    当月不在列表               → 不判断，满仓（对齐果仁 IF(OR(月份...), 检查, 1) 的语义）
    TIMING_CONFIRM_DAYS = 1    → 当天跌破即清仓
    TIMING_CONFIRM_DAYS = N    → 需连续 N 个交易日同向才切换「持仓/空仓」

    状态机用 g.timing_state / g.timing_cnt 保存；聚宽会持久化 g，
    所以跨日、跨进程都能接上。数据取不到时保持现状，不推进计数（避免误清仓/误回场）。
    """
    if not TIMING_MONTHS:
        return True
    if context.current_dt.month not in TIMING_MONTHS:
        return True

    idx = _ensure_index(context)
    val, ma = idx.get_value(), idx.get_ma(MA_DAYS)
    if val is None or ma is None:
        log.warn('[择时] 微盘指数未就绪，保持现状')
        return getattr(g, 'timing_state', True)

    above = val >= ma

    # 单日生效：直接跟随当天信号
    if TIMING_CONFIRM_DAYS <= 1:
        if not above:
            log.info('[择时] %s 微盘 %.2f < MA%d %.2f → 清仓'
                     % (context.current_dt.date(), val, MA_DAYS, ma))
        return above

    # 连续确认：同向则清零计数，反向则累加，达到 N 才切换状态
    state = getattr(g, 'timing_state', True)
    if above == state:
        g.timing_cnt = 0
        return state
    cnt = getattr(g, 'timing_cnt', 0) + 1
    if cnt >= TIMING_CONFIRM_DAYS:
        g.timing_state = above
        g.timing_cnt = 0
        log.info('[择时] %s 微盘 %.2f / MA%d %.2f 连续%d日 → %s'
                 % (context.current_dt.date(), val, MA_DAYS, ma,
                    TIMING_CONFIRM_DAYS, '持仓' if above else '清仓'))
        return above
    g.timing_cnt = cnt
    return state


# ==========================================================
# 每日调仓
# ==========================================================
def rebalance(context):
    """每日调仓管线：择时 → 筛选 → 排序 → 执行

    这个顺序是策略的骨架：
      1. 择时决定「今天做不做」
      2. 筛选决定「哪些能买」（硬性剔除，不含任何偏好）
      3. 排序决定「先买哪些」（因子打分；目前唯一因子=总市值，权重 100%）
      4. 执行决定「怎么换手」（目标持仓、缓冲位、涨停规则）
    加因子只动第 3 步，前两步和最后一步都不用碰。
    """
    cd = get_current_data()

    # ---- 1. 择时：不过就清仓，本轮结束 ----
    if not _timing_ok(context):
        _sell_stocks(context, cd, all_of_them=True)
        _park_cash(context, cd)
        return

    # ---- 2. 筛选：池 → 硬性剔除 → 剔 ST ----
    codes, cap_sorted = _screen_candidates(context, cd)
    if not codes:
        log.warn('[选股] 候选为空，保持现状')
        return

    # ---- 3. 排序：对全部候选打分，取前 N ----
    ordered = _rank_candidates(codes, cap_sorted, context)
    if not ordered:
        log.warn('[排序] 结果为空，保持现状')
        return

    # ---- 4. 执行 ----
    # 4.1 不卖区：排名在 SELL_BUFFER 以内不卖（名次翻倍才换手）
    keep = set(ordered[:SELL_BUFFER])

    # 4.2 涨停规则：昨日涨停、今日开板 → 先卖（今天仍封板的继续持有）
    sold = _handle_limit_up(context, cd)

    # 4.3 卖出跌出缓冲位的
    sold |= _sell_stocks(context, cd, keep=keep)

    # 4.4 腾出 ETF 资金
    if IDLE_ETF in context.portfolio.positions:
        order_target_value(IDLE_ETF, 0)

    # 4.5 补齐空位（停牌/涨停买不进的顺延到后面名次）
    held = [s for s in context.portfolio.positions
            if s != IDLE_ETF and s not in sold]
    slots = STOCK_NUM - len(held)
    if slots <= 0:
        return

    buyable = []
    for s in ordered:
        if s in sold:
            continue
        bar = _bar(cd, s)
        if bar is None or bar.paused or bar.last_price >= bar.high_limit:
            continue
        buyable.append(s)
    buy_list = [s for s in buyable if s not in held][:slots]
    if not buy_list:
        return

    # 按目标等权买入，现金不够时按可用资金均分
    per = min(context.portfolio.total_value / STOCK_NUM,
              context.portfolio.available_cash / len(buy_list))
    for s in buy_list:
        order_value(s, per)
        log.info('[买] %s 约 %.0f 元' % (s, per))


# ==========================================================
# 工具
# ==========================================================
def _is_new_stock(list_date, today, tdays):
    """上市不足 MIN_LIST_DAYS 个交易日 → True

    tdays 为覆盖窗口的交易日数组（datetime64[D]）。取不到时退回自然日口径。
    start_date 读出来是 datetime.date（不是 Timestamp），pd.Timestamp() 包一层。
    """
    if tdays is None or len(tdays) == 0:
        return (today - pd.Timestamp(list_date).date()).days < MIN_LIST_DAYS
    sd = np.datetime64(pd.Timestamp(list_date).date(), 'D')
    if sd < tdays[0]:
        return False        # 窗口外上市，交易日数必然 > MIN_LIST_DAYS
    return len(tdays) - int(np.searchsorted(tdays, sd, side='left')) < MIN_LIST_DAYS


# ==========================================================
# 选股管线
#   1) _screen_candidates  只做剔除，不改变候选之间的相对顺序
#   2) _rank_candidates    对全部候选打分排序，取前 take 名
# 加因子时只改 2) 的打分部分，筛选与执行都不用动。
# ==========================================================
def _screen_candidates(context, cd):
    """筛选：股票池 → 硬性剔除（科创/北交/B股/新股/停牌）→ 剔 ST

    返回 (codes, cap_sorted)：
      codes       过滤后的候选，保持输入 pool 的相对顺序
      cap_sorted  True = codes 已按总市值升序（全市场模式下 pool 本身就是市值序）

    成分取法对齐 ZI多策略最终版：get_index_stocks(code, context.current_dt)，
    第二参数必须是 datetime；传 datetime.date 时取不到成分。
    POOL_INDEX 为空/None 时用全市场：按市值升序取全表，过滤后由排序层直接切片，
    不再走 in_(keep) —— 5000+ 只塞进 IN 子句会静默返回空表。
    CANDIDATE_LIMIT > 0 时只取市值最小前 N 只做候选（限定池子大小的实验用）。
    """
    prev = context.previous_date
    today = context.current_dt.date()

    # --- 取池：指数成分 / 全市场 ---
    if POOL_INDEX:
        try:
            pool = get_index_stocks(POOL_INDEX, context.current_dt) or []
        except Exception as e:
            log.warn('[选股] get_index_stocks(%s) 异常: %s' % (POOL_INDEX, e))
            pool = []
        if not pool:
            log.warn('[选股] %s 成分取不到，本轮不调仓' % POOL_INDEX)
            return [], False
    else:
        q = query(valuation.code).order_by(valuation.market_cap.asc())
        # 聚宽 get_fundamentals 默认只返回 1000 行，想拿全市场必须显式放大 limit
        q = q.limit(CANDIDATE_LIMIT if CANDIDATE_LIMIT and CANDIDATE_LIMIT > 0 else 6000)
        df0 = get_fundamentals(q, date=prev)
        if df0 is None or df0.empty:
            log.warn('[选股] 全市场市值查询返回空')
            return [], False
        pool = df0['code'].tolist()

    # --- 硬性剔除：科创 / 北交 / B股 / 新股 / 停牌 ---
    sec = get_all_securities(['stock'], date=prev)

    # 新股门槛按交易日算：一次取足窗口，逐只 searchsorted 数上市后走过多少交易日。
    # 窗口长度 > MIN_LIST_DAYS 个交易日，上市日早于窗口起点的直接判老股。
    try:
        tdays = np.array(get_trade_days(
            start_date=context.current_dt - pd.Timedelta(days=MIN_LIST_DAYS * 2 + 60),
            end_date=context.current_dt), dtype='datetime64[D]')
    except Exception as e:
        log.warn('[选股] 交易日序列获取失败，新股门槛退回自然日口径: %s' % e)
        tdays = None

    keep = []
    n_kcb = n_notsec = n_new = n_nobar = n_paused = n_price = 0
    for c in pool:
        if c[:3] in ('688', '689') or c[0] in ('4', '8', '9'):
            n_kcb += 1
            continue
        if c not in sec.index:
            n_notsec += 1
            continue
        if _is_new_stock(sec.loc[c, 'start_date'], today, tdays):
            n_new += 1
            continue
        # 不能写 `c not in cd`：聚宽 get_current_data() 的成员判断不可靠，
        # 会对池里每一只都返回 True，导致候选被整池清空且不报错。
        try:
            bar = cd[c]
        except Exception:
            n_nobar += 1
            continue
        if bar.paused:
            n_paused += 1
            continue
        if MAX_PRICE and bar.last_price and bar.last_price > MAX_PRICE:
            n_price += 1
            continue
        keep.append(c)
    n_basic = len(keep)
    if not keep:
        log.warn('[选股] 基础过滤后为空：池%d 剔科创%d 不在表%d 新股%d 无行情%d 停牌%d 超价%d'
                 % (len(pool), n_kcb, n_notsec, n_new, n_nobar, n_paused, n_price))
        return [], False

    # --- 剔 ST ---
    try:
        st = get_extras('is_st', keep, start_date=prev, end_date=prev)
        if not st.empty:
            row = st.iloc[0].fillna(False).astype(bool)
            keep = row[~row].index.tolist()
    except Exception as e:
        log.warn('[选股] ST 过滤异常: %s' % e)
    if not keep:
        log.warn('[选股] ST 过滤后为空（基础 %d）' % n_basic)
        return [], False

    # get_extras 返回的是列序，恢复成 pool 的顺序，保证全市场模式下仍是市值升序
    order = {c: i for i, c in enumerate(pool)}
    keep.sort(key=lambda c: order.get(c, 10 ** 9))
    log.info('[筛选] 池%d → 基础%d(剔价%d) → 非ST%d' % (len(pool), n_basic, n_price, len(keep)))
    return keep, (not POOL_INDEX)


def _rank_candidates(codes, cap_sorted, context):
    """排序：对**全部候选**打分，返回前 take 名。

    目前唯一因子 = 总市值（权重 100%，升序）。
    以后加因子时改这里：把 codes 逐个算综合得分，按得分排序后返回前 take 名，
    筛选层和执行层都不用动。注意打分必须在 codes 全体上做 —— 先截断再打分会让
    因子只在某个市值子集里生效。

    take = SELL_BUFFER + STOCK_NUM * 2：
      前 SELL_BUFFER 名 → 排名掉出这个范围才卖（名次翻倍才换手）
      余下 STOCK_NUM*2 → 备用名额，停牌/涨停买不进时顺延到后面的名次
    """
    take = SELL_BUFFER + STOCK_NUM * 2

    # 全市场模式：codes 已按市值升序（来自 pool），直接取前缀。
    # 不能再走 in_(codes)：4000+ 只塞进 IN 子句会让聚宽静默返回空表。
    if cap_sorted:
        n = min(take, len(codes))
        log.info('[排序] 候选%d（已按市值升序）→ 取前%d' % (len(codes), n))
        return codes[:n]

    # 指数池：成分顺序与市值无关，查一次市值排序
    q = query(valuation.code).filter(valuation.code.in_(codes)).order_by(
        valuation.market_cap.asc()).limit(take)
    df = get_fundamentals(q, date=context.previous_date)
    if df is None or df.empty:
        log.warn('[排序] 市值排序为空（候选 %d）' % len(codes))
        return []
    log.info('[排序] 候选%d → 取前%d' % (len(codes), len(df)))
    return df['code'].tolist()


def _bar(cd, code):
    """取单只标的的当前行情。
    聚宽 get_current_data() 不支持可靠的 `code in cd` 成员判断
    （对池里每只都返回 False，会静默清空候选），所以统一用 try 取值。"""
    try:
        return cd[code]
    except Exception:
        return None


def _sell_stocks(context, cd, keep=None, all_of_them=False):
    """卖出不在 keep 里的持仓，返回已下单的标的。
    当日涨停的不卖（让利润奔跑，等开板再由 _handle_limit_up 处理）。"""
    sold = set()
    for s in list(context.portfolio.positions):
        if s == IDLE_ETF:
            continue
        if not all_of_them and keep is not None and s in keep:
            continue
        bar = _bar(cd, s)
        if bar is None or bar.paused or bar.last_price <= bar.low_limit:
            continue
        if bar.last_price >= bar.high_limit:
            log.info('[涨停] %s 封板，本轮不卖' % s)
            continue
        order_target_value(s, 0)
        sold.add(s)
        log.info('[卖] %s' % s)
    return sold


def _park_cash(context, cd):
    cash = context.portfolio.available_cash
    if cash < 10000:
        return
    bar = _bar(cd, IDLE_ETF)
    if bar is None or bar.paused:
        return
    order_value(IDLE_ETF, cash)
