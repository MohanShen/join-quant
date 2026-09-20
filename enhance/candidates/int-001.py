# Type-level integration candidate — 全A-H-low
# expId: int-001
# legs (equal weight, isolated books):
#   A  strategies/2026-05-12_网格交易策略-年化30_-网格大法好_熊市不用跑-598050b9.py  [网格]      objective 0.1411  sharpe 1.19
#   B  strategies/2026-07-05_低换手红利策略-93379f98.py                              [红利低频]  objective 0.1365  sharpe 1.46
# component-scan (ex-post, cost-free, daily-rebalanced UPPER BOUND — not a result):
#   corr 0.2614 over 484 shared days, 50/50 blend score 0.1798 sharpe 1.56, uplift +0.0359
#
# Why sub-portfolios rather than one shared book: the grid leg buys dips out of whatever cash
# is on hand, so a single pool would let it starve the dividend leg at its 25-day rebalance.
# That is a cash-contention artefact, not the 50/50 blend being tested, and it would make the
# measurement uninterpretable. set_subportfolios gives each leg its own cash.
#
# Frozen epoch-5 cost block below is reproduced verbatim from harness-config pythonLiterals().
# Both legs' own set_slippage / set_order_cost / set_benchmark calls are REMOVED — the bench
# is the harness's, not the authors'.

import numpy
import pandas as pd
from pandas import Series
from jqdata import *
from jqdata import finance
import numpy as np
from datetime import timedelta

A = 0   # pindex — 网格
B = 1   # pindex — 低换手红利


def initialize(context):
    # ---- frozen harness block (epoch 5) ----
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_option('order_volume_ratio', 0.05)
    set_benchmark('000300.XSHG')
    set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
    try:
        # kept on ONE line so it matches harness-config's literal verbatim (--verify greps it)
        set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0, min_commission=5), type='fund')
    except NameError:
        pass   # set_order_cost is not bound at module scope in every JQ runtime
    set_slippage(FixedSlippage(0))
    log.set_level('order', 'error')

    # ---- equal weight, isolated books ----
    half = context.portfolio.starting_cash * 0.5
    set_subportfolios([
        SubPortfolioConfig(cash=half, type='stock'),
        SubPortfolioConfig(cash=half, type='stock'),
    ])

    # ---- leg A state (网格) ----
    g.count = 30
    g.cash = half                      # the leg sizes its grid unit off this
    g.buy_stock = []
    g.initial_price = {}
    g.month = context.current_dt.month
    run_monthly(select_stock_by_industry, 1, 'open')

    # ---- leg B state (低换手红利) ----
    g.stock_num = 10
    g.rebalance_days = 25
    g.day_count = 0
    g.turnover_window = 20
    run_daily(check_rebalance, time='14:50')


# ════════════════════════ LEG A — 网格 ════════════════════════

def select_stock_by_industry(context):
    month = context.current_dt.month
    if month % 3 != g.month % 3:
        return
    industry_list = ['I64', 'I65']
    stocks = []
    for industry_code in industry_list:
        stock_set = get_industry_stocks(industry_code)
        q = query(
            valuation.code, valuation.market_cap, valuation.pe_ratio
        ).filter(
            valuation.code.in_(stock_set),
            valuation.pe_ratio < 50
        ).order_by(
            valuation.market_cap.desc()
        ).limit(g.count)
        df = get_fundamentals(q)
        stock_set = list(df['code'])
        variance_list = []
        for stock in stock_set:
            variance_list.append(variance(stock))
        s1 = Series(variance_list, index=stock_set).rank()
        stocks = list(s1[s1 < 6].index)
        for stock in stocks:
            g.buy_stock.append(stock)
            g.initial_price[stock] = 0
    reset_position(context)
    return None


def reset_position(context):
    for stock in list(context.subportfolios[A].long_positions.keys()):
        if stock not in g.buy_stock:
            order_target_value(stock, 0, pindex=A)
    return None


