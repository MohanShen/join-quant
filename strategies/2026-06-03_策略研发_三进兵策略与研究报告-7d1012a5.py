# Clone from JoinQuant
# postId: 7d1012a5369fc50322e45a4a9847ca4b
# backtestId: f0dd2f4ef113ad19fb86541b7c25661c
# title: 【策略研发】三进兵策略与研究报告

"""
说明：
所谓的三进兵，是指三条EMA均线组合的策略javascript:void(0);
交易原则：
系统由三条EMA均线组合而成，分别为小均线、中均线、大均线
当小均线金叉大均线、并且中均线位于大均线下方时，买入
当小均线死叉中均线，并且中均线位于大均线上方时，卖出
止损：当买入后，如果收盘价跌破中均线，止损
选股：本策略里没有做自动选股，而是手动挑选了一些
在研究里做了更多股票的研究，发现本策略并不是适合所有的股票的
所以，各位宽友如果有想法，可在此基础上做迭代，并分享出来，展示你的才华
"""

import numpy as np
import pandas as pd
import datetime
from jqdata import *
from jqlib.technical_analysis import *

def initialize(context):
    # 所谓的三进兵，就是这里的三个Ma线
    g.ma_min = 5
    g.ma_med = 20
    g.ma_max = 60
    
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 设置成交量比例
    set_option('order_volume_ratio', 0.25)
    # 日志过滤
    log.set_level('order', 'error')
    # 为股票设定滑点为百分比滑点
    set_slippage(PriceRelatedSlippage(0.00246),type='stock')
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    g.stokcs_pool = ['300014.XSHE', '300059.XSHE', '300168.XSHE', '300253.XSHE', '300274.XSHE']
    g.hold_count = 5
    run_daily(trade_func, 'open') 

def trade_func(context):
    # 整合日期
    days = get_trade_days(end_date=context.current_dt.date(), count=5)
    yesterday = days[-2]
    before_yesterday = days[-3]

    for stock in context.portfolio.positions.keys():
        # 判断是否有卖出信号 
        re_value = is_sell(stock, yesterday, before_yesterday, g.ma_min,g.ma_med,g.ma_max)
        # 判断是否触发止损信号
        re_loss = is_loss(stock, yesterday, g.ma_min,g.ma_med,g.ma_max)

        if re_value or re_loss:
            log.info('卖出信号成立',stock)
            
            order_target(stock, 0)
    
    for stock in g.stokcs_pool:
        # 判断是否有买入信号
        re_value = is_buy(stock, yesterday, before_yesterday, g.ma_min,g.ma_med,g.ma_max)

        if re_value:
            if stock in context.portfolio.positions.keys():
                continue
            log.info('买入信号成立',stock)
            
            if g.hold_count <= len(context.portfolio.positions):
                break
            buy_count = g.hold_count - len(context.portfolio.positions)
            cash = context.portfolio.available_cash/(buy_count*1.5)
            order_value(stock, cash)


def after_trading_end(context):
    log.info('='*50)

# 获取ma值
def get_ma(stock, ma_value, end_dt):
    price = get_price(security=stock, 
                      end_date=end_dt, 
                      frequency='daily', 
                      fields=['close'], 
                      skip_paused=False, 
                      fq='pre', 
                      count=ma_value+10)['close']
    ma = price[-ma_value:].mean()
    return ma

# 获取ema值
def get_ema(stock, ma_value, end_dt):
    ema = EMA(stock, check_date=end_dt, timeperiod=ma_value)
    return ema[stock]

# 判断是否出现买入信息
def is_buy(stock, yesterday, before_yesterday, *ema):
    ma_min = ema[0]
    ma_med = ema[1]
    ma_max = ema[2]
    
    # 求出上一个交易日的ma_min，ma_med,ma_max的值
    y_ma_min_value = get_ema(stock, ma_min, yesterday)
    y_ma_med_value = get_ema(stock, ma_med, yesterday)
    y_ma_max_value = get_ema(stock, ma_max, yesterday)

    # 求出上上个交易日的ma_min，ma_med,ma_max的值
    by_ma_min_value = get_ema(stock, ma_min, before_yesterday)
    by_ma_med_value = get_ema(stock, ma_med, before_yesterday)
    by_ma_max_value = get_ema(stock, ma_max, before_yesterday)

    if (y_ma_min_value > y_ma_max_value) and (by_ma_min_value < by_ma_max_value) and (y_ma_med_value < y_ma_max_value):
        return True
    else:
        return False
    
# 判断是否有卖出信息
def is_sell(stock, yesterday, before_yesterday, *ema):
    ma_min = ema[0]
    ma_med = ema[1]
    ma_max = ema[2]
    
    # 求出上一个交易日的ma_min，ma_med,ma_max的值
    y_ma_min_value = get_ema(stock, ma_min, yesterday)
    y_ma_med_value = get_ema(stock, ma_med, yesterday)
    y_ma_max_value = get_ema(stock, ma_max, yesterday)

    # 求出上上个交易日的ma_min，ma_med,ma_max的值
    by_ma_min_value = get_ema(stock, ma_min, before_yesterday)
    by_ma_med_value = get_ema(stock, ma_med, before_yesterday)
    by_ma_max_value = get_ema(stock, ma_max, before_yesterday)

    if (y_ma_min_value > y_ma_med_value) and (by_ma_min_value < by_ma_med_value) and (y_ma_med_value > y_ma_max_value):
        return True
    else:
        return False
        
        
# 判断是否有止损信息
def is_loss(stock, yesterday, *ema):
    ma_min = ema[0]
    ma_med = ema[1]
    ma_max = ema[2]
    
    # 昨日收盘价
    close = get_price(security=stock, 
                          end_date=yesterday,
                          frequency='daily', 
                          fields=['open','close'], 
                          skip_paused=False, 
                          fq='pre', 
                          count=10)['close'][-1] 
    
    
    # 求出上一个交易日的ma_min，ma_med,ma_max的值
    y_ma_min_value = get_ema(stock, ma_min, yesterday)
    y_ma_med_value = get_ema(stock, ma_med, yesterday)
    y_ma_max_value = get_ema(stock, ma_max, yesterday)
    
    if (close < y_ma_med_value) and (y_ma_med_value < y_ma_max_value):
        return True
    else:
        return False

    