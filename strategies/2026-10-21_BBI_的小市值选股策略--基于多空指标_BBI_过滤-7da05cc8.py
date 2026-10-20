# Clone from JoinQuant
# postId: 7da05cc892ce9a80eb2bb079f00b34a5
# backtestId: 49ef4879a76fbdbdfd9bf78730d5b11f
# title: BBI 的小市值选股策略--基于多空指标（BBI）过滤

# 克隆自聚宽文章：https://www.joinquant.com/post/60630
# 标题：基于BBI（多空指标）的小市值选股策略_选股逻辑分析-克隆
# 作者：萤火量化

# 克隆自聚宽文章：https://www.joinquant.com/view/community/detail/24f283accd1c0dfb083c8e7b52c5c675
# 标题：回撤小，年化收益率高的策略
# 作者：股市的说法 

# from jqdata import *
from jqfactor import *
import numpy as np
import pandas as pd
import random
from datetime import time, datetime, timedelta

# 初始化函数
def initialize(context):
    # 开启防未来函数，设定基线，真实价格，滑点及交易成本
    set_option('avoid_future_data', True)
    set_benchmark('000001.XSHG')
    set_option('use_real_price', True)
    set_slippage(FixedSlippage(1/10000))
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=1/10000, 
                         close_commission=1/10000, close_today_commission=0, min_commission=5), type='stock')
    
    # 过滤order中低于error级别的日志
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'debug')
    
    # 创建全局变量字典替代G()对象
    context.g = {}
    
    # 初始化全局变量
    context.g['no_trading_today_signal'] = False  # 是否为可交易日
    context.g['run_stoploss'] = True  # 是否进行止损
    
    # 全局变量list
    context.g['hold_list'] = [] # 当前持仓的全部股票    
    context.g['yesterday_HL_list'] = [] # 记录持仓中昨日涨停的股票
    context.g['target_list'] = []  # 准备买入的标的
    context.g['not_buy_again'] = []    # 不再买入的标的
    
    # 全局变量float/str
    context.g['stock_num'] = 5
    context.g['m_days'] = 5  # 取值参考天数
    context.g['up_price'] = 80  # 设置股票单价
    context.g['reason_to_sell'] = ''
    context.g['stoploss_strategy'] = 3  # 1为止损线止损，2为市场趋势止损, 3为联合1、2策略
    context.g['stoploss_limit'] = 0.05  # 止损线
    context.g['stoploss_market'] = 0.05  # 市场趋势止损参数
    context.g['c'] = 0  # 止损天数计数器
    
    # 设置交易运行时间
    run_daily(prepare_stock_list, '8:00')       # 每天开盘前更新全局参数，持仓和昨日涨停
    run_weekly(weekly_adjustment, 2, '10:00')   # 每周二上午10点检查并调仓
    run_daily(sell_stocks, time='10:30')         # 每天检查止损
    run_daily(sell_stocks, time='14:00')         # 每天检查止损
    run_daily(trade_afternoon, time='14:30')     # 涨停检查/余额交易

# 全局变量快捷访问函数
def g(context):
    return context.g

# 1-1 更新全局参数，每天开盘前运行
def prepare_stock_list(context):
    # 更新已持有列表
    g(context)['hold_list'] = list(context.portfolio.positions.keys())
    
    # 更新持有股票中昨日涨停的股票
    if g(context)['hold_list']:
        df = get_price(g(context)['hold_list'], end_date=context.previous_date, frequency='daily', 
                      fields=['close', 'high_limit', 'low_limit'], count=1, panel=False, fill_paused=False)
        df = df[df['close'] == df['high_limit']]
        g(context)['yesterday_HL_list'] = list(df.code)
    else:
        g(context)['yesterday_HL_list'] = []
    
    # 全年可交易，无需特殊日期判断
    g(context)['no_trading_today_signal'] = False

