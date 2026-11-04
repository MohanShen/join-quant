# Clone from JoinQuant
# postId: 392d10761c1078db77ada49a39aa3fee
# backtestId: b17bc257081e405ca699d221d589dc89
# title: 社区总结一：传统多因子策略

import talib
import pandas as pd
import numpy as np
import math
import jqdata
import time,datetime
from jqdata import *
from jqfactor import neutralize
from prettytable import PrettyTable
from jqdata import finance
from jqfactor import get_factor_values
import warnings
#导入需要的数据库
from jqfactor import get_factor_values
from jqdata import finance


'''
================================================================================
总体回测前
================================================================================
'''
#总体回测前要做的事情
def initialize(context):
    set_params()      # 设置策参数
    set_variables()   # 设置中间变量
    set_backtest()    # 设置回测条件
    
#设置策略参数
def set_params():
    g.tc = 5          # 设置调仓天数
    g.stocknum = 5 # 持有股票数量

#设置中间变量
def set_variables():
    g.t = 0                # 记录回测运行的天数
    g.if_trade = False     # 当天是否交易
    g.hold_list = []       #当前持仓的全部股票    
    g.yesterday_HL_list = [] #记录持仓中昨日涨停的股票
    
#设置回测条件
def set_backtest():
    # 当前价格的百分比设置滑点
    #set_slippage(PriceRelatedSlippage(0.002))   
    # 设置对比基准
    set_benchmark('000300.XSHG') 
    # 使用真实价格
    set_option('use_real_price', True)
    # 设置报错等级
    log.set_level('order', 'error')
    run_daily(prepare_stock_list, '9:05')
    run_daily(market_open, time='9:30')
    
'''
================================================================================
每天开盘前
================================================================================
'''    
def prepare_stock_list(context):
    #获取已持有列表
    g.hold_list= []
    for position in list(context.portfolio.positions.values()):
        stock = position.security
        g.hold_list.append(stock)
    #获取昨日涨停列表
    if g.hold_list != []:
        df = get_price(g.hold_list, end_date=context.previous_date, frequency='daily', fields=['close','high_limit'], count=1, panel=False, fill_paused=False)
        df = df[df['close'] == df['high_limit']]
        g.yesterday_HL_list = list(df.code)
    else:
        g.yesterday_HL_list = []
        
def before_trading_start(context):
    if g.t%g.tc==0:
        #每g.tc天，交易一次
        g.if_trade=True 
        # 设置手续费
        set_slip_fee(context) 
    g.t += 1
    
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
    
    
'''
================================================================================
每天开盘时
================================================================================
'''    
def market_open(context):
    if g.if_trade == True:
        buy_stocks = select_stocks(context)
        if len(buy_stocks)!=0:
            for stock in buy_stocks:
                log.info(show_stock(stock))
            adjust_position(context, buy_stocks)
        else:
            long_positions_dict = context.portfolio.long_positions
            positions = [*long_positions_dict]
            for stock in positions:
                order_target_value(stock,0)
    g.if_trade = False
    

def filter_paused_and_st_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused 
    and not current_data[stock].is_st and 'ST' not in current_data[stock].
    name and '*' not in current_data[stock].name and '退' not in current_data[stock].name]
    
def filter_gem_stock(stock_list):
    #过滤创业板股票
    return [stock for stock in stock_list  if stock[0:3] != '300']
    
def filter_inno_stock(security_list) :
    #过滤科创板股票
    return [stock for stock in security_list if stock[0:3] != '688' and stock[0:3] != '787']
    # 返回结果
    
def filter_new_stock(context, stock_list):
    tmpList = []
    for stock in stock_list :
        days_public=(context.current_dt.date() - get_security_info(stock).start_date).days
        # 上市未超过1年
        if days_public > 365 :
            tmpList.append(stock)
    return tmpList

def filter_limit_stock(context,stock_list):
    #过滤涨停和跌停的股票
    tmpList = []
    curr_data = get_current_data()
    for stock in stock_list:
        # 未涨停，也未跌停
        if curr_data[stock].low_limit < curr_data[stock].day_open < curr_data[stock].high_limit:
            tmpList.append(stock)
    return tmpList

