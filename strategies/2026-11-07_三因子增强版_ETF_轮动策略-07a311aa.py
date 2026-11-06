# Clone from JoinQuant
# postId: 07a311aa6fc43372ef43392aacdc5842
# backtestId: df0103903e9780672e1287e22b78781d
# title: 【三因子增强版】ETF 轮动策略

# 克隆自聚宽文章：https://www.joinquant.com/post/65759
# 标题：【三因子版】ETF轮动策略适应性改造
# 说明：保留原加权回归动量算法，新增低波+趋势因子，2%/98%缩尾+截面Zscore标准化

import numpy as np
import math
import pandas as pd

def initialize(context):
    # ==================== 实盘基础设置 ====================
    set_option("avoid_future_data", True)
    set_option("use_real_price", True)
    
    set_slippage(FixedSlippage(0.000), type="fund")
    set_slippage(FixedSlippage(0.003), type="stock")
    
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0,
            open_commission=0.0002,
            close_commission=0.0002,
            close_today_commission=0,
            min_commission=5,
        ),
        type="fund",
    )
    
    set_order_cost(
        OrderCost(
            open_tax=0, close_tax=0,
            open_commission=0, close_commission=0,
            close_today_commission=0, min_commission=0,
        ),
        type="mmf",
    )
    
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    set_benchmark("513100.XSHG")

    # ==================== ETF池 ====================
    g.etf_pool3 = [
        "518880.XSHG", "159980.XSHE", "159985.XSHE", "501018.XSHG",
        "513100.XSHG", "513500.XSHG", "513520.XSHG", "513030.XSHG",
        "159920.XSHE", "510300.XSHG", "510210.XSHG", "159915.XSHE",
        "588080.XSHG", "159995.XSHE", "513050.XSHG", "159852.XSHE",
        "159845.XSHE", "515030.XSHG", "159806.XSHE", "516160.XSHG",
        "159928.XSHE", "511010.XSHG", "511880.XSHG",
    ]
    
    g.etf_pool = g.etf_pool3
        
    # ==================== 基础策略参数 ====================
    g.lookback_days = 25
    g.holdings_num = 1
    g.stop_loss = 0.95
    g.loss = 0.97
    g.defensive_etf = "511880.XSHG"
    g.min_score_threshold = 0.0
    g.max_score_threshold = 5.0
    g.min_money = 5000
    
    # 短期动量过滤
    g.use_short_momentum_filter = True
    g.short_lookback_days = 10
    g.short_momentum_threshold = 0.0
    
    # ATR动态止损
    g.use_atr_stop_loss = True
    g.atr_period = 14
    g.atr_multiplier = 2
    g.atr_trailing_stop = False
    g.atr_exclude_defensive = True
    
    # MA过滤
    g.use_ma_filter = False
    g.ma_short_period = 5
    g.ma_long_period = 25
    g.ma_filter_condition = "above"
    
    # RSI过滤
    g.use_rsi_filter = True
    g.rsi_period = 6
    g.rsi_lookback_days = 1
    g.rsi_threshold = 95
    
    # MACD过滤
    g.use_macd_filter = False
    g.macd_fast_period = 12
    g.macd_slow_period = 26
    g.macd_signal_period = 9
    g.macd_filter_condition = "bullish"
    
    # 成交量异常过滤
    g.use_volume_filter = False
    g.volume_lookback_days = 7
    g.volume_threshold = 2.0
    g.volume_exclude_defensive = True
    
    # 布林带过滤
    g.use_bollinger_filter = False
    g.bollinger_period = 20
    g.bollinger_std = 2.0
    g.bollinger_lookback_days = 3

    # ==================== 三因子核心参数 ====================
    g.factor_weights = {
        "momentum": 0.4,    # 原策略加权回归动量
        "volatility": 0.3,  # 低波动率因子
        "trend": 0.3,       # 短期趋势强度
    }
    g.vol_lookback_days = 25
    g.winsor_pct = 0.02   # 2%/98% 分位缩尾，已完整保留
    # =====================================================

    # 持仓管理
    g.positions = {}
    g.position_highs = {}
    g.position_stop_prices = {}

    # 交易调度
    run_daily(etf_trade, time='14:20')
    run_daily(check_positions, time='09:30')
    run_daily(check_atr_stop_loss, time='09:35')

