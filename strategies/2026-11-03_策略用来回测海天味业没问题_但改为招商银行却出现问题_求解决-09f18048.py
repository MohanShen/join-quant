# Clone from JoinQuant
# postId: 09f18048288a88a9ccc7610ee541b05e
# backtestId: 04199496fce043a5693ab3712fb6197e
# title: 策略用来回测海天味业没问题，但改为招商银行却出现问题，求解决

import statsmodels.api as sm
def initialize(context):
    set_option('use_real_price', True)
    set_parameter(context)
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    run_daily(before_market_open, time='before_open', reference_security='000300.XSHG') 
    run_daily(market_open, time='9:30', reference_security='000300.XSHG')
    run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')
def set_parameter(context):
    g.N = 18
    g.M = 1100
    g.init = False
    g.stock_num = 5
    g.security = '603288.XSHG'
    set_benchmark(g.security)
    g.days = 0
    g.buy = 0.7
    g.sell = -0.5
    g.ans = []
    g.ans_rightdev= []
    g.blacklist = []   
    previous_date = context.current_dt - datetime.timedelta(days=1)
    prices = get_price(g.security, '2005-01-05', previous_date, '1d', ['high', 'low'])
    prices[np.isnan(prices)] = 0
    prices[np.isinf(prices)] = 0
    highs = prices.high
    lows = prices.low
    g.ans = []
    for i in range(len(highs))[g.N:]:
        data_high = highs.iloc[i-g.N+1:i+1]
        data_low = lows.iloc[i-g.N+1:i+1]
        X = sm.add_constant(data_low)
        model = sm.OLS(data_high,X)
        results = model.fit()
        g.ans.append(results.params[1])
        g.ans_rightdev.append(results.rsquared)
def before_market_open(context):
    g.days += 1
    g.statsDate = context.current_dt.date()
    send_message('策略正常，运行第%s天~'%g.days)
def market_open(context):
    times = context.current_dt.month
    security = g.security
    beta=0
    r2=0
    if g.init:
        g.init = False
    else:
        prices = attribute_history(security, g.N, '1d', ['high', 'low'])#获取过去g.n（18）天的最高价、最低价
        prices[np.isnan(prices)] = 0
        prices[np.isinf(prices)] = 0
        highs = prices.high
        lows = prices.low
        X = sm.add_constant(lows)
        model = sm.OLS(highs, X)
        beta = model.fit().params[1]
        g.ans.append(beta)
        r2=model.fit().rsquared    
        g.ans_rightdev.append(r2)
    section = g.ans[-g.M:]
    mu = np.mean(section)
    sigma = np.std(section)
    zscore = (section[-1]-mu)/sigma  
    zscore_rightdev= zscore*beta*r2
    print(zscore_rightdev)
    if zscore_rightdev > g.buy:
        log.info("市场风险在合理范围")
        trade_func(context)
    elif (zscore_rightdev < g.sell) and (len(context.portfolio.positions.keys()) > 0):
        log.info("市场风险过大，保持空仓状态")
        for s in context.portfolio.positions.keys():
            order_target(s, 0)
def trade_func(context):
    stock_list = ['603288.XSHG']
    positions_list = context.portfolio.positions.keys()
    stock_list = unpaused(context,stock_list,positions_list)
    stock_list = remove_st(context,stock_list, g.statsDate)
    stock_list = remove_limit_up(context, stock_list, positions_list) 
    pool = []
    for stock in stock_list:
        if stock not in g.blacklist:
            pool.append(stock)    
    pool = pool[:g.stock_num]
    log.info('总共选出%s只股票'%len(pool))
    if len(pool)>0:
        cash = context.portfolio.total_value/len(pool)
    sell_list = set(positions_list) - set(pool)
    for stock in sell_list:
        order_target_value(stock, 0)
    for s in pool:
        order_target_value(s,cash)
def f_sum(x):
    return sum(x)
def after_market_close(context):
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    log.info('今日账户总资产：%s'%round(context.portfolio.total_value,2))
    record(P=(100-math.ceil(context.portfolio.available_cash / context.portfolio.total_value * 100)))
def fun_delNewShare(context, equity, deltaday):
    deltaDate = context.current_dt.date() - dt.timedelta(deltaday)
    tmpList = []
    for stock in equity:
        if get_security_info(stock).start_date < deltaDate:
            tmpList.append(stock)
    return tmpList
def unpaused(context,stock_list, positions_list):
    current_data = get_current_data()
    tmpList = []
    for stock in stock_list:
        if not current_data[stock].paused or stock in positions_list:
            tmpList.append(stock)
    return tmpList
def remove_st(context, stock_list, statsDate):
    current_data = get_current_data()
    return [s for s in stock_list if not current_data[s].is_st]
def remove_limit_up(context, stock_list, positions_list):
    h = history(1, '1m', 'close', stock_list, df=False, skip_paused=False, fq='pre')
    h2 = history(1, '1m', 'high_limit', stock_list, df=False, skip_paused=False, fq='pre')
    tmpList = []
    for stock in stock_list:
        if h[stock][0] < h2[stock][0] or stock in positions_list:
                tmpList.append(stock)
    return tmpList