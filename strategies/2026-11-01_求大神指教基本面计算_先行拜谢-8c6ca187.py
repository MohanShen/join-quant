# Clone from JoinQuant
# postId: 8c6ca187e23335b3a19e449d4d9e649f
# backtestId: d46cb7a38aca23355703d05cd69fcf04
# title: 求大神指教基本面计算！！先行拜谢

# 克隆自聚宽文章：https://www.joinquant.com/post/3809
# 标题：均线策略-沪深300指数5日vs60日均线，策略年化收益 24.49%，是一个可以实际采用的策略吗？
# 作者：秦岭

def initialize(context):
    # 设置操作对象和参考标准
    g.security = '601668.XSHG'
    set_benchmark('601668.XSHG')
    # 设置手续费，指数基金的手续费设置为万一, 每笔交易最低扣5块钱
    set_commission(PerTrade(buy_cost=0.0001, sell_cost=0.0001, min_cost=5))
    # 千分之一的滑点费用
    set_slippage(FixedSlippage(0.001))

# 按天回测
def handle_data(context, data):
    security = g.security
    # 获取股票的收盘价
    close_data = attribute_history(security, 120, '1d', ['close'],df=False)
    # 取得过去5天的平均价格
    ma5 = close_data['close'][-5:].mean()
    # 取得过去60天的平均价格
    ma120= close_data['close'].mean()
    # 取得当前的现金
    cash = context.portfolio.available_cash
    
    #如果5日均线大于60日均线，所有资金买入
    if (ma5 > ma120):
        # 用所有 cash 买入股票
        order_value(security, cash)
        # 记录这次买入
        log.info("Buying %s" % (security))
    # 画出当前的价格
    #record(current_price = data[security].price)