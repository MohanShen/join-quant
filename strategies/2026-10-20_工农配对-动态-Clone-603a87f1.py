# Clone from JoinQuant
# postId: 603a87f1444bca8729b0d65a5098c72b
# backtestId: 2186f9ac7853f003949d08067bce7734
# title: 工农配对-动态-Clone

# 克隆自聚宽文章：https://www.joinquant.com/post/6180
# 标题：银行配对-工农配对动态系数版
# 作者：配对达人

import talib
import numpy as np
import pandas as pd
from sklearn import linear_model
'''
================================================================================
总体回测前
================================================================================
'''
# 初始化函数，设定要操作的股票、基准等等
#总体回测前要做的事情
def initialize(context):
    set_params()                             # 设置策略常量
    set_variables()                          # 设置中间变量
    set_backtest()                           # 设置回测条件
    set_benchmark('601398.XSHG')
    #getCoeff(context)
    #get_fzbz(context)
    
#1 
#设置策略参数
def set_params():
    #g.stocks=['601398.XSHG', '601939.XSHG']  # 设置银行股票 工行，建行
    g.stocks=['601398.XSHG', '601288.XSHG']  #工行农行
    g.flag_stat = False                      # 默认不开启统计
    #g.a = 0.7356
    #g.b = 0
    #g.c = 1.0261
    #g.d = 0
    #g.fzbz = 1                     # 阀值标准
    g.year=0
    '''
    工行预测涨幅=建行涨幅*a+b
    建行预测=工行*c+d
    '''
    
#2
#设置中间变量
def set_variables():
    return None
#3
#设置回测条件
def set_backtest():
    set_option('use_real_price',True)        # 用真实价格交易
    log.set_level('order','debug')           # 设置报错等级

    
'''
================================================================================
每天开盘前
================================================================================
'''
#每天开盘前要做的事情
def before_trading_start(context):
    set_slip_fee(context)                 # 设置手续费与手续费
    # 设置可行股票池
    g.feasible_stocks = set_feasible_stocks(g.stocks,context)# 得到所有股票昨日收盘价, 每天只需要取一次, 所以放在 before_trading_start 中
    g.last_df = history(1,'1d','close', security_list=g.stocks)
    #log.debug(g.last_df)
    #每月获取动态系数g.a,g.b,g.c,g.d
    #run_monthly(getCoeff, 1, 'before_open')
    #run_monthly(get_fzbz, 1, 'before_open')
    g.fz = 0                              # 每天重置
    if g.year!=context.current_dt.year:
        g.year=context.current_dt.year
        getCoeff(context)
        get_fzbz(context)
        
    
# 过滤停牌股票
def filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]

# 停牌返回True，    
def is_paused(stock):
    current_data = get_current_data()
    return current_data[stock].paused
    
# 过滤ST及其他具有退市标签的股票
def filter_st_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list 
        if not current_data[stock].is_st 
        and 'ST' not in current_data[stock].name 
        and '*' not in current_data[stock].name 
        and '退' not in current_data[stock].name]
        
#4
# 设置可行股票池：过滤掉当日停牌的股票
# 输入：initial_stocks为list类型,表示初始股票池； context（见API）
# 输出：unsuspened_stocks为list类型，表示当日未停牌的股票池，即：可行股票池
def set_feasible_stocks(initial_stocks,context):
    # 判断初始股票池的股票是否停牌，返回list
    pick_stock = filter_paused_stock(initial_stocks)
    # 去除ST
    pick_stock = filter_st_stock(pick_stock)
    return pick_stock

    
#5
# 根据不同的时间段设置滑点与手续费
# 输入：context（见API）
# 输出：none
def set_slip_fee(context):
    # 将滑点设置为0
    set_slippage(FixedSlippage(0)) 
    # 根据不同的时间段设置手续费
    set_commission(PerTrade(buy_cost=0.00025, sell_cost=0.00125, min_cost=5)) 

'''
================================================================================
开盘前选股
================================================================================
'''
    
# 计算股票池，存入g.df_pick
def stocks_to_buy(context, data):
    list_can_buy = []
    
    
        
'''
================================================================================
每分钟交易时
================================================================================
'''

def prcIncPer(data):
    data=data.dropna(axis=0)
    tmp=data.shift(1).fillna(0)
    tmp=(data-tmp)/tmp*100
    #tmp.columns=['percentage']
    return tmp[1:]
    
