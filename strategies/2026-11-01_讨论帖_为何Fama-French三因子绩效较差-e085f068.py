# Clone from JoinQuant
# postId: e085f0680706a2f775b4bb9dd5731d71
# backtestId: 482b28816c2caae7547d6973fe1c151e
# title: 【讨论帖】为何Fama-French三因子绩效较差

import statsmodels.api as sm
from statsmodels import regression
import numpy as np
import pandas as pd
import time 
from datetime import date
from jqdata import *


'''
================================================================================
总体回测前
================================================================================
'''
#总体回测前要做的事情
def initialize(context):
    set_params()        #1 设置策参数
    set_variables()     #2 设置中间变量
    set_backtest()      #3 设置回测条件
    # 定时运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
    # 开盘前运行，按月运行
    run_monthly(before_trading_start, monthday = 1, time = 'before_open', reference_security='000300.XSHG')
    # 开盘时运行
    run_monthly(trade, monthday = 1, time = 'open', reference_security='000300.XSHG')
    # 收盘后运行
    run_daily(after_trading_end, time='after_close', reference_security='000300.XSHG')

    
#设置策参数
def set_params():
    g.yb = 63               # 样本长度
    g.N = 15                # 持仓数目
    g.rf = 0.04             # 无风险利率
    g.index = '000300.XSHG' # 定义基准沪深300


#设置中间变量
def set_variables():
    g.feasible_stocks = []  # 当前可交易股票池


#设置回测条件
def set_backtest():
    set_benchmark('000300.XSHG')                    # 以沪深300为基准
    set_option('use_real_price', True)              # 用真实价格交易
    log.info('初始函数开始运行且全局只运行一次')    # 输出内容到日志 log.info()
    log.set_level('order', 'error')                 # 设置报错等级，过滤掉order系列API产生的比error级别低的log


'''
================================================================================
每天开盘前
================================================================================
'''
# 每天开盘前要做的事情
def before_trading_start(context):
    # 输出运行时间
    log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))
    # 设置手续费与滑点
    set_slip_fee(context) 
    # 设置可行股票池：获得当前开盘的沪深300股票池并剔除当前或者计算样本期间停牌的股票
    g.feasible_stocks = set_feasible_stocks(get_index_stocks('000300.XSHG'),g.yb,context)
    

# 根据不同的时间段设置滑点与手续费
def set_slip_fee(context):
    # 将滑点设置为0.002
    set_slippage(PriceRelatedSlippage(0.002)) 
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
    unsuspened_stocks = list(suspened_info_df[unsuspened_index].index)
    # 进一步，筛选出前days天未曾停牌的股票list:
    feasible_stocks=[]
    current_data=get_current_data()
    for stock in unsuspened_stocks:
        if sum(attribute_history(stock, days, unit='1d', fields=('paused'), skip_paused=False))[0]==0:
            feasible_stocks.append(stock)
            
    return feasible_stocks


'''
================================================================================
每天交易时
================================================================================
'''

#每天交易时要做的事情
def trade(context):
    # 输出运行时间
    log.info('函数运行时间(trade):'+str(context.current_dt.time()))
    # 获取回归的alpha，该df的index为code
    df_alpha = get_df_alpha(g.feasible_stocks,context)
    # 按照alpha从小到大排序，小的在前面
    log.info(df_alpha.sort('alpha',ascending = True))
    stocks = list(df_alpha.sort('alpha',ascending = True).index)
    # 获取前g.N支股票为holding_list
    holding_list = stocks[0:g.N]
    log.info(holding_list)
    # 重新调整仓位，输入context，使用信号结果holding_list
    rebalance(context, holding_list)


