# Clone from JoinQuant
# postId: 7abd13a29f8f93f989c97f808cc87834
# backtestId: 53366105f0cc33409bc90ecae248739e
# title: 请教一下大神，每天回测怎么保存一个变量

def initialize(context):
    # 定义一个全局变量, 保存要操作的股票
    # 000001(股票:平安银行)
    g.security = '510900.XSHG'
    # 初始化此策略
    # 设置我们要操作的股票池, 这里我们只操作一支股票
    g.cash = 1000000
    g.initial_price= 1.00
    set_universe([g.security])


def setup_position(context,data,bench,status):
    security = g.security
    bottom_price = g.initial_price
    cash = context.portfolio.cash
    current_price = data[security].close
    amount = context.portfolio.positions[security].total_amount 
    current_value = current_price*amount
    unit_value = g.cash/100
    returns = (current_price-bottom_price)/bottom_price
    trade_times=0
    #卖出
    if (status == 'short'):
        if current_price > 0.95 and current_value > 2*unit_value and trade_times==2:
            order_target_value(security,1*unit_value)
            trade_times=1
            log.info("Selling %s" % (security))
        if current_price > 0.90 and current_value > 3*unit_value and trade_times==3:
            order_target_value
            trade_times=2
            log.info("Selling %s" % (security))
        if current_price > 0.85 and current_value > 4*unit_value and trade_times==4:
            order_target_value(security,3*unit_value)
            trade_times=3
            log.info("Selling %s" % (security))
        if current_price > 0.80 and current_value > 5*unit_value and trade_times==5:
            order_target_value(security,4*unit_value)
            trade_times=4
            log.info("Selling %s" % (security))
        if current_price > 0.75 and current_value > 6*unit_value and trade_times==6:
            order_target_value(security,5*unit_value)
            trade_times=5
            log.info("Selling %s" % (security))
    # 买入
    if (status == 'long') and cash >0:
        if current_price < 0.95 and current_value < 1*unit_value and trade_times==0:
            order_target_value(security,1*unit_value)
            trade_times=1
            log.info("Buying %s" % (security))
        if current_price < 0.90 and current_value < 2*unit_value and trade_times==1:            
            order_target_value(security,2*unit_value)
            trade_times=2
            log.info("Buying %s" % (security))
        if current_price < 0.85 and current_value < 3*unit_value and trade_times==2:           
            order_target_value(security,3*unit_value)
            trade_times=3
            log.info("Buying %s" % (security))
        if current_price < 0.80 and current_value < 4*unit_value and trade_times==3:            
            order_target_value
            trade_times=4
            log.info("Buying %s" % (security))
        if current_price < 0.75 and current_value < 5*unit_value and trade_times==4:            
            order_target_value(security,5*unit_value)
            trade_times=5
            log.info("Buying %s" % (security))
    return True

# 每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)调用一次
def handle_data(context, data):
	#补仓步长：-3%，-5%，-8%，-12%
	setup_position(context,data,-0.05,'long')
	#空仓步长：5%，10%，15%，20%
	setup_position(context,data,0.15,'short')
	security = g.security
	current_price=data[security].close
	record(stock_price=current_price)

