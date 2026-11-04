# Clone from JoinQuant
# postId: 94c64f0683469fc3cbe323c4196f5f7f
# backtestId: 525122fac9def52d4b10eb09b348c893
# title: 小市值，26年-30收益-低回撤

# -*- coding: utf-8 -*-     
#变种小狮子 + 涨停基因股池 v3.0
from jqdata import *
from datetime import timedelta

def initialize(context):
    set_option('avoid_future_data', True)
    set_benchmark('399101.XSHE')
    set_option('use_real_price', True)
    set_slippage(PriceRelatedSlippage(0.01), type="stock")
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0.0005,
            open_commission=0.0001,
            close_commission=0.0001,
            close_today_commission=0,
            min_commission=1,
        ),
        type="stock",
    )

    g.stock_num = 6
    g.limit_days_window = 3 * 250
    g.init_stock_count = 1000
    g.stoploss_limit = 0.93
    g.stoploss_market = 0.93
    g.stoploss_strategy = 3
    g.min_price = 2.0
    g.loss_blacklist = {}
    g.loss_blacklist_days = 20

    g.no_trading_today_signal = False
    g.pass_april = True
    g.run_stoploss = True
    g.hold_list = []
    g.yesterday_HL_list = []
    g.target_list = []
    g.not_buy_again = []
    g.reason_to_sell = ''

    run_daily(prepare_stock_list, '9:05')
    run_weekly(weekly_adjustment, 2, '10:30')
    run_daily(sell_stocks, time='10:00')
    run_daily(trade_afternoon, time='14:20')
    run_daily(trade_afternoon, time='14:55')
    run_daily(close_account, '14:50')

def prepare_stock_list(context):
    g.hold_list = [p.security for p in context.portfolio.positions.values()]
    if g.hold_list:
        df = get_price(g.hold_list, end_date=context.previous_date, frequency='daily',
                       fields=['close', 'high_limit', 'low_limit'], count=1,
                       panel=False, fill_paused=False)
        df = df[df['close'] == df['high_limit']]
        g.yesterday_HL_list = list(df.code)
    else:
        g.yesterday_HL_list = []
    g.no_trading_today_signal = today_is_between(context)

def get_history_highlimit(context, stock_list, days=3 * 250, p=0.10):
    df = get_price(stock_list, end_date=context.previous_date, frequency="daily",
                   fields=["close", "high_limit"], count=days, panel=False)
    df = df[df["close"] == df["high_limit"]]
    if df.empty:
        return []
    grouped_result = df.groupby('code').size().reset_index(name='count')
    grouped_result = grouped_result.sort_values(by=["count"], ascending=False)
    return grouped_result["code"].tolist()[:int(len(grouped_result) * p)]

def get_start_point(context, stock_list, days=3 * 250):
    df = get_price(stock_list, end_date=context.previous_date, frequency="daily",
                   fields=["open", "low", "close", "high_limit"], count=days, panel=False)
    stock_start_point = {}
    stock_price_bias = {}
    current_data = get_current_data()

    for code, group in df.groupby('code'):
        group = group.sort_values('time')
        limit_hit_rows = group[group['close'] == group['high_limit']]
        if not limit_hit_rows.empty:
            latest_limit_hit = limit_hit_rows.iloc[-1]
            latest_limit_index = latest_limit_hit.name
            previous_rows = group[group.index <= latest_limit_index].iloc[::-1]
            for idx, row in previous_rows.iterrows():
                if row['close'] < row['open']:
                    stock_start_point[code] = row['low']
                    break

    for code, start_point in stock_start_point.items():
        if start_point <= 0:
            continue
        try:
            last_price = current_data[code].last_price
            if last_price <= 0:
                continue
            stock_price_bias[code] = last_price / start_point
        except Exception:
            continue

    sorted_list = sorted(stock_price_bias.items(), key=lambda x: x[1], reverse=False)
    return [i[0] for i in sorted_list]

def get_stock_list(context):
    yesterday = context.previous_date
    initial_list = get_all_securities("stock", yesterday).index.tolist()
    initial_list = filter_new_stock(context, initial_list)
    initial_list = filter_kcbj_stock(initial_list)
    initial_list = filter_st_stock(initial_list)
    initial_list = filter_paused_stock(initial_list)
    initial_list = filter_loss_black(context, initial_list)

    q = query(valuation.code, indicator.eps).filter(
        valuation.code.in_(initial_list)
    ).order_by(valuation.market_cap.asc())
    df = get_fundamentals(q)
    initial_list = df['code'].tolist()[:g.init_stock_count]
    initial_list = filter_low_price_stock(context, initial_list)
    initial_list = filter_limitup_stock(context, initial_list)
    initial_list = filter_limitdown_stock(context, initial_list)
    initial_list = get_history_highlimit(context, initial_list, g.limit_days_window)
    initial_list = get_start_point(context, initial_list, g.limit_days_window)
    stock_list = get_stock_industry(initial_list)
    return stock_list[:g.stock_num * 2]

