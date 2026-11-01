# study variant u-premium — family: 均线乖离择时 (OBSERVE-ONLY probe)
# source: strategies/2026-10-28_使用标普500_60日均线乖离度增加超额收益的策略-648c2da3.py
# construction: py2to3(source) + one added run_daily(log_premium_probe,'09:31') + appended logger + OVERRIDE
# control: must reproduce base e9 row (annual 34.90 / sharpe 2.02 / maxDD 9.98)
# built: 2026-11-01 by study/均线乖离择时/build-premium.js
# Clone from JoinQuant
# postId: 648c2da31a48a9804dec14673d602583
# backtestId: d077aa2b8c1e824c7fb701827da90d2a
# title: 使用标普500 60日均线乖离度增加超额收益的策略

# -*- coding: utf-8 -*-
"""聚宽 Python 3 在线回测：标普500 MA60高乖离卖出、回落接回。

直接粘贴本文件即可，不需要上传任何数据文件。
信号与交易均使用513500 ETF，行情由聚宽get_price接口取得。
建议日频回测：2014-05-01起至平台可用日期，初始资金100000元。
使用ETF自身MA60，不能直接套用此前美国指数回测收益。
"""
from jqdata import *
import builtins as py_builtins
import math


def initialize(context):
    g.security = '513500.XSHG'   # 博时标普500ETF
    g.ma_window = 60
    g.sell_bias = 0.085         # +8.5%清仓；改为0.06可检验另一候选
    g.buy_bias = 0.045          # +4.5%及以下接回，包括所有负乖离
    g.commission = 0.001        # 单边0.1%，作为与本地研究一致的成本假设
    g.min_commission = 5        # 如需券商最低5元，可改为5
    g.target_invested = None
    g.last_trade_day = None
    g.daily_signal = None

    set_benchmark(g.security)
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_slippage(FixedSlippage(0))
    set_order_cost(OrderCost(
        open_tax=0, close_tax=0,
        open_commission=g.commission, close_commission=g.commission,
        close_today_commission=0, min_commission=g.min_commission
    ), type='fund')

    log.info('直接使用聚宽ETF日K。MA%d；买回<=%.2f%%，卖出>=%.2f%%；交易%s。'
             % (g.ma_window, g.buy_bias*100,
                g.sell_bias*100, g.security))
    run_daily(trade_at_open, time='09:30', reference_security=g.security)
    run_daily(log_after_close, time='15:30', reference_security=g.security)
    run_daily(log_premium_probe, time='09:31', reference_security=g.security)  # u-premium probe (observe-only)


def load_api_signal(context):
    """只取上一中国交易日及以前的60条完整日K，避免当日收盘未来数据。"""
    frame = get_price(g.security, end_date=context.previous_date,
                      count=g.ma_window, frequency='daily', fields=['close'],
                      skip_paused=True, fq='pre', panel=False)
    if frame is None or len(frame) < g.ma_window:
        return None
    frame = frame.sort_index()
    dates = [value.date() for value in frame.index]
    if len(set(dates)) != len(dates) or dates[-1] > context.previous_date:
        raise ValueError('行情返回重复日期或未来日期，停止回测。')
    if dates[-1] != context.previous_date:
        log.warn('ETF最新日K为%s，早于上一交易日%s，本日跳过信号。'
                 % (dates[-1], context.previous_date))
        return None
    closes = [float(value) for value in frame['close']]
    if not py_builtins.all(math.isfinite(value) and value > 0 for value in closes):
        log.warn('ETF历史收盘价存在空值或无效价格，本日跳过信号。')
        return None
    ma = math.fsum(closes[-g.ma_window:]) / g.ma_window
    close = closes[-1]
    signal_date = dates[-1]
    return {'date': signal_date, 'close': close, 'ma': ma, 'bias': close/ma-1}


def next_target(previous, bias, buy_bias, sell_bias):
    """两条阈值之间维持状态，边界包含等号。"""
    if bias >= sell_bias:
        return False
    if bias <= buy_bias:
        return True
    return previous


def affordable_lots(cash, price, commission, min_commission):
    """按100份取整，并给佣金留足资金；不额外留固定百分比现金。"""
    if not math.isfinite(price) or price <= 0 or cash <= min_commission:
        return 0
    lots = int(cash / (price*100*(1+commission)))
    while lots > 0:
        value = lots*100*price
        if value + py_builtins.max(value*commission, min_commission) <= cash:
            return lots*100
        lots -= 1
    return 0


def trade_at_open(context):
    today = context.current_dt.date()
    if g.last_trade_day == today:
        return
    g.last_trade_day = today
    g.daily_signal = load_api_signal(context)
    if g.daily_signal is None:
        log.info('%s：暂无完整有效的%d日ETF行情，本日不交易。' % (today, g.ma_window))
        return
    s = g.daily_signal
    position = context.portfolio.positions.get(g.security)
    amount = position.total_amount if position is not None else 0
    if g.target_invested is None:
        g.target_invested = amount > 0
    g.target_invested = next_target(g.target_invested, s['bias'],
                                    g.buy_bias, g.sell_bias)
    log.info('北京时间%s，信号日期%s，ETF收盘%.4f，MA60 %.4f，乖离%+.4f%%；'
             '目标%s，实际%d份。' % (today, s['date'], s['close'], s['ma'],
                                   s['bias']*100, '持仓' if g.target_invested else '空仓', amount))
    if (g.target_invested and amount > 0) or (not g.target_invested and amount == 0):
        return
    # 未完成委托期间不叠加下单；目标会在下一交易日用最新信号再判断。
    if py_builtins.any(o.security == g.security for o in get_open_orders().values()):
        log.warn('有未完成委托，本日不重复下单。')
        return
    current = get_current_data()[g.security]
    if current.paused:
        log.warn('ETF停牌或尚未上市，保留目标状态，下一交易日再检查。')
        return
    price = float(current.day_open)
    if not math.isfinite(price) or price <= 0:
        log.warn('ETF开盘价无效，本日不下单。')
        return
    if g.target_invested:
        if price >= current.high_limit:
            log.warn('ETF开盘涨停，暂不买入。')
            return
        shares = affordable_lots(context.portfolio.available_cash, price,
                                 g.commission, g.min_commission)
        if shares == 0:
            log.info('可用资金不足买入100份并支付佣金。')
            return
        result = order(g.security, shares)
        log.info('提交买入%d份，开盘参考价%.4f，委托返回%s。'
                 % (shares, price, result))
    else:
        if price <= current.low_limit:
            log.warn('ETF开盘跌停，暂不卖出。')
            return
        if position.closeable_amount <= 0:
            log.warn('持仓暂不可卖，下一交易日再检查。')
            return
        result = order_target_value(g.security, 0)
        log.info('提交清仓，开盘参考价%.4f，委托返回%s。' % (price, result))
    if result is None:
        log.warn('没有创建有效委托，请检查聚宽订单日志。目标状态不代表成交。')