# 1-2 选股模块，每周运行一遍
def get_stock_list(context):
    initial_list = get_index_stocks('399101.XSHE')  # 从中小综指中选股
    initial_list = filter_new_stock(context, initial_list)  # 过滤次新股
    initial_list = filter_kcbj_stock(initial_list)  # 过滤科创北交所股票
    initial_list = filter_st_stock(initial_list)    # 过滤ST股票
    
    # 筛选市值5-50亿，按市值升序排列
    q = query(valuation.code, valuation.market_cap).filter(
        valuation.code.in_(initial_list),
        valuation.market_cap.between(5, 50)
    ).order_by(valuation.market_cap.asc())
    df_fun = get_fundamentals(q)[:100]
    
    initial_list = list(df_fun.code)
    initial_list = filter_paused_stock(initial_list)                # 过滤停牌股票
    initial_list = filter_limitup_stock(context, initial_list)      # 过滤昨日涨停股票
    initial_list = filter_limitdown_stock(context, initial_list)     # 过滤昨日跌停股票
    initial_list = filter_highprice_stock(context, initial_list)    # 过滤股价过高的票
    
    # 再次筛选前50小市值股票
    q = query(valuation.code, valuation.market_cap).filter(
        valuation.code.in_(initial_list)
    ).order_by(valuation.market_cap.asc())
    df_fun = get_fundamentals(q)[:50]
    final_list = list(df_fun.code)
    
    # 增加BBI过滤条件：前一日收盘价在BBI线之上
    if not final_list:
        return final_list
        
    # 获取前24个交易日的收盘价数据
    start_date = context.previous_date - timedelta(days=60)  # 多取一些天数确保有足够数据
    prices = get_price(final_list, start_date=start_date, end_date=context.previous_date, 
                      frequency='daily', fields='close', panel=False)
    
    # 计算每只股票的BBI值
    bbi_dict = {}
    prev_close_dict = {}  # 用于存储前一日收盘价
    
    for stock in final_list:
        stock_data = prices[prices['code'] == stock]
        if len(stock_data) < 24:  # 确保有足够数据计算
            continue
            
        closes = stock_data['close'].values
        # 存储前一日收盘价
        prev_close_dict[stock] = closes[-1]
        
        # 计算不同周期的移动平均
        ma3 = np.mean(closes[-3:])
        ma6 = np.mean(closes[-6:])
        ma12 = np.mean(closes[-12:])
        ma24 = np.mean(closes[-24:])
        
        # 计算BBI
        bbi = (ma3 + ma6 + ma12 + ma24) / 4
        bbi_dict[stock] = bbi
    
    # 筛选前一日收盘价大于BBI的股票
    filtered_list = [stock for stock in prev_close_dict.keys() 
                   if stock in bbi_dict 
                   and prev_close_dict[stock] > bbi_dict[stock]]
    
    # 按市值重新排序
    if filtered_list:
        q = query(valuation.code, valuation.market_cap).filter(
            valuation.code.in_(filtered_list)
        ).order_by(valuation.market_cap.asc())
        df_filtered = get_fundamentals(q)
        return list(df_filtered.code)
    
    return filtered_list

# 1-3 每周调整持仓
def weekly_adjustment(context):
    # 全年可交易，直接执行调仓逻辑
    # 获取应买入列表 
    g(context)['not_buy_again'] = []  # 每周重置不再买入标的
    g(context)['target_list'] = get_stock_list(context)  # 获取目标股票池
    target_list = g(context)['target_list'][:g(context)['stock_num']]
    
    # 调仓卖出
    current_high_limit = now_high_limit(context)  # 当前涨停股票
    for stock in g(context)['hold_list']:
        # 非目标股且非涨停股则卖出
        if (stock not in target_list) and (stock not in current_high_limit):
            position = context.portfolio.positions[stock]
            if close_position(position):
                log.info("卖出[%s]" % (stock))
            else:
                log.info("!!! 卖出失败[%s]" % (stock))
        else:
            log.info("已持有[%s]" % (stock))
    
    # 调仓买入
    buy_security(context, target_list)
    
    # 记录已买入股票
    for stock in list(context.portfolio.positions.keys()):
        g(context)['not_buy_again'].append(stock)

