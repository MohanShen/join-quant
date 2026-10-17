# Clone from JoinQuant
# postId: 4ac4bd9a05f0a3bb565bcfa888ae2fac
# backtestId: f5d52eedb33c8ac26ebc39b57665e71a
# title: 低相关ETF组合：回撤11.72%

from jqdata import *
import datetime
import math


def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)

    log.set_level('order', 'error')

    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0,
            open_commission=0.00005,
            close_commission=0.00005,
            close_today_commission=0,
            min_commission=0
        ),
        type='fund'
    )

    g.cash_etf = '511880.XSHG'

    # 多资产ETF池：A股、海外、港股、黄金、债券、商品
    g.etf_pool = [
        '510300.XSHG',  # 沪深300ETF
        '510500.XSHG',  # 中证500ETF
        '512100.XSHG',  # 中证1000ETF
        '159915.XSHE',  # 创业板ETF
        '513100.XSHG',  # 纳指ETF
        '513500.XSHG',  # 标普500ETF
        '159920.XSHE',  # 恒生ETF
        '518880.XSHG',  # 黄金ETF
        '511010.XSHG',  # 国债ETF
        '512400.XSHG',  # 有色金属ETF
        '159985.XSHE',  # 豆粕ETF
        '159980.XSHE'   # 有色期货ETF
    ]

    # 观察窗口
    g.lookback_days = 120
    g.short_days = 60
    g.vol_days = 20

    # 组合参数
    g.max_hold = 4
    g.position_ratio = 0.95
    g.max_single_weight = 0.35

    # 信号过滤
    g.min_long_momentum = -0.03
    g.min_short_momentum = -0.06
    g.min_score = -0.02
    g.max_vol = 0.045
    g.max_dd = 0.30

    # 相关性惩罚，越大越偏好低相关
    g.corr_penalty = 0.18

    g.min_list_days = 180

    run_monthly(rebalance, 1, time='10:00')


def rebalance(context):
    signals = build_signals(context)

    if len(signals) == 0:
        log.info('没有有效ETF，切换到货币ETF')
        trade_to_weights(context, {g.cash_etf: 0.98})
        return

    selected = select_low_corr_etfs(signals)

    if len(selected) == 0:
        log.info('没有选出低相关组合，切换到货币ETF')
        trade_to_weights(context, {g.cash_etf: 0.98})
        return

    weights = build_weights(selected, signals)

    used = 0.0
    for code in weights:
        used += weights[code]

    cash_weight = 0.98 - used
    if cash_weight > 0.02:
        weights[g.cash_etf] = cash_weight

    log.info('入选ETF: %s' % selected)
    log.info('目标权重: %s' % weights)

    trade_to_weights(context, weights)


def build_signals(context):
    result = {}

    for code in g.etf_pool:
        if not is_listed(context, code):
            continue

        sig = calc_signal(context, code)

        if sig is None:
            continue

        if sig['vol'] > g.max_vol:
            continue

        if sig['max_dd'] > g.max_dd:
            continue

        if sig['ret120'] < g.min_long_momentum and sig['ret60'] < g.min_short_momentum:
            continue

        if sig['score'] < g.min_score:
            continue

        result[code] = sig

    return result


def calc_signal(context, code):
    count = g.lookback_days + 1

    try:
        df = get_price(
            code,
            end_date=context.previous_date,
            count=count,
            frequency='daily',
            fields=['close'],
            panel=False
        )

        if df is None or len(df) < count:
            return None

        closes = []
        for x in list(df['close']):
            closes.append(float(x))

        close = closes[-1]

        if close <= 0:
            return None

        base120 = closes[0]
        base60 = closes[-g.short_days - 1]

        if base120 <= 0 or base60 <= 0:
            return None

        ret120 = close / base120 - 1.0
        ret60 = close / base60 - 1.0

        returns = calc_returns(closes)
        vol = calc_vol(returns[-g.vol_days:])
        max_dd = calc_max_dd(closes)

        # 动量为主，波动和回撤做轻微惩罚
        score = ret120 * 0.55 + ret60 * 0.45 - vol * 1.8 - max_dd * 0.15

        return {
            'ret120': ret120,
            'ret60': ret60,
            'vol': vol,
            'max_dd': max_dd,
            'score': score,
            'returns': returns
        }

    except Exception as e:
        log.info('计算信号异常: %s %s' % (code, e))
        return None


