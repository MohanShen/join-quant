# Clone from JoinQuant
# postId: 17412c3ce1cd0c6d8bcda3b8ee86e65a
# backtestId: 7bf683ae109443b160502ec0678c2a75
# title: 【牛年春节-策略比赛】在给定的股票池里程序化操作增强收益

# 克隆自聚宽文章：https://www.joinquant.com/post/31662
# 标题：任意股票稳定收益的风控系统
# 作者：曹经纬

# 导入函数库
from jqdata import *
from kuanke.wizard import *
import numpy as np
import pandas as pd
import talib
import datetime
import time
import requests
import json
import uuid


# 垃圾股
#g_special_symbol = ['000012.XSHE', '000024.XSHE', '000027.XSHE', '000028.XSHE', '000049.XSHE', '000063.XSHE', '000069.XSHE', '000089.XSHE', '000100.XSHE', '000157.XSHE']
# 普通股
#g_special_symbol = ['000001.XSHE', '600612.XSHG', '600600.XSHG', '600674.XSHG', '000513.XSHE', '600801.XSHG', '600884.XSHG', '600893.XSHG', '600703.XSHG', '600720.XSHG']
# 优质股
g_special_symbol = ['600519.XSHG', '000858.XSHE', '601318.XSHG', '000333.XSHE', '300750.XSHE', '600036.XSHG', '601888.XSHG', '002475.XSHE', '600276.XSHG', '601012.XSHG']
# 基金冲仓 2020年9月30日
#g_special_symbol = ['600519.XSHG', '000858.XSHE', '601318.XSHG', '000333.XSHE', '300750.XSHE', '600036.XSHG', '601888.XSHG', '002475.XSHE', '600276.XSHG', '601012.XSHG', '600887.XSHG', '601166.XSHG', '300760.XSHE', '600031.XSHG', '300059.XSHE', '000568.XSHE', '000651.XSHE', '603259.XSHG', '000661.XSHE', '300014.XSHE']


g_use_dapan_zhishun = True      # 是否使用大盘止损
g_use_yinzi_xuangu = True       # 是否使用因子选股
g_use_gegu_zeshi = True         # 是否使用个股择时
g_show_account_info = False     # 是否显示动态仓位和动态回撤


# 初始化函数，设定基准等等
def initialize(context):
    log.info('=============================================')
    log.info('%s initialize' % datetime_to_string(context.current_dt))
    
    set_benchmark(g_special_symbol[0] if len(g_special_symbol) == 1 else '000300.XSHG')
    set_option('use_real_price', True)
    log.info('初始函数开始运行且全局只运行一次')
    log.set_level('order', 'error')
    
    # 设置固定点差
    #set_slippage(FixedSlippage(0.02))
    
    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    
    
