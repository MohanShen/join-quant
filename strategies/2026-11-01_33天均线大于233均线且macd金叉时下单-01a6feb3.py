# Clone from JoinQuant
# postId: 01a6feb3cbb18cb70a578a5f5b340ecc
# backtestId: edca3605a672d76ab8455b07fadf0ec7
# title: 33天均线大于233均线且macd金叉时下单

import math 
import talib
import numpy as np
import pandas as pd 


def initialize(context):
    set_params()
   
    set_backtest()
    
    
def set_params():
   
    g.security='000001.XSHE'
    

    
    
def set_backtest():
    set_option('use_real_price',True)
    log.set_level('order','error')
    
    
def before_trading_start(context):
    set_slip_fee(context)
    
    
def set_slip_fee(context):
    set_slippage(FixedSlippage(0))
    dt=context.current_dt
    if dt>datetime.datetime(2013,1,1):
        set_commission(PerTrade(PerTrade(buy_cost=0.0003, sell_cost=0.0003, min_cost=5)))
    elif dt>datetime.datetime(2011,1,1):
        set_commission(PerTrade(buy_cost=0.001, sell_cost=0.002, min_cost=5))
    elif dt>datetime.datetime(2009,1,1):
        set_commission(PerTrade(buy_cost=0.002, sell_cost=0.003, min_cost=5))
    else:
        set_commission(PerTrade(buy_cost=0.003, sell_cost=0.004, min_cost=5))
        
        
def handle_data(context,data):
   
    ma33=ma('g.security',33)
    ma233=ma('g.security',233)
    tobuy=signal_stock_buy(context,data)
    tosell=signal_stock_sell(context,data)
    
    if tosell==1:
        order_target_value(g.security,0)
        
   
    if tobuy==1:
        order_target_value(g.security,context.portfolio.portfolio_value)
    if not (1 in tosell) or (1 in tobuy):
        send_message("今日无操作")


def mymacd(price,fastperiod=12,slowperiod=26,signalperiod=9):
    df=get_price('g.security',start_date='2015-01-01',end_date='2016-01-01',frequency='daily')
    df[df['volume']==0]=np.nan
    df=df.dropna()
    ewma12=pd.ewma(price,span=fastperiod)
    ewma60=pd.ewma(price,span=slowperiod)
    dif=ewma12-ewma60
    dea=pd.ewma(dif,span=signalperiod)
    bar=(dif-dea)
    return dif,dea,bar
    
    
def ma(security_code,days):
    a=attribute_history(security_code,days,'1d',('close'))
    sum=0
    for i in range(1,days+1):
        sum+=a['close'][-i]
    return sum/days
    
    
        
def signal_stock_sell(context,data):
    sell=[0]*len(g.security)
    mydif,mydea,mybar=mymacd(df['close'].values,fastperiod=12,slowperiod=26,signalperiod=9)
    p1=mydif[-1],mydea[-1],mybar[-1]
    p2=mydif[-2],mydea[-2],mybar[-2]
    
    if ma33<ma233 and p2[0]>p2[1] and p1[0]<p1[1]:
        sell=1
    return sell
    
    
def signal_stock_buy(context,data):
    buy=[0]*len(g.security)
    mydif,mydea,mybar=mymacd(df['close'].values,fastperiod=12,slowperiod=26,signalperiod=9)
    p1=mydif[-1],mydea[-1],mybar[-1]
    p2=mydif[-2],mydea[-2],mybar[-2]
    if ma33>ma233 and p2[0]<p2[1] and p1[0]>p2[1]:
        buy=1
    return buy



def after_trading_end(context):
    return
    

