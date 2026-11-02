# Clone from JoinQuant
# postId: aed45d1d38aaedc2c2f4b7037db3bbde
# backtestId: f5be1703726f9844031fc5c51b63df86
# title: 期货9：00开盘价数据出错。

import talib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import datetime


def initialize(context):
    #-----------------------------------------------------------------------------------------------
    set_benchmark('RB9999.XSGE')
    set_slippage(FixedSlippage(0))
    init_cash = context.portfolio.starting_cash 
    set_subportfolios([SubPortfolioConfig(cash=init_cash, type='futures')])    
    set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0, close_commission=0, close_today_commission=0, min_commission=0), type='futures')
    #run_daily( while_open, time='every_bar', reference_security='RB9999.XSGE')
    set_option('futures_margin_rate', 0.1)
    

    #run_daily(open2,'21:01')

    
    
    run_daily(open2,'09:01')



def open2(context):    
    
    C = get_dominant_future('RB')
    print ('合约:',C)
    array1 = get_bars(C, 1, unit='1m',
                 fields=['date', 'open','high','low','close'],
                 include_now=True, end_dt=None, fq_ref_date=None)
    print (array1['date'],array1['open'],array1['high'],array1['low'],array1['close'])
    
    '''g.lastprice = float(array1['open'])
    print ('AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',g.lastprice)
    current_data = get_current_data()
    AA = current_data[C].last_price
    
    print ('SS:',AA)'''
    
    
    
    
    
def var_is_trading(time,var):
    '''获取当前时间是否是该标的的交易时间,收盘不算交易时间
    传入:  date: datetime.datetime ,策略中逻辑时间为context.current_dt
           var:  标的代码,默认为AG的交易时间'''
    next_m = time+datetime.timedelta(minutes=1)
    temp = get_price(var,end_date=next_m,frequency='1m',count=1)
    if temp.index[-1] != next_m:
        return False
    else:
        return True      
