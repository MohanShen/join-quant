# Clone from JoinQuant
# postId: 0717871e0a1d680573c8d349c1647642
# backtestId: 4560c0c5f06a2a97ba634aaf68586a74
# title: 全自动拟合神器 别再当拟合怪的奴隶了 我要让人人都能拟合

from jqdata import *
import numpy as np
import math

def initialize(context):
    set_benchmark('510300.XSHG')
    set_option('use_real_price', True)

    # 直接从 g 对象读取 extras 注入的参数（使用 getattr 提供默认值更安全）
    g.lookback_days = getattr(g, 'lookback_days', 20)
    g.holdings_num = getattr(g, 'holdings_num', 2)
    g.stop_loss_threshold = getattr(g, 'stop_loss_threshold', 0.95)

    log.info(f"最终参数: lookback_days={g.lookback_days}, holdings_num={g.holdings_num}, stop_loss_threshold={g.stop_loss_threshold}")

    # ETF 池
    g.etf_pool = ['510300.XSHG', '510500.XSHG', '159915.XSHE', '159949.XSHE']

    # 每日交易
    run_daily(trade, time='10:00')


def calc_momentum(code, lookback_days):
    prices = attribute_history(code, lookback_days + 1, '1d', ['close'])['close']
    price_series = prices.values
    if len(price_series) < lookback_days:
        return None
    y = np.log(price_series)
    x = np.arange(len(y))
    slope, intercept = np.polyfit(x, y, 1)
    annual_return = math.exp(slope * 250) - 1
    y_fit = slope * x + intercept
    ss_res = np.sum((y - y_fit)**2)
    ss_tot = np.sum((y - np.mean(y))**2)
    r2 = 1 - ss_res / ss_tot if ss_tot != 0 else 0
    return annual_return * r2


def trade(context):
    current_data = get_current_data()
    scores = []

    for etf in g.etf_pool:
        score = calc_momentum(etf, g.lookback_days)
        if score is not None:
            scores.append((etf, score))

    if not scores:
        return

    scores.sort(key=lambda x: x[1], reverse=True)
    target = [etf for etf, _ in scores[:g.holdings_num]]

    for position in list(context.portfolio.positions.keys()):
        if position not in target:
            order_target_value(position, 0)
            log.info(f"{context.current_dt} 卖出: {position}")

    cash = context.portfolio.available_cash
    if len(target) > 0:
        alloc = cash / len(target)
        for etf in target:
            order_value(etf, alloc)
            log.info(f"{context.current_dt} 买入: {etf} 金额: {alloc:.2f}")

    for etf in target:
        pos = context.portfolio.positions.get(etf, None)
        if pos and pos.avg_cost > 0:
            current_price = current_data[etf].last_price
            if current_price < pos.avg_cost * g.stop_loss_threshold:
                order_target_value(etf, 0)
                log.info(f"{context.current_dt} 止损卖出: {etf} 成本: {pos.avg_cost:.2f} 当前价: {current_price:.2f}")

    record(cash=context.portfolio.available_cash,
           total_value=context.portfolio.total_value)