def variance(security_code):
    hist1 = attribute_history(security_code, 180, '1d', 'close', df=False)
    narray = numpy.array(hist1['close'])
    sum1 = narray.sum()
    narray2 = narray * narray
    sum2 = narray2.sum()
    N = len(hist1['close'])
    mean = sum1 / N
    var = sum2 / N - mean ** 2
    return var


def security_return(days, security_code):
    hist1 = attribute_history(security_code, days + 1, '1d', 'close', df=False)
    return (hist1['close'][-1] - hist1['close'][0]) / hist1['close'][0]


def conduct_nday_stoploss(context, security_code, days, bench):
    if security_return(days, security_code) <= bench:
        for stock in g.buy_stock:
            order_target_value(stock, 0, pindex=A)
        return True
    return False


def security_accumulate_return(context, data, stock):
    positions = context.subportfolios[A].long_positions
    if stock not in positions:
        return None
    current_price = data[stock].price
    cost = positions[stock].avg_cost
    if cost != 0:
        return (current_price - cost) / cost
    return None


def conduct_accumulate_stoploss(context, data, stock, bench):
    r = security_accumulate_return(context, data, stock)
    if r is not None and r < bench:
        order_target_value(stock, 0, pindex=A)
        return True
    return False


def is_fall_nday(days, stock):
    his = history(days + 1, '1d', 'close', [stock], df=False)
    cnt = 0
    for i in range(days):
        daily_returns = (his[stock][i + 1] - his[stock][i]) / his[stock][i]
        if daily_returns < 0:
            cnt += 1
    return cnt == 5


def compare_current_nmoveavg(data, stock, days, multi):
    return data[stock].price > multi * data[stock].mavg(days)


def initial_price(context, data, stock):
    if g.initial_price[stock] == 0:
        g.initial_price[stock] = data[stock].price
    return None


def setup_position(context, data, stock, bench, status):
    bottom_price = g.initial_price[stock]
    if bottom_price == 0:
        return
    sub = context.subportfolios[A]
    cash = sub.available_cash
    current_price = data[stock].price
    positions = sub.long_positions
    amount = positions[stock].total_amount if stock in positions else 0
    current_value = current_price * amount
    unit_value = g.cash / 40
    returns = (current_price - bottom_price) / bottom_price
    if status == 'short':
        if returns > bench and current_value > 6 * unit_value:
            order_target_value(stock, 6 * unit_value, pindex=A)
        if returns > 2 * bench and current_value > 3 * unit_value:
            order_target_value(stock, 3 * unit_value, pindex=A)
        if returns > 3 * bench and current_value > 1 * unit_value:
            order_target_value(stock, 1 * unit_value, pindex=A)
        if returns > 4 * bench and current_value > 0:
            order_target_value(stock, 0, pindex=A)
    if status == 'long' and cash > 0:
        if returns < bench and current_value < 4 * unit_value:
            order_target_value(stock, 4 * unit_value, pindex=A)
        if returns < 2 * bench and current_value < 7 * unit_value:
            order_target_value(stock, 7 * unit_value, pindex=A)
        if returns < 3 * bench and current_value < 9 * unit_value:
            order_target_value(stock, 9 * unit_value, pindex=A)
        if returns < 4 * bench and current_value < 10 * unit_value:
            order_target_value(stock, 10 * unit_value, pindex=A)
    return True


def handle_data(context, data):
    if conduct_nday_stoploss(context, '000001.XSHG', 2, -0.03):
        return
    for stock in g.buy_stock:
        if conduct_accumulate_stoploss(context, data, stock, -0.2):
            return
        if is_fall_nday(5, stock):
            return
        if compare_current_nmoveavg(data, stock, 5, 1.5) \
           or compare_current_nmoveavg(data, stock, 10, 1.5):
            return
        initial_price(context, data, stock)
        setup_position(context, data, stock, -0.08, 'long')
        setup_position(context, data, stock, 0.15, 'short')


# ════════════════════════ LEG B — 低换手红利 ════════════════════════

def check_rebalance(context):
    g.day_count += 1
    if g.day_count % g.rebalance_days == 1 or g.day_count == 1:
        rebalance_b(context)