# ==================== 三因子预处理工具函数 ====================
def winsorize_dict(scores_dict, pct):
    """截面缩尾处理：2%/98%分位收敛极端值，保留全部样本"""
    arr = np.array([v for v in scores_dict.values() if not np.isnan(v)])
    if len(arr) < 3:
        return scores_dict
    lower = np.nanpercentile(arr, pct * 100)
    upper = np.nanpercentile(arr, (1 - pct) * 100)
    out = {}
    for k, v in scores_dict.items():
        out[k] = np.clip(v, lower, upper) if not np.isnan(v) else np.nan
    return out

def normalize_factor_dict(scores_dict):
    """截面Z-score标准化"""
    vals = [v for v in scores_dict.values() if not np.isnan(v)]
    if len(vals) < 2:
        return {k: 0.0 for k in scores_dict}
    mu = np.mean(vals)
    sigma = np.std(vals, ddof=1)
    if sigma == 0:
        return {k: 0.0 for k in scores_dict}
    res = {}
    for k, v in scores_dict.items():
        res[k] = (v - mu) / sigma if not np.isnan(v) else 0.0
    return res
# =============================================================

# ATR计算
def calculate_atr(security, period=14):
    try:
        needed_days = period + 20
        hist_data = attribute_history(security, needed_days, '1d', ['high', 'low', 'close'])
        if len(hist_data) < period + 1:
            return 0, [], False, f"数据不足{period+1}天"
        
        high_prices = hist_data['high'].values
        low_prices = hist_data['low'].values
        close_prices = hist_data['close'].values
        
        tr_values = np.zeros(len(high_prices))
        for i in range(1, len(high_prices)):
            tr1 = high_prices[i] - low_prices[i]
            tr2 = abs(high_prices[i] - close_prices[i-1])
            tr3 = abs(low_prices[i] - close_prices[i-1])
            tr_values[i] = max(tr1, tr2, tr3)
        
        atr_values = np.zeros(len(tr_values))
        for i in range(period, len(tr_values)):
            atr_values[i] = np.mean(tr_values[i-period+1:i+1])
        
        current_atr = atr_values[-1] if len(atr_values) > 0 else 0
        valid_atr = atr_values[period:] if len(atr_values) > period else atr_values
        return current_atr, valid_atr, True, "计算成功"
    except Exception as e:
        log.warn(f"计算{security} ATR时出错: {e}")
        return 0, [], False, f"计算出错:{str(e)}"

# ATR止损执行
def check_atr_stop_loss(context):
    if not g.use_atr_stop_loss:
        return
    current_data = get_current_data()
    for security in list(context.portfolio.positions.keys()):
        if security not in g.etf_pool:
            continue
        position = context.portfolio.positions[security]
        if position.total_amount <= 0:
            continue
        if g.atr_exclude_defensive and security == g.defensive_etf:
            continue
        try:
            current_price = current_data[security].last_price
            if current_price == 0:
                continue
            cost_price = position.avg_cost
            current_atr, atr_values, success, atr_info = calculate_atr(security, g.atr_period)
            if not success:
                continue
            
            if security not in g.position_highs:
                g.position_highs[security] = current_price
            else:
                g.position_highs[security] = max(g.position_highs[security], current_price)
            position_high = g.position_highs[security]
            
            if g.atr_trailing_stop:
                atr_stop_price = position_high - g.atr_multiplier * current_atr
            else:
                atr_stop_price = cost_price - g.atr_multiplier * current_atr
            g.position_stop_prices[security] = atr_stop_price
            
            if current_price <= atr_stop_price:
                success = smart_order_target_value(security, 0, context)
                if success:
                    security_name = get_security_name(security)
                    loss_percent = (current_price/cost_price - 1) * 100
                    atr_stop_type = "跟踪" if g.atr_trailing_stop else "固定"
                    log.info(f"🚨 ATR动态止损({atr_stop_type})卖出: {security} {security_name}，成本: {cost_price:.3f}，现价: {current_price:.3f}，亏损: {loss_percent:.2f}%")
                    if security in g.position_highs:
                        del g.position_highs[security]
                    if security in g.position_stop_prices:
                        del g.position_stop_prices[security]
        except Exception as e:
            log.warn(f"检查{security} ATR止损时出错: {e}")

