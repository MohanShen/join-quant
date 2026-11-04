# Clone from JoinQuant
# postId: d9420b920aa364c3ba35e03951b74046
# backtestId: 10f89c77a5eac69ca01594b48146a7c4
# title: 桐峰小市值-debug第二版，10年千倍

#### 克隆自聚宽文章：https://www.joinquant.com/post/58646
#### 标题：实盘前的debug让收益翻倍(十年回测近千倍)
#### 作者：蚂蚁量化

#### 克隆自聚宽文章：https://www.joinquant.com/post/58633
#### 标题：准备实盘，帮忙看看是否可以？
#### 作者：桐峰

# -*- coding: utf-8 -*-
"""
量化交易策略：小市值选股+动态止损系统
核心逻辑：
1. 每月从中小板指筛选市值5-300亿的股票池
2. 每周调仓持有市值最小的4只股票
3. 实施组合止损策略（个股止损+大盘止损）
4. 特殊处理涨停板股票
5. 每年1月和4月空仓
"""

# 聚宽平台API
from jqdata import *  
# 因子分析模块（未实际使用但保留）
from jqfactor import *  
import numpy as np  
import pandas as pd  
from datetime import time, timedelta  

# ========== 全局参数配置 ==========
BENCHMARK = '000001.XSHG'  # 上证指数作为基准
MARKET_INDEX = '399101.XSHE'  # 中小板指作为选股范围
EMPTY_MONTHS = [1, 4]  # 1月和4月空仓
CASH_ETF = '511880.XSHG'  # 货币ETF用于空仓时现金管理

# 止损策略类型常量
STOPLOSS_SINGLE = 1   # 仅个股止损
STOPLOSS_MARKET = 2   # 仅大盘止损 
STOPLOSS_COMBINED = 3 # 复合止损策略（默认）


def initialize(context):
    """策略初始化函数，由聚宽框架自动调用"""
    # 防止未来函数
    set_option('avoid_future_data', True)
    # 设置基准收益率
    set_benchmark(BENCHMARK)
    # 使用真实价格回测
    set_option('use_real_price', True)
    # 设置滑点（单边0.3%）
    set_slippage(FixedSlippage(3/1000))
    # 设置交易成本（股票万2.5，卖出印花税0.1%）
    set_order_cost(
        OrderCost(
            open_tax=0,                # 买入印花税
            close_tax=0.001,           # 卖出印花税
            open_commission=2.5/10000, # 买入佣金
            close_commission=2.5/10000,# 卖出佣金
            close_today_commission=0,  # 平今佣金（股票无）
            min_commission=5           # 最低佣金
        ),
        type='stock'
    )
    
    # 设置日志级别
    log.set_level('order', 'error')   # 订单日志只报错
    log.set_level('system', 'error')  # 系统日志只报错
    log.set_level('strategy', 'debug') # 策略日志显示debug信息

    # ========== 初始化全局变量 ==========
    g.trading_signal = True       # 当日是否可交易
    g.run_stoploss = True         # 是否运行止损逻辑
    g.hold_list = []              # 当前持仓股票列表
    g.yesterday_HL_list = []      # 昨日涨停股票列表
    g.target_list = []            # 本周目标股票池
    g.pass_months = EMPTY_MONTHS  # 空仓月份配置
    g.limitup_stocks = []         # 当日涨停股票列表
    g.target_stock_count = 4      # 目标持仓数量
    g.sell_reason = ''            # 卖出原因记录（用于日志）
    g.stoploss_strategy = STOPLOSS_COMBINED  # 使用复合止损策略
    g.stoploss_limit = 0.06       # 个股止损阈值6%
    g.stoploss_market = 0.05      # 大盘止损阈值5%
    g.etf = CASH_ETF              # 现金管理ETF代码
    
    # 初始执行选股
    filter_monthly(context)
    # ========== 定时任务设置 ==========
    run_monthly(filter_monthly, 1, '9:00')      # 每月1号9点选股
    run_daily(prepare_stock_list, '9:05')       # 每日开盘前准备
    run_daily(trade_afternoon, '14:00')         # 下午交易时段
    run_daily(sell_stocks, '10:00')             # 上午执行止损
    run_daily(close_account, '14:50')           # 收盘前清理仓位
    run_weekly(weekly_adjustment, 2, '10:00')   # 每周二调仓

def prepare_stock_list(context):
    """每日开盘前准备数据"""
    # 获取当前持仓列表
    g.hold_list = [pos.security for pos in context.portfolio.positions.values()]
    g.limitup_stocks = []  # 重置当日涨停列表

    if g.hold_list:
        # 获取持仓股昨日收盘价和涨停价
        price_df = get_price(
            g.hold_list,
            end_date=context.previous_date,  # 使用前一日数据
            frequency='daily',
            fields=['close', 'high_limit'], # 需要收盘价和涨停价
            count=1,
            panel=False,
            fill_paused=False
        )
        # 筛选昨日收盘价等于涨停价的股票
        g.yesterday_HL_list = price_df[price_df['close'] == price_df['high_limit']]['code'].tolist()
    else:
        g.yesterday_HL_list = []

    # 检查当日是否可交易（非空仓月份）
    g.trading_signal = today_is_tradable(context)

