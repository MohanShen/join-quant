# Clone from JoinQuant
# postId: 332d3a3313f302412e6ccfb7c5b84011
# backtestId: 862f5e9e73e945d285a891fd7f3aada2
# title: 凯利公式+均值回归（只做牛市下的反弹），效果看起来还是可以的

import numpy
import pandas
import datetime

def initialize(context):
    SetConst()
    SetVariable()
    SetOption()

def SetConst():
    g.Security="000009.XSHE"
    g.Index="000001.XSHG"
    g.t=5
    g.ratio=0.2
    g.ma=10

def SetVariable():
    g.run=0
    g.IfTrade=False
    temp=get_price(g.Security, "2006-01-01", "2014-12-31", "1d", ["close"], True)
    g.Data={}
    for i in range(g.ma-1,len(temp)-g.t):
        deviate=GetDeviate(temp,i)
        Return=GetReturn(temp,i)
        AddData(deviate,Return)
    print(g.Data)
        
#扩充数据库
def AddData(deviate,Return):
    if deviate in g.Data.keys():
        if Return>0:
            g.Data[deviate]["earn"]=(g.Data[deviate]["earn"]*g.Data[deviate]["win"]+Return)/(g.Data[deviate]["win"]+1)
            g.Data[deviate]["win"]+=1
            g.Data[deviate]["total"]+=1
        elif Return<0:
            g.Data[deviate]["loss"]=(g.Data[deviate]["loss"]*g.Data[deviate]["lost"]-Return)/(g.Data[deviate]["lost"]+1)
            g.Data[deviate]["lost"]+=1
            g.Data[deviate]["total"]+=1
    else:
        if Return>0:
            g.Data[deviate]={"win":1,"lost":0,"total":1,"earn":Return,"loss":0}
        elif Return<0:
            g.Data[deviate]={"win":0,"lost":1,"total":1,"earn":0,"loss":-Return}

#获取偏离度
def GetDeviate(List,index):
    ma=GetMa(List,index,g.ma)
    flag=GetIndexFlag(List.index[index])
    return ((List.iloc[index,0]-ma)*100//ma,flag)
    
#获取行情标记
def GetIndexFlag(date_):
    temp=get_price(g.Index, end_date=date_, frequency="1d", fields=["close"], count=30)
    ma10=GetMa(temp,29,10)
    ma20=GetMa(temp,29,20)
    ma30=GetMa(temp,29,30)
    if ma10>ma20 and ma20>ma30:
        return 1
    elif ma30>ma20 and ma20>ma10:
        return -1
    else:
        return 0
    
#获取移动平均值 
def GetMa(List,index,n):
    sum=0
    for i in range(n):
        sum+=List.iloc[index-i,0]
    return sum/n

#获取未来t天的收益率
def GetReturn(List,index):
    return (List.iloc[index+g.t,0]-List.iloc[index,0])/List.iloc[index,0]
    
def SetOption():
    set_option("use_real_price",True)
    log.set_level("order","error")
    set_benchmark(g.Security)

def before_trading_start(context):
    if g.run%g.t==0:
        g.IfTrade=True
        SetSlipAndFee(context)
        temp=attribute_history(security=g.Security,count=g.ma,unit= "1d",fields= ["close"], skip_paused=True, df=True)
        deviate=GetDeviate(temp,g.ma-1)
        if deviate[0]>0:
            g.run-=1
        g.Kelly=kelly(deviate)
        print(g.Kelly)
    g.run+=1

def SetSlipAndFee(context):
    set_slippage(FixedSlippage(0))
    today=context.current_dt
    if today>datetime.datetime(2013,1, 1):
        set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0013, close_today_commission=0, min_commission=5),type="stock")
    elif today>datetime.datetime(2011,1, 1):
        set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.001, close_commission=0.002, close_today_commission=0, min_commission=5),type="stock")
    elif today>datetime.datetime(2009,1, 1):
        set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.002, close_commission=0.003, close_today_commission=0, min_commission=5),type="stock")
    else:
        set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.003, close_commission=0.004, close_today_commission=0, min_commission=5),type="stock")
        
def handle_data(context, data):
    if g.IfTrade==True:
        g.IfTrade=False
        capital=context.portfolio.total_value*g.ratio*g.Kelly
        order_target_value(g.Security,capital)

#获取仓位比例
def kelly(deviate):
    if deviate[0]>0 or deviate[1]!=1:
        return 0
    if deviate not in g.Data.keys():
        return 0
    if g.Data[deviate]["total"]<10:
        return 0
    Pwin=g.Data[deviate]["win"]*1.0/(g.Data[deviate]["total"])
    Plose=g.Data[deviate]["lost"]*1.0/(g.Data[deviate]["total"])
    print(Pwin,g.Data[deviate]["earn"],Plose,g.Data[deviate]["loss"])
    if Pwin==1:
        return 1
    elif Plose==1:
        return 0
    else:
        return Pwin/g.Data[deviate]["loss"]-Plose/g.Data[deviate]["earn"]
#每日更新数据库
def after_trading_end(context):
    temp=get_price(security=g.Security, end_date=context.current_dt, frequency="1d", fields=["close"], skip_paused=True, count=g.t+g.ma)
    deviate=GetDeviate(temp,g.ma-1)
    Return=GetReturn(temp,g.ma-1)
    AddData(deviate,Return)