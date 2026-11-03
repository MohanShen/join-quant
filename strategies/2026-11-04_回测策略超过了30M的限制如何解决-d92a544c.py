# Clone from JoinQuant
# postId: d92a544cd52d55a13e3e7bad138a3f44
# backtestId: d8149b226c80ac22df68083d741da5f9
# title: 回测策略超过了30M的限制如何解决

from __future__ import division
import datetime # 获取时间
from datetime import timedelta
from jqdata import *
import numpy as np
import pandas as pd
import statsmodels.api as sm

def set_param():
    # 交易设置
    g.stocknum = 4 # 理想持股数量
    g.bearpercent = 1 # 熊市仓位
    g.bearposition = True # 熊市是否持仓
    g.sellrank = 10 # 排名多少位之后(不含)卖出
    g.buyrank = 9 # 排名多少位之前(含)可以买入

    # 初始筛选
    g.tradeday = 300 # 上市天数
    g.increase1d = 0.087 # 前一日涨幅
    g.tradevaluemin = 0.01 # 最小流通市值 单位（亿）
    g.tradevaluemax = 1000 # 最大流通市值 单位（亿）
    g.pbmin = 0.01 # 最小市净率
    g.pbmax = 30 # 最大市净率

    # 排名条件及权重，正数代表从小到大，负数表示从大到小
    # 各因子权重：总市值，流通市值，最新价格，5日平均成交量，60日涨幅
    g.weights = [5,5,8,4,10]
    
    # 配置择时
    g.MA = ['000001.XSHG', 10] # 均线择时
    g.choose_time_signal = True # 启用择时信号
    g.threshold = 0.003 # 牛熊切换阈值
    g.buyagain = 5 # 再次买入的间隔时间
    
    g.signal=-1
    # 定义全局变量
    g.high=[]
    g.low=[]
    g.betas=[]
    g.r2s=[]
    g.to_hold=''
    
    #定义参数
    g.M=250
    g.N=18

# 获取股票n日以来涨幅，根据当前价计算
# n 默认20日
def get_growth_rate(security, n=20):
    lc = get_close_price(security, n)
    c = get_close_price(security, 1, '1m')
    
    if not isnan(lc) and not isnan(c) and lc != 0:
        return (c - lc) / lc
    else:
        log.error("数据非法, security: %s, %d日收盘价: %f, 当前价: %f" %(security, n, lc, c))
        return 0
        
def get_growth_rate60(security):
    price60d = attribute_history(security, 60, '1d', 'close', False)['close'][0]
    pricenow = get_close_price(security, 1, '1m')
    if not isnan(pricenow) and not isnan(price60d) and price60d != 0:
        return pricenow / price60d
    else:
        return 100

# 过滤涨停的股票
def filter_limitup_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    
    # 已存在于持仓的股票即使涨停也不过滤，避免此股票再次可买，但因被过滤而导致选择别的股票
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys() 
        or last_prices[stock][-1] < current_data[stock].high_limit]

# 获取前n个单位时间当时的收盘价
def get_close_price(security, n, unit='1d'):
    return attribute_history(security, n, unit, 'close')['close'][0]

# 平仓，卖出指定持仓
def close_position(security):
    order = order_target_value(security, 0) # 可能会因停牌或跌停失败
    if order != None and order.status == OrderStatus.held:
        g.sold_stock[security] = 0

# 清空卖出所有持仓
def clear_position(context):
    if context.portfolio.positions:
        log.info("==> 清仓，卖出所有股票")
        for stock in context.portfolio.positions.keys():
            close_position(stock)

# 过滤停牌股票
def filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]

# 过滤ST及其他具有退市标签的股票
def filter_st_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list 
        if not current_data[stock].is_st 
        and 'ST' not in current_data[stock].name 
        and '*' not in current_data[stock].name 
        and '退' not in current_data[stock].name]
        
# 过滤创业版股票
def filter_gem_stock(context, stock_list):
    # return [stock for stock in stock_list if stock[0:3] != '300']
    # return [stock for stock in stock_list if '300' not in  stock and '301' not in  stock]
    return [stock for stock in stock_list if stock[0:3] != '300' and stock[0:3] !='301']

# 过滤次新股
def filter_new_stock(context, stock_list):
    return [stock for stock in stock_list if (context.previous_date - datetime.timedelta(days=g.tradeday)) > get_security_info(stock).start_date]

# 过滤昨日涨幅过高的股票
def filter_increase1d(stock_list):
    return [stock for stock in stock_list if get_close_price(stock, 1) / get_close_price(stock, 2) < (1 + g.increase1d)]

