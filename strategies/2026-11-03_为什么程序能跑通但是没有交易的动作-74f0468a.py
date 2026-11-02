# Clone from JoinQuant
# postId: 74f0468a5a71ecf57d664c97c72c7385
# backtestId: c9af3db6c778526437e236b82f293d93
# title: 为什么程序能跑通但是没有交易的动作

# 克隆自聚宽文章：https://www.joinquant.com/post/3709
# 标题：【量化课堂】因子研究系列之一 -- 估值和资本结构因子
# 作者：JoinQuant量化课堂

# 多因子选股模型
# 先导入所需要的程序包

import datetime
import numpy as np
import pandas as pd
import time
from jqdata import *
from pandas import Series, DataFrame


'''
================================================================================
总体回测前
================================================================================
'''

#总体回测前要做的事情
def initialize(context):
    set_params()    #1 设置策参数
    set_variables() #2 设置中间变量
    set_backtest()  #3 设置回测条件

#1 设置策略参数
def set_params():
    g.factor = 'ALR'          # 当前回测的单因子
    g.shift = 21           # 设置一个观测天数（天数）
    g.precent = 0.01       # 持仓占可选股票池比例
    g.index='000001.XSHG'  # 定义股票池，上交所股票
    # 定义因子以及排序方式，默认False方式为降序排列，原值越大sort_rank排序越小
    g.factors = { 'ALR': False}
    # 设定选取sort_rank： True 为最大，False 为最小
    g.sort_rank = True
    
# 'BP': False, 'EP': False, 'PEG': False, 'DP': False,
# 'CFP': False, 'PS': False, 'ALR': False, 
# 'FACR': False, 'CMC': False
            
    
#2 设置中间变量
def set_variables():
    g.feasible_stocks = []  # 当前可交易股票池
    g.if_trade = False      # 当天是否交易
    g.num_stocks = 0        # 设置持仓股票数目

    
#3 设置回测条件
def set_backtest():
    set_benchmark('000001.XSHG')       # 设置为基准
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
            g.feasible_stocks = set_feasible_stocks(get_index_stocks(g.index), g.shift,context)
    		#6 设置手续费与手续费
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
    return feasible_stocks
    
#6 根据不同的时间段设置滑点与手续费
def set_slip_fee(context):
    # 将滑点设置为0
    set_slippage(FixedSlippage(0)) 
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
	    #8 获得买入卖出信号，输入context，输出股票列表list
	    # 字典中对应默认值为false holding_list筛选为true，则选出因子得分最大的
        holding_list = get_stocks(g.feasible_stocks, 
                                context, 
                                g.factors, 
                                asc = g.sort_rank, 
                                factor_name = g.factor)
        #9 重新调整仓位，输入context,使用信号结果holding_list
        rebalance(context, holding_list)
	g.if_trade = False

#7 获得因子信息
# stocks_list调用g.feasible_stocks factors调用字典g.factors
# 输出所有对应数据和对应排名，DataFrame
def get_factors(stocks_list, context, factors):
    # 从可行股票池中生成股票代码列表
    df_all_raw = pd.DataFrame(stocks_list)
    # 修改index为股票代码
    df_all_raw['code'] = df_all_raw[0]
    df_all_raw.index = df_all_raw['code']
    # 格式调整，没有一步到位中间有些东西还在摸索，简洁和效率的一个权衡
    del df_all_raw[0]
    stocks_list300 = list(df_all_raw.index)
    # 每一个指标量都合并到一个dataframe里
    for key,value in g.factors.items():
        # 构建一个新的字符串，名字叫做 'get_df_'+ 'key'
        tmp='get_df' + '_' + key
        # 声明字符串是个方程
        aa = globals()[tmp](stocks_list, context, value)
        # 合并处理
        df_all_raw = pd.concat([df_all_raw,aa], axis=1)
    # 删除code列
    del df_all_raw['code']
    # 对于新生成的股票代码取list
    stocks_list_more = list(df_all_raw.index)
    # 可能在计算过程中并如的股票剔除
    for stock in stocks_list_more[:]:
        if stock not in stocks_list300:
            df_all_raw.drop(stock)
    return df_all_raw

