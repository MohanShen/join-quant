# Clone from JoinQuant
# postId: 4e2baa956364e2351eafe8d38e909cea
# backtestId: d87dfcd8659d5216691d8f780d5c1f90
# title: 今年以来68%，适合震荡上行市场，10盘不到20天30%

#连板数 count >= 3 为真龙头，跳过5%回撤止盈。连板数=2的执行回撤止盈。卖出优先级：
#涨停 → 持有
#跌停 → 无法卖出
#非龙头回撤≥5% → 清仓（新增）
#亏损 → 清仓
#盈利 → 卖一半
#尾盘没涨停 → 清仓
#龙头票不受第3条约束，让它自由奔跑到不涨停或尾盘

from jqdata import *
from jqfactor import *
from jqlib.technical_analysis import *
import datetime as dt
import pandas as pd
import numpy as np

def initialize(context):
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_option("match_by_signal", True)
    log.set_level('system', 'error')
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003,
                             close_today_commission=0, min_commission=5), type='stock')

    g.buy_pct = 2
    g.jqfactor = 'VOL5'
    g.sort = True
    g.emo_count = []
    g.top_n = 5

    g.today_list = []
    g.target_list = []
    g.position_high = {}
    g.dragon_count = {}

    run_daily(sell_check_open, '09:27')
    run_daily(get_stock_list, '09:25:00')
    run_daily(buy, '09:30:00')
    run_daily(update_position_high, '09:31')
    run_daily(update_position_high, '10:00')
    run_daily(sell_pullback, '10:00')
    run_daily(sell_check_morning, '10:30')
    run_daily(update_position_high, '11:00')
    run_daily(update_position_high, '13:30')
    run_daily(update_position_high, '14:00')
    run_daily(sell_pullback, '14:00')
    run_daily(sell_check_afternoon, '14:30')
    run_daily(print_position_info, '15:02')


def update_position_high(context):
    current_data = get_current_data()
    for stock in list(context.portfolio.positions.keys()):
        pos = context.portfolio.positions[stock]
        if pos.total_amount <= 0:
            continue
        current_price = current_data[stock].last_price
        if current_price is None or current_price <= 0:
            continue
        if stock not in g.position_high or current_price > g.position_high[stock]:
            g.position_high[stock] = current_price


def sell_pullback(context):
    current_data = get_current_data()
    for stock in list(context.portfolio.positions.keys()):
        pos = context.portfolio.positions[stock]
        if pos.closeable_amount <= 0:
            continue
        if stock not in g.position_high:
            continue
        avg_cost = pos.avg_cost
        current_price = current_data[stock].last_price
        high_price = g.position_high[stock]
        if avg_cost <= 0 or current_price <= 0 or high_price <= avg_cost:
            continue

        pullback = (high_price - current_price) / high_price
        dragon_count = g.dragon_count.get(stock, 1)

        if dragon_count >= 3:
            continue

        if pullback >= 0.05:
            if current_price > current_data[stock].low_limit:
                try:
                    stock_name = get_security_info(stock).display_name
                except:
                    stock_name = stock
                log.info('[Pullback TP] %s(%s) cost:%.2f high:%.2f now:%.2f pullback:%.1f%%' % (
                    stock_name, stock, avg_cost, high_price, current_price, pullback * 100))
                order_target(stock, 0)
                if stock in g.position_high:
                    del g.position_high[stock]
                if stock in g.dragon_count:
                    del g.dragon_count[stock]


