# Clone from JoinQuant
# postId: 6cd8593d65463246232efbbb17b9963f
# backtestId: 9697cf659946c04ca182c76dfc67a8d2
# title: 求帮忙看一下我这个代码问题出在哪，出处是一个彼得林奇的PEG选股

import pandas as pd


def initialize(context):
    set_params()
    set_backtest()
    set_variables()
    
def set_params():
    g.tc = 15      #调仓天数
    g.num_stock = 10      # 每次调仓的最大股票数量
    
def set_variables():
    g.t = 0       #记录回测运行天数
    g.if_trade = False           # 当天是否交易
    
def set_backtest():
    set_option('use_real_price',True)
    log.set_level('order','warning')
    
def before_trading_start(context):
    if g.t % g.tc == 0:
        g.if_trade = True
        set_slip_fee(context)
        g.stocks = get_index_stocks('000300.XSHG')            #这个函数可以获取指数成份股
        g.feasible_stocks = set_feasible_stocks(g.stocks,context)        #设置可行股票池
    g.t += 1
    
def set_feasible_stocks(initial_stocks,context):
    paused_info = []
    current_data = get_current_data()
    for i in initial_stocks:
        paused_info.append(current_data[i].paused)     # 把停牌的股票放进列表里
    df_paused_info = pd.DataFrame({'paused_info':paused_info},index=initial_stocks)
    unsuspened_stocks = list(df_paused_info.index[df_paused_info.paused_info==False])
    return unsuspened_stocks
    

def set_slip_fee(context):
    set_slippage(FixedSlippage(0))
    dt = context.current_dt    
    if dt > datetime.datetime(2013,1,1):
        set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.0003, close_commission=0.0013, close_today_commission=0, min_commission=5),type='stock')
    else:
        set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.003, close_commission=0.004, close_today_commission=0, min_commission=5),type='stock')
        

def handle_data(context, data):
    if g.if_trade == 'True':
        #把买卖的股票先选好，然后执行买卖操作的函数全都执行
        list_to_buy = stocks_to_buy(context)
        list_to_sell = stocks_to_sell(context,list_to_buy)
        sell_operation(list_to_sell)
        buy_operation(context,list_to_buy)
    g.if_trade = False
    
def get_PEG(context,stock_list):
    q_PE_G = query(valuation.code,valuation.pe_ratio,indicator.inc_net_profit_year_on_year).filter(valuation.code.in_(stock_list))
    df_PE_G = get_fundamentals(q_PE_G)
    df_Growth_PE_G = df_PE_G[(df_PE_G.pe_ratio > 0)&(df_PE_G.inc_net_profit_year_on_year>0)]
    df_Growth_PE_G.dropna()
    Series_PE = df_Growth_PE_G.ix[:,'pe_ratio']
    Series_G = df_Growth_PE_G.ix[:,'inc_net_profit_year_on_year']
    Series_PEG = Series_PE / Series_G
    Series_PEG.index = df_Growth_PE_G.ix[:,0]
    df_PEG = pd.DataFrame(Series_PEG)
    return df_PEG
    
    
    
    
    
def stocks_to_buy(context):
    list_to_buy = []
    df_PEG = get_PEG(context,g.feasible_stocks)   #引用一个获取PEG的函数
    df_sort_PEG = df_PEG.sort(columns=[0],asscending=[1])    #对其进行排序
    for i in range(g.num_stocks):    #按照PEG从小到大的顺序取前十个股票
        if df_sort_PEG.ix[i,0] < 0.5:
            list_to_buy.append(df_sort_PEG.index[i])
    return list_to_buy
    
def stocks_to_sell(context,list_to_buy):
    list_to_sell = []
    for stock_sell in context.portfolio.positions:
        if stock_sell not in list_to_buy:
            list_to_sell.append(stock_sell)
    return list_to_sell
    
    
def sell_operation(list_to_sell):
    for stock_sell in list_to_sell:
        order_target_value(stock_sell,0)

def buy_operation(context,list_to_buy):
    for stock_sell in list_to_buy:
        #   为每个持仓股票分配资金
        g.capital_unit = context.portfolio.portfolio_value/len(list_to_buy)
        for stock_buy in list_to_buy:
            order_target_value(stock_buy,g.capital_unit)
            
def after_trading_end(context):
    return 
    
    
    
    
    
    

