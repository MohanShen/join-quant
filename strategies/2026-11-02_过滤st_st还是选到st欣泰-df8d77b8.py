# Clone from JoinQuant
# postId: df8d77b8c4f5a64e89a12fa55d5ccb07
# backtestId: d67bf17d83dcb72a69c2fe5da9567ae0
# title: 过滤st、*st还是选到st欣泰

from datetime import datetime as dt
from datetime import timedelta as td

def initialize(context):
    run_daily(period,time='every_bar')
    g.stocksnum = 2
    g.period = 25
    g.days = 0
#过滤停牌
def unpaused(stockspool):
    current_data=get_current_data()
    return [s for s in stockspool if not current_data[s].paused]
#过滤ST,*ST
def filter_st(context, stock_list):
    df = get_extras('is_st', stock_list, start_date=context.current_dt.date(), end_date=context.current_dt.date()).T
    df.columns = ['is_st']
    df = df[df.is_st == False]
    return df.index.tolist()
#过滤开盘涨停
def filter_tday_open_high_limit(stock_list):
    a_stock_list = []
    current_data = get_current_data()
    for stock in stock_list:
        tday_open = current_data[stock].day_open
        thigh_limit = current_data[stock].high_limit
        if tday_open != thigh_limit:
            a_stock_list.append(stock)
    return a_stock_list
#过滤退市股票
def filter_delist(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not '退' in current_data[stock].name]
#过滤新股
def filter_new(context, stock_list, n=30):
    a_stock_list = []
    td_date = context.previous_date - td(days=n)
    for stock in stock_list:
        start_date = get_security_info(stock).start_date
        if start_date < td_date:
            a_stock_list.append(stock)
    return a_stock_list
def period(context):
    if g.days % g.period == 0:
        scu = get_index_stocks('000001.XSHG')+get_index_stocks('399106.XSHE')
        q = query(valuation.code).filter(valuation.code.in_(scu),valuation.pe_ratio > 25).order_by(valuation.market_cap.asc()).limit(g.stocksnum)
        w = get_fundamentals(q)
        #去除停牌股票
        buylist = unpaused(list(w['code']))
        #去除ST，*ST
        buylist = filter_st(context, buylist)
        #去除开盘涨停股票
        buylist = filter_tday_open_high_limit(buylist)
        #去除退市股票
        buylist = filter_delist(buylist)
        #去除新股
        buylist = filter_new(context, buylist)
        #不在buylist中的股票全部卖出
        for stock in context.portfolio.positions:
            if stock not in buylist:
                order_target(stock,0)
        position_per_stk = context.portfolio.cash/g.stocksnum
        for stock in buylist:
            order_value(stock,position_per_stk)
            #获得股票持仓成本
            cost = context.portfolio.positions[stock].avg_cost
            if cost == 0:
                continue
            #获得股票现价
            price = context.portfolio.positions[stock].price
            #计算收益率
            ret = price/cost-1
            #当亏损达到5%时则卖出股票
            if ret<=-0.05:
                order_target(stock,0)
                print('触发止损')
            #当盈利达到5%时则卖出股票
            elif ret>=0.05:
                order_target(stock,0)
                print('触发止盈')
    g.days += 1