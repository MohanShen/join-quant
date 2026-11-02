# Clone from JoinQuant
# postId: ace8d89ecd7fc2a3fe08b274c6f50f1d
# backtestId: ce097a8c6db3a26f77368faeb054e8c2
# title: 当天卖出股票的钱，当天不能再买进？

def initialize(context):
    # 定义一个全局变量, 保存要操作的股票
    # 000001(股票:平安银行)
    g.security = '000001.XSHE'
    # 初始化此策略
    # 设置我们要操作的股票池, 这里我们只操作一支股票
    set_universe(g.security)
    

# 每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)调用一次
def handle_data(context, data):
    security = g.security
    # 取得当前的现金
    cash = context.portfolio.cash

    order_target('000001.XSHE', 0)
    order_value('000001.XSHE', cash)
