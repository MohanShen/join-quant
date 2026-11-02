# Clone from JoinQuant
# postId: e7e1b4f4ddf140db5194f07ed7a2f92d
# backtestId: c0f9879c11a57128c33060fd6160524d
# title: 基金回测出现的问题，出现两次赎回

# 导入函数库
import jqdata
import math
import talib
import numpy as np
from functools import reduce
import time
import itertools
import logging
# 初始化函数，设定基准等等
def initialize(context):
    #基准指数E
    g.benchmark_index = '399394.XSHE'  #399394    399997.XSHE   000990
    # 要操作的股票：（g.为全局变量）
    g.buy = '160219.OF'         #160219 005176 000879 161725  110022
    set_benchmark(g.benchmark_index)
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 输出内容到日志 lo1g.info()
    log.debug('指数：%s，名称：%s'%(g.benchmark_index , get_security_info(g.benchmark_index).display_name))
    log.debug("基金代码：%s，基金名称：%s"%(g.buy , get_fund_info(g.buy)['fund_name']))
    log.debug("------------------------------------------------------")
    # 过滤掉order系列API产生的比error级别低的log
    log.set_level('order', 'error')
    ### 基金费率设定 ### 买入=0.0012  卖出=0.005
    set_order_cost(OrderCost(open_commission=0.0012, close_commission=0.005, min_commission=0),type='stock_fund')
    # 初始化场外基金仓位
    set_subportfolios([SubPortfolioConfig(context.portfolio.cash, 'open_fund')])
    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
    # 买入卖出操作
    run_daily(market_open, time='14:45')
    #提前发微信提醒，不做买卖
    run_daily(market_msg, time='14:45')
    # 收盘后运行
    run_daily(after_market_close, time='after_close')
    g.closebuy=0    #买入收盘价
    g.closesell=0   #卖出收盘价
    g.mdate1=0      #买入日期
    g.mdate2=0      #卖出日期
    #可修改变量
    g.zhang=0.06    #涨幅
    g.die=-0.05     #跌幅
    g.bl1=1         #发散变量
    g.bl2=2         #收敛变量
    g.blday=5      #MA5持续上涨
# 开盘时运行函数
def market_open(context):
    #持有份额
    Nowfene=context.portfolio.positions[g.buy].sellable_amount
    #持有金额
    available_cash = context.portfolio.available_cash
    ##########################     策略    ############################     
    #计算执行时间
    stock =g.benchmark_index
    date=context.current_dt
    log.debug(date)
    #log.debug("指数:%s"%stock)
    dif,dea,macd = MACD(context,stock)
    MA5=MA(context,60,5,stock)
    MA10=MA(context,60,10,stock)
    MA20=MA(context,60,20,stock)
    MA30=MA(context,60,30,stock)
    MA60=MA(context,60,60,stock)
    MA120=MA(context,60,120,stock)
    '''============================================================================策略============================================================================'''    
    #买
    #dif发散
    if abs(macd[-1])>20 and abs(macd[-2])>20 and abs(macd[-3])>20 and macd[-1]>0 and MA5[-1]>MA60[-1]:
        if MAdivergence(dif,g.bl1):
            if available_cash!=0:
                g.mdate1=context.current_dt
                g.closebuy = attribute_history(g.benchmark_index, 5, '1d', 'close')
                g.closebuy=g.closebuy['close'][-1]
                txt = g.buy
                log.debug('macd买入： %s' % txt)
                #申购基金
                purchase(g.buy, available_cash, pindex=0)
                '''
    if abs(macd[-1])>20 and abs(macd[-2])>20 and abs(macd[-3])>20   :
        if MAbuy(MA5,g.blday):
            if available_cash!=0:
                g.mdate1=context.current_dt
                g.closebuy = attribute_history(g.benchmark_index, 5, '1d', 'close')
                g.closebuy=g.closebuy['close'][-1]
                txt = g.buy
                log.debug('买入： %s' % txt)
                #申购基金
                purchase(g.buy, available_cash, pindex=0)

'''
    #dif收敛
    #if abs(macd[-1])<20 and abs(macd[-2])<20 and abs(macd[-3])<20 and abs(macd[-4])<20:
    if MAconvergence(dif,dea,g.bl2):
        if Nowfene!=0:
            g.mdate2=context.current_dt
            log.info(len(jqdata.get_trade_days(start_date=g.mdate1, end_date=g.mdate2)))
            x=len(jqdata.get_trade_days(start_date=g.mdate1, end_date=g.mdate2))
            if x>7:
                txt = g.buy
                log.debug('macd卖出： %s' % txt)
                #赎回基金
                redeem(g.buy, Nowfene,pindex=0)

    closesell=attribute_history(g.benchmark_index, 1, '1d', ['close'])
    closesell=closesell['close'][-1]
    a=(closesell-g.closebuy)/g.closebuy
    if a<g.die:
        if Nowfene!=0:
            txt = g.buy
            log.debug('跌幅百分之5卖出:%s' % txt)
            #赎回基金
            redeem(g.buy, Nowfene,pindex=0)
    if a>g.zhang:
        if Nowfene!=0:
            txt = g.buy
            log.debug('涨幅百分之9卖出: %s' % txt)
            #赎回基金
            redeem(g.buy, Nowfene,pindex=0)
    if abs(macd[-1])<20 and abs(macd[-2])<20 and abs(macd[-3])<20:
        if Nowfene!=0:
            g.mdate2=context.current_dt
            log.info(len(jqdata.get_trade_days(start_date=g.mdate1, end_date=g.mdate2)))
            x=len(jqdata.get_trade_days(start_date=g.mdate1, end_date=g.mdate2))
            txt = g.buy
            log.debug('abs卖出： %s' % txt)
            #赎回基金
            redeem(g.buy, Nowfene,pindex=0)
            '''
    if MA5[-1]<MA10[-1]:
        if Nowfene!=0:
            g.mdate2=context.current_dt
            log.info(len(jqdata.get_trade_days(start_date=g.mdate1, end_date=g.mdate2)))
            x=len(jqdata.get_trade_days(start_date=g.mdate1, end_date=g.mdate2))
            txt = g.buy
            log.debug('abs卖出： %s' % txt)
            #赎回基金
            redeem(g.buy, Nowfene,pindex=0)
   '''
    #清仓计算收益
    if date =='2018-12-30':
        if Nowfene!=0:
        #赎回基金
            redeem(g.buy, Nowfene,pindex=0)
            log.debug("清仓")
    log.debug('指数：%s，名称：%s'%(g.benchmark_index , get_security_info(g.benchmark_index).display_name))
    log.debug("基金代码：%s，基金名称：%s"%(g.buy , get_fund_info(g.buy)['fund_name']))
    '''==========================================================================================================================================================='''
