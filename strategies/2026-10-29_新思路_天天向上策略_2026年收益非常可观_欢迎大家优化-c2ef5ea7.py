# Clone from JoinQuant
# postId: c2ef5ea72d478dc5b85ad0c8b904b411
# backtestId: 71965ee6fd90ce4b213a58d9edc27f8e
# title: 新思路！天天向上策略！2026年收益非常可观，欢迎大家优化！

import pandas as pd
import numpy as np

def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_order_cost(OrderCost(
        close_tax=0.001,
        open_commission=0.0003,
        close_commission=0.0003,
        min_commission=5
    ), type='stock')

    # ===== 可配置参数 =====
    g.touch_threshold = 0.01   # T-2日最低价与20日线的最大距离（1%以内算"碰到"）
    g.stop_loss_pct  = -0.05   # 止损线
    g.lookback_days  = 25      # 条件1：过去N个交易日不跌破20日线
    g.pending_buy    = None

    run_daily(sell_and_select, time='09:31')
    run_daily(buy_target,      time='09:35')
    run_daily(monitor_stop_loss, time='every_bar')


# ========== 工具函数 ==========

def get_holding(context):
    positions = list(context.portfolio.positions.keys())
    return positions[0] if positions else None


def filter_stock_pool(context):
    stocks = list(get_all_securities(['stock']).index)
    cd = get_current_data()
    return [s for s in stocks
            if not cd[s].paused
            and not cd[s].is_st
            and '退' not in cd[s].name]


# ========== 核心选股（向量化） ==========

def select_stock(context):
    stock_pool = filter_stock_pool(context)
    if not stock_pool:
        return None

    # 取130个交易日（120日线需前置120天，多10天余量）
    df = get_price(stock_pool, end_date=context.previous_date, count=130,
                   fields=['close', 'low'], panel=False, fq='pre')
    if df is None or len(df) == 0:
        return None

    # 计算 MA5 / MA10 / MA20 / MA60 / MA120
    df['ma5']   = df.groupby('code')['close'].transform(lambda x: x.rolling(5).mean())
    df['ma10']  = df.groupby('code')['close'].transform(lambda x: x.rolling(10).mean())
    df['ma20']  = df.groupby('code')['close'].transform(lambda x: x.rolling(20).mean())
    df['ma60']  = df.groupby('code')['close'].transform(lambda x: x.rolling(60).mean())
    df['ma120'] = df.groupby('code')['close'].transform(lambda x: x.rolling(120).mean())

    # 按日期倒序编号：rn=1→T-1日, rn=2→T-2日, ...
    df['rn'] = df.groupby('code')['time'].rank(
        ascending=False, method='first'
    ).astype(int)

    # pivot 宽表：index=股票, columns=rn
    close_pivot = df.pivot(index='code', columns='rn', values='close')
    low_pivot   = df.pivot(index='code', columns='rn', values='low')
    ma5_pivot   = df.pivot(index='code', columns='rn', values='ma5')
    ma10_pivot  = df.pivot(index='code', columns='rn', values='ma10')
    ma20_pivot  = df.pivot(index='code', columns='rn', values='ma20')
    ma60_pivot  = df.pivot(index='code', columns='rn', values='ma60')
    ma120_pivot = df.pivot(index='code', columns='rn', values='ma120')

    # ---------- 条件3：T-1日收涨 ----------
    cond3 = close_pivot[1] > close_pivot[2]

    # ---------- 条件2：T-2日（rn=2）盘中最低价触碰20日线且不跌破 ----------
    t2_low  = low_pivot[2]
    t2_ma20 = ma20_pivot[2]
    cond2 = (t2_low >= t2_ma20) & \
            ((t2_low - t2_ma20) / t2_ma20 <= g.touch_threshold) & \
            t2_ma20.notna()

    # ---------- 条件1：过去20个交易日（rn=2~21）每天盘中最低价 >= 当日20日线 ----------
    rn_cols = list(range(2, 2 + g.lookback_days))
    rn_cols = [c for c in rn_cols if c in low_pivot.columns]
    period_low  = low_pivot[rn_cols]
    period_ma20 = ma20_pivot[rn_cols]
    cond1 = (period_low >= period_ma20).all(axis=1) & \
            period_ma20.notna().all(axis=1)

    # ---------- 条件4：5/10/20/60/120日线在T-1日同步向上 ----------
    cond_ma_up = (ma5_pivot[1]   > ma5_pivot[2])   & \
                 (ma10_pivot[1]  > ma10_pivot[2])  & \
                 (ma20_pivot[1]  > ma20_pivot[2])  & \
                 (ma60_pivot[1]  > ma60_pivot[2])  & \
                 (ma120_pivot[1] > ma120_pivot[2]) & \
                 ma5_pivot[1].notna() & ma10_pivot[1].notna() & \
                 ma20_pivot[1].notna() & ma60_pivot[1].notna() & ma120_pivot[1].notna()

    # ---------- 合并全部条件 ----------
    all_cond = cond1 & cond2 & cond3 & cond_ma_up
    candidates = all_cond[all_cond].index.tolist()

    if not candidates:
        return None

    # 选总市值最小的
    q = query(valuation.code, valuation.market_cap).filter(
        valuation.code.in_(candidates)
    ).order_by(valuation.market_cap.asc())
    val_df = get_fundamentals(q)
    return val_df.iloc[0]['code'] if len(val_df) > 0 else None


# ========== 交易执行 ==========

def sell_and_select(context):
    g.pending_buy = None
    holding = get_holding(context)
    new_target = select_stock(context)

    if not new_target:
        return
    if holding and new_target != holding:
        order_target(holding, 0)
        g.pending_buy = new_target
        log.info(f'[9:31] 卖出 {holding}，待买入 {new_target}')
    elif not holding:
        g.pending_buy = new_target


def buy_target(context):
    if not g.pending_buy:
        return
    stock = g.pending_buy
    cd = get_current_data()
    if cd[stock].last_price >= cd[stock].high_limit * 0.998:
        log.info(f'[9:35] {stock} 接近涨停，跳过')
        g.pending_buy = None
        return
    order_target_value(stock, context.portfolio.total_value)
    log.info(f'[9:35] 买入 {stock}')
    g.pending_buy = None


def monitor_stop_loss(context):
    holding = get_holding(context)
    if not holding:
        return
    pos = context.portfolio.positions[holding]
    if pos.avg_cost <= 0:
        return
    price = get_current_data()[holding].last_price
    if price <= 0:
        return
    if (price - pos.avg_cost) / pos.avg_cost < g.stop_loss_pct:
        order_target(holding, 0)
        log.info(f'[止损] {holding} 成本{pos.avg_cost:.2f} 现价{price:.2f}')


def after_trading_end(context):
    holding = get_holding(context)
    log.info(f'[收盘] 持仓: {holding or "空仓"}, 总资产: {context.portfolio.total_value:.2f}')
