# Clone from JoinQuant
# postId: 1a3789bf86cd8ccae6f7cbcf8234f3de
# backtestId: 99f3f684ec1eeff914657b5b2e1434f7
# title: 上升趋势策略 ：少交易、试仓确认、盈利后加仓、趋势破坏退出

# -*- coding: utf-8 -*-
from jqdata import *
import numpy as np


def initialize(context):
    """
    上升趋势单票策略 V3：少交易 + 先小仓试错 + 失败快速止损 + 盈利后跟踪止盈
    """

    # ===== 基础设置 =====
    g.benchmark_index = '000985.XSHG'
    set_benchmark(g.benchmark_index)
    set_option('use_real_price', True)

    try:
        set_option('avoid_future_data', True)
    except:
        pass

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

    set_slippage(PriceRelatedSlippage(0.002))
    log.set_level('order', 'error')

    # ===== 股票池参数 =====
    # 只测试指定票时可填写，例如：
    # g.custom_pool = ['603929.XSHG', '600522.XSHG', '002432.XSHE', '600219.XSHG']
    g.custom_pool = []

    g.enable_gem = True
    g.enable_star = False
    g.enable_bj = False

    g.max_scan_n = 900
    g.min_list_days = 250

    # 市值过滤，单位：亿元
    g.min_market_cap = 30
    g.max_market_cap = 2500

    # 流动性过滤
    g.min_turnover_ratio = 0.7
    g.min_avg_money_20 = 120000000

    # ===== 趋势选股参数 =====
    g.lookback = 160
    g.min_bars = 130

    # 有趋势，但不能已经极端透支
    g.min_ret_60 = 0.14
    g.min_ret_120 = 0.18
    g.min_relative_60 = 0.08
    g.max_ret_60 = 1.20
    g.max_ret_20 = 0.55
    g.max_ret_10 = 0.28
    g.max_price_ma20_ratio = 1.16
    g.max_price_ma60_ratio = 1.55

    # ATR 波动率过滤，太妖的票不做
    g.min_atr_ratio = 0.025
    g.max_atr_ratio = 0.115

    # ===== 仓位参数 =====
    g.probe_position = 0.35       # 初始试仓
    g.core_position = 0.65        # 走出来后的核心仓
    g.strong_position = 0.82      # 盈利突破后的强仓
    g.risk_position = 0.35        # 软风险仓位
    g.max_position = 0.85

    # ===== 交易频率控制 =====
    g.empty_cooldown_days = 5
    g.add_cooldown_days = 3
    g.reduce_cooldown_days = 3
    g.min_rebalance_gap = 0.12

    # ===== 止损 / 趋势结束参数 =====
    g.quick_stop_loss = -0.075
    g.quick_stop_days = 8
    g.quick_stop_ma20_break = 0.965

    g.trend_stop_ma60_break = 0.985
    g.trend_stop_ma30_break_days = 3
    g.high_drawdown_stop = -0.14
    g.high_drawdown_big_profit = -0.11

    # K 线风险
    g.big_down_pct = -0.07
    g.upper_shadow_ratio = 0.45
    g.heavy_volume_ratio = 1.25

    # 大盘过滤只限制新开仓，不强制卖已有持仓
    g.use_market_filter = True

    # ===== 状态变量 =====
    g.hold_stock = None
    g.hold_start_date = None
    g.hold_high_close = 0.0
    g.hold_high_date = None
    g.entry_price = 0.0
    g.max_profit = 0.0
    g.last_add_date = None
    g.last_reduce_date = None
    g.last_clear_date = None
    g.last_action_date = None
    g.last_candidates = []
    g.last_signal = None

    # ===== 定时任务 =====
    run_daily(trade_morning, time='09:40')
    run_daily(intraday_risk_control, time='14:50')
    run_daily(after_market_log, time='after_close')


# =========================================================
# 主交易逻辑
# =========================================================

