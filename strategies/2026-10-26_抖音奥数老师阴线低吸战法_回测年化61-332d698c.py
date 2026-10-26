# Clone from JoinQuant
# postId: 332d698cb9253897075223b96f0ab5fd
# backtestId: c774cd610ab2797a7b244d460bcf687d
# title: 抖音奥数老师阴线低吸战法，回测年化61%

# 阴线买入法 V3
# 平台：聚宽 JoinQuant
# 回测频率：分钟
# 目标：
# 在 V2 基础上降低单票满仓风险，加入市场状态仓位和弱势恢复期控制
#
# 核心：
# 14:30 选股
# 14:50 买入
# 次日 10:00 清仓
# 不追涨，只买有资金活跃痕迹后的缩量阴线回踩10日线

from jqdata import *
import pandas as pd
import numpy as np
import datetime


def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)

    log.set_level('order', 'error')

    set_slippage(FixedSlippage(0.002))

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

    # ==========================
    # 仓位控制
    # ==========================
    g.reserve_cash_ratio = 0.02

    # 强势市场
    g.strong_max_hold_num = 2
    g.strong_total_position = 0.92
    g.strong_max_single_position = 0.46
    g.strong_min_score = 112

    # 普通市场
    g.normal_max_hold_num = 1
    g.normal_total_position = 0.62
    g.normal_max_single_position = 0.62
    g.normal_min_score = 122

    # 弱势恢复期
    g.recovery_max_hold_num = 1
    g.recovery_total_position = 0.45
    g.recovery_max_single_position = 0.45
    g.recovery_min_score = 132

    # 弱势状态下不买
    g.weak_total_position = 0.0

    # 连续弱势后，恢复期持续多少个交易日
    g.weak_trigger_days = 3
    g.recovery_days = 3
    g.weak_streak = 0
    g.recover_streak = 0
    g.market_state = 'normal'
    g.trade_mode = 'normal'

    # 单只股票卖出后冷却天数，减少反复横跳
    g.stock_cooldown_days = 2
    g.sell_date = {}

    # ==========================
    # 股票池过滤
    # ==========================
    g.only_main_board = True
    g.min_list_days = 180

    g.min_circ_mv = 15
    g.max_circ_mv = 250

    g.min_turnover = 1.2
    g.max_turnover = 18

    g.min_price = 3
    g.max_price = 80

    # ==========================
    # 市场环境
    # ==========================
    g.market_index = '000985.XSHG'

    # ==========================
    # 阴线买入条件
    # ==========================
    g.active_lookback = 25
    g.limitup_pct = 0.095
    g.strong_pct = 0.07

    g.max_today_gain = 0.01
    g.max_today_drop = -0.050

    g.ma10_down_tolerance = 0.018
    g.ma10_up_tolerance = 0.020

    g.ma10_ma20_gap_max = 0.065
    g.price_ma20_gap_max = 0.11

    g.recent_10d_gain_max = 0.30

    g.shrink_vs_yesterday = 0.88
    g.shrink_vs_avg5 = 0.85

    g.layer_volume_ratio = 1.55

    g.min_avg_money_5 = 30000000

    # 尾盘不能贴日内低点
    g.close_above_day_low = 0.006

    # 尾盘不能明显走弱
    g.last_30min_drop_max = -0.012

    # 当前价格不能明显低于日内均价线
    g.close_vs_vwap_min = 0.995

    # ==========================
    # 卖出参数
    # ==========================
    g.stop_loss = 0.038
    g.take_profit = 0.022

    g.today_candidates = []
    g.buy_date = {}

    run_daily(before_market_open, time='before_open')
    run_daily(select_stocks, time='14:30')
    run_daily(buy_stocks, time='14:50')
    run_daily(morning_risk_control, time='every_bar')
    run_daily(force_sell_positions, time='10:00')
    run_daily(force_sell_positions, time='14:45')


def before_market_open(context):
    g.today_candidates = []
    update_market_mode(context)


# =========================================================
# 更新市场状态
# =========================================================

