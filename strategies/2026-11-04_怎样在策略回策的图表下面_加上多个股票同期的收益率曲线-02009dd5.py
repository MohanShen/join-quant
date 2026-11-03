# Clone from JoinQuant
# postId: 02009dd564789c12f9b2b59a0850938d
# backtestId: d18752c697e088a9b8ba914fb0b6a0a4
# title: 怎样在策略回策的图表下面，加上多个股票同期的收益率曲线？

# 导入函数库
from jqdata import *

# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')

    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')

    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
      # 开盘前运行
    run_daily(before_market_open, time='before_open', reference_security='000300.XSHG')
      # 开盘时运行
    run_daily(market_open, time='open', reference_security='000300.XSHG')
      # 收盘后运行
    run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')
    g.time = 0
    g.time1 = 0

## 开盘前运行函数
def before_market_open(context):
    # 输出运行时间
    log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))

    # 给微信发送消息（添加模拟交易，并绑定微信生效）
    # send_message('美好的一天~')

    # 要操作的股票：平安银行（g.为全局变量）
    g.security1 = '600519.XSHG'
    g.security2 = '603288.XSHG'
    g.security3 = '603899.XSHG'
    g.security4 = '300529.XSHE'

## 开盘时运行函数
def market_open(context):
    log.info('函数运行时间(market_open):'+str(context.current_dt.time()))
    
    security1 = g.security1
    security2 = g.security2
    security3 = g.security3
    security4 = g.security4
    # 获取股票的收盘价
    close_data1 = get_bars(security1, count=5, unit='1d', fields=['close'])
    close_data2 = get_bars(security2, count=5, unit='1d', fields=['close'])
    close_data3 = get_bars(security3, count=5, unit='1d', fields=['close'])
    close_data4 = get_bars(security4, count=5, unit='1d', fields=['close'])
    # 取得上一时间点价格
    current_price1 = close_data1['close'][-1]
    current_price2 = close_data2['close'][-1]
    current_price3 = close_data3['close'][-1]
    current_price4 = close_data4['close'][-1]
    
    # 取得当前的现金
    cash = context.portfolio.available_cash
    
    if (g.time1 == 0):
        g.current_price11 = current_price1
        g.current_price22 = current_price2
        g.current_price33 = current_price3
        g.current_price44 = current_price4
    g.time1 += 1
    

    # 如果上一时间点价格高出五天平均价1%, 则全仓买入
    if (g.time == 0):
        # 记录这次买入
        log.info("买入后不动")
        # 用所有 cash 买入股票
        order_value(security1, cash/4)
        order_value(security2, cash/4)
        order_value(security3, cash/4)
        order_value(security4, cash/4)
    g.time += 1
    
    record(贵州茅台=current_price1/g.current_price11-1) 
    record(海天味业=current_price2/g.current_price22-1)
    record(晨光股份=current_price3/g.current_price33-1)
    record(健帆生物=current_price4/g.current_price44-1)

## 收盘后运行函数
def after_market_close(context):
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    #得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    log.info('一天结束')
    log.info(g.time)
    log.info(g.time1)
    log.info('##############################################################')
     