# Clone from JoinQuant
# postId: 61f513b7d7ab28ac1e17022e92f36fab
# backtestId: 2ec2c79d1039865e0c85fcec8bb3b4ce
# title: 获取数据缺失

enable_profile()
# 导入函数库
from jqdata import *
import pandas as pd
import numpy as np
import datetime as dt
import talib as ta
from datetime import date,timedelta 
import statsmodels.api as sm

# 初始化函数，设定基准等等
def initialize(context):
    set_params(context)
    set_variables(context)
    set_backtest()

    run_daily(stop_loss)
    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
    # 开盘前运行
    run_daily(before_market_open, time='before_open', reference_security='000300.XSHG')
    # 每天9:31运行
    run_daily(stop_loss, time='9:31', reference_security='000300.XSHG')
    # 每天9:31运行
    run_daily(handle_bar, time='9:31', reference_security='000300.XSHG')

#设置策参数
def set_params(context):
    g.tc = 20                               #调仓频率      
    g.t=0
    g.big_small = 'big'                     #big是降序，small为升序
    context.stock = '000300.XSHG'
    g.long_pct = 0.05
    g.stock='000300.XSHG'                     #择时选取的指数
    
    g.total_positionprevious=0              #仓位
    g.N = 18                                #RSRS选取的回归长度 
    g.M = 1100                              #RSRS均值窗口 
        
def set_variables(context): 
    context.X_length=11 
    context.flag=True
    g.buy = 0.7                              #买入阀门
    g.sell = -0.7                            #卖出阀门
    g.ans = []
    g.ans_rightdev= []
 
def set_backtest():
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    set_option("avoid_future_data", True)
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0002, close_commission=0.0002, min_commission=5), type='stock')
    
## 开盘前运行函数
def before_market_open(context):
    #需要先建立过去的数据集合，否则后面新数据没有历史数据作为窗口
    if context.flag:
        initlast_date=context.current_dt.date()-timedelta(days=1)
        prices = get_price(g.stock, start_date='2006-06-05', end_date=initlast_date, frequency='daily', fields=['high', 'low'])
        #获取最高价和最低价
        highs = prices.high
        lows = prices.low
        #建立一个初始的装有beta从过去到初始阶段的历史数据的列表g.ans
        g.ans = []
        for i in range(len(highs))[g.N:]:
            data_high = highs.iloc[i-g.N+1:i+1]
            data_low = lows.iloc[i-g.N+1:i+1]
            X = sm.add_constant(data_low)
            model = sm.OLS(data_high,X)
            results = model.fit()
            g.ans.append(results.params[1])
        
            # 装有rsquare从过去到初始阶段历史数据的列表    
            g.ans_rightdev.append(results.rsquared)
        context.flag=False

#个股止损
def stop_loss(context):
    data = get_current_data()
    for stock in context.portfolio.positions.keys():
        cumulative_return=data[stock].last_price/context.portfolio.positions[stock].acc_avg_cost
        if cumulative_return<0.9:
            order_target_value(stock,0)
            