def update_market_mode(context):
    state = get_market_state(context)
    g.market_state = state

    if state == 'weak':
        g.weak_streak += 1
        g.recover_streak = 0
        g.trade_mode = 'weak'

    else:
        if g.weak_streak >= g.weak_trigger_days or g.recover_streak > 0:
            g.recover_streak += 1
        else:
            g.recover_streak = 0

        g.weak_streak = 0

        if 1 <= g.recover_streak <= g.recovery_days:
            g.trade_mode = 'recovery'
        else:
            if state == 'strong':
                g.trade_mode = 'strong'
            else:
                g.trade_mode = 'normal'

            if g.recover_streak > g.recovery_days:
                g.recover_streak = 0

    log.info(
        '市场状态：%s，交易模式：%s，弱势连续：%s，恢复计数：%s'
        % (g.market_state, g.trade_mode, g.weak_streak, g.recover_streak)
    )


def get_market_state(context):
    try:
        df = get_price(
            g.market_index,
            end_date=context.previous_date,
            count=80,
            frequency='daily',
            fields=['close'],
            skip_paused=True,
            fq='pre'
        )

        if df is None or len(df) < 60:
            return 'normal'

        close = df['close']

        ma5 = close.rolling(5).mean().iloc[-1]
        ma10 = close.rolling(10).mean().iloc[-1]
        ma20 = close.rolling(20).mean().iloc[-1]
        ma60 = close.rolling(60).mean().iloc[-1]

        ma20_ago = close.rolling(20).mean().iloc[-5]
        ma60_ago = close.rolling(60).mean().iloc[-5]

        c = close.iloc[-1]

        ret3 = c / close.iloc[-4] - 1
        ret5 = c / close.iloc[-6] - 1

        high20 = close.iloc[-20:].max()
        drawdown20 = c / high20 - 1

        ma20_slope_ok = ma20 >= ma20_ago * 0.995
        ma60_slope_ok = ma60 >= ma60_ago * 0.992

        # 强势市场：指数多头，且没有短期大回撤
        if (
            c >= ma5 * 0.995 and
            ma5 >= ma10 * 0.995 and
            ma10 >= ma20 * 0.995 and
            ma20_slope_ok and
            drawdown20 > -0.035 and
            ret5 > -0.015
        ):
            return 'strong'

        # 普通市场：没有明显跌破中期线
        if (
            c >= ma20 * 0.985 and
            ma10 >= ma20 * 0.985 and
            ma20_slope_ok and
            drawdown20 > -0.060
        ):
            return 'normal'

        # 弱势恢复：刚从下跌里抬头，但还没完全转强
        if (
            c >= ma5 * 0.995 and
            ret3 > 0 and
            drawdown20 > -0.080 and
            ma60_slope_ok
        ):
            return 'normal'

        return 'weak'

    except Exception as e:
        log.info('市场状态判断异常，默认 normal：%s' % e)
        return 'normal'


def get_trade_plan():
    if g.trade_mode == 'strong':
        return {
            'can_trade': True,
            'max_hold_num': g.strong_max_hold_num,
            'total_position': g.strong_total_position,
            'max_single_position': g.strong_max_single_position,
            'min_score': g.strong_min_score
        }

    if g.trade_mode == 'normal':
        return {
            'can_trade': True,
            'max_hold_num': g.normal_max_hold_num,
            'total_position': g.normal_total_position,
            'max_single_position': g.normal_max_single_position,
            'min_score': g.normal_min_score
        }

    if g.trade_mode == 'recovery':
        return {
            'can_trade': True,
            'max_hold_num': g.recovery_max_hold_num,
            'total_position': g.recovery_total_position,
            'max_single_position': g.recovery_max_single_position,
            'min_score': g.recovery_min_score
        }

    return {
        'can_trade': False,
        'max_hold_num': 0,
        'total_position': 0,
        'max_single_position': 0,
        'min_score': 999
    }


# =========================================================
# 14:30选股
# =========================================================

