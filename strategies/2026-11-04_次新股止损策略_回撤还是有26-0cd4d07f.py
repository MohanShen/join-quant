# Clone from JoinQuant
# postId: 0cd4d07f59cff31346852916b7f5396c
# backtestId: bbb4cde80e2e30bcae447b99e2296e6a
# title: 次新股止损策略，回撤还是有26%？

import talib as tl
def initialize(context):
    set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
    set_option('use_real_price', True)
    g.buy_stock_count = 4 
    g.black_list = {}
    g.ornum = 8
def before_trading_start(context):
    blacklist(context)
    
def handle_data(context, data):
    for stock in context.portfolio.positions.keys():
        if data[stock].close < data[stock].vwap(20) - data[stock].stddev(20):
            if data[stock].close < 1.06*data[stock].low_limit:
                order_target_value(stock, 0)
                log.info("止损")
                g.black_list[stock] = 0
        if data[stock].close > data[stock].vwap(60) + 2*data[stock].stddev(60):
            if data[stock].close < 0.97*data[stock].high_limit:
                order_target_value(stock, 0)
                log.info("止盈 ")
                g.black_list[stock] = 0
    hour = context.current_dt.hour
    minute = context.current_dt.minute
    if hour == 10 and minute == 00:
        buy_stocks = select_stocks(context,data)
        adjust_position(context,data, buy_stocks)
def filter_paused_and_st_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused 
    and not current_data[stock].is_st and 'ST' not in current_data[stock].
    name and '*' not in current_data[stock].name and '退' not in current_data[stock].name]
def filter_gem_stock(context, stock_list):
    return [stock for stock in stock_list  if stock[0:3] != '300']
def select_stocks(context,data):
    q = query(valuation.code, valuation.circulating_market_cap).order_by(
            valuation.circulating_market_cap.asc()).filter(
            valuation.circulating_market_cap <= 100).limit(100)
    df = get_fundamentals(q)
    stock_list = list(df['code'])
    stock_list = filter_paused_and_st_stock(stock_list)
    stock_list = filter_gem_stock(context, stock_list)
    # stock_list = filter_RSI_stock(context, stock_list)
    blacklist = ["600656.XSHG","300372.XSHE","600403.XSHG","600421.XSHG","600733.XSHG","300399.XSHE",
                 "600145.XSHG","002679.XSHE","000020.XSHE","002330.XSHE","300117.XSHE","300135.XSHE",
                 "002566.XSHE","002119.XSHE","300208.XSHE","002237.XSHE","002608.XSHE","000691.XSHE",
                 "002694.XSHE","002715.XSHE","002211.XSHE","000788.XSHE","300380.XSHE","300028.XSHE",
                 "000668.XSHE","300033.XSHE","300126.XSHE","300340.XSHE","300344.XSHE","002473.XSHE"]        
    tmpList = []
    for stock in stock_list :
        days_public=(context.current_dt.date() - get_security_info(stock).start_date).days
        if days_public < 365:
                tmpList.append(stock)
    stock_list = tmpList
    filter_stocks = []
    last_prices = history(1, '1m', 'close', security_list=stock_list)
    curr_data = get_current_data()
    for stock in stock_list:
        if last_prices[stock][-1] < curr_data[stock].high_limit:
            if last_prices[stock][-1] > curr_data[stock].low_limit:
                if stock not in blacklist:
                    filter_stocks.append(stock)
    stock_list = filter_stocks
    stock_list = stock_list[:g.buy_stock_count] 
    stock_list = [stock for stock in stock_list if stock not in g.black_list]
    return stock_list;
def adjust_position(context,data, buy_stocks):
    # stop_loss(context, data)
    for stock in context.portfolio.positions.keys():
        last_prices = history(1, '1m', 'close', security_list=context.portfolio.positions.keys())
        if stock not in buy_stocks:
            curr_data = get_current_data()
            if last_prices[stock][-1] < 0.98*curr_data[stock].high_limit:
                position = context.portfolio.positions[stock]
                order_target_value(stock, 0)
    for stock in buy_stocks:
        position_count = len(context.portfolio.positions)
        if g.buy_stock_count > position_count:
            value = context.portfolio.cash / (g.buy_stock_count-position_count)
            if context.portfolio.positions[stock].total_amount == 0:
                order_target_value(stock, value)


def blacklist(context):
    list_q = list(g.black_list.keys())
    for security in list_q:
        g.black_list[security]+= 1
        if g.black_list[security] > g.ornum:
            del g.black_list[security]
            
def filter_RSI_stock(context, stock_list):
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys() 
        or get_RSI(stock)]
