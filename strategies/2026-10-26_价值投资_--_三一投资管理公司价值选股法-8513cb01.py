# Clone from JoinQuant
# postId: 8513cb0185ab2b43a18e6e2064232983
# backtestId: 0b1df5307a373fcf02857bd31b933121
# title: 价值投资 -- 三一投资管理公司价值选股法

from datetime import timedelta, date
import pandas as pd

def initialize(context):
    log.info('Computing...')
    set_benchmark('000300.XSHG')
    set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
    set_slippage(PriceRelatedSlippage())
    g.i = 400
    g.stocknum = 30 # 持股数
    ## 自动设定调仓月份（如需使用自动，注销下段）
    f = 4  # 调仓频率
    log.info(range(1,13,12/f))
    g.Transfer_date = range(1,13,12/f)
    
    ## 手动设定调仓月份（如需使用手动，注销上段）
    # g.Transfer_date = (3,9)
    run_daily(dapan_stoploss) #根据大盘止损，如不想加入大盘止损，注释此句即可
    ## 按月调用程序
    run_monthly(Transfer,20)

def Transfer(context):
    months = context.current_dt.month
    if months in g.Transfer_date:
        ## 分配资金
        if len(context.portfolio.positions) < g.stocknum :
            Num = g.stocknum  - len(context.portfolio.positions)
            Cash = context.portfolio.cash/Num
        else: 
            Cash = context.portfolio.cash
        
        ##获得Buylist
        PE_list = Check_PE(context)
        PB_list = Check_PB(context)
        X = Check_Dividend_Yield(context)
        DY_list = list(dict(X).keys())
        Buylist = list(set(PE_list)&set(PB_list)&set(DY_list))
        log.info(len(Buylist))
        
        ## 卖出
        if len(context.portfolio.positions) > 0:
            for stock in context.portfolio.positions.keys():
                if stock not in Buylist:
                    order_target(stock, 0)
        ## 买入
        if len(Buylist) > 0:
            for stock in Buylist:
               if stock not in context.portfolio.positions.keys():
                   order_value(stock,Cash)
    else:
        pass

def Check_PE(context):
    PE = get_fundamentals(query(
            valuation.code,
            valuation.day,
            valuation.pe_ratio
        ).filter(
            valuation.pe_ratio > 0,
        ).order_by(
            # 按PE升序排列
            valuation.pe_ratio.asc()
        ).limit(
            g.i
        ))
    return list(PE.code)

def Check_PB(context):
    PB = get_fundamentals(query(
            valuation.code,
            valuation.day,
            valuation.pb_ratio
        ).filter(
            valuation.pb_ratio > 0,
        ).order_by(
            # 按PE升序排列
            valuation.pb_ratio.asc()
        ).limit(
            g.i
        ))
    return list(PB.code)

def Check_Dividend_Yield(context):
    EPS = get_fundamentals(query(
        income.code,
        income.day,
        income.basic_eps
    ))
    L = list(EPS.code)
    h = history(1, '1d', 'price', security_list=L, df=False)
    DY_stock = dict(zip(EPS['code'],EPS['basic_eps']))
    for stock in L:
        DY_stock[stock] = DY_stock[stock]/h[stock][0]
    DY_stock = sorted(DY_stock.iteritems(),key=lambda t:t[1],reverse=True)
    return DY_stock[:g.i]

def dapan_stoploss(context):
    ## 根据局大盘止损，具体用法详见dp_stoploss函数说明
    stoploss = dp_stoploss(kernel=2, n=10, zs=0.1)
    if stoploss:
        if len(context.portfolio.positions)>0:
            for stock in list(context.portfolio.positions.keys()):
                order_target(stock, 0)
        # return
        
def dp_stoploss(kernel=2, n=10, zs=0.03):
    '''
    方法1：当大盘N日均线(默认60日)与昨日收盘价构成“死叉”，则发出True信号
    方法2：当大盘N日内跌幅超过zs，则发出True信号
    '''
    # 止损方法1：根据大盘指数N日均线进行止损
    if kernel == 1:
        t = n+2
        hist = attribute_history('000300.XSHG', t, '1d', 'close', df=False)
        temp1 = sum(hist['close'][1:-1])/float(n)
        temp2 = sum(hist['close'][0:-2])/float(n)
        close1 = hist['close'][-1]
        close2 = hist['close'][-2]
        if (close2 > temp2) and (close1 < temp1):
            return True
        else:
            return False
    # 止损方法2：根据大盘指数跌幅进行止损
    elif kernel == 2:
        hist1 = attribute_history('000300.XSHG', n, '1d', 'close',df=False)
        if ((1-float(hist1['close'][-1]/hist1['close'][0])) >= zs):
            return True
        else:
            return False