def filter_monthly(context):
    """月度选股：从中小板指筛选小市值股票"""
    # 构建查询：选择中小板指成分股，市值5-300亿，按市值升序排列
    q = query(
        valuation.code,
    ).filter(
        valuation.code.in_(get_index_stocks(MARKET_INDEX)),
        valuation.market_cap.between(5, 300)  # 市值单位：亿元
    ).order_by(
        valuation.market_cap.asc()  # 小市值优先
    )
    # 获取基本面数据
    fund_df = get_fundamentals(q)
    # 取市值最小的N*20只股票（N为目标持仓数）
    g.month_scope = fund_df['code'].head(g.target_stock_count * 20).tolist()
    
def get_stock_list(context):
    """从月度股票池筛选最终候选股票"""
    # 先进行基础过滤（剔除ST、新股等）
    filtered_stocks = filter_stocks(context, g.month_scope)

    # 再次查询市值数据
    q = query(
        valuation.code,
        valuation.market_cap
    ).filter(
        valuation.code.in_(filtered_stocks),
        valuation.market_cap.between(5, 300)
    ).order_by(
        valuation.market_cap.asc()  # 仍然按市值排序
    )
    fund_df = get_fundamentals(q)
    # 取市值最小的N*3只作为候选（N为目标持仓数）
    candidate_stocks = fund_df['code'].head(g.target_stock_count * 3).tolist()
    return candidate_stocks

def weekly_adjustment(context):
    """每周调仓逻辑"""
    if not g.trading_signal:
        # 空仓月份直接买入货币ETF
        buy_security(context, [g.etf])
        log.info(f"空仓月份({g.pass_months})，持有{g.etf}")
        return

    # 获取本周目标股票池
    g.target_list = get_stock_list(context)
    log.info(f"本周目标持仓：{g.target_list}")
    
    # 构建卖出列表（需同时满足三个条件）：
    # 1. 不在本周目标前N名
    # 2. 昨日未涨停（给予涨停股额外持有机会）
    # 3. 未停牌
    current_data = get_current_data()
    sell_list = [
        stock for stock in g.hold_list
        if stock not in g.target_list[:g.target_stock_count] and 
           stock not in g.yesterday_HL_list and 
           not current_data[stock].paused
    ]
    
    # 执行卖出
    for stock in sell_list:
        close_position(context.portfolio.positions[stock])
    log.info(f"调仓卖出：{sell_list}")
    log.info(f"继续持有：{[s for s in g.hold_list if s not in sell_list]}")
    
    # 计算需要买入的数量
    to_buy_num = g.target_stock_count - len(context.portfolio.positions)
    # 构建买入列表（需同时满足三个条件）：
    # 1. 在目标池中
    # 2. 当前未持有
    # 3. 昨日未涨停（避免追高）
    to_buy = [x for x in g.target_list 
             if x not in context.portfolio.positions.keys() and 
                x not in g.yesterday_HL_list][:to_buy_num]
    buy_security(context, to_buy)

def check_limit_up(context):
    """检查昨日涨停股今日是否开板"""
    if not g.yesterday_HL_list:
        return
        
    current_data = get_current_data()
    for stock in g.yesterday_HL_list:
        current_close = current_data[stock].last_price
        high_limit = current_data[stock].high_limit

        if current_close < high_limit:
            # 如果涨停打开则卖出
            close_position(context.portfolio.positions[stock])
            g.sell_reason = 'limitup'  # 记录卖出原因
            g.limitup_stocks.append(stock)  # 加入当日涨停列表
            log.info(f"{stock}涨停打开，执行卖出")
        else:
            log.info(f"{stock}维持涨停，继续持有")

def check_remain_amount(context):
    """卖出后剩余资金处理"""
    if not g.sell_reason:  # 无卖出操作直接返回
        return

    g.hold_list = [pos.security for pos in context.portfolio.positions.values()]
    cash = context.portfolio.cash

    if g.sell_reason == 'limitup':
        # 涨停卖出后的资金再投资
        need_buy_count = g.target_stock_count - len(g.hold_list)
        if need_buy_count > 0:
            # 从目标池排除已涨停股票
            candidates = [s for s in g.target_list 
                         if s not in g.limitup_stocks and 
                            s not in g.hold_list]
            buy_list = candidates[:need_buy_count]
            log.info(f"涨停卖出后剩余资金{cash:.2f}元，补仓：{buy_list}")
            buy_security(context, buy_list)
    elif g.sell_reason == 'stoploss':
        # 止损后转货币ETF
        log.info(f"止损后剩余资金{cash:.2f}元，持有{g.etf}")
        buy_security(context, [g.etf])

    g.sell_reason = ''  # 重置卖出原因

def trade_afternoon(context):
    """下午交易时段操作"""
    if g.trading_signal:
        check_limit_up(context)   # 检查涨停股
        check_remain_amount(context)  # 处理剩余资金

