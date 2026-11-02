# Clone from JoinQuant
# postId: 1d43f5be8b7164a047c4f1feeb4125ca
# backtestId: 86010ad42d75829a0ec1790c417b09ce
# title: 请问今天50ETF盘中价格怎么不正常？

def initialize(context):
    # 定义一个全局变量, 保存要操作的股票
    # 设立基准为沪深300
    set_benchmark("000300.XSHG")
    # 初始化此策略
    # 设置我们要操作的股票池
    g.stocks=["510050.XSHG","159915.XSHE","518880.XSHG","513500.XSHG"]
    g.stock_last=maxstock(g.stocks)
    run_weekly(peroid, -1,"14:50")
# 每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)调用一次

def peroid(context):
    stock=maxstock(g.stocks)
    #current_price = history(1, '1m', 'close', stock, df=False,skip_paused=True).get(stock)[0]
    if incre_rate(stock,20)<0 :#or current_price<MA(stock,20)
        clear_out(context)
    #log.info("last stockC is %s and stock is %s",g.stock_last,stock)
    #log.info("inc of stockC is %s and inc of last is %s",incre_rate(stock,20),incre_rate(g.stock_last,20))
    if stock<>g.stock_last:
        #log.info("last stockA is %s and stock is %s",g.stock_last,stock)
        #log.info("inc of stockA is %s and inc of last is %s",incre_rate(stock,20),incre_rate(g.stock_last,20))
        if incre_rate(stock,20)>0 and incre_rate(stock,20)-incre_rate(g.stock_last,20)>0.01:
            #log.info("last stock is %s and stock is %s",g.stock_last,stock)
            #log.info("inc of stock is %s and inc of last is %s",incre_rate(stock,20),incre_rate(g.stock_last,20))
            if stock not in context.portfolio.positions:
                if g.stock_last in context.portfolio.positions:
                    order_target(g.stock_last, 0)
                    log.info("Sell %s : ", g.stock_last)
                cash = context.portfolio.cash
                log.info("Cash : %s ", cash)
                order_value(stock, cash)
                log.info("Buy : %s", stock)
            g.stock_last=stock
            #log.info("last stockA is %s",g.stock_last)
    else:
        #log.info("last stock and stock is %s",stock)
        #log.info("inc of stockB is %s and inc of last is %s",incre_rate(stock,20),incre_rate(g.stock_last,20))
        if incre_rate(stock,20)>0 and stock not in context.portfolio.positions:
            cash = context.portfolio.cash
            log.debug("Cash : %s ", cash)
            order_value(stock, cash)
            log.info("Buy : %s", stock)

def incre_rate(stock, days):
    h1 = attribute_history(stock, days-1, '1d', 'close',skip_paused=True)
    h2 = attribute_history(stock, days, '1d', 'close',skip_paused=True)
    h3 = attribute_history(stock, days+1, '1d', 'close',skip_paused=True)
    h=(h1["close"][0]+h2["close"][0]+h3["close"][0])/3
    current_price = history(1, '1m', 'close', stock, df=False,skip_paused=True).get(stock)[0]
    # log.info("current price of %s : %s", stock, current_price)
    i_rate = (current_price - h)/h
    # log.info("close price of %s %s days ago: %s", stock, days, h)
    # log.info("increase rate : %s", i_rate)
    return i_rate

def maxstock(stocks):
    stock=stocks[0]
    for n in range(len(stocks)):
        if incre_rate(stocks[n],20)>incre_rate(stock,20):
            stock=stocks[n]
    return stock

#def MA(stock, days):
#    return history(days, '1d', 'close', [stock], df=False,skip_paused=True)[stock].mean()
    
def clear_out(context):
    for p in context.portfolio.positions:
        order_target(p, 0)