def handle_bar(context):
    stock = g.stock
    beta=0
    r2=0
    
    prices = attribute_history(stock, g.N, unit='1d', fields=['high', 'low'], skip_paused=False, df=True, fq='pre')
    highs = prices.high
    lows = prices.low
    X = sm.add_constant(lows)
    model = sm.OLS(highs, X)
    #得到beta
    beta = model.fit().params[1]
    #将新的beta添加到装有历史数据列表
    g.ans.append(beta)
    #得到rsquare数据
    r2=model.fit().rsquared
    #将新的rsquare添加到装有历史数据列表
    g.ans_rightdev.append(r2)
    
    #为了标准化当下的beta数值，拿过去1100天的数据作为均值的窗口
    section = g.ans[-g.M:]
    # 计算均值序列
    mu = np.mean(section)
    # 计算标准化RSRS指标序列
    sigma = np.std(section)
    zscore = (section[-1]-mu)/sigma  
    #计算右偏RSRS标准分，就是将标准化后的beta数据乘以原始beta再乘以拟合度
    zscore_rightdev= zscore*beta*r2
    
    #根据交易信号买入卖出
    if zscore_rightdev > g.buy:
        total_position=1
    elif zscore_rightdev < g.sell:
        total_position=0     
    else:
        total_position=g.total_positionprevious
    
    data = get_current_data()
    if (g.total_positionprevious != total_position) or (g.t%g.tc==0):
        g.total_positionprevious=total_position
        
        last_date = get_trade_days(None, context.current_dt, 2)[0]
        securities=get_all_securities(['stock'],date=last_date)
        log.info(securities.index)
        #对stock_list进行去除st，停牌等处理
        stock_list=fun_remove_new(context, securities, 60)
        stock_list=fun_unpaused(data, stock_list)
        stock_list=fun_st(data,stock_list)
        stock_list=fun_highlimit(data,stock_list)
        
        #以下是各单因子
        #规模因子
        cap_df = market_cap(stock_list, 'market_cap',last_date)
        cap_df = cap_df * -1
        log.info(cap_df)
        #估值因子
        PB_df = PB(stock_list, 'pb_ratio',last_date)
        PB_df = PB_df * -1
        log.info(PB_df)
        #动量因子
        MTM20_df = MTM20(stock_list, 'MTM20')
        MTM20_df=MTM20_df* -1
        log.info(MTM20_df)
        #质量因子
        #1.ROE（高利润）
        roe_df = roe(stock_list, 'roe',last_date)
        log.info(roe_df)
        #2.净利润同比增长率（高成长）
        net_profit_growth_ratio_df=net_profit_growth_ratio(stock_list,'inc_net_profit_to_shareholders_year_on_year',last_date)
        log.info(net_profit_growth_ratio_df)
        #波动率因子
        ATR20_df = ATR20(stock_list, 'ATR20')
        ATR20_df = ATR20_df * -1
        log.info(ATR20_df)
        #合并多因子
        concat_obj = [cap_df, PB_df,MTM20_df,roe_df,net_profit_growth_ratio_df,ATR20_df]
        df = pd.concat(concat_obj, axis=1)
        df = df.dropna()
#       log.info(type(df))
        sum = df.sum(axis=1)
        #log.info(sum)

        #进行排序
        if g.big_small == 'big':
            # 按照大排序
            sum.sort_values(ascending = False,inplace=True)
        if g.big_small == 'small':
            # 按照小排序
            sum.sort_values(ascending = True,inplace=True)
        # 根据比例取出排序后靠前部分
        
        stock_list1 = sum[0:int(len(stock_list)*g.long_pct)].index
        #log.info(stock_list1)
        buy_list = []
        for stock in stock_list1:
            buy_list.append(stock)
        #买卖操作
        for stock in list(context.portfolio.positions):
            if stock not in buy_list:
                order_target(stock, 0)
                
        cash = context.portfolio.portfolio_value
        position=cash*g.total_positionprevious
 #       position=cash*g.SAR_signal
        num=int(len(stock_list)*g.long_pct)
        ## 买入
        for stock in buy_list:
            order_target_value(stock,position/num)
            
    g.t=g.t+1

"""
以下对股票列表进行去除ST，停牌，去新股，以及去除开盘涨停股
"""   
#去除开盘涨停股票
def fun_highlimit(data,stock_list):
    return [stock for stock in stock_list if data[stock].day_open!=data[stock].high_limit]

#去除st股票
def fun_st(data,stock_list): 
    return [stock for stock in stock_list if not data[stock].is_st]

#去除停牌股票 
def fun_unpaused(data, stock_list):
    return [s for s in stock_list if not data[s].paused]     

#去除新上市股票 
def fun_remove_new(context, securities, days):
    deltaDate = context.current_dt.date() - dt.timedelta(days)
    stock_list = []
    for row in securities.itertuples():
        if row.start_date < deltaDate:
            stock_list.append(row.Index)
    return stock_list
  
"""
以下是单因子
"""    
def market_cap(stocklist, factor,last_date):
    # 取数据
    df = get_fundamentals(query(valuation.code, valuation.market_cap).filter(valuation.code.in_(stocklist)),date=last_date)
    # log.info(df)
    df = df.set_index('code')
    # 绝对中位数法取极值
    after_MAD = MAD(factor, df)
    # z-score法标准化
    after_zscore = zscore(factor, after_MAD)
    return after_zscore    
    