def filter_low_price_stock(context, stock_list):
    if not stock_list:
        return []
    try:
        df = get_price(stock_list, end_date=context.previous_date, count=1,
                       fields=['close'], panel=False)
        if df is None or df.empty:
            return stock_list
        return df[df['close'] >= g.min_price]['code'].tolist()
    except Exception:
        return stock_list

def filter_loss_black(context, stock_list):
    if not stock_list:
        return []
    result = []
    for stock in stock_list:
        if stock in g.loss_blacklist and context.current_dt < g.loss_blacklist[stock]:
            continue
        result.append(stock)
    return result

def weekly_adjustment(context):
    if g.no_trading_today_signal:
        return

    g.not_buy_again = []
    g.target_list = get_stock_list(context)
    target_list = g.target_list
    candidate_set = set(g.target_list)

    for stock in g.hold_list:
        if stock in candidate_set:
            continue
        if stock in g.yesterday_HL_list:
            continue
        position = context.portfolio.positions[stock]
        close_position(position)

    buy_security_with_limit(context, target_list, g.stock_num)

    for position in list(context.portfolio.positions.values()):
        g.not_buy_again.append(position.security)

def buy_security_with_limit(context, target_list, target_num):
    position_count = len(context.portfolio.positions)
    if target_num <= position_count:
        return

    total_value = context.portfolio.total_value
    invest_value = total_value * 0.98
    value_per_stock = invest_value / target_num

    bought_num = 0
    for stock in target_list:
        if context.portfolio.positions[stock].total_amount > 0:
            continue
        if bought_num >= (target_num - position_count):
            break
        if context.portfolio.available_cash < value_per_stock * 0.5:
            break
        if open_position(stock, value_per_stock):
            g.not_buy_again.append(stock)
            bought_num += 1
            if len(context.portfolio.positions) >= target_num:
                break

def check_limit_up(context):
    if not g.yesterday_HL_list:
        return
    cd_all = get_current_data()
    for stock in g.yesterday_HL_list[:]:
        if stock not in context.portfolio.positions:
            continue
        pos = context.portfolio.positions[stock]
        if pos.closeable_amount <= 0:
            continue
        if stock not in cd_all:
            continue
        cd = cd_all[stock]
        if cd.paused:
            continue
        now_time = context.current_dt
        current_data = get_price(stock, end_date=now_time, frequency='1m',
                                 fields=['close', 'high_limit'], skip_paused=False,
                                 fq='pre', count=1, panel=False, fill_paused=True)
        if current_data is not None and not current_data.empty:
            if current_data.iloc[0, 0] < current_data.iloc[0, 1]:
                close_position(pos)
                g.reason_to_sell = 'limitup'

def trade_afternoon(context):
    if g.no_trading_today_signal:
        return
    check_limit_up(context)
    huanshou(context)
    check_remain_amount(context)

def sell_stocks(context):
    if not g.run_stoploss:
        return

    if g.stoploss_strategy == 1:
        for stock in context.portfolio.positions.keys():
            pos = context.portfolio.positions[stock]
            if pos.price >= pos.avg_cost * 2:
                close_position(pos)
            elif pos.price < pos.avg_cost * g.stoploss_limit:
                close_position(pos)
                g.reason_to_sell = 'stoploss'
                g.loss_blacklist[stock] = context.current_dt + timedelta(days=g.loss_blacklist_days)
    elif g.stoploss_strategy == 2:
        stock_df = get_price(security=get_index_stocks('399101.XSHE'),
                             end_date=context.previous_date, frequency='daily',
                             fields=['close', 'open'], count=1, panel=False)
        down_ratio = (stock_df['close'] / stock_df['open']).mean()
        if down_ratio <= g.stoploss_market:
            g.reason_to_sell = 'stoploss'
            for stock in context.portfolio.positions.keys():
                close_position(context.portfolio.positions[stock])
    elif g.stoploss_strategy == 3:
        stock_df = get_price(security=get_index_stocks('399101.XSHE'),
                             end_date=context.previous_date, frequency='daily',
                             fields=['close', 'open'], count=1, panel=False)
        down_ratio = (stock_df['close'] / stock_df['open']).mean()
        if down_ratio <= g.stoploss_market:
            g.reason_to_sell = 'stoploss'
            for stock in context.portfolio.positions.keys():
                close_position(context.portfolio.positions[stock])
        else:
            for stock in context.portfolio.positions.keys():
                pos = context.portfolio.positions[stock]
                if pos.price < pos.avg_cost * g.stoploss_limit:
                    close_position(pos)
                    g.reason_to_sell = 'stoploss'
                    g.loss_blacklist[stock] = context.current_dt + timedelta(days=g.loss_blacklist_days)

