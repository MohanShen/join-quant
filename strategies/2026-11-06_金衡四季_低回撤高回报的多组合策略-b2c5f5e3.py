# Clone from JoinQuant
# postId: b2c5f5e36ba82f18c85169a18495d43e
# backtestId: 23809fe62f79f441c851882326d83e6a
# title: 金衡四季：低回撤高回报的多组合策略

# -*- coding: utf-8 -*-
"""金衡四季：黄金20% + 红利价值20% + ETF动量20% + 十只小市值40%"""
import builtins
import datetime
import math

import numpy as np
import pandas as pd
from jqdata import *
from jqdata import finance


STRATEGY_NAME = '金衡四季'
BASE_WEIGHTS = (0.20, 0.20, 0.20, 0.40)
NAMES = ('黄金', '红利价值增强', 'ETF动量', '十只小市值')
COUNTS = (1, 5, 1, 10)
EMPTY_MONTHS = (1, 4)
CASH_RESERVE = 0.005
GOLD = '518880.XSHG'
SMALL_FACTOR_WEIGHTS = np.array([1.0, 1.0, 1.6, 0.8, 2.0])
ETF_DAYS = 25
ETF_SCORE_MAX = 6.0
ETF_STOP = -0.03
ETF_POOL = (
    '510180.XSHG', '159915.XSHE', '588190.XSHG',
    '510410.XSHG', '512290.XSHG', '512480.XSHG', '512710.XSHG',
    '515650.XSHG', '515070.XSHG', '516160.XSHG', '159851.XSHE',
    '159637.XSHE', '512880.XSHG', '518880.XSHG', '501018.XSHG',
    '159985.XSHE', '159980.XSHE', '513100.XSHG', '159509.XSHE',
    '513030.XSHG', '513520.XSHG', '513690.XSHG', '513130.XSHG',
    '159550.XSHE', '511220.XSHG',
)


def seasonal_weights(month):
    return (1.0 / 3, 1.0 / 3, 1.0 / 3, 0.0) if month in EMPTY_MONTHS else BASE_WEIGHTS


def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    
    for kind, tax in [('stock', 0.0005), ('fund', 0.0)]:
        set_order_cost(OrderCost(open_tax=0, close_tax=tax,
                                open_commission=0.0003, close_commission=0.0003,
                                close_today_commission=0, min_commission=5), type=kind)
    set_slippage(FixedSlippage(0.02), type='stock')
    set_slippage(FixedSlippage(0.002), type='fund')
    cash = float(context.portfolio.starting_cash)
    weights = seasonal_weights(context.current_dt.month)
    values = [cash * w for w in weights]
    values[-1] = cash - builtins.sum(values[:-1])
    set_subportfolios([SubPortfolioConfig(cash=v, type='stock') for v in values])
    g.targets = {i: [] for i in range(4)}
    g.high_limits = {i: [] for i in (1, 3)}
    g.pending_exits = {i: [] for i in range(4)}
    g.blocked_today = []
    g.active = []
    g.order_accounts = {}
    g.month = None
    g.week = None
    g.rebalancing = False
    g.weights = weights
    schedule_tasks()


def after_code_changed(context):

    if len(context.subportfolios) != 4 or not hasattr(g, 'targets'):
        raise ValueError('金衡四季需要新建四子账户回测/模拟实例。')
    schedule_tasks()


def schedule_tasks():
    unschedule_all()
    run_daily(prepare_day, time='09:10')
    run_daily(etf_stop_loss, time='10:00')
    run_daily(plan_and_sell, time='10:40')
    run_daily(transfer_and_buy, time='10:45')
    run_daily(etf_volume_check, time='13:30')
    run_daily(check_limit_open, time='14:00')
    run_daily(report, time='15:10')


def sub(context, index):
    return context.subportfolios[index]


def holdings(context, index):
    return {s: p for s, p in sub(context, index).long_positions.items()
            if p.total_amount > 0}


