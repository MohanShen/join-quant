# 导入函数库
from jqdata import *
from jqfactor import *
import numpy as np
import pandas as pd
import datetime

# 初始化函数
def initialize(context):
    g.signal = ''
    # 开启防未来函数
    set_option('avoid_future_data', True)
    # 设定基准
    set_benchmark('399101.XSHE')
    # 用真实价格交易
    set_option('use_real_price', True)
    # 将滑点设置为0
    set_slippage(FixedSlippage(3/10000))
    # 设置交易成本
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=2.5/10000, 
                            close_commission=2.5/10000, close_today_commission=0, min_commission=5), type='stock')
    # 过滤日志
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'debug')

    # 初始化全局变量 bool
    g.no_trading_today_signal = False  # 是否为可交易日
    g.pass_april = True  # 是否1月和四月空仓
    g.run_stoploss = True  # 是否进行止损
    g.defense_signal = False  # 防御信号
    g.industries = ["银行I"]  # 高位防御板块
    g.cnt_defense_signal = []  # 择时次数

    # 全局变量list
    g.hold_list = []  # 当前持仓的全部股票
    g.yesterday_HL_list = []  # 记录持仓中昨日涨停的股票
    g.target_list = []
    g.not_buy_again = []

    # 全局变量 - 修改：默认持仓改为4只
    g.stock_num = 4
    g.up_price = 100  # 设置股票单价
    g.reason_to_sell = ''
    g.stoploss_strategy = 3  # 1为止损线止损，2为市场趋势止损, 3为联合1、2策略
    g.stoploss_limit = 0.91  # 止损线
    g.stoploss_market = 0.95  # 市场趋势止损参数

    g.HV_control = True  # 日频判断是否放量
    g.HV_duration = 120  # HV控制周期
    g.HV_ratio = 0.9  # HV控制比例
    g.stockL = []
    # 修改：空仓期间改为持有现金，清空防御性股票列表
    g.no_trading_buy = []
    g.no_trading_hold_signal = False

    # 设置交易运行时间
    run_daily(prepare_stock_list, '9:05')
    run_weekly(weekly_adjustment, 2, '10:30')
    run_daily(sell_stocks, time='10:00')  # 止损函数
    run_daily(trade_afternoon, time='14:25')  # 检查涨停股
    run_daily(trade_afternoon, time='14:55')  # 检查涨停股
    run_daily(close_account, '14:50')
    run_weekly(print_position_info, 5, time='15:10')
    run_daily(check_defense_trigger, '09:30')  # 新增：防御信号检查

# 1-1 准备股票池
def prepare_stock_list(context):
    # 获取已持有列表
    g.hold_list = []
    for position in list(context.portfolio.positions.values()):
        stock = position.security
        g.hold_list.append(stock)

    # 获取昨日涨停列表
    if g.hold_list != []:
        df = get_price(g.hold_list, end_date=context.previous_date, frequency='daily', 
                     fields=['close', 'high_limit', 'low_limit'], count=1, panel=False, fill_paused=False)
        df = df[df['close'] == df['high_limit']]
        g.yesterday_HL_list = list(df.code)
    else:
        g.yesterday_HL_list = []

    # 判断今天是否为账户资金再平衡的日期或防御日
    g.no_trading_today_signal = today_is_between(context) or g.defense_signal


# 1-2 选股模块
def get_stock_list(context):
    final_list = []
    MKT_index = '399101.XSHE'
    initial_list = get_index_stocks(MKT_index)
    initial_list = filter_new_stock(context, initial_list)
    initial_list = filter_kcbj_stock(initial_list)
    initial_list = filter_st_stock(initial_list)
    initial_list = filter_paused_stock(initial_list)
    q = query(valuation.code).filter(valuation.code.in_(initial_list)).order_by(
        valuation.circulating_market_cap.asc()).limit(200)
    initial_list = list(get_fundamentals(q).code)

    initial_list = filter_limitup_stock(context, initial_list)
    initial_list = filter_limitdown_stock(context, initial_list)
    q = query(valuation.code, indicator.eps).filter(valuation.code.in_(initial_list)).order_by(
        valuation.market_cap.asc())
    df = get_fundamentals(q)
    stock_list = list(df.code)
    stock_list = stock_list[:100]
    stock_list = get_stock_industry(stock_list)
    # 配合持仓数量修改，目标列表长度调整为持仓数的2倍
    final_list = stock_list[:g.stock_num * 2]
    log.info('今日前10:%s' % final_list)
    return final_list


