# Clone from JoinQuant
# postId: 995abb4db9469615cedb9e754fe67e39
# backtestId: 25705f085c0f4ada7e762e58957a9bcd
# title: RPS多周期趋势跟踪策略（无未来函数版）

import numpy as np
import pandas as pd
from jqdata import *

def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    log.info('RPS多周期策略（无未来函数 + 信号对齐版）')

    g.N = 20
    g.M = 5

    g.day_rps_low = 85
    g.day_rps_high = 92
    g.week_rps_threshold = 80
    g.month_rps_threshold = 75
    g.sell_rps_high = 96
    g.sell_rps_low = 80

    g.index_code = '000300.XSHG'
    g.ma_period = 20

    run_daily(before_market_open, time='09:00')
    run_daily(market_open, time='09:30')

    g.buy_list = []
    g.rps_data = {}
    g.last_calc_date = None
    g.market_trend_bull = False


# =========================
# 盘前计算（核心）
# =========================
def before_market_open(context):
    current_date = context.current_dt.date()
    end_dt = context.current_dt   # 🔥核心：绝对不能用 previous_date

    if g.last_calc_date == current_date:
        return

    log.info(f'[{current_date}] 开始计算')

    try:
        # 1️⃣ 大盘趋势
        g.market_trend_bull = check_market_trend(end_dt)

        # 2️⃣ 股票池
        stock_pool = get_stock_pool(context)
        if not stock_pool:
            g.buy_list = []
            return

        # 3️⃣ RPS（全部用 end_dt）
        day_rps = calculate_rps(stock_pool, '20d', end_dt)
        week_rps = calculate_rps(stock_pool, '20w', end_dt)
        month_rps = calculate_rps(stock_pool, '20m', end_dt)

        # 4️⃣ 斜率
        slopes = {}
        for stock in stock_pool:
            slope = get_linear_regression_slope(stock, end_dt, g.N)
            if slope is not None:
                slopes[stock] = slope

        # 5️⃣ 筛选（完全保持原逻辑）
        candidates = []
        for stock in stock_pool:
            if stock in day_rps and stock in week_rps and stock in month_rps and stock in slopes:
                d = day_rps[stock]
                w = week_rps[stock]
                m = month_rps[stock]
                s = slopes[stock]

                if (g.day_rps_low < d < g.day_rps_high and
                    w > g.week_rps_threshold and
                    m > g.month_rps_threshold):

                    candidates.append({
                        'stock': stock,
                        'day_rps': d,
                        'week_rps': w,
                        'month_rps': m,
                        'slope': s
                    })

        # 排序（保持原策略）
        candidates.sort(key=lambda x: x['slope'])
        g.buy_list = candidates[:g.M]

        g.rps_data = {
            'day': day_rps,
            'week': week_rps,
            'month': month_rps
        }

        g.last_calc_date = current_date

        log.info(f'候选:{len(candidates)} 买入:{len(g.buy_list)}')

    except Exception as e:
        log.error(f"错误: {str(e)}")
        g.buy_list = []
        g.market_trend_bull = False


# =========================
# 大盘趋势
# =========================
def check_market_trend(end_dt):
    try:
        prices = get_price(g.index_code,
                           end_date=end_dt,
                           count=g.ma_period+5,
                           frequency='1d',
                           fields=['close'])

        if len(prices) < g.ma_period:
            return False

        ma20 = prices['close'].rolling(g.ma_period).mean().iloc[-1]
        return prices['close'].iloc[-1] > ma20

    except:
        return False


