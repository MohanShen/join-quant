# Clone from JoinQuant
# postId: 8ccac7234a3932c6e49574bb95640451
# backtestId: 9b59f11f0bc33a97ec57add7e906451f
# title: 请帮我把条件选股换成自选资格股票？

# 克隆自聚宽文章：https://www.joinquant.com/post/7095
# 标题：【新手入门教程】MACD均线择时策略
# 作者： Quant中找米吃的阿鼠

import pandas as pd
import numpy as np
import talib  ## 使用talib计算MACD的参数

def initialize(context):
    set_params()
    set_backtest()
    run_daily(trade, 'every_bar')
    
def set_params():
    g.days=0    
    g.refresh_rate=10 
    
def set_backtest():
    set_benchmark('000905.XSHG') 
    set_option('use_real_price', True)  
    log.set_level('order', 'error')
    
#每天开盘前要做的事情
def before_trading_start(context):
    set_slip_fee(context)

# 根据不同的时间段设置滑点与手续费
def set_slip_fee(context):
    set_slippage(FixedSlippage(0.02)) 
    
    dt=context.current_dt
    if dt>datetime.datetime(2013,1, 1):
        set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003, close_today_commission=0, min_commission=5), type='stock')
    else:
        set_order_cost(OrderCost(open_tax=0, open_commission=0.003,close_commission=0.003, close_tax=0.001,min_commission=5), type='stock')

def paused_filter(security_list):
    current_data = get_current_data()
    security_list = [stock for stock in security_list if not current_data[stock].paused]
    return security_list


def delisted_filter(security_list):
    current_data = get_current_data()
    security_list = [stock for stock in security_list if not '退' in current_data[stock].name]
    return security_list

def st_filter(security_list):
    current_data = get_current_data()
    security_list = [stock for stock in security_list if not current_data[stock].is_st]
    return security_list
    
#######进行操作的过程#######   
def trade(context):
    stock_to_choose = get_fundamentals(query(
        valuation.code, valuation.pe_ratio, 
        valuation.pb_ratio,valuation.market_cap, 
        indicator.eps, indicator.inc_net_profit_annual
    ).filter(
        valuation.pe_ratio < 40,
        valuation.pe_ratio > 10,
        indicator.eps > 0.3,
        indicator.inc_net_profit_annual > 0.30,
        indicator.roe > 15
    ).order_by(
        valuation.pb_ratio.asc()
    ).limit(
        50), date=None)
    
    stockpool = list(stock_to_choose['code'])
    stockpool = paused_filter(stockpool)
    stockpool = delisted_filter(stockpool)
    stockpool = st_filter(stockpool)
    
    long_list = []
    short_list = []
    hold = []
    
    if g.days%g.refresh_rate == 0:
        for stock in stockpool:
            prices = attribute_history(stock,300, '1d',['close'])
            price = array(prices['close'])
            macd_tmp = talib.MACD(price, fastperiod=12, slowperiod=26, signalperiod=20)
            DIF = macd_tmp[0]
            DEA = macd_tmp[1]
            MACD = macd_tmp[2]
            
            # 判断MACD走向
            if MACD[-1] > 0 and MACD[-4] < 0:
                long_list.append(stock)
            elif MACD[-1] < 0 and MACD[-4] > 0:
                short_list.append(stock)
    
            
        stockset = list(context.portfolio.positions.keys())
            
        for stock in stockset:
            if stock in short_list:
                order_target_value(stock, 0) 
            else:
                hold.append(stock)#如果不在卖出列表里则持有
            
        buy_list = []
        for stock in long_list:
            if stock not in hold:
                buy_list.append(stock)#新增的买入股票
    
        if len(buy_list)==0: 
            Cash = context.portfolio.available_cash
        else:
            Cash = context.portfolio.available_cash/len(buy_list)
            for stock in buy_list:
                order_target_value(stock, Cash)        
        g.days = 1
    else:
        g.days += 1 