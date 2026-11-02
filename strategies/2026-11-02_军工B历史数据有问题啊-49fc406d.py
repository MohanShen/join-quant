# Clone from JoinQuant
# postId: 49fc406da85c7f0b67df5963356a311d
# backtestId: 1209f188fc0360f217c6afa60dce7e58
# title: 军工B历史数据有问题啊

def initialize(context):
    g.security = '150182.XSHE'   # 军工B
    set_universe([g.security])

def handle_data(context, data):
    security = g.security
    index = '399967.XSHE'   # 中证军工

    a5 = data[security].mavg(5)
    a10 = data[security].mavg(10)
    
    b5 = data[index].mavg(5)
    b10 = data[index].mavg(10)
    
    current_price = data[security].price
    cash = context.portfolio.cash
    today = context.current_dt.day

    if b5 > b10 and today < 25: # 五日线大于十日线买入
        if cash > 100 * current_price:
            order_value(security, cash)
    elif current_price < a5:    # 卖出要敏感一些
        if context.portfolio.positions[security].amount > 0:
            print('清仓')
            order_target(security, 0)

    record(stock_price=data[security].price)