def get_stock_list(context):
    date = context.previous_date
    date = transform_date(date, 'str')

    initial_list = prepare_stock_list(date)
    hl_list = get_hl_stock(initial_list, date)
    ccd_hl = get_continue_count_df(hl_list, date, 20) if len(hl_list) != 0 else pd.DataFrame(index=[], data={'count':[],'extreme_count':[]})
    ccd_lb = ccd_hl[ccd_hl['count']>=2]
    lt_lb = list(ccd_lb.index)
    dct = get_concept(lt_lb, date)

    if market_signal(context):
        g.buy_pct = 2
        log.info("market good, pct=2")
    else:
        g.buy_pct = 1
        log.info("market weak, pct=1")

    hot_concepts = get_hot_concept(dct, ccd_lb, date)

    stock_list = []
    combined_df = pd.DataFrame(index=[], data={'count':[],'extreme_count':[]})
    for concept in hot_concepts:
        hot_stocks = get_stocks_by_concept_name(concept)
        hot_stocks = filter_stock_list(hot_stocks, date)
        hl_hot_list = list(set(hl_list) & set(hot_stocks))
        ccd = ccd_hl[ccd_hl.index.isin(hl_hot_list)]
        combined_df = pd.concat([combined_df, ccd], ignore_index=False)

    occurrence_count = combined_df.groupby(combined_df.index).size()
    final_df = combined_df[~combined_df.index.duplicated(keep='last')]
    final_df.loc[:, 'occurrence'] = final_df.index.map(occurrence_count)
    final_df = final_df[(final_df['occurrence']>=2) & (final_df['extreme_count']/final_df['count']<=0.66)]
    final_df = final_df.sort_values('count', ascending=False)
    log.info(final_df)
    lt = list(final_df.index)[:]

    condition_dct = {}
    current_data = get_current_data()
    for s in lt:
        try:
            hist = attribute_history(security=s, count=1, unit='1d', fields=('close', 'low', 'high', 'paused', 'high_limit'),
                                     skip_paused=False, df=False, fq='pre')
            condition = ''
            pct_chg = (current_data[s].day_open - hist['close'][-1]) / hist['close'][-1]
            if (pct_chg >= 0.02) and (pct_chg <= 0.08) and (current_data[s].day_open <= current_data[s].high_limit - 0.03):
                condition += 'buy'
            if len(condition) != 0:
                condition_dct[s] = get_security_info(s, date).display_name + ' —— ' + condition
        except:
            pass
    stock_list = stock_list + list(condition_dct.keys())

    df = get_factor_filter_df(context, stock_list, g.jqfactor, g.sort)
    stock_list = list(df.index)
    log.info('before factor: %s' % stock_list)
    stock_list = stock_list[:g.top_n]
    log.info('after factor (top%d): %s' % (g.top_n, stock_list))

    # MOD: 打印选股结果时带上名称
    for s in stock_list:
        try:
            name = get_security_info(s).display_name
        except:
            name = s
        log.info('选股: %s(%s)' % (name, s))

    g.dragon_count = {}
    for s in stock_list:
        if s in final_df.index:
            g.dragon_count[s] = int(final_df.loc[s, 'count'])
        else:
            g.dragon_count[s] = 1

    hold_list = list(context.portfolio.positions)
    g.target_list = [x for x in stock_list if x not in hold_list]
    g.target_list = g.target_list[:]


def buy(context):
    current_data = get_current_data()
    if len(g.target_list) > 0:
        value1 = context.portfolio.total_value / g.buy_pct
        value = min(context.portfolio.available_cash, value1) / len(g.target_list)
        for s in g.target_list:
            # MOD: 获取股票名称用于日志
            try:
                stock_name = get_security_info(s).display_name
            except:
                stock_name = s

            if current_data[s].paused or 'ST' in current_data[s].name or '退' in current_data[s].name:
                log.info('skip %s(%s) paused/ST' % (stock_name, s))  # MOD: 加名称
                continue
            if context.portfolio.available_cash / current_data[s].last_price > 100:
                order_value(s, value, LimitOrderStyle(current_data[s].day_open))
                log.info('buy %s(%s)' % (stock_name, s))  # MOD: 加名称
                g.position_high[s] = current_data[s].day_open


def sell_check_open(context):
    current_data = get_current_data()
    for stock in context.portfolio.positions:
        amount = context.portfolio.positions[stock].closeable_amount
        if amount == 0:
            continue
        open_price = current_data[stock].day_open
        hist = attribute_history(stock, 1, '1d', ['close'], skip_paused=False)
        if len(hist) > 0:
            prev_close = hist['close'][0]
        else:
            prev_close = current_data[stock].high_limit / 1.1

        # MOD: 统一在loop开头获取名称
        try:
            stock_name = get_security_info(stock).display_name
        except:
            stock_name = stock

        if open_price < prev_close and open_price > current_data[stock].low_limit:
            log.info('【open stop】%s(%s) open:%.2f prev:%.2f sell' % (stock_name, stock, open_price, prev_close))  # MOD: 加名称
            order_target(stock, 0)
            if stock in g.position_high:
                del g.position_high[stock]
            if stock in g.dragon_count:
                del g.dragon_count[stock]
        elif open_price == current_data[stock].low_limit:
            log.info('【open stop】%s(%s) limit down, cannot sell' % (stock_name, stock))  # MOD: 加名称


