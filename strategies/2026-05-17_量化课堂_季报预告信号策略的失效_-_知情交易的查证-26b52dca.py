# Clone from JoinQuant
# postId: 26b52dcafc4dcefb062cdcd8a4d016c8
# backtestId: 98f08835579c093c25519c838bd13a37
# title: 【量化课堂】季报预告信号策略的失效 - 知情交易的查证

from jqdata import *
import tushare as ts
import numpy as np
import pandas as pd
import math
import pickle
from collections import defaultdict
# 初始化函数，设定基准等等
def initialize(context):
    rf = read_file('DateStockDict.pkl')
    load_Package = pickle.loads(rf)
    g.FL, g.PL, g.posi_stock_season_list = load_Package
    # 设定沪深300作为基准
    set_benchmark('000985.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    # set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    
    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
      # 开盘前运行
    run_daily(before_market_open, time='before_open', reference_security='000300.XSHG') 
      # 开盘时运行
    run_daily(market_open, time='open', reference_security='000300.XSHG')
      # 收盘后运行
    # run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')
    
## 开盘前运行函数     
def before_market_open(context):
    today = context.current_dt.date().isoformat()
    if today in g.FL.keys():
        today_buy_list = g.FL[today][0]
        for tup in today_buy_list:
            stock = tup[0]
            if stock in context.portfolio.positions:
                for i in range(len(g.posi_stock_season_list)):
                    if g.posi_stock_season_list[i][0] == stock:
                        g.posi_stock_season_list.pop(i)
                        break
                g.posi_stock_season_list.append(tup)
            else:
                g.posi_stock_season_list.append(tup)
                
    if today in g.PL.keys():
        today_sell_alt_list = g.PL[today][0]
        for tup in today_sell_alt_list:
            for i in range(len(g.posi_stock_season_list)):
                if g.posi_stock_season_list[i] == tup:
                    g.posi_stock_season_list.pop(i)
                    break
            
            
## 开盘时运行函数
def market_open(context):
    posi_list = [stock for stock,season in g.posi_stock_season_list]
    act_posi_list = filter_paused_and_st_stock(posi_list)
    for stock in context.portfolio.positions:
        if stock not in posi_list:
            order_target(stock, 0)
    if len(act_posi_list) > 0 :
        value = context.portfolio.total_value / len(act_posi_list)
        for stock in posi_list:
            order_target_value(stock, value)
            
# 过滤停牌 st        
def filter_paused_and_st_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused 
    and not current_data[stock].is_st and 'ST' not in current_data[stock].
    name and '*' not in current_data[stock].name and '退' not in current_data[stock].name]          