# 布林带计算与过滤
def calculate_bollinger_bands(prices, period=20, std_dev=2.0):
    if len(prices) < period:
        return [], [], []
    middle_band = np.zeros(len(prices))
    upper_band = np.zeros(len(prices))
    lower_band = np.zeros(len(prices))
    for i in range(period - 1, len(prices)):
        window = prices[i-period+1:i+1]
        middle = np.mean(window)
        std = np.std(window)
        upper = middle + std_dev * std
        lower = middle - std_dev * std
        middle_band[i] = middle
        upper_band[i] = upper
        lower_band[i] = lower
    return middle_band[period-1:], upper_band[period-1:], lower_band[period-1:]

def check_bollinger_filter(etf, current_price, lookback_days=5, period=20, std_dev=2.0):
    try:
        needed_days = max(period, lookback_days) + 10
        price_data = attribute_history(etf, needed_days, '1d', ['close', 'high'])
        if len(price_data) < period:
            return True, f"数据不足{period}天"
        close_prices = price_data['close'].values
        middle_band, upper_band, lower_band = calculate_bollinger_bands(close_prices, period, std_dev)
        if len(upper_band) < lookback_days:
            return True, f"布林带数据不足{lookback_days}天"
        
        recent_upper_band = upper_band[-lookback_days:]
        recent_close_prices = close_prices[-(len(middle_band)-len(upper_band)+lookback_days):][-lookback_days:]
        
        breakthrough_occurred = False
        for i in range(len(recent_close_prices)):
            if recent_close_prices[i] > recent_upper_band[i]:
                breakthrough_occurred = True
                break
        
        ma5 = np.mean(close_prices[-5:]) if len(close_prices) >= 5 else np.mean(close_prices)
        
        if breakthrough_occurred and current_price < ma5:
            return False, f"近{lookback_days}日曾突破上轨且现价<MA5"
        else:
            return True, f"未触发布林带过滤"
    except Exception as e:
        log.warn(f"检查{etf}布林带时出错: {e}")
        return True, f"检查出错:{str(e)}"

# 成交量异常检查
def check_volume_anomaly(etf, lookback_days=10, threshold=2.0, exclude_defensive=False, defensive_etf=""):
    if exclude_defensive and etf == defensive_etf:
        return True, 0.0, 0, 0, "防御ETF豁免"
    try:
        volume_lookback = lookback_days + 5
        volume_data = attribute_history(etf, volume_lookback, '1d', ['volume'])
        if len(volume_data) < lookback_days:
            return True, 0.0, 0, 0, f"数据不足{lookback_days}天"
        recent_volume = volume_data['volume'].iloc[-1]
        if len(volume_data) >= lookback_days + 1:
            avg_volume = volume_data['volume'].iloc[-(lookback_days+1):-1].mean()
        else:
            avg_volume = volume_data['volume'].iloc[:-1].mean()
        if avg_volume <= 0:
            return True, 0.0, recent_volume, avg_volume, f"历史均量异常"
        volume_ratio = recent_volume / avg_volume
        if volume_ratio > threshold:
            return False, volume_ratio, recent_volume, avg_volume, f"成交量异常"
        else:
            return True, volume_ratio, recent_volume, avg_volume, f"成交量正常"
    except Exception as e:
        log.warn(f"检查{etf}成交量时出错: {e}")
        return True, 0.0, 0, 0, f"检查出错:{str(e)}"

