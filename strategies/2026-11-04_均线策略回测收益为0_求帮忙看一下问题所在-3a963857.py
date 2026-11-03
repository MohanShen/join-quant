# Clone from JoinQuant
# postId: 3a9638574521da11d7d4c4f412f263a9
# backtestId: dbeb34e12e1edc03d5f47bb7596633e9
# title: 均线策略回测收益为0，求帮忙看一下问题所在。

# 导入函数库
from jqdata import *

def initialize(context):
    
    set_benchmark('000300.XSHG')# 设定沪深300作为基准
    set_option('use_real_price', True)# 开启动态复权模式(真实价格)

    run_daily(before_market_open, time='before_open', reference_security='000300.XSHG')
    run_daily(market_open, time='open', reference_security='000300.XSHG')
    run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')
    
    #设置买入卖出时间
    g.lag = 30
    g.hour = 14
    g.minute = 54
    sd = 0.01#偏离度
    
    g.security = '510300.XSHG'# 要操作的股票：300etf

## 开盘前运行函数
def before_market_open(context):
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')#设置手续费

## 每天交易时
def market_open(context):
    hour = context.current_dt.hour
    minute = context.current_dt.minute
    
    if hour == g.hour and minute == g.minute:
        signal = get_signal(context)
        
        if signal == 'Sell stock':
            sell_the_stocks(context)
        elif signal == 'Buy stock':
            buy_the_stocks(context,signal)    
    
def get_signal(context):
    
    security = g.security
    
    close_data_13 = get_bars(security, count=13, unit='1d', fields=['close'])
    close_data_60 = get_bars(security, count=60, unit='1d', fields=['close'])
    
    # 取得过去五天的平均价格
    MA13 = close_data_13['close'].mean()
    MA60 = close_data_60['close'].mean()
    
    if (MA13-MA60>MA60*sd) and (cash>0):
        return 'Buy stock'
    else:
        return 'Sell stock'
    
def sell_the_stocks(context):
    return (log.info("Selling %s" % signal), order_target_value(stock, 0))

def buy_the_stocks(context,signal):
    return (log.info("Buying %s"% signal ),order_value(eval('g.%s'% signal), context.portfolio.cash))
    

## 收盘后运行函数
def after_market_close(context):
    return