# 1-3 整体调整持仓
def weekly_adjustment(context):
    # 打印当前日期和信号状态，用于调试
    log.info(f"日期: {context.current_dt.date()}, g.pass_april={g.pass_april}, "
             f"g.no_trading_today_signal={g.no_trading_today_signal}, g.defense_signal={g.defense_signal}")
    
    # 空仓月份或防御信号触发时执行防御性策略
    if g.no_trading_today_signal:
        # 清仓现有股票
        close_no_trading_hold(context)
        
        # 买入防御性资产或空仓
        if g.defense_signal:
            log.info("高位防御信号触发，空仓")
            g.no_trading_hold_signal = True
        else:
            # 修改：空仓月份改为持有现金
            log.info("空仓月份，持有现金")
            g.no_trading_hold_signal = True
        return
        
    # 非空仓月份且无防御信号的正常调仓逻辑
    close_no_trading_hold(context)
    
    # 获取应买入列表
    g.not_buy_again = []
    g.target_list = get_stock_list(context)
    target_list = g.target_list[:g.stock_num * 2]
    log.info(str(target_list))

    # 记录当次调仓卖出的股票
    sold_stocks = []
    # 调仓卖出
    for stock in g.hold_list:
        if (stock not in target_list) and (stock not in g.yesterday_HL_list):
            log.info("卖出[%s]" % (stock))
            position = context.portfolio.positions[stock]
            close_position(position)
            sold_stocks.append(stock)  # 记录卖出的股票
    
    # 调整后的买入列表：剔除刚卖出的股票和已持有的股票
    adjusted_target_list = [
        stock for stock in target_list
        if stock not in sold_stocks and stock not in context.portfolio.positions.keys()
    ]

    buy_security(context, adjusted_target_list)  # 传入过滤后的列表

    # 记录已买入股票
    for position in list(context.portfolio.positions.values()):
        stock = position.security
        g.not_buy_again.append(stock)


# 1-4 调整昨日涨停股票
def check_limit_up(context):
    now_time = context.current_dt
    if g.yesterday_HL_list != []:
        # 对昨日涨停股票观察到尾盘如不涨停则提前卖出，如果涨停即使不在应买入列表仍暂时持有
        for stock in g.yesterday_HL_list:
            if context.portfolio.positions[stock].closeable_amount > -100:
                current_data = get_price(stock, end_date=now_time, frequency='1m', 
                                        fields=['close', 'high_limit'], skip_paused=False, 
                                        fq='pre', count=1, panel=False, fill_paused=True)
                if current_data.iloc[0, 0] < current_data.iloc[0, 1]:
                    log.info("[%s]涨停打开，卖出" % (stock))
                    position = context.portfolio.positions[stock]
                    close_position(position)
                    g.reason_to_sell = 'limitup'
                else:
                    log.info("[%s]涨停，继续持有" % (stock))


# 1-5 处理剩余资金
def check_remain_amount(context):
    if g.reason_to_sell == 'limitup':  # 涨停售出则次日再次交易
        g.hold_list = []
        for position in list(context.portfolio.positions.values()):
            stock = position.security
            g.hold_list.append(stock)
        # 根据修改后的持仓数量判断
        if len(g.hold_list) < g.stock_num:
            target_list = get_stock_list(context)
            # 剔除本周一曾买入的股票
            target_list = filter_not_buy_again(target_list)
            target_list = target_list[:min(g.stock_num, len(target_list))]
            log.info('有余额可用' + str(round((context.portfolio.cash), 2)) + '元。' + str(target_list))
            buy_security(context, target_list)
            g.reason_to_sell = ''
    else:
        log.info('虽然有余额（' + str(round((context.portfolio.cash), 2)) + '元）可用，但是为止损后余额，下周再交易')
        g.reason_to_sell = ''


