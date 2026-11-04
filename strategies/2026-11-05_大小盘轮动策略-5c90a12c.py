# Clone from JoinQuant
# postId: 5c90a12c8440f65b7e675928ee0e24cf
# backtestId: e13958f106c4efe7051a4a7daa31bffb
# title: 大小盘轮动策略

# 可以自己import我们平台支持的第三方python模块，比如pandas、numpy等。
import pandas
import datetime as dt
# 在这个方法中编写任何的初始化逻辑。context对象将会在你的算法策略的任何方法之间做传递。
def initialize(context):
    
    set_option('use_real_price', True)
    # 设置手续费，买入时万分之三，卖出时千分之1.3（含了千分之1的印花税）, 每笔交易最低扣5块钱
    set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
    #设置买卖总滑点为千分之三，系统默认的滑点是PriceRelatedSlippage(0.00246)
    set_slippage(PriceRelatedSlippage(0.003))

    g.small = 120
    g.big = 120
    g.ma_day = 20
    g.rate=[]
    #run_daily(update)
    run_daily(reselect)
    
    
def before_trading_start(context):

    date = context.current_dt.strftime("%Y-%m-%d")
    stocks = get_all_securities(['stock'],date = date)
    stocks = list(stocks.index)
    
    #小市值
    q_small = query(
    valuation.code,
    valuation.circulating_market_cap
    ).filter(
    valuation.code.in_(stocks),
    ).order_by(valuation.circulating_market_cap.asc()
    ).limit(g.small*3)
    #.limit(g.small*3)
    
    df_small = get_fundamentals(q_small)
    g.stocks_small = df_small.code
    
    #大市值
    q_big = query(
    valuation.code,
    valuation.circulating_market_cap
    ).filter(
    valuation.code.in_(stocks),
    ).order_by(valuation.circulating_market_cap.desc()
    ).limit(g.big*3)
    #.limit(g.big*3)
    
    df_big = get_fundamentals(q_big)
    g.stocks_big = df_big.code
    
    
def no_pause_zt_dt(stockspool):
    current_data=get_current_data()
    return [s for s in stockspool if (
    	not current_data[s].paused) and (
    	current_data[s].day_open < current_data[s].high_limit*0.995) and (
    	current_data[s].day_open > current_data[s].low_limit*0.995)]
    
    
# 剔除上市时间较短的产品
def fun_delNewShare(context, equity, deltaday):
    deltaDate = context.current_dt.date() - dt.timedelta(deltaday)

    tmpList = []
    for stock in equity:
        if get_security_info(stock).start_date < deltaDate:
            tmpList.append(stock)

    return tmpList
    
    
def update(context):
    stocks_big=[]
    stocks_small=[]
    stocks_b=0
    stocks_s=0
    #过滤停牌和涨跌停：
    print('11111',len(g.stocks_big),len(g.stocks_small))
    g.stocks_big = no_pause_zt_dt(g.stocks_big)
    g.stocks_small = no_pause_zt_dt(g.stocks_small)
    print('22222',len(g.stocks_big),len(g.stocks_small))
    #剔除上市不足60天的股票：
    g.stocks_big = fun_delNewShare(context, g.stocks_big, 60)
    g.stocks_small = fun_delNewShare(context, g.stocks_small, 60)
    print('33333',len(g.stocks_big),len(g.stocks_small))
    #剔除st
    date = context.current_dt.strftime("%Y-%m-%d")
    st=get_extras('is_st', g.stocks_big, start_date=date, end_date=date, df=True)
    st=st.loc[date]
    g.stocks_big=list(st[st==False].index)[0:g.big]
    
    st=get_extras('is_st', g.stocks_small, start_date=date, end_date=date, df=True)
    st=st.loc[date]
    g.stocks_small=list(st[st==False].index)[0:g.small]
    print('444444',len(g.stocks_big),len(g.stocks_small))
    
    
    for stock in g.stocks_big:
        stocks_b = stocks_b + 1
        ma = history(g.ma_day, unit='1d',field='close', security_list=stock, df=True).mean()
        close = history(1, unit='1d', field='close', security_list=stock,df=False)
        if  close[stock] > ma[stock]:
            stocks_big.append(stock)
            #stock_big = stocks_big[0:g.big]
   
    
    for stock in g.stocks_small:
        stocks_s = stocks_s + 1
        ma = history(g.ma_day, unit='1d',field='close', security_list=stock, df=True).mean()
        close = history(1, unit='1d', field='close', security_list=stock,df=False)
        if  close[stock] > ma[stock]:
            stocks_small.append(stock)
            #stocks_small = stocks_small[0:g.small]
    
    print('55555555',len(stocks_big),len(stocks_small),stocks_b,stocks_s)

    b=float(len(stocks_big))/float(stocks_b)
    s=float(len(stocks_small))/float(stocks_s)
    print('b',b)
    print('s',s)
    #这两个择时条件作用比较大
    g.stocks=[]
    if (b>s)and (b>0.5):
        g.stocks=stocks_big
        g.rate=b
    elif (s>=b) and (s>0.5):
        g.stocks=stocks_small
        g.rate=s

    #下面的择时条件作用相对较小
    price_20return_total = 0
    price_20return = []
    for stock in g.stocks:
        price = history(g.ma_day, '1d', 'close', stock, df = False)
        price_20return = price[stock][19]/price[stock][0]
        price_20return_total = price_20return_total + price_20return
    print('price_20return_total',price_20return_total)    
    
    if price_20return_total < len(g.stocks):
        print('len(g.stocks)',len(g.stocks))
        g.stock = []
    
    
def get_holdings(context):

    holdings = []
    if context.portfolio.positions.keys() !=[]:
        for stock in context.portfolio.positions.keys():
            if context.portfolio.positions[stock].total_amount > 0:
                holdings.append(stock)
                
    return holdings
    
    
def get_trading_stocks(context,to_buy):
    trading_stocks = []
    for stock in to_buy:
        trading_stocks.append(stock)
        
    return trading_stocks
    
    
def reselect(context):
    update(context)
    stocks = set(g.stocks)
    holdings = set(get_holdings(context))
    
    to_buy = stocks - holdings
    to_sell = holdings - stocks
    current_data=get_current_data()
    
    for stock in to_sell:
        if not current_data[stock].paused and \
        context.portfolio.positions[stock].sellable_amount > 0:
            order_target_value(stock,0)
            
    if len(to_buy) == 0:
        return
    
    to_buy = get_trading_stocks(context,to_buy)
    
    if len(to_buy) > 0:
        average_value = context.portfolio.portfolio_value/len(to_buy)
    
    for stock in to_buy:
        if context.portfolio.cash > average_value:
            order_target_value(stock, average_value)
    
    

