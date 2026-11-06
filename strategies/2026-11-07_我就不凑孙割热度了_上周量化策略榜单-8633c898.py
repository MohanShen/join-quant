# Clone from JoinQuant
# postId: 8633c89899322b5eacb00161f773f366
# backtestId: 3464c614667d6f4d1ab8964f5fc12df3
# title: 我就不凑孙割热度了，上周量化策略榜单

# 克隆自聚宽文章：https://www.joinquant.com/post/74931
# 标题：上个月分享的跟着基金经理跑的策略挺有用的
# 作者：派大星搞不懂宇宙社会学

# ============================================================
# 策略名称：基金经理抱团 + 动量轮动
# 说明：
#   股池不再固定，每季度动态从 29 只科技基金的持仓中提取"抱团股"
#   （被 ≥3 只基金共同持有的股票），然后沿用三因子动量打分轮动。
#
# 核心创新：
#   1. 股池 = 机构共识票（基金经理用钱投票选出来的）
#   2. 季度更新，跟随机构调仓节奏
#   3. 过滤港股（仅保留 A 股），不限板块（主板 + 创业板 + 科创板均可）
#   4. 动量因子在共识池里做二次精选
#
# 数据时序说明（避免未来信息）：
#   Q4 报告 → 次年 1 月底可用  |  Q1 报告 → 4 月底可用
#   Q2 中报 → 8 月底可用      |  Q3 报告 → 10 月底可用
# ============================================================

import numpy as np
from jqdata import *

# ============================================================
# 基金清单（与基金研究保持一致）
# ============================================================
# 近一个月收益排名前30的基金（2026-05-29 数据）
FUND_CODES = [
    "501046",  # 财通福鑫定开混合发起 — 近1月 12.64%
    "014915",  # 财通匠心优选一年持有期混合A — 近1月 12.20%
    "014916",  # 财通匠心优选一年持有期混合C — 近1月 12.19%
    "017490",  # 财通景气甄选一年持有期混合A — 近1月 11.29%
    "017491",  # 财通景气甄选一年持有期混合C — 近1月 11.28%
    "006502",  # 财通集成电路产业股票A — 近1月 9.89%
    "006503",  # 财通集成电路产业股票C — 近1月 9.88%
    "001480",  # 财通成长优选混合A — 近1月 9.11%
    "021528",  # 财通成长优选混合C — 近1月 9.11%
    "024480",  # 财通品质甄选混合A — 近1月 8.77%
    "024481",  # 财通品质甄选混合C — 近1月 8.77%
    "004320",  # 前海开源沪港深乐享生活 — 近1月 4.11%
    "008983",  # 财通科技创新混合A — 近1月 0.87%
    "008984",  # 财通科技创新混合C — 近1月 0.86%
    "720001",  # 财通价值动量混合A — 近1月 9.14%
    "021523",  # 财通价值动量混合C — 近1月 9.13%
    "011369",  # 华商均衡成长混合A — 近1月 7.32%
    "011370",  # 华商均衡成长混合C — 近1月 7.31%
    "001170",  # 宏利复兴混合A — 近1月 7.93%
    "017612",  # 宏利复兴混合C — 近1月 7.92%
    "002692",  # 富国创新科技混合A — 近1月 5.11%
    "011120",  # 富国创新科技混合C — 近1月 5.09%
    "257070",  # 国联安优选行业混合 — 近1月 8.58%
    "014023",  # 宏利景气领航两年持有混合 — 近1月 8.12%
    "162201",  # 宏利成长混合 — 近1月 7.36%
    "020821",  # 大成领先动力混合A — 近1月 8.62%
    "024592",  # 圆信永丰科技驱动混合发起A — 近1月 7.27%
    "020822",  # 大成领先动力混合C — 近1月 8.61%
    "024593",  # 圆信永丰科技驱动混合发起C — 近1月 7.27%
    "011899",  # 长安鑫瑞科技6个月定开混合A — 近1月 3.16%
]


