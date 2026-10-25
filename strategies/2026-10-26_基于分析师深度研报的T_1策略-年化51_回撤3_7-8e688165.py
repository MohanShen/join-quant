# Clone from JoinQuant
# postId: 8e688165e9e1704058d379d70e47c7dc
# backtestId: fed410ce19517e8d1b0cfd0523e73d10
# title: 基于分析师深度研报的T+1策略-年化51%，回撤3.7%

# 导入函数库
from jqdata import *
import pandas as pd
import pandas as pd
from six import BytesIO


# 初始化函数，设定基准等等
def initialize(context):
    body=read_file("深度报告数据0.csv")
    g.datapd=pd.read_csv(BytesIO(body))
    g.datapd['证券代码']=[str(1000000+int(code))[1::] for code in g.datapd['证券代码'].tolist()]
    #去除新三板股票
    g.datapd=g.datapd[g.datapd['证券代码']<'7']
    g.datapd=g.datapd[(g.datapd['证券代码']<'4')|(g.datapd['证券代码']>='6')]
    g.datapd['证券代码']=[code+'.XSHG' if code[0]=='6' else code+'.XSHE' for code in g.datapd['证券代码'].tolist()]
    #留下14：59前分享的研报
    g.datapd=g.datapd[g.datapd['time']<='14:59']
    g.datapd=g.datapd[g.datapd['页数']>=20]
    # print(g.datapd.head(10))
    # raise 11
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
    set_order_cost(OrderCost(close_tax=0, open_commission=0, close_commission=0, min_commission=0), type='stock')

    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
    #中午卖出股票
    run_daily(sell_stock, time='11:20', reference_security='000300.XSHG')
    
    #  收盘前买入股票
    run_daily(buy_stock, time='15:00', reference_security='000300.XSHG')

def sell_stock(context):
    
    hold_stock = context.portfolio.positions.keys()
    for s  in hold_stock:
        # g.available_cash=g.available_cash+context.portfolio.positions[s].va
        order_target_value(s,0)  
    return

def buy_stock(context):
    date1=str(context.current_dt)[0:10]
    date2=str(context.previous_date)[0:10]
    datapd2=g.datapd[g.datapd['分享日期']==date1]
    buylist=list(set(datapd2['证券代码'].tolist()))
    if len(buylist)==0:
        return
    buynum=max(2,len(buylist))
    cash = context.portfolio.available_cash/buynum
    for s in buylist:
        order_target_value(s,cash)
    return