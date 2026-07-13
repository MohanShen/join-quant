# Research candidate SMOKE TEST — join-quant autoresearch (epoch 2)
# expId:    jul12-022-smoke  (Arc-4 STEP-0 plumbing check — NOT a strategy)
# purpose:  confirm Pipeline 2 runs a 2-subportfolio (stock + index_futures) strategy to
#           `completed` under the frozen harness OVERRIDE, with a short IC futures order.
#           P&L is irrelevant; only that it COMPLETES without error.
# harness:  research/harness.md (冻结成本 OVERRIDE 见文末; 迭代只跑 --window train)

import datetime


def initialize(context):
    _set_frozen_harness()   # 勿改：见 research/harness.md §2
    sc = context.portfolio.starting_cash
    set_subportfolios([
        SubPortfolioConfig(cash=sc * 0.7, type='stock'),
        SubPortfolioConfig(cash=sc * 0.3, type='index_futures'),
    ])
    run_daily(trade, time='9:35', reference_security='000300.XSHG')


def _set_frozen_harness():
    # ============ FROZEN（勿改）：research/harness.md §2 ============
    set_option('use_real_price', True)
    log.set_level('order', 'error')
    set_benchmark('000300.XSHG')
    set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
    set_slippage(FixedSlippage(0))
    # ===================================================================


def trade(context):
    # (b) 股票子仓(index 0)：买一只流动 ETF 510300，目标 90% 子仓市值
    stock_sub = context.subportfolios[0]
    order_target_value('510300.XSHG', stock_sub.total_value * 0.9, pindex=0)

    # (c) 期货子仓(index 1)：做空 1 手 IC 主力合约，处理主力换月
    fut = get_dominant_future('IC')
    if not fut:
        return
    fsub = context.subportfolios[1]
    # 换月：平掉非主力的旧空单
    for code in list(fsub.short_positions.keys()):
        if code != fut:
            order_target(code, 0, side='short', pindex=1)
    # 维持 1 手主力空单
    order_target(fut, 1, side='short', pindex=1)


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
