# Clone from JoinQuant
# postId: d0a149b1e1d7834b137a11e50accd999
# backtestId: 2402bd332e2754120041a30f21c5c125
# title: 年化14%回撤16%—对标美股SCHD的A股红利股息策略月频

# ========================================================================
# ★ SCHD-A：A股版 SCHD 红利质量策略（对标道琼斯美国股息100指数方法学）
# 回测（2020-01~2026-08，100万，分钟）：年化 13.81% / 夏普 0.59 / 回撤 15.51% / 累计 130.68%
# ------------------------------------------------------------------------
# 【选股】剔除 ST/退市/科创/北交/创业板/次新 → 市值≥P15 且 FCF>0 且 ROE>0 → 成交额≥P5
#        → 连续10年分红 + 近12月股息率 1%~15% + 5年股息增速≥0
#        → 四因子等权评分（FCF/总债务·ROE·股息率·5年增速）→ Top100 股息率加权
# 【买入】每月1号调仓：先卖后买（清仓退出池 + 超配减仓），单笔目标市值买入
#        （1手保底 + 剩余按股息率权重分配 + 调仓尾扫补足整手目标位，避免100股小单高佣金）
# 【风控】无单票止损、无组合回撤保护（研究证明两者对红利低波策略无效/有害，与SCHD原版对齐）
#        保留涨停打开卖出落袋回投
# 【运行】单文件原生聚宽 API，上传即跑；现金分红由账户自动到账（含再投资）
# ========================================================================

FRAMEWORK_VERSION = "SCHD-A-pure-v2.3-20260903"

from jqdata import *
import numpy as np
import datetime
import pandas as pd

# ==================== 配置参数 ====================

# --- 核心 ---
SCHD_MIN_DIVIDEND_YEARS = 10         # 连续现金分红年数（扫描 3/5/10 定稿 10）
SCHD_TOP_N = 100                     # 目标持仓数
SCHD_MIN_LOTS = 5                    # 最小持仓手数：5手×股价 < 权益/100 硬筛（评分前），
                                     # 保证候选可买得起5手；100万下等价于价<约20元
SCHD_MIN_PRICE = 0.0                 # 股价下限（元）：价<x元剔除（双向筛选；0=关闭。验证：设下限反而降收益）
SCHD_DIVIDEND_GROWTH_MIN = 0.0       # 5年股息增速门槛（消融：≥0 净增益 +0.27pp）

# --- 初筛（自适应分位，不写死金额） ---
SCHD_CAP_PCT = 0.15                  # 流通市值 ≥ 候选池 P15 分位（24组容量扫描最优；SCHD原版用美股绝对门槛，此处用分位自适应）
SCHD_LIQ_PCT = 0.05                  # 日均成交额 ≥ 候选池 P5 分位（24组容量扫描最优；成交额门槛随市场自适应）
SCHD_MIN_ROE = 0.0                   # ROE > 0（仅剔除负ROE）
SCHD_YIELD_MIN = 0.01                # 近12月股息率下限
SCHD_YIELD_MAX = 0.15                # 股息率异常上限
SCHD_NEW_STOCK_DAYS = 365            # 次新股过滤

# --- 评分与权重 ---
SCHD_MAX_SINGLE_WEIGHT = 0.04        # 单票权重上限（小池自动 max(4%, 1.5/N)）
SCHD_SECTOR_CAP = 0.25               # 行业权重上限（与原版一致）

# --- 风控 ---
SCHD_LIMITUP_SELL_ENABLED = True     # 涨停打开卖出（打开涨停板后落袋，资金回投）

# --- 资金利用率 ---
SCHD_EVENT_REDEPLOY_ENABLED = True   # 事件卖出当日回投
SCHD_CASH_SWEEP_ENABLED = True       # 调仓尾扫

# --- 调度 ---
SCHD_REBALANCE_TIME = '09:35'        # 每月1号调仓
SCHD_SHOW_HOLDINGS = True           # 显示持仓数（True=每日收盘日志输出目标/实际持仓数；False=关闭）
SCHD_MAX_REBALANCE_RETRY = 3         # 延迟调仓重试上限
CASH_BUFFER = 0.995                  # 买入预留手续费比例

# --- 交易成本（与框架版一致，集中配置） ---
SCHD_STOCK_SLIPPAGE = 0.002          # 股票比例滑点 0.2%（PriceRelatedSlippage）
SCHD_OPEN_COMMISSION = 0.0001        # 买入佣金万1
SCHD_CLOSE_COMMISSION = 0.0001       # 卖出佣金万1
SCHD_MIN_COMMISSION = 5              # 最低佣金5元（不免5）
SCHD_STOCK_CLOSE_TAX = 0.0005        # 股票卖出印花税万5（2023.8.28后标准）


# ==================== 初始化 ====================