def sell_stocks(context):
    """执行止损策略"""
    if not g.run_stoploss:  # 止损开关检查
        return

    positions = context.portfolio.positions
    if not positions:  # 无持仓直接返回
        return
        
    current_data = get_current_data()
    
    # 个股止损逻辑（复合策略或单独策略）
    if g.stoploss_strategy in (STOPLOSS_SINGLE, STOPLOSS_COMBINED):
        for stock, pos in positions.items():
            current_price = pos.price
            avg_cost = pos.avg_cost
            if current_data[stock].paused: continue  # 跳过停牌股
            
            # 止盈逻辑（收益率≥100%）
            if current_price >= avg_cost * 2:
                order_target_value(stock, 0)
                log.debug(f"{stock}收益100%，执行止盈")
            # 止损逻辑（亏损≥阈值）
            elif current_price < avg_cost * (1 - g.stoploss_limit):
                order_target_value(stock, 0)
                log.debug(f"{stock}跌幅达{int(g.stoploss_limit*100)}%，执行止损")
                g.sell_reason = 'stoploss'  # 记录止损原因

    # 大盘止损逻辑（复合策略或单独策略）
    if g.stoploss_strategy in (STOPLOSS_MARKET, STOPLOSS_COMBINED):
        # 获取中小板指当日涨跌幅
        index_price = get_price(
            MARKET_INDEX,
            end_date=context.previous_date,
            frequency='daily',
            fields=['open', 'close'],
            count=1
        )
        if not index_price.empty:
            # 计算日内涨跌幅（收盘/开盘-1）
            market_down_ratio = (index_price['close'].iloc[0] / index_price['open'].iloc[0]) - 1
            if abs(market_down_ratio) >= g.stoploss_market:
                # 当昨天日内涨跌幅超过g.stoploss_market, 清仓所有非ETF持仓
                for stock in positions.keys():
                    if stock == g.etf: continue
                    order_target_value(stock, 0)
                g.sell_reason = 'stoploss'
                log.debug(f"市场平均跌幅{market_down_ratio:.2%}，执行止损")

def filter_stocks(context, stock_list):
    """股票过滤器：剔除不符合条件的股票"""
    if not stock_list:
        return []

    current_data = get_current_data()
    # 获取前一分钟收盘价（用于判断涨跌停）
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    filtered = []

    for stock in stock_list:
        data = current_data[stock]
        # 基础过滤条件
        if data.paused: continue                   # 剔除停牌股
        if data.is_st or '退' in data.name:       # 剔除ST/*ST/退市股
            continue  
        if stock.startswith(('30', '68', '8', '4')): # 剔除创业板/科创板等
            continue  
        # 涨跌停过滤（已持仓股不受限）
        if stock not in g.hold_list and last_prices[stock].iloc[-1] >= data.high_limit:
            continue  # 剔除涨停股
        if stock not in g.hold_list and last_prices[stock].iloc[-1] <= data.low_limit:
            continue  # 剔除跌停股
        # 次新股过滤（上市不满375天）
        listing_date = get_security_info(stock).start_date
        if (context.previous_date - listing_date).days < 375:
            continue

        filtered.append(stock)
    return filtered

# ========== 以下是工具函数 ==========
def order_target_value_(security, value):
    """带日志的下单函数"""
    if value == 0:
        log.debug(f"清仓 {security}")
    else:
        log.debug(f"下单 {security}，目标市值 {value:.2f} 元")
    return order_target_value(security, value)

def open_position(security, value):
    """开仓操作"""
    order = order_target_value_(security, value)
    return order is not None and order.filled > 0  # 返回是否成交

def close_position(position):
    """平仓操作"""
    security = position.security
    order = order_target_value_(security, 0)
    if order:
        return order.status == OrderStatus.held and order.filled == order.amount
    return False

def buy_security(context, target_list):
    """按等金额买入股票"""
    current_hold = [pos.security for pos in context.portfolio.positions.values()]
    need_buy = [stock for stock in target_list if stock not in current_hold]
    if not need_buy:
        return

    buy_count = len(need_buy)
    cash = context.portfolio.cash
    if cash <= 0 or buy_count <= 0:
        return

    # 等分现金买入
    per_stock_value = cash / buy_count

    for stock in need_buy:
        if open_position(stock, per_stock_value):
            log.info(f"买入 {stock}，金额 {per_stock_value:.2f} 元")
            # 达到目标持仓数即停止
            if len(context.portfolio.positions) == g.target_stock_count:
                break

def today_is_tradable(context):
    """检查当日是否交易日（非空仓月份）"""
    return context.current_dt.month not in g.pass_months

def close_account(context):
    """收盘前清理仓位（空仓月份专用）"""
    if not g.trading_signal:
        current_data = get_current_data()
        current_hold = [pos.security for pos in context.portfolio.positions.values()]
        for stock in current_hold: 
            if current_data[stock].paused: continue  # 跳过停牌股
            if stock == g.etf: continue              # 保留货币ETF
            close_position(context.portfolio.positions[stock])
            log.info(f"空仓月份清仓：{stock}")