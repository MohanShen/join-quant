# Clone from JoinQuant
# postId: a92001a64353c1f7891680b8f30a5f0f
# backtestId: 7861123023f826993761c8660d4f0161
# title: OLS回归的量化之旅Chapter 2

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
    g.recent=5
    g.his=30
    g.refresh_rate=5
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
        valuation.code, valuation.market_cap, valuation.pe_ratio, income.total_operating_revenue
    ).filter(
        valuation.market_cap > 1000,
        valuation.pe_ratio < 15,
        income.total_operating_revenue > 200
    ).order_by(
        # 按pe_ratio降序排列
        valuation.pe_ratio.desc()
    ).limit(
        # 最多返回100个
        100
    ), date=None)
        print df

        scores = pd.DataFrame(columns = ('code','score'))
        for stock in df['code']:
            result=OLS(stock)
            scores=scores.set_value(len(scores),['code','score'],[stock,result])
        stock_sort=scores.sort('score')['code']
        
        ## 获取持仓列表
        sell_list = list(context.portfolio.positions.keys())
        for stock in sell_list:
            if stock not in stock_sort[:(g.stocknum+2)]:
                stock_sell = stock
                order_target_value(stock_sell, 0) 
            
        ## 分配资金
        if len(context.portfolio.positions) < g.stocknum :
            Num = g.stocknum - len(context.portfolio.positions)
            Cash = context.portfolio.cash/g.stocknum
        else: 
            Cash = 0
        
        ## 买入股票
        for stock in stock_sort:
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


def OLS(security):
    nsample1=g.recent
    nsample2=g.his
 
    close_data = attribute_history(security, nsample2+2, '1d', ['close'],df=False)
    y1 = close_data['close'][-nsample1:]
    y2 = close_data['close'][-nsample2:]
 
    x1 = np.linspace(1, nsample1, nsample1)
    x2 = np.linspace(1, nsample2, nsample2)
 
    X1 = sm.add_constant(x1)
    X2 = sm.add_constant(x2)

    result1 = sm.OLS(y1, X1).fit()
    result2 = sm.OLS(y2, X2).fit()

    c1=result1.params[1]
    c2=result2.params[1]
    
    if (c2>1)or(c2<-1):
        result=c1/c2
    else:
        result=c1-c2
    return result
        
    
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
