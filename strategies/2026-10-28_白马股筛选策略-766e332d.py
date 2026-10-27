# Clone from JoinQuant
# postId: 766e332da1a04fb586f3b65bbf4d8e5f
# backtestId: 2ed50e6589377c85d3b187385c299e4d
# title: 白马股筛选策略

import statsmodels.api as sm
import numpy as np
import matplotlib.pyplot as plt
import time 
import pandas as pd
from datetime import date
from jqdata import *

def initialize (context):
    # 设置参数
    set_params()
    # 设置回测
    set_backtest()
    # 初始化输赢统计
    run_daily(trade, 'every_bar')

def set_params():
    g.days=0
    g.refresh_rate=9
    g.stocknum=3
    
def set_backtest():
    # 设置回测基准
    set_benchmark('000300.XSHG')
    # 使用真实价格
    set_option('use_real_price', True)
    # 设置报错
    log.set_level('order', 'error')
    
    
def trade(context):
    if g.days%g.refresh_rate == 0:
        df = get_fundamentals(query(
        valuation.code, valuation.pe_ratio, valuation.market_cap, indicator.eps, indicator.inc_return, indicator.inc_net_profit_annual
    ).filter(
        valuation.pe_ratio < 40,
        valuation.pe_ratio > 35,
        indicator.eps > 0.3,
        indicator.inc_net_profit_annual > 0.30,
        indicator.roe > 0.20
    ).order_by(
        # 按市值升序排列
        indicator.roe.desc()
    ).limit(
        # 最多返回100个
        100), date=None)
        mylist = pd.DataFrame(columns = ('code','order'))
        i=0
  
        for stock in df['code']:
            mylist=mylist.set_value(len(mylist),['code','order'],[stock,i])
            i=i+1
        stocksort=mylist.sort('order')['code'] 
        ## 获取持仓列表
        sell_list = list(context.portfolio.positions.keys())
        for stock in sell_list:
            if stock not in stocksort[:g.stocknum]:
                stock_sell = stock
                order_target_value(stock_sell, 0) 
                
            ## 分配资金
        if len(context.portfolio.positions) < g.stocknum :
            Num = g.stocknum - len(context.portfolio.positions)
            Cash = context.portfolio.cash/Num
        else: 
            Cash = 0
        
        ## 买入股票
        for stock in stocksort[:g.stocknum]:
            stock_buy = stock
            order_target_value(stock_buy, Cash)
        
        # 天计数加一
        g.days = 1
    else:
        g.days += 1

# 过滤停牌股票
def filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]

    
def before_trading_start(context):
    # 设置手续费和滑点
    set_slip_fee(context)

# ---代码块8
# 根据不同的时间段设置滑点与手续费
def set_slip_fee(context):
    # 将滑点设置为0)
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
