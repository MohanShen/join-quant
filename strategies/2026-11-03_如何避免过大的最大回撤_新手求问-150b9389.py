# Clone from JoinQuant
# postId: 150b9389c8c7b055ba917e127e443133
# backtestId: 0c4d4bbb902de8072342ccd677338ad1
# title: 如何避免过大的最大回撤（新手求问）

# 克隆自聚宽文章：https://www.joinquant.com/post/258
# 标题：量化投资学习——行业龙头股均线（收益率填坑优化版）
# 作者：冰柠檬

#股票池需要如下：
#沪深300池，
#当前不停牌的股票池，
#有历史数据的股票池,
#两者的交集得到可用股票池
#持仓股票池
#可用股票池中剔除持仓股票得到的股票池（可以进行买入操作的股票池）
#将要买入的股票池：即上述股票池中发出买入信号得到的股票池
#将要卖出的股票池：持仓股票池中，没有停牌的，发出卖出信号的股票池
enable_profile()
import random
import numpy as np
import pandas as pd
from pandas import Series,DataFrame
import scipy.stats as stats
import math
def initialize(context):
    #初始化沪深300
    # g.stocks_ttl = get_index_stocks('000300.XSHG')
    # scu0 = get_index_stocks('000001.XSHG')
    # scu3 = get_index_stocks('399001.XSHE')
    # scu = scu0+scu3
    # df = get_fundamentals(query(
    #     valuation.code,valuation.market_cap
    # ).filter(
    #     valuation.code.in_(scu)
    # ).order_by(
    #     valuation.market_cap.desc()
    # ).limit(20),
    # ).dropna()

    # g.stocks_ttl = list(df.code)
    # set_benchmark('000300.XSHG')
    # g.stocks_ttl = ['000651.XSHE','601318.XSHG','000012.XSHE','002299.XSHE','600150.XSHG','600027.XSHG','600900.XSHG'
    #                 ,'600406.XSHG','600151.XSHG','002241.XSHE','000563.XSHE','000002.XSHE','601668.XSHG','002269.XSHE'
    #                 ,'600019.XSHG','600089.XSHG','600362.XSHG','002005.XSHE','600115.XSHG','601866.XSHG','600352.XSHG'
    #                 ,'600004.XSHG','601186.XSHG','002415.XSHE','002489.XSHE','002340.XSHE','601088.XSHG','000581.XSHE','000625.XSHE'
    #                 ,'600917.XSHG','600415.XSHG','600196.XSHG','600256.XSHG','600887.XSHG','600585.XSHG','601006.XSHG','000063.XSHE'
    #                 ,'300027.XSHE','600456.XSHG','600511.XSHG','600036.XSHG','600519.XSHG','600663.XSHG','600030.XSHG','000538.XSHE'
    #                 ,'600108.XSHG','600655.XSHG']
                    
    # set_universe(g.stocks_ttl)

    # set_order_cost(OrderCost(open_tax=0, close_tax=0.001, \
    #                          open_commission=0.0005, close_commission=0.00013,\
    #                          close_today_commission=0, min_commission=5), type='stock')
    # #g.stocks_ttl = []
    # stocks = get_industry_stocks('801780')

    #初始化可用股票池(不停牌的股票池)
    g.stocks_trading=[]
    #初始化有历史数据的股票池
    g.stocks_hist=[]
    #初始化持仓股票池
    g.stocks_hold=[]
    #初始化备选股票池
    g.stocks_toChoose=[]
    #将要买入的股票池
    g.stocks_toBuy=[]
    #将要卖出的股票池
    g.stocks_toSell=[]
    #长短均线的间隔
    g.total_return = []
    g.shortMA=10
    g.longMA=60
    #持仓持有股票数量的最大上限
    g.numHoldmax=30
    # 坑满时每次调仓量
    g.num_of_change=15
    #设置计算几日收益率
    g.period=10
    #调仓率
    g.change = 5
    #计时器
    g.days = 0
    
    g.week = 1
    
    #计算低波的时间段与拿在手中的天数
    g.var_days = 30
    g.volume_days = 30
    
    run_weekly(before_market_open,1,time='before_open')
    run_weekly(trade,1, time='open')
    run_weekly(after_market_close,1, time='after_close')

