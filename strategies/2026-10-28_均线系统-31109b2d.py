# Clone from JoinQuant
# postId: 31109b2d1b4944b1aabd9056aea39a36
# backtestId: 0d4f14457450ea4cb4a1366c9725f665
# title: 均线系统

import talib
import numpy as np
import pandas as pd
import scipy as sp

def initialize(context):
    g.security = '159915.XSHE'
    g.m = 1
    g.n = 42
    g.lag = 100
    g.state = 0
    g.algo = 'GMA'
    set_universe([g.security])
    set_commission(PerTrade(buy_cost=0.0008, sell_cost=0.0013, min_cost=5))

def getMA(x, lag, algo):
    x=x[-lag:]
    if algo == 'SMA':
        return mean(x)
    elif algo == 'GMA':
        mu = 1.0
        for el in x:
            mu = mu*el
        return np.power(mu,1.0/lag);

def handle_data(context, data):
    h = attribute_history(g.security,g.lag,'1d',('open', 'close', 'high', 'low', 'volume'),skip_paused=True)
    p = h['close'].values
    fast = getMA(p, g.m, g.algo)
    slow = getMA(p, g.n, g.algo)
    
    signal = fast-slow
    
    cash = context.portfolio.cash
    
    if g.state == 0:
        if signal > 0:
            order_target_value(g.security, cash)
            g.state = 1
    if g.state == 1:
        if signal < 0:
            order_target_value(g.security, 0)
            g.state = 0
            
    print g.state
        
    record(fast = fast)
    record(slow = slow)
