# Clone from JoinQuant
# postId: 69d68509efbce8fbca4737289612ddff
# backtestId: c34d16324cbe89022d456a459ce36cdc
# title: 为什么过滤后只剩1个股票，而且不能交易？

import math
from jqfactor import get_factor_values
from pandas.core.frame import DataFrame
def initialize(context):
    set_option('use_real_price', True)
    g.security_universe_index = "399101.XSHE"  
    g.chosen_stock_list1 = [] 
    g.chosen_stock_list2 = [] 
    g.chosen_stock_list3 = [] 
    g.chosen_stock_list = [] 
    g.sold_stock = {}  
    g.buy_stock_count = 3
    g.sellrank = 10 
    g.buyrank = 9 
    g.tradeday = 250
    g.increase1d = 0.087 
    g.buyagain = 5 
    # 各因子权重：总市值，流通市值，最新价格，5日平均成交量，60日涨幅
    g.weights = [5,5,8,4,10]
    run_daily(before_trading_start,'09:01')
    run_daily(mybuylist,'09:02')
    run_daily(mysell, '09:30')
    run_daily(mybuy, '09:30')
def get_stock_list(context):
    initial_list = get_index_stocks(g.security_universe_index)
    q = query(valuation.code).filter(valuation.code.in_(initial_list)).order_by(valuation.circulating_market_cap.asc())
    q = q.limit(g.buy_stock_count * 25)
    df = get_fundamentals(q)
    stock_list = list(df['code'])
    filters = [
        filter_st_stock,
        filter_paused_stock,
        lambda lst: filter_limitup_stock(context, lst),
        lambda lst: filter_limitdown_stock(context, lst),
        lambda lst: filter_new_stock(context, lst),
        filter_increase1d,
        filter_buyagain
    ]
    for f in filters:
        stock_list = f(stock_list)
    return stock_list
def get_stock_rank_m_m(stock_list):
    rank_stock_list = get_fundamentals(query(valuation.code, valuation.market_cap, valuation.circulating_market_cap).filter(valuation.code.in_(stock_list)).order_by(valuation.circulating_market_cap.asc()).limit(200))
    volume5d = [attribute_history(stock, 1200, '1m', 'volume', df=False)['volume'].sum() for stock in rank_stock_list['code']]
    increase60d = [get_growth_rate60(stock) for stock in rank_stock_list['code']]
    current_price = [get_close_price(stock, 1, '1m') for stock in rank_stock_list['code']]
    if not rank_stock_list['circulating_market_cap'].empty:
        min_circulating_market_cap = min(rank_stock_list['circulating_market_cap'])
    else:
        min_circulating_market_cap = 0
    if not rank_stock_list['market_cap'].empty:
        min_market_cap = min(rank_stock_list['market_cap'])
    else:
        min_market_cap = 0
    if volume5d:
        min_volume = min(volume5d)
    else:
        min_volume = 0
    if increase60d:
        min_increase60d = min(increase60d)
    else:
        min_increase60d = 0
    if current_price:
        min_price = min(current_price)
    else:
        min_price = 0
    totalcount = []
    for i in rank_stock_list.index:
        log_market_cap = math.log(min_market_cap / rank_stock_list['market_cap'][i]) * g.weights[0]
        log_circulating_market_cap = math.log(min_circulating_market_cap / rank_stock_list['circulating_market_cap'][i]) * g.weights[1]
        log_price = math.log(min_price / current_price[i]) * g.weights[2]
        log_volume = math.log(min_volume / volume5d[i]) * g.weights[3]
        log_increase60d = math.log(min_increase60d / increase60d[i]) * g.weights[4]
        total = log_market_cap +log_circulating_market_cap+log_price +log_volume +log_increase60d
        totalcount.append([i, total])
    totalcount.sort(key=lambda x: x[1])    
    return [rank_stock_list['code'][totalcount[-1-i][0]] for i in range(min(g.sellrank, len(rank_stock_list)))]
def close_position(code):
    order = order_target_value(code, 0) 
    if order and order.status == OrderStatus.held:
        g.sold_stock[code] = 0
def before_trading_start(context):
    temp = g.sold_stock
    g.sold_stock = {}
    for stock in temp.keys():
        if temp[stock] >= g.buyagain - 1:
            pass
        else:
            g.sold_stock[stock] = temp[stock]+1
    chosen_stock_list1 = get_stock_list(context)
    chosen_stock_list1 = get_stock_rank_m_m(chosen_stock_list1)[:3]
    chosen_stock_list2 = get_stock_list(context)[:5]
    union_list = list(set(chosen_stock_list1 + chosen_stock_list2))
    g.chosen_stock_list = union_list  
    g.chosen_stock_list = get_fundamentals(
    query(valuation.code)
    .filter(valuation.code.in_(union_list))
    .order_by(valuation.circulating_market_cap.asc()))
def mybuylist(context):
    hold_stocks = filter_buyagain(g.chosen_stock_list)
    print('今日4次过滤后还剩 %s 个' % len(hold_stocks))
