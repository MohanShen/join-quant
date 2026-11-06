# Clone from JoinQuant
# postId: 601d59bad0a5bc601152b3f963783ba0
# backtestId: e2c2e230679080ccae2c152a5a2f3b88
# title: 「周线箱体突破」低频·2020至今年化21%、最大回撤15%

# -*- coding: utf-8 -*-
from jqdata import *
from jqdata import finance
import numpy as np
import pandas as pd
import datetime


def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)

    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.001,
        open_commission=0.0003, close_commission=0.0003,
        min_commission=5
    ), type='stock')

    set_order_cost(OrderCost(
        open_tax=0, close_tax=0,
        open_commission=0.0003, close_commission=0.0003,
        min_commission=5
    ), type='fund')

    set_slippage(FixedSlippage(0.001))
    log.set_level('order', 'error')

    g.hold_num = 5
    g.max_single_position = 0.25

    g.index_pool = ['000300.XSHG', '000905.XSHG']

    g.ma_year_window = 52
    g.ma_sell_window = 10
    g.low_break_lookback = 26
    g.low_break_tolerance_start = 10
    g.low_break_tolerance_max = 2
    g.stand_above_weeks = 2

    # 箱体震荡：最短10周，最长52周
    g.box_min_weeks = 10
    g.box_max_weeks = 52
    g.box_high_ratio = 1.10
    g.box_low_ratio = 0.90
    g.box_outside_tolerance = 1

    g.breakout_confirm_weeks = 2

    # 买入限制：F-1、F、F+1 三周涨幅上限
    g.f_week_gain_max = 0.20

    g.max_weeks_after_confirm = 4

    g.cooldown_trade_days = 20

    # 周线 MA52 止损：连续2周收盘<MA52 且 至少1周最低<MA52×0.97
    g.break_ma52_weeks = 2
    g.break_ma52_low_ratio = 0.97

    # 止盈
    g.take_profit_price_ratio = 1.1
    g.take_profit_week_gain_min = 0.02

    # 极端涨幅卖出
    g.extreme_week_gain_sell = 0.30

    # 冲高回落卖出
    g.drop_from_week_high_sell = 0.15

    g.bond_etfs = ['511010.XSHG']
    g.min_bond_adjust = 5000

    g._all_sec_cache = None
    g._all_sec_cache_date = None
    g._candidate_cache_date = None
    g._candidate_cache = []
    g._trade_days_cache = {}
    g._last_trade_day_cache = {}
    g._weekly_data_cache = {}

    g.sold_dates = {}
    g.position_entry_dates = {}
    g.entry_prices = {}

    run_daily(daily_sell_check, time='14:20')
    run_daily(weekly_buy, time='14:30')
    run_daily(idle_cash_to_bond, time='14:40')
    run_daily(final_clear, time='14:50')


# ==================== 基础工具 ====================

def _is_last_backtest_day(context):
    try:
        end_date = context.run_params.end_date
        if end_date is None:
            return False
        if isinstance(end_date, datetime.datetime):
            end_date = end_date.date()
        elif not isinstance(end_date, datetime.date):
            try:
                end_date = pd.Timestamp(end_date).date()
            except Exception:
                return False
        return context.current_dt.date() >= end_date
    except Exception:
        return False


def _to_date_util(d):
    if isinstance(d, datetime.datetime):
        return d.date()
    elif isinstance(d, datetime.date):
        return d
    else:
        try:
            return pd.Timestamp(d).date()
        except Exception:
            return None


def _get_stock_names(context, codes):
    if not codes:
        return {}
    if (g._all_sec_cache is None or g._all_sec_cache_date is None or
            (context.previous_date - g._all_sec_cache_date).days > 30):
        try:
            g._all_sec_cache = get_all_securities(
                types=['stock'], date=context.previous_date)
            g._all_sec_cache_date = context.previous_date
        except Exception as e:
            log.warn('get_all_securities 失败：%s' % e)
            g._all_sec_cache = None
            return {c: c for c in codes}

    names = {}
    for c in codes:
        try:
            if c in g._all_sec_cache.index:
                names[c] = g._all_sec_cache.loc[c, 'display_name']
            else:
                names[c] = c
        except Exception:
            names[c] = c
    return names


def _format_codes_with_names(context, codes, limit=None):
    if not codes:
        return ''
    if limit is not None and len(codes) > limit:
        show = codes[:limit]
        suffix = ' ... (共%d只)' % len(codes)
    else:
        show = codes
        suffix = ''
    names = _get_stock_names(context, show)
    return ', '.join(['%s(%s)' % (c, names.get(c, c)) for c in show]) + suffix


def _count_trade_days(start_date, end_date):
    key = (start_date, end_date)
    if key in g._trade_days_cache:
        return g._trade_days_cache[key]
    try:
        days = get_trade_days(start_date=start_date, end_date=end_date)
        cnt = len(days) if days is not None else 0
    except Exception:
        cnt = 0
    g._trade_days_cache[key] = cnt
    if len(g._trade_days_cache) > 2000:
        g._trade_days_cache.clear()
    return cnt


