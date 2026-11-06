# Clone from JoinQuant
# postId: bc753923d426cdf77266cc7ee64e7398
# backtestId: 7d625e207814bb3453ffc1ecff49bebf
# title: 亏懵了吧，来看看改版的红利增强策略！

# 克隆自聚宽文章：https://www.joinquant.com/post/61657
# 标题：红利可以抄底吗
# 作者：wywy1995

# ============================================================================
# 【HLD-P07-3J-2】红利增强（3J + 月线MACD激进择时）
# ----------------------------------------------------------------------------
# 基座：HLD-P07-3J = 现金优化 + 移动止盈（盈利20%+回落5%）
# 本版新增：月线MACD择时（沪深300 月线红绿柱），激进调整双轨配比：
#   红柱（进攻）：低波2 + 价值6
#   绿柱（防御）：低波6 + 价值2
# 其余逻辑（现金优化、移动止盈、双轨选股、限价单）与 3J 完全一致
#
# 【实验设计】MACD 择时三版本对照：
#   3J-1 = 双轨温和切换（价值 3↔5）
#   3J-2 = 双轨激进切换（价值 2↔6）
#   3J-3 = 仅价值轨切换（低波固定5，价值 1↔5）
# ============================================================================

import datetime

import pandas as pd
import talib
import talib as tb
from jqdata import *
from jqfactor import get_factor_values


def initialize(context):

    set_option("avoid_future_data", True)
    set_option('use_real_price', True)
    set_benchmark('000015.XSHG')
    log.set_level('order', 'error')
    log.set_level('history', 'error')
    log.set_level('system', 'error')

    g.sell_list = []
    g.buy_df = []
    g.target_num = [5, 3]          # 默认基准，每月由 MACD 择时覆盖
    g.high_limit_list = []

    # 移动止盈参数
    g.high_prices = {}
    g.profit_lock = 0.20
    g.trailing_drawdown = 0.05

    run_daily(prepare_stock_list, '09:00')
    run_monthly(get_stock_list, 1, '09:01')
    run_monthly(trade, 1, '09:30')
    run_daily(check_limit_up, '10:00')
    run_daily(trailing_stop_check, time='14:50')


# 【09:00 晨间准备】更新持仓中"昨日涨停"的股票列表
def prepare_stock_list(context):

    g.high_limit_list = []
    g.hold_list = list(context.portfolio.positions)
    if len(g.hold_list) != 0:
        df = get_price(g.hold_list, end_date=context.previous_date, frequency='daily', fields=['close', 'high_limit'], count=1, panel=False, fill_paused=False, skip_paused=False).dropna()
        df = df[df['close'] == df['high_limit']]
        g.high_limit_list = list(df.code)


# 【现金优化】贪心分配 + 尾款轮询均摊，单只仓位帽 1.3 × 均等仓位
def allocate_cash(buy_list, price_map, total_cash):
    n = len(buy_list)
    if n == 0:
        return {}

    prev_close = {s: price_map[s] / 1.05 for s in buy_list}
    equal_value = total_cash / n
    cap_value = equal_value * 1.3

    amounts = {s: 0 for s in buy_list}
    remaining = total_cash

    sorted_codes = sorted(buy_list, key=lambda s: prev_close[s])
    for s in sorted_codes:
        pc = prev_close[s]
        if pc <= 0:
            continue
        target_value = min(equal_value, cap_value)
        lots = int(target_value / pc / 100)
        while lots > 0 and lots * 100 * pc > remaining:
            lots -= 1
        amounts[s] = lots * 100
        remaining -= lots * 100 * pc

    while True:
        progressed = False
        for s in sorted_codes:
            pc = prev_close[s]
            if pc <= 0:
                continue
            current_value = amounts[s] * pc
            if current_value + 100 * pc > cap_value:
                continue
            if remaining >= 100 * pc:
                amounts[s] += 100
                remaining -= 100 * pc
                progressed = True
        if not progressed:
            break

    return amounts


# 【月线MACD】计算沪深300月线MACD红绿柱
def get_macd_M(stock_list, check_date):
    macd_list = {}
    if isinstance(check_date, str):
        check_date = datetime.datetime.strptime(check_date, "%Y-%m-%d %H:%M:%S")
    if isinstance(stock_list, str):
        stock_list = [stock_list]
    for stock in stock_list:
        array = get_bars(security=stock, count=500, unit='1M', fields=['close'], include_now=False, end_dt=check_date, fq_ref_date=check_date)
        close_list = array['close']
        dif, dea, macd = tb.MACD(close_list, fastperiod=12, slowperiod=26, signalperiod=9)
        last_dif = dif[-1]
        last_dea = dea[-1]
        last_macd = macd[-1]
        macd_dic = (last_dif, last_dea, last_macd * 2)
        macd_list[stock] = macd_dic
    return macd_list


