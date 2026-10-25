# Clone from JoinQuant
# postId: b27131c6fb393ca6cae017eb0896ee67
# backtestId: 584fa897337d802bba6a33bed6185f42
# title: 双因子加指标模型

import numpy as np
import pandas as pd
import talib as tl

import scipy as sp


def initialize(context):
    benchmarklist = ['000300.XSHG','510050.XSHG','000300.XSHG','510050.XSHG']
    benchmark = benchmarklist[0]
    set_benchmark(benchmark)
    set_commission(PerTrade(buy_cost=0.0008, sell_cost=0.0013, min_cost=5))
    
    context.assets = get_index_stocks('000935.XSHG')
    set_universe(context.assets)
    
    context.ratioPE = None
    context.ratioPB = None
    context.upPE = 40
    context.upPB = 2.0
    
    context.prob = 0.5
    
    context.loss = 0.93
    context.earn = 1.25
    
    context.hold = []
    context.buy = []
    context.sell = []
    context.pool = []

    run_daily(rebalance, time='open')

def handle_data(context, data):
    pass
    
def before_trading_start(context):
    
    context.hold = context.portfolio.positions.keys()
    
    context.fdf = get_fundamentals(
            query(
                valuation.code,
                valuation.pe_ratio,
                valuation.pb_ratio
            ).filter(
                valuation.code.in_(context.assets),
                valuation.pe_ratio>0.0,
                valuation.pe_ratio<100,
                valuation.pb_ratio>0.0,
                valuation.pb_ratio<100
            ).order_by(
                valuation.pe_ratio.asc()
            ))
            
    context.fdf = context.fdf.set_index(context.fdf.columns.values[0])
    
    context.ratioPE = context.fdf.pe_ratio.quantile(context.prob)
    context.ratioPB = context.fdf.pb_ratio.quantile(context.prob)

    context.fdf = context.fdf[context.fdf.pe_ratio < context.ratioPE]
    context.fdf = context.fdf[context.fdf.pb_ratio < context.ratioPB]

    context.pool = context.fdf.T.columns.values
    

def rebalance(context):
    context.buy = filterPaused(list(set(context.pool)-set(context.hold)))
    context.sell = filterPaused(list(set(context.hold)-set(context.pool)))
    
    if len(context.sell)>0:
        for s in context.sell:
            order_target(s, 0)
    
    if len(context.buy)>0:
        buy = filterBuy(context.buy, context)
        if len(buy)>0:
            risk = len(context.buy) - len(buy)
            cash = context.portfolio.cash/(len(buy)+np.exp(0.5*risk)-1)
            for i in range(len(buy)):
                order_target_value(buy[i], cash)
                
    if len(context.hold)>0:
        hold = filterHold(context.hold, context)
        if len(hold)>0:
            for s in hold:
                order_target(s, 0)

def filterHold(stocks, context):
    hold = []
    fdf = get_fundamentals(
            query(
                valuation.code,
                valuation.pe_ratio,
                valuation.pb_ratio
            ).filter(
                valuation.code.in_(stocks),
            ))
    fdf = fdf.set_index(fdf.columns.values[0])
    pe = fdf['pe_ratio']
    pb = fdf['pb_ratio']
    
    for i in range(len(stocks)):
        s = stocks[i]
        p = context.portfolio.positions[s]
        
        if p.price/p.avg_cost <= context.loss and (pe[s]>0.8*context.ratioPE or pb[s]>0.8*context.ratioPB):
            hold.append(s)
        
        elif p.price/p.avg_cost >= context.earn and (pe[s]>0.8*context.ratioPE or pb[s]>0.8*context.ratioPB):
            hold.append(s)
        
        elif stopLoss(s, kernel=2, n=10, zs=0.03):
            hold.append(s)
            
    return hold

def filterBuy(stocks, context):
    buy = []
    fdf = get_fundamentals(
            query(
                valuation.code,
                valuation.pe_ratio,
                valuation.pb_ratio
            ).filter(
                valuation.code.in_(stocks),
            ))
    fdf = fdf.set_index(fdf.columns.values[0])
    
    pe = fdf['pe_ratio']
    pb = fdf['pb_ratio']
        
    for i in range(len(stocks)):
        s = stocks[i]
        if pe[s]<=min(context.ratioPE,context.upPE) or pb[s]<=min(context.ratioPB,context.upPB):
            if signalBuy(s, context):
                buy.append(s)
    
    return buy

def filterPaused(stocks):
    h = history(1, unit='1d', field='paused', security_list=stocks, df=False)
    return [s for s in stocks if not h[s]]

def signalBuy(stock, context):
    ar = AR(stock)
    
    h = attribute_history(stock, 100, unit='1d',fields=('close', 'high', 'low'),skip_paused=True)
    highp = h['high'].values
    lowp = h['low'].values
    closep = h['close'].values
    
    RSI_F = tl.RSI(closep, timeperiod=20)
    RSI_S = tl.RSI(closep, timeperiod=60)
    isFgtS = RSI_F > RSI_S
    
    rsiS = RSI_S[-1]
    rsiF = RSI_F[-1]
    
    if rsiS > 55 and isFgtS[-1]:
        return True
    elif rsiS <= 55 \
        and isFgtS[-1] and isFgtS[-2] \
        and isFgtS[-3] and isFgtS[-4] \
        and isFgtS[-5] :
            return True
    else:
        return False
    

def signalSell(stock, context):
    
    ar = AR(stock)

    h = attribute_history(stock, 80, unit='1d',fields=('close', 'high', 'low'),skip_paused=True)
    highp = h['high'].values
    lowp = h['low'].values
    closep = h['close'].values
    
    RSI_F = tl.RSI(closep, timeperiod=20)
    RSI_S = tl.RSI(closep, timeperiod=60)
    isFgtS = RSI_F > RSI_S
    
    rsiS = RSI_S[-1]
    rsiF = RSI_F[-1]
    
    print RSI_F[-5:-1]
    print RSI_S[-5:-1]
    print isFgtS[-5:-1]
    
    if ar>80:
        return True
    elif isFgtS[-1] == False and rsiS < 60 :
        return True
    else:
        return False
    
def stopLoss(stock, kernel=2, n=10, zs=0.03):
    
    if kernel == 1:
        h = attribute_history(stock, n+2, '1d', 'close', df=False)
        ma1 = 1.0*sum(h['close'][1:-1])/n
        ma2 = 1.0*sum(h['close'][0:-2])/n
        c1 = h['close'][-1]
        c2 = h['close'][-2]
        if (c2 > ma2) and (c1 < ma1):
            return True
        else:
            return False
            
    elif kernel == 2:
        h = attribute_history(stock, n, '1d', 'close',df=False)
        r = 1-1.0*h['close'][-1]/h['close'][0]
        if (r >= zs):
            return True
        else:
            return False
    
def AR(stock):
    l=attribute_history(stock, 26, '1d',fields=('open', 'high', 'low'),skip_paused=True)
    ar=sum(l['high']-l['open'])/sum(l['open']-l['low'])*100
    return ar    
 
    
     