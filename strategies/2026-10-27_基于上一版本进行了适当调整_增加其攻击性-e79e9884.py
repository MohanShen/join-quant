# Clone from JoinQuant
# postId: e79e9884f4de707afadcfcd2b07bbe86
# backtestId: 3fc8feb844c22c49e5fa5f55f5bbe327
# title: 基于上一版本进行了适当调整，增加其攻击性

# -*- coding: utf-8 -*-
# ============================================================
# 进攻型多ETF轮动趋势跟踪策略
# 平台：JoinQuant（聚宽）  Python3
# 目标：年化15%~20%，最大回撤可接受20%~25%
# ============================================================

import numpy as np
import pandas as pd
from jqdata import *


# ============================================================
# 一、参数配置区（集中管理，方便修改）
# ============================================================

# ---------- 标的池 ----------
ETF_POOL = [
    '510300.XSHG',   # 沪深300ETF（宽基）
    '510500.XSHG',   # 中证500ETF（宽基）
    '159915.XSHE',   # 创业板ETF（宽基、高弹性）
    '512880.XSHG',   # 证券ETF（强周期行业）
    '518880.XSHG',   # 黄金ETF（避险资产）
    '513100.XSHG',   # 纳指ETF（跨境资产）
]
INDEX_SYMBOL = '000300.XSHG'   # 大盘择时用的沪深300指数

# ---------- 布林带 ----------
BB_PERIOD    = 20       # 布林带周期
BB_DEVFACTOR = 2.0      # 标准差倍数

# ---------- ATR ----------
ATR_PERIOD     = 14     # ATR周期
ATR_STOP_MULT  = 2.5    # 初始止损 = 入场价 - 2.5 * ATR
ATR_TRAIL_MULT = 4.0    # 移动止盈回撤阈值 = 4.0 * ATR

# ---------- 趋势过滤 ----------
MA_TREND_PERIOD = 60    # 标的趋势均线（MA60）

# ---------- 大盘择时 ----------
INDEX_MA_SHORT = 20     # 大盘短均线
INDEX_MA_LONG  = 60     # 大盘长均线

# ---------- 仓位管理 ----------
RISK_PER_TRADE    = 0.02   # 单笔最大风险：总资金 2%
MAX_POSITION_PCT  = 0.50   # 单只ETF市值上限：总资金 50%
MAX_HOLDINGS      = 3      # 最多同时持有 3 只 ETF

# ---------- 风控 ----------
MAX_CONSEC_LOSSES   = 20   # 连续亏损次数阈值
PAUSE_RECOVERY_DAYS = 5    # 空仓恢复所需天数


# ============================================================
# 二、初始化
# ============================================================
def initialize(context):
    # 基准
    set_benchmark(INDEX_SYMBOL)
    # 前复权价格
    set_option('use_real_price', True)
    # 手续费：ETF 万2.5、最低5元、无印花税
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0,
        open_commission=0.00025, close_commission=0.00025,
        close_today_commission=0, min_commission=5
    ), type='fund')
    # 滑点 0.1%
    set_slippage(FixedSlippage(0.001))
    # 订单日志级别
    log.set_level('order', 'error')

    # ---- 全局状态（聚宽模拟盘持久化必须用 g）----
    g.pool             = ETF_POOL
    g.state            = {}   # {symbol: {entry_price, stop_price, highest, atr, entry_date, size}}
    g.consecutive_losses = 0  # 连续亏损计数
    g.pause_days_left    = 0  # 连续亏损暂停中的空仓天数
    g.trade_records      = [] # 已完成交易明细

    # 每个交易日开盘执行主逻辑
    run_daily(main_logic, time='open')


