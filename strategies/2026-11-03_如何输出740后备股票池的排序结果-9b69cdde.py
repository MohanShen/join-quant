# Clone from JoinQuant
# postId: 9b69cdde5ddd6a9c03a97edff877a60d
# backtestId: 5cafebc8b7de9fba2bd8272d28d02012
# title: 如何输出740后备股票池的排序结果

import math
from jqfactor import get_factor_values
from jqdata import *
def initialize(context):
    # 设置基准为中小综指（399101.XSHE）
    set_benchmark('399101.XSHE')
    # 设置使用实际价格
    set_option('use_real_price', True)
    # 设置滑点为0.00
    set_slippage(PriceRelatedSlippage(0.00))
    # 设置交易成本，平仓的佣金为0.001，开仓佣金为0.0003，最低佣金为5
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    # 中小综指（399101.XSHE）作为股票池
    g.security_universe_index = "399101.XSHE"  
    # 选中的股票列表
    g.chosen_stock_list = [] 
    # 已卖出的股票
    g.sold_stock = {}  
    # 每次最多买入股票数量
    g.buy_stock_count = 5
    # 过去30天最高价格比当前价格下降超过30%，表示熊市
    g.bearpercent = 0.3 
    # 是否处于熊市
    g.bearposition = True
    # 卖出时的排名阈值（1-10）
    g.sellrank = 10 
    # 买入时的排名阈值（1-10）
    g.buyrank = 9 
    # 新股可交易天数
    g.tradeday = 300 
    # 过去1天的涨幅
    g.increase1d = 0.087 
    # 计算中小综指数（399101.XSHE）的13日移动平均线
    g.MA = ['399101.XSHE', 13] 
    # 是否触发选股时间信号
    g.choose_time_signal = False
    # 牛熊切换阈值
    g.threshold = 0.003
    # 再次买入的间隔时间
    g.buyagain = 5 
    # 排名条件及权重，正数代表从小到大，负数表示从大到小
    # 各因子权重：总市值，流通市值，最新价格，5日平均成交量，60日涨幅
    g.weights = [5,5,8,4,10]
    # 是否牛市
    g.isbull = False
    # 空仓专用信号
    g.nohold = True
    # 每天的 09:30 执行 mysell 函数
    run_daily(mysell, '09:30')
    # 每天的 09:31 执行 mybuy 函数
    run_daily(mybuy, '09:31')
    # 只记录错误信息，不记录其他信息。
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('history', 'error')
    # log.info('初始函数开始运行且全局只运行一次')
# 获取前n个单位时间当时的收盘价
    # 定义了一个名为 get_close_price 的函数，该函数接收三个参数：code，n，unit。
    # 其中，code 是代码，n 是数量，unit 默认为 '1d'，表示时间单位。
    # 该函数返回调用 attribute_history 函数后获得的收盘价的第一个值。
def get_close_price(code, n, unit='1d'):
    return attribute_history(code, n, unit, 'close')['close'][0]
# 牛熊市场判断函数
    # 定义了一个名为 get_bull_bear_signal_minute 的函数，该函数用于获取牛熊信号。
def get_bull_bear_signal_minute():
    # 调用 get_bars 函数获取收盘价，并将返回值的 'close' 部分赋值给变量 closes。
    closes = get_bars(security=g.MA[0], count=g.MA[1], unit='1d', fields=['close'],
    include_now=True, df=False)['close']
    # 获取最后一个收盘价的值，并将其赋值给变量 now_index。
    now_index = closes[-1]
    # 获取 closes 的平均值，并将其赋值给变量 MAold。
    MAold = closes.mean()
    # 获取变量 g.threshold 的值，并将其赋值给变量 threshold。
    threshold = g.threshold
    # 判断变量 g.isbull 是否为真，
    # 如果为真，则判断 now_index * (1 + threshold) 是否小于等于 MAold。
    # 如果为真，则将 g.isbull 设置为假。
    if g.isbull:
        # 现价比g.MA均价低，两者差值大于阈值时转熊
        if now_index * (1 + threshold) <= MAold:
            g.isbull = False
        # 判断变量 g.isbull 是否为假，
        # 如果为假，则判断 now_index 是否大于 MAold * (1 + threshold)。
        # 如果为真，则将 g.isbull 设置为真。
    else:
        # 现价比g.MA均价高，两者差值大于阈值时转牛
        if now_index > MAold * (1 + threshold):
            g.isbull = True
