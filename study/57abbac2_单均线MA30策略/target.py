# Clone from JoinQuant
# postId: 57abbac20a8584f8ef8f8e0e10ebb489
# backtestId: 383f8adfaf82c91a916e0cb420fffa7b
# title: 年化15.84%的单均线策略


def initialize(context):
    # 定义一个全局变量, 保存要操作的股票
    # 000001(股票:平安银行)
    g.security = '000016.XSHG'
    
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)t
    set_option('use_real_price', True)
    run_daily(fun2, time='14:53')

def fun2(context):
    security = g.security
    security1 = '510050.XSHG'
    close_data = attribute_history(security, 30, '1d', ['close'])
    MA30 = close_data['close'].mean()
    current_price = close_data['close'][-1]
    cash = context.portfolio.cash

    
    if current_price > 1.02*MA30:
        order_value(security1, cash)
        log.info("Buying %s" % (security1))
    elif current_price < 0.95*MA30 and context.portfolio.positions[security1].closeable_amount > 0:
        order_target(security1, 0)
        log.info("Selling %s" % (security1))
    
    