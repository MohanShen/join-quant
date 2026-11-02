# Clone from JoinQuant
# postId: 6b79e09ce3815e415892662b8e8bdf0b
# backtestId: d747d8bc0b0eb04549f39d3b8a0ff802
# title: 最简单的股债平衡策略，小白求指正

# 导入函数库
from jqdata import *

# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')
    
    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    
    run_monthly(tiaocang, 1, time='9:30')
    
def tiaocang(context):
    g.stocks = {
        '510300.XSHG', #沪深300
        '511010.XSHG', #5年国债
        }
    for stock in g.stocks:
        order_target_value(stock, context.portfolio.total_value/2)