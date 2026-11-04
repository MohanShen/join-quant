# Clone from JoinQuant
# postId: a197e98c725be30c0e03d318a341655d
# backtestId: 3fa8d04f3aa0d891032b3b5213a87a9d
# title: 小市值策略，绝对没有未来函数，12年回测数值稳定

# 融合策略：变种小狮子V2.2 + 韶华一致性顶层总开关
# 顶层逻辑：每日盘前计算韶华一致性信号作为总闸，清仓信号则暂停小狮子交易
from jqdata import *
from jqfactor import *
import numpy as np
import pandas as pd
from datetime import time, datetime, timedelta

# ====================== 初始化 ======================
def initialize(context):
    set_option('avoid_future_data', True)
    set_benchmark('000905.XSHG')
    set_option('use_real_price', True)
    set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
    set_slippage(FixedSlippage(0.0002))

    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'debug')

    # ------------- 变种小狮子原有全局变量 -------------
    g.no_trading_today_signal = False
    g.pass_april = True
    g.run_stoploss = True
    g.hold_list = []
    g.yesterday_HL_list = []
    g.target_list = []
    g.not_buy_again = []
    g.filter_loss_black = True
    g.loss_black = {}
    g.stock_num = 6
    g.up_price = 20
    g.limit_days_window = 3 * 250
    g.init_stock_count = 1000
    g.reason_to_sell = ''
    g.stoploss_strategy = 3
    g.stoploss_limit = 0.91
    g.stoploss_market = 0.93
    g.HV_control = False
    g.HV_duration = 120
    g.HV_ratio = 0.9
    g.stockL = []
    g.no_trading_buy = []
    g.no_trading_hold_signal = False

    # ------------- 韶华一致性指标参数（来自原文）-------------
    g.consistency_window = 120       # 一致性计算周期
    g.boll_n = 2                     # 布林带倍数
    g.consistency_signal = "照常"    # 每日盘前信号：满上 / 照常 / 清仓

    # 调度时间
    run_daily(prepare_stock_list, '9:05')
    run_daily(calc_consistency_signal, '8:30') #【新增】盘前8:30计算韶华一致性信号
    run_weekly(weekly_sell,2,'10:15')
    run_weekly(weekly_buy,2,'10:30')
    run_daily(sell_stocks, time='10:00')
    run_daily(trade_afternoon, time='14:20')
    run_daily(trade_afternoon, time='14:55')
    run_daily(close_account, '14:50')


# ====================== 【新增模块】韶华一致性指标计算 ======================
def calc_consistency_signal(context):
    """每日盘前计算一致性，输出信号：满上 / 照常 / 清仓"""
    yesterday = context.previous_date
    # 获取微盘股池（这里用中证1000替代微盘群体，可按需替换）
    stock_pool = get_index_stocks('000852.XSHG', date=yesterday)
    if len(stock_pool) < 50:
        g.consistency_signal = "清仓"
        log.info("一致性计算：股票池不足，信号=清仓")
        return

    # 获取窗口内每日涨跌幅
    price_df = get_price(stock_pool, end_date=yesterday, frequency='daily', fields=['close'],
                         count=g.consistency_window, panel=False, fill_paused=False)
    if price_df.empty:
        g.consistency_signal = "清仓"
        log.info("一致性计算：价格数据为空，信号=清仓")
        return
    # 透视表：行=时间，列=股票，值=收盘价
    price_pivot = price_df.pivot(index='time', columns='code', values='close')
    ret_df = price_pivot.pct_change()
    # 每日上涨股票占比 = 一致性
    consistency_series = (ret_df > 0).sum(axis=1) / ret_df.count(axis=1)
    cons_mean = consistency_series.mean()
    cons_std = consistency_series.std()
    cons_upper = cons_mean + g.boll_n * cons_std
    cons_lower = cons_mean - g.boll_n * cons_std
    latest_cons = consistency_series.iloc[-1]

    log.info(f"一致性指标：最新值{latest_cons:.4f}，均值{cons_mean:.4f}，上轨{cons_upper:.4f}，下轨{cons_lower:.4f}")
    # 原文规则：熊市判断，低于下轨=清仓；高于上轨=满上；其余照常
    if latest_cons <= cons_lower:
        g.consistency_signal = "清仓"
    elif latest_cons >= cons_upper:
        g.consistency_signal = "满上"
    else:
        g.consistency_signal = "照常"
    log.info(f"【韶华顶层信号】{g.consistency_signal}")


