# Clone from JoinQuant
# postId: 0c1d00e6c6095f65bf56abb928a13596
# backtestId: dd70690546df83e1dbb0d944df41c5ff
# title: 年化73%银行轮动策略，无未来函数

# 克隆自聚宽文章：https://www.joinquant.com/post/3549
# 标题：银行轮动（中、农、工、商）无止损，年化77%
# 作者：囚徒

import math
import pandas as pd
import numpy as np
import statsmodels.api as sm
import scipy.stats as scs
import scipy.optimize as sco
import talib as tl
from datetime import timedelta

#enable_profile()
#enable_profile()
bank_stocks=['601398.XSHG', # 工行
             '601288.XSHG', # 建行
             '601939.XSHG', # 农行
             '601988.XSHG', # 中行
            #  '601088.XSHG' # 交通银行
            #  '600000.XSHG' # 招商银行
             ]     
# 初始化参数
def initialize(context):
    # 初始化此策略
    # 开启防未来函数
    set_option('avoid_future_data', True)
    # 设置要操作的股票池为空，每天需要不停变化股票池
    set_universe([])
    g.riskbench = '000300.XSHG'
    # set_commission(PerTrade(buy_cost=0.0002, sell_cost=0.00122, min_cost=5)) 
    set_order_cost(OrderCost(close_tax=0.0005, 
    open_commission=0.0001, close_commission=0.0001, min_commission=1), type='stock')  
    # FixedSlippage(0.02)：价差 2 分钱，买卖各加减一半，即单边固定 1 分钱
    set_slippage(FixedSlippage(0.001), type="stock") 
    set_option('use_real_price', True)
    # 设置基准对比为沪深300指数
    
    
    g.inter = 0.004
    
# 每天交易前调用
def before_trading_start(context):
    g.df_last = history(1, unit='1d', field='close', security_list=bank_stocks, df=False, skip_paused=True, fq='pre')
    # 每个交易日重置"当日已换股"标记
    g.swapped_today = False
  
# 每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)调用一次
def handle_data(context, data):

    # 每个交易日最多换股一次：当日已换过就直接跳过，
    # 避免分钟级价格噪声驱动一天内反复买卖
    if g.swapped_today:
        return

    raito = []
    
    for code in bank_stocks:
        # 计算每只银行股的"当日涨跌幅 + 1"：
        #   data[code].close       当前 bar 的收盘价（日频回测下即当日收盘价 / 最新价）
        #   g.df_last[code][-1]    before_trading_start 里 history(1,'1d') 取到的昨日收盘价（前复权）
        # 两者相除 = 今日相对昨收的涨幅，1.0 表示平盘；
        # 下面用四只股票的 ratio 横向比较，买入 ratio 最小（当日最弱）的一只，属于弱势轮动/均值回归思路
        # 注意：日频回测中 data[code].close 取的是当日日线 bar 的收盘价，而 handle_data 在 09:30 就执行，
        #       等于提前知道了当天尾盘价位，属于未来函数；正式使用应改为尾盘 run_daily(..., time='1450') 决策
        raito.append( data[code].close / g.df_last[code][-1] )
        
    min_index = raito.index(min(raito))
    target = bank_stocks[min_index]

    # 只统计真实持仓：清仓后 positions 里可能还留着数量为 0 的旧记录
    positions = context.portfolio.positions
    holding = [code for code in positions if positions[code].total_amount > 0]

    # 空仓：四只银行股涨跌幅分化超过阈值才建仓
    if not holding:
        if max(raito) - min(raito) > g.inter:
            order_target_value(target, context.portfolio.total_value)
            g.swapped_today = True
        return

    # 异常多持仓（历史遗留 / 卖单未完全成交）：策略只应持有一只最弱的，
    # 其余标的凡可卖的一律清掉；清理日不再建仓，避免继续叠加
    if len(holding) > 1:
        for code in holding:
            if code != target and positions[code].closeable_amount > 0:
                order_target(code, 0)
        g.swapped_today = True
        return

    # 正常单持仓：现持仓比最弱者强出阈值才换股
    code = holding[0]
    index = bank_stocks.index(code)
    if raito[index] - min(raito) > g.inter:
        # T+1 保护：当日买入的部分不可卖，卖不掉就不换，避免"卖单没成交却又买入"
        if positions[code].closeable_amount <= 0:
            return
        order_target(code, 0)
        order_target_value(target, context.portfolio.total_value)
        g.swapped_today = True
            
# 每天交易后调用
def after_trading_end(context):
    if bank_stocks[0] in context.portfolio.positions and context.portfolio.positions[bank_stocks[0]].total_amount > 0:
        record(code0=context.portfolio.positions[bank_stocks[0]].total_amount)
    if bank_stocks[1] in context.portfolio.positions and context.portfolio.positions[bank_stocks[1]].total_amount > 0:
        record(code1=context.portfolio.positions[bank_stocks[1]].total_amount)
    if bank_stocks[2] in context.portfolio.positions and context.portfolio.positions[bank_stocks[2]].total_amount > 0:
        record(code2=context.portfolio.positions[bank_stocks[2]].total_amount)
    if bank_stocks[3] in context.portfolio.positions and context.portfolio.positions[bank_stocks[3]].total_amount > 0:
        record(code3=context.portfolio.positions[bank_stocks[3]].total_amount)    