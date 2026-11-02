# Clone from JoinQuant
# postId: b778009930765884f5c90c23a3d13242
# backtestId: 9246a41fdd84c0671f97c05a03e89771
# title: 固定滑点0.01，限价卖出滑点判断无效？

bank_stocks =  ['601988.XSHG']
trend_stock='399951.XSHE'

# 初始化参数
def initialize(context):

    set_benchmark(trend_stock)
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, \
                             open_commission=0.00025, close_commission=0.00025,\
                             close_today_commission=0, min_commission=5), type='stock')
 
    set_slippage(FixedSlippage(0.01)) 
    set_option('use_real_price', True)
    log.set_level('order', 'error')
            
    
# 每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)调用一次
def handle_data(context, data):

    if context.current_dt.day==8 and  context.current_dt.hour == 9 and context.current_dt.minute ==30 :
        order_value(bank_stocks[0], 50000,LimitOrderStyle(3.98))
        order_value(bank_stocks[0], 50000,LimitOrderStyle(3.99))
    
    if context.current_dt.day==9 and  context.current_dt.hour == 9 and context.current_dt.minute ==30 :
        order_target(bank_stocks[0], 0,LimitOrderStyle(4.01))




