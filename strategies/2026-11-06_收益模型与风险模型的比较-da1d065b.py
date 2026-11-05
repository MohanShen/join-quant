# Clone from JoinQuant
# postId: da1d065b23cf36e47a4bb2aa35074323
# backtestId: 3b74d4a07797f555ab4c3674ea8c073e
# title: 收益模型与风险模型的比较

# 单因子选股模型
# 先导入所需要的程序包
#单因子转为多因子可以在g.factor处修改，改为list即可

import datetime
import numpy as np
import pandas as pd
import time
from jqdata import *
from pandas import Series, DataFrame
import statsmodels.api as sm
from jqfactor import get_factor_values



'''
================================================================================
总体回测前
================================================================================
'''

#总体回测前要做的事情（永远不变的）
def initialize(context):
    set_params()    #1 设置策参数
    set_variables() #2 设置中间变量
    set_backtest()  #3 设置回测条件

#1 设置策略参数
def set_params():
    # 单因子测试时g.factor不应为空
    #'BP','inc_net_profit_year_on_year','operating_profit','inc_revenue_year_on_year','roe','ps_ratio','pe_ratio','mom_month','mom_quarter','VOL60'
    g.factor = ['BP','inc_net_profit_year_on_year','operating_profit','inc_revenue_year_on_year','roe','ps_ratio','pe_ratio','mom_month','mom_quarter','VOL60']        # 当前回测的单因子
    g.shift = 21           # 设置一个观测天数（天数）
    g.precent = 0.05       # 持仓占可选股票池比例
    g.index='000906.XSHG'  # 定义股票池，中证800
    # 定义因子以及排序方式，默认False方式为降序排列，原值越大sort_rank排序越小
    #通俗讲，False为越小越赚钱，True为越大越赚钱
    #事实证明pe_ratio不管是选大的还是小的都跑不赢大盘，但大的还是比小的好
    g.factors = {'BP': False,'inc_net_profit_year_on_year':False,'operating_profit':False,
    'inc_revenue_year_on_year':False,'roe':False,'pe_ratio':True,'ps_ratio':True,'mom_month':True,
    'mom_quarter':True,'VOL60':True
    }
    # 设定选取sort_rank： True 为最大，False 为最小
    g.sort_rank = True
    g.quantile = (0, 5)
'''
000906.XSHG
中证800
'''

#2 设置中间变量
def set_variables():
    g.feasible_stocks = []  # 当前可交易股票池
    g.if_trade = False      # 当天是否交易
    g.num_stocks = 0        # 设置持仓股票数目

    
#3 设置回测条件
def set_backtest():
    set_benchmark('000906.XSHG')       # 设置为基准
    set_option('use_real_price', True) # 用真实价格交易
    log.set_level('order', 'error')    # 设置报错等级

'''
================================================================================
每天开盘前
================================================================================
'''
#每天开盘前要做的事情
def before_trading_start(context):
    # 获得当前日期
    day = context.current_dt.day
    yesterday = context.previous_date
    rebalance_day = shift_trading_day(yesterday, 1)
    if yesterday.month != rebalance_day.month:
        if yesterday.day > rebalance_day.day:
            g.if_trade = True 
            #5 设置可行股票池：获得当前开盘的股票池并剔除当前或者计算样本期间停牌的股票
            g.feasible_stocks = set_feasible_stocks(get_index_stocks(g.index),g.shift,context)
    		#6 设置滑点与手续费
            set_slip_fee(context)
            # 购买股票为可行股票池对应比例股票
            g.num_stocks = int(len(g.feasible_stocks)*g.precent)

#4
# 某一日的前shift个交易日日期 
# 输入：date为datetime.date对象(是一个date，而不是datetime)；shift为int类型
# 输出：datetime.date对象(是一个date，而不是datetime)
def shift_trading_day(date,shift):
    # 获取所有的交易日，返回一个包含所有交易日的 list,元素值为 datetime.date 类型.
    tradingday = get_all_trade_days()
    # 得到date之后shift天那一天在列表中的行标号 返回一个数
    shiftday_index = list(tradingday).index(date)+shift
    # 根据行号返回该日日期 为datetime.date类型
    return tradingday[shiftday_index]

