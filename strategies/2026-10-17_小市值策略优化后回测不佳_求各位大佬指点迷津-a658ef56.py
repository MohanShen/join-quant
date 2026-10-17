# Clone from JoinQuant
# postId: a658ef560be8bdf7f3012ce60c721f35
# backtestId: af18c2e416f4f1d70728eab5da94826e
# title: 小市值策略优化后回测不佳，求各位大佬指点迷津

# 克隆自聚宽文章：https://www.joinquant.com/post/57064
# 标题：大小盘风格切换：菜场大妈收益进一步提高
# 作者：ETF量化老司机
# ===== 修复与优化版本 =====
# 优化点：
# 1. 选股池改为全A股（剔除ST、停牌、次新、科创北交、涨跌停、高价股）
# 2. 引入PE、ROE过滤，提升质量
# 3. 修复行业分散函数，确保10个不同行业
# 4. 止损线放宽至0.88，大盘止损改用指数本身涨跌幅
# 5. 四月空仓改为半仓（保留50%仓位）
# 6. 修复涨跌停过滤使用前日收盘价
# 7. 增加持仓数量至10只
# 8. 修复平仓函数状态判断
# 9. 换手放量检测调整阈值
# 10. 集成动态调仓函数 adjust_stock_num

from jqdata import *
from jqfactor import *
import numpy as np
import pandas as pd
import datetime

# 初始化函数
def initialize(context):
    g.signal = ''
    set_option('avoid_future_data', True)
    set_benchmark('399101.XSHE')
    set_option('use_real_price', True)
    set_slippage(FixedSlippage(3/10000))
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=2.5/10000, close_commission=2.5/10000, close_today_commission=0, min_commission=5), type='stock')
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'debug')

    # 全局变量
    g.no_trading_today_signal = False
    g.pass_april = True          # 四月半仓（原为空仓）
    g.run_stoploss = True
    g.hold_list = []
    g.yesterday_HL_list = []
    g.target_list = []
    g.not_buy_again = []

    g.stock_num = 10             # 从6只增加到10只
    g.up_price = 100
    g.reason_to_sell = ''
    g.stoploss_strategy = 3
    g.stoploss_limit = 0.88      # 放宽止损线
    g.stoploss_market = 0.95

    g.HV_control = False
    g.HV_duration = 120
    g.HV_ratio = 0.9
    g.stockL = []
    g.no_trading_buy = ['600036.XSHG', '518880.XSHG', '600900.XSHG']
    g.no_trading_hold_signal = False

    # 定时运行
    run_daily(prepare_stock_list, '9:05')
    run_weekly(weekly_adjustment, 2, '10:30')   # 每周二调仓
    run_daily(sell_stocks, time='10:00')
    run_daily(trade_afternoon, time='14:25')
    run_daily(trade_afternoon, time='14:55')
    run_daily(close_account, '14:50')
    run_weekly(print_position_info, 5, time='15:10')


# 1-1 准备股票池
def prepare_stock_list(context):
    g.hold_list = [position.security for position in list(context.portfolio.positions.values())]

    # 获取昨日涨停列表（持有股中收盘价=涨停价）
    if g.hold_list:
        df = get_price(g.hold_list, end_date=context.previous_date, frequency='daily',
                       fields=['close', 'high_limit'], count=1, panel=False, fill_paused=False)
        df = df[df['close'] == df['high_limit']]
        g.yesterday_HL_list = list(df.code)
    else:
        g.yesterday_HL_list = []

    g.no_trading_today_signal = today_is_between(context)


# 1-2 选股模块（优化版）
def get_stock_list(context):
    # 改为全A股作为初始池
    initial_list = get_all_securities(['stock']).index.tolist()
    initial_list = filter_new_stock(context, initial_list)      # 剔除上市不足375天
    initial_list = filter_kcbj_stock(initial_list)              # 剔除科创、北交、4/8开头
    initial_list = filter_st_stock(initial_list)                # 剔除ST、退市
    initial_list = filter_paused_stock(initial_list)            # 剔除停牌

    # 过滤涨跌停（使用前一日数据）
    initial_list = filter_limitup_stock(context, initial_list)
    initial_list = filter_limitdown_stock(context, initial_list)

    # 过滤高价股
    initial_list = filter_highprice_stock(context, initial_list)

    if not initial_list:
        return []

    # 查询基本面数据：市值、PE、ROE
    q = query(valuation.code, valuation.circulating_market_cap, valuation.pe_ratio, indicator.roe)\
          .filter(valuation.code.in_(initial_list))
    df = get_fundamentals(q)
    # 过滤 PE 异常（<=0 或 >80）和 ROE <=0
    df = df[(df['pe_ratio'] > 0) & (df['pe_ratio'] < 80) & (df['roe'] > 0)]
    df = df.sort_values('circulating_market_cap')  # 按流通市值升序
    stock_list = list(df.code)[:200]                # 取前200只

    # 行业分散：从前200只中选取10个不同行业的股票
    selected = get_stock_industry(stock_list, max_num=g.stock_num*2)  # 取2倍数量供后续筛选
    final_list = selected[:g.stock_num*2] if selected else stock_list[:g.stock_num*2]
    log.info('今日候选池（前20）：%s' % final_list[:20])
    return final_list


