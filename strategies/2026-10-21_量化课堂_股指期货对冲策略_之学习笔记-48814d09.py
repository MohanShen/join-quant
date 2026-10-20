# Clone from JoinQuant
# postId: 48814d09238fb9b80764f6e79997ac3a
# backtestId: 3ed5dd2b6a8f30b59c9ca11f2ed599fc
# title: “【量化课堂】股指期货对冲策略”之学习笔记

import statsmodels.api as sm
from statsmodels import regression
import numpy as np
import pandas as pd
#import time 
#from datetime import date
from jqdata import *
import datetime
from dateutil.relativedelta import relativedelta
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
    #set_subportfolios([SubPortfolioConfig(cash=context.portfolio.starting_cash*(1/1.3) ,type='stock'),SubPortfolioConfig(cash=context.portfolio.starting_cash*0.3/1.3,type='index_futures')])
    # 分仓
    stock_cash = np.round(context.portfolio.starting_cash*(1/1.3),0)
    future_cash = context.portfolio.starting_cash - stock_cash
    set_subportfolios(
            [
            SubPortfolioConfig(cash=stock_cash, type='stock'),
            SubPortfolioConfig(cash=future_cash,type='index_futures')
            ]
        )

#1
#设置策参数
def set_params():
    g.tc=20             #调仓频率
    g.yb=63             # 样本长度
    g.percentile=0.03   #设置选股的百分比
    g.pre_future=''     #用来装上次进入的期货合约名字
    g.futures_margin_rate = 0.10   #股指期货保证金比例
    g.futures_symbol = 'IF' #期货指数种类IF,IH,IC
    g.futures_multiplier = 300  # IF和IH每点价值300元，IC为200元
#2
#设置中间变量
def set_variables():
    g.t = 0                     #运行天数
    g.in_position_stocks = []   #持仓股票
    
#3
#设置回测条件
def set_backtest():
    set_option('use_real_price', True) #用真实价格交易
#    log.set_level('order', 'error')
    log.set_level('order', 'warning')
    set_slippage(FixedSlippage(0))     #将滑点设置为0

'''
================================================================================
每天开盘前
================================================================================
'''
#每天开盘前要做的事情
def before_trading_start(context):
    log.info('---------------------------------------------------------------------')
    set_slip_fee(context)
    #g.all_stocks = set_feasible_stocks(get_all_securities(['stock']).index,g.yb,context)

#4 根据不同的时间段设置滑点与手续费
def set_slip_fee(context):
    # 将滑点设置为0
    set_slippage(FixedSlippage(0)) 
    # 根据不同的时间段设置手续费
    dt=context.current_dt
    # log.info(type(context.current_dt))
    
    if dt>datetime.datetime(2013,1, 1):
        set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5)) 
        
    elif dt>datetime.datetime(2011,1, 1):
        set_commission(PerTrade(buy_cost=0.001, sell_cost=0.002, min_cost=5))
            
    elif dt>datetime.datetime(2009,1, 1):
        set_commission(PerTrade(buy_cost=0.002, sell_cost=0.003, min_cost=5))
                
    else:
        set_commission(PerTrade(buy_cost=0.003, sell_cost=0.004, min_cost=5))
    
    # 设置期货合约保证金
    if dt>datetime.datetime(2015,9,7):
        g.futures_margin_rate = 0.2 
    else:
        g.futures_margin_rate = 0.1 
    set_option('futures_margin_rate', g.futures_margin_rate)

#5
# 设置可行股票池：
# 过滤掉当日停牌的股票,且筛选出前days天未停牌股票，这里我们设置为一个季度
# 输入：stock_list-list类型,样本天数days-int类型，context（见API）
# 输出：颗星股票池-list类型
def set_feasible_stocks(stock_list,days,context):
    # 得到是否停牌信息的dataframe，停牌的1，未停牌得0
    suspened_info_df = get_price(list(stock_list), start_date=context.current_dt, \
        end_date=context.current_dt, frequency='daily', fields='paused')['paused'].T
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


'''
================================================================================
每天交易时
================================================================================
'''
#每个交易日需要运行的函数
def handle_data(context, data):
    # 计算持仓股票
    g.in_position_stocks = compute_signals(context)
    # 计算对冲比例和 beta
    hedge_ratio, beta = compute_hedge_ratio(context, g.in_position_stocks)
    # 调仓
    rebalance(hedge_ratio, beta, context)
    # 天数加一
    g.t += 1

