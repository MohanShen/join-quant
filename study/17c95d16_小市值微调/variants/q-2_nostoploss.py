# Clone from JoinQuant
# postId: 17c95d16cc715df781ff7f2004d0f5e2
# backtestId: badb1a31c6bfb32fff1c2b13df25d5d2
# title: 小市值微调：年化109%｜回撤15%｜胜率75%

# 导入函数库
from jqdata import *
from jqfactor import *
import numpy as np
import pandas as pd
from datetime import time
from jqdata import finance
import datetime

# 初始化函数 
def initialize(context):
    # 开启防未来函数
    set_option('avoid_future_data', True)
    # 设定基准
    set_benchmark('399101.XSHE')
    # 用真实价格交易
    set_option('use_real_price', True)
    # 将滑点设置为0
    set_slippage(FixedSlippage(3/10000))
    # 设置交易成本万分之三
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=2.5/10000, close_commission=2.5/10000, close_today_commission=0, min_commission=5), type='stock')
    
    # 日志设置
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'debug')
    
    # 初始化全局变量 bool
    g.trading_signal = True  # 是否为可交易日
    g.run_stoploss = True  # 是否进行止损
    g.filter_audit = False  # 是否筛选审计意见
    g.adjust_num = True  # 是否调整持仓数量
    
    # 全局变量 list
    g.hold_list = []  # 当前持仓的全部股票    
    g.yesterday_HL_list = []  # 记录持仓中昨日涨停的股票
    g.target_list = [] # 目标持仓列表
    g.limitup_stocks = []   # 记录涨停的股票避免再次买入
    
    # --- 修改点1：定义详细的空仓时间段 (格式：'MM-DD') ---
    g.pass_periods = [
        ('01-01', '01-31'), 
        ('04-01', '04-30'),
        ('12-15', '12-31')
    ]
    
    # 全局变量 float/str
    g.min_mv = 0  # 股票最小市值要求
    g.max_mv = 10000  # 股票最大市值要求
    g.stock_num = 3  # 持股数量
    g.reason_to_sell = ''
    g.stoploss_strategy = 1  # 1为止损线止损，2为市场趋势止损, 3为联合1、2策略
    g.stoploss_limit = 0.10  # 止损线
    g.stoploss_market = 0.05  # 市场趋势止损参数
    g.highest = 50  # 股票单价上限设置
    g.lowest = 1
    
    # 设置交易运行时间
    run_daily(prepare_stock_list, '9:05')
    
    # --- 修改点2：买卖时间分离 ---
    run_weekly(weekly_sell_task, 3, '09:30')
    run_weekly(weekly_buy_task, 3, '09:31')
    
    run_daily(trade_afternoon, time='14:20', reference_security='399101.XSHE') # 检查持仓中的涨停股是否需要卖出
    run_daily(sell_stocks, time='10:00') # 止损函数
    run_daily(sell_stocks, time='14:00') # 止损函数
    run_daily(close_account, '14:50')

# 1-1 准备股票池
def prepare_stock_list(context):
    # 获取已持有列表
    g.hold_list = []
    g.limitup_stocks = []
    for position in list(context.portfolio.positions.values()):
        stock = position.security
        g.hold_list.append(stock)
    
    # 获取昨日涨停列表
    if g.hold_list != []:
        df = get_price(g.hold_list, end_date=context.previous_date, frequency='daily', fields=['close','high_limit','low_limit'], count=1, panel=False, fill_paused=False)
        df = df[df['close'] == df['high_limit']]
        g.yesterday_HL_list = list(df.code)
    else:
        g.yesterday_HL_list = []
        
    # 每天检查一次是否在空仓期，更新信号
    check_pass_period(context)