def is_last_trade_day_of_week_cached(today):
    if today in g._last_trade_day_cache:
        return g._last_trade_day_cache[today]

    try:
        start = today - datetime.timedelta(days=10)
        end = today + datetime.timedelta(days=15)
        days = get_trade_days(start_date=start, end_date=end)
        if days is None or len(days) == 0:
            g._last_trade_day_cache[today] = False
            return False

        day_list = []
        for d in days:
            dd = _to_date_util(d)
            if dd is not None:
                day_list.append(dd)

        if not day_list:
            g._last_trade_day_cache[today] = False
            return False

        today_iso = today.isocalendar()
        today_week = (today_iso[0], today_iso[1])

        this_week_days = []
        for d in day_list:
            iso = d.isocalendar()
            if (iso[0], iso[1]) == today_week:
                this_week_days.append(d)

        if not this_week_days:
            result = False
        else:
            result = (today == max(this_week_days))
    except Exception as e:
        log.warn('判断本周最后一个交易日失败：%s' % e)
        result = False

    g._last_trade_day_cache[today] = result
    if len(g._last_trade_day_cache) > 60:
        keys = sorted(g._last_trade_day_cache.keys())
        for k in keys[:-30]:
            del g._last_trade_day_cache[k]
    return result


def get_min_lot(security):
    if security.startswith('688'):
        return 200
    return 100


def get_safe_limit_price(current_data, security, side='buy'):
    info = current_data[security]
    price = info.last_price
    if price is None or price <= 0:
        return None
    if side == 'buy':
        raw = round(price * 1.02, 2)
        try:
            if info.high_limit and raw > info.high_limit:
                raw = info.high_limit
        except Exception:
            pass
        return raw
    else:
        raw = round(price * 0.98, 2)
        try:
            if info.low_limit and raw < info.low_limit:
                raw = info.low_limit
        except Exception:
            pass
        return raw


def safe_buy(context, security, target_value):
    cd = get_current_data()
    info = cd[security]
    if info.paused or info.last_price is None or info.last_price <= 0:
        return False

    price = info.last_price
    min_lot = get_min_lot(security)
    if int(target_value / price) < min_lot:
        log.info('【买入跳过】%s 目标股数不足%d股' % (security, min_lot))
        return False

    order = None
    try:
        if security.startswith('688'):
            lp = get_safe_limit_price(cd, security, 'buy')
            if lp:
                order = order_target_value(security, target_value,
                                           style=LimitOrderStyle(lp))
            else:
                order = order_target_value(security, target_value)
        else:
            order = order_target_value(security, target_value)
    except Exception as e:
        log.warn('【买入下单异常】%s: %s' % (security, e))
        return False

    if order is None:
        return False

    filled = getattr(order, 'filled', None)
    if filled is not None:
        try:
            if float(filled) <= 0:
                return False
        except Exception:
            pass
    return True


def safe_sell(context, security):
    cd = get_current_data()
    if security.startswith('688'):
        lp = get_safe_limit_price(cd, security, 'sell')
        if lp:
            order_target_value(security, 0, style=LimitOrderStyle(lp))
        else:
            order_target_value(security, 0)
    else:
        order_target_value(security, 0)


# ==================== 国债ETF现金管理 ====================

def _get_active_bond_etf(context, current_data):
    for code in g.bond_etfs:
        pos = context.portfolio.positions.get(code)
        if pos and pos.total_amount > 0:
            try:
                cd = current_data[code]
                if cd.paused:
                    continue
                price = cd.last_price
                if price is not None and price > 0:
                    return code
            except Exception:
                continue

    for code in g.bond_etfs:
        try:
            cd = current_data[code]
            if cd.paused:
                continue
            price = cd.last_price
            if price is not None and price > 0:
                return code
        except Exception:
            continue
    return None


def _get_total_bond_value(context, current_data):
    total = 0
    for code in g.bond_etfs:
        pos = context.portfolio.positions.get(code)
        if pos and pos.total_amount > 0:
            try:
                price = current_data[code].last_price
                if price is not None and price > 0:
                    total += pos.total_amount * price
            except Exception:
                pass
    return total


def adjust_bond(context, target_bond, current_data):
    if target_bond < 0:
        target_bond = 0

    active = _get_active_bond_etf(context, current_data)
    if active is None:
        return

    for code in g.bond_etfs:
        if code == active:
            continue
        pos = context.portfolio.positions.get(code)
        if pos and pos.total_amount > 0:
            try:
                order_target_value(code, 0)
            except Exception as e:
                log.warn('清仓债券ETF %s 失败: %s' % (code, e))

    try:
        bond_price = current_data[active].last_price
    except Exception:
        return
    if bond_price is None or bond_price <= 0:
        return

    bond_pos = context.portfolio.positions.get(active)
    cur_amount = bond_pos.total_amount if bond_pos else 0
    target_amount = int(target_bond / bond_price / 100) * 100

    if target_amount < 100:
        if cur_amount >= 100:
            order_target_value(active, 0)
        return

    if abs(target_amount - cur_amount) < 100:
        return

    order_target_value(active, target_amount * bond_price)