def initialize(context):
    """
    初始化函数
    """
    # ==================== 实盘交易设置 ====================
    set_option("avoid_future_data", True)
    set_option("use_real_price", True)
    set_slippage(PriceRelatedSlippage(0.001), type="stock")

    # 交易成本设置
    set_order_cost(OrderCost(
        open_tax=0,
        close_tax=0.001,
        open_commission=0.0001,
        close_commission=0.0001,
        close_today_commission=0,
        min_commission=5
    ), type='stock')

    log.set_level('order', 'error')
    log.set_level('strategy', 'info')

    # ==================== 策略参数 ====================
    g.lookback_days = 20       # 动量计算周期（天）
    g.holdings_num = 5         # 持仓数量（Top N）
    g.min_money = 5000         # 最小交易金额

    # 抱团参数
    g.min_fund_count = 15       # 最少被多少只基金持有才算"抱团"
    g.quarter_refresh_day = 15  # 每个季度第几个交易日刷新股池

    # 风控参数
    g.stop_loss = 0.95         # 固定止损线（亏损 5% 卖出）

    # 三因子线性权重
    g.weight_momentum = 0.8    # 区间动量
    g.weight_r2 = 0.8          # 趋势质量 R²
    g.weight_vol = 0.3         # 量价共振

    # ==================== 初始股池 ====================
    # 不再使用固定科技股池，完全依赖基金经理抱团池动态生成
    # 首个交易日盘前会触发拉取，后续每月 1 号按报告期切换刷新
    g.stock_pool = []
    g.pool_source = "等待抱团池"

    # ==================== 交易时间安排 ====================
    run_daily(before_trading_start, time='09:00')  # 盘前：检查是否需要刷新抱团池
    run_daily(rebalance, time='10:30')              # 每日调仓
    run_daily(check_positions, time='09:50')        # 早盘：记录持仓

    log.info(f"策略初始化完成，初始股池: {len(g.stock_pool)} 只")
    log.info(f"抱团阈值: ≥{g.min_fund_count} 只基金 | 持仓数: {g.holdings_num}")


# ============================================================
# 季度抱团池刷新
# ============================================================

def get_report_period_for_date(current_date):
    """
    根据当前日期，确定应该使用哪个报告期的数据。
    避免未来信息：只在报告披露后才使用对应季度的数据。

    返回 (period_start, period_end, label) 或 (None, None, None)
    """
    year = current_date.year
    month = current_date.month

    # Q4 报告 → 次年 1 月底可用（保守取 2 月 1 日）
    # Q1 报告 → 4 月底可用（保守取 5 月 1 日）
    # Q2 中报 → 8 月底可用（保守取 9 月 1 日）
    # Q3 报告 → 10 月底可用（保守取 11 月 1 日）

    if month >= 11:
        # 11 月之后：Q3 报告已出
        return (f"{year}-07-01", f"{year}-09-30", f"Q3-{year}")
    elif month >= 9:
        # 9-10 月：Q2 中报已出
        return (f"{year}-04-01", f"{year}-06-30", f"Q2-{year}")
    elif month >= 5:
        # 5-8 月：Q1 报告已出
        return (f"{year}-01-01", f"{year}-03-31", f"Q1-{year}")
    elif month >= 2:
        # 2-4 月：上年 Q4 报告已出
        return (f"{year - 1}-10-01", f"{year - 1}-12-31", f"Q4-{year - 1}")
    else:
        # 1 月：只能看上上年 Q3（Q4 报告还没出）
        return (f"{year - 1}-07-01", f"{year - 1}-09-30", f"Q3-{year - 1}")


def fetch_consensus_pool(context):
    """
    从基金持仓数据中提取抱团股池。
    1. 查询所有基金在指定报告期的前十大持仓
    2. 统计每只股票被多少只基金持有
    3. 保留 ≥ min_fund_count 的股票
    4. 过滤港股（仅保留 .XSHE / .XSHG 结尾的 A 股）
    """
    period_start, period_end, label = get_report_period_for_date(context.current_dt)

    if period_start is None:
        log.warning("无法确定报告期，保持现有股池")
        return []

    log.info(f"正在拉取基金持仓数据 — 报告期: {label} ({period_start} ~ {period_end})")

    all_holdings = []
    success_count = 0

    for fund_code in FUND_CODES:
        try:
            q = (
                query(finance.FUND_PORTFOLIO_STOCK)
                .filter(
                    finance.FUND_PORTFOLIO_STOCK.code == fund_code,
                    finance.FUND_PORTFOLIO_STOCK.period_start == period_start,
                    finance.FUND_PORTFOLIO_STOCK.period_end == period_end,
                )
                .order_by(finance.FUND_PORTFOLIO_STOCK.rank.asc())
                .limit(20)
            )
            df = finance.run_query(q)
            if df is not None and len(df) > 0:
                df["_fund_code"] = fund_code
                all_holdings.append(df[["symbol", "name", "_fund_code"]])
                success_count += 1
        except Exception as e:
            pass  # 静默跳过单只基金的数据缺失

    if not all_holdings:
        log.warning(f"未拉取到任何基金持仓数据，保持现有股池")
        return []

    df_all = pd.concat(all_holdings, ignore_index=True)
    log.info(f"成功拉取 {success_count}/{len(FUND_CODES)} 只基金，共 {len(df_all)} 条持仓")

    # 统计每只股票被多少只基金持有
    stock_fund_count = df_all.groupby(["symbol", "name"])["_fund_code"].nunique().reset_index()
    stock_fund_count.columns = ["symbol", "name", "fund_count"]

    # 过滤：≥3 基金抱团
    consensus = stock_fund_count[stock_fund_count["fund_count"] >= g.min_fund_count].copy()
    log.info(f"抱团阈值 ≥{g.min_fund_count}：{len(consensus)} 只候选股票")

    # FUND_PORTFOLIO_STOCK 的 symbol 是纯代码（无后缀）
    # 疑似港股：以 .HK 结尾 或 非 6 位数字代码
    consensus["is_hk"] = consensus["symbol"].str.endswith(".HK") | \
                          ~consensus["symbol"].str.match(r"\d{6}")
    hk_count = consensus["is_hk"].sum()
    if hk_count > 0:
        log.info(f"过滤疑似港股 {hk_count} 只（代码非 6 位数字）")

    consensus = consensus[~consensus["is_hk"]]


    # 提取股票代码列表，补上交易所后缀（FUND_PORTFOLIO_STOCK 返回裸代码）
    def _add_suffix(code):
        return f"{code}.XSHG" if code.startswith("6") else f"{code}.XSHE"

    pool = sorted(consensus["symbol"].apply(_add_suffix).tolist())

    # 打印抱团 Top 10
    top10 = consensus.nlargest(10, "fund_count")
    for _, row in top10.iterrows():
        log.info(f"  抱团 {row['symbol']} {row['name']} ← {int(row['fund_count'])} 只基金")

    return pool