# 过滤卖出不足buyagain日的股票
def filter_buyagain(stock_list):
    return [stock for stock in stock_list if stock not in g.sold_stock.keys()]

def get_stock_list(context):
    # 获得前一个交易日
    # print('context.current_dt.date',context.current_dt.date())
    last_tradeday=get_trade_days(start_date=None, end_date=context.current_dt.date(), count=2)
    # print('last_tradeday',last_tradeday)
    # print('last_tradeday[0]',last_tradeday[0])
    # medical_industry_code=get_index_stocks('399101.XSHE',date=last_tradeday[0])
    # print('medical_industry_code',medical_industry_code)
    # print('valuation.code',valuation.code)
    # df = get_fundamentals(query(valuation.code)).dropna()
    df = get_fundamentals(query(valuation.code).order_by(valuation.circulating_market_cap.asc()).limit(300)).dropna()
    # df = get_fundamentals(query(medical_industry_code).filter(valuation.pb_ratio.between(g.pbmin, g.pbmax)
    #     ).order_by(valuation.circulating_market_cap.asc()).limit(1000)).dropna()
    stock_list = list(df['code'])
    print('len(stock_list)1',len(stock_list))
    
    # 过滤创业板、ST、停牌、当日涨停、次新股、昨日涨幅过高
    stock_list = filter_gem_stock(context, stock_list)
    print('len(stock_list)2',len(stock_list))
    stock_list = filter_science_stock(context, stock_list)
    print('len(stock_list)3',len(stock_list))
    stock_list = filter_st_stock(stock_list)
    print('len(stock_list)4',len(stock_list))
    stock_list = filter_paused_stock(stock_list)
    print('len(stock_list)5',len(stock_list))
    # stock_list = filter_limitup_stock(context, stock_list)
    stock_list = filter_new_stock(context, stock_list)
    print('len(stock_list)6',len(stock_list))
    # stock_list = filter_increase1d(stock_list)
    # stock_list = filter_buyagain(stock_list)
    # 剔除黑名单
    blacklist=[]
    stock_list=[i for i in stock_list if i not in blacklist]
    print('len(stock_list)2',len(stock_list))
    return stock_list

# 过滤科创版股票
def filter_science_stock(context, stock_list):
    return [stock for stock in stock_list if stock[0:3] != '688']

# 调仓策略：控制在设置的仓位比例附近，如果过多或过少则调整
# 熊市时按设置的总仓位比例控制
def my_adjust_position(context, hold_stocks):

    for stock in context.portfolio.positions.keys():
        current_data = get_current_data()
        price1d = get_close_price(stock, 1)
        nosell_1 = context.portfolio.positions[stock].price >= current_data[stock].high_limit
        sell_2 = stock not in hold_stocks
        if sell_2 and not nosell_1:
            close_position(stock)

def mybuy(context):
    uu=[]
    for i in g.chosen_stock_list:
        # print(i)
        try:
            # print(cal_z(context,i))
            # dd.append(cal_z(context,i))
            if cal_z(context,i)==1:
                uu.append(i)
        except:
            # dd.append(0)
            continue
    # mm['signal']=dd
    # 获得可投资的个股
    # print('mm1',mm)
    # print('mm[mm.signal==1]',mm[mm.signal==1])
    # g.chosen_stock_list=[i for i in mm.code if list(mm[mm.code==i].signal)[0]==1]
    g.chosen_stock_list=uu
    print('chosen_stock_list)',len(g.chosen_stock_list))
    
        
    log.info("待买股票列表：%s" %(g.chosen_stock_list))
    # if g.choose_time_signal and (not g.isbull):
    #     free_value = context.portfolio.total_value * g.bearpercent
    #     minpercent = 0.7 / g.stocknum * g.bearpercent
    # else:
    free_value = context.portfolio.total_value
    #     minpercent = 0.7 / g.stocknum
    free_cash = free_value - context.portfolio.positions_value
    hold_stocks=[stock for stock in context.portfolio.positions.keys()]
    print('hold_stocks',hold_stocks)
    print(' g.chosen_stock_list', g.chosen_stock_list)
    if  len(g.chosen_stock_list)!=0:
        buycash = free_value / len(g.chosen_stock_list)
        [order_value(i, buycash) for  i in g.chosen_stock_list if i not in hold_stocks]
        # print('可买入股票',[i for i in g.chosen_stock_list if i  not  in hold_stocks])