def get_stock_pool(context):
    curr_date = context.current_dt.date()
    all_stocks = get_all_securities(['stock'], date=curr_date)
    all_stocks = all_stocks[~all_stocks.index.str.startswith('688')]
    stock_list = list(all_stocks.index)
    current_data = get_current_data()
    return [s for s in stock_list if not current_data[s].paused]


def get_dividend_yield_ttm(stock_list, date):
    start_date = date - timedelta(days=365)
    q = query(
        finance.STK_XR_XD.code,
        finance.STK_XR_XD.bonus_ratio_rmb,
        finance.STK_XR_XD.a_registration_date,
        finance.STK_XR_XD.plan_progress
    ).filter(
        finance.STK_XR_XD.code.in_(stock_list),
        finance.STK_XR_XD.a_registration_date >= str(start_date),
        finance.STK_XR_XD.a_registration_date <= str(date),
        finance.STK_XR_XD.plan_progress == '实施方案'
    )
    df_all = []
    offset = 0
    while True:
        df_batch = finance.run_query(q.offset(offset).limit(4000))
        if df_batch is None or len(df_batch) == 0:
            break
        df_all.append(df_batch)
        if len(df_batch) < 4000:
            break
        offset += 4000
    if not df_all:
        return pd.Series(dtype=float)
    df_div = pd.concat(df_all, ignore_index=True)
    df_div = df_div[df_div['bonus_ratio_rmb'].notna() & (df_div['bonus_ratio_rmb'] > 0)]
    if len(df_div) == 0:
        return pd.Series(dtype=float)
    df_div['dps'] = df_div['bonus_ratio_rmb'] / 10.0
    dps_ttm = df_div.groupby('code')['dps'].sum()
    price_stocks = list(dps_ttm.index)
    price_df = get_price(price_stocks, end_date=date, frequency='daily',
                         fields=['close'], count=1, panel=False)
    price_dict = dict(zip(price_df['code'], price_df['close']))
    dy_dict = {}
    for stock in price_stocks:
        if stock in price_dict and price_dict[stock] > 0:
            dy_dict[stock] = dps_ttm[stock] / price_dict[stock]
    return pd.Series(dy_dict)


def calc_factor_rank(context, stock_list):
    prev_date = context.previous_date
    dy_series = get_dividend_yield_ttm(stock_list, prev_date)
    if len(dy_series) == 0:
        return []
    turnover_dict = {}
    batch_size = 500
    for i in range(0, len(stock_list), batch_size):
        batch = stock_list[i:i + batch_size]
        df_val = get_valuation(batch, end_date=prev_date, count=g.turnover_window,
                               fields=['code', 'turnover_ratio'])
        if df_val is not None and len(df_val) > 0:
            turnover_dict.update(df_val.groupby('code')['turnover_ratio'].mean().to_dict())
    turnover_series = pd.Series(turnover_dict)
    df = pd.DataFrame({'dy_ttm': dy_series, 'turnover_20d': turnover_series}).dropna()
    df = df[df['dy_ttm'] > 0]
    if len(df) == 0:
        return []
    df['dy_rank'] = df['dy_ttm'].rank(ascending=False, method='min')
    df['turnover_rank'] = df['turnover_20d'].rank(ascending=True, method='min')
    df['total_rank'] = df['dy_rank'] * 3 + df['turnover_rank'] * 3
    df = df.sort_values('total_rank', ascending=True)
    return list(df.index[:g.stock_num])


def rebalance_b(context):
    stock_list = get_stock_pool(context)
    target_list = calc_factor_rank(context, stock_list)
    if len(target_list) == 0:
        return
    current_data = get_current_data()
    sub = context.subportfolios[B]
    for stock in list(sub.long_positions.keys()):
        if stock not in target_list and not current_data[stock].paused:
            order_target_value(stock, 0, pindex=B)
    target_value = sub.total_value / g.stock_num
    for stock in target_list:
        if not current_data[stock].paused:
            order_target_value(stock, target_value, pindex=B)
