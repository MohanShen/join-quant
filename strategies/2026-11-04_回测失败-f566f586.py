# Clone from JoinQuant
# postId: f566f586736897a3b7c8f8e72d7c7243
# backtestId: 9099a6bee68eec4e0ad4d829039adc2a
# title: 回测失败

# 导入函数库
from jqdata import *
import time
import datetime
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

    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
      # 开盘时运行
    run_daily(market_open, time='open', reference_security='000300.XSHG')

    g.security = get_index_stocks('000300.XSHG')
    print(g.security)

    g.hold=[]

    

## 开盘时运行函数
def market_open(context):
    #筛选过去10个交易日涨幅大于30%的股票：
    for stocks in g.security:
        a=attribute_history(stocks,3,'1d')
        a1=int(float(a['money'][-1]))
        g.hold=g.hold+[a1]

    jjj=sorted(g.hold,reverse=True)
    quanbu=sum(jjj)#全部的总和
    qian5=jjj[0:15]
    bufen=sum(qian5)#前5%的总和
    zzz=bufen/quanbu#前5%的百分比
    sss=attribute_history('000300.XSHG',3,'1d')
    sz50=sss['close'][-1]
    
    print('百分比'+str(zzz))
    print('沪深'+str(sz50))
    g.hold=[]


    

        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        