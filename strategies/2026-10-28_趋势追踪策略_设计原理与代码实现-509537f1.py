# Clone from JoinQuant
# postId: 509537f14c71f2696545cb31da85d4a4
# backtestId: edf0cf6e91b9da50e6ca19370c6955a9
# title: 趋势追踪策略：设计原理与代码实现

# 导入聚宽库
import jqdata
import pandas as pd
import numpy as np

# ====================== 策略核心类 ======================
class DelphiIIAggressiveV2:
    def __init__(self,
                 atr_period=14,
                 atr_multiplier=1.05,
                 stop_multiplier=1.5,
                 adx_period=14,
                 adx_threshold=19,
                 ma_period=20,
                 lock_atr_mult=1.7,
                 max_trades_per_day=4,
                 breakout_days=1,
                 volume_ratio=1.1,
                 time_stop_days=7,
                 max_drawdown_stop=0.08):
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier
        self.stop_multiplier = stop_multiplier
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold
        self.ma_period = ma_period
        self.lock_atr_mult = lock_atr_mult
        self.max_trades_per_day = max_trades_per_day
        self.breakout_days = breakout_days
        self.volume_ratio = volume_ratio
        self.time_stop_days = time_stop_days
        self.max_drawdown_stop = max_drawdown_stop

    @staticmethod
    def _wilder_smooth(series, period):
        smoothed = series.copy()
        if len(series) < period:
            smoothed[:] = np.nan
            return smoothed
        alpha = 1.0 / period
        smoothed.iloc[period-1] = series.iloc[:period].mean()
        for i in range(period, len(series)):
            smoothed.iloc[i] = (1 - alpha) * smoothed.iloc[i-1] + alpha * series.iloc[i]
        return smoothed

    def _calc_atr(self, high, low, close):
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return self._wilder_smooth(tr, self.atr_period)

    def _calc_adx(self, high, low, close):
        period = self.adx_period
        up_move = high.diff()
        down_move = -low.diff()
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
        tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
        atr_series = self._wilder_smooth(tr, period)
        plus_di = 100 * self._wilder_smooth(pd.Series(plus_dm, index=tr.index), period) / atr_series
        minus_di = 100 * self._wilder_smooth(pd.Series(minus_dm, index=tr.index), period) / atr_series
        sum_di = plus_di + minus_di
        sum_di = sum_di.where(sum_di != 0, 1e-8)
        dx = (abs(plus_di - minus_di) / sum_di) * 100
        adx = self._wilder_smooth(dx, period)
        return adx

    def generate_signals(self, df):
        df = df.copy()
        df['ATR'] = self._calc_atr(df['high'], df['low'], df['close'])
        df['ADX'] = self._calc_adx(df['high'], df['low'], df['close'])
        df['UpperBand'] = df['close'].shift(1) + df['ATR'].shift(1) * self.atr_multiplier
        df['MA20'] = df['close'].rolling(self.ma_period).mean()
        df['VolMA20'] = df['volume'].rolling(20).mean()

        pos = 0
        entry_price = 0.0
        entry_atr = 0.0
        highest_price = 0.0
        stop_price = 0.0
        profit_lock = None
        break_upper_count = 0
        signals = []
        hold_days = 0

        for i in range(len(df)):
            price = df['close'].iloc[i]
            atr = df['ATR'].iloc[i]
            adx = df['ADX'].iloc[i]
            upper = df['UpperBand'].iloc[i]
            ma20 = df['MA20'].iloc[i]
            volume = df['volume'].iloc[i]
            vol_ma20 = df['VolMA20'].iloc[i]

            if pd.isna(atr) or pd.isna(adx) or pd.isna(upper):
                signals.append(0)
                break_upper_count = 0
                continue

            if price > upper:
                break_upper_count += 1
            else:
                break_upper_count = 0

            adx_ok = adx > self.adx_threshold
            above_ma20 = price >= ma20 if not pd.isna(ma20) else True
            volume_ok = volume > vol_ma20 * self.volume_ratio if not pd.isna(vol_ma20) else True

            if pos == 0:
                if break_upper_count >= self.breakout_days and adx_ok and above_ma20 and volume_ok:
                    pos = 1
                    entry_price = price
                    entry_atr = atr
                    highest_price = price
                    stop_price = price - atr * self.stop_multiplier
                    profit_lock = None
                    hold_days = 0
                    signals.append(1)
                else:
                    signals.append(0)
            elif pos == 1:
                hold_days += 1
                if price > highest_price:
                    highest_price = price
                if price >= entry_price + self.lock_atr_mult * entry_atr:
                    lock_candidate = entry_price + (price - entry_price) * 0.5
                    profit_lock = lock_candidate if profit_lock is None else max(profit_lock, lock_candidate)
                effective_stop = stop_price
                if profit_lock is not None:
                    effective_stop = max(stop_price, profit_lock)
                if hold_days >= self.time_stop_days:
                    signals.append(0)
                    pos = 0
                    continue
                if (highest_price - price) / highest_price >= self.max_drawdown_stop:
                    signals.append(0)
                    pos = 0
                    continue
                if price <= effective_stop:
                    signals.append(0)
                    pos = 0
                else:
                    signals.append(1)
        df['signal'] = signals
        return df

