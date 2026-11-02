# Clone from JoinQuant
# postId: d843b52e12fe47c55f1e12e910f4a081
# backtestId: 3b24d8c8754a9ad217fcff110b3a499a
# title: 策略需要更新到python3，请各位大神帮忙

import statsmodels.api as sm
def initialize(context):
    set_option('use_real_price', True)
    set_parameter(context)
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    run_daily(before_market_open, time='before_open', reference_security='000300.XSHG') 
    run_daily(market_open, time='open', reference_security='000300.XSHG')
def set_parameter(context):
    g.N = 18
    g.M = 1100
    g.init = True
    g.stock_num = 5
    g.security = '000300.XSHG'
    set_benchmark(g.security)
    g.days = 0
    g.buy = 0.7
    g.sell = -0.5
    g.ans = []
    g.ans_rightdev= []
    prices = get_price(g.security, '2005-01-05', context.previous_date, '1d', ['high', 'low'])
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
    send_message('策略正常，运行第%s天~'%g.days)
def market_open(context):
    security = g.security
    beta=0
    r2=0
    if g.init:
        g.init = False
    else:
        prices = attribute_history(security, g.N, '1d', ['high', 'low'])
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
    df = get_fundamentals(query(valuation.code,valuation.pb_ratio,indicator.roe))
    df = df[(df['roe']>0) & (df['pb_ratio']>0)].sort('pb_ratio')
    df.index = df['code'].values
    df['1/roe'] = 1/df['roe']
    df['point'] = df[['pb_ratio','1/roe']].rank().T.apply(f_sum)
    df = df.sort('point')
    pool = df.index
    log.info('总共选出%s只股票'%len(pool))
    cash = context.portfolio.total_value/g.stock_num 
    hold_stock = context.portfolio.positions.keys() 
    for s in hold_stock:
        if s not in pool:
            order_target(s,0)
    industry_set = ['HY001', 'HY002', 'HY003', 'HY004', 'HY005', 'HY006', 'HY007', 'HY008', 'HY009', 
              'HY010', 'HY011']
    for s in pool:
        bIndustryRepeat = False
        for j in context.portfolio.positions.keys():
            for k in industry_set:
                industry = get_industry_stocks(k, date = None)
                if (s in industry) and (j in industry):
                    bIndustryRepeat = True
        if not bIndustryRepeat:
            order_target_value(s,cash)
        if len(context.portfolio.positions.keys()) == g.stock_num:
            break
def f_sum(x):
    return sum(x)
def after_market_close(context):
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    log.info('今日账户总资产：%s'%round(context.portfolio.total_value,2))