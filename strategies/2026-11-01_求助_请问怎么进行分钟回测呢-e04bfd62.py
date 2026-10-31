# Clone from JoinQuant
# postId: e04bfd6269bc605cae5d5133076f6f47
# backtestId: edbbf15de6fce9419e67088fdfc63dc7
# title: 求助，请问怎么进行分钟回测呢？

import numpy as np 
import pandas as pd

def initialize(context):
    # 定义一个全局变量, 保存要操作的股票
    # 000001(股票:平安银行)
    g.security = '150176.XSHE'
    # 初始化此策略
    # 设置我们要操作的股票池, 这里我们只操作一支股票
    #初始资金，基准价格，网格次数
    g.cash = 100000
    g.initial_price= 1.00
    g.trade_times=0
    #网格步长，网格档数
    g.step=0.05
    g.dang=10
    g.bottom=g.initial_price-(g.dang)*g.step
    #print g.bottom
    g.space=np.linspace(g.initial_price,g.bottom,g.dang+1)
    print g.space
    #stock生效，设置基准参数
    set_universe([g.security])
    set_benchmark('510900.XSHG')

#判断买入卖出操作，由现价、当前仓位和网格次数决定到达网格价格买入卖出数量
def setup_position(context,data,status):
    security = g.security
    space=g.space
    #bottom_price = g.initial_price
    cash = context.portfolio.cash
    #print cash
    #print g.cash
    current_price = data[security].close
    amount = context.portfolio.positions[security].total_amount 
    current_value = current_price*amount
    unit_value = g.cash/10
    #returns = (current_price-bottom_price)/bottom_price
    #卖出
    if (status == 'short'):
        if current_price > space[1] and g.trade_times==2:
            log.info("卖出第二档 Selling %s" % (security))
            order_value(security,-unit_value)
            g.trade_times=1
            log.info("trade_times %d" % (g.trade_times))

        if current_price > space[2] and g.trade_times==3:
            log.info("卖出第三档 Selling %s %s" % (security,current_price))
            order_value(security,-unit_value)
            g.trade_times=2
            log.info("trade_times %d" % (g.trade_times))
            
        if current_price > space[3] and g.trade_times==4:
            log.info("卖出第四档 Selling %s %s" % (security,current_price))
            order_value(security,-unit_value)
            g.trade_times=3
            log.info("trade_times %d" % (g.trade_times))
            
        if current_price > space[4] and g.trade_times==5:
            log.info("卖出第五档 Selling %s %s" % (security,current_price))
            order_value(security,-unit_value)
            g.trade_times=4
            log.info("trade_times %d" % (g.trade_times))
            
        if current_price > space[5] and  g.trade_times==6:
            g.trade_times=5
            log.info("卖出第六档 Selling %s %s" % (security,current_price))
            order_value(security,-unit_value)
            log.info("trade_times %d" % (g.trade_times))
        if current_price > space[6] and g.trade_times==7:
            g.trade_times=6
            log.info("卖出第七档 Selling %s" % (security))
            order_value(security,-unit_value)
            log.info("trade_times %d" % (g.trade_times))
        if current_price > space[7] and g.trade_times==8:
            g.trade_times=7
            log.info("卖出第八档 Selling %s" % (security))
            order_value(security,-unit_value)
            log.info("trade_times %d" % (g.trade_times))
        if current_price > space[8] and g.trade_times==9:
            g.trade_times=8
            log.info("卖出第九档 Selling %s" % (security))
            order_value(security,-unit_value)
            log.info("trade_times %d" % (g.trade_times))
        if current_price > space[9] and g.trade_times==10:
            g.trade_times=9
            log.info("卖出第十档 Selling %s" % (security))
            order_value(security,-unit_value)
            log.info("trade_times %d" % (g.trade_times))
    # 买入
    if (status == 'long') and cash >0:
        if current_price < space[1] and current_value < 1*unit_value and g.trade_times==0:
            g.trade_times=1
            log.info("买入第一档 Buying %s %s" % (security,current_price))
            order_value(security,unit_value)
            log.info("trade_times %d" % (g.trade_times))
        if current_price < space[2] and current_value < 2*unit_value and g.trade_times==1:            
            g.trade_times=2
            log.info("买入第二档 Buying %s %s" % (security,current_price))
            order_value(security,unit_value)
            log.info("trade_times %d" % (g.trade_times))
        if current_price < space[3] and current_value < 3*unit_value and g.trade_times==2:           
            g.trade_times=3
            log.info("买入第三档 Buying %s %s" % (security,current_price))
            order_value(security,unit_value)
            log.info("trade_times %d" % (g.trade_times))
        if current_price < space[4] and current_value < 4*unit_value and g.trade_times==3:            
            g.trade_times=4
            log.info("买入第四档 Buying %s %s" % (security,current_price))
            order_value(security,unit_value)
            log.info("trade_times %d" % (g.trade_times))
        if current_price < space[5] and current_value < 5*unit_value and g.trade_times==4:            
            g.trade_times=5
            log.info("买入第五档 Buying %s %s" % (security,current_price))
            order_value(security,unit_value)
            log.info("trade_times %d" % (g.trade_times))
        if current_price < space[6] and current_value < 6*unit_value and g.trade_times==5:            
            g.trade_times=6
            log.info("买入第六档 Buying %s %s" % (security,current_price))
            order_value(security,unit_value)
            log.info("trade_times %d" % (g.trade_times))
        if current_price < space[7] and current_value < 7*unit_value and g.trade_times==6:            
            g.trade_times=7
            log.info("买入第七档 Buying %s" % (security))
            order_value(security,unit_value)
            log.info("trade_times %d" % (g.trade_times))
        if current_price < space[8] and current_value < 8*unit_value and g.trade_times==7:            
            g.trade_times=8
            log.info("买入第八档 Buying %s" % (security))
            order_value(security,unit_value)
            log.info("trade_times %d" % (g.trade_times))
        if current_price < space[9] and current_value < 9*unit_value and g.trade_times==8:            
            g.trade_times=9
            log.info("买入第九档 Buying %s" % (security))
            order_value(security,unit_value)
            log.info("trade_times %d" % (g.trade_times))
        if current_price < space[10] and current_value < 10*unit_value and g.trade_times==9:            
            g.trade_times=10
            log.info("买入第十档 Buying %s" % (security))
            order_value(security,unit_value)
            log.info("trade_times %d" % (g.trade_times))
    return True

# 每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)调用一次
def handle_data(context, data):
	#补仓步长：-3%，-5%，-8%，-12%
	setup_position(context,data,'long')
	#空仓步长：5%，10%，15%，20%
	setup_position(context,data,'short')
	security = g.security
	current_price=data[security].close
	record(stock_price=current_price)