# ============================================================
# 三、大盘择时
# ============================================================
def get_index_regime():
    """
    基于昨日沪深300收盘价判断市场状态：
      'offensive'：收盘 >= MA20，允许开新仓
      'neutral'  ：MA60 <= 收盘 < MA20，禁止开新仓但可持仓
      'defensive'：收盘 < MA60，强制清仓且禁止开新仓
    """
    hist = attribute_history(
        INDEX_SYMBOL, INDEX_MA_LONG + 5, '1d',
        ['close'], skip_paused=True, df=False
    )
    close = hist['close']
    if len(close) < INDEX_MA_LONG:
        return 'defensive'

    ma20 = np.mean(close[-INDEX_MA_SHORT:])
    ma60 = np.mean(close[-INDEX_MA_LONG:])
    cur  = close[-1]

    if cur < ma60:
        return 'defensive'
    elif cur < ma20:
        return 'neutral'
    else:
        return 'offensive'


# ============================================================
# 四、指标计算
# ============================================================
def calc_indicators(symbol):
    """
    基于昨日收盘数据计算：
      - 布林带（20, 2）
      - MA60（趋势过滤）
      - MA20（止盈条件B用）
      - ATR(14)
    返回字典；数据不足返回 None
    """
    lookback = max(MA_TREND_PERIOD, BB_PERIOD) + ATR_PERIOD + 5
    hist = attribute_history(
        symbol, lookback, '1d',
        ['high', 'low', 'close'],
        skip_paused=True, df=False
    )
    if len(hist['close']) < MA_TREND_PERIOD + 2:
        return None

    close = hist['close']
    high  = hist['high']
    low   = hist['low']

    # ---- 布林带（昨日 & 前日）----
    ma20      = np.mean(close[-BB_PERIOD:])
    std20     = np.std(close[-BB_PERIOD:])
    bb_upper_yest = ma20 + BB_DEVFACTOR * std20

    ma20_prev    = np.mean(close[-BB_PERIOD - 1:-1])
    std20_prev   = np.std(close[-BB_PERIOD - 1:-1])
    bb_upper_prev = ma20_prev + BB_DEVFACTOR * std20_prev

    # ---- MA60 趋势过滤 ----
    ma60 = np.mean(close[-MA_TREND_PERIOD:])

    # ---- MA20 向下拐头判断 ----
    ma20_slope_down = ma20 < ma20_prev

    # ---- ATR(14) ----
    trs = []
    for i in range(-ATR_PERIOD, 0):
        tr = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1])
        )
        trs.append(tr)
    atr = np.mean(trs)

    return {
        'close_yest'     : close[-1],       # 昨日收盘价
        'close_prev'     : close[-2],       # 前日收盘价
        'high_yest'      : high[-1],        # 昨日最高价
        'bb_upper_yest'  : bb_upper_yest,   # 昨日布林上轨
        'bb_upper_prev'  : bb_upper_prev,   # 前日布林上轨
        'ma60'           : ma60,
        'ma20'           : ma20,
        'ma20_slope_down': ma20_slope_down,
        'atr'            : atr,
    }