# 获取股票现价和60日以前的价格涨幅
def get_growth_rate60(code):
    # 获取股票60天前的收盘价
    price60d = attribute_history(code, 60, '1d', 'close', False)['close'][0]
    # 获取股票当前的收盘价
    pricenow = get_close_price(code, 1, '1m')
    # 判断价格是否存在 NaN 和价格是否为0，避免除0错误
    if not math.isnan(pricenow) and not math.isnan(price60d) and price60d != 0:
    # 返回现价除以60天前的收盘价得到的涨幅
        return pricenow / price60d
    else:
    # 返回100
        return 100
# 黑名单        
    # 定义了一个函数get_blacklist
def get_blacklist():
    # 该函数返回一个空的列表
    return[]
# 过滤创业版、科创版股票
def filter_gem_stock(context, stock_list):
    return [stock for stock in stock_list if stock[0:3] != '300' and stock[0:3] != "688"]
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
# 开盘前运行数
# 取流通市值最小的1000股作为基础的股票池，以备继续筛选
def get_stock_list(context):
    # 获取基准指数下的所有股票代码
    initial_list = get_index_stocks(g.security_universe_index)
    # 查询这些股票的相关信息，并以流通市值从小到大排序
    q = query(valuation.code).filter(valuation.code.in_(initial_list)).order_by(valuation.circulating_market_cap.asc())
    # 限制取得的股票数量为 buy_stock_count * 30
    q = q.limit(g.buy_stock_count * 30)
    # 获取股票的基本面数据
    df = get_fundamentals(q)
    # 获取股票的代码列表
    stock_list = list(df['code'])
    # 过滤ST、停牌、当日涨停、当日跌停、次新股、昨日涨幅过高、卖出后天数不够
    # 定义一个名为 filters 的列表，其中包含以下函数
    filters = [
        filter_st_stock,
        filter_paused_stock,
    # 一个匿名函数，该函数接受一个名为 lst 的参数，并调用
        lambda lst: filter_limitup_stock(context, lst),
    # 一个匿名函数，该函数接受一个名为 lst 的参数，并调用
        lambda lst: filter_limitdown_stock(context, lst),
    # 一个匿名函数，该函数接受一个名为 lst 的参数，并调用
        lambda lst: filter_new_stock(context, lst),
        filter_increase1d,
        filter_buyagain
    ]
    # 对 filters 列表中的每个函数进行循环：
    # 将该函数作用于 stock_list 变量，并将结果赋值给 stock_list
    for f in filters:
        stock_list = f(stock_list)
    return stock_list
# 后备股票池进行综合排序筛选
    # 定义了一个函数get_stock_rank_m_m，该函数接收一个参数stock_list，
    # 其作用是根据某些规则计算出股票排名，并返回排名最高的若干只股票的代码
def get_stock_rank_m_m(stock_list):
    rank_stock_list = get_fundamentals(query(valuation.code, valuation.market_cap, valuation.circulating_market_cap).filter(valuation.code.in_(stock_list)).order_by(valuation.circulating_market_cap.asc()).limit(200))
    # 5日累计成交量最小的
    volume5d = [attribute_history(stock, 1200, '1m', 'volume', df=False)['volume'].sum() for stock in rank_stock_list['code']]
    # 60日涨幅最小的
    increase60d = [get_growth_rate60(stock) for stock in rank_stock_list['code']]
    # 当前价格最低的
    current_price = [get_close_price(stock, 1, '1m') for stock in rank_stock_list['code']]
    # 流通市值最小的
    min_circulating_market_cap = min(rank_stock_list['circulating_market_cap'])
    # 总市值最小的
    min_market_cap = min(rank_stock_list['market_cap'])
    # 5日累计成交量最小的
    min_volume = min(volume5d)
    # 60日涨幅最小的
    min_increase60d = min(increase60d)
    # 当前价格最低的
    min_price = min(current_price)
    # 遍历每只股票，计算出它的总得分（total），并将每只股票的索引和得分存入列表totalcount
    totalcount = []
    for i in rank_stock_list.index:
        log_volume = math.log(min_volume / volume5d[i]) * g.weights[3]
        log_price = math.log(min_price / current_price[i]) * g.weights[2]
        log_circulating_market_cap = math.log(min_circulating_market_cap / rank_stock_list['circulating_market_cap'][i]) * g.weights[1]
        log_market_cap = math.log(min_market_cap / rank_stock_list['market_cap'][i]) * g.weights[0]
        log_increase60d = math.log(min_increase60d / increase60d[i]) * g.weights[4]
        total = log_volume + log_price + log_circulating_market_cap + log_market_cap + log_increase60d
        totalcount.append([i, total])
    # 累加后排序
    # 对totalcount按得分排序，并取出得分最高的若干只股票的代码
    totalcount.sort(key=lambda x:x[1])    
    #（若干数量取决于变量g.sellrank，为它以前定义过的值），返回这些代码组成的列表
    return [rank_stock_list['code'][totalcount[-1-i][0]] for i in range(min(g.sellrank, len(rank_stock_list)))]
