# Clone from JoinQuant
# postId: 967ffec417fcba2d7a94c70f6d34396a
# backtestId: de207eef7607365450afa269be79f41d
# title: 关于talib的macd函数，计算周期中，碰到股票停牌时，计算出来的macd值和股票软件不一致的问题

# 导入函数库
import jqdata
import talib
import numpy as np
import pandas as pd

# 初始化函数，设定基准等等
def initialize(context):
    
    # 定义一个全局变量, 保存要操作的股票
    g.security = '600171.XSHG'
    
    #真实价格
    set_option('use_real_price', True)
    
    # 股票类交易手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, \
                             open_commission=0.0003, close_commission=0.0003,\
                             close_today_commission=0, min_commission=5), type='stock')
    
    context.TIME_PERIOD = 5
    
#该函数会在每天开始交易前被调用一次, 依据的时间是股票的交易时间，即该函数启动时间为 9:20
#def before_trading_start(context):
    
    #取得当日融券标的券，并过滤停牌股票
    #g.marginsec_stocks= filter_paused_stock(get_marginsec_stocks())
#    g.marginsec_stocks = filter_paused_stock(get_index_stocks('000001.XSHG' ))
    #log.info("%s" % (g.marginsec_stocks))
    
    #取得股票的历史收盘价
#    g.price = get_price(g.marginsec_stocks, end_date=context.current_dt,fields=['close'])
    
def after_trading_end(context):    
    
    #取得当日融券标的券，并过滤停牌股票
    #g.marginsec_stocks= filter_paused_stock(get_marginsec_stocks())
    g.marginsec_stocks = filter_paused_stock(get_index_stocks('000001.XSHG' ))
    #log.info("%s" % (g.marginsec_stocks))
    
    #取得股票的历史收盘价
    g.price = get_price(g.marginsec_stocks, end_date=context.current_dt,fields=['close'])
    
    if not g.security in g.marginsec_stocks:
        return
    
    price = g.price['close'][g.security].values
    #price = np.hstack((price,[data[stock].close]))
    
    avg_5 = talib.EMA(price, 5)
    avg_22 = talib.EMA(price, 22)
    #log.info("avg_5:%s, avg_22:%s" % (avg_5[-1], avg_22[-1]))
    
    #price = np.hstack((price,[data[g.security].close]))
    dif, dea, macd = talib.MACD(price,  
                                    fastperiod=5,  
                                    slowperiod=22,  
                                    signalperiod=10) 
    
    log.info("DIF:%s, DEA:%s,MACD:%s, price:%s" % (dif[-1], dea[-1], macd[-1], price[-2]))
    
    dif, dea, macd = myMACD(price,  
                                    fastperiod=5,  
                                    slowperiod=22,  
                                    signalperiod=10) 
    
    #log.info("MyMACD DIF:%s, DEA:%s,MACD:%s, price:%s" % (dif[-1], dea[-1], macd[-1], price[-2]))
    #if dif[-3] >= dea[-3] and dif[-2] < dea[-2] and dif[-1] < dea[-1]:
        #log.info("DIF:%s, DEA:%s,MACD:%s,DIF:%s, DEA:%s,MACD:%s,DIF:%s, DEA:%s,MACD:%s" % (dif[-3], dea[-3], macd[-3],dif[-2], dea[-2], macd[-2],dif[-1], dea[-1], macd[-1]))

# 开盘时运行函数
#def handle_data(context, data):
    #log.info('handle_data')
    #for stock in g.marginsec_stocks:
    #    # 用Talib计算RSI值
    #    price = g.price['close'][stock].values
    #    price = np.hstack((price,[data[stock].close]))
    #    rsi_data = talib.RSI(price,timeperiod=context.TIME_PERIOD)[-1]
    #    if rsi_data >= 80:
    #        log.info("stock:%s, %f" % (stock,rsi_data))
    
#    if not g.security in g.marginsec_stocks:
#        return
    
#    price = g.price['close'][g.security].values
    #price = np.hstack((price,[data[stock].close]))

    #price = np.hstack((price,[data[g.security].close]))
#    dif, dea, macd = talib.MACD(price,  
#                                    fastperiod=5,  
#                                    slowperiod=22,  
#                                    signalperiod=10) 
    
#    log.info("DIF:%s, DEA:%s,MACD:%s" % (dif[-2], dea[-2], macd[-2]))
    
#    if price[-5:].mean() > price[-10:].mean() and price[-10:].mean() > price[-20:].mean() and price[-20:].mean() > price[-30:].mean() and price[-30:].mean() > price[-60:].mean() and macd[-1] > signal[-1] and macd[-1] > 0:
#        log.info("buy stock %s", context.current_dt)
    
    
# 过滤停牌股票
def filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]

#自定义计算macd函数 
def myMACD(price, fastperiod=12, slowperiod=26, signalperiod=9):
    ewma12 = pd.ewma(price,span=fastperiod)
    ewma60 = pd.ewma(price,span=slowperiod)
    dif = ewma12-ewma60
    dea = pd.ewma(dif,span=signalperiod)
    bar = (dif-dea) * 2 #有些地方的bar = (dif-dea)*2，但是talib中MACD的计算是bar = (dif-dea)*1
    return dif,dea,bar