def before_trading_start(context):
    """
    盘前检查：如果进入新的报告披露窗口，刷新抱团股池。
    每月 1 号检查一次，避免每天重复查询。
    """
    today = context.current_dt.date()
    current_period = get_report_period_for_date(context.current_dt)
    current_label = current_period[2] if current_period[2] else "NONE"

    # 记录上次使用的报告期标签
    if not hasattr(g, '_last_period_label'):
        g._last_period_label = None

    # 触发条件：空池立即拉取，非空池每月第一天检查报告期切换
    pool_empty = len(g.stock_pool) == 0
    if (pool_empty or today.day == 1) and current_label != g._last_period_label:
        log.info(f"=== 报告期切换: {g._last_period_label} → {current_label} ===")
        new_pool = fetch_consensus_pool(context)

        if new_pool and len(new_pool) >= 3:
            g.consensus_pool = new_pool
            g.stock_pool = new_pool
            g.pool_source = f"抱团池-{current_label}"
            g._last_period_label = current_label
            log.info(f"✓ 股池已切换为抱团池: {len(g.stock_pool)} 只")
        elif new_pool:
            log.warning(f"抱团池仅有 {len(new_pool)} 只股票（不足 3 只），保持现有股池")
        else:
            log.warning("抱团池为空，保持现有股池")


# ============================================================
# 纯动量三因子打分
# ============================================================

