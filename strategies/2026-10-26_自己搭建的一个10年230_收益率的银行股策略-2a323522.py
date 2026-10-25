# Clone from JoinQuant
# postId: 2a3235229fdfd62a917c78a5d8236c15
# backtestId: 1c770f0f1cb42e87e17b574b39aaba59
# title: 自己搭建的一个10年230%收益率的银行股策略

# 聚宽策略：银行股精简轮动增强版（基于139%收益策略优化）
# 核心：PB + 股息率 + 动量（权重30/30/40），布林择时，250日线动态仓位
# 止损放宽至-12%，持仓3只分散，每周固定调仓

from jqdata import finance
import datetime
import pandas as pd

def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)

    set_order_cost(OrderCost(open_tax=0, close_tax=0.0005,
                             open_commission=0.000095, close_commission=0.000095,
                             close_today_commission=0, min_commission=1), type='stock')

    g.stocks = ['601398.XSHG', '601939.XSHG', '601288.XSHG', '601988.XSHG', '600036.XSHG']
    g.max_holdings = 3          # 分散持仓
    g.min_holdings = 2
    g.buy_prices = {}

    # 每周五调仓
    run_weekly(rebalance, weekday=5, time='close')


def calc_dividend_yield(stock, context):
    """计算TTM股息率"""
    start_date = context.current_dt - datetime.timedelta(days=365)
    q = query(
        finance.STK_XR_XD.code,
        finance.STK_XR_XD.bonus_ratio_rmb
    ).filter(
        finance.STK_XR_XD.code == stock,
        finance.STK_XR_XD.a_bonus_date >= start_date
    )
    df = finance.run_query(q)
    if df.empty:
        return 0.0
    total_div = df['bonus_ratio_rmb'].sum() / 10.0
    if total_div <= 0:
        return 0.0
    df_price = get_price(stock, end_date=context.current_dt, frequency='daily',
                         fields=['close'], count=1, skip_paused=True, fq=None)
    if len(df_price) == 0:
        return 0.0
    price = df_price['close'].iloc[-1]
    if price <= 0:
        return 0.0
    return total_div / price


def get_ma250(stock, context):
    df = get_price(stock, end_date=context.current_dt, frequency='daily',
                   fields=['close'], count=260, skip_paused=True)
    if len(df) >= 250:
        return df['close'].rolling(250).mean().iloc[-1]
    return None


def get_bollinger(stock, context, period=20, num_std=2):
    df = get_price(stock, end_date=context.current_dt, frequency='daily',
                   fields=['close'], count=period+5, skip_paused=True)
    if len(df) < period:
        return None
    close = df['close']
    ma = close.rolling(period).mean()
    std = close.rolling(period).std()
    return {
        'ma': ma.iloc[-1],
        'close': close.iloc[-1]
    }


def rebalance(context):
    # ----- 获取基本面数据（PB）-----
    df_fund = get_fundamentals(
        query(
            valuation.code,
            valuation.pb_ratio
        ).filter(
            valuation.code.in_(g.stocks)
        )
    )
    if len(df_fund) == 0:
        return

    # ----- 计算得分 -----
    scores = {}
    # 价格数据
    price_data = {}
    for stock in g.stocks:
        df = get_price(stock, end_date=context.current_dt, frequency='daily',
                       fields=['close'], count=30, skip_paused=True)
        if len(df) >= 20:
            price_data[stock] = df['close']

    for _, row in df_fund.iterrows():
        code = row['code']
        pb = row['pb_ratio']
        if pb is None or pb <= 0:
            continue

        # 股息率
        dy = calc_dividend_yield(code, context)
        if dy <= 0:
            continue

        # 因子1：低PB
        pb_score = 1 / pb
        # 因子2：高股息
        dy_score = dy * 100
        # 因子3：近一月动量（收益率越高分越高）
        mom_score = 0
        if code in price_data and len(price_data[code]) >= 20:
            ret_1m = (price_data[code].iloc[-1] - price_data[code].iloc[-20]) / price_data[code].iloc[-20]
            mom_score = max(0, (ret_1m + 0.05) * 10)  # 将涨幅映射为正分

        # 综合评分（动量权重提高）
        scores[code] = 0.30 * pb_score + 0.30 * dy_score + 0.40 * mom_score

    if not scores:
        return

    # ----- 择时：股价低于布林中轨的股票才纳入候选-----
    eligible_stocks = []
    for stock in g.stocks:
        if stock not in scores:
            continue
        bb = get_bollinger(stock, context)
        if bb is None:
            continue
        if bb['close'] <= bb['ma']:
            eligible_stocks.append(stock)

    # 若没有符合条件的股票，空仓时放宽条件（允许略高于中轨5%）
    if not eligible_stocks:
        has_position = any(
            context.portfolio.positions[s].total_amount > 0
            for s in g.stocks if context.portfolio.positions.get(s)
        )
        if not has_position:
            sorted_stocks = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
            for s in sorted_stocks[:3]:
                bb = get_bollinger(s, context)
                if bb and (bb['close'] - bb['ma']) / bb['ma'] < 0.05:
                    eligible_stocks.append(s)
        else:
            # 有持仓但无新标的，保留持仓不调仓
            return

    # 按得分排序
    eligible_stocks.sort(key=lambda x: scores.get(x, 0), reverse=True)

    # ----- 动态仓位：250日线决定仓位高低 -----
    ma250 = get_ma250('601398.XSHG', context)
    current_price_icbc = get_bollinger('601398.XSHG', context)['close'] if get_bollinger('601398.XSHG', context) else None
    if ma250 is not None and current_price_icbc is not None and current_price_icbc < ma250:
        target_position_ratio = 0.5
    else:
        target_position_ratio = 1.0

    total_value = context.portfolio.total_value
    target_per_stock_value = (total_value * target_position_ratio) / g.min_holdings

    # ----- 止损：-12% -----
    for stock in g.stocks:
        pos = context.portfolio.positions.get(stock)
        if pos and pos.total_amount > 0:
            current_price = get_bollinger(stock, context)['close'] if get_bollinger(stock, context) else None
            if current_price is not None:
                loss_pct = (current_price - pos.avg_cost) / pos.avg_cost
                if loss_pct < -0.12:
                    order_target(stock, 0)

    # ----- 确定目标持仓 -----
    current_holdings = [
        s for s in g.stocks
        if context.portfolio.positions.get(s) and context.portfolio.positions[s].total_amount > 0
    ]

    target_holdings = eligible_stocks[:g.max_holdings]
    # 如果目标持仓少于最小持有数，补充候选
    if len(target_holdings) < g.min_holdings:
        for s in eligible_stocks:
            if s not in target_holdings:
                target_holdings.append(s)
                if len(target_holdings) >= g.min_holdings:
                    break
        # 若仍不足，保留当前持仓
        if len(target_holdings) < g.min_holdings and current_holdings:
            target_holdings = current_holdings[:g.min_holdings]

    # ----- 调仓 -----
    for stock in current_holdings:
        if stock not in target_holdings:
            order_target(stock, 0)

    for stock in target_holdings:
        max_single = total_value * 0.4
        target_value = min(target_per_stock_value, max_single)
        order_target_value(stock, target_value)