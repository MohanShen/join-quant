# Clone from JoinQuant
# postId: 0b1921556f56e141c02cd34a2b50a112
# backtestId: d3431360527886a4cc5805aa6e454a83
# title: 聚宽对接Q*T自动下单全通链路零成本SP验证60倍七星高照

# 克隆自聚宽文章：https://www.joinquant.com/post/70329
# 标题：60倍七星高照+高斯+拉普拉斯
# 作者：king088

# 克隆自聚宽文章：https://www.joinquant.com/post/69163
# 标题：【策略优化】ETF轮动策略优化-V1.7.2
# 作者：晨曦量化# ==================== 全局导入与配置 ====================
import numpy as np
import math
import datetime
import pandas as pd
import json
import redis
import time
import logging
from jqdata import *

# Redis 配置（请勿外泄密码）
REDIS_HOST = "redis"  #这里填你自己的redis链接地址
REDIS_PORT = 12345    #这里填你自己的端口
REDIS_PASSWORD = "deujgrdfhytyg"  #这里填你自己的密匙
REDIS_STREAM_NAME = "trading_signals"   #这里填你redis名字
STRATEGY_NAME = "七星高照ETF轮动策略"   #这里填自己的策略名字

# 全局标志（仅用于记录状态，不维持连接）
_redis_reachable = False

MIN_TRADE_AMOUNT = 5000   # 最小交易金额

# ==================== Redis 信号模块 ====================
def _is_backtest(context):
    """判断当前是否为回测模式"""
    try:
        run_type = context.run_type
        if run_type == 'backtest':
            return True
    except:
        return True
    return False

def _generate_trade_id():
    """生成微秒级唯一 trade_id"""
    return datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')

def _send_single_signal(context, action, stock_code, order_volume, order_price, trade_id):
    """
    发送单个信号到 Redis（临时连接 + 重试3次）
    action: 'BUY' 或 'SELL'
    order_volume: 股数（正数）
    """
    timestamp = datetime.datetime.now().timestamp()
    signal = {
        "strategy": STRATEGY_NAME,
        "action": action,
        "stock_code": stock_code,
        "order_volume": order_volume,
        "order_price": round(order_price, 3),
        "timestamp": timestamp,
        "trade_id": trade_id
    }
    # 回测模式：仅记录日志
    if _is_backtest(context):
        log.info(f"[回测模式] 模拟发送信号：{json.dumps(signal, ensure_ascii=False)}")
        return True
    
    # 实盘/模拟：临时连接+重试
    def send_with_retry(signal_dict, max_retries=3, retry_delay=0.5):
        last_exception = None
        for attempt in range(1, max_retries+1):
            try:
                client = redis.StrictRedis(
                    host=REDIS_HOST,
                    port=REDIS_PORT,
                    password=REDIS_PASSWORD,
                    socket_timeout=3,
                    socket_connect_timeout=3,
                    decode_responses=True
                )
                client.ping()
                msg_id = client.xadd(REDIS_STREAM_NAME, signal_dict, maxlen=10000)
                client.close()
                log.info(f"✅ Redis 发送成功，msg_id={msg_id}")
                return True
            except Exception as e:
                last_exception = e
                log.warning(f"Redis 发送尝试 {attempt}/{max_retries} 失败：{e}")
                if attempt < max_retries:
                    time.sleep(retry_delay)
        log.error(f"❌ Redis 发送彻底失败：{last_exception}")
        return False
    
    success = send_with_retry(signal)
    if success:
        log.info(f"📡 信号已发送：{json.dumps(signal, ensure_ascii=False)}")
    else:
        log.warning(f"⚠️ 信号未发送（已落盘日志）：{json.dumps(signal, ensure_ascii=False)}")
    return success

