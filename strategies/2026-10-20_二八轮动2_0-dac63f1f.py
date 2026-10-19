# Clone from JoinQuant
# postId: dac63f1fbbe6daea4898bc3d110d8aaf
# backtestId: 1ddb59484f628eb56f2142488e9790f8
# title: 二八轮动2.0

import numpy as np
import pandas as pd
import scipy as sp
import scipy.optimize
import datetime
import talib

from scipy import linalg as sla
from scipy import spatial

def initialize(context):
    set_benchmark('000300.XSHG')
    set_commission(PerTrade(buy_cost=0.0008, sell_cost=0.0013, min_cost=5))
    
    ETF = [u'510300.XSHG',
           u'510500.XSHG']
    
    context.assets = ETF
    set_universe(context.assets)
    
    context.param = {}
    context.param['lag'] = 200
    context.param['lastDate'] = datetime.datetime.strptime('1840-01-01', '%Y-%m-%d')
    context.param['riskFree'] = u'511010.XSHG' # start from 2013-03-25
    
    w = 1.0*np.ones(len(context.assets))/len(context.assets)
    context.param['weights'] = w
    
    context.strategy = Strategy(ETF, context.param)
    
    run_weekly(context.strategy.onRebalance,-1, time='open')
    run_daily(context.strategy.ruleRebalance, time='open')
    run_daily(context.strategy.doRebalance, time='open')
    

def handle_data(context, data):
    pass
  