# 1-6 下午检查交易
def trade_afternoon(context):
    if not g.no_trading_today_signal:
        check_limit_up(context)
        if g.HV_control:
            check_high_volume(context)
        huanshou(context)
        check_remain_amount(context)


# 1-7 止盈止损
def sell_stocks(context):
    if g.run_stoploss:
        if g.stoploss_strategy == 1:
            for stock in context.portfolio.positions.keys():
                # 股票盈利大于等于100%则卖出
                if context.portfolio.positions[stock].price >= context.portfolio.positions[stock].avg_cost * 2:
                    order_target_value(stock, 0)
                    log.debug("收益100%止盈,卖出{}".format(stock))
                # 止损
                elif context.portfolio.positions[stock].price < context.portfolio.positions[stock].avg_cost * g.stoploss_limit:
                    order_target_value(stock, 0)
                    log.debug("收益止损,卖出{}".format(stock))
                    g.reason_to_sell = 'stoploss'
        elif g.stoploss_strategy == 2:
            stock_df = get_price(security=get_index_stocks('399101.XSHE'), end_date=context.previous_date, 
                                frequency='daily', fields=['close', 'open'], count=1, panel=False)
            down_ratio = (stock_df['close'] / stock_df['open']).mean()
            if down_ratio < g.stoploss_market:
                g.reason_to_sell = 'stoploss'
                log.debug("大盘惨跌,平均降幅{:.2%}".format(1 - down_ratio))
                for stock in context.portfolio.positions.keys():
                    order_target_value(stock, 0)
        elif g.stoploss_strategy == 3:
            stock_df = get_price(security=get_index_stocks('399101.XSHE'), end_date=context.previous_date, 
                                frequency='daily', fields=['close', 'open'], count=1, panel=False)
            down_ratio = (stock_df['close'] / stock_df['open']).mean()
            if down_ratio < g.stoploss_market:
                g.reason_to_sell = 'stoploss'
                log.debug("大盘惨跌,平均降幅{:.2%}".format(1 - down_ratio))
                for stock in context.portfolio.positions.keys():
                    order_target_value(stock, 0)
            else:
                for stock in context.portfolio.positions.keys():
                    if context.portfolio.positions[stock].price < context.portfolio.positions[stock].avg_cost * g.stoploss_limit:
                        order_target_value(stock, 0)
                        log.debug("收益止损,卖出{}".format(stock))
                        g.reason_to_sell = 'stoploss'


# 3-2 调整放量股票
def check_high_volume(context):
    current_data = get_current_data()
    for stock in context.portfolio.positions:
        if current_data[stock].paused:
            continue
        if current_data[stock].last_price == current_data[stock].high_limit:
            continue
        if context.portfolio.positions[stock].closeable_amount == 0:
            continue
        df_volume = get_bars(stock, count=g.HV_duration, unit='1d', fields=['volume'], include_now=True, df=True)
        if not df_volume.empty and df_volume['volume'].values[-1] > g.HV_ratio * df_volume['volume'].values.max():
            log.info("[%s]天量，卖出" % stock)
            position = context.portfolio.positions[stock]
            close_position(position)


# 2-1 过滤停牌股票
def filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]


# 2-2 过滤ST及其他具有退市标签的股票
def filter_st_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list
            if not current_data[stock].is_st
            and 'ST' not in current_data[stock].name
            and '*' not in current_data[stock].name
            and '退' not in current_data[stock].name]


# 2-3 过滤科创北交股票
def filter_kcbj_stock(stock_list):
    for stock in stock_list[:]:
        if stock[0] == '4' or stock[0] == '8' or stock[:2] == '68' or stock[:2] == '30':
            stock_list.remove(stock)
    return stock_list


# 2-4 过滤涨停的股票
def filter_limitup_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] < current_data[stock].high_limit]