def choose_stocks():
    stocks = get_index_stocks('000001.XSHG')
    stockVol = history(g.volume_days, '1d', 'volume', stocks)
    #stocks_up = mean(stockVol).sort_values(ascending=False).index[:100]
    #stocks_down = mean(stockVol).sort_values(ascending=True).index[:20]
    #stockVol = stockVol[stocks_up]
    g.stocks_ttl = []
 
    stockVol.dropna(axis=0,how='any',thresh=None)
    a1=np.array(stockVol.iloc[0])
    a2=np.array(stockVol.iloc[g.volume_days-1])
    stocks_volume=DataFrame(a2/a1,columns=['volume'],index=stockVol.columns)
    stocks_volume = stocks_volume.sort_values(by='volume',ascending=False)
    g.stocks_ttl = stocks_volume.index[:100]

    set_universe(g.stocks_ttl)

    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, \
                             open_commission=0.0005, close_commission=0.00013,\
                             close_today_commission=0, min_commission=5), type='stock')
    
def before_market_open(context):
    #得到当前的可用的股票池
    #调仓频率

    g.run_today = g.days % g.change == 0
    if g.run_today:
        choose_stocks()
        current_data = get_current_data(g.stocks_ttl)
        g.stocks_trading=[]
        #得到有历史数据的股票池，并且得到有历史数据
        operate_buy={}
        g.stocks_hist=[]
        for stock in g.stocks_ttl:
            #得到当前的不停牌股票
            if not current_data[stock].paused:
                hdict = attribute_history(stock,g.longMA+1, '1d', ('close'),skip_paused=True)
                #取出有历史数据的股票
                temp_hist = np.array([x for x in hdict.close if str(x) != 'nan'])
                if len(temp_hist)>=g.longMA:
                    g.stocks_hist.append(stock)
                    signal=cal_signal(temp_hist)
                    operate_buy.update({stock:signal})
    
        #根据信号，得到最后的备选池
        for stock in g.stocks_hist:
            if operate_buy[stock]==1 and stock not in g.stocks_hold:
                g.stocks_toBuy.append(stock)
            elif operate_buy[stock] ==-1 and stock in g.stocks_hold:
                    g.stocks_toSell.append(stock)
                
        for stock in context.portfolio.positions.keys():
            flag = stop_code(stock,context)
            if flag and stock not in g.stocks_toSell:
                g.stocks_toSell.append(stock)
#Input: 某只股票历史数据
#Output: 判断是否买入的信号：数字1:买入，-1卖出，0表示不变
def cal_signal(data_withHist):
    MA_shortYesterday=calMA(data_withHist,g.shortMA)
    MA_shortBeforeYesterday=calMA(data_withHist[:-1],g.shortMA)
    MA_longYesterday=calMA(data_withHist,g.longMA)
    MA_longBeforeYesterday=calMA(data_withHist[:-1],g.longMA)
    signal=0
    if MA_shortBeforeYesterday<MA_longBeforeYesterday and MA_shortYesterday>MA_longYesterday:
        signal=1 
    elif MA_shortYesterday<MA_longYesterday:
        signal=-1
    return signal
    
#计算均值
def calMA(data_withHist,num):
    ma=data_withHist[-1*num:].mean()
    return ma
    
 
#计算股票list里近N日的收益率
def calreturn(stocklist):
    #取出每只股票period天的收盘价格
    stocks_info=history(g.period,'1d','close',security_list=stocklist)
    stocks_info_var=history(g.var_days,'1d','close',security_list=stocklist)
    stocks_info.dropna(axis=0,how='any',thresh=None)
    a1=np.array(stocks_info.iloc[0])
    a2=np.array(stocks_info.iloc[g.period-1])
    stocks_return=DataFrame(a2/a1,columns=['return'],index=stocks_info.columns)
    stocks_var = DataFrame(np.array(stocks_info_var.var()),columns=['var'],index=stocks_info_var.columns)
    stocks_return = stocks_return.sort_values(by='return',ascending=False)
    stocks_var = stocks_var.sort_values(by='var',ascending=True)
    stocks_score = stocks_var['var'].rank()+stocks_return['return'].rank(ascending=False)
    stocks_score = stocks_score.to_frame()
    stocks_score.columns = ['score']
    stocks_score = stocks_score.sort_values(by='score',ascending=True)
    return stocks_return   


    