def prepare_day(context):
    g.blocked_today = []
    g.pending_exits[2] = [s for s in g.pending_exits[2] if s in holdings(context, 2)]
    open_ids = set(get_open_orders())
    g.order_accounts = {key: value for key, value in g.order_accounts.items() if key in open_ids}
    for index in (1, 3):
        codes = list(holdings(context, index))
        g.high_limits[index] = []
        if codes:
            df = get_price(codes, end_date=context.previous_date, count=1,
                           frequency='daily', fields=['close', 'high_limit'],
                           panel=False, fill_paused=False)
            if df is not None and not df.empty:
                g.high_limits[index] = df.loc[df.close == df.high_limit, 'code'].tolist()


def plan_and_sell(context):
    today = context.current_dt.date()
    month = (today.year, today.month)
    week = tuple(today.isocalendar()[:2])
    monthly = g.month != month
    weekly = g.week != week
    g.active = [2]
    if monthly:
        g.weights = seasonal_weights(today.month)
        g.rebalancing = True
        g.targets[0] = [GOLD]
        g.targets[1] = select_dividend(context)
        g.pending_exits[1] = [] 
        g.active.extend([0, 1, 3])
        g.month = month
    if monthly or weekly:
        g.targets[3] = [] if today.month in EMPTY_MONTHS else select_small_cap(context)
        g.pending_exits[3] = []
        g.active.append(3)
        g.week = week
    if today.month in EMPTY_MONTHS:
        g.targets[3] = []
        g.active.append(3) 
    g.targets[2] = rank_etfs(context)[:1]
    if g.rebalancing:
        g.active.extend(range(4))
    g.active.extend(i for i in range(4)
                    if builtins.any(s in holdings(context, i) for s in g.pending_exits[i]))
    g.active = sorted(set(g.active))
    # 所有账户先卖，5分钟后再转账和买入。
    for index in range(4):
        for code in list(g.pending_exits[index]):
            if code in holdings(context, index):
                submit_target(context, index, code, 0)
    for index in g.active:
        sell_to_plan(context, index)


def account_budget(context, index):
    value = float(sub(context, index).total_value)
    if g.rebalancing:
        total = builtins.sum(float(s.total_value) for s in context.subportfolios)
        value = min(value, total * g.weights[index])
    return max(0.0, value * (1.0 - CASH_RESERVE))


def protected(context, index, code):
    return (index in (1, 3) and code in g.high_limits[index]
            and code not in g.pending_exits[index]
            and not (index == 3 and context.current_dt.month in EMPTY_MONTHS))


def target_plan(context, index):

    positions = holdings(context, index)
    candidates = [s for s in g.targets[index] if s not in g.pending_exits[index]]

    old = {s: p for s, p in positions.items() if s not in candidates}
    existing = [s for s in candidates if s in positions]
    slots = max(0, COUNTS[index] - len(old) - len(existing))
    chosen = existing + [s for s in candidates if s not in positions][:slots]
    locked = builtins.sum(float(p.value) for p in old.values())
    cash_for_targets = max(0.0, account_budget(context, index) - locked)

    divisor = max(len(chosen), COUNTS[index] - len(old))
    each = cash_for_targets / divisor if divisor else 0.0
    return {s: each for s in chosen}


def sell_to_plan(context, index):
    for code in list(holdings(context, index)):
        if code not in g.targets[index] and not protected(context, index, code):
            request_exit(context, index, code)
    plan = target_plan(context, index)
    for code, target in plan.items():
        position = holdings(context, index).get(code)
        if position and position.value > target:
            submit_target(context, index, code, target)


def transfer_and_buy(context):
    if g.rebalancing:
        rebalance_cash(context)
    for index in g.active:
        plan = target_plan(context, index)
        log.info('%s 买入计划：%s；可用现金 %.2f' % (
            NAMES[index], plan, sub(context, index).available_cash))
        for code, target in plan.items():
            position = holdings(context, index).get(code)
            value = float(position.value) if position else 0.0
            if target > value:
                submit_target(context, index, code, target)


