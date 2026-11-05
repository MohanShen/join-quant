# Clone from JoinQuant
# postId: 8905082d6c50da0e844e2357a47d87fe
# backtestId: 91c21ebd343bd090b86e78a6db8074e6
# title: 小市值策略，现在不断建楼，欢迎大家留言，回测结果附上。

from jqdata import *
import numpy as np
import pandas as pd

# ======================================================================
# 低开反弹原版：小市值500只，低开破昨低买5只次日卖
# 已验证：年化45.52% 夏普2.383 回撤23.93%
# ======================================================================
def initialize(context):
    g.choice = 500
    g.stock_num = 2
    g.stock_pool = []

    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_benchmark('399303.XSHE')
    set_slippage(FixedSlippage(0.02))
    set_order_cost(OrderCost(close_tax=0.0005, open_commission=0.0000854,
                             close_commission=0.0000854, min_commission=5), type='stock')

    run_daily(my_trade, time='9:30', reference_security='399303.XSHE')


def before_trading_start(context):
    df = get_fundamentals(query(valuation.code, valuation.market_cap
        ).order_by(valuation.market_cap.asc()).limit(g.choice))
    g.stock_pool = list(df['code'])
    cdata = get_current_data()
    g.stock_pool = [s for s in g.stock_pool if not (
        cdata[s].paused or cdata[s].is_st or
        'ST' in cdata[s].name or '*' in cdata[s].name or
        '退' in cdata[s].name or s.startswith('688') or
        s.startswith('8') or s.startswith('4'))]


def my_trade(context):
    # 卖昨天买的
    for s in list(context.portfolio.positions.keys()):
        if context.portfolio.positions[s].closeable_amount > 0:
            order_target(s, 0)

    cdata = get_current_data()
    held = set(context.portfolio.positions.keys())
    buy_list = []
    for s in g.stock_pool:
        if len(buy_list) >= g.stock_num:
            break
        if s in held:
            continue
        df = attribute_history(s, 5, '1d', ('close', 'low', 'high', 'paused'), False)
        if df['paused'].max() == 0:
            today_open = cdata[s].day_open
            prev_close = df['close'][-1]
            prev_low = df['low'][-1]
            chg = (today_open - prev_close) / prev_close * 100
            if today_open < prev_low and -8 < chg < -1:
                low = min(df['low'].values[-4:])
                high = max(df['high'].values[-4:])
                if (high - low) / low * 100 <= 20:
                    ema5 = df['close'].ewm(span=5).mean()
                    if prev_close > ema5.values[-1]:
                        buy_list.append(s)

    if buy_list:
        per = context.portfolio.available_cash / g.stock_num
        for s in buy_list:
            order_target_value(s, per)
        log.info(f"买入{len(buy_list)}只")
