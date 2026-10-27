# Clone from JoinQuant
# postId: 71d4258b6b719b5739114d29977f3b6d
# backtestId: 9fee3c05f273431cc25cdcad8c3449a9
# title: 颈线突破的波段策略

# -*- coding: utf-8 -*-
"""
蒋文辉三度操盘策略 v14 · ABCD + 涨停 + BC间隔>20天 + 三度评分(修改版)
====================================================================
【最新修改】
  1. 颈线 = B点收盘价 × 0.98
  2. 镜像止损：-5%减1/3，-8%全清
  3. 入池条件：C点之后（含今日）恰好1次涨停（≤1次）
  4. 买入条件：当日涨幅 > 0
  5. 【修改】每天只开仓1只，最大持仓量不限制
  6. 【新增】最小开仓份额为总资产的20%，不足不开仓
  7. 卖出策略：镜像止损、盈利>100%且未涨停全清、超期、追踪止盈、C区清仓
  8. 买入日志输出ABCD四个时间点
  9. AB之间连板必须小于3板（即最多2板）
 10. BC回撤不能超过AC涨幅的61.8%（黄金分割比例）
 11. 最大持股天数改为21天
 12. 交易时间调整：14:45 卖出，14:50 买入
 13. 买入点 MA10 > MA30 且两线均向上
 14. 买入前检索1年内买入价上方是否有向下缺口
 15. 大盘择时：上证指数 > MA20 才允许开仓
====================================================================
"""

# ============================================================
# 调试开关（可选）
# ============================================================
DEBUG_STOCK = None   # 例如 '002716.XSHE'

# ============================================================
# CONFIG
# ============================================================
CONFIG = {
    'LIQUIDITY_FLOOR': 0,
    'NECKLINE_LOOKBACK': 90,
    'NECKLINE_USE_FIELD': 'close',

    'MAX_HOLDINGS': 9999,               # 【修改】最大持仓量不限制（用大数表示）
    'MAX_DAILY_BUY': 1,                 # 【修改】每天只开仓1只
    'MIN_OPEN_RATIO': 0.20,             # 【新增】最小开仓份额：总资产的20%

    'STOP_LOSS_HARD': -0.08,
    'MIRROR_STOP_LEVELS': [(-0.05, 0.333, '减1/3'), (-0.08, 1.00, '全清')],
    'NECKLINE_DELAY_PROFIT': 0.03,
    'NECKLINE_DELAY_DAYS': 3,
    'MAX_HOLD_DAYS': 21,

    'BASE_MIN_DAYS': 20,
    'BASE_RECENT_DAYS': 10,
    'BASE_MAX_AMP': 0.40,
    'BASE_MIN_AMP': 0.02,
    'BASE_MIN_VOLUME': 5e5,
    'SANYANG_VOL_RATIO': 1.2,
    'SANYANG_YANG_RATIO': 0.50,
    'SANYANG_GINI_THRESHOLD': 0.4,
    'GUHWEI_SPREAD_MAX': 0.06,
    'BREAKOUT_VOL_RATIO': 1.0,
    'BREAKOUT_CLOSE_POS': 0.60,
    'BREAKOUT_OPEN_POS': 0.25,
    'BREAKOUT_BODY_MIN': 0.02,

    'VOLUME_RATIO_THRESHOLD': 1.5,
    'AB_MAX_CONSECUTIVE_LIMIT': 3,
    'BC_DRAWDOWN_MAX_RATIO_OF_AC': 0.618,

    'PROFIT_CLEAR_THRESHOLD': 1.00,

    'C_LIMIT_MAX_COUNT': 1,
    'MA_FILTER_ENABLE': True,

    # 向下缺口过滤参数
    'GAP_FILTER_ENABLE': True,
    'GAP_LOOKBACK_DAYS': 250,
    'GAP_PROXIMITY_THRESHOLD': 0.98,

    # 大盘择时参数
    'MARKET_TIMING_ENABLE': True,
    'MARKET_INDEX': '000001.XSHG',
    'MARKET_MA_PERIOD': 20,
}

# ============================================================
# 导入依赖
# ============================================================
import numpy as np
from datetime import timedelta, datetime

# ============================================================
# 基础池过滤
# ============================================================
def is_valid_stock(code):
    if not isinstance(code, str):
        return False
    s = str(code)
    if s.startswith('300') or s.startswith('301') or s.startswith('688'):
        return False
    if s.startswith('8') or s.startswith('9') or s.startswith('4'):
        return False
    if 'ST' in s.upper():
        return False
    return True

def filter_by_liquidity(stock_list, min_liquidity_yi):
    if min_liquidity_yi <= 0:
        return list(stock_list)
    try:
        import jqdata
        finance_mod = jqdata.finance
        valuation = finance_mod.valuation
        query = jqdata.query
        q = query(valuation.code, valuation.circulating_market_cap)
        fund_df = get_fundamentals(q)
        if fund_df is None or len(fund_df) == 0:
            log.warn('get_fundamentals 返回空，跳过市值过滤')
            return list(stock_list)
        threshold = min_liquidity_yi * 1e8
        cap_codes = set(fund_df.loc[fund_df['circulating_market_cap'] >= threshold, 'code'].tolist())
        filtered = [s for s in stock_list if s in cap_codes]
        log.info(f'【流通市值过滤】阈值={min_liquidity_yi}亿元 原{len(stock_list)} → {len(filtered)}')
        return filtered
    except Exception as e:
        log.error(f'filter_by_liquidity 失败: {e}，跳过过滤')
        return list(stock_list)

# ============================================================
# 大盘择时函数
# ============================================================
def check_market_timing(context):
    """
    大盘择时：上证指数 > MA20 才允许开仓
    返回：(是否允许开仓, 大盘当前价, 大盘MA20)
    """
    if not CONFIG.get('MARKET_TIMING_ENABLE', True):
        return True, None, None

    try:
        index_code = CONFIG['MARKET_INDEX']
        ma_period = CONFIG['MARKET_MA_PERIOD']

        hist = get_price(index_code, count=ma_period, end_date=context.current_dt,
                         frequency='daily', fields=['close'], skip_paused=True)
        if hist is None or len(hist) < ma_period:
            log.warn(f'【大盘择时】{index_code} 历史数据不足({0 if hist is None else len(hist)}<{ma_period})，默认允许开仓')
            return True, None, None

        index_ma = float(hist['close'].mean())
        current_data = get_current_data()
        index_price = getattr(current_data[index_code], 'last_price', None)
        if index_price is None or index_price <= 0:
            index_price = float(hist['close'].iloc[-1])

        allow = index_price > index_ma
        return allow, index_price, index_ma
    except Exception as e:
        log.warn(f'【大盘择时】计算异常: {e}，默认允许开仓')
        return True, None, None

