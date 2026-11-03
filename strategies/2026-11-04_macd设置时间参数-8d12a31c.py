# Clone from JoinQuant
# postId: 8d12a31c96e5471288f1854d56c528d6
# backtestId: 945377dc160f104aa0f53c2a885389f0
# title: macd设置时间参数

from jqlib.technical_analysis import *
from jqdata import *
import talib 
import talib as tl
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import datetime

def initialize(context):

    run_daily(trade, 'every_bar')

#每天开盘前要做的事情
def before_trading_start(context):
    set_slip_fee(context)

# 根据不同的时间段设置滑点与手续费
def set_slip_fee(context):
    set_slippage(FixedSlippage(0.02)) 

    dt=context.current_dt
    if dt>datetime.datetime(2013,1, 1):
        set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003, close_today_commission=0, min_commission=5), type='stock')
    else:
        set_order_cost(OrderCost(open_tax=0, open_commission=0.003,close_commission=0.003, close_tax=0.001,min_commission=5), type='stock')


def trade(context):

  
    g.security = ['000001.XSHE','600000.XSHG']
    # 均分买入几只股票
    hold = 2
    total_value = context.portfolio.total_value# 获取总资产
   
    macd_dif, macd_dea, macd_macd = MACD(g.security,check_date = '2021-01-15', SHORT = 12, LONG = 26, MID = 9)
    for stock in g.security:
        print(macd_dif[stock])
        print(macd_dea[stock])
        print(macd_macd[stock])
        macd = np.float(macd_macd[stock])
        print(type(macd))
        print(macd)
        if macd > 0:
            order_target_value(stock,1/hold*total_value)
            print('买入')
        if macd < 0:
            order_target(stock,0)
            print('卖出')