def getStockPrice(stock, interval): # 输入stock证券名，interval期
    h = attribute_history(stock, interval, unit='1d', fields=('close'), skip_paused=True)
    return (h['close'].values[0] , h['close'].values[-1])
    
def close_position(position):
    security = position.security
    order = order_target_value_(security, 0)  # 可能会因停牌失败
    if order != None:
        if order.status == OrderStatus.held and order.filled == order.amount:
            return True
    return False    
    
#获取北向资金持股比例数据
def get_HK_stocklist(context,date):
    stocklist_small =[]
    stocklist_big = []
    HK_link_id = [310001,310002]
    q = query(finance.STK_HK_HOLD_INFO.code,finance.STK_HK_HOLD_INFO.share_ratio).filter(
            finance.STK_HK_HOLD_INFO.link_id.in_(HK_link_id),finance.STK_HK_HOLD_INFO.day == date,
            finance.STK_HK_HOLD_INFO.share_ratio > 1).order_by(finance.STK_HK_HOLD_INFO.share_ratio.desc())
    df_HK_HOLD=finance.run_query(q)
    if df_HK_HOLD.empty:
        return (stocklist_small,stocklist_big)
    else: 
        stocklist = list(df_HK_HOLD['code'])
        # 过滤掉停牌的和ST的
        stocklist = filter_paused_and_st_stock(stocklist)
        stocklist = filter_new_stock(context, stocklist)
        stocklist = filter_limit_stock(context,stocklist)
        df_market_cap = get_fundamentals(query(valuation.code,valuation.market_cap).filter(
            valuation.code.in_(stocklist)
            #valuation.pb_ratio > 0,
            #indicator.inc_return > 0,
            #indicator.inc_total_revenue_year_on_year > 0,
            #indicator.inc_net_profit_year_on_year > 0
        ), date=date)
        df_market_cap = df_market_cap.set_index(['code'])
        #df_close_price = get_price(stocklist,end_date=date, frequency='daily', count = 1,fields=['close'],panel=False)
    
        #df_HK_HOLD['market_value'] = df_close_price['close']*df_HK_HOLD['share_number']
        df_HK_HOLD = df_HK_HOLD.set_index(['code'])
        df_HK_HOLD = df_HK_HOLD.join(df_market_cap)
        df_HK_HOLD = df_HK_HOLD.sort_values(by = 'market_cap')
        df_HK_HOLD =df_HK_HOLD.dropna(how='any',axis=0)
        
        
        stocklist_small = list(df_HK_HOLD.index)[:100]
        stocklist_big = list(df_HK_HOLD.index)[-100:]
        
        return (stocklist_small,stocklist_big)

def get_factor_data(stocklist,date):
    HK_link_id = [310001,310002]
    df_HK_HOLD = finance.run_query(query(finance.STK_HK_HOLD_INFO.code,finance.STK_HK_HOLD_INFO.share_number).filter(finance.STK_HK_HOLD_INFO.code.in_(stocklist),finance.STK_HK_HOLD_INFO.day == date)).T
    if df_HK_HOLD.empty:
        return pd.DataFrame(columns=[])
    else:
        df_HK_HOLD.columns = df_HK_HOLD.loc['code'].values
        df_HK_HOLD.drop(axis=0,labels=['code'],inplace=True)
        df_HK_HOLD.index = [date]
        df_close_price = get_price(stocklist,end_date=date, frequency='daily', count = 1,fields=['close'], skip_paused=False, fq='pre', panel=True)['close']
        factor_data=df_HK_HOLD * df_close_price #持股数量与收盘股价相乘得出北向资金持股市值
        stock_list = factor_data.T.sort_index(by = date).index.values.tolist()[-g.stocknum:]  
        return stock_list
        
        
