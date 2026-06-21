# Clone from JoinQuant
# postId: 0aa4028d0fc64587d42050232f2d158e
# backtestId: 776b8146bfe0da17838c3886cbf193f6
# title: 追电ETF动量轮动 —10年60多倍收益

"""
ETF 动量轮动策略（简化版 + 止损）
=================================
- 加权线性回归动量打分，持有动量最强的 ETF
- 固定比例止损
"""

import numpy as np
import pandas as pd
import math


def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_slippage(FixedSlippage(0.001))
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0,
        open_commission=0.0002, close_commission=0.0002,
        close_today_commission=0, min_commission=5
    ), type='fund')
    log.set_level('system', 'error')

    g.etf_pool = [
        "513100.XSHG",  # 纳指ETF
        "513520.XSHG",  # 日经ETF
        "513030.XSHG",  # 德国ETF
        "518880.XSHG",  # 黄金ETF
        "161226.XSHE",  # 白银LOF
        "159985.XSHE",  # 豆粕ETF
        "511090.XSHG",  # 30年国债ETF
        "159525.XSHE",  # 红利低波
        "513130.XSHG",  # 恒生科技
        "159915.XSHE",  # 创业板100
        "159628.XSHE",  # 国证2000
    ]

    g.m_days    = 25       # 动量计算天数
    g.max_hold  = 1        # 最大持仓数
    g.stop_loss = -0.10    # 止损线（-10%）
    
    g.entry = {}           # {etf: 买入价}

    run_daily(trade, '9:30')


def momentum_score(etf):
    """加权线性回归动量打分"""
    df = attribute_history(etf, g.m_days, '1d', ['close'])
    prices = np.append(df['close'].values, get_current_data()[etf].last_price)
    y = np.log(prices)
    n = len(y)
    x = np.arange(n)
    w = np.linspace(1, 2, n)

    slope, intercept = np.polyfit(x, y, 1, w=w)
    annual_ret = math.exp(slope * 250) - 1
    resid = y - (slope * x + intercept)
    r2 = 1 - np.sum(w * resid ** 2) / np.sum(w * (y - y.mean()) ** 2)

    return annual_ret * r2


def rank(context):
    """排序：动量>0且≤6的ETF"""
    scores = {etf: momentum_score(etf) for etf in g.etf_pool}
    df = pd.DataFrame({'score': scores}).sort_values('score', ascending=False)
    log.info('\n' + str(df))
    # 只保留合理区间：正动量，但不极端
    df = df[(df['score'] > 0) & (df['score'] <= 4.8)]
    return list(df.index)


def stop_loss_check(context):
    """止损检查"""
    for etf, pos in list(context.portfolio.positions.items()):
        if pos.total_amount == 0:
            continue
        entry = g.entry.get(etf)
        if entry is None:
            continue
        now = get_current_data()[etf].last_price
        pnl = (now - entry) / entry
        if pnl <= g.stop_loss:
            order_target_value(etf, 0)
            g.entry.pop(etf, None)
            log.info(f'⚠️ 止损 {etf} | 成本:{entry:.3f} 现价:{now:.3f} 亏损:{pnl*100:.1f}%')


def trade(context):
    stop_loss_check(context)

    target = rank(context)[:g.max_hold]

    # 卖出不在目标的
    for etf in list(context.portfolio.positions.keys()):
        if etf not in target and context.portfolio.positions[etf].total_amount > 0:
            order_target_value(etf, 0)
            g.entry.pop(etf, None)
            log.info(f'卖出 {etf}')

    # 买入目标
    held = sum(1 for p in context.portfolio.positions.values() if p.total_amount > 0)
    if held < g.max_hold and target:
        cash = context.portfolio.available_cash / (g.max_hold - held)
        for etf in target:
            if context.portfolio.positions[etf].total_amount == 0:
                order_target_value(etf, cash)
                g.entry[etf] = get_current_data()[etf].last_price
                log.info(f'买入 {etf}')
