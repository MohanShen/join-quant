# Clone from JoinQuant
# postId: 43fca771ed17613212b6056fed74911f
# backtestId: afe25c6e198dab69002078946aa880b0
# title: 一日游短线策略

import pandas as pd
import numpy as np
import math

def initialize(context):
    context.s1 = "399005.XSHE"
    context.max_num_stocks = 100
    context.valid_num_stocks = 3
    context.datas = {}
    context.OBSERVATION= 20
    context.ma = 0
    context.lastma = 0
 
#指定股票池
#小市值
def get_stocks_fundamental(context):
    fundamental_df = get_fundamentals(
        query(valuation.code, valuation.market_cap)
        .order_by(valuation.market_cap.asc())
        .limit(context.max_num_stocks)
    )
    return list(fundamental_df["code"])
#根据指数获取
def get_stocks_byindex(context):
    return get_index_stocks(context.s1)
    
def before_trading_start(context):
    #取得股票池，可换为小市值或指数，也可自己写方法设置
    stocks = get_stocks_fundamental(context)
    context.stocks = stocks
    stocks.append(context.s1)
    set_universe(stocks)


def is_trading(bar_dict):
    def make_filter(stock):
        return not bar_dict[stock].paused and  not bar_dict[stock].is_st
    return make_filter

def should_buy(bar_dict):
    def make_filter(stock):
        ma20 = sum(history(10,'1d','close')[stock][:])/10
        ma5 = sum(history(5,'1d','close')[stock][:])/5
        return ma5 > ma20
    return make_filter
    
def should_clear(stocks,context,bar_dict):
    ma5 = sum(history(5,'1d','close')[context.s1][:])/5
    return ma5 > bar_dict[context.s1].close
    
def should_clear2(stocks,context,bar_dict):
    context.lastma = context.ma
    context.ma = sum(history(context.OBSERVATION,'1d','close')[context.s1][:])/context.OBSERVATION
    
    if context.lastma == 0:
        return True
    print "context.ma:"+str(context.ma)
    print "context.lastma:"+str(context.lastma)
    print "context.ma < context.lastma:"+str(context.ma < context.lastma)
    
    return context.ma < context.lastma

# 每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)调用一次
def handle_data(context, data):
    have_set = set(context.portfolio.positions.keys())

    holds = context.stocks
    
    #1 数据筛选：过滤是否停牌 过滤st
    current_data = get_current_data()
    is_trading_filter = is_trading(current_data)
    holds = list(filter(is_trading_filter, holds))
    
    #2 过滤选出满足条件的个股
    should_buy_fliter = should_buy(data)
    holds = list(filter(should_buy_fliter, holds))
    print("筛选后剩余股票数:" + str(len(holds)))
    
    #3 操作股票的数量选择
    holds = holds[:context.valid_num_stocks]
    
    if not len(holds) == context.valid_num_stocks:
        print(holds)
        
    # 大盘把控
    if should_clear2(holds,context,data):
        holds = []
        print "大盘风向有变，今日开盘时，只平仓，不建仓"
    
    hold_set = set(holds)

    to_buy = hold_set - have_set
    to_sell = have_set - hold_set
    
    is_trading_filter = is_trading(get_current_data(to_sell))
    to_sell = list(filter(is_trading_filter, to_sell))
    
    for stock in to_sell:
        if not low_enough(stock,data):
            order_target(stock, 0)
            print "Selling:"+stock
        
    if len(to_buy) == 0:
        return
    
    each = context.portfolio.cash/len(to_buy)
    
    for stock in to_buy:
        if not high_enough(stock,data):
            print "money:"+str(each)
            print "price:"+str(data[stock].close)
            volume = int(each/data[stock].close/100*0.998) * 100
            print "buying:"+stock+",count:"+str(volume)
            if volume > 0:
                order_target(stock, volume)
    
def high_enough(stock, bar_dict):
    price = history (2, '1d', 'close')[stock].ix[0]
    if math.isnan(price):
        return True
    pricenow = bar_dict[stock].close
    pct_change = (pricenow - price) / price
    print "stock:"+str(stock)+",high_enough:"+str(pct_change)
    return pct_change>0.1
    
    
def low_enough(stock, bar_dict):
    price = history (2, '1d', 'close')[stock].ix[0]
    if math.isnan(price):
        return True
    pricenow = bar_dict[stock].close
    pct_change = (pricenow - price) / price
    print "stock:"+str(stock)+",low_enough:"+str(pct_change)
    return pct_change<-0.1