# 1-7 每天定点检查止损
def sell_stocks(context):
    if g(context)['run_stoploss']:
        if g(context)['stoploss_strategy'] == 1:
            for stock in context.portfolio.positions.keys():
                position = context.portfolio.positions[stock]
                # 止盈100%
                if position.price >= position.avg_cost * 2:
                    order_target_value(stock, 0)
                    log.debug("收益100%止盈,卖出{}".format(stock))
                # 止损7%
                elif position.price < position.avg_cost * (1 - g(context)['stoploss_limit']):
                    order_target_value(stock, 0)
                    log.debug("收益止损,卖出{}".format(stock))
                    g(context)['reason_to_sell'] = 'stoploss'
                    
        elif g(context)['stoploss_strategy'] == 2:
            # 计算市场整体跌幅
            stocks = get_index_stocks('399101.XSHE')
            stock_df = get_price(security=stocks, end_date=context.previous_date, 
                                frequency='daily', fields=['close', 'open'], count=1, panel=False)
            down_ratio = abs((stock_df['close'] / stock_df['open'] - 1)).mean()
            
            # 市场大跌时清仓
            if down_ratio >= g(context)['stoploss_market']:
                g(context)['reason_to_sell'] = 'stoploss'
                log.debug("大盘惨跌,平均降幅{:.2%}".format(down_ratio))
                for stock in context.portfolio.positions.keys():
                    order_target_value(stock, 0)
                    
        elif g(context)['stoploss_strategy'] == 3:
            # 市场整体风险检查
            stocks = get_index_stocks('399101.XSHE')
            stock_df = get_price(security=stocks, end_date=context.previous_date, 
                                frequency='daily', fields=['close', 'open'], count=1, panel=False)
            down_ratio = abs((stock_df['close'] / stock_df['open'] - 1)).mean()
            
            if down_ratio >= g(context)['stoploss_market']:
                g(context)['reason_to_sell'] = 'stoploss'
                log.debug("基准指数暴跌,平均降幅{:.2%},全部清仓".format(down_ratio))
                for stock in context.portfolio.positions.keys():
                    order_target_value(stock, 0)
            else:
                # 个股止损
                for stock in context.portfolio.positions.keys():
                    position = context.portfolio.positions[stock]
                    if position.price < position.avg_cost * (1 - g(context)['stoploss_limit']):
                        order_target_value(stock, 0)
                        log.debug("达到止损,卖出{}".format(stock))
                        g(context)['reason_to_sell'] = 'stoploss'

# 1-4 检查涨停股是否打开涨停
def check_limit_up(context):
    now_time = context.current_dt  # 当前时间
    if g(context)['yesterday_HL_list']:
        # 检查昨日涨停股票
        for stock in g(context)['yesterday_HL_list']:
            current_data = get_price(stock, end_date=now_time, frequency='1m', 
                                    fields=['close', 'high_limit'], count=1, panel=False)
            if not current_data.empty and current_data.iloc[0]['close'] < current_data.iloc[0]['high_limit']:
                position = context.portfolio.positions[stock]
                if close_position(position):
                    log.info("[%s]涨停打开，卖出" % (stock))
                    g(context)['reason_to_sell'] = 'limitup'
            else:
                log.info("[%s]涨停，继续持有" % (stock))

# 1-5 账户余额检查及再买入
def check_remain_amount(context):
    # 因涨停卖出时可再买入
    if g(context)['reason_to_sell'] == 'limitup':
        g(context)['hold_list'] = list(context.portfolio.positions.keys())
        if len(g(context)['hold_list']) < g(context)['stock_num']:
            # 过滤不再买入标的
            target_list = [s for s in g(context)['target_list'] if s not in g(context)['not_buy_again']]
            target_list = target_list[:min(g(context)['stock_num'] - len(g(context)['hold_list']), len(target_list))]
            
            log.info('有余额可用:' + str(round(context.portfolio.cash, 2)) + '元')
            buy_security(context, target_list)
            
        g(context)['reason_to_sell'] = ''
    else:
        g(context)['c'] += 1
        log.info('刚刚止损，隔1天再交易')
        if g(context)['c'] % 2 == 0:
            g(context)['reason_to_sell'] = ''

# 1-6 下午交易操作
def trade_afternoon(context):
    # 全年可交易，直接执行下午交易逻辑
    check_limit_up(context)       # 检查涨停股
    check_remain_amount(context)  # 余额再投资

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
    return [stock for stock in stock_list
            if stock[0] not in ['4', '8']  # 过滤北交所
            and not stock.startswith('688')  # 过滤科创板
            and not stock.startswith('300')]  # 过滤创业板

