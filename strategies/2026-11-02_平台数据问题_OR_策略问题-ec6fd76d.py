# Clone from JoinQuant
# postId: ec6fd76ded67745d4ea9cc863c893dd0
# backtestId: badfcdd4d808a87da3fef137ca95cc89
# title:  平台数据问题 OR 策略问题？

def initialize(context): #初始化
    set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))# 设置手续费率
    set_benchmark('000300.XSHG')        # 设置基准指数：沪深300指数 '000300.XSHG'
    g.period = 1                    # 调仓频率，单位：日
    g.days = 0                      # 调仓计时器，单位：日
    g.selected_stock_count = 100    # 备选股票数量
    g.buy_stock_count = 10          # 买入股票数量
    g.trade_time = '09:35'          # 每天调仓执行时间
    run_daily(trade, g.trade_time)  # 每日定时交易
    # handle_data每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次
def handle_data(context, data): 
    pass
    ''' 获取前n个单位时间当时的收盘价 '''
def get_close_price(security, n, unit='1d'):
    return attribute_history(security, n, unit, ('close'), True)['close'][0]
def filter_problem_stock(stock_list):#过滤停牌及ST类股票
    curr_data = get_current_data()
    return  [stock for stock in stock_list if not curr_data[stock].paused and 
        not curr_data[stock].is_st and 'ST' not in curr_data[stock].name and
        '*' not in curr_data[stock].name and '退' not in curr_data[stock].name]
def trade(context):
    if g.days % g.period == 0:
        buy_stocks = select_stocks(context)
        rebalance_positions(context, buy_stocks)
    g.days += 1
    if g.days>=g.period : g.days = 0
def select_stocks(context):
    qvaule = query(
        valuation.code, valuation.circulating_market_cap,
        ).order_by(valuation.circulating_market_cap.asc()
        ).filter(
        valuation.circulating_market_cap <= 150) 
    df = get_fundamentals(qvaule)
    stock_list = filter_problem_stock(list(df['code'])) # 过滤ST *ST 退市股票
    stock_list = stock_list[:g.buy_stock_count]         # 选取指定数量股票

    filter_stocks = []
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    curr_data = get_current_data()
    for stock in stock_list:
        if stock not in context.portfolio.positions.keys():
            if last_prices[stock][-1] < curr_data[stock].high_limit:
                filter_stocks.append(stock)

    stock_list= filter_stocks
    return stock_list;
def rebalance_positions(context, buy_stocks):
    position = context.portfolio.positions
    last_prices = history(1, unit='1m', field='close', security_list=position.keys())
    curr_data = get_current_data()
    for stock in position.keys():   
        if stock not in buy_stocks:
            if last_prices[stock][-1] < curr_data[stock].high_limit:
                order_target_value(stock, 0)
# 按股票数量分仓,根据可用金额平均分配购买
    position = context.portfolio.positions
    buy_stock_count = g.buy_stock_count - len(position)
    if buy_stock_count>0:
        value = context.portfolio.cash / buy_stock_count
        i = 0
        for stock in buy_stocks:
            if position[stock].total_amount == 0 :
                i += 1
                order_target_value(stock, value)
                if i>= buy_stock_count: break

    
    