# 1-3 整体调整持仓
def weekly_adjustment(context):
    # 动态调整持股数量
    g.stock_num = adjust_stock_num(context)

    if g.no_trading_today_signal == False:
        close_no_trading_hold(context)

        g.not_buy_again = []
        target_list = get_stock_list(context)
        target_list = target_list[:g.stock_num * 2] if target_list else []
        log.info('目标持仓列表：%s' % target_list)

        # 卖出不在目标池且非昨日涨停的股票
        for stock in g.hold_list:
            if (stock not in target_list) and (stock not in g.yesterday_HL_list):
                log.info("卖出[%s]" % stock)
                close_position(context.portfolio.positions[stock])

        # 买入
        buy_security(context, target_list)

        # 记录已买入
        for pos in list(context.portfolio.positions.values()):
            g.not_buy_again.append(pos.security)


# 1-4 检查昨日涨停股（尾盘打开则卖出）
def check_limit_up(context):
    now_time = context.current_dt
    if g.yesterday_HL_list:
        for stock in g.yesterday_HL_list:
            pos = context.portfolio.positions.get(stock)
            if pos is None or pos.closeable_amount <= 0:
                continue
            current_data = get_price(stock, end_date=now_time, frequency='1m',
                                     fields=['close', 'high_limit'], skip_paused=False,
                                     fq='pre', count=1, panel=False, fill_paused=True)
            if current_data.iloc[0, 0] < current_data.iloc[0, 1]:
                log.info("[%s]涨停打开，卖出" % stock)
                close_position(pos)
                g.reason_to_sell = 'limitup'
            else:
                log.info("[%s]涨停，继续持有" % stock)


# 1-5 补仓（涨停卖出后的剩余资金）
def check_remain_amount(context):
    if g.reason_to_sell == 'limitup':
        g.hold_list = [pos.security for pos in list(context.portfolio.positions.values())]
        if len(g.hold_list) < g.stock_num:
            target_list = get_stock_list(context)
            target_list = filter_not_buy_again(target_list)
            target_list = target_list[:min(g.stock_num, len(target_list))]
            if target_list:
                log.info('涨停卖出后剩余资金补仓，目标：' + str(target_list))
                buy_security(context, target_list)
            g.reason_to_sell = ''
    else:
        log.info('止损后余额不补仓，下周再交易')


# 1-6 下午检查
def trade_afternoon(context):
    if g.no_trading_today_signal == False:
        check_limit_up(context)
        if g.HV_control:
            check_high_volume(context)
        huanshou(context)          # 换手率放量检测
        check_remain_amount(context)


# 1-7 止盈止损（优化）
def sell_stocks(context):
    if not g.run_stoploss:
        return
    # 大盘止损：使用指数本身涨跌幅
    if g.stoploss_strategy in (2, 3):
        index_df = get_price('399101.XSHE', end_date=context.previous_date,
                             frequency='daily', fields=['close', 'open'], count=1)
        if not index_df.empty:
            down_ratio = index_df['close'].iloc[-1] / index_df['open'].iloc[-1]
            if down_ratio < g.stoploss_market:
                log.debug("大盘惨跌，当日跌幅{:.2%}，清仓".format(1 - down_ratio))
                for stock in list(context.portfolio.positions.keys()):
                    close_position(context.portfolio.positions[stock])
                g.reason_to_sell = 'stoploss'
                return

    # 个股止损（策略1或3且未触发大盘止损）
    if g.stoploss_strategy in (1, 3):
        for stock in list(context.portfolio.positions.keys()):
            pos = context.portfolio.positions[stock]
            if pos.price < pos.avg_cost * g.stoploss_limit:
                close_position(pos)
                log.debug("个股止损，卖出{}".format(stock))
                g.reason_to_sell = 'stoploss'
            elif pos.price >= pos.avg_cost * 2:   # 止盈100%
                close_position(pos)
                log.debug("止盈100%%，卖出{}".format(stock))


# 2-1 过滤停牌
def filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]

# 2-2 过滤ST
def filter_st_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list
            if not current_data[stock].is_st
            and 'ST' not in current_data[stock].name
            and '*' not in current_data[stock].name
            and '退' not in current_data[stock].name]

