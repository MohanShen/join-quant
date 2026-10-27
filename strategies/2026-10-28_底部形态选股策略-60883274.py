# Clone from JoinQuant
# postId: 608832742e7d9344eaae1598cf527b10
# backtestId: 76fc632e9125f7b0c8e65b267ee6192f
# title: 底部形态选股策略

from jqdata import *
import datetime as dt
import numpy as np
import pandas as pd


# ==================== 股票池：大周期选股参数 ====================
UNIVERSE_MODE = 'all'  # 全A；改 'index' 则只用中证500+1000
UNIVERSE_INDEXES = ['000905.XSHG', '000852.XSHG']
LCS_MIN_SCORE = 75
LCS_ONLY_RELAY = True  # 本副本只研究中继
LCS_MIN_FLOAT_CAP_YI = 100.0
LCS_HIST_COUNT = 160
LCS_MIN_BARS = 130
MIN_LIST_DAYS = 120

BOTTOM_DROP_MIN = 0.30
BOTTOM_DAY_RET_MIN = 0.015
BOTTOM_VOL_MA10_MULT = 1.2
BOTTOM_RSI_OVERSOLD = 30.0
BOTTOM_RSI_RECOVER = 40.0
BOTTOM_PROBE_LOOKBACK = 60
BOTTOM_PROBE_PCT = 0.05
BOTTOM_PROBE_VOL_MULT = 1.5

RELAY_BOUNCE_MIN = 0.10
RELAY_BOUNCE_MAX = 0.40
RELAY_RET10_LO = -0.10
RELAY_RET10_HI = 0.20
RELAY_DAY_RET_MIN = 0.015
RELAY_VOL_MA10_MULT = 1.2
MARKET_INDEX = '000001.XSHG'
MARKET_WARNING_MA_DAYS = 10


# ==================== 日线短线买点参数 ====================
MACD_FAST, MACD_SLOW, MACD_SIGNAL = 8, 17, 9
ATR_CONTRACT_RATIO = 0.95
MA20_SLOPE_LOOKBACK = 3
MA20_TOUCH_PCT = 0.02      # 近3日最低价落到 MA20 上方 2% 以内视为回踩
MA20_BREAK_WICK_PCT = 0.005  # 允许最低价略刺破 MA20 0.5%，收盘仍须不破

SESAME_VS_MA10 = 0.35
SESAME_VS_MAX10 = 0.25
EXTREME_VS_PREV = 0.50
EXTREME_VS_MA5 = 0.40
MA_NEAR_PCT = 0.035

PTS_MA_GOLDEN = 16
PTS_MA_NEAR = 18
PTS_MA20 = 15
PTS_FRACTAL = 12
PTS_RSI = 8
PTS_KDJ = 6
SCORE_MAX = 59
SCAN_TIMES = ('15:00',)
# 只买这一组；空字符串则退回「按软分排序补满5仓」
SOFT_BUY_ITEMS = '底分型+RSI+KDJ'
REQUIRE_GRAVITY = True      # 重心未抬升则不买


# ==================== 交易与日志 ====================
MAX_POSITIONS = 5
STOP_LOSS_PCT = 0.02
EARLY_LOCK_TRIGGER = 0.03   # 浮盈达到 +3% 后启动保本锁
EARLY_LOCK_PCT = 0.01       # 止损上移至成本 +1%
LOCK_FEE_PCT = 0.001        # 另加 0.1% 覆盖手续费 → 实际锁在 +1.1%
TIME_EXIT_TRADE_DAYS = 5    # 买入后第几个交易日收盘检查
TIME_EXIT_MIN_GAIN = 0.02   # 累计涨幅须超过 +2%，否则平仓
RECENT_HIGH_BARS = 5        # 「近期新高」对比买入前近5日最高价
PROFIT_GUARD_PCT = 0.07
LOCK_AFTER_GUARD_PCT = 0.05
ATR_PERIOD = 14
ATR_STOP_MULT = 2.0
ATR_STOP_MULT_TIGHT = 1.2
MIN_LOT = 100

TRADE_LOG_ENABLED = True
TRADE_LOG_CSV = 'short_buy_relay_trades.csv'
SIGNAL_LOG_CSV = 'short_buy_relay_signals.csv'
DAILY_LOG_CSV = 'short_buy_relay_daily.csv'


# ==================== 通用指标 ====================
def _to_date(value):
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return pd.Timestamp(value).date()


def _finite(value, default=np.nan):
    try:
        value = float(value)
        return value if np.isfinite(value) else default
    except Exception:
        return default


def _ema(values, span):
    return pd.Series(np.asarray(values, dtype=float)).ewm(
        span=span, adjust=False
    ).mean().values


def _macd(close, fast=12, slow=26, signal=9):
    dif = _ema(close, fast) - _ema(close, slow)
    dea = _ema(dif, signal)
    hist = (dif - dea) * 2
    return dif, dea, hist


def _rsi(close, period=14):
    c = pd.Series(np.asarray(close, dtype=float))
    delta = c.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).values


def _kdj(high, low, close, n=9):
    h, l, c = pd.Series(high), pd.Series(low), pd.Series(close)
    lowest = l.rolling(n).min()
    highest = h.rolling(n).max()
    rsv = (c - lowest) / (highest - lowest).replace(0, np.nan) * 100
    k = rsv.ewm(com=2, adjust=False).mean()
    d = k.ewm(com=2, adjust=False).mean()
    return k.values, d.values, (3 * k - 2 * d).values


