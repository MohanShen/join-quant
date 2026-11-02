# Clone from JoinQuant
# postId: 4720155708a8afedaa2d62ddbe9eac92
# backtestId: 539b3f42c8b55663bef142508434ac98
# title: PE-百分位策略网格化投资

# 克隆自聚宽文章：https://www.joinquant.com/post/27243
# 标题：PE百分位策略
# 作者：知识之妖

# 导入函数库
from jqdata import *
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, date, timedelta
import copy


'''
自行设置标的，指数，基准，指数表的开始和结束时间（在initset()中）
'''
# 初始化函数，设定基准等等
def initialize(context):
    # 基准
    set_benchmark('000905.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')
    # 选择标的
    g.security = '159922.XSHE'
    #指数选择
    g.index='000905.XSHG'
    #初始化PE表等参数
    initset()
    curdate=context.current_dt
    g.perlist=getpercent(g.s.date(),curdate.date())
    #prvent exception
    g.prepe=0
    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    
    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
      # 开盘前运行
    run_daily(before_market_open, time='before_open', reference_security=g.security)
      # 开盘时运行
    #run_daily(market_open, time='open', reference_security='000300.XSHG')
      # 收盘后运行
    #run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')
    # 每月开盘前运行
    run_monthly(updatelist, 2, time='after_close')
    
## 开盘前运行函数
def before_market_open(context):
    # 输出运行时间
    #log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))
    
    # 给微信发送消息（添加模拟交易，并绑定微信生效）
    # send_message('美好的一天~')
    #g.security = '160706.XSHE'
    predate=context.previous_date
    prepe=g.petable.loc[predate]['pe_ratio']
    if(prepe<=g.perlist[3]):
        cash = context.portfolio.available_cash
        order_value(g.security, cash)
        print(predate)
        print('prepe', prepe)
        print('buy', prepe, g.perlist)
    if(prepe>=g.perlist[7]):
        order_target_value(g.security,0)
        print(predate)
        print('prepe', prepe)
        print('sell', prepe, g.perlist)
    if(prepe>=g.perlist[6]):
        print(predate)
        print('prepe', prepe)
        print('sell', prepe, g.perlist)
    record(
        PE=prepe, 
        高估=g.perlist[7], 
        低估=g.perlist[3], 
    )

        

## 开盘时运行函数

## 收盘后运行函数
def after_market_close(context):
    return
    
#初始，结束指数时间需要自己设置
def initset():
    g.s=datetime(2007,2,1)
    g.e=datetime(2020,5,2)
    g.petable=get_index_history_pepb(g.index,g.s.date(),g.e.date(),1,1)
    log.set_level('order', 'error') # 过滤掉order系列API产生的比error级别低的log
    print(g.petable)
    

'''
获取任意指数一段时间的历史 pe 和 pb 估值列表，通过计算当前的估值在历史估值的百分位，来判断当前市场的估值高低。由于加权方式可能不同，可能各个指数公开的估值数据有差异，但用于判断估值相对高低没有问题

输入：
    indexCode:  要查询指数的代码
    begin:    查询开始时间，格式为'yyyy-MM-dd'
    end:    查询结束时间，格式为'yyyy-MM-dd'
    interval: 计算指数估值的间隔天数，增加间隔时间可提高计算性能
    indexType: 1为等权重方式计算，0为按市值加权计算
输出：
    result:  指数历史估值的 DataFrame，index 为时间，列为pe_ratio（市盈率）， pb_ratio（市净率）
'''
def get_index_history_pepb(indexCode,begin,end,interval=5,indexType=1):

    all_days=get_all_trade_days()

    ratios=[]
    days=[]
    pbs=[]

    i=0
    for day in all_days:
        if(day<=begin or day>=end):
            continue
        
        i=i+1
        
#         print i%interval
        if(i%interval!=0):
            continue
            
        stocks = get_index_stocks(indexCode,day)
        q = query(
            valuation.pe_ratio,valuation.pb_ratio,valuation.circulating_market_cap
        ).filter(
            valuation.code.in_(stocks)
        )

        df=get_fundamentals(q,day)
        
        df=df[df['pe_ratio']>0]
        
        if(indexType==0):
            pe_ratio=df['circulating_market_cap'].sum()/(df['circulating_market_cap']/df['pe_ratio']).sum()
            pb_ratio=df['circulating_market_cap'].sum()/(df['circulating_market_cap']/df['pb_ratio']).sum()
        else:
            pe_ratio=df['pe_ratio'].size/(1/df['pe_ratio']).sum()
            pb_ratio=df['pb_ratio'].size/(1/df['pb_ratio']).sum()
        ratios.append(pe_ratio)
        pbs.append(pb_ratio)
        days.append(day)

    result=pd.DataFrame({'pe_ratio':ratios,'pb_ratio':pbs},index=days)
    
    return result


#10年PE百分位，若指数历史小于10年，则为历史百分位
def getpercent(start,end):
    if(end.replace(year=end.year-10)>start):
        start=end.replace(year=end.year-10)
    print('end',end)
    print('start',start)
    te=g.petable[start:end]
    out=copy.deepcopy(te['pe_ratio'].values)
    out.sort()
    temper=[]
    for i in range(11):
        ind=int((i/10)*(len(out)-1))
        temper.append(out[ind])
    return temper
#PE百分位每月更新
def updatelist(context):
    curdate=context.current_dt
    g.perlist=getpercent(g.s.date(),curdate.date())

