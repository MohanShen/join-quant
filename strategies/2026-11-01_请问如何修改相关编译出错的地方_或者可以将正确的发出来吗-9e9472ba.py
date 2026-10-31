# Clone from JoinQuant
# postId: 9e9472baca976e35a3dc318e34766987
# backtestId: 21073badae271f9be97f02677482aaf1
# title: 请问如何修改相关编译出错的地方，或者可以将正确的发出来吗？

#RSRS三因子模型选股
# 2010-11-30 到 2020-11-30, ￥10000000, 每天

import statsmodels.api as sm
from statsmodels import regression
import numpy as np
import pandas as pd
import time 
from datetime import date
from jqdata import *


'''
================================================================================
总体回测前c
================================================================================
'''
#总体回测前要做的事情
def initialize(context):
    set_params()        #1设置策参数
    set_variables()     #2设置中间变量
    set_backtest()      #3设置回测条件
    
#1
#设置策参数
def set_params():
    g.tc=18  # 调仓频率
    g.yb=63  # 样本长度
    g.N = 18
    g.M = 1100
    g.init = True
    g.cc=15   # 持仓数目
    g.NoF=3  # 三因子模型
#1-2
# 买入阈值
    g.buy =0.6
    g.sell = -0.7
    g.ans = []
    g.ans_rightdev= []
    g.Mysecurity = '000300.XSHG'
      # 计算2010年11月30日至回测开始日期的RSRS斜率指标
    prices = get_price(g.Mysecurity, '2010-11-30', context.previous_date, '1d', ['high', 'low']).dropna()
    highs = prices.high
    lows = prices.low
    
    g.ans = []
    for i in range(len(highs))[g.N:]:
        
        data_high = highs.iloc[i-g.N+1:i+1]
        
        data_low = lows.iloc[i-g.N+1:i+1]
        X = sm.add_constant(data_low)
        model = sm.OLS(data_high,X)
        results = model.fit()
        g.ans.append(results.params.low)
        #计算r2
        g.ans_rightdev.append(results.rsquared)
#2
#设置中间变量
def set_variables():
    g.t=0               #记录连续回测天数
    g.rf=0.04           #无风险利率
    g.if_trade=False    #当天是否交易
    
    #将2010-10-30至今所有交易日弄成列表输出
    today=date.today()     #取当日时间xxxx-xx-xx
    a=get_all_trade_days() #取所有交易日:[datetime.date(2010, 11, 30)到datetime.date(2020, 11, 230)]
    g.ATD=['']*len(a)      #获得len(a)维的单位向量
    for i in range(0,len(a)):
        g.ATD[i]=a[i].isoformat() #转换所有交易日为iso格式:2010-11-30到2020-11-30
        #列表会取到2020-11-30，现在需要将大于今天的列表全部砍掉
        if today<=a[i]:
            break
    g.ATD=g.ATD[:i]        #iso格式的交易日：2010-11-30至今
    
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
    if g.t%g.tc==0:
        #每g.tc天，交易一次行
        g.if_trade=True 
        # 设置手续费与手续费
        set_slip_fee(context) 
        # 设置可行股票池：获得当前开盘的沪深300股票池并剔除当前或者计算样本期间停牌的股票
        g.all_stocks = set_feasible_stocks(get_index_stocks('000300.XSHG'),g.yb,context)
    g.t+=1

#4 根据不同的时间段设置滑点与手续费
def set_slip_fee(context):
    # 将滑点设置为0
    set_slippage(FixedSlippage(0)) 
    # 根据不同的时间段设置手续费
    dt=context.current_dt
    log.info(type(context.current_dt))
    
    if dt>datetime.datetime(2013,1, 1):
        set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5)) 
        
    elif dt>datetime.datetime(2011,1, 1):
        set_commission(PerTrade(buy_cost=0.001, sell_cost=0.002, min_cost=5))
                
    else:
        set_commission(PerTrade(buy_cost=0.003, sell_cost=0.004, min_cost=5))


