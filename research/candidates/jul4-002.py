# Research candidate — join-quant autoresearch
# expId:    jul4-002 (001 + 大盘MA20择时)
# baseline: 最小市值月度轮动 (min-cap monthly rotation)
# harness:  research/harness.md（冻结评测台 epoch 1）
# schema:   docs/research-schema.md
#
# ┌─────────────────────────────────────────────────────────────────────────┐
# │ 这是策略脚手架。agent 只在四个「因子槽位」(FACTOR SLOT) 内变异，           │
# │ 从 docs/wiki-schema.md §2.1 的受控因子词表里组合信号。                     │
# │   选股 SLOT → select_stocks   择时 SLOT → market_ok                        │
# │   风控 SLOT → risk_exits       仓位 SLOT → target_weights                  │
# │ 「勿改区块」(FROZEN) 由 research/harness.md 冻结：基准/手续费/滑点。         │
# │ 平台级常量（区间/基础资金/频率）由 Pipeline 2 设定，不在本文件。            │
# └─────────────────────────────────────────────────────────────────────────┘

import datetime


# ============================================================================
# 回测初始化
# ============================================================================
def initialize(context):
    set_params()
    set_variables()
    _set_frozen_harness()   # 勿改：见 research/harness.md


def set_params():
    # —— 可调参数（agent 可在因子槽位相关范围内变异）——
    g.N = 10            # 持仓数目
    g.tc = 20           # 调仓间隔（交易日），≈ 月度
    g.min_list_days = 250   # 次新过滤（自然日），真实性过滤，勿降到更低
    g.ma_market = 20    # 大盘择时均线周期（沪深300）


def set_variables():
    g.t = 0             # 回测运行天数计数
    g.if_trade = False  # 当日是否调仓


def _set_frozen_harness():
    # ============ FROZEN（勿改）：research/harness.md epoch 1 ============
    set_option('use_real_price', True)
    log.set_level('order', 'error')
    set_benchmark('000300.XSHG')                                   # 仅显示用，不影响 objective
    set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
    set_slippage(FixedSlippage(0))                                 # 零滑点（见 harness.md §2 警示）
    # ===================================================================


# ============================================================================
# 每天开盘前：按调仓周期决定今天是否换仓
# ============================================================================
def before_trading_start(context):
    g.if_trade = (g.t % g.tc == 0)
    g.t += 1


# ============================================================================
# 主逻辑
# ============================================================================
def handle_data(context, data):
    # 风控 SLOT 每日生效（即使非调仓日）
    for s in risk_exits(context):
        _safe_sell(context, s)

    if not g.if_trade:
        return

    # 择时 SLOT：不满足则清仓空仓，跳过选股
    if not market_ok(context):
        for s in list(context.portfolio.positions.keys()):
            _safe_sell(context, s)
        return

    # 选股 SLOT → 仓位 SLOT
    targets = select_stocks(context)
    weights = target_weights(context, targets)

    # 先卖出不在目标里的
    for s in list(context.portfolio.positions.keys()):
        if s not in weights:
            _safe_sell(context, s)
    # 再按目标权重买入/调仓
    total = context.portfolio.total_value
    for s, w in weights.items():
        _safe_order_value(context, s, total * w)


# ============================================================================
# 因子槽位（agent 变异区）——baseline 只实现「选股=最小市值 / 仓位=等权」，
# 择时与风控为直通(pass-through)。变异 = 在这些函数里按受控词表增删/替换/调参。
# ============================================================================

# —— 选股 SLOT（选股因子：规模价值·小市值 + 质量基本面·国九条）——
# 变异(jul4-001)：在最小市值上叠加「国九条」质量过滤（净利润>0 且 营业收入>1亿）。
# 源：[[小市值因子]] 绩效横评「强过滤者夏普最高/回撤最低」；[[aaba7575]] 国九族。
def select_stocks(context):
    stocks = _investable_universe(context)
    q = (query(valuation.code, valuation.market_cap)
         .filter(valuation.code.in_(stocks),
                 income.net_profit > 0,             # 国九条：盈利
                 income.operating_revenue > 1e8)    # 国九条：营收>1亿
         .order_by(valuation.market_cap.asc())
         .limit(g.N))
    df = get_fundamentals(q)
    return list(df['code'])


# —— 择时 SLOT（择时因子：趋势均线·大盘 MA 防御）——
# 变异(jul4-002)：叠加大盘均线择时——沪深300 收盘跌破 MA(g.ma_market) 则空仓。
# 源：[[择时-均线]]；[[小市值因子]]「无择时+无止损是高回撤主因」；2024-01 微盘踩踏应可规避。
def market_ok(context):
    idx = '000300.XSHG'
    hist = attribute_history(idx, g.ma_market + 1, '1d', ['close'], df=False)['close']
    if len(hist) < g.ma_market:
        return True
    return hist[-1] > hist[-g.ma_market:].mean()


# —— 风控 SLOT（风控因子：止损线/止盈/大盘趋势/盈利保护/… 见 harness/wiki 枚举）——
def risk_exits(context):
    """返回需强制卖出的标的列表。baseline：无风控，返回空。"""
    return []


# —— 仓位 SLOT（仓位因子：等权/动态持仓数/满仓单标的/流动性配权/预留资金）——
def target_weights(context, stocks):
    """返回 {code: weight}，weight 求和≤1。baseline：等权满仓。"""
    if not stocks:
        return {}
    w = 1.0 / len(stocks)
    return {s: w for s in stocks}


# ============================================================================
# 工具（真实性过滤 + 安全下单）——research/harness.md §3 强制，勿移除
# ============================================================================
def _investable_universe(context):
    """全 A 股，剔除 ST/*ST、停牌、上市不足 g.min_list_days。"""
    cd = get_current_data()
    sec_info = get_all_securities(types=['stock'], date=context.current_dt)
    cutoff = (context.current_dt - datetime.timedelta(days=g.min_list_days)).date()
    out = []
    for s in sec_info.index:
        if cd[s].is_st or cd[s].paused:
            continue
        if sec_info.loc[s, 'start_date'] > cutoff:
            continue
        out.append(s)
    return out


def _safe_order_value(context, s, value):
    """涨停不买。"""
    cd = get_current_data()
    px = cd[s].last_price
    if px is None or (cd[s].high_limit and px >= cd[s].high_limit):
        return
    order_target_value(s, value)


def _safe_sell(context, s):
    """跌停不强卖。"""
    if s not in context.portfolio.positions:
        return
    cd = get_current_data()
    px = cd[s].last_price
    if px is not None and cd[s].low_limit and px <= cd[s].low_limit:
        return
    order_target_value(s, 0)