def after_code_changed(context):
    log.info('=============================================')
    log.info('%s after_code_changed' % datetime_to_string(context.current_dt))
    g.http_cookie = '%s#%s' % (str(uuid.uuid1()), datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    g.max_drawdown_rate = 0.0
    g.max_balance = 0
    g.buy_stock_count = max(1, len(g_special_symbol))

    
    unschedule_all()
    run_daily(timer_trade, time='14:40', reference_security='000300.XSHG')
    if g_show_account_info:
        run_daily(timer_show_account_info, time='14:40', reference_security='000001.XSHG')   
        
        
#----------+----------+----------+----------+----------+----------+----------+----------+    
class ReqOrderInfo():
    def __init__(self):
        self.action = ''
        self.strategy_id = 'joinquant_133232'
        self.symbol = ''
        self.side = 'long' # long short
        self.type = 'buy' # sell buy
        self.price = 0.0
        self.time = '1990-01-01 00:00:00'
        self.balance_rate = 0.1
        
        
class RspOrderInfo(object):
    def __init__(self):
        self.symbol = ''
        self.price_buy = 0.0
        self.price_sell = 0.0
        self.time = ''
        self.contract = ''
        self.strategy_id = ''
        self.order_id = ''
        self.type = 'buy'
        self.side = 'long'
        self.amount = 0
        self.turnover = 0.0
        self.enddate = datetime.date(1990, 1, 1)    
        
        
class QuoteInfo():
    def __init__(self):
        self.symbol = ''
        self.price = 0.0
        self.time = '1990-01-01 00:00:00'        


#----------+----------+----------+----------+----------+----------+----------+----------+        
def timer_show_account_info(context):
    vbalance = context.portfolio.total_value
    g.max_balance = max(g.max_balance, vbalance)
    drawdown = int((g.max_balance - vbalance) / g.max_balance * 100)
    turnover = int((context.portfolio.total_value - context.portfolio.available_cash) / context.portfolio.total_value * 100)
    record(动态回撤=drawdown, 仓位比例=turnover)


def timer_trade(context):
    check_out_lists = g_special_symbol
    check_out_lists = [symbol for symbol in check_out_lists if get_security_info(symbol).start_date < context.current_dt.date()]
    g.buy_stock_count = max(1, len(check_out_lists))
    
    if g_use_yinzi_xuangu:
        check_out_lists = check_for_financial_indicator(context, check_out_lists)
        
    if g_use_gegu_zeshi:
        #check_out_lists = [symbol for symbol in check_out_lists if RSI_judge_qujian(symbol, (50, 99), 90)]
        check_out_lists = [symbol for symbol in check_out_lists if check_for_rsi(symbol, 90, 50, 99, False)]
        
    # 大盘止损
    if g_use_dapan_zhishun:
        request = ReqOrderInfo()
        request.action = 'order'
        request.cookie = g.http_cookie
        request.time = datetime_to_string(context.current_dt)
        request.auth = '6985C4E4-5EA2-401A-A038-E4C6D51028A2-07DD8CBA-C695-4F21-8B52-9B87BE6B2F5F'
        
        ok, orders = get_held_order_from_http_server(context, request, 'http://47.115.155.199:12341')
        if not ok:
            log.info('%s 大盘预测[未知]' % datetime_to_string(context.current_dt))
        elif ok and len(orders) == 0:
            log.info('%s 大盘预测[下跌]' % datetime_to_string(context.current_dt))
            check_out_lists = []
        elif ok and len(orders) > 0:
            log.info('%s 大盘预测[上涨]' % datetime_to_string(context.current_dt))

    adjust_position(context, check_out_lists)    
    
    
#----------+----------+----------+----------+----------+----------+----------+----------+    
# RSI技术指标择时        
def check_for_rsi(symbol, period, rsi_min, rsi_max, show_rsi=False):
    hst = attribute_history(symbol, period + 1, '1d', ['close'], fq='post')
    close = hst['close'].tolist()
    if (math.isnan(close[0]) or math.isnan(close[-1])):
        return False
    
    rsi = talib.RSI(np.array(close), timeperiod=period)[-1]  
    if (show_rsi):
        record(RSI=rsi-rsi_min)  

    return (rsi_min < rsi < rsi_max)        


# 财务指标选股    
def check_for_financial_indicator(context, symbol_list):
    stmt = query(valuation.code).filter(
        valuation.circulating_market_cap > 0
    ).filter(
        valuation.code.in_(symbol_list)
    ).filter(
        valuation.market_cap > 0.1,                                                                                 # 市值 
        income.net_profit > 1e6,                                                                                    # 净利润
        #valuation.pe_ratio > 5, valuation.pe_ratio < 100,                                                           # 动态市盈率
        #indicator.inc_net_profit_year_on_year > 3, indicator.inc_net_profit_year_on_year < 300,                     # 净利润同比增长
        indicator.roe > 2, indicator.roe < 200,                                                                      # 净资产收益率，ROE大于国际标准的通胀率2%
        #indicator.gross_profit_margin > 10, indicator.gross_profit_margin < 100,                                    # 毛利率
        #balance.total_liability / balance.total_assets > 0.05, balance.total_liability / balance.total_assets < 0.8  # 负债率
    )
    
    check_out_lists = list(get_fundamentals(stmt).code)
    
    # 过滤: 三停（停牌、涨停、跌停）及st,*st,退市
    check_out_lists = filter_st_stock(check_out_lists)
    check_out_lists = filter_limitup_stock(context, check_out_lists)
    check_out_lists = filter_limitdown_stock(context, check_out_lists)
    check_out_lists = filter_paused_stock(check_out_lists)

    return check_out_lists       
    

#----------+----------+----------+----------+----------+----------+----------+----------+    
# 交易
def adjust_position(context, buy_list):
    buy(context, buy_list)
    sell(context, buy_list)

    
# 买入    
def buy(context, buy_list):
    for stock in buy_list:
        order_target_value(stock, context.portfolio.total_value / g.buy_stock_count, MarketOrderStyle())    
        
# 卖出        
def sell(context, buy_list):
    sell_list = [security for security in context.portfolio.positions.keys() if security not in buy_list]
    for stock in sell_list:
        order_target_value(stock, 0, MarketOrderStyle())
    
#----------+----------+----------+----------+----------+----------+----------+----------+
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


# 过滤涨停的股票
def filter_limitup_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    
    # 已存在于持仓的股票即使涨停也不过滤，避免此股票再次可买，但因被过滤而导致选择别的股票
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] < current_data[stock].high_limit]