def before_trading_start(context):
    for stock in list(g.sold_stock.keys()):
        if g.sold_stock[stock] >= g.buyagain - 1:
            del g.sold_stock[stock]
        else:
            g.sold_stock[stock] += 1
    g.chosen_stock_list = get_stock_list(context)
    set_slip_fee(context)
    print("已设置交易成本")

def myscheduler():
    set_param()
    unschedule_all()
    run_daily(gogogo, '14:00')
    run_daily(mybuy, '14:05')
    
def after_code_changed(context):
    myscheduler()

def initialize(context):
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    myscheduler()
    g.isbull = False # 是否牛市
    g.chosen_stock_list = [] # 存储选出来的股票
    g.nohold = True # 空仓专用信号
    g.sold_stock = {} # 近期卖出的股票及卖出天数

def gogogo(context):
    my_adjust_position(context, g.chosen_stock_list)
        
# 根据不同的时间段设置滑点与手续费
def set_slip_fee(context):
    # 将滑点设置为0
    set_slippage(FixedSlippage(0)) 
    # 根据不同的时间段设置手续费
    dt=context.current_dt
    if dt>datetime.datetime(2013,1, 1):
        set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5)) 
        
    elif dt>datetime.datetime(2011,1, 1):
        set_commission(PerTrade(buy_cost=0.001, sell_cost=0.002, min_cost=5))
            
    elif dt>datetime.datetime(2009,1, 1):
        set_commission(PerTrade(buy_cost=0.002, sell_cost=0.003, min_cost=5))
    else:
        set_commission(PerTrade(buy_cost=0.003, sell_cost=0.004, min_cost=5))
        
#获取之前N个交易日的日期
def get_before_after_trade_days(date, count, is_before=True):
    """
    date :查询日期
    count : 前后追朔的数量
    is_before : True , 前count个交易日  ; False ,后count个交易日

    返回 : 基于date的日期, 向前或者向后count个交易日的日期 ,一个datetime.date 对象
    """
    from jqdata import  get_trade_days
    import pandas as pd
    all_date = pd.Series(get_all_trade_days())
    if isinstance(date,str):
        all_date = all_date.astype(str)
    if isinstance(date,datetime.datetime):
        date = date.date()

    if is_before :
        return list(all_date[all_date< date].tail(count))
    else :
        return list(all_date[all_date>date].head(count))
        
# 计算当前Z值,计算周期值
def cal_z(context,stock):
    g.signal=-1
    # # 获得历史的beta和R Squared
    #取前M+N个交易日
    previouse_date=context.previous_date.strftime('%Y-%m-%d')
    dates=get_before_after_trade_days(previouse_date,g.M+g.N-1)
    # print(dates)
    start_date=dates[0]
    #取数据
    data=get_bars(stock,count=len(dates),
        unit='1d',fields=['high','low'],end_dt=previouse_date
        ,df=True)
    g.low=list(data['low'])
    g.high=list(data['high'])
    for i in range(g.N-1,len(dates)):
        #计算beta
        tmp_low=g.low[i-g.N+1:i+1]
        # print('tmp_low',tmp_low)
        tmp_high=g.high[i-g.N+1:i+1]
        x=sm.add_constant(tmp_low)#sm.add_constant ()。它会在一个 array 左侧加上一列 111
        # print('x',x)
        # 建立回归模型
        model=sm.OLS(tmp_high,x)
        results=model.fit()
        # print('results',results)
        g.betas.append(results.params[1])#获得betas值
        g.r2s.append(results.rsquared)#模型的拟合度(R Squared)
    # print('g.low',g.low)
    # print('g.high',g.high)
        
    data=attribute_history(stock, 1, '1m', ['high','low'])
    # print('data',data)
    # data=get_price(stock,end_date=previouse_date,count=1,
    #     frequency='1m',fields=['high','low'])
    # print('data2',data)
    g.high.append(data.iloc[0]['high'])
    g.low.append(data.iloc[0]['low'])
    #计算当日beta
    tmp_low=g.low[-g.N+1:]
    tmp_high=g.high[-g.N+1:]
    x=sm.add_constant(tmp_low)
    model=sm.OLS(tmp_high,x)
    results=model.fit()
    g.betas.append(results.params[1])
    g.r2s.append(results.rsquared)
    #计算标准分
    mean=np.mean(g.betas[-g.M:])
    sigma=np.std(g.betas[-g.M:])
    zscore=(g.betas[-1]-mean)/sigma
    z=zscore*g.betas[-1]*g.r2s[-1]
    signal=g.signal
    if z>0.7:
        signal=1
    if z<-0.7:
        signal=-1
    return signal