#   平仓，卖出指定持仓
def close_position(code):
    # 对某个代码下单并将仓位全部平掉，可能会因停牌或跌停失败
    order = order_target_value(code, 0) 
    # 如果下单成功且状态为已下单，则在 sold_stock 字典中将该代码的值设为0
    if order and order.status == OrderStatus.held:
        g.sold_stock[code] = 0
#   定义清仓函数
def clear_position(context):
    # 获取当前持仓的股票
    positions = context.portfolio.positions
    # 如果有持仓
    if positions:
        # 记录一条信息
        log.info("==> 清仓")
        # 遍历所有股票
        for stock in positions.keys():
            # 关闭这个持仓
            close_position(stock)
#   定义卖出后的天数
def before_trading_start(context):
    # 临时变量temp用于存储已售出的股票
    temp = g.sold_stock
    # 重置已售出的股票
    g.sold_stock = {}
    # 遍历temp，查看已售出股票是否可以再次购买
    for stock in temp.keys():
        # 如果已经过了设定的再次购买天数，跳过此次循环
        if temp[stock] >= g.buyagain - 1:
            pass
        # 否则，将该股票加入已售出股票中
        else:
            g.sold_stock[stock] = temp[stock]+1
    # 获取当前可以买入的股票列表
    g.chosen_stock_list = get_stock_list(context)
#   定义调仓策略：控制在设置的仓位比例附近，如果过多或过少则调整
    #熊市时按设置的总仓位比例控制
def my_adjust_position(context, hold_stocks):
    # 按是否择时、牛熊市等条件计算个股资金正常占比和最大占比
    # 可用价值的当前组合的总资产
    free_value = context.portfolio.total_value * (g.bearpercent if g.choose_time_signal and (not g.isbull) else 1)
    # 计算一只股票最大的仓位比例
    maxpercent = 1.3 / g.buy_stock_count * (g.bearpercent if g.choose_time_signal and (not g.isbull) else 1)
    # 计算每支股票的可用金额
    buycash = free_value / g.buy_stock_count
    # 获取当前股票数据
    current_data = get_current_data()
    # 持有的股票如果不在选股池，没有涨停就卖出；如果仓位比重大于最大占比限制，就降到正常仓位比重
    # 遍历持仓的股票
    for stock in context.portfolio.positions.keys():
        current_data = get_current_data()
        # 获取股票一天前的收盘价
        price1d = get_close_price(stock, 1)
        # 判断股票是否不在持仓清单里面，是否已经到了涨停价
        nosell_1 = context.portfolio.positions[stock].price >= current_data[stock].high_limit
        # 当由牛转熊时，股票排序不在前g.buy_stock_count内都卖出
        if g.direction == -1: 
            sell_2 = stock not in hold_stocks[:g.buy_stock_count]
        else:
        # 如果股票不在持仓清单里面且未到涨停价，则卖出
            sell_2 = stock not in hold_stocks
        if sell_2 and not nosell_1:
            close_position(stock)
        # 如果该股票的当前仓位比例已经大于设定的最大仓位比例，则降低仓位
        else:
            current_percent = context.portfolio.positions[stock].value / context.portfolio.total_value
            if current_percent > maxpercent:order_target_value(stock, buycash)
