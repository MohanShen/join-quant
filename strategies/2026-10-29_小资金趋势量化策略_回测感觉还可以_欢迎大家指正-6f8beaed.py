# Clone from JoinQuant
# postId: 6f8beaed4fc192695989163e9e8ce26a
# backtestId: 028c3af3d0345a0898350ddebc8f2aec
# title: 小资金趋势量化策略，回测感觉还可以，欢迎大家指正

# -*- coding: utf-8 -*-
"""
自适应双模式策略
==============================================
根据市场状态自动切换：
  - 牛市/震荡：动量突破（追强势股）
  - 熊市：超跌反弹（抄恐慌底）+ 更严格过滤

关键认知：
  熊市中要更挑剔——只在"恐慌+缩量企稳+跌前强势"三重确认后才出手。
  宁可错过，不可做错。快速止盈（4%），快速止损（2.5%）。
"""

import numpy as np
import pandas as pd


def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.001,
        open_commission=0.00025, close_commission=0.00025,
        min_commission=5
    ), type='stock')

    g.stock_num = 3               # 3只（更集中，减少交易笔数）
    g.max_price = 35
    g.min_amount = 5e7            # 提高到5000万（流动性更好）
    g.stop_loss = -0.025
    g.take_profit = 0.05
    g.max_hold_days = 5           # 5天（多拿2天，减少换手）
    g.target_utilization = 0.50   # 仓位利用率50%

    # 股票池：中证1000（小市值）+ 排除688/300
    try:
        pool = get_index_stocks('000852.XSHG')
        g.stock_pool = [s for s in pool
                        if not s.startswith('688') and not s.startswith('300')]
    except Exception:
        g.stock_pool = []
    log.info(f'股票池: {len(g.stock_pool)}只')

    g.buy_prices = {}
    g.buy_dates = {}
    run_daily(main_trading, time='10:00')
    run_daily(risk_control, time='14:45')
    log.info('=== 自适应双模式 3只/仓位50%/止盈5%止损2.5% ===')


def main_trading(context):
    regime = _regime(context)
    if regime == 'cash':
        _sell_all(context)
        return

    # 根据市场状态选策略
    if regime == 'bull':
        candidates = _scan_momentum(context)
    else:
        candidates = _scan_bounce(context)

    max_n = g.stock_num if regime == 'bull' else 1  # 熊市只做1只（少而精）
    if len(candidates) < max_n:
        return

    target = list(candidates.keys())[:max_n]
    held = _held(context)
    for s in held:
        if s not in target:
            _sell(s)
            _clean(s)

    for s in target:
        if s in held:
            continue
        p = candidates[s]
        lots = _lots(context.portfolio.total_value, p, max_n)
        try:
            order(s, lots * 100)
            g.buy_prices[s] = p
            g.buy_dates[s] = context.current_dt
            log.info(f'[买入] {s} ¥{p:.2f} {regime}')
        except Exception:
            pass


# ============================================================
# 市场状态判断
# ============================================================

def _regime(context):
    """
    bull:  指数 > 20MA 且 20MA > 60MA（上升趋势）
    bear:  指数 < 60MA（下跌趋势，但可做超跌反弹）
    cash:  指数 < 60MA 且今天大盘跌 >2%（恐慌日，空仓）
    """
    try:
        d = attribute_history('000300.XSHG', 65, '1d', ['close'])
        if d is None or len(d) < 60:
            return 'bear'
        c = d['close'].values
        ma20 = np.mean(c[-20:])
        ma60 = np.mean(c[-60:])
        cur = c[-1]

        # 恐慌日 → 空仓
        if len(c) >= 2 and (c[-1] - c[-2]) / c[-2] < -0.02:
            return 'cash'

        if cur > ma20 and ma20 > ma60:
            return 'bull'
        elif cur > ma60:
            return 'bear'
        else:
            # 熊市但指数不在恐慌日 → 可以抄底
            return 'bear' if (c[-1] - c[-2]) / c[-2] > -0.02 else 'cash'
    except Exception:
        return 'bear'


# ============================================================
# 动量模式（牛市用）
# ============================================================

def _scan_momentum(context):
    """强市追涨：10日动量 + 放量 + 接近新高"""
    result = {}
    try:
        df = get_price(g.stock_pool, count=15, end_date=context.current_dt,
                       frequency='daily', fields=['close', 'volume', 'high'],
                       panel=False, fq='pre')
    except Exception:
        return result
    if df is None or 'code' not in df.columns:
        return result

    for stock, gdf in df.groupby('code'):
        try:
            if len(gdf) < 12:
                continue
            c = gdf['close'].values.astype(float)
            v = gdf['volume'].values.astype(float)
            h = gdf['high'].values.astype(float)

            if c[-1] <= 0 or c[-1] > g.max_price:
                continue
            if v[-1] <= 0 or c[-1] * v[-1] < g.min_amount:
                continue

            ret10 = (c[-1] - c[-10]) / c[-10] if c[-10] > 0 else 0
            if ret10 < 0.04:  # 10日涨超4%
                continue

            ret3 = (c[-1] - c[-3]) / c[-3] if c[-3] > 0 else 0
            if ret3 < -0.02:  # 近3日不能跌超2%（回调太多不算强势）
                continue

            v10 = np.mean(v[-11:-1])
            vol_r = v[-1] / v10 if v10 > 0 else 1
            if vol_r < 1.1:
                continue

            h20 = np.max(h[-15:])
            near = (c[-1] - h20) / h20 if h20 > 0 else -1
            if near < -0.04:
                continue

            score = ret10 * 3 + vol_r + near * 5
            result[stock] = (c[-1], score)
        except Exception:
            continue

    sorted_items = sorted(result.items(), key=lambda x: x[1][1], reverse=True)
    return {s: p for s, (p, _) in sorted_items}


