# Clone from JoinQuant
# postId: 557d5149494bfcf356177085fa35327b
# backtestId: cb85e87742775743f2bed98e5eab6cd4
# title: 为什么这个二八轮动策略收益率是0%

#二八轮动#
'''
=================================================
总体回测前设置参数和回测
=================================================
'''
def initialize(context):
    set_params()    #1设置策参数
    set_variables() #2设置中间变量
    set_backtest()  #3设置回测条件

#1 设置参数
def set_params():
    # 设置基准收益
    #set_benchmark('000300.XSHG') 
    set_benchmark('000905.XSHG')
    g.lag = 20
    g.hour = 14
    g.minute = 53
    
    g.hs =  '000300.XSHG' #300指数
    g.zz =  '000905.XSHG'#500指数
    g.gz =  '511010.XSHG'#国债指数
    
    #g.ETF300 = '510300.XSHG'#'510300.XSHG'#
   # g.ETF500 = '510500.XSHG'#'510500.XSHG'#


#2 设置中间变量
def set_variables():
    return

#3 设置回测条件
def set_backtest():
    #set_option('use_real_price', True) #用真实价格交易
    log.set_level('order', 'error')



'''
=================================================
每天开盘前
=================================================
'''
#每天开盘前要做的事情
def before_trading_start(context):
    set_slip_fee(context) 

#4 
# 根据不同的时间段设置滑点与手续费

def set_slip_fee(context):
    # 将滑点设置为0
    set_slippage(FixedSlippage(0)) 
    # 根据不同的时间段设置手续费
    dt=context.current_dt
    
    if dt>datetime.datetime(2013,1, 1):
        set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5)) 
        
    elif dt>datetime.datetime(2011,1, 1):
        set_commission(PerTrade(buy_cost=0.001, sell_cost=0.002, min_cost=5))
            
    elif dt>datetime.datetime(2009,1, 1):
        set_commission(PerTrade(buy_cost=0.002, sell_cost=0.003, min_cost=5))
                
    else:
        set_commission(PerTrade(buy_cost=0.003, sell_cost=0.004, min_cost=5))




'''
=================================================
每日交易时
=================================================
''' 
def handle_data(context, data):
    # 获得当前时间
    hour = context.current_dt.hour
    minute = context.current_dt.minute
    
    # 每天收盘时调整仓位
    if hour == g.hour and minute == g.minute:
        signal = get_signal(context)
        
        if signal == 'sell_the_stocks':
            sell_the_stocks(context)
        elif signal == 'adjust_one':
            adjust_one(context)
        elif signal == 'adjust_two':
            adjust_two(context)
        elif signal == 'adjust_three':
            adjust_three(context)
        elif signal == 'adjust_four' :
            adjust_four(context)
            
       # if signal == 'sell_the_stocks':
           # sell_the_stocks(context)
        #elif signal == 'ETF300' or signal == 'ETF500':
           # buy_the_stocks(context,signal)
       # elif signal == '300_To_500':
           # sell_the_stocks(context)
           # buy_the_stocks(context,'ETF500')
       # elif signal == '500_To_300':
           # sell_the_stocks(context)
           # buy_the_stocks(context,'ETF300')
#5
#获取信号
def get_signal(context):
    
    #沪深300与中证500的当日收盘价
    hs300,cp300 = getStockPrice(g.hs, g.lag)
    zz500,cp500 = getStockPrice(g.zz, g.lag)
    gz100,cp100 = getStockPrice(g.gz, g.lag)
    
    #计算前20日变动
    hs300increase = (cp300 - hs300) / hs300
    zz500increase = (cp500 - zz500) / zz500
        
    hold300 = context.portfolio.positions[g.hs].total_amount
    hold500 = context.portfolio.positions[g.zz].total_amount
     
    if hs300increase <= 0 and zz500increase <= 0:
        return 'sell_the_stocks'
    elif hs300increase  > 0 and zz500increase <= 0:
        if hold300 < hold500:
            return 'adjust_one'
        elif hold300 == hold500:
            return 'adjust_two'
    elif hs300increase <= 0 and zz500increase > 0:
        if hold300 > hold500:
            return 'adjust_three'
        elif hold300 == hold500:
            return 'adjust_four'
    elif hs300increase >0 and zz500increase > 0:
        if hs300increase - 0.05 >= zz500increase:
            if hold300 < hold500:
                return 'adjust_one'
            elif hold300 == hold500:
                return 'adjust_two'
        elif zz500increase - 0.05 >= hs300increase:
            if hold300 < hold500:
                return 'adjust_one'
            elif hold300 == hold500:
                return 'adjust_two'
            else:
                return 'adjust_three'
        elif hold300 == hold500:
            return 'adjust_four'
        
    

#6
#取得股票某个区间内的所有收盘价（用于取前20日和当前 收盘价）
def getStockPrice(stock, interval):
    h = attribute_history(stock, interval, unit='1d', fields=('close'), skip_paused=True)
    return (h['close'].values[0],h['close'].values[-1])

#7
#卖出股票
def sell_the_stocks(context):
    for stock in context.portfolio.positions.keys():
        return (log.info("Selling %s" % stock), order_target_value(stock, 0))
        return(log.info("Buying" ),order_target_value([g.gz],context.portfolio.cash))

#8
#买入股票
#def buy_the_stocks(context,signal):
   #return (log.info("Buying %s"% signal ),order_value(eval('g.%s'% signal),context.portfolio.positions_value))
#9#
#2:8轮动
def adjust_one(context):
    return(log.info("selling" ),order_target_value(g.zz, 0.2*context.portfolio.positions_value))
    return(log.info("Buying" ),order_target_value(g.hs, context.portfolio.positions.cash))
    
def adjust_two(context):
    return(log.info("selling" + "国债" ),order_target_value(g.gz,0))
    return(log.info("Buying" ),order_target_value(g.hs, 0.8*context.portfolio.cash))
    return(log.info("Buying"),order_target_value(g.zz, 0.2*context.portfolio.cash))

def adjust_three(context):
    return(log.info("selling" ),order_target_value(g.hs, 0.2*context.portfolio.positions_value))
    return(log.info("Buying" ),order_target_value(g.zz, context.portfolio.cash))
    
def adjust_four(context):
    return(log.info("selling"),order_target_value(g.gz,0))
    return(log.info("Buying"),order_target_value(g.hs, 0.2*context.portfolio.cash))
    return(log.info("Buying"),order_target_value(g.zz, 0.8*context.portfolio.cash))
    
'''
=================================================
每日收盘后（本策略中不需要）
=================================================
'''  
def after_trading_end(context):
    return