def _idle_cash_to_bond(context, current_data):
    if _is_last_backtest_day(context):
        return

    cash = context.portfolio.available_cash
    if cash < g.min_bond_adjust:
        return

    active = _get_active_bond_etf(context, current_data)
    if active is None:
        return

    cur_bond_value = _get_total_bond_value(context, current_data)
    adjust_bond(context, cur_bond_value + cash, current_data)


def idle_cash_to_bond(context):
    if _is_last_backtest_day(context):
        return
    current_data = get_current_data()
    _idle_cash_to_bond(context, current_data)


# ==================== 股票池 ====================

def filter_stocks(context):
    all_stocks = []
    for index_code in g.index_pool:
        try:
            all_stocks.extend(
                get_index_stocks(index_code, date=context.previous_date))
        except Exception as e:
            log.warn('获取指数成分股失败：%s %s' % (index_code, e))

    all_stocks = list(set(all_stocks))
    if not all_stocks:
        return []

    current_data = get_current_data()

    if (g._all_sec_cache is None or g._all_sec_cache_date is None or
            (context.previous_date - g._all_sec_cache_date).days > 30):
        try:
            g._all_sec_cache = get_all_securities(
                types=['stock'], date=context.previous_date)
            g._all_sec_cache_date = context.previous_date
        except Exception as e:
            log.warn('get_all_securities 失败：%s' % e)
            g._all_sec_cache = None

    if g._all_sec_cache is not None:
        start_date_map = g._all_sec_cache['start_date'].to_dict()
    else:
        start_date_map = {}

    result = []
    for s in all_stocks:
        try:
            cd = current_data[s]
            if cd.is_st or '退' in cd.name or cd.paused:
                continue
            sd = start_date_map.get(s)
            if sd is None:
                continue
            if (context.previous_date - sd).days < 365:
                continue
            result.append(s)
        except Exception:
            continue
    return result


# ==================== 价格与周线构建 ====================

def _get_price_batched(codes, start_date, end_date, fields,
                       frequency='daily', batch_size=80):
    if not codes:
        return pd.DataFrame()

    all_df = []
    for i in range(0, len(codes), batch_size):
        batch = codes[i:i + batch_size]
        try:
            df = get_price(
                batch,
                start_date=start_date,
                end_date=end_date,
                frequency=frequency,
                fields=fields,
                panel=False,
                fq='pre'
            )
            if df is not None and len(df) > 0:
                all_df.append(df)
        except Exception as e:
            log.warn('get_price 批次失败：%s' % e)

    if not all_df:
        return pd.DataFrame()
    return pd.concat(all_df, ignore_index=True)


def _get_today_bar_map(context, codes):
    if not codes:
        return {}

    today = context.current_dt.date()
    current_data = get_current_data()
    result = {}

    try:
        df = get_price(
            codes,
            start_date=today,
            end_date=today,
            frequency='1m',
            fields=['open', 'high', 'low', 'close', 'volume'],
            panel=False,
            fq='pre'
        )
    except Exception as e:
        log.warn('获取今日实时数据失败：%s' % e)
        df = None

    if df is not None and len(df) > 0:
        for code, sub in df.groupby('code'):
            sub = sub.sort_values('time')
            if len(sub) == 0:
                continue

            try:
                cd = current_data[code]
                last_price = cd.last_price
            except Exception:
                last_price = None

            if last_price is None or last_price <= 0:
                last_price = float(sub['close'].values[-1])

            last_price = float(last_price)

            result[code] = {
                'open': float(sub['open'].values[0]),
                'high': max(float(sub['high'].max()), last_price),
                'low': min(float(sub['low'].min()), last_price),
                'close': last_price,
                'volume': float(sub['volume'].sum()),
            }
    else:
        for code in codes:
            try:
                cd = current_data[code]
                if cd.paused or cd.last_price is None or cd.last_price <= 0:
                    continue
                p = float(cd.last_price)
                result[code] = {
                    'open': p, 'high': p, 'low': p,
                    'close': p, 'volume': 0.0
                }
            except Exception:
                continue
    return result


