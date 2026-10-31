# Clone from JoinQuant
# postId: 42b25b31b2c61413e5b98173dac34ef0
# backtestId: 518850599640f9279087d1bde42cef29
# title: 回测中如何避免引入未来函数

# 克隆自聚宽文章：https://www.joinquant.com/post/22220
# 标题：能把沪深300做到30多倍的策略？
# 作者：SOHUSONNY

from jqdata import *
import talib as ta
import pandas as pd
import numpy as np

# 初始化函数，设定基准等等
def initialize(context):
    g.stock='000300.XSHG'
    g.last_stop_loss=list()
    g.stop_loss_blockday=7
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    # 过滤掉order系列API产生的比error级别低的log
    log.set_level('order', 'error')

    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')


    run_daily(make_stoploss, time='open')
    run_daily(make_stoploss, time='10:25')
    run_daily(make_stoploss, time='11:20')
    run_daily(make_stoploss, time='13:55')
    run_daily(make_stoploss, time='14:50')

    run_daily(after_market_close, time='after_close')
    run_daily(choosebuy, time='before_open')

    
def stop_loss(position_list1,n,dt):
    list_stop_loss1 = []
    for code in position_list1:
        #print('stop_loss code:'+code+",   The n is:"+str(n))
        data=get_price(code,end_date=dt,count=80,frequency='60m',fields='close')
        max_close=data.max()[0]
        signal=(data.iloc[-1,0]-max_close)/max_close
        if signal <= -0.02:
            list_stop_loss1.append(code)
    return list_stop_loss1    

def fillingdata(df_tmp_,stockname):
    df_tmp_['ma5']=ta.SMA(df_tmp_['close'],timeperiod=5)
    df_tmp_['ma10']=ta.SMA(df_tmp_['close'],timeperiod=10)
    df_tmp_['ma30']=ta.SMA(df_tmp_['close'],timeperiod=30)
    df_tmp_['ma60']=ta.SMA(df_tmp_['close'],timeperiod=60)
    df_tmp_['vma5']=ta.SMA(df_tmp_['volume'],timeperiod=5)
    df_tmp_['vma10']=ta.SMA(df_tmp_['volume'],timeperiod=10)
    up_,mid_,dn_ = ta.BBANDS(df_tmp_['close'],timeperiod=20,nbdevup=1,nbdevdn=1)
    df_tmp_['bollup']=up_
    df_tmp_['bollmid']=mid_
    df_tmp_['bolldn']=dn_
    df_tmp_['stddev']=df_tmp_['bollup']-df_tmp_['bollmid']
    df_tmp_['stdpercent']=df_tmp_['stddev']/df_tmp_['close']
    df_tmp_['stdma5']=ta.SMA(df_tmp_['stdpercent'],timeperiod=5)
    df_tmp_['stdma10']=ta.SMA(df_tmp_['stdpercent'],timeperiod=10)
    df_tmp_['stock']=stockname
    df_tmp_['buyflag']=(df_tmp_['close'].values>df_tmp_['bollup'].values)&(df_tmp_['close'].values>df_tmp_['ma60'].values)&\
                (df_tmp_['vma5'].values>df_tmp_['vma10'].values)&(df_tmp_['close'].values>df_tmp_['ma5'].values)#&(df_tmp_['ma5'].values>df_tmp_['ma10'].values)#&(df_tmp_['ma5'].values>df_tmp_['ma30'])
    df_tmp_=df_tmp_.reset_index().set_index('stock')
    return df_tmp_    
    
def choosebuy(context):
    stock=get_index_stocks(g.stock,date=context.current_dt)
    #stock='000016.XSHG'
    ind=get_price('000300.XSHG',end_date=context.current_dt,count=10)
    ind['ma5']=ta.SMA(ind['close'],timeperiod=5)
    ind['ma10']=ta.SMA(ind['close'],timeperiod=10)
    ind['indactor']=(ind['close'].values > ind['ma5'].values) #&(ind['ma5'].values>ind['ma10'].values)
    if ind.iloc[-1]['indactor']:
        if isinstance(stock,list):
            c= get_price(stock,end_date=context.current_dt,count=60).to_frame()
            stock_df=pd.DataFrame()
            for code in stock:
                df_tmp=c.swaplevel('major','minor').loc[code]
                if len(df_tmp)<60:continue
                df_tmp=fillingdata(df_tmp,code)
                stock_df=stock_df.append(df_tmp)
        elif isinstance(stock,str):
            df_tmp= get_price(stock,end_date=context.current_dt,count=60)
            stock_df=fillingdata(df_tmp,stock)
        else:
            print(type(stock))
        buylist=stock_df[stock_df['buyflag']].index.tolist()
        if (buylist != []):
            buylist=list(set(buylist)-set(g.last_stop_loss))
            g.last_stop_loss=[]
            n_=15
            for security in buylist:
                order_value(security, context.portfolio.available_cash/n_)
            send_message('美好的一天，开始交易！' + str(buylist))
    else:
        g.last_stop_loss=[]
    
def make_stoploss(context):
    log.error("Make stop loss is working!"+str(context.current_dt))
    position_list=context.portfolio.positions.keys()
    n=20
    list_stop_loss = stop_loss(position_list,n,context.current_dt)
    if list_stop_loss != []:
        log.error("execute stop loss!The Date is:"+str(context.current_dt)+"the stocks:"+str(list_stop_loss))
        for code in list_stop_loss:
            order_target_value(code,0)
        g.last_stop_loss=list_stop_loss
        send_message('止损!'+ str(list_stop_loss))

def cleanposition(context):
    for stock in context.portfolio.positions.keys():
        order_target_value(stock,0)
   

## 收盘后运行函数
def after_market_close(context):
    #log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    
    #得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
        #log.info('一天结束')
        log.info('##############################################################')