def select_stocks(context):
    g.today_candidates = []

    plan = get_trade_plan()

    if not plan['can_trade']:
        log.info('14:30 当前交易模式为 %s，不选股' % g.trade_mode)
        return

    stocks = get_stock_universe(context)
    candidates = []

    for stock in stocks:
        result = check_stock_signal(stock, context)

        if result is not None and result['score'] >= plan['min_score']:
            candidates.append(result)

    if len(candidates) == 0:
        log.info('14:30 无符合条件股票')
        return

    candidates = sorted(candidates, key=lambda x: x['score'], reverse=True)

    g.today_candidates = candidates[:plan['max_hold_num'] * 5]

    log.info(
        '14:30 候选股数量：%s，交易模式：%s，最低分：%s'
        % (len(g.today_candidates), g.trade_mode, plan['min_score'])
    )

    for c in g.today_candidates[:10]:
        log.info(
            '候选：%s %s 分数：%.2f 现价：%.2f MA10：%.2f 预计量比：%.2f 今日涨幅：%.2f%%'
            % (
                c['stock'],
                c['name'],
                c['score'],
                c['price'],
                c['ma10'],
                c['projected_vol_ratio'],
                c['today_ret'] * 100
            )
        )


# =========================================================
# 14:50买入
# =========================================================

def buy_stocks(context):
    plan = get_trade_plan()

    if not plan['can_trade']:
        log.info('14:50 当前交易模式为 %s，不买入' % g.trade_mode)
        return

    if len(g.today_candidates) == 0:
        log.info('14:50 无候选股，不买入')
        return

    if len(context.portfolio.positions) > 0:
        log.info('14:50 当前仍有持仓，暂停新开仓')
        return

    final_list = []

    for c in g.today_candidates:
        stock = c['stock']
        result = check_stock_signal(stock, context)

        if result is not None and result['score'] >= plan['min_score']:
            final_list.append(result)

    if len(final_list) == 0:
        log.info('14:50 复核后无股票符合条件')
        return

    final_list = sorted(final_list, key=lambda x: x['score'], reverse=True)
    final_list = final_list[:plan['max_hold_num']]

    total_value = context.portfolio.total_value
    available_cash = context.portfolio.available_cash * (1 - g.reserve_cash_ratio)

    target_total_value = total_value * plan['total_position']
    raw_value_per_stock = target_total_value / len(final_list)
    max_single_value = total_value * plan['max_single_position']

    value_per_stock = min(raw_value_per_stock, max_single_value, available_cash / len(final_list))

    if value_per_stock <= 0:
        return

    today = context.current_dt.date()

    for c in final_list:
        stock = c['stock']

        order_target_value(stock, value_per_stock)
        g.buy_date[stock] = today

        log.info(
            '14:50 买入：%s %s 金额：%.2f 分数：%.2f 模式：%s'
            % (stock, c['name'], value_per_stock, c['score'], g.trade_mode)
        )


# =========================================================
# 股票池
# =========================================================

def get_stock_universe(context):
    date = context.previous_date
    all_stocks = list(get_all_securities(['stock'], date=date).index)
    current_data = get_current_data()

    base = []

    for stock in all_stocks:
        if g.only_main_board:
            if stock.startswith('300') or stock.startswith('301'):
                continue
            if stock.startswith('688') or stock.startswith('689'):
                continue
            if stock.startswith('8') or stock.startswith('4'):
                continue

        if is_stock_in_cooldown(stock, context):
            continue

        try:
            cd = current_data[stock]
        except:
            continue

        if cd.paused:
            continue

        if cd.is_st:
            continue

        name = cd.name

        if 'ST' in name or '*ST' in name or '退' in name:
            continue

        price = cd.last_price

        if price is None or price <= 0:
            continue

        if price < g.min_price or price > g.max_price:
            continue

        if price >= cd.high_limit * 0.995:
            continue

        if price <= cd.low_limit * 1.005:
            continue

        try:
            info = get_security_info(stock)

            if info is None:
                continue

            listed_days = (context.current_dt.date() - info.start_date).days

            if listed_days < g.min_list_days:
                continue

        except:
            continue

        base.append(stock)

    try:
        q = query(
            valuation.code,
            valuation.circulating_market_cap,
            valuation.turnover_ratio
        ).filter(
            valuation.code.in_(base),
            valuation.circulating_market_cap >= g.min_circ_mv,
            valuation.circulating_market_cap <= g.max_circ_mv,
            valuation.turnover_ratio >= g.min_turnover,
            valuation.turnover_ratio <= g.max_turnover
        )

        df = get_fundamentals(q, date=context.previous_date)

        if df is None or len(df) == 0:
            return base

        return list(df['code'])

    except Exception as e:
        log.info('基本面过滤异常，使用基础股票池：%s' % e)
        return base


