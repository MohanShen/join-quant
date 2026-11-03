# Clone from JoinQuant
# postId: 00ecbaa398a355359a85ca5081c04db5
# backtestId: e944c474b89f923cf0d998e43352003a
# title: create_backtest能否改变security数值？

# 导入函数库
def initialize(context):
    # 定义一个全局变量, 保存要操作的股票
    # 000001(股票:平安银行)
    g.security = '000007.XSHE'
    # 初始化此策略
    # 设置我们要操作的股票池, 这里我们只操作一支股票
    set_universe([g.security])
    # 设置均线长度
    g.ma_long = 5
    g.m = 1.01

# 每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)调用一次
def handle_data(context, data):
    security = g.security
    # 取得过去五天的平均价格
    average_price = data[security].mavg(g.ma_long, 'close')
    # 取得上一时间点价格
    current_price = data[security].close
    # 取得当前的现金
    cash = context.portfolio.cash

    # 如果上一时间点价格高出五天平均价1%, 则全仓买入
    if current_price > g.m*average_price:
        # 用所有 cash 买入股票
        order_value(security, cash)
        # 记录这次买入
        log.info("Buying %s" % (security))
    # 如果上一时间点价格低于五天平均价, 则空仓卖出
    elif current_price < average_price and context.portfolio.positions[security].sellable_amount > 0:
        # 卖出所有股票,使这只股票的最终持有量为0
        order_target(security, 0)
        # 记录这次卖出
        log.info("Selling %s" % (security))
    # 画出上一时间点价格
    record(stock_price=current_price)