# 2-5 过滤跌停的股票
def filter_limitdown_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list if (stock in context.portfolio.positions.keys()
                                              or last_prices[stock][-1] > current_data[stock].low_limit)]


# 2-6 过滤次新股
def filter_new_stock(context, stock_list):
    yesterday = context.previous_date
    return [stock for stock in stock_list if not yesterday - get_security_info(stock).start_date < datetime.timedelta(days=375)]


# 2-6.5 过滤股价
def filter_highprice_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] <= g.up_price]


# 2-7 删除本周一买入的股票
def filter_not_buy_again(stock_list):
    return [stock for stock in stock_list if stock not in g.not_buy_again]


# 获取股票所属行业
def get_stock_industry(stock_list):
    result = get_industry(security=stock_list)
    selected_stocks = []
    industry_list = []

    for stock_code, info in result.items():
        # 优先使用申万二级行业
        industry_name = None
        if 'sw_l2' in info:
            industry_name = info['sw_l2']['industry_name']
        # 没有申万二级行业则使用申万一级行业
        elif 'sw_l1' in info:
            industry_name = info['sw_l1']['industry_name']
        if industry_name is None:
            continue
            
        if industry_name not in industry_list:
            industry_list.append(industry_name)
            selected_stocks.append(stock_code)
            # 控制选取数量
            if len(selected_stocks) >= 10:
                break
    
    return selected_stocks


# 换手率计算
def huanshoulv(context, stock, is_avg=False):
    if is_avg:
        # 计算平均换手率
        start_date = context.current_dt - datetime.timedelta(days=20)
        end_date = context.previous_date
        df_volume = get_price(stock, end_date=end_date, frequency='daily', fields=['volume'], count=20)
        df_cap = get_valuation(stock, end_date=end_date, fields=['circulating_cap'], count=1)
        circulating_cap = df_cap['circulating_cap'].iloc[0] if not df_cap.empty else 0
        if circulating_cap == 0:
            return 0.0
        df_volume['turnover_ratio'] = df_volume['volume'] / (circulating_cap * 10000)
        return df_volume['turnover_ratio'].mean()
    else:
        # 计算实时换手率
        date_now = context.current_dt
        df_vol = get_price(stock, start_date=date_now.date(), end_date=date_now, frequency='1m', 
                          fields=['volume'], skip_paused=False, fq='pre', panel=True, fill_paused=False)
        volume = df_vol['volume'].sum()
        date_pre = context.previous_date
        df_circulating_cap = get_valuation(stock, end_date=date_pre, fields=['circulating_cap'], count=1)
        circulating_cap = df_circulating_cap['circulating_cap'].iloc[0] if not df_circulating_cap.empty else 0
        if circulating_cap == 0:
            return 0.0
        turnover_ratio = volume / (circulating_cap * 10000)
        return turnover_ratio


# 换手检测
def huanshou(context):
    shrink, expand = 0.003, 0.1
    current_data = get_current_data()
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
        action, icon = '', ''
        if avg < 0.003:
            action, icon = '缩量', '❄️'
        elif rt > expand and r > 2:
            action, icon = '放量', '?'
        if action:
            log.info(f"{action} {stock} {get_security_info(stock).display_name} "
                     f"换手率:{rt:.2%}→均:{avg:.2%} 倍率:{r:.1f}x {icon}")
            position = context.portfolio.positions[stock]
            close_position(position)
            g.reason_to_sell = 'limitup'


# 3-1 交易模块-自定义下单
def ordertarget_value(security, value):
    if value == 0:
        log.debug("Selling out %s" % (security))
    else:
        log.debug("Order %s to value %f" % (security, value))
    return order_target_value(security, value)


# 3-2 交易模块-开仓
def open_position(security, value):
    order = ordertarget_value(security, value)
    if order is not None and order.filled > 0:
        return True
    return False


# 3-3 交易模块-平仓
def close_position(position):
    security = position.security
    order = ordertarget_value(security, 0)  # 可能会因停牌失败
    if order is not None:
        if order.status == 'filled' and order.filled == order.amount:
            return True
    return False


