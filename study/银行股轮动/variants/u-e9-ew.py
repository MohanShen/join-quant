# Clone from JoinQuant
# postId: 2a3235229fdfd62a917c78a5d8236c15
# backtestId: 1c770f0f1cb42e87e17b574b39aaba59
# title: 自己搭建的一个10年230%收益率的银行股策略

# 聚宽策略：银行股精简轮动增强版（基于139%收益策略优化）
# 核心：PB + 股息率 + 动量（权重30/30/40），布林择时，250日线动态仓位
# 止损放宽至-12%，持仓3只分散，每周固定调仓

from jqdata import finance
import datetime
import pandas as pd

def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)

    set_order_cost(OrderCost(open_tax=0, close_tax=0.0005,
                             open_commission=0.000095, close_commission=0.000095,
                             close_today_commission=0, min_commission=1), type='stock')

    g.stocks = ['601398.XSHG', '601939.XSHG', '601288.XSHG', '601988.XSHG', '600036.XSHG']
    g.max_holdings = 3          # 分散持仓
    g.min_holdings = 2
    g.buy_prices = {}

    # 每周五调仓
    run_weekly(rebalance, weekday=5, time='close')


def calc_dividend_yield(stock, context):
    """计算TTM股息率"""
    start_date = context.current_dt - datetime.timedelta(days=365)
    q = query(
        finance.STK_XR_XD.code,
        finance.STK_XR_XD.bonus_ratio_rmb
    ).filter(
        finance.STK_XR_XD.code == stock,
        finance.STK_XR_XD.a_bonus_date >= start_date
    )
    df = finance.run_query(q)
    if df.empty:
        return 0.0
    total_div = df['bonus_ratio_rmb'].sum() / 10.0
    if total_div <= 0:
        return 0.0
    df_price = get_price(stock, end_date=context.current_dt, frequency='daily',
                         fields=['close'], count=1, skip_paused=True, fq=None)
    if len(df_price) == 0:
        return 0.0
    price = df_price['close'].iloc[-1]
    if price <= 0:
        return 0.0
    return total_div / price


def get_ma250(stock, context):
    df = get_price(stock, end_date=context.current_dt, frequency='daily',
                   fields=['close'], count=260, skip_paused=True)
    if len(df) >= 250:
        return df['close'].rolling(250).mean().iloc[-1]
    return None


def get_bollinger(stock, context, period=20, num_std=2):
    df = get_price(stock, end_date=context.current_dt, frequency='daily',
                   fields=['close'], count=period+5, skip_paused=True)
    if len(df) < period:
        return None
    close = df['close']
    ma = close.rolling(period).mean()
    std = close.rolling(period).std()
    return {
        'ma': ma.iloc[-1],
        'close': close.iloc[-1]
    }


def rebalance(context):
    # u-e9-ew: equal-weight 20% x 5, weekly Friday close. No score/Bollinger/MA250/stop.
    tv = context.portfolio.total_value
    for s in g.stocks:
        order_target_value(s, tv * 0.20)


# ===== AUTORESEARCH NORMALIZATION OVERRIDE (appended; strategies/ file untouched) =====
# harness/harness.md §2 — force the frozen execution settings regardless of what the
# raw strategy sets, even if it re-sets costs every bar. Values are pinned in
# harness/config/epoch-<n>.json; utils/harness-config.js --verify checks this block
# still matches, because Python running on JQ's servers cannot read that JSON.
__jq_set_slippage = set_slippage
def set_slippage(*a, **k):
    __jq_set_slippage(FixedSlippage(0))
__jq_set_commission = set_commission
def set_commission(*a, **k):
    __jq_set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
# epoch 4: set_commission does NOT govern funds, so 170 held strategies were running
# ETF trades on their own costs. Pin the fund table too, and neutralise re-sets.
# epoch 6: it does not govern STOCKS either. JQ deprecated set_commission in favour of
# set_order_cost, so a strategy's own type='stock' call won outright and 95 of 215 held
# strategies were being charged their AUTHOR's fees. Measured by probe: a 5%/side stock
# commission injected into int-001 moved total return +64.44% -> -11.33% (-75.77pp), i.e.
# the bench had no control over stock fees at all. Both tables are now pinned, and the
# fall-through forwards only the types we do not model (futures, mmf, ...).
# Guarded: unlike set_slippage/set_commission, set_order_cost is NOT bound at module
# scope in every JQ runtime — rebinding it unguarded raised NameError at import and
# the whole strategy came back compile-error.
try:
    __jq_set_order_cost = set_order_cost
    def __jq_cost_type(a, k):
        t = k.get('type')
        if t is None and len(a) > 1:
            t = a[1]
        return t
    def set_order_cost(*a, **k):
        __t = __jq_cost_type(a, k)
        if __t == 'fund':
            __jq_set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0, min_commission=5), type='fund')
        elif __t == 'stock':
            __jq_set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0.001, min_commission=5), type='stock')
        else:
            __jq_set_order_cost(*a, **k)
except NameError:
    pass
try:
    __jq_orig_initialize = initialize
    def initialize(context):
        __jq_orig_initialize(context)
        set_option('use_real_price', True)
        # epoch 4 pins, applied AFTER the strategy's own initialize so they win
        set_option('avoid_future_data', True)
        set_option('order_volume_ratio', 0.05)
        set_slippage(FixedSlippage(0))
        set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
        try:
            set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0, min_commission=5), type='fund')
        except Exception:
            pass
        # epoch 6: pin the stock table too, AFTER the strategy's own initialize so it wins
        # even when the strategy set its costs there rather than at module scope.
        try:
            set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0.001, min_commission=5), type='stock')
        except Exception:
            pass
except NameError:
    pass
# ===== END OVERRIDE =====