# ====================== 变种小狮子原有函数（仅增加顶层信号判断） ======================
def prepare_stock_list(context):
    g.hold_list= []
    for position in list(context.portfolio.positions.values()):
        stock = position.security
        g.hold_list.append(stock)
    if g.hold_list != []:
        df = get_price(g.hold_list, end_date=context.previous_date, frequency='daily', fields=['close','high_limit','low_limit'], count=1, panel=False, fill_paused=False)
        df = df[df['close'] == df['high_limit']]
        g.yesterday_HL_list = list(df.code)
    else:
        g.yesterday_HL_list = []
    g.no_trading_today_signal = today_is_between(context)


def get_history_highlimit(context, stock_list, days=3*250, p=0.10):
    df = get_price(
        stock_list,
        end_date=context.previous_date,
        frequency="daily",
        fields=["close", "high_limit"],
        count=days,
        panel=False,
        fill_paused=False,
    )
    df = df[df["close"] == df["high_limit"]]
    grouped_result = df.groupby('code').size().reset_index(name='count')
    grouped_result = grouped_result.sort_values(by=["count"], ascending=False)
    result_list = grouped_result["code"].tolist()[:int(len(grouped_result)*p)]
    log.info(f"涨停基因筛选：筛选前合计{len(grouped_result)}个， 筛选后合计{len(result_list)}个")
    return result_list


def get_start_point(context, stock_list, days=3*250):
    df = get_price(
        stock_list,
        end_date=context.previous_date,
        frequency="daily",
        fields=["open", "low", "close", "high_limit"],
        count=days,
        panel=False,
    )
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
            target_row = None
            for idx, row in previous_rows.iterrows():
                if row['close'] < row['open']:
                    stock_start_point[code] = row['low']
                    break
    for code, start_point in stock_start_point.items():
        last_price = current_data[code].last_price
        bias = last_price / start_point
        stock_price_bias[code] = bias
    sorted_list = sorted(stock_price_bias.items(), key=lambda x: x[1], reverse=False)
    return [i[0] for i in sorted_list]


def get_stock_list(context):
    final_list = []
    yesterday = context.previous_date
    initial_list = get_all_securities("stock", yesterday).index.tolist()
    initial_list = filter_new_stock(context, initial_list)
    initial_list = filter_kcbj_stock(initial_list)
    initial_list = filter_st_stock(initial_list)
    initial_list = filter_paused_stock(initial_list)
    if g.filter_loss_black:
        initial_list = filter_loss_black(context, initial_list, days=20)
    q = query(
        valuation.code,indicator.eps
        ).filter(
            valuation.code.in_(initial_list)
            ).order_by(
                valuation.market_cap.asc()
                )
    df = get_fundamentals(q, date=context.previous_date)
    initial_list = df['code'].tolist()[:g.init_stock_count]
    initial_list = filter_limitup_stock(context, initial_list)
    initial_list = filter_limitdown_stock(context, initial_list)
    initial_list = get_history_highlimit(context, initial_list, g.limit_days_window)
    initial_list = get_start_point(context, initial_list, g.limit_days_window)
    stock_list = get_stock_industry(initial_list)
    final_list = stock_list[:g.stock_num*2]
    log.info('今日候选股票:%s' % final_list)
    return final_list


