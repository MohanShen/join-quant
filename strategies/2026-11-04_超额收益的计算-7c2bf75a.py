# Clone from JoinQuant
# postId: 7c2bf75a7b6fcc449816862e8997700f
# backtestId: 55c83c556a9c6aa9064911601f80d71f
# title: 超额收益的计算

# 多因子策略-APT模型（Multi-factor） 
# 2019-01-02 到 2019-06-30

'''
目前处于起点2019-01-02(周三)，在昨天的中证全指(sample = get_index_stocks('000985.XSHG', date = None) )里
取符合条件（剔除 停牌,ST、*ST股票，不足3个月 等股票后的剩余股票）的股票，然后(df = get_fundamentals(q, date = None))
取上个交易日这些股票满足指定因子条件(.filter(
                        # 优选基本面质量较好的股票进行回归
                        valuation.pe_ratio / indicator.inc_net_profit_year_on_year>0,
                        valuation.pe_ratio / indicator.inc_net_profit_year_on_year<1,
                        valuation.code.in_(sample)))
的因子数据记为df,之后经过数据清洗得到df,再用同样方法取5个交易日(g.tc = 5)前因子数据记为df_p，
之后再把这5交易日的这些股票的收益率(Y = df[['momentum_value']])做为Y值,再把df_p中去掉'market_cap'
的其他因子数据值记为X_p,对于X_p和Y做线性回归，得到weights = linreg(X_p,Y)，再用得到的weights作
points = X.dot(weights[1:]) + weights[0]，得到这些股票对于未来5个交易日的预测收益率，再对于points
做排序，选出前50只股票;

'''
import math
import datetime
import numpy as np
import pandas as pd
from jqdata import *
# 导入多元线性规划需要的工具包
import statsmodels.api as sm
from statsmodels import regression
import datetime as dt
from datetime import date

'''
================================================================================
总体回测前
================================================================================
'''
#总体回测前要做的事情
def initialize(context):
    set_params()      # 设置策参数
    set_variables()   # 设置中间变量
    set_backtest()    # 设置回测条件
    

#设置策略参数
def set_params():
    g.tc = 5          # 设置调仓天数 # 5个交易日 
    g.stocknum = 50   # 持有股票数量


#设置中间变量
def set_variables():
    g.t = 0                # 记录回测运行的天数
    g.if_trade = False     # 当天是否交易
    
    #将2005-01-04至今所有交易日弄成列表输出
    today=date.today()     #取当日时间xxxx-xx-xx
    # print(today)       # 2020-10-21
    # print(type(today)) # <class 'datetime.date'>
    a=get_all_trade_days() #取所有交易日:[datetime.date(2005, 1, 4)到datetime.date(2020, 12, 31)]
    g.ATD=['']*len(a)      #获得len(a)维的单位向量
    # print(g.ATD)
    # ['', '', '', '',....]
    for i in range(0,len(a)):
        g.ATD[i]=a[i].isoformat() #转换所有交易日为iso格式:2005-01-04到2020-12-31
        #列表会取到2020-12-31，现在需要将大于今天的列表全部砍掉
        if today<=a[i]: # 
            break
    # print(i)
    g.ATD=g.ATD[:i]        
    # log.info(g.ATD)
    # ['2005-01-04', '2005-01-05', '2005-01-06',...'2020-10-19', '2020-10-20']


#设置回测条件
def set_backtest():
     
    # 设置对比基准
    set_benchmark('000300.XSHG') 
    # 使用真实价格
    set_option('use_real_price', True)
    # 设置报错等级
    log.set_level('order', 'error')


'''
================================================================================
每天开盘前
================================================================================
'''
# 每天开盘前要做的事。计算tiaocang
def before_trading_start(context):
    if g.t%g.tc==0:
        #每g.tc天，交易一次
        g.if_trade=True 
        # 设置手续费与手续费
        set_slip_fee(context) 
    g.t += 1
    

# 设置可行股票池：
# 过滤掉当日停牌的股票,且筛选出前days天未停牌股票
# 输入：stock_list为list类型,样本天数days为int类型，context（见API）
# 输出：list
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
        if sum(attribute_history(stock, days, unit='1d',fields=('paused'),skip_paused=False))[0]==0:
            feasible_stocks.append(stock)
    return feasible_stocks


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