def PB(stocklist, factor,last_date):
    # 取数据
    df = get_fundamentals(query(valuation.code, valuation.pb_ratio).filter(valuation.code.in_(stocklist)),date=last_date)
    df = df.set_index('code')
    # 绝对中位数法取极值
    after_MAD = MAD(factor, df)
    # z-score法标准化
    after_zscore = zscore(factor, after_MAD)
    return after_zscore

def MTM20(stocklist, factor):
    # 取数据
    for stock in stocklist:
        df1=history(20, unit='1d', field='close', security_list=stock, df=True, fq='none')
        #log.info(df1)
        s = pd.DataFrame([(df1[stock][-1]-df1[stock][0])/df1[stock][0]], index=[stock])
    #    log.info(s)
        if 'df' in locals():
            df = df.append(s)
        else:
            df = s
    #log.info(df)
    df.columns = ['MTM20']
    df.index.name = 'code'
    # 绝对中位数法取极值
    after_MAD = MAD(factor, df)
    # z-score法标准化
    after_zscore = zscore(factor, after_MAD)
    return after_zscore

def roe(stocklist, factor,last_date):
    # 取数据
    df = get_fundamentals(query(valuation.code, indicator.roe).filter(valuation.code.in_(stocklist)),date=last_date)
#    log.info(df)
    df = df.set_index('code')
    # 绝对中位数法取极值
    after_MAD = MAD(factor, df)
    # z-score法标准化
    after_zscore = zscore(factor, after_MAD)
    return after_zscore

def net_profit_growth_ratio(stocklist, factor,last_date):
    # 取数据
    df = get_fundamentals(query(valuation.code, indicator.inc_net_profit_to_shareholders_year_on_year).filter(valuation.code.in_(stocklist)),date=last_date)
#    log.info(df)
    df = df.set_index('code')
    # 绝对中位数法取极值
    after_MAD = MAD(factor, df)
    # z-score法标准化
    after_zscore = zscore(factor, after_MAD)
    return after_zscore   

def ATR20(stocklist, new_factor):
    # 取数据
    for stock in stocklist:
        Data_ATR = attribute_history(stock, 20, unit='1d', fields=['close','high','low'], skip_paused=False, df=True, fq='none')
        close_ATR = np.array(Data_ATR['close'])
        high_ATR = np.array(Data_ATR['high'])
        low_ATR = np.array(Data_ATR['low'])
        '''
        if np.isnan(close_ATR).any():
            continue
        '''    
        ATR = ta.ATR(high_ATR, low_ATR, close_ATR, timeperiod=1)
        indices = ~np.isnan(ATR)
        result = np.average(ATR[indices])
        s = pd.Series(result.astype(float), index=[stock])
        if 'ATR_df' in locals():
            ATR_df = ATR_df.append(s)
        else:
            ATR_df = s
    df = ATR_df.to_frame()
    df.index.name = 'code'
    df.columns = [new_factor]
    # 绝对中位数法取极值
    after_MAD = MAD(new_factor, df)
    # z-score法标准化
    after_zscore = zscore(new_factor, after_MAD)
    return after_zscore

"""
以下是进行因子数据处理，对因子进行MAD去极值，以及标准化处理
"""    
def MAD(factor, df):
    # 取得中位数
    median = df[factor].median()
    # 取得数据与中位数差值
    df1 = df-median
    # 取得差值绝对值
    df1 = df1.abs()
    # 取得绝对中位数
    MAD = df1[factor].median()
    # 得到数据上下边界
    extreme_upper = median + 3 * 1.483 * MAD
    extreme_lower = median - 3 * 1.483 * MAD
    # 将数据上下边界外的数值归到边界上
    df.ix[(df[factor]<extreme_lower), factor] = extreme_lower
    df.ix[(df[factor]>extreme_upper), factor] = extreme_upper
    return df

# z-score标准化
def zscore(factor, df):
    # 取得均值
    mean = df[factor].mean()
    # 取得标准差
    std = df[factor].std()
    # 取得标准化后数据
    df = (df - mean) / std
    return df  