# ============================================================
# 向下缺口检查函数
# ============================================================
def has_gap_pressure_above(stock, last_price, context):
    """检查个股在过去1年内、买入价上方是否有向下缺口。"""
    if not CONFIG.get('GAP_FILTER_ENABLE', True):
        return False, []

    try:
        lookback = CONFIG.get('GAP_LOOKBACK_DAYS', 250)
        df = get_price(stock, count=lookback + 1, end_date=context.current_dt,
                       frequency='daily', fields=['high', 'low'], skip_paused=True)
        if df is None or len(df) < 2:
            return False, []

        highs = df['high'].values
        lows = df['low'].values
        dates = df.index

        gap_hits = []
        for i in range(1, len(highs)):
            if lows[i-1] > highs[i]:
                gap_lower = float(highs[i])
                gap_upper = float(lows[i-1])
                if gap_lower > last_price:
                    if last_price > gap_lower * CONFIG['GAP_PROXIMITY_THRESHOLD']:
                        gap_date = dates[i].strftime('%Y-%m-%d')
                        gap_hits.append({
                            'date': gap_date,
                            'gap_lower': gap_lower,
                            'gap_upper': gap_upper,
                            'proximity': last_price / gap_lower,
                        })

        return len(gap_hits) > 0, gap_hits
    except Exception as e:
        log.warn(f'【缺口检查】{stock} 异常: {e}')
        return False, []

# ============================================================
# ABCD 形态识别
# ============================================================
def find_neckline_ABCD(stock, today, lookback=60, field='close'):
    df = get_price(stock, end_date=today, count=lookback + 1,
                   fields=['open', 'close', 'high', 'low', 'volume'],
                   fq='pre', skip_paused=True)
    if df is None or len(df) < lookback + 1:
        return {'valid': False, 'reason': f'数据不足(需{lookback+1}天)', 'neckline_price': None}
    if field not in df.columns:
        field = 'close'
    closes = df[field].values
    win_closes = closes[:-1]
    d_close = float(closes[-1])
    if len(win_closes) < lookback:
        return {'valid': False, 'reason': '窗口不足', 'neckline_price': None}

    b_idx = int(np.argmax(win_closes))
    b_close = float(win_closes[b_idx])
    if b_idx == 0:
        return {'valid': False, 'reason': 'A必须在B之前', 'neckline_price': None}
    a_idx = int(np.argmin(win_closes[:b_idx]))
    a_close = float(win_closes[a_idx])

    if b_idx >= len(win_closes) - 1:
        return {'valid': False, 'reason': 'B后无C区间', 'neckline_price': None}
    c_closes = win_closes[b_idx + 1:]
    if len(c_closes) == 0:
        return {'valid': False, 'reason': 'B-D之间无数据', 'neckline_price': None}
    c_local = int(np.argmin(c_closes))
    c_idx = b_idx + 1 + c_local
    c_close = float(win_closes[c_idx])

    if c_idx - b_idx <= 20:
        return {'valid': False, 'reason': f'B-C间隔{c_idx-b_idx}天，不大于20天，剔除', 'neckline_price': None}

    if not (c_close > a_close):
        return {'valid': False, 'reason': f'C({c_close:.2f}) ≤ A({a_close:.2f})', 'neckline_price': None}

    ac_gain = (b_close - a_close) / a_close if a_close > 0 else 0
    bc_drawdown = (b_close - c_close) / b_close if b_close > 0 else 0
    max_allowed_drawdown = CONFIG['BC_DRAWDOWN_MAX_RATIO_OF_AC'] * ac_gain
    if bc_drawdown > max_allowed_drawdown:
        return {'valid': False,
                'reason': f'BC回撤{bc_drawdown:.2%}>61.8%×AC涨幅({ac_gain:.2%})={max_allowed_drawdown:.2%}，剔除',
                'neckline_price': None}

    ab_segment = win_closes[a_idx:b_idx+1]
    max_consec = 0
    cur_consec = 0
    for i in range(1, len(ab_segment)):
        prev = ab_segment[i-1]
        curr = ab_segment[i]
        if prev > 0 and (curr - prev) / prev >= 0.095:
            cur_consec += 1
            max_consec = max(max_consec, cur_consec)
        else:
            cur_consec = 0
    if max_consec >= CONFIG['AB_MAX_CONSECUTIVE_LIMIT']:
        return {'valid': False, 'reason': f'AB连板{max_consec}板≥3板，剔除', 'neckline_price': None}

    dates = df.index
    a_date = dates[a_idx].strftime('%Y-%m-%d')
    b_date = dates[b_idx].strftime('%Y-%m-%d')
    c_date = dates[c_idx].strftime('%Y-%m-%d')
    d_date = dates[-1].strftime('%Y-%m-%d')
    volumes = df['volume'].values
    b_volume = float(volumes[b_idx]) if b_idx < len(volumes) else 0

    neckline_price = b_close * 0.98

    return {
        'valid': True,
        'neckline_price': neckline_price,
        'abcd_info': {
            'a_idx': a_idx,
            'b_idx': b_idx,
            'c_idx': c_idx,
            'a_close': a_close,
            'b_close': b_close,
            'c_close': c_close,
            'd_close': d_close,
            'a_date': a_date,
            'b_date': b_date,
            'c_date': c_date,
            'd_date': d_date,
            'b_volume': b_volume,
            'bc_drawdown': bc_drawdown,
            'ac_gain': ac_gain,
            'max_consec_limit': max_consec,
        },
        'reason': 'OK',
    }