# 过滤跌停的股票
def filter_limitdown_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] > current_data[stock].low_limit]

            
# 获取最近价格
def get_last_price(context, symbol, fq='post'):
    if get_current_data()[symbol].paused:
        log.info('%s 今日停牌' % symbol)
        return -1.0
    
    hst = attribute_history(symbol, 2, '1m', ['close'], fq=fq)
    close_list = hst['close'].tolist()
    if close_list is not None and len(close_list) >= 1:
        return close_list[-1]
    else:
        return -1.0


# 获取昨日收盘价        
def get_last_day_price(context, symbol, fq='post'):
    if get_current_data()[symbol].paused:
        log.info('%s 今日停牌' % symbol)
        return -1.0
    
    hst = attribute_history(symbol, 2, '1d', ['close'], fq=fq)
    close_list = hst['close'].tolist()
    if close_list is not None and len(close_list) >= 1:
        return close_list[-1]
    else:
        return -1.0        
        
        
def get_historical_price(context, symbol, vdatetime, fq='post'):
    hst = get_price(symbol, vdatetime, vdatetime, '1m', fields=None, skip_paused=True, fq=fq, count=None)
    close_list = hst['close']
    if close_list is not None and len(close_list) >= 1:
        return close_list[-1]
    else:
        return -1.0    
        


#----------+----------+----------+----------+----------+----------+----------+----------+
def get_held_order_from_http_server(context, request, url):
    httpclient = requests.session()
    url = '%s?action=get_held_order' % url
    vheaders = {'Content-Type': 'application/json'}
    vbody = json.dumps(request.__dict__)
    
    try:
        response = httpclient.post(url, headers=vheaders, data=vbody)
        response_dict_array = response.json()
    except:
        return False, []
    
    if response_dict_array is None:
        return True, []

    orders = []
    for response_dict in response_dict_array:
        vorder = RspOrderInfo()
        vorder.__dict__ = response_dict
        orders.append(vorder)
        
    return True, orders     
    

#----------+----------+----------+----------+----------+----------+----------+----------+
def datetime_to_string(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def datetime_to_datestring(dt):
    return dt.strftime("%Y-%m-%d")

def string_to_datetime(st):
    return datetime.datetime.strptime(st, "%Y-%m-%d %H:%M:%S")

def string_to_timestamp(st):
    return time.mktime(time.strptime(st, "%Y-%m-%d %H:%M:%S"))

def timestamp_to_string(sp):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(sp))

def datetime_to_timestamp(dt):
    return time.mktime(dt.timetuple())

def timestamp_to_struct(sp):
    return time.localtime(sp)
    