# =========================
# 开盘交易
# =========================
def market_open(context):
    current_data = get_current_data()
    end_dt = context.current_dt

    # 卖出（不变）
    for position in context.portfolio.positions.values():
        stock = position.security

        if stock in g.rps_data.get('day', {}):
            rps = g.rps_data['day'][stock]
        else:
            rps = calculate_single_rps(stock, end_dt, g.N)

        if rps > g.sell_rps_high or rps < g.sell_rps_low:
            if not current_data[stock].paused:
                order_target(stock, 0)

    # 大盘过滤（不变）
    if not g.market_trend_bull:
        return

    holdings = list(context.portfolio.positions.keys())
    num_to_buy = g.M - len(holdings)

    if num_to_buy <= 0:
        return

    buy_candidates = [x for x in g.buy_list if x['stock'] not in holdings]
    target_list = buy_candidates[:num_to_buy]

    if not target_list:
        return

    cash_per = context.portfolio.available_cash / len(target_list)

    for item in target_list:
        stock = item['stock']

        if current_data[stock].paused or current_data[stock].is_st:
            continue

        price = current_data[stock].day_open
        shares = int(cash_per / price / 100) * 100

        if shares >= 100:
            order(stock, shares)


# =========================
# 股票池
# =========================
def get_stock_pool(context):
    stocks = get_index_stocks('000300.XSHG', context.current_dt)
    current_data = get_current_data()
    current_date = context.current_dt.date()

    result = []

    for stock in stocks:
        info = get_security_info(stock)
        if info is None:
            continue

        days = (current_date - info.start_date).days

        if (not current_data[stock].is_st and
            not current_data[stock].paused and
            days > 250):
            result.append(stock)

    return result


# =========================
# RPS计算（核心）
# =========================
def calculate_rps(stock_list, period, end_dt):

    if period.endswith('d'):
        days_needed = int(period[:-1]) + 10
        label = 'day'
    elif period.endswith('w'):
        days_needed = int(period[:-1]) * 5 + 20
        label = 'week'
    elif period.endswith('m'):
        days_needed = int(period[:-1]) * 22 + 30
        label = 'month'
    else:
        return {}

    prices = get_price(stock_list,
                       end_date=end_dt,
                       count=days_needed,
                       frequency='1d',
                       fields=['close'])

    returns = {}

    for stock in stock_list:
        if stock not in prices['close']:
            continue

        ps = prices['close'][stock].dropna()
        if len(ps) < 20:
            continue

        try:
            if label == 'day':
                ret = ps.iloc[-1] / ps.iloc[-int(period[:-1])] - 1

            elif label == 'week':
                wp = ps.resample('W').last()
                ret = wp.iloc[-1] / wp.iloc[-int(period[:-1])] - 1

            elif label == 'month':
                mp = ps.resample('M').last()
                ret = mp.iloc[-1] / mp.iloc[-int(period[:-1])] - 1

            returns[stock] = ret

        except:
            continue

    if not returns:
        return {}

    df = pd.DataFrame(list(returns.items()), columns=['stock', 'return'])
    df['rank'] = df['return'].rank(pct=True) * 100

    return dict(zip(df['stock'], df['rank']))


# =========================
# 单股RPS
# =========================
def calculate_single_rps(stock, end_dt, N):
    try:
        prices = get_price(stock, end_date=end_dt, count=N+5, frequency='1d', fields=['close'])
        index_prices = get_price('000300.XSHG', end_date=end_dt, count=N, frequency='1d', fields=['close'])

        if len(prices) < N or len(index_prices) < N:
            return 50

        stock_ret = prices['close'].iloc[-1] / prices['close'].iloc[-N] - 1
        index_ret = index_prices['close'].iloc[-1] / index_prices['close'].iloc[0] - 1

        if stock_ret > index_ret:
            return min(85 + (stock_ret - index_ret) * 5, 99)
        else:
            return max(50, 85 - (index_ret - stock_ret) * 5)

    except:
        return 50


# =========================
# 斜率
# =========================
def get_linear_regression_slope(stock, end_dt, N=20):
    try:
        prices = get_price(stock, end_date=end_dt, count=N+5, frequency='1d', fields=['close'])

        if len(prices) < N:
            return None

        close_prices = prices['close'].dropna().iloc[-N:]
        log_prices = np.log(close_prices.values)

        x = np.arange(len(log_prices))
        slope, _ = np.polyfit(x, log_prices, 1)

        return slope

    except:
        return None