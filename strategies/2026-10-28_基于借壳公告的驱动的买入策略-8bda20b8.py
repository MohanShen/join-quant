# Clone from JoinQuant
# postId: 8bda20b846dbc42b41f4ed82edde4d49
# backtestId: 3792088cb096de51b50e8e538d9587f2
# title: 基于借壳公告的驱动的买入策略

import statsmodels.api as sm
from statsmodels import regression
import numpy as np
import pandas as pd
import time
from datetime import date
from jqdata import *
import datetime


def initialize(context):
    set_params()
    # Define global variables
    # Define and obtain global background data like trading dates series
    set_backtest()
    # Set options for backtesting
    df = gta.run_query(query(gta.BD_DATEINFO.SYMBOL,gta.BD_DATEINFO.SHORTNAME, gta.BD_DATEINFO.STARTDATE, gta.BD_DATEINFO.ENDDATE).filter(gta.BD_DATEINFO.LISTSIGN ==2).order_by(gta.BD_DATEINFO.STARTDATE.asc()))

    
def set_params():
    g.if_trade  = False
    g.t = 0  
    g.tf = 1  
    g.hold_list = {}
    g.deferred_list = []
    #利用一个字典存储（需要考虑停牌的问题，借壳之后不一定能马上买入，不能的就存在这里。然后字典里的value每个交易日-1，用来决定持仓多久。）
    
    
def set_backtest():
    set_benchmark('000300.XSHG') 
    set_option('use_real_price', True)
    log.set_level('order','error')
    
    
    

def set_slip_fee(context):
    # 将滑点设置为0
    set_slippage(FixedSlippage(0)) 
    # 根据不同的时间段设置手续费
    dt=context.current_dt
    log.info(type(context.current_dt))
   
    if dt>datetime.datetime(2013,1, 1):
        set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5)) 
    elif dt>datetime.datetime(2011,1, 1):
        set_commission(PerTrade(buy_cost=0.001, sell_cost=0.002, min_cost=5))
    elif dt>datetime.datetime(2009,1, 1):
        set_commission(PerTrade(buy_cost=0.002, sell_cost=0.003, min_cost=5))
    else:
        set_commission(PerTrade(buy_cost=0.003, sell_cost=0.004, min_cost=5))

'''
=====
'''
def before_trading_start(context):
    g.t += 1
    if g.t % g.tf == 0:
            g.if_trade = True
            set_slip_fee(context)
    

def handle_data(context, data):
    if g.if_trade == True:
        #寻找借壳上市股票，10个交易日持仓之后卖出
        #首先找到今天的日期

        todaystr = context.current_dt.strftime("%Y-%m-%d")
        #然后用gta.query语句找到对应于今天的那个壳（可能没有）
        df_tmp = gta.run_query(query(gta.BD_DATEINFO.SYMBOL,gta.BD_DATEINFO.SHORTNAME, gta.BD_DATEINFO.STARTDATE, gta.BD_DATEINFO.ENDDATE).filter(gta.BD_DATEINFO.LISTSIGN == 2, gta.BD_DATEINFO.STARTDATE == todaystr).order_by(gta.BD_DATEINFO.STARTDATE.asc()))
        if len(df_tmp) != 0:
            for i in range(0,len(df_tmp)):
                gta_ticker = df_tmp['SYMBOL'].values[i]
              
                if gta_ticker[0] != '9' and gta_ticker[0] != '2' and df_tmp['SHORTNAME'].values[i][0:3]!='*ST': #聚宽不支持B股
                    normal_ticker = ticker_trans(gta_ticker)  
                    q = query(valuation.code, valuation.pb_ratio, valuation.market_cap,valuation.pe_ratio).filter(valuation.pb_ratio < 40,valuation.market_cap >2,valuation.market_cap < 100,valuation.pe_ratio > 50,valuation.code.in_([normal_ticker]))
                    tmp = get_fundamentals(q, context.current_dt.strftime('%Y-%m-%d'))
                    #print df_tmp['SHORTNAME'].values[i]
                    if len(tmp) !=0:    
                        print tmp
                        g.hold_list[normal_ticker] = 10
                        print 'holdlist',g.hold_list
                    
                #print todaystr, df_tmp
                #print df_tmp['SYMBOL'].values[0]
                #print (df_tmp['SYMBOL'].values[0] == '600233')
            
        
        #    hold_list = list(g.hold_list.keys())
        #trade_long(hold_list)
        #trade_sell(hold_list)
        do_trade(g.hold_list,context)
        roll_holding(g.hold_list,context)
    g.if_trade = False

def ticker_trans(_gta_ticker):
    print _gta_ticker
    if _gta_ticker[0] == '6' or _gta_ticker[0] == '5':
        tmp = '.XSHG' 
    elif str(_gta_ticker[0]) == '3' or _gta_ticker[0] == '0'or _gta_ticker[0] == '9':
        tmp = '.XSHE'
    return _gta_ticker + tmp
    

def roll_holding(hold_list,context):
    for stk in g.deferred_list:
        order_target_value(stk,0)
    for stk in hold_list.keys():
            hold_list[stk] -= 1 
            if hold_list[stk] <= 0:
                order_target_value(stk,0)
                if context.portfolio.positions[stk].total_amount > 0:
                    g.deferred_list.append(stk)
                del hold_list[stk]

def do_trade(hold_list,context):
    if len(hold_list) !=0:
        num = len(hold_list)  
        capital_amount = context.portfolio.total_value
        order_target_value('000012.XSHG',0)
        individual_amount = capital_amount / num
        for stk in hold_list.keys():
            order_target_value(stk,individual_amount)
    else: 
        order_target_value('000012.XSHG',context.portfolio.total_value)