# Clone from JoinQuant
# postId: 26edc678da82015c0bc8c7825edf7b6d
# backtestId: 90a40909773795d4cc407367ab03744c
# title: 为什么回测时，系统会自动做一些小额交易？

from jqdata import *  # 导入函数库


def initialize(context):  # 初始化函数，设定基准等等
    set_benchmark('000036.XSHE')   # 设定沪深300作为基准
    set_option('use_real_price', True)  # 开启动态复权模式(真实价格)
    log.info('初始函数开始运行且全局只运行一次')  # 输出内容到日志 log.info()
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')

    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001
                            ,open_commission=0.0003
                            ,close_commission=0.0003
                            ,min_commission=5)
                  ,type='stock')

    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
      # 开盘前运行
    #run_daily(before_market_open, time='before_open', reference_security='000300.XSHG')
      # 开盘时运行
    run_daily(market_open, time='open', reference_security='000036.XSHE')
      # 收盘后运行
#    run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')

## 开盘前运行函数
#def before_market_open(context):
    # 输出运行时间
#    log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))

    # 给微信发送消息（添加模拟交易，并绑定微信生效）
    # send_message('美好的一天~')

    # 要操作的股票：平安银行（g.为全局变量）
    g.security = '000001.XSHE'
    


## 开盘时运行函数
def market_open(context):
    log.info('函数运行时间(market_open):'+str(context.current_dt.time()))
    security = '000036.XSHE'
    # 获取股票的收盘价
    close_data = get_bars(security, count=5, unit='1d', fields=['close'])
    # 取得过去五天的平均价格
    #MA5 = close_data['close'].mean()
    # 取得上一时间点价格
    current_price = close_data['close'][-1]
    # 取得当前的现金
    #cash = context.portfolio.available_cash

    # 方法1：123%
    if (current_price <= 3.7):
        order_target_value(security, 50000)
    elif (current_price >= 4.5) and context.portfolio.positions['000036.XSHE'].closeable_amount > 0:
        order(security, -context.portfolio.positions['000036.XSHE'].closeable_amount)
    #if context.portfolio.available_cash/current_price > 1000 :
    #    order(security,1000) 
    #elif current_price-context.portfolio.positions['000036.XSHE'].avg_cost > 0.2:
    #    order(security, -context.portfolio.positions['000036.XSHE'].closeable_amount)
        



## 收盘后运行函数
#def after_market_close(context):
#    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    #得到当天所有成交记录
#    trades = get_trades()
#    for _trade in trades.values():
#        log.info('成交记录：'+str(_trade))
#    log.info('一天结束')
#    log.info('##############################################################')
