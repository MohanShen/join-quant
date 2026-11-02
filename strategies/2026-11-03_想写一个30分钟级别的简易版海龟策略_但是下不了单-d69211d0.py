# Clone from JoinQuant
# postId: d69211d0d638aac62f791e9dbc866c25
# backtestId: 9179ba65d59efdb8ac847bc808930029
# title: 想写一个30分钟级别的简易版海龟策略，但是下不了单

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

## 开盘前运行函数
def before_market_open(context):
    # 输出运行时间
    log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))

    # 给微信发送消息（添加模拟交易，并绑定微信生效）
    # send_message('美好的一天~')

    # 要操作的股票：沪深300etf（g.为全局变量）
    g.security = '510300.XSHG'

## 开盘时运行函数
def market_open(context):
    log.info('函数运行时间(market_open):'+str(context.current_dt.time()))
    security = g.security
    # 获取股票的175天30分钟的开盘价、收盘价、最高价、和最低价
    my_data = get_bars(security, count=1400, unit='30m', fields=['open','close','high','low'],
    include_now=False,end_dt='2020-03-26',df=True)
    #判断是否买卖，以及买卖数量
    for i in range(1400):
        if i >22:
            ma20_start = i - 20
            ma10_start = i - 10
            cut20_data = my_data.iloc[ma20_start:i,0:4]
            cut10_data = my_data.iloc[ma10_start:i,0:4]
            if cut20_data.iloc[0,1] > cut20_data.loc[:,'high'].max():
                cash = context.portfolio.available_cash
                log.info("价格高于前20天最高价, 全仓买入 %s" % (security))
                order(security,1000)
            elif cut10_data.iloc[0,1] < cut10_data.loc[:,'low'].min():
                log.info("价格低于前10天最低价, 全仓卖出 %s" % (security))
                order_target(security, 0)
    

## 收盘后运行函数
def after_market_close(context):
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    #得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    log.info('一天结束')
    log.info('##############################################################')