def _boll(close, n=20, k=2.0):
    s = pd.Series(np.asarray(close, dtype=float))
    mid = s.rolling(n).mean()
    std = s.rolling(n).std()
    return (mid + k * std).values, mid.values, (mid - k * std).values


def _tr_series(high, low, close):
    high, low, close = map(lambda x: np.asarray(x, dtype=float), (high, low, close))
    tr = np.full(len(close), np.nan)
    if len(close):
        tr[0] = high[0] - low[0]
    for i in range(1, len(close)):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )
    return tr


def _atr_last(high, low, close, period):
    tr = _tr_series(high, low, close)
    if len(tr) < period:
        return None
    value = pd.Series(tr).rolling(period).mean().iloc[-1]
    return None if pd.isna(value) else float(value)


def _golden_cross(fast, slow):
    if len(fast) < 2:
        return False
    vals = (fast[-2], fast[-1], slow[-2], slow[-1])
    return not any(pd.isna(x) for x in vals) and fast[-2] <= slow[-2] and fast[-1] > slow[-1]


def _ma_slope_up(ma, lookback=3):
    if len(ma) <= lookback or pd.isna(ma[-1]) or pd.isna(ma[-1 - lookback]):
        return False
    return ma[-1] > ma[-1 - lookback]


# ==================== 大周期选股 ====================
def _filter_board(stocks):
    out = []
    for stock in stocks:
        code = str(stock).split('.')[0]
        if code.startswith(('688', '689', '8', '4')) or str(stock).endswith('.XBJ'):
            continue
        try:
            info = get_security_info(stock)
            name = (info.display_name or '') if info else ''
            if 'ST' in name.upper() or '退' in name:
                continue
        except Exception:
            continue
        out.append(stock)
    return out


def _cap_ok(stock, date_str):
    try:
        q = query(valuation.circulating_market_cap).filter(valuation.code == stock)
        frame = get_fundamentals(q, date=date_str)
        if frame is not None and not frame.empty:
            return float(frame.iloc[0]['circulating_market_cap']) >= LCS_MIN_FLOAT_CAP_YI
    except Exception:
        pass
    return True


def _daily_bars(stock, end_date, count=LCS_HIST_COUNT):
    try:
        frame = get_price(
            stock, end_date=end_date, frequency='daily',
            fields=['open', 'high', 'low', 'close', 'volume', 'money'],
            skip_paused=True, fq='pre', count=count,
        )
        if frame is None or frame.empty:
            return None
        frame = frame.replace([np.inf, -np.inf], np.nan).dropna(
            subset=['open', 'high', 'low', 'close', 'volume']
        )
        return frame.reset_index(drop=True)
    except Exception:
        return None


def _macd_green_shorten_or_gc(dif, dea, hist):
    if len(dif) < 3:
        return False
    if np.isfinite(dif[-1]) and np.isfinite(dea[-1]) and dif[-1] > dea[-1]:
        return True
    h1, h2, h3 = hist[-3], hist[-2], hist[-1]
    return not any(pd.isna(x) for x in (h1, h2, h3)) and h1 < 0 and h3 > h2 > h1


def _probe_yang(close, volume, vol_ma60):
    start = max(1, len(close) - BOTTOM_PROBE_LOOKBACK)
    for i in range(start, len(close)):
        prev, cur = _finite(close[i - 1], 0), _finite(close[i], 0)
        vma, vol = _finite(vol_ma60[i], 0), _finite(volume[i], 0)
        if prev > 0 and (cur - prev) / prev > BOTTOM_PROBE_PCT:
            if vma > 0 and vol > vma * BOTTOM_PROBE_VOL_MULT:
                return True
    return False


def _score_bottom(frame):
    c = frame['close'].values.astype(float)
    h = frame['high'].values.astype(float)
    l = frame['low'].values.astype(float)
    v = frame['volume'].values.astype(float)
    if len(c) < LCS_MIN_BARS:
        return 0, {}
    ma5 = pd.Series(c).rolling(5).mean().values
    ma10 = pd.Series(c).rolling(10).mean().values
    ma20 = pd.Series(c).rolling(20).mean().values
    vma10 = pd.Series(v).rolling(10).mean().values
    vma60 = pd.Series(v).rolling(60).mean().values
    dif, dea, hist = _macd(c)
    rsi = _rsi(c, 14)
    high120 = _finite(np.nanmax(h[-120:]), 0)
    drop = (high120 - c[-1]) / high120 if high120 > 0 else 0
    day_ret = c[-1] / c[-2] - 1 if c[-2] > 0 else 0
    atr20 = _atr_last(h, l, c, 20)
    atr60 = _atr_last(h, l, c, 60)
    rsi_win = rsi[-20:]
    rsi_ok = (
        np.isfinite(rsi_win).any()
        and np.nanmin(rsi_win) < BOTTOM_RSI_OVERSOLD
        and _finite(rsi[-1], 0) >= BOTTOM_RSI_RECOVER
    )
    tests = [
        ('120日跌幅>30%', 15, drop > BOTTOM_DROP_MIN),
        ('收盘站上MA20', 15, np.isfinite(ma20[-1]) and c[-1] > ma20[-1]),
        ('20日ATR<60日ATR', 15, atr20 is not None and atr60 is not None and atr20 < atr60),
        ('近10日均量<60日均量', 10, _finite(vma60[-1], 0) > 0 and np.mean(v[-10:]) < vma60[-1]),
        ('MACD绿柱缩短或已金叉', 10, _macd_green_shorten_or_gc(dif, dea, hist)),
        ('MA5金叉MA10', 20, _golden_cross(ma5, ma10)),
        ('涨幅>1.5%且放量', 10, day_ret > BOTTOM_DAY_RET_MIN and _finite(vma10[-1], 0) > 0 and v[-1] > vma10[-1] * BOTTOM_VOL_MA10_MULT),
        ('RSI超卖回升', 5, rsi_ok),
        ('近60日放量试盘', 5, _probe_yang(c, v, vma60)),
    ]
    return sum(pts for _, pts, hit in tests if hit), {
        'items': {name: pts if hit else 0 for name, pts, hit in tests},
        'score_max': 105,
    }