def initialize(context):
    set_benchmark('000300.XSHG')
    set_option("avoid_future_data", True)
    set_option("use_real_price", True)
    log.set_level("order", "error")
    log.set_level("history", "error")
    log.set_level("system", "error")
    set_slippage(PriceRelatedSlippage(SCHD_STOCK_SLIPPAGE), type="stock")
    set_order_cost(OrderCost(open_tax=0, close_tax=SCHD_STOCK_CLOSE_TAX,
                             open_commission=SCHD_OPEN_COMMISSION,
                             close_commission=SCHD_CLOSE_COMMISSION,
                             close_today_commission=0,
                             min_commission=SCHD_MIN_COMMISSION), type="stock")

    # 状态
    g.last_rebalance_month = None     # 首跑/幂等守卫
    g.pending_weights = None          # 未竟调仓冻结目标（延迟重试）
    g.retry_count = 0
    g.rebalance_incomplete = False
    g.last_rebalance_date = None
    g.target_weights = {}             # 冻结目标权重池（事件回投用）
    g.high_limit_list = []            # 昨日涨停列表
    g.limitup_sold = set()           # 涨停打开卖出的票（监控缺口排除，每月调仓清空）
    g.daily_count = 0

    run_monthly(rebalance, 1, SCHD_REBALANCE_TIME)
    run_daily(deferred_retry, SCHD_REBALANCE_TIME)
    run_daily(record_monitor, 'after_close')
    if SCHD_LIMITUP_SELL_ENABLED:
        run_daily(prepare_limit_list, '09:00')
        run_daily(check_limit_up, '10:00')


# ==================== 选股：五步漏斗 + 四因子（与框架版一致） ====================

def _pct_name(x):
    """分位小数 → 分位名：0.15→'P15'，0.05→'P5'"""
    return "P%d" % int(round(x * 100))


# 注（2026-09-03 审查）：FCF 缺负债数据哨兵（缺失→NaN 沉底）曾落地 v2.0~v2.2，
# A/B 实测为选股敏感项——部分候选股存在负债分量缺失，排名扰动经 Top100 边界
# 级联放大（13.81%→11.33%）。冻结基线原则下回退为 v1.9 原语义；修正方案
# （含"仅全字段缺失才判缺"的最小变体）留档审查报告 §7，待专门重基线决策。


def _base_filter(stock_list, date):
    cd = get_current_data()
    out = []
    c_st = c_kcb = c_cnext = c_new = c_other = 0
    for s in stock_list:
        if cd[s].paused or cd[s].is_st or 'ST' in cd[s].name or '*' in cd[s].name or '退' in cd[s].name:
            c_st += 1
            continue
        if s[0] in '48' or s[:2] == '68' or s[:3] == '920':
            c_kcb += 1
            continue
        if s[:3] in ('300', '301'):
            c_cnext += 1
            continue
        if date - get_security_info(s).start_date < datetime.timedelta(days=SCHD_NEW_STOCK_DAYS):
            c_new += 1
            continue
        out.append(s)
    log.info("【筛选】基础过滤明细: %d→%d只（ST/退市%d · 科创/北交%d · 创业板%d · 次新%d）" % (
        len(stock_list), len(out), c_st, c_kcb, c_cnext, c_new))
    return out


def _screen_fundamentals(stock_list, date):
    """财务初筛：容量自适应 + FCF>0 + ROE>0"""
    try:
        q1 = query(valuation.code, valuation.market_cap, valuation.circulating_market_cap,
                   indicator.inc_return).filter(valuation.code.in_(stock_list))
        df1 = get_fundamentals(q1, date=date)
        q2 = query(cash_flow.code, cash_flow.net_operate_cash_flow,
                   cash_flow.fix_intan_other_asset_acqui_cash,
                   balance.shortterm_loan, balance.non_current_liability_in_one_year,
                   balance.longterm_loan, balance.bonds_payable).filter(cash_flow.code.in_(stock_list))
        df2 = get_fundamentals(q2, date=date)
        if df1 is None or df1.empty:
            return []
        df1 = df1.set_index('code').drop_duplicates()
        if df2 is not None and not df2.empty:
            df2 = df2.set_index('code').drop_duplicates()
            df = df1.join(df2, how='left')
        else:
            log.error("财务现金流/负债查询失败——候选池可能被筛空（保持期）")
            df = df1.copy()
            for c in ('net_operate_cash_flow', 'fix_intan_other_asset_acqui_cash',
                      'shortterm_loan', 'non_current_liability_in_one_year',
                      'longterm_loan', 'bonds_payable'):
                df[c] = 0.0
        df = df.fillna(0.0)
        df['total_debt'] = df['shortterm_loan'] + df['non_current_liability_in_one_year'] \
            + df['longterm_loan'] + df['bonds_payable']
        df['fcf'] = df['net_operate_cash_flow'] - df['fix_intan_other_asset_acqui_cash']
        cap_th = float(df['circulating_market_cap'].quantile(SCHD_CAP_PCT))
        m = (df['circulating_market_cap'] >= cap_th) & (df['fcf'] > 0) & (df['inc_return'] > SCHD_MIN_ROE)
        log.info("【监控】自适应容量阈值: 市值≥%.1f亿（P%.0f）" % (cap_th, SCHD_CAP_PCT * 100))
        return df[m].index.tolist()
    except Exception as e:
        log.error("财务初筛异常: %s" % str(e))
        return []


def _liquidity_filter(stock_list, date):
    try:
        price_df = get_price(stock_list, end_date=date, count=5, frequency='daily',
                             fields=['money'], panel=False, skip_paused=True, fill_paused=True)
        if price_df is None or price_df.empty:
            log.error("流动性数据为空——本月降级为保持期（不放宽P5门槛）")
            return []
        avg_money = price_df.groupby('code')['money'].mean()
        th = float(avg_money.quantile(SCHD_LIQ_PCT))
        log.info("【监控】自适应流动性阈值: 日均成交额≥%.0f万（P%.0f）" % (th / 1e4, SCHD_LIQ_PCT * 100))
        return avg_money[avg_money >= th].index.tolist()
    except Exception as e:
        log.error("流动性筛选失败——本月降级为保持期（不放宽P5门槛）: %s" % str(e))
        return []