# ============================================================
# 五、主交易逻辑（每个交易日开盘 9:30 执行）
# ============================================================
def main_logic(context):
    current_date = context.current_dt.date()
    current_data = get_current_data()

    # ==================================================
    # 1. 大盘择时
    # ==================================================
    regime = get_index_regime()

    # ==================================================
    # 2. 持仓管理：止损 / 止盈 / 大盘防御清仓
    # ==================================================
    for symbol in list(context.portfolio.positions.keys()):
        pos = context.portfolio.positions[symbol]
        if pos.total_amount <= 0:
            continue
        if symbol not in g.state:       # 非本策略开仓
            continue

        st  = g.state[symbol]
        ind = calc_indicators(symbol)
        if ind is None:
            continue

        cur_close = ind['close_yest']

        # 更新持仓期间最高价（用昨日最高价刷新）
        st['highest'] = max(st['highest'], ind['high_yest'])

        # 出场条件
        stop_hit      = cur_close <= st['stop_price']
        trail_hit     = (st['highest'] - cur_close) >= ATR_TRAIL_MULT * st['atr']
        ma20_hit      = (cur_close < ind['ma20']) and ind['ma20_slope_down']
        defensive_hit = (regime == 'defensive')

        if not (stop_hit or trail_hit or ma20_hit or defensive_hit):
            continue

        # 归因（优先级：防御 > 止损 > 移动止盈 > MA20止盈）
        if defensive_hit:
            reason = '大盘防御清仓'
        elif stop_hit:
            reason = '初始止损'
        elif trail_hit:
            reason = '移动止盈(回撤)'
        else:
            reason = '移动止盈(MA20)'

        # 今日开盘价卖出（市价单）
        order_target(symbol, 0)

        exit_price = current_data[symbol].day_open
        if not exit_price or exit_price <= 0 or np.isnan(exit_price):
            exit_price = cur_close

        pnl = (exit_price - st['entry_price']) * st['size']
        g.trade_records.append({
            'symbol'     : symbol,
            'entry_date' : st['entry_date'],
            'exit_date'  : current_date,
            'entry_price': st['entry_price'],
            'exit_price' : exit_price,
            'size'       : st['size'],
            'pnl'        : pnl,
            'reason'     : reason,
        })

        if pnl < 0:
            g.consecutive_losses += 1
        else:
            g.consecutive_losses = 0

        log.info('[%s] 卖出 %s @%.3f 数量=%d 盈亏=%.2f 原因=%s 连亏=%d' % (
            current_date, symbol, exit_price, st['size'],
            pnl, reason, g.consecutive_losses
        ))
        del g.state[symbol]

    # ==================================================
    # 3. 连续亏损暂停 & 恢复检查
    # ==================================================
    if g.consecutive_losses >= MAX_CONSEC_LOSSES:
        recovered = False

        # 恢复条件A：大盘站上 MA20
        if regime == 'offensive':
            recovered = True
            log.info('[%s] 大盘重新站上MA20，恢复开仓' % current_date)

        # 恢复条件B：空仓 >= PAUSE_RECOVERY_DAYS 个交易日
        if not recovered:
            holdings = sum(
                1 for s in context.portfolio.positions
                if context.portfolio.positions[s].total_amount > 0
            )
            if holdings == 0:
                g.pause_days_left += 1
                log.info('[%s] 暂停中，空仓第 %d 天' % (
                    current_date, g.pause_days_left))
                if g.pause_days_left >= PAUSE_RECOVERY_DAYS:
                    recovered = True
                    log.info('[%s] 空仓满%d天，恢复开仓' % (
                        current_date, PAUSE_RECOVERY_DAYS))
            else:
                # 仍有持仓则重置空仓计数（理论上不应出现）
                g.pause_days_left = 0

        if recovered:
            g.consecutive_losses = 0
            g.pause_days_left    = 0
        else:
            return

    # ==================================================
    # 4. 非进攻状态：禁止开新仓
    # ==================================================
    if regime != 'offensive':
        return

    current_holdings = sum(
        1 for s in context.portfolio.positions
        if context.portfolio.positions[s].total_amount > 0
    )
    if current_holdings >= MAX_HOLDINGS:
        return

    # ==================================================
    # 5. 开仓信号扫描
    # ==================================================
    for symbol in g.pool:
        # 已持仓
        if symbol in context.portfolio.positions and \
                context.portfolio.positions[symbol].total_amount > 0:
            continue

        ind = calc_indicators(symbol)
        if ind is None:
            continue

        # --- 四个开仓条件 ---
        cond1 = ind['close_yest'] > ind['bb_upper_yest']     # 今日(昨收)突破上轨
        cond2 = ind['close_prev'] <= ind['bb_upper_prev']    # 前日仍在上轨内
        cond3 = ind['bb_upper_yest'] > ind['bb_upper_prev']  # 上轨向上
        cond4 = ind['close_yest'] > ind['ma60']              # 站上 MA60

        if not (cond1 and cond2 and cond3 and cond4):
            continue

        # --- 入场价：今日开盘价 ---
        entry_price = current_data[symbol].day_open
        if not entry_price or entry_price <= 0 or np.isnan(entry_price):
            entry_price = ind['close_yest']

        # --- 初始止损价 ---
        stop_price = entry_price - ATR_STOP_MULT * ind['atr']
        risk_per_share = entry_price - stop_price
        if risk_per_share <= 0:
            continue

        # --- 仓位计算：按 2% 风险 ---
        total_value = context.portfolio.total_value
        risk_amount = total_value * RISK_PER_TRADE
        size = int(risk_amount / risk_per_share)
        size = (size // 100) * 100        # 按 100 份取整

        # --- 单只 50% 资金上限 ---
        max_size_pct = int(total_value * MAX_POSITION_PCT / entry_price)
        max_size_pct = (max_size_pct // 100) * 100
        size = min(size, max_size_pct)

        # --- 可用现金约束（留 1% 余量应对手续费）---
        avail_cash = context.portfolio.available_cash
        max_size_cash = int(avail_cash * 0.99 / entry_price)
        max_size_cash = (max_size_cash // 100) * 100
        size = min(size, max_size_cash)

        if size < 100:      # 不足 100 份放弃
            continue

        # --- 下单：市价买入，聚宽在下一 tick（同一开盘）成交 ---
        order(symbol, size)

        # --- 记录持仓状态 ---
        g.state[symbol] = {
            'entry_price': entry_price,
            'stop_price' : stop_price,
            'highest'    : entry_price,
            'atr'        : ind['atr'],
            'entry_date' : current_date,
            'size'       : size,
        }

        log.info('[%s] 开仓 %s 数量=%d 入场价~%.3f 止损价~%.3f ATR=%.3f' % (
            current_date, symbol, size, entry_price, stop_price, ind['atr']
        ))

        current_holdings += 1
        if current_holdings >= MAX_HOLDINGS:
            break


# ============================================================
# 六、回测结束统计
# ============================================================
def on_strategy_end(context):
    if not g.trade_records:
        log.info('============ 无交易记录 ============')
        return

    df = pd.DataFrame(g.trade_records)
    total_trades = len(df)
    wins   = df[df['pnl'] > 0]
    losses = df[df['pnl'] <= 0]

    win_rate    = len(wins) / total_trades * 100 if total_trades > 0 else 0
    avg_win     = wins['pnl'].mean() if len(wins) > 0 else 0
    avg_loss    = abs(losses['pnl'].mean()) if len(losses) > 0 else 1
    profit_factor = avg_win / avg_loss if avg_loss > 0 else 0

    # 最大连续亏损（按时间顺序遍历）
    max_consec, cur_consec = 0, 0
    for pnl in df['pnl'].values:
        if pnl < 0:
            cur_consec += 1
            max_consec = max(max_consec, cur_consec)
        else:
            cur_consec = 0

    # 平均持仓天数
    try:
        df['entry_dt'] = pd.to_datetime(df['entry_date'])
        df['exit_dt']  = pd.to_datetime(df['exit_date'])
        avg_days = (df['exit_dt'] - df['entry_dt']).dt.days.mean()
    except Exception:
        avg_days = 0

    total_return = (context.portfolio.total_value /
                    context.portfolio.starting_cash - 1) * 100

    log.info('=' * 60)
    log.info('     进攻型多ETF轮动趋势跟踪策略 — 回测报告')
    log.info('=' * 60)
    log.info('  期末权益:       %.2f' % context.portfolio.total_value)
    log.info('  总收益率:       %.2f%%' % total_return)
    log.info('  交易次数:       %d' % total_trades)
    log.info('  盈利次数:       %d' % len(wins))
    log.info('  亏损次数:       %d' % len(losses))
    log.info('  胜率:           %.2f%%' % win_rate)
    log.info('  盈亏比:         %.2f' % profit_factor)
    log.info('  最大连续亏损:   %d 次' % max_consec)
    log.info('  平均持仓天数:   %.1f 天' % avg_days)
    log.info('=' * 60)

    log.info('--- 交易明细 ---')
    for _, row in df.iterrows():
        log.info('%s %s→%s 入场%.3f 出场%.3f 盈亏%+.2f (%s)' % (
            row['symbol'], row['entry_date'], row['exit_date'],
            row['entry_price'], row['exit_price'], row['pnl'], row['reason']
        ))