# 2-3 过滤科创北交
def filter_kcbj_stock(stock_list):
    return [stock for stock in stock_list
            if not (stock[0] in ('4','8') or stock[:2] in ('68','30'))]

# 2-4 过滤涨停（使用前一日数据）
def filter_limitup_stock(context, stock_list):
    if not stock_list:
        return []
    df = get_price(stock_list, end_date=context.previous_date,
                   frequency='daily', fields=['close', 'high_limit'], count=1, panel=False)
    # 持有股票允许涨停，其他股票要求前日收盘价小于前日涨停价
    result = []
    for stock in stock_list:
        row = df[df['code'] == stock]
        if row.empty:
            continue
        if stock in context.portfolio.positions.keys() or row.iloc[0]['close'] < row.iloc[0]['high_limit']:
            result.append(stock)
    return result

# 2-5 过滤跌停
def filter_limitdown_stock(context, stock_list):
    if not stock_list:
        return []
    df = get_price(stock_list, end_date=context.previous_date,
                   frequency='daily', fields=['close', 'low_limit'], count=1, panel=False)
    result = []
    for stock in stock_list:
        row = df[df['code'] == stock]
        if row.empty:
            continue
        if stock in context.portfolio.positions.keys() or row.iloc[0]['close'] > row.iloc[0]['low_limit']:
            result.append(stock)
    return result

# 2-6 过滤次新（上市不足375天）
def filter_new_stock(context, stock_list):
    yesterday = context.previous_date
    return [stock for stock in stock_list
            if not (yesterday - get_security_info(stock).start_date < datetime.timedelta(days=375))]

# 2-6.5 过滤高价股
def filter_highprice_stock(context, stock_list):
    if not stock_list:
        return []
    df = get_price(stock_list, end_date=context.previous_date,
                   frequency='daily', fields=['close'], count=1, panel=False)
    result = []
    for stock in stock_list:
        row = df[df['code'] == stock]
        if row.empty:
            continue
        if stock in context.portfolio.positions.keys() or row.iloc[0]['close'] <= g.up_price:
            result.append(stock)
    return result

# 2-7 过滤本周已买入
def filter_not_buy_again(stock_list):
    return [stock for stock in stock_list if stock not in g.not_buy_again]

# 2-8 行业分散（修复版）
def get_stock_industry(stock_list, max_num=20):
    """
    从stock_list中按顺序选取最多max_num只股票，保证行业（申万二级）不重复。
    """
    if not stock_list:
        return []
    industry_dict = get_industry(stock_list)
    selected = []
    seen = set()
    for stock in stock_list:
        info = industry_dict.get(stock, {})
        industry = info.get('sw_l2', {}).get('industry_name', '')
        if industry and industry not in seen:
            seen.add(industry)
            selected.append(stock)
        elif not industry and stock not in selected:
            # 如果无法获取行业，也加入（但尽量少）
            selected.append(stock)
        if len(selected) >= max_num:
            break
    return selected


# 换手率计算（优化）
def huanshoulv(context, stock, is_avg=False):
    if is_avg:
        # 20日平均换手
        df_volume = get_price(stock, end_date=context.previous_date,
                              frequency='daily', fields=['volume'], count=20, panel=False)
        if df_volume.empty:
            return 0.0
        df_cap = get_valuation(stock, end_date=context.previous_date, fields=['circulating_cap'], count=1)
        if df_cap.empty or df_cap.iloc[0]['circulating_cap'] == 0:
            return 0.0
        circulating_cap = df_cap.iloc[0]['circulating_cap']
        avg_vol = df_volume['volume'].mean()
        return avg_vol / (circulating_cap * 10000)
    else:
        # 实时换手（当日累计成交量 / 前日流通市值）
        now = context.current_dt
        df_vol = get_price(stock, start_date=now.date(), end_date=now,
                           frequency='1m', fields=['volume'], skip_paused=False, fq='pre', panel=False)
        if df_vol.empty:
            return 0.0
        total_vol = df_vol['volume'].sum()
        df_cap = get_valuation(stock, end_date=context.previous_date, fields=['circulating_cap'], count=1)
        if df_cap.empty or df_cap.iloc[0]['circulating_cap'] == 0:
            return 0.0
        circulating_cap = df_cap.iloc[0]['circulating_cap']
        return total_vol / (circulating_cap * 10000)