#5
# 设置可行股票池：
# 过滤掉当日停牌的股票,且筛选出前days天未停牌股票
# 输入：stock_list-list类型,样本天数days-int类型，context（见API）
# 输出：颗星股票池-list类型
def set_feasible_stocks(stock_list,days,context):
    # 得到是否停牌信息的dataframe，停牌的1，未停牌得0
    suspened_info_df = get_price(list(stock_list), start_date=context.current_dt, end_date=context.current_dt, frequency='daily', fields='paused')['paused'].T
    # 过滤停牌股票 返回dataframe
    unsuspened_index = suspened_info_df.iloc[:,0]<1
    # 得到当日未停牌股票的代码list:
    unsuspened_stocks = suspened_info_df[unsuspened_index].index
    # 进一步，筛选出前days天未曾停牌的股票list:
    feasible_stocks=[]
    current_data=get_current_data()
    for stock in unsuspened_stocks:
  # 计算2010年11月30日至回测开始日期的RSRS斜率指标
    prices = get_price(g.Mysecurity, '2010-11-30', context.previous_date, '1d', ['high', 'low']).dropna()
    highs = prices.high
    lows = prices.low
    g.ans = []
    for i in range(len(highs))[g.N:]:
        data_high = highs.iloc[i-g.N+1:i+1]
        data_low = lows.iloc[i-g.N+1:i+1]
        X = sm.add_constant(data_low)
        model = sm.OLS(data_high,X)
        results = model.fit()
        g.ans.append(results.params.low)
        #计算r2
        g.ans_rightdev.append(results.rsquared)

#择时RSRS计算
def zheshi():
    #RSRS择时指标计算
    security = g.Mysecurity
    beta=0
    r2=0
    if g.init:
        g.init = False
    else:
        # RSRS斜率指标定义
        prices = attribute_history(security, g.N, '1d', ['high', 'low'],fq=None) #指数无复权,个股应该使用前复权
        highs = prices.high
        lows = prices.low
        X = sm.add_constant(lows)
        model = sm.OLS(highs, X)
        beta = model.fit().params.low
        g.ans.append(beta)
        #计算r2
        r2=model.fit().rsquared
        g.ans_rightdev.append(r2)
    # 计算标准化的RSRS指标
    # 计算均值序列    
    section = g.ans[-g.M:]
    # 计算均值序列
    mu = np.mean(section)
    # 计算标准化RSRS指标序列
    sigma = np.std(section)
    zscore = (section[-1]-mu)/sigma  
    #计算右偏RSRS标准分
    zscore_rightdev= zscore*beta*r2
    return zscore_rightdev
        if sum(attribute_history(stock, days, unit='1d',fields=('paused'),skip_paused=False))[0]==0:
            feasible_stocks.append(stock)
    return feasible_stocks




'''
================================================================================
每天交易时
================================================================================
'''

#每天交易时要做的事情
def handle_data(context, data):
    if g.if_trade==True:
        # 获得调仓日的日期字符串
        todayStr=str(context.current_dt)[0:10]#去掉时分秒，保留年月日
        # 计算每个股票的ai
        ais=FF(g.all_stocks,getDay(todayStr,-g.yb),getDay(todayStr,-1),g.rf)
        # 为每个持仓股票分配资金
        g.everyStock=context.portfolio.portfolio_value/g.cc
        # 依打分排序，当前需要持仓的股票
        try:
            stock_sort=ais.sort('score')['code']
        except AttributeError:
            stock_sort=ais.sort_values('score')['code']
        order_stock_sell(context,data,stock_sort)
                
        order_stock_buy(context,data,stock_sort)       
                
    g.if_trade=False


#6
#获得卖出信号，并执行卖出操作
#输入：context, data，已排序股票列表stock_sort-list类型
#输出：none
def order_stock_sell(context,data,stock_sort):
    # 对于不需要持仓的股票，全仓卖出
    for stock in context.portfolio.positions:
        #除去排名前g.cc个股票（选股！）
        if stock not in stock_sort[:g.cc]:
            stock_sell = stock
            order_target_value(stock_sell, 0)


#7
#获得买入信号，并执行买入操作
#输入：context, data，已排序股票列表stock_sort-list类型
#输出：none
def order_stock_buy(context,data,stock_sort):
    # 对于需要持仓的股票，按分配到的份额买入
    for stock in stock_sort:
        stock_buy = stock
        order_target_value(stock_buy, g.everyStock)