# 3-4 买入模块
def buy_security(context, target_list, cash=0, buy_number=0):
    # 调仓买入
    position_count = len(context.portfolio.positions)
    target_num = g.stock_num  # 使用修改后的持仓数量
    if cash == 0:
        cash = context.portfolio.total_value  # cash
    if buy_number == 0:
        buy_number = target_num
    bought_num = 0
    
    # 计算还可以买入的股票数量
    available_slots = target_num - position_count
    if available_slots <= 0:
        return  # 持仓已满，不执行买入
    
    value = cash / target_num  # 每只股票的买入金额
    remaining_slots = available_slots
    
    for stock in target_list:
        # 跳过已持有的股票
        if context.portfolio.positions.get(stock, None) is not None and context.portfolio.positions[stock].total_amount > 0:
            continue
            
        # 检查是否还有可用仓位
        if remaining_slots <= 0:
            break
            
        if bought_num < buy_number:
            if open_position(stock, value):
                log.info("买入[%s]（%s元）" % (stock, value))
                g.not_buy_again.append(stock)  # 记录已买入的股票
                bought_num += 1
                remaining_slots -= 1  # 减少可用仓位


# 4-1 判断今天是否为1月、4月或防御日
def today_is_between(context):
    today = context.current_dt.strftime('%m-%d')
    if g.pass_april:
        # 1月和4月为空仓月份
        if (('04-01' <= today) and (today <= '04-30')) or (('01-01' <= today) and (today <= '01-31')):
            return True
    return False


# 4-2 清仓后次日资金可转
def close_account(context):
    if g.no_trading_today_signal:
        if len(g.hold_list) != 0 and g.no_trading_hold_signal == False:
            for stock in g.hold_list:
                position = context.portfolio.positions[stock]
                if close_position(position):
                    log.info("卖出[%s]" % (stock))
                else:
                    log.info("卖出[%s]错误！！！！！" % (stock))
            # 修改：空仓期间不买入任何股票，保持现金
            g.no_trading_hold_signal = True


# 4-3 清仓防御期间股票
def close_no_trading_hold(context):
    if g.no_trading_hold_signal:
        for stock in g.hold_list:
            position = context.portfolio.positions[stock]
            close_position(position)
            log.info("卖出[%s]" % (stock))
        g.no_trading_hold_signal = False


# 1-8 动态调仓代码
def adjust_stock_num(context):
    ma_para = 10  # 设置MA参数
    today = context.previous_date
    start_date = today - datetime.timedelta(days=ma_para * 2)
    index_df = get_price('399101.XSHE', start_date=start_date, end_date=today, frequency='daily')
    index_df['ma'] = index_df['close'].rolling(window=ma_para).mean()
    last_row = index_df.iloc[-1]
    diff = last_row['close'] - last_row['ma']

    # 根据差值结果返回数字（已根据新的默认持仓数调整）
    result = 3 if diff >= 500 else \
        3 if 200 <= diff < 500 else \
        4 if -200 <= diff < 200 else \
        5 if -500 <= diff < -200 else \
        6
    return result


# 打印持仓信息
def print_position_info(context):
    print('———————————————————————————————————')
    for position in list(context.portfolio.positions.values()):
        securities = position.security
        cost = position.avg_cost
        price = position.price
        ret = 100 * (price / cost - 1)
        value = position.value
        amount = position.total_amount
        print('代码:{}'.format(securities))
        print('收益率:{}%'.format(format(ret, '.2f')))
        print('持仓(股):{}'.format(amount))
        print('市值:{}'.format(format(value, '.2f')))
        print('———————————————————————————————————')
    print('余额:{}'.format(format(context.portfolio.cash, '.2f')))
    print('———————————————————————————————————————分割线————————————————————————————————————————')    


# === 以下是从策略一整合的高位防御功能 ===