def _score_relay(frame):
    c = frame['close'].values.astype(float)
    h = frame['high'].values.astype(float)
    l = frame['low'].values.astype(float)
    v = frame['volume'].values.astype(float)
    if len(c) < 80:
        return 0, {}
    ma10 = pd.Series(c).rolling(10).mean().values
    ma20 = pd.Series(c).rolling(20).mean().values
    vma10 = pd.Series(v).rolling(10).mean().values
    atr10 = _atr_last(h, l, c, 10)
    atr20 = _atr_last(h, l, c, 20)
    low60 = _finite(np.nanmin(l[-60:]), 0)
    bounce = (c[-1] - low60) / low60 if low60 > 0 else 0
    ret10 = c[-1] / c[-10] - 1 if c[-10] > 0 else 0
    above_ma20 = all(
        np.isfinite(c[i]) and np.isfinite(ma20[i]) and c[i] > ma20[i]
        for i in range(len(c) - 10, len(c))
    )
    day_ret = c[-1] / c[-2] - 1 if c[-2] > 0 else 0
    high5 = np.nanmax(h[-6:-1])
    tests = [
        ('60日低点反弹10%~40%', 20, RELAY_BOUNCE_MIN <= bounce <= RELAY_BOUNCE_MAX),
        ('ATR10<ATR20', 15, atr10 is not None and atr20 is not None and atr10 < atr20),
        ('近10日收盘在MA20上', 15, above_ma20),
        ('近10日涨跌-10%~20%', 10, RELAY_RET10_LO <= ret10 <= RELAY_RET10_HI),
        ('当日涨幅>1.5%', 10, day_ret > RELAY_DAY_RET_MIN),
        ('当日量>MA10×1.2', 10, _finite(vma10[-1], 0) > 0 and v[-1] > vma10[-1] * RELAY_VOL_MA10_MULT),
        ('MA10斜率向上', 10, _ma_slope_up(ma10, 3)),
        ('突破近5日高', 10, c[-1] > high5),
    ]
    return sum(pts for _, pts, hit in tests if hit), {
        'items': {name: pts if hit else 0 for name, pts, hit in tests},
        'score_max': 100,
    }


def _lcs_evaluate(frame):
    if frame is None or len(frame) < 80:
        return None
    if LCS_ONLY_RELAY:
        relay, r_detail = _score_relay(frame)
        if relay < LCS_MIN_SCORE:
            return None
        return {'score': relay, 'mode': 'relay', 'detail': r_detail}
    if len(frame) < LCS_MIN_BARS:
        return None
    bottom, b_detail = _score_bottom(frame)
    relay, r_detail = _score_relay(frame)
    if bottom >= relay:
        score, mode, detail = bottom, 'bottom', b_detail
    else:
        score, mode, detail = relay, 'relay', r_detail
    if score < LCS_MIN_SCORE:
        return None
    return {'score': score, 'mode': mode, 'detail': detail}


def _sh_index_vs_ma10(context, end_date=None):
    """上证收盘是否站上 MA10。取不到数据时视为未站上，禁止开仓。"""
    end_date = end_date if end_date is not None else context.current_dt
    try:
        frame = get_price(
            MARKET_INDEX, end_date=end_date, frequency='daily',
            fields=['close'], skip_paused=True, fq='pre',
            count=MARKET_WARNING_MA_DAYS + 5,
        )
        if frame is None or len(frame) < MARKET_WARNING_MA_DAYS:
            return {'above': False, 'close': None, 'ma10': None}
        close = float(frame['close'].iloc[-1])
        ma10 = float(frame['close'].tail(MARKET_WARNING_MA_DAYS).mean())
        return {'above': close >= ma10, 'close': close, 'ma10': ma10}
    except Exception:
        return {'above': False, 'close': None, 'ma10': None}


def _log_sh_index_gate(context, state, action):
    close, ma10 = state.get('close'), state.get('ma10')
    if close is None or ma10 is None:
        log.info('预警：上证MA10数据缺失，%s' % action)
        return
    if state['above']:
        log.info('上证站上MA10 close=%.2f ma10=%.2f，%s' % (close, ma10, action))
    else:
        log.info('预警：上证未站上MA10 close=%.2f ma10=%.2f，%s' % (close, ma10, action))


def _is_lcs_refresh_day(context):
    """本周第一个交易日刷新大周期池；回测首日池为空也会建池。"""
    if not getattr(g, 'lcs_pool', None):
        return True
    today = _to_date(context.current_dt)
    prev = _to_date(context.previous_date)
    return prev.isocalendar()[:2] != today.isocalendar()[:2]