def trade_morning(context):
    """
    早盘逻辑：
    1. 有持仓，只管理当前持仓，不排名换股。
    2. 空仓，满足冷却 + 大盘过滤后才选股。
    3. 新买先试仓，盈利确认后再加仓。
    """

    sync_hold_state(context)
    stock = get_current_holding(context)

    # ===== 有持仓：只管这只票 =====
    if stock:
        signal = calc_stock_signal(stock, context, for_hold=True)
        g.last_signal = signal

        if signal is None:
            log.info('持仓票数据不足，暂不处理：%s' % stock)
            return

        update_hold_tracking(signal, context)
        hold_days = get_hold_days(context)

        if signal.get('hard_exit', False):
            log.info('趋势/买点失败，清仓：%s，持仓天数：%s，原因：%s' %
                     (stock, hold_days, signal.get('reason', '')))
            order_to_target_percent(context, stock, 0.0, '清仓：' + signal.get('reason', ''), force=True)
            clear_hold_state(context)
            return

        target_pct = calc_hold_target_percent(signal, context)
        order_to_target_percent(context, stock, target_pct, signal.get('reason', '趋势持有'), force=False)
        return

    # ===== 空仓：冷却期不买 =====
    if in_empty_cooldown(context):
        log.info('清仓后冷却期，暂不开新仓')
        return

    # ===== 大盘弱，不新开 =====
    if g.use_market_filter and not market_ok_for_open(context):
        log.info('大盘环境偏弱，暂不开新仓')
        return

    # ===== 只在空仓时选股 =====
    candidates = select_candidates(context)
    g.last_candidates = candidates[:10]

    if len(candidates) == 0:
        log.info('今日无合格趋势候选')
        return

    best = candidates[0]
    best_stock = best['stock']

    if not can_buy(best_stock):
        log.info('候选第一无法买入，可能涨停/停牌/ST：%s' % best_stock)
        return

    log.info('新开试仓：%s，分数 %.2f，状态 %s，原因 %s' %
             (best_stock, best['score'], best['state'], best['reason']))

    order_to_target_percent(context, best_stock, g.probe_position, '新开趋势试仓', force=True)
    mark_new_holding(best_stock, best, context)


# =========================================================
# 盘中风控：只做硬风险，不频繁做T
# =========================================================

def intraday_risk_control(context):
    stock = get_current_holding(context)
    if not stock:
        return

    if not can_sell(stock):
        return

    today = context.current_dt.strftime('%Y-%m-%d')
    start_dt = today + ' 09:30:00'
    end_dt = context.current_dt

    try:
        mdf = get_price(
            stock,
            start_date=start_dt,
            end_date=end_dt,
            frequency='1m',
            fields=['open', 'close', 'high', 'low', 'money'],
            fq='pre'
        )
    except Exception as e:
        log.info('盘中数据获取失败：%s，%s' % (stock, str(e)))
        return

    if mdf is None or len(mdf) < 20:
        return

    hist = get_daily_history(stock, count=90)
    if hist is None or len(hist) < 70:
        return

    day_open = float(mdf['open'].iloc[0])
    last_price = float(mdf['close'].iloc[-1])
    day_high = float(mdf['high'].max())
    day_low = float(mdf['low'].min())
    prev_close = float(hist['close'].iloc[-1])

    close = hist['close']
    ma20 = float(close.rolling(20).mean().iloc[-1])
    ma30 = float(close.rolling(30).mean().iloc[-1])
    ma60 = float(close.rolling(60).mean().iloc[-1])

    day_ret = last_price / prev_close - 1
    open_ret = last_price / day_open - 1 if day_open > 0 else 0

    entry_ret = 0.0
    try:
        pos = context.portfolio.positions[stock]
        if pos.avg_cost > 0:
            entry_ret = last_price / float(pos.avg_cost) - 1
    except:
        pass

    # 买入后亏损过大，直接认错
    if entry_ret <= g.quick_stop_loss:
        log.info('盘中触发买错止损：%s，入场收益 %.2f%%' % (stock, entry_ret * 100))
        order_to_target_percent(context, stock, 0.0, '盘中买错止损', force=True)
        clear_hold_state(context)
        return

    # 大阴线打穿 MA30
    if day_ret <= -0.085 and last_price < ma30:
        log.info('盘中大阴破 MA30，清仓：%s，盘中跌幅 %.2f%%' % (stock, day_ret * 100))
        order_to_target_percent(context, stock, 0.0, '盘中大阴破位', force=True)
        clear_hold_state(context)
        return

    # 跌破 MA60
    if last_price < ma60 * 0.975:
        log.info('盘中跌破 MA60，清仓：%s' % stock)
        order_to_target_percent(context, stock, 0.0, '盘中跌破MA60', force=True)
        clear_hold_state(context)
        return

    # 软风险，只降一次，不频繁做T
    amplitude = max(day_high - day_low, 0.01)
    upper_shadow = (day_high - max(day_open, last_price)) / amplitude
    current_pct = get_position_percent(context, stock)

    today_money = float(mdf['money'].sum())
    avg_money_20 = float(hist['money'].tail(20).mean())
    money_ratio = today_money / avg_money_20 if avg_money_20 > 0 else 1

    long_upper = upper_shadow >= g.upper_shadow_ratio and last_price <= day_high * 0.955 and money_ratio >= 1.15
    big_down = day_ret <= g.big_down_pct or open_ret <= -0.06

    if (big_down or long_upper) and current_pct > g.risk_position + 0.12 and reduce_cooldown_ok(context):
        log.info('盘中软风险降仓：%s，跌幅 %.2f%%，上影 %.2f，量比 %.2f' %
                 (stock, day_ret * 100, upper_shadow, money_ratio))
        order_to_target_percent(context, stock, g.risk_position, '盘中软风险降仓', force=True)
        g.last_reduce_date = context.current_dt.date()