# ============================================================
# 基底分析
# ============================================================
def analyze_base(stock, today, base_min_days, base_recent_days, base_max_amp,
                 base_min_amp, base_min_volume, abcd_info=None, lookback=None,
                 interval_type='AC', check_amp=True):
    fetch_count = max(base_min_days + 60, (lookback or 60) + 30)
    df = get_price(stock, end_date=today, count=fetch_count,
                   fields=['open', 'close', 'high', 'low', 'volume'],
                   fq='pre', skip_paused=True)
    if df is None or len(df) < 5:
        return {'valid': False, 'reason': f'数据不足(仅{0 if df is None else len(df)}天)'}

    closes = df['close'].values
    opens = df['open'].values
    highs = df['high'].values
    lows = df['low'].values
    volumes = df['volume'].values
    n = len(closes)

    if abcd_info is not None and lookback is not None:
        win_start = n - lookback - 1
        a_abs = win_start + abcd_info['a_idx']
        b_abs = win_start + abcd_info['b_idx']
        c_abs = win_start + abcd_info['c_idx']
        if a_abs < 0 or c_abs >= n or b_abs < 0 or b_abs >= n:
            return {'valid': False, 'reason': f'索引越界(a={a_abs}, b={b_abs}, c={c_abs}, n={n})'}

        if interval_type == 'AC':
            base_start_idx = a_abs
            base_end_idx = c_abs + 1
        else:
            base_start_idx = b_abs
            base_end_idx = c_abs + 1

        if base_end_idx - base_start_idx < base_min_days:
            return {'valid': False, 'reason': f'{interval_type}区间长度{base_end_idx-base_start_idx}<{base_min_days}'}

        if check_amp:
            if b_abs > c_abs:
                return {'valid': False, 'reason': 'B索引大于C索引'}
            bc_high = float(np.max(highs[b_abs:c_abs+1]))
            bc_low = float(np.min(lows[b_abs:c_abs+1]))
            if bc_low <= 0:
                return {'valid': False, 'reason': f'BC最低价<=0 ({bc_low})'}
            bc_mid = (bc_high + bc_low) / 2
            amp = (bc_high - bc_low) / bc_mid
            if amp > base_max_amp or amp < base_min_amp:
                return {'valid': False, 'reason': f'BC振幅{amp:.2%}超出范围[{base_min_amp:.2%},{base_max_amp:.2%}]', 'amp': amp}
    else:
        base_start_idx = max(0, n - base_min_days - 1)
        base_end_idx = n - 1
        if base_end_idx - base_start_idx < base_min_days // 2:
            return {'valid': False, 'reason': f'基底长度{base_end_idx-base_start_idx}<{base_min_days//2}'}
        if check_amp:
            pass

    base_close = closes[base_start_idx:base_end_idx]
    base_open = opens[base_start_idx:base_end_idx]
    base_high = highs[base_start_idx:base_end_idx]
    base_low = lows[base_start_idx:base_end_idx]
    base_vol = volumes[base_start_idx:base_end_idx]

    mean_vol = float(np.mean(base_vol))
    if mean_vol < base_min_volume:
        return {'valid': False, 'reason': f'日均量{mean_vol:.0f}<{base_min_volume:.0f}', 'mean_vol': mean_vol}

    is_yang = base_close > base_open
    yang_volumes = base_vol[is_yang]
    yin_volumes = base_vol[~is_yang]
    yang_count = int(np.sum(is_yang))
    yin_count = int(len(is_yang) - yang_count)
    yang_cum = float(np.sum(yang_volumes))
    yin_cum = float(np.sum(yin_volumes))

    big_yang_count = 0
    for i in range(len(base_close)):
        if base_low[i] > 0 and (base_close[i] - base_open[i]) / base_open[i] >= 0.05 and is_yang[i]:
            big_yang_count += 1

    yang_ratio = yang_cum / yin_cum if yin_cum > 0 else 0
    avg_yang_vol = float(np.mean(yang_volumes)) if len(yang_volumes) > 0 else 0
    if avg_yang_vol > 0:
        big_yang_vol = yang_volumes[yang_volumes >= avg_yang_vol * 1.5] if len(yang_volumes) > 0 else []
        yang_concentration = float(np.sum(big_yang_vol) / yang_cum) if yang_cum > 0 else 0
    else:
        yang_concentration = 0

    interval_days = base_end_idx - base_start_idx

    return {
        'valid': True,
        'high_max': float(np.max(base_high)),
        'low_min': float(np.min(base_low)),
        'amp': amp if 'amp' in locals() else 0,
        'mean_vol': mean_vol,
        'max_vol': float(np.max(base_vol)),
        'yang_cum': yang_cum,
        'yin_cum': yin_cum,
        'yang_count': yang_count,
        'yin_count': yin_count,
        'yang_ratio': yang_ratio,
        'yang_concentration': yang_concentration,
        'big_yang_count': big_yang_count,
        'interval_days': interval_days,
        'df_subset': df.iloc[base_start_idx:base_end_idx].copy(),
        'base_start_idx': base_start_idx,
        'base_end_idx': base_end_idx,
    }

# ============================================================
# A/B区识别
# ============================================================
def detect_ab_zone(df_subset, today, neckline_price):
    default = {
        'is_ab': False,
        'ma5_today': 0.0,
        'ma10_today': 0.0,
        'ma20_today': 0.0,
        'ma_spread': 0.0,
        'turn_up': False,
        'dist_to_neck': 0.0,
    }
    if df_subset is None or len(df_subset) < 20:
        return default

    closes = df_subset['close'].values
    ma5_series = []
    ma10_series = []
    ma20_series = []
    for i in range(len(closes)):
        if i >= 4:
            ma5_series.append(np.mean(closes[i-4:i+1]))
        else:
            ma5_series.append(np.nan)
        if i >= 9:
            ma10_series.append(np.mean(closes[i-9:i+1]))
        else:
            ma10_series.append(np.nan)
        if i >= 19:
            ma20_series.append(np.mean(closes[i-19:i+1]))
        else:
            ma20_series.append(np.nan)
    ma5_series = np.array(ma5_series)
    ma10_series = np.array(ma10_series)
    ma20_series = np.array(ma20_series)

    valid_mask = ~np.isnan(ma5_series) & ~np.isnan(ma10_series) & ~np.isnan(ma20_series)
    if np.sum(valid_mask) < 5:
        return default

    valid_indices = np.where(valid_mask)[0][-5:]
    ma5_v = ma5_series[valid_indices]
    ma10_v = ma10_series[valid_indices]
    ma20_v = ma20_series[valid_indices]

    all_ma = np.concatenate([ma5_v, ma10_v, ma20_v])
    ma_min, ma_max = np.min(all_ma), np.max(all_ma)
    ma_mid = np.median(all_ma)
    if ma_mid <= 0:
        return default
    ma_spread = (ma_max - ma_min) / ma_mid

    if len(ma5_v) >= 3:
        ma5_slope = (ma5_v[-1] - ma5_v[-3]) / ma5_v[-3] if ma5_v[-3] > 0 else -1
        turn_up = ma5_slope > 0
    else:
        turn_up = False

    close_today = float(closes[-1])
    if neckline_price > 0:
        dist_to_neck = (close_today - neckline_price) / neckline_price
    else:
        dist_to_neck = 0

    is_ab = (ma_spread <= CONFIG['GUHWEI_SPREAD_MAX']
             and turn_up
             and -0.05 <= dist_to_neck <= 0.05)

    return {
        'is_ab': is_ab,
        'ma5_today': float(ma5_series[-1]) if not np.isnan(ma5_series[-1]) else 0.0,
        'ma10_today': float(ma10_series[-1]) if not np.isnan(ma10_series[-1]) else 0.0,
        'ma20_today': float(ma20_series[-1]) if not np.isnan(ma20_series[-1]) else 0.0,
        'ma_spread': float(ma_spread),
        'turn_up': bool(turn_up),
        'dist_to_neck': float(dist_to_neck),
    }