# ====================== 全局变量与缓存 ======================
strategy = None
daily_trade_count = {}
CACHE = {}
CACHE_DATE = None
INDICATOR_CACHE = {}
MIN_BARS = 60

def initialize(context):
    global strategy
    set_option('use_real_price', True)
    set_benchmark('000300.XSHG')
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.001,
        open_commission=0.0003, close_commission=0.0003,
        min_commission=5
    ), type='stock')

    strategy = DelphiIIAggressiveV2(
        atr_period=14,
        atr_multiplier=1.05,
        stop_multiplier=1.5,
        adx_period=14,
        adx_threshold=19,
        ma_period=20,
        lock_atr_mult=1.7,
        max_trades_per_day=4,
        breakout_days=1,
        volume_ratio=1.1,
        time_stop_days=7,
        max_drawdown_stop=0.08
    )

    g.max_positions = 10
    g.single_position_ratio = 0.20
    g.benchmark_ma_period = 200
    g.stock_pool = []
    g.last_update_date = None

    run_daily(handle_bar, time='09:35')
    log.info("策略初始化完成（开仓版本，沪深300+中证500）")

def get_stock_data(stock, context, count=80):
    global CACHE, CACHE_DATE
    today = context.current_dt.date()
    if CACHE_DATE != today:
        CACHE.clear()
        INDICATOR_CACHE.clear()
        CACHE_DATE = today
    if stock not in CACHE:
        df = get_price(stock, end_date=context.previous_date, count=count, frequency='daily', skip_paused=True)
        if df is None or len(df) < MIN_BARS:
            return None
        CACHE[stock] = df
    return CACHE[stock]

def get_stock_indicators(stock, context):
    if stock in INDICATOR_CACHE:
        return INDICATOR_CACHE[stock]
    df = get_stock_data(stock, context)
    if df is None:
        return None
    df_tail = df.tail(60)
    atr = strategy._calc_atr(df_tail.high, df_tail.low, df_tail.close)
    adx = strategy._calc_adx(df_tail.high, df_tail.low, df_tail.close)
    upper = df_tail.close.shift(1) + atr.shift(1) * strategy.atr_multiplier
    ma20 = df_tail.close.rolling(20).mean()
    vol_ma20 = df_tail.volume.rolling(20).mean()

    res = {
        'close': df_tail.close.iloc[-1],
        'upper': upper.iloc[-1],
        'adx': adx.iloc[-1],
        'ma20': ma20.iloc[-1],
        'vol_ma20': vol_ma20.iloc[-1],
        'volume': df_tail.volume.iloc[-1]
    }
    INDICATOR_CACHE[stock] = res
    return res

def ultra_quick_filter(stock, context):
    """极简预筛选：收盘价 > 20日均线"""
    ind = get_stock_indicators(stock, context)
    if ind is None:
        return False
    if ind['close'] < ind['ma20']:
        return False
    return True

def quick_check(stock, context):
    """完整预筛选（不含连续突破计数）"""
    ind = get_stock_indicators(stock, context)
    if ind is None:
        return False
    if ind['close'] <= ind['upper']:
        return False
    if ind['adx'] <= strategy.adx_threshold:
        return False
    if ind['close'] < ind['ma20']:
        return False
    if ind['volume'] < ind['vol_ma20'] * strategy.volume_ratio:
        return False
    return True

def get_benchmark_data(context, count=250):
    df = get_price('000300.XSHG', end_date=context.previous_date, count=count, frequency='daily', fields=['close'])
    if df is None or len(df) < 200:
        return None
    df['MA200'] = df['close'].rolling(200).mean()
    return df

def update_stock_pool(context):
    if g.last_update_date == context.current_dt.date():
        return
    g.last_update_date = context.current_dt.date()
    try:
        hs300 = get_index_stocks('000300.XSHG', date=context.previous_date)
        zz500 = get_index_stocks('000905.XSHG', date=context.previous_date)  # 修正中证500代码
        g.stock_pool = list(set(hs300 + zz500))
        log.info("股票池更新完成，总标的数量: %d (沪深300: %d, 中证500: %d)" % 
                 (len(g.stock_pool), len(hs300), len(zz500)))
    except Exception as e:
        log.error("更新股票池出错: %s" % str(e))
        g.stock_pool = []