def weekly_sell(context):
    # ========== 顶层总开关判断 ==========
    if g.consistency_signal == "清仓":
        log.info("【顶层信号清仓】本周禁止调仓，全部持仓卖出")
        for stock in g.hold_list:
            position = context.portfolio.positions[stock]
            close_position(position)
        return
    if g.no_trading_today_signal == False:
        current_data = get_current_data()
        close_no_trading_hold(context)
        g.not_buy_again = []
        g.target_list = get_stock_list(context)
        target_list = g.target_list[:g.stock_num*2]
        log.info(f"候选列表:{target_list}")
        for stock in g.hold_list:
            if (stock not in target_list) and (stock not in g.yesterday_HL_list) and (current_data[stock].last_price < current_data[stock].high_limit):
                log.info("卖出[%s]" % (stock))
                position = context.portfolio.positions[stock]
                close_position(position)
            else:
                log.info("继续持有[%s]" % (stock))


def weekly_buy(context):
    # ========== 顶层总开关判断 ==========
    if g.consistency_signal == "清仓":
        log.info("【顶层信号清仓】禁止买入")
        return
    if g.no_trading_today_signal == False:
        current_data = get_current_data()
        g.not_buy_again = []
        g.target_list = get_stock_list(context)
        target_list = g.target_list[:g.stock_num*2]
        log.info(f"候选列表:{target_list}")
        buy_security(context,target_list)


def check_limit_up(context):
    now_time = context.current_dt
    if g.yesterday_HL_list != []:
        for stock in g.yesterday_HL_list:
            if context.portfolio.positions[stock].closeable_amount > -100:
                current_data = get_price(stock, end_date=now_time, frequency='1m', fields=['close','high_limit'], skip_paused=False, fq='pre', count=1, panel=False, fill_paused=True)
                if current_data.iloc[0,0] < current_data.iloc[0,1]:
                    log.info("[%s]涨停打开，卖出" % (stock))
                    position = context.portfolio.positions[stock]
                    close_position(position)
                    g.reason_to_sell = 'limitup'
                else:
                    log.info("[%s]涨停，继续持有" % (stock))


def check_remain_amount(context):
    if g.reason_to_sell == 'limitup': #【修复bug is→==】
        g.hold_list= []
        for position in list(context.portfolio.positions.values()):
            stock = position.security
            g.hold_list.append(stock)
        if len(g.hold_list) < g.stock_num:
            target_list = get_stock_list(context)
            target_list = filter_not_buy_again(target_list)
            target_list = target_list[:min(g.stock_num, len(target_list))]
            log.info('有余额可用'+str(round((context.portfolio.cash),2))+'元。'+ str(target_list))
            buy_security(context,target_list)
        g.reason_to_sell = ''
    else:
        g.reason_to_sell = ''


def trade_afternoon(context):
    # ========== 顶层总开关判断 ==========
    if g.consistency_signal == "清仓":
        return
    if g.no_trading_today_signal == False:
        check_limit_up(context)
        if g.HV_control == True:
            check_high_volume(context)
        huanshou(context)
        check_remain_amount(context)


