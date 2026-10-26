# Clone from JoinQuant
# postId: 33fdc588089b8f6bfb3b0b700cf3c480
# backtestId: 1ebad33070cd2696fc073e22ca79df2b
# title: 壹章｜量化交易：盈利性因子分析

from jqdata import jy 
import talib
import numpy as np 
import pandas as pd  
import datetime
import time

def initialize(context):
    set_params()
    set_variables()
    set_backtest()
def set_params():
    g.tc = 240
    g.days=120
    g.N = 20
def set_variables():
    g.t = 0 
    g.if_trade =False
def set_backtest():
    set_slippage(PriceRelatedSlippage(0.002))
    set_benchmark('000300.XSHG')
    set_option('use_real_price',True)
    log.set_level('order','error')
def before_trading_start(context):
    if g.t%g.tc == 0:
        g.if_trade = True
        set_slip_fee(context)
    g.t +=1  
def set_feasible_stocks(stock_list,days,context):
    suspened_info_df = get_price(list(stock_list),start_date = context.current_dt,end_date = context.current_dt,frequency = 'daily',fields = 'paused')['paused'].T 
    unsuspened_index = suspened_info_df.iloc[:,0] < 1  
    unsuspened_stocks = suspened_info_df[unsuspened_index].index
    feasible_stocks = []
    current_data = get_current_data()
    for stock in unsuspened_stocks:
        if sum(sttribute_history(stock,days,unit = '1d',fields=('paused'),skip_paused = False))[0] == 0:
            feasible_stocks.append(stock)
    return feasible_stocks
def set_slip_fee(context):
    set_slippage(FixedSlippage(0))
    dt = context.current_dt
    if dt > datetime.datetime(2013,1,1):
        set_commission(PerTrade(buy_cost = 0.0003,sell_cost = 0.0013,min_cost = 5))
    elif dt > datetime.datetime(2011,1,1):
        set_commission(PerTrade(buy_cost = 0.001,sell_cost = 0.002,min_cost = 5))
    elif dt > datetime.datetime(2009,1,1):
        set_commission(PerTrade(buy_cost = 0.002,sell_cost = 0.003,min_cost = 5))
    else:
        set_commission(PerTrade(buy_cost = 0.003,sell_cost = 0.004,min_cost = 5))
def filter_stock_ST(stock_list):
    curr_data = get_current_data()
    for stock in stock_list:
        if (curr_data[stock].paused) or (curr_data[stock].is_st) or ('ST' in curr_data[stock].name) \
            or ('*' in curr_data[stock].name) \
            or ('退' in curr_data[stock].name):
                stock_list.remove(stock)
    return stock_list
def filter_stock_limit(stock_list):
    curr_data =get_current_data()
    for stock in stock_list:
        price =curr_data[stock].day_open
        if (curr_data[stock].high_limit <= price) or (price <= curr_data[stock].low_limit):
            stock_list.remove(stock)
    return stock_list
def remove_new_stocks(security_list,context):
    for stock in security_list:
        days_public = (context.current_dt.date() - get_security_info(stock).start_date).days
        if days_public < 720:
            security_list.remove(stock)
    return security_list
    
#每日交易时 

def getStockPrice(stock,interval):
    h = attribute_history(stock,inter,interval,unit = '1d',fields = ('close'),skip_paused = True)
    return (h['close'].values[0],h['close'].values[-1])
    
def handle_data(context,data):
    if g.if_trade ==True:
        currenttime = int(str(context.current_dt)[0:4] + str(context.current_dt)[5:7] + str(context.current_dt)[8:10])
        #log.info(currenttime)
        currenttime1 = int(str(context.current_dt)[0:4])-1
        sample = get_all_securities('stock',date = None)
        sample = list(sample.index)
        sample = filter_stock_ST(sample)
        sample = remove_new_stocks(sample,context)
        sample = filter_stock_limit(sample)
        #log.info(sample)
        #sample =get_index_stocks('000001.XSHG',date = None)
        #log.info(sample)
        q = query(valuation.code,valuation.market_cap,
                    valuation.pe_ratio,valuation.pb_ratio,
                    income.net_profit,
                    income.financial_expense,
                    income.income_tax_expense,
                    income.fair_value_variable_income,
                    income.investment_income,
                    balance.total_owner_equities,
                    balance.shortterm_loan,
                    balance.non_current_liability_in_one_year,
                    balance.longterm_loan,
                    balance.bonds_payable,
                    balance.longterm_account_payable
                    ).filter(
                    valuation.market_cap > 100,
                    income.net_profit > 0,
                    valuation.pe_ratio > 0,
                    valuation.pe_ratio < 100,
                    indicator.roa >0,
                    indicator.roe >0,
                    indicator.gross_profit_margin > 0,
                    indicator.net_profit_margin  > 0,
                    )
        fundamentals_df =get_fundamentals(q , date =None,statDate =currenttime1)
        ROIC_df = fundamentals_df.fillna(value=0)
        ROIC_df['EBIT'] = ROIC_df.net_profit+ROIC_df.financial_expense+ROIC_df.income_tax_expense-ROIC_df.fair_value_variable_income-ROIC_df.investment_income
        ROIC_df['IC'] = ROIC_df.total_owner_equities+ROIC_df.shortterm_loan+ROIC_df.non_current_liability_in_one_year+ROIC_df.longterm_loan+ROIC_df.bonds_payable+ROIC_df.longterm_account_payable
        ROIC_df['ROIC'] = ROIC_df.EBIT*0.75/ROIC_df.IC
        ROIC_df = ROIC_df.loc[:,['code','market_cap','ROIC']]
        ROIC_df = ROIC_df.sort_values(by=['ROIC'], ascending=False)
        #log.info(ROIC_df)
        g.Total_N =int( len(ROIC_df) / g.N)
        ROIC_df_N = ROIC_df.iloc[0:g.Total_N,:]
        log.info(len(ROIC_df_N))
        ROIC = ROIC_df_N['ROIC']
        ROIC_ver = ROIC.mean()
        log.info(ROIC_ver)
        ROIC_MC = ROIC_df_N['market_cap']
        ROIC_MC_ver =ROIC_MC.mean()
        log.info(ROIC_MC_ver)
        order_list = list(ROIC_df_N.code)
        log.info(order_list)
        if len(order_list) > 0 :
            order_stock_sell(context,order_list)
            order_stock_buy(context,order_list)
        
    g.if_trade =False
    
def order_stock_sell(context,order_list):
    for stock in context.portfolio.positions:
        if stock not in order_list:
            order_target_value(stock,0) 

def order_stock_buy(context,order_list):
    print (len(context.portfolio.positions))
    if len(context.portfolio.positions)< g.Total_N:
        num = g.Total_N - len(context.portfolio.positions)
        g.each_stock_cash = context.portfolio.available_cash / num 
    else:
        cash = 0  
        num = 0  
    for stock in order_list:
        if (stock not in context.portfolio.positions) and (len(context.portfolio.positions)< g.Total_N):
            order_target_value(stock,g.each_stock_cash)