def sell_check_morning(context):
    current_data = get_current_data()
    for stock in context.portfolio.positions:
        amount = context.portfolio.positions[stock].closeable_amount
        if amount == 0:
            continue
        curr_price = current_data[stock].last_price
        high_limit = current_data[stock].high_limit
        low_limit = current_data[stock].low_limit
        avg_cost = context.portfolio.positions[stock].avg_cost
        is_limit = curr_price >= (high_limit - 0.01)

        # MOD: loop开头统一获取名称
        try:
            stock_name = get_security_info(stock).display_name
        except:
            stock_name = stock

        if is_limit:
            log.info('【10:30 hold】%s(%s) limit up' % (stock_name, stock))  # MOD: 加名称
            continue

        if curr_price == low_limit:
            log.info('%s(%s) limit down, cannot sell' % (stock_name, stock))  # MOD: 加名称
            continue

        # pullback check (non-dragon only)
        if stock in g.position_high and avg_cost > 0:
            high_price = g.position_high[stock]
            pullback = (high_price - curr_price) / high_price if high_price > 0 else 0
            dragon_count = g.dragon_count.get(stock, 1)
            if dragon_count < 3 and pullback >= 0.05 and curr_price > avg_cost:
                log.info('【10:30 pullback TP】%s(%s) pullback %.1f%% sell' % (stock_name, stock, pullback * 100))  # MOD: 加名称
                order_target(stock, 0)
                if stock in g.position_high:
                    del g.position_high[stock]
                if stock in g.dragon_count:
                    del g.dragon_count[stock]
                continue

        pnl_ratio = (curr_price - avg_cost) / avg_cost
        if pnl_ratio < 0:
            log.info('【10:30 stop】%s(%s) loss %.2f%% sell' % (stock_name, stock, pnl_ratio * 100))  # MOD: 加名称
            order_target(stock, 0)
            if stock in g.position_high:
                del g.position_high[stock]
            if stock in g.dragon_count:
                del g.dragon_count[stock]
        else:
            target_amount = int(amount / 2 / 100) * 100
            if target_amount < 100:
                order_target(stock, 0)
                log.info('【10:30 TP】%s(%s) profit %.2f%% too few shares, sell all' % (stock_name, stock, pnl_ratio * 100))  # MOD: 加名称
            else:
                order_target(stock, target_amount)
                log.info('【10:30 TP】%s(%s) profit %.2f%% sell half' % (stock_name, stock, pnl_ratio * 100))  # MOD: 加名称
            if stock in g.position_high:
                del g.position_high[stock]
            if stock in g.dragon_count:
                del g.dragon_count[stock]


def sell_check_afternoon(context):
    current_data = get_current_data()
    for stock in context.portfolio.positions:
        amount = context.portfolio.positions[stock].closeable_amount
        if amount == 0:
            continue
        curr_price = current_data[stock].last_price
        high_limit = current_data[stock].high_limit
        low_limit = current_data[stock].low_limit
        avg_cost = context.portfolio.positions[stock].avg_cost
        is_limit = curr_price >= (high_limit - 0.01)

        # MOD: loop开头统一获取名称
        try:
            stock_name = get_security_info(stock).display_name
        except:
            stock_name = stock

        if is_limit:
            log.info('【14:30 hold】%s(%s) limit up overnight' % (stock_name, stock))  # MOD: 加名称
        else:
            if curr_price == low_limit:
                log.info('%s(%s) limit down, cannot sell' % (stock_name, stock))  # MOD: 加名称
                continue

            # pullback check (non-dragon only)
            if stock in g.position_high and avg_cost > 0:
                high_price = g.position_high[stock]
                pullback = (high_price - curr_price) / high_price if high_price > 0 else 0
                dragon_count = g.dragon_count.get(stock, 1)
                if dragon_count < 3 and pullback >= 0.05 and curr_price > avg_cost:
                    log.info('【14:30 pullback TP】%s(%s) pullback %.1f%% sell' % (stock_name, stock, pullback * 100))  # MOD: 加名称
                    order_target(stock, 0)
                    if stock in g.position_high:
                        del g.position_high[stock]
                    if stock in g.dragon_count:
                        del g.dragon_count[stock]
                    continue

            log.info('【14:30 clear】%s(%s) not limit up, sell' % (stock_name, stock))  # MOD: 加名称
            order_target(stock, 0)
            if stock in g.position_high:
                del g.position_high[stock]
            if stock in g.dragon_count:
                del g.dragon_count[stock]


