# Clone from JoinQuant
# postId: 2e3bd31df7e0567f4abed6bbb09ce14f
# backtestId: 36a3077d19b2f39f33ccb786352f637d
# title: 小市值超跌+大盘止损，请大神帮忙剔除st、*st以及退市博元

import pandas as pd
import numpy as np

def initialize(context):
    g.stop_threshold = -0.02
    g.choicenum = 5 #预选小市值股票数
    g.days = 0 # 计时器
    g.period = 10 #调仓频率
    g.openorder=[] #未能成功清仓的股票名
def before_trading_start(context):
    # 今天是否运行
    g.run_today = g.days % g.period == 0
    if g.run_today:
        # 设置沪深两市所有股票为股票池
        scu0 = get_index_stocks('000001.XSHG')
        scu3 = get_index_stocks('399001.XSHE')
        scu = scu0+scu3
        set_universe(scu)

# open/close orders
def rebalance(context):
    # close stock positions not in the current universe
    for stock in context.portfolio.positions.keys():
        if stock not in g.stocks:
            order_target_value(stock, 0)
    
    # close all positions when index drops by stop_threshold
    index_hist = history(2, "1d", "close", security_list=[g.index])
    print(index_hist)
    index_return_1d = index_hist[g.index].iloc[-1]/index_hist[g.index].iloc[-2] - 1
    if index_return_1d < g.stop_threshold:
        for stock in g.stocks:
            order_target_value(stock, 0)
        return
    
    stock_hist = history(g.period, "1d", "close")
    stock_return = (stock_hist.ix[g.period-1]-stock_hist.ix[0])/stock_hist.ix[0]
    stock_return = stock_return[g.stocks].order()
    
    print(stock_return)
    g.stocks = [stock for stock in stock_return.index]
    g.stocks = g.stocks[:g.top_count]
            
        
def handle_data(context, data):
    # 调仓日交易
    if g.run_today:
        # 每天只运行一次
        g.run_today = False

        date=context.current_dt.strftime("%Y-%m-%d")
        buylist = []

        # 清空未完成订单
        for stock in g.openorder:
            order_target(stock,0)
        g.openorder=[]

        # 选出低市值的股票，buylist
        df = get_fundamentals(query(
                valuation.code,valuation.market_cap
            ).filter(
                valuation.code.in_(context.universe)
            ).order_by(
                valuation.market_cap.asc()
            ).limit(g.choicenum), date=date
            ).dropna()
        buylist = list(df['code'])

        # 目前持仓中不在buylist中的股票，清仓
        for stock in context.portfolio.positions:
            if stock not in buylist:
                order_target(stock,0)

        # 等权重买入buylist中的股票
        position_per_stk = context.portfolio.cash/g.choicenum
        for stock in buylist:
            if not data[stock].isnan():
                amount = int(position_per_stk/data[stock].price)
                order(stock, +amount)

    #获得每天未成功卖单股票
    orders=get_open_orders()
    g.openorder += [t.security for t in orders if not t.is_buy]
    
    # 天数加一
    g.days += 1