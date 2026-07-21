# Clone from JoinQuant
# postId: e49b2079c243d68975593c0b02877dad
# backtestId: 6a7a8a173f6499ef18b6217b0e693900
# title: 小盘风帆30：从零做一个小市值基础策略研究

# -*- coding: utf-8 -*-
# 小盘风帆30
# 总市值100~200 + 股价<=30 + 双周调仓 + 等权30只
# 增加防守规则：每年1月、4月空仓
# 适配聚宽 JoinQuant

from jqdata import *
import pandas as pd
import numpy as np
import datetime


def initialize(context):
    # =========================
    # 基础设置
    # =========================
    set_benchmark('000905.XSHG')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)

    log.set_level('order', 'error')

    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0.001,
            open_commission=0.0003,
            close_commission=0.0003,
            close_today_commission=0,
            min_commission=5
        ),
        type='stock'
    )

    set_slippage(FixedSlippage(0.002), type='stock')

    # =========================
    # 策略参数
    # =========================

    # 总市值第101~200小
    g.rank_start = 100
    g.rank_end = 200

    # 等权持仓数量
    g.stock_num = 30

    # 固定最高股价过滤
    g.max_price = 30.0

    # 最短上市天数
    g.min_listed_days = 220

    # 1月和4月空仓
    g.empty_months = [1, 4]

    # 双周调仓计数器
    g.week_counter = 0

    # 双周相位：0表示第1、3、5...次周频回调调仓
    g.rebalance_offset = 0

    # 每周检查一次：
    # - 如果是1月/4月，则卖出并空仓；
    # - 如果不是空仓月份，则按双周频率调仓。
    run_weekly(rebalance, weekday=1, time='10:00')


# ============================================================
# 调仓主函数
# ============================================================

def rebalance(context):
    g.week_counter += 1

    current_month = context.current_dt.month
    current_data = get_current_data()

    # 1月和4月空仓：每周都检查并清仓，不受双周调仓节奏限制
    if current_month in g.empty_months:
        log.info('当前月份为%d月，执行空仓规则' % current_month)
        sell_all_positions(context, current_data)
        return

    # 非空仓月份，执行双周调仓
    if not is_biweekly_rebalance_week():
        log.info('双周频：本周跳过调仓，counter=%d' % g.week_counter)
        return

    log.info('双周频：本周执行调仓，counter=%d' % g.week_counter)

    end_date = context.previous_date
    target_stocks = select_stocks(context, end_date)

    if len(target_stocks) == 0:
        log.info('本次未选出目标股票，不交易')
        return

    log.info('目标股票数量：%d' % len(target_stocks))
    log.info('目标股票：%s' % target_stocks)

    sell_not_in_targets(context, target_stocks, current_data)
    buy_or_adjust_to_equal_weight(context, target_stocks, current_data)


def is_biweekly_rebalance_week():
    # week_counter=1 表示第一次周频回调
    return ((g.week_counter - 1 - g.rebalance_offset) % 2 == 0)


# ============================================================
# 选股逻辑
# ============================================================

def select_stocks(context, end_date):
    base_stocks = build_base_stock_list(context, end_date)

    if len(base_stocks) == 0:
        return []

    q = query(
        valuation.code,
        valuation.market_cap
    ).filter(
        valuation.code.in_(base_stocks),
        valuation.market_cap > 0
    ).order_by(
        valuation.market_cap.asc()
    )

    df = get_fundamentals(q, date=end_date)

    if df is None or df.empty:
        return []

    df = df.set_index('code')
    df = df.sort_values('market_cap', ascending=True)

    # 先取总市值第101~200小
    segment_df = df.iloc[g.rank_start:g.rank_end].copy()

    if segment_df.empty:
        return []

    # 获取上一交易日收盘价，避免使用未来数据
    price_map = get_last_close_map(list(segment_df.index), end_date)
    segment_df['last_close'] = segment_df.index.map(lambda x: price_map.get(x, np.nan))

    # 股价过滤：0 < price <= 30
    segment_df = segment_df[
        (segment_df['last_close'] > 0) &
        (segment_df['last_close'] <= g.max_price)
    ].copy()

    if segment_df.empty:
        return []

    # 最后再按总市值从小到大取前30只
    target_stocks = list(segment_df.index[:g.stock_num])

    return target_stocks