#5    
# 设置可行股票池
# 过滤掉当日停牌的股票,且筛选出前days天未停牌股票
# 输入：stock_list为list类型,样本天数days为int类型，context（见API）
# 输出：list=g.feasible_stocks
def set_feasible_stocks(stock_list,days,context):
    # 得到是否停牌信息的dataframe，停牌的1，未停牌得0
    suspened_info_df = get_price(list(stock_list), 
                       start_date=context.current_dt, 
                       end_date=context.current_dt, 
                       frequency='daily', 
                       fields='paused'
    )['paused'].T
    # 过滤停牌股票 返回dataframe
    unsuspened_index = suspened_info_df.iloc[:,0]<1
    # 得到当日未停牌股票的代码list:
    unsuspened_stocks = suspened_info_df[unsuspened_index].index
    # 进一步，筛选出前days天未曾停牌的股票list:
    feasible_stocks = []
    current_data = get_current_data()
    for stock in unsuspened_stocks:
        if sum(attribute_history(stock, 
                                 days, 
                                 unit = '1d',
                                 fields = ('paused'), 
                                 skip_paused = False
                                )
            )[0] == 0:
            feasible_stocks.append(stock)
    #剔除ST股
    st_data = get_extras('is_st', feasible_stocks, end_date = context.previous_date, count = 1)
    stockList = [stock for stock in feasible_stocks if not st_data[stock][0]]
    return stockList
    
#6 根据不同的时间段设置滑点与手续费(永远不变的函数)
def set_slip_fee(context):
    # 将滑点设置为0
    set_slippage(PriceRelatedSlippage(0.002)) 
    # 根据不同的时间段设置手续费
    dt=context.current_dt
    
    if dt>datetime.datetime(2013,1, 1):
        set_commission(PerTrade(buy_cost=0.0003, 
                                sell_cost=0.0013, 
                                min_cost=5)) 
        
    elif dt>datetime.datetime(2011,1, 1):
        set_commission(PerTrade(buy_cost=0.001, 
                                sell_cost=0.002, 
                                min_cost=5))
            
    elif dt>datetime.datetime(2009,1, 1):
        set_commission(PerTrade(buy_cost=0.002, 
                                sell_cost=0.003, 
                                min_cost=5))
                
    else:
        set_commission(PerTrade(buy_cost=0.003, 
                                sell_cost=0.004, 
                                min_cost=5))
'''
================================================================================
每天交易时
================================================================================
'''
def handle_data(context,data):
	# 如果为交易日
    if g.if_trade == True: 
	    #7 获得买入卖出信号，输入context，输出股票列表list
	    # 字典中对应默认值为false holding_list筛选为true，则选出因子得分最大的
        holding_list = get_stocks(g.feasible_stocks, 
                                context,
                                asc = g.sort_rank)
        # 新加入的部分，计算holding_list长度
        total_number = len(holding_list)
        # print 'feasible_stocks is %d, holding is %d' %(len(g.feasible_stocks), total_number)
        # 提取需要的分位信息
        (start_q, end_q) =  g.quantile
        #8 重新调整仓位，输入context,使用信号结果holding_list
        rebalance(context, holding_list, start_q, end_q, total_number)
	g.if_trade = False

#7 原始数据重提取因子打分排名（核心逻辑）
def get_stocks(stocks_list, context, asc):
    result = pd.DataFrame()
    for i in g.factor:
        # 构建一个新的字符串，名字叫做 'get_df_'+ 'key'
        tmp = 'get_df'+'_'+i
        # 声明字符串是个方程
        aa = globals()[tmp](stocks_list,context,g.factors[i])
        #合并所有因子分数数据
        result = pd.concat([result,aa],axis = 1)
    score = 'factor_sorted_rank'
    #result['BP_sorted_rank']+result['inc_net_profit_year_on_year_sorted_rank']+result['operating_profit_sorted_rank']+result['inc_revenue_year_on_year_sorted_rank']+result['roe_sorted_rank']+result['ps_ratio_sorted_rank']+result['pe_ratio_sorted_rank']+result['mom_month_sorted_rank']+result['mom_quarter_sorted_rank']+result['VOL60_sorted_rank']
    result[score] = result['BP_sorted_rank']+result['inc_net_profit_year_on_year_sorted_rank']+result['operating_profit_sorted_rank']+result['inc_revenue_year_on_year_sorted_rank']+result['roe_sorted_rank']+result['ps_ratio_sorted_rank']+result['pe_ratio_sorted_rank']+result['mom_month_sorted_rank']+result['mom_quarter_sorted_rank']+result['VOL60_sorted_rank']
    result = result.dropna()
    # 生成排名序数
    stocks = list(result.sort(score,ascending = asc).index)
    
    return stocks
    

