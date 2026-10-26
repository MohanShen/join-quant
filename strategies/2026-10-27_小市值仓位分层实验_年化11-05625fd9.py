# Clone from JoinQuant
# postId: 05625fd91d15f21aa69b2cb6a6a00cc6
# backtestId: b6ba50293ba369db8dbd37df9f96eb0c
# title: 小市值仓位分层实验：年化11%

from jqdata import *
import datetime


def initialize(context):
    set_benchmark('000300.XSHG')
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

    # 判断小盘环境
    g.market_index = '000852.XSHG'

    # 防御ETF
    g.cash_etf = '511880.XSHG'
    g.gold_etf = '518880.XSHG'
    g.bond_etf = '511010.XSHG'
    g.nasdaq_etf = '513100.XSHG'

    g.all_etfs = [
        g.cash_etf,
        g.gold_etf,
        g.bond_etf,
        g.nasdaq_etf
    ]

    # 总仓位
    g.max_total_position = 0.98

    # 晴雨模式下的小盘仓位
    g.sun_stock_weight = 0.70
    g.cloud_stock_weight = 0.40
    g.rain_stock_weight = 0.00

    # 小盘阶梯调仓参数
    g.hold_num = 30
    g.pool_num = 120
    g.query_limit = 700
    g.keep_rank = 90
    g.max_replace_num = 4
    g.min_list_days = 250

    # 市场环境参数
    g.short_ma = 60
    g.long_ma = 120

    run_weekly(rebalance, 1, time='10:00')


def rebalance(context):
    weather = get_market_weather(context)
    stock_weight = get_stock_weight_by_weather(weather)

    log.info('当前市场天气: %s, 小盘目标仓位: %.2f' % (weather, stock_weight))

    weights = {}

    if stock_weight > 0:
        ranked = get_ranked_stocks(context)

        if len(ranked) > 0:
            target_stocks = build_step_target(context, ranked)
            log.info('小盘目标持仓: %s' % target_stocks)

            if len(target_stocks) > 0:
                each_weight = stock_weight / len(target_stocks)

                for stock in target_stocks:
                    weights[stock] = each_weight

    used_weight = 0.0
    for code in weights:
        used_weight += weights[code]

    defense_weight = g.max_total_position - used_weight
    if defense_weight < 0:
        defense_weight = 0.0

    defense_weights = build_defense_weights(context, weather, defense_weight)

    for code in defense_weights:
        if code not in weights:
            weights[code] = 0.0
        weights[code] += defense_weights[code]

    log.info('最终目标权重: %s' % weights)
    trade_to_weights(context, weights)


def get_market_weather(context):
    try:
        df = get_price(
            g.market_index,
            end_date=context.previous_date,
            count=g.long_ma + 5,
            frequency='daily',
            fields=['close'],
            panel=False
        )

        if df is None or len(df) < g.long_ma:
            return 'cloud'

        closes = list(df['close'])
        close = float(closes[-1])

        ma60 = average(closes[-g.short_ma:])
        ma120 = average(closes[-g.long_ma:])

        base60 = float(closes[-g.short_ma])
        base120 = float(closes[-g.long_ma])

        ret60 = close / base60 - 1.0
        ret120 = close / base120 - 1.0

        log.info('中证1000 close=%.2f ma60=%.2f ma120=%.2f ret60=%.2f ret120=%.2f' %
                 (close, ma60, ma120, ret60, ret120))

        if close > ma60 and close > ma120 and ret60 > 0:
            return 'sun'

        if close > ma120 * 0.96 or ret120 > -0.08:
            return 'cloud'

        return 'rain'

    except Exception as e:
        log.info('市场天气判断异常: %s' % e)
        return 'cloud'


def get_stock_weight_by_weather(weather):
    if weather == 'sun':
        return g.sun_stock_weight

    if weather == 'cloud':
        return g.cloud_stock_weight

    return g.rain_stock_weight


