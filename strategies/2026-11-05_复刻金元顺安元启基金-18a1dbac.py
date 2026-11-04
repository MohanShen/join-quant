# Clone from JoinQuant
# postId: 18a1dbac3d2151cd4f2a169389bad14e
# backtestId: e37818f985d13fbeb42c412fac91134c
# title: 复刻金元顺安元启基金。

from jqdata import *
from jqfactor import *
import numpy as np
import pandas as pd

def initialize(context):
    set_benchmark('399303.XSHE') 
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_slippage(FixedSlippage(0.002))
    
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.00015, close_commission=0.00015, close_today_commission=0, min_commission=5), type='stock')
    log.set_level('order', 'error')
    
    g.stock_num = 80 
    g.hold_days = 10 
    g.days_counter = 0
    g.pass_months = [1] 
    
    run_daily(trade_logic, '09:30')

def trade_logic(context):
    current_month = context.current_dt.month
    
    if current_month in g.pass_months:
        if len(context.portfolio.positions) > 0:
            for stock in list(context.portfolio.positions.keys()):
                order_target_value(stock, 0)
            log.info("进入一月空仓期，已清空所有持仓")
        return
        
    g.days_counter += 1
    
    if g.days_counter < g.hold_days and len(context.portfolio.positions) > 0:
        return
        
    g.days_counter = 0
    
    target_list = get_yuanqi_pool(context)
    log.info(f"本次选出 {len(target_list)} 只符合元启逻辑的微盘股")
    
    for stock in list(context.portfolio.positions.keys()):
        if stock not in target_list:
            order_target_value(stock, 0)
            
    if len(target_list) > 0:
        value_per_stock = context.portfolio.total_value / len(target_list)
        for stock in target_list:
            order_target_value(stock, value_per_stock)

def get_yuanqi_pool(context):
    current_data = get_current_data()
    all_stocks = list(get_all_securities(['stock']).index)
    
    valid_stocks = []
    for s in all_stocks:
        if not current_data[s].is_st and not current_data[s].paused and '退' not in current_data[s].name:
            if (context.current_dt.date() - get_security_info(s).start_date).days > 365:
                valid_stocks.append(s)
                
    q = query(
        valuation.code
    ).filter(
        valuation.code.in_(valid_stocks),
        income.net_profit > 0 
    ).order_by(
        valuation.market_cap.asc() 
    ).limit(g.stock_num * 2) 
    
    df = get_fundamentals(q)
    if len(df) == 0:
        return []
        
    candidate_list = list(df['code'])
    
    prices = history(20, '1d', 'close', candidate_list)
    ret_20d = (prices.iloc[-1] - prices.iloc[0]) / prices.iloc[0]
    
    target_stocks = ret_20d.sort_values(ascending=True).head(g.stock_num).index.tolist()
    
    return target_stocks