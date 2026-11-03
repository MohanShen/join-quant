# Clone from JoinQuant
# postId: 5ef9d209382bdd8f2523dd29ab37704b
# backtestId: 93d68f99b4ea6784ab05909a0558735f
# title: tushare和聚宽的数据不一致？

# https://www.joinquant.com/view/community/detail/7fe7e01ebbe6082101b4c57a4daaac57



def initialize(context):
    run_daily(period,time='every_bar')
    g.security = '000001.XSHE'
    set_order_cost(OrderCost(open_tax=0, close_tax=0.000, open_commission=0.0003, close_commission=0.0003, close_today_commission=0, min_commission=0), type='stock')
    #set_benchmark("000300.XSHG")
    #set_benchmark("513100.XSHG")
    

def period(context):
    order(g.security, 100)