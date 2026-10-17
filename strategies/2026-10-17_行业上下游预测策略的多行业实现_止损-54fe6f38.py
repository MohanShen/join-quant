# Clone from JoinQuant
# postId: 54fe6f38a242b0e0c9198c7dd4bd6e7c
# backtestId: 26a4b5b9029890571eb9174f53135bd7
# title: 行业上下游预测策略的多行业实现+止损

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
    # set_bg()
    # Define and obtain global background data like trading dates series
    set_backtest()
    # Set options for backtesting

def set_params():

# To be adjusted   
    g.N = 2 # g.N also serves as iteration limit
    g.t1 = [3,3]#*g.N
    g.t2 = [5,5]#*g.N
    g.lag = [0,12]#*g.N
    # estimated lag period for price impact transfered from indicator to portfolio 
    g.num = [5,5]#*g.N
    g.indi_index = ['502024.XSHG','399231.XSHE']#,'000820.XSHG']
    g.ptf_index = ['399235.XSHE','399652.XSHE']#,'000811.XSHG']
    g.suspendate_start = [1121,1124]#*g.N
    g.suspendate_end = [1121,1124]#*g.N
    g.indi_win = [1.001,1.05]#*g.N
    g.indi_lose = [0.98,0.98]#*g.N
    g.vol_ratio = [1.01,1.4]#*g.N
    g.ptf_trend_lose = [0.9,0.8]#*g.N #judge on ptf_index
    g.ptf_individual_lose = [0.9,0.9]#*g.N # 0 means do no indivual stop in loss
    g.blacklist = {}
    # used to define when vol is out of range
# End of Adjustment    
    g.if_trade = False #* g.N
    g.industry_stopped = [0] * g.N
    g.value_record = [0,0,0]
    g.t = 2 # days traded
    g.tf = 1 #trading frequency  
    
 
    # number of stocks invested each time  
    g.tradeDaySeries = get_all_trade_days()
 

    
def if_stop_loss(stk,t1,t2,lose_signal):
    df_trail = attribute_history(security = stk, count = t2, unit = '1d', fields = ['close'])['close']
    MA_long = sum(df_trail[t2-t1:t2])/t1
    MA_short = sum(df_trail[0:t2])/t2
    if MA_short < MA_long *lose_signal:
        return True
    else:
        return False
   
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
#        g.stockPool = set_feasible_stocks(get_index_stocks(g.ptf_index),g.t2,context)

# suspend trading for specific industry during 'start' to 'end' period
def if_suspendate(context,start,end):
    #return False
    mon_start = int(start/100)  
    mon_end = int(end/100) 
    dat_start = start % 100
    dat_end = end % 100

    if start > end:
        skip_year = True
    else:
        skip_year = False

    if skip_year:
        if(context.current_dt > datetime.datetime(context.current_dt.year,mon_start,dat_start) or context.current_dt < datetime.datetime(context.current_dt.year,mon_end,dat_end)):
            return True
        else:
            return False
    else:
        if(context.current_dt > datetime.datetime(context.current_dt.year,mon_start,dat_start) and context.current_dt < datetime.datetime(context.current_dt.year,mon_end,dat_end)):
            return True
        else:
            return False    
    


# Filter paused stocks given stock pool and tracing period
# Input: stk_pl - list of stocks(id), tp - periods to examine (note: not the global param g.tp, though most times we input g.tp as tp)
# Return: list of stocks(id)
def set_feasible_stocks(stk_pl, tp, context):
    susInfo_df = get_price(security = stk_pl, start_date = context.current_dt, end_date = context.current_dt, frequency = '1d', fields = 'paused', skip_paused = False)['paused'].T
    tradable_pool = susInfo_df[susInfo_df.iloc[:,0] < 1].index

    feasible_pool = []
    for stk in tradable_pool:
        if sum(attribute_history(security = stk, count = tp, unit = '1d', fields = 'paused', skip_paused = False,df = True)['paused']) == 0:
            feasible_pool.append(stk) 
    return feasible_pool

'''
=====
'''

def roll_blacklist(blacklist):
    for stk in blacklist.keys():
        blacklist[stk] += 1
        if blacklist[stk] >= 9:
            del blacklist[stk]
        