# 8获得调仓信号
# 原始数据重提取因子打分排名
def get_stocks(stocks_list, context, factors, asc, factor_name):
    # 7获取原始数据
    df_all_raw1 = get_factors(stocks_list, context, factors)
    # 根据factor生成列名
    score = factor_name + '_' + 'sorted_rank'
    stocks = list(df_all_raw1.sort(score, ascending = asc).index)
    return stocks

# 9交易调仓
# 依本策略的买入信号，得到应该买的股票列表
# 借用买入信号结果，不需额外输入
# 输入：context（见API）
def rebalance(context, holding_list):
    # 每只股票购买金额
    every_stock = context.portfolio.portfolio_value/g.num_stocks
    # 空仓只有买入操作
    if len(list(context.portfolio.positions.keys()))==0:
        # 原设定重scort始于回报率相关打分计算，回报率是升序排列
        for stock_to_buy in list(holding_list)[0:g.num_stocks]: 
            order_target_value(stock_to_buy, every_stock)
    else :
        # 不是空仓先卖出持有但是不在购买名单中的股票
        for stock_to_sell in list(context.portfolio.positions.keys()):
            if stock_to_sell not in list(holding_list)[0:g.num_stocks]:
                order_target_value(stock_to_sell, 0)
        # 因order函数调整为顺序调整，为防止先行调仓股票由于后行调仓股票占金额过大不能一次调整到位，这里运行两次以解决这个问题
        for stock_to_buy in list(holding_list)[0:g.num_stocks]: 
            order_target_value(stock_to_buy, every_stock)
        for stock_to_buy in list(holding_list)[0:g.num_stocks]: 
            order_target_value(stock_to_buy, every_stock)

# 因子数据处理函数单独编号，与系列文章中对应            

# 1BP
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
    # 使用股票代码作为index
    df_BP.index = df_BP.code
    # 删除无用数据
    del df_BP['code']
    return df_BP
    
# 2EP
# 得到一个dataframe：包含股票代码、盈利收益率EP和EP_sorted_rank
# 默认date = context.current_dt的前一天,使用默认值，避免未来函数，不建议修改
# 获得动态市盈率pe_ratio
def get_df_EP(stock_list, context, asc):
    df_EP = get_fundamentals(query(valuation.code, valuation.pe_ratio
                     ).filter(valuation.code.in_(stock_list)))
    # 获得pe倒数
    df_EP['EP'] = df_EP['pe_ratio'].apply(lambda x: 1/x)
    # 删除nan，以备数据中某项没有产生nan
    df_EP = df_EP[pd.notnull(df_EP['EP'])]
    # 复制一个dataframe，按对应项目排序
    df_EP['EP_sorted_rank'] = df_EP['EP'].rank(ascending = asc, method = 'dense')
    # 使用股票代码作为index
    df_EP.index = df_EP.code
    # 删除无用数据
    del df_EP['code']
    return df_EP