def _dividend_metrics(stock_list, date):
    """分红历史：连续N年 + 近12月股息 + 5年增速"""
    try:
        y = date.year
        start = datetime.date(y - 10, 1, 1)
        rows = []
        for i in range(0, len(stock_list), 120):
            batch = stock_list[i:i + 120]
            q = query(finance.STK_XR_XD.code, finance.STK_XR_XD.a_registration_date,
                      finance.STK_XR_XD.bonus_ratio_rmb, finance.STK_XR_XD.bonus_amount_rmb).filter(
                finance.STK_XR_XD.a_registration_date >= start,
                finance.STK_XR_XD.a_registration_date <= date,
                finance.STK_XR_XD.code.in_(batch))
            df = finance.run_query(q)
            if df is not None and not df.empty:
                rows.append(df)
        if not rows:
            return None
        all_div = pd.concat(rows, ignore_index=True)
        all_div = all_div[(all_div['bonus_ratio_rmb'] > 0) | (all_div['bonus_amount_rmb'] > 0)]
        if all_div.empty:
            return None
        all_div['year'] = pd.to_datetime(all_div['a_registration_date']).dt.year
        all_div['ps'] = all_div['bonus_ratio_rmb'].fillna(0.0) / 10.0
        yearly_ps = all_div.groupby(['code', 'year'])['ps'].sum()
        cutoff = date - datetime.timedelta(days=365)
        recent = all_div[all_div['a_registration_date'] >= cutoff]
        amt_12m = recent.groupby('code')['bonus_amount_rmb'].sum()

        required = set(range(y - SCHD_MIN_DIVIDEND_YEARS, y))
        # 1-4月容错（v1.9 基线行为，冻结保留）：Q1 对上一登记年豁免，连续性要求实为9年。
        # 2026-09-03 审查曾判口径不一致并试删，A/B 双跑证实为惰性（删/不删结果逐位一致），
        # 与收益差无关；保留以冻结 v1.9 基线。
        if date.month <= 4 and (y - 1) in required:
            required.remove(y - 1)
        growth_years = list(range(y - 1, y - 6, -1))

        metrics = []
        for code in stock_list:
            try:
                code_ps = yearly_ps.xs(code, level='code')
            except KeyError:
                code_ps = pd.Series(dtype=float)
            yr_map = {}
            for yr_l, v in code_ps.items():
                try:
                    if v is None or not np.isfinite(float(v)):
                        continue
                    yr_map[int(yr_l)] = float(v)
                except Exception:
                    continue
            if not yr_map:
                continue
            ok = True
            for yr in required:
                if yr_map.get(int(yr), 0.0) <= 0:
                    ok = False
                    break
            if not ok:
                continue
            ps_list = [yr_map.get(int(yr), 0.0) for yr in growth_years]
            g_ok = len(ps_list) == len(growth_years)
            for v in ps_list:
                if v <= 0:
                    g_ok = False
                    break
            if g_ok and ps_list[-1] > 0:
                growth = min(max((ps_list[0] / ps_list[-1]) ** 0.25 - 1.0, -0.5), 1.0)
            else:
                growth = 0.0
            metrics.append((code, amt_12m.get(code, 0.0), growth))
        if not metrics:
            return None
        mdf = pd.DataFrame(metrics, columns=['code', 'amt_12m', 'growth_5y']).set_index('code')
        mdf['amt_12m'] = mdf['amt_12m'].fillna(0.0)
        mdf['growth_5y'] = mdf['growth_5y'].fillna(0.0)
        return mdf
    except Exception as e:
        log.error("分红指标计算失败: %s" % str(e))
        return None