# 换手率放量检测（调整阈值）
def huanshou(context):
    threshold_expand = 0.10    # 当日换手>10%
    threshold_ratio = 3.0      # 当日/平均 > 3倍
    current_data = get_current_data()
    for stock in list(context.portfolio.positions.keys()):
        pos = context.portfolio.positions[stock]
        if current_data[stock].paused or pos.closeable_amount == 0:
            continue
        if current_data[stock].last_price >= current_data[stock].high_limit * 0.97:
            continue  # 接近涨停不卖
        rt = huanshoulv(context, stock, False)
        avg = huanshoulv(context, stock, True)
        if avg == 0 or avg < 0.003:
            continue
        if rt > threshold_expand and rt / avg > threshold_ratio:
            log.info("放量卖出 %s 换手率:%.2f%% 均:%.2f%% 倍率:%.1f" %
                     (stock, rt*100, avg*100, rt/avg))
            close_position(pos)
            g.reason_to_sell = 'limitup'


# 交易模块
def close_position(position):
    """平仓，简化判断"""
    if position is None:
        return False
    order = order_target_value(position.security, 0)
    return order is not None

def open_position(security, value):
    order = order_target_value(security, value)
    return order is not None and order.filled > 0

def buy_security(context, target_list, cash=0, buy_number=0):
    if not target_list:
        return
    cash = cash or context.portfolio.total_value
    buy_number = buy_number or g.stock_num
    position_count = len(context.portfolio.positions)
    if position_count >= g.stock_num:
        return
    value = cash / g.stock_num   # 平均分配
    bought = 0
    for stock in target_list:
        if context.portfolio.positions[stock].total_amount == 0:
            if open_position(stock, value):
                log.info("买入[%s] %s元" % (stock, value))
                g.not_buy_again.append(stock)
                bought += 1
            if len(context.portfolio.positions) >= g.stock_num:
                break


# 四月半仓判断
def today_is_between(context):
    today = context.current_dt.strftime('%m-%d')
    if g.pass_april:
        # 四月份将仓位减半（不是完全空仓），但此处只标记信号，实际在close_account中处理
        if ('04-01' <= today <= '04-30'):
            return True
    return False

# 空仓/半仓处理
def close_account(context):
    if g.no_trading_today_signal:
        # 四月：清仓小市值，买入避险品种（但保留半仓资金？原逻辑是全清，我们改为半仓）
        if len(g.hold_list) != 0 and not g.no_trading_hold_signal:
            for stock in g.hold_list:
                close_position(context.portfolio.positions[stock])
            # 只买入半仓避险品种（金额为总资产的50%）
            half_cash = context.portfolio.total_value * 0.5
            for stock in g.no_trading_buy:
                if half_cash > 0:
                    order_target_value(stock, half_cash / len(g.no_trading_buy))
            g.no_trading_hold_signal = True

def close_no_trading_hold(context):
    if g.no_trading_hold_signal:
        for stock in g.hold_list:
            close_position(context.portfolio.positions[stock])
        # 清空避险持仓
        for stock in g.no_trading_buy:
            close_position(context.portfolio.positions.get(stock))
        g.no_trading_hold_signal = False

# 动态调仓数量
def adjust_stock_num(context):
    ma_para = 10
    today = context.previous_date
    start_date = today - datetime.timedelta(days=ma_para*2)
    index_df = get_price('399101.XSHE', start_date=start_date, end_date=today, frequency='daily')
    if index_df.empty:
        return g.stock_num
    index_df['ma'] = index_df['close'].rolling(window=ma_para).mean()
    last_row = index_df.iloc[-1]
    diff = last_row['close'] - last_row['ma']
    # 根据偏离调整持股数量
    if diff >= 500:
        return 3
    elif 200 <= diff < 500:
        return 4
    elif -200 <= diff < 200:
        return 5
    elif -500 <= diff < -200:
        return 6
    else:
        return 8   # 大跌时增加持股分散风险

# 打印持仓
def print_position_info(context):
    print('———————————————————————————————————')
    for pos in list(context.portfolio.positions.values()):
        print('代码:{} 收益率:{:.2f}% 市值:{:.2f}'.format(
            pos.security, 100*(pos.price/pos.avg_cost-1), pos.value))
    print('余额:{:.2f}'.format(context.portfolio.cash))
    print('———————————————————————————————————————')


# 放量检测（备用）
def check_high_volume(context):
    current_data = get_current_data()
    for stock in list(context.portfolio.positions.keys()):
        pos = context.portfolio.positions[stock]
        if current_data[stock].paused or pos.closeable_amount == 0:
            continue
        if current_data[stock].last_price == current_data[stock].high_limit:
            continue
        df_volume = get_bars(stock, count=g.HV_duration, unit='1d',
                             fields=['volume'], include_now=True, df=True)
        if df_volume.empty:
            continue
        if df_volume['volume'].values[-1] > g.HV_ratio * df_volume['volume'].values.max():
            log.info("[%s]天量，卖出" % stock)
            close_position(pos)