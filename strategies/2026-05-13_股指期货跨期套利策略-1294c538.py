# Clone from JoinQuant
# postId: 1294c538b5f7c2fdaf74368cf3222bda
# backtestId: a59cbf75fbb800f2b05151ff03ecd7f6
# title: 股指期货跨期套利策略

import statsmodels.api as sm
from statsmodels import regression
import numpy as np
import pandas as pd
import time 
from datetime import date
from jqdata import *
import datetime
from dateutil.relativedelta import relativedelta
import matplotlib.pyplot as plt
from statsmodels.tsa.stattools import adfuller
'''
================================================================================
总体回测前
================================================================================
'''

#总体回测前要做的事情
def initialize(context):
    set_params()        #1设置策参数
    set_variables()     #2设置中间变量
    set_backtest()      #3设置回测条件
    set_subportfolios([SubPortfolioConfig(cash=0 ,type='stock'),SubPortfolioConfig(cash=context.portfolio.total_value ,type='index_futures')])
    

#1
#设置策参数
def set_params():
    g.yb=63
    g.start=' 09:30:00'
    g.end=' 14:20:00'
#2
#设置中间变量
def set_variables():
    #标记是哪种仓位的买卖操作
    g.count_1,g.count_2=0,0
#3
#设置回测条件
def set_backtest():
    set_option('use_real_price', True) #用真实价格交易
    log.set_level('order', 'error')
    set_slippage(FixedSlippage(0))     #将滑点设置为0

'''
================================================================================
每天开盘前
================================================================================
'''
#每天开盘前要做的事情
def before_trading_start(context):
    #设置股票交易手续费
    set_slip_fee(context)
    g.side=0
#4 根据不同的时间段设置滑点与手续费
def set_slip_fee(context):
    # 将滑点设置为0
    set_slippage(FixedSlippage(0)) 
    # 根据不同的时间段设置手续费
    dt=context.current_dt
    # 设置期货合约保证金和手续费
    #15-09-07之前，保证金费率及交易手续费都较低，15-09-07之后保证金费率及交易手续费都变得较高，且在此之后每天最逗只能交易10手
    if dt<datetime.datetime(2012,9,24):
        #期货合约保证金
        g.futures_margin_rate = 0.12 
        #手续费
        set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.00005, close_commission=0.00005, close_today_commission=0.00005, min_commission=0), type='index_futures')
        #每日最多交易手数,之前没有交易限制
        g.count=float('inf')
    elif dt<datetime.datetime(2015,8,28):
        g.futures_margin_rate = 0.12
        set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.000025, close_commission=0.000025, close_today_commission=0.000025, min_commission=0), type='index_futures')
        g.count=float('inf')
    elif dt<datetime.datetime(2015,9,6):
        g.futures_margin_rate = 0.4
        set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.000025, close_commission=0.000025, close_today_commission=0.00115, min_commission=0), type='index_futures')
        g.count=float('inf')
    else:
        g.futures_margin_rate = 0.4
        set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.000025, close_commission=0.000025, close_today_commission=0.0023, min_commission=0), type='index_futures')
        g.count=5
    set_option('futures_margin_rate', g.futures_margin_rate)


'''
================================================================================
每天交易时
================================================================================
'''

#6
#每个交易日需要运行的函数
def handle_data(context,data):
    #获取交易信号
    signal=get_signal(context)
    #根据交易信号进行建仓平仓
    rebalance(context,signal)




#7        
#获取交易信号        
def get_signal(context):
    #取今天交易日期字符串
    day=context.current_dt.strftime('%Y-%m-%d')
    #获取最近相邻两月份过去240分钟的的股指期货价格数据
    df = attribute_history(get_current_month_future(context,'IF'),240,'1m','close')
    df1= attribute_history(get_next_month_future(context,'IF'),240,'1m','close')
    #取出pd.Series数据，后面回归用
    ts = df['close']  # 生成pd.Series对象
    ts1=df1['close']
    # 查看数据格式，并排除数据错误所带来的误差
    #将上述所得数据取对数
    ts_log,ts1_log = np.log(ts),np.log(ts1)
    x1,y1=ts_log.values,ts1_log.values
    #将pd.Series转化为np.array
    x=np.array(x1)
    X=sm.add_constant(x)
    y=np.array(y1)
    results = sm.OLS(y, X).fit()
    resid=y-(results.params[0]+results.params[1]*x)
    #记录残差项
    resid1=pd.Series(resid)
    resid1.dropna(inplace=True)    
    
    if len(resid1)>0:

        #对残差项进行ADF检验，并记录检验p值
        p_value=testStationarity(resid1)['p-value']
        
        print (context.current_dt,p_value)
        #将ADF检验的p临界值设为0.01，当p小于0.01时拒绝原假设，认为序列平稳
        if(p_value<0.01):
            f1,f2=get_current_month_future(context,'IF'),get_next_month_future(context,'IF')
            #取过去1分钟的两相邻月份股市期货收盘价
            df_01=attribute_history(f1,1,'1m',fields='close')
            df_02=attribute_history(f2,1,'1m',fields='close')
            df_1=np.log(df_01)
            df_2=np.log(df_02)
            #带入之前回归得到的方程计算每一分钟的残差resid_2
            resid_2=np.array(df_2)-results.params[0]-results.params[1]*np.array(df_1)
            resid_3=resid_2/resid1.std()
            return resid_3
        else:
            #如果resid_1不平稳，则返回一个较大的数
            return 100
    else:
        return 100