# =========================================================
# 选股
# =========================================================

def select_candidates(context):
    universe = get_base_universe(context)
    if not universe:
        return []

    index_ret_60 = calc_index_ret_60(context)
    results = []

    for stock in universe:
        if not can_scan_stock(stock):
            continue

        signal = calc_stock_signal(stock, context, index_ret_60=index_ret_60, for_hold=False)
        if signal is None:
            continue

        if signal.get('qualified', False) and not signal.get('hard_exit', False):
            if can_buy(stock):
                results.append(signal)

    results = sorted(results, key=lambda x: x['score'], reverse=True)
    return results


def get_base_universe(context):
    if g.custom_pool and len(g.custom_pool) > 0:
        return g.custom_pool

    try:
        securities = get_all_securities(types=['stock'], date=context.previous_date)
        stocks = list(securities.index)
    except Exception as e:
        log.info('获取全市场股票失败：%s' % str(e))
        return []

    filtered = []
    for stock in stocks:
        code = stock.split('.')[0]

        if not g.enable_star and code.startswith('688'):
            continue
        if not g.enable_bj and (stock.endswith('.BJ') or stock.endswith('.XBEI') or code.startswith('8') or code.startswith('4')):
            continue
        if not g.enable_gem and code.startswith('300'):
            continue

        try:
            info = get_security_info(stock)
            if info is None:
                continue
            list_days = (context.previous_date - info.start_date).days
            if list_days < g.min_list_days:
                continue
        except:
            continue

        filtered.append(stock)

    try:
        q = query(
            valuation.code,
            valuation.market_cap,
            valuation.turnover_ratio
        ).filter(
            valuation.code.in_(filtered),
            valuation.market_cap >= g.min_market_cap,
            valuation.market_cap <= g.max_market_cap,
            valuation.turnover_ratio >= g.min_turnover_ratio
        ).order_by(
            valuation.turnover_ratio.desc()
        ).limit(
            g.max_scan_n
        )

        df = get_fundamentals(q, date=context.previous_date)
        if df is not None and len(df) > 0:
            return list(df['code'])
    except Exception as e:
        log.info('基本面过滤失败，使用原始股票池截断：%s' % str(e))

    return filtered[:g.max_scan_n]


# =========================================================
# 单股信号
# =========================================================