# RSI计算
def calculate_rsi(prices, period=6):
    if len(prices) < period + 1:
        return []
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gains = np.zeros_like(prices)
    avg_losses = np.zeros_like(prices)
    avg_gains[period] = np.mean(gains[:period])
    avg_losses[period] = np.mean(losses[:period])
    rsi_values = np.zeros(len(prices))
    rsi_values[:period] = 50
    for i in range(period + 1, len(prices)):
        avg_gains[i] = (avg_gains[i-1] * (period - 1) + gains[i-1]) / period
        avg_losses[i] = (avg_losses[i-1] * (period - 1) + losses[i-1]) / period
        if avg_losses[i] == 0:
            rsi_values[i] = 100
        else:
            rs = avg_gains[i] / avg_losses[i]
            rsi_values[i] = 100 - (100 / (1 + rs))
    return rsi_values[period:]

# MACD计算
def calculate_macd(prices, fast_period=12, slow_period=26, signal_period=9):
    if len(prices) < slow_period + signal_period:
        return [], [], []
    def calculate_ema(data, period):
        ema = np.zeros_like(data)
        ema[0] = data[0]
        alpha = 2 / (period + 1)
        for i in range(1, len(data)):
            ema[i] = alpha * data[i] + (1 - alpha) * ema[i-1]
        return ema
    ema_fast = calculate_ema(prices, fast_period)
    ema_slow = calculate_ema(prices, slow_period)
    dif = ema_fast - ema_slow
    dea = calculate_ema(dif, signal_period)
    macd_bar = dif - dea
    start_idx = slow_period + signal_period - 1
    return dif[start_idx:], dea[start_idx:], macd_bar[start_idx:]

# 持仓检查
def check_positions(context):
    current_data = get_current_data()
    for security in context.portfolio.positions:
        position = context.portfolio.positions[security]
        if position.total_amount > 0:
            security_name = get_security_name(security)
            log.info(f"📊 持仓检查: {security} {security_name}, 数量: {position.total_amount}, 成本: {position.avg_cost:.3f}")

