# Clone from JoinQuant
# postId: 7d1012a5369fc50322e45a4a9847ca4b
# backtestId: f0dd2f4ef113ad19fb86541b7c25661c
# title: 【策略研发】三进兵策略与研究报告

"""
说明：
所谓的三进兵，是指三条EMA均线组合的策略javascript:void(0);
交易原则：
系统由三条EMA均线组合而成，分别为小均线、中均线、大均线
当小均线金叉大均线、并且中均线位于大均线下方时，买入
当小均线死叉中均线，并且中均线位于大均线上方时，卖出
止损：当买入后，如果收盘价跌破中均线，止损
选股：本策略里没有做自动选股，而是手动挑选了一些
在研究里做了更多股票的研究，发现本策略并不是适合所有的股票的
所以，各位宽友如果有想法，可在此基础上做迭代，并分享出来，展示你的才华
"""

import numpy as np
import pandas as pd
import datetime
from jqdata import *
from jqlib.technical_analysis import *

def initialize(context):
    # 所谓的三进兵，就是这里的三个Ma线
    g.ma_min = 5
    g.ma_med = 20
    g.ma_max = 60
    
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 设置成交量比例
    set_option('order_volume_ratio', 0.25)
    # 日志过滤
    log.set_level('order', 'error')
    # 为股票设定滑点为百分比滑点
    set_slippage(PriceRelatedSlippage(0.00246),type='stock')
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    __pool = get_index_stocks('399006.XSHE', date='2021-12-31')  # u-1dc: pre-registered pool rule, ranks 11-15 by cap, data ends before TRAIN
    __pool_df = get_fundamentals(query(valuation.code, valuation.market_cap).filter(valuation.code.in_(__pool)).order_by(valuation.market_cap.desc()).limit(15), date='2021-12-31')
    g.stokcs_pool = list(__pool_df['code'])[10:15]
    g.hold_count = 5
    run_daily(trade_func, 'open') 

def trade_func(context):
    # u-1dc: buy-and-hold control on the u-1 pool (q-1 hold form: equal weight on the first bar, never trade again)
    if getattr(g, 'bought', False):
        return
    for stock in g.stokcs_pool:
        order_target_value(stock, context.portfolio.total_value / len(g.stokcs_pool))
    g.bought = True


def after_trading_end(context):
    log.info('='*50)

# 获取ma值
def get_ma(stock, ma_value, end_dt):
    price = get_price(security=stock, 
                      end_date=end_dt, 
                      frequency='daily', 
                      fields=['close'], 
                      skip_paused=False, 
                      fq='pre', 
                      count=ma_value+10)['close']
    ma = price[-ma_value:].mean()
    return ma

# 获取ema值
def get_ema(stock, ma_value, end_dt):
    ema = EMA(stock, check_date=end_dt, timeperiod=ma_value)
    return ema[stock]

# 判断是否出现买入信息
def is_buy(stock, yesterday, before_yesterday, *ema):
    ma_min = ema[0]
    ma_med = ema[1]
    ma_max = ema[2]
    
    # 求出上一个交易日的ma_min，ma_med,ma_max的值
    y_ma_min_value = get_ema(stock, ma_min, yesterday)
    y_ma_med_value = get_ema(stock, ma_med, yesterday)
    y_ma_max_value = get_ema(stock, ma_max, yesterday)

    # 求出上上个交易日的ma_min，ma_med,ma_max的值
    by_ma_min_value = get_ema(stock, ma_min, before_yesterday)
    by_ma_med_value = get_ema(stock, ma_med, before_yesterday)
    by_ma_max_value = get_ema(stock, ma_max, before_yesterday)

    if (y_ma_min_value > y_ma_max_value) and (by_ma_min_value < by_ma_max_value) and (y_ma_med_value < y_ma_max_value):
        return True
    else:
        return False
    
# 判断是否有卖出信息
def is_sell(stock, yesterday, before_yesterday, *ema):
    ma_min = ema[0]
    ma_med = ema[1]
    ma_max = ema[2]
    
    # 求出上一个交易日的ma_min，ma_med,ma_max的值
    y_ma_min_value = get_ema(stock, ma_min, yesterday)
    y_ma_med_value = get_ema(stock, ma_med, yesterday)
    y_ma_max_value = get_ema(stock, ma_max, yesterday)

    # 求出上上个交易日的ma_min，ma_med,ma_max的值
    by_ma_min_value = get_ema(stock, ma_min, before_yesterday)
    by_ma_med_value = get_ema(stock, ma_med, before_yesterday)
    by_ma_max_value = get_ema(stock, ma_max, before_yesterday)

    if (y_ma_min_value > y_ma_med_value) and (by_ma_min_value < by_ma_med_value) and (y_ma_med_value > y_ma_max_value):
        return True
    else:
        return False
        
        
# 判断是否有止损信息
def is_loss(stock, yesterday, *ema):
    ma_min = ema[0]
    ma_med = ema[1]
    ma_max = ema[2]
    
    # 昨日收盘价
    close = get_price(security=stock, 
                          end_date=yesterday,
                          frequency='daily', 
                          fields=['open','close'], 
                          skip_paused=False, 
                          fq='pre', 
                          count=10)['close'][-1] 
    
    
    # 求出上一个交易日的ma_min，ma_med,ma_max的值
    y_ma_min_value = get_ema(stock, ma_min, yesterday)
    y_ma_med_value = get_ema(stock, ma_med, yesterday)
    y_ma_max_value = get_ema(stock, ma_max, yesterday)
    
    if (close < y_ma_med_value) and (y_ma_med_value < y_ma_max_value):
        return True
    else:
        return False

    

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
