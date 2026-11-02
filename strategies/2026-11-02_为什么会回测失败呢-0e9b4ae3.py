# Clone from JoinQuant
# postId: 0e9b4ae3b63bba821ca95221afe7d997
# backtestId: b1b60acfa6609eb5521e839ad40ccb83
# title: 为什么会回测失败呢

# 克隆自聚宽文章：https://www.joinquant.com/post/1697
# 标题：【量化课堂】动量策略入门
# 作者：JoinQuant量化课堂

# 动量策略入门（Momentum Strategy）
# 2012-01-02 到 2016-06-30, ￥2000000, 每天

from jqdata import *

'''
================================================================================
总体回测前
================================================================================
'''
#总体回测前要做的事情
def initialize(context):
    set_params()    #1设置策参数
    set_variables() #2设置中间变量
    set_backtest()  #3设置回测条件

#1
#设置策略参数
def set_params():
    g.N = 30   # 设置收益率回测区间（天数）
    g.tc = 30  # 设置调仓天数
    g.num_stocks = 10  # 设置每次调仓选取的股票数量
    # 定义股票池，创业板指数成分股
    g.index='399006.XSHE'
    # 每次持股占股票池的比例
    g.ratio = 0.15

#2
#设置中间变量
def set_variables():
    g.t = 0 #记录回测运行的天数
    g.if_trade = False #当天是否交易

#3
#设置回测条件
def set_backtest():
    set_benchmark('000300.XSHG')
    set_option('use_real_price',True) # 用真实价格交易
    log.set_level('order','error')    # 设置报错等级




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
        # 设置可行股票池：获得当前开盘的沪深300股票池并剔除当前或者计算样本期间停牌的股票
        g.feasible_stocks = set_feasible_stocks(get_index_stocks(g.index),g.N,context)
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




'''
================================================================================
每天交易时
================================================================================
'''
def handle_data(context,data):
    if g.if_trade == True:
        # 依本策略的买入信号，得到应该买的股票列表
        MS_should_buy = buy_signal(context, data)
        # 计算现在的总资产，以分配资金，这里是等额权重分配 返回一个数
        MonPerStock=context.portfolio.portfolio_value/g.num_stocks
        # 得到当前持仓中可卖出的股票
        if len(context.portfolio.positions)>0:
            #当持仓不为零时，剔除持仓股票中停牌股即可 返回list
            holding = context.portfolio.positions
        else:
            # 当持仓为0时，可卖出股票为0 返回list
            holding = []
        # 对于不需要持仓的股票，全仓卖出
        for stock in holding:
            if stock not in MS_should_buy:
                order_target_value(stock, 0)
        # 对于需要持仓的股票，按分配到的份额买入
        for stock in MS_should_buy:
            order_target_value(stock, MonPerStock)
    g.if_trade = False

#6
# 依本策略的买入信号，得到应该买的股票列表
# 输入：context, data（见API）
# 输出：应该买的股票列表，list类型
def buy_signal(context, data):
    # 将昨天设置为收益率计算最后一天 返回datetime.date对象
    enddate = context.previous_date
    # 将昨日日期向前推g.N(这是个整数）得到收益率计算周期第一天 返回datetime.date对象
    startdate = ShiftTradingDay(enddate,-g.N)
    # 得到回测收益率的股票列表（由于上市、退市等因素，此列表与我们实际可交易股票有一定差异）返回list
    stocks = set_feasible_stocks(get_index_stocks(g.index),g.N,context)
    # 按收益率降序排列 返回list
    sorted_list = stock_ret(stocks,startdate,enddate,asc = False)
    # 截取最高的g.num_stocks个
    should_buy = sorted_list[0:g.num_stocks]
    return should_buy

#7
# 某一日的前shift个交易日日期 
# 输入：date为datetime.date对象(是一个date，而不是datetime)；shift为int类型
# 输出：datetime.date对象(是一个date，而不是datetime)
def ShiftTradingDay(date,shift):
    # 获取所有的交易日，返回一个包含所有交易日的 list,元素值为 datetime.date 类型.
    tradingday = get_all_trade_days()
    # 得到date之后shift天那一天在列表中的行标号 返回一个数
    shiftday_index = tradingday.index(date)+shift
    # 根据行号返回该日日期 为datetime.date类型
    return tradingday[shiftday_index]  

#8   
# 根据期间收益率（用前复权收盘价计算）给股票排名
# 输入：stock_list为list类型；startdate enddate为datetime.date对象；asc为布尔类型
# 输出：list类型
def stock_ret(stock_list,startdate,enddate,asc = False):
    # 得到回测区间内股票收盘价 返回dataframe
    log.info(startdate)
    log.info(enddate)
    df_close = get_price(list(stock_list),start_date = startdate, end_date = enddate)['close'].T
    # 删去空值 返回dataframe
    df_close = df_close.dropna(axis = 0)
    # 计算回测区间收益率 返回dataframe
    df_close['ret']=(df_close[enddate]-df_close[startdate])/df_close[startdate]
    #按收益率降序排列，获取股票代码，返回list
    stocks = df_close.sort('ret', ascending = asc).index
    # 返回股票代码list
    return stocks
    



'''
================================================================================
每天收盘后
================================================================================
'''
# 每日收盘后要做的事情（本策略中不需要）
def after_trading_end(context):
    return