# ==================== 三因子计算核心 ====================
def calculate_momentum_metrics(etf):
    try:
        lookback = max(g.lookback_days, g.short_lookback_days, g.ma_long_period, 
                      g.rsi_period + g.rsi_lookback_days, 
                      g.macd_slow_period + g.macd_signal_period,
                      g.volume_lookback_days,
                      g.bollinger_period + g.bollinger_lookback_days,
                      g.vol_lookback_days) + 20
        prices = attribute_history(etf, lookback, '1d', ['close', 'high'])
        current_data = get_current_data()
        if len(prices) < lookback:
            return None
            
        current_price = current_data[etf].last_price
        price_series = np.append(prices["close"].values, current_price)
        
        # MA计算
        if len(price_series) >= g.ma_long_period:
            ma5 = np.mean(price_series[-g.ma_short_period:])
            ma25 = np.mean(price_series[-g.ma_long_period:])
            if g.ma_filter_condition == "above":
                ma_condition_met = ma5 >= ma25
            else:
                ma_condition_met = ma5 <= ma25
            ma_ratio = ma5 / ma25 - 1
        else:
            ma5 = 0; ma25 = 0; ma_condition_met = True; ma_ratio = 0

        # RSI过滤
        rsi_filter_pass = True
        current_rsi = 0; max_rsi = 0
        if g.use_rsi_filter and len(price_series) >= g.rsi_period + g.rsi_lookback_days:
            rsi_values = calculate_rsi(price_series, g.rsi_period)
            if len(rsi_values) >= g.rsi_lookback_days:
                recent_rsi = rsi_values[-g.rsi_lookback_days:]
                rsi_ever_above_threshold = np.any(recent_rsi > g.rsi_threshold)
                if rsi_ever_above_threshold:
                    rsi_filter_pass = False
                    max_rsi = np.max(recent_rsi)
                    current_rsi = recent_rsi[-1]

        # MACD过滤
        macd_filter_pass = True
        dif_value = 0; dea_value = 0; macd_bar = 0
        if g.use_macd_filter and len(price_series) >= g.macd_slow_period + g.macd_signal_period:
            dif_values, dea_values, macd_bars = calculate_macd(
                price_series, g.macd_fast_period, g.macd_slow_period, g.macd_signal_period
            )
            if len(dif_values) > 0:
                dif_value = dif_values[-1]; dea_value = dea_values[-1]; macd_bar = macd_bars[-1]
                if g.macd_filter_condition == "bullish":
                    macd_filter_pass = dif_value > dea_value
                else:
                    macd_filter_pass = dif_value < dea_value

        # 成交量过滤
        volume_filter_pass = True
        volume_ratio = 0
        if g.use_volume_filter:
            volume_filter_pass, volume_ratio, _, _, _ = check_volume_anomaly(
                etf, g.volume_lookback_days, g.volume_threshold,
                g.volume_exclude_defensive, g.defensive_etf
            )

        # 布林带过滤
        bollinger_filter_pass = True
        bollinger_info = "未启用"
        if g.use_bollinger_filter:
            bollinger_filter_pass, bollinger_info = check_bollinger_filter(
                etf, current_price, g.bollinger_lookback_days, g.bollinger_period, g.bollinger_std
            )

        # 短期动量
        if len(price_series) >= g.short_lookback_days + 1:
            short_return = price_series[-1] / price_series[-(g.short_lookback_days + 1)] - 1
        else:
            short_return = 0

        # ========== 因子1：原策略加权回归动量（100%保留原算法）==========
        recent_price_series = price_series[-(g.lookback_days + 1):]
        y = np.log(recent_price_series)
        x = np.arange(len(y))
        weights = np.linspace(1, 2, len(y))
        slope, intercept = np.polyfit(x, y, 1, w=weights)
        annualized_returns = math.exp(slope * 250) - 1
        ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
        ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot else 0
        raw_momentum = annualized_returns * r_squared

        # ========== 因子2：低波动率因子 ==========
        if len(price_series) >= g.vol_lookback_days + 1:
            vol_series = price_series[-(g.vol_lookback_days + 1):]
            daily_ret = np.diff(vol_series) / vol_series[:-1]
            volatility = np.std(daily_ret, ddof=1)
            raw_volatility = -volatility
        else:
            raw_volatility = np.nan

        # ========== 因子3：短期趋势强度因子 ==========
        if len(price_series) >= g.short_lookback_days:
            trend_close = price_series[-g.short_lookback_days:]
            x_trend = np.arange(g.short_lookback_days)
            trend_slope = np.polyfit(x_trend, trend_close, deg=1)[0]
            mean_p = np.mean(trend_close)
            raw_trend = trend_slope / mean_p if mean_p > 1e-8 else np.nan
        else:
            raw_trend = np.nan

        # 近3日跌幅风控
        if len(price_series) >= 4:
            day1_ratio = price_series[-1] / price_series[-2]
            day2_ratio = price_series[-2] / price_series[-3]
            day3_ratio = price_series[-3] / price_series[-4]
            if min(day1_ratio, day2_ratio, day3_ratio) < g.loss:
                raw_momentum = -999
                log.info(f"⚠️ {etf} 近3日单日跌幅超阈值，已排除")

        return {
            'etf': etf,
            'annualized_returns': annualized_returns,
            'r_squared': r_squared,
            'raw_momentum': raw_momentum,
            'raw_volatility': raw_volatility,
            'raw_trend': raw_trend,
            'norm_momentum': 0.0,
            'norm_volatility': 0.0,
            'norm_trend': 0.0,
            'score': 0.0,
            'current_price': current_price,
            'short_return': short_return,
            'short_momentum_pass': short_return >= g.short_momentum_threshold,
            'ma5': ma5, 'ma25': ma25,
            'ma_condition_met': ma_condition_met,
            'rsi_filter_pass': rsi_filter_pass,
            'current_rsi': current_rsi,
            'macd_filter_pass': macd_filter_pass,
            'dif': dif_value, 'dea': dea_value, 'macd_bar': macd_bar,
            'volume_filter_pass': volume_filter_pass,
            'volume_ratio': volume_ratio,
            'bollinger_filter_pass': bollinger_filter_pass,
            'bollinger_info': bollinger_info,
        }
    except Exception as e:
        log.warn(f"计算{etf}因子时出错: {e}")
        return None