# 过滤股票，过滤停牌退市ST股票，选股时使用
def filter_stock_ST(stock_list):
    curr_data = get_current_data()
    for stock in stock_list:
        if (curr_data[stock].paused) or (curr_data[stock].is_st) or ('ST' in curr_data[stock].name)\
            or ('*' in curr_data[stock].name)\
            or ('退' in curr_data[stock].name):
            stock_list.remove(stock)
    return stock_list


# 交易时使用，过滤每日开盘时的涨跌停股filter low_limit/high_limit    
def filter_stock_limit(stock_list):  
    curr_data = get_current_data()
    for stock in stock_list:
        price = curr_data[stock].day_open
        if (curr_data[stock].high_limit <= price) or (price <= curr_data[stock].low_limit):
            stock_list.remove(stock)
    return stock_list


# 可选项: 过滤上市180日以内次新股
def remove_new_stocks(security_list,context):
    #log.info(get_security_info(security_list[0]).start_date) # 1991-04-03
    #log.info(context.current_dt.date() - get_security_info(security_list[0]).start_date)
    # 10136 days, 0:00:00
    #log.info(type(context.current_dt.date() - get_security_info(security_list[0]).start_date))
    # <class 'datetime.timedelta'>
    #log.info((context.current_dt.date() - get_security_info(security_list[0]).start_date).days)
    # 10136
    for stock in security_list:
        days_public = (context.current_dt.date() - get_security_info(stock).start_date).days
        if days_public < 180:
            security_list.remove(stock)
    return security_list


# DF类型MAD数据清洗function，一次处理多列数据
def fun_normalizeData(df):
    '''
    df是:
              code     market_cap    ...       anon_2    anon_3
    0     000001.XSHE   1610.5846    ...     4.090362  0.894694
    1     000002.XSHE   2629.5259    ...     1.884783  0.115265
    2     000010.XSHE     26.7273    ...    -3.791897  0.007572
    3     000016.XSHE     78.0174    ...     1.130176  0.020864
    .....
    1324  603989.XSHG     78.5463    ...     1.122789  0.760972
    1325  603991.XSHG     13.5505    ...     0.713207  0.960245
    1326  603993.XSHG    812.1314    ...     1.275536  0.940128
    1327  603996.XSHG     22.6313    ...     2.866264  0.977009
    
    [1328 rows x 7 columns]
    '''
    #log.info(df.keys()) # df如果是srries返回的是索引,df是dataframe返回的是列名
    #log.info(df.keys())
    '''
    Index(['code', 'market_cap', 'anon_1', 'inc_net_profit_year_on_year',
    'inc_revenue_year_on_year', 'anon_2', 'anon_3'],
    dtype='object')
    '''
    for key in df.keys():
        
        if (key != 'code'):
            mad = func_mad(df[key])
           
            MA = np.mean(df[key])
            for i in range(len(df[key])):
                x = df.loc[i,key]
                if (x > MA + 3*mad):
                    x = MA + 3*mad
                elif (x < MA - 3*mad):
                    x = MA - 3*mad
    return df


# 求MAD绝对中位值
def func_mad(myData):
    
    return np.mean(np.absolute(myData - np.mean(myData)))    


# 取得股票某个区间内的所有收盘价（用于取前interval日和当前日 收盘价）
def getStockPrice(stock, interval): # 输入stock证券名，interval期
    h = attribute_history(stock, interval, unit='1d', fields=('close'), skip_paused=True)
    # log.info(type(h))          # <class 'pandas.core.frame.DataFrame'>
    # log.info(type(h['close'])) # <class 'pandas.core.series.Series'>
    return (h['close'].values[0] , h['close'].values[-1])
    # 0是第一个（interval周期的值,-1是最近的一个值(昨天收盘价)）
 

