# Clone from JoinQuant
# postId: 346bc18177a5ccde409d82bb9a09e500
# backtestId: 224e8f4ac4633de8b46336f5e443a7c2
# title: 一个没劲的波动策略

import math
import talib as tl
import pandas as pd
import numpy as np
from datetime import timedelta
import talib


# 名称：
# 介绍：
# 风险：
# 仓位：
# 适用：
# 其他：

def initialize(context):
    # 初始化此策略
    # 设置要操作的股票池为空，每天需要不停变化股票池
    set_universe([])
    
    # 设置手续费，买入时万分之三，卖出时万分之三加千分之一印花税, 每笔交易最低扣5块钱
    set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
    
    # 设置风险基准为沪深300指数
    g.riskbench = '000300.XSHG'

    # 设置基准对比为沪深300指数
    set_benchmark(g.riskbench)

    # 关闭部分log
    log.set_level('order', 'error')
    
    # 设置真实交易时间
    set_option('use_real_price',True)
    
    # 初始化日期
    g.d_yesterday = ''
    g.d_today = ''
    
    ###### 各类常量 ######
    g.con_START_DATE = 100 # 股票上市时间限制
    g.con_MARKET_CAP = 200 # 流通市值标准
    
    # 初始化当日买卖列表
    g.stock_buy = []
    g.stock_sell = []

    run_weekly(weekly23, 1, time='open')
    run_weekly(weekly23, 2, time='open')
    run_weekly(weekly23, 3, time='open')
    run_weekly(clean, 4, time='open')
    run_weekly(weekly23, 5, time='open')

    #run_daily(daily, time='open')

def clean(context):
   
    for stock in context.portfolio.positions.keys():
        order_target(stock, 0)
    weekly(context)
    log.info("定期清空")

# 开盘后止损止盈
def check_price(context, stock):
    price = context.portfolio.positions[stock].price
    avg_cost = context.portfolio.positions[stock].avg_cost
    
    if avg_cost  > price:
        return False
    else:
        return True
        
def weekly23(context):
    #if context.current_dt.isoweekday() <> 14:
    if len(context.portfolio.positions.keys()) <= 0:
       weekly(context)
       
def weekly(context):
    for stock in context.portfolio.positions.keys():
        order_target(stock, 0)

    cash = context.portfolio.cash
    log.info(g.stock_buy)
    for stock in g.stock_buy:
        order_value(stock, cash / len(g.stock_buy))