# 6
# 计算持仓股票
# 输出一 list 股票
def compute_signals(context):
    # 如果是调仓日
    if g.t%g.tc==0:
        # 获取可行股票池
        all_stocks = set_feasible_stocks(get_all_securities(['stock']).index,g.yb,context)
        # 获取所有股票的财务数据总负债和总资产
        q = query(
                balance.code, balance.total_liability, balance.total_assets, \
                (balance.total_liability/balance.total_assets).label('ALR')
            ).filter(
                balance.code.in_(all_stocks)
            ).order_by(
                (balance.total_liability/balance.total_assets).desc()        #按资产负债率降序
            )
        data = get_fundamentals(q)
        stock_list = data['code'].tolist()
        # 过滤掉ST
        # current_data = get_current_data()
        # stock_list = [stock for stock in stock_list \
            # if not current_data[stock].is_st]
        # 输出最靠前的 3%
        return stock_list[:int(len(all_stocks)*g.percentile)]
        '''
        # 获取所有股票的财务数据总负债和总资产
        q = query(balance.code, balance.total_liability, balance.total_assets).filter(balance.code.in_(g.all_stocks))
        data = get_fundamentals(q)
        # 计算资产负债比
        data['ALR'] = data['total_liability']/data['total_assets']
        # 资产负债比从大到小排列
        data = data.sort('ALR', ascending=False)
        # 输出最靠前的 3%
        return list(data.code)[:int(float(len(g.all_stocks))*g.percentile)]
        '''
    # 如果不是调仓日
    else:
        # 延续旧的持仓股票
        return g.in_position_stocks

# 7 
# 计算对冲比例
# 输出两个 float
def compute_hedge_ratio(context, in_position_stocks):
    # 取股票在样本时间内的价格
    prices = history(g.yb, '1d', 'close', in_position_stocks)
    # 取指数在样本时间内的价格
    index_prices = attribute_history('000300.XSHG', g.yb, '1d', 'close')
    # prices 行:日期,列:各只股票 =>pct_change():dataframe, 结构不变，值为日收益率=>[1:] drop first row
    # =>mean(axis=1)横向平均,Series=>.values:array
    portfolio_Rets = prices.pct_change()[1:].mean(axis=1).values
    # pct_change():dataframe, 结构不变，值为日收益率=>[1:] drop first row=>.close:Series =>values:array
    index_Rets = index_prices.pct_change()[1:].close.values
    '''
    # 计算股票在样本时间内的日收益率
    rets = [(prices.iloc[i+1,:]-prices.iloc[i,:])/prices.iloc[i,:] for i in range(g.yb-1)]
    # 计算日收益率平均
    portfolio_Rets = [np.mean(x) for x in rets]
    # 计算指数的日收益率
    index_Rets = [(y-x)/x for (x,y) in zip(index_prices[:-1],index_prices[1:])]
    '''
    '''
    计算组合和指数的协方差矩阵cov_mat: shape(2*2)
                Rp       |    Rm
         Rp    Var(Rp)   | cov(Rp,Rm)
         Rm   cov(Rm,Rp) | Var(Rm)
    '''
    cov_mat = np.cov(portfolio_Rets, index_Rets)
    # 计算组合的系统性风险beta
    beta = cov_mat[0,1]/cov_mat[1,1]
    '''
    # 另一种算法
    index_Rets = sm.add_constant(index_Rets)    # 常数用来拟合alpha，系数用来拟合beta
    model = regression.linear_model.OLS(portfolio_Rets, index_Rets).fit()  #线性回归，OLS普通最小二乘法ordinary least square
    alpha, beta = model.params[0], model.params[1]
    '''
    # 计算并返回对冲比例
    return 1 + beta*g.futures_margin_rate + beta/5, beta
    