# ==================== 三因子截面打分排序 ====================
def get_ranked_etfs():
    candidate_metrics = []
    raw_mom_dict = {}
    raw_vol_dict = {}
    raw_trend_dict = {}

    for etf in g.etf_pool:
        metrics = calculate_momentum_metrics(etf)
        if metrics is None:
            continue
        
        # 近3日跌幅不合格直接跳过
        if metrics['raw_momentum'] <= -999:
            continue
        
        # 前置过滤
        if g.use_short_momentum_filter and not metrics['short_momentum_pass']:
            continue
        if g.use_ma_filter and not metrics['ma_condition_met']:
            continue
        if g.use_rsi_filter and not metrics['rsi_filter_pass']:
            continue
        if g.use_macd_filter and not metrics['macd_filter_pass']:
            continue
        if g.use_volume_filter and not metrics['volume_filter_pass']:
            continue
        if g.use_bollinger_filter and not metrics['bollinger_filter_pass']:
            continue
        
        # 原始动量异常值过滤
        if not (0 < metrics['raw_momentum'] < g.max_score_threshold):
            continue

        candidate_metrics.append(metrics)
        raw_mom_dict[etf] = metrics['raw_momentum']
        raw_vol_dict[etf] = metrics['raw_volatility']
        raw_trend_dict[etf] = metrics['raw_trend']

    if len(candidate_metrics) < 2:
        return candidate_metrics

    # 第二步：三因子各自独立做 2%/98% Winsorize 缩尾
    win_mom = winsorize_dict(raw_mom_dict, g.winsor_pct)
    win_vol = winsorize_dict(raw_vol_dict, g.winsor_pct)
    win_trend = winsorize_dict(raw_trend_dict, g.winsor_pct)

    # 第三步：三因子各自独立做截面Z-score标准化
    norm_mom = normalize_factor_dict(win_mom)
    norm_vol = normalize_factor_dict(win_vol)
    norm_trend = normalize_factor_dict(win_trend)

    # 第四步：加权计算综合得分
    for metrics in candidate_metrics:
        etf = metrics['etf']
        metrics['norm_momentum'] = norm_mom[etf]
        metrics['norm_volatility'] = norm_vol[etf]
        metrics['norm_trend'] = norm_trend[etf]
        
        metrics['score'] = (
            g.factor_weights['momentum'] * norm_mom[etf] +
            g.factor_weights['volatility'] * norm_vol[etf] +
            g.factor_weights['trend'] * norm_trend[etf]
        )

    candidate_metrics.sort(key=lambda x: x['score'], reverse=True)
    return candidate_metrics

# 获取证券名称
def get_security_name(security):
    current_data = get_current_data()
    return current_data[security].name if security in current_data else security