def _build_weekly_bars(df, today=None, today_bar_map=None):
    result = {}
    if df is None or len(df) == 0:
        return result

    df = df.copy()
    df['time'] = pd.to_datetime(df['time'])

    if today is not None and today_bar_map:
        add_rows = []
        for code, bar in today_bar_map.items():
            if bar is None:
                continue
            add_rows.append({
                'code': code,
                'time': pd.Timestamp(today),
                'open': float(bar['open']),
                'high': float(bar['high']),
                'low': float(bar['low']),
                'close': float(bar['close']),
                'volume': float(bar.get('volume', 0)),
            })
        if add_rows:
            df = pd.concat([df, pd.DataFrame(add_rows)], ignore_index=True)

    df = df.dropna(subset=['close'])
    if len(df) == 0:
        return result

    df = df.sort_values(['code', 'time'])

    for code, sub in df.groupby('code', sort=False):
        sub = sub.sort_values('time').copy()
        sub['date'] = sub['time'].dt.date
        sub['iso_year'] = sub['date'].apply(lambda d: d.isocalendar()[0])
        sub['iso_week'] = sub['date'].apply(lambda d: d.isocalendar()[1])

        weekly = sub.groupby(['iso_year', 'iso_week']).agg({
            'time': 'last',
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
        }).reset_index()
        weekly = weekly.sort_values('time').reset_index(drop=True)

        opens = weekly['open'].values.astype(float)
        highs = weekly['high'].values.astype(float)
        lows = weekly['low'].values.astype(float)
        closes = weekly['close'].values.astype(float)
        n = len(closes)

        ma52 = np.full(n, np.nan)
        ma10 = np.full(n, np.nan)
        for i in range(n):
            if i >= g.ma_year_window - 1:
                ma52[i] = np.mean(closes[i - g.ma_year_window + 1:i + 1])
            if i >= g.ma_sell_window - 1:
                ma10[i] = np.mean(closes[i - g.ma_sell_window + 1:i + 1])

        result[code] = {
            'dates': weekly['time'].tolist(),
            'opens': opens,
            'highs': highs,
            'lows': lows,
            'closes': closes,
            'ma52': ma52,
            'ma10': ma10,
        }
    return result


# ==================== 核心筛选 ====================

def _check_week_gain_limit(opens, closes, k):
    """检查第k周涨幅是否 <= 20%"""
    if k < 0 or k >= len(opens):
        return False
    if opens[k] <= 0:
        return False
    gain = closes[k] / opens[k] - 1
    return gain <= g.f_week_gain_max


def _check_box_breakout(w):
    if w is None:
        return False

    opens = w['opens']
    highs = w['highs']
    closes = w['closes']
    ma52 = w['ma52']
    n = len(closes)

    if n < 80:
        return False

    last = n - 1
    if np.isnan(ma52[last]):
        return False

    start_f = last - 1 - g.max_weeks_after_confirm
    end_f = last - 1

    if start_f < 0:
        start_f = 0
    if end_f < start_f:
        return False

    for F in range(end_f, start_f - 1, -1):
        if F < 1 or F + 1 >= n:
            continue

        if np.isnan(ma52[F]) or np.isnan(ma52[F + 1]):
            continue

        # 箱体震荡周数范围：box_min_weeks ~ box_max_weeks
        d_min = max(0, F - g.box_max_weeks)
        d_max = F - g.box_min_weeks
        if d_max < d_min:
            continue

        found_d = None
        box_max_close = None

        for D in range(d_max, d_min - 1, -1):
            if D < g.low_break_lookback:
                continue
            if D + g.stand_above_weeks >= F:
                continue
            if np.isnan(ma52[D]):
                continue

            if not (closes[D] > ma52[D]):
                continue

            ok = True
            for j in range(D - 9, D):
                if j < 0 or np.isnan(ma52[j]):
                    ok = False
                    break
                if closes[j] > ma52[j]:
                    ok = False
                    break
            if not ok:
                continue

            cnt_above = 0
            for j in range(D - g.low_break_lookback, D - 9):
                if j < 0 or np.isnan(ma52[j]):
                    ok = False
                    break
                if closes[j] > ma52[j]:
                    cnt_above += 1
            if not ok or cnt_above > g.low_break_tolerance_max:
                continue

            if np.isnan(ma52[D + 1]) or np.isnan(ma52[D + 2]):
                continue
            if not (closes[D + 1] > ma52[D + 1] and
                    closes[D + 2] > ma52[D + 2]):
                continue

            box_weeks = F - D
            if box_weeks < g.box_min_weeks or box_weeks > g.box_max_weeks:
                continue

            outside_cnt = 0
            box_ok = True
            for j in range(D, F):
                if np.isnan(ma52[j]):
                    box_ok = False
                    break
                low = g.box_low_ratio * ma52[j]
                high = g.box_high_ratio * ma52[j]
                if closes[j] < low or closes[j] > high:
                    outside_cnt += 1
                    if outside_cnt > g.box_outside_tolerance:
                        box_ok = False
                        break
            if not box_ok:
                continue

            if ma52[last] <= ma52[D]:
                continue

            seg_close = closes[D:F]
            seg_ma52 = ma52[D:F]
            if len(seg_close) == 0:
                continue

            max_idx = int(np.argmax(seg_close))
            bmc = float(seg_close[max_idx])
            if bmc <= 0:
                continue

            if not np.isnan(seg_ma52[max_idx]):
                upper_bound = g.box_high_ratio * float(seg_ma52[max_idx])
                if bmc > upper_bound:
                    bmc = upper_bound

            found_d = D
            box_max_close = bmc
            break

        if found_d is None:
            continue

        if not (closes[F] > box_max_close and closes[F + 1] > box_max_close):
            continue

        # 买入限制：F-1、F、F+1 三周涨幅均 <= 20%
        if not _check_week_gain_limit(opens, closes, F - 1):
            continue
        if not _check_week_gain_limit(opens, closes, F):
            continue
        if not _check_week_gain_limit(opens, closes, F + 1):
            continue

        return True

    return False