def sell_stocks(context):
    # ========== 顶层总开关判断 ==========
    if g.consistency_signal == "清仓":
        return
    if g.run_stoploss == True:
        if g.stoploss_strategy == 1:
            for stock in context.portfolio.positions.keys():
                if context.portfolio.positions[stock].price >= context.portfolio.positions[stock].avg_cost * 2:
                    order_target_value(stock, 0)
                    log.debug("收益100%止盈,卖出{}".format(stock))
                    g.loss_black[stock] = context.current_dt
                elif context.portfolio.positions[stock].price < context.portfolio.positions[stock].avg_cost * g.stoploss_limit:
                    order_target_value(stock, 0)
                    log.debug("触发止损,卖出{}".format(stock))
                    g.reason_to_sell = 'stoploss'
                    g.loss_black[stock] = context.current_dt
        elif g.stoploss_strategy == 2:
            stock_df = get_price(security=get_index_stocks('399101.XSHE'), end_date=context.previous_date, frequency='daily', fields=['close', 'open'], count=1,panel=False)
            down_ratio = (stock_df['close'] / stock_df['open']).mean()
            if down_ratio <= g.stoploss_market:
                g.reason_to_sell = 'stoploss'
                log.debug("大盘惨跌,平均降幅{:.2%}".format(down_ratio))
                for stock in context.portfolio.positions.keys():
                    order_target_value(stock, 0)
        elif g.stoploss_strategy == 3:
            stock_df = get_price(security=get_index_stocks('399101.XSHE'), end_date=context.previous_date, frequency='daily', fields=['close', 'open'], count=1,panel=False)
            down_ratio = (stock_df['close'] / stock_df['open']).mean()
            if down_ratio <= g.stoploss_market:
                g.reason_to_sell = 'stoploss'
                log.debug("大盘惨跌,平均降幅{:.2%}".format(down_ratio))
                for stock in context.portfolio.positions.keys():
                    order_target_value(stock, 0)
            else:
                for stock in context.portfolio.positions.keys():
                    if context.portfolio.positions[stock].price < context.portfolio.positions[stock].avg_cost * g.stoploss_limit:
                        order_target_value(stock, 0)
                        log.debug("触发止损,卖出{}".format(stock))
                        g.reason_to_sell = 'stoploss'
                        g.loss_black[stock] = context.current_dt


def check_high_volume(context):
    current_data = get_current_data()
    for stock in context.portfolio.positions:
        if current_data[stock].paused == True:
            continue
        if current_data[stock].last_price == current_data[stock].high_limit:
            continue
        if context.portfolio.positions[stock].closeable_amount ==0:
            continue
        df_volume = get_bars(stock,count=g.HV_duration,unit='1d',fields=['volume'],include_now=True, df=True)
        if df_volume['volume'].values[-1] > g.HV_ratio*df_volume['volume'].values.max():
            position = context.portfolio.positions[stock]
            r = close_position(position)
            log.info(f"[{stock}]天量，卖出, close_position: {r}")
            g.reason_to_sell = 'limitup'


# ====================== 过滤函数、交易辅助函数 ======================
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
    for stock in stock_list[:]:
        if stock[0] == '4' or stock[0] == '8' or stock[:2] == '68':
            stock_list.remove(stock)
    return stock_list

def filter_limitup_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] < current_data[stock].high_limit]

def filter_limitdown_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list if (stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] > current_data[stock].low_limit)]

def filter_new_stock(context,stock_list):
    yesterday = context.previous_date
    return [stock for stock in stock_list if not yesterday - get_security_info(stock).start_date <  timedelta(days=375)]

def filter_not_buy_again(stock_list):
    return [stock for stock in stock_list if stock not in g.not_buy_again]

def filter_loss_black(context, stock_list, days=20):
    result_list = []
    for stock in stock_list:
        if (
            stock in g.loss_black.keys()
            and context.current_dt - g.loss_black[stock]
            < timedelta(days=days)
        ):
            log.info(f"{stock}由于近期止损被过滤, 止损时间：{g.loss_black[stock]}")
            continue
        result_list.append(stock)
    return result_list

def get_stock_industry(stock):
    result = get_industry(security=stock)
    selected_stocks = []
    industry_list = []
    for stock_code, info in result.items():
        industry_name = info['sw_l2']['industry_name']
        if industry_name not in industry_list:
            industry_list.append(industry_name)
            selected_stocks.append(stock_code)
            if len(industry_list) == 10 :
                break
    return selected_stocks

