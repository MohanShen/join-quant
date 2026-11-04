# Clone from JoinQuant
# postId: 7606d2d71fbd9e8d34f7cdc0784c1caf
# backtestId: d8ef285c3aa60a529128b40e26dead81
# title: 单均线策略【5日】2007-2016 深证指数基金

def initialize(context):
    # 定义一个全局变量, 保存要操作的股票
    # 000001(股票:平安银行)
    g.security = '159901.XSHE'
    # 初始化此策略
    # 设置我们要操作的股票池, 这里我们只操作一支股票
    set_universe([g.security])
    set_benchmark('000001.XSHG')
# 每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)调用一次
def handle_data(context, data):
    security = g.security
    # 取得过去五天的平均价格
    average_price = data[security].mavg(5)
    # 取得上一时间点价格
    current_price = data[security].price
    # 取得当前的现金
    cash = context.portfolio.cash

    # 如果上一时间点价格高出五天平均价1%, 则全仓买入
    if current_price > 1.01*average_price:
        # 计算可以买多少只股票
        number_of_shares = int(cash/current_price)
        # 购买量大于0时，下单
        if number_of_shares > 0:
            # 买入股票
            order(security, +number_of_shares)
            # 记录这次买入
            log.info("Buying %s" % (security))
    # 如果上一时间点价格低于五天平均价, 则空仓卖出
    elif current_price < average_price and context.portfolio.positions[security].amount > 0:
        # 卖出所有股票,使这只股票的最终持有量为0
        order_target(security, 0)
        # 记录这次卖出
        log.info("Selling %s" % (security))
    # 画出上一时间点的价格
    record(stock_price=data[security].price)