def get_candidates(context):
    today = context.current_dt.date()

    if g._candidate_cache_date == today:
        return list(g._candidate_cache)

    stock_list = filter_stocks(context)
    if not stock_list:
        g._candidate_cache_date = today
        g._candidate_cache = []
        return []

    end_date = context.previous_date
    start_date = end_date - datetime.timedelta(days=1100)

    df = _get_price_batched(
        stock_list,
        start_date=start_date,
        end_date=end_date,
        fields=['open', 'high', 'low', 'close'],
        frequency='daily',
        batch_size=80
    )

    if df is None or len(df) == 0:
        log.info('【筛选】日线数据为空')
        g._candidate_cache_date = today
        g._candidate_cache = []
        return []

    today_bar_map = _get_today_bar_map(context, stock_list)
    weekly_data = _build_weekly_bars(
        df, today=today, today_bar_map=today_bar_map)

    candidates = []
    for code in stock_list:
        if code not in weekly_data:
            continue
        try:
            if _check_box_breakout(weekly_data[code]):
                candidates.append(code)
        except Exception as e:
            log.warn('检查 %s 箱体突破失败：%s' % (code, e))

    candidates = sorted(list(set(candidates)))

    g._candidate_cache_date = today
    g._candidate_cache = candidates

    log.info('【周线箱体突破筛选】股票池=%d 候选=%d %s' % (
        len(stock_list),
        len(candidates),
        _format_codes_with_names(context, candidates, limit=20)
    ))

    return candidates


# ==================== 高分红 + 低换手排名 ====================

def _get_dividend_ratio_simple(context, stock_list):
    if not stock_list:
        return pd.DataFrame()

    end_date = context.previous_date
    start_date = end_date - datetime.timedelta(days=730)

    q = query(
        valuation.code,
        valuation.market_cap
    ).filter(valuation.code.in_(stock_list))

    try:
        df_fund = get_fundamentals(q, date=end_date)
    except Exception as e:
        log.warn('获取市值失败：%s' % e)
        return pd.DataFrame()

    if df_fund is None or len(df_fund) == 0:
        return pd.DataFrame()

    df_fund = df_fund.dropna(subset=['market_cap'])
    if len(df_fund) == 0:
        return pd.DataFrame()

    codes = list(df_fund['code'])
    dividend_list = []
    interval = 1000

    for i in range(0, len(codes), interval):
        batch = codes[i:i + interval]
        q_div = query(
            finance.STK_XR_XD.code,
            finance.STK_XR_XD.bonus_amount_rmb
        ).filter(
            finance.STK_XR_XD.a_registration_date >= start_date,
            finance.STK_XR_XD.a_registration_date <= end_date,
            finance.STK_XR_XD.code.in_(batch)
        )
        try:
            df_temp = finance.run_query(q_div)
            if df_temp is not None and len(df_temp) > 0:
                dividend_list.append(df_temp)
        except Exception as e:
            log.warn('分红查询失败：%s' % e)

    if dividend_list:
        df_div = pd.concat(dividend_list, ignore_index=True)
        df_div = df_div.groupby('code')['bonus_amount_rmb'].sum().reset_index()
        df_div.columns = ['code', 'total_dividend_rmb']
    else:
        df_div = pd.DataFrame(columns=['code', 'total_dividend_rmb'])

    df = pd.merge(df_fund[['code', 'market_cap']], df_div, on='code', how='left')
    df['total_dividend_rmb'] = df['total_dividend_rmb'].fillna(0)
    df['dividend_ratio'] = df['total_dividend_rmb'] / (df['market_cap'] * 1e8) * 100

    return df[['code', 'dividend_ratio']]


def _get_avg_turnover(context, stock_list, days=20):
    if not stock_list:
        return pd.DataFrame()

    end_date = context.previous_date
    start_date = end_date - datetime.timedelta(days=60)

    try:
        price_df = get_price(
            stock_list,
            start_date=start_date,
            end_date=end_date,
            frequency='daily',
            fields=['volume'],
            panel=False
        )
    except Exception as e:
        log.warn('获取换手成交量失败：%s' % e)
        return pd.DataFrame()

    if price_df is None or len(price_df) == 0:
        return pd.DataFrame()

    trade_dates = sorted(price_df['time'].unique())[-days:]
    price_df = price_df[price_df['time'].isin(trade_dates)]

    q = query(
        valuation.code,
        valuation.circulating_cap
    ).filter(valuation.code.in_(stock_list))

    try:
        df_cap = get_fundamentals(q, date=end_date)
    except Exception as e:
        log.warn('获取流通股本失败：%s' % e)
        return pd.DataFrame()

    if df_cap is None or len(df_cap) == 0:
        return pd.DataFrame()

    df_cap = df_cap.dropna(subset=['circulating_cap'])
    if len(df_cap) == 0:
        return pd.DataFrame()

    df = pd.merge(price_df, df_cap, on='code', how='inner')
    df = df[df['volume'] > 0]
    if len(df) == 0:
        return pd.DataFrame()

    df['turnover'] = df['volume'] / (df['circulating_cap'] * 1e4)
    turnover_avg = df.groupby('code')['turnover'].mean().reset_index()
    turnover_avg.columns = ['code', 'turnover_avg']
    return turnover_avg