def select_low_corr_etfs(signals):
    candidates = sorted(
        signals.keys(),
        key=lambda x: signals[x]['score'],
        reverse=True
    )

    selected = []

    while len(selected) < g.max_hold:
        best_code = None
        best_score = -999999.0

        for code in candidates:
            if code in selected:
                continue

            base_score = signals[code]['score']

            if len(selected) == 0:
                final_score = base_score
            else:
                avg_corr = average_corr(code, selected, signals)
                final_score = base_score - avg_corr * g.corr_penalty

            if final_score > best_score:
                best_score = final_score
                best_code = code

        if best_code is None:
            break

        selected.append(best_code)

    return selected


def average_corr(code, selected, signals):
    total = 0.0
    count = 0

    for other in selected:
        corr = calc_corr(signals[code]['returns'], signals[other]['returns'])

        # 负相关是好事，但不要让它过度放大分数
        if corr < -0.5:
            corr = -0.5

        total += corr
        count += 1

    if count == 0:
        return 0.0

    return total / count


def build_weights(selected, signals):
    raw = {}
    raw_sum = 0.0

    for code in selected:
        vol = signals[code]['vol']

        if vol < 0.005:
            vol = 0.005

        # 低波动权重大，动量强略微加分
        momentum_bonus = 1.0 + max(0.0, signals[code]['score'])
        value = momentum_bonus / vol

        raw[code] = value
        raw_sum += value

    if raw_sum <= 0:
        return {g.cash_etf: 0.98}

    weights = {}
    used = 0.0

    for code in selected:
        w = raw[code] / raw_sum * g.position_ratio

        if w > g.max_single_weight:
            w = g.max_single_weight

        weights[code] = w
        used += w

    return weights


def trade_to_weights(context, weights):
    total_value = context.portfolio.total_value

    for code in list(context.portfolio.positions.keys()):
        pos = context.portfolio.positions[code]

        if pos.total_amount <= 0:
            continue

        if code not in weights:
            if can_sell(code):
                order_target_value(code, 0)

    for code in weights:
        target_value = total_value * weights[code]

        if can_buy(code) or has_position(context, code):
            order_target_value(code, target_value)


def calc_returns(closes):
    result = []

    for i in range(1, len(closes)):
        prev = float(closes[i - 1])
        now = float(closes[i])

        if prev > 0:
            result.append(now / prev - 1.0)

    return result


def calc_corr(a, b):
    n = min(len(a), len(b))

    if n < 20:
        return 0.0

    x = a[-n:]
    y = b[-n:]

    avg_x = average(x)
    avg_y = average(y)

    cov = 0.0
    var_x = 0.0
    var_y = 0.0

    for i in range(n):
        dx = x[i] - avg_x
        dy = y[i] - avg_y

        cov += dx * dy
        var_x += dx * dx
        var_y += dy * dy

    if var_x <= 0 or var_y <= 0:
        return 0.0

    return cov / math.sqrt(var_x * var_y)


def calc_vol(returns):
    if len(returns) == 0:
        return 0.02

    avg = average(returns)

    var = 0.0
    for r in returns:
        var += (r - avg) * (r - avg)

    return math.sqrt(var / len(returns))


def calc_max_dd(closes):
    if len(closes) == 0:
        return 0.0

    high = closes[0]
    max_dd = 0.0

    for price in closes:
        if price > high:
            high = price

        if high > 0:
            dd = 1.0 - price / high

            if dd > max_dd:
                max_dd = dd

    return max_dd


def average(values):
    if len(values) == 0:
        return 0.0

    total = 0.0

    for v in values:
        total += float(v)

    return total / len(values)


def has_position(context, code):
    if code not in context.portfolio.positions:
        return False

    return context.portfolio.positions[code].total_amount > 0


def is_listed(context, code):
    try:
        info = get_security_info(code)

        if info is None:
            return False

        if info.start_date + datetime.timedelta(days=g.min_list_days) > context.previous_date:
            return False

        return True

    except Exception:
        return False


def can_buy(code):
    try:
        data = get_current_data()[code]

        if data.paused:
            return False

        if data.last_price >= data.high_limit:
            return False

        return True

    except Exception:
        return False


def can_sell(code):
    try:
        data = get_current_data()[code]

        if data.paused:
            return False

        if data.last_price <= data.low_limit:
            return False

        return True

    except Exception:
        return False