def handle_data(context, data):
    roll_blacklist(g.blacklist)
    g.value_record.append(context.portfolio.total_value)
    if g.if_trade == True:    

        
        trade_sell_list = []
        df_ptf = pd.DataFrame(columns = ['code','market_cap'])
        #df_ptf.set_index(['code'])
        count = 0

        for i in range(0,g.N):
            current_pool = []
            g.tp = 0
            mom_flag = 0
            g.tp = g.t2[i]+g.lag[i]+1 
            a = []
            a = get_index_stocks(g.ptf_index[i])
            if if_suspendate(context,g.suspendate_start[i],g.suspendate_end[i]) :
                print context.portfolio.positions.keys()
                trade_sell_list += a
            else:
                if g.industry_stopped[i] > 0:
                    g.industry_stopped[i] -= 1;
                if if_stop_loss(g.ptf_index[i],5,20,g.ptf_trend_lose[i])or (g.value_record[g.t]<0.95*g.value_record[g.t-1] and g.value_record[g.t-1]<0.95*g.value_record[g.t-2])or(g.value_record[g.t]<0.85*g.value_record[g.t-1]):
                    if g.industry_stopped[i] == 0:
                        g.industry_stopped[i] = 3
    
                if g.industry_stopped[i]:
                    trade_sell_list += a
                 
                    #for stk in get_index_stocks(g.ptf_index[i],context.current_dt):
                    #    print stk
                    #    order_target_value(stk, 0)
                else:
                    current_pool = set_feasible_stocks(a,g.tp,context)
                    for stk in current_pool:
                        if if_stop_loss(stk,5,20,g.ptf_individual_lose[i]):
                            if stk not in g.blacklist.keys():
                                g.blacklist[stk] = 0
                    for stk in g.blacklist:
                        if stk in current_pool:
                            current_pool.remove(stk)
                    mom_flag = get_flag(context,g.indi_index[i],g.t1[i], g.t2[i], g.tp, g.lag[i],g.indi_win[i],g.indi_lose[i],g.vol_ratio[i])
                    print mom_flag
                    if mom_flag == 0:
                        pass
                    elif mom_flag == -1:
                        trade_sell_list += current_pool
                    else:
                        # 在可以买入的前提下，按照市值加权买入各个股票
                        
                        g.q = query(valuation.code, valuation.market_cap).filter(valuation.code.in_(current_pool))
                        df_raw = get_fundamentals(g.q, date = context.current_dt)
                        
                        df_tmp = df_raw.sort('market_cap')[0:g.num[i]]
                        df_tmp = df_tmp.set_index(['code'])
                        if count == 0:
                            df_ptf = df_ptf.set_index(['code'])
                            count += 1
                        #df_tmp = df_tmp.set_index(['code'])
                        df_ptf = pd.concat([df_ptf,df_tmp])
                    
               
        if (len(df_ptf) != 0) or (len(trade_sell_list)!=0):
           #df_ptf.reset_index(drop = True)

           df_ptf = pd.DataFrame(df_ptf,columns = ['code','market_cap'])
           #df_ptf.set_index(['code'])
           do_trade(context,df_ptf,trade_sell_list)
    g.if_trade = False            

#def 


# do_trade: should input a dataframe with stock code & mkt_cap     
def do_trade(context,df_portfolio,trade_sell_list):
    if len(df_portfolio !=0):
        cumcap = sum(df_portfolio['market_cap'])
        df_portfolio['market_cap'] = df_portfolio['market_cap']/cumcap
        totalAsset = context.portfolio.total_value
        df_portfolio['tradeVal'] = totalAsset * df_portfolio['market_cap']
        #print df_ptf
        #print context.portfolio.positions.keys()
    for stk in trade_sell_list:
        order_target_value(stk,0)
    for stk in context.portfolio.positions.keys():
        if (stk not in df_portfolio.index) and if_stop_loss(stk,5,20,0.95):
            order_target_value(stk,0)
        
    #Deal with changed components of index

    if len(df_portfolio) !=0:    
        for stk in context.portfolio.positions.keys():
            if stk not in df_portfolio.index:
                order_target_value(stk,0)
        
    # Whether or not sell the stocks currently neither in sell_list nor in buy_list
        for stk in df_portfolio.index:
            a = df_portfolio.loc[stk,['tradeVal']]
            if len(a)!= 1:
                a = a.iloc[0,0]

            order_target_value(stk,a)
        

def get_flag(context, indi_index, t1, t2, tp, lag,win,lose,vol_ratio):
    df_indicator = attribute_history(security = indi_index, count = tp + lag, unit = '1d', fields = ['close'])['close']
    MA_t1 = sum(df_indicator[tp - t1  : tp + 1])/t1
    Var_t1 = np.var(df_indicator[tp  - t1 :tp + 1])
    MA_t2 = sum(df_indicator[tp - t2 : tp + 1])/t2
    Var_t2 = np.var(df_indicator[tp - t2 :tp + 1])
    #print df_indicator
    print MA_t1, MA_t2
    if (MA_t1 > win * MA_t2) and (Var_t1 > vol_ratio * Var_t2*t1/t2):
        return 1
    elif MA_t1 < lose * MA_t2:
        return -1
    else:
        return 0

