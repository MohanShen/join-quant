# Clone from JoinQuant
# postId: 468129e89dd7b2901598429672a987f2
# backtestId: 9ecc9537ac1895bd6c59313046f25cc5
# title: “异动罗盘——寻找特例独行的股票”研究

from jqdata import *
import pandas as pd
import numpy as np
from pandas import Series, DataFrame
import datetime as datetime
import time as time

def initialize(context):
    set_params()
    set_variables()
    set_backtest()

def set_params():
    g.stocks = get_index_stocks('000001.XSHG')
    g.stocks.remove('600000.XSHG')
    g.stocks.remove('600010.XSHG')
    g.stocks_hold = {}
    g.num_stocks = 15
    g.global_pearson = {}
    Buylist = list([])
    
def set_variables():
    g.sell_conditions = {}      # 股票的卖出判定
    g.stock_stats = {}      # 记录输赢统计
    g.stock_best_ranges = {}   # 记录最佳买入区间

def set_backtest():
    set_benchmark('000001.XSHG')
    set_option('use_real_price', True) #使用真实价格
    log.set_level('order', 'error') #设置报错


def collect_buylist(feasible_stocks):
    Buylist = []
    i = datetime.datetime.now()
    pearson = list([])
    something = 0
    for stock in feasible_stocks:   
        df = attribute_history(stock, count=240, unit='1m', fields=['close','volume','money'])
        df_shangzheng = attribute_history('000001.XSHG',count=240, unit='1m', fields=['close','volume'])
        volume1 = df['volume']
        money1 = df['money']
        closeprice1 = df['close']
        closeprice2 = df_shangzheng['close']
        closeprice11 = closeprice1**2
        closeprice22 = closeprice2**2
        closeprice12 = closeprice1*closeprice2
        df2 = get_money_flow([stock],count=240, fields='change_pct')
        change_pct0 = df2['change_pct']
        change_pct = calc(change_pct0)
        if calc(money1)<2000000 or change_pct == 0.1 or change_pct == -0.1 :
            break
        pearson = (mean(closeprice12)-mean(closeprice1)*mean(closeprice2))/ (sqrt(mean(closeprice11)-mean(closeprice1)**2)*sqrt(mean(closeprice22)-mean(closeprice2)**2))
        if stock in g.global_pearson.keys():
            g.global_pearson[stock].append(pearson)
        else:
            g.global_pearson[stock] = [pearson]
        if len(g.global_pearson[stock])<41 or len(g.global_pearson[stock]) == nan:
            break
        else:
            for i in range(40):
                something = something + (g.global_pearson[stock][-i]-mean(g.global_pearson[stock][-40:]))**2
        relevancy = (g.global_pearson[stock][-1]-mean(g.global_pearson[stock][-40:]))/sqrt(something)
        if relevancy < -0.1:
            Buylist.append(stock)
    return Buylist

def calc(numbers):
    sum = 0
    for n in numbers:
        sum = sum + n 
    return sum

def mean(numbers):
    sum = 0
    for n in numbers:
        sum = sum + n
        m = sum/len(numbers)
    return m

def sqrt(numbers):
    n = numbers**0.5
    return n

def set_feasible_stocks(initial_stocks): 
    paused_info = []
    ST_info = []
    current_data = get_current_data()
    for i in initial_stocks:
        paused_info.append(current_data[i].paused)
        ST_info.append(current_data[i].is_st)
    df_paused_info = pd.DataFrame({'paused_info':paused_info},index = initial_stocks)
    df_ST_info = pd.DataFrame({'ST_info':ST_info},index = initial_stocks)
    feasible_stocks = list(df_paused_info.index[(df_paused_info.paused_info == False) & (df_ST_info.ST_info == False)])
    return feasible_stocks
  
# 每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)调用一次
def handle_data(context, data):
    position = context.portfolio.positions
    cash = context.portfolio.cash/g.num_stocks
    for key in g.stocks_hold.keys():
        g.stocks_hold[key] += 1
    a = set_feasible_stocks(g.stocks)
    Buylist = collect_buylist(a)
    sell_the_stocks(Buylist,position)
    buy_the_stocks(Buylist,position,cash)
    # if Buylist!=[]:
    #     print(Buylist)

def sell_the_stocks(Buylist,position):
    if len(position) != 0:
        for stock in position.keys():
            # print(g.stocks_hold[stock])
            if g.stocks_hold[stock] == 60:
                order_target(stock, 0)
                del g.stocks_hold[stock]
                log.info("Selling %s" % (stock))

def buy_the_stocks(Buylist,position,cash):
    if len(Buylist) != 0:
       if  len(Buylist)-len(position)>0:
            for stock in Buylist:
                order_target_value(stock,cash)
                g.stocks_hold[stock] = 0
                log.info("Buying %s" % (stock))