def is_stock_in_cooldown(stock, context):
    if stock not in g.sell_date:
        return False

    last_sell_date = g.sell_date[stock]
    days = (context.current_dt.date() - last_sell_date).days

    return days <= g.stock_cooldown_days


# =========================================================
# 单股信号
# =========================================================

def check_stock_signal(stock, context):
    current_data = get_current_data()

    try:
        cd = current_data[stock]
    except:
        return None

    price = cd.last_price
    name = cd.name

    if price is None or price <= 0:
        return None

    hist = get_price(
        stock,
        end_date=context.previous_date,
        count=80,
        frequency='daily',
        fields=['open', 'close', 'high', 'low', 'volume', 'money'],
        skip_paused=True,
        fq='pre'
    )

    if hist is None or len(hist) < 60:
        return None

    close = hist['close']
    high = hist['high']
    volume = hist['volume']
    money = hist['money']

    ma10_series = close.rolling(10).mean()
    ma20_series = close.rolling(20).mean()
    ma60_series = close.rolling(60).mean()

    ma10 = ma10_series.iloc[-1]
    ma20 = ma20_series.iloc[-1]
    ma60 = ma60_series.iloc[-1]

    if np.isnan(ma10) or np.isnan(ma20) or np.isnan(ma60):
        return None

    prev_close = close.iloc[-1]

    avg_money_5 = money.iloc[-5:].mean()

    if avg_money_5 < g.min_avg_money_5:
        return None

    # 10日线向上
    if not (ma10_series.iloc[-1] > ma10_series.iloc[-3] > ma10_series.iloc[-5]):
        return None

    if ma10 <= ma20:
        return None

    if price < ma60:
        return None

    ma_gap = ma10 / ma20 - 1

    if ma_gap > g.ma10_ma20_gap_max:
        return None

    price_ma20_gap = price / ma20 - 1

    if price_ma20_gap > g.price_ma20_gap_max:
        return None

    recent_10d_gain = close.iloc[-1] / close.iloc[-10] - 1

    if recent_10d_gain > g.recent_10d_gain_max:
        return None

    today_ret = price / prev_close - 1

    if today_ret > g.max_today_gain:
        return None

    if today_ret < g.max_today_drop:
        return None

    intraday = get_today_intraday_data(stock, context)

    if intraday is None or len(intraday) < 35:
        return None

    day_open = intraday['open'].iloc[0]
    now_close = intraday['close'].iloc[-1]
    day_low = intraday['low'].min()
    today_volume = intraday['volume'].sum()
    today_money = intraday['money'].sum()

    if day_open <= 0:
        return None

    # 今日必须是阴线
    if now_close >= day_open:
        return None

    # 必须有回踩10日线动作
    if day_low > ma10 * (1 + g.ma10_up_tolerance):
        return None

    if price < ma10 * (1 - g.ma10_down_tolerance):
        return None

    if price > ma10 * (1 + g.ma10_up_tolerance):
        return None

    # 尾盘不能贴着日内最低点
    if price <= day_low * (1 + g.close_above_day_low):
        return None

    # 尾盘30分钟不能继续明显下坠
    last_30 = intraday.iloc[-30:]

    if len(last_30) >= 20:
        last_30_ret = last_30['close'].iloc[-1] / last_30['close'].iloc[0] - 1

        if last_30_ret < g.last_30min_drop_max:
            return None

    # 当前价格不能明显低于日内均价线
    total_volume = intraday['volume'].sum()
    total_money = intraday['money'].sum()

    if total_volume <= 0:
        return None

    vwap = total_money / total_volume

    if price < vwap * g.close_vs_vwap_min:
        return None

    # 缩量判断
    minute_ratio = get_trading_minute_ratio(context.current_dt)

    if minute_ratio <= 0:
        return None

    projected_volume = today_volume / minute_ratio
    projected_money = today_money / minute_ratio

    yesterday_volume = volume.iloc[-1]
    avg5_volume = volume.iloc[-5:].mean()

    if yesterday_volume <= 0 or avg5_volume <= 0:
        return None

    if projected_volume > yesterday_volume * g.shrink_vs_yesterday:
        return None

    if projected_volume > avg5_volume * g.shrink_vs_avg5:
        return None

    if projected_money < g.min_avg_money_5 * 0.6:
        return None

    active_info = get_active_info(hist)

    if not active_info['is_active']:
        return None

    if active_info['last_active_distance'] > 18:
        return None

    if active_info['last_active_distance'] <= 1:
        return None

    if not has_layer_volume(hist):
        return None

    projected_vol_ratio = projected_volume / avg5_volume

    score = calc_score(
        price=price,
        ma10=ma10,
        ma20=ma20,
        ma60=ma60,
        today_ret=today_ret,
        projected_vol_ratio=projected_vol_ratio,
        active_info=active_info,
        ma10_series=ma10_series,
        recent_10d_gain=recent_10d_gain,
        day_low=day_low,
        vwap=vwap
    )

    return {
        'stock': stock,
        'name': name,
        'price': price,
        'ma10': ma10,
        'ma20': ma20,
        'score': score,
        'today_ret': today_ret,
        'projected_vol_ratio': projected_vol_ratio
    }