def before_open_daily(context):
    g.scanned_today = set()
    open_state = _sh_index_vs_ma10(context, context.previous_date)
    g.sh_above_ma10 = bool(open_state['above'])
    if not open_state['above']:
        _log_sh_index_gate(context, open_state, '今日开盘预警，15:00前仍以收盘再判是否允许买入')
    if _is_lcs_refresh_day(context):
        build_lcs_pool(context)
        return
    names = [x['stock'] for x in g.lcs_pool]
    if names:
        set_universe(names)
    log.info('沿用大周期池=%d 建池日=%s' % (
        len(g.lcs_pool), getattr(g, 'lcs_pool_date', ''),
    ))


def build_lcs_pool(context):
    """用上一交易日完整日K生成本周大周期池。"""
    ref = context.previous_date
    date_str = _to_date(ref).strftime('%Y-%m-%d')
    stocks = []
    try:
        if UNIVERSE_MODE == 'all':
            stocks = list(get_all_securities(['stock'], date=date_str).index)
        else:
            for index_code in UNIVERSE_INDEXES:
                stocks.extend(get_index_stocks(index_code, date=date_str))
            stocks = list(dict.fromkeys(stocks))
    except Exception as exc:
        log.info('基础股票池读取失败: %s' % exc)
        return

    stocks = _filter_board(stocks)
    selected = []
    for stock in stocks:
        try:
            info = get_security_info(stock)
            if not info or not info.start_date:
                continue
            if (_to_date(ref) - _to_date(info.start_date)).days < MIN_LIST_DAYS:
                continue
        except Exception:
            continue
        if not _cap_ok(stock, date_str):
            continue
        hit = _lcs_evaluate(_daily_bars(stock, ref))
        if hit and hit['score'] >= LCS_MIN_SCORE:
            selected.append({
                'stock': stock,
                'lcs_score': hit['score'],
                'lcs_mode': hit['mode'],
            })
    selected.sort(key=lambda x: (-x['lcs_score'], str(x['stock'])))
    g.lcs_pool = selected
    g.lcs_meta = {x['stock']: x for x in selected}
    g.lcs_pool_date = date_str
    set_universe([x['stock'] for x in selected])
    log.info('%s 重建大周期池=%d 门槛=%d' % (
        date_str, len(selected), LCS_MIN_SCORE,
    ))


def _bars_for_close_scan(stock, context):
    """15:00 收盘扫描：使用含当日完整日K，不再做盘中量能折算。"""
    frame = _daily_bars(stock, context.current_dt, count=120)
    if frame is None or len(frame) < 30:
        return None, {}
    vol = float(frame['volume'].iloc[-1])
    return frame, {
        'raw_volume': vol,
        'projected_volume': vol,
        'elapsed_fraction': 1.0,
    }


# ==================== 日线版短线买点 ====================
def _ma_setup(close):
    s = pd.Series(close)
    ma5, ma10 = s.rolling(5).mean(), s.rolling(10).mean()
    if len(s) < 12 or any(pd.isna(x) for x in (ma5.iloc[-1], ma10.iloc[-1], ma5.iloc[-2], ma10.iloc[-2])):
        return 'none', {}
    m5, m10 = float(ma5.iloc[-1]), float(ma10.iloc[-1])
    p5, p10 = float(ma5.iloc[-2]), float(ma10.iloc[-2])
    slope_up, ma10_up = m5 > p5, m10 >= p10
    price = max(float(close[-1]), 1e-8)
    meta = {'ma5': m5, 'ma10': m10}
    golden1 = p5 <= p10 and m5 > m10
    golden2 = False
    if len(s) >= 13 and not any(pd.isna(x) for x in (ma5.iloc[-3], ma10.iloc[-3])):
        golden2 = ma5.iloc[-3] <= ma10.iloc[-3] and p5 > p10 and m5 > m10
    if (golden1 or golden2) and slope_up and ma10_up and price >= min(m5, m10) * 0.995:
        return 'golden', meta
    gap = abs(m5 - m10) / price
    converging = m5 < m10 and p5 <= p10 and (m10 - m5) < (p10 - p5)
    if m5 < m10 and slope_up and (converging or gap <= MA_NEAR_PCT):
        return 'near', meta
    return 'none', meta


def _volume_shrink(volume):
    cur = float(volume[-1])
    history = np.asarray(volume[:-1], dtype=float)
    if len(history) < 5:
        return False, {}
    ma10 = float(np.mean(history[-10:]))
    ma5 = float(np.mean(history[-5:]))
    max10 = float(np.max(history[-10:]))
    prev = float(history[-1])
    sesame = cur <= ma10 * SESAME_VS_MA10 or cur <= max10 * SESAME_VS_MAX10
    extreme = cur <= prev * EXTREME_VS_PREV or cur <= ma5 * EXTREME_VS_MA5
    return bool(sesame or extreme), {
        'sesame': sesame, 'extreme': extreme, 'vs_prev': cur / prev if prev > 0 else None,
    }


def _macd_setup(close):
    dif, dea, hist = _macd(close, MACD_FAST, MACD_SLOW, MACD_SIGNAL)
    i = len(close) - 1
    for back in (0, 1):
        j = i - back
        if j >= 1 and dif[j - 1] <= dea[j - 1] and dif[j] > dea[j]:
            if dif[i] > dea[i]:
                return 'golden', {'dif': dif[i], 'dea': dea[i]}
    if dif[i] < dea[i]:
        gap = abs(dif[i] - dea[i]) / max(abs(dif[i]), abs(dea[i]), 1e-8)
        if dif[i] > dif[i - 1] and gap <= 0.15:
            return 'near', {'dif': dif[i], 'dea': dea[i], 'gap': gap}
    return 'none', {'dif': dif[i], 'dea': dea[i]}