def trade(context):
    #首先卖出持仓中该卖出的股票
    if g.run_today:
        g.run_today = False
        flag = stop(context)
        if flag:
            sell_all(context)
        else:
            for stock in g.stocks_toSell:
                order_target(stock,0)
            g.stocks_hold=list(set(g.stocks_hold).difference(set(g.stocks_toSell)))
            #g.stocks_hold = []
            # 计算还剩下的坑位
            num_canBuy=g.numHoldmax-len(g.stocks_hold)
            # log.info(num_canBuy)
            
            # log.info(g.stocks_toBuy)
            # 如果坑满了，剔除坑中持有的一部分收益不好的股票，买入备选池中收益率较好的股票
            if num_canBuy == 0 and len(g.stocks_toBuy)>0:
                stocks_holdreturnup=calreturn(g.stocks_hold)
                stocks_tobuyreturnup=calreturn(g.stocks_toBuy)
                for i in range(0,min(len(g.stocks_toBuy),g.num_of_change)):
                    order_target(stocks_holdreturnup.index[i],0)
                    g.stocks_hold.remove(stocks_holdreturnup.index[i])
                num_canBuy=g.numHoldmax-len(g.stocks_hold)
                cash_perShare=context.portfolio.cash/num_canBuy
                for i in range(0,num_canBuy):
                    order_target_value(stocks_tobuyreturnup.index[len(stocks_tobuyreturnup)-i-1],cash_perShare)
            
            # 如果坑没满
            elif num_canBuy>0:
                
                #如果备选股票池中的股票数量小于可买的股票，则全部买入
                if len(g.stocks_toBuy)<=num_canBuy:
                    if len(g.stocks_toBuy)==0:
                        cash_perShare=context.portfolio.cash/num_canBuy
                    else:
                        cash_perShare=context.portfolio.cash/len(g.stocks_toBuy)
                    for i in range(0,len(g.stocks_toBuy)):
                        # log.info('here')
                        # log.info(g.stocks_toBuy[i])
                        # log.info(cash_perShare)
                        order_target_value(g.stocks_toBuy[i],cash_perShare)
            
                #如果备选池的股票大于可买数量，则按照收益率买入
                elif len(g.stocks_toBuy)>num_canBuy:
                    stocks_tobuyreturnup=calreturn(g.stocks_toBuy)
                    cash_perShare=context.portfolio.cash/num_canBuy
                    for i in range (0,num_canBuy):
                         order_target_value(stocks_tobuyreturnup.index[len(stocks_tobuyreturnup)-i-1],cash_perShare)
                        #成功下单完了以后更新g.stocks_hold
            
        
        
#5.2 大盘止损
def stop(context):
    # 大盘指数前130日内最高价超过最低价2倍，则清仓止损
    # 基于历史数据判定，因此若状态满足，则当天都不会变化
    # 增加此止损，回撤降低，收益降低
    
    flag = False
    index = '000300.XSHG'

    h = attribute_history(index, 7, unit='1d', fields=('close', 'high', 'low'), skip_paused=True)
    #h = attribute_history(index, 14, unit='1d', fields=('close', 'high', 'low'), skip_paused=True)

    low_price = h.low.min()
    high_price = h.high.max()
    if 0.92*high_price > h.close[-1]:
        # 当日第一次输出日志
        #log.info("==> 大盘止损，%s指数前130日内最高价超过最低价2倍, 最高价: %f, 最低价: %f" %(get_security_info(index).display_name, high_price, low_price))
        flag = True
    # elif len(g.total_return)>0 and context.portfolio.total_value<0.92*np.max(g.total_return):
    #     g.total_return = []
    #     flag = True
    else:
        flag = False
    
    return flag


def stop_code(index, context):
    flag = False
    h = attribute_history(index, 7, unit='1d', fields=('close', 'high', 'low'), skip_paused=True)
    low_price = h.low.min()
    high_price = h.high.max()
    if 1.3*low_price < h.close[-1] or 0.88*high_price > h.close[-1]:
        # 当日第一次输出日志
        #log.info("==> 大盘止损，%s指数前130日内最高价超过最低价2倍, 最高价: %f, 最低价: %f" %(get_security_info(index).display_name, high_price, low_price))
        flag = True
    else:
        flag = False
    
    return flag




def sell_all(context):
        hold_stock_list = context.portfolio.positions.keys()
        for code in hold_stock_list:
            order_target(code, 0)
            g.stocks_hold = []
    #记录一下实际持仓：
    
    
def after_market_close(context):
    g.stocks_hold=list(context.portfolio.positions.keys())
    g.stocks_trading=[]
    #初始化有历史数据的股票池
    g.stocks_hist=[]
    #初始化持仓股票池
    g.stocks_toChoose=[]
    #将要买入的股票池
    g.stocks_toBuy=[]
    #将要卖出的股票池
    g.stocks_toSell=[]
    
    # g.total_return.append(context.portfolio.total_value)
    g.days +=1
    