# 2-4 过滤除持仓外涨停的股票
def filter_limitup_stock(context, stock_list):
    if not stock_list:
        return []
    
    # 获取昨日收盘价和涨停价
    df = get_price(stock_list, end_date=context.previous_date, frequency='daily',
                  fields=['close', 'high_limit'], count=1, panel=False, fill_paused=False)
    if df.empty:
        return stock_list
    
    # 筛选涨停股代码
    limit_up_stocks = df[df['close'] == df['high_limit']]['code'].tolist()
    
    # 返回非涨停股或持仓股
    return [stock for stock in stock_list 
            if stock in g(context)['hold_list'] or stock not in limit_up_stocks]

# 2-5 过滤除了持仓外跌停的股票
def filter_limitdown_stock(context, stock_list):
    if not stock_list:
        return []
    
    # 获取昨日收盘价和跌停价
    df = get_price(stock_list, end_date=context.previous_date, frequency='daily',
                  fields=['close', 'low_limit'], count=1, panel=False, fill_paused=False)
    if df.empty:
        return stock_list
    
    # 筛选跌停股代码
    limit_down_stocks = df[df['close'] == df['low_limit']]['code'].tolist()
    
    # 返回非跌停股或持仓股
    return [stock for stock in stock_list 
            if stock in g(context)['hold_list'] or stock not in limit_down_stocks]

# 2-6 过滤次新股
def filter_new_stock(context, stock_list):
    if not stock_list:
        return []
    
    yesterday = context.previous_date
    filtered = []
    for stock in stock_list:
        info = get_security_info(stock)
        # 上市超过1年（375天）
        if (yesterday - info.start_date).days > 375:
            filtered.append(stock)
    return filtered

# 2-7 过滤除持仓外股价过高的股票
def filter_highprice_stock(context, stock_list):
    if not stock_list:
        return []
    
    # 获取昨日收盘价
    prices = get_price(stock_list, end_date=context.previous_date, frequency='daily',
                      fields='close', count=1, panel=False)
    if prices.empty:
        return []
    
    # 按股票分组获取最后收盘价
    last_prices = prices.groupby('code')['close'].last()
    
    # 返回持仓股或低价股
    return [stock for stock in stock_list 
            if stock in g(context)['hold_list'] or last_prices.get(stock, 999) <= g(context)['up_price']]

# 2-8 过滤不再买入标的
def filter_not_buy_again(stock_list):
    return [stock for stock in stock_list if stock not in g(context)['not_buy_again']]

# 3-1 交易模块-自定义下单
def order_target_value(security, value):
    if value == 0:  # 清仓操作
        result = order_target(security, 0)
        if result:
            log.debug("卖出成功: %s" % security)
            return True
        return False
    else:  # 买入操作
        log.debug("买入[%s]，金额:%.2f" % (security, value))
        result = order_value(security, value)
        if result and result.filled > 0:
            return True
        return False

# 3-2 交易模块-开仓
def open_position(security, value):
    return order_target_value(security, value)

# 3-3 交易模块-平仓
def close_position(position):
    return order_target_value(position.security, 0)

# 3-4 买入模块
def buy_security(context, target_list):
    position_count = len(context.portfolio.positions)  # 当前持仓数
    target_num = len(target_list)  # 目标持仓数
    
    if target_num > position_count:
        # 计算每只股票应分配的金额
        value_per_stock = context.portfolio.cash / (target_num - position_count)
        
        for stock in target_list:
            # 排除已有持仓
            if context.portfolio.positions.get(stock) is None or context.portfolio.positions[stock].closeable_amount == 0:
                if open_position(stock, value_per_stock):
                    log.info("买入[%s]，金额%.2f元" % (stock, value_per_stock))
                    g(context)['not_buy_again'].append(stock)  # 加入不再买入列表
                    if len(context.portfolio.positions) == target_num:
                        break

# 辅助函数：获取当前涨停股
def now_high_limit(context):
    cdata = get_current_data()
    return [stock for stock in g(context)['hold_list'] 
            if stock in cdata and getattr(cdata[stock], 'last_price', 0) >= getattr(cdata[stock], 'high_limit', 0)]