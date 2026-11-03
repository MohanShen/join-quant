# Clone from JoinQuant
# postId: e3b0df8bb4d78b16260d69b12f5acb74
# backtestId: c75497e322fe79dcc51b32c73eb0ea43
# title: 布林带代码问题

# 导入函数库
from jqdata import *

# 初始化函数，设定基准等等
def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    g.security='601318.XSHG'
    g.M=20
    g.k=2
    
def handle_data(context,data):
    #newsr=attribute_history( g.security,count=g.M,fields=['close'])
    sr=attribute_history( g.security,count=g.M)['close']
    ma=sr.mean()
    up=ma+g.k*sr.std()
    down=ma-g.k*sr.std()
    p=get_current_data()[ g.security].day_open
    amount=context.portfolio.positions[ g.security].total_amount
    cash=context.portfolio.available_cash

    
    if p<down and amount==0:
        order_value( g.security,cash)
    
    elif p>up and amount>0:
        order_target( g.security,0)
    #print(newsr)