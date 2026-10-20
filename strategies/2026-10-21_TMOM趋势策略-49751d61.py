# Clone from JoinQuant
# postId: 49751d61952b3ab1e8d939ea3edfecdc
# backtestId: d6f8a061913c8687bd0f35445a562d5c
# title: TMOM趋势策略

import talib
import numpy as np
import pandas as pd
import scipy as sp

def initialize(context):
    g.security = '159915.XSHE'
    g.n = 24
    g.rf = 0.02
    g.lag = 100
    g.state = 0
    set_universe([g.security])
    set_commission(PerTrade(buy_cost=0.0008, sell_cost=0.0013, min_cost=5))

def getTMOM(x, lag, rf):
    x=x[-lag:]
    tmom = (x[-1]/x[1]-1)-g.rf
    return tmom

def handle_data(context, data):
    h = attribute_history(g.security,g.lag,'1d',
                          ('open', 'close', 'high', 'low', 'volume'),
                          skip_paused=True)
                          
    p = h['close'].values

    tmom = getTMOM(p, g.n, g.rf)
    
    signal = tmom > 0
    
    cash = context.portfolio.cash
    
    if g.state == 0:
        if signal ==True:
            order_target_value(g.security, cash)
            g.state = 1
    if g.state == 1:
        if signal == False:
            order_target_value(g.security, 0)
            g.state = 0
            
    print tmom
        
    record(TMOM = tmom)