def my_adjust_position(context, hold_stocks):
    free_value = context.portfolio.total_value
    maxpercent = 1.3 / g.buy_stock_count
    buycash = free_value / g.buy_stock_count
    current_data = get_current_data()
    for stock, position in context.portfolio.positions.items():
        price1d = get_close_price(stock, 1)
        nosell_1 = position.price >= current_data[stock].high_limit
        sell_2 = stock not in hold_stocks
        if sell_2 and not nosell_1:
            close_position(stock)
        else:
            current_percent = position.value / context.portfolio.total_value
            if current_percent > maxpercent:
                order_target_value(stock, buycash)

def mybuy(context):
    hold_stocks = filter_buyagain(g.chosen_stock_list)
    free_value, minpercent = context.portfolio.total_value, 0.7 / g.buy_stock_count
    buycash = free_value / g.buy_stock_count
    free_cash = free_value - context.portfolio.positions_value
    min_buy = context.portfolio.total_value / (g.buy_stock_count * 10)
    blacklist = get_blacklist()
    for i in range(min(g.buyrank, len(hold_stocks))):
        if len(context.portfolio.positions) >= g.buy_stock_count:
            break
        stock = hold_stocks[i]
        if stock in blacklist:
            continue
        if free_cash <= min_buy:
            break
        position = context.portfolio.positions.get(stock)
        current_percent = position.value / context.portfolio.total_value if position else 0
        if current_percent >= minpercent:
            continue
        tobuy = min(free_cash, buycash - position.value) if position else min(buycash, free_cash)
        order_value(stock, tobuy)
        free_cash -= tobuy
#   卖出、调仓函数
def mysell(context):
        g.chosen_stock_list = get_stock_rank_m_m(g.chosen_stock_list)
        my_adjust_position(context, g.chosen_stock_list)
def get_close_price(code, n, unit='1d'):
    return attribute_history(code, n, unit, 'close')['close'][0]
def get_growth_rate60(code):
    price60d = attribute_history(code, 60, '1d', 'close', False)['close'][0]
    pricenow = get_close_price(code, 1, '1m')
    if not math.isnan(pricenow) and not math.isnan(price60d) and price60d != 0:
        return pricenow / price60d
    else:
        return 100
# 黑名单        
    # 定义了一个函数get_blacklist
def get_blacklist():
    # 该函数返回一个空的列表
    return[]
# 定义过滤停牌股票
def filter_paused_stock(stock_list):
    # 获取当前股票数据
	current_data = get_current_data()
	# 返回未停牌的股票列表
	return [stock for stock in stock_list if not current_data[stock].paused]
# 定义过滤ST及其他具有退市标签的股票        
def filter_st_stock(stock_list):
    # 获取当前数据
    current_data = get_current_data()
    # 返回符合以下条件的股票列表：
    # - current_data字典中该股票的is_st属性为False
    # - current_data字典中该股票的name属性不包含字符串"ST"
    # - current_data字典中该股票的name属性不包含字符"*"
    # - current_data字典中该股票的name属性不包含字符串"退"
    return [stock for stock in stock_list if not current_data[stock].is_st and 'ST' not in current_data[stock].name and '*' not in current_data[stock].name and '退' not in current_data[stock].name]
# 定义过滤涨停的股票
def filter_limitup_stock(context, stock_list):
    # 获取每只股票的最后一个价格
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    # 获取当前数据
    current_data = get_current_data()
    # 返回符合以下条件的股票列表：
    # - 股票在投资组合的持仓列表中
    # - 或者该股票的最后一个价格小于该股票的涨停价
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys() 
        or last_prices[stock][-1] < current_data[stock].high_limit]
# 定义过滤跌停的股票
def filter_limitdown_stock(context, stock_list):
    # 获取每只股票的最后一个价格
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    # 获取当前数据
    current_data = get_current_data()
    # 返回符合以下条件的股票列表：
    # - 股票在投资组合的持仓列表中
    # - 或者该股票的最后一个价格大于该股票的跌停价
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
			or last_prices[stock][-1] > current_data[stock].low_limit]
# 定义过滤次新股
def filter_new_stock(context, stock_list):
    # 使用列表推导式，遍历 stock_list 中的每一个股票
    # 若股票的上市日期比 context.previous_date 减去 g.tradeday 天数大，则说明该股票是新股
    # 将符合要求的新股票加入列表中并返回
    return [stock for stock in stock_list if (context.previous_date - datetime.timedelta(days=g.tradeday)) > get_security_info(stock).start_date]
# 定义过滤昨日涨幅过高的股票    
def filter_increase1d(stock_list):
    # 使用列表推导式，遍历 stock_list 中的每一个股票
    # 若股票的 1d 涨幅小于 (1 + g.increase1d)，则将该股票加入列表中并返回
    return [stock for stock in stock_list if get_close_price(stock, 1) / get_close_price(stock, 2) < (1 + g.increase1d)]
# 定义过滤买过的股票
def filter_buyagain(stock_list):
    # 使用列表推导式，遍历 stock_list 中的每一个股票
    # 若该股票在 g.sold_stock 中，说明该股票已经卖出，不再加入列表中并返回
    return [stock for stock in stock_list if stock not in g.sold_stock.keys()]