def calc_stock_signal(stock, context, index_ret_60=None, for_hold=False):
    df = get_daily_history(stock, count=g.lookback)
    if df is None or len(df) < g.min_bars:
        return None

    close = df['close']
    open_ = df['open']
    high = df['high']
    low = df['low']
    volume = df['volume']
    money = df['money']

    last = float(close.iloc[-1])
    prev = float(close.iloc[-2])
    if last <= 0 or prev <= 0:
        return None

    ma5 = close.rolling(5).mean()
    ma10 = close.rolling(10).mean()
    ma20 = close.rolling(20).mean()
    ma30 = close.rolling(30).mean()
    ma60 = close.rolling(60).mean()
    ma120 = close.rolling(120).mean()

    if np.isnan(ma120.iloc[-1]):
        return None

    ma5_v = float(ma5.iloc[-1])
    ma10_v = float(ma10.iloc[-1])
    ma20_v = float(ma20.iloc[-1])
    ma30_v = float(ma30.iloc[-1])
    ma60_v = float(ma60.iloc[-1])
    ma120_v = float(ma120.iloc[-1])

    ma20_5ago = float(ma20.iloc[-6])
    ma30_5ago = float(ma30.iloc[-6])
    ma60_20ago = float(ma60.iloc[-21])
    ma120_20ago = float(ma120.iloc[-21])

    ret5 = last / float(close.iloc[-6]) - 1
    ret10 = last / float(close.iloc[-11]) - 1
    ret20 = last / float(close.iloc[-21]) - 1
    ret60 = last / float(close.iloc[-61]) - 1
    ret120 = last / float(close.iloc[-121]) - 1

    high20 = float(high.tail(20).max())
    high60 = float(high.tail(60).max())
    high120 = float(high.tail(120).max())
    low60 = float(low.tail(60).min())

    drawdown_20_high = last / high20 - 1
    drawdown_60_high = last / high60 - 1
    drawdown_120_high = last / high120 - 1
    pos_60 = (last - low60) / max(high60 - low60, 0.01)

    avg_money_20 = float(money.tail(20).mean())
    avg_money_60 = float(money.tail(60).mean())
    avg_vol_20 = float(volume.tail(20).mean())
    vol_ratio = float(volume.iloc[-1]) / avg_vol_20 if avg_vol_20 > 0 else 1

    atr_ratio = calc_atr_ratio(df, n=14)

    last_open = float(open_.iloc[-1])
    last_high = float(high.iloc[-1])
    last_low = float(low.iloc[-1])
    day_ret = last / prev - 1
    open_close_ret = last / last_open - 1 if last_open > 0 else 0
    amplitude = max(last_high - last_low, 0.01)
    upper_shadow = (last_high - max(last_open, last)) / amplitude

    big_bear = (day_ret <= g.big_down_pct or open_close_ret <= -0.065) and vol_ratio >= 1.10
    long_upper = upper_shadow >= g.upper_shadow_ratio and last <= last_high * 0.955 and vol_ratio >= 1.15

    below_ma20_days = count_condition(close.tail(3), ma20.tail(3), '<')
    below_ma30_days = count_condition(close.tail(3), ma30.tail(3), '<')

    if index_ret_60 is None:
        index_ret_60 = calc_index_ret_60(context)
    relative_60 = ret60 - index_ret_60

    hold_drawdown = drawdown_60_high
    entry_ret = 0.0
    max_profit = 0.0

    if for_hold:
        if g.hold_high_close and g.hold_high_close > 0:
            hold_drawdown = last / g.hold_high_close - 1
        try:
            pos = context.portfolio.positions[stock]
            if pos.avg_cost > 0:
                entry_ret = last / float(pos.avg_cost) - 1
                max_profit = max(g.max_profit, g.hold_high_close / float(pos.avg_cost) - 1) if g.hold_high_close > 0 else g.max_profit
        except:
            pass

    hold_days = get_hold_days(context) if for_hold else 0

    # ===== 趋势结构 =====
    ma_bull = (
        last > ma20_v * 0.985 and
        ma20_v > ma60_v * 1.015 and
        ma60_v > ma120_v * 0.98
    )

    slope_good = (
        ma20_v > ma20_5ago and
        ma30_v > ma30_5ago and
        ma60_v > ma60_20ago * 1.003
    )

    strong_return = (
        ret60 >= g.min_ret_60 and
        ret120 >= g.min_ret_120 and
        relative_60 >= g.min_relative_60
    )

    not_extreme_return = (
        ret60 <= g.max_ret_60 and
        ret20 <= g.max_ret_20 and
        ret10 <= g.max_ret_10
    )

    not_far_from_ma = (
        last <= ma20_v * g.max_price_ma20_ratio and
        last <= ma60_v * g.max_price_ma60_ratio
    )

    liquid = avg_money_20 >= g.min_avg_money_20
    volatility_ok = g.min_atr_ratio <= atr_ratio <= g.max_atr_ratio

    # 买点结构：回踩修复 / 平台突破
    recent_touch_ma20 = float(low.tail(12).min()) <= ma20_v * 1.04
    recent_close_near_ma20 = float(close.tail(12).min()) <= ma20_v * 1.07
    recent_pullback = recent_touch_ma20 or recent_close_near_ma20

    last_20_range = (float(high.tail(20).max()) - float(low.tail(20).min())) / max(last, 0.01)

    platform_breakout = (
        last >= high20 * 0.985 and
        vol_ratio >= 1.03 and
        ret10 <= 0.22 and
        last_20_range <= 0.42 and
        not long_upper and
        day_ret < 0.085
    )

    pullback_repair = (
        recent_pullback and
        last > ma20_v and
        last > ma10_v * 0.985 and
        day_ret > -0.025 and
        ret5 > -0.08 and
        not big_bear and
        not long_upper
    )

    trend_hold_ok = (
        last > ma20_v and
        drawdown_60_high >= -0.13 and
        pos_60 >= 0.58 and
        day_ret < 0.085 and
        not big_bear and
        not long_upper
    )

    candle_ok = not big_bear and not long_upper and day_ret < 0.085

    qualified = (
        ma_bull and
        slope_good and
        strong_return and
        not_extreme_return and
        not_far_from_ma and
        liquid and
        volatility_ok and
        candle_ok and
        (pullback_repair or platform_breakout or trend_hold_ok)
    )

    # ===== 硬退出 =====
    hard_reasons = []
    ma20_down = ma20_v < ma20_5ago

    if for_hold:
        if entry_ret <= g.quick_stop_loss:
            hard_reasons.append('买入后亏损超过%.1f%%' % (abs(g.quick_stop_loss) * 100))

        if hold_days <= g.quick_stop_days and last < ma20_v * g.quick_stop_ma20_break:
            hard_reasons.append('新开仓后快速跌破MA20')

        if max_profit >= 0.16 and hold_drawdown <= g.high_drawdown_big_profit and last < ma20_v:
            hard_reasons.append('盈利后回撤过大且跌破MA20')

        if hold_drawdown <= g.high_drawdown_stop and last < ma30_v:
            hard_reasons.append('持仓高点回撤过大且跌破MA30')

    if last < ma60_v * g.trend_stop_ma60_break and ma20_down:
        hard_reasons.append('跌破MA60且MA20下行')

    if ma20_v < ma60_v and last < ma60_v:
        hard_reasons.append('MA20跌破MA60')

    if last < ma120_v * 0.985:
        hard_reasons.append('跌破MA120')

    if below_ma30_days >= g.trend_stop_ma30_break_days and ma20_down:
        hard_reasons.append('连续跌破MA30且MA20转弱')

    if big_bear and last < ma20_v:
        hard_reasons.append('放量大阴跌破MA20')

    hard_exit = len(hard_reasons) > 0

    # ===== 软风险 =====
    soft_reasons = []

    if big_bear:
        soft_reasons.append('大阴线')
    if long_upper:
        soft_reasons.append('长上影')
    if below_ma20_days >= 2 and last < ma20_v:
        soft_reasons.append('连续跌破MA20')
    if for_hold and hold_drawdown <= -0.09 and last < ma20_v:
        soft_reasons.append('持仓高点回撤超过9%且破MA20')
    if ret10 > 0.26 or last > ma20_v * 1.18:
        soft_reasons.append('短线过热')

    soft_risk = len(soft_reasons) > 0

    if hard_exit:
        state = 'dead'
        reason = '；'.join(hard_reasons)
    elif pullback_repair:
        state = 'pullback_repair'
        reason = '回踩MA20附近后修复'
    elif platform_breakout:
        state = 'platform_breakout'
        reason = '平台突破'
    elif soft_risk:
        state = 'risk'
        reason = '；'.join(soft_reasons)
    else:
        state = 'trend_hold'
        reason = '趋势保持'

    # ===== 打分 =====
    score = 0.0
    score += min(max(ret60, 0), 0.9) * 120
    score += min(max(ret120, 0), 1.4) * 50
    score += min(max(relative_60, 0), 0.9) * 130
    score += min(max(ma20_v / ma60_v - 1, 0), 0.30) * 150
    score += min(max(ma60_v / ma120_v - 1, 0), 0.35) * 90
    score += pos_60 * 25

    if avg_money_20 > avg_money_60:
        score += 8
    if pullback_repair:
        score += 28
    if platform_breakout:
        score += 20
    if recent_pullback:
        score += 12

    ma20_gap = last / ma20_v - 1
    if ma20_gap > 0.10:
        score -= (ma20_gap - 0.10) * 180

    if ret60 > 0.80:
        score -= (ret60 - 0.80) * 50
    if ret20 > 0.35:
        score -= (ret20 - 0.35) * 80
    if atr_ratio > 0.09:
        score -= (atr_ratio - 0.09) * 300
    if big_bear:
        score -= 50
    if long_upper:
        score -= 40
    if drawdown_120_high < -0.20:
        score -= 25

    return {
        'stock': stock,
        'qualified': qualified,
        'score': score,
        'state': state,
        'reason': reason,
        'hard_exit': hard_exit,
        'soft_risk': soft_risk,
        'pullback_repair': pullback_repair,
        'platform_breakout': platform_breakout,
        'last': last,
        'ma5': ma5_v,
        'ma10': ma10_v,
        'ma20': ma20_v,
        'ma30': ma30_v,
        'ma60': ma60_v,
        'ma120': ma120_v,
        'ret5': ret5,
        'ret10': ret10,
        'ret20': ret20,
        'ret60': ret60,
        'ret120': ret120,
        'relative_60': relative_60,
        'drawdown_20_high': drawdown_20_high,
        'drawdown_60_high': drawdown_60_high,
        'drawdown_120_high': drawdown_120_high,
        'hold_drawdown': hold_drawdown,
        'entry_ret': entry_ret,
        'max_profit': max_profit,
        'vol_ratio': vol_ratio,
        'avg_money_20': avg_money_20,
        'atr_ratio': atr_ratio,
        'big_bear': big_bear,
        'long_upper': long_upper,
        'below_ma20_days': below_ma20_days,
        'below_ma30_days': below_ma30_days,
    }


