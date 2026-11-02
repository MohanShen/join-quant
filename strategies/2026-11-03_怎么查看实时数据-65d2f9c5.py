# Clone from JoinQuant
# postId: 65d2f9c59cf1fd733fa24b90cc235214
# backtestId: 5f4949ad76c18e14982737bf3deac3d2
# title: 怎么查看实时数据？

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
    run_daily(trade, time='every_bar')
    #   # 开盘前运行
    # run_daily(before_market_open, time='before_open', reference_security='000300.XSHG')
    #   # 开盘时运行
    # run_daily(market_open, time='open', reference_security='000300.XSHG')
    #   # 收盘后运行
    # run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')
def trade(context):
    #分别获取5、15日收盘价均线  
    # ma5=attribute_history(security='600373.XSHG',count=5,unit='1d',fields=['close'])['close'].mean()  
    ma15=attribute_history(security='600373.XSHG',count=15,unit='1d',fields=['close'])['close'].mean()
    price=get_price(security='600373.XSHG',frequency='1m')['close'][-1]

    if price>ma15 and context.portfolio.positions_value==0:  #如果5日均线大于15日均线，并且持仓为0，即没有持仓
        cash=context.portfolio.available_cash  #获取当前的可用资金
        order_value(security='600373.XSHG',value=cash) #根据价值下单买入对应股票，买入金额为全部
    if price<ma15 and context.portfolio.positions_value>0:
        order_target(security='600373.XSHG',amount=0)#把指定股票的持股数量降低到0，即卖出全部股票