# 获得每天的数据
def get_stock_list(context):
    # 取得流通市值200亿以下的股票数据
    d_startdate = (context.current_dt  - timedelta(days = g.con_START_DATE)).strftime("%Y-%m-%d")
    
    q = query(
		valuation.code, valuation.circulating_cap
	).filter(
	    valuation.code.notin_(['002219.XSHE','000692.XSHE','002322.XSHE','600671.XSHG', '600297.XSHG']),
	    valuation.circulating_market_cap < g.con_MARKET_CAP
    )
    
    df = get_fundamentals(q, date = d_startdate)

    df.index = list(df['code'])

    # 去除ST，*ST
    st = get_extras('is_st', list(df['code']), start_date = g.d_today, end_date = g.d_today, df = True)
    st = st.iloc[0]
    stock_list = list(st[st == False].index)
    
    days = 29
    
    # 获得股票池数据
    df_list = get_price(stock_list, start_date=g.d_today, end_date=g.d_today, frequency='daily', fields=['open', 'close', 'high', 'low', 'paused', 'volume'])

    # 获取收盘价
    df_close = history(days, unit='1d', field='close', security_list = stock_list, skip_paused=True)
    df_close = df_close.append(df_list['close'])
    
    # 获取收盘价
    df_high = history(days, unit='1d', field='high', security_list = stock_list, skip_paused=True)
    df_high = df_high.append(df_list['high'])
    
    # 获取收盘价
    df_low = history(days, unit='1d', field='low', security_list = stock_list, skip_paused=True)
    df_low = df_low.append(df_list['low'])
    
    # 获取历史停牌
    df_paused_sum = history(days, unit='1d', field='paused', security_list = stock_list)
    df_paused_sum = df_paused_sum.append(df_list['paused'])
    df_paused_sum = pd.DataFrame(np.sum(df_paused_sum))
    df_paused_sum.columns = ['paused_sum']
    
    # 获取成交量
    df_volume = df_list['volume']
    df_volume = df_volume.T 
    
    for col in df_volume.columns:
        df_volume[col] = df_volume[col] / (df['circulating_cap'] * 100)
        
    df_volume.columns = ['volume']
    
    # 最高价的最高价
    df_high_h = pd.DataFrame(df_high.max())
    df_high_h.columns = ['high_h']
    
    # 最低价的最低价
    df_low_l = pd.DataFrame(df_low.min())
    df_low_l.columns = ['low_l']
    
    # 收盘价的最高价
    df_close_h = pd.DataFrame(df_high.max())
    df_close_h.columns = ['close_h']
    
    # 收盘价的最低价
    df_close_l = pd.DataFrame(df_close.min())
    df_close_l.columns = ['close_l']
    
    # 开始日收盘价
    df_start = df_close.head(1)
    df_start.index = ['start']
    df_start = df_start.T
    
    # 结束日收盘价
    df_end = df_close.tail(1)
    df_end.index = ['end']
    df_end = df_end.T
    
    # 获取停牌
    df_paused = df_list['paused'].T
    df_paused.columns = ['paused']
    
    df_result = pd.concat([df_start, df_end], axis = 1, join_axes = [df_start.index])
    df_result = pd.concat([df_result, df_paused], axis = 1, join_axes = [df_result.index])
    df_result = pd.concat([df_result, df_volume], axis = 1, join_axes = [df_result.index])
    df_result = pd.concat([df_result, df_high_h], axis = 1, join_axes = [df_result.index])
    df_result = pd.concat([df_result, df_low_l], axis = 1, join_axes = [df_result.index])
    df_result = pd.concat([df_result, df_close_h], axis = 1, join_axes = [df_result.index])
    df_result = pd.concat([df_result, df_close_l], axis = 1, join_axes = [df_result.index])
    
    df_result = df_result[df_result['paused'] == 0]

    df_result['usual_wave'] = (df_result['close_h'] - df_result['close_l']) / df_result['start']
    df_result['max_wave'] = (df_result['high_h'] - df_result['low_l']) / df_result['start']
    df_result['start_end'] = (df_result['end'] - df_result['start']) / df_result['start']
    
    df_result = df_result[df_result['usual_wave'] < 0.2]
    df_result = df_result[df_result['max_wave'] <= 0.22]
    #df_result['usual_wave'] = df_result['usual_wave'] / df_result['max_wave']
    df_result = df_result.sort(columns = 'usual_wave', ascending = False).tail(10)
    df_result = df_result.sort(columns = 'max_wave', ascending = False).head(3)
    df_result = df_result[df_result['start_end'] < df_result['usual_wave'] * 0.6]
    df_result = df_result[df_result['start_end'] > 0 - df_result['usual_wave'] * 0.6]
    
    log.info(df_result)
    g.stock_buy = set(list(g.stock_buy) + list(df_result.index))

# 检验沪深300的二十日线
def get_under_line():
    df_list = get_price([g.riskbench],start_date = g.d_today, end_date = g.d_today, frequency = 'daily', fields = ['close'])
    
    df_close = history(21, unit='1d', field='close', security_list=[g.riskbench])
    df_close = df_close.append(df_list['close'])
    
    df_MA22 = pd.DataFrame(df_close.tail(15).mean())
    df_MA22.columns = ['MA22']
    
    df_MA1 = df_list['close']
    df_MA1.columns = ['MA1']
    
    ma22 = 0

    record(MA1=df_MA1['MA1'][0])
    record(MA22=df_MA22['MA22'][0])
    
    if df_MA1['MA1'][0] < df_MA22['MA22'][0]:
        ma22 = 1
    
    return ma22 
    
# 每天交易前调用
def before_trading_start(context):
    # 昨天
    g.d_yesterday = (context.current_dt  - timedelta(days = 1)).strftime("%Y-%m-%d")
    
    # 今天
    g.d_today = (context.current_dt).strftime("%Y-%m-%d")
    
# 每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)调用一次
def handle_data(context, data):
    pass

# 每天交易后调用
def after_trading_end(context):
    g.stock_buy = []
    g.stock_sell = []
    
    if get_under_line() == 0:
        get_stock_list(context)
    else:
        g.stock_sell = list(context.portfolio.positions.keys())

    