# ============================================================
# 超跌反弹模式（熊市用，更严格）
# ============================================================

def _scan_bounce(context):
    """
    熊市超跌反弹（三重确认）：
    1. 昨天跌 4-9% + 放量（>1.5x均量）
    2. 跌前5天偏强（> -2%）
    3. 今天缩量企稳（量<昨天70%, 价>昨天低点）
    """
    result = {}
    try:
        df = get_price(g.stock_pool, count=8, end_date=context.current_dt,
                       frequency='daily', fields=['close', 'low', 'volume'],
                       panel=False, fq='pre')
    except Exception:
        return result
    if df is None or 'code' not in df.columns:
        return result

    for stock, gdf in df.groupby('code'):
        try:
            if len(gdf) < 8:
                continue
            c = gdf['close'].values.astype(float)
            l = gdf['low'].values.astype(float)
            v = gdf['volume'].values.astype(float)

            if np.any(c <= 0):
                continue

            # 昨天 = [-2], 今天 = [-1], 前天 = [-3]
            cy, ct, cp = c[-2], c[-1], c[-3]
            ly = l[-2]
            vy, vt = v[-2], v[-1]

            # 昨天跌 4-9%
            chg_y = (cy - cp) / cp
            if not (-0.09 <= chg_y <= -0.04):
                continue
            if cy <= cp * 0.902:
                continue

            # 跌前5天走势（索引0到-3的区间）= (cp - c[0]) / c[0]
            pre_ret = (cp - c[0]) / c[0]
            if pre_ret < -0.02:
                continue

            # 昨天放量 > 1.5x 前5天均量
            v_avg = np.mean(v[:5])
            if v_avg <= 0 or vy < v_avg * 1.5:
                continue

            # 今天缩量 < 70% 昨天量
            if vt > vy * 0.7:
                continue

            # 今天价格 > 昨天最低
            if ct <= ly:
                continue

            # 价格、流动性
            if ct > g.max_price:
                continue
            if cy * vy < g.min_amount:
                continue

            score = abs(chg_y) * 10 + (vy / v_avg)
            result[stock] = (ct, score)
        except Exception:
            continue

    sorted_items = sorted(result.items(), key=lambda x: x[1][1], reverse=True)
    return {s: p for s, (p, _) in sorted_items}


# ============================================================
# 风控 & 工具
# ============================================================

def risk_control(context):
    held = _held(context)
    if not held:
        return
    prices = {}
    try:
        df = get_price(held, count=1, end_date=context.current_dt,
                       frequency='daily', fields=['close'], panel=False, fq='pre')
        if df is not None and 'code' in df.columns:
            for s, gdf in df.groupby('code'):
                try:
                    prices[s] = float(gdf['close'].iloc[-1])
                except Exception:
                    continue
    except Exception:
        pass

    for s in held:
        p = prices.get(s)
        if not p or p <= 0:
            continue
        bp = g.buy_prices.get(s)
        if not bp:
            continue
        pnl = (p - bp) / bp
        days = (context.current_dt.date() - g.buy_dates[s].date()).days if g.buy_dates.get(s) else 0
        if pnl < g.stop_loss or pnl > g.take_profit or (days >= g.max_hold_days and pnl < 0):
            _sell(s)
            log.info(f'[{"止盈" if pnl > 0 else "止损"}] {s} {pnl:.2%} {days}天')
            _clean(s)


def _held(context):
    return [s for s in context.portfolio.positions
            if context.portfolio.positions[s].total_amount > 0]


def _sell_all(context):
    for s in _held(context):
        _sell(s)
        _clean(s)


def _lots(total_value, price, n):
    """
    按目标仓位利用率计算手数
    例：10万本金 × 45%利用率 / 4只 / 30元股价 ≈ 3.75手 → 3-4手
    """
    per_position = total_value * g.target_utilization / n  # 每只目标金额
    lots = int(per_position / (price * 100))  # 换算成手
    # 至少1手，确保买得起
    max_afford = int(total_value * 0.8 / n / (price * 100))
    lots = min(lots, max_afford)
    return max(1, lots)


def _sell(s):
    try:
        order_target(s, 0)
    except Exception:
        pass


def _clean(s):
    g.buy_prices.pop(s, None)
    g.buy_dates.pop(s, None)