def _ma20_pullback_hold(close, low):
    """回踩 MA20 不破，且 MA20 斜率向上。"""
    if len(close) < 20 + MA20_SLOPE_LOOKBACK + 1:
        return False, {}
    ma20 = pd.Series(close).rolling(20).mean()
    m_now = ma20.iloc[-1]
    m_prev = ma20.iloc[-1 - MA20_SLOPE_LOOKBACK]
    if pd.isna(m_now) or pd.isna(m_prev) or float(m_now) <= 0:
        return False, {}
    m_now, m_prev = float(m_now), float(m_prev)
    slope_up = m_now > m_prev
    c = float(close[-1])
    hold = c >= m_now
    recent_low = float(np.min(low[-3:]))
    pullback = (
        recent_low <= m_now * (1 + MA20_TOUCH_PCT)
        and recent_low >= m_now * (1 - MA20_BREAK_WICK_PCT)
    )
    return bool(slope_up and hold and pullback), {
        'ma20': m_now,
        'slope_up': slope_up,
        'hold': hold,
        'pullback': pullback,
        'close': c,
        'recent_low': recent_low,
    }


def _gravity_ok(open_, high, low, close):
    tp = (open_ + high + low + close) / 4.0
    if len(tp) < 4:
        return False
    direct = tp[-1] >= tp[-2] >= tp[-3]
    ma3 = pd.Series(tp).rolling(3).mean()
    turn = np.isfinite(ma3.iloc[-1]) and np.isfinite(ma3.iloc[-2]) and ma3.iloc[-1] > ma3.iloc[-2]
    return bool(direct or turn)


def _short_signal(frame):
    open_ = frame['open'].values.astype(float)
    high = frame['high'].values.astype(float)
    low = frame['low'].values.astype(float)
    close = frame['close'].values.astype(float)
    volume = frame['volume'].values.astype(float)

    volume_ok, volume_meta = _volume_shrink(volume)
    macd, macd_meta = _macd_setup(close)
    ma20_ok, ma20_meta = _ma20_pullback_hold(close, low)
    atr3, atr8 = _atr_last(high, low, close, 3), _atr_last(high, low, close, 8)
    atr_ok = atr3 is not None and atr8 is not None and atr3 < atr8 * ATR_CONTRACT_RATIO
    gravity_ok = _gravity_ok(open_, high, low, close)
    flags = {
        'volume': volume_ok,
        'macd': macd in ('golden', 'near'),
        'ma20': ma20_ok,
        'atr': atr_ok,
        'gravity': gravity_ok,
    }

    ma_setup, ma_meta = _ma_setup(close)
    soft_score = PTS_MA_GOLDEN if ma_setup == 'golden' else PTS_MA_NEAR if ma_setup == 'near' else 0
    ma5, ma10 = ma_meta.get('ma5', 0), ma_meta.get('ma10', 0)
    ma20_s = pd.Series(close).rolling(20).mean()
    ma20_soft = (
        len(close) >= 20 and np.isfinite(ma20_s.iloc[-1])
        and ma20_s.iloc[-1] >= ma20_s.iloc[-2] * 0.998
        and (ma5 >= ma20_s.iloc[-1] * 0.98 or ma10 >= ma20_s.iloc[-1] * 0.98)
    )
    if ma20_soft:
        soft_score += PTS_MA20
    fractal = len(low) >= 3 and low[-2] < low[-3] and low[-2] < low[-1]
    if fractal:
        soft_score += PTS_FRACTAL
    rsi = _rsi(close, 14)
    rsi_ok = np.isfinite(rsi[-1]) and rsi[-1] >= 48
    if rsi_ok:
        soft_score += PTS_RSI
    k, d, _ = _kdj(high, low, close)
    kdj_ok = (
        np.isfinite(k[-1]) and np.isfinite(d[-1])
        and ((_golden_cross(k, d)) or (k[-1] >= 50 and d[-1] >= 40))
    )
    if kdj_ok:
        soft_score += PTS_KDJ

    soft_parts = []
    if ma_setup == 'golden':
        soft_parts.append('MA金叉')
    elif ma_setup == 'near':
        soft_parts.append('MA近叉')
    if ma20_soft:
        soft_parts.append('MA20靠近')
    if fractal:
        soft_parts.append('底分型')
    if rsi_ok:
        soft_parts.append('RSI')
    if kdj_ok:
        soft_parts.append('KDJ')
    soft_items = '+'.join(soft_parts) if soft_parts else '全空'

    px = float(close[-1])
    day_ret = px / float(close[-2]) - 1 if len(close) >= 2 and close[-2] > 0 else np.nan
    ma5_s = pd.Series(close).rolling(5).mean()
    ma5_now = float(ma5_s.iloc[-1]) if len(close) >= 5 and np.isfinite(ma5_s.iloc[-1]) else np.nan
    extend_ma5 = px / ma5_now - 1 if np.isfinite(ma5_now) and ma5_now > 0 else np.nan

    return {
        'hit': True,
        'tier': 'soft',
        'combos': [],
        'score': min(SCORE_MAX, int(soft_score)),
        'price': px,
        'flags': flags,
        'macd_setup': macd,
        'volume_meta': volume_meta,
        'macd_meta': macd_meta,
        'ma20_meta': ma20_meta,
        'soft_ma': ma_setup,
        'soft_ma20': bool(ma20_soft),
        'soft_fractal': bool(fractal),
        'soft_rsi': bool(rsi_ok),
        'soft_kdj': bool(kdj_ok),
        'soft_items': soft_items,
        'day_ret': day_ret,
        'extend_ma5': extend_ma5,
    }


