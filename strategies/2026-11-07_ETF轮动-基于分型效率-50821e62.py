# Clone from JoinQuant
# postId: 50821e62b68a1b873aee5bb6e48c5639
# backtestId: dd6812546211392624fb9e56e3f99096
# title: ETF轮动-基于分型效率

from jqdata import *
import numpy as np
import pandas as pd


def initialize(context):
    # 基准
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)

    # 滑点和手续费
    set_slippage(FixedSlippage(0.002))
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0,
            open_commission=0.0002,
            close_commission=0.0002,
            close_today_commission=0,
            min_commission=5
        ),
        type='fund'
    )
    log.set_level('system', 'error')

    # ETF池
    g.etf_pool = [
        '518880.XSHG',  # 黄金ETF
        '513100.XSHG',  # 纳指100
        '159915.XSHE',  # 创业板100
        '510880.XSHG',  # 红利ETF
    ]

    # 固定参数：不再优化
    g.m_days = 20
    g.fe_threshold = 0.35

    run_daily(trade, '9:30')


def calc_fractal_efficiency(prices):
    prices = np.asarray(prices, dtype=float)
    if len(prices) < 2 or np.any(prices <= 0):
        return 0.0

    log_prices = np.log(prices)
    net_move = abs(log_prices[-1] - log_prices[0])
    total_move = np.sum(np.abs(np.diff(log_prices)))

    if total_move <= 0:
        return 0.0
    return float(net_move / total_move)


def get_rank(etf_pool):
    score_list = []
    filtered_etfs = []

    for etf in etf_pool:
        df = attribute_history(etf, g.m_days, '1d', ['close'], skip_paused=True)
        if df is None or len(df) < g.m_days:
            continue

        prices = df['close'].values
        if np.any(prices <= 0):
            continue

        fe = calc_fractal_efficiency(prices)

        # 分形效率过滤 + 区间上涨过滤
        if fe < g.fe_threshold:
            continue
        if prices[-1] <= prices[0]:
            continue

        score_list.append(fe)
        filtered_etfs.append(etf)

    if not filtered_etfs:
        return []

    score_df = pd.DataFrame(index=filtered_etfs, data={'score': score_list})
    score_df = score_df.sort_values(by='score', ascending=False)
    return list(score_df.index)


def trade(context):
    target_num = 1
    rank_list = get_rank(g.etf_pool)

    # 没有满足条件的标的 -> 清仓
    if not rank_list:
        for etf in list(context.portfolio.positions.keys()):
            order_target_value(etf, 0)
        return

    target_list = rank_list[:target_num]

    # 先卖出非目标持仓
    hold_list = list(context.portfolio.positions.keys())
    for etf in hold_list:
        if etf not in target_list:
            order_target_value(etf, 0)

    # 再买入目标持仓
    hold_list = list(context.portfolio.positions.keys())
    current_holds = [etf for etf in hold_list if context.portfolio.positions[etf].total_amount > 0]

    if len(current_holds) < target_num:
        slots = target_num - len(current_holds)
        if slots > 0:
            value = context.portfolio.available_cash / slots
            for etf in target_list:
                if etf not in current_holds:
                    order_target_value(etf, value)