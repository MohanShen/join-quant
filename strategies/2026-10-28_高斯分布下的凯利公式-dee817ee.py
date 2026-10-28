# Clone from JoinQuant
# postId: dee817eee2b90d0d4f5ff355c24ae80d
# backtestId: 3747ca39f078e25fe03b7cbebb0bdf1f
# title: 高斯分布下的凯利公式

import numpy as np
import scipy as sp
import pandas as pd

def initialize(context):

    context.asset = u'510300.XSHG'
    set_universe(context.asset)
    set_commission(PerTrade(buy_cost=0.0008, sell_cost=0.0013, min_cost=5))

    context.w = 0
    context.lag = 24

    run_daily(rebalance,time='open')

def handle_data(context, data):
    pass
    
def rebalance(context):
    
    h = attribute_history(context.asset,context.lag,'1d',
                          ('open', 'close', 'high', 'low', 'volume'),
                          skip_paused=True)
                          
    p = h['close']
    ret = p.pct_change().dropna().values

    r = np.mean(ret)
    var = np.var(ret)
    
    normalizer = len(ret)
    var_scaled = var*normalizer
    w = Kelly(r, var_scaled)
    
    value = context.portfolio.portfolio_value
    order_target_value(context.asset, value*w)

def Kelly(r, var):
    w_opt = r/var
    if w_opt<0:
        w_opt = 0
    if w_opt>1:
        w_opt = 1

    return w_opt
    
    return r, C