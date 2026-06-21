# Clone from JoinQuant
# postId: a67b6f261c9dfe2da84239e2a95c4f30
# backtestId: 5eaa486824470da4563d5a6f8414938d
# title: 双均线择时优化（考虑均线低于一定比例进行卖出判断）

from jqdata import *
def initialize(context):
    # 设定交易成本
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    # 设定全局变量，股票池
    g.security = '000001.XSHE'
    g.ma20_select = []
    g.aa = 0
    # 初始化此策略
    # 设定可用于购买股票的资金
    # 基准设定为沪深300
    set_benchmark('000001.XSHE')
    #每日运行程序
    run_daily(buy_proflio,'9:30')

# 对股票进行20日均线、60日均线交叉进行判断，若20日均线自下向上突破60日均线，买入；若20日均线自上向下突破60日均线，卖出
def func(context,security_111,cash):
    #获取前一交易日信息
    date = context.previous_date
    #获取股票历史收盘价数据
    g.price = get_price(g.security,end_date = date,fields = 'close',skip_paused=True,count = 61)
    g.price['ma20'] = g.price['close'].rolling(20).mean()
    g.price['ma60'] = g.price['close'].rolling(60).mean()
    #获取前一交易日20日、60日均线数据
    ma20_1 = g.price['ma20'][-1:].values[0]
    ma60_1 = g.price['ma60'][-1:].values[0]
    #获取前前一交易日20日、60日均线数据
    ma20_2 = g.price['ma20'][-2:-1].values[0]
    ma60_2 = g.price['ma60'][-2:-1].values[0]
    # 判断决定是否买入
    if (ma60_1-ma20_1)<0 and (ma60_2-ma20_2)>0:
        g.aa = ma20_1
        g.ma20_select = [ma20_1]
        order_value(security_111, cash)              
        # 记录这次买入
        log.info("Buying %s" % (security_111))
        print('buy',security_111, cash)
    # 判断是否卖出
    elif (ma60_1-ma20_1)>0 and (ma60_2-ma20_2)<0 and context.portfolio.positions[security_111].sellable_amount > 0:
        # 卖出所有股票,使这只股票的最终持有量为0
        order_target(security_111, 0)
        # 记录这次卖出
        log.info("Selling %s" % (security_111))
        g.ma20_select = []
    elif len(g.ma20_select) != 0 and max(g.ma20_select)-g.aa != 0 and(ma20_1-max(g.ma20_select))/(max(g.ma20_select)-g.aa)<-0.1:
        # 卖出所有股票,使这只股票的最终持有量为0
        order_target(security_111, 0)
        # 记录这次卖出
        log.info("Selling %s" % (security_111))
        print(g.ma20_select,max(g.ma20_select),ma20_1)
        print((ma20_1-max(g.ma20_select))/(max(g.ma20_select)-g.aa))
        g.ma20_select = []
    elif len(g.ma20_select) != 0 and max(g.ma20_select)-g.aa == 0 and ma20_1-max(g.ma20_select)<0:
        # 卖出所有股票,使这只股票的最终持有量为0
        order_target(security_111, 0)
        # 记录这次卖出
        log.info("Selling %s" % (security_111))
        print(g.ma20_select,max(g.ma20_select),ma20_1)
        print((ma20_1-max(g.ma20_select))/(max(g.ma20_select)-g.aa))
        g.ma20_select = []
    elif len(g.ma20_select) != 0:
        g.ma20_select.append(ma20_1)
    record(ma20=ma20_1,ma60=ma60_1)  
def buy_proflio(context):
    g.money = context.portfolio.available_cash
    func(context,g.security,g.money)



    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
