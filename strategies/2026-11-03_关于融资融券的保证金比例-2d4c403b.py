# Clone from JoinQuant
# postId: 2d4c403b822e8f972b724d7e7631e218
# backtestId: 722d770fb9ec61380c11512e1614ad06
# title: 关于融资融券的保证金比例

# 克隆自聚宽文章：https://www.joinquant.com/post/16998
# 标题：【配对交易】基于zscore的配对交易策略（胜率88.2%）
# 作者：Matthew_Zou

# 导入函数库
from datetime import datetime
import pandas as pd
from jqdata import *

# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', False)
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')
    
    set_subportfolios([SubPortfolioConfig(context.portfolio.cash, 'stock_margin')])
    # 设定融资利率: 年化8%, 默认8%
    set_option('margincash_interest_rate', 0.08)
    # 设置融资保证金比率: 150%, 默认100%
    set_option('margincash_margin_rate', 1.0)

    # 设定融券利率: 年化10%, 默认10%
    set_option('marginsec_interest_rate', 0.0)
    # 设定融券保证金比率: 150%, 默认100%
    set_option('marginsec_margin_rate', 0.1)
    
    
    
    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    run_daily(market_open, time='every_bar', reference_security='000300.XSHG')

    g.code1 = '002415.XSHE'
    g.code2 = '000651.XSHE'
    g.window = 60
    g.high = 2
    g.low  = -2
    g.hold = 0
    
    g.zscore_df = pd.Series()
    
## 开盘时运行函数
def market_open(context):
    yesterday = get_the_day(context.current_dt, 1)
    zscore = get_zscore(yesterday)
    g.zscore_df[yesterday] = zscore 
    write_file("zscore.csv", g.zscore_df.to_csv(), append=False)
    zscore_1 = get_zscore(get_the_day(context.current_dt, 2))
    # print(yesterday, zscore)
    record(zscore=zscore)
    record(high=g.high)
    record(low=g.low)
    A = g.code1
    B = g.code2
    
    
    current_data = get_current_data()
    priceA = current_data[A].last_price
    priceB = current_data[B].last_price
    
    if(g.hold != 1 and zscore <= g.low and zscore_1 >= g.low):
        # 股票1超跌或股票2超涨，做多股票1，做空股票2
        if g.code2 in context.subportfolios[0].long_positions.keys():
            order_target_value(g.code2, 0) # 有多先平多
        # 开空仓
        numB = context.portfolio.available_cash/priceB
        marginsec_open(g.code2, numB)
        
        # 有空先平空
        log.info("available_cash(before close short): "+str(context.portfolio.available_cash))
        order_value(g.code1, context.portfolio.available_cash)
        log.info("available_cash: "+str(context.portfolio.available_cash))
        if g.code1 in context.portfolio.short_positions.keys():
            Q = context.subportfolios[0].short_positions[g.code1].closeable_amount
            marginsec_close(g.code1, Q)
        # 开多仓
        print('buy1')
        g.hold = 1
    elif(g.hold != 2 and zscore >= g.high and zscore_1 <= g.high):
        if g.code1 in context.subportfolios[0].long_positions.keys():
            order_target_value(g.code1, 0) # 有多先平多
        # 开空仓
        log.info("available_cash(before open short A): "+str(context.portfolio.available_cash))
        numA = context.portfolio.available_cash/priceA
        marginsec_open(g.code1, numA)
        
        # 有空先平空
        log.info("available_cash(before close short): "+str(context.portfolio.available_cash))
        order_value(g.code2, context.portfolio.available_cash)
        log.info("available_cash: medium: " + str(context.portfolio.available_cash))
        if g.code2 in context.portfolio.short_positions.keys():
            Q = context.subportfolios[0].short_positions[g.code2].closeable_amount
            marginsec_close(g.code2, Q)
        
        log.info("available_cash: "+str(context.portfolio.available_cash))
        print('buy2')
        g.hold = 2

# 计算zscore
# 传入的date应为昨天的日期，而不是今天，防止未来函数
def get_zscore(date):
    price_df = get_price([g.code1, g.code2], end_date=date, count=g.window, fields='close').close
    sub = price_df[g.code1] - price_df[g.code2]
    ma = sub.mean()
    std = sub.std()
    zscore = round((sub[-1] - ma) / std, 4)
    return zscore

def get_the_day(date,T):
    '''输入,当前日期  向前推T天个交易日
      比如date为9月13,前几天无节假日,传入T=1,返回上一个交易日的日期'''
    return get_trade_days(end_date=date,count=T+1)[0]