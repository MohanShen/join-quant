# Clone from JoinQuant
# postId: 62a9b3aeb7e7898a23c45a0675ae5ab2
# backtestId: cc471daca5aca2efe78971e98d36f40f
# title: 四大四小银行轮动2只周频轮动-升级版

# 克隆自聚宽文章：https://www.joinquant.com/post/62562
# 标题：八大行 轮动做T，已实盘
# 作者：fqd1999

import math
import pandas as pd
import numpy as np
import statsmodels.api as sm
import scipy.stats as scs
import scipy.optimize as sco
import talib as tl
from datetime import timedelta

# 八大银行股票池：原四大行 + 工行、农行、中行、建行
bank_stocks = [
    '601528.XSHG',  # 瑞丰银行
    '001227.XSHE',  # 兰州银行  
    '601860.XSHG',  # 紫金银行
    '600908.XSHG',  # 无锡银行
    '601398.XSHG',  # 工商银行
    '601288.XSHG',  # 农业银行
    '601939.XSHG',  # 建设银行
    '601988.XSHG'   # 中国银行
]

# 初始化参数
def initialize(context):
    # 设置股票池为空（动态调整）
    set_universe([])
    g.riskbench = '000300.XSHG'  # 沪深300作为基准

    # 使用真实价格
    set_option('use_real_price', True)
    
     # 滑点设置（实际交易滑点）
    set_slippage(PriceRelatedSlippage(0.001))
    

    set_option('use_real_price', True)
    set_option('avoid_future_data', True)  # 防未来函数
    # 交易成本设置（保持原始）
    set_order_cost(OrderCost(
        open_tax=0,  # 买入无印花税
        close_tax=0.0005,  # 卖出印花税万5
        open_commission=0.0001,  # 买入佣金万一
        close_commission=0.0001,  # 卖出佣金万一
        close_today_commission=0,  # 无实际意义，保留0
        min_commission=5  # 最低佣金5元
    ), type='stock')
    
    
    # 价差阈值（0.5%）
    g.inter = 0.004
    # 初始化止损标记（Python 3需显式定义）
    g.is_stop = False
    # 记录每只股票的买入日期
    g.buy_dates = {}

# 每天交易前调用
def before_trading_start(context):
    # 获取前一交易日收盘价（Python 3中history函数返回DataFrame时兼容处理）
    g.df_last = history(
        1, 
        unit='1d', 
        field='close', 
        security_list=bank_stocks, 
        df=False, 
        skip_paused=True, 
        fq='pre'
    )

# 每个单位时间调用（按分钟回测时每分钟触发）
def handle_data(context, data):
    raito = []
    # 计算当前价格与前一日收盘价的比值（涨幅比例）
    for code in bank_stocks:
        # Python 3中列表索引和除法兼容
        raito.append(data[code].close / g.df_last[code][-1])
    
    # 空仓时的开仓逻辑
    if not context.portfolio.positions:  # Python 3中keys()返回视图，直接判断是否为空更简洁
        if max(raito) - min(raito) > g.inter:
            # 找到涨幅最小的股票索引
            min_index = raito.index(min(raito))
            # 满仓买入
            order_value(bank_stocks[min_index], context.portfolio.total_value)
            # 记录买入日期
            g.buy_dates[bank_stocks[min_index]] = context.current_dt.date()
            g.is_stop = True
    # 持仓时的调仓逻辑
    else:
        # Python 3中dict.keys()返回视图，需转换为列表取第一个元素
        code = list(context.portfolio.positions.keys())[0]
        index = bank_stocks.index(code)
        # 当前持仓涨幅与最小涨幅的差值超过阈值时调仓
        if raito[index] - min(raito) > g.inter:
            # 检查是否是今天买入的股票
            if code in g.buy_dates and g.buy_dates[code] == context.current_dt.date():
                # 如果是今天买入的，不能卖出，跳过调仓
                log.info(f"股票{code}是今天买入的，不能卖出，跳过调仓")
                return
            # 清空当前持仓
            order_target(code, 0)
            # 确保卖出后资金可用再买入（实际交易中需要处理延迟）
            min_index = raito.index(min(raito))
            # 这里需要处理资金到账的延迟，可能需要第二天才能买入
            # 从买入日期记录中移除
            if code in g.buy_dates:
                del g.buy_dates[code]
            
            # 买入新的涨幅最小的股票
            min_index = raito.index(min(raito))
            order_value(bank_stocks[min_index], context.portfolio.total_value)
            # 记录新买入股票的日期
            g.buy_dates[bank_stocks[min_index]] = context.current_dt.date()
            g.is_stop = True