def rank_candidates_by_dividend_turnover(context, candidates, top_n):
    if len(candidates) <= top_n:
        return list(candidates)

    df_div = _get_dividend_ratio_simple(context, candidates)
    df_turn = _get_avg_turnover(context, candidates, days=20)

    if df_div is None or len(df_div) == 0:
        df = pd.DataFrame({'code': candidates})
        df['dividend_ratio'] = 0.0
    else:
        df = df_div.copy()

    if df_turn is None or len(df_turn) == 0:
        df['turnover_avg'] = 0.0
    else:
        df = pd.merge(df, df_turn, on='code', how='outer')

    df = df[df['code'].isin(candidates)].copy()
    df['dividend_ratio'] = df['dividend_ratio'].fillna(0.0)

    max_turn = df['turnover_avg'].max() if 'turnover_avg' in df and len(df) > 0 else 999.0
    if pd.isna(max_turn):
        max_turn = 999.0
    df['turnover_avg'] = df['turnover_avg'].fillna(max_turn)

    df['dividend_rank'] = df['dividend_ratio'].rank(ascending=False, method='min')
    df['turnover_rank'] = df['turnover_avg'].rank(ascending=True, method='min')
    df['total_score'] = df['dividend_rank'] + df['turnover_rank']
    df = df.sort_values(['total_score', 'code'], ascending=[True, True])

    result = list(df['code'].head(top_n))
    log.info('【高分红+低换手排名】候选=%d 取前%d: %s' % (
        len(candidates), top_n,
        _format_codes_with_names(context, result)
    ))
    return result


# ==================== 卖出：每日14:20 多规则 ====================

def _check_ma52_break(closes, lows, ma52, weeks, low_ratio):
    """连续 weeks 周收盘 < MA52，且其中至少一周最低 < 该周MA52×low_ratio"""
    if len(closes) < weeks or len(ma52) < weeks or len(lows) < weeks:
        return False, None

    n = len(closes)
    start = n - weeks

    for i in range(start, n):
        if np.isnan(ma52[i]):
            return False, None
        if not (closes[i] < ma52[i]):
            return False, None

    hit_low = False
    for i in range(start, n):
        if lows[i] < ma52[i] * low_ratio:
            hit_low = True
            break

    if not hit_low:
        return False, None

    return True, start


