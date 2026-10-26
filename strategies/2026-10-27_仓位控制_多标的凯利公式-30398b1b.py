# Clone from JoinQuant
# postId: 30398b1b2428da4a3c77efca37bd83ba
# backtestId: 8beaafbd84bedbda28b82363e57fcb6b
# title: 仓位控制：多标的凯利公式

import numpy as np
import scipy as sp
import pandas as pd
import math
import scipy.optimize

def initialize(context):

    ETF = [u'510050.XSHG',
           u'510300.XSHG',
           u'510500.XSHG',
           u'511010.XSHG']
           
    context.assets = ETF
    set_universe(context.assets)
    set_commission(PerTrade(buy_cost=0.0008, sell_cost=0.0013, min_cost=5))

    context.w = []
    context.lag = 24

    run_daily(rebalance,time='open')

def handle_data(context, data):
    pass
    
def rebalance(context):
    
    h = history(context.lag,'1d','close',context.assets, df=True)
    ret = h.pct_change().dropna().values
    ret = ret.transpose()

    r, C = getReturnCovariance(ret, context)
    w = Kelly(r, C)
    
    print w
    print r
    trade(w, context)


def trade(w, context):
    
    for i in range(len(w)):
        if math.isnan(w[i]):
            return
    
    value = context.portfolio.portfolio_value
    # first allocation
    if len(context.w) == 0:
        for i in range(len(context.assets)):
            order_target_value(context.assets[i], value*w[i])
    # update weights
    else:
        # sell first
        for i in range(len(context.assets)):
            if w[i]<context.w[i]:
                order_target_value(context.assets[i], value*w[i])
        # then buy
        for i in range(len(context.assets)):
            if w[i]>=context.w[i]:
                order_target_value(context.assets[i], value*w[i])

def Kelly(r, C):
    numAsset = len(r)
    w = 1.0*np.ones(numAsset)/numAsset
    
    bound = [(0,1) for i in range(numAsset)]
    constrain = ({'type':'eq', 'fun': lambda w: sum(w)-1.0 })
    
    result = sp.optimize.minimize(objFunc, w, (r, C), method='SLSQP', constraints=constrain, bounds=bound)  
    w_opt = result.x
        
    for i in range(numAsset):
        if w_opt[i] <0.05:
            w_opt[i] = 0.0
            
    w_opt = w_opt/sum(w_opt)

    return w_opt
    
def objFunc(w, r, C):
    val = 0.5*dot(dot(w, C), w)-dot(r,w)
    return val

def getReturnCovariance(ret, context): 
    numAsset, numData = ret.shape
    
    r = np.zeros(numAsset)
    for i in range(numAsset):
        r[i] = np.mean(ret[i,:])
        
    C = cov(ret)
    
    return r, C