def linRegr(d,Y):
    d=d.dropna()
    Y=Y.dropna()
    if len(d)!=len(Y):
        length=min(len(d),len(Y))
        d=d[:length]
        Y=Y[:length]
    regr = linear_model.LinearRegression()
    X=[]
    #for i in np.array(d['percentage'].values):
    for i in np.array(d.values):
        X.append([i])
    #predict_value=regr.fit(X,np.array(Y['percentage'].values))
    predict_value=regr.fit(X,np.array(Y.values))
    b = regr.intercept_
    a= regr.coef_
    #print a[0],
    return a[0],b
    
def amplitude(data):
    up=(data['high']-data['open'])/data['open']*100
    dn=(data['open']-data['low'])/data['open']*100
    ap = up+dn
    return 1.5/ap.mean()
    
def getCoeff(context):
    h=history(400, unit='1d', field='close', security_list=g.stocks, df=True, skip_paused=False, fq='pre')
    tmp0=h[g.stocks[0]]
    tmp1=h[g.stocks[1]]
    data0=prcIncPer(tmp0)
    data1=prcIncPer(tmp1)
    g.a,g.b=linRegr(data1,data0)
    g.c,g.d=linRegr(data0,data1)

def get_fzbz(context):
    #amp_bench='000016.XSHG'
    amp_bench='000001.XSHG'
    tmp = attribute_history(amp_bench, 50, unit='1d',fields=['open', 'close', 'high', 'low'],skip_paused=True, df=True, fq='pre')
    g.fzbz=amplitude(tmp)
    #print 'fzbz is %f' % g.fzbz
    
# 回测时做的事情
def handle_data(context,data):
    # 工行   g.stocks[0]
    # 建行   g.stocks[1]
    '''
    工行和建行的涨幅
    工行预测涨幅=建行涨幅*a+b
    建行预测=工行*c+d
    工行实际-工行预测=误差0
    建行实际-建行预测=误差1
    误差0-误差1=阀值
    阀值变量
    阀值变量负数那就买入工行0卖出建行1（要是有持仓的话）
    正数就是买入建行卖出工行
    买入挂单和卖出挂单都是按照买一或者卖一
    '''
    # 得到当前资金余额
    cash = context.portfolio.cash
    price0 = data[g.stocks[0]].close
    price1 = data[g.stocks[1]].close
    last_close0 = g.last_df[g.stocks[0]][0]
    last_close1 = g.last_df[g.stocks[1]][0]
    #print last_close0,last_close1
    zf0 = (price0-last_close0)/last_close0*100
    zf1 = (price1-last_close1)/last_close1*100

    yczf0 = zf1*g.a+g.b
    yczf1 = zf0*g.c+g.d
    wc0 = zf0 - yczf0
    wc1 = zf1 - yczf1
    g.fz_before = g.fz
    g.fz = wc0 - wc1
    #print g.a,g.b,g.c,g.d,g.fz,g.fzbz
    #print '--------'
    if g.fz_before > 0 and g.fz < -1*g.fzbz:
        # 惊天大逆转
        orders = get_open_orders()
        for _order in orders.values():
            log.info(_order.order_id)
    elif g.fz_before < 0 and g.fz > g.fzbz:
        orders = get_open_orders()
        for _order in orders.values():
            log.info(_order.order_id)
    if g.fz < -1*g.fzbz:                          # 跟阀值标准比
        #return g.stocks[0]
        if context.portfolio.positions[g.stocks[1]].sellable_amount > 0:
            #order_target(g.stocks[1], 0, LimitOrderStyle(price1-0.01))
            order_target(g.stocks[1], 0)
        #order_value(g.stocks[0], cash, LimitOrderStyle(price0+0.01))
        order_value(g.stocks[0], cash)
        '''
        if g.fz < g.fz_before and g.fz_before < g.fzbz: #更低估 撤单追买卖
            orders = get_open_orders()
            for _order in orders.values():
                cancel_order(_order)
            if context.portfolio.positions[g.stocks[1]].sellable_amount > 0:
        '''
    elif g.fz > g.fzbz:
        #return g.stocks[1]
        if context.portfolio.positions[g.stocks[0]].sellable_amount > 0:
            #order_target(g.stocks[0], 0, LimitOrderStyle(price0-0.01))
            order_target(g.stocks[0], 0)
        #order_value(g.stocks[1], cash, LimitOrderStyle(price1+0.01))
        order_value(g.stocks[1], cash)
    
    
'''
================================================================================
每天交易后
================================================================================
'''
#每个交易日结束运行
def after_trading_end(context):
    #得到当前未完成订单
    orders = get_open_orders()
    for _order in orders.values():
        log.info(_order.order_id)  