def build_defense_weights(context, weather, total_weight):
    result = {}

    if total_weight <= 0:
        return result

    if weather == 'sun':
        ratios = {
            g.gold_etf: 0.35,
            g.bond_etf: 0.35,
            g.nasdaq_etf: 0.20,
            g.cash_etf: 0.10
        }
    elif weather == 'cloud':
        ratios = {
            g.gold_etf: 0.35,
            g.bond_etf: 0.45,
            g.cash_etf: 0.20
        }
    else:
        ratios = {
            g.gold_etf: 0.35,
            g.bond_etf: 0.45,
            g.cash_etf: 0.20
        }

    usable = []
    for code in ratios:
        if is_etf_listed(context, code):
            usable.append(code)

    if len(usable) == 0:
        result[g.cash_etf] = total_weight
        return result

    ratio_sum = 0.0
    for code in usable:
        ratio_sum += ratios[code]

    for code in usable:
        result[code] = total_weight * ratios[code] / ratio_sum

    return result


def get_ranked_stocks(context):
    q = query(
        valuation.code,
        valuation.market_cap,
        valuation.pb_ratio,
        valuation.pe_ratio,
        valuation.turnover_ratio,
        indicator.roe
    ).filter(
        valuation.market_cap > 5,
        valuation.market_cap < 120,
        valuation.pb_ratio > 0,
        valuation.pb_ratio < 6,
        valuation.pe_ratio > 0,
        valuation.pe_ratio < 120,
        valuation.turnover_ratio > 0,
        valuation.turnover_ratio < 12,
        indicator.roe > -5
    ).order_by(
        valuation.market_cap.asc(),
        valuation.pb_ratio.asc(),
        valuation.turnover_ratio.asc()
    ).limit(g.query_limit)

    df = get_fundamentals(q, date=context.previous_date)

    if df is None or len(df) == 0:
        return []

    current_data = get_current_data()
    rows = []

    for i in range(len(df)):
        stock = df.iloc[i]['code']

        if not is_good_stock(context, stock, current_data):
            continue

        market_cap = float(df.iloc[i]['market_cap'])
        pb = float(df.iloc[i]['pb_ratio'])
        turnover = float(df.iloc[i]['turnover_ratio'])
        roe = float(df.iloc[i]['roe'])

        score = (
            market_cap * 1.00 +
            pb * 4.00 +
            turnover * 0.80 -
            roe * 0.03
        )

        rows.append({
            'code': stock,
            'score': score
        })

    rows = sorted(rows, key=lambda x: x['score'])

    result = []
    for r in rows:
        result.append(r['code'])
        if len(result) >= g.pool_num:
            break

    return result


def build_step_target(context, ranked):
    current = get_current_stock_positions(context)

    rank_map = {}
    for i in range(len(ranked)):
        rank_map[ranked[i]] = i + 1

    must_sell = []
    soft_sell = []

    for stock in current:
        if stock not in rank_map:
            must_sell.append(stock)
        else:
            rank = rank_map[stock]
            if rank > g.keep_rank:
                soft_sell.append(stock)

    soft_sell = sorted(
        soft_sell,
        key=lambda x: rank_map.get(x, 9999),
        reverse=True
    )

    replace_left = g.max_replace_num - len(must_sell)
    if replace_left < 0:
        replace_left = 0

    sell_list = []

    for stock in must_sell:
        sell_list.append(stock)

    for stock in soft_sell[:replace_left]:
        sell_list.append(stock)

    target = []

    for stock in current:
        if stock not in sell_list:
            target.append(stock)

    for stock in ranked:
        if len(target) >= g.hold_num:
            break

        if stock not in target:
            target.append(stock)

    return target[:g.hold_num]


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


def get_current_stock_positions(context):
    result = []

    for code in context.portfolio.positions.keys():
        pos = context.portfolio.positions[code]

        if pos.total_amount <= 0:
            continue

        if code in g.all_etfs:
            continue

        result.append(code)

    return result


def is_good_stock(context, stock, current_data):
    if stock.startswith('688') or stock.startswith('689'):
        return False

    if stock.startswith('4') or stock.startswith('8'):
        return False

    if stock.startswith('200') or stock.startswith('900'):
        return False

    try:
        info = get_security_info(stock)

        if info is None:
            return False

        if info.start_date + datetime.timedelta(days=g.min_list_days) > context.previous_date:
            return False

        data = current_data[stock]

        if data.paused:
            return False

        if data.is_st:
            return False

        name = data.name
        if name.startswith('ST') or name.startswith('*ST') or '退' in name:
            return False

        return True

    except Exception:
        return False


def is_etf_listed(context, code):
    try:
        info = get_security_info(code)

        if info is None:
            return False

        if info.start_date > context.previous_date:
            return False

        return True

    except Exception:
        return False


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