def huanshou(context):
    current_data = get_current_data()
    shrink, expand = 0.003, 0.1
    for stock in context.portfolio.positions:
        if current_data[stock].paused:
            continue
        if current_data[stock].last_price >= current_data[stock].high_limit * 0.97:
            continue
        if context.portfolio.positions[stock].closeable_amount == 0:
            continue
        rt = huanshoulv(context, stock, False)
        avg = huanshoulv(context, stock, True)
        if avg == 0:
            continue
        r = rt / avg
        if avg < shrink:
            close_position(context.portfolio.positions[stock])
            g.reason_to_sell = 'limitup'
        elif rt > expand and r > 2:
            close_position(context.portfolio.positions[stock])
            g.reason_to_sell = 'limitup'

def huanshoulv(context, stock, is_avg=False):
    if is_avg:
        df_volume = get_price(stock, end_date=context.previous_date,
                              frequency='daily', fields=['volume'], count=20, panel=False)
        if df_volume is None or df_volume.empty:
            return 0.0
        df_cap = get_valuation(stock, end_date=context.previous_date,
                               fields=['circulating_cap'], count=1)
        cap = df_cap['circulating_cap'].iloc[0] if not df_cap.empty else 0
        if cap == 0:
            return 0.0
        df_volume['turnover_ratio'] = df_volume['volume'] / (cap * 10000)
        return df_volume['turnover_ratio'].mean()
    else:
        date_now = context.current_dt
        df_vol = get_price(stock, start_date=date_now.date(), end_date=date_now,
                           frequency='1m', fields=['volume'], skip_paused=False,
                           fq='pre', panel=True, fill_paused=False)
        if df_vol is None or df_vol.empty:
            return 0.0
        volume = df_vol['volume'].sum()
        date_pre = context.previous_date
        df_cap = get_valuation(stock, end_date=date_pre,
                               fields=['circulating_cap'], count=1)
        cap = df_cap['circulating_cap'].iloc[0] if not df_cap.empty else 0
        if cap == 0:
            return 0.0
        return volume / (cap * 10000)

def check_remain_amount(context):
    if g.reason_to_sell == 'limitup':
        g.hold_list = [p.security for p in context.portfolio.positions.values()]
        if len(g.hold_list) < g.stock_num:
            target_list = get_stock_list(context)
            target_list = filter_not_buy_again(target_list)
            target_list = target_list[:min(g.stock_num, len(target_list))]
            buy_security_with_limit(context, target_list, g.stock_num)
        g.reason_to_sell = ''
    else:
        g.reason_to_sell = ''

def filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]

def filter_st_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list
            if not current_data[stock].is_st
            and 'ST' not in current_data[stock].name
            and '*' not in current_data[stock].name
            and '退' not in current_data[stock].name]

def filter_kcbj_stock(stock_list):
    result = []
    for stock in stock_list:
        if stock[0] == '4' or stock[0] == '8' or stock[:2] == '68':
            continue
        result.append(stock)
    return result

def filter_limitup_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] < current_data[stock].high_limit]

def filter_limitdown_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] > current_data[stock].low_limit]

def filter_new_stock(context, stock_list):
    yesterday = context.previous_date
    return [stock for stock in stock_list
            if not yesterday - get_security_info(stock).start_date < timedelta(days=375)]

def filter_not_buy_again(stock_list):
    return [stock for stock in stock_list if stock not in g.not_buy_again]

def get_stock_industry(stock):
    result = get_industry(security=stock)
    selected_stocks = []
    industry_list = []
    for stock_code, info in result.items():
        if 'sw_l2' in info and info['sw_l2']:
            industry_name = info['sw_l2']['industry_name']
            if industry_name not in industry_list:
                industry_list.append(industry_name)
                selected_stocks.append(stock_code)
                if len(industry_list) == 10:
                    break
    return selected_stocks

def order_target_value_(security, value):
    return order_target_value(security, value)

def open_position(security, value):
    order = order_target_value_(security, value)
    if order is not None and order.filled > 0:
        return True
    return False

def close_position(position):
    security = position.security
    order = order_target_value_(security, 0)
    if order is not None:
        if order.status == OrderStatus.held and order.filled == order.amount:
            return True
    return False

def today_is_between(context):
    today = context.current_dt.strftime('%m-%d')
    if g.pass_april:
        if (('04-01' <= today) and (today <= '04-30')) or (('01-01' <= today) and (today <= '01-30')):
            return True
        else:
            return False
    else:
        return False

def close_account(context):
    if g.no_trading_today_signal:
        if len(g.hold_list) != 0:
            for stock in g.hold_list:
                position = context.portfolio.positions.get(stock)
                if position is not None and position.total_amount > 0:
                    close_position(position)

def handle_data(context, data=None):
    pass