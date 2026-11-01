# Clone from JoinQuant
# postId: b360f946a9001efef27c8275184ce420
# backtestId: 1755739e853bfa30fe254b765b944a4e
# title: 求助 ，请帮我看看那里出问题了。

def initialize(context):
    g.daily_buy_count=10
    stocks = list(get_all_securities(['stock']).index)
    set_universe(stocks)
    
    run_daily(morning_sell_all,'open')
    
    
def morning_sell_all(context):
    for security in context.portfolio.positions:
        order_target(security,0)
        log.info("selling%s"%(security))
def before_trading_start(context):
    g.today_bought_stocks=set()
    g.last_df=history(1,'1d','close')
    
def handle_data(context, data):
    if context.current_dt.hour>11:
        return
    if len(g.today_bought_stocks)>=g.daily_buy_count:
        return
    for security in (g.stocks-g.today_bought_stocks):
        price=data[security].close
        last_close=g.last_df[security][0]
        if price/last_close>1.095 \
            and price/last_close<1.099\
            and data[security].high_limit-last_close>=1:
            cash=context.portfolio.cash
            need_count=g.daily_buy_count-len(g.today_bought_stocks)
            buy_cash=context.portfolio.cash/need_count
            order_value(security,buy_cash)
            g.today_bought_stocks.add(security)
            log.info("buying %s"%(security))
            if len(g.today_bought_stocks)>=g.daily_buy_count:
                break
            
        
    