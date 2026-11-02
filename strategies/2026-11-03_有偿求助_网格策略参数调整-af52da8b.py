# Clone from JoinQuant
# postId: af52da8b62b26a70f6b1154423426593
# backtestId: b7a3514e31e9141deffeeb7839aedd65
# title: 【有偿求助】网格策略参数调整

# 克隆自聚宽文章：https://www.joinquant.com/post/23340
# 标题：简单高效的网格交易
# 作者：Hawkingz

# 网格交易

# 导入函数库
from jqdata import *

# 初始化函数，设定基准等等
def initialize(context):
    # 设定比亚迪 002594.XSHE 作为基准
    set_benchmark('600519.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')

    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之一点二，卖出时佣金万分之一点二加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(open_commission=0.00012, close_commission=0.00112, min_commission=5), type='fund')

    # 设置标的
    g.security = '600519.XSHG'  # 比亚迪股票代码

    # 网格交易参数设置
    g.grid=0.01  # 价格上涨或下跌2%为一格

    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
      # 开盘时运行
    run_daily(market_open, time='open', reference_security='600519.XSHG')
      # 收盘后运行
    run_daily(after_market_close, time='after_close', reference_security='600519.XSHG')

## 开盘时运行函数
def market_open(context):
    log.info('函数运行时间(market_open):'+str(context.current_dt.time()))
    security = g.security
    
    # 获取最新价格
    current_data = get_current_data()
    current_price=current_data[security].last_price
    
    # 取得当前的现金
    cash = context.portfolio.available_cash

    # 建立底仓
    if len(context.portfolio.positions) == 0:
        # 设置资金份额
        g.grid_cash = cash/10  # 可用资金分成10份
        # 使用50%资金建立底仓
        orders=order_value(security, cash*0.6)
        if orders is None:
            print("创建订单失败...")
        else:
            log.info("空仓, 建立底仓，买入{}".format(security))
            # 记录平均成交价格
            g.last_order_price=orders.price
            # 设置仓位份额
            g.grid_pos=round(orders.amount/5/100)*100  # 将全仓位分成10份

    # 如果下跌1个网格, 则买入1份资金的标的
    elif (current_price/g.last_order_price-1 < -g.grid) and (cash > 0):
        orders=order_value(security, g.grid_cash)
        if orders is None:
            print("创建订单失败...")
        else:
            log.info("价格下跌1个网格，买入1份资金：{}".format(security))
            # 记录平均成交价格
            g.last_order_price=orders.price

    # 如果上涨1个网格, 则卖出1份仓位
    elif (current_price/g.last_order_price-1 > g.grid) and context.portfolio.positions[security].closeable_amount >= g.grid_pos:
        orders=order(security, -g.grid_pos)
        if orders is None:
            print("创建订单失败...")
        else:
            log.info("价格上涨1个网格, 卖出1份仓位：{}".format(security))
            # 记录平均成交价格
            g.last_order_price=orders.price

## 收盘后运行函数
def after_market_close(context):
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    #得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    log.info('一天结束')
    log.info('##############################################################')