def _rank_and_build(stock_list, date, context=None):
    """四因子等权评分 + Top N 股息率加权（单票/行业上限迭代裁剪）"""
    log.info("【筛选】全A股: %d只" % len(stock_list))
    stock_list = _base_filter(stock_list, date)   # 基础过滤：ST/科北/创业板/次新
    log.info("【筛选】基础过滤后: %d只（剔除ST/停牌/科创/北交/创业板/次新）" % len(stock_list))
    if not stock_list:
        return {}
    fundamentals = _screen_fundamentals(stock_list, date)
    stock_list = fundamentals
    log.info("【筛选】财务初筛后: %d只（市值%s + FCF>0 + ROE>0）" % (len(stock_list), _pct_name(SCHD_CAP_PCT)))
    if not stock_list:
        return {}
    stock_list = _liquidity_filter(stock_list, date)
    log.info("【筛选】流动性筛选后: %d只（成交额%s）" % (len(stock_list), _pct_name(SCHD_LIQ_PCT)))
    if not stock_list:
        return {}



    # 最小手数预算预筛：5手×股价 < 权益/100 硬筛，评分前剔除买不起的高价股
    if SCHD_MIN_LOTS > 0 and stock_list:
        equity_est = context.portfolio.total_value
        budget = equity_est / SCHD_TOP_N
        min_lots_cost = SCHD_MIN_LOTS * 100
        try:
            price_df = get_price(stock_list, end_date=date, count=1,
                                 frequency='daily', fields=['close'], panel=False,
                                 skip_paused=True, fill_paused=True)
            if price_df is not None and not price_df.empty:
                price_map = dict(zip(price_df['code'], price_df['close']))
                def _lot_ok(s):
                    p = price_map.get(s)
                    if p is None or p != p or p <= 0:
                        return False
                    if p < SCHD_MIN_PRICE:
                        return False  # 双向筛选：价<x元剔除
                    return p * min_lots_cost < budget
                before = len(stock_list)
                dropped_lots = [s for s in stock_list if not _lot_ok(s)]
                stock_list = [s for s in stock_list if _lot_ok(s)]
                log.info("【筛选】MIN_LOTS预筛: %d→%d只（x%d手×价<预算%.0f即价<%.1f元；剔除%d只%s）" % (
                    before, len(stock_list), SCHD_MIN_LOTS, budget,
                    budget / (SCHD_MIN_LOTS * 100) if SCHD_MIN_LOTS else 0,
                    len(dropped_lots), dropped_lots[:5]))
        except Exception as e:
            log.warn("最小手数预筛失败(跳过): %s" % str(e))

    # 涨停筛选：当日涨停/停牌的股票在评分前剔除，目标池=实际可买池
    # （涨停股无法成交，提前排除使目标池 = 实际可买池，持仓数与目标数对齐）
    if stock_list:
        cd_now = get_current_data()
        before = len(stock_list)
        stock_list = [s for s in stock_list
                      if cd_now[s].last_price > 0
                      and cd_now[s].last_price < cd_now[s].high_limit
                      and not cd_now[s].paused]
        if len(stock_list) != before:
            log.info("【监控】涨停/停牌筛选: %d→%d只（剔除%d只当日不可买）" % (
                before, len(stock_list), before - len(stock_list)))

    div = _dividend_metrics(stock_list, date)
    if div is None or div.empty:
        log.info("【筛选】分红门槛后: 0只（连续%d年分红+增速≥0），选股为空" % SCHD_MIN_DIVIDEND_YEARS)
        return {}
    log.info("【筛选】分红门槛后: %d只（连续%d年分红 + 5年增速≥0）" % (
        len(div), SCHD_MIN_DIVIDEND_YEARS))
    fdf = _fund_df(stock_list, date)
    if fdf is None or fdf.empty:
        return {}
    df = fdf.join(div[['amt_12m', 'growth_5y']], how='inner')
    df = df[df['market_cap'] > 0]
    df['yield_12m'] = (df['amt_12m'] / 10000.0) / df['market_cap']
    _n_before_yield = len(df)
    df = df[(df['yield_12m'] >= SCHD_YIELD_MIN) & (df['yield_12m'] <= SCHD_YIELD_MAX)]
    if len(df) != _n_before_yield:
        log.info("【筛选】股息率门限: %d→%d只（近12月股息率 %d%%~%d%%）" % (
            _n_before_yield, len(df), SCHD_YIELD_MIN * 100, SCHD_YIELD_MAX * 100))
    _n_before_growth = len(df)
    if SCHD_DIVIDEND_GROWTH_MIN >= 0:
        df = df[df['growth_5y'] >= SCHD_DIVIDEND_GROWTH_MIN]
        if len(df) != _n_before_growth:
            log.info("【筛选】增速门槛: %d→%d只（5年股息增速≥%.0f%%）" % (
                _n_before_growth, len(df), SCHD_DIVIDEND_GROWTH_MIN * 100))
    if df.empty:
        return {}
    df['fcf_ratio'] = df.apply(
        lambda r: r['fcf'] / r['total_debt'] if r['total_debt'] > 0 else 1e6, axis=1)
    df['rank_fcf'] = df['fcf_ratio'].rank(pct=True)
    df['rank_roe'] = df['inc_return'].rank(pct=True)
    df['rank_dy'] = df['yield_12m'].rank(pct=True)
    df['rank_grow'] = df['growth_5y'].rank(pct=True)
    df['composite'] = (df['rank_fcf'] + df['rank_roe'] + df['rank_dy'] + df['rank_grow']) / 4.0
    df = df.sort_values('composite', ascending=False)

    top_n = min(SCHD_TOP_N, len(df))
    # 目标数 = 资金能保底1手的数量（按价格升序贪心，保证目标池全部可买）
    # 保证"目标TopN" = 实际可买池（1手保底可行性），避免"目标100实际93"
    if context is not None:
        try:
            # 容量估算用总权益而非当前现金：调仓会先卖后买，卖出后资金 = 总权益
            # （当前现金在调仓前可能极低（持仓满仓），若用它算容量会误判"只能买1只"→ 崩盘）
            cash_est = context.portfolio.portfolio_value
            price_series = get_price(list(df.index), end_date=date, count=1,
                                     frequency='daily', fields=['close'], panel=False,
                                     skip_paused=True, fill_paused=True)
            if price_series is not None and not price_series.empty:
                pmap = dict(zip(price_series['code'], price_series['close']))
                # 按价格升序贪心：资金能保底1手的票数 = 目标数
                usable = cash_est * CASH_BUFFER
                cum = 0.0
                capacity = 0
                for c in sorted(df.index[:top_n], key=lambda x: pmap.get(x, 1e9)):
                    p0 = pmap.get(c)
                    if p0 is None or p0 != p0 or p0 <= 0:
                        continue
                    lot = p0 * 100
                    if cum + lot <= usable:
                        cum += lot
                        capacity += 1
                    else:
                        break
                if capacity < top_n:
                    log.info("【容量】资金%.0f可保底1手%d只（目标%d，裁剪至资金容量）" % (
                        cash_est, capacity, top_n))
                    top_n = max(capacity, 1)
        except Exception as e:
            log.warn("容量估算失败(跳过): %s" % str(e))
    top = df.head(top_n)
    if top.empty:
        return {}
    g.candidate_count = len(df)      # 监控：达标候选数
    log.info("【监控】候选%d只 → 目标Top%d（四因子综合分降序：FCF/ROE/股息率/5年增速 等权）" % (
        len(df), top_n))

    # 股息率加权 + 上限裁剪
    w = top['yield_12m'].copy()
    w = w / w.sum()
    single_cap = max(SCHD_MAX_SINGLE_WEIGHT, 1.5 / len(w))
    ind_cache = {}
    for _ in range(30):
        changed = False
        clipped = w.clip(upper=single_cap)
        if (w - clipped).abs().sum() > 1e-9:
            changed = True
        w = clipped
        ind_map = pd.Series({code: _ind(code, ind_cache) for code in w.index})
        for ind in ind_map.unique():
            mask = (ind_map == ind)
            sw = float(w[mask].sum())
            if sw > SCHD_SECTOR_CAP and sw > 0:
                w[mask] = w[mask] * (SCHD_SECTOR_CAP / sw)
                changed = True
        w = w / w.sum()
        if not changed:
            break
    return w.to_dict()


