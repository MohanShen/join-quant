# Clone from JoinQuant
# postId: 4da8f69689131ea8117e500e6be84621
# backtestId: e1e1c2bca62ac877e736b4943671c730
# title: 带收益预测的Markowitz动态平衡策略

import numpy as np
import pandas as pd
import scipy as sp
import scipy.optimize
import datetime
import talib

from scipy import linalg as sla
from scipy import spatial

def initialize(context):
    benchmarkList = ['000300.XSHG','510050.XSHG','000300.XSHG','510050.XSHG']
    benchmark = benchmarkList[0]
    stocklist = get_index_stocks('000300.XSHG')
    
    set_commission(PerTrade(buy_cost=0.0008, sell_cost=0.0013, min_cost=5))

    assets = [u'159919.XSHE',u'159908.XSHE',u'159902.XSHE']
    set_universe(assets)
    
    g.assets = assets
    g.lag = 200
    
    g.lastRebalanceDate =  datetime.datetime.strptime('2010-01-01', '%Y-%m-%d')

    g.position = np.zeros(len(g.assets))
    g.w_low = 0.0
    g.w_up = 1.0
    
def handle_data(context, data):
    currentDate = context.current_dt
    deltaDays = (currentDate - g.lastRebalanceDate).days
    
    h = history(g.lag, unit='1d', field='close', security_list=None, df=True)
    
    
    dailyReturns = h.pct_change().dropna()
    dailyReturns = np.array(dailyReturns)
    r, C = getReturnCovariance(dailyReturns)
    
    print r
    
    for i in range(len(g.assets)):
        r[i] = getReturn(h[g.assets[i]])
    
    print r
    
    w = Markowitz(dailyReturns, r, C)
    
    if needRebalance(context) == True:
        trade(context, w)
    
    

def needRebalance(context):
    if sum(g.position) == 0.0:
        return True
    
    position = np.zeros(len(g.assets))
    for i in range(len(g.assets)):    
        price = context.portfolio.positions[g.assets[i]].price
        amount = context.portfolio.positions[g.assets[i]].amount
        position[i] = price*amount
    
    v_old = g.position
    v_new = position
    w_old = v_old/sum(v_old)
    w_new = v_new/sum(v_new)
    
    deltaW = abs(w_new - w_old)
    deltaV = abs(v_new - v_old)
    
    for i in range(len(g.assets)):
        if w_old[i]!=0.0:
            if deltaW[i]/w_old[i]>0.25:
                return True
        if v_old[i]!=0.0:
            if deltaV[i]/v_old[i]>0.05:
                return True
    
def trade(context, w):
    value = context.portfolio.portfolio_value
    g.position = np.zeros(len(g.assets))
    
    for i in range(len(g.assets)):
        order_target_value(g.assets[i], value*w[i])
        g.position[i] = value*w[i]
        
    g.lastRebalanceDate = context.current_dt

def Markowitz(dailyReturns, r, C):
    numData, numAsset = dailyReturns.shape
    w = 1.0*np.ones(numAsset)/numAsset
    bound = [(g.w_low,g.w_up) for i in range(numAsset)]
    constrain = ({'type':'eq', 'fun': lambda w: sum(w)-1.0 })
    
    N = 500
    s_max = -100.0
    w_s = np.zeros(numAsset)
    r_s = 0.0
    C_s = 0.0
    for tau in [10**(5.0*t/N-1.0) for t in range(N)]:
        result = sp.optimize.minimize(objFunc, w, (r, C, tau), method='SLSQP', constraints=constrain, bounds=bound)  
        w_opt = result.x
        
        
        for i in range(numAsset):
            if w_opt[i] <0.05:
                w_opt[i] = 0.0
        w_opt = w_opt/sum(w_opt)
  
        r_opt = sum(w_opt*r)
        C_opt = dot(dot(w, C), w)
        s = r_opt/C_opt
        
        if s_max < s:
            s_max = s
            w_s = w_opt
            r_s = r_opt
            C_s = C_opt

    return w_s
        
def objFunc(w, r, C, tau):
    val = tau*dot(dot(w, C), w)-sum(w*r)
    return val

def getReturn(price):
    p = price.resample('M',how='last').pct_change().dropna().values
    
    x=np.atleast_2d(np.linspace(0,len(p),len(p))).T
    
    hypcov = [1.0,1.5,0.1]
    K_DD = isoSE(hypcov,x,x)
    L_DD = sla.cholesky(K_DD + np.eye(len(x))*0.01)
    
    mu = np.mean(p)
    y = p-mu
    alpha = np.atleast_2d(sla.cho_solve((L_DD,False), y)).T
    xt = np.atleast_2d(np.linspace(len(p)-10,len(p)+10,20)).T
    K_XD = isoSE(hypcov,xt,x)
    yt = mu+np.dot(K_XD,alpha)

    r = np.mean(yt[0].T)
    return r


def isoSE(hypcov, X1=None, X2=None, diag=False):

    sf2 = np.exp(2*hypcov[0])
    ell2 = np.exp(2*hypcov[1])
    if diag:
        K = np.zeros((X1.shape[0],1))
    else:
        if X1 is X2:
            K = sp.spatial.distance.cdist(X1/ell2, X1/ell2, 'sqeuclidean')
        else:
            K = sp.spatial.distance.cdist(X1/ell2, X2/ell2, 'sqeuclidean')
    K = sf2*np.exp(-K/2)
    return K
    
def getReturnCovariance(dailyReturns): 
    numData, numAsset = dailyReturns.shape
    r = np.zeros(numAsset)
    for i in range(numAsset):
        r[i] = np.mean(dailyReturns[i,:])
    C = cov(dailyReturns.transpose())
    
    r = (1+r)**255-1
    C = C * 255
    
    return r, C 
    
    
    
    
    