# Clone from JoinQuant
# postId: 371f0110c92dfa09f7078a3d90bc98c6
# backtestId: 504f2a43406729bb73c4a1256df0d003
# title: 一点想法

import jqdata # 导入函数库
import numpy as np
import pandas as pd
import statsmodels.api as sm

'''
================================================================================
运行策略之前
================================================================================
'''

def initialize(context): # 初始化函数，运行前调用
    set_params() #给参数的函数


def set_params():
    g.security1 = '000418.XSHE' # 股票1 x
    g.security2 = '002508.XSHE' # 股票2 y
    g.regression_ratio = 0.8376 # 回归系数
    g.N1 = []
    g.N2 = []
    #g.p = 0.5 # 股票1默认仓位
    #g.q = 0.5 # 股票2默认仓位
    g.outsignal = 0
    g.days = 0 
    g.number_days = 20
    g.test_days = 120 # 算z-score天数
    
    
def before_trading_start(context): # 每个交易日前调用的函数
    set_slip_fee(context) # 设置滑点
    
    
def set_slip_fee(context):
    set_slippage(FixedSlippage(0)) # 将滑点初始设置为0
    dt=context.current_dt # 根据不同的时间段设置手续费
    if dt>datetime.datetime(2013,1, 1):
        set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5)) 
    elif dt>datetime.datetime(2011,1, 1):
        set_commission(PerTrade(buy_cost=0.001, sell_cost=0.002, min_cost=5))
    elif dt>datetime.datetime(2009,1, 1):
        set_commission(PerTrade(buy_cost=0.002, sell_cost=0.003, min_cost=5))
    else:
        set_commission(PerTrade(buy_cost=0.003, sell_cost=0.004, min_cost=5))

'''        
================================================================================
每天交易时
================================================================================
'''

def handle_data(context, data):
    dt = context.current_dt # 当前日期
    current_price1 = data[g.security1].price # 当前价格N 
    current_price2 = data[g.security2].price # 当前价格N
    if dt.hour==9 and dt.minute==30: #早上九点半开盘
        g.days += 1
        g.N1 = calculate_N(g.security1, g.N1) #计算N的值
        g.N2 = calculate_N(g.security2, g.N2) 
    if g.days > 20:
        value = context.portfolio.portfolio_value # 当前持有的股票和现金的总价值
        cash = context.portfolio.available_cash # 可花费的现金
        dollar_volatility1 = g.N1[-1] # 计算美元波动的价格
        dollar_volatility2 = g.N2[-1]
        unit1 = value * 0.01 / dollar_volatility1 # 依本策略，计算买卖的单位
        unit2 = value * 0.01 / dollar_volatility2
        new_state = get_signal() # 获取当前状态，根据状态决定如何操作
        if new_state == 'buy1':
            market_in(current_price1, unit1, cash, g.security1, 3) # 进场 买第一只
            print '进场1'
            #market_out(current_price2, unit2, cash, g.security2) # 清空第二只
        if new_state == 'add1':
            market_in(current_price1, unit1, cash, g.security1, 2) # 加仓 第一只
            #market_out(current_price2, unit2, cash, g.security2) # 继续减仓 第二只
            print '加仓1'
        if new_state == 'add2':
            market_in(current_price1, unit1, cash, g.security1, 1) # 第二次加仓 第一只
            #market_out(current_price2, unit2, cash, g.security2) # 第三次减仓 第二只
            print '加仓2'
        if new_state == 'buy2':
            market_in(current_price2, unit2, cash, g.security2, 3) # 进场 买第二只
            #market_out(current_price1, unit1, cash, g.security1) # 清空第一只
            print '进场2'
        if new_state == 'add3':
            market_in(current_price2, unit1, cash, g.security1, 2) # 加仓 第二只
            #market_out(current_price1, unit1, cash, g.security1) # 继续减仓 第一只
            print '加仓3'
        if new_state == 'add4':
            market_in(current_price2, unit2, cash, g.security2, 1) # 第二次加仓 第二只
            #market_out(current_price1, unit1, cash, g.security1) # 第三次减仓 第一只
            print '加仓4'
        if new_state == 'side':
            stop_loss() # 空仓和止损函数用同一个
            print '平仓'
        if new_state == 'out':
            stop_loss() # 空仓和止损函数用同一个

def z_test1(): # 计算今天的z-score
    prices1 = np.array(attribute_history(g.security1, g.test_days, '1d', ['close']).close) # 获得历史数据
    prices2 = np.array(attribute_history(g.security2, g.test_days, '1d', ['close']).close)
    stable_series = prices2 - g.regression_ratio * prices1 # 根据回归比例算它们的平稳序列 Y-a.X
    series_mean = mean(stable_series) # 算均值
    sigma = np.std(stable_series) # 算标准差
    diff = stable_series[-1] - series_mean # 算序列现值离均值差距多少 
    return(diff/sigma) # 返回z值
    
def z_test2(): # 计算前一天的z-score
    prices1 = np.array(attribute_history(g.security1, g.test_days+1, '1d', ['close']).close) # 获得历史数据
    prices2 = np.array(attribute_history(g.security2, g.test_days+1, '1d', ['close']).close)
    prices1 = prices1[0:g.test_days]
    prices2 = prices2[0:g.test_days]
    stable_series = prices2 - g.regression_ratio * prices1 # 根据回归比例算它们的平稳序列 Y-a.X
    series_mean = mean(stable_series) # 算均值
    sigma = np.std(stable_series) # 算标准差
    diff = stable_series[-1] - series_mean # 算序列现值离均值差距多少 
    return(diff/sigma) # 返回z值