# =========================================================
# 今日分钟数据
# =========================================================

def get_today_intraday_data(stock, context):
    today_str = context.current_dt.strftime('%Y-%m-%d')
    start_time = today_str + ' 09:30:00'

    try:
        df = get_price(
            stock,
            start_date=start_time,
            end_date=context.current_dt,
            frequency='1m',
            fields=['open', 'close', 'high', 'low', 'volume', 'money'],
            skip_paused=True,
            fq=None
        )

        if df is None or len(df) == 0:
            return None

        return df

    except:
        return None


# =========================================================
# 前期活跃度
# =========================================================

def get_active_info(hist):
    recent = hist.iloc[-g.active_lookback:].copy()

    if len(recent) < 10:
        return {
            'is_active': False,
            'limitup_count': 0,
            'strong_count': 0,
            'last_active_distance': 999
        }

    close = recent['close']
    high = recent['high']
    volume = recent['volume']

    pct = close.pct_change()
    vol_ma5 = volume.rolling(5).mean()

    limit_mask = (pct >= g.limitup_pct) & (close >= high * 0.995)
    strong_mask = (pct >= g.strong_pct) & (volume >= vol_ma5 * 1.5)

    active_mask = limit_mask | strong_mask

    limitup_count = int(limit_mask.sum())
    strong_count = int(strong_mask.sum())

    if active_mask.sum() <= 0:
        return {
            'is_active': False,
            'limitup_count': 0,
            'strong_count': 0,
            'last_active_distance': 999
        }

    active_indices = np.where(active_mask.values)[0]
    last_active_distance = len(recent) - 1 - active_indices[-1]

    return {
        'is_active': True,
        'limitup_count': limitup_count,
        'strong_count': strong_count,
        'last_active_distance': last_active_distance
    }


# =========================================================
# 分层量
# =========================================================

def has_layer_volume(hist):
    if len(hist) < 50:
        return False

    recent = hist.iloc[-g.active_lookback:]
    base = hist.iloc[-50:-g.active_lookback]

    if len(base) < 10:
        return False

    recent_max_volume = recent['volume'].max()
    base_avg_volume = base['volume'].mean()

    if base_avg_volume <= 0:
        return False

    return recent_max_volume >= base_avg_volume * g.layer_volume_ratio


# =========================================================
# 早盘风控
# =========================================================

