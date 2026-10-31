# Clone from JoinQuant
# postId: a73e6945fe5d1ae66ed8953c21fd6fe1
# backtestId: b665c1f5996f36a07581a60713555655
# title: 请教下如何得到MACD,KDJ这样指标的API,谢谢

# 定义一个全局变量, 保存要操作的证券
# 000001(股票:平安银行)
security = '000001.XSHE'
# 初始化此策略
# 设置我们要操作的股票池, 这里我们只操作一支股票
set_universe([security])

# 每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)调用一次
def handle_data(context, data):
    # 取得过去五天的平均价格
    average_price = data[security].mavg(5)
    # 取得当前价格
    current_price = data[security].price
    # 取得当前的现金
    cash = context.portfolio.cash

    # 如果当前价格高出五天平均价1%, 则全仓买入
    if current_price > 1.01*average_price:
        # 计算可以买多少只股票
        number_of_shares = int(cash/current_price)
        # 购买量大于0时，下单
        if number_of_shares > 0:
            # 买入股票
            order(security, +number_of_shares)
            # 记录这次买入
            log.info("Buying %s" % (security))
    # 如果当前价格低于五天平均价, 则空仓卖出
    elif current_price < average_price and context.portfolio.positions[security].amount > 0:
        # 卖出所有股票,使这只股票的最终持有量为0
        order_target(security, 0)
        # 记录这次卖出
        log.info("Selling %s" % (security))
    # 画出当前的价格
    record(stock_price=data[security].price)
