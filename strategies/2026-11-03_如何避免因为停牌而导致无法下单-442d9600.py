# Clone from JoinQuant
# postId: 442d9600b7ac8e37b1dfe97e205c84a0
# backtestId: 7229aa5d13da8e421d017133bc38b78a
# title: 如何避免因为停牌而导致无法下单？

# 定义一个全局变量, 保存要操作的证券
security = '002230.XSHE'
set_benchmark('002230.XSHE')
g.org_cost=0
# 初始化此策略
# 设置我们要操作的股票池
set_universe([security])
# 设定基准
# set_benchmark(benchmark)
# 设定手续费
set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
# 设定滑点
set_slippage(FixedSlippage(0))
Closemean = [0]
Current_close = [0]

# 每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)调用一次
def handle_data(context, data):
    count=30
    # 回测T时间，取得T-1……T-5过去n天的收盘价
    close_price =history(count, unit='1d', field='close', security_list=None)
    closemean=close_price[security].mean()
    Closemean.append(closemean)
    # 回测T时间，取得T-1的收盘价
    current_close = data[security].close
    Current_close.append(current_close)
    # 取得T-1日平均价格
    current_price = data[security].price
    # 取得当前的现金
    cash = context.portfolio.cash
    # T-2日收盘价 < T-2日的均线 and  T-1日收盘价 > T-1日的均线, 则全仓买入
    if Current_close[-2] < Closemean[-2] and Current_close[-1] > Closemean[-1] and data[security].paused==False:
        # 计算可以买多少只股票
        number_of_shares = int(cash/current_price)
        # 购买量大于0时，下单
        if number_of_shares > 0:
            # 以市单价买入股票，日回测时即是开盘价
            order(security, +number_of_shares)
            # 记录这次买入
            log.info("Buying %s" % (security))
            log.info("Buying %f" % (current_price))
            g.org_cost=context.portfolio.positions_value
    # T-1日收盘价 < T-1日的均线, 则空仓卖出
    elif Current_close[-1] < Closemean[-1] and context.portfolio.positions[security].amount > 0:
       #  and context.portfolio.positions[security].amount*current_price>g.org_cost:
        log.info("T-1日收盘价 %f" % ((Current_close[-1])))
        log.info("T-1日的均线 %f" % (Closemean[-1]))
        log.info("sell price %f" % (current_price))  
        # 卖出所有股票,使这只股票的最终持有量为0
        order_target(security, 0)
       # order_target(security, 0, LimitOrderStyle(current_price))
        # 记录这次卖出
        log.info("Selling %s" % (security))
        log.info("Total cash %s" % (context.portfolio.cash))
    # 画出当前的价格
    record(stock_price=data[security].close)
    record(avg_price=closemean)