# =========================================================
# 仓位控制
# =========================================================

def calc_hold_target_percent(signal, context):
    stock = signal['stock']
    current_pct = get_position_percent(context, stock)
    entry_ret = signal.get('entry_ret', 0.0)
    max_profit = signal.get('max_profit', 0.0)

    if signal.get('hard_exit', False):
        return 0.0

    # 软风险只降仓
    if signal.get('soft_risk', False):
        return g.risk_position

    # 没赚钱之前，不加仓
    if entry_ret < 0.03:
        return min(current_pct if current_pct > 0 else g.probe_position, g.probe_position)

    # 有 3% 以上浮盈，且站稳 MA20，加到核心仓
    if entry_ret >= 0.03 and signal['last'] > signal['ma20']:
        target = g.core_position
    else:
        target = g.probe_position

    # 有 8% 以上浮盈，或者平台突破，再加到强仓
    if entry_ret >= 0.08 and (signal.get('platform_breakout', False) or signal['last'] > signal['ma10']):
        target = g.strong_position

    # 曾经盈利较多但已经回撤，先降回核心仓
    if max_profit >= 0.18 and signal.get('hold_drawdown', 0) <= -0.08:
        target = min(target, g.core_position)

    return target


def order_to_target_percent(context, stock, target_pct, reason='', force=False):
    if target_pct < 0:
        target_pct = 0.0
    if target_pct > g.max_position:
        target_pct = g.max_position

    current_pct = get_position_percent(context, stock)

    if not force:
        if abs(target_pct - current_pct) < g.min_rebalance_gap:
            return

        if target_pct > current_pct and not add_cooldown_ok(context):
            return

        if target_pct < current_pct and not reduce_cooldown_ok(context):
            return

    if target_pct > current_pct and not can_buy(stock):
        log.info('无法买入：%s，原因：%s' % (stock, reason))
        return

    if target_pct < current_pct and not can_sell(stock):
        log.info('无法卖出：%s，原因：%s' % (stock, reason))
        return

    target_value = context.portfolio.total_value * target_pct
    log.info('调仓：%s，当前 %.0f%% -> 目标 %.0f%%，原因：%s' %
             (stock, current_pct * 100, target_pct * 100, reason))

    order_target_value(stock, target_value)

    today = context.current_dt.date()
    g.last_action_date = today

    if target_pct > current_pct:
        g.last_add_date = today
    elif target_pct < current_pct:
        g.last_reduce_date = today


