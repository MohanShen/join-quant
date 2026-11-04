# Clone from JoinQuant
# postId: 05c5944d99d330471c567cd909144b1f
# backtestId: 7ec50857df4777468d5e335aa92c0369
# title: 【缠论初探】笔方向破坏的级别共振策略

# 导入聚宽函数库
import jqdata
import numpy as np   
import pandas as pd    
# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000001.XSHG')
    g.security = '000001.XSHG'
    # 开启动态复权模式(真实价格)
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    # 过滤掉order系列API产生的比error级别低的log
    ### 股票相关设定 ###
    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
      # 开盘前运行
    run_daily(before_market_open, time='before_open', reference_security='000001.XSHG') 
      # 开盘时运行
    run_daily(market_open, time='every_bar', reference_security='000001.XSHG')
      # 收盘后运行
    run_daily(after_market_close, time='after_close', reference_security='000001.XSHG')
    
## 开盘前运行函数     
def before_market_open(context):
    # 输出运行时间
    log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))
    df_d=get_price(g.security,end_date=context.current_dt,frequency='1d',fields=['high','low'],count=100)
    df_5d=get_price(g.security,end_date=context.current_dt,frequency='5d',fields=['high','low'],count=100)
    df_60m=get_price(g.security,end_date=context.current_dt,frequency='60m',fields=['high','low'],count=100)
    #df_30m=get_price(g.security,end_date=context.current_dt,frequency='m',fields=['high','low'],count=100)
    # 给微信发送消息（添加模拟交易，并绑定微信生效）
    df_d=label_k_func(df_d)
    df_5d=label_k_func(df_5d)
    df_60m=label_k_func(df_60m)
    #df_15m=label_k_func(df_5d)
    #返回1表示处于未被打破的上升阶段，返回-1表示未被打破的下降阶段
    g.j=label_bi_func(df_d)
    g.l=label_bi_func(df_5d)
    g.k=label_bi_func(df_60m)
## 开盘时运行函数
def market_open(context):
    if (g.j,g.l,g.k)==(1,1,1):
        cash=context.portfolio.cash 
        order_value(g.security,cash)
    elif (g.j,g.l,g.k)==(-1,-1,-1):
        order_target(g.security,0)
## 收盘后运行函数  
def after_market_close(context):
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    #得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    log.info('一天结束')
    log.info('##############################################################')
    
def label_k_func(df):
    #进行K线的包含关系处理，再原数据表中增加label进行是否有效的标记，增加两列记录合并K线后的极值
    h=df['high'].values
    l=df['low'].values
    df['t']=pd.Series(range(len(df)),index=df.index)
    t=df['t'].values
    label=[1]
    h_jizhi,l_jizhi=h[0],l[0]
    high_new=[h[0]]
    low_new=[l[0]]
    #标记Ｋ线的有效性，上升Ｋ线为１，下降为－１，无效为０
    for i in t[1:]:
        #缠论上升K线的定义
        if h[i]>h_jizhi and l[i]>l_jizhi:
            label.append(1)
            h_jizhi=max(h[i],h[i-1])
            l_jizhi=max(l[i],l[i-1])
        #缠论下降K线的定义
        elif h[i]<h_jizhi and l[i]<l_jizhi:
            label.append(-1)
            h_jizhi=min(h[i],h[i-1])
            l_jizhi=min(l[i],l[i-1])
        #包涵K线的处理
        else:
            label.append(0)
            #下面的内容主要是进行极值的更新
            for j in label[::-1]:
                if j != 0:
                    a=j
                    break
            if a==1:
                h_jizhi=max(h[i],h_jizhi)
                l_jizhi=max(l[i],l_jizhi)
            else:
                h_jizhi=min(h[i],h_jizhi)
                l_jizhi=min(l[i],l_jizhi)
        high_new.append(h_jizhi)
        low_new.append(l_jizhi)
    #把结果添加到df
    df['label_k']=pd.Series(label,index=df.index)
    df['high_k']=pd.Series(high_new,index=df.index)
    df['low_k']=pd.Series(low_new,index=df.index)
    return df

#找出可以构成笔的K线位置
#step1 找出有效笔的起点位置
#得到有效笔的起点位置
##先将有效K先的label整理成列表l1
def label_bi_func(df):
    l1=[]
    list1=df['label_k'].values
    for i in range(len(list1)):
        if list1[i]!=0:
            l1.append(i)
    ##记录有效位置的起点
    label_s_e=[]
    for z in range(2,len(l1)):
        if (list1[l1[z]],list1[l1[z-1]],list1[[l1[z-2]]])==(1,1,1):
            label_s_e.append((l1[z-2],1))
        elif (list1[l1[z]],list1[l1[z-1]],list1[[l1[z-2]]])==(-1,-1,-1):
            label_s_e.append((l1[z-2],-1))
    ##取到第一个有效起点
    label_se=[]
    a=0
    for i in range(1,len(label_s_e)):
        if a==0:
            label_se.append(label_s_e[i][0])
            if label_s_e[i][1]==1:
                a=1
            elif label_s_e[i][1]==-1:
                a=-1
        elif a==1:
            if label_s_e[i][1]==1:
                pass
            elif label_s_e[i][1]==-1:
                label_se.append(label_s_e[i][0])
                a=-1
        elif a==-1:
            if label_s_e[i][1]==1:
                label_se.append(label_s_e[i][0])
                a=1
            elif label_s_e[i][1]==-1:
                pass
    return a