def huanshoulv(context, stock, is_avg=False):
    if is_avg:
        start_date = context.current_dt - timedelta(days=20)
        end_date = context.previous_date
        df_volume = get_price(stock,end_date=end_date, frequency='daily', fields=['volume'],count=20)
        df_cap = get_valuation(stock, end_date=end_date, fields=['circulating_cap'], count=1)
        circulating_cap = df_cap['circulating_cap'].iloc[0] if not df_cap.empty else 0
        if circulating_cap == 0:
            return 0.0
        df_volume['turnover_ratio'] = df_volume['volume'] / (circulating_cap * 10000)
        return df_volume['turnover_ratio'].mean()
    else:
        date_now = context.current_dt
        df_vol = get_price(stock, start_date=date_now.date(), end_date=date_now, frequency='1m', fields=['volume'],
                           skip_paused=False, fq='pre', panel=True, fill_paused=False)
        volume = df_vol['volume'].sum()
        date_pre = context.previous_date
        df_circulating_cap = get_valuation(stock, end_date=date_pre, fields=['circulating_cap'], count=1)
        circulating_cap = df_circulating_cap['circulating_cap'].iloc[0]  if not df_circulating_cap.empty else 0
        if circulating_cap == 0:
            return 0.0
        turnover_ratio = volume / (circulating_cap * 10000)
        return turnover_ratio

def huanshou(context):
    ss = []
    current_data = get_current_data()
    shrink, expand = 0.003, 0.1
    for stock in context.portfolio.positions:
        if current_data[stock].paused == True:
            continue
        if current_data[stock].last_price >= current_data[stock].high_limit*0.97:
            continue
        if context.portfolio.positions[stock].closeable_amount ==0:
            continue
        rt = huanshoulv(context, stock, False)
        avg = huanshoulv(context, stock, True)
        if avg == 0: continue
        r = rt / avg
        action, icon = '', ''
        if avg < 0.003:
            action, icon = '缩量', '❄️'
        elif rt > expand and r > 2:
            action, icon = '放量', '🔥'
        if action:
            position = context.portfolio.positions[stock]
            r = close_position(position)
            log.info(f"{action} {stock} {get_security_info(stock).display_name} 换手率:{rt:.2%}→均:{avg:.2%} 倍率:{r:.1f}x close_position: {r}")
            g.reason_to_sell = 'limitup'

def order_target_value_(security, value):
    return order_target_value(security, value)

def open_position(security, value):
    order = order_target_value_(security, value)
    if order != None and order.filled > 0:
        return True
    return False

def close_position(position):
    security = position.security
    order = order_target_value_(security, 0)
    if order != None:
        if order.status == OrderStatus.held and order.filled == order.amount:
            return True
    return False

def buy_security(context,target_list,cash=0,buy_number=0):
    position_count = len(context.portfolio.positions)
    target_num = g.stock_num
    if cash == 0:
        cash = context.portfolio.total_value
    if buy_number == 0:
        buy_number = target_num
    bought_num = 0
    print('---------------------buy_number：%s'%buy_number)
    if target_num > position_count:
        value = cash / (target_num)
        for stock in target_list:
            if context.portfolio.positions[stock].total_amount == 0:
                if bought_num < buy_number:
                    if open_position(stock, value):
                        g.not_buy_again.append(stock)
                        bought_num += 1
                        if len(context.portfolio.positions) == target_num:
                            break

def today_is_between(context):
    today = context.current_dt.strftime('%m-%d')
    if g.pass_april is True:
        if (('04-01' <= today) and (today <= '04-30')) or (('01-01' <= today) and (today <= '01-30')):
            return True
        else:
           return False
    else:
        return False

def close_account(context):
    if g.no_trading_today_signal == True:
        if len(g.hold_list) != 0 and g.no_trading_hold_signal == False:
            for stock in g.hold_list:
                position = context.portfolio.positions[stock]
                if close_position(position):
                    log.info("卖出[%s]" % (stock))
                else:
                    log.info("卖出[%s]错误！！！！！" % (stock))
            buy_security(context, g.no_trading_buy)
            g.no_trading_hold_signal = True

def close_no_trading_hold(context):
    if g.no_trading_hold_signal == True:
        for stock in g.hold_list:
            position = context.portfolio.positions[stock]
            close_position(position)
            log.info("卖出[%s]" % (stock))
        g.no_trading_hold_signal = False

