# Clone from JoinQuant
# postId: c00eaff6850a2850e9824962a596a269
# backtestId: 1efa4b14ac3014665487eacbc7fddedf
# title: 【一个简单的趋势线策略，编译出错】【请大神指点】

# 导入聚宽函数库
import jqdata

# 初始化函数，设定要操作的股票、基准等等
def initialize(context):
    # 定义一个全局变量, 保存要操作的股票
    # 000001(股票:平安银行)
    g.security = '000001.XSHE'
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)

# 每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)调用一次
def handle_data(context, data):
    security = g.security
    # 获取股票的收盘价
    close_data = attribute_history(security, 10, '1d', ['close'],df=False)
    # 取得过去五天的平均价格
    ma5 = close_data['close'][-5:].mean()
    # 取得过去10天的平均价格
    ma10 = close_data['close'].mean()
    # 取得当前的现金
    cash = context.portfolio.cash

    # 如果当前有余额，并且五日均线大于十日均线
    if ma5 > ma10:
        # 用所有 cash 买入股票
        order_value(security, cash)
        # 记录这次买入
        log.info("Buying %s" % (security))

    # 如果五日均线小于十日均线，并且目前有头寸
    elif ma5 < ma10 and context.portfolio.positions[security].closeable_amount> 0:
        # 全部卖出
        order_target(security, 0)
        # 记录这次卖出
        log.info("Selling %s" % (security))

    # 绘制五日均线价格
    record(ma5=ma5)
    # 绘制十日均线价格
    record(ma10=ma10)