# Clone from JoinQuant
# postId: 3ae4f4be4eebde66bf1a0c460092fdf3
# backtestId: 8853246ce7d3ef3e26d01d17f325ad3d
# title: 在回测交易过程中，发现有股票停牌一段时间后就退市，可是股票还在持仓中，无法卖出，怎么处理呢？

def initialize(context):
    # 定义一个全局变量, 保存要操作的股票
    # 000001(股票:平安银行)
    g.security = '000562.XSHE'
    # 初始化此策略
    # 设置我们要操作的股票池, 这里我们只操作一支股票
    set_universe(g.security)

# 每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)调用一次
def handle_data(context, data):
    security = g.security
    #stock_name = get_security_info('000333.XSHE').display_name
    #log.info("股票简称：%s"%stock_name)
    # 得到五日均线价格
    ma5 = data[security].mavg(5, 'close')
    # 得到十日均线价格
    ma10 = data[security].mavg(10, 'close')
    # 取得昨天收盘价
    price = data[security].close
    # 得到当前资金余额
    cash = context.portfolio.cash

    # 如果当前有余额，并且五日均线大于十日均线
    if ma5 > ma10:
        # 用所有 cash 买入股票
        order_value(security, cash)
        # 记录这次买入
        log.info("Buying %s" % (security))

        # 如果五日均线小于十日均线，并且目前有头寸
        #elif ma5 < ma10 and context.portfolio.positions[security].sellable_amount > 0:
            # 全部卖出
            #order_target(security, 0)
            # 记录这次卖出
            #log.info("Selling %s" % (security))
    
#每个交易日结束运行
def after_trading_end(context):
    #得到当天所有订单
    #orders = get_orders()
    #for stock in context.portfolio.positions.keys():
        #for _order in orders.values():
             #log.info(_order.filled)
    #pass
    holdlist = context.portfolio.positions.keys()
    log.info("当前持仓个股列表为：%s"%holdlist)



