# Clone from JoinQuant
# postId: 688a1c5c5f1f9c86e8c1c68f49b4036c
# backtestId: 0b6d5d84e57577b9e8a80a1cc450a21f
# title: 请教当期EMA的调用方法以及N期前EMA数值的调用方法

import math
def initialize(context):
    g.security = '000001.XSHE'      #导入A股指数
    set_universe([g.security])      #将指数设置为股票池子
    set_benchmark('000300.XSHG')    #设置基准收益为沪深300指数
    set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))     #设置交易手续费
    set_option('use_real_price',True)   #设置以真实价格（除权）交易
    g.stocks_trading=[]     #初始化可用股票池(不停牌的股票池)
    g.stocks_hist=[]        #初始化有历史数据的股票池
    g.stocks_hold=[]        #初始化持仓股票池
    g.stocks_toChoose=[]    #初始化备选股票池
    g.stocks_toBuy=[]       #将要买入的股票池
    g.stocks_toSell=[]      #将要卖出的股票池
    
#定义EMA计算方法
def EMA(security,N):       #N为天数，C为价格
    # 获取EXPMA初始值为回测时间段和上市交集的前N-1个收盘价均值
    global EXPMA2,EXPMA1,init_price
    init_price=None
    #EXPMA1为前日EMA值，EXPMA2为当日EMA值
    close_price = history(N, unit='1d', field='close', security_list=None)
    if init_price is None and not math.isnan(close_price[security][1]):
        init_price = close_price[security].mean()#nan和N-1个数，mean为N-1个数的均值
        EXPMA2 = init_price
    EXPMA1 = EXPMA2
    if not math.isnan(close_price[security][0]):
        # 回测T时间，取得T-1的收盘价
        current_close = close_price[security][-1]
        a = 2/(N+1)
        EXPMA2 = a * current_close + (1 - a)*EXPMA1
    EXPMA=EXPMA2
    return EXPMA

def buy_ruler(stockid):
    pass
    
# 每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)调用一次
def handle_data(context, data):
    #获取当前现金
    cash=context.portfolio.cash
    log.info(EMA(g.security,14))