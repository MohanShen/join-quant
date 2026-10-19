# Clone from JoinQuant
# postId: 49756729df1dd7ea142f51b0c6920f16
# backtestId: 50ed2b32abbe11b1b9e947314a57d34a
# title: 基于卡尔曼滤波器的银行搬砖

import numpy as np
def initialize(context):
    benchmarklist = ['000300.XSHG','510050.XSHG','000300.XSHG','510050.XSHG']
    benchmark = benchmarklist[0]
    set_benchmark(benchmark)
    set_commission(PerTrade(buy_cost=0.0008, sell_cost=0.0013, min_cost=5))
    
    bank = [u'600000.XSHG',
            u'601169.XSHG',
            u'600036.XSHG',
            u'600015.XSHG',
            u'601166.XSHG',
            u'601988.XSHG',
            u'601328.XSHG',
            u'601398.XSHG',
            u'000001.XSHE',
            u'601288.XSHG',
            u'601818.XSHG',
            u'601998.XSHG',
            u'601939.XSHG',
            u'600016.XSHG']
    g.assets = get_index_stocks('000935.XSHG')
    #g.assets = bank
    set_universe(g.assets)

    g.ratio = 0.5
    g.hold = []
    
    g.delta = 0.001
    g.Vw = g.delta / (1 - g.delta)
    g.Ve = 0.001
    
    g.muPE = None
    g.SigmaPE = None
    
    g.muPB = None
    g.SigmaPB = None

def before_trading_start(context):
    if g.assets:
        g.df = get_fundamentals(
            query(
                valuation.code,
                valuation.pe_ratio,
                valuation.pb_ratio
            ).filter(
                valuation.code.in_(g.assets)
            ).order_by(
                valuation.pe_ratio.asc()
            ))
    g.df = g.df.loc[g.df.pe_ratio > 0]
    
    yPE = np.mean(g.df['pe_ratio'])
    yPB = np.mean(g.df['pb_ratio'])
    g.muPE, g.SigmaPE = Kalman(g.muPE, g.SigmaPE, yPE, g.Vw, g.Ve)
    g.muPB, g.SigmaPB = Kalman(g.muPB, g.SigmaPB, yPB, g.Vw, g.Ve)

    #g.df = g.df[g.df.pe_ratio < g.df.pe_ratio.quantile(g.ratio)]
    #g.df = g.df[g.df.pb_ratio < g.df.pb_ratio.quantile(g.ratio)]
    g.df = g.df[g.df.pe_ratio < g.muPE]
    g.df = g.df[g.df.pb_ratio < g.muPB]
    g.dfBuy = g.df
    
def Kalman(mu, Sigma, y, Vw, Ve):
    if mu is None:
        mu = y # np.mean(g.df['pe_ratio'])
        Sigma = 1.0
    else:
        # transition
        mu = mu
        Sigma = Sigma + Vw
        
        # observation
        yhat = mu
        e = y - yhat
        Q = Sigma + Ve

        # filtering
        K = Sigma/Q
        mu = mu + K*e
        Sigma = Sigma - K*Sigma
    return mu, Sigma

def after_trading_end(context):
    g.hold = context.portfolio.positions.keys()

def filterPaused(stocks,data):
    curData = get_current_data()
    return [s for s in stocks if not curData[s].paused]
    
def handle_data(context, data):
    
    buy = list(set(g.dfBuy.code)-set(g.hold))
    sell = list(set(g.hold)-set(g.dfBuy.code))
    buy = filterPaused(buy,data)
    sell = filterPaused(sell,data)
    
    for s in sell:
        order_target(s, 0)
    
    if len(buy)>0:
        
        dfBuy = get_fundamentals(
            query(
                valuation.code,
                valuation.pe_ratio
            ).filter(
                valuation.code.in_(buy)
            ))
        w = dfBuy['pe_ratio'].values
        w = 1/w 
        w = w/sum(w)
        cash = context.portfolio.cash
        for i in range(len(buy)):
            order_target_value(buy[i], cash*w[i])
    
    
    
    
    
    
    
     