def daily_sell_check(context):
    if _is_last_backtest_day(context):
        return

    today = context.current_dt.date()
    current_data = get_current_data()

    holdings = [
        s for s in context.portfolio.positions
        if s not in g.bond_etfs and context.portfolio.positions[s].total_amount > 0
    ]
    if not holdings:
        return

    end_date = context.previous_date
    start_date = end_date - datetime.timedelta(days=200)

    df = _get_price_batched(
        holdings,
        start_date=start_date,
        end_date=end_date,
        fields=['open', 'high', 'low', 'close'],
        frequency='daily',
        batch_size=50
    )

    if df is None or len(df) == 0:
        return

    today_bar_map = _get_today_bar_map(context, holdings)
    weekly_data = _build_weekly_bars(
        df, today=today, today_bar_map=today_bar_map)

    is_week_end = is_last_trade_day_of_week_cached(today)

    to_sell = []

    for code in holdings:
        if code not in weekly_data:
            continue
        try:
            cd = current_data[code]
            if cd.paused:
                continue
            price = cd.last_price
            if price is None or price <= 0:
                continue

            w = weekly_data[code]
            closes_w = w['closes']
            lows_w = w['lows']
            ma52_w = w['ma52']

            if len(closes_w) == 0:
                continue

            week_open = w['opens'][-1]
            week_high = w['highs'][-1]

            # 1) 周线MA52止损：连续2周收盘<MA52，且其中至少一周最低<MA52×0.97
            ma52_break, start_i = _check_ma52_break(
                closes_w, lows_w, ma52_w,
                g.break_ma52_weeks, g.break_ma52_low_ratio)
            if ma52_break:
                k1 = start_i
                k2 = start_i + g.break_ma52_weeks - 1
                to_sell.append((
                    code,
                    '周线MA52止损：连续%d周收盘<MA52且最低<MA52×%.2f；'
                    '第1周收盘%.2f<MA52=%.2f低%.2f，'
                    '第2周收盘%.2f<MA52=%.2f低%.2f' % (
                        g.break_ma52_weeks, g.break_ma52_low_ratio,
                        closes_w[k1], ma52_w[k1], lows_w[k1],
                        closes_w[k2], ma52_w[k2], lows_w[k2]
                    )
                ))
                continue

            # 2) 极端涨幅卖出：本周至今涨幅 > 30%
            if week_open is not None and week_open > 0:
                week_gain = price / week_open - 1
                if week_gain > g.extreme_week_gain_sell:
                    to_sell.append((
                        code,
                        '极端涨幅：本周至今涨幅%.2f%%>%.0f%%（本周开盘%.2f，现价%.2f）' % (
                            week_gain * 100,
                            g.extreme_week_gain_sell * 100,
                            week_open, price
                        )
                    ))
                    continue

            # 3) 冲高回落卖出：本周最高价 > 当前价 × 1.15
            if week_high is not None and week_high > 0:
                drop_ratio = (week_high - price) / price if price > 0 else 0
                if week_high > price * (1 + g.drop_from_week_high_sell):
                    to_sell.append((
                        code,
                        '冲高回落：本周最高%.2f > 现价%.2f×%.2f=%.2f，'
                        '回落幅度%.2f%%>%.0f%%' % (
                            week_high, price,
                            1 + g.drop_from_week_high_sell,
                            price * (1 + g.drop_from_week_high_sell),
                            drop_ratio * 100,
                            g.drop_from_week_high_sell * 100
                        )
                    ))
                    continue

            # 4) 止盈：仅每周最后一个交易日14:20判断
            if is_week_end:
                entry_price = g.entry_prices.get(code)
                if entry_price is None:
                    pos = context.portfolio.positions.get(code)
                    if pos is not None and pos.price is not None and pos.price > 0:
                        entry_price = float(pos.price)
                        g.entry_prices[code] = entry_price

                if entry_price is not None and price > entry_price * g.take_profit_price_ratio:
                    if week_open is not None and week_open > 0:
                        upper_shadow = week_high - price
                        body_gain = price - week_open
                        week_gain_abs = abs(price - week_open) / week_open

                        cond2 = upper_shadow > body_gain
                        cond3 = week_gain_abs > g.take_profit_week_gain_min

                        if cond2 and cond3:
                            to_sell.append((
                                code,
                                '止盈：现价%.2f>买入价%.2f×%.2f=%.2f，'
                                '本周高%.2f现价%.2f开盘%.2f，'
                                '上影%.2f>实体%.2f，周涨跌幅%.2f%%>%.0f%%' % (
                                    price, entry_price,
                                    g.take_profit_price_ratio,
                                    entry_price * g.take_profit_price_ratio,
                                    week_high, price, week_open,
                                    upper_shadow, body_gain,
                                    week_gain_abs * 100,
                                    g.take_profit_week_gain_min * 100
                                )
                            ))
        except Exception as e:
            log.warn('检查 %s 卖出条件失败：%s' % (code, e))

    if not to_sell:
        return

    names = _get_stock_names(context, [c for c, _ in to_sell])
    total_sell_value = 0

    for code, reason in to_sell:
        pos = context.portfolio.positions.get(code)
        if pos is None or pos.total_amount <= 0:
            continue

        try:
            sell_value = pos.total_amount * current_data[code].last_price
        except Exception:
            sell_value = 0

        safe_sell(context, code)

        g.position_entry_dates.pop(code, None)
        g.entry_prices.pop(code, None)
        g.sold_dates[code] = today
        total_sell_value += sell_value

        log.info('【卖出】%s(%s) | 理由=%s | 金额≈%.0f' % (
            code, names.get(code, code), reason, sell_value))

    if total_sell_value > 0:
        bond_value = _get_total_bond_value(context, current_data)
        adjust_bond(context, bond_value + total_sell_value, current_data)


# ==================== 买入：每周最后一个交易日14:30 ====================