def _entry_gate(signal):
    """重心未抬升则禁止开仓（仍写信号日志）。"""
    fails = []
    if REQUIRE_GRAVITY and not signal.get('flags', {}).get('gravity'):
        fails.append('无重心')
    return (not fails), fails


# ==================== 扫描与买入 ====================
def _current_price(stock):
    try:
        data = get_current_data()[stock]
        return float(data.last_price) if data and data.last_price else None
    except Exception:
        return None


def scan_and_buy(context):
    scan_time = context.current_dt.strftime('%H:%M')
    state = _sh_index_vs_ma10(context, context.current_dt)
    g.sh_above_ma10 = bool(state.get('above'))
    if not state.get('above'):
        _log_sh_index_gate(context, state, '停止买入')
        return
    _log_sh_index_gate(context, state, '允许买入')
    held = set(
        stock for stock, pos in context.portfolio.positions.items()
        if pos.total_amount > 0
    )
    candidates = []
    for item in g.lcs_pool:
        stock = item['stock']
        if stock in held or stock in g.scanned_today:
            continue
        frame, partial = _bars_for_close_scan(stock, context)
        if frame is None:
            continue
        signal = _short_signal(frame)
        gate_ok, gate_fails = _entry_gate(signal)
        signal['gate_ok'] = gate_ok
        signal['gate_fail'] = '+'.join(gate_fails)
        _log_signal(context, stock, item, signal, partial, scan_time)
        candidate = dict(item)
        candidate.update(signal)
        if SOFT_BUY_ITEMS and candidate.get('soft_items') != SOFT_BUY_ITEMS:
            continue
        if not gate_ok:
            continue
        candidates.append(candidate)

    candidates.sort(key=lambda x: (
        -x['score'], -x['lcs_score'], str(x['stock'])
    ))
    slots = max(0, MAX_POSITIONS - len(held))
    buys = candidates[:slots]
    cash = context.portfolio.available_cash
    per_cash = cash / slots if slots > 0 else 0
    current = get_current_data()
    bought = 0
    for item in buys:
        stock = item['stock']
        try:
            if current[stock].paused or current[stock].is_st:
                continue
            price = float(current[stock].last_price)
        except Exception:
            price = item.get('price')
        if not price or price <= 0:
            continue
        amount = int(per_cash / price / MIN_LOT) * MIN_LOT
        if amount < MIN_LOT:
            continue
        order(stock, amount)
        bought += 1
        g.entry_price[stock] = price
        g.position_high[stock] = price
        g.ever_profit[stock] = False
        g.early_lock[stock] = False
        g.entry_date[stock] = _to_date(context.current_dt)
        g.scanned_today.add(stock)
        _log_trade({
            'date': str(context.current_dt),
            'action': 'BUY',
            'stock': stock,
            'name': _stock_name(stock),
            'price': round(price, 3),
            'amount': amount,
            'lcs_score': item['lcs_score'],
            'lcs_mode': item['lcs_mode'],
            'tier': item['tier'],
            'short_score': item['score'],
            'soft_items': item.get('soft_items', ''),
            'soft_ma': item.get('soft_ma', ''),
            'soft_ma20': item.get('soft_ma20', ''),
            'soft_fractal': item.get('soft_fractal', ''),
            'soft_rsi': item.get('soft_rsi', ''),
            'soft_kdj': item.get('soft_kdj', ''),
            'scan_time': scan_time,
            'reason': 'soft=%d %s' % (item['score'], item.get('soft_items', '')),
            'day_ret': round(item.get('day_ret', 0) * 100, 2) if np.isfinite(item.get('day_ret', np.nan)) else '',
            'extend_ma5': round(item.get('extend_ma5', 0) * 100, 2) if np.isfinite(item.get('extend_ma5', np.nan)) else '',
            'gravity': item.get('flags', {}).get('gravity', ''),
        })
    log.info('%s 大周期池=%d 候选=%d 买入=%d %s' % (
        scan_time, len(g.lcs_pool), len(candidates), bought,
        [(x['stock'], x['score'], x.get('soft_items', '')) for x in buys],
    ))


# ==================== 风控卖出 ====================
def _position_price(stock, position, data=None):
    if data is not None:
        try:
            bar = data[stock]
            px = float(getattr(bar, 'close', 0) or getattr(bar, 'price', 0) or 0)
            if px > 0:
                return px
        except Exception:
            pass
    price = _current_price(stock)
    return price if price and price > 0 else float(position.price or 0)


def _cached_atr(stock, context):
    key = (str(context.current_dt.date()), stock)
    cache = getattr(g, 'atr_cache', None)
    if cache is None:
        g.atr_cache = {}
        cache = g.atr_cache
    if key in cache:
        return cache[key]
    frame = _daily_bars(stock, context.previous_date, count=ATR_PERIOD + 8)
    atr = None
    if frame is not None:
        atr = _atr_last(
            frame['high'].values, frame['low'].values, frame['close'].values, ATR_PERIOD,
        )
    cache[key] = atr
    return atr