# 3PEG
# 输入：context(见API)；stock_list为list类型，表示股票池
# 输出：df_PEG为dataframe: index为股票代码，data为相应的PEG值
def get_df_PEG(stock_list, context, asc):
    # 查询股票池里股票的市盈率，收益增长率
    q_PE_G = query(valuation.code, valuation.pe_ratio, indicator.inc_net_profit_year_on_year
                 ).filter(valuation.code.in_(stock_list)) 
    # 得到一个dataframe：包含股票代码、市盈率PE、收益增长率G
    # 默认date = context.current_dt的前一天,使用默认值，避免未来函数，不建议修改
    df_PE_G = get_fundamentals(q_PE_G)
    # 筛选出成长股：删除市盈率或收益增长率为负值的股票
    df_Growth_PE_G = df_PE_G[(df_PE_G.pe_ratio >0)&(df_PE_G.inc_net_profit_year_on_year >0)]
    # 去除PE或G值为非数字的股票所在行
    df_Growth_PE_G.dropna()
    # 得到一个Series：存放股票的市盈率TTM，即PE值
    Series_PE = df_Growth_PE_G.ix[:,'pe_ratio']
    # 得到一个Series：存放股票的收益增长率，即G值
    Series_G = df_Growth_PE_G.ix[:,'inc_net_profit_year_on_year']
    # 得到一个Series：存放股票的PEG值
    Series_PEG = Series_PE/Series_G
    # 将股票与其PEG值对应
    Series_PEG.index = df_Growth_PE_G.ix[:,0]
    # 生成空dataframe
    df_PEG = pd.DataFrame(Series_PEG)
    # 将Series类型转换成dataframe类型
    df_PEG['PEG'] = pd.DataFrame(Series_PEG)
    # 得到一个dataframe：包含股票代码、盈利收益率PEG和PEG_sorted_rank
    # 赋予顺序排列PEG数据序数编号
    df_PEG['PEG_sorted_rank'] = df_PEG['PEG'].rank(ascending = asc, method = 'dense')
    # 删除不需要列
    df_PEG = df_PEG.drop(0, 1)
    return df_PEG

# 4DP
# 得到一个dataframe：包含股票代码、股息率(DP)和DP_sorted_rank
# 默认date = context.current_dt的前一天,使用默认值，避免未来函数，不建议修改
def get_df_DP(stock_list, context, asc):
    # 获得dividend_payable和market_cap 应付股利(元)和总市值(亿元)
    df_DP = get_fundamentals(query(balance.code, balance.dividend_payable, valuation.market_cap
                     ).filter(balance.code.in_(stock_list)))
    # 按公式计算
    df_DP['DP'] = df_DP['dividend_payable']/(df_DP['market_cap']*100000000)
    # 删除nan
    df_DP = df_DP.dropna()
    # 生成排名序数
    df_DP['DP_sorted_rank'] = df_DP['DP'].rank(ascending = asc, method = 'dense')
    # 使用股票代码作为index
    df_DP.index = df_DP.code
    # 删除无用数据
    del df_DP['code']
    del df_DP['dividend_payable'] 
    del df_DP['market_cap']
    # 改个名字
    df_DP.columns = ['DP', 'DP_sorted_rank']
    return df_DP

# 5CFP
# 得到一个dataframe：包含股票代码、现金收益率CFP和CFP_sorted_rank
# 默认date = context.current_dt的前一天,使用默认值，避免未来函数，不建议修改
def get_df_CFP(stock_list, context, asc):
    # 获得市现率pcf_ratio cashflow/price
    df_CFP = get_fundamentals(query(valuation.code, valuation.pcf_ratio
                     ).filter(valuation.code.in_(stock_list)))
    # 获得pcf倒数
    df_CFP['CFP'] = df_CFP['pcf_ratio'].apply(lambda x: 1/x)
    # 删除nan，以备数据中某项没有产生nan
    df_CFP = df_CFP[pd.notnull(df_CFP['CFP'])]
    # 生成序列数字排名
    df_CFP['CFP_sorted_rank'] = df_CFP['CFP'].rank(ascending = asc, method = 'dense')
    # 使用股票代码作为index
    df_CFP.index = df_CFP.code
    # 删除无用数据
    del df_CFP['code']
    return df_CFP