#8            
#根据交易信号进行建仓或者平仓
def rebalance(context,signal):
    resid_3=signal
    #获取最近相邻两月份从9:30到14:20的股指期货价格
    f1,f2=get_current_month_future(context,'IF'),get_next_month_future(context,'IF')
    #此处用了个未来函数，查一下未来成交量
    t1,t2=get_price(f1,count=1,end_date=context.current_dt,frequency='1m',fields='volume'),get_price(f2,count=1,end_date=context.current_dt,frequency='1m',fields='volume')
    #取过去1分钟的两相邻月份股市期货收盘价
    df_01=attribute_history(f1,1,'1m',fields='close')
    df_02=attribute_history(f2,1,'1m',fields='close')
    print (df_01['close'],df_02['close'])
    if(len(df_01['close'].dropna())!=0 and len(df_02['close'].dropna())!=0):
        t=min(int(t1['volume'].values/10),int(t2['volume'].values/10),int((context.portfolio.total_value/2)/(300*g.futures_margin_rate*df_01['close'].values)),int((context.portfolio.total_value/2)/(300*g.futures_margin_rate*df_02['close'].values)),(g.count))
        print('t:%d'%t)
        #根据signal值选择建仓或者平仓
        if(resid_3>1.0 and resid_3 <2 and g.count_1==0 and g.count_2==0):
            if(context.current_dt.strftime('%H:%M')<'14:59'):
    
                #将仓位中的钱一半进入低估期货的长头寸，一半进入高估期货的短头寸
                order_target(f1,t,side='long',pindex=1)
                order_target(f2,t,side='short',pindex=1)
                g.count=g.count-t
                print (g.count)
                g.count_1=1
        elif(resid_3<-1 and resid_3>-2 and g.count_1==0 and g.count_2==0):
            if(context.current_dt.strftime('%H:%M')<'14:59'):
                #将仓位中的钱一半进入低估期货的长头寸，一半进入高估期货的短头寸
                order_target(f1,t,side='short',pindex=1)
                order_target(f2,t,side='long',pindex=1)
                g.count=g.count-t
                print (g.count)
                g.count_2=1
        elif(abs(resid_3)<1 or abs(resid_3)>2):
            #根据之前记录的仓位信息进行平仓，或者当临近收盘时将仍为平仓的仓位平仓
            if(g.count_1==1):
                #平仓后将记号恢复为0
                g.count_1=0
                order_target(f1,0,side='long',pindex=1)
                order_target(f2,0,side='short',pindex=1)
                print(context.portfolio.total_value)
            elif(g.count_2==1):
                #平仓后将记号恢复为0
                g.count_2=0
                order_target(f1,0,side='short',pindex=1)
                order_target(f2,0,side='long',pindex=1)
                print(context.portfolio.total_value)

#9
# 取当月连续string，symbol是'IF','IC','IH'
# 输出例如'IF1508.CCFX'
def get_current_month_future(context, symbol):
    dt = context.current_dt
    month_begin_day = datetime.date(dt.year, dt.month, 1).isoweekday()
    third_friday_date = 20-month_begin_day + 7*(month_begin_day>5)
    # 如果没过第三个星期五或者第三个星期五（包括）至昨日的所有天都停盘
    if dt.day<=third_friday_date or (dt.day>third_friday_date and not any([datetime.date(dt.year, dt.month, third_friday_date+i) in get_all_trade_days() for i in range(dt.day-third_friday_date)])):
        year = str(dt.year)[2:]
        month = str(dt.month)
    else:
        year = str(dt.year+dt.month//12)[2:]
        month = str(dt.month%12+1)
    if len(month)==1:
        month = '0'+month
    return(symbol+year+month+'.CCFX')

#10
# 取下月连续string
def get_next_month_future(context, symbol):
    dt = context.current_dt
    month_begin_day = datetime.date(dt.year, dt.month, 1).isoweekday()
    third_friday_date = 20-month_begin_day + 7*(month_begin_day>5)
    # 如果没过第三个星期五或者第三个星期五（包括）至昨日的所有天都停盘
    if dt.day<=third_friday_date or (dt.day>third_friday_date and not any([datetime.date(dt.year, dt.month, third_friday_date+i) in get_all_trade_days() for i in range(dt.day-third_friday_date)])):
        year = str(dt.year+dt.month//12)[2:]
        month = str(dt.month%12+1)
    else:
        next_dt = dt + relativedelta(months=2)
        year = str(dt.year+(dt.month+1)//12)[2:]
        month = str((dt.month+1)%12+1)
    if len(month)==1:
        month = '0'+month
    return(symbol+year+month+'.CCFX')
    
#11
#做ADF检验
def testStationarity(ts):
    dftest = adfuller(ts)
    # 对上述函数求得的值进行语义描述，即取t值，p值，滞后长度，样本个数
    dfoutput = pd.Series(dftest[0:4], index=['Test Statistic','p-value','#Lags Used','Number of Observations Used'])
    for key,value in dftest[4].items():
        dfoutput['Critical Value (%s)'%key] = value
    return dfoutput


'''
================================================================================
每天收盘后
================================================================================
'''
#12
# 每日收盘后要做的事情（本策略中不需要）
def after_trading_end(context):
    return