# 每天交易后调用，计算并记录累计收益率
def after_trading_end(context):
    """
    计算银行股的累计收益率
    股票池：八大银行
    """

    # 初始化累计收益率历史记录（如果不存在）
    if not hasattr(g, 'cumulative_return_history'):
        g.cumulative_return_history = {stock: [] for stock in bank_stocks}
    if not hasattr(g, 'dates_history'):
        g.dates_history = []

    # 获取历史价格数据（包含当天）
    lookback_days = 1  # 只需要前一天的数据来计算当日收益率
    try:
        hist_data = history(lookback_days, '1d', 'close', bank_stocks, df=True, skip_paused=True, fq='pre')

        # 获取当前价格
        current_data = get_current_data()
        current_prices = {stock: current_data[stock].last_price for stock in bank_stocks}

        # 记录当前日期
        current_date = context.current_dt.strftime('%Y-%m-%d')
        g.dates_history.append(current_date)

        # 计算每个股票的日收益率和更新累计收益率
        for stock in bank_stocks:
            if stock in hist_data.columns and len(hist_data[stock]) >= lookback_days:
                # 计算当日收益率
                prev_close = hist_data[stock].iloc[-1]  # 昨日收盘价
                today_close = current_prices[stock]  # 今日收盘价
                daily_return = (today_close - prev_close) / prev_close

                # 计算累计收益率
                if not g.cumulative_return_history[stock]:  # 第一天
                    cumulative_return = daily_return
                else:
                    prev_cumulative = g.cumulative_return_history[stock][-1]
                    cumulative_return = (1 + prev_cumulative) * (1 + daily_return) - 1

                g.cumulative_return_history[stock].append(cumulative_return)

                # 使用record函数记录累计收益率（用于回测图表）
                if stock == '601528.XSHG':
                    record(瑞丰银行=round(cumulative_return * 100, 2))
                elif stock == '001227.XSHE':
                    record(兰州银行=round(cumulative_return * 100, 2))
                elif stock == '601860.XSHG':
                    record(紫金银行=round(cumulative_return * 100, 2))
                elif stock == '600908.XSHG':
                    record(无锡银行=round(cumulative_return * 100, 2))
                elif stock == '601398.XSHG':
                    record(工商银行=round(cumulative_return * 100, 2))
                elif stock == '601288.XSHG':
                    record(农业银行=round(cumulative_return * 100, 2))
                elif stock == '601939.XSHG':
                    record(建设银行=round(cumulative_return * 100, 2))
                elif stock == '601988.XSHG':
                    record(中国银行=round(cumulative_return * 100, 2))
            else:
                # 数据不足时记录0
                cumulative_return = 0
                g.cumulative_return_history[stock].append(cumulative_return)

        # 打印当日累计收益率情况
        log.info("累计收益率报告 " + "*" * 60)
        for stock in bank_stocks:
            stock_name = get_stock_name(stock)
            latest_cumulative = g.cumulative_return_history[stock][-1] if g.cumulative_return_history[stock] else 0
            log.info(f"  {stock} {stock_name}:  {latest_cumulative * 100:.2f}%")

    except Exception as e:
        log.error(f"计算累计收益率失败: {e}")

# 辅助函数：获取股票名称
def get_stock_name(stock_code):
    name_mapping = {
        '601528.XSHG': '瑞丰银行',
        '001227.XSHE': '兰州银行',
        '601860.XSHG': '紫金银行', 
        '600908.XSHG': '无锡银行',
        '601398.XSHG': '工商银行',
        '601288.XSHG': '农业银行',
        '601939.XSHG': '建设银行',
        '601988.XSHG': '中国银行'
    }
    return name_mapping.get(stock_code, stock_code)