def get_factor_filter_list(date,stock_list,jqfactor_list):
    df = pd.DataFrame(index = stock_list)
    
    for jqfactor in jqfactor_list:
        score_list = get_factor_values(stock_list,jqfactor,end_date = date,
          count=1)[jqfactor].ix[0].tolist()
        df[jqfactor] = score_list
        df.dropna(inplace = True)
        if jqfactor == 'book_to_price_ratio':
            factor = df.sort_values(by=jqfactor,ascending=True)[jqfactor]
        else:
            factor = df.sort_values(by=jqfactor,ascending=False)[jqfactor]
        single_groupnum = int(len(factor)/10)
        factor = pd.DataFrame(factor)
        factor[jqfactor + "score"] = 0
        for i in range(10):
            if i == 9:
                factor[jqfactor + "score"][i * single_groupnum:] = i + 1
            factor[jqfactor + "score"][i * single_groupnum:(i + 1) * single_groupnum] = i + 1
        df = pd.concat([df, factor[jqfactor + "score"]], axis=1)
        
    sum_score = df[['residual_volatilityscore','share_turnover_monthlyscore','book_to_price_ratio']].sum(1).sort_values()
    
    stocklist_small = sum_score[-g.stocknum:].index
    #filter_list=list(df.code)[0:int(g.percentile*len(stock_list))]
    return stocklist_small
        
        

def select_stocks(context):
    '''
    if get_growth_rate(g.index,10) < 0.01:
        print('沪深300指数近10日涨幅小于1%，空仓')
        stock_list = []
        return stock_list
    elif get_growth_rate(g.index,10) >= 0.01:
        print('沪深300指数近10日涨幅大于等于1%，开仓')
    '''
    Yesterday = context.previous_date
    stocklist_small,stocklist_big = get_HK_stocklist(context,Yesterday)
    
    
    momentum_small = []
    momentum_big = []
    a,b = 0,0
    for stock in stocklist_small:
        interval,Yesterday = getStockPrice(stock, 20) 
        stock_momentum = Yesterday / interval - 1 
        momentum_small.append(stock_momentum)
        a += stock_momentum
    
    for stock in stocklist_big:
        interval,Yesterday = getStockPrice(stock, 20) 
        stock_momentum = Yesterday / interval - 1
        momentum_big.append(stock_momentum)
        b += stock_momentum
    Yesterday = context.previous_date
    #stocklist_small,stocklist_big = get_HK_stocklist(context,Yesterday)
    print(a,b)
    if len(momentum_small) ==0 or len(momentum_big) == 0:
        print('无数据不交易')
        stock_list = []
        return stock_list
    else:
        avg_momentum_small = a/len(momentum_small)
        avg_momentum_big = b/len(momentum_big)
        
        if avg_momentum_small>avg_momentum_big:
            jqfactor_list = ['residual_volatility','share_turnover_monthly','book_to_price_ratio']
            stocklist_small = get_factor_filter_list(Yesterday,stocklist_small,jqfactor_list)
            #rv_list = get_factor_filter_list(Yesterday,stm_list,'residual_volatility')
            #df_small = get_price(rv_list,end_date=Yesterday, frequency='daily',count=1)['close']
            #df_small.index = ['close']
            #df_small = df_small.sort_index(axis = 1,by = 'close')
            #cols = [x for i,x in enumerate(df_small.columns) if df_small.iat[0,i]<2]
            #df_small = df_small.drop(cols,axis=1)
            #stocklist_small = list(df_small.columns.values)
            
            return stocklist_small
        else:
            stocklist_big = get_factor_data(stocklist_big,Yesterday)
            return stocklist_big



def adjust_position(context, buy_stocks):
    # 现持仓的股票，如果不在“目标池”中，且未涨停，就卖出
    if len(context.portfolio.positions)>0:
        last_prices = history(1, '1m', 'close', security_list=list(context.portfolio.positions.keys()))
        for stock in list(context.portfolio.positions.keys()):
            if stock not in buy_stocks :
                curr_data = get_current_data()
                if last_prices[stock][-1] < curr_data[stock].high_limit:
                    order_target_value(stock, 0)
    # 依次买入“目标池”中的股票            
    for stock in buy_stocks:
        
        g.buy_stock_count = len(buy_stocks)
        value = context.portfolio.total_value / g.buy_stock_count
        if context.portfolio.positions[stock].total_amount == 0:
            order_target_value(stock, value)
            