def build_base_stock_list(context, end_date):
    securities = get_all_securities(types=['stock'], date=end_date)

    if securities is None or securities.empty:
        return []

    end_dt = pd.to_datetime(end_date)
    current_data = get_current_data()

    stocks = []

    for stock in list(securities.index):
        try:
            # 过滤北交所常见代码段
            if stock[0] == '4' or stock[0] == '8':
                continue

            # 过滤科创板
            if stock[:2] == '68':
                continue

            # 过滤上市时间太短的股票
            start_date = pd.to_datetime(securities.loc[stock, 'start_date'])
            if (end_dt - start_date).days < g.min_listed_days:
                continue

            cd = current_data[stock]
            name = cd.name

            # 过滤停牌、ST、退市风险
            if cd.paused:
                continue
            if cd.is_st:
                continue
            if 'ST' in name or '*' in name or '退' in name:
                continue

            stocks.append(stock)

        except Exception:
            continue

    return stocks


def get_last_close_map(stock_list, end_date):
    result = {}

    if len(stock_list) == 0:
        return result

    try:
        price_df = get_price(
            stock_list,
            end_date=end_date,
            count=1,
            frequency='daily',
            fields=['close'],
            panel=False
        )
    except Exception as e:
        log.info('获取收盘价失败：%s' % str(e))
        return result

    if price_df is None or price_df.empty:
        return result

    return dict(zip(price_df['code'].values, price_df['close'].values))


# ============================================================
# 交易逻辑
# ============================================================

def sell_all_positions(context, current_data):
    for stock in list(context.portfolio.positions.keys()):
        if can_sell(stock, context, current_data):
            amount = context.portfolio.positions[stock].closeable_amount
            if amount > 0:
                order(stock, -amount)
                log.info('空仓月份卖出：%s，数量=%d' % (stock, amount))


def sell_not_in_targets(context, target_stocks, current_data):
    target_set = set(target_stocks)

    for stock in list(context.portfolio.positions.keys()):
        if stock in target_set:
            continue

        if not can_sell(stock, context, current_data):
            continue

        amount = context.portfolio.positions[stock].closeable_amount

        if amount > 0:
            order(stock, -amount)
            log.info('卖出非目标股票：%s，数量=%d' % (stock, amount))


def buy_or_adjust_to_equal_weight(context, target_stocks, current_data):
    if len(target_stocks) == 0:
        return

    target_value = context.portfolio.total_value / float(len(target_stocks))

    # 先降仓：把目标内明显超配的股票降到接近等权
    for stock in target_stocks:
        if stock not in context.portfolio.positions:
            continue

        if not can_sell(stock, context, current_data):
            continue

        price = get_current_price(stock, current_data)
        if price <= 0:
            continue

        position = context.portfolio.positions[stock]
        current_value = position.total_amount * price

        over_value = current_value - target_value

        # 超过一手才调整，避免碎调仓
        if over_value >= price * 100:
            sell_shares = int(over_value / price / 100) * 100
            sell_shares = min(sell_shares, position.closeable_amount)

            if sell_shares >= 100:
                order(stock, -sell_shares)
                log.info('等权降仓：%s，数量=%d' % (stock, sell_shares))

    # 再买入/补仓
    cash = context.portfolio.available_cash

    for stock in target_stocks:
        if not can_buy(stock, current_data):
            continue

        price = get_current_price(stock, current_data)
        if price <= 0:
            continue

        current_value = 0.0

        if stock in context.portfolio.positions:
            current_value = context.portfolio.positions[stock].total_amount * price

        need_value = target_value - current_value

        if need_value <= 0:
            continue

        buy_value = min(need_value, cash)

        # 不使用 min_buy_value，只保留100股整数手
        if buy_value < price * 100:
            continue

        shares = int(buy_value / price / 100) * 100
        max_cash_shares = int(cash / price / 100) * 100
        shares = min(shares, max_cash_shares)

        if shares < 100:
            continue

        order(stock, shares)

        trade_value = shares * price
        cash -= trade_value

        log.info('等权买入/补仓：%s，数量=%d，金额约=%.2f' % (
            stock,
            shares,
            trade_value
        ))


# ============================================================
# 买卖可行性判断
# ============================================================

def can_buy(stock, current_data):
    try:
        cd = current_data[stock]

        if cd.paused:
            return False

        if cd.is_st:
            return False

        name = cd.name
        if 'ST' in name or '*' in name or '退' in name:
            return False

        price = cd.last_price

        if price is None or price <= 0:
            return False

        # 涨停不买
        if price >= cd.high_limit * 0.999:
            return False

        return True

    except Exception:
        return False


def can_sell(stock, context, current_data):
    try:
        if stock not in context.portfolio.positions:
            return False

        position = context.portfolio.positions[stock]

        if position.closeable_amount <= 0:
            return False

        cd = current_data[stock]

        if cd.paused:
            return False

        price = cd.last_price

        if price is None or price <= 0:
            return False

        # 跌停不卖
        if price <= cd.low_limit * 1.001:
            return False

        return True

    except Exception:
        return False


def get_current_price(stock, current_data):
    try:
        price = current_data[stock].last_price
        if price is None:
            return 0.0
        return float(price)
    except Exception:
        return 0.0