def check_macd_trend(context):
    """月线MACD红绿柱判断：True=红柱(进攻,多配价值)，False=绿柱(防御,多配低波)"""
    yesterday = context.previous_date
    re_value = get_macd_M(['000300.XSHG'], yesterday)
    dif, dea, macd = re_value['000300.XSHG']
    if macd > 0:
        return True
    else:
        return False


# 【月度选股 09:01】双轨合成 + MACD择时配比 + 现金优化分配
def get_stock_list(context):

    g.buy_df = pd.DataFrame(index=[], columns=['name', 'price', 'amount', 'value'])
    yesterday = str(context.previous_date)
    today = context.current_dt

    # ---------- MACD 月线择时（激进） ----------
    macd_bull = check_macd_trend(context)
    if macd_bull:
        g.target_num = [2, 6]  # 红柱：低波2 + 价值6（进攻）
        print('月线MACD红柱 → 进攻: 低波2 + 价值6')
    else:
        g.target_num = [6, 2]  # 绿柱：低波6 + 价值2（防御）
        print('月线MACD绿柱 → 防御: 低波6 + 价值2')

    # 初始过滤
    initial_list = get_all_securities('stock', today).index.tolist()
    initial_list = filter_new_stock(context, initial_list)
    initial_list = filter_kcb_stock(initial_list)
    initial_list = filter_st_stock(initial_list)
    initial_list = filter_paused_stock(initial_list)

    # 红利低波
    stock_list = initial_list
    stock_list = get_dividend_ratio_filter_list(context, stock_list, False, 0.00, 0.10, 0.03)
    stock_list = get_factor_filter_list(context, stock_list, 'beta', True, 0.00, 0.50)
    HLDB_list = stock_list[:min(g.target_num[0], len(stock_list))]

    # 红利价值
    stock_list = initial_list
    df = get_fundamentals(query(
            valuation.code,
        ).filter(
            valuation.code.in_(stock_list),
            valuation.pe_ratio.between(5, 50),
            indicator.inc_return.between(5, 100),
            indicator.inc_total_revenue_year_on_year.between(5, 100),
            indicator.inc_net_profit_year_on_year.between(10, 100),
        ))
    stock_list = list(df.code)
    stock_list = get_dividend_ratio_filter_list(context, stock_list, False, 0.00, 0.10, 0.03)
    HLJZ_list = stock_list[:min(g.target_num[1], len(stock_list))]

    # 两轨合并去重
    target_list = list(set(HLDB_list).union(set(HLJZ_list)))
    g.sell_list = [s for s in g.hold_list if s not in target_list and s not in g.high_limit_list]
    buy_list = [s for s in target_list if s not in g.hold_list]

    # 计算下单价格与数量（现金优化）
    total_cash = context.portfolio.available_cash
    if len(g.sell_list) > 0:
        for s in g.sell_list:
            total_cash += context.portfolio.positions[s].value

    if len(buy_list) > 0:
        df = get_price(buy_list, end_date=yesterday, frequency='1d', count=1, fields=['close'], fq='pre', panel=False, skip_paused=False, fill_paused=True).set_index('code')
        price_map = {}
        for s in buy_list:
            price_map[s] = round(df.loc[s, 'close'] * 1.05, 2)
        amounts = allocate_cash(buy_list, price_map, total_cash)
        g.buy_df['name'] = [get_security_info(s, yesterday).display_name for s in buy_list]
        g.buy_df['price'] = [price_map[s] for s in buy_list]
        g.buy_df['amount'] = [amounts[s] for s in buy_list]
        g.buy_df['value'] = [price_map[s] * amounts[s] for s in buy_list]
        g.buy_df.index = buy_list

    print('卖出', g.sell_list)
    print('———————————————————————————————————')
    print('红利低波', g.buy_df)
    print('———————————————————————————————————')


# 【每月1日 09:30 执行交易】
def trade(context):

    current_data = get_current_data()

    for s in g.sell_list:
        if current_data[s].last_price < current_data[s].high_limit:
            order_target_value(s, 0)
            if s in g.high_prices:
                del g.high_prices[s]

    df = g.buy_df
    for s in list(df.index):
        if df.loc[s, 'amount'] <= 0:
            continue
        print('买入', [s, df.loc[s, 'name']])
        order(s, df.loc[s, 'amount'], LimitOrderStyle(df.loc[s, 'price']))
        print('———————————————————————————————————')