# =========================================================
# 状态管理
# =========================================================

def sync_hold_state(context):
    stock = get_current_holding(context)

    if stock != g.hold_stock:
        g.hold_stock = stock

        if stock:
            g.hold_start_date = context.current_dt.date()
            signal = calc_stock_signal(stock, context, for_hold=True)
            if signal:
                g.hold_high_close = signal.get('last', 0.0)
                g.hold_high_date = context.previous_date
                g.entry_price = signal.get('last', 0.0)
            else:
                g.hold_high_close = 0.0
                g.hold_high_date = None
                g.entry_price = 0.0
            g.max_profit = 0.0
        else:
            g.hold_start_date = None
            g.hold_high_close = 0.0
            g.hold_high_date = None
            g.entry_price = 0.0
            g.max_profit = 0.0


def mark_new_holding(stock, signal, context):
    g.hold_stock = stock
    g.hold_start_date = context.current_dt.date()
    g.hold_high_close = signal.get('last', 0.0)
    g.hold_high_date = context.previous_date
    g.entry_price = signal.get('last', 0.0)
    g.max_profit = 0.0
    g.last_add_date = context.current_dt.date()
    g.last_action_date = context.current_dt.date()


def clear_hold_state(context):
    g.hold_stock = None
    g.hold_start_date = None
    g.hold_high_close = 0.0
    g.hold_high_date = None
    g.entry_price = 0.0
    g.max_profit = 0.0
    g.last_clear_date = context.current_dt.date()
    g.last_action_date = context.current_dt.date()


