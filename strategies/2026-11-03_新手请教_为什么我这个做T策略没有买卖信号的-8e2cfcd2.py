# Clone from JoinQuant
# postId: 8e2cfcd2df50d08e3be8665b1ad9faad
# backtestId: 54ba5ded6c4a560500c23301606acdf0
# title: 新手请教，为什么我这个做T策略没有买卖信号的？

from jqdata import *
import numpy as np
import pandas as pd

def initialize(context):
    # 基本设置
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    log.set_level('order', 'info')  # 调整日志级别
    
    # 策略参数
    g.stock = '600178.XSHG'       # 标的证券
    g.r_period = 120              # R值计算周期
    g.ema_window = 3              # EMA周期
    g.trend_window = 10           # 趋势线周期
    g.buy_threshold = -80         # 买入阈值（调整为更宽松的范围）
    g.sell_threshold = -20        # 卖出阈值
    g.slippage = 0.005            # 滑点率
    
    # 风控参数
    g.max_daily_loss = -0.03      # 单日最大亏损比例
    g.min_volume = 1000000        # 最小成交量（股）
    
    # 底仓参数
    g.base_position = 1000        # 初始底仓
    g.trade_unit = 200            # 每次交易单位
    g.min_hold = 200              # 最小保留持仓
    
    # 初始化历史数据缓存
    init_history_data(context)    # 预加载历史数据
    
    # 定时运行设置
    run_daily(before_market_open, time='before_open')
    run_daily(market_open, time='every_bar')
    run_daily(after_market_close, time='after_close')

def init_history_data(context):
    """初始化时加载历史数据"""
    hist_data = get_bars(g.stock, g.r_period+10, '1d', ['high','low'], include_now=True)
    g.hist_high = hist_data['high'].tolist()[-g.r_period:]  # 保留指定周期数据
    g.hist_low = hist_data['low'].tolist()[-g.r_period:]
    g.R_values = []
    g.R_emas = []

def before_market_open(context):
    """每日开盘前初始化"""
    g.daily_start_value = context.portfolio.total_value

def market_open(context):
    """盘中执行逻辑"""
    try:
        # 风控检查
        if not risk_control(context):
            return
            
        # 获取当前价格
        current_data = get_current_data()[g.stock]
        current_price = current_data.last_price
        
        # 获取当日高低价（通过get_bars获取当日数据）
        today_data = get_bars(g.stock, 1, '1d', ['high','low'], include_now=True)
        if len(today_data) == 0:
            log.warn("获取当日数据失败")
            return
        
        day_high = today_data['high'][0]
        day_low = today_data['low'][0]
        
        # 更新缓存（临时保存当日数据）
        temp_highs = g.hist_high.copy() + [day_high]
        temp_lows = g.hist_low.copy() + [day_low]
        hhv = max(temp_highs[-g.r_period:])
        llv = min(temp_lows[-g.r_period:])
        
        # 检查最高价和最低价是否相同
        if hhv == llv:
            log.warn("最高价和最低价相同，跳过R值计算")
            return
            
        # 计算R值
        R = -100 * (hhv - current_price) / (hhv - llv)
        
        # 维护R值序列
        g.R_values.append(R)
        if len(g.R_values) > 200:
            g.R_values.pop(0)
            
        # 计算EMA
        if len(g.R_values) >= g.ema_window:
            ema = pd.Series(g.R_values).ewm(span=g.ema_window).mean().iloc[-1]
            g.R_emas.append(ema)
            
            # 计算趋势线
            if len(g.R_emas) >= g.trend_window:
                trend = pd.Series(g.R_emas[-g.trend_window:]).mean()
                
                # 获取持仓数量（安全方式）
                current_position = context.portfolio.positions[g.stock].total_amount if g.stock in context.portfolio.positions else 0
                
                # 执行交易（改用市价单）
                execute_trade(context, trend, current_position, current_price)
                
    except Exception as e:
        log.error(f"策略执行异常: {str(e)}")

def execute_trade(context, trend, position, price):
    """执行交易指令（市价单）"""
    # 计算考虑滑点的有效价格
    effective_price = price * (1 + g.slippage) if trend < g.buy_threshold else price * (1 - g.slippage)
    
    # 卖出逻辑
    if trend > g.sell_threshold and position > g.min_hold:
        # 计算可卖出的最大数量（不超过200股，且不低于最小持仓）
        sell_amount = min(g.trade_unit, position - g.min_hold)
        if sell_amount > 0:
            order(g.stock, -sell_amount)
            log.info(f"触发卖出 {sell_amount}股 @{effective_price:.2f}")
        
    # 买入逻辑
    elif trend < g.buy_threshold:
        # 计算可买入的最大数量（不超过200股）
        available_cash = context.portfolio.available_cash * 0.995
        buy_amount = min(g.trade_unit, int(available_cash / effective_price // 100) * 100)
        if buy_amount >= 100:  # 最小交易单位为100股
            order(g.stock, buy_amount)
            log.info(f"执行买入 {buy_amount}股 @{effective_price:.2f}")

def risk_control(context):
    """综合风控模块"""
    current_data = get_current_data()[g.stock]
    
    # 涨跌停检查
    if current_data.high_limit == current_data.low_limit:
        log.warn("标的证券涨跌停，跳过交易")
        return False
    
    # 成交量检查（取昨日成交量）
    vol_data = get_bars(g.stock, 2, '1d', ['volume'])
    if len(vol_data) < 2 or vol_data['volume'][-2] < g.min_volume:
        log.warn("成交量不足，跳过交易")
        return False
    
    # 单日亏损控制
    current_value = context.portfolio.total_value
    daily_loss = (current_value - g.daily_start_value) / g.daily_start_value
    if daily_loss < g.max_daily_loss:
        # 仅在持仓超过最小持仓时卖出
        current_position = context.portfolio.positions[g.stock].total_amount if g.stock in context.portfolio.positions else 0
        if current_position > g.min_hold:
            order_target(g.stock, g.min_hold)  # 调整至最小持仓
        log.warn(f"单日亏损超过阈值 {g.max_daily_loss*100:.2f}%，调整持仓")
        return False
            
    return True

def after_market_close(context):
    """收盘后更新数据缓存"""
    # 获取当日完整数据
    today_data = get_bars(g.stock, 1, '1d', ['high','low'], include_now=True)
    if len(today_data) == 0:
        return
    
    # 更新历史数据缓存
    g.hist_high.append(today_data['high'][0])
    g.hist_low.append(today_data['low'][0])
    
    # 保持缓存长度不超过计算周期
    if len(g.hist_high) > g.r_period:
        g.hist_high.pop(0)
        g.hist_low.pop(0)
    
    # 记录净值
    log.info(f"当日收盘净值: {context.portfolio.total_value:.2f}")