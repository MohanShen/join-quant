# Clone from JoinQuant
# postId: 28bccac78066c35622a6afb2453c3164
# backtestId: 7902657197ad000c9243368d82e761cf
# title: 年化358%回撤6%强到让人怀疑的策略

#总体回测前要做的事情
def initialize(context):
    set_params()        #1设置策参数
    set_variables() #2设置中间变量
    set_backtest()   #3设置回测条件


#1
#设置策参数
def set_params():
    g.ANO = '101'
    g.tc=5  # 调仓频率
    g.yb=63  # 样本长度
    g.N=10   # 持仓数目
    
#2
#设置中间变量
def set_variables():
    g.t=0              #记录回测运行的天数
    g.if_trade=False   #当天是否交易
    
    
#3
#设置回测条件
def set_backtest():
    set_option('use_real_price', True)#用真实价格交易
    log.set_level('order', 'error')
    
    # 打开防未来函数
    set_option("avoid_future_data", True)
    # 关闭强制撮合功能
    set_option("match_by_signal", False) 


'''
================================================================================
每天开盘前
================================================================================
'''

#每天开盘前要做的事情
def before_trading_start(context):
    if g.t%g.tc==0:
        #每g.tc天，交易一次行
        g.if_trade=True 
        # 设置手续费与手续费
        set_slip_fee(context) 
        # 设置可行股票池：获得当前开盘的创业板指股票池并剔除当前或者计算样本期间停牌的股票
        #base_stocks = get_stocks()
        base_stocks = get_index_stocks('399006.XSHE')
        g.all_stocks = set_feasible_stocks(base_stocks,g.yb,context)
    g.t+=1
    
#4
# 设置可行股票池
# 过滤掉当日停牌的股票,且筛选出前days天未停牌股票
# 输入：stock_list为list类型,样本天数days为int类型，context（见API）
# 输出：list
def set_feasible_stocks(stock_list,days,context):
    # 得到是否停牌信息的dataframe，停牌的1，未停牌得0
    suspened_info_df = get_price(list(stock_list), start_date=context.current_dt, end_date=context.current_dt, frequency='daily', fields='paused')['paused'].T
    # 过滤停牌股票 返回dataframe
    unsuspened_index = suspened_info_df.iloc[:,0]<1
    # 得到当日未停牌股票的代码list:
    unsuspened_stocks = suspened_info_df[unsuspened_index].index
    # 进一步，筛选出前days天未曾停牌的股票list:
    feasible_stocks=[]
    current_data=get_current_data()
    for stock in unsuspened_stocks:
        if sum(attribute_history(stock, days, unit='1d',fields=('paused'),skip_paused=False))[0]==0:
            feasible_stocks.append(stock)
    return feasible_stocks
    
#5
# 根据不同的时间段设置滑点与手续费
def set_slip_fee(context):
    # 将滑点设置为0
    set_slippage(FixedSlippage(0)) 
    # 根据不同的时间段设置手续费
    dt=context.current_dt
    log.info(type(context.current_dt))
    
    if dt>datetime.datetime(2013,1, 1):
        set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5)) 
        
    elif dt>datetime.datetime(2011,1, 1):
        set_commission(PerTrade(buy_cost=0.001, sell_cost=0.002, min_cost=5))
            
    elif dt>datetime.datetime(2009,1, 1):
        set_commission(PerTrade(buy_cost=0.002, sell_cost=0.003, min_cost=5))
                
    else:
        set_commission(PerTrade(buy_cost=0.003, sell_cost=0.004, min_cost=5))

from jqlib.alpha101 import *

def get_stock_factor_values(date):
    no = g.ANO
    cmd = 'alpha_'+no+'(date, g.all_stocks)'
    df = eval(cmd)
    df = df.sort_values(ascending=False)
    return df
    
'''
================================================================================
每天交易时
================================================================================
'''

def handle_data(context, data):
    if g.if_trade==True:
    # 计算现在的总资产，以分配资金，这里是等额权重分配
        g.everyStock=context.portfolio.portfolio_value/g.N
        today = str(context.current_dt)[0:10]
        df = get_stock_factor_values(today)
        print(df)
        toBuy = df.index.values[:g.N]
        # 对于不需要持仓的股票，全仓卖出
        order_stock_sell(context,data,toBuy)
        # 对于不需要持仓的股票，按分配到的份额买入
        order_stock_buy(context,data,toBuy)
    g.if_trade=False    



#6
#获得卖出信号，并执行卖出操作
#输入：context, data，toBuy-list
#输出：none
def order_stock_sell(context,data,toBuy):
    #如果现有持仓股票不在股票池，清空
    list_position=context.portfolio.positions.keys()
    for stock in list_position:
        if stock not in toBuy:
            order_target(stock, 0)

#7
#获得买入信号，并执行买入操作
#输入：context, data，toBuy-list
#输出：none
def order_stock_buy(context,data,toBuy):
    # 对于不需要持仓的股票，按分配到的份额买入
    for i in range(0,len(g.all_stocks)):
        if indexOf(g.all_stocks[i],toBuy)>-1:
            order_target_value(g.all_stocks[i], g.everyStock)


#8
#查找一个元素在数组里面的位置，如果不存在，则返回-1
#输入：元素，对应数组
#输出：-1
def indexOf(e,a):
    for i in range(0,len(a)):
        if e==a[i]:
            return i
    return -1
