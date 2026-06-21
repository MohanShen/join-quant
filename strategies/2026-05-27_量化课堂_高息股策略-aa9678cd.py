# Clone from JoinQuant
# postId: aa9678cdd03286cc189b50a7e930e699
# backtestId: 956858ac6e0e3b21e2fc353b4fd4a48e
# title: 【量化课堂】高息股策略

from jqdata import jy
import numpy as np
import pandas as pd
import datetime


import time
#1 设置参数
def set_params():
    set_benchmark('000300.XSHG') # 设置基准收益
    run_monthly(Transfer, 1) # 按月回测


#2 设置中间变量
def set_variables():
    g.size_start = 5 #股息率从小到大排列，从g.size_start开始
    g.size_end=20 #股息率从小到大排列，一直排列到g.size_end开始
    g.months = [1,2,3,4,5,6,7,10] #交易运行的月份
    g.stocks=[]

#3 设置回测条件
def set_backtest():
    set_option('use_real_price', True) #用真实价格交易
    log.set_level('order', 'error')

def initialize(context):
    set_params()    #1设置策参数
    set_variables() #2设置中间变量
    set_backtest()  #3设置回测条件

'''
=================================================
每天开盘前
=================================================
'''
#每天开盘前要做的事情
def before_trading_start(context):
    set_slip_fee(context)
    g.stocks=get_index_stocks('000300.XSHG')
    g.stocks=set_feasible_stocks(g.stocks,context)

#4
# 根据不同的时间段设置滑点与手续费
def set_slip_fee(context):
    # 将滑点设置为0
    set_slippage(FixedSlippage(0))
    # 根据不同的时间段设置手续费
    dt=context.current_dt

    if dt>datetime.datetime(2013,1, 1):
        set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))

    elif dt>datetime.datetime(2011,1, 1):
        set_commission(PerTrade(buy_cost=0.001, sell_cost=0.002, min_cost=5))

    elif dt>datetime.datetime(2009,1, 1):
        set_commission(PerTrade(buy_cost=0.002, sell_cost=0.003, min_cost=5))

    else:
        set_commission(PerTrade(buy_cost=0.003, sell_cost=0.004, min_cost=5))


#5
# 设置可行股票池：过滤掉当日停牌的股票
# 输入：initial_stocks为list类型,表示初始股票池； context（见API）
# 输出：unsuspened_stocks为list类型，表示当日未停牌的股票池，即：可行股票池
def set_feasible_stocks(initial_stocks,context):
    # 判断初始股票池的股票是否停牌，返回list
    paused_info = []
    current_data = get_current_data()
    for i in initial_stocks:
        paused_info.append(current_data[i].paused)
    df_paused_info = pd.DataFrame({'paused_info': paused_info},index = initial_stocks)
    unsuspened_stocks =list(df_paused_info.index[df_paused_info.paused_info == False])
    return unsuspened_stocks



'''
=================================================
每日交易时
=================================================
'''

def Transfer(context):
    #在指定月份（指定月份在g.months这一list中设定）卖卖股票
    #上述设定主要是防止换仓太过频繁
    if context.current_dt.month in g.months:
        tobuy=get_signal(context,g.stocks)
        sell_the_stocks(context,tobuy)
        buy_the_stocks(context,tobuy)

#6 获得交易信号
#（在这里即是获得高息股的股票list，记为Buylist）
#注：为了减少重复计算，本函数没有输出，而是将Buylist设置为全局变量
def get_signal(context,stocks):
    year = context.current_dt.year-1

    #将当前股票池转换为聚源的内部股票代码
    stocks_symbols=jy.run_query(query(
        jy.SecuMain.InnerCode,
        jy.SecuMain.SecuCode,
    ).filter(
        jy.SecuMain.SecuCode.in_([s[0:6] for s in stocks])
    ))
    stocks_symbol = list(stocks_symbols.InnerCode)

    #如果知道前一年的分红，那么得到前一年的分红数据
    df1 = jy.run_query(query(
        jy.LC_Dividend.InnerCode,#股票代码
        jy.LC_Dividend.CashDiviRMB,#股票分红
        jy.LC_Dividend.AdvanceDate,#分红消息的时间
    ).filter(
        jy.LC_Dividend.IfDividend == 1,  #有分红的股票
        jy.LC_Dividend.EndDate.contains(str(year)),
    #            #且分红信息在上一年度
        jy.LC_Dividend.InnerCode.in_(stocks_symbol)
    )).dropna(axis=0)

    stocks_symbol_this_year=list(df1['InnerCode'])

    #如果前一年的分红不知道，那么知道前两年的分红数据
    df2 = jy.run_query(query(
        jy.LC_Dividend.InnerCode,#股票代码
        jy.LC_Dividend.CashDiviRMB,#股票分红
        jy.LC_Dividend.AdvanceDate,#分红消息的时间
    ).filter(
        jy.LC_Dividend.IfDividend == 1,  #有分红的股票
        jy.LC_Dividend.EndDate.contains(str(year - 1)),
    #            #且分红信息在上一年度
        jy.LC_Dividend.InnerCode.in_(stocks_symbol),
        jy.LC_Dividend.InnerCode.notin_(stocks_symbol_this_year)
    )).dropna(axis=0)

    df= pd.concat((df2,df1))
    # 下面四行代码用于选择在当前时间内能已知去年股息信息的股票
    df['pubtime'] = df['AdvanceDate'].apply(lambda dt: dt.strftime('%Y%m%d')).astype(int)
    currenttime  = int(context.current_dt.strftime('%Y%m%d'))

    # 筛选出pubtime小于当前时期的股票，然后剔除'AdvanceDate','pubtime','InnerCode'三列
    df = df[(df.pubtime < currenttime)]

    df['InnerCode'] = df['InnerCode'].replace(
        stocks_symbols.set_index('InnerCode')['SecuCode'].map(normalize_code).to_dict()
    )
    df.index=list(df['InnerCode'])

    df=df.drop(['InnerCode','pubtime','AdvanceDate'],axis=1)

    #接下来这一步是考虑多次分红的股票，因此需要累加股票的多次分红
    #按照股票代码分堆
    df = df.groupby(df.index).sum()

    #得到当前股价
    Price=history(1, unit='1d', field='close', security_list=list(df.index), df=True, skip_paused=False, fq='pre')
    Price=Price.iloc[0]
    df['pre_close']=Price


    #计算股息率 = 股息/股票价格
    df['divpercent'] = df['CashDiviRMB'] / df['pre_close']


    #将股息率排序，取股息率最高的前五（g.size）股票，作为要买入的股票
    try:
        df=df.sort(columns=['divpercent'], axis=0, ascending=False)
    except AttributeError:
        df=df.sort_values(by=['divpercent'], axis=0, ascending=False)

    log.info(df)

    Buylist =list(df.index)[g.size_start:g.size_end]
    return Buylist


#7 卖出股票
def sell_the_stocks(context,Buylist):
    #如果有持仓，就卖掉那些不在上面buylist中的股票
    if len(context.portfolio.positions) != 0:
        for stock in context.portfolio.positions.keys():
            if stock not in Buylist:
                order_target(stock, 0)

#8 买入股票
def buy_the_stocks(context,Buylist):
    #如果有需要买入的股票，就平均分配资金买入
    if  len(Buylist)-len(context.portfolio.positions)>0:
        value = context.portfolio.portfolio_value / (g.size_end-g.size_start+1)
        for stock in Buylist:
            #（已买入的股票无需再次买入）
            order_target_value(stock,value)