def get_signal(): # 返回新的状态，是一个string,根据信号对股票进行操作
    z_score1 = z_test1()
    z_score2 = z_test2()
    if g.outsignal == 0:
        if 1 < z_score1 < 2 and -1 <= z_score2 <= 1:
            return('buy1') # 进场 买第一只，并卖出第二只
        if 2 < z_score1 < 3 and 1 <= z_score2 <= 2: 
            return('add1') # 给第一只 第一次加仓
        if z_score1 > 3 and 2 <= z_score2 <= 3:
            return('add2') # 给第一只 第二次加仓
        #if z_score > 4:
        #    return('out')
        if -2 < z_score1 < -1 and -1 <= z_score2 <= 1: 
            return('buy2') # 进场 买第二只，并卖出第一只
        if -3 < z_score1 < -2 and -2 <= z_score2 <= -1:
            return('add3') # 给第二只 第一次加仓
        if z_score1 < -3 and -3 <= z_score2 <= -2:
            return('add4') # 给第二只 第二次加仓
        #if z_score < -4:
        #    return ('out') 
        if -1 <= z_score1 <= 1 and 1 < z_score2 < 2: # 如果在正负标准差之
            return('side') 
        if -1 <= z_score1 <= 1 and -2 < z_score2 < -1: # 如果在正负标准差之
            return('side')
    if g.outsignal == 1:
        return('out')

def calculate_N(stock, N): # 计算N值
    if g.days <= 20: # 如果交易天数小于等于20天，N值的计算需要二十天的数据
        price = attribute_history(stock, g.days, '1d',('high','low','close'))
        lst = []
        for i in range(0, g.days):
            h_l = price['high'][i]-price['low'][i]
            h_c = price['high'][i]-price['close'][i]
            c_l = price['close'][i]-price['low'][i]
            True_Range = max(h_l, h_c, c_l) # 计算 True Range
            lst.append(True_Range)
        current_N = np.mean(np.array(lst)) # 计算前g.days（小于等于20）天的True_Range平均值，即当前N的值：
        N.append(current_N)
    else: # 如果交易天数超过20天
        price = attribute_history(stock, 1, '1d',('high','low','close'))
        h_l = price['high'][0]-price['low'][0]
        h_c = price['high'][0]-price['close'][0]
        c_l = price['close'][0]-price['low'][0]
        True_Range = max(h_l, h_c, c_l)
        current_N = (True_Range + (g.number_days-1) * N[-1]) / g.number_days
        N.append(current_N)
    return N
    
##### 把入场和加仓写作一个函数，因为重复比较多，a是买入的份数
def market_in(current_price, unit, cash, stock, a): # stock储存要操作的股票名，current_price和cash用来计算可以购买的股票股数（手）
    num_of_shares = cash / current_price # 计算可以买该股票的股数
    if num_of_shares >= unit: # 海龟策略里买卖单位
        print unit
        print current_price
        order(stock, a*int(unit))

def market_out(current_price, unit, cash, stock): # 卖出后保留b个unit单位的股票
    num_of_shares = cash / current_price # 计算可以买该股票的股数
    if num_of_shares >= unit: # 海龟策略里买卖单位
        print unit
        print current_price
        order_target(stock, 0)

def stop_loss():
    order_target(g.security1, 0)
    order_target(g.security2, 0)
    
'''        
================================================================================
每天收盘后 # 每天计算回归系数
================================================================================
'''

def after_trading_end(context):
    suma = attribute_history(g.security1, 20, '1d', ('close'))
    a=0
    for i in range(1,21):
        a+=suma['close'][-i]
    a = a/20
    
    sumb = attribute_history(g.security1, 60, '1d', ('close'))
    b=0
    for i in range(1,61):
        b+=sumb['close'][-i]
    b = b/60
    
    sumc = attribute_history(g.security2, 20, '1d', ('close'))
    c=0
    for i in range(1,21):
        c+=sumc['close'][-i]
    c = c/20
    
    sumd = attribute_history(g.security2, 60, '1d', ('close'))
    d=0
    for i in range(1,61):
        d+=sumd['close'][-i]
    d = d/60
    
    if a < b and c < d:
        g.outsignal = 1
    else:
        g.outsignal = 0
    
    
    
    #stockPol = ['600804.XSHG', '601611.XSHG', '600115.XSHG', '600085.XSHG', '600718.XSHG', '600089.XSHG', '601111.XSHG', '600875.XSHG']
    #if g.outsignal == 1:
    #    g.security1 = stockPol[1] # 股票1 x
    #    g.security2 = stockPol[2] # 股票2 y
    #    prices1 = np.array(attribute_history(g.security1, 200, '1d', ['close']).close) # 获得历史数据
    #    prices2 = np.array(attribute_history(g.security2, 200, '1d', ['close']).close)
    #    prices1 = sm.add_constant(prices1)
    #    results = sm.OLS(prices2,prices1).fit()
    #    g.regression_ratio = results.params[1]
    #    g.outsignal = 0
    