# ====================== 每日主逻辑（开仓版本） ======================
def handle_bar(context):
    global daily_trade_count
    today = context.current_dt.date()
    if today not in daily_trade_count:
        daily_trade_count[today] = 0

    log.info("===== 新交易日: %s =====" % today)

    # 大盘环境判断（200日均线）
    benchmark = get_benchmark_data(context, 250)
    market_ok = True
    if benchmark is not None:
        last_close = benchmark['close'].iloc[-1]
        last_ma200 = benchmark['MA200'].iloc[-1]
        if last_close < last_ma200:
            market_ok = False
            log.info("大盘状态: 收盘=%.2f < MA200=%.2f 【弱势行情，暂停开新仓】" % (last_close, last_ma200))
        else:
            log.info("大盘状态: 收盘=%.2f >= MA200=%.2f 【强势行情，允许开仓】" % (last_close, last_ma200))
    else:
        log.warn("大盘数据不足200根，默认允许开仓")

    # 更新股票池
    update_stock_pool(context)
    if not g.stock_pool:
        log.warn("股票池为空，跳过")
        return

    total_value = context.portfolio.total_value
    cash = context.portfolio.available_cash
    log.info("账户总资产: %.2f | 可用现金: %.2f" % (total_value, cash))

    positions = context.portfolio.positions
    actual_holdings = [s for s in positions if positions[s].total_amount > 0]
    log.info("当前持仓标的数量: %d" % len(actual_holdings))

    # 平仓检查（持仓股票）
    for stock in actual_holdings:
        df = get_stock_data(stock, context)
        if df is None:
            log.warn("%s 获取K线数据失败" % stock)
            continue
        sig_df = strategy.generate_signals(df)
        last_sig = sig_df['signal'].iloc[-1]
        last_price = sig_df['close'].iloc[-1]
        log.info("持仓标的 %s 最新价格: %.2f , 持仓信号: %d (1持有/0平仓)" % (stock, last_price, last_sig))
        if last_sig == 0:
            order_target(stock, 0)
            log.info("【平仓】%s 已全部清仓" % stock)

    # 重新获取实际持仓（平仓后）
    actual_holdings = [s for s in positions if positions[s].total_amount > 0]

    # 开仓限制
    if len(actual_holdings) >= g.max_positions:
        log.info("已达最大持仓数 %d，不再开新仓" % g.max_positions)
        return
    if daily_trade_count[today] >= strategy.max_trades_per_day:
        log.info("今日已达最大开仓次数 %d" % strategy.max_trades_per_day)
        return
    if not market_ok:
        log.info("大盘处于200日均线下方，不开新仓")
        return

    # 扫描股票池（三级筛选）
    # 第一级：极简过滤（收盘价 > 20日均线）
    ultra_candidates = []
    for stock in g.stock_pool:
        if stock in actual_holdings:
            continue
        if ultra_quick_filter(stock, context):
            ultra_candidates.append(stock)
    log.info("极简过滤后剩余 %d 只股票" % len(ultra_candidates))

    # 第二级：完整预筛选（ADX、上轨突破、成交量）
    filtered = []
    for stock in ultra_candidates:
        if quick_check(stock, context):
            filtered.append(stock)
    log.info("完整预筛选通过 %d 只股票" % len(filtered))

    if not filtered:
        log.info("无候选股票")
        return

    # 第三级：获取完整信号并计算强度
    candidates = []
    for stock in filtered:
        df = get_stock_data(stock, context)
        if df is None:
            continue
        sig_df = strategy.generate_signals(df)
        last_sig = sig_df['signal'].iloc[-1]
        if last_sig == 1:
            last_close = sig_df['close'].iloc[-1]
            upper = sig_df['UpperBand'].iloc[-1]
            atr = sig_df['ATR'].iloc[-1]
            strength = (last_close - upper) / atr if atr > 0 else 0
            candidates.append((stock, strength, last_close))

    if not candidates:
        log.info("无满足完整开仓信号的股票")
        return

    # 按信号强度降序排序
    candidates.sort(key=lambda x: x[1], reverse=True)
    slots_available = g.max_positions - len(actual_holdings)
    to_buy = min(slots_available, len(candidates), strategy.max_trades_per_day - daily_trade_count[today])

    for i in range(to_buy):
        stock, strength, price = candidates[i]
        target_value = total_value * g.single_position_ratio
        if cash < target_value:
            target_value = cash * 0.95
        if target_value < 5000:
            log.info("可用资金不足5000，停止买入")
            break
        order_value(stock, target_value)
        daily_trade_count[today] += 1
        log.info("【开多】%s @ %.2f , 强度=%.4f , 单仓配比=%.2f , 当日已开仓 %d 次" % 
                 (stock, price, strength, g.single_position_ratio, daily_trade_count[today]))
        if daily_trade_count[today] >= strategy.max_trades_per_day:
            break