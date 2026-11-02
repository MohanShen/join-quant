# Clone from JoinQuant
# postId: 85f7d2afec92a3194a8809a46a217161
# backtestId: c8154ce7db870c23317a84abb6e8236b
# title: 期货成交价格问题，望大佬帮帮忙

import statsmodels.api as sm
from statsmodels import regression
import numpy as np
import pandas as pd
import time 
from datetime import date
from jqdata import *
import datetime
from dateutil.relativedelta import relativedelta
import json
from six import StringIO

def initialize(context):
    money = []
    set_benchmark('IH9999.CCFX')
    g.adjust_position_hour = 14
    g.adjust_position_minute = 50
    set_params()        #1设置策参数
    g.last_future = None
    init_cash = context.portfolio.starting_cash 
    set_option('use_real_price', True)
    set_subportfolios([SubPortfolioConfig(cash=init_cash, type='futures')])
    set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0, close_commission=0, close_today_commission=0, min_commission=0), type='index_futures')
    run_daily( while_open, time='every_bar', reference_security='IH9999.CCFX')
    

def set_params():
    g.moneytarget = 1000000
    g.renko = 1000000
    g.position = 0  
    g.future_index1 = 'IH'
    g.future_index2 = 'IC'
    g.pre_future=''#用来装上次进入的期货合约名字
    g.mark = ''
    g.future_index = ''
    g.gr_indexA = 0
    g.gr_index1 = 0
    g.gr_index2 = 0
    g.future1 = get_dominant_future(g.future_index1)
    g.future2 = get_dominant_future(g.future_index2)
    
def before_market_open(context):
      # 获取当月期货合约
    g.future = get_dominant_future(g.future_index)      
    g.future1 = get_dominant_future(g.future_index1)
    g.future2 = get_dominant_future(g.future_index2)
    
def while_open(context):     
    money = [context.portfolio.portfolio_value]
    record(price = context.portfolio.portfolio_value)
    hour = context.current_dt.hour
    minute = context.current_dt.minute
    
    if hour == g.adjust_position_hour and minute == g.adjust_position_minute:
        g.future1 = get_dominant_future(g.future_index1)
        g.future2 = get_dominant_future(g.future_index2)
    
        g.gr_index1 = get_growth_rate(g.future1)
        g.gr_index2 = get_growth_rate(g.future2)  
        
        if  g.gr_index1 > g.gr_index2:
            g.future_index = 'IH'
            g.gr_indexA = g.gr_index1
            g.target = 2
    
        if  g.gr_index2 > g.gr_index1:
            g.future_index = 'IC'
            g.gr_indexA = g.gr_index2
            g.target = 3
        
        g.future = get_dominant_future(g.future_index) 
        
        
        if g.last_future == None:
            g.last_future = g.future
        elif g.last_future != g.future:
            if g.position == 1:
                order_target(g.last_future,0,side='long')
                g.position = 0
            elif g.position == -1:
                order_target(g.last_future,0,side='long')
                g.position = 0
            g.last_future = g.future
            log.info("主力合约改变，平仓！")   
            print 'money:'
            print money
            print'------------------------------------------------------------------'
    
    if hour == 9 and minute == 05 :
        do_handle_data(context) 
    if hour == 9 and minute == 10 :
        do_handle_data(context) 
    if hour == 9 and minute == 15 :
        do_handle_data(context) 
    if hour == 9 and minute == 20 :
        do_handle_data(context) 
    if hour == 9 and minute == 25 :
        do_handle_data(context) 
    if hour == 9 and minute == 30 :
        do_handle_data(context) 
    if hour == 9 and minute == 35 :
        do_handle_data(context) 
    if hour == 9 and minute == 40 :
        do_handle_data(context) 
    if hour == 9 and minute == 45 :
        do_handle_data(context) 
    if hour == 9 and minute == 50 :
        do_handle_data(context) 
    if hour == 9 and minute == 55 :
        do_handle_data(context) 
    if hour == 10 and minute == 00 :
        do_handle_data(context)
    if hour == 10 and minute == 05 :
        do_handle_data(context)    
    if hour == 10 and minute == 10 :
        do_handle_data(context) 
    if hour == 10 and minute == 15 :
        do_handle_data(context) 
    if hour == 10 and minute == 20 :
        do_handle_data(context) 
    if hour == 10 and minute == 25 :
        do_handle_data(context) 
    if hour == 10 and minute == 30 :
        do_handle_data(context) 
    if hour == 10 and minute == 35 :
        do_handle_data(context) 
    if hour == 10 and minute == 40 :
        do_handle_data(context) 
    if hour == 10 and minute == 45 :
        do_handle_data(context) 
    if hour == 10 and minute == 50 :
        do_handle_data(context) 
    if hour == 10 and minute == 55 :
        do_handle_data(context)
    if hour == 11 and minute == 00 :
        do_handle_data(context)
    if hour == 11 and minute == 05 :
        do_handle_data(context)    
    if hour == 11 and minute == 10 :
        do_handle_data(context) 
    if hour == 11 and minute == 15 :
        do_handle_data(context) 
    if hour == 11 and minute == 20 :
        do_handle_data(context) 
    if hour == 11 and minute == 25 :
        do_handle_data(context) 
    if hour == 11 and minute == 30 :
        do_handle_data(context)     
    if hour == 13 and minute == 05 :
        do_handle_data(context)    
    if hour == 13 and minute == 10 :
        do_handle_data(context) 
    if hour == 13 and minute == 15 :
        do_handle_data(context) 
    if hour == 13 and minute == 20 :
        do_handle_data(context) 
    if hour == 13 and minute == 25 :
        do_handle_data(context) 
    if hour == 13 and minute == 30 :
        do_handle_data(context)     
    if hour == 13 and minute == 35 :
        do_handle_data(context) 
    if hour == 13 and minute == 40 :
        do_handle_data(context) 
    if hour == 13 and minute == 45 :
        do_handle_data(context) 
    if hour == 13 and minute == 50 :
        do_handle_data(context) 
    if hour == 13 and minute == 55 :
        do_handle_data(context) 
    if hour == 14 and minute == 00 :
        do_handle_data(context)
    if hour == 14 and minute == 05 :
        do_handle_data(context)    
    if hour == 14 and minute == 10 :
        do_handle_data(context) 
    if hour == 14 and minute == 15 :
        do_handle_data(context) 
    if hour == 14 and minute == 20 :
        do_handle_data(context) 
    if hour == 14 and minute == 25 :
        do_handle_data(context) 
    if hour == 14 and minute == 30 :
        do_handle_data(context)     
    if hour == 14 and minute == 35 :
        do_handle_data(context) 
    if hour == 14 and minute == 40 :
        do_handle_data(context) 
    if hour == 14 and minute == 45 :
        do_handle_data(context) 
    if hour == 14 and minute == 50 :
        do_handle_data(context) 
    if hour == 14 and minute == 55 :
        do_handle_data(context) 
    if hour == 14 and minute == 59 :
        do_handle_data(context)    
        
        