# ============================================================
# 三度评分函数
# ============================================================
def calc_thickness(base_info, params):
    if not base_info.get('valid'):
        return 0
    score = 0
    if base_info['yang_ratio'] >= params['SANYANG_VOL_RATIO']:
        score += 1
    if base_info['yang_count'] / max(1, base_info['yang_count'] + base_info['yin_count']) >= params['SANYANG_YANG_RATIO']:
        score += 1
    if base_info['yang_concentration'] >= params['SANYANG_GINI_THRESHOLD']:
        score += 1
    if base_info.get('interval_days', 0) > 30:
        score += 1
    return score

def calc_force(ab_zone_info, breakout_info, pullback_info, params):
    score = 0
    if ab_zone_info.get('is_ab'):
        score += 1
    if breakout_info.get('is_breakout'):
        if breakout_info.get('vol_ratio', 0) >= params['BREAKOUT_VOL_RATIO']:
            score += 1
        if breakout_info.get('close_pos', 0) >= params['BREAKOUT_CLOSE_POS']:
            score += 1
    if pullback_info.get('passed'):
        score += 1
    return score

def calc_speed(ma5_today, ma10_today, ma20_today, params):
    score = 0
    if ma5_today > ma10_today * 1.001 and ma10_today > 0:
        score += 1
    if ma10_today > ma20_today * 1.001 and ma20_today > 0:
        score += 1
    return score

# ============================================================
# 收盘后构建候选池
# ============================================================
def build_candidate_pool(context):
    today = context.current_dt
    candidates = {}
    stats = {
        'scanned': 0,
        'no_neckline': 0,
        'no_ab_zone': 0,
        'no_c_limit': 0,
        'too_many_c_limit': 0,
        'no_base': 0,
        'added': 0
    }

    held_set = set()
    for s, p in context.portfolio.positions.items():
        if p.total_amount > 0:
            held_set.add(s)

    for stock in g.base_pool:
        if stock in held_set:
            continue

        stats['scanned'] += 1

        abcd = find_neckline_ABCD(
            stock, today,
            lookback=CONFIG['NECKLINE_LOOKBACK'],
            field=CONFIG['NECKLINE_USE_FIELD'],
        )
        if not abcd['valid']:
            stats['no_neckline'] += 1
            continue

        neckline_price = abcd['neckline_price']
        abcd_info = abcd['abcd_info']
        a_idx = abcd_info['a_idx']
        b_idx = abcd_info['b_idx']
        c_idx = abcd_info['c_idx']

        df = get_price(stock, end_date=today, count=CONFIG['NECKLINE_LOOKBACK'] + 1,
                       fields=['close'], fq='pre', skip_paused=True)
        if df is None or len(df) < CONFIG['NECKLINE_LOOKBACK'] + 1:
            continue
        ab_closes = df['close'].iloc[a_idx:b_idx+1].values
        if len(ab_closes) < 2:
            continue

        has_limit = False
        for i in range(1, len(ab_closes)):
            prev = ab_closes[i-1]
            curr = ab_closes[i]
            if prev > 0 and (curr - prev) / prev >= 0.095:
                has_limit = True
                break
        if not has_limit:
            stats['no_ab_zone'] += 1
            continue

        full_df = get_price(stock, end_date=today, count=CONFIG['NECKLINE_LOOKBACK'] + 1,
                            fields=['close'], fq='pre', skip_paused=True)
        if full_df is None or len(full_df) < CONFIG['NECKLINE_LOOKBACK'] + 1:
            continue
        closes = full_df['close'].values

        c_limit_count = 0
        for i in range(c_idx + 1, len(closes)):
            if i == 0:
                continue
            prev = closes[i-1]
            curr = closes[i]
            if prev > 0 and (curr - prev) / prev >= 0.095:
                c_limit_count += 1

        if c_limit_count == 0:
            stats['no_c_limit'] += 1
            continue
        if c_limit_count > CONFIG['C_LIMIT_MAX_COUNT']:
            stats['too_many_c_limit'] += 1
            continue

        base_info_bc = analyze_base(
            stock, today,
            base_min_days=CONFIG['BASE_MIN_DAYS'],
            base_recent_days=CONFIG['BASE_RECENT_DAYS'],
            base_max_amp=CONFIG['BASE_MAX_AMP'],
            base_min_amp=CONFIG['BASE_MIN_AMP'],
            base_min_volume=CONFIG['BASE_MIN_VOLUME'],
            abcd_info=abcd_info,
            lookback=CONFIG['NECKLINE_LOOKBACK'],
            interval_type='BC',
            check_amp=True
        )
        if not base_info_bc['valid']:
            stats['no_base'] += 1
            continue

        base_info_ac = analyze_base(
            stock, today,
            base_min_days=CONFIG['BASE_MIN_DAYS'],
            base_recent_days=CONFIG['BASE_RECENT_DAYS'],
            base_max_amp=CONFIG['BASE_MAX_AMP'],
            base_min_amp=CONFIG['BASE_MIN_AMP'],
            base_min_volume=CONFIG['BASE_MIN_VOLUME'],
            abcd_info=abcd_info,
            lookback=CONFIG['NECKLINE_LOOKBACK'],
            interval_type='AC',
            check_amp=False
        )
        if not base_info_ac['valid']:
            stats['no_base'] += 1
            continue

        ab_zone = detect_ab_zone(base_info_ac['df_subset'], today, neckline_price)

        today_df = get_price(stock, end_date=today, count=2,
                             fields=['open', 'close', 'high', 'low', 'volume'],
                             fq='pre', skip_paused=True)
        if today_df is None or len(today_df) < 1:
            continue
        op, cl, hi, lo, vo = today_df.iloc[-1][['open','close','high','low','volume']]
        if op <= 0 or lo <= 0:
            continue
        neckline_vol = abcd_info['b_volume']
        if neckline_vol <= 0:
            continue

        body_pct = (cl - op) / op
        vol_ratio = vo / neckline_vol
        close_pos = (cl - lo) / (hi - lo) if hi > lo else 0
        open_pos = (op - lo) / (hi - lo) if hi > lo else 0

        is_breakout = (body_pct >= CONFIG['BREAKOUT_BODY_MIN']
                       and vol_ratio >= CONFIG['BREAKOUT_VOL_RATIO']
                       and close_pos >= CONFIG['BREAKOUT_CLOSE_POS']
                       and open_pos >= CONFIG['BREAKOUT_OPEN_POS'])

        df_pre = base_info_ac['df_subset']
        if len(df_pre) >= 7:
            vol_mean_pre = float(np.mean(df_pre['volume'].values[-7:-1]))
            recent_vols = df_pre['volume'].values[-5:]
            wash_days = int(np.sum(recent_vols < vol_mean_pre * 0.85))
        else:
            wash_days = 0
        pullback_pass = (wash_days >= 1)

        t_score = calc_thickness(base_info_bc, CONFIG)
        f_score = calc_force(ab_zone,
                             {'is_breakout': is_breakout, 'vol_ratio': vol_ratio, 'close_pos': close_pos},
                             {'passed': pullback_pass}, CONFIG)
        s_score = calc_speed(ab_zone['ma5_today'], ab_zone['ma10_today'], ab_zone['ma20_today'], CONFIG)
        total_score = t_score + f_score + s_score

        candidates[stock] = {
            'neckline': neckline_price,
            'abcd_info': abcd_info,
            'breakout_low': neckline_price,
            'score_info': {
                't_score': t_score,
                'f_score': f_score,
                's_score': s_score,
                'total_score': total_score,
            },
            'c_limit_count': c_limit_count,
        }
        stats['added'] += 1

    g.candidate_pool = candidates
    log.info(f'【候选池构建】扫描{stats["scanned"]}只，颈线筛{stats["no_neckline"]}，无涨停筛{stats["no_ab_zone"]}，C后无涨停筛{stats["no_c_limit"]}，C后涨停过多筛{stats["too_many_c_limit"]}，基底筛{stats["no_base"]}，新增候选{stats["added"]}只')
    if DEBUG_STOCK is not None and DEBUG_STOCK in candidates:
        log.info(f'【调试】目标股票 {DEBUG_STOCK} 已加入候选池，颈线={candidates[DEBUG_STOCK]["neckline"]:.2f}，总分={candidates[DEBUG_STOCK]["score_info"]["total_score"]}')