class Strategy(object):
    def __init__(self, assets, param):
        self.assets = assets
        self.param = param
        self.rebalance = True
        
    def initialize(self, context):
        pass
    def before_trading_start(self, context):
        pass
    def handle_data(self, context, data):
        pass
    
    def onRebalance(self, context):
        self.rebalance = True
        
    def ruleRebalance(self, context):
        lag = self.param['lag']
        assets = self.assets
        pos_old = np.zeros(len(assets))
        pos_new = np.zeros(len(assets))
        for i in range(len(assets)):    
            s = assets[i]
            p_new = history(30, '1d', 'close')[s].values[-1]
            p_old = history(30, '1d', 'close')[s].values[0]
            amount = context.portfolio.positions[s].amount 
            pos_new[i] = p_new*amount
            pos_old[i] = p_old*amount
            
        v_old = pos_old
        v_new = pos_new
        w_old = v_old/sum(v_old)
        w_new = v_new/sum(v_new)
        
        deltaW = abs(w_new - w_old)
        deltaV = abs(v_new - v_old)
        
        for i in range(len(context.assets)):
            if w_old[i]!=0.0:
                if deltaW[i]/w_old[i]>0.25:
                    self.rebalance = True
            if v_old[i]!=0.0:
                if deltaV[i]/v_old[i]>0.05:
                    self.rebalance = True
    
    def doSell(self, context):
        assetFree = self.param['riskFree']
        assets = self.assets
        weights = self.param['weights']
        cash = context.portfolio.portfolio_value
        
        for i in range(len(assets)):
            if weights[i] <= 0 or self.stopLoss(assets[i]):
                order_target(assets[i], 0.0)
                
    def doBuy(self, context):
        assetFree = self.param['riskFree']
        assets = self.assets
        weights = self.param['weights']
        cash = context.portfolio.portfolio_value
        
        for i in range(len(assets)):
            if weights[i] > 0 and not self.stopLoss(assets[i]):
                order_target_value(assets[i], cash*weights[i])
    
    def getExcessReturn(self, context):
        lag = self.param['lag']
        assetFree = self.param['riskFree']
        assets = self.assets
        
        retEx = np.zeros(len(assets))
        hFree = attribute_history(assetFree, lag,'1d', fields=('close'), skip_paused=True, df=True)
        retFree = hFree['close'].resample('M',how='last').iloc[[0,-1]].pct_change()[1]
        for i in range(len(assets)):
            hETF = attribute_history(assets[i], lag,'1d', fields=('close'), skip_paused=True, df=True)
            retETF = hETF['close'].resample('M',how='last').iloc[[0,-1]].pct_change()[1]
            retEx[i] = retETF - retFree
        
        return retEx
        
    def doRebalance(self, context):
        if self.rebalance == True:
            self.MarkowitzAssetAllocation(context)
            self.RobustAssetAllocation(context)
            self.doSell(context)
            self.doBuy(context)
            
            self.rebalance = False
    
    def getReturnRisk(self, context, ret):
        numData, numAsset = ret.shape
        
        r = np.mean(ret, axis=0)
        C = np.cov(ret.T)
        
        r = (1+r)**255-1
        C = C * 255
    
        return r, C 
        
    def RobustAssetAllocation(self, context):
        lag = self.param['lag']
        assets = self.assets
        
        retEx = self.getExcessReturn(context)
        weights = self.param['weights']
        
        for i in range(len(assets)):
            w = 0.0
            hETF = attribute_history(assets[i], lag,'1d', fields=('close'), skip_paused=True, df=True)
            closep = hETF['close'].values
            lastC = closep[-1]
            sma = talib.SMA(closep, 5)[-1]
            
            if retEx[i] > 0:
                w += 0.5
            if lastC > sma and retEx[i] > 0:
                w += 0.5 
        
            weights[i] = weights[i]*w
            
        self.param['weights'] = weights
        
    def objFunc(self, w, r, C):
        risk = w.dot(C.dot(w))
        ret = w.dot(r)
        return risk
    
    def MarkowitzAssetAllocation(self, context):
        lag = self.param['lag']
        assets = self.assets
        
        price = []
        for s in assets:
            hETF = attribute_history(s, lag,'1d', fields=('close'), skip_paused=True, df=True)
            closep = hETF['close'].values
            price.append(closep)
        
        retDF  = pd.DataFrame(price).T.pct_change().dropna()
        ret = np.array(retDF)
        
        r, C = self.getReturnRisk(context, ret)
        
        for i in range(len(context.assets)):
            if len(pd.DataFrame(price).T[i])>0:
                r[i] = self.getReturn(pd.DataFrame(price).T[i])
        
        r = r/sum(r)
        
        numAsset = len(r)
        w = 1.0*np.ones(numAsset)/numAsset
        bound = [(0,1) for i in range(numAsset)]
        constrain = ({'type':'eq', 'fun': lambda w: r.dot(w)-1.0 })
        
        result = sp.optimize.minimize(self.objFunc, w, (r, C), method='SLSQP', constraints=constrain, bounds=bound)  
        w_opt = result.x
        
        for i in range(numAsset):
            if w_opt[i] <0.05:
                w_opt[i] = 0.0
        w_opt = w_opt/sum(w_opt)
        
        self.param['weights'] = w_opt
        
        
    def getReturn(self, price):
        price = price.groupby(lambda x: x/2).mean()
        p = price.pct_change().replace([np.inf, -np.inf], np.nan).dropna().values
        
        if len(p)==0:
            return 0
        
        x=np.atleast_2d(np.linspace(0,len(p),len(p))).T
        
        hypcov = [1.0,1.6,0.1]
        K_DD = self.isoSE(hypcov,x,x)
        L_DD = sla.cholesky(K_DD + np.eye(len(x))*0.01)
        
        mu = np.mean(p)
        
        y = p-mu
    
        alpha = np.atleast_2d(sla.cho_solve((L_DD,False), y)).T
    
        xt = np.atleast_2d(np.linspace(len(p)-5,len(p)+25,30)).T
        
        K_XD = self.isoSE(hypcov,xt,x)
        yt = mu+np.dot(K_XD,alpha)
    
        r = max((1+np.mean(yt[0].T))**2-1,0)
        return r 
     
    def isoSE(self, hypcov, X1=None, X2=None, diag=False):
    
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
        
    def stopLoss(self, stock, lag=10, loss=0.93):
        h = attribute_history(stock,lag,'1d',('open', 'close', 'high', 'low', 'volume'),skip_paused=True)
        closep = h['close'].values
        firstC = closep[0]
        lastC = closep[-1]
    
        if (lastC/firstC<= loss):
            return True
        else:
            return False  
        
     