def check_limit_up(context):
    now_time = context.current_dt
    if g.yesterday_HL_list != []:
        #对昨日涨停股票观察到尾盘如不涨停则提前卖出，如果涨停即使不在应买入列表仍暂时持有
        for stock in g.yesterday_HL_list:
            current_data = get_price(stock, end_date=now_time, frequency='1m', fields=['close','high_limit'], skip_paused=False, fq='pre', count=1, panel=False, fill_paused=True)
            if current_data.iloc[0,0] <    current_data.iloc[0,1]:
                log.info("[%s]涨停打开，卖出" % (stock))
                position = context.portfolio.positions[stock]
                close_position(position)
            else:
                log.info("[%s]涨停，继续持有" % (stock))
 
            
def show_stock(stock):
    '''
    获取股票代码的显示信息    
    :param stock: 股票代码，例如: '603822.SH'
    :return: str，例如：'603822 嘉澳环保'
    '''
    return u"%s %s" % (stock[:6], get_security_info(stock).display_name)


            


'''
# 策略看10天涨幅
def get_growth_rate(security, n = 10):
    lc = get_close_price(security, n)
    #c = data[security].close
    c = get_close_price(security, 1, '1m')

    if not isnan(lc) and not isnan(c) and lc != 0:
        return (c - lc) / lc
    else:
        log.error("数据非法, security: %s, %d日收盘价: %f, 当前价: %f" %(security, n, lc, c))
        return 0
        
# 获取前n个单位时间当时的收盘价
def get_close_price(security, n, unit='1d'):
    return attribute_history(security, n, unit, ('close'), True)['close'][0]

def shifttradingday(date,shift):
    #获取N天前的交易日日期
    # 获取所有的交易日，返回一个包含所有交易日的 list,元素值为 datetime.date 类型.
    tradingday = get_all_trade_days()
    print tradingday
    # 得到date之后shift天那一天在列表中的行标号 返回一个数
    shiftday_index = list(tradingday).index(date)+shift
    print shiftday_index
    # 根据行号返回该日日期 为datetime.date类型
    return tradingday[shiftday_index]

    
def get_portfolio_info_text(context,new_stocks,op_sfs=[0]):
    # new_stocks是需要持仓的股票列表
    sub_str = ''
    table = PrettyTable(["仓号","股票", "持仓", "当前价", "盈亏率","持仓比"])  
    for sf_id in range(len(context.subportfolios)):
        cash = context.subportfolios[sf_id].cash
        p_value = context.subportfolios[sf_id].positions_value
        total_values = p_value +cash
        if sf_id in op_sfs:
            sf_id_str = str(sf_id) + ' *'
        else:
            sf_id_str = str(sf_id)
        for stock in context.subportfolios[sf_id].long_positions.keys():
            position = context.subportfolios[sf_id].long_positions[stock]
            if sf_id in op_sfs and stock in new_stocks:
                stock_str = show_stock(stock) + ' *'
            else:
                stock_str = show_stock(stock)
            stock_raite = (position.total_amount * position.price) / total_values * 100
            table.add_row([sf_id_str,
                stock_str,
                position.total_amount,
                position.price,
                "%.2f%%"%((position.price - position.avg_cost) / position.avg_cost * 100), 
                "%.2f%%"%(stock_raite)]
                )
        if sf_id < len(context.subportfolios) - 1:
            table.add_row(['----','---------------','-----','----','-----','-----'])
        sub_str += '[仓号: %d] [总值:%d] [持股数:%d] [仓位:%.2f%%] \n'%(sf_id,
            total_values,
            len(context.subportfolios[sf_id].long_positions)
            ,p_value*100/(cash+p_value))
    print '子仓详情:\n' + sub_str + str(table)
    '''