#8
# 依本策略的买入信号，得到应该买的股票列表
# 借用买入信号结果，不需额外输入
# 输入：context（见API）
def rebalance(context, holding_list, start_q, end_q, total_number):
    if end_q == 100:
        end_q = 100
    # 每只股票购买金额
    every_stock = context.portfolio.portfolio_value/g.num_stocks
    # 空仓只有买入操作
    if len(list(context.portfolio.positions.keys()))==0:
        # 原设定重scort始于回报率相关打分计算，回报率是升序排列
        for stock_to_buy in holding_list[start_q * total_number / 100 : end_q * total_number / 100]: 
            order_target_value(stock_to_buy, every_stock)
    else :
        # 不是空仓先卖出持有但是不在购买名单中的股票
        for stock_to_sell in list(context.portfolio.positions.keys()):
            if stock_to_sell not in holding_list[start_q * total_number / 100 : end_q * total_number / 100]:
                order_target_value(stock_to_sell, 0)
        # 因order函数调整为顺序调整，为防止先行调仓股票由于后行调仓股票占金额过大不能一次调整到位，这里运行两次以解决这个问题
        for stock_to_buy in holding_list[start_q * total_number / 100 : end_q * total_number / 100]: 
            order_target_value(stock_to_buy, every_stock)
        for stock_to_buy in holding_list[start_q * total_number / 100 : end_q * total_number / 100]: 
            order_target_value(stock_to_buy, every_stock)



#获取11个因子值
#1、月度动量
def get_df_mom_month(stock_list,context,asc):
    #取当天的收盘价数据
    df_mom_month = get_price(stock_list,start_date = context.current_dt - datetime.timedelta(days = 31),end_date = context.current_dt - datetime.timedelta(days = 1),fields = ['close'])['close']
    #将数据转置，让index列为股票代码
    df_mom_month = df_mom_month.T
    #计算月度动量
    df_mom_month['mom_month'] = df_mom_month.iloc[:,-1]/df_mom_month.iloc[:,0] - 1
    #删除nan
    df_mom_month = df_mom_month[pd.notnull(df_mom_month['mom_month'])]
    #复制一个df，放置排序结果
    df_mom_month['mom_month_sorted_rank'] = df_mom_month['mom_month'].rank(ascending = asc,method = 'dense')
    #给权重
    df_mom_month['mom_month_sorted_rank'] = 0 * df_mom_month['mom_month_sorted_rank']
    
    return df_mom_month
    

#2、获取净利润增长率inc_net_profit_year_on_year
def get_df_inc_net_profit_year_on_year(stock_list,context,asc):
    q = query(valuation.code,indicator.inc_net_profit_year_on_year).filter(valuation.code.in_(stock_list))
    #获取inc_net_profit_year_on_year数据
    df_inc_net_profit_year_on_year = get_fundamentals(q,date = context.current_dt-datetime.timedelta(days = 1))
    # 删除nan，以备数据中某项没有产生nan
    df_inc_net_profit_year_on_year = df_inc_net_profit_year_on_year[pd.notnull(df_inc_net_profit_year_on_year['inc_net_profit_year_on_year'])]
    # 复制一个dataframe，按对应项目排序
    df_inc_net_profit_year_on_year['inc_net_profit_year_on_year_sorted_rank'] = df_inc_net_profit_year_on_year['inc_net_profit_year_on_year'].rank(ascending = asc, method = 'dense')
    #给权重
    #df_inc_net_profit_year_on_year['inc_net_profit_year_on_year_sorted_rank'] = 1 * df_inc_net_profit_year_on_year['inc_net_profit_year_on_year_sorted_rank']
    # 使用股票代码作为index
    df_inc_net_profit_year_on_year.index = df_inc_net_profit_year_on_year.code
    # 删除无用数据
    del df_inc_net_profit_year_on_year['code']
    
    return df_inc_net_profit_year_on_year