def rebalance_cash(context):
    subs = context.subportfolios
    total = builtins.sum(float(s.total_value) for s in subs)
    targets = [total * w for w in g.weights]
    for donor in range(4):
        for receiver in range(4):
            if donor == receiver:
                continue
            amount = min(float(subs[donor].total_value) - targets[donor],
                         targets[receiver] - float(subs[receiver].total_value),
                         float(subs[donor].available_cash),
                         float(subs[donor].transferable_cash))
            amount = math.floor(amount * 100) / 100
            if amount < 1:
                continue
            try:
                transfer_cash(from_pindex=donor, to_pindex=receiver, cash=amount)
            except Exception as error:
                log.warn('账户转账失败，将重试：%s' % error)
    tolerance = max(10.0, total * 0.0001)
    g.rebalancing = builtins.any(abs(float(s.total_value) - targets[i]) > tolerance
                        for i, s in enumerate(subs))
    if g.rebalancing:
        log.info('月度再平衡尚有偏差，保留任务到下一交易日。各账户偏差：%s' %
                 [round(float(s.total_value) - targets[i], 2) for i, s in enumerate(subs)])


def submit_target(context, index, code, target):
    data = get_current_data()[code]
    price = float(data.last_price)
    if data.paused or not np.isfinite(price) or price <= 0:
        return None
    position = holdings(context, index).get(code)
    current_value = float(position.value) if position else 0.0
    target = max(0.0, float(target))
    if target < current_value:
        if price <= data.low_limit or position.closeable_amount <= 0:
            return None

        target = max(target, (position.total_amount - position.closeable_amount) * price)
    else:
        if price >= data.high_limit or (index == 2 and code in g.blocked_today):
            return None
        cash = max(0.0, float(sub(context, index).available_cash) - 5.0)
        target = min(target, current_value + cash / 1.0003)
    if target > 0 and abs(target - current_value) < price * 100:
        return None

    if builtins.any(o.security == code and g.order_accounts.get(key, index) == index
           for key, o in get_open_orders().items()):
        log.info('%s %s 已有未完成委托，跳过重复目标单。' % (NAMES[index], code))
        return None
    result = order_target_value(code, target, pindex=index)
    if result is not None:
        g.order_accounts[result.order_id] = index
        log.info('%s %s 目标单已提交：目标市值 %.2f，订单 %s，已成交数量 %s' % (
            NAMES[index], code, target, result.order_id, result.filled))
    if result is None:
        log.warn('%s %s 目标单未被接受，目标市值 %.2f' % (NAMES[index], code, target))
    return result


def stock_universe(context, age):
    current = get_current_data()
    result = []
    for code in get_all_securities('stock', date=context.previous_date).index:
        if code.startswith(('4', '8', '68', '92')):
            continue
        data = current[code]
        if data.is_st or builtins.any(tag in data.name for tag in ('ST', '*', '退')):
            continue
        info = get_security_info(code)
        if info and (context.previous_date - info.start_date).days >= age:
            result.append(code)
    return result


def tradable_targets(context, index, ranked):
    current = get_current_data()
    held = holdings(context, index)
    return [s for s in ranked if not current[s].paused
            and np.isfinite(current[s].last_price) and current[s].last_price > 0
            and (s in held or current[s].low_limit < current[s].last_price < current[s].high_limit)
            ][:COUNTS[index]]