# ==================== 策略初始化 ====================
def initialize(context):
    """
    初始化函数：设置交易参数、ETF池、核心参数、调度任务
    """
    set_option("avoid_future_data", True)
    set_option("use_real_price", True)
    set_slippage(PriceRelatedSlippage(0.0001), type="fund")
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0,
            open_commission=0.0001,
            close_commission=0.0001,
            close_today_commission=0,
            min_commission=5,
        ),
        type="fund",
    )
    set_benchmark("161226.XSHE")
    
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'debug')
    log.info("========== 策略初始化开始 ==========")
    
    # ---------- ETF池 ----------
    g.etf_pool_bak = [
        "518880.XSHG",   # 黄金ETF
        "159985.XSHE",   # 豆粕ETF
        "501018.XSHG",   # 南方原油
        "161226.XSHE",   # 白银LOF
        "513100.XSHG",   # 纳指ETF
        "159915.XSHE",   # 创业板ETF
        "511220.XSHG",   # 城投债ETF
    ]
    g.etf_pool  = [
        "518880.XSHG", "159980.XSHE", "159985.XSHE", "501018.XSHG",
        "161226.XSHE", "159981.XSHE", "513100.XSHG", "159509.XSHE",
        "513290.XSHG", "513500.XSHG", "159529.XSHE", "513400.XSHG",
        "513520.XSHG", "513030.XSHG", "513080.XSHG", "513310.XSHG",
        "513730.XSHG", "159792.XSHE", "513130.XSHG", "513050.XSHG",
        "159920.XSHE", "513690.XSHG", "510300.XSHG", "510500.XSHG",
        "510050.XSHG", "510210.XSHG", "159915.XSHE", "588080.XSHG",
        "512100.XSHG", "563360.XSHG", "563300.XSHG", "512890.XSHG",
        "159967.XSHE", "512040.XSHG", "159201.XSHE", "511380.XSHG",
        "511010.XSHG", "511220.XSHG",
    ]
    
    # ---------- 核心参数 ----------
    g.lookback_days = 25
    g.holdings_num = 1
    g.defensive_etf = "511880.XSHG"
    g.min_money = 5000
    
    # 盈利保护
    g.enable_profit_protection = True
    g.profit_protection_lookback = 1
    g.profit_protection_threshold = 0.05
    g.profit_protection_check_times = ['11:00']
    g.loss = 0.97
    g.min_score_threshold = 0
    g.max_score_threshold = 100.0
    
    # 成交量过滤
    g.enable_volume_check = True
    g.volume_lookback = 5
    g.volume_threshold = 2
    g.volume_return_limit = 1
    
    # 短期动量过滤
    g.use_short_momentum_filter = True
    g.short_lookback_days = 10
    g.short_momentum_threshold = 0.0
    
    # 溢价率过滤
    g.enable_premium_filter = True
    g.premium_threshold = 0.20
    
    # 运行时变量
    g.rankings_cache = {'date': None, 'data': None}
    
    # 震荡期参数
    g.enable_range_bound_mode = True
    g.current_filter = '正常期'
    g.risk_state = '正常期'
    g.lookback_high_low_days = 20
    g.risk_benchmark = '510300.XSHG'
    g.laplace_s_param = 0.05
    g.laplace_min_slope = 0.001
    g.gaussian_sigma = 1.2
    g.gaussian_min_slope = 0.002
    g.enable_bias_trigger = True
    g.bias_threshold = 0.10
    g.ma_period = 20
    g.enable_rsi_trigger = True
    g.rsi_overbought = 75
    g.rsi_pullback = 60
    g.previous_rsi = None
    g.enable_stop_loss_trigger = False
    g.stop_loss_triggered_today = False
    g.stop_loss_triggered_date = None
    g.enable_low_point_rise_trigger = True
    g.low_point_rise_threshold = 0.03
    g.enable_stable_signal_trigger = True
    g.drawdown_recovery = 0.03
    g.max_range_bound_days = 15
    g.stable_days = 0
    g.filter_switch_cooldown = 2
    g.last_switch_date = None
    g.range_bound_start_date = None
    g.range_bound_days_count = 0
    g.previous_drawdown = None
    
    # 交易调度（统一在13:10卖出+买入）
    run_daily(check_positions, time='09:10')
    run_daily(etf_trade, time='13:10')   # 合并卖出和买入
    
    # 盈利保护独立检查
    for check_time in g.profit_protection_check_times:
        run_daily(profit_protection_check, time=check_time)
        log.info(f"已注册盈利保护检查时间：{check_time}")
    
    # 震荡期检查
    run_daily(check_range_bound, time='13:55')
    run_daily(reset_range_bound_daily, time='15:10')
    
    log.info(f"策略初始化完成：ETF池{len(g.etf_pool)}只，动量周期{g.lookback_days}天，持仓{g.holdings_num}只")
    if g.enable_premium_filter:
        log.info(f"溢价率过滤已启用，阈值：{g.premium_threshold*100:.0f}%")
    log.info(f"震荡期模式：{'开启' if g.enable_range_bound_mode else '关闭'}")
    
    # 首次运行时判断当前震荡期状态
    init_range_bound_status(context)
    log.info("========== 策略初始化完成 ==========")

# ==================== 辅助函数 ====================
def get_name(security):
    try:
        return get_current_data()[security].name
    except:
        return "未知"

