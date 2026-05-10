# Clone from JoinQuant
# postId: c64897c86349a1d0fa7f91d1141cb167
# backtestId: e1345bed42ec4e625fd9070592e28691
# title: 【策略研发】三进兵策略（第二版）

"""
版本号：v2.1
本次迭代，添加了自动评估三均线最优组合功能。
这里的最优组合是按近一段时间，收益最大的最优组合为结果。
经过回测，整体比第一个版本提升了4.1%的收益。
后期将计划添加以收益加权最优组合计算均线组合，并添加自动选股功，请期待！

策略说明：
所谓的三进兵，是指三条EMA均线组合的策略
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
    log.info('执行[initialize]函数，时间节点{}'.format(datetime.datetime.now()))

    # 三进兵组合最优计算值
    g.three_ema_dic = {}
    
    # 三进兵的三个值集合
    g.ma_min = [3, 5, 7]
    g.ma_med = [10, 20, 30]
    g.ma_max = [40, 50, 60]

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
    # 交易股票池
    g.stokcs_pool = ['300014.XSHE', '300059.XSHE', '300168.XSHE', '300253.XSHE', '300274.XSHE']
    # 最在持仓量
    g.hold_count = 5
    # 首次计算均线组合
    for stock in g.stokcs_pool:
        emas = calculate(stock, (g.ma_min, g.ma_med, g.ma_max))
        g.three_ema_dic[stock] = emas
    # 交易定时函数
    run_daily(trade_func, 'open') 


def trade_func(context):
    log.info('执行[trade_func]函数，时间节点{}'.format(datetime.datetime.now()))

    # 整合日期
    days = get_trade_days(end_date=context.current_dt.date(), count=5)
    yesterday = days[-2]
    before_yesterday = days[-3]

    for stock in context.portfolio.positions.keys():
        # 判断是否有卖出信号 
        re_value = is_sell(stock, yesterday, before_yesterday, g.three_ema_dic[stock][0], g.three_ema_dic[stock][1], g.three_ema_dic[stock][2])
        # 判断是否触发止损信号
        re_loss = is_loss(stock, yesterday, g.three_ema_dic[stock][0], g.three_ema_dic[stock][1], g.three_ema_dic[stock][2])

        if re_value or re_loss:
            log.info('卖出信号成立',stock)
            order_target(stock, 0)
            # 更新均线组合
            emas = calculate(stock, (g.ma_min, g.ma_med, g.ma_max))
            g.three_ema_dic[stock] = emas
    
    for stock in g.stokcs_pool:

        # 判断是否有买入信号
        re_value = is_buy(stock, yesterday, before_yesterday, g.three_ema_dic[stock][0], g.three_ema_dic[stock][1], g.three_ema_dic[stock][2])

        if re_value:
            if stock in context.portfolio.positions.keys():
                continue
            log.info('买入信号成立：',stock)
            log.info('均线组合：', g.three_ema_dic[stock])
            
            if g.hold_count <= len(context.portfolio.positions):
                break
            buy_count = g.hold_count - len(context.portfolio.positions)
            cash = context.portfolio.available_cash/(buy_count*1.5)
            order_value(stock, cash)


def after_trading_end(context):
    log.info('执行[after_trading_end]函数，时间节点{}'.format(datetime.datetime.now()))

    log.info('='*50)

"""
公用函数
"""
# 获取ma_min值
def get_ma(stock, ma_value, end_dt):
    # log.info('执行[get_ma]函数，时间节点{}'.format(datetime.datetime.now()))

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
    # log.info('执行[get_ema]函数，时间节点{}'.format(datetime.datetime.now()))

    ema = EMA(stock, check_date=end_dt, timeperiod=ma_value)
    return ema[stock]


# 判断是否出现买入信息
def is_buy(stock, yesterday, before_yesterday, *ema):
    # log.info('执行[is_buy]函数，时间节点{}'.format(datetime.datetime.now()))

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
    # log.info('执行[is_sell]函数，时间节点{}'.format(datetime.datetime.now()))

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
    # log.info('执行[is_loss]函数，时间节点{}'.format(datetime.datetime.now()))

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

    
# 过滤掉有止影线和小实体阳线的时刻
def is_high_line(stock, end_dt):
    # log.info('执行[is_high_line]函数，时间节点{}'.format(datetime.datetime.now()))

    price = get_price(security=stock, 
                          end_date=end_dt, 
                          frequency='daily', 
                          fields=['open', 'close', 'high', 'low', 'volume', 'money'], 
                          skip_paused=False, 
                          fq='pre', 
                          count=1)
    open = price['open'][0]
    close = price['close'][0]
    high = price['high'][0]
    low = price['low'][0]

    o_c_ratio = (open-close)/close
    h_c_ratio = (high-close)/close

    if o_c_ratio > 0 and h_c_ratio < 0.02:
        return True
    else:
        return False

"""
历史回测函数
"""
def trade(stock,ma_min,ma_med,ma_max,trade_days):
    # log.info('执行[trade]函数，时间节点{}'.format(datetime.datetime.now()))

    # 记录盈利
    wine_loss_history = []
    # 持仓
    hold_list = {}
    # 权重
    weight = 0
    # 总权重
    last_weihgt = len(trade_days)
    
    # 因为回测的是历史
    for trade_day in trade_days:
        # 权重累加
        weight += 1
        # 将要被使用的日期集合
        the_days = get_trade_days(end_date=trade_day, count=5)
        # 回测当天
        today = the_days[-1]
        # 上一个交易日
        yesterday = the_days[-2]
        # 上上个交易日
        before_yesterday = the_days[-4]

        # ========================卖出操作========================
        sell_list = []
        for stock,info in hold_list.items():
            trade_day = info[0]
            buy_price = info[1]

            # 判断是否有卖出信号 
            re_value = is_sell(stock, yesterday, before_yesterday, ma_min,ma_med,ma_max)
            # 判断是否触发止损信号
            loss = is_loss(stock, yesterday, ma_min,ma_med,ma_max)
            
            # 进行卖出操作
            if re_value or loss:
                sell_list.append(stock)
                price = get_price(security=stock, 
                          end_date=today,  # 现实中成交按当天的开盘价交易
                          frequency='daily', 
                          fields=['open','close'], 
                          skip_paused=False, 
                          fq='pre', 
                          count=10)['open'][-1] 
                
                # 进行记录
                trade_dic = {'stock':stock,
                             'buy_date':trade_day,
                             'buy_price':buy_price,
                             'sell_date':today,
                             'sell_price':price,
                             'ratio':(price-buy_price)/buy_price,
                             'MA':(ma_min,ma_med,ma_max),
                             'weight':weight,
                             'count':last_weihgt}
                wine_loss_history.append(trade_dic)
        
        # 从持仓中删除已经卖出的股票
        for stock in sell_list:
            del hold_list[stock]
        # ========================卖出操作========================

            
        # ========================买入操作========================
        # 判断是否有买入信号
        re_value = is_buy(stock, yesterday, before_yesterday, ma_min,ma_med,ma_max)
        # 如果有买入信号，则买入
        if re_value:
            # 在今天的开盘时买入，参考的买入价格是昨天的收盘价
            price = get_price(security=stock, 
                          end_date=today, # 现实中按当天的开盘价交易 
                          frequency='daily', 
                          fields=['open','close'], 
                          skip_paused=False, 
                          fq='pre', 
                          count=10)['open'][-1]
            hold_list[stock] = [today, price]
        # ========================买入操作========================
    
    #========================将最后一次未卖出的也记录==========================
    if stock in hold_list.keys():
        sell_list.append(stock)
        price = get_price(security=stock, 
                  end_date=today,  # 现实中成交按当天的开盘价交易
                  frequency='daily', 
                  fields=['open','close'], 
                  skip_paused=False, 
                  fq='pre', 
                  count=10)['open'][-1] 

        # 进行记录
        trade_dic = {'stock':stock,
                     'buy_date':trade_day,
                     'buy_price':buy_price,
                     'sell_date':today,
                     'sell_price':price,
                     'ratio':(price-buy_price)/buy_price,
                     'MA':(ma_min,ma_med,ma_max),
                     'weight':weight,
                     'count':last_weihgt}
        wine_loss_history.append(trade_dic)
    #========================将最后一次未卖出的也记录==========================

    # 返回交易记录
    return wine_loss_history
    
"""
计算个股三进兵最优组合
"""
def calculate(stock, emas):
    log.info('执行[calculate]函数，时间节点{}'.format(datetime.datetime.now()))

    # 获取一段时间的交易日期
    days = get_trade_days(end_date=datetime.datetime.now(), count=250)[0:-1]

    # 保存回测记录
    all_list = []

    # 回测不同的三进兵组合 
    for ma1 in emas[0]:
        for ma2 in emas[1]:
            for ma3 in emas[2]:
                # log.info(ma1, ma2, ma3)
                re_dic = trade(stock,ma1,ma2,ma3,days)
                for _dic in re_dic:
                    all_list.append(_dic)
                
    
    # 输出各三进兵组合的值
    df = pd.DataFrame(all_list,columns=['stock', 
                                        'buy_date', 
                                        'buy_price', 
                                        'sell_date', 
                                        'sell_price', 
                                        'ratio', 
                                        'MA', 
                                        'weight', 
                                        'count'])
    group = df.groupby(by=['MA'])

    max_sum = group.sum()
    max_sum = max_sum.sort_index(by=['ratio'],ascending=False).loc[:,['ratio']].head()
    emas = max_sum.index[0]
    
    log.info(stock, emas)
    return emas