# Clone from JoinQuant
# postId: 026ca994b02f40b79ea5a6e3a936fdc5
# backtestId: 22a66d1e7bf40bd5d8ce92c4547d5fbd
# title: Delta对冲实现复制策略

# 导入函数库
from jqdata import *
import pandas as pd
import numpy as np
from pandas import Series
from scipy import stats

def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('RB9999.XSGE')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')
    # 输出内容到日志 log.info()

    ### 期货相关设定 ###
    # 设定账户为金融账户
    set_subportfolios([SubPortfolioConfig(cash=context.portfolio.starting_cash, type='index_futures')])
    # 螺纹钢手续费：万分之一，平今仓万分之一
    set_order_cost(OrderCost(open_commission=0.0001, close_commission=0.0001,close_today_commission=0.0001), type='futures')
    # 设定保证金比例9%（RB1901）
    set_option('futures_margin_rate', 0.09)
    
    g.future= 'RB1901.XSGE'
    F0=3725
    K=F0*1.05
    r=0.015
    sigma=0.20119
    
    df=get_price('RB1901.XSGE', start_date='2018-06-15', end_date='2018-08-11', frequency='daily', fields=None, skip_paused=False, fq='pre', count=None)
    clospr=df['close']
    clospr=Series.as_matrix(clospr)
    
    ttm=np.zeros(40)
    ttm[0]=0.169
    for x in range(1,40):
        ttm[x]=ttm[x-1]-(0.165/39)

    Delta=delta(clospr,ttm,K,r,sigma)
    g.Delta=1000*Delta
    
    print g.Delta
    print get_price('RB1901.XSGE', start_date='2018-08-10', end_date='2018-08-11', frequency='daily', fields=None, skip_paused=False, fq='pre', count=None)
    run_daily(market_open, time='every_bar')

def market_open(context):
    ti=len(get_trade_days(start_date='2018-06-15', end_date=context.current_dt, count=None))
    if  ti == 1:
        order(g.future, g.Delta[0] , side='long', pindex=0)
    elif ti == 40:
        order(g.future, -g.Delta[38] , side='long', pindex=0)
    else:
        order(g.future, g.Delta[ti-1]-g.Delta[ti-2] , side='long', pindex=0)
        
def delta(F0,T,K,r,sigma):
    d1 = np.exp(-r*T)*(np.log(F0/K)+(0.5*sigma**2)*T)/(sigma*np.sqrt(T))
    delta = stats.norm.cdf(d1,0.0,1.0)
    return delta
















########################## 获取期货合约信息，请保留 #################################
# 获取当天时间正在交易的期货主力合约
def get_future_code(symbol):
    future_code_list = {'A':'A9999.XDCE', 'AG':'AG9999.XSGE', 'AL':'AL9999.XSGE', 'AU':'AU9999.XSGE',
                        'B':'B9999.XDCE', 'BB':'BB9999.XDCE', 'BU':'BU9999.XSGE', 'C':'C9999.XDCE',
                        'CF':'CF9999.XZCE', 'CS':'CS9999.XDCE', 'CU':'CU9999.XSGE', 'ER':'ER9999.XZCE',
                        'FB':'FB9999.XDCE', 'FG':'FG9999.XZCE', 'FU':'FU9999.XSGE', 'GN':'GN9999.XZCE',
                        'HC':'HC9999.XSGE', 'I':'I9999.XDCE', 'IC':'IC9999.CCFX', 'IF':'IF9999.CCFX',
                        'IH':'IH9999.CCFX', 'J':'J9999.XDCE', 'JD':'JD9999.XDCE', 'JM':'JM9999.XDCE',
                        'JR':'JR9999.XZCE', 'L':'L9999.XDCE', 'LR':'LR9999.XZCE', 'M':'M9999.XDCE',
                        'MA':'MA9999.XZCE', 'ME':'ME9999.XZCE', 'NI':'NI9999.XSGE', 'OI':'OI9999.XZCE',
                        'P':'P9999.XDCE', 'PB':'PB9999.XSGE', 'PM':'PM9999.XZCE', 'PP':'PP9999.XDCE',
                        'RB':'RB9999.XSGE', 'RI':'RI9999.XZCE', 'RM':'RM9999.XZCE', 'RO':'RO9999.XZCE',
                        'RS':'RS9999.XZCE', 'RU':'RU9999.XSGE', 'SF':'SF9999.XZCE', 'SM':'SM9999.XZCE',
                        'SN':'SN9999.XSGE', 'SR':'SR9999.XZCE', 'T':'T9999.CCFX', 'TA':'TA9999.XZCE',
                        'TC':'TC9999.XZCE', 'TF':'TF9999.CCFX', 'V':'V9999.XDCE', 'WH':'WH9999.XZCE',
                        'WR':'WR9999.XSGE', 'WS':'WS9999.XZCE', 'WT':'WT9999.XZCE', 'Y':'Y9999.XDCE',
                        'ZC':'ZC9999.XZCE', 'ZN':'ZN9999.XSGE'}
    try:
        return future_code_list[symbol]
    except:
        return 'WARNING: 无此合约'


# 获取当天时间正在交易的股指期货合约
def get_stock_index_futrue_code(context,symbol,month='current_month'):
    '''
    获取当天时间正在交易的股指期货合约。其中:
    symbol:
            'IF' #沪深300指数期货
            'IC' #中证500股指期货
            'IH' #上证50股指期货
    month:
            'current_month' #当月
            'next_month'    #隔月
            'next_quarter'  #下季
            'skip_quarter'  #隔季
    '''
    display_name_dict = {'IC':'中证500股指期货','IF':'沪深300指数期货','IH':'上证50股指期货'}
    month_dict = {'current_month':0, 'next_month':1, 'next_quarter':2, 'skip_quarter':3}

    display_name = display_name_dict[symbol]
    n = month_dict[month]
    dt = context.current_dt.date()
    a = get_all_securities(types=['futures'], date=dt)
    try:
        df = a[(a.display_name == display_name) & (a.start_date <= dt) & (a.end_date >= dt)]
        return df.index[n]
    except:
        return 'WARRING: 无此合约'

# 获取当天时间正在交易的国债期货合约
def get_treasury_futrue_code(context,symbol,month='current'):
    '''
    获取当天时间正在交易的国债期货合约。其中:
    symbol:
            'T' #10年期国债期货
            'TF' #5年期国债期货
    month:
            'current' #最近期
            'next'    #次近期
            'skip'    #最远期
    '''
    display_name_dict = {'T':'10年期国债期货','TF':'5年期国债期货'}
    month_dict = {'current':0, 'next':1, 'skip':2}

    display_name = display_name_dict[symbol]
    n = month_dict[month]
    dt = context.current_dt.date()
    a = get_all_securities(types=['futures'], date=dt)
    try:
        df = a[(a.display_name == display_name) & (a.start_date <= dt) & (a.end_date >= dt)]
        return df.index[n]
    except:
        return 'WARRING: 无此合约'

# 获取金融期货合约到期日
def get_CCFX_end_date(fature_code):
    # 获取金融期货合约到期日
    return get_security_info(fature_code).end_date
