# Clone from JoinQuant
# postId: 8e8861f0c4c759472dee046ec006b8d3
# backtestId: 3932ee250e33c2787da0fb67c2f80b60
# title: 【市场仪表盘】重大升级！从 7 维到 13 维的宏观风险模型

# ============================================================
# 聚宽策略：右侧趋势短线（持仓不超过5日）
# 核心逻辑：MACD金叉 + 量价共振 + 均线多头三重信号
# 建议回测区间：2020-01-01 ~ 2024-12-31
# 建议资金：100万
# ============================================================

from jqdata import *
import pandas as pd
import numpy as np
import talib


def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    log.set_level('order', 'error')

    # 手续费：印花税0.1% + 双边佣金0.03%（券商折扣）
    set_order_cost(OrderCost(
        close_tax=0.001,
        open_commission=0.0003,
        close_commission=0.0003,
        min_commission=5
    ), type='stock')

    g.max_positions   = 5      # 最大持仓只数
    g.max_hold_days   = 5      # 最大持仓交易日
    g.stop_loss_pct   = 0.05   # 止损 5%
    g.take_profit_pct = 0.10   # 止盈 10%
    g.position_pct    = 0.90   # 使用资金比例

    # {stock: 买入时的交易日序号}
    g.hold_days = {}

    # 早盘：选股买入 + 止损止盈检查
    run_daily(on_market_open, time='09:31')
    # 尾盘：超期清仓
    run_daily(on_market_close, time='14:45')


# ────────────────────────────────────────────────────────────
# 市场整体环境过滤：大盘弱势时不开新仓
# ────────────────────────────────────────────────────────────
def market_is_healthy(context):
    """判断大盘是否处于上升趋势（MA20 上方）"""
    index = '000001.XSHG'  # 上证指数
    df = get_price(index, count=25, end_date=context.current_dt,
                   frequency='daily', fields=['close'], skip_paused=True)
    if len(df) < 22:
        return True
    ma20 = df['close'].rolling(20).mean().iloc[-1]
    latest = df['close'].iloc[-1]
    return latest > ma20


# ────────────────────────────────────────────────────────────
# 早盘主函数
# ────────────────────────────────────────────────────────────
def on_market_open(context):
    # 1. 先做止损止盈
    check_exit(context)
    # 2. 大盘环境允许 & 仓位未满时才开新仓
    if market_is_healthy(context):
        if len(context.portfolio.positions) < g.max_positions:
            stocks = select_stocks(context)
            execute_buy(context, stocks)


# ────────────────────────────────────────────────────────────
# 尾盘：超过5交易日强制清仓
# ────────────────────────────────────────────────────────────
def on_market_close(context):
    for stock in list(context.portfolio.positions.keys()):
        if stock in g.hold_days:
            days = g.hold_days[stock]
            if days >= g.max_hold_days:
                order_target(stock, 0)
                log.info(f'[超期清仓] {stock} 持仓 {days} 日')
                g.hold_days.pop(stock, None)
        # 每日持仓天数 +1
        if stock in g.hold_days:
            g.hold_days[stock] += 1


# ────────────────────────────────────────────────────────────
# 止损 / 止盈
# ────────────────────────────────────────────────────────────
def check_exit(context):
    for stock in list(context.portfolio.positions.keys()):
        pos = context.portfolio.positions[stock]
        if pos.avg_cost <= 0:
            continue
        pnl = (pos.price - pos.avg_cost) / pos.avg_cost

        if pnl <= -g.stop_loss_pct:
            order_target(stock, 0)
            log.info(f'[止损] {stock}  亏损 {pnl:.2%}')
            g.hold_days.pop(stock, None)
        elif pnl >= g.take_profit_pct:
            order_target(stock, 0)
            log.info(f'[止盈] {stock}  盈利 {pnl:.2%}')
            g.hold_days.pop(stock, None)