# 智能下单函数
def smart_order_target_value(security, target_value, context):
    current_data = get_current_data()
    if current_data[security].paused:
        log.info(f"{security} 今日停牌，跳过交易")
        return False
    if current_data[security].last_price >= current_data[security].high_limit:
        log.info(f"{security} 当前涨停，跳过买入")
        return False
    if current_data[security].last_price <= current_data[security].low_limit:
        log.info(f"{security} 当前跌停，跳过卖出")
        return False
    
    current_price = current_data[security].last_price
    if current_price == 0:
        return False
    
    target_amount = int(target_value / current_price)
    target_amount = (target_amount // 100) * 100
    if target_amount <= 0 and target_value > 0:
        target_amount = 100
    
    current_position = context.portfolio.positions.get(security, None)
    current_amount = current_position.total_amount if current_position else 0
    amount_diff = target_amount - current_amount
    
    trade_value = abs(amount_diff) * current_price
    if 0 < trade_value < g.min_money:
        log.info(f"{security} 交易金额小于最小交易额，跳过")
        return False

    if amount_diff < 0:
        closeable_amount = current_position.closeable_amount if current_position else 0
        if closeable_amount == 0:
            log.info(f"{security} 当天买入不可卖出(T+1)")
            return False
        amount_diff = -min(abs(amount_diff), closeable_amount)

    if amount_diff != 0:
        order_result = order(security, amount_diff)
        if order_result:
            if security not in g.positions:
                g.positions[security] = 0
            g.positions[security] = target_amount
            
            if amount_diff > 0 and security in g.etf_pool:
                g.position_highs[security] = current_price
                if g.use_atr_stop_loss and not (g.atr_exclude_defensive and security == g.defensive_etf):
                    current_atr, _, success, _ = calculate_atr(security, g.atr_period)
                    if success:
                        g.position_stop_prices[security] = current_price - g.atr_multiplier * current_atr
            
            security_name = get_security_name(security)
            if amount_diff > 0:
                log.info(f"📥 买入 {security} {security_name}，数量: {amount_diff}，价格: {current_price:.3f}")
            else:
                log.info(f"📤 卖出 {security} {security_name}，数量: {abs(amount_diff)}，价格: {current_price:.3f}")
            return True
        else:
            log.warn(f"下单失败: {security}")
            return False
    return False

# 防御ETF可用性检查
def is_defensive_etf_available():
    current_data = get_current_data()
    defensive_etf = g.defensive_etf
    if defensive_etf not in g.etf_pool:
        return False
    if current_data[defensive_etf].paused:
        return False
    if current_data[defensive_etf].last_price >= current_data[defensive_etf].high_limit:
        return False
    if current_data[defensive_etf].last_price <= current_data[defensive_etf].low_limit:
        return False
    return True

# 主交易函数
def etf_trade(context):
    ranked_etfs = get_ranked_etfs()
    
    log.info("=== ETF三因子综合排名 ===")
    for metrics in ranked_etfs:
        etf_name = get_security_name(metrics['etf'])
        log.info(f"{metrics['etf']} {etf_name}: 综合得分={metrics['score']:.4f} | "
                 f"动量={metrics['norm_momentum']:.4f} | "
                 f"低波={metrics['norm_volatility']:.4f} | "
                 f"趋势={metrics['norm_trend']:.4f}")
    
    # 确定目标ETF
    target_etf = None
    if ranked_etfs and ranked_etfs[0]['score'] >= g.min_score_threshold:
        target_etf = ranked_etfs[0]['etf']
        top_metrics = ranked_etfs[0]
        etf_name = get_security_name(target_etf)
        log.info(f"🎯 选中标的: {target_etf} {etf_name}，综合得分: {top_metrics['score']:.4f}")
    else:
        if is_defensive_etf_available():
            target_etf = g.defensive_etf
            log.info(f"🛡️ 进入防御模式，切换货币ETF")
        else:
            log.info("💤 空仓模式")
    
    target_etfs = [target_etf] if target_etf else []
    
    # 固定百分比止损
    for security in list(context.portfolio.positions.keys()):
        position = context.portfolio.positions[security]
        if security in g.etf_pool and position.total_amount > 0:
            current_price = position.price
            cost_price = position.avg_cost
            if current_price <= cost_price * g.stop_loss:
                success = smart_order_target_value(security, 0, context)
                if success:
                    loss_percent = (current_price/cost_price-1)*100
                    log.info(f"🚨 固定止损卖出: {security}，亏损: {loss_percent:.2f}%")
                    if security in g.position_highs:
                        del g.position_highs[security]
                    if security in g.position_stop_prices:
                        del g.position_stop_prices[security]

    # 调仓执行
    total_value = context.portfolio.total_value
    target_value = total_value if target_etfs else 0
    current_positions = set(context.portfolio.positions.keys())
    target_etfs_set = set(target_etfs)
    
    for security in current_positions:
        if security in g.etf_pool and security not in target_etfs_set:
            position = context.portfolio.positions[security]
            if position.total_amount > 0:
                smart_order_target_value(security, 0, context)
                if security in g.position_highs:
                    del g.position_highs[security]
                if security in g.position_stop_prices:
                    del g.position_stop_prices[security]

    for etf in target_etfs:
        current_value = 0
        if etf in context.portfolio.positions:
            position = context.portfolio.positions[etf]
            if position.total_amount > 0:
                current_value = position.total_amount * position.price
        
        if abs(current_value - target_value) > target_value * 0.05 or current_value == 0:
            smart_order_target_value(etf, target_value, context)

def trade(context):
    etf_trade(context)
