# Clone from JoinQuant
# postId: 64dfbd8c126c0427c14cca37a21f05d4
# backtestId: e182b22352f9bc9d44096002b5b45e10
# title: 回测收益率为0问题

from jqdata import *
import talib as ta
import numpy as np

def initialize(context):
    # 策略参数设置
    set_params(context)    # 1. 设置参数
    set_variables()         # 2. 设置中间变量
    set_backtest()          # 3. 设置回测条件
     # 设置期货保证金比例（PVC通常为10%）
    set_option('futures_margin_rate', 0.10)

def set_params(context):
    # PVC主力合约
    context.symbol = 'V9999.XDCE'  # 聚宽期货主力连续合约代码
    # 布林线参数
    context.bb_period = 20      # 布林中轨周期
    context.bb_dev = 2          # 标准差倍数
    # ADX趋势过滤参数
    context.adx_period = 14     # ADX周期
    context.adx_threshold = 25  # 趋势强度阈值
    # 止损参数
    context.atr_period = 14     # ATR周期
    context.stop_loss_mult = 1  # 止损ATR倍数
    # 仓位管理
    context.max_position = 0.3  # 最大仓位比例
    context.risk_per_trade = 0.02 # 单笔风险比例

def set_variables():
    # 存储布林带宽度历史数据
    g.bb_width = []

def set_backtest():
    set_option('use_real_price', True)  # 使用真实价格
    log.set_level('order', 'error')      # 设置日志级别

# 每个交易日开盘前运行
def before_trading_start(context):
    pass

# 每日交易逻辑（收盘前运行）
def handle_data(context, data):
       # 检查合约是否在数据中
    if context.symbol not in data:
        return
   
    # 1. 获取历史数据
    prices = get_price(context.symbol, count=100, end_date=context.current_dt, 
                      frequency='daily', fields=['close','high','low','volume'])
    
    # 2. 计算指标
    close = prices.close.values
    # 布林线
    mid_band = ta.SMA(close, timeperiod=context.bb_period)
    std = ta.STDDEV(close, context.bb_period)
    upper_band = mid_band + context.bb_dev * std
    lower_band = mid_band - context.bb_dev * std
    # ADX趋势强度
    adx = ta.ADX(prices.high, prices.low, prices.close, timeperiod=context.adx_period)
    # ATR波动率
    atr = ta.ATR(prices.high, prices.low, prices.close, timeperiod=context.atr_period)
    
    # 3. 判断震荡市条件
    current_width = upper_band[-1] - lower_band[-1]
    g.bb_width.append(current_width)
    if len(g.bb_width) > 20:
        width_percentile = np.percentile(g.bb_width[-20:], 30)  # 过去20日宽度的30%分位
        is_volatile = current_width < width_percentile  # 布林带收窄
    else:
        is_volatile = False
    
    # 4. 生成交易信号
    current_price = data[context.symbol].close  # 使用收盘价或最新价
    position_obj = context.portfolio.positions.get(context.symbol, None)
    position = position_obj.amount if position_obj else 0  # 无持仓时为0
    
    # 多头信号：价格触下轨 + 低波动 + 无趋势
    if (current_price <= lower_band[-1]) and (adx[-1] < context.adx_threshold) and is_volatile:
        if position <= 0:  # 无持仓或空头
            order_target = calculate_position_size(context, current_price, lower_band[-1], atr[-1])
            order_target_value(context.symbol, order_target)
            
    # 空头信号：价格触上轨 + 低波动 + 无趋势
    elif (current_price >= upper_band[-1]) and (adx[-1] < context.adx_threshold) and is_volatile:
        if position >= 0:  # 无持仓或多头
            order_target = -calculate_position_size(context, current_price, upper_band[-1], atr[-1])
            order_target_value(context.symbol, order_target)
            
    # 5. 止盈止损逻辑
    if position != 0:
        # 动态止盈：回归中轨平仓
        if (position > 0 and current_price >= mid_band[-1]) or \
           (position < 0 and current_price <= mid_band[-1]):
            close_position(context, data)
            
        # 硬止损：ATR止损
        entry_price = context.portfolio.positions[context.symbol].avg_cost
        stop_loss_level = entry_price - context.stop_loss_mult * atr[-1] if position > 0 else \
                          entry_price + context.stop_loss_mult * atr[-1]
        if (position > 0 and current_price <= stop_loss_level) or \
           (position < 0 and current_price >= stop_loss_level):
            close_position(context, data)

def calculate_position_size(context, entry_price, trigger_price, atr):
    # 根据风险计算仓位
    risk_amount = context.portfolio.total_value * context.risk_per_trade
    stop_loss_distance = abs(entry_price - (trigger_price - context.stop_loss_mult * atr))
    position_size = min(risk_amount / stop_loss_distance, 
                        context.max_position * context.portfolio.total_value / entry_price)
    return position_size

def close_position(context, data):
    order_target(context.symbol, 0)
    
# 绘制布林线（聚宽研究环境使用）
def plot_indicators():
    from jqresearch import get_price
    prices = get_price('PVC9999', count=100, end_date='2023-12-31', frequency='daily')
    mid = ta.SMA(prices.close, 20)
    std = ta.STDDEV(prices.close, 20)
    plt.figure(figsize=(14,7))
    plt.plot(prices.close, label='Price')
    plt.plot(mid, label='Mid Band')
    plt.plot(mid + 2*std, label='Upper Band')
    plt.plot(mid - 2*std, label='Lower Band')
    plt.legend()
    plt.show()