#3、获取营业利润数据operating_profit
def get_df_operating_profit(stock_list,context,asc):
    q = query(valuation.code,income.operating_profit).filter(valuation.code.in_(stock_list))
    #获取营业利润operating_profit数据
    df_operating_profit = get_fundamentals(q,date = context.current_dt - datetime.timedelta(days = 1))
    ##删除nan
    df_operating_profit = df_operating_profit[pd.notnull(df_operating_profit['operating_profit'])]
    #复制一个df，放入排序结果
    df_operating_profit['operating_profit_sorted_rank'] = df_operating_profit['operating_profit'].rank(ascending = asc,method = 'dense')
    #给权重
    df_operating_profit['operating_profit_sorted_rank'] = 0.8 * df_operating_profit['operating_profit_sorted_rank']
    #使用股票代码作为index
    df_operating_profit.index = df_operating_profit['code']
    #删除无用数据
    del df_operating_profit['code']
    
    return df_operating_profit
    
    
#4、获取营业收入增长率inc_revenue_year_on_year
def get_df_inc_revenue_year_on_year(stock_list,context,asc):
    q = query(valuation.code,indicator.inc_revenue_year_on_year).filter(valuation.code.in_(stock_list))
    #获取营业收入增长率inc_revenue_year_on_year数据
    df_inc_revenue_year_on_year = get_fundamentals(q,date = context.current_dt - datetime.timedelta(days = 1))
    #删除nan
    df_inc_revenue_year_on_year = df_inc_revenue_year_on_year[pd.notnull(df_inc_revenue_year_on_year['inc_revenue_year_on_year'])]
    #复制一个df，放入排序结果
    df_inc_revenue_year_on_year['inc_revenue_year_on_year_sorted_rank'] = df_inc_revenue_year_on_year['inc_revenue_year_on_year'].rank(ascending = asc,method = 'dense')
    #给权重
    #df_inc_revenue_year_on_year['inc_revenue_year_on_year_sorted_rank'] = 1 * df_inc_revenue_year_on_year['inc_revenue_year_on_year_sorted_rank']
    #使用股票代码作为index
    df_inc_revenue_year_on_year.index = df_inc_revenue_year_on_year['code']
    #删除无用数据
    del df_inc_revenue_year_on_year['code']
    
    return df_inc_revenue_year_on_year
        

#5、roe涨跌幅


#6、 BP
# 得到一个dataframe：包含股票代码、账面市值比BP和对应排名BP_sorted_rank
# 默认date = context.current_dt的前一天,使用默认值，避免未来函数，不建议修改
# 获得市净率pb_ratio
def get_df_BP(stock_list, context, asc):
    df_BP = get_fundamentals(query(valuation.code, valuation.pb_ratio
                     ).filter(valuation.code.in_(stock_list)))
    # 获得pb倒数
    df_BP['BP'] = df_BP['pb_ratio'].apply(lambda x: 1/x)
    # 删除nan，以备数据中某项没有产生nan
    df_BP = df_BP[pd.notnull(df_BP['BP'])]
    # 生成排名序数
    df_BP['BP_sorted_rank'] = df_BP['BP'].rank(ascending = asc, method = 'dense')
    #给权重
    #df_BP['BP_sorted_rank'] = 0.9 * df_BP['BP_sorted_rank']
    # 使用股票代码作为index
    df_BP.index = df_BP.code
    # 删除无用数据
    del df_BP['code']
    
    return df_BP
    

#7、季度动量
def get_df_mom_quarter(stock_list,context,asc):
    #取当天和一个季度前的收盘价数据
    df_mom_quarter = get_price(stock_list,start_date = context.current_dt - datetime.timedelta(days = 91),end_date = context.current_dt - datetime.timedelta(days = 1),fields = ['close'])['close']
    #将数据转置，让index列为股票代码
    df_mom_quarter = df_mom_quarter.T
    #计算季度动量
    df_mom_quarter['mom_quarter'] = df_mom_quarter.iloc[:,-1]/df_mom_quarter.iloc[:,0] - 1
    #删除nan
    df_mom_quarter = df_mom_quarter[pd.notnull(df_mom_quarter['mom_quarter'])]
    #复制一个df，放置排序结果
    df_mom_quarter['mom_quarter_sorted_rank'] = df_mom_quarter['mom_quarter'].rank(ascending = asc,method = 'dense')
    #给权重
    #df_mom_quarter['mom_quarter_sorted_rank'] = 0.5 * df_mom_quarter['mom_quarter_sorted_rank']
    
    return df_mom_quarter