def update_hold_tracking(signal, context):
    last = signal.get('last', 0.0)
    if last and last > g.hold_high_close:
        g.hold_high_close = last
        g.hold_high_date = context.previous_date

    try:
        stock = signal['stock']
        pos = context.portfolio.positions[stock]
        if pos.avg_cost > 0:
            profit = last / float(pos.avg_cost) - 1
            if profit > g.max_profit:
                g.max_profit = profit
    except:
        pass


def get_hold_days(context):
    if g.hold_start_date is None:
        return 0
    return count_trade_days(g.hold_start_date, context.previous_date)


def count_trade_days(start_date, end_date):
    try:
        if start_date is None or end_date is None:
            return 0
        if start_date > end_date:
            return 0
        days = get_trade_days(start_date=start_date, end_date=end_date)
        return len(days)
    except:
        return 0


def in_empty_cooldown(context):
    if g.last_clear_date is None:
        return False
    days = count_trade_days(g.last_clear_date, context.previous_date)
    return days < g.empty_cooldown_days


def add_cooldown_ok(context):
    if g.last_add_date is None:
        return True
    days = count_trade_days(g.last_add_date, context.previous_date)
    return days >= g.add_cooldown_days


def reduce_cooldown_ok(context):
    if g.last_reduce_date is None:
        return True
    days = count_trade_days(g.last_reduce_date, context.previous_date)
    return days >= g.reduce_cooldown_days


# =========================================================
# 大盘过滤
# =========================================================

def market_ok_for_open(context):
    try:
        df = attribute_history(
            g.benchmark_index,
            130,
            unit='1d',
            fields=['close'],
            skip_paused=True,
            df=True,
            fq='pre'
        )
        if df is None or len(df) < 120:
            return True

        close = df['close']
        last = float(close.iloc[-1])
        ma20 = float(close.rolling(20).mean().iloc[-1])
        ma60 = float(close.rolling(60).mean().iloc[-1])
        ma120 = float(close.rolling(120).mean().iloc[-1])
        ma20_5ago = float(close.rolling(20).mean().iloc[-6])

        if last > ma60 and ma20 >= ma20_5ago:
            return True
        if last > ma20 and ma20 > ma60:
            return True
        if last > ma120 and ma20 > ma60:
            return True

        return False
    except:
        return True


def calc_index_ret_60(context):
    try:
        df = attribute_history(
            g.benchmark_index,
            70,
            unit='1d',
            fields=['close'],
            skip_paused=True,
            df=True,
            fq='pre'
        )
        if df is None or len(df) < 61:
            return 0.0
        return float(df['close'].iloc[-1] / df['close'].iloc[-61] - 1)
    except:
        return 0.0


# =========================================================
# 通用函数
# =========================================================