# 1-2 选股模块
def get_stock_list(context):
    final_list = []
    MKT_index = '399101.XSHE'
    initial_list = filter_stocks(context, get_index_stocks(MKT_index))
    
    q = query(
        valuation.code,
        valuation.market_cap,
        income.np_parent_company_owners,
        income.net_profit,
        income.operating_revenue
    ).filter(
        valuation.code.in_(initial_list),
        valuation.market_cap.between(g.min_mv, g.max_mv),
        income.np_parent_company_owners > 0,
        income.net_profit > 0,
        income.operating_revenue > 1e8
    ).order_by(valuation.market_cap.asc()).limit(g.stock_num * 3)
    
    df = get_fundamentals(q)
    if g.filter_audit is True:
        before_audit_filter = len(df)
        df['audit'] = df['code'].apply(lambda x: filter_audit(context, x))
        df = df[df['audit'] == True]
        log.info('去除掉了存在审计问题的股票{}只'.format(len(df)-before_audit_filter))
    
    final_list = list(df.code)
    
    if len(final_list) == 0:
        log.info('无适合股票，空仓观望')
        return []
    else:
        last_prices = history(1, unit='1d', field='close', security_list=final_list)
        return [stock for stock in final_list if stock in g.hold_list or last_prices[stock][-1] >= g.lowest]


def weekly_sell_task(context):

    # 再次确认是否在空仓期
    check_pass_period(context)
    
    if g.trading_signal:
        # 1. 确定持仓数量
        new_num = adjust_stock_num(context)
        if g.stock_num != new_num:
            g.stock_num = new_num
            log.info(f'持仓数量修改为{new_num}')
        
        if new_num == 0:
            g.target_list = []
            log.info('MA指示指数大跌，清仓避险')
        else:
            # 2. 选股，生成目标列表 (这个列表会保留到下午使用)
            g.target_list = get_stock_list(context)[:g.stock_num]
            log.info(f"本周目标持仓: {g.target_list}")

        # 3. 执行卖出：卖出不在目标列表且昨日未涨停的股票
        sell_list = [stock for stock in g.hold_list if stock not in g.target_list and stock not in g.yesterday_HL_list]
        
        if sell_list:
            log.info("执行卖出计划: [%s]" % (str(sell_list)))
            sell_positions = [context.portfolio.positions[stock] for stock in sell_list]
            for position in sell_positions:
                close_position(position)
        else:
            log.info("无需要卖出的股票")
            
    else:
        # 如果是空仓期，清空目标列表，并执行清仓
        g.target_list = []
        log.info('当前处于空仓避险期，执行清仓')
        if g.hold_list:
            for stock in g.hold_list:
                close_position(context.portfolio.positions[stock])


def weekly_buy_task(context):
  
    # 如果是非交易期，或者目标列表为空，则不买入
    if not g.trading_signal or not g.target_list:
        log.info("无买入信号或目标列表为空，跳过买入")
        return

    # 确定保留的股票（在目标列表中或昨日涨停的）
    keep_list = [stock for stock in g.hold_list if stock in g.target_list or stock in g.yesterday_HL_list]
    log.info("当前保留持仓: [%s]" % (str(keep_list)))
    
    # 执行买入
    buy_security(context, g.target_list)


# 1-4 调整昨日涨停股票
def check_limit_up(context):
    now_time = context.current_dt
    if g.yesterday_HL_list != []:
        # 对昨日涨停股票观察到尾盘如不涨停则提前卖出
        for stock in g.yesterday_HL_list:
            current_data = get_price(stock, end_date=now_time, frequency='1m', fields=['close','high_limit'], skip_paused=False, fq='pre', count=1, panel=False, fill_paused=True)
            if current_data.iloc[0,0] < current_data.iloc[0,1]:
                log.info("[%s]涨停打开，卖出" % (stock))
                position = context.portfolio.positions[stock]
                close_position(position)
                g.reason_to_sell = 'limitup'
                g.limitup_stocks.append(stock)
            else:
                log.info("[%s]涨停，继续持有" % (stock))