def _close_position(context, stock, entry, price, reason):
    order_target(stock, 0)
    _log_trade({
        'date': str(context.current_dt),
        'action': 'SELL',
        'stock': stock,
        'name': _stock_name(stock),
        'price': round(price, 3),
        'amount': 0,
        'lcs_score': '',
        'lcs_mode': '',
        'tier': '',
        'short_score': '',
        'soft_items': '',
        'soft_ma': '',
        'soft_ma20': '',
        'soft_fractal': '',
        'soft_rsi': '',
        'soft_kdj': '',
        'scan_time': context.current_dt.strftime('%H:%M'),
        'reason': '%s pnl=%.2f%%' % (reason, (price / entry - 1) * 100),
    })
    for mapping in (g.entry_price, g.position_high, g.ever_profit, g.early_lock, g.entry_date):
        mapping.pop(stock, None)


def _held_trade_days_after_entry(context, stock):
    """买入日之后已过的交易日数（不含买入日）。"""
    entry_d = getattr(g, 'entry_date', {}).get(stock)
    if not entry_d:
        return 0
    entry_d = _to_date(entry_d)
    today = _to_date(context.current_dt)
    if today <= entry_d:
        return 0
    try:
        start = entry_d + dt.timedelta(days=1)
        days = get_trade_days(start_date=str(start), end_date=str(today))
        return len(days) if days is not None else 0
    except Exception:
        return 0


def _pre_entry_high(stock, entry_d):
    """买入日前近 RECENT_HIGH_BARS 个交易日的最高价。"""
    try:
        frame = get_price(
            stock, end_date=entry_d, frequency='daily',
            fields=['high'], skip_paused=True, fq='pre',
            count=RECENT_HIGH_BARS + 1,
        )
        if frame is None or frame.empty:
            return None
        last_d = _to_date(frame.index[-1])
        hist = frame.iloc[:-1] if last_d >= _to_date(entry_d) else frame
        if hist.empty:
            return None
        return float(np.nanmax(hist['high'].values))
    except Exception:
        return None


def _holding_high(stock, context, entry_d):
    """买入日（含）至今的最高价。"""
    try:
        frame = get_price(
            stock, end_date=context.current_dt, frequency='daily',
            fields=['high'], skip_paused=True, fq='pre',
            count=TIME_EXIT_TRADE_DAYS + 8,
        )
        if frame is None or frame.empty:
            return None
        entry_d = _to_date(entry_d)
        highs = [
            float(h) for d, h in zip(frame.index, frame['high'].values)
            if _to_date(d) >= entry_d and np.isfinite(h)
        ]
        return max(highs) if highs else None
    except Exception:
        return None


def check_time_exit(context):
    """第5个交易日收盘：必须创出买入前近5日新高且累计涨幅>2%，否则无条件平仓。"""
    for stock in list(context.portfolio.positions.keys()):
        position = context.portfolio.positions[stock]
        if position.total_amount <= 0:
            continue
        if getattr(position, 'closeable_amount', 0) <= 0:
            continue
        if _held_trade_days_after_entry(context, stock) != TIME_EXIT_TRADE_DAYS:
            continue
        entry = float(g.entry_price.get(stock) or position.avg_cost or 0)
        price = _position_price(stock, position)
        if entry <= 0 or not price or price <= 0:
            continue
        gain = price / entry - 1
        entry_d = g.entry_date.get(stock)
        pre_high = _pre_entry_high(stock, entry_d) if entry_d else None
        hold_high = _holding_high(stock, context, entry_d) if entry_d else None
        broke_high = (
            pre_high is not None and hold_high is not None and hold_high > pre_high
        )
        if broke_high and gain > TIME_EXIT_MIN_GAIN:
            continue
        if not broke_high and gain <= TIME_EXIT_MIN_GAIN:
            reason = '5日未新高且未涨2%'
        elif not broke_high:
            reason = '5日未创新高'
        else:
            reason = '5日涨幅未超2%'
        _close_position(context, stock, entry, price, reason)


def check_exit(context, data=None):
    for stock in list(context.portfolio.positions.keys()):
        position = context.portfolio.positions[stock]
        if position.total_amount <= 0:
            continue
        # A股 T+1：当日买入的仓位不可卖，避免记录一笔实际未成交的卖单。
        if getattr(position, 'closeable_amount', 0) <= 0:
            continue
        entry = float(g.entry_price.get(stock) or position.avg_cost or 0)
        price = _position_price(stock, position, data)
        if entry <= 0 or price <= 0:
            continue
        peak = max(float(g.position_high.get(stock) or entry), price)
        g.position_high[stock] = peak
        if price > entry:
            g.ever_profit[stock] = True
        pnl = price / entry - 1
        if pnl <= -STOP_LOSS_PCT:
            _close_position(context, stock, entry, price, '硬止损-2%')
            continue
        peak_gain = peak / entry - 1
        if peak_gain >= EARLY_LOCK_TRIGGER:
            g.early_lock[stock] = True
        stop = None
        reason = None
        if g.early_lock.get(stock):
            stop = entry * (1 + EARLY_LOCK_PCT + LOCK_FEE_PCT)
            reason = '浮盈3%锁+1.1%'
        atr = _cached_atr(stock, context)
        if atr:
            if peak_gain >= PROFIT_GUARD_PCT:
                atr_stop = max(
                    entry * (1 + LOCK_AFTER_GUARD_PCT),
                    peak - ATR_STOP_MULT_TIGHT * atr,
                )
                if stop is None or atr_stop > stop:
                    stop, reason = atr_stop, 'ATR收紧锁利'
            elif g.ever_profit.get(stock) and not g.early_lock.get(stock):
                atr_stop = peak - ATR_STOP_MULT * atr
                if price > entry and (stop is None or atr_stop > stop):
                    stop, reason = atr_stop, 'ATR移动止损'
        if stop is not None and price <= stop:
            _close_position(context, stock, entry, price, reason)


