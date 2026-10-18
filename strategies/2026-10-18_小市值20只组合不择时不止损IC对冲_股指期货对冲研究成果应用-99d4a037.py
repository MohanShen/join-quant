# Clone from JoinQuant
# postId: 99d4a0378dd55d61fe5ce19581ee81c0
# backtestId: e9da53733c42ceb9ee6604be12e14366
# title: 小市值20只组合不择时不止损IC对冲——股指期货对冲研究成果应用

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
    g.tc=5              # 调仓频率
    g.yb=63             # 样本长度
    
    g.pick_stock_count = 100    # 备选股票数量
    g.buy_stock_count = 20     # 买入股票数目
    
    g.pre_future=''     #用来装上次进入的期货合约名字
    g.futures_margin_rate = 0.10   #股指期货保证金比例
    g.futures_symbol = 'IC' #期货指数种类IF,IH,IC
    g.futures_multiplier = (200 if g.futures_symbol=='IC' else 300)  # IF和IH每点价值300元，IC为200元
#2
#设置中间变量
def set_variables():
    g.t = 0                     #运行天数
    g.in_position_stocks = []   #持仓股票
    
#3
#设置回测条件
def set_backtest():
    set_option('use_real_price', True) #用真实价格交易
    log.set_level('order', 'warning')
    # set_slippage(FixedSlippage(0))     #将滑点设置为0

'''
================================================================================
每天开盘前
================================================================================
'''
#每天开盘前要做的事情
def before_trading_start(context):
    log.info('---------------------------------------------------------------------')
    set_slip_fee(context)

#4 根据不同的时间段设置滑点与手续费
def set_slip_fee(context):
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

'''
================================================================================
每天交易时
================================================================================
'''
#每个交易日需要运行的函数
def handle_data(context, data):
    # 计算持仓股票
    g.in_position_stocks = compute_signals(context, data)
    # 计算对冲比例和 beta
    hedge_ratio, beta = compute_hedge_ratio(context, g.in_position_stocks)
    # 调仓
    rebalance(hedge_ratio, beta, context)
    # 天数加一
    g.t += 1

def pick_stocks(context, data):
    q = query(valuation.code)
    q = q.filter(
            indicator.eps > 0,
            ~valuation.code.like('300%')    #剔除创业板
            )
    q = q.order_by(
                valuation.market_cap.asc()
            ).limit(
                g.pick_stock_count
            )
    
    df = get_fundamentals(q)
    stock_list = list(df['code'])

    # 剔除上市未超过120天的(因为样本要求63个交易日的数据)，停牌的，ST的，涨跌停的    
    dToday = context.current_dt.date()
    current_data = get_current_data()
    stock_list = [stock for stock in stock_list if \
        (dToday - get_security_info(stock).start_date).days > 120 and
        (not current_data[stock].paused) and 
        (not current_data[stock].is_st) and 
        (current_data[stock].low_limit < data[stock].close < current_data[stock].high_limit)]
    
    # 对股票评分
    dst_stocks = {}
    for stock in stock_list:
        h = attribute_history(stock, 130, unit='1d', fields=('close', 'high', 'low'), skip_paused=True)
        low_price_130 = h.low.min()
        high_price_130 = h.high.max()

        avg_15 = data[stock].mavg(15, field='close')
        cur_price = data[stock].close
        
        score = (cur_price-low_price_130) + (cur_price-high_price_130) + (cur_price-avg_15)
        
        dst_stocks[stock] = score
    
    df = pd.DataFrame({'score':dst_stocks})    
    df = df.sort(columns='score', ascending=True)
    stock_list = df.index.tolist()

    return stock_list[:g.buy_stock_count]

# 6
# 计算持仓股票
# 输出一 list 股票
def compute_signals(context, data):
    # 如果是调仓日
    if g.t%g.tc==0:
        return pick_stocks(context, data)   #选股
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

    #计算组合和指数的协方差矩阵cov_mat
    cov_mat = np.cov(portfolio_Rets, index_Rets)
    # 计算组合的系统性风险beta
    beta = cov_mat[0,1]/cov_mat[1,1]

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