# ============================================================
# 14:45 卖出
# ============================================================
def trade_at_1445(context):
    positions = context.portfolio.positions
    hold_stocks = [s for s, p in positions.items() if p.total_amount > 0]

    for stock in hold_stocks:
        df_today = get_price(stock, end_date=context.current_dt, count=1,
                             fields=['close'], fq='pre', skip_paused=True)
        if df_today is None or len(df_today) == 0:
            continue
        current_price = df_today['close'].iloc[-1]
        update_position_state(context, stock, current_price)

    for stock in hold_stocks:
        df_today = get_price(stock, end_date=context.current_dt, count=1,
                             fields=['close', 'volume'],
                             fq='pre', skip_paused=True)
        if df_today is None or len(df_today) == 0:
            continue
        current_price = df_today['close'].iloc[-1]
        pos = positions[stock]
        hold_price = pos.avg_cost
        ret = (current_price - hold_price) / hold_price
        state = g.position_states.get(stock)

        action = None
        reason = None

        # P1 镜像止损
        if state is not None:
            ms_triggered, ms_ratio, ms_action_name, ms_idx = check_mirror_stop(state, ret)
            if ms_triggered:
                if ms_ratio >= 1.0:
                    action = 'sell_all'
                    reason = f'镜像止损:{ms_action_name} 浮亏{ret*100:.2f}%'
                else:
                    action = 'reduce_1_3'
                    reason = f'镜像止损:{ms_action_name} 浮亏{ret*100:.2f}%'
                if ms_idx not in state['mirror_stop_levels_reached']:
                    state['mirror_stop_levels_reached'].append(ms_idx)

        # P2 盈利>100% 且当日未涨停 → 全清
        if action is None and ret > CONFIG['PROFIT_CLEAR_THRESHOLD']:
            current_data = get_current_data()[stock]
            high_limit = getattr(current_data, 'high_limit', None)
            is_limit_up = False
            if high_limit is not None and high_limit > 0 and current_price >= high_limit:
                is_limit_up = True
            if not is_limit_up:
                action = 'sell_all'
                reason = f'盈利{ret*100:.2f}%>100%且未涨停，全清'
            else:
                if DEBUG_STOCK == stock:
                    log.info(f'【持有】{stock} 盈利{ret*100:.2f}%>100%，但当日涨停，继续持有')

        # P5 超期
        if action is None and state and state['hold_days'] >= CONFIG['MAX_HOLD_DAYS']:
            zone = get_trade_zone_v12(context, stock, current_price)
            if zone == 'A':
                if DEBUG_STOCK == stock:
                    log.info(f'【超期】{stock} 持仓{state["hold_days"]}日，但处于A区，不减仓')
                pass
            else:
                action = 'reduce_half'
                reason = f'持仓{state["hold_days"]}日超期（不在A区）'

        # P6 动态追踪止盈
        if action is None and state is not None and state.get('max_floating', 0) > 0:
            max_f = state['max_floating']
            max_price = state.get('max_price', current_price)
            if max_price > 0:
                price_drawdown = (max_price - current_price) / max_price
            else:
                price_drawdown = 0

            if price_drawdown >= 0.10 and max_f >= 0.15:
                action = 'sell_all'
                reason = f'追踪止盈: 最高价{max_price:.2f}→回撤{price_drawdown*100:.1f}% (≥10%)，全清'
            elif price_drawdown >= 0.08 and max_f >= 0.15 and state.get('trailing_triggered', 0) >= 3:
                action = 'sell_all'
                reason = f'追踪止盈: 最高价{max_price:.2f}→回撤{price_drawdown*100:.1f}% (≥8%)，全清'
            elif price_drawdown >= 0.06 and max_f >= 0.10 and state.get('trailing_triggered', 0) >= 2:
                action = 'reduce_1_3'
                reason = f'追踪止盈: 最高价{max_price:.2f}→回撤{price_drawdown*100:.1f}% (≥6%)，再减1/3'
                state['trailing_triggered'] = state.get('trailing_triggered', 0) + 1
            elif price_drawdown >= 0.04 and max_f >= 0.06 and state.get('trailing_triggered', 0) >= 1:
                action = 'reduce_1_3'
                reason = f'追踪止盈: 最高价{max_price:.2f}→回撤{price_drawdown*100:.1f}% (≥4%)，再减1/3'
                state['trailing_triggered'] = state.get('trailing_triggered', 0) + 1
            elif price_drawdown >= 0.03 and max_f >= 0.03 and state.get('trailing_triggered', 0) == 0:
                action = 'reduce_1_3'
                reason = f'追踪止盈: 最高价{max_price:.2f}→回撤{price_drawdown*100:.1f}% (≥3%)，减1/3'
                state['trailing_triggered'] = state.get('trailing_triggered', 0) + 1
            elif price_drawdown >= 0.10:
                action = 'sell_all'
                reason = f'追踪止盈: 最高价{max_price:.2f}→回撤{price_drawdown*100:.1f}% (≥10%)，兜底全清'

        # P7 C区清仓
        if action is None and get_trade_zone_v12(context, stock, current_price) == 'C':
            action = 'sell_all'
            reason = 'C区'

        if action == 'sell_all':
            order_target(stock, 0)
            log.info(f'【卖出】{stock}:{reason}')
        elif action == 'reduce_half':
            if pos.total_amount >= 200:
                order_target(stock, pos.total_amount // 2)
                log.info(f'【减半】{stock}:{reason}')
            else:
                order_target(stock, 0)
                log.info(f'【清仓(仓位小)】{stock}:{reason}')
        elif action == 'reduce_1_3':
            if pos.total_amount >= 300:
                reduce_to = pos.total_amount * 2 // 3
                reduce_to = (reduce_to // 100) * 100
                if reduce_to > 0 and reduce_to < pos.total_amount:
                    order_target(stock, reduce_to)
                    log.info(f'【减1/3】{stock}:{reason}')
                else:
                    if pos.total_amount >= 200:
                        order_target(stock, pos.total_amount // 2)
                        log.info(f'【减半】{stock}:{reason}(1/3减不动)')
                    else:
                        order_target(stock, 0)
                        log.info(f'【清仓(仓位小)】{stock}:{reason}')

    held_now = set([s for s, p in positions.items() if p.total_amount > 0])
    for stock in list(g.position_states.keys()):
        if stock not in held_now:
            g.position_states.pop(stock, None)

# ============================================================
# 14:50 买入（每天最多开1只，单只开仓 ≥ 总资产的20%）
# ============================================================
def check_and_buy_at_1450(context):
    if DEBUG_STOCK is not None:
        log.info(f'【调试】候选池股票列表: {list(g.candidate_pool.keys())}')
        if DEBUG_STOCK in g.candidate_pool:
            info = g.candidate_pool[DEBUG_STOCK]
            log.info(f'【调试】目标股票 {DEBUG_STOCK} 在候选池中，颈线={info["neckline"]:.2f}，总分={info["score_info"]["total_score"]}')
            current_data = get_current_data()[DEBUG_STOCK]
            if current_data:
                last_price = getattr(current_data, 'last_price', None)
                high_limit = getattr(current_data, 'high_limit', None)
                pre_close_df = get_price(DEBUG_STOCK, count=2, end_date=context.current_dt, frequency='daily', fields=['close'], skip_paused=True)
                if pre_close_df is not None and len(pre_close_df) >= 2:
                    pre_close = pre_close_df['close'].iloc[-2]
                else:
                    pre_close = None
                log.info(f'【调试】{DEBUG_STOCK} 最新价={last_price}, 涨停价={high_limit}, 昨收={pre_close}')
        else:
            log.info(f'【调试】目标股票 {DEBUG_STOCK} 不在候选池中')

    today = context.current_dt.date()
    if not hasattr(g, 'last_buy_date'):
        g.last_buy_date = None
        g.bought_count_today = 0
    if g.last_buy_date != today:
        g.last_buy_date = today
        g.bought_count_today = 0

    # ===== 【修改】每天最多开仓1只 =====
    if g.bought_count_today >= CONFIG['MAX_DAILY_BUY']:
        log.info(f'【14:50】今日已开仓{CONFIG["MAX_DAILY_BUY"]}只，不再买入')
        return
    # =================================

    # 大盘择时判断
    allow_buy, index_price, index_ma = check_market_timing(context)
    if not allow_buy:
        if index_price is not None and index_ma is not None:
            log.info(f'【大盘择时】上证指数{index_price:.2f} ≤ MA{CONFIG["MARKET_MA_PERIOD"]}{index_ma:.2f}，暂停开仓')
        else:
            log.info(f'【大盘择时】大盘状态不佳，暂停开仓')
        return
    else:
        if index_price is not None and index_ma is not None:
            log.info(f'【大盘择时】上证指数{index_price:.2f} > MA{CONFIG["MARKET_MA_PERIOD"]}{index_ma:.2f}，允许开仓')

    if not hasattr(g, 'candidate_pool') or not g.candidate_pool:
        log.info('【14:50】候选池为空，跳过')
        return

    held_set = set()
    for s, p in context.portfolio.positions.items():
        if p.total_amount > 0:
            held_set.add(s)

    # ===== 【修改】最大持仓不限制，跳过持仓数量检查 =====
    # 只保留每天开仓数量限制（已在前面判断）
    # ==================================================

    available_cash = context.portfolio.available_cash
    total_value = context.portfolio.total_value
    min_open_cash = total_value * CONFIG['MIN_OPEN_RATIO']

    # ===== 【新增】最小开仓份额检查 =====
    if available_cash < min_open_cash:
        log.info(f'【最小开仓】可用资金{available_cash:.2f} < 总资产{total_value:.2f}×{CONFIG["MIN_OPEN_RATIO"]*100:.0f}% = {min_open_cash:.2f}，今日不开仓')
        return
    # ====================================

    buy_candidates = []
    for stock, info in g.candidate_pool.items():
        if stock in held_set:
            continue

        current_data = get_current_data()[stock]
        if current_data is None:
            continue
        last_price = getattr(current_data, 'last_price', None)
        if last_price is None or last_price <= 0:
            continue

        high_limit = getattr(current_data, 'high_limit', None)
        if high_limit is not None and high_limit > 0 and last_price >= high_limit:
            if DEBUG_STOCK is not None and stock == DEBUG_STOCK:
                log.info(f'【调试】{stock} 涨停价{high_limit:.2f}，现价{last_price:.2f}，剔除')
            continue

        price_vol_df = get_price(stock, count=2, end_date=context.current_dt, frequency='daily',
                                  fields=['open', 'close', 'volume'], skip_paused=True)
        if price_vol_df is None or len(price_vol_df) < 2:
            if DEBUG_STOCK is not None and stock == DEBUG_STOCK:
                log.info(f'【调试】{stock} 无法获取前一日数据，跳过')
            continue

        pre_close = price_vol_df['close'].iloc[-2]
        if pre_close <= 0:
            continue

        today_open = price_vol_df['open'].iloc[-1]
        today_vol = price_vol_df['volume'].iloc[-1]
        prev_vol = price_vol_df['volume'].iloc[-2]

        daily_gain = (last_price - pre_close) / pre_close
        if daily_gain <= 0:
            if DEBUG_STOCK is not None and stock == DEBUG_STOCK:
                log.info(f'【调试】{stock} 当日涨幅{daily_gain*100:.2f}% ≤0，不买入')
            continue

        vol_ratio_threshold = CONFIG.get('VOLUME_RATIO_THRESHOLD', 1.5)
        if prev_vol > 0 and today_vol > prev_vol * vol_ratio_threshold:
            if last_price < today_open:
                if DEBUG_STOCK is not None and stock == DEBUG_STOCK:
                    log.info(f'【调试】{stock} 放量下跌，剔除 (今日量{int(today_vol)} 前日量{int(prev_vol)}，现价{last_price:.2f} 开盘{today_open:.2f})')
                continue

        neckline = info['neckline']
        if last_price <= neckline:
            if DEBUG_STOCK is not None and stock == DEBUG_STOCK:
                log.info(f'【调试】{stock} 现价{last_price:.2f} ≤ 颈线{neckline:.2f}，不买入')
            continue

        # MA10 > MA30 且两线均向上
        if CONFIG.get('MA_FILTER_ENABLE', True):
            try:
                ma_hist = get_price(stock, count=31, end_date=context.current_dt,
                                    frequency='daily', fields=['close'], skip_paused=True)
                if ma_hist is None or len(ma_hist) < 31:
                    if DEBUG_STOCK is not None and stock == DEBUG_STOCK:
                        log.info(f'【调试】{stock} MA历史数据不足({0 if ma_hist is None else len(ma_hist)}<31)，跳过')
                    continue
                ma_closes = ma_hist['close'].values.copy()
                ma_closes[-1] = last_price

                ma10_today = float(np.mean(ma_closes[-10:]))
                ma30_today = float(np.mean(ma_closes[-30:]))
                ma10_yesterday = float(np.mean(ma_closes[-11:-1]))
                ma30_yesterday = float(np.mean(ma_closes[-31:-1]))

                ma_ok = (ma10_today > ma30_today
                         and ma10_today > ma10_yesterday
                         and ma30_today > ma30_yesterday)
                if not ma_ok:
                    if DEBUG_STOCK is not None and stock == DEBUG_STOCK:
                        log.info(f'【调试】{stock} 均线不满足: MA10今日={ma10_today:.3f}, MA30今日={ma30_today:.3f}, '
                                 f'MA10昨日={ma10_yesterday:.3f}, MA30昨日={ma30_yesterday:.3f}')
                    continue
            except Exception as e:
                if DEBUG_STOCK is not None and stock == DEBUG_STOCK:
                    log.info(f'【调试】{stock} MA计算异常: {e}，跳过')
                continue

        # 向下缺口检查
        if CONFIG.get('GAP_FILTER_ENABLE', True):
            has_gap, gap_hits = has_gap_pressure_above(stock, last_price, context)
            if has_gap:
                nearest_gap = min(gap_hits, key=lambda x: x['gap_lower'])
                if DEBUG_STOCK is not None and stock == DEBUG_STOCK:
                    log.info(f'【调试】{stock} 上方存在向下缺口压力，剔除: '
                             f'缺口日期={nearest_gap["date"]}, '
                             f'缺口下沿={nearest_gap["gap_lower"]:.2f}, '
                             f'缺口上沿={nearest_gap["gap_upper"]:.2f}, '
                             f'买入价={last_price:.2f}, '
                             f'买入价/缺口下沿={nearest_gap["proximity"]*100:.2f}%')
                continue
            else:
                if DEBUG_STOCK is not None and stock == DEBUG_STOCK:
                    log.info(f'【调试】{stock} 上方无向下缺口，通过')

        gain = (last_price - neckline) / neckline
        buy_candidates.append({
            'stock': stock,
            'price': last_price,
            'neckline': neckline,
            'gain': gain,
            'daily_gain': daily_gain,
            'abcd_info': info['abcd_info'],
            'total_score': info['score_info']['total_score'],
            't_score': info['score_info']['t_score'],
            'f_score': info['score_info']['f_score'],
            's_score': info['score_info']['s_score'],
            'c_limit_count': info.get('c_limit_count', 0),
        })

    if not buy_candidates:
        log.info('【14:50】无满足买入条件的股票')
        return

    buy_candidates.sort(key=lambda x: (-x['total_score'], x['gain']))

    if DEBUG_STOCK is not None:
        log.info('【调试】候选排名（按三度总分降序，涨幅升序）:')
        target_rank = None
        for idx, item in enumerate(buy_candidates):
            rank = idx + 1
            stock_code = item['stock']
            score = item['total_score']
            gain_pct = item['gain'] * 100
            daily = item['daily_gain'] * 100
            if stock_code == DEBUG_STOCK:
                target_rank = rank
                log.info(f'  ★ 排名{rank}: {stock_code} 总分{score} 相对颈线涨幅{gain_pct:.2f}% 当日涨幅{daily:.2f}% (目标股票)')
            else:
                log.info(f'  排名{rank}: {stock_code} 总分{score} 相对颈线涨幅{gain_pct:.2f}% 当日涨幅{daily:.2f}%')
        if target_rank is not None:
            if target_rank <= 1:
                log.info(f'【调试】目标股票 {DEBUG_STOCK} 排名第{target_rank}，将被买入（每天只买第1名）')
            else:
                log.info(f'【调试】目标股票 {DEBUG_STOCK} 排名第{target_rank}，今日只买第1名，不会买入')
        else:
            log.info(f'【调试】目标股票 {DEBUG_STOCK} 不在候选列表中')

    # ===== 【修改】只取第1名买入（每天最多1只） =====
    buy_candidates = buy_candidates[:1]
    # ===============================================

    for item in buy_candidates:
        # ===== 【修改】单只投入 = 可用资金全部（不再有单只上限） =====
        invest_cash = available_cash
        # 再次检查是否满足最小开仓份额
        if invest_cash < min_open_cash:
            log.info(f'【最小开仓】{item["stock"]} 可投入资金{invest_cash:.2f} < 总资产×{CONFIG["MIN_OPEN_RATIO"]*100:.0f}% = {min_open_cash:.2f}，不开仓')
            continue
        # ===========================================================

        amount = int(invest_cash / item['price'] / 100) * 100
        if amount <= 0:
            continue

        order(item['stock'], amount)
        available_cash -= amount * item['price']
        g.bought_count_today += 1

        g.position_states[item['stock']] = {
            'buy_price': float(item['price']),
            'max_floating': 0.0,
            'current_ret': 0.0,
            'hold_days': 0,
            'breakout_low': item['neckline'],
            'max_price': float(item['price']),
            'tp_levels_reached': [],
            'mirror_stop_levels_reached': [],
            'neckline_delay_until': None,
            'use_high_score_tp': False,
            'trailing_triggered': 0,
        }

        g.candidate_pool.pop(item['stock'], None)

        ai = item['abcd_info']
        pos_ratio = (amount * item['price']) / total_value * 100
        log.info(f'【买入-ABCD时间点】{item["stock"]} '
                 f'A={ai["a_date"]}(价{ai["a_close"]:.2f}) '
                 f'B={ai["b_date"]}(价{ai["b_close"]:.2f}) '
                 f'C={ai["c_date"]}(价{ai["c_close"]:.2f}) '
                 f'D={ai["d_date"]}(价{ai["d_close"]:.2f}) '
                 f'BC间隔={ai["c_idx"]-ai["b_idx"]}天 '
                 f'AC涨幅={ai.get("ac_gain", 0)*100:.2f}% '
                 f'BC回撤={ai.get("bc_drawdown", 0)*100:.2f}% '
                 f'AB最大连板={ai.get("max_consec_limit", 0)}板 '
                 f'C后涨停次数={item.get("c_limit_count", 0)}次')
        log.info(f'【买入】{item["stock"]} {amount}股 价{item["price"]:.2f} 仓位占比{pos_ratio:.2f}% 颈线{item["neckline"]:.2f} 当日涨幅{item["daily_gain"]*100:.2f}% 相对颈线涨幅{item["gain"]*100:.2f}% 总分{item["total_score"]} (T{item["t_score"]} F{item["f_score"]} S{item["s_score"]}) '
                 f'ABCD[A={ai["a_close"]:.2f} B={ai["b_close"]:.2f} C={ai["c_close"]:.2f} D={ai["d_close"]:.2f}]')

        if DEBUG_STOCK is not None and item['stock'] == DEBUG_STOCK:
            log.info(f'【调试】目标股票 {DEBUG_STOCK} 已成功买入')

# ============================================================
# 持仓状态管理及辅助函数
# ============================================================
def update_position_state(context, stock, current_price):
    pos = context.portfolio.positions[stock]
    if pos.total_amount <= 0:
        g.position_states.pop(stock, None)
        return
    hold_price = pos.avg_cost
    current_ret = (current_price - hold_price) / hold_price if hold_price > 0 else 0
    state = g.position_states.get(stock)
    if state is None:
        state = {
            'buy_price': float(hold_price),
            'max_floating': current_ret,
            'current_ret': current_ret,
            'hold_days': 0,
            'breakout_low': float(hold_price) * 0.98,
            'max_price': current_price,
            'tp_levels_reached': [],
            'mirror_stop_levels_reached': [],
            'neckline_delay_until': None,
            'use_high_score_tp': False,
            'trailing_triggered': 0,
        }
    else:
        state['max_floating'] = max(state['max_floating'], current_ret)
        state['current_ret'] = current_ret
        state['hold_days'] += 1
        if current_price > state.get('max_price', current_price):
            state['max_price'] = current_price
    g.position_states[stock] = state

def check_mirror_stop(state, ret):
    levels_reached = state.get('mirror_stop_levels_reached', [])
    levels = CONFIG['MIRROR_STOP_LEVELS']
    for idx, (threshold, ratio, action) in enumerate(levels):
        if ret <= threshold and idx not in levels_reached:
            return True, ratio, action, idx
    return False, 0, '', None

def get_trade_zone_v12(context, stock, current_price):
    df = get_price(stock, end_date=context.current_dt, count=60,
                   fields=['close'], fq='pre', skip_paused=True)
    if df is None or len(df) < 60:
        return 'C'
    closes = df['close'].values
    ma20 = np.mean(closes[-20:])
    ma60 = np.mean(closes)
    if current_price > ma20 * 1.05 and current_price > ma60 * 1.10:
        return 'A'
    elif current_price > ma20 * 0.95 and current_price > ma60 * 0.95:
        return 'B'
    else:
        return 'C'

def log_states(context):
    log.info(f'【状态】候选池{len(g.candidate_pool)}只，持仓{len(g.position_states)}只')

# ============================================================
# 初始化
# ============================================================
def initialize(context):
    all_stocks = list(get_all_securities(['stock']).index)
    base_pool = [s for s in all_stocks if is_valid_stock(s)]
    log.info(f'基础池(基本过滤后){len(base_pool)} 只')

    g.base_pool = filter_by_liquidity(base_pool, CONFIG['LIQUIDITY_FLOOR'])
    log.info(f'基础池(流通市值过滤后){len(g.base_pool)} 只')

    g.candidate_pool = {}
    g.position_states = {}
    g.buy_list = []
    g.last_pending_date = None
    g.last_buy_date = None
    g.bought_count_today = 0

    set_benchmark('000852.XSHG')
    set_order_cost(OrderCost(open_tax=0.0, close_tax=0.001,
                             open_commission=0.0003, close_commission=0.0003,
                             min_commission=5), type='stock')
    set_option('use_real_price', True)

    # 交易时间：14:45 先卖出，14:50 后买入
    run_daily(build_candidate_pool, time='15:05')
    run_daily(trade_at_1445, time='14:45')          # 卖出
    run_daily(check_and_buy_at_1450, time='14:50')  # 买入
    run_daily(log_states, time='15:20')