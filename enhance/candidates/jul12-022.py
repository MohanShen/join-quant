# Research candidate — join-quant autoresearch (epoch 2)
# expId:    jul12-022  (idea-19 NEW baseline Arc-4: 市场中性 微盘多头 − IC 空头对冲)
# baseExpId: (none — fresh strategy; long engine reuses jul12-013)
# harness:  research/harness.md (冻结成本 OVERRIDE 见文末; 迭代只跑 --window train)
# design:   双子仓 [stock 0.7 / index_futures 0.3]. 多头(子仓0): 市值最小 400 -> §3 真实性过滤
#           -> 最小 10 只等权, run_weekly 调仓. 空头对冲(子仓1): 做空 IC 主力合约, 名义规模≈多头
#           市值 (beta≈1 首版), 主力换月时滚动. Factors §2.1: 选股·规模价值[小市值];
#           仓位[等权10 + 股指期货beta对冲]; concept [[期货与套利]].
# filters:  §3 强制真实性 — 剔除 ST/*ST/退, 停牌, 次新(<250自然日), 涨停开盘不买/跌停不卖;
#           另剔除 688* (科创板) 与 30* (创业板 300/301).
# note:     ESTABLISH Arc-4 参考 objective(TRAIN); 无 bar to beat. gate sharpe>=2.5 仍计算.
#           ⚠⚠ 强制真实性红线: 冻结零滑点 + 股票手续费 **不覆盖期货**; 对冲拖累(滑点/手续费/基差/
#           换月) 被系统性低估 -> objective 偏乐观, 非净可实现. 另: IC(中证500 中盘)对微盘多头存在
#           残余 basis beta, 对冲不完美. 两点必须写进实验页 flags.

import datetime


# ============================================================================
# 回测初始化
# ============================================================================
def initialize(context):
    set_params()
    _set_frozen_harness()   # 勿改：见 research/harness.md §2
    sc = context.portfolio.starting_cash
    set_subportfolios([
        SubPortfolioConfig(cash=sc * 0.7, type='stock'),          # 子仓0：微盘多头
        SubPortfolioConfig(cash=sc * 0.3, type='index_futures'),  # 子仓1：IC 空头保证金
    ])
    run_weekly(rebalance, weekday=1, time='open', reference_security='000300.XSHG')


def set_params():
    g.universe_size = 400   # 初筛：市值升序最小 400 只
    g.hold_count = 10       # 多头持仓数（等权）
    g.min_list_days = 250   # 次新过滤（自然日）
    g.ic_mult = 200         # IC 合约乘数：200 元/点


def _set_frozen_harness():
    # ============ FROZEN（勿改）：research/harness.md §2 ============
    set_option('use_real_price', True)
    log.set_level('order', 'error')
    set_benchmark('000300.XSHG')                                   # 仅显示用，不影响 objective
    set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
    set_slippage(FixedSlippage(0))                                 # 零滑点（见 harness.md §2；不覆盖期货）
    # ===================================================================


# ============================================================================
# 主逻辑：周度 微盘多头等权 + IC 空头 beta≈1 对冲
# ============================================================================
def rebalance(context):
    # ---- 多头腿（子仓0）----
    targets = select_stocks(context)
    stock_sub = context.subportfolios[0]

    # 先卖出不在目标里的（跌停不强卖）
    for s in list(stock_sub.long_positions.keys()):
        if s not in targets:
            _safe_sell(s)

    long_value = 0.0
    if targets:
        each = stock_sub.total_value / g.hold_count
        for s in targets:
            _safe_order_value(s, each)
        long_value = each * len(targets)   # 计划部署的多头市值

    # ---- 空头对冲腿（子仓1）：做空 IC 主力，名义≈多头市值 ----
    fut = get_dominant_future('IC')
    fsub = context.subportfolios[1]
    if not fut:
        return

    # 换月：平掉非主力旧空单
    for code in list(fsub.short_positions.keys()):
        if code != fut:
            order_target(code, 0, side='short', pindex=1)

    # IC 价格 -> 目标空头手数（名义 ≈ 多头市值, beta≈1）
    price = _future_price(fut)
    if price is None or price <= 0 or long_value <= 0:
        contracts = 0
    else:
        notional_per = price * g.ic_mult
        contracts = int(round(long_value / notional_per))
    order_target(fut, contracts, side='short', pindex=1)


def select_stocks(context):
    """市值升序取最小 g.universe_size 只 -> §3 真实性/板块过滤 -> 取最小 g.hold_count 只。"""
    q = (query(valuation.code, valuation.market_cap)
         .order_by(valuation.market_cap.asc())
         .limit(g.universe_size))
    df = get_fundamentals(q)
    pool = list(df['code'])   # 已按市值升序
    filtered = _apply_truth_filters(context, pool)
    return filtered[:g.hold_count]


def _future_price(fut):
    """取期货最近收盘价用于对冲手数计算。"""
    try:
        cd = get_current_data()
        px = cd[fut].last_price
        if px and px > 0:
            return px
    except Exception:
        pass
    try:
        hp = attribute_history(fut, 5, '1d', ['close'], df=False)
        return hp['close'][-1]
    except Exception:
        return None


# ============================================================================
# 真实性过滤 + 安全下单（子仓0 多头）—— research/harness.md §3 强制，勿移除
# ============================================================================
def _apply_truth_filters(context, stocks):
    """剔除 ST/*ST/退、停牌、次新(<g.min_list_days)、科创板(688*)、创业板(30*)。保持市值升序。"""
    cd = get_current_data()
    sec_info = get_all_securities(types=['stock'], date=context.current_dt)
    cutoff = (context.current_dt - datetime.timedelta(days=g.min_list_days)).date()
    out = []
    for s in stocks:
        if s.startswith('688') or s.startswith('30'):
            continue
        info = cd[s]
        if info.is_st or info.paused or ('退' in info.name):
            continue
        if s not in sec_info.index:
            continue
        if sec_info.loc[s, 'start_date'] > cutoff:
            continue
        out.append(s)
    return out


def _safe_order_value(s, value):
    """涨停开盘不买（子仓0）。"""
    cd = get_current_data()
    px = cd[s].last_price
    if px is None or (cd[s].high_limit and px >= cd[s].high_limit):
        return
    order_target_value(s, value, pindex=0)


def _safe_sell(s):
    """跌停不强卖（子仓0）。"""
    cd = get_current_data()
    px = cd[s].last_price
    if px is not None and cd[s].low_limit and px <= cd[s].low_limit:
        return
    order_target_value(s, 0, pindex=0)


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