def log_after_close(context):
    position = context.portfolio.positions.get(g.security)
    amount = position.total_amount if position is not None else 0
    if g.daily_signal is not None:
        record(etf_bias_pct=g.daily_signal['bias']*100,
               sell_threshold_pct=g.sell_bias*100,
               buy_threshold_pct=g.buy_bias*100,
               invested=1 if amount > 0 else 0)
    for trade in get_trades().values():
        log.info('实际成交：%s' % trade)
    log.info('收盘资产%.2f元，可用现金%.2f元，ETF持仓%d份。'
             % (context.portfolio.total_value, context.portfolio.available_cash, amount))


# ===== u-premium probe (observe-only; no orders, no state the book reads) =====
def log_premium_probe(context):
    try:
        today = context.current_dt.date()
        s = g.daily_signal
        nav = get_extras('unit_net_value', [g.security], end_date=context.previous_date, count=62)
        col = nav[g.security].dropna()
        if len(col) == 0:
            log.info('PREM %s NONAV' % today)
            return
        nav_date = col.index[-1].date()
        nav_last = float(col.iloc[-1])
        tail = [float(v) for v in col.iloc[-60:]]
        nav_ma = math.fsum(tail) / len(tail)
        navbias = nav_last / nav_ma - 1
        if s is not None:
            close = s['close']
            sig_date = s['date']
            pbias = s['bias']
        else:
            close = float('nan')
            sig_date = None
            pbias = float('nan')
        premium = close / nav_last - 1
        log.info('PREM %s %s %.4f %s %.4f %+.6f %.4f %+.6f %d %+.6f'
                 % (today, sig_date, close, nav_date, nav_last, premium, nav_ma, navbias, len(tail), pbias))
    except Exception as e:
        log.info('PREM %s ERR %s' % (context.current_dt.date(), e))


# ===== AUTORESEARCH NORMALIZATION OVERRIDE (appended; strategies/ file untouched) =====
# harness/harness.md §2 — force the frozen execution settings regardless of what the
# raw strategy sets, even if it re-sets costs every bar. Values are pinned in
# harness/config/epoch-<n>.json; utils/harness-config.js --verify checks this block
# still matches, because Python running on JQ's servers cannot read that JSON.
__jq_set_slippage = set_slippage
def set_slippage(*a, **k):
    __jq_set_slippage(FixedSlippage(0))
__jq_set_commission = set_commission
def set_commission(*a, **k):
    __jq_set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
# epoch 4: set_commission does NOT govern funds, so 170 held strategies were running
# ETF trades on their own costs. Pin the fund table too, and neutralise re-sets.
# epoch 6: it does not govern STOCKS either. JQ deprecated set_commission in favour of
# set_order_cost, so a strategy's own type='stock' call won outright and 95 of 215 held
# strategies were being charged their AUTHOR's fees. Measured by probe: a 5%/side stock
# commission injected into int-001 moved total return +64.44% -> -11.33% (-75.77pp), i.e.
# the bench had no control over stock fees at all. Both tables are now pinned, and the
# fall-through forwards only the types we do not model (futures, mmf, ...).
# Guarded: unlike set_slippage/set_commission, set_order_cost is NOT bound at module
# scope in every JQ runtime — rebinding it unguarded raised NameError at import and
# the whole strategy came back compile-error.
try:
    __jq_set_order_cost = set_order_cost
    def __jq_cost_type(a, k):
        t = k.get('type')
        if t is None and len(a) > 1:
            t = a[1]
        return t
    def set_order_cost(*a, **k):
        __t = __jq_cost_type(a, k)
        if __t == 'fund':
            __jq_set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0, min_commission=5), type='fund')
        elif __t == 'stock':
            __jq_set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0.001, min_commission=5), type='stock')
        else:
            __jq_set_order_cost(*a, **k)
except NameError:
    pass
try:
    __jq_orig_initialize = initialize
    def initialize(context):
        __jq_orig_initialize(context)
        set_option('use_real_price', True)
        # epoch 4 pins, applied AFTER the strategy's own initialize so they win
        set_option('avoid_future_data', True)
        set_option('order_volume_ratio', 0.05)
        set_slippage(FixedSlippage(0))
        set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
        try:
            set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0, min_commission=5), type='fund')
        except Exception:
            pass
        # epoch 6: pin the stock table too, AFTER the strategy's own initialize so it wins
        # even when the strategy set its costs there rather than at module scope.
        try:
            set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0.001, min_commission=5), type='stock')
        except Exception:
            pass
except NameError:
    pass
# ===== END OVERRIDE =====