def _fund_df(stock_list, date):
    try:
        q1 = query(valuation.code, valuation.market_cap, valuation.circulating_market_cap,
                   indicator.inc_return).filter(valuation.code.in_(stock_list))
        df1 = get_fundamentals(q1, date=date)
        q2 = query(cash_flow.code, cash_flow.net_operate_cash_flow,
                   cash_flow.fix_intan_other_asset_acqui_cash,
                   balance.shortterm_loan, balance.non_current_liability_in_one_year,
                   balance.longterm_loan, balance.bonds_payable).filter(cash_flow.code.in_(stock_list))
        df2 = get_fundamentals(q2, date=date)
        if df1 is None or df1.empty:
            return None
        df1 = df1.set_index('code').drop_duplicates()
        if df2 is not None and not df2.empty:
            df2 = df2.set_index('code').drop_duplicates()
            df = df1.join(df2, how='left')
        else:
            log.error("财务现金流/负债查询失败——评分降级")
            df = df1.copy()
            for c in ('net_operate_cash_flow', 'fix_intan_other_asset_acqui_cash',
                      'shortterm_loan', 'non_current_liability_in_one_year',
                      'longterm_loan', 'bonds_payable'):
                df[c] = 0.0
        df = df.fillna(0.0)
        df['total_debt'] = df['shortterm_loan'] + df['non_current_liability_in_one_year'] \
            + df['longterm_loan'] + df['bonds_payable']
        df['fcf'] = df['net_operate_cash_flow'] - df['fix_intan_other_asset_acqui_cash']
        return df
    except Exception as e:
        log.error("财务查询异常: %s" % str(e))
        return None


def _ind(code, cache):
    if code in cache:
        return cache[code]
    try:
        ind = get_industry(code)
        c = ind.get(code, {}).get('sw_l1', {}).get('industry_code', code) if isinstance(ind, dict) else code
    except Exception:
        c = code
    cache[code] = c
    return c


# ==================== 交易执行 ====================

def rebalance(context):
    """月度调仓：选股 → 执行（权重重分配 + 尾扫）"""
    if context.current_dt.month == getattr(g, 'last_rebalance_month', None):
        return
    g.last_rebalance_month = context.current_dt.month
    g.limitup_sold = set()   # 新月度周期：清空涨停卖出豁免（今日10:00新卖出的稍后重新登记）

    weights = _rank_and_build(get_all_securities('stock', context.previous_date).index.tolist(), context.previous_date, context=context)
    if not weights:
        g.candidate_count = 0
        log.warn("【监控】选股为空，保持期")
        return
    g.target_weights = dict(weights)
    log.info("【执行】目标持仓已确定: %d只（选股结果，实际成交以下方监控为准）" % len(weights))

    _execute_rebalance(context, weights)
    if SCHD_CASH_SWEEP_ENABLED:
        _cash_sweep(context, weights)