# 1-5 如果昨天有股票卖出或者买入失败，剩余的金额今天早上买入
def check_remain_amount(context):
    if g.reason_to_sell == 'limitup': # 判断提前售出原因
        # 更新持仓列表
        current_hold_list = []
        for position in list(context.portfolio.positions.values()):
            stock = position.security
            current_hold_list.append(stock)
            
        if len(current_hold_list) < g.stock_num:
            # 计算需要买入的股票数量
            num_stocks_to_buy = min(len(g.limitup_stocks), g.stock_num - len(current_hold_list))
            # 排除掉刚卖出的涨停股
            target_list = [stock for stock in g.target_list if stock not in g.limitup_stocks][:num_stocks_to_buy]
            if target_list:
                log.info('涨停卖出后有余额，补仓买入: ' + str(target_list))
                buy_security(context, target_list)
        g.reason_to_sell = ''
        
    elif g.reason_to_sell == 'stoploss':
        log.info('止损触发，持有现金观望')
        g.reason_to_sell = ''

# 1-6 下午检查交易
def trade_afternoon(context):
    if g.trading_signal == True:
        check_limit_up(context)
        check_remain_amount(context)
        
# 1-7 止盈止损
def sell_stocks(context):
    return  # q-2 ablation: disable intraday stop-loss (no-op)
    if g.run_stoploss:
        current_positions = context.portfolio.positions

        if g.stoploss_strategy == 1 or g.stoploss_strategy == 3:
            for stock in list(current_positions.keys()):
                price = current_positions[stock].price
                avg_cost = current_positions[stock].avg_cost
                # 个股盈利止盈
                if price >= avg_cost * 2:
                    order_target_value(stock, 0)
                    log.debug("收益100%止盈,卖出{}".format(stock))
                # 个股止损
                elif price < avg_cost * (1 - g.stoploss_limit):
                    order_target_value(stock, 0)
                    log.debug("收益止损,卖出{}".format(stock))
                    g.reason_to_sell = 'stoploss'

        if g.stoploss_strategy == 2 or g.stoploss_strategy == 3:
            stock_df = get_price(security=get_index_stocks('399101.XSHE'), end_date=context.previous_date, frequency='daily', fields=['close', 'open'], count=1, panel=False)
            down_ratio = abs((stock_df['close'] / stock_df['open'] - 1).mean())
            # 市场大跌止损
            if down_ratio >= g.stoploss_market:
                g.reason_to_sell = 'stoploss'
                log.debug("大盘惨跌,平均降幅{:.2%}".format(down_ratio))
                for stock in list(current_positions.keys()):
                    order_target_value(stock, 0)

# 1-8 动态调仓代码
def adjust_stock_num(context):
    if g.adjust_num is True:
        ma_para = 10  # 设置MA参数
        today = context.previous_date
        start_date = today - datetime.timedelta(days = ma_para*2)
        index_df = get_price('399101.XSHE', start_date=start_date, end_date=today, frequency='daily')
        index_df['ma'] = index_df['close'].rolling(window=ma_para).mean()
        last_row = index_df.iloc[-1]
        diff = last_row['close'] - last_row['ma']
        # 根据差值结果返回数字
        result = 3 if diff >= 500 else \
                 3 if 200 <= diff < 500 else \
                 4 if -200 <= diff < 200 else \
                 5 if -500 <= diff < -200 else \
                 6
        return result
    else:
        return g.stock_num

# 2 过滤各种股票
def filter_stocks(context, stock_list):
    current_data = get_current_data()
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    filtered_stocks = []
    for stock in stock_list:
        if current_data[stock].paused:  # 停牌
            continue
        if current_data[stock].is_st:  # ST
            continue
        if '退' in current_data[stock].name:  # 退市
            continue
        if stock.startswith('30') or stock.startswith('68') or stock.startswith('8') or stock.startswith('4'):  # 市场类型
            continue
        if not (stock in context.portfolio.positions or last_prices[stock][-1] < current_data[stock].high_limit):  # 涨停
            continue
        if not (stock in context.portfolio.positions or last_prices[stock][-1] > current_data[stock].low_limit):  # 跌停
            continue
        # 次新股过滤
        start_date = get_security_info(stock).start_date
        if context.previous_date - start_date < timedelta(days=375):
            continue
        filtered_stocks.append(stock)
    return filtered_stocks