def calculate_momentum_score(security, lookback):
    """
    三因子纯动量打分：
      因子1 — 区间动量：lookback 日价格回报率
      因子2 — 趋势质量：对数价格线性拟合的 R²
      因子3 — 量价共振：近 5 日均量 / 近 20 日均量
    得分 = w1×区间动量 + w2×R² + w3×量比
    """
    w1 = g.weight_momentum
    w2 = g.weight_r2
    w3 = g.weight_vol

    try:
        prices = attribute_history(security, lookback + 10, '1d',
                                   ['close', 'volume'], skip_paused=True, df=False)
        if len(prices['close']) < lookback:
            return 0

        price_series = prices['close'][-lookback - 1:]
        vol_series = prices['volume'][-lookback - 1:]

        if len(price_series) < lookback + 1:
            return 0

        current_data = get_current_data()
        current_price = current_data[security].last_price
        if current_price is None or current_price <= 0:
            return 0

        price_series = np.append(price_series, current_price)

        # ---- 因子1：区间动量 ----
        momentum = price_series[-1] / price_series[0] - 1

        # ---- 因子2：趋势质量 R² ----
        y = np.log(price_series)
        x = np.arange(len(y))
        slope, intercept = np.polyfit(x, y, 1)
        ss_res = np.sum((y - (slope * x + intercept)) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot != 0 else 0

        # ---- 因子3：量价共振 ----
        if len(vol_series) >= 20:
            vol_short = np.mean(vol_series[-5:])
            vol_long = np.mean(vol_series[-20:])
            vol_ratio = vol_short / vol_long if vol_long > 0 else 1.0
        else:
            vol_ratio = 1.0

        score = w1 * momentum + w2 * r_squared + w3 * vol_ratio
        return score

    except Exception as e:
        log.warning(f"计算 {security} 得分出错: {e}")
        return 0


# ============================================================
# 获取目标持仓
# ============================================================

def get_target_weights(context):
    """
    对当前股池内所有标的打分，选出得分最高的 g.holdings_num 只，等权重分配。
    返回：{security: weight} 字典
    """
    scores = []
    pool = g.stock_pool
    for stock in pool:
        score = calculate_momentum_score(stock, g.lookback_days)
        if score > 0:
            scores.append((stock, score))

    if not scores:
        log.warning("无任何标的得分 >0，将保持现有持仓不变")
        return {}

    scores.sort(key=lambda x: x[1], reverse=True)
    top_stocks = [s[0] for s in scores[:g.holdings_num]]
    weight = 1.0 / len(top_stocks)
    target = {stock: weight for stock in top_stocks}

    log.info(f"今日得分前 {g.holdings_num} 名 [{g.pool_source}]: "
             f"{[s[0].split('.')[0] for s in scores[:g.holdings_num]]}")
    return target


# ============================================================
# 智能下单
# ============================================================

def smart_order_target_value(context, security, target_value):
    """
    下单到目标市值（处理停牌、涨跌停、最小交易单位）。
    仅交易主板 A 股，100 股起买。
    """
    current_data = get_current_data()
    if security not in current_data:
        return False
    if current_data[security].paused:
        log.info(f"{security} 停牌，跳过")
        return False

    price = current_data[security].last_price
    if price <= 0:
        return False

    if security in context.portfolio.positions.keys():
        pos = context.portfolio.positions[security]
        current_amount = pos.total_amount
        closeable = pos.closeable_amount
    else:
        current_amount = 0
        closeable = 0

    target_amount = int(target_value / price)
    target_amount = (target_amount // 100) * 100

    # 修正点：科创板起买 200 股，其余 100 股
    if security.startswith('688'):
        if target_amount > 0 and target_amount < 200:
            target_amount = 200
    else:
        if target_amount <= 0 and target_value > 0:
            target_amount = 100

    diff_amount = target_amount - current_amount
    if diff_amount == 0:
        return True

    if abs(diff_amount) * price < g.min_money:
        return False

    if diff_amount < 0:
        if closeable <= 0:
            log.info(f"{security} 无可卖股份（T+1 限制）")
            return False
        diff_amount = -min(abs(diff_amount), closeable)

    order_result = order(security, diff_amount, LimitOrderStyle(price))

    if order_result:
        action = "买入" if diff_amount > 0 else "卖出"
        log.info(f"{action} {security} {abs(diff_amount)} 股 @ {price:.3f}")
        return True
    else:
        log.warning(f"下单失败: {security} 数量 {diff_amount}")
        return False


# ============================================================
# 调仓主函数
# ============================================================

def rebalance(context):
    log.info(f"=== 开始调仓 [{g.pool_source}] ===")

    target_weights = get_target_weights(context)

    if not target_weights:
        log.info("无有效信号，保持现有持仓不变")
        return

    total_value = context.portfolio.total_value
    usable_value = total_value * 0.99
    target_dict = {sec: usable_value * weight for sec, weight in target_weights.items()}

    # 【第一阶段：卖出（清仓或减仓）】
    existing = set(context.portfolio.positions.keys())
    for sec in existing:
        if sec not in target_dict:
            smart_order_target_value(context, sec, 0)
        else:
            pos = context.portfolio.positions[sec]
            current_value = pos.total_amount * pos.price
            if current_value > target_dict[sec]:
                smart_order_target_value(context, sec, target_dict[sec])

    # 【第二阶段：买入（建仓或加仓）】
    for sec, target_value in target_dict.items():
        if sec in existing:
            pos = context.portfolio.positions[sec]
            current_value = pos.total_amount * pos.price
        else:
            current_value = 0
        if current_value < target_value:
            smart_order_target_value(context, sec, target_value)

    # 【固定止损检查】
    for sec in list(context.portfolio.positions.keys()):
        pos = context.portfolio.positions[sec]
        if pos.total_amount > 0:
            current_price = pos.price
            avg_cost = pos.avg_cost
            if current_price <= avg_cost * g.stop_loss:
                log.info(f"触发止损: {sec} 成本 {avg_cost:.3f} 现价 {current_price:.3f}")
                smart_order_target_value(context, sec, 0)

    log.info("=== 调仓完成 ===")


def check_positions(context):
    """记录当日持仓"""
    held_count = 0
    for sec, pos in context.portfolio.positions.items():
        if pos.total_amount > 0:
            held_count += 1
            log.info(f"持仓 {sec} 数量 {pos.total_amount} "
                     f"成本 {pos.avg_cost:.3f} 现价 {pos.price:.3f}")
    log.info(f"当前持有 {held_count} 只股票，股池来源: {g.pool_source}，"
             f"股池大小: {len(g.stock_pool)}")
