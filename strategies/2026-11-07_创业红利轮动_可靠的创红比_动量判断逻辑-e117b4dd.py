# Clone from JoinQuant
# postId: e117b4ddd7db1978271fa72a733acb95
# backtestId: 154942e44132199bb666e5b23dcc5e26
# title: 「创业红利轮动」可靠的创红比、动量判断逻辑

# -*- coding: utf-8 -*-
"""
成长红利风格轮动 + 创业板动量择时

"""

import numpy as np
import pandas as pd
from datetime import timedelta
from jqdata import *


# ============================================================
# 【开关】空仓期配置
# ============================================================
USE_DIVIDEND_IN_CASH = True
#   True  → 空仓期买入并持有红利ETF（推荐：不浪费资金时间价值）
#   False → 空仓期持现金


# ============================================================
# 一、常量
# ============================================================
GROWTH_INDEX = '399006.XSHE'           # 创业板指
DIVIDEND_INDEX = '510880.XSHG'         # 上证红利ETF（比值 + 空仓期标的）
DIVIDEND_ETF_FALLBACK = '515180.XSHG'  # 备选：中证红利ETF
GROWTH_ETF = '159915.XSHE'             # 创业板ETF（易方达）

MA_WINDOW       = 20
BUFFER          = 0.015

MOMENTUM_WINDOW = 20
MOMENTUM_ENTER  = 0.05
MOMENTUM_EXIT   = -0.01

CONFIRM_DAYS    = 1         # 显式改为 1
COOLDOWN_DAYS   = 10


# ============================================================
# 二、初始化
# ============================================================
def initialize(context):
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_benchmark('159915.XSHE')

    set_order_cost(
        OrderCost(
            open_tax=0, close_tax=0,
            open_commission=0.00025, close_commission=0.00025,
            min_commission=5
        ),
        type='fund'
    )
    set_slippage(FixedSlippage(0.001))
    log.set_level('order', 'error')

    g.signal_state = 'growth'
    g.pending_state = None
    g.pending_days = 0
    g.last_exit_date = None


# ============================================================
# 三、数据工具
# ============================================================
def get_index_close(index_code, end_date, lookback_days=400):
    start_date = end_date - timedelta(days=lookback_days)
    try:
        df = get_price(
            index_code, start_date=start_date, end_date=end_date,
            frequency='daily', fields=['close'],
            panel=False, skip_paused=True
        )
    except Exception as e:
        log.info("[取数异常] {}: {}".format(index_code, e))
        return None, 0
    if df is None or len(df) == 0:
        return None, 0
    # 将 time 列设为索引，确保按日期对齐
    if 'time' in df.columns:
        df = df.set_index('time')
    df.index = pd.to_datetime(df.index)
    return df['close'], len(df)


def get_dividend_close(end_date, lookback_days=400):
    for code in [DIVIDEND_INDEX, DIVIDEND_ETF_FALLBACK]:
        close, n = get_index_close(code, end_date, lookback_days)
        if close is not None and n > 0:
            return close, code, n
    return None, None, 0


def calc_ratio_and_ma(context, buffer_pct=None):
    if buffer_pct is None:
        buffer_pct = BUFFER

    end_date = context.previous_date
    lookback = MA_WINDOW * 2 + 30

    g_c, g_n = get_index_close(GROWTH_INDEX, end_date, lookback)
    d_c, d_code, d_n = get_dividend_close(end_date, lookback)

    if g_c is None or d_c is None:
        return None, None, None

    # 按日期对齐，避免 iloc 错位
    df = pd.concat([g_c, d_c], axis=1, join='inner')
    df.columns = ['growth', 'dividend']
    df = df.dropna()
    if len(df) < MA_WINDOW + 1:
        return None, None, None

    ratio = df['growth'] / df['dividend']
    if len(ratio) < MA_WINDOW:
        return None, None, None

    ma = ratio.rolling(MA_WINDOW).mean().dropna()
    if len(ma) == 0:
        return None, None, None

    cur_r = ratio.iloc[-1]
    cur_m = ma.iloc[-1]

    raw = None
    if cur_r > cur_m * (1 + buffer_pct):
        raw = 'growth'
    elif cur_r < cur_m * (1 - buffer_pct):
        raw = 'dividend'

    if raw is not None and raw != g.signal_state:
        if g.pending_state == raw:
            g.pending_days += 1
        else:
            g.pending_state = raw
            g.pending_days = 1
        if g.pending_days >= CONFIRM_DAYS:
            g.signal_state = raw
            g.pending_state = None
            g.pending_days = 0
            log.info(">>> 风格确认切换为 {}".format(g.signal_state))
    else:
        g.pending_state = None
        g.pending_days = 0

    return cur_r, cur_m, g.signal_state