# 2.1 筛选审计意见
def filter_audit(context, code):
    lstd = context.previous_date
    last_year = (lstd.replace(year=lstd.year - 3, month=1, day=1)).strftime('%Y-%m-%d')
    q = query(finance.STK_AUDIT_OPINION).filter(finance.STK_AUDIT_OPINION.code==code,finance.STK_AUDIT_OPINION.pub_date>=last_year)
    df = finance.run_query(q)
    df['report_type'] = df['report_type'].astype(str)
    contains_nums = df['report_type'].str.contains(r'2|3|4|5')
    return not contains_nums.any()

# 3-1 交易模块-自定义下单
def order_target_value_(security, value):
    if value == 0:
        pass
    else:
        log.debug("Order %s to value %f" % (security, value))
    return order_target_value(security, value)

# 3-2 交易模块-开仓
def open_position(security, value):
    order = order_target_value_(security, value)
    if order != None and order.filled > 0:
        return True
    return False

# 3-3 交易模块-平仓
def close_position(position):
    security = position.security
    order = order_target_value_(security, 0)
    if order != None:
        if order.status == OrderStatus.held and order.filled == order.amount:
            return True
    return False

# 3-4 买入模块
def buy_security(context, target_list):
    # 调仓买入
    position_count = len(context.portfolio.positions)
    target_num = len(target_list)
    
    if target_num == 0:
        return

    # 找出实际需要新买入的股票
    stocks_to_buy = [s for s in target_list if s not in context.portfolio.positions]
    
    if len(stocks_to_buy) > 0:
        # 资金分配：可用资金 / 待买入数量
        value = context.portfolio.cash / len(stocks_to_buy)
        for stock in stocks_to_buy:
            if open_position(stock, value):
                log.info("买入[%s]（%s元）" % (stock, value))

# --- 修改点5：详细的日期段判断逻辑 ---
def check_pass_period(context):
    # 获取当前日期的 'MM-DD' 格式
    current_md = context.current_dt.strftime('%m-%d')
    
    is_pass = False
    for start_date, end_date in g.pass_periods:
        # 字符串比较 '01-01' <= '01-15' <= '01-31' 是有效的
        if start_date <= current_md <= end_date:
            is_pass = True
            break
            
    if is_pass:
        g.trading_signal = False
        log.info(f"当前日期 {current_md} 处于空仓避险期")
    else:
        g.trading_signal = True

# 4-2 清仓后次日资金可转
def close_account(context):
    # 每天收盘前检查，如果是空仓期，强制卖出
    check_pass_period(context)
    if g.trading_signal == False:
        if len(g.hold_list) != 0:
            for stock in g.hold_list:
                position = context.portfolio.positions[stock]
                close_position(position)
                log.info("空仓期，强制清理持仓[%s]" % (stock))

# ===== AUTORESEARCH NORMALIZATION OVERRIDE (appended; strategies/ file untouched) =====
# research/harness.md §2 — force zero slippage + frozen commission regardless of
# what the raw strategy sets, even if it re-sets costs every bar.
__jq_set_slippage = set_slippage
def set_slippage(*a, **k):
    __jq_set_slippage(FixedSlippage(0))
__jq_set_commission = set_commission
def set_commission(*a, **k):
    __jq_set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
try:
    __jq_orig_initialize = initialize
    def initialize(context):
        __jq_orig_initialize(context)
        set_option('use_real_price', True)
        set_slippage(FixedSlippage(0))
        set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
except NameError:
    pass
# ===== END OVERRIDE =====
