# Clone from JoinQuant
# postId: 4e9060cc541d2969a155cf9746062e09
# backtestId: 4419a7888721275d34b5209b56fb5631
# title: 回测的时候还是有手续费

# 导入函数库
from jqdata import *
import time
# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    g.kj={            
             #'000016.XSHG':'510050.XSHG',#上证50 2004-01-02
             '399006.XSHE':'399006.XSHE',#创业板指2010-06-01 2011y
             '399905.XSHE':'399905.XSHE',#中证500 2007-01-15
             '000300.XSHG':'000300.XSHG',#沪深300 2005-04-08
             #'000015.XSHG':'510880.XSHG',#上证红利指数	红利ETF	2007-01-18
            #'399004.XSHE':'399004.XSHE',#深证100R 	2003-01-02
            #'000991.XSHG':'159938.XSHE',#全指医药	广发医药	2015-01-08
            #'000852.XSHG':'000852.XSHG',#	中证1000指数	2014-10-17	
           
            

        }
    g.hy={
        '399932.XSHE':'399932.XSHE',#中证主要消费2009-07-03	消费ETF	2013-09-16
         #'399931.XSHE',#中证可选消费指数 场内etf成交额太少
        '000991.XSHG':'000991.XSHG',#全指医药2011-08-02 广发医药	2015-01-08
        #'399441.XSHE',国证生物医药指数2015-01-20
        '000015.XSHG':'000015.XSHG',#上证红利指数	红利ETF	2007-01-18
        #'000922.XSHG',#中证红利 没有场内etf
        '000993.XSHG':'000993.XSHG',#全指信息2011-08-02	信息技术	2015-02-05
        #'000827.XSHG':'000827.XSHG',#中证环保2012-09-25	环保ETF	2017-02-28	
        #'399971.XSHE':'399971.XSHE',#中证传媒2014-04-15传媒ETF	2018-01-19
        #'399975.XSHE':'512880.XSHG',#中证全指证券2013-07-15	证券ETF	2016-08-08
        #'399986.XSHE':'512800.XSHG',#中证银行指数 银行ETF	2017-08-03
        #'399997.XSHE'#中证白酒指数 无场内etf
        '399967.XSHE':'399967.XSHE', #中证军工2013-12-26  2016-08-08
        #'513050.XSHG':'513050.XSHG'#中概互联	2017-01-18	是
        }
    #g.status='start'
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')
    #run_monthly(set_status, 1, time='9:30')
    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之2，卖出时佣金万分之2加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.000, open_commission=0.0000, close_commission=0.0000, min_commission=0), type='fund')
    set_slippage(PriceRelatedSlippage(0.000))

    run_daily(jiaoyi, time='14:59')
def jiaoyi(context):
    old_etf=set(context.portfolio.positions.keys())
    index_list=list(g.kj.keys())
    #g.status=='start':
    new_index=select_index_ma(index_list,context.current_dt,13,13,120)
    #new_etf = set([g.kj[new_index]]) if new_index else set()
    new_etf = set([new_index])
    caozuo(context,old_etf,new_etf)
    return None 
    
def caozuo(context,old_etf=set(),new_etf=set()):
    sell=old_etf-new_etf
    buy=new_etf-old_etf
    if sell:
        order_target(list(sell)[0],0)
    if buy:
        order_value(list(buy)[0],context.portfolio.available_cash)
    return None
def select_index_ma(index_list,dt,RPS_N=13,MA_N=13,MA_N2=120):
    days=max(RPS_N,MA_N,MA_N2)+10
    date=dt.strftime("%Y-%m-%d")
    #get_price 未来函数：回测时候最近的一行数据用的是15：00的close，用get——bar更新
    df=get_price(index_list,fields=['close'],end_date=date,count=days).to_frame()
    
    for zhishu in index_list:
        #dt 是datetime
        array = get_bars(zhishu, 1, unit='5m',fields=['close'],include_now=True,end_dt=dt)
        df.loc[(date,zhishu)]=array[0][0]
    
    jg=pd.DataFrame()
    for k,sl in df.groupby(level=1):
        sl=sl.sort_index(level=0,ascending=True)
        sl2=sl.copy()
        sl2['zhangfu']=sl2.close/sl2.close.shift(RPS_N)-1
        sl2['ma']=sl.close.rolling(MA_N).mean()
        sl2['ma2']=sl.close.rolling(MA_N2).mean()
        jg = jg.append(sl2.iloc[-1])
    xz = jg.sort_values('zhangfu',ascending=False)[:1]
    xz= xz[(xz.close>xz.ma) & (xz.ma>=xz.ma2)]
    index_selected= xz.index[0][1] if len(xz)>0 else '000012.XSHG'
    return index_selected  