# ==================== 日志 ====================
def _stock_name(stock):
    try:
        info = get_security_info(stock)
        return info.display_name if info else str(stock)
    except Exception:
        return str(stock)


def _log_trade(record):
    g.trade_records.append(record)


def _log_signal(context, stock, lcs, signal, partial, scan_time):
    g.signal_records.append({
        'date': str(context.current_dt.date()),
        'scan_time': scan_time,
        'stock': stock,
        'name': _stock_name(stock),
        'lcs_score': lcs['lcs_score'],
        'lcs_mode': lcs['lcs_mode'],
        'hit': signal['hit'],
        'tier': signal['tier'],
        'short_score': signal['score'],
        'price': round(signal['price'], 3),
        'macd': signal['macd_setup'],
        'volume': signal['flags']['volume'],
        'ma20_hold': signal['flags']['ma20'],
        'atr': signal['flags']['atr'],
        'gravity': signal['flags']['gravity'],
        'day_ret': None if not np.isfinite(signal.get('day_ret', np.nan)) else round(float(signal['day_ret']) * 100, 2),
        'extend_ma5': None if not np.isfinite(signal.get('extend_ma5', np.nan)) else round(float(signal['extend_ma5']) * 100, 2),
        'gate_ok': signal.get('gate_ok', ''),
        'gate_fail': signal.get('gate_fail', ''),
        'soft_items': signal.get('soft_items', ''),
        'soft_ma': signal.get('soft_ma', ''),
        'soft_ma20': signal.get('soft_ma20', False),
        'soft_fractal': signal.get('soft_fractal', False),
        'soft_rsi': signal.get('soft_rsi', False),
        'soft_kdj': signal.get('soft_kdj', False),
        'elapsed_fraction': round(partial.get('elapsed_fraction', 0), 3),
        'projected_volume': round(partial.get('projected_volume', 0), 0),
        'combos': '|'.join(signal['combos']),
    })


def _flush_logs(context):
    if not TRADE_LOG_ENABLED:
        return
    try:
        if g.trade_records:
            write_file(TRADE_LOG_CSV, pd.DataFrame(g.trade_records).to_csv(index=False))
        if g.signal_records:
            write_file(SIGNAL_LOG_CSV, pd.DataFrame(g.signal_records).to_csv(index=False))
        if g.daily_records:
            write_file(DAILY_LOG_CSV, pd.DataFrame(g.daily_records).to_csv(index=False))
    except Exception as exc:
        log.info('写日志失败: %s' % exc)


def after_close(context):
    g.daily_records.append({
        'date': str(context.current_dt.date()),
        'total_value': context.portfolio.total_value,
        'cash': context.portfolio.available_cash,
        'positions': len([
            1 for p in context.portfolio.positions.values() if p.total_amount > 0
        ]),
        'lcs_pool': len(g.lcs_pool),
        'lcs_pool_date': getattr(g, 'lcs_pool_date', ''),
        'sh_above_ma10': getattr(g, 'sh_above_ma10', False),
    })
    _flush_logs(context)


# ==================== 聚宽生命周期 ====================
def initialize(context):
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_benchmark(MARKET_INDEX)
    set_slippage(FixedSlippage(0.002))
    set_order_cost(OrderCost(
        open_tax=0,
        close_tax=0.001,
        open_commission=0.0003,
        close_commission=0.0003,
        close_today_commission=0,
        min_commission=5,
    ), type='stock')

    g.lcs_pool = []
    g.lcs_meta = {}
    g.lcs_pool_date = ''
    g.scanned_today = set()
    g.entry_price = {}
    g.position_high = {}
    g.ever_profit = {}
    g.early_lock = {}
    g.entry_date = {}
    g.trade_records = []
    g.signal_records = []
    g.daily_records = []
    g.atr_cache = {}
    g.sh_above_ma10 = False

    run_daily(before_open_daily, time='before_open')
    run_daily(check_time_exit, time='15:00')
    run_daily(scan_and_buy, time='15:00')
    run_daily(after_close, time='after_close')

    log.info(
        '初始化：中继研究版 只买[%s]；须重心；最多%d仓'
        % (SOFT_BUY_ITEMS or '按软分补仓', MAX_POSITIONS)
    )


def after_code_changed(context):
    """聚宽热更新时补齐新字段。"""
    for name, default in (
        ('lcs_pool', []), ('lcs_meta', {}), ('lcs_pool_date', ''),
        ('scanned_today', set()),
        ('entry_price', {}), ('position_high', {}), ('ever_profit', {}),
        ('early_lock', {}), ('entry_date', {}),
        ('trade_records', []), ('signal_records', []), ('daily_records', []),
        ('atr_cache', {}), ('sh_above_ma10', False),
    ):
        if not hasattr(g, name):
            setattr(g, name, default)


def handle_data(context, data):
    """分钟回测：每根K跟踪持仓止损；日频则每天只走一次。"""
    t = context.current_dt.time()
    if t < dt.time(9, 30) or t > dt.time(14, 57):
        return
    if dt.time(11, 30) < t < dt.time(13, 0):
        return
    check_exit(context, data)