#8
#按照Fama-French规则计算k个参数并且回归，计算出股票的alpha并且输出
#输入：stocks-list类型； begin，end为“yyyy-mm-dd”类型字符串,rf为无风险收益率-double类型
#输出：最后的打分-dataframe类型
def FF (stocks,begin,end,rf):
    LoS=len(stocks)
    #查询三因子/五因子的语句
    q = query(
        valuation.code,
        valuation.market_cap,
        (balance.total_owner_equities/valuation.market_cap/100000000.0).label("BTM"),
        indicator.roe,
        balance.total_assets.label("Inv")
    ).filter(
        valuation.code.in_(stocks)
    )
    
    df = get_fundamentals(q,begin)
    
    #计算5因子再投资率的时候需要跟一年前的数据比较，所以单独取出计算
    ldf=get_fundamentals(q,getDay(begin,-252))
    # 若前一年的数据不存在，则暂且认为Inv=0
    if len(ldf)==0:
        ldf=df
    df["Inv"]=np.log(df["Inv"]/ldf["Inv"])
    
    
    # 选出特征股票组合
    try:
        S=df.sort('market_cap')['code'][:LoS/3]
        B=df.sort('market_cap')['code'][LoS-LoS/3:]
        L=df.sort('BTM')['code'][:LoS/3]
        H=df.sort('BTM')['code'][LoS-LoS/3:]
        W=df.sort('roe')['code'][:LoS/3]
        R=df.sort('roe')['code'][LoS-LoS/3:]
        C=df.sort('Inv')['code'][:LoS/3]
        A=df.sort('Inv')['code'][LoS-LoS/3:]
    except AttributeError:
        S=df.sort_values('market_cap')['code'][:int(LoS/3)]
        B=df.sort_values('market_cap')['code'][LoS-int(LoS/3):]
        L=df.sort_values('BTM')['code'][:int(LoS/3)]
        H=df.sort_values('BTM')['code'][LoS-int(LoS/3):]
        W=df.sort_values('roe')['code'][:int(LoS/3)]
        R=df.sort_values('roe')['code'][LoS-int(LoS/3):]
        C=df.sort_values('Inv')['code'][:int(LoS/3)]
        A=df.sort_values('Inv')['code'][LoS-int(LoS/3):]
    
    # 获得样本期间的股票价格并计算日收益率
    df2 = get_price(stocks,begin,end,'1d')
    df3=df2['close'][:]
    df4=np.diff(np.log(df3),axis=0)+0*df3[1:]
    #求因子的值
    SMB=sum(df4[S].T)/len(S)-sum(df4[B].T)/len(B)
    HMI=sum(df4[H].T)/len(H)-sum(df4[L].T)/len(L)
    RMW=sum(df4[R].T)/len(R)-sum(df4[W].T)/len(W)
    CMA=sum(df4[C].T)/len(C)-sum(df4[A].T)/len(A)
    
    #用沪深300作为大盘基准
    dp=get_price('000300.XSHG',begin,end,'1d')['close']
    RM=diff(np.log(dp))-rf/252
    
    #将因子们计算好并且放好
    X=pd.DataFrame({"RM":RM,"SMB":SMB,"HMI":HMI,"RMW":RMW,"CMA":CMA})
    #取前g.NoF个因子为策略因子
    factor_flag=["RM","SMB","HMI","RMW","CMA"][:g.NoF]
    print (factor_flag)
    X=X[factor_flag]
    
    # 对样本数据进行线性回归并计算ai
    t_scores=[0.0]*LoS
    for i in range(LoS):
        t_stock=stocks[i]
        sample=pd.DataFrame()
        t_r=linreg(X,df4[t_stock]-rf/252,len(factor_flag))
        t_scores[i]=t_r[0]
    
    #这个scores就是alpha 
    scores=pd.DataFrame({'code':stocks,'score':t_scores})
    return scores


#9
# 辅助线性回归的函数
# 输入:X:回归自变量 Y:回归因变量 完美支持list,array,DataFrame等三种数据类型
#      columns:X有多少列，整数输入，不输入默认是3（）
# 输出:参数估计结果-list类型
def linreg(X,Y,columns=3):
    X=sm.add_constant(array(X))
    Y=array(Y)
    if len(Y)>1:
        results = regression.linear_model.OLS(Y, X).fit()
        return results.params
    else:
        return [float("nan")]*(columns+1)


#10
# 日期计算之获得某个日期之前或者之后dt个交易日的日期
# 输入:precent-当前日期-字符串（如2020-11-30）
#      dt-整数，如果要获得之前的日期，写负数，获得之后的日期，写正数
# 输出:字符串（如2020-11-30）
def getDay(precent,dt):
    for i in range(0,len(g.ATD)):
        if precent<=g.ATD[i]:
            t_temp = i
            if t_temp+dt>=0:
                return g.ATD[t_temp+dt]#present偏移dt天后的日期
            else:
                t= datetime.datetime.strptime(g.ATD[0],'%Y-%m-%d')+datetime.timedelta(days = dt)
                t_str=datetime.datetime.strftime(t,'%Y-%m-%d')
                return t_str




'''
================================================================================
每天收盘后
================================================================================
'''
#每天收盘后要做的事情
def after_trading_end(context):
    return
# 进行长运算（本模型中不需要）