#8、市盈率pe_ratio
def get_df_pe_ratio(stock_list,context,asc):
    q = query(valuation.code,valuation.pe_ratio).filter(valuation.code.in_(stock_list))
    #获取pe_ratio数据
    df_pe_ratio = get_fundamentals(q,context.current_dt - datetime.timedelta(days = 1))
    #删除nan
    df_pe_ratio = df_pe_ratio[pd.notnull(df_pe_ratio['pe_ratio'])]
    #生成排名序数
    df_pe_ratio['pe_ratio_sorted_rank'] = df_pe_ratio['pe_ratio'].rank(ascending = asc,method = 'dense')
    #市盈率给的权重为0.5
    df_pe_ratio['pe_ratio_sorted_rank'] = 0.5 * df_pe_ratio['pe_ratio_sorted_rank']
    #使用股票代码作为index
    df_pe_ratio.index = df_pe_ratio['code']
    #删除无用数据
    del df_pe_ratio['code']
    
    return df_pe_ratio
    
        
#9、市销率ps_ratio
def get_df_ps_ratio(stock_list,context,asc):
    q = query(valuation.code,valuation.ps_ratio).filter(valuation.code.in_(stock_list))
    #获取ps_ratio数据
    df_ps_ratio = get_fundamentals(q,date = context.current_dt - datetime.timedelta(days = 1))
    #删除nan    
    df_ps_ratio = df_ps_ratio[pd.notnull(df_ps_ratio['ps_ratio'])]
    #生成排名序数
    df_ps_ratio['ps_ratio_sorted_rank'] = df_ps_ratio['ps_ratio'].rank(ascending = asc,method = 'dense')
    #市销率给的权重为0.5
    df_ps_ratio['ps_ratio_sorted_rank'] = 0.5 * df_ps_ratio['ps_ratio_sorted_rank']
    #使用股票代码作为index
    df_ps_ratio.index = df_ps_ratio['code']
    #删除无用数据
    del df_ps_ratio['code']
    
    return df_ps_ratio
    
        
#10、roe
def get_df_roe(stock_list,context,asc):
    q = query(valuation.code,indicator.roe).filter(valuation.code.in_(stock_list))
    #获取roe数据
    df_roe = get_fundamentals(q,date = context.current_dt - datetime.timedelta(days = 1))
    #删除nan
    df_roe = df_roe[pd.notnull(df_roe['roe'])]
    #生成排名序数
    df_roe['roe_sorted_rank'] = df_roe['roe'].rank(ascending = asc,method = 'dense')
    #给权重
    #df_roe['roe_sorted_rank'] = 1 * df_roe['roe_sorted_rank']
    #使用股票代码作为index
    df_roe.index = df_roe['code']
    #删除无用数据
    del df_roe['code']
    
    return df_roe
    
    
#11、60日平均换手率
def get_df_VOL60(stock_list,context,asc):
    #获取因子数据
    df_VOL60 = get_factor_values(securities = stock_list, factors='VOL60', end_date = context.previous_date,count = 1)
    df_VOL60 = df_VOL60['VOL60'].T
    df_VOL60.columns = ['VOL60']
    #删除nan
    df_VOL60 = df_VOL60[pd.notnull(df_VOL60['VOL60'])]
    #生成排名序数
    df_VOL60['VOL60_sorted_rank'] = df_VOL60['VOL60'].rank(ascending = asc,method = 'dense')
    #给权重
    #df_VOL60['VOL60_sorted_rank'] = 1.5 * df_VOL60['VOL60_sorted_rank']
    
    return df_VOL60
    
    
'''
================================================================================
每天收盘后
================================================================================
'''
# 每日收盘后要做的事情（本策略中不需要）
def after_trading_end(context):
    return