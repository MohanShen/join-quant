# Clone from JoinQuant
# postId: df7e3966b111970452d8e5e431761400
# backtestId: 81c543989fb628fd469c60f94481bbf3
# title: 网格交易策略，执行报错，请大佬看看要怎么修改

# 导入函数库
# 导入聚宽函数库
from jqdata import *

# 初始化此策略
def initialize(context):
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 设置股票池为山东路桥
    g.security = '000498.XSHE'
    # 设置网格上限和下限
    g.upper_limit = 7.5
    g.lower_limit = 4.5
    # 设置网格间隔
    g.grid_space = 0.1
    # 设置每份股数
    g.share_per_grid = 500
    # 设置底仓股数
    g.base_position = 100000 // 6
    # 每天开盘前运行
    run_daily(before_market_open, time='before_open', reference_security=g.security)

# 每天开盘前运行的函数
def before_market_open(context):
    # 获取当前股价
    current_price = attribute_history(g.security, 1, '1d', ['close'])['close'][0]
    # 计算底仓资金
    base_position_value = g.base_position * 6
    # 计算额外购买资金
    extra_cash_needed = (g.upper_limit - g.lower_limit) / g.grid_space * g.share_per_grid * 6
    # 总资金需求
    total_cash_needed = base_position_value + extra_cash_needed
    # 打印总资金需求
    log.info("Total cash needed: {:.2f}".format(total_cash_needed))

# 每分钟运行的函数
def handle_data(context, data):
    # 获取当前股价
    current_price = data[g.security].close
    # 检查是否在网格范围内
    if current_price <= g.upper_limit and current_price >= g.lower_limit:
        # 计算当前股价所在的网格
        grid_number = int((current_price - g.lower_limit) / g.grid_space)
        # 计算当前网格的价格
        grid_price = g.lower_limit + grid_number * g.grid_space
        # 检查是否需要买入或卖出
        if current_price < grid_price:
            # 买入操作
            order(g.security, g.share_per_grid)
            log.info("Buy {} shares of {}".format(g.share_per_grid, g.security))
        elif current_price > grid_price:
            # 卖出操作
            order(g.security, -g.share_per_grid)
            log.info("Sell {} shares of {}".format(g.share_per_grid, g.security))