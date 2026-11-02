# Clone from JoinQuant
# postId: c0c41a84d8c16e79aa982ecd069d0700
# backtestId: 62bd7ec40fd96d68caa3a2307cb9f6b3
# title: 请问为什么会出现那么多买入100只？

# 导入函数库
import jqdata
from jqlib.technical_analysis import *
import pandas as pd
import numpy as np
import talib as tl



# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    log.set_level('order', 'error')
    g.holding_high_price = 0    #持有期间最高价
    g.days =18
    g.a1 = 0.15 
    g.a2 = 0 
    g.a3 = -0.15

    #设置分仓，仓位1占仓位的50%，仓位2占总仓位的50%。分别交易不同的股票，仓位资金隔开。
    set_subportfolios([SubPortfolioConfig(cash=context.portfolio.starting_cash*0.1 ,type='stock'),\
                SubPortfolioConfig(cash=context.portfolio.starting_cash*0.1,type='stock'),SubPortfolioConfig(cash=context.portfolio.starting_cash*0.1,type='stock'),\
                SubPortfolioConfig(cash=context.portfolio.starting_cash*0.1,type='stock'),SubPortfolioConfig(cash=context.portfolio.starting_cash*0.1,type='stock'),\
                SubPortfolioConfig(cash=context.portfolio.starting_cash*0.1,type='stock'),SubPortfolioConfig(cash=context.portfolio.starting_cash*0.1,type='stock'),\
                SubPortfolioConfig(cash=context.portfolio.starting_cash*0.1,type='stock'),SubPortfolioConfig(cash=context.portfolio.starting_cash*0.1,type='stock'),
                SubPortfolioConfig(cash=context.portfolio.starting_cash*0.1,type='stock')])

    g.stock=['000001.XSHE', '000002.XSHE', '000008.XSHE', '000060.XSHE', '000063.XSHE', '000069.XSHE', '000100.XSHE', '000157.XSHE', '000166.XSHE', '000333.XSHE']

    g.transaction_sub_status = True

    set_universe([g.stock]) 
    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.00333, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    
    ## 运行函数（reference_stock为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
 
      # 开盘时或每分钟开始时运行
    run_daily(market_open, time='every_bar', reference_security='000300.XSHG')


    
## 开盘时运行函数
def market_open(context):
    i=0
    for stock in g.stock:
   
        Data = attribute_history(stock, g.days, unit='1d',fields=('close'),skip_paused=True,df=False)
   
        current_close = Data['close'][-1]  
   
        mclose = Data['close'].mean() 
        
        bias=current_close/mclose -1
        cur_position=context.portfolio.positions[stock].total_amount
        # 取得当前可用的资金
        cash = context.subportfolios[i].available_cash
    
        # 买入策略
        if g.a2<bias<g.a1 or bias<g.a3:
        
            order_value(stock, cash, pindex=i)
        # 卖出策略
   
        if bias>g.a1 or g.a3<bias<g.a2 : 
            if cur_position>0:#持仓量大于零
                order_target(stock, 0,pindex=i)

    i=i+1

