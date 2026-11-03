# Clone from JoinQuant
# postId: a35bb7945d265eb4b76dc48466892da6
# backtestId: 1c0cf98456b850aecce8bf81b77015c7
# title: 研究MA这个栗子，时间不是当前时间的前5天均值！！！！

# 导入函数库
from jqdata import *
from jqlib.technical_analysis import *


def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    #log.info('初始函数开始运行且全局只运行一次')
    #log.set_level('order', 'error')
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    g.security = "000002.XSHE"
    
def handle_data(context,data):
    security = g.security
    close_data = attribute_history(security, 5, '1d' , ['close'])
    print('***********************')
    print(close_data['close'])
    MA5 = close_data['close'].mean()
    print(MA5)
    current_price = close_data['close'][-1]
    print(current_price)
    cash = context.portfolio.cash
    if current_price>1.1*MA5:
        order_value(security,cash)
        #log.info("Buying %s" % (security))
    elif current_price < 0.9*MA5 and context.portfolio.positions[security].closeable_amount >0:
        order_target(security,0)
        #log.info('selling %s' %(security))
        
    