# 计算市场宽度
def get_market_breadth(context, ma_days):
    required_days = ma_days + 35
    end_date = context.current_dt      
    trade_days = get_trade_days(end_date=end_date, count=required_days)
    # 获取行业分类数据
    sw_l1 = get_industries('sw_l1', date=end_date)
    industry_stocks = {}
    for idx, row in sw_l1.iterrows():
        ind_stocks = get_industry_stocks(idx, date=end_date)
        industry_stocks[row['name']] = ind_stocks  # 存储行业对应的股票列表
    # 获取所有股票
    all_stocks = []
    for stocks in industry_stocks.values():
        all_stocks.extend(stocks)
    all_stocks = list(set(all_stocks))  # 去重
    # 获取价格数据
    data = get_bars(all_stocks, end_dt=end_date, count=required_days, unit='1d', 
                   fields=['close'], include_now=True, df=True)
    price_data = data.reset_index()
    price_data = price_data.pivot(index='level_1', columns='level_0', values='close')  # 转换为时间序列格式
    ma = price_data.rolling(window=ma_days).mean()  # 计算移动平均
    above_ma = price_data > ma  # 标记股价是否在均线上方
    # 按行业计算均线分数
    industry_scores = pd.DataFrame(index=price_data.index)  # 初始化行业得分表
    
    for industry, stocks in industry_stocks.items():
        # 获取行业内有效股票
        valid_stocks = list(set(above_ma.columns) & set(stocks))
        if valid_stocks:
            # 计算行业得分（符合条件的股票比例）
            industry_scores[industry] = 100 * above_ma[valid_stocks].sum(axis=1) / len(valid_stocks)
    transposed_data = industry_scores[-3:].mean()  # 近3天
    sorted_data = transposed_data.sort_values(ascending=False)
    return sorted_data

# 计算趋势指标:接近近期高点
def calculate_trend_indicators(context, index_symbol='399101.XSHE'):
    """计算趋势指标:接近近期高点"""
    high_lookback = 60   # 近期高点观察窗口
    high_proximity = 0.95       # 接近高点的阈值（95%）
    # 获取历史数据
    data = get_bars(index_symbol, end_dt=context.current_dt, 
                  count=high_lookback, unit='1d', fields=['close','high'], 
                  include_now=True, df=True)
    current_price = data['close'].iloc[-1]
    # 计算近期高点接近度
    max_high = data['high'][-high_lookback:].max()
    is_high = True if current_price >= (max_high * high_proximity) else False 
    return is_high  

# 防御信号检查
def check_defense_trigger(context):
    """防御条件检查"""
    if g.defense_signal:  # 如果已经进入防御板块，检查是否保持
        # 行业强度判断
        sorted_data = get_market_breadth(context, 20)
        defense_in_top = any([ind in sorted_data.index[:3] for ind in g.industries])  # 防御板块在前3
        g.defense_signal = defense_in_top
        log.info(f"防御保持: {g.defense_signal} top宽度:{sorted_data.index[:3].tolist()} "
                 f"防御次数: {sum(g.cnt_defense_signal)}")
    else:
        # 趋势高位判断条件
        is_high = calculate_trend_indicators(context)
        if is_high:
            # 行业强度判断
            sorted_data = get_market_breadth(context, 20)
            defense_in_top = any([ind in sorted_data.index[:3] for ind in g.industries])  # 防御板块在前3
            # 相对强度判断
            avg_score = sorted_data[[ind not in g.industries for ind in sorted_data.index]].mean()
            defense_score = sorted_data[[ind in g.industries for ind in sorted_data.index]].max()
            relative_strength = (defense_score - avg_score) / avg_score
            above_average = relative_strength > 0.1  # 相对强度超过10%
            # 综合判断
            is_defense = is_high and defense_in_top and above_average
            g.defense_signal = is_defense
            if is_defense:
                g.cnt_defense_signal.append(is_defense)
            log.info(f"触发防御: {g.defense_signal} 高位:{is_high} top宽度:{sorted_data.index[:3].tolist()} "
                     f"相对强度:{above_average}")
        else:
            g.defense_signal = False
            log.info(f"触发防御: {g.defense_signal} 高位:{is_high}")