def do_handle_data(context):        
    '''global g.future_index
    global gr_indexB
    global target
    
    gr_index3 = get_growth_rate1(g.future1)
    gr_index4 = get_growth_rate1(g.future2)'''
    
    if g.gr_indexA == g.gr_index1 :
        g.gr_indexB = get_growth_rate1(g.future1)
        
    if g.gr_indexA == g.gr_index2 :
        g.gr_indexB = get_growth_rate1(g.future2)
    
   
    if g.gr_indexA < 0.01:
        if g.position == 1:
                order_target(g.future,0,side='long', pindex=0)
                print '日平仓'    
                g.position = 0
                
                
    if g.gr_indexB < 0:
        if g.position == 1:
                order_target(g.future,0,side='long', pindex=0)
                print '5分平仓'  
                g.position = 0            
    
    
    if g.gr_indexA > 0.01 and g.gr_indexB > 0:
        if g.position != 1:
            order(g.future,g.target, side='long', pindex=0)
            if context.portfolio.positions[g.future].total_amount > 0:
                g.position = 1
                print '开多'
                print 'g.position',g.position
    
    
    
    

def get_growth_rate(security, n=20):
    lc = get_close_price(security, n)
    c = get_close_price(security, 1, '1m')
    
    if not isnan(lc) and not isnan(c) and lc != 0:
        return (c - lc) / lc
    else:
        '''log.error("数据非法, security: %s, %d日收盘价: %f, 当前价: %f" %(security, n, lc, c))'''
        return 0

def get_close_price(security, n, unit='1d'):
    return attribute_history(security, n, unit, ('close'), True)['close'][0]    
    
    
def get_growth_rate1(security, n=20):
    lc = get_close_price1(security, n)
    c = get_close_price1(security, 1, '1m')
    
    if not isnan(lc) and not isnan(c) and lc != 0:
        return (c - lc) / lc
    else:
        '''log.error("数据非法, security: %s, %d日收盘价: %f, 当前价: %f" %(security, n, lc, c))'''
        return 0   
    
def get_close_price1(security, n, unit='5m'):
    return attribute_history(security, n, unit, ('close'), True)['close'][0]     
    
    
    
    
    