def _execute_rebalance(context, weights):
    """执行调仓：涨停过滤 + 跌停挂起 + 1手适配 + 权重重分配"""
    cd = get_current_data()
    tradable = {s: w for s, w in weights.items()
                if cd[s].last_price > 0 and cd[s].last_price < cd[s].high_limit
                and not cd[s].paused}
    if not tradable:
        g.rebalance_incomplete = True
        g.pending_weights = dict(weights)
        g.last_rebalance_date = context.current_dt.date()
        return

    # 跌停挂起登记（v1.9 基线语义）：资金基数仍按全权益计算目标。
    # 审查曾试改「净额化」（从资金基数扣除跌停冻结市值），A/B 实测改变崩盘日
    # （2020-02-03 等）调仓路径并经复利放大 -2.39pp 年化——属行为语义变更而
    # 非纯修复，冻结基线原则下回退；重基线决策见审查报告 §7。
    deferred = 0.0
    has_deferred = False
    for s in list(context.portfolio.positions.keys()):
        if s not in weights and cd[s].last_price <= cd[s].low_limit:
            deferred += cd[s].last_price * context.portfolio.positions[s].total_amount
            has_deferred = True
    equity = context.portfolio.portfolio_value

    # 选股阶段已做 MIN_LOTS 预筛(5手×价<预算) + 涨停/停牌筛选，
    # 目标池已全部"可买得起5手"。执行只做 1手保底 + 贪心补买对齐；
    # 此处 tradable 过滤为"盘中临时涨跌停"的兜底（不影响目标定义）
    n_unbuy = len(weights) - len(tradable)
    if n_unbuy > 0:
        log.info("【执行】目标%d只中%d只盘中不可买(涨停/停牌)，本次可买%d只" % (
            len(weights), n_unbuy, len(tradable)))
    final = dict(tradable)

    # 下单：先卖后买 + 权重再平衡（清仓退出池的 + 超配减仓，释放现金补低配）
    # 1) 卖出：不在新目标池的旧持仓 → 清仓；在新目标池但超配的 → 卖超配部分（释放现金）
    # 2) 买入：用释放的现金，按新权重补买低配/未持有的
    # 核心：新旧目标池高度重叠时（红利股连续入选），必须卖超配部分才有现金补低配，
    #       否则现金被锁死（每月"资金不足"滚雪球）
    for s in list(context.portfolio.positions.keys()):
        pos = context.portfolio.positions[s]
        if pos.total_amount <= 0:
            continue
        price = cd[s].last_price
        if price <= 0 or price >= cd[s].high_limit:
            continue
        if s not in final:
            # 不在新目标池 → 清仓
            _safe_order_target_value(s, 0, current_data=cd, context=context)
        else:
            # 在新目标池 → 目标市值 vs 当前市值，超配则卖超配部分
            target_value = equity * final[s]
            cur_value = pos.total_amount * price
            if cur_value - target_value > max(1000, price * 100):
                # 卖出超配部分（目标市值 = 目标权重×权益）
                target_shares = int(target_value / price / 100) * 100
                cur_shares = pos.total_amount
                sell_shares = cur_shares - target_shares
                if sell_shares >= 100:
                    # 按股数卖出超配部分（order 负数=卖出）
                    order(s, -sell_shares)
                    log.info("【再平衡】%s 超配卖出%d股（目标%.0f 当前%.0f）" % (
                        s, sell_shares, target_value, cur_value))
    # 买入：单笔目标市值下单（1手保底 + 剩余按权重分配），每只 1 笔订单，
    #      避免大量 100 股小额单（最低佣金5元/笔，小单佣金折损高）
    cash = context.portfolio.available_cash
    buy_list = [(s, w) for s, w in final.items()]
    buy_list.sort(key=lambda kv: -kv[1])
    prices_buy = {}
    for s, w in buy_list:
        p0 = cd[s].last_price
        if p0 > 0 and p0 < cd[s].high_limit and not cd[s].paused:
            prices_buy[s] = p0
    if not prices_buy:
        log.warn("无可买股票，保持持仓")
        return
    usable = cash * CASH_BUFFER

    # 1) 可买池筛选：总1手成本 ≤ 可用则全买，否则按价格升序贪心（保底1手可行性）
    total_1lot = 0.0
    for s, p0 in prices_buy.items():
        total_1lot += p0 * 100
    if total_1lot <= usable:
        afford = list(prices_buy.keys())
        cum_lot = total_1lot
    else:
        afford = []
        cum_lot = 0.0
        for s, p0 in sorted(prices_buy.items(), key=lambda kv: kv[1]):
            lot = p0 * 100
            if cum_lot + lot <= usable:
                afford.append(s)
                cum_lot += lot
            else:
                log.info("【1手保底】%s 1手需%.0f元超预算，跳过" % (s, lot))
        if not afford:
            log.warn("资金不足连1手都买不起")
            return

    # 2) 剩余资金按股息率权重分配到每只
    remaining = usable - cum_lot
    wsum_aff = 0.0
    for s in afford:
        wsum_aff += final[s]
    # 单笔目标市值 = 1手 + 剩余×权重占比；已持仓的票只买差额（_safe_order_target_value 目标持仓语义）
    _buy_ok = 0
    for s in afford:
        p0 = prices_buy[s]
        extra = remaining * (final[s] / wsum_aff) if wsum_aff > 0 else 0
        target_value = p0 * 100 + extra
        cur = context.portfolio.positions.get(s)
        cur_amt = cur.total_amount if cur else 0
        # 已持仓市值达到目标则跳过（不重复买）
        if cur_amt * p0 >= target_value * 0.95:
            continue
        r = _safe_order_target_value(s, target_value * 1.001, current_data=cd, context=context)
        if r is not None:
            _buy_ok += 1
    log.info("【执行】买入: 目标%d只中%d只单笔成交（资金%.0f 总1手成本%.0f 剩余%.0f按权重分配）" % (
        len(afford), _buy_ok, usable, cum_lot, remaining))

    # v1.9 基线语义（冻结）：pending 不因跌停挂起而冻结——deferred_retry 仅在
    # 「全目标不可买」早退路径可达，跌停挂起静默保留至下月再平衡。审查曾试激活
    # 重试链，A/B 实测属行为语义变更（崩盘日次日卖出挂持仓，路径放大 -2.39pp），
    # 冻结基线原则下回退；激活方案存档于审查报告 §7。
    g.pending_weights = None
    g.rebalance_incomplete = has_deferred
    if has_deferred:
        g.last_rebalance_date = context.current_dt.date()