# 8
# 调仓函数
# 输入对冲比例
def rebalance(hedge_ratio, beta, context):
    log.info('hedge_ratio: %.6f, beta: %.6f, futures_margin_rate: %.2f' % (hedge_ratio, beta, g.futures_margin_rate))
    
    # 计算资产总价值
    total_value = context.portfolio.total_value
    log.info('portfolio Total_value: %.2f, Stock subportfolio total_value: %.2f, Futures subportfolio total_value: %.2f' % \
        (total_value, context.subportfolios[0].total_value, context.subportfolios[1].total_value))
    # 计算预期的股票账户价值
    expected_stock_value = np.round(total_value/hedge_ratio,0)
    
    # 将两个账户的钱调到预期的水平
    # Futures to Stock
    cash_FtoS = min(context.subportfolios[1].transferable_cash, max(0, expected_stock_value-context.subportfolios[0].total_value))
    transfer_cash(1, 0, cash_FtoS)
    log.info('期货账户出金: %.2f' % cash_FtoS)
    
    # Stock to Futures
    cash_StoF = min(context.subportfolios[0].transferable_cash, max(0, context.subportfolios[0].total_value-expected_stock_value))
    transfer_cash(0, 1,cash_StoF )
    log.info('股票账户出金: %.2f' % cash_StoF)
    
    # 计算股票账户价值（预期价值和实际价值其中更小的那个）
    stock_value = min(context.subportfolios[0].total_value, expected_stock_value)
    log.info('Target stock_value: %.2f' % stock_value)
    
    # 计算相应的期货保证金价值
    futures_margin = stock_value * beta * g.futures_margin_rate 
    log.info('Target futures_margin: %.2f' % futures_margin)
    
    # 调整股票仓位，在 g.in_position_stocks 里的等权分配
    for stock in context.subportfolios[0].long_positions.keys():
        if stock not in g.in_position_stocks:
            order_target(stock, 0, pindex=0)
    '''        
    for stock in g.in_position_stocks:
        order_target_value(stock, stock_value/len(g.in_position_stocks), pindex=0)
    for stock in g.in_position_stocks:
        order_target_value(stock, stock_value/len(g.in_position_stocks), pindex=0)
    '''
    curr_data = get_current_data()
    target_stocks = [stock for stock in g.in_position_stocks if not curr_data[stock].paused ] #过滤掉今日停牌的
    
    per_value = stock_value/len(g.in_position_stocks) #每只股票应该达到的权值    
    over_weight_list  = [stock for stock in target_stocks if \
        context.subportfolios[0].long_positions[stock].value > per_value]  #现持仓中超权的
    under_weight_list = [stock for stock in target_stocks if \
        stock not in over_weight_list]  #剩余的，就是贴权的，应该补权
    
    for stock in over_weight_list:      # 超权的先减仓，削高
        order_target_value(stock, per_value, pindex=0)
    for stock in under_weight_list:     # 贴权的再加仓，填低
        order_target_value(stock, per_value, pindex=0)
        
    # 获取下月连续合约 string
    current_future = get_next_month_future(context, g.futures_symbol)   #g.futures_symbol: IF,IH,IC
    # 如果下月合约和原本持仓的期货不一样
    if g.pre_future!='' and g.pre_future!=current_future:
        # 就把仓位里的期货平仓
        order_target(g.pre_future, 0, side='short', pindex=1)
    # 现有期货合约改为刚计算出来的
    g.pre_future = current_future
    
    '''
    # 获取沪深300价格
    index_price = attribute_history('000300.XSHG',1, '1d', 'close').close.iloc[0]
    log.info('HS300 index_price: %.2f' %  index_price)
    '''
    # 获取期货指数价格
    index_price = attribute_history(current_future, 1, '1d', 'close').close.iloc[0]
    log.info('Index futures: %s, Price: %.2f' % (current_future, index_price))
    
    # 计算并调整需要的空单仓位
    nShortAmount = int(np.round(futures_margin/(index_price * g.futures_multiplier * g.futures_margin_rate),0))   # 目标手数
    nHoldAmount = context.subportfolios[1].short_positions[current_future].total_amount  #现持仓手数
    log.info('股指期货: %s, 现持仓手数: %d, 目标手数: %d' % (current_future, nHoldAmount, nShortAmount))
    if nShortAmount != nHoldAmount:
        order = order_target(current_future, nShortAmount, side='short', pindex=1)
        if order != None and order.filled > 0:
            log.info('Futures: %s, action: short %s, filled: %d, price: %.2f' % \
                (order.security, ('平空' if order.is_buy else '开仓'), order.filled, order.price))
        else:
            log.info('Futures: %s, order failure' % (current_future))
    
    # 记录调仓完毕之后的信息：
    log.info('股指期货标的价值F: %.2f, beta: %.6f, 股票总市值S: %.2f' % \
        (context.subportfolios[1].positions_value, beta, context.subportfolios[0].positions_value))
    # 检验调仓后是否满足 F = beta * S，看其偏离度%：100*(F/( beta * S) - 1), 负数：股指期货不足，正数：股指期货超量
    log.info('股指期货标的价值偏离度: %.2f%%' % \
        (100*(context.subportfolios[1].positions_value/( beta * context.subportfolios[0].positions_value) - 1)))
    
# 取下月连续string
# 输入 context 和一个 string，后者是'IF'或'IC'或'IH'
# 输出一 string，如 'IF1509.CCFX'
# 进入本月第三周即切换到下月合约，而不等第三周的周五本月合约结束
def get_next_month_future(context, symbol):
    dt = context.current_dt
    month_begin_day = datetime.date(dt.year, dt.month, 1).isoweekday() # 本月1号是星期几(1-7)
    third_monday_date = 16 - month_begin_day + 7*(month_begin_day>5) #本月的第三个星期一是几号
    # 如果今天没过第三个星期一
    if dt.day < third_monday_date:
        next_dt = dt #本月合约
    else:
        next_dt = dt + relativedelta(months=1)  #切换至下月合约
    
    year = str(next_dt.year)[2:]
    month = ('0' + str(next_dt.month))[-2:]
    
    return (symbol+year+month+'.CCFX')