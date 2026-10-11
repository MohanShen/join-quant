# Clone from JoinQuant
# postId: c4f480e3e9868a1173cbcf6dde16e769
# backtestId: 91bcf06fbf0d8f23cd1a366dd450624f
# title: 7.8%极限回撤，用架构解耦重构多策略动态路由

# 导入函数库
from jqdata import *
import numpy as np
import pandas as pd
import talib 

def initialize(context):
    set_benchmark('513100.XSHG')
    set_option('use_real_price', True)
    log.set_level('order', 'error')
    set_order_cost(OrderCost(close_tax=0.0, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    
    g.security = '513100.XSHG'      
    g.current_regime = 2 
    g.strategy_weights = {0: 0.0, 1: 0.0, 2: 1.0} 
    g.highest_since_buy = 0.0
    
    # 动态仓位缩放系数 (新增)
    g.position_scale = 1.0

    # 核心参数 (纳指最优配置)
    g.trend_ema_days = 90         
    g.atr_crisis_multi = 1.5      
    g.turtle_high_days = 30       
    g.turtle_low_days = 15        
    g.rsi_period = 14             
    g.rsi_buy_limit = 32          
    g.rsi_sell_limit = 50         
    g.stop_loss_atr_multi = 3.0   

    # 🌟 优化一：改时间！将买卖执行点放在尾盘 14:50，完美避开早盘高溢价和跳空风险
    run_daily(before_market_open, time='before_open', reference_security='000300.XSHG')
    run_daily(market_trade, time='14:50', reference_security='000300.XSHG')

def before_market_open(context):
    log.info('='*50)
    bars = get_bars(g.security, count=150, unit='1d', fields=['close', 'high', 'low'], df=True)
    if bars is None or len(bars) < 150: return
        
    close_np = np.array(bars['close'], dtype=float)
    high_np = np.array(bars['high'], dtype=float)
    low_np = np.array(bars['low'], dtype=float)
    
    ema_trend = talib.EMA(close_np, timeperiod=g.trend_ema_days)
    is_uptrend = close_np[-1] > ema_trend[-1]
    
    atr = talib.ATR(high_np, low_np, close_np, timeperiod=14)
    atr_ma = talib.SMA(atr, timeperiod=g.trend_ema_days)
    
    # 🌟 优化二：波动率动态仓位缩放系数计算
    # 如果当前ATR远大于均值，说明风险升高，计算缩放比例降仓位
    current_vol_ratio = atr[-1] / atr_ma[-1] if atr_ma[-1] > 0 else 1.0
    if current_vol_ratio > 1.2:
        g.position_scale = 1.2 / current_vol_ratio # 波动越大，系数越小(如0.8, 0.7)
    else:
        g.position_scale = 1.0

    is_high_volatility = current_vol_ratio > g.atr_crisis_multi

    if not is_uptrend and is_high_volatility:
        g.current_regime = 0
        g.strategy_weights = {0: 1.0, 1: 0.0, 2: 0.0} 
    elif not is_uptrend and not is_high_volatility:
        g.current_regime = 1
        g.strategy_weights = {0: 0.0, 1: 0.8, 2: 0.2} 
    else:
        g.current_regime = 2
        g.strategy_weights = {0: 0.0, 1: 0.0, 2: 1.0} 
        if g.position_scale < 1.0:
            log.info('🛡️ 牛市高波预警：当前波动率放大，系统自动将目标仓位缩放至 {:.1f}%%'.format(g.position_scale * 100))

def market_trade(context):
    security = g.security
    total_value = context.portfolio.total_value 
    current_position = context.portfolio.positions[security].closeable_amount
    
    # 引入 volume 字段用于成交量过滤
    bars = get_bars(security, count=150, unit='1d', fields=['close', 'high', 'low', 'volume'], df=True)
    close_np = np.array(bars['close'], dtype=float)
    high_np = np.array(bars['high'], dtype=float)
    low_np = np.array(bars['low'], dtype=float)
    vol_np = np.array(bars['volume'], dtype=float)
    current_price = close_np[-1]
    
    if current_position > 0:
        if current_price > g.highest_since_buy: g.highest_since_buy = current_price
    else:
        g.highest_since_buy = current_price

    # --- 策略 A: 海龟突破 (带成交量滤网) ---
    signal_breakout = 0.0
    highest_n = np.max(high_np[-g.turtle_high_days-1:-1]) 
    lowest_n = np.min(low_np[-g.turtle_low_days-1:-1])   
    
    # 🌟 优化三：放量突破滤网。当前成交量必须大于过去10天平均量的80%，否则视为假突破
    avg_vol_10 = np.mean(vol_np[-11:-1])
    is_volume_confirmed = vol_np[-1] > (avg_vol_10 * 0.8)
    
    if current_price > highest_n and is_volume_confirmed: 
        signal_breakout = 1.0 
    elif current_price < lowest_n: 
        signal_breakout = 0.0 
    else: 
        signal_breakout = (current_position * current_price) / total_value if total_value > 0 else 0.0

    # --- 策略 B: 非对称 RSI ---
    signal_rsi = 0.0
    rsi_val = talib.RSI(close_np, timeperiod=g.rsi_period)[-1]
    if rsi_val < g.rsi_buy_limit: signal_rsi = 1.0 
    elif rsi_val > g.rsi_sell_limit and current_position > 0: signal_rsi = 0.0
    else: signal_rsi = (current_position * current_price) / total_value if total_value > 0 else 0.0

    signal_defense = 0.0 

    # --- ATR 吊灯止损 ---
    atr = talib.ATR(high_np, low_np, close_np, timeperiod=14)[-1]
    chandelier_exit_price = g.highest_since_buy - (g.stop_loss_atr_multi * atr)
    
    if current_position > 0 and current_price < chandelier_exit_price:
        log.error('🚨 【ATR 吊灯止损触发】 强制清仓！')
        order_target(security, 0)
        g.highest_since_buy = 0.0 
        return 

    # --- 中央路由合成 (叠加动态仓位缩放) ---
    base_ratio = (g.strategy_weights[2] * signal_breakout + 
                  g.strategy_weights[1] * signal_rsi + 
                  g.strategy_weights[0] * signal_defense)
    
    # 最终仓位 = 基础路由仓位 * 波动率缩放系数
    target_ratio = max(0.0, min(1.0, base_ratio * g.position_scale))
    target_value = total_value * target_ratio 
    current_value = current_position * current_price
    
    if abs(target_value - current_value) > total_value * 0.10:
        log.info('🛒 执行路由仓位: {:.1f}%% (已叠加波动率风控)'.format(target_ratio * 100))
        order_target_value(security, target_value)