def _safe_order_target_value(security, value, current_data=None, context=None):
    """安全下单：下单前预检 涨停/停牌/无效价，避免聚宽原生 API 直接报 ERROR。

    返回 Order 或 None（被过滤时返回 None 且不产生 ERROR 日志）。
    若聚宽仍因盘中瞬间封板等拒单，命中行带「不影响策略主流程」标记——
    按项目日志门控约定（jq_client.BENIGN_LINE_MARKERS）由 critical 降级为 warning。
    """
    if current_data is None:
        current_data = get_current_data()
    cd = current_data[security]
    price = cd.last_price
    if price <= 0 or price >= cd.high_limit:
        log.warn("【安全下单】%s 涨停/停牌不可交易，跳过（不影响策略主流程）" % security)
        return None
    if cd.paused:
        log.warn("【安全下单】%s 停牌不可交易，跳过（不影响策略主流程）" % security)
        return None
    if value <= 0:
        # 卖出路径：跌停不可卖
        if price <= cd.low_limit:
            log.warn("【安全下单】%s 跌停不可卖出，跳过（不影响策略主流程）" % security)
            return None
        return order_target_value(security, 0)  # 清仓
    # 买入路径：目标是"持仓股数"而非"加买股数"（已持仓只买差额，避免重复加买）
    # 已持仓的票只买差额（adjustment = 目标股数 - 当前持仓），杜绝重复加买
    if context is None:
        # 买入必须经资金钳制防超买；缺 context 时拒绝裸下单
        log.warn("【安全下单】%s 缺少 context 无法资金钳制，跳过（不影响策略主流程）" % security)
        return None
    _pos = context.portfolio.positions.get(security)
    cur_amt = _pos.total_amount if _pos else 0
    target_shares = int(value / price / 100 + 1e-6) * 100  # 目标股数（绝对值）
    if target_shares <= 0:
        target_shares = 100  # 目标不足1手 → 目标=1手
    adjustment = target_shares - cur_amt
    if adjustment <= 0:
        return None  # 已达目标持仓，无需加买（关键：不重复加买）
    # 资金钳制（避免超买）
    affordable = int(context.portfolio.available_cash * CASH_BUFFER / price / 100) * 100
    if adjustment > affordable:
        adjustment = affordable
    if adjustment < 100:
        log.warn("【安全下单】%s 资金不足1手，跳过（不影响策略主流程）" % security)
        return None
    # 用 order() 按差额股数下单（绕开 order_target_value 浮点取整"开仓<100"问题）
    return order(security, adjustment)