# 6PS
# 得到一个dataframe：包含股票代码、P/SALES（PS市销率TTM）和PS_sorted_rank
# 默认date = context.current_dt的前一天,使用默认值，避免未来函数，不建议修改
def get_df_PS(stock_list, context, asc):
    # 获得市销率TTMps_ratio
    df_PS = get_fundamentals(query(valuation.code, valuation.ps_ratio
                     ).filter(valuation.code.in_(stock_list)))
    # 删除nan，以备数据中某项没有产生nan
    df_PS = df_PS[pd.notnull(df_PS['ps_ratio'])]
    # 生成排名序数
    df_PS['PS_sorted_rank'] = df_PS['ps_ratio'].rank(ascending = asc, method = 'dense')
    # 使用股票代码作为index
    df_PS.index = df_PS.code
    # 删除无用数据
    del df_PS['code']
    # 改个名字
    df_PS.columns = ['PS', 'PS_sorted_rank']
    return df_PS

# 7ALR
# 得到一个dataframe：包含股票代码、资产负债率(asset-liability ratio, ALR)
# 和ALR_sorted_rank
# 默认date = context.current_dt的前一天,使用默认值，避免未来函数，不建议修改
def get_df_ALR(stock_list, context, asc):
    # 获得total_liability和total_assets 负债合计(元)和资产总计(元)
    df_ALR = get_fundamentals(query(balance.code, balance.total_liability, balance.total_assets
                     ).filter(balance.code.in_(stock_list)))
    # 复制一个dataframe，按对应项目排序
    df_ALR['ALR'] = df_ALR['total_liability']/df_ALR['total_assets']
    # 删除nan
    df_ALR = df_ALR.dropna()
    # 生成排名序数
    df_ALR['ALR_sorted_rank'] = df_ALR['ALR'].rank(ascending = asc, method = 'dense')
    # 使用股票代码作为index
    df_ALR.index = df_ALR.code
    # 删除无用数据
    del df_ALR['code']
    del df_ALR['total_liability'] 
    del df_ALR['total_assets']
    return df_ALR

# 8FACR
# 得到一个dataframe：包含股票代码、固定资产比例(fixed assets to capital ratio, FACR )
# 和FACR_sorted_rank
# 默认date = context.current_dt的前一天,使用默认值，避免未来函数，不建议修改
def get_df_FACR(stock_list, context, asc):
    # 获得fixed_assets和total_assets 固定资产(元)和资产总计(元)
    df_FACR = get_fundamentals(query(balance.code, balance.fixed_assets, balance.total_assets
                     ).filter(balance.code.in_(stock_list)))
    # 根据公式计算
    df_FACR['FACR'] = df_FACR['fixed_assets']/df_FACR['total_assets']
    # 删除nan
    df_FACR = df_FACR.dropna()
    # 生成排名序数
    df_FACR['FACR_sorted_rank'] = df_FACR['FACR'].rank(ascending = asc, method = 'dense')
    # 使用股票代码作为index
    df_FACR.index = df_FACR.code
    # 删除无用数据
    del df_FACR['code']
    del df_FACR['fixed_assets'] 
    del df_FACR['total_assets']
    # 改个名字
    df_FACR.columns = ['FACR', 'FACR_sorted_rank']
    return df_FACR

# 9CMC
# 得到一个dataframe：包含股票代码、流通市值CMC和CMC_sorted_rank
# 默认date = context.current_dt的前一天,使用默认值，避免未来函数，不建议修改
def get_df_CMC(stock_list, context, asc):
    # 获得流通市值 circulating_market_cap 流通市值(亿)
    df_CMC = get_fundamentals(query(valuation.code, valuation.circulating_market_cap
                     ).filter(valuation.code.in_(stock_list)))
    # 删除nan
    df_CMC = df_CMC.dropna()
    # 生成排名序数
    df_CMC['CMC_sorted_rank'] = df_CMC['circulating_market_cap'].rank(ascending = asc, method = 'dense')
    # 使用股票代码作为index
    df_CMC.index = df_CMC.code
    # 删除无用数据
    del df_CMC['code']
    # 改个名字
    df_CMC.columns = ['CMC', 'CMC_sorted_rank']
    return df_CMC

'''
================================================================================
每天收盘后
================================================================================
'''
# 每日收盘后要做的事情（本策略中不需要）
def after_trading_end(context):
    return