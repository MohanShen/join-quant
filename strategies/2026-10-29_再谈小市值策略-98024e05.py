# Clone from JoinQuant
# postId: 98024e05b191902c2e2d8b3e9cbdb1b9
# backtestId: 4f52458e884776944b7c444bd6445fb3
# title: 再谈小市值策略

# 将原日线KDJ策略改为周线KDJ策略，交易频率调整为每周一执行。

# 导入函数库
from jqlib.technical_analysis import *
from jqdata import *
import talib
from datetime import datetime, timedelta
from prettytable import PrettyTable 
import time

# 初始化函数，设定基准等等
def initialize(context):
    set_params()    #设置相关参数
    set_option("avoid_future_data", True) #去掉未来函数
    set_backtest(context)  #设置回测基本数据
    # 修改点1：交易频率改为每周一运行
    run_weekly(trade, weekday=1, time='9:30') # 每周一早上9:30运行

def set_params():
    g.buy_type='KDJ_WEEKLY' # 修改策略名称以示区别
    g.buy_stock_count =4
    g.refresh_rate=10
    g.weeks = 0
    g.stock_dic={}
    
def set_backtest(context):
    set_benchmark('000300.XSHG')        #将基准设置沪深300
    set_option('use_real_price', True)  #开启动态复权
      # 股票类交易手续费和滑点
    set_slip_fee(context)
    log.set_level('order', 'error')     #设定报错等级
def set_slip_fee(context):
    set_slippage(FixedSlippage(0.01))   #滑点为0.01
    dt=context.current_dt
    if dt>datetime(2013,1, 1):
        set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003, close_today_commission=0, min_commission=5), type='stock')
    else:
        set_order_cost(OrderCost(open_tax=0, open_commission=0.003,close_commission=0.003, close_tax=0.001,min_commission=5), type='stock')    
    
    
def paused_filter(security_list):
    current_data = get_current_data()
    security_list = [stock for stock in security_list if not current_data[stock].paused]
    return security_list    
    
def delisted_filter(security_list):
    current_data = get_current_data()
    security_list = [stock for stock in security_list if not '退' in current_data[stock].name]
    return security_list
    
def st_filter(security_list):
    current_data = get_current_data()
    security_list = [stock for stock in security_list if not current_data[stock].is_st]
    return security_list
def filterStock(stock_to_choose):
    stockpool = list(stock_to_choose['code'])
    stockpool = paused_filter(stockpool)
    stockpool = delisted_filter(stockpool)
    stockpool = st_filter(stockpool)  
    return stockpool
def  day_of_week(context):
    current_date = context.current_dt
    num = current_date.isoweekday()
   
    return num
def time_is_right(context,num):
    if num == day_of_week(context):
       
        return True
    return False
        
def trade(context):    
    buy_stocks =    select_buy_stock(context)
  
    sell_stock(context,buy_stocks)
    # 修改点2：删除原有的周五判断，因为run_weekly已限定为周一
    buy_stock(context,buy_stocks)
#过滤股票
def choose_stock():
    stock_to_choose = get_fundamentals(query(
        valuation.code, valuation.pe_ratio, 
        valuation.pb_ratio,valuation.market_cap, 
        indicator.eps, indicator.inc_net_profit_annual
    ).filter(
       
        valuation.pe_ratio.between(10,100),
    ).order_by(
        valuation.market_cap.asc()
    ).limit(
        100), date=None)    
    
       
    return stock_to_choose

#选择股票
def select_buy_stock(context):
    stock_to_choose = choose_stock()
    filter_list = filterStock(stock_to_choose)
    buy_list =[]
    for code in filter_list:
        if is_buy(context,code,60):
            buy_list.append(code)
       
    return buy_list