# 【10:00 昨日涨停观察】
def check_limit_up(context):
    current_data = get_current_data()

    if g.high_limit_list != []:
        for s in g.high_limit_list:
            if current_data[s].last_price < current_data[s].high_limit:
                order_target_value(s, 0)
                if s in g.high_prices:
                    del g.high_prices[s]
                print(s, '涨停打开，卖出')
                print('———————————————————————————————————')
            else:
                print(s, '涨停，继续持有')
                print('———————————————————————————————————')


# 【14:50 移动止盈】曾盈利20% 且 从最高点回落5% → 卖出（涨停跳过）
def trailing_stop_check(context):
    current_data = get_current_data()

    for s in list(context.portfolio.positions.keys()):
        pos = context.portfolio.positions[s]
        if pos.total_amount <= 0:
            continue
        price = current_data[s].last_price
        avg_cost = pos.avg_cost
        if price <= 0 or avg_cost <= 0:
            continue

        if s not in g.high_prices:
            g.high_prices[s] = max(price, avg_cost)
        elif price > g.high_prices[s]:
            g.high_prices[s] = price

        if price >= current_data[s].high_limit:
            continue

        if g.high_prices[s] >= avg_cost * (1 + g.profit_lock) and price <= g.high_prices[s] * (1 - g.trailing_drawdown):
            order_target_value(s, 0)
            print(s, current_data[s].name, '移动止盈：曾盈利20%且从高点回落5%')
            print('———————————————————————————————————')
            if s in g.high_prices:
                del g.high_prices[s]


############################################################################################################################################################################

# ==================== 过滤函数 ====================
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

def filter_kcb_stock(stock_list):
    return [stock for stock in stock_list if ((stock[0] != '4') and (stock[0] != '8') and (stock[0:2] != '68'))]

def filter_new_stock(context, stock_list):
    yesterday = context.previous_date
    return [stock for stock in stock_list if not yesterday - get_security_info(stock).start_date < datetime.timedelta(days=250)]

# 【股息率筛选】近一年实际分红 ÷ 总市值，排序截取区间
def get_dividend_ratio_filter_list(context, stock_list, sort, p1, p2, threshold):
    time1 = context.previous_date
    time0 = time1 - datetime.timedelta(days=365)
    interval = 1000
    list_len = len(stock_list)
    q = query(finance.STK_XR_XD.code, finance.STK_XR_XD.a_registration_date, finance.STK_XR_XD.bonus_amount_rmb
    ).filter(
        finance.STK_XR_XD.a_registration_date >= time0,
        finance.STK_XR_XD.a_registration_date <= time1,
        finance.STK_XR_XD.code.in_(stock_list[:min(list_len, interval)]))
    df = finance.run_query(q)
    if list_len > interval:
        df_num = list_len // interval
        for i in range(df_num):
            q = query(finance.STK_XR_XD.code, finance.STK_XR_XD.a_registration_date, finance.STK_XR_XD.bonus_amount_rmb
            ).filter(
                finance.STK_XR_XD.a_registration_date >= time0,
                finance.STK_XR_XD.a_registration_date <= time1,
                finance.STK_XR_XD.code.in_(stock_list[interval * (i + 1):min(list_len, interval * (i + 2))]))
            temp_df = finance.run_query(q)
            df = df.append(temp_df)
    dividend = df.fillna(0)
    dividend = dividend.set_index('code')
    dividend = dividend.groupby('code').sum()
    temp_list = list(dividend.index)
    q = query(valuation.code, valuation.market_cap).filter(valuation.code.in_(temp_list))
    cap = get_fundamentals(q, date=time1)
    cap = cap.set_index('code')
    df = pd.concat([dividend, cap], axis=1, sort=False)
    df['dividend_ratio'] = (df['bonus_amount_rmb'] / 10000) / df['market_cap']
    df = df.sort_values(by=['dividend_ratio'], ascending=sort)
    df = df[int(p1 * len(df)):int(p2 * len(df))]
    df = df[df['dividend_ratio'] > threshold]
    return list(df.index)

# 【因子排序过滤】beta 升序取前50%（低波）
def get_factor_filter_list(context, stock_list, jqfactor, sort, p1, p2):
    yesterday = context.previous_date
    score_list = get_factor_values(stock_list, jqfactor, end_date=yesterday, count=1)[jqfactor].iloc[0].tolist()
    df = pd.DataFrame(columns=['code', 'score'])
    df['code'] = stock_list
    df['score'] = score_list
    df = df.dropna()
    df.sort_values(by='score', ascending=sort, inplace=True)
    final_list = list(df.code)[int(p1 * len(df)):int(p2 * len(df))]
    return final_list
