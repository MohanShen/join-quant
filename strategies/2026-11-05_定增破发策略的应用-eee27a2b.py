# Clone from JoinQuant
# postId: eee27a2bf9c4b805496cae642a40e19b
# backtestId: d1fdb291d1982144b275b1b30bc5a134
# title: 定增破发策略的应用

import statsmodels.api as sm
from statsmodels import regression
import numpy as np
import pandas as pd
import time
from datetime import date
from jqdata import *
import datetime

#之后可以转变思路，不一定要达到发行价，只要有上涨即可


def initialize(context):
    set_params()
    set_backtest()
    
def set_params():
    g.if_trade = False
    g.tf = 1  
    g.t = 0 # record total trading length
    g.hold_list = {} #record any stock whose SEO px is lower than curr.px, ticker as keys(), SEO px as values()
    # would maintain holding unless lower than SEO price
    g.deferred_list = []
    # to avoid delayed trading
    g.tolerance_level = 1
    g.critical_px = {}# record the close price at that critical SEO date

def set_backtest():
    set_benchmark('000300.XSHG')
    set_option('use_real_price',True)
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


def handle_data(context,data):
    todaystr = context.current_dt.strftime("%Y-%m-%d")
    sell_list = []
    new_tmp = {}
    
    for dstk in g.deferred_list:
        order_target_value(dstk,0)
        if context.portfolio.positions[dstk].total_amount == 0:
            g.deferred_list.remove(dstk)
    print str(context.current_dt.date)
    df_tmp = gta.run_query(query(gta.STK_EQ_SEO_PRIVATE.SYMBOL, 
                        gta.STK_EQ_SEO_PRIVATE.DECLAREDATE,
                        gta.STK_EQ_SEO_PRIVATE.PRICE,
                        ).filter(gta.STK_EQ_SEO_PRIVATE.DECLAREDATE == todaystr))
    if not df_tmp.empty:
        print df_tmp
        
        for i in range(0,len(df_tmp)):
            
            new_tmp[ticker_trans(df_tmp.iloc[i,:].SYMBOL)] = df_tmp.iloc[i,:].PRICE
        for nstk in new_tmp.keys():
            if judge_lower(context,nstk,new_tmp,0.95*g.tolerance_level) and (not judge_lower(context,nstk,new_tmp,0.4*g.tolerance_level)):
            # 回测中发现[晨鸣纸业]发行的价格与真实股价相差很大，发现其实是优先股，所以以定增价的0.4倍判断是否是同一类股票
                g.hold_list[nstk] = new_tmp[nstk]
                g.critical_px[nstk] = attribute_history(nstk, 1, unit = '1d', fields = ['close'])['close'].values[0]
            else:
                del new_tmp[nstk]
    
    
    '''
    if not df_tmp.empty:
        # print a['DECLAREDATE'].values[0] == '2010-03-16' # used for check
        for i in range(0,len(df_tmp)):
            
            g.hold_list[ticker_trans(df_tmp.iloc[i,:].SYMBOL)] = df_tmp.iloc[i,:].PRICE
    print '目前的拟持仓选择是',g.hold_list # used for check
    '''
    for stk in g.hold_list.keys():
        if judge_lower(context,stk,g.critical_px,1.2*g.tolerance_level) and judge_lower(context,stk,g.hold_list,0.99*g.tolerance_level): #发布定增是利好，在升高到一定程度时候卖出
            pass
        else:
            del g.hold_list[stk]
            del g.critical_px[stk]
            sell_list.append(stk)
    for sstk in sell_list:
        order_target_value(stk,0)
        if context.portfolio.positions[sstk].total_amount != 0:
            g.deferred_list.append(sstk)
    if len(g.hold_list) != 0:
        total_cap = context.portfolio.total_value
        individual_cap = total_cap/len(g.hold_list)
        for bstk in g.hold_list.keys():
            order_target(bstk, individual_cap)

    print g.hold_list
    g.if_trade = False

def ticker_trans(_gta_ticker):
    print _gta_ticker
    if _gta_ticker[0] == '6' or _gta_ticker[0] == '5':
        tmp = '.XSHG' 
    elif str(_gta_ticker[0]) == '3' or _gta_ticker[0] == '0'or _gta_ticker[0] == '9':
        tmp = '.XSHE'
    return _gta_ticker + tmp

def judge_lower(context,stk,hold_list,tlr_lvl):
    print '目前进行比价',stk
    #todaystr = context.current_dt.strftime("%Y-%m-%d")
    df_curr_px = attribute_history(stk, 1, unit='1d', fields=['close'], skip_paused=True, df=True, fq='pre')
    print df_curr_px['close'].values[0]
    print hold_list[stk]
    if not df_curr_px.empty:
        if float(df_curr_px['close'].values[0]) < float(hold_list[stk]) * tlr_lvl:
            print '找到一个', stk
            return True
    return False