def select_dividend(context):
    stocks = stock_universe(context, 250)
    current = get_current_data()
    stocks = [s for s in stocks if not current[s].paused]
    if not stocks:
        return []
    df = get_fundamentals(query(valuation.code).filter(
        valuation.code.in_(stocks), valuation.pe_ratio.between(5, 50),
        indicator.inc_return.between(5, 100),
        indicator.inc_total_revenue_year_on_year.between(5, 100),
        indicator.inc_net_profit_year_on_year.between(10, 100)), date=context.previous_date)
    stocks = df.code.tolist()
    frames = []
    end = context.previous_date
    start = end - datetime.timedelta(days=365)

    for offset in range(0, len(stocks), 200):
        page = 0
        while True:
            table = finance.STK_XR_XD
            q = query(table.id, table.code, table.bonus_amount_rmb).filter(
                table.code.in_(stocks[offset:offset + 200]),
                table.a_registration_date >= start,
                table.a_registration_date <= end).order_by(table.id.asc()).limit(1000).offset(page)
            rows = finance.run_query(q)
            if rows is None or rows.empty:
                break
            frames.append(rows)
            if len(rows) < 1000:
                break
            page += 1000
    if not frames:
        return []
    dividends = pd.concat(frames, ignore_index=True).groupby('code').bonus_amount_rmb.sum()
    cap = get_fundamentals(query(valuation.code, valuation.market_cap).filter(
        valuation.code.in_(list(dividends.index))), date=end).set_index('code').market_cap
    ratios = (dividends / 10000.0 / cap.where(cap > 0)).dropna().sort_values(ascending=False)

    ratios = ratios.iloc[:int(len(ratios) * 0.10)]
    return tradable_targets(context, 1, ratios[ratios > 0.03].index.tolist())


def small_scores(frame):

    frame = frame.replace([np.inf, -np.inf], np.nan).dropna()
    frame = frame[(frame > 0).all(axis=1)]
    if frame.empty:
        return pd.Series(dtype=float)
    scores = np.log(frame.min(axis=0) / frame).mul(SMALL_FACTOR_WEIGHTS, axis=1).sum(axis=1)
    return scores.sort_values(ascending=False, kind='mergesort')


def select_small_cap(context):
    stocks = stock_universe(context, 375)
    if not stocks:
        return []
    df = get_fundamentals(query(valuation.code, valuation.market_cap,
                                valuation.circulating_market_cap).filter(
        valuation.code.in_(stocks), valuation.pb_ratio > 0, indicator.inc_return > 0,
        indicator.inc_total_revenue_year_on_year > 0,
        indicator.inc_net_profit_year_on_year > 0
    ).order_by(valuation.market_cap.asc()).limit(100), date=context.previous_date)
    rows = {}
    for row in df.itertuples():

        minutes = attribute_history(row.code, 1200, '1m', ['close', 'volume'])
        daily = attribute_history(row.code, 60, '1d', ['close'])
        if len(minutes) < 1200 or len(daily) < 60:
            continue
        price = float(minutes.close.iloc[-1])
        old = float(daily.close.iloc[0])
        if old <= 0:
            continue
        rows[row.code] = [row.market_cap, row.circulating_market_cap, price,
                          float(minutes.volume.sum()), price / old]
    frame = pd.DataFrame.from_dict(rows, orient='index', columns=['mc', 'cmc', 'price', 'volume', 'return'])
    return tradable_targets(context, 3, small_scores(frame).index.tolist())


def momentum_score(prices):
    prices = np.asarray(prices, dtype=float)
    if len(prices) < 4 or not np.isfinite(prices).all() or (prices <= 0).any():
        return None
    if np.min(prices[-3:] / prices[-4:-1]) < 0.95:
        return None
    y = np.log(prices)
    x = np.arange(len(y))
    weights = np.linspace(1, 2, len(y))
    slope, intercept = np.polyfit(x, y, 1, w=weights)
    residual = np.sum(weights * (y - (slope * x + intercept)) ** 2)
    variance = np.sum(weights * (y - np.mean(y)) ** 2)
    r2 = 1 - residual / variance if variance > 0 else 0.0
    annual = np.expm1(np.clip(slope * 250, -700, 700))
    return float(annual * r2)