# 协助进行线性回归(SVR)
# 输入：factors是所有股票的上一期因子值-list，returns是股票上一期的收益
# 支持list,array,DataFrame等三种数据类型
def linreg(factors,returns):
    # 加入一列常数列，表示市场的状态以及因子以外没有考虑到的因素
    #log.info(factors)
    '''
                    LEV      IR_YOY     INP_YOY   ROE_PB    PE_G
    000001.XSHE   1.075471   14.21      7.3500  4.134018  0.885156
    000002.XSHE   1.177494   48.12     73.7200  1.915273  0.113426
    000010.XSHE   1.419399  -78.23   -278.8000 -3.768781  0.007618
    ......
    603991.XSHG   2.707745   47.38     35.5700  0.703932  0.972921
    603993.XSHG   1.915143   -0.46     16.4600  1.275536  0.940128
    603996.XSHG   1.468767   -4.54     14.0100  2.904769  0.964047
    
    [1325 rows x 5 columns]
    '''
    #log.info(returns)
    '''
                    momentum_value
    000001.XSHE       -0.004246
    000002.XSHE       -0.002513
    000010.XSHE       -0.057803
    .......
    603991.XSHG        0.000000
    603993.XSHG       -0.048101
    603996.XSHG       -0.028351
    
    [1325 rows x 1 columns]
    '''
    X = sm.add_constant(array(factors)) #在array(factors)前加上一列常数1，方便做带截距项的回归
    #log.info(X)
    '''
    [[1.0 1.07547135 14.21 7.35 4.13401785 0.88515647]
     [1.0 1.1774943000000002 48.12 73.72 1.91527349 0.11342648]
     [1.0 1.4193993 -78.23 -278.8 -3.76878109 0.00761836]
     ...
     [1.0 2.70774467 47.38 35.57 0.70393229 0.97292101]
     [1.0 1.91514322 -0.46 16.46 1.27553611 0.94012763]
     [1.0 1.46876707 -4.54 14.01 2.90476865 0.96404709]]
    '''
    Y = array(returns)
    #log.info(Y)
    '''
    [[-0.004246284501061459]
     [-0.002512562814070307]
     [-0.05780346820809257]
     ...
     [0.0]
     [-0.048101265822784955]
     [-0.028350515463917536]]
    '''
    # 进行多元线性回归
    results = regression.linear_model.OLS(Y, X).fit()
    #log.info(results.params)
    '''
    [-0.03306949668733328 0.0007440155274406572 4.420077871477438e-06
     -2.1601961345841375e-07 0.0017023724085484093 0.004018463443365391]
    '''
    #log.info(results.summary())
    '''
         OLS Regression Results                            
    ==============================================================================
    Dep. Variable:                      y   R-squared:                       0.024
    Model:                            OLS   Adj. R-squared:                  0.020
    Method:                 Least Squares   F-statistic:                     6.467
    Date:                Tue, 22 Sep 2020   Prob (F-statistic):           5.99e-06
    Time:                        14:29:53   Log-Likelihood:                 2461.9
    No. Observations:                1325   AIC:                            -4912.
    Df Residuals:                    1319   BIC:                            -4881.
    Df Model:                           5                                         
    Covariance Type:            nonrobust                                         
    ==============================================================================
                     coef    std err          t      P>|t|      [0.025      0.975]
    ------------------------------------------------------------------------------
    const         -0.0331      0.002    -16.166      0.000      -0.037      -0.029
    x1             0.0007      0.000      1.914      0.056   -1.85e-05       0.002
    x2           4.42e-06   5.45e-06      0.812      0.417   -6.26e-06    1.51e-05
    x3          -2.16e-07   2.75e-07     -0.787      0.431   -7.55e-07    3.23e-07
    x4             0.0017      0.000      5.092      0.000       0.001       0.002
    x5             0.0040      0.004      1.056      0.291      -0.003       0.011
    ==============================================================================
    Omnibus:                      185.558   Durbin-Watson:                   1.919
    Prob(Omnibus):                  0.000   Jarque-Bera (JB):             1549.867
    Skew:                           0.356   Prob(JB):                         0.00
    Kurtosis:                       8.250   Cond. No.                     1.47e+04
    ==============================================================================

    '''
    # log.info(results.resid) # 每个数据点的残差值
    '''
    [0.0173672163995195 0.02576778174172893 -0.01911921537562762 ...
     0.025745150716659282 -0.022400382502769885 -0.005169696686360914]
    '''
    # 进行SVR回归
    # svr = SVR(kernel='rbf', gamma=0.1) 
    # model = svr.fit(X, Y)
    # 返回多元线性回归的参数值
    return results.params
    # return model.get_params()

