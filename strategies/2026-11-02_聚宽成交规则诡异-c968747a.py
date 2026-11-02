# Clone from JoinQuant
# postId: c968747adabef5d82a78e8479436c5ef
# backtestId: 3c6899a02024e9a856db3e7ad2c5f4df
# title: 聚宽成交规则诡异····

from jqdata import *
from jqlib.technical_analysis import *


def initialize(context):
    run_daily(period,time='every_bar')
    g.security = '600048.XSHG'
    set_benchmark('600048.XSHG')
    set_option('use_real_price', True)
    g.first_bar_open = 0.0
    g.n = 3

def period(context):
    
    security = g.security
    
    #获取当前的现金总量
    cash = context.portfolio.cash
    start_cash = context.portfolio.starting_cash
    #获取当前持仓
    closeable_amount = context.portfolio.positions[security].closeable_amount
    #获取当前分钟线的时间，获取当前分钟线的最新价格
    current_date = context.current_dt.date()
    
    previous_date = context.previous_date
    current_time = context.current_dt.time().strftime("%H%M%S")
    current_price = get_current_data()
    current_price = current_price[security].last_price
    total_amount = context.portfolio.positions[security].total_amount
    
    df_p_price = get_price(security, end_date=current_date, frequency='daily', \
    fields=['high','low'], fq=None, count=(g.n+1))
    h4=df_p_price['high'][1]
    h5=df_p_price['high'][2]
    l4=df_p_price['low'][1]
    l5=df_p_price['low'][2]
    
    p_1_date = get_trade_days(end_date=current_date, count=(g.n+1))[0]
    p_2_date = get_trade_days(end_date=current_date, count=(g.n+1))[1]
    p_3_date = get_trade_days(end_date=current_date, count=(g.n+1))[2]
    
    MA1 = MA(security, p_1_date, timeperiod=5)[security]
    MA2 = MA(security, p_2_date, timeperiod=5)[security]
    MA3 = MA(security, p_3_date, timeperiod=5)[security]
    
    int_MA5=2
    if MA1 < MA2 and MA2 < MA3:
        int_MA5=1
    elif MA1 > MA2 and MA2 > MA3:
        int_MA5=0
    
    
        #当前最高价、最低价、开盘价、收盘价
    df_price = get_price(security, start_date=current_date, end_date=current_date, \
    frequency='daily', fields=['open','high','low','close'], fq=None)
    current_open = df_price['open'][0]
    current_high = df_price['high'][0]
    current_low = df_price['low'][0]
    current_close = df_price['close'][0]
    
    
    sell_price = round(current_open * 1.01,2)
    buy_price = round(current_open * 0.99,2)
    
    if  total_amount < 100 and cash == start_cash :
        order(security, 6000)
        print("first_buying__________ %s" % (security))
    
    if int_MA5 == 1 and h5 > h4 and current_date.strftime("%Y%m%d") != '20180102':  

        if current_time == '093000':
            order(security, 6000)
            order(security, -6000, LimitOrderStyle(sell_price))
        elif current_time == '145900' :
            order_target(security, 6000)
            
    elif int_MA5 == 0 and l5 < l4 and current_date.strftime("%Y%m%d") != '20180102':    

        if current_time == '093000':
            order(security, -6000)
            order(security, 6000, LimitOrderStyle(buy_price))
        elif current_time == '145900' :
            order_target(security, 6000)
        