def morning_risk_control(context):
    now = context.current_dt.time()

    if now < datetime.time(9, 31) or now > datetime.time(10, 0):
        return

    current_data = get_current_data()
    today = context.current_dt.date()

    for stock in list(context.portfolio.positions.keys()):
        position = context.portfolio.positions[stock]

        if position.total_amount <= 0:
            continue

        if g.buy_date.get(stock, None) == today:
            continue

        try:
            price = current_data[stock].last_price
        except:
            continue

        if price is None or price <= 0:
            continue

        cost = position.avg_cost

        if cost <= 0:
            continue

        ret = price / cost - 1

        if ret <= -g.stop_loss:
            order_target(stock, 0)
            g.sell_date[stock] = today
            log.info('早盘止损卖出：%s 收益：%.2f%%' % (stock, ret * 100))
            continue

        if ret >= g.take_profit:
            if not is_strong_intraday(stock, context):
                order_target(stock, 0)
                g.sell_date[stock] = today
                log.info('早盘止盈卖出：%s 收益：%.2f%%' % (stock, ret * 100))


# =========================================================
# 次日10:00纪律清仓
# =========================================================

def force_sell_positions(context):
    today = context.current_dt.date()

    for stock in list(context.portfolio.positions.keys()):
        position = context.portfolio.positions[stock]

        if position.total_amount <= 0:
            continue

        if g.buy_date.get(stock, None) == today:
            continue

        order_target(stock, 0)
        g.sell_date[stock] = today
        log.info('纪律清仓卖出：%s' % stock)


# =========================================================
# 早盘是否强势
# =========================================================

def is_strong_intraday(stock, context):
    intraday = get_today_intraday_data(stock, context)

    if intraday is None or len(intraday) < 5:
        return False

    close = intraday['close']
    volume = intraday['volume']
    money = intraday['money']

    last_price = close.iloc[-1]

    total_volume = volume.sum()
    total_money = money.sum()

    if total_volume <= 0:
        return False

    vwap = total_money / total_volume

    if last_price >= vwap:
        return True

    return False


# =========================================================
# 当前交易日分钟进度
# =========================================================

def get_trading_minute_ratio(dt):
    t = dt.time()
    total_minutes = 240

    if t < datetime.time(9, 30):
        passed = 0

    elif t <= datetime.time(11, 30):
        passed = (dt.hour - 9) * 60 + dt.minute - 30

    elif t < datetime.time(13, 0):
        passed = 120

    elif t <= datetime.time(15, 0):
        passed = 120 + (dt.hour - 13) * 60 + dt.minute

    else:
        passed = 240

    passed = max(1, min(passed, total_minutes))

    return float(passed) / float(total_minutes)


# =========================================================
# 打分函数
# =========================================================

def calc_score(
    price,
    ma10,
    ma20,
    ma60,
    today_ret,
    projected_vol_ratio,
    active_info,
    ma10_series,
    recent_10d_gain,
    day_low,
    vwap
):
    score = 0

    dist_ma10 = abs(price / ma10 - 1)
    score += max(0, 35 - dist_ma10 * 1200)

    score += max(0, 28 * (1 - projected_vol_ratio))

    score += active_info['limitup_count'] * 13
    score += active_info['strong_count'] * 6

    distance = active_info['last_active_distance']

    if 2 <= distance <= 5:
        score += 16
    elif 6 <= distance <= 10:
        score += 13
    elif 11 <= distance <= 18:
        score += 7

    ma10_slope = ma10_series.iloc[-1] / ma10_series.iloc[-5] - 1
    score += min(18, max(0, ma10_slope * 900))

    if -0.03 <= today_ret <= -0.003:
        score += 14
    elif -0.045 <= today_ret < -0.03:
        score += 7
    elif -0.003 < today_ret <= 0.01:
        score += 4

    ma_gap = ma10 / ma20 - 1
    score += max(0, 10 - ma_gap * 100)

    score += max(0, 12 - recent_10d_gain * 35)

    low_gap = price / day_low - 1
    score += min(8, low_gap * 600)

    # 当前价高于日内均价线略加分
    vwap_gap = price / vwap - 1
    if vwap_gap >= 0:
        score += min(8, vwap_gap * 500)
    else:
        score += max(-8, vwap_gap * 500)

    return score