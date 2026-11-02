# Clone from JoinQuant
# postId: a2cebe66e0a1fddc60d2414de130d0f4
# backtestId: 82c52633e90421c879255338e07b767c
# title: 求帮助写策略~我想运行一下看看结果。谢谢各位~

'''
双均线策略，当五日均线位于十日均线上方则买入，反之卖出。
'''

## 初始化函数，设定要操作的股票、基准等等
def initialize(context):
    # 定义一个全局变量, 保存要操作的股票
    # 000002(股票:万科A)
    g.security = '000002.XSHE'
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # True为开启动态复权模式，使用真实价格交易
    set_option('use_real_price', True) 
    # 设定成交量比例
    set_option('order_volume_ratio', 1)
    # 股票类交易手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, \
                             open_commission=0.0003, close_commission=0.0003,\
                             close_today_commission=0, min_commission=5), type='stock')
    # 运行函数
    run_daily(trade, 'every_bar')

## 交易程序
def trade(context):
    security = g.security
    # 设定均线窗口长度
    n1 = 5
    n2 = 10
    # 获取股票的收盘价
    close_data = attribute_history(security, n2+2, '1d', ['close'],df=False)
    # 取得过去 ma_n1 天的平均价格
    ma_n1 = close_data['close'][-n1:].mean()
    # 取得过去 ma_n2 天的平均价格
    ma_n2 = close_data['close'][-n2:].mean()
    # 取得当前的现金
    cash = context.portfolio.cash

    # 如果当前有余额，并且n1日均线大于n2日均线
    if ma_n1 > ma_n2:
        # 用所有 cash 买入股票
        order_value(security, cash)
        # 记录这次买入
        log.info("Buying %s" % (security))

    # 如果n1日均线小于n2日均线，并且目前有头寸
    elif ma_n1 < ma_n2 and context.portfolio.positions[security].closeable_amount > 0:
        # 全部卖出
        order_target(security, 0)
        # 记录这次卖出
        log.info("Selling %s" % (security))

    # 绘制n1日均线价格
    record(ma_n1=ma_n1)
    # 绘制n2日均线价格
    record(ma_n2=ma_n2)