def market_msg(context):
    send_message('指数：%s，名称：%s，对应基金：%s,'%(g.benchmark_index , get_security_info(g.benchmark_index).display_name , g.buy))
    # 收盘后运行函数  
def after_market_close(context):
    # 获取账户的持仓价值
    positions_value = context.portfolio.positions_value
    available_cash = context.portfolio.available_cash
    returns = context.portfolio.returns / 100    
    log.debug("当前持仓: %.2f，账户余额：%.2f，总权益的累计收益率：%.2f" %(positions_value , available_cash , returns))
    log.debug("------------------------------------------------------")
############################         自定义函数         ############################
def MAbuy(MA5,day):
    MA55 = MA5[-1]
    rising = True
    temp = -1
    for i in range(day):
        MA55 = MA5[temp]
        MA55pre = MA5[temp-1]
        if MA55 <MA55pre:
            rising = False
        temp = temp- 1
    #log.info('发散:%s'%rising)
    return rising
    
'''
功能：计算MACD
'''
def MACD(context,stock):
    short_period = 12
    long_period = 26
    mid_period = 9
    his_close = attribute_history(stock,233,'1d','close',fq='pre')
    close = np.array(his_close)
    c = list(itertools.chain.from_iterable(close))
    close = np.array(c) 
    short_ema = talib.EMA(close, short_period)
    long_ema = talib.EMA(close, long_period)
    dif = short_ema - long_ema
    dea = talib.EMA(dif, mid_period)
    macd = (dif - dea) * 2
    return dif,dea,macd
    
'''
'''
#MA收敛：快线（上方）和慢线（下方）连续day天递减（包括不变）但今天没有交叉，或者今天已经交叉；
'''
def MAconvergence(dif,day):
    diff = dif[-1]
    #if diff <= 0:
    #    return True #今天已经交叉
    #else:
    temp = -1
    for i in range(day):
        diff = dif[temp]
        diffpre = dif[temp-1]
        if diff > diffpre:
            rising = False
        temp = temp- 1
    #log.info('收敛:%s'%rising)
    rising = True
    return rising
'''
#MA发散：快线（上方）和慢线（下方）连续day天递增（包括不变）
  
def MAdivergence(dif,day):
    diff = dif[-1]
    #if diff <= 0:
    #    return False #快线在下方
    #else:
    rising = True
    temp = -1
    for i in range(day):
        diff = dif[temp]
        diffpre = dif[temp-1]
        if diff < diffpre:
            rising = False
        temp = temp- 1
    #log.info('发散:%s'%rising)
    return rising

#连续dif>dea  x天买   发散
'''
def MAdivergence(dif,dea,macd,day):
    temp=-1
    for i in range(day):
        diff = dif[temp]    #记录当天dif
        deaa = dea[temp]    #dea
        macdd=macd[temp]
        macddpre=macd[temp-1]
        diffpre = dif[temp-1]   #前一天dif
        #deaapre = dea[temp-1]      
        if diff>deaa and macdd>macddpre>0:  #如果当天dif>dea且dif>前一天dif macd上涨
            rising = True               #真
        else:
            rising = False              #否则假
        temp=temp-1
    return rising
'''
#连续dif<dea  x天卖     收敛
def MAconvergence(dif,dea,day):
    temp=-1
    for i in range(day):
        diff = dif[temp]
        deaa = dea[temp]
        diffpre = dif[temp-1]
        #deaapre = dea[temp-1]
        if diff<deaa: #and diffpre>deaapre:
            rising = True
        else:
            rising = False
        temp=temp-1
    return rising

'''
MA数组
'''
def MA(context,day,ma,stock):
    his_close = attribute_history(stock,day+ma-1, '1d', 'close', fq='pre')
    
    #log.info("前X天收盘价:%s"%his_close)
    close = np.array(his_close)  
    #log.info(close)
    #转换一维数组
    c = list(itertools.chain.from_iterable(close))
    close = np.array(c) 
    #log.info(c)
    arr_ma= talib.MA(close, ma)    #log.info(arr_ma)
    return arr_ma[ma-1:]
