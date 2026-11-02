# Clone from JoinQuant
# postId: 9cad7a7b5870eaea6d2004f02194ed8b
# backtestId: b999679ac799a8beeeef061ac1894965
# title: 为什么在策略环境里面不可以调用statsmodels.api下面的UnobservedComponents包，而在研究环境可以？

# 导入函数库
import jqdata
from datetime import datetime,timedelta,date
import pandas as pd
import talib as tb
import numpy as np
import statsmodels.api as sm
import matplotlib.pyplot as plt

# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True) #False
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')
    
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    set_subportfolios([SubPortfolioConfig(cash=500000, type='stock')])
    # g.max_holddays = 30
    g.num_stocks = 1
    # g.stocks_hold = {} # hold持股时间 
    g.securitys = ['601800.XSHG'] #get_index_stocks('000300.XSHG') # get_concept_stocks('GN001')  #['000049.XSHE']#
    #g.securitys = Filter_young_stock(context, g.securitys) # 过滤上市天数小于365天的股票

    #开盘时运行
    run_daily(market_open, time='open', reference_security='000300.XSHG')

## 开盘时运行函数
def market_open(context):
    #log.info('函数运行时间(market_open):'+str(context.current_dt.time()))
    restricted_model = {'level': 'smooth trend', 'cycle': True, 'damped_cycle': True, 'stochastic_cycle': False }

    current_data = get_current_data()
    securitys = [stock for stock in g.securitys if not current_data[stock].paused]
    if len(securitys) == 0 :return 
    
    start_date = context.current_dt-timedelta(days=365)  #).date()
    curre_date = context.current_dt
    price=get_price(securitys, start_date=start_date, end_date=curre_date, frequency='1d', fields=None, skip_paused=False, fq='pre', count=None)
    log_price=np.log(price.close)
    price['log_price'] = log_price
    #log.info(log_price)
    #output_mod = sm.tsa.UnobservedComponents(log_price, **restricted_model)
    #output_res = output_mod.fit(method='powell', disp=False)
    hp_cycle, hp_trend = sm.tsa.filters.hpfilter(log_price, lamb=129600)
    log.info( hp_trend)
