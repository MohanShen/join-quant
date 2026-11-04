# Clone from JoinQuant
# postId: db583cfecee607941b94f9fc268573de
# backtestId: a9e06cf71c13d95b8432b5caa6250d5c
# title: 对MACD均线择时策略的改进

'''
筛选出符合：
10<市盈率（pe_ratio）<40, 市净率（pb_ratio)<3, 净利润环比增长率(inc_net_profit_annual)>0.3，净资产收益率(roe)>15的股票，按照销售毛利率进行降序排列，选取前50只
买入：DIF从下而上穿过DEA，即形成金叉
卖出：DIF从上往下穿过DEA，即形成死叉
十天一次调仓
主要用于学习量化的朋友交流所用，熟悉技术分析指标的调用
作者：刘永平
'''
import pandas as pd
import numpy as np
import talib  ## 使用talib计算MACD的参数
def initialize(context):
    g.days=0#计算持有天数
    g.refresh_rate=10#调仓的频率
    set_benchmark('000905.XSHG')#设置参考指数
    set_option('use_real_price', True)
    log.set_level('order', 'error')#过滤日志错误
    run_daily(trade, 'every_bar')
    
def before_trading_start(context):
    set_slip_fee(context)

#设置下滑，交易费率
def set_slip_fee(context):
    set_slippage(FixedSlippage(0.02)) 
    dt=context.current_dt
    if dt>datetime.datetime(2013,1, 1):
        set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003, close_today_commission=0, min_commission=5), type='stock')
    else:
        set_order_cost(OrderCost(open_tax=0, open_commission=0.003,close_commission=0.003, close_tax=0.001,min_commission=5), type='stock')

#过滤停牌股票 
def paused_filter(security_list):
    current_data=get_current_data()
    security_list = [stock for stock in security_list if not current_data[stock].paused]
    return security_list

#过滤退市股票
def delisted_filter(security_list):
    current_data = get_current_data()
    security_list = [stock for stock in security_list if not '退' in current_data[stock].name]
    return security_list

#过滤ST   
def st_filter(security_list):
    current_data = get_current_data()
    security_list = [stock for stock in security_list if not current_data[stock].is_st]
    return security_list 
    
#对持仓股票每日进行检查，死叉卖出   
def zy_zs(context):
    dqhold = list(context.portfolio.positions.keys())
    for stock in dqhold:
            prices=attribute_history(stock,300,'1d',['close'])
            price=array(prices['close'])
            MACD_tmp=talib.MACD(price,fastperiod=12,slowperiod=26,signalperiod=20)
            DIF=MACD_tmp[0]
            DEA=MACD_tmp[1]
            MACD=MACD_tmp[2]
            if MACD[-1]<0 and MACD[-4]>0:
                order_target_value(stock, 0)
def trade(context):
    zy_zs(context)#卖出死叉个股
    #如果手中不持有股票，则立即进行选股
    if len(context.portfolio.positions.keys())==0:
        g.days=0
    #10<市盈率(pe_ratio)<40，每股盈余(eps)>0.3，净资产收益率(roe)>15，净利润环比增长率>0.3，并按照市净率进行升序排列，取前五十只。
    if g.days%g.refresh_rate==0:
        stock_to_choose=get_fundamentals(query(
                valuation.code,valuation.pe_ratio,valuation.market_cap,
                indicator.eps,indicator.inc_net_profit_annual
                ).filter(
                        valuation.pe_ratio<40,
                        valuation.pe_ratio>10,
                        indicator.eps>0.3,
                        indicator.inc_net_profit_annual>0.3,
                        indicator.roe>15
                        ).order_by(valuation.pb_ratio.asc()
                        ).limit(
                                50),date=None)
        #过滤停牌、退市、ST个股
        stockpool = list(stock_to_choose['code'])
        stockpool = paused_filter(stockpool)
        stockpool = delisted_filter(stockpool)
        stockpool = st_filter(stockpool)
        jx_list=[]#MACD金叉列表
        sx_list=[]#MACD死叉列表
        hold=[]#持有列表
          
        for stock in stockpool:
            prices=attribute_history(stock,300,'1d',['close'])
            price=array(prices['close'])
            MACD_tmp=talib.MACD(price,fastperiod=12,slowperiod=26,signalperiod=20)
            DIF=MACD_tmp[0]
            DEA=MACD_tmp[1]
            MACD=MACD_tmp[2]
            if MACD[-1]>0 and MACD[-4]<0:
                jx_list.append(stock)
            elif MACD[-1]<0 and MACD[-4]>0:
                sx_list.append(stock)
                
        #卖出手中死叉个股          
        stockset = list(context.portfolio.positions.keys())
        for stock in stockset:
            if stock in jx_list:
                hold.append(stock)#如果金叉则持有
            else:
                 order_target_value(stock, 0) #卖出非金叉个股
        #构建买入列表
        buy_list = []
        for stock in jx_list:
            if stock not in hold:
                buy_list.append(stock)#新增的买入股票
              
        #分配资金，购买股票      
        if len(buy_list)==0:
            Cash=context.portfolio.available_cash
        else:
            Cash = context.portfolio.available_cash/len(buy_list)
            for stock in buy_list:
                order_target_value(stock, Cash)        
        g.days = 1
    else:
        g.days += 1