# 求dataframe 对于X的中性化后的df, X是df中的一个key
def df_neutralization(df, X):
    for key in df.keys():
        if (key!='code' and key!=X):
            y = df[key]
            x = df[X]
            df[key] = linres(y, x)
    return df
  
     
# 求线性回归残差（中性化用途）
def linres(y,x):
    y = array(y)
    x = sm.add_constant(array(x))
    if len(y)>1:
        model = regression.linear_model.OLS(y,x).fit()
    return model.resid

# 自己加的
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
每天交易时
================================================================================
'''
def handle_data(context, data):

    # 每个调仓日截面上，进行数据提取和计算
    if g.if_trade == True:
        # 从000985中证全指中提取个股，由全部A股股票中剔除ST、*ST股票，不足3个月等股票后的剩余股票构成样本股
        sample = get_index_stocks('000985.XSHG', date = None) 
        # '000985.XSHG'是中证全指，目前处于2019-01-02 09:30:00，date = None 默认值是今天
        # log.info(sample)
        #  ['000001.XSHE', '000002.XSHE', '000004.XSHE',...]
        # log.info(len(sample)) # 3435
        sample = set_feasible_stocks(sample,63,context)
        # 过滤停牌退市ST股票，次新股
        sample = filter_stock_ST(sample)
        sample = remove_new_stocks(sample,context)
        sample = filter_stock_limit(sample)
        # log.info(len(sample)) # 3415
        # 获取基本面数据并作初步计算
        q1 = query(valuation.code, 
                    valuation.market_cap, # 总市值(亿元)
                    balance.total_assets / balance.total_liability, # 杠杆率
                    indicator.inc_net_profit_year_on_year, # 净利润同比增长率（质量成长）
                    indicator.inc_revenue_year_on_year, # 营业收入同比增长率（规模成长）
                    indicator.roe / valuation.pb_ratio, # PB-ROE
                    valuation.pe_ratio / indicator.inc_net_profit_year_on_year, # PEG
                    ).filter(
                       valuation.code.in_(sample))
                    
        # 本期基本面数据df，并清洗
        df1 = get_fundamentals(q1, date = None) # 目前处于2019-01-02 09:30:00，date = None 默认是昨天
        #log.info(df1)
        '''
                 code      market_cap    ...        anon_2     anon_3
        0     000001.XSHE   1610.5846    ...      4.090362   0.894694
        1     000002.XSHE   2629.5259    ...      1.884783   0.115265
        2     000004.XSHE     13.4615    ...     -0.334164  -0.462624
        .....
        3412  603997.XSHG     48.9331    ...      1.853023   1.285784
        3413  603998.XSHG     20.0139    ...      0.733611  -0.959809
        3414  603999.XSHG     27.8784    ...      0.609088  -8.986838
        
        [3415 rows x 7 columns]
        '''
        
        q = query(valuation.code, 
                    valuation.market_cap, # 总市值(亿元)
                    balance.total_assets / balance.total_liability, # 杠杆率
                    indicator.inc_net_profit_year_on_year, # 净利润同比增长率（质量成长）
                    indicator.inc_revenue_year_on_year, # 营业收入同比增长率（规模成长）
                    indicator.roe / valuation.pb_ratio, # PB-ROE
                    valuation.pe_ratio / indicator.inc_net_profit_year_on_year, # PEG
                    ).filter(
                        # 优选基本面质量较好的股票进行回归
                        valuation.pe_ratio / indicator.inc_net_profit_year_on_year>0,
                        valuation.pe_ratio / indicator.inc_net_profit_year_on_year<1,
                        valuation.code.in_(sample))
                    
        # 本期基本面数据df，并清洗
        df = get_fundamentals(q, date = None) # 目前处于2019-01-02 09:30:00， date = None 默认是昨天
        #log.info(df)
        '''
                code       market_cap    ...       anon_2    anon_3
        0     000001.XSHE   1610.5846    ...     4.090362  0.894694
        1     000002.XSHE   2629.5259    ...     1.884783  0.115265
        2     000010.XSHE     26.7273    ...    -3.791897  0.007572
        ......
        1325  603991.XSHG     13.5505    ...     0.713207  0.960245
        1326  603993.XSHG    812.1314    ...     1.275536  0.940128
        1327  603996.XSHG     22.6313    ...     2.866264  0.977009
        
        [1328 rows x 7 columns]
        '''
        df.dropna(axis=0,how='any') # 删除表中含有任何NaN的行 ()的参数inplace默认是false,即不替换
        # 如果是inplace=true,则替换
        #log.info(df.dropna(axis=0,how='any'))
        '''
    
                  code     market_cap    ...       anon_2    anon_3
        0     000001.XSHE   1610.5846    ...     4.090362  0.894694
        1     000002.XSHE   2629.5259    ...     1.884783  0.115265
        2     000010.XSHE     26.7273    ...    -3.791897  0.007572
        3     000016.XSHE     78.0174    ...     1.130176  0.020864
        .....
        1324  603989.XSHG     78.5463    ...     1.122789  0.760972
        1325  603991.XSHG     13.5505    ...     0.713207  0.960245
        1326  603993.XSHG    812.1314    ...     1.275536  0.940128
        1327  603996.XSHG     22.6313    ...     2.866264  0.977009
        
        [1328 rows x 7 columns]
        '''
        #log.info(df.keys())
        '''
        Index(['code', 'market_cap', 'anon_1', 'inc_net_profit_year_on_year',
        'inc_revenue_year_on_year', 'anon_2', 'anon_3'],
        dtype='object')
        '''
        
        
        # 打开后执行3倍MAD数据清洗
        df = fun_normalizeData(df)
        
        # 获得调仓日的日期字符串
        todayStr=str(context.current_dt)[0:10]#去掉时分秒，保留年月日
        # print(context.current_dt) # 2019-01-02 09:30:00
        # print(type(context.current_dt)) # <class 'datetime.datetime'>
        # print(str(context.current_dt)) 2019-01-02 09:30:00  是'str'
        # print(todayStr) # 2019-01-02
        # print(type(todayStr)) # <class 'str'>
        pre_date = getDay(todayStr,g.tc) # 2019-01-02 是周三 ，往前数g.tc(5)个交易日
   
        
       
        # 上一期基本面数据df_p，并清洗
        df_p = get_fundamentals(q, date = pre_date)
        df_p.dropna(axis=0,how='any') # 删除表中含有任何NaN的行
        # 打开后执行3倍MAD数据清洗
        df_p = fun_normalizeData(df_p)
        
        # 求个股本周期回报值（个股名单在df.code列中），作为回归目标Y
        momentum = []
       
        #log.info(df.code)       # series
        #log.info(list(df.code)) # ['000001.XSHE', '000002.XSHE', '000010.XSHE',...]
        #log.info(df.code.values) 
        # 数组 [000001.XSHE 000002.XSHE 000010.XSHE ... 603991.XSHG 603993.XSHG,603996.XSHG]
        #log.info(df['code'].values) 
        # 数组 [000001.XSHE 000002.XSHE 000010.XSHE ... 603991.XSHG 603993.XSHG,603996.XSHG]
        #log.info(list(df['code'].values)) # ['000001.XSHE', '000002.XSHE', '000010.XSHE',...]
        for i in list(df.code):    
            interval,Yesterday = getStockPrice(i, g.tc) 
            stock_momentum = Yesterday / interval - 1
            momentum.append((i, stock_momentum))
        # log.info(momentum)
        '''
        [('000001.XSHE', -0.004246284501061459), ('000002.XSHE', -0.002512562814070307),....]
        '''
        # 转化成np.array结构，方便取出第二列数据（回报值）
        np_momentuma = np.array(momentum)
        # log.info(np_momentuma)
        '''
        [[000001.XSHE -0.004246284501061459]
         [000002.XSHE -0.002512562814070307]
         [000010.XSHE -0.05780346820809257]
         ...
         [603991.XSHG 0.0]
         [603993.XSHG -0.048101265822784955]
         [603996.XSHG -0.028350515463917536]]
        '''
        # log.info(type(np_momentuma[0][0])) # <class 'numpy.str_'>
        # log.info(type(np_momentuma[0][1])) # <class 'numpy.str_'>
        momentum_value = np_momentuma[:,1].astype(float).tolist()
        # log.info(momentum_value)
        # [-0.004246284501061459, -0.002512562814070307,....]
        # log.info(np_momentuma[:,1])
        # [-0.004246284501061459 -0.002512562814070307 -0.05780346820809257 ... 0.0
        #  -0.048101265822784955 -0.028350515463917536]
        # log.info(type(np_momentuma[:,1][0])) <class 'numpy.str_'>
        # log.info(list(np_momentuma[:,1]))
        # ['-0.004246284501061459', '-0.002512562814070307',...]
        # log.info(np_momentuma[:,1].tolist())
        #  ['-0.004246284501061459', '-0.002512562814070307',...]
        # log.info(list(np_momentuma[:,1].astype(float)))
        # 和 momentum_value = np_momentuma[:,1].astype(float).tolist() 一样
        '''[[000001.XSHE -0.004246284501061459]
             [000002.XSHE -0.002512562814070307]
             [000010.XSHE -0.05780346820809257]
             ...
             [603991.XSHG 0.0]
             [603993.XSHG -0.048101265822784955]
             [603996.XSHG -0.028350515463917536]]
        虽然是ndarray,但里面的每个元素其实是str，所以np_momentuma[:,1]是str形成的ndarray,
        必须要要先.astype(float)
         '''
        df['momentum_value'] = momentum_value
        #log.info(df)  # [1328 rows x 8 columns]


        # ====================== 新增因子部分 开始 ========================
        # 此处可新增各类自定义因子
        # ====================== 新增因子部分 结束 ========================
    
        # 本期因子排列命名，并中性化（可选）
        df = df.dropna()
        #log.info(df) # [1328 rows x 8 columns]
        df.columns = ['code','market_cap','LEV','INP_YOY','IR_YOY','ROE_PB', 'PE_G','momentum_value']
        df.index = df.code.values
        # log.info(df)
        '''
                         code     market_cap       ...            PE_G  momentum_value
        000001.XSHE  000001.XSHE   1610.5846       ...        0.894694       -0.004246
        000002.XSHE  000002.XSHE   2629.5259       ...        0.115265       -0.002513
        000010.XSHE  000010.XSHE     26.7273       ...        0.007572       -0.057803
        .......
        [1328 rows x 8 columns]
        '''
        #d f['momentum_value'] = np.log(df['momentum_value']) 
        # 市值中性化过程
        # df = df_neutralization(df,'market_cap')
        del df['code'] # 删除df的'code'列
        # log.info(df)
        '''
                       market_cap   LEV          ...        PE_G         momentum_value
        000001.XSHE   1610.5846   1.075471       ...        0.894694       -0.004246
        000002.XSHE   2629.5259   1.177494       ...        0.115265       -0.002513
        000010.XSHE     26.7273   1.419399       ...        0.007572       -0.057803
        .....
        [1328 rows x 7 columns]
        '''
        
        # 上期因子排列命名，并中性化（可选）
        df_p = df_p.dropna()
        df_p.columns = ['code','market_cap','LEV','INP_YOY','IR_YOY','ROE_PB', 'PE_G']
        df_p.index = df_p.code.values
        # 市值中性化过程
        # df_p = df_neutralization(df_p,'market_cap')
        del df_p['code']
        # log.info(df_p) # 
        '''
                     market_cap      LEV      ...       ROE_PB      PE_G
        000001.XSHE   1593.4142   1.075471    ...     4.134018  0.885156
        000002.XSHE   2587.5771   1.177494    ...     1.915273  0.113426
        000010.XSHE     26.8912   1.419399    ...    -3.768781  0.00761
        ....
        [1331 rows x 6 columns]
        '''
        # X_p是上一期的因子值部分，X是本期因子值部分，Y是回归目标
        X_p = df_p[['LEV','IR_YOY','INP_YOY','ROE_PB','PE_G']]
        # log.info(X_p) # dataframe
        ''' 
                        LEV      IR_YOY     INP_YOY    ROE_PB      PE_G
        000001.XSHE   1.075471   14.21      7.3500  4.134018  0.885156
        000002.XSHE   1.177494   48.12     73.7200  1.915273  0.113426
        000010.XSHE   1.419399  -78.23   -278.8000 -3.768781  0.007618
        .....
        [1331 rows x 5 columns]
        '''
        X = df[['LEV','IR_YOY','INP_YOY','ROE_PB', 'PE_G']]
        # log.info(X) # dataframe
        '''
                         LEV     IR_YOY     INP_YOY  ROE_PB      PE_G
        000001.XSHE   1.075471   14.21      7.3500  4.090362  0.894694
        000002.XSHE   1.177494   48.12     73.7200  1.884783  0.115265
        000010.XSHE   1.419399  -78.23   -278.8000 -3.791897  0.007572
        .....
        [1328 rows x 5 columns]
        '''
        Y = df[['momentum_value']]
        # log.info(Y) # dataframe
        '''
                      momentum_value
        000001.XSHE       -0.004246
        000002.XSHE       -0.002513
        000010.XSHE       -0.057803
        .....
        [1328 rows x 1 columns]
        '''
        # log.info(df['momentum_value']) # series
        '''
        000001.XSHE   -0.004246
        000002.XSHE   -0.002513
        000010.XSHE   -0.057803
        ........
        '''

        
        # 舍弃X_p和Y中不同的index（股票代码），如[u'000975.XSHE']
        # 先去除X_p比Y多的index
        diffIndex = X_p.index.difference(Y.index)   #包含在第一个集合中，但不包含在第二个集合
        # 删除整行
        X_p = X_p.drop(diffIndex,errors='ignore')
        X = X.drop(diffIndex,errors='ignore')
        Y = Y.drop(diffIndex,errors='ignore')  
        
        # 然后去除Y比X_p多的index
        diffIndex = Y.index.difference(X_p.index)
        X_p = X_p.drop(diffIndex,errors='ignore')
        X = X.drop(diffIndex,errors='ignore')
        Y = Y.drop(diffIndex,errors='ignore')
        # log.info(X_p) # [1325 rows x 5 columns]
        # log.info(X)   # [1325 rows x 5 columns]
        # log.info(Y)   # [1325 rows x 1 columns]
        
        # 用上期因子值，和本期回报率，训练得到权重weights
        weights = linreg(X_p,Y)   #一元线性回归
        # print (weights)
        # print(shape(weights))
        # 带入本期因子值X，到股价公式，weights[1:]是从第二行开始所有行
        # print(weights)
        # log.info(type(X)) # dataframe
        # log.info(shape(weights)) # (6,)
        points = X.dot(weights[1:]) + weights[0]
        #log.info(points)
        '''
        000001.XSHE   -0.021649
        000002.XSHE   -0.028325
        000010.XSHE   -0.038724
        000016.XSHE   -0.029843
        ......
        '''
        # log.info(type(points)) # series
       
        # 做降序排序，买入回归股价高的股票
        points.sort_values(ascending = False,inplace=True)
        print (points)        
        # 通过list函数将factor的index列转化成list数据类型，然后买入前g.stocknum个
        order_list = list(points.index[:g.stocknum])
        # 最终名单，分别下单给两个交易函数
        order_stock_sell(context,order_list)
        order_stock_buy(context,order_list)
        
    g.if_trade = False


# 执行卖出        
def order_stock_sell(context,order_list):
    # 对于不需要持仓的股票，全仓卖出
    for stock in context.portfolio.positions:
        # 除去buy_list内的股票，其他都卖出
        if stock not in order_list:
            order_target_value(stock, 0)

            
# 执行买入(自己修改了)           
def order_stock_buy(context,order_list):
    # 对于需要持仓的股票，按分配到的份额买入
    for stock in order_list:
        if stock not in context.portfolio.positions:
                order_target_value(stock, 500000)    