# 获取FF三因子与个股超额收益率回归的残差数据
def get_df_alpha(stocks_list,context):
    # 获取个股一个月日度超额收益率数据
    price = get_price(stocks_list,end_date = context.previous_date,count = 1+g.yb,fields = ['close'])['close']
    ri = price/price.shift(1) - 1
    ri_rf = ri - g.rf
    # 获取FF三因子日度数据
    # 获取市场风险溢价日度数据
    index_price = get_price(g.index,end_date = context.previous_date,count = 1+g.yb,fields = ['close'])
    rm = index_price/index_price.shift(1) - 1
    rm_rf = rm - g.rf
    rm_rf.columns = ['benchmark']
    # 获取每日的SMB和HML数据
    d_list = []
    smb_list = []
    hml_list = []
    for i in price.index.tolist():
        # 获取个股日度超额收益率数据
        price_oneday = get_price(stocks_list, end_date = i, fields = ['close'], count = 2)['close']
        ret_oneday = price_oneday/price_oneday.shift(1) - 1
        ri_rf_oneday = ret_oneday - g.rf
        ri_rf_oneday = ri_rf_oneday.iloc[-1,:]
        ri_rf_oneday.name = 'ri_rf_oneday'
        # 获取SMB日度数据
        # 获取BP、市值数据
        q = query(valuation.code,valuation.market_cap,valuation.pb_ratio).filter(valuation.code.in_(stocks_list))
        factor_data = get_fundamentals(q,date = i)
        factor_data.loc[:,'BP'] = 1/factor_data.loc[:,'pb_ratio']
        factor_data.index = factor_data['code']
        # 删除无用数据
        del factor_data['code']
        del factor_data['pb_ratio']
        # 个股超额收益率数据与因子数据合并
        factor_data = pd.concat([factor_data,ri_rf_oneday],axis = 1)
        # 计算市值大、小公司
        medium_line = factor_data.loc[:,'market_cap'].quantile(1/2)
        # 生成small列，small为1，big为2
        factor_data.loc[factor_data.loc[:,'market_cap'] < medium_line,'small'] = 1
        factor_data.loc[factor_data.loc[:,'market_cap'] >= medium_line,'small'] = 2
        # 计算股权账面价值/股权市值高、中、低公司
        high_line = factor_data.loc[:,'BP'].quantile(0.7)
        low_line = factor_data.loc[:,'BP'].quantile(0.3)
        # 生成low列，1为low，3为medium，5为high
        factor_data.loc[factor_data.loc[:,'BP'] > high_line,'low'] = 5
        factor_data.loc[factor_data.loc[:,'BP'] < low_line,'low'] = 1
        factor_data.loc[(factor_data.loc[:,'BP'] >= low_line)&(factor_data.loc[:,'BP'] <= high_line),'low'] = 3
        # 生成judge列，用small列加low列
        factor_data['judge'] = factor_data['small']+factor_data['low']
        # 获取六种组别的公司
        s_l = factor_data.loc[factor_data['judge'] == 2,:]
        s_m = factor_data.loc[factor_data['judge'] == 4,:]
        s_h = factor_data.loc[factor_data['judge'] == 6,:]
        b_l = factor_data.loc[factor_data['judge'] == 3,:]
        b_m = factor_data.loc[factor_data['judge'] == 5,:]
        b_h = factor_data.loc[factor_data['judge'] == 7,:]
        # 计算每组的权重
        s_l['weight'] = s_l['market_cap']/s_l['market_cap'].sum()
        s_m['weight'] = s_m['market_cap']/s_m['market_cap'].sum()
        s_h['weight'] = s_h['market_cap']/s_h['market_cap'].sum()
        b_l['weight'] = b_l['market_cap']/b_l['market_cap'].sum()
        b_m['weight'] = b_m['market_cap']/b_m['market_cap'].sum()
        b_h['weight'] = b_h['market_cap']/b_h['market_cap'].sum()
        # 计算每组的加权收益率
        s_l['wr'] = s_l['weight'] * s_l['ri_rf_oneday']
        s_m['wr'] = s_m['weight'] * s_m['ri_rf_oneday']
        s_h['wr'] = s_h['weight'] * s_h['ri_rf_oneday']
        b_l['wr'] = b_l['weight'] * b_l['ri_rf_oneday']
        b_m['wr'] = b_m['weight'] * b_m['ri_rf_oneday']
        b_h['wr'] = b_h['weight'] * b_h['ri_rf_oneday']
        # 计算SMB
        smb = (s_l['wr'].sum() + s_m['wr'].sum() + s_h['wr'].sum())/3 - (b_l['wr'].sum() + b_m['wr'].sum() + b_h['wr'].sum())/3
        # 获取HML日度数据
        hml = (s_l['wr'].sum() + b_l['wr'].sum())/2 - (s_h['wr'].sum() + b_h['wr'].sum())/2
        # 写入一个df，index列为日期
        d_list.append(i)
        smb_list.append(smb)
        hml_list.append(hml)
    smb_hml = pd.DataFrame({'date':d_list,'smb':smb_list,'hml':hml_list})
    smb_hml.index = smb_hml['date']
    del smb_hml['date']
    # 市场风险溢价、smb、hml合并在一起
    smb_hml_rm_rf = pd.concat([smb_hml,rm_rf],axis = 1)
    # 每一支股票与三因子回归
    c_list = []
    alpha_list = []
    for j in ri_rf.columns.tolist():
        # 数据合并在一起
        ri_rf_y = ri_rf[j]
        ri_rf_y.name = 'yi'
        ri_rf_smb_hml_rm_rf = pd.concat([smb_hml_rm_rf,ri_rf_y],axis = 1)
        # 去重
        ri_rf_smb_hml_rm_rf = ri_rf_smb_hml_rm_rf.dropna()
        if len(ri_rf_smb_hml_rm_rf) != 0:
            # 模型回归
            model = sm.formula.ols('yi ~ smb + hml + benchmark', data = ri_rf_smb_hml_rm_rf).fit()
            # 取截距项
            coef = model.params[0]
            # 存入df_alpha
            c_list.append(j)
            alpha_list.append(coef)
        else:
            continue
    df_alpha = pd.DataFrame({'code':c_list,'alpha':alpha_list})
    df_alpha.index = df_alpha['code']
    del df_alpha['code']
    
    return df_alpha


# 依本策略的买入信号，得到应该买的股票列表
# 借用买入信号结果，不需额外输入
# 输入：context，holding_list（见API）
def rebalance(context, holding_list):
    # 每只股票购买金额
    every_stock = context.portfolio.portfolio_value/g.N
    # 空仓只有买入操作
    if len(list(context.portfolio.positions.keys())) == 0:
        for stock_to_buy in holding_list:
            order_target_value(stock_to_buy, every_stock)
    else :
        # 不是空仓先卖出持有但是不在购买名单中的股票
        for stock_to_sell in list(context.portfolio.positions.keys()):
            if stock_to_sell not in holding_list:
                order_target_value(stock_to_sell, 0)
        # 因order函数调整为顺序调整，为防止先行调仓股票由于后行调仓股票占金额过大不能一次调整到位，这里运行两次以解决这个问题
        for stock_to_buy in holding_list:
            order_target_value(stock_to_buy, every_stock)
        for stock_to_buy in holding_list:
            order_target_value(stock_to_buy, every_stock)
            
            
'''
================================================================================
每天收盘后
================================================================================
'''
#每天收盘后要做的事情
def after_trading_end(context):
    log.info(str('函数运行时间(after_trading_end):'+str(context.current_dt.time())))
    log.info('一天结束')
    log.info('##############################################################')