# ==================== helper functions (unchanged except get_stocks_by_concept_name) ====================

def extract_concepts(data_dict):
    all_concepts = set()
    for stock_code, info in data_dict.items():
        if 'jq_concept' in info:
            for concept_dict in info['jq_concept']:
                all_concepts.add(concept_dict['concept_name'])
    return list(all_concepts)


def transform_date(date, date_type):
    if type(date) == str:
        str_date = date
        dt_date = dt.datetime.strptime(date, '%Y-%m-%d')
        d_date = dt_date.date()
    elif type(date) == dt.datetime:
        str_date = date.strftime('%Y-%m-%d')
        dt_date = date
        d_date = dt_date.date()
    elif type(date) == dt.date:
        str_date = date.strftime('%Y-%m-%d')
        dt_date = dt.datetime.strptime(str_date, '%Y-%m-%d')
        d_date = date
    dct = {'str': str_date, 'dt': dt_date, 'd': d_date}
    return dct[date_type]


def get_shifted_date(date, days, days_type='T'):
    d_date = transform_date(date, 'd')
    yesterday = d_date + dt.timedelta(-1)
    if days_type == 'N':
        shifted_date = yesterday + dt.timedelta(days + 1)
    if days_type == 'T':
        all_trade_days = [i.strftime('%Y-%m-%d') for i in list(get_all_trade_days())]
        if str(yesterday) in all_trade_days:
            shifted_date = all_trade_days[all_trade_days.index(str(yesterday)) + days + 1]
        else:
            for i in range(100):
                last_trade_date = yesterday - dt.timedelta(i)
                if str(last_trade_date) in all_trade_days:
                    shifted_date = all_trade_days[all_trade_days.index(str(last_trade_date)) + days + 1]
                    break
    return str(shifted_date)


def filter_new_stock(initial_list, date, days=50):
    d_date = transform_date(date, 'd')
    return [stock for stock in initial_list if d_date - get_security_info(stock).start_date > dt.timedelta(days=days)]


def filter_st_stock(initial_list, date):
    str_date = transform_date(date, 'str')
    if get_shifted_date(str_date, 0, 'N') != get_shifted_date(str_date, 0, 'T'):
        str_date = get_shifted_date(str_date, -1, 'T')
    df = get_extras('is_st', initial_list, start_date=str_date, end_date=str_date, df=True)
    df = df.T
    df.columns = ['is_st']
    df = df[df['is_st'] == False]
    return list(df.index)


def filter_kcbj_stock(initial_list):
    return [stock for stock in initial_list if stock[0] != '4' and stock[0] != '8' and stock[:2] != '68']


def filter_paused_stock(initial_list, date):
    df = get_price(initial_list, end_date=date, frequency='daily', fields=['paused'], count=1, panel=False, fill_paused=True)
    df = df[df['paused'] == 0]
    return list(df.code)


def filter_name_stock(initial_list):
    current_data = get_current_data()
    filtered_list = []
    for s in initial_list:
        name = current_data[s].name
        if 'ST' not in name and '※ST' not in name and '退' not in name:
            filtered_list.append(s)
    return filtered_list


def filter_stock_list(stock_list, date):
    if not stock_list:
        return []
    stock_list = filter_kcbj_stock(stock_list)
    stock_list = filter_new_stock(stock_list, date)
    stock_list = filter_st_stock(stock_list, date)
    stock_list = filter_paused_stock(stock_list, date)
    stock_list = filter_name_stock(stock_list)
    return stock_list


def prepare_stock_list(date):
    initial_list = get_all_securities('stock', date).index.tolist()
    initial_list = filter_stock_list(initial_list, date)
    return initial_list


def get_init_emo_count(context, date):
    d1 = get_shifted_date(date, -3)
    d2 = get_shifted_date(date, -2)
    date_list = [d1, d2]
    emo_count = []
    for date in date_list:
        initial_list = prepare_stock_list(date)
        hl_list = get_hl_stock(initial_list, date)
        CCD = get_continue_count_df(hl_list, date, 20) if len(hl_list) != 0 else pd.DataFrame(index=[], data={'count':[],'extreme_count':[]})
        M = CCD['count'].max() if len(CCD) != 0 else 0
        emo_count.append(M)
    return emo_count