def is_buy(context,code,value):
    # 修改点3：获取当前日期对应的上周五日期
    # 策略在周一运行，我们需要获取上一个交易周结束日（上周五）的日期
    # 修复：get_trade_days返回的是数组，需要取第一个元素
    last_friday_list = get_trade_days(end_date=context.current_dt, count=1) # 默认获取最近一个交易日
    last_friday = last_friday_list[0] if len(last_friday_list) > 0 else context.current_dt
    
    # 确保获取到的是周五，如果不是，则向前查找直到周五
    while last_friday.weekday() != 4: # 4代表周五
        last_friday_list = get_trade_days(end_date=last_friday - timedelta(days=1), count=1)
        last_friday = last_friday_list[0] if len(last_friday_list) > 0 else last_friday - timedelta(days=1)
    
    # 获取上上周五的日期
    two_weeks_ago_friday_list = get_trade_days(end_date=last_friday - timedelta(days=7), count=1)
    two_weeks_ago_friday = two_weeks_ago_friday_list[0] if len(two_weeks_ago_friday_list) > 0 else last_friday - timedelta(days=7)
    
    while two_weeks_ago_friday.weekday() != 4:
        two_weeks_ago_friday_list = get_trade_days(end_date=two_weeks_ago_friday - timedelta(days=1), count=1)
        two_weeks_ago_friday = two_weeks_ago_friday_list[0] if len(two_weeks_ago_friday_list) > 0 else two_weeks_ago_friday - timedelta(days=1)
    
    # 修改点4：使用周线数据计算KDJ，unit='1w'
    # 计算上周五（T-1周）的周线KDJ
    k_value,d_value,j_value =KDJ(code, last_friday, N =13, M1=7, M2=5, unit = '1w', include_now = True, fq_ref_date = None)
    if k_value[code]>value and d_value[code] > value and j_value[code]>value :
        return False
    
    # 计算上上周五（T-2周）的周线KDJ
    k_value2,d_value2,j_value2 =KDJ(code, two_weeks_ago_friday, N =13, M1=7, M2=5, unit = '1w', include_now = True, fq_ref_date = None)
    
    # 买入条件：上周五KDJ三值均小于阈值，且上周五三值均大于上上周五（周线金叉雏形）
    if k_value2[code]<k_value[code] and d_value2[code]  < d_value[code] and j_value2[code] < j_value[code] :
        return True
    return False

def is_sell(context,code,value):
    # 修改点5：卖出逻辑同样使用周线数据
    # 获取上周五日期
    last_friday_list = get_trade_days(end_date=context.current_dt, count=1)
    last_friday = last_friday_list[0] if len(last_friday_list) > 0 else context.current_dt
    
    while last_friday.weekday() != 4:
        last_friday_list = get_trade_days(end_date=last_friday - timedelta(days=1), count=1)
        last_friday = last_friday_list[0] if len(last_friday_list) > 0 else last_friday - timedelta(days=1)
    
    # 获取上上周五日期
    two_weeks_ago_friday_list = get_trade_days(end_date=last_friday - timedelta(days=7), count=1)
    two_weeks_ago_friday = two_weeks_ago_friday_list[0] if len(two_weeks_ago_friday_list) > 0 else last_friday - timedelta(days=7)
    
    while two_weeks_ago_friday.weekday() != 4:
        two_weeks_ago_friday_list = get_trade_days(end_date=two_weeks_ago_friday - timedelta(days=1), count=1)
        two_weeks_ago_friday = two_weeks_ago_friday_list[0] if len(two_weeks_ago_friday_list) > 0 else two_weeks_ago_friday - timedelta(days=1)
    
    # 计算上周五（T-1周）的周线KDJ
    k_value,d_value,j_value =KDJ(code, last_friday, N =13, M1=7, M2=5, unit = '1w', include_now = True, fq_ref_date = None)
    # 卖出条件1：上周五KDJ任一值超过超买阈值
    if k_value[code]>value or d_value[code]  >value or j_value[code]>value :
        return True
    
    # 计算上上周五（T-2周）的周线KDJ
    k_value2,d_value2,j_value2 =KDJ(code, two_weeks_ago_friday, N =13, M1=7, M2=5, unit = '1w', include_now = True, fq_ref_date = None)
    # 卖出条件2：上周五KDJ任一值小于上上周五（周线出现走弱迹象）
    if k_value2[code]>k_value[code] or d_value2[code]  > d_value[code] or j_value2[code]> j_value[code] :
        return True
    return False
        
 #卖出的策略，只要不在buy_list里的都卖出
def sell_stock(context,buy_stocks):
    log.info("卖出股票") 
    for stock in list(context.portfolio.positions.keys()):
        log.info("卖出股票"+stock) 
        if is_sell(context,stock,115):
           order_target_value(stock, 0)
#这里完成股票的策略选择
def buy_stock(context,buy_stocks):
    for stock in buy_stocks:
        position_count = len(context.portfolio.positions)
        if g.buy_stock_count > position_count:
            value = context.portfolio.cash / (g.buy_stock_count - position_count)
            if context.portfolio.positions[stock].total_amount == 0:
                order_target_value(stock, value)