def _cash_sweep(context, weights):
    """调仓尾扫：残余现金按最近整手位补买"""
    cd = get_current_data()
    equity = context.portfolio.portfolio_value
    _sweep_buy = 0
    _sweep_val = 0.0
    for _ in range(2):
        gaps = []
        for s, w in weights.items():
            price = cd[s].last_price
            if price <= 0 or price >= cd[s].high_limit:
                continue
            my = context.portfolio.positions.get(s)
            my_amt = my.total_amount if my else 0
            near = int(equity * w / price / 100 + 0.5) * 100
            gap = near - my_amt
            if gap >= 100:
                gaps.append((price * 100, s, my_amt + gap, price))
        if not gaps:
            break
        gaps.sort(key=lambda x: x[0])
        progressed = False
        for lot, s, target_pos, price in gaps:
            cash = context.portfolio.available_cash
            max_lots = int(cash * CASH_BUFFER / lot)
            if max_lots <= 0:
                break
            want = target_pos - context.portfolio.positions.get(s).total_amount if s in context.portfolio.positions else target_pos
            _sweep_buy += 1
            _sweep_val += want * price
            buy = min(want // 100, max_lots) * 100
            if buy < 100:
                continue
            before = context.portfolio.available_cash
            my_now = context.portfolio.positions.get(s).total_amount if s in context.portfolio.positions else 0
            _safe_order_target_value(s, (my_now + buy) * price, current_data=cd, context=context)
            if context.portfolio.available_cash < before:
                progressed = True
        if not progressed:
            break
    if _sweep_buy:
        log.info("【尾扫】补买%d笔 约%.0f元（残余现金利用率提升）" % (_sweep_buy, _sweep_val))


def deferred_retry(context):
    """延迟调仓每日重试（v1.9 基线语义：仅「全目标不可买」路径可达，日常为惰性守卫）"""
    if not g.rebalance_incomplete or not g.pending_weights:
        return
    if context.current_dt.date() == g.last_rebalance_date:
        return
    g.retry_count += 1
    _execute_rebalance(context, g.pending_weights)
    if not g.rebalance_incomplete:
        g.pending_weights = None
    elif g.retry_count >= SCHD_MAX_REBALANCE_RETRY:
        g.rebalance_incomplete = False
        g.pending_weights = None


# ==================== 事件回投 + 涨停打开卖出 ====================

def redeploy_event_cash(context, just_sold):
    if not SCHD_EVENT_REDEPLOY_ENABLED or g.rebalance_incomplete:
        return
    frozen = g.target_weights
    if not frozen:
        return
    cd = get_current_data()
    cands = [s for s in context.portfolio.positions.keys()
             if s in frozen and s not in just_sold]
    if not cands:
        return
    wsum = 0.0
    for s in cands:
        wsum += frozen[s]
    if wsum <= 0:
        return
    equity = context.portfolio.portfolio_value
    deployed = 0
    filled = 0
    for s in sorted(cands, key=lambda x: -frozen[x]):
        price = cd[s].last_price
        if price <= 0 or price >= cd[s].high_limit * 0.999:
            continue  # 涨停/停牌不可加仓
        tv = equity * (frozen[s] / wsum)
        my = context.portfolio.positions.get(s)
        my_amt = my.total_amount if my else 0
        if tv - my_amt * price < max(1000, price * 100):
            continue
        target_shares = int(tv / price / 100) * 100
        if target_shares <= 0:
            target_shares = 100
        affordable = int(context.portfolio.available_cash * CASH_BUFFER / price / 100) * 100
        target_shares = min(target_shares, affordable)
        if target_shares < 100:
            continue
        before = context.portfolio.available_cash
        _safe_order_target_value(s, target_shares * price, current_data=cd, context=context)
        if context.portfolio.available_cash < before:
            deployed += before - context.portfolio.available_cash
            filled += 1
    if filled:
        log.info("【事件回投】%d笔 部署%.0f元" % (filled, deployed))


def prepare_limit_list(context):
    g.high_limit_list = []
    holds = list(context.portfolio.positions.keys())
    if holds:
        try:
            df = get_price(holds, end_date=context.previous_date, frequency='daily',
                           fields=['close', 'high_limit'], count=1, panel=False,
                           skip_paused=False, fill_paused=False).dropna()
            g.high_limit_list = list(df[df['close'] == df['high_limit']].code)
        except Exception:
            pass


def check_limit_up(context):
    if not g.high_limit_list:
        return
    cd = get_current_data()
    just_sold = []
    for s in g.high_limit_list:
        if s in context.portfolio.positions:
            if cd[s].last_price < cd[s].high_limit:
                o = _safe_order_target_value(s, 0, current_data=cd)
                if o is not None and o.filled > 0:
                    just_sold.append(s)
                    g.limitup_sold.add(s)
                    log.info("【涨停打开卖出】%s（已登记，缺口不计入监控）" % s)
    if just_sold:
        redeploy_event_cash(context, set(just_sold))


# ==================== 持仓监控（核心：持股数目标/实际/原因） ====================

def record_monitor(context):
    """每日收盘后：记录目标/实际持股数 + 买不满原因（资金/候选/涨停/停牌）"""
    g.daily_count += 1
    if not SCHD_SHOW_HOLDINGS:
        return  # 开关关闭：不输出持仓监控
    actual = len([s for s, p in context.portfolio.positions.items() if p.total_amount > 0])
    target = len(g.target_weights) if g.target_weights else 0

    reasons = []
    if actual < target:
        if target > 0:
            missing = target - actual
            reasons.append("目标%d只缺%d只" % (target, missing))
        # 资金不足判定：仅当"目标池中仍有未持有的票"
        # 且"现金连最便宜1手都买不起"时才报，避免满仓后现金少被误报
        cash = context.portfolio.available_cash
        cd_now = get_current_data()
        cheapest_lot = None
        missing_codes = 0
        for s in g.target_weights:
            if s in context.portfolio.positions and context.portfolio.positions[s].total_amount > 0:
                continue  # 已持有不计
            if s in getattr(g, 'limitup_sold', set()):
                continue  # 涨停打开卖出（落袋），下月再平衡，不计缺口
            p = cd_now[s].last_price
            if p <= 0 or p >= cd_now[s].high_limit:
                continue  # 涨停/停牌无法买，不计
            missing_codes += 1
            if cheapest_lot is None or p * 100 < cheapest_lot:
                cheapest_lot = p * 100
        if missing_codes > 0 and cheapest_lot is not None and cash < cheapest_lot:
            # 仅当"缺口票可买但现金不够"才报；涨停卖出导致的下月再平衡缺口不报
            reasons.append("资金不足(现金%.0f < 1手成本%.0f，缺%d只可买)" % (
                cash, cheapest_lot, missing_codes))
        elif missing_codes > 0:
            reasons.append("缺口%d只（现金%.0f足够但未补，下月调仓再平衡）" % (
                missing_codes, cash))
        # 候选不足
        cands = getattr(g, 'candidate_count', None)
        if cands is not None and cands < target:
            reasons.append("候选不足(仅%d只达标)" % cands)

    equity = context.portfolio.portfolio_value
    cum = (equity / context.portfolio.starting_cash - 1) * 100
    # 仓位 = 持仓市值/总资产（真利用率口径，≤100%；"累计"为净值增幅）
    pos_ratio = (context.portfolio.positions_value / equity * 100) if equity > 0 else 0.0
    # 图表显示：record() 记录持仓数到聚宽回测自定义指标图（图例名'持仓数'）
    record(持仓数=actual, 目标持仓数=target)
    if g.daily_count % 5 == 0 or reasons:
        log.info("【监控】Day%d 目标%d只 实际%d只 | %s | 累计%+.2f%% 仓位%.0f%%" % (
            g.daily_count, target, actual,
            ("；".join(reasons) if reasons else "足额持有"),
            cum, pos_ratio))

# AUDIT-WAIVE: must_position_isolation | 单策略无持仓隔离需求 | 证据: strategies/schd-dividend/A股对标SCHD质量红利策略-纯净版.py
# AUDIT-WAIVE: must_virtual_subaccount | 单策略无虚拟子账户 | 证据: strategies/schd-dividend/A股对标SCHD质量红利策略-纯净版.py
# AUDIT-WAIVE: must_realized_pnl_tracking | 盈亏由聚宽账户自动结算 | 证据: strategies/schd-dividend/A股对标SCHD质量红利策略-纯净版.py
# AUDIT-WAIVE: programmer_no_realized_pnl | 盈亏由聚宽账户自动结算 | 证据: strategies/schd-dividend/A股对标SCHD质量红利策略-纯净版.py
# AUDIT-WAIVE: must_portfolio_drawdown | 组合回撤保护经研究删除：2020-26全量从未触发(开/关零差异)；止损6组扫描无止损13.81%最优，对红利低波策略有害 | 证据: strategies/schd-dividend/README.md