def calc_momentum(context, index_code, window=None):
    if window is None:
        window = MOMENTUM_WINDOW
    end_date = context.previous_date
    close, n = get_index_close(index_code, end_date, window * 2 + 30)
    if close is None or len(close) < window + 1:
        return None
    close = close.iloc[-window:]
    if len(close) < 2:
        return None
    return close.iloc[-1] / close.iloc[0] - 1


# ============================================================
# 四、交易工具
# ============================================================
def has_position(context, security):
    if security in context.portfolio.positions:
        return context.portfolio.positions[security].total_amount > 0
    return False


def order_target_percent_safe(context, security, target_pct):
    if target_pct <= 0:
        order_target_value(security, 0)
        return
    px = get_current_data()[security].last_price
    if px is None or px <= 0 or np.isnan(px):
        return
    target_value = context.portfolio.total_value * target_pct
    shares = int(target_value / px / 100) * 100
    if shares < 100:
        return
    order_target(security, shares)


def days_since_exit(context):
    if g.last_exit_date is None:
        return 999
    # 计算从退出日到当前日的交易日数量（不包含退出日当天）
    trade_days = get_trade_days(start_date=g.last_exit_date, end_date=context.current_dt.date())
    return len(trade_days) - 1


# ============================================================
# 五、核心交易逻辑（统一处理成长 / 红利 / 现金三种状态）
# ============================================================
def growth_timing(context):
    """
    目标状态机：
      - 'growth'   : 持创业板ETF（成长信号强 + 动量 > +5%）
      - 'dividend' : 持红利ETF（开关开启，空仓期配置）
      - 'cash'     : 持现金（开关关闭，原策略行为）
    """
    momentum = calc_momentum(context, GROWTH_INDEX, MOMENTUM_WINDOW)
    if momentum is None:
        return

    ratio, ma, style_signal = calc_ratio_and_ma(context, BUFFER)

    log.info("[择时] 动量={:.4f}, 比值={}, MA20={}, 风格={}".format(
        momentum,
        'None' if ratio is None else round(ratio, 4),
        'None' if ma is None else round(ma, 4),
        style_signal
    ))

    has_growth = has_position(context, GROWTH_ETF)
    has_dividend = has_position(context, DIVIDEND_INDEX)
    in_cooldown = days_since_exit(context) < COOLDOWN_DAYS

    # ---- 判断信号 ----
    enter = (
        (style_signal == 'growth') and
        (momentum > MOMENTUM_ENTER) and
        (not in_cooldown)
    )
    exit_sig = (style_signal != 'growth') or (momentum < MOMENTUM_EXIT)

    # ---- 决定目标状态 ----
    if enter:
        target = 'growth'
    elif exit_sig:
        target = 'dividend' if USE_DIVIDEND_IN_CASH else 'cash'
    else:
        # 中间状态：维持当前持仓对应的状态
        if has_growth:
            target = 'growth'
        elif has_dividend:
            target = 'dividend'
        else:
            target = 'dividend' if USE_DIVIDEND_IN_CASH else 'cash'

    # ---- 执行调仓 ----
    if target == 'growth':
        # 目标：持创业板，清红利
        if has_dividend:
            order_target_value(DIVIDEND_INDEX, 0)
            log.info(">>> 清仓红利ETF")
        if not has_growth:
            order_target_percent_safe(context, GROWTH_ETF, 1.0)
            log.info(">>> 买入创业板ETF, 动量={:.4f}".format(momentum))

    elif target == 'dividend':
        # 目标：持红利，清创业板
        if has_growth:
            order_target_value(GROWTH_ETF, 0)
            g.last_exit_date = context.current_dt.date()
            log.info(">>> 清仓创业板, 动量={:.4f}, 冷却期开始".format(momentum))
        if not has_dividend:
            order_target_percent_safe(context, DIVIDEND_INDEX, 1.0)
            log.info(">>> 空仓期买入红利ETF")

    else:  # target == 'cash'
        if has_growth:
            order_target_value(GROWTH_ETF, 0)
            g.last_exit_date = context.current_dt.date()
            log.info(">>> 清仓创业板, 动量={:.4f}, 冷却期开始".format(momentum))
        if has_dividend:
            order_target_value(DIVIDEND_INDEX, 0)
            log.info(">>> 清仓红利ETF")


# ============================================================
# 六、每日运行
# ============================================================
def handle_data(context, data):
    growth_timing(context)


# ============================================================
# 七、收盘后
# ============================================================
def after_trading_end(context):
    for sec, pos in context.portfolio.positions.items():
        if pos.total_amount > 0:
            log.info("持仓: {} 数量: {} 市值: {:.2f}".format(
                sec, pos.total_amount, pos.value))