def weekly_buy(context):
    if _is_last_backtest_day(context):
        return

    today = context.current_dt.date()

    for code in list(g.sold_dates.keys()):
        if (today - g.sold_dates[code]).days > 90:
            del g.sold_dates[code]

    if not is_last_trade_day_of_week_cached(today):
        return

    current_data = get_current_data()
    total_value = context.portfolio.total_value

    holdings = [
        s for s in context.portfolio.positions
        if s not in g.bond_etfs and context.portfolio.positions[s].total_amount > 0
    ]

    slots = g.hold_num - len(holdings)
    if slots <= 0:
        log.info('【周买入】无空位，持仓=%d' % len(holdings))
        _idle_cash_to_bond(context, current_data)
        return

    candidates = get_candidates(context)
    if not candidates:
        log.info('【周买入】无候选')
        _idle_cash_to_bond(context, current_data)
        return

    holdings_set = set(holdings)

    filtered = []
    for code in candidates:
        if code in holdings_set:
            continue

        sold = g.sold_dates.get(code)
        if sold is not None:
            td_passed = _count_trade_days(sold, today)
            if td_passed <= g.cooldown_trade_days:
                continue

        try:
            cd = current_data[code]
            if cd.paused or cd.last_price is None or cd.last_price <= 0:
                continue
        except Exception:
            continue

        filtered.append(code)

    if not filtered:
        log.info('【周买入】候选全部被排除')
        _idle_cash_to_bond(context, current_data)
        return

    if len(filtered) > slots:
        to_buy = rank_candidates_by_dividend_turnover(context, filtered, slots)
    else:
        to_buy = list(filtered)
        log.info('【周买入】候选不超过剩余仓位，不排名直接买入：%s' % (
            _format_codes_with_names(context, to_buy)
        ))

    if not to_buy:
        _idle_cash_to_bond(context, current_data)
        return

    bond_value = _get_total_bond_value(context, current_data)
    cash = context.portfolio.available_cash
    available = bond_value + cash

    if available < 1000:
        log.info('【周买入】可用资金不足 %.0f' % available)
        return

    n_buy = len(to_buy)
    per_max = total_value * g.max_single_position
    per = min(available / n_buy, per_max)

    valid = []
    for code in to_buy:
        cd = current_data[code]
        min_lot = get_min_lot(code)
        if cd.last_price * min_lot > per:
            log.info('【周买入跳过】%s 一手%d股=%.0f > 单只额度=%.0f' % (
                code, min_lot, cd.last_price * min_lot, per))
            continue
        valid.append(code)

    if not valid:
        log.info('【周买入】所有候选一手均超过单只额度')
        _idle_cash_to_bond(context, current_data)
        return

    to_buy = valid
    n_buy = len(to_buy)
    per = min(available / n_buy, per_max)
    buy_amount = per * n_buy

    names = _get_stock_names(context, to_buy)

    log.info('【周买入执行】买入%d只，每只≈%.0f(%.1f%%)，可用=%.0f' % (
        n_buy, per, per / total_value * 100 if total_value > 0 else 0, available))

    need_from_bond = max(0, buy_amount - cash)
    if need_from_bond > 0:
        bond_target = max(0, bond_value - need_from_bond)
        adjust_bond(context, bond_target, current_data)

    success_count = 0

    for code in to_buy:
        ok = safe_buy(context, code, per)
        if not ok:
            log.info('【周买入失败】%s(%s) 下单未成功' % (
                code, names.get(code, code)))
            continue

        pos = context.portfolio.positions.get(code)
        if pos is None or pos.total_amount <= 0:
            log.info('【周买入失败】%s(%s) 未成交' % (
                code, names.get(code, code)))
            continue

        success_count += 1
        g.position_entry_dates[code] = today
        g.sold_dates.pop(code, None)

        try:
            px = current_data[code].last_price
        except Exception:
            px = 0

        if px is not None and px > 0:
            g.entry_prices[code] = float(px)
        else:
            try:
                if pos.price is not None and pos.price > 0:
                    g.entry_prices[code] = float(pos.price)
            except Exception:
                pass

        log.info('【周买入】%s(%s) 金额≈%.0f 价格≈%.2f 买入价记录=%.2f' % (
            code, names.get(code, code), per, px,
            g.entry_prices.get(code, 0)))

    if success_count < n_buy:
        cur_cash = context.portfolio.available_cash
        if cur_cash >= g.min_bond_adjust:
            cur_bond = _get_total_bond_value(context, current_data)
            adjust_bond(context, cur_bond + cur_cash, current_data)


# ==================== 最后一天清仓 ====================

def _clear_all_positions(context):
    current_data = get_current_data()
    all_codes = list(context.portfolio.positions.keys())
    if not all_codes:
        return

    stock_codes = [c for c in all_codes if c not in g.bond_etfs]
    bond_codes = [c for c in all_codes if c in g.bond_etfs]

    names = _get_stock_names(context, stock_codes) if stock_codes else {}
    total_value = 0

    for code in stock_codes:
        pos = context.portfolio.positions.get(code)
        if pos is None or pos.total_amount <= 0:
            continue
        try:
            price = current_data[code].last_price
            value = pos.total_amount * price if price and price > 0 else 0
            safe_sell(context, code)
            total_value += value
            log.info('【最后一天清仓】%s(%s) 卖出≈%.0f' % (
                code, names.get(code, code), value))
        except Exception as e:
            log.warn('清仓 %s 失败: %s' % (code, e))

        g.position_entry_dates.pop(code, None)
        g.entry_prices.pop(code, None)

    for code in bond_codes:
        pos = context.portfolio.positions.get(code)
        if pos is None or pos.total_amount <= 0:
            continue
        try:
            price = current_data[code].last_price
            value = pos.total_amount * price if price and price > 0 else 0
            safe_sell(context, code)
            total_value += value
            log.info('【最后一天清仓】%s 卖出≈%.0f' % (code, value))
        except Exception as e:
            log.warn('清仓债券 %s 失败: %s' % (code, e))

    log.info('【最后一天清仓完成】清仓总额≈%.0f' % total_value)


def final_clear(context):
    if _is_last_backtest_day(context):
        _clear_all_positions(context)