def rsrs_pass(history_frame, last_price):
    if len(history_frame) < 250:
        return False
    low = history_frame.low.values.astype(float)
    high = history_frame.high.values.astype(float)
    if not np.isfinite(low).all() or not np.isfinite(high).all() or np.var(low[-18:]) <= 1e-12:
        return False
    slope = np.polyfit(low[-18:], high[-18:], 1)[0]
    slopes = []
    for end in range(20, len(low) + 1):
        x, y = low[end - 20:end], high[end - 20:end]
        variance = np.var(x)
        if variance > 1e-12:
            slopes.append(float(np.mean((x - x.mean()) * (y - y.mean())) / variance))
    if not slopes:
        return False
    beta = float(np.mean(slopes) - 2 * np.std(slopes))
    if not np.isfinite(beta) or abs(beta) <= 1e-12 or slope <= beta:
        return False
    strength = (slope - beta) / abs(beta)
    return (strength > 0.15
            or (strength > 0.03 and last_price > history_frame.close.iloc[-5:].mean())
            or last_price > history_frame.close.iloc[-10:].mean())


def volume_ratio(context, code):
    past = attribute_history(code, 7, '1d', ['volume'])
    if len(past) < 7 or past.volume.mean() <= 0:
        return None
    # 修复原文件“1分钟量/日均量”的口径：使用当日截至当前的累计成交量。
    today = get_price(code, start_date=context.current_dt.date(), end_date=context.current_dt,
                      frequency='1m', fields=['volume'], panel=False)
    if today is None or today.empty:
        return None
    return float(today.volume.sum() / past.volume.mean())


def rank_etfs(context):
    current = get_current_data()
    ranked = []
    for code in ETF_POOL:
        info = get_security_info(code)
        if (info is None or info.start_date > context.previous_date
                or code in g.blocked_today or code in g.pending_exits[2]):
            continue
        data = current[code]
        if data.paused or data.last_price <= 0 or data.day_open <= 0:
            continue
        if data.last_price / data.day_open - 1 <= ETF_STOP:
            continue
        if not data.low_limit < data.last_price < data.high_limit:
            continue
        hist = attribute_history(code, 250, '1d', ['close', 'high', 'low'], skip_paused=False)
        if hist is None or len(hist) < 250 or hist.isna().any().any():
            continue
        score = momentum_score(np.append(hist.close.iloc[-ETF_DAYS:].values, data.last_price))
        if score is None or not 0 < score < ETF_SCORE_MAX:
            continue
        ratio = volume_ratio(context, code)
        if ratio is not None and ratio > 2:
            continue
        if rsrs_pass(hist, data.last_price):
            ranked.append((code, score))
    ranked.sort(key=lambda item: item[1], reverse=True)
    log.info('ETF动量候选：%s' % ranked[:5])
    return [code for code, score in ranked]


def request_exit(context, index, code):
    if code not in g.pending_exits[index]:
        g.pending_exits[index].append(code)
    g.targets[index] = [s for s in g.targets[index] if s != code]
    submit_target(context, index, code, 0)


def etf_stop_loss(context):
    current = get_current_data()
    for code in holdings(context, 2):
        data = current[code]
        if data.day_open > 0 and data.last_price / data.day_open - 1 <= ETF_STOP:
            g.blocked_today.append(code)
            request_exit(context, 2, code)


def etf_volume_check(context):
    current = get_current_data()
    for code, position in holdings(context, 2).items():
        if position.init_time.date() == context.current_dt.date():
            continue
        ratio = volume_ratio(context, code)

        if ratio is not None and ratio > 2 and current[code].last_price >= current[code].day_open:
            g.blocked_today.append(code)
            request_exit(context, 2, code)


def check_limit_open(context):
    current = get_current_data()
    for index in (1, 3):
        for code in g.high_limits[index]:
            if code in holdings(context, index) and current[code].last_price < current[code].high_limit:
                request_exit(context, index, code)



def report(context):
    total = builtins.sum(float(s.total_value) for s in context.subportfolios)
    for index in range(4):
        account = sub(context, index)
        log.info('%s | %s 资产 %.2f，现金 %.2f，占比 %.2f%%，持仓 %s' % (
            STRATEGY_NAME, NAMES[index], account.total_value, account.available_cash,
            100 * account.total_value / total if total else 0,
            list(holdings(context, index))))
