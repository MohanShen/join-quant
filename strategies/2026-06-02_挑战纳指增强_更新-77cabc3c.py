# Clone from JoinQuant
# postId: 77cabc3c180e77700dc170c7fec07907
# backtestId: fc1782f0a5a3a5e1182ec36721253377
# title: 挑战纳指增强（更新）

# 导入函数库
from jqdata import *

# 初始化函数，设定基准等
def initialize(context):
    # 设定比较基准
    set_benchmark('513100.XSHG') #纳指ETF100
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 开启避免未来数据模式
    set_option("avoid_future_data", True)
    
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')

    # 设置交易手续费
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')

    # 全局变量
    g.security = '513100.XSHG'  # 操作标的
    g.length = 10               # 支撑和阻力位计算长度
    g.sensitivity = 0.05       # 灵敏度
    g.stop_loss_pct = 0.5      # 止损百分比
    g.take_profit_pct = 0.2   # 止盈百分比

    # 每天开盘时运行
    run_daily(market_open, time='open')

# 开盘时运行函数
def market_open(context):
    log.info('函数运行时间(market_open): ' + str(context.current_dt.time()))
    security = g.security

    # 获取历史数据
    hist_data = get_bars(security, count=g.length, unit='1d', fields=['open', 'high', 'low', 'close'])

    # 计算支撑位和阻力位
    support = min(hist_data['low'])
    resistance = max(hist_data['high'])

    # 当前K线数据
    current_open = hist_data['open'][-1]
    current_high = hist_data['high'][-1]
    current_low = hist_data['low'][-1]
    current_close = hist_data['close'][-1]

    # 判断K线形态
    def is_hammer():
        body = current_close - current_open
        price_range = current_high - current_low
        lower_shadow = current_open - current_low
        upper_shadow = current_high - current_close
        return body > 0 and lower_shadow > body * 2 and upper_shadow < body * 0.5 and price_range > 0

    def is_shooting_star():
        body = current_open - current_close
        price_range = current_high - current_low
        lower_shadow = current_close - current_low
        upper_shadow = current_high - current_open
        return body > 0 and upper_shadow > body * 2 and lower_shadow < body * 0.5 and price_range > 0

    def is_doji():
        body = current_close - current_open
        price_range = current_high - current_low
        return abs(body) < (price_range * 0.1)  

    def is_pin_bar():
        body = current_close - current_open
        price_range = current_high - current_low
        lower_shadow = current_open - current_low
        upper_shadow = current_high - current_close
        return (upper_shadow > body * 2 and lower_shadow < body * 0.5) or (lower_shadow > body * 2 and upper_shadow < body * 0.5)

    # 买入条件：锤子线、十字星或Pin Bar，且价格接近支撑位
    long_condition = (is_hammer() or is_doji() or is_pin_bar()) and current_close <= support * (1 + g.sensitivity)

    # 卖出条件：射击之星、十字星或Pin Bar，且价格接近阻力位
    short_condition = (is_shooting_star() or is_doji() or is_pin_bar()) and current_close >= resistance * (1 - g.sensitivity)

    # 执行买入操作
    if long_condition and context.portfolio.positions[security].total_amount == 0:
        log.info("买入条件满足，买入 %s" % security)
        order_value(security, context.portfolio.available_cash)  # 全仓买入
        # 设置止盈和止损
        g.avg_price_long = current_close  # 记录买入均价
        g.long_stop_level = g.avg_price_long * (1 - g.stop_loss_pct)
        g.long_take_profit_level = g.avg_price_long * (1 + g.take_profit_pct)

    # 执行卖出操作
    elif short_condition and context.portfolio.positions[security].total_amount == 0:
        log.info("卖出条件满足，卖出 %s" % security)
        order_target(security, 0)  # 清仓卖出
        # 设置止盈和止损
        g.avg_price_short = current_close  # 记录卖出均价
        g.short_stop_level = g.avg_price_short * (1 + g.stop_loss_pct)
        g.short_take_profit_level = g.avg_price_short * (1 - g.stop_loss_pct)

    # 止盈止损逻辑
    if security in context.portfolio.positions:
        position = context.portfolio.positions[security]
        if position.total_amount > 0:  # 多头持仓
            if current_close <= g.long_stop_level or current_close >= g.long_take_profit_level:
                log.info("触发止盈/止损，卖出 %s" % security)
                order_target(security, 0)  # 清仓卖出

# 收盘后运行函数
def after_market_close(context):
    log.info('函数运行时间(after_market_close): ' + str(context.current_dt.time()))
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：' + str(_trade))
    log.info('一天结束')
    log.info('##############################################################')