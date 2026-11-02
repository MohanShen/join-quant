# Clone from JoinQuant
# postId: 32b3258e378abb2a82120b93208e1765
# backtestId: 1e45993d1f9f916ecb23175fd8c3229c
# title: 【已解决】关于聚宽成交价格、复权的问题，求助各位盼回复

# 导入函数库
from jqdata import *

# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('300059.XSHE')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 开盘时运行
    run_daily(market_close, time='15:00', reference_security='000300.XSHG')

    set_order_cost(OrderCost(open_tax=0, close_tax=0.0, open_commission=0.0, close_commission=0.0, close_today_commission=0, min_commission=0), type='stock')

## 开盘时运行函数
def market_close(context): 
    #设置成你的白酒标的股池
    security = '300059.XSHE'
 
    order_target_value(security, 0)

    order_value(security, context.portfolio.total_value)

        








    
