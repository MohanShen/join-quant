# Research candidate — join-quant autoresearch (epoch 2)
# expId:    jul12-016  (idea-13 Arc-2 = jul12-015 + 择时·趋势均线 国证2000 MA60 全书防御)
# baseExpId: jul12-015  (min-cap 周度轮动 + -15% 日度止损; TRAIN score 0.2366, sharpe 1.67 DQ, maxdd 22%)
# harness:  research/harness.md (冻结成本 OVERRIDE 见文末; 迭代只跑 --window train)
# design:   min-cap 周度轮动 + 风控·个股止损(-15% 日检, 继承) + 择时·MA60 大盘防御:
#           调仓前若 399303 收盘 < MA60 则清仓空仓本轮不买(慢均线,少 MA20 抖动).
#           universe_size=400 -> hold_count=10 等权.
# filters:  §3 强制真实性 — 剔除 ST/*ST/退, 停牌, 次新(<250自然日), 涨停开盘不买/跌停不卖;
#           另剔除 688* (科创板) 与 30* (创业板 300/301).
# note:     Arc-2 目标: 过 sharpe>=2.5; best-so-far score to beat = 0.2366 (jul12-015).
#           观察 MA60 是否削掉 2022 持续下行段 -> maxdd 远低于 22% 且 sharpe 跳向 2.5, annual 保住.
#           证伪: annual 崩(2023震荡仍抖) 或 sharpe<2.5+annual保住(太慢滞后) -> 决定 MA120 vs 选股倾斜.
#           ⚠ 小市值轮动换手偏高, 零滑点下 objective 偏高估 (harness §2).

import datetime


# ============================================================================
# 回测初始化
# ============================================================================
def initialize(context):
    set_params()
    _set_frozen_harness()   # 勿改：见 research/harness.md §2
    # 周度调仓：每周第 1 个交易日开盘换仓
    run_weekly(rebalance, weekday=1, time='open', reference_security='000300.XSHG')
    # 风控·止损：每日 14:50 检查个股止损线 -15%
    run_daily(stop_loss_check, time='14:50', reference_security='000300.XSHG')


def set_params():
    g.universe_size = 400   # 初筛股票池：按市值升序取最小的 400 只
    g.hold_count = 10       # 目标持仓数（等权）
    g.min_list_days = 250   # 次新过滤（自然日），真实性过滤，勿降


def _set_frozen_harness():
    # ============ FROZEN（勿改）：research/harness.md §2 ============
    set_option('use_real_price', True)
    log.set_level('order', 'error')
    set_benchmark('000300.XSHG')                                   # 仅显示用，不影响 objective
    set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
    set_slippage(FixedSlippage(0))                                 # 零滑点（见 harness.md §2 警示）
    # ===================================================================


# ============================================================================
# 主逻辑：周度最小市值等权轮动
# ============================================================================
def rebalance(context):
    # 择时·趋势均线：国证2000 收盘 < MA60 -> 大盘防御，清仓空仓，本轮不买
    h = attribute_history('399303.XSHE', 60, '1d', ['close'])
    ma60 = h['close'].mean()
    cur = h['close'][-1]
    if cur < ma60:
        for s in list(context.portfolio.positions.keys()):
            _safe_sell(context, s)
        return

    targets = select_stocks(context)

    # 先卖出不在目标里的（跌停不强卖）
    for s in list(context.portfolio.positions.keys()):
        if s not in targets:
            _safe_sell(context, s)

    if not targets:
        return

    # 再等权买入/调仓（涨停开盘不买）
    value_each = context.portfolio.total_value / g.hold_count
    for s in targets:
        _safe_order_value(context, s, value_each)


def select_stocks(context):
    """按市值升序取最小 g.universe_size 只 -> §3 真实性/板块过滤 -> 取最小 g.hold_count 只。"""
    q = (query(valuation.code, valuation.market_cap)
         .order_by(valuation.market_cap.asc())
         .limit(g.universe_size))
    df = get_fundamentals(q)
    pool = list(df['code'])   # 已按市值升序
    filtered = _apply_truth_filters(context, pool)
    return filtered[:g.hold_count]


# ============================================================================
# 风控·止损 —— 每日 14:50 个股 -15% 止损（跌停不卖）
# ============================================================================
def stop_loss_check(context):
    cd = get_current_data()
    for s, pos in list(context.portfolio.positions.items()):
        if pos.sellable_amount <= 0:
            continue
        px = cd[s].last_price
        if px is None or pos.avg_cost <= 0:
            continue
        # 跌停不卖
        if cd[s].low_limit and px <= cd[s].low_limit:
            continue
        ret = (px - pos.avg_cost) / pos.avg_cost
        if ret <= -0.15:
            order_target_value(s, 0)


# ============================================================================
# 真实性过滤 + 安全下单 —— research/harness.md §3 强制，勿移除
# ============================================================================
def _apply_truth_filters(context, stocks):
    """剔除 ST/*ST/退、停牌、次新(<g.min_list_days)、科创板(688*)、创业板(30*)。
    涨停开盘不买 / 跌停不卖 在下单函数中处理。保持输入的市值升序。"""
    cd = get_current_data()
    sec_info = get_all_securities(types=['stock'], date=context.current_dt)
    cutoff = (context.current_dt - datetime.timedelta(days=g.min_list_days)).date()
    out = []
    for s in stocks:
        # 板块剔除：科创板 688*、创业板 300*/301*
        if s.startswith('688') or s.startswith('30'):
            continue
        info = cd[s]
        if info.is_st or info.paused or ('退' in info.name):
            continue
        # 次新：上市不足 g.min_list_days 自然日
        if s not in sec_info.index:
            continue
        if sec_info.loc[s, 'start_date'] > cutoff:
            continue
        out.append(s)
    return out


def _safe_order_value(context, s, value):
    """涨停开盘不买。"""
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


# ===== AUTORESEARCH NORMALIZATION OVERRIDE (appended; strategies/ file untouched) =====
# research/harness.md §2 — force zero slippage + frozen commission regardless of
# what the raw strategy sets, even if it re-sets costs every bar.
__jq_set_slippage = set_slippage
def set_slippage(*a, **k):
    __jq_set_slippage(FixedSlippage(0))
__jq_set_commission = set_commission
def set_commission(*a, **k):
    __jq_set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
try:
    __jq_orig_initialize = initialize
    def initialize(context):
        __jq_orig_initialize(context)
        set_option('use_real_price', True)
        set_slippage(FixedSlippage(0))
        set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
except NameError:
    pass
# ===== END OVERRIDE =====
