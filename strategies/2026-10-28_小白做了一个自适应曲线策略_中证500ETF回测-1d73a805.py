# Clone from JoinQuant
# postId: 1d73a8055d65aa5aeb68e0730b8948eb
# backtestId: b8601c92886c643f60b3e77cc1f99842
# title: 小白做了一个自适应曲线策略，中证500ETF回测

# 导入TA-Lib
import talib
# 导入numpy命名为np
import numpy as np
# 导入pandas命名为pd
import pandas as pd

set_benchmark('399905.XSHE')
set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0003, min_cost=1))

def initialize(context):
    # 定义一个全局变量, 保存要操作的股票
    g.security = '399905.XSHE'
    g.flag = 0
    g.N1=7.0
    g.N2=9.0
    g.N=9
    g.label =0 
    g.AMA=[0,0,0]
    set_universe([g.security])

# 每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)调用一次
def handle_data(context, data):
    security = g.security
    last_Nday_close_price = history(g.N, unit='1d', field='close', security_list=None)
    sumPdiff = 0
    
    for i in range(0,g.N-1):
        sumPdiff = sumPdiff + abs (last_Nday_close_price[security][i+1]-last_Nday_close_price[security][i])
        
    eff = abs(last_Nday_close_price[security][g.N-1]-last_Nday_close_price[security][0])/sumPdiff

    sc = eff*2/(g.N1+1)-eff*2/(g.N2+1)+2/(g.N2+1)
    c = sc * sc
    ama = c * last_Nday_close_price[security][-1]+(1-c)*g.AMA[-1]
    
    if g.label  == 0:
        g.AMA[2]=last_Nday_close_price[security][-1]
        g.label = g.label +1
    else:
        g.AMA.append(ama)
    
    cash = context.portfolio.cash
    print g.AMA
    if (g.AMA[-1] - g.AMA[-2])> 0.01 and (g.AMA[-2] - g.AMA[-3]) < -0.01 :
         print g.AMA[-1]
         print g.AMA[-2]
         print g.AMA[-3]
         order_value('510500.XSHG', cash)
         log.info("Buying %s" % (security))
     
    elif  (g.AMA[-1] - g.AMA[-2])< 0.01 and (g.AMA[-2] - g.AMA[-3]) > -0.01 :
        order_target('510500.XSHG', 0)
        log.info("Selling %s" % (security))
      
    # 画出上一时间点价格