#   买入函数
def mybuy(context):
    # 如果标记为不持股，则直接返回
    # 如果全局变量g.nohold的值为真，则退出函数，不执行后面的代码。
    if g.nohold:
        return
    # 过滤可以买入的股票列表
    # 使用filter_buyagain函数对股票列表进行筛选，得到名为hold_stocks的可以买入的股票列表。
    hold_stocks = filter_buyagain(g.chosen_stock_list)
    # 获取投资组合总价值，最低持仓比例为0.7 / 买入股票数量
    # 初始化变量free_value为当前组合的总资产
    # 初始化变量minpercent为每支股票在组合中的最低份额（即组合总资产除以买入股票数量再乘以0.7）。
    free_value, minpercent = context.portfolio.total_value, 0.7 / g.buy_stock_count
    # 如果启用了买入时间信号并且不是牛市，则将投资组合价值乘以牛熊市百分比
    # 如果全局变量g.choose_time_signal为真且全局变量g.isbull的值为假，说明当前是熊市，
    # 此时将free_value和minpercent同时乘以全局变量g.bearpercent的值
    if g.choose_time_signal and not g.isbull:
        free_value *= g.bearpercent
        minpercent *= g.bearpercent
    # 每支股票买入的总价值为投资组合总价值除以买入股票数量
    # 计算每支股票的买入金额，并将其赋值给变量buycash
    buycash = free_value / g.buy_stock_count
    # 现有现金减去持仓股票总价值为可用现金
    # 计算当前组合中的剩余现金，并将其赋值给变量free_cash
    free_cash = free_value - context.portfolio.positions_value
    # 最小买入额为投资组合总价值除以买入股票数量的10倍
    # 计算每次买入的最低金额，并将其赋值给变量min_buy。
    min_buy = context.portfolio.total_value / (g.buy_stock_count * 10)
    # 获取黑名单列表
    # 调用函数get_blacklist，获取黑名单列表，并将其赋值给变量blacklist。
    blacklist = get_blacklist()
    # 遍历前n支排名靠前的股票（n为买入数量）
    # 使用for循环遍历可买入的股
    for i in range(min(g.buyrank, len(hold_stocks))):
        # 如果已买入的股票数量大于等于买入数量，那么循环结束
        if len(context.portfolio.positions) >= g.buy_stock_count:
            break
        stock = hold_stocks[i]
        # 从 hold_stocks 中取出一个股票，如果该股票在黑名单内，则跳过这个股票
        if stock in blacklist:
            continue
        # 如果当前可用现金不足以购买最小购买金额，那么循环结束
        if free_cash <= min_buy:
            break
        # 获取该股票的持仓，如果该股票已经持有，则计算它的仓位占比
        position = context.portfolio.positions.get(stock)
        # 如果该股票没有持有，则将当前仓位占比设置为0
        current_percent = position.value / context.portfolio.total_value if position else 0
        # 如果当前仓位占比已经大于最小仓位占比，那么跳过该股票
        if current_percent >= minpercent:
            continue
        # 计算要购买的金额，该金额为 min(free_cash, buycash - position.value) 或 
        # min(buycash, free_cash) 中的较小值，具体计算方法取决于该股票是否已持有
        tobuy = min(free_cash, buycash - position.value) if position else min(buycash, free_cash)
        # 使用 order_value 函数以该股票的价值为参数下单购买该股票
        order_value(stock, tobuy)
        # 不管有没有成交，只要下单了就从free_cash中扣除tobuy的资金
        # 将当前可用现金减去该购买金额
        free_cash -= tobuy
#   卖出、调仓函数
def mysell(context):
    # 记录下当前市场是否为牛市
    temp0 = g.isbull
    # 获取牛熊信号，判断市场是否进入牛市
    get_bull_bear_signal_minute()
    temp1 = g.isbull
    # 判断市场是否从熊市转为牛市，或从牛市转为熊市，或不变
    if temp0 == temp1:
        g.direction = 0  #  牛熊不变
    elif temp1:
        g.direction = 1  #  熊转牛 +1
    else:
        g.direction = -1 #  牛转熊 -1 
    # 记录日志，显示当前市场是牛市还是熊市
    log.info("%s市" % ("牛" if g.isbull else "熊"))
    # 如果当前市场为牛市，或当前市场为熊市但维持现有仓位，
    # 或当前时刻不选择信号且可选股票数量大于等于10
    # 则根据选择的股票列表调整仓位，并记录未平仓
    if (not g.choose_time_signal or g.isbull or g.bearposition) and len(g.chosen_stock_list) >= 10:
        # 获取选择的股票排名列表
        g.chosen_stock_list = get_stock_rank_m_m(g.chosen_stock_list)
        # 调整仓位
        my_adjust_position(context, g.chosen_stock_list)
        # 记录未平仓
        g.nohold = False
    else:
    # 如果当前市场为熊市，且当前时刻选择信号，或可选股票数量小于10，
    # 则清空仓位，并记录已平仓
        clear_position(context)
        g.nohold = True