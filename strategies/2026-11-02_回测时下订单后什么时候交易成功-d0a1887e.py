# Clone from JoinQuant
# postId: d0a1887e985da86ab1ab2426ddf85668
# backtestId: 52a45832f40aa5e027437cdd49e3683a
# title: 回测时下订单后什么时候交易成功

import talib

def initialize(context):
    # 对比标的
    set_benchmark('000300.XSHG') 
    
    # 设置佣金
    set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))

    g.stock = u'159915.XSHE' # 创业板ETF
    g.gold = u'518880.XSHG' # 黄金ETF
    g.debt  = u'511010.XSHG' # 上证5年期国债ETF

    g.lag = 20 # 回看前20天
    
    g.security=[g.stock,g.gold,g.debt]
    
    set_universe(g.security)

# def before_trading_start(context):
#     context.holdLarge = True
#     context.holdSmall = True
#     # 获得当前持仓
#     context.hold = list(context.portfolio.positions.keys())
    
#     print context.hold
    
#     lag = context.lag
#     hLarge = history(lag,'1d','close',context.large,df=True)[context.large].values
#     cLarge = hLarge[-1]
#     mLarge = talib.SMA(hLarge, 20)[-1]
    
#     hSmall = history(lag,'1d','close',context.small,df=True)[context.small].values
#     cSmall = hSmall[-1]
#     mSmall = talib.SMA(hSmall, 20)[-1]
    
#     if cLarge < mLarge:
#         context.holdLarge = False
#         print 'large lower than SMA20'
#     if cSmall < mSmall:
#         context.holdSmall = False
#         print 'small lower than SMA20'


def handle_data(context, data):
    
    # lag = g.lag
    # 获得当前时间
    hour = context.current_dt.hour
    minute = context.current_dt.minute
    
    
    
    # 每天下午14:55调仓
    if hour ==14 and minute==50:
        
        # 获得当前总资产
        # value = context.portfolio.portfolio_value
        # print value
        # print context.portfolio.cash
        pfl=context.portfolio
        
        holdStock=g.stock in pfl.positions
        holdGold=g.gold in pfl.positions
        holdDebt=g.debt in pfl.positions
        
        log.info('创业板%s,黄金%s,国债%s',holdStock,holdGold,holdDebt)
        
        close = history(g.lag,'1d','close')
        stockClose=close[g.stock]
        goldClose=close[g.gold]
        
        pStock = data[g.stock].close
        retStock = (pStock - stockClose[0])/stockClose[0]
        
        pGold = data[g.gold].close
        retGold = (pGold - goldClose[0])/goldClose[0]
        
        log.info( 'stock return:%.2f,gold return:%.2f',retStock,retGold)
        
        
        if retStock<=0 and retGold<=0:
            if holdStock:
                order_target(g.stock, 0)
            if holdGold:
                order_target(g.gold, 0)
            if not holdDebt:
                log.info('买入国债%.2f元',pfl.cash)
                order_target_value(g.debt, pfl.cash)
        else:
            if retStock>retGold:
                if holdGold:
                    order_target(g.gold, 0)
                if holdDebt:
                    order_target(g.debt, 0)
                    
                if not holdStock:
                    log.info('买入创业板%.2f元',pfl.cash)
                    order_target_value(g.stock, pfl.cash)
                
            elif retGold>retStock:
                if holdStock:
                    order_target(g.stock, 0)
                if holdDebt:
                    order_target(g.debt, 0)
                
                if not holdGold:
                    log.info('买入黄金%.2f元',pfl.cash)
                    order_target_value(g.gold, pfl.cash)
        
        
        
        
        
        
        