# ────────────────────────────────────────────────────────────
# 选股核心：三重共振信号
#   信号①  MACD 金叉（DIF 上穿 DEA）—— 右侧趋势确认
#   信号②  均线多头排列 MA5 > MA10 > MA20 —— 主趋势向上
#   信号③  量比 > 1.5 —— 资金放量进场
#   过滤：  RSI(6) 在 50~78 之间（健康上涨，非极度超买）
# ────────────────────────────────────────────────────────────
def select_stocks(context):
    today = context.current_dt.date()

    # ── 初步股票池过滤 ──
    all_stocks = get_all_securities('stock', date=context.current_dt).index.tolist()
    current_data = get_current_data()

    pool = []
    for s in all_stocks:
        # 过滤 ST / *ST
        name = get_security_info(s).display_name
        if 'ST' in name:
            continue
        # 过滤科创板（688）、北交所（8/4开头）
        if s.startswith('688') or s.startswith('8') or s.startswith('4'):
            continue
        # 过滤停牌
        if current_data[s].paused:
            continue
        # 过滤已持仓
        if s in context.portfolio.positions:
            continue
        # 过滤涨跌停（无法成交）
        price = current_data[s].last_price
        if price >= current_data[s].high_limit or price <= current_data[s].low_limit:
            continue
        # 股价过滤（过低的垃圾股）
        if price < 3:
            continue
        pool.append(s)

    # ── 计算指标，打分排序 ──
    candidates = []
    # 随机打乱，避免总取同一批（也可按市值排序取前500）
    import random
    random.shuffle(pool)
    scan_limit = min(600, len(pool))

    for stock in pool[:scan_limit]:
        try:
            df = get_price(stock, count=40,
                           end_date=context.current_dt,
                           frequency='daily',
                           fields=['close', 'volume'],
                           skip_paused=True)
            if len(df) < 35:
                continue

            close  = df['close'].values.astype(float)
            volume = df['volume'].values.astype(float)

            # MACD (12, 26, 9)
            dif, dea, hist = talib.MACD(close, 12, 26, 9)

            # 均线
            ma5  = talib.SMA(close, 5)
            ma10 = talib.SMA(close, 10)
            ma20 = talib.SMA(close, 20)

            # RSI(6) — 短线用小周期
            rsi6 = talib.RSI(close, 6)

            # ── 最新 & 前一根 ──
            c0, c1     = close[-1],  close[-2]
            d0, d1     = dif[-1],    dif[-2]
            e0, e1     = dea[-1],    dea[-2]
            ma5_0      = ma5[-1]
            ma10_0     = ma10[-1]
            ma20_0     = ma20[-1]
            rsi_0      = rsi6[-1]

            # 量比（昨日量 / 过去5日均量）
            vol_ma5    = np.mean(volume[-6:-1])
            vol_ratio  = volume[-2] / vol_ma5 if vol_ma5 > 0 else 0

            # ── 三重信号 ──
            # 信号①：MACD 金叉（上一根 DIF < DEA，当前 DIF > DEA）
            macd_cross = (d1 < e1) and (d0 > e0)

            # 信号②：均线多头排列
            ma_align   = (ma5_0 > ma10_0 > ma20_0)

            # 信号③：量比 > 1.5 且价格在 MA20 上方
            vol_ok     = (vol_ratio > 1.5) and (c0 > ma20_0)

            # 过滤：RSI 健康区间
            rsi_ok     = 50 < rsi_0 < 78

            if not (macd_cross and rsi_ok):
                continue

            # 评分（满足越多越高质量）
            score = 0
            score += 4 if macd_cross else 0
            score += 3 if ma_align    else 0
            score += 2 if vol_ok      else 0
            score += 1 if rsi_0 < 70  else 0   # RSI 未极度超买加分

            candidates.append({'stock': stock, 'score': score})

        except Exception:
            continue

    candidates.sort(key=lambda x: x['score'], reverse=True)
    selected = [c['stock'] for c in candidates[:g.max_positions * 2]]

    if selected:
        log.info(f'[选股] 今日候选: {selected[:10]}')
    return selected


# ────────────────────────────────────────────────────────────
# 买入执行
# ────────────────────────────────────────────────────────────
def execute_buy(context, stocks):
    positions_count = len(context.portfolio.positions)
    slots = g.max_positions - positions_count
    if slots <= 0 or not stocks:
        return

    cash_per = context.portfolio.available_cash * g.position_pct / slots
    bought = 0

    for stock in stocks:
        if bought >= slots:
            break
        if stock in context.portfolio.positions:
            continue

        order_value(stock, cash_per)
        g.hold_days[stock] = 1
        log.info(f'[买入] {stock}  金额 {cash_per:,.0f} 元')
        bought += 1