def market_signal(context):
    prices = attribute_history('000300.XSHG', 60, '1d', fields=['close'], skip_paused=True)
    if len(prices) < 60:
        return False
    ma5 = prices['close'].rolling(window=5).mean()
    ma20 = prices['close'].rolling(window=20).mean()
    return (ma5.iloc[-1] > ma20.iloc[-1] and prices['close'].iloc[-1] > ma5.iloc[-1])


def get_hot_concept(dct, ccd, date):
    concept_count = {}
    for key in dct:
        lb_count = ccd[ccd.index == key]['count'].iloc[0]
        for i in dct[key]['jq_concept']:
            if i['concept_name'] in concept_count.keys():
                concept_count[i['concept_name']] += lb_count
            else:
                if i['concept_name'] not in ['转融券标的', '融资融券', '深股通', '沪股通', '国企改革']:
                    concept_count[i['concept_name']] = 1
    df = pd.DataFrame(list(concept_count.items()), columns=['concept_name', 'concept_count'])
    df = df.set_index('concept_name')
    df = df.sort_values(by='concept_count', ascending=False)
    concept = list(df.index)[0:5]
    log.info('hot concepts (top5): %s' % concept)
    return concept


# ========== 修复的函数 ==========
def get_stocks_by_concept_name(concept_name):
    df_concepts = get_concepts()
    concept_code = df_concepts[df_concepts['name'] == concept_name].index
    if len(concept_code) == 0:
        log.info("warn: concept '%s' not found" % concept_name)
        return []
    try:
        stocks = get_concept_stocks(str(concept_code[0]))
        return stocks
    except Exception as e:
        log.info("[error] get concept stocks failed | concept: %s | %s" % (concept_name, str(e)))
        return []


def get_hl_stock(initial_list, date):
    df = get_price(initial_list, end_date=date, frequency='daily', fields=['close', 'high_limit'], count=1,
                  panel=False, fill_paused=False, skip_paused=False)
    df = df.dropna()
    df = df[df['close'] == df['high_limit']]
    return list(df.code)


def get_continue_count_df(hl_list, date, watch_days):
    if not hl_list:
        return pd.DataFrame(columns=['count', 'extreme_count'])
    df = get_price(hl_list, end_date=date, frequency='daily', fields=['close', 'high_limit', 'low'],
                   count=watch_days, panel=False, fill_paused=False, skip_paused=False)
    if df.empty:
        return pd.DataFrame(columns=['count', 'extreme_count'])
    results = []
    for stock in hl_list:
        stock_df = df[df['code'] == stock].copy()
        stock_df = stock_df.sort_values('time', ascending=False)
        stock_df.reset_index(drop=True, inplace=True)
        consecutive_count = 0
        extreme_count = 0
        for i in range(len(stock_df)):
            row = stock_df.iloc[i]
            if row['close'] == row['high_limit']:
                consecutive_count += 1
                if row['low'] == row['high_limit']:
                    extreme_count += 1
            else:
                break
        if consecutive_count > 0:
            results.append({'code': stock, 'count': consecutive_count, 'extreme_count': extreme_count})
    result_df = pd.DataFrame(results)
    if not result_df.empty:
        result_df.set_index('code', inplace=True)
    return result_df


def get_factor_filter_df(context, stock_list, jqfactor, sort):
    if len(stock_list) != 0:
        yesterday = context.previous_date
        score_list = get_factor_values(stock_list, jqfactor, end_date=yesterday, count=1)[jqfactor].iloc[0].tolist()
        df = pd.DataFrame(index=stock_list, data={'score': score_list}).dropna()
        df = df.sort_values(by='score', ascending=sort)
    else:
        df = pd.DataFrame(index=[], data={'score': []})
    return df


def print_position_info(context):
    for position in list(context.portfolio.positions.values()):
        securities = position.security
        cost = position.avg_cost
        price = position.price
        ret = 100 * (price / cost - 1)
        value = position.value
        amount = position.total_amount
        # MOD: 获取名称
        try:
            stock_name = get_security_info(securities).display_name
        except:
            stock_name = securities
        log.info('持仓 %s(%s) cost:%.2f price:%.2f ret:%.2f%% amount:%d value:%.2f' % (
            stock_name, securities, cost, price, ret, amount, value))
    log.info('==========')