def get_daily_history(stock, count=160):
    try:
        df = attribute_history(
            stock,
            count,
            unit='1d',
            fields=['open', 'close', 'high', 'low', 'volume', 'money'],
            skip_paused=True,
            df=True,
            fq='pre'
        )
        if df is None or len(df) == 0:
            return None
        return df.dropna()
    except Exception as e:
        log.info('获取日线失败：%s，%s' % (stock, str(e)))
        return None


def calc_atr_ratio(df, n=14):
    try:
        high = df['high']
        low = df['low']
        close = df['close']
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = abs(high - prev_close)
        tr3 = abs(low - prev_close)
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        atr = tr.rolling(n).mean().iloc[-1]
        last = close.iloc[-1]
        if last <= 0:
            return 0.0
        return float(atr / last)
    except:
        return 0.0


def get_current_holding(context):
    positions = []
    for stock, pos in context.portfolio.positions.items():
        if pos.total_amount > 0:
            positions.append((stock, pos.value))

    if len(positions) == 0:
        return None

    positions = sorted(positions, key=lambda x: x[1], reverse=True)
    main_stock = positions[0][0]

    if len(positions) > 1:
        for stock, value in positions[1:]:
            if can_sell(stock):
                log.info('清理多余持仓：%s' % stock)
                order_target_value(stock, 0)

    return main_stock


def get_position_percent(context, stock):
    try:
        if stock in context.portfolio.positions:
            value = context.portfolio.positions[stock].value
            total = context.portfolio.total_value
            if total > 0:
                return value / total
        return 0.0
    except:
        return 0.0


def can_scan_stock(stock):
    try:
        cd = get_current_data()[stock]
        if cd.paused:
            return False
        if cd.is_st:
            return False
        name = cd.name
        if 'ST' in name or '*' in name or '退' in name:
            return False
        if cd.last_price is None or cd.last_price <= 0:
            return False
        return True
    except:
        return False


def can_buy(stock):
    try:
        cd = get_current_data()[stock]
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
        if price >= cd.high_limit * 0.995:
            return False
        return True
    except:
        return False


def can_sell(stock):
    try:
        cd = get_current_data()[stock]
        if cd.paused:
            return False
        price = cd.last_price
        if price is None or price <= 0:
            return False
        if price <= cd.low_limit * 1.005:
            return False
        return True
    except:
        return False


def count_condition(series_a, series_b, op):
    cnt = 0
    try:
        for a, b in zip(series_a, series_b):
            if op == '<' and float(a) < float(b):
                cnt += 1
            elif op == '>' and float(a) > float(b):
                cnt += 1
    except:
        pass
    return cnt


# =========================================================
# 日志
# =========================================================

def after_market_log(context):
    stock = get_current_holding(context)
    log.info('========== 上升趋势单票 V3 收盘日志 =========')

    if stock and g.last_signal:
        s = g.last_signal
        hold_days = get_hold_days(context)
        log.info('当前持仓：%s | 持仓天数：%s | 状态：%s | 原因：%s | 入场收益：%.2f%% | 最大盈利：%.2f%% | 高点回撤：%.2f%% | 60日涨幅：%.2f%% | ATR：%.2f%%' %
                 (
                     stock,
                     hold_days,
                     s.get('state', ''),
                     s.get('reason', ''),
                     s.get('entry_ret', 0) * 100,
                     g.max_profit * 100,
                     s.get('hold_drawdown', 0) * 100,
                     s.get('ret60', 0) * 100,
                     s.get('atr_ratio', 0) * 100
                 ))
        return

    if not g.last_candidates:
        log.info('当前空仓，今日无候选')
        return

    log.info('空仓候选 TOP10：')
    for i, item in enumerate(g.last_candidates):
        log.info('%d. %s | 分数 %.2f | 状态 %s | 原因 %s | 60日涨幅 %.2f%% | 回撤 %.2f%% | MA20偏离 %.2f%% | ATR %.2f%%' %
                 (
                     i + 1,
                     item['stock'],
                     item['score'],
                     item['state'],
                     item['reason'],
                     item['ret60'] * 100,
                     item['drawdown_60_high'] * 100,
                     (item['last'] / item['ma20'] - 1) * 100,
                     item['atr_ratio'] * 100
                 ))