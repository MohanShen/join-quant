# Clone from JoinQuant
# postId: 10462767a29759cef45c042d9e6c9a9b
# backtestId: 106b55943f3f5c14f570f08d1687361a
# title: 有几个关键语句写不出来

import jqdata
import numpy as np
import pandas as pd
import talib
import datetime
from jqlib.technical_analysis import *
from kuanke.wizard import *

# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')
    
    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    g.stocklist=[]
    g.limit = 5 #最大持仓5个股票
    run_daily(market_init, time='before_open', reference_security='000300.XSHG') 
    run_daily(market_open, time='9:30', reference_security='000300.XSHG')
    run_daily(market_close, time='15:00', reference_security='000300.XSHG')

    
def market_init(context):
    #选股    
    df = get_fundamentals(query(valuation.code,valuation.circulating_market_cap).filter(valuation.circulating_market_cap>120).limit(300), date=context.current_dt)
    g.stocklist = df['code'].tolist()
    g.stocklist = paused_filter(g.stocklist)
    g.stocklist = st_filter(g.stocklist)
    for security in context.portfolio.positions.keys():
        g.stocklist.append(security)
    
# 过滤停牌、ST股
def paused_filter(security_list):
    current_data = get_current_data()
    security_list = [stock for stock in security_list if not current_data[stock].paused]
    return security_list
def st_filter(security_list):
    current_data = get_current_data()
    security_list = [stock for stock in security_list if not current_data[stock].is_st]
    return security_list

## 开盘时运行函数
def market_open(context):
    # log.info('函数运行时间(market_open):'+str(context.current_dt.time()))
    buy_list = []
    sell_list = []
    #卖出
    for security in context.portfolio.positions.keys():
        #ma1 死叉 ma20 或者 持有超过5天
        sec_obj = context.portfolio.positions[security]
        minus = (context.current_dt - sec_obj.init_time)
        days = int(minus.days)
        if days>11:
            sell_list.append(security)
        #止损 跌幅超过5%
        returns = round(((sec_obj.price-sec_obj.avg_cost)/sec_obj.avg_cost)*100,2)
        if returns<=-8:
            sell_list.append(security)
            break
        max = recent_high_price(security)
        #止盈
        if returns>9 and ((max-sec_obj.price)/sec_obj.price)*100<=3:
            #涨幅超过10%后回撤3% 计算最高回撤，先获取最近3天最高价格
            sell_list.append(security)
    
    #买入
    #MA1 金叉 ma5 ,ma1 金叉 ma20 ma5 金叉 ma20
    for security in g.stocklist:
        if security not in context.portfolio.positions \
        and MA_judge_jincha(security, 9, 45) \
        and MA_MONEY_judge_duotou(security, 4, 49):
            # 当日成交量放大，前一交易日上涨（1-3%），当日未涨停
            data_pre = attribute_history(security,count=3,unit='1d', \
                        fields=['open', 'close', 'high', 'low', 'volume', 'money'])
            #data_now = attribute_history(security,start_date=context.current_dt,end_date=context.current_dt)
            # print data_pre
            # print data_now
            yesterday_grown = ((data_pre['close'][-1] - data_pre['close'][-2])/data_pre['close'][-2])*100
            yesterday_2_grown = ((data_pre['close'][-2] - data_pre['close'][-3])/data_pre['close'][-3])*100
            vol = data_pre['volume'][-1]>data_pre['volume'][-2]
            if vol and yesterday_grown>0:
                log.info('%s符合买入！'%security)
                buy_list.append(security)
    if len(sell_list)>0:
        for security in sell_list:
            order_target(security, 0)
    if len(buy_list)>0 and len(context.portfolio.positions)<g.limit:
        buy_nums = g.limit-len(context.portfolio.positions)
        if buy_nums>0:
            cash = context.portfolio.available_cash/buy_nums
            for security in buy_list[0:buy_nums]:
                order_value(security, cash)
                
def market_close(context):
    log.info("持仓列表：%s"%context.portfolio.positions.keys())
def recent_high_price(security,n=5):
    h = attribute_history(security,count=n,unit='1d',fields=['close', 'high'])
    return h['high'].max()