def check_defensive_etf_available(context):
    data = get_current_data()
    etf = g.defensive_etf
    if data[etf].paused:
        return False
    if data[etf].last_price >= data[etf].high_limit:
        return False
    if data[etf].last_price <= data[etf].low_limit:
        return False
    return True

def smart_order_target_value(security, target_value, context):
    """
    智能下单：根据目标市值调整持仓，处理停牌、涨跌停、最小交易金额、T+1
    返回值: (是否成功, 实际成交股数, 成交价)
    """
    data = get_current_data()
    name = get_name(security)
    
    if data[security].paused:
        log.info(f"{security} {name} 停牌，跳过")
        return False, 0, 0
    
    price = data[security].last_price
    if price == 0:
        log.info(f"{security} {name} 当前价格0，跳过")
        return False, 0, 0
    
    target_amount = int(target_value / price)
    target_amount = (target_amount // 100) * 100
    if target_amount <= 0 and target_value > 0:
        target_amount = 100
    
    cur_pos = context.portfolio.positions.get(security, None)
    cur_amount = cur_pos.total_amount if cur_pos else 0
    diff = target_amount - cur_amount
    
    # 检查涨跌停
    if diff > 0:  # 买入
        if data[security].last_price >= data[security].high_limit:
            log.info(f"{security} {name} 涨停，跳过买入")
            return False, 0, 0
    elif diff < 0:  # 卖出
        if data[security].last_price <= data[security].low_limit:
            log.info(f"{security} {name} 跌停，跳过卖出")
            return False, 0, 0
    
    # 最小交易金额检查
    trade_val = abs(diff) * price
    if 0 < trade_val < g.min_money:
        log.info(f"{security} {name} 交易金额{trade_val:.2f} < {g.min_money}，跳过")
        return False, 0, 0
    
    # T+1处理：卖出时只能卖出可卖股数
    actual_diff = diff
    if diff < 0:
        closeable = cur_pos.closeable_amount if cur_pos else 0
        if closeable == 0:
            log.info(f"{security} {name} 当天买入不可卖出")
            return False, 0, 0
        actual_diff = -min(abs(diff), closeable)
        if actual_diff == 0:
            return False, 0, 0
    
    if actual_diff != 0:
        order_result = order(security, actual_diff)
        if order_result:
            log.info(f"{'📥 买入' if actual_diff>0 else '📤 卖出'} {security} {name} 数量{abs(actual_diff)} 价格{price:.3f}")
            # 发送信号到 Redis（实际成交后）
            action = "BUY" if actual_diff > 0 else "SELL"
            trade_id = _generate_trade_id()
            _send_single_signal(context, action, security, abs(actual_diff), price, trade_id)
            return True, abs(actual_diff), price
        else:
            log.warning(f"下单失败: {security} {name} 数量{actual_diff}")
            return False, 0, 0
    return False, 0, 0

# ==================== 盈利保护函数 ====================
def profit_protection_check(context):
    if not g.enable_profit_protection:
        return
    log.info("========== 盈利保护独立检查开始 ==========")
    for sec in list(context.portfolio.positions.keys()):
        if sec not in g.etf_pool and sec != g.defensive_etf:
            continue
        pos = context.portfolio.positions[sec]
        if pos.total_amount > 0:
            if check_profit_protection(sec, context):
                # 卖出并发送信号
                success, vol, price = smart_order_target_value(sec, 0, context)
                if success:
                    log.info(f"🛡️ 盈利保护卖出：{sec} {get_name(sec)}")
                    if g.enable_stop_loss_trigger:
                        g.stop_loss_triggered_today = True
                        g.stop_loss_triggered_date = context.current_dt.date()
    log.info("========== 盈利保护独立检查完成 ==========")

def check_profit_protection(security, context, lookback=None, threshold=None):
    if not g.enable_profit_protection:
        return False
    lookback = lookback or g.profit_protection_lookback
    threshold = threshold or g.profit_protection_threshold
    hist = attribute_history(security, lookback, '1d', ['high'])
    if hist.empty or len(hist) < lookback:
        return False
    max_high = hist['high'].max()
    current_price = get_current_data()[security].last_price
    if current_price <= max_high * (1 - threshold):
        log.info(f"🔻 {security} 触发盈利保护：回撤{(1 - current_price/max_high)*100:.2f}%")
        return True
    return False

# ==================== 溢价率获取 ====================
def get_premium_rate(code, date, max_back_days=5):
    price_data = get_price(code, start_date=date, end_date=date, frequency='daily', fields=['close'])
    if price_data.empty:
        return None, None, None
    price = price_data['close'].iloc[0]
    net_value = None
    used_date = date
    start_date = date - datetime.timedelta(days=max_back_days*2)
    trade_days = get_trade_days(start_date=start_date, end_date=date)
    trade_days = [pd.to_datetime(d).date() for d in trade_days]
    for dt in reversed(trade_days):
        if dt > date: continue
        net_data = get_extras('unit_net_value', code, start_date=dt, end_date=dt, df=True)
        if not net_data.empty and not pd.isna(net_data[code].iloc[0]):
            net_value = net_data[code].iloc[0]
            used_date = dt
            break
        try:
            q = query(finance.FUND_NET_VALUE).filter(finance.FUND_NET_VALUE.code == code, finance.FUND_NET_VALUE.day == dt)
            net_df = finance.run_query(q)
            if not net_df.empty:
                net_value = net_df['net_value'].iloc[0]
                used_date = dt
                break
        except:
            continue
    if net_value is None:
        return None, None, None
    premium_rate = (price - net_value) / net_value
    return premium_rate, price, net_value

# ==================== 震荡期机制 ====================
def calculate_rsi(close, period=14):
    try:
        if len(close) < period+1: return None
        deltas = np.diff(close)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        if avg_loss == 0: return 100
        rs = avg_gain / avg_loss
        return 100 - (100/(1+rs))
    except:
        return None

def laplace_filter(price, s=0.05):
    alpha = 1 - np.exp(-s)
    L = np.zeros(len(price))
    L[0] = price[0]
    for t in range(1, len(price)):
        L[t] = alpha * price[t] + (1 - alpha) * L[t-1]
    return L

def gaussian_filter_last_two(price, sigma=1.2):
    n = len(price)
    if n < 2: return 0,0
    idx_1 = np.arange(n)
    weights_1 = np.exp(-((idx_1+1)**2)/(2*sigma**2))[::-1]
    weights_1 /= np.sum(weights_1)
    g1 = np.sum(price * weights_1)
    price_2 = price[:-1]
    idx_2 = np.arange(n-1)
    weights_2 = np.exp(-((idx_2+1)**2)/(2*sigma**2))[::-1]
    weights_2 /= np.sum(weights_2)
    g2 = np.sum(price_2 * weights_2)
    return g1, g2

def get_risk_benchmark_state(context):
    required_days = max(g.ma_period, g.lookback_high_low_days)
    lookback = required_days + 30
    end_date = getattr(context, 'previous_date', None)
    if end_date is None: return None
    df = get_price(g.risk_benchmark, end_date=end_date, count=lookback, frequency='daily', fields=['close','high','low'], panel=False)
    if df is None or len(df) < required_days: return None
    daily_close = df['close'].values.astype(float)
    daily_high = df['high'].values.astype(float)
    daily_low = df['low'].values.astype(float)
    current_price = float(daily_close[-1])
    intraday_high, intraday_low = current_price, current_price
    try:
        today = context.current_dt.date()
        minute_df = get_price(g.risk_benchmark, start_date=today, end_date=context.current_dt, frequency='1m', fields=['close','high','low'], panel=False, fill_paused=False)
        if minute_df is not None and not minute_df.empty:
            minute_close = minute_df['close'].dropna()
            minute_high = minute_df['high'].dropna()
            minute_low = minute_df['low'].dropna()
            if not minute_close.empty:
                current_price = float(minute_close.iloc[-1])
                intraday_high = float(minute_high.max()) if not minute_high.empty else current_price
                intraday_low = float(minute_low.min()) if not minute_low.empty else current_price
    except: pass
    close_series = np.append(daily_close, current_price)
    high_series = np.append(daily_high, max(intraday_high, current_price))
    low_series = np.append(daily_low, min(intraday_low, current_price))
    recent_high = np.max(high_series[-g.lookback_high_low_days:])
    recent_low = np.min(low_series[-g.lookback_high_low_days:])
    ma = np.mean(close_series[-g.ma_period:])
    current_rsi = calculate_rsi(close_series, period=14)
    previous_rsi = calculate_rsi(daily_close, period=14)
    return {
        'close_series': close_series,
        'current_price': current_price,
        'recent_high': recent_high,
        'recent_low': recent_low,
        'ma': ma,
        'current_rsi': current_rsi,
        'previous_rsi': previous_rsi,
    }

def is_fresh_stop_loss_signal(context):
    signal_date = getattr(g, 'stop_loss_triggered_date', None)
    if signal_date is None: return False
    today = context.current_dt.date()
    previous_date = getattr(context, 'previous_date', None)
    if signal_date == today: return True
    if previous_date is not None and signal_date == previous_date: return True
    g.stop_loss_triggered_today = False
    g.stop_loss_triggered_date = None
    return False

def init_range_bound_status(context):
    if not g.enable_range_bound_mode: return
    log.info("【首次运行】初始化震荡期状态...")
    try:
        if context.previous_date is None: return
        end_date = context.previous_date
        lookback = max(g.ma_period, g.lookback_high_low_days)+30
        df = get_price(g.risk_benchmark, end_date=end_date, count=lookback, frequency='daily', fields=['close','high','low'], panel=False)
        if df is None or len(df) < max(g.ma_period, g.lookback_high_low_days): return
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        current_price = close[-1]
        recent_high = np.max(high[-g.lookback_high_low_days:]) if len(close)>=g.lookback_high_low_days else np.max(high)
        recent_low = np.min(low[-g.lookback_high_low_days:]) if len(close)>=g.lookback_high_low_days else np.min(low)
        ma = np.mean(close[-g.ma_period:])
        bias = (current_price - ma)/ma if ma>0 else 0
        current_rsi = calculate_rsi(close, period=14)
        should_enter = False
        signals = []
        if g.enable_bias_trigger and bias > g.bias_threshold:
            should_enter = True
            signals.append(f"乖离率{bias:.2%}>{g.bias_threshold:.0%}")
        if g.enable_rsi_trigger and current_rsi is not None and len(close)>=15:
            prev_rsi = calculate_rsi(close[:-1], period=14)
            if prev_rsi is not None and prev_rsi > g.rsi_overbought and current_rsi < g.rsi_pullback:
                should_enter = True
                signals.append(f"RSI超买回落{prev_rsi:.1f}->{current_rsi:.1f}")
        if should_enter:
            g.current_filter = '震荡期'
            g.risk_state = '震荡期'
            g.range_bound_start_date = end_date
            g.range_bound_days_count = 0
            log.info(f"【首次运行】进入震荡期: {'; '.join(signals)}")
        else:
            g.current_filter = '正常期'
            g.risk_state = '正常期'
            if len(close)>=g.lookback_high_low_days:
                g.previous_drawdown = (recent_high - current_price)/recent_high if recent_high>0 else 0
            else:
                g.previous_drawdown = 0
            g.previous_rsi = current_rsi
    except Exception as e:
        log.warning(f"【首次运行】异常: {e}")

def check_and_exit_range_bound_mode(context):
    if not g.enable_range_bound_mode: return
    if g.current_filter != '震荡期': return
    log.info("【震荡期退出检查】开始...")
    try:
        benchmark_state = get_risk_benchmark_state(context)
        if benchmark_state is None: return
        close = benchmark_state['close_series']
        current_price = benchmark_state['current_price']
        recent_high = benchmark_state['recent_high']
        recent_low = benchmark_state['recent_low']
        current_drawdown = (recent_high - current_price)/recent_high if recent_high>0 else 0
        rise_from_low = (current_price - recent_low)/recent_low if recent_low>0 else 0
        recovery_signals = []
        ma = benchmark_state['ma']
        current_rsi = benchmark_state['current_rsi']
        if g.enable_low_point_rise_trigger and rise_from_low >= g.low_point_rise_threshold:
            recovery_signals.append(f"从低点上涨{rise_from_low:.2%}>={g.low_point_rise_threshold:.0%}")
        if g.enable_stable_signal_trigger:
            if current_price > ma: recovery_signals.append("价格站上均线")
            if len(close)>=2 and close[-1]>close[-2]: recovery_signals.append("价格回升")
            if g.previous_drawdown is not None and current_drawdown < g.previous_drawdown:
                recovery_signals.append("回撤收窄")
            if current_rsi is not None and g.previous_rsi is not None and current_rsi > g.previous_rsi:
                recovery_signals.append(f"RSI回升({current_rsi:.1f})")
            drawdown_safe = current_drawdown < g.drawdown_recovery
            if drawdown_safe:
                g.stable_days += 1
            else:
                g.stable_days = 0
        g.previous_drawdown = current_drawdown
        g.previous_rsi = current_rsi
        range_bound_days = 0
        if g.range_bound_start_date is not None:
            trade_days = get_trade_days(start_date=g.range_bound_start_date, end_date=context.current_dt.date())
            range_bound_days = len(trade_days) - 1
            if range_bound_days >= g.max_range_bound_days:
                recovery_signals.append(f"震荡期满({range_bound_days}天)")
        low_point_condition = g.enable_low_point_rise_trigger and rise_from_low >= g.low_point_rise_threshold
        stable_condition = False
        if g.enable_stable_signal_trigger:
            drawdown_safe = current_drawdown < g.drawdown_recovery
            stable_condition = drawdown_safe and len(recovery_signals) >= 2 and g.stable_days >= 2
        force_condition = range_bound_days >= g.max_range_bound_days
        should_recover = low_point_condition or stable_condition or force_condition
        if should_recover:
            can_switch = True
            if g.last_switch_date is not None:
                trade_days = get_trade_days(start_date=g.last_switch_date, end_date=context.current_dt.date())
                days_since = len(trade_days) - 1
                if days_since < g.filter_switch_cooldown:
                    can_switch = False
            if can_switch:
                g.current_filter = '正常期'
                g.risk_state = '正常期'
                g.last_switch_date = context.current_dt.date()
                g.range_bound_start_date = None
                g.range_bound_days_count = 0
                g.stable_days = 0
                log.info(f"【退出震荡期】切换回拉普拉斯滤波器: {'; '.join(recovery_signals)}")
        else:
            log.info("【震荡期退出检查】未满足退出条件")
    except Exception as e:
        log.warning(f"【震荡期退出检查】出错: {e}")

def check_and_enter_range_bound_mode(context):
    if not g.enable_range_bound_mode: return
    log.info("【震荡期进入检查】开始...")
    stop_loss_signal_active = is_fresh_stop_loss_signal(context)
    can_switch = True
    if g.last_switch_date is not None:
        trade_days = get_trade_days(start_date=g.last_switch_date, end_date=context.current_dt.date())
        days_since = len(trade_days) - 1
        if days_since < g.filter_switch_cooldown:
            can_switch = False
            log.info(f"【震荡期检查】冷却中，距上次切换{days_since}天")
    if g.current_filter == '震荡期':
        log.info("【震荡期检查】已在震荡期")
        return
    if not can_switch: return
    risk_signals = []
    try:
        benchmark_state = get_risk_benchmark_state(context)
        if benchmark_state is not None:
            close = benchmark_state['close_series']
            current_price = benchmark_state['current_price']
            if g.enable_bias_trigger:
                ma = benchmark_state['ma']
                bias = (current_price - ma)/ma if ma>0 else 0
                if bias > g.bias_threshold:
                    risk_signals.append(f"乖离率过大({bias:.2%}>{g.bias_threshold:.0%})")
            if g.enable_rsi_trigger:
                current_rsi = benchmark_state['current_rsi']
                if len(close) >= 15 and current_rsi is not None:
                    prev_rsi = benchmark_state['previous_rsi']
                    if prev_rsi is not None and prev_rsi > g.rsi_overbought and current_rsi < g.rsi_pullback and current_rsi < prev_rsi:
                        risk_signals.append(f"RSI超买回落({prev_rsi:.1f}->{current_rsi:.1f})")
    except Exception as e:
        log.warning(f"【震荡期检查】异常: {e}")
    if g.enable_stop_loss_trigger and stop_loss_signal_active:
        risk_signals.append("盈利保护触发止损")
    if len(risk_signals) > 0:
        g.current_filter = '震荡期'
        g.risk_state = '震荡期'
        g.last_switch_date = context.current_dt.date()
        g.range_bound_start_date = context.current_dt.date()
        g.range_bound_days_count = 0
        g.stable_days = 0
        g.stop_loss_triggered_today = False
        g.stop_loss_triggered_date = None
        log.info(f"【进入震荡期】切换到高斯滤波器: {'; '.join(risk_signals)}")
    else:
        log.info("【震荡期检查】未满足进入条件")

def check_range_bound(context):
    if not g.enable_range_bound_mode: return
    log.info("========== 震荡期检查开始 ==========")
    log.info(f"当前状态: {g.current_filter}")
    check_and_exit_range_bound_mode(context)
    check_and_enter_range_bound_mode(context)
    log.info(f"检查后状态: {g.current_filter}")
    g.rankings_cache = {'date': None, 'data': None}
    log.info("========== 震荡期检查完成 ==========")

def reset_range_bound_daily(context):
    if g.current_filter == '震荡期' and g.range_bound_start_date is not None:
        trade_days = get_trade_days(start_date=g.range_bound_start_date, end_date=context.current_dt.date())
        g.range_bound_days_count = len(trade_days) - 1
        log.info(f"震荡期已持续 {g.range_bound_days_count} 个交易日")
    log.debug("收盘震荡期标志重置完成")

# ==================== 核心计算模块 ====================
def get_cached_rankings(context):
    today = context.current_dt.date()
    if g.rankings_cache['date'] != today:
        log.info("重新计算ETF排名...")
        ranked = get_ranked_etfs(context)
        g.rankings_cache = {'date': today, 'data': ranked}
    else:
        log.debug("使用缓存的ETF排名")
    return g.rankings_cache['data']

def get_annualized_returns(price_series, lookback_days):
    recent = price_series[-(lookback_days + 1):]
    y = np.log(recent)
    x = np.arange(len(y))
    weights = np.linspace(1, 2, len(y))
    slope, _ = np.polyfit(x, y, 1, w=weights)
    return math.exp(slope * 250) - 1

def get_volume_ratio(context, security, lookback=None, threshold=None):
    lookback = lookback or g.volume_lookback
    threshold = threshold or g.volume_threshold
    try:
        name = get_name(security)
        hist = attribute_history(security, lookback, '1d', ['volume'])
        if hist.empty or len(hist) < lookback:
            return None
        avg_vol = hist['volume'].mean()
        today = context.current_dt.date()
        df_vol = get_price(security, start_date=today, end_date=context.current_dt,
                           frequency='1m', fields=['volume'], skip_paused=False, fq='pre')
        if df_vol is None or df_vol.empty:
            return None
        current_vol = df_vol['volume'].sum()
        ratio = current_vol / avg_vol if avg_vol > 0 else 0
        if ratio > threshold:
            log.debug(f"{security} {name} 成交量比{ratio:.2f} > {threshold}")
            return ratio
        return None
    except Exception as e:
        log.warning(f"成交量计算失败 {security}: {e}")
        return None

def calculate_momentum_metrics(context, etf):
    try:
        name = get_name(etf)
        lookback = max(g.lookback_days, g.short_lookback_days) + 20
        prices = attribute_history(etf, lookback, '1d', ['close', 'high'])
        if len(prices) < g.lookback_days:
            log.debug(f"{etf} {name} 历史数据不足{len(prices)}天，跳过")
            return None
        current_price = get_current_data()[etf].last_price
        price_series = np.append(prices["close"].values, current_price)
        
        # 盈利保护检查
        if check_profit_protection(etf, context):
            log.info(f"🚫 {etf} {name} 触发盈利保护，排除")
            return None
        
        # 溢价率过滤
        if g.enable_premium_filter:
            prev_date = get_trade_days(end_date=context.current_dt.date(), count=2)[0]
            premium, _, _ = get_premium_rate(etf, prev_date)
            if premium is not None and premium > g.premium_threshold:
                log.info(f"🚫 {etf} {name} 溢价率{premium*100:.2f}% > {g.premium_threshold*100:.0f}%，排除")
                return None
        
        # 成交量过滤
        if g.enable_volume_check:
            vol_ratio = get_volume_ratio(context, etf)
            if vol_ratio is not None:
                annualized = get_annualized_returns(price_series, g.lookback_days)
                if annualized > g.volume_return_limit:
                    log.info(f"📉 {etf} {name} 成交量放量{vol_ratio:.1f}倍，年化{annualized*100:.1f}% > 阈值，过滤")
                    return None
        
        # 短期动量过滤
        if len(price_series) >= g.short_lookback_days + 1:
            short_return = price_series[-1] / price_series[-(g.short_lookback_days + 1)] - 1
            short_annualized = (1 + short_return) ** (250 / g.short_lookback_days) - 1
        else:
            short_annualized = 0
        if g.use_short_momentum_filter and short_annualized < g.short_momentum_threshold:
            log.debug(f"{etf} {name} 短期动量{short_annualized*100:.1f}% < 阈值，过滤")
            return None
        
        # 长期动量
        recent = price_series[-(g.lookback_days + 1):]
        y = np.log(recent)
        x = np.arange(len(y))
        weights = np.linspace(1, 2, len(y))
        slope, intercept = np.polyfit(x, y, 1, w=weights)
        annualized_returns = math.exp(slope * 250) - 1
        ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
        ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot != 0 else 0
        score = annualized_returns * r_squared
        
        # 近3日单日跌幅过滤
        if len(price_series) >= 4:
            day1 = price_series[-1] / price_series[-2]
            day2 = price_series[-2] / price_series[-3]
            day3 = price_series[-3] / price_series[-4]
            if min(day1, day2, day3) < g.loss:
                log.info(f"⚠️ {etf} {name} 近3日有单日跌幅超{(1-g.loss)*100:.1f}%，排除")
                return None
        
        # 动态滤波器
        if g.enable_range_bound_mode and len(price_series) >= 10:
            laplace_values = laplace_filter(price_series, s=g.laplace_s_param)
            laplace_slope = laplace_values[-1] - laplace_values[-2] if len(laplace_values) >= 2 else 0
            passed_laplace = (current_price > laplace_values[-1] and laplace_slope > g.laplace_min_slope)
            g1_val, g2_val = gaussian_filter_last_two(price_series, sigma=g.gaussian_sigma)
            gaussian_slope = g1_val - g2_val
            passed_gaussian = (current_price > g1_val and gaussian_slope > g.gaussian_min_slope)
            if g.current_filter == '正常期':
                passed_filter = passed_laplace
            else:
                passed_filter = passed_gaussian
            if not passed_filter:
                log.debug(f"{etf} {name} 未通过{g.current_filter}滤波器，过滤")
                return None
        
        return {
            'etf': etf,
            'etf_name': name,
            'annualized_returns': annualized_returns,
            'r_squared': r_squared,
            'score': score,
            'current_price': current_price,
            'short_annualized': short_annualized,
        }
    except Exception as e:
        log.warning(f"计算{etf}时出错: {e}")
        return None

def get_ranked_etfs(context):
    etf_metrics = []
    for etf in g.etf_pool:
        if get_current_data()[etf].paused:
            log.debug(f"{etf} {get_name(etf)} 停牌，跳过")
            continue
        metrics = calculate_momentum_metrics(context, etf)
        if metrics is not None:
            if g.min_score_threshold < metrics['score'] < g.max_score_threshold:
                etf_metrics.append(metrics)
            else:
                log.debug(f"{etf} {metrics['etf_name']} 得分{metrics['score']:.2f}超出阈值")
    etf_metrics.sort(key=lambda x: x['score'], reverse=True)
    return etf_metrics

# ==================== 交易执行（统一13:10） ====================
def check_positions(context):
    """每日开盘检查持仓状态，仅用于日志"""
    for sec in context.portfolio.positions:
        pos = context.portfolio.positions[sec]
        if pos.total_amount > 0:
            log.info(f"📊 持仓：{sec} {get_name(sec)} 数量{pos.total_amount} 成本{pos.avg_cost:.3f} 现价{pos.price:.3f}")

def etf_trade(context):
    """统一交易入口：先卖出不符合条件的，再买入目标ETF"""
    log.info("========== 交易开始 (13:10) ==========")
    
    # 获取最新排名
    ranked = get_cached_rankings(context)
    
    # 确定目标ETF列表（得分前N名且满足得分阈值）
    target_etfs = []
    for m in ranked[:g.holdings_num]:
        if m['score'] >= g.min_score_threshold:
            target_etfs.append(m['etf'])
    
    # 若没有目标ETF且防御可用，则把防御ETF作为目标
    defensive_available = check_defensive_etf_available(context)
    if not target_etfs and defensive_available:
        target_etfs = [g.defensive_etf]
        log.info(f"🛡️ 进入防御模式，目标ETF：{g.defensive_etf} {get_name(g.defensive_etf)}")
    elif not target_etfs:
        log.info("💤 无目标ETF且防御不可用，保持空仓")
        return
    
    target_set = set(target_etfs)
    
    # 先卖出不在目标列表的持仓
    for sec in list(context.portfolio.positions.keys()):
        if sec not in g.etf_pool and sec != g.defensive_etf:
            continue
        if sec not in target_set:
            pos = context.portfolio.positions[sec]
            if pos.total_amount > 0:
                smart_order_target_value(sec, 0, context)
                log.info(f"📤 卖出不在目标的持仓：{sec} {get_name(sec)}")
    
    # 再买入目标ETF（等权分配）
    total_val = context.portfolio.total_value
    target_per_etf = total_val / len(target_etfs)
    
    for etf in target_etfs:
        current_val = 0
        if etf in context.portfolio.positions:
            pos = context.portfolio.positions[etf]
            if pos.total_amount > 0:
                current_val = pos.total_amount * pos.price
        if abs(current_val - target_per_etf) > target_per_etf * 0.05 or current_val == 0:
            smart_order_target_value(etf, target_per_etf, context)
            action = "买入" if current_val < target_per_etf else "调仓"
            log.info(f"📦 {action}：{etf} {get_name(etf)} 目标金额{target_per_etf:.2f}")
    
    log.info("========== 交易完成 ==========")
    #https://cloud.redis.io  免费中转站服务器
    #Q端获取代码网盘没搞好，直接放这下面运行错误。 需要的+qq848303186收到后发你们
 