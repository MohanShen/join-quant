# Clone from JoinQuant
# postId: 857c716760cf1d6ebec0905c0c9b9774
# backtestId: 07d10dfc1e76d186e5dd162224deef3b
# title: 有没有人帮忙修改策略的

# 克隆自聚宽文章：https://www.joinquant.com/post/42297
# 标题：首板突破300天排板战法
# 作者：游资小码哥

# 克隆自聚宽文章：https://www.joinquant.com/post/34053
# 标题：对 二板排板战法 的部分优化
# 作者：xloong

# 二板排板战法研究-游资小码哥
# https://www.joinquant.com/view/community/detail/25e48a8c5048bc2d02f785aeb913afd4?type=1
# 导入函数库
# enable_profile()
from jqdata import *
import pandas as pd
from six import BytesIO

# 初始化函数，设定基准等等
def initialize(context):
   # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    set_option("match_by_signal", True) # # 强制撮合，仅支持限价单。使用限价单进行委托时将不对委托价格和成交数量进行任何检查而直接成交

    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')
    # g 内置全局变量
    g.my_security = '510300.XSHG'
    set_universe([g.my_security])
    g.help_stock = []
    g.help_stock_have = []
    
    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    
    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
      # 开盘前运行
    run_daily(before_market_open, time='before_open', reference_security='000300.XSHG')
      # 开盘时运行
    run_daily(market_run, time='every_bar', reference_security='000300.XSHG')

    run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')
    
    
def function_buy(stock, cash, context):
    stock_owner = context.portfolio.positions
    open_cash = 0
    orders = ''
    if len(stock_owner) == 0:
        open_cash = cash / 2
    elif len(stock_owner) == 1:
        open_cash = cash
    print("1."+stock+"买入金额"+str(open_cash))
    if stock not in stock_owner and open_cash > 20000:
        orders = order_value(stock, open_cash)
    return orders
    
# def function_buy(stock, cash, context):
#     stock_owner = context.portfolio.positions
#     open_cash = 0
#     orders = ''
#     if len(stock_owner) == 0:
#         open_cash = cash / 4
#     elif len(stock_owner) == 1:
#         open_cash = cash / 3
#     elif len(stock_owner) == 2:
#         open_cash = cash / 2
#     elif len(stock_owner) == 3:
#         open_cash = cash
#     print("1."+stock+"买入金额"+str(open_cash))
#     if stock not in stock_owner and open_cash > 20000:
#         orders = order_value(stock, open_cash)
#     return orders
            
# 开盘时运行函数
def market_run(context):
    #log.info('【market_run】')
    time_now = context.current_dt.strftime('%H:%M:%S')
    now = context.current_dt
    zeroToday = now - datetime.timedelta(hours=now.hour, minutes=now.minute, seconds=now.second,microseconds=now.microsecond)
    lastToday = zeroToday + datetime.timedelta(hours=9, minutes=31, seconds=00)
    cash = context.portfolio.available_cash
    pre_date =  (context.current_dt + timedelta(days = -1)).strftime("%Y-%m-%d")
    gc_data = get_current_data()
    # log.info(now) # 当前对应分钟
    if len(g.help_stock) > 0 and time_now>='09:30:00':
        for stock in g.help_stock:
            # log.info(df_panel_all['close'][stock].values)
            if(cash > 5000):
                gc_stock = gc_data[stock]
                current_price = gc_stock.last_price
                day_open_price = gc_stock.day_open
                day_high_limit = gc_stock.high_limit 
                df_panel = get_price(stock, count = 1,end_date=pre_date, frequency='daily', fields=['open', 'high', 'close','low', 'high_limit','money','pre_close'])
                pre_high = df_panel['high'].values
                pre_close = df_panel['close'].values
                pre_open = df_panel['open'].values
                pre_high_limit = df_panel['high_limit'].values
                # 当天分钟级 最高最低
                df_panel_all = get_price(
                    stock, 
                    start_date=lastToday, 
                    end_date=context.current_dt, 
                    frequency='minute', 
                    fields=['high','low','close','high_limit','money','volume']
                )
                df_min_low_all = df_panel_all.loc[:,"close"].min()
                df_max_high_all = df_panel_all.loc[:,"close"].max()
                money_all = df_panel_all.loc[:,"money"].sum()
                volume_all = df_panel_all.loc[:,"volume"].sum()
                #分时均价线
                minute_price = money_all / (volume_all+0.0001)
                count_limit = (df_panel_all.loc[:,'close'] == df_panel_all.loc[:,'high_limit']).sum() 
                df_panel_three = get_price(stock, count = 3, end_date=context.current_dt, frequency='minute', fields=['close','high_limit','money','volume'])
                low_allday_three = df_panel_three.loc[:,"close"].min()
                
                df_panel_3 = get_price(stock, count = 3,end_date=pre_date, frequency='daily', fields=['open', 'close','high_limit','money','low'],skip_paused=True)
                sum_plus_max_3 = (df_panel_3.loc[:,'close'] == df_panel_3.loc[:,'high_limit']).sum()
                
                # if time_now <= '09:50:00' and count_limit >= 3:
                #     print("去掉早上涨停的票"+str(stock))
                #     g.help_stock.remove(stock)
                #     g.help_stock_have.append(stock)
                
                if  df_min_low_all < day_high_limit and count_limit >= 10 and count_limit <= 20 and current_price == day_high_limit:
                    #open_cash = cash / len(g.help_stock) and day_open_price <  day_high_limit
                    print(stock+" 1.买入金额 "+str(cash))
                    function_buy(stock, cash, context)
                    g.help_stock.remove(stock)
                    g.help_stock_have.append(stock)

    if len(context.portfolio.positions):
        stock_owner = context.portfolio.positions
        for stock_two in stock_owner:
            if context.portfolio.positions[stock_two].closeable_amount > 0:
                current_price = gc_data[stock_two].last_price
                day_open_price = gc_data[stock_two].day_open
                day_high_limit = gc_data[stock_two].high_limit 
                day_low_limit = gc_data[stock_two].low_limit 
                df_panel = get_price(stock_two, count = 1,end_date=pre_date, frequency='daily', fields=['open', 'high', 'close','low', 'high_limit','money','pre_close'])
                pre_high = df_panel['high'].values
                pre_high_limit = df_panel['high_limit'].values
                pre_close = df_panel['close'].values
                pre_low = df_panel['low'].values
                date_init = context.portfolio.positions[stock_two].init_time
                str_date_init =  (date_init + timedelta(days = 2)).strftime("%Y-%m-%d")
                str_current_dt =  (context.current_dt).strftime("%Y-%m-%d")
                #查询当天的最高价
                df_panel_allday = get_price(
                    stock_two, 
                    start_date=lastToday, 
                    end_date=context.current_dt, 
                    frequency='minute', 
                    fields=['high','low','close','high_limit','money']
                )
                # low_allday = df_panel_allday.loc[:,"low"].min()
                high_allday = df_panel_allday.loc[:,"high"].max()
                #平均持仓成本
                cost = context.portfolio.positions[stock_two].avg_cost
                
                count_limit_allday = (df_panel_allday.loc[:,'close'] == df_panel_allday.loc[:,'high_limit']).sum() 
                
                df_before10 = df_panel_allday.iloc[:10]
                count_limit_before10 = (df_before10.loc[:,'close'] == df_before10.loc[:,'high_limit']).sum() 
                
                # print("----------------------------------")
                if current_price >= cost * 2 and current_price > day_low_limit: # and current_price < day_open_price
                    print("1.卖出股票：小于最高价0.97倍"+str(stock_two))
                    order_target(stock_two, 0)
                elif current_price <  cost * 0.92 and current_price < day_open_price and  pre_close == pre_high_limit and current_price > day_low_limit:
                    print("2.卖出股票：亏了3个点"+str(stock_two))
                    order_target(stock_two, 0)
                elif current_price <  cost * 0.97 and current_price < day_open_price and time_now >= '09:35:00' and  pre_close < pre_high_limit and current_price > day_low_limit:
                    print("2.卖出股票：亏了3个点"+str(stock_two))
                    order_target(stock_two, 0)
                elif current_price <  day_high_limit * 0.96 and time_now >= '14:30:00' and current_price > day_low_limit:
                    print("3.卖出股票：亏了7个点"+str(stock_two))
                    order_target(stock_two, 0)
                # elif day_open_price <  pre_close * 0.98 and current_price < pre_close * 0.99 and time_now >= '10:00:00' and current_price >= cost * 1.2 and current_price < high_allday * 0.98:
                #     print("4.卖出股票：亏了7个点")
                #     order_target(stock_two, 0)
                # elif day_open_price <  pre_close * 1.01 and day_open_price >  pre_close * 0.99 and time_now >= '09:45:00' and current_price <= day_open_price * 0.98 and current_price < high_allday * 0.98:
                #     print("5.卖出股票：点"+str(stock_two))
                #     order_target(stock_two, 0)
                elif high_allday ==  day_high_limit and count_limit_allday > 30 and current_price < day_high_limit and day_open_price < day_high_limit * 0.95 and count_limit_before10 >= 2:
                    print("6.卖出股票："+str(stock_two))
                    order_target(stock_two, 0)
                elif day_open_price <  pre_close * 0.97 and current_price < day_open_price and pre_close < pre_high_limit:
                    print("7.卖出股票：开盘价太低"+str(stock_two))
                    order_target(stock_two, 0)
                elif day_open_price < pre_close * 0.99 and current_price < day_open_price:
                    print("8.卖出股票："+str(stock_two))
                    order_target(stock_two, 0)
                elif day_open_price > pre_close * 1.045 and current_price < high_allday * 0.97 and day_open_price < day_high_limit:
                    print("9.卖出股票："+str(stock_two))
                    order_target(stock_two, 0)
                elif day_open_price > pre_close * 1.045 and current_price < day_open_price and time_now <= '09:33:00':
                    print("10.卖出股票："+str(stock_two))
                    order_target(stock_two, 0)
                elif high_allday > pre_close * 1.045 and day_open_price < pre_close * 1.03 and high_allday > day_open_price * 1.03 and current_price < high_allday and current_price <= cost * 1.1 and time_now <= '09:40:00':
                    print("11.卖出股票："+str(stock_two))
                    order_target(stock_two, 0)

        
# 开盘前运行函数 选择二板放量股 并且横盘震荡
def before_market_open(context):
    date_now = (context.current_dt+ timedelta(days = -1)).strftime("%Y-%m-%d")#'2021-01-15'#datetime.datetime.now()
    yesterday = (context.current_dt + timedelta(days = -360)).strftime("%Y-%m-%d")
    trade_date = get_trade_days(start_date=yesterday, end_date=date_now, count=None)
    ##查询所有股票的当天的涨停板
    stocks = list(get_all_securities(['stock']).index)
    end_date=trade_date[trade_date.size-1]
    pre_date=trade_date[trade_date.size-2]
    pre_date_10=trade_date[trade_date.size-10]
    pre_date_20=trade_date[trade_date.size-20]
    pre_date_40=trade_date[trade_date.size-40]
    pre_date_150=trade_date[trade_date.size-150]
    # log.info(trade_date.size) # 21 
    log.info(trade_date[trade_date.size-1])
    stock_list = stocks
    ##去除st的连板股票
    stock_list = filter_st(stock_list)
    ##查询所有股票的当天的涨停板
    # 耗时
    tmpList_limit = get_future_function(context,stock_list)
    tmpList_day = filter_stock_by_days(context,tmpList_limit,30)
    tmpList = pick_high_limit(tmpList_day,context,end_date,pre_date,pre_date_10)
    #print(tmpList_limit)
    #未来函数，便于测试----------------------------------------
    
    # print("--------------")
    # print(stock_tmp)  
    
    ##筛选上市时间大于1080天的股票
    
    
    for stock_flat in tmpList:
        g.help_stock.append(stock_flat)
    print("----------------最后被选出的股票-----------")
    print(len(g.help_stock))
    print(g.help_stock)

def get_future_function(context,stocks):
    date_now = (context.current_dt).strftime("%Y-%m-%d")
    
    df_panel = get_price(stocks, count = 1,end_date=date_now, frequency='daily', fields=['open', 'close','high_limit','high','money','pre_close','low'])
    df_high = df_panel['high']
    df_high_limit = df_panel['high_limit']
    high_limit_stock = []
    for stock in (stocks):
        if(stock[0:2] == '30' or stock[0:2] == '68'):
            continue
        
        _high_limit = (df_high_limit[stock].values)
        _high = (df_high[stock].values)
        if _high == _high_limit:
            high_limit_stock.append(stock)
    return high_limit_stock
    



# 选出打板的股票
def pick_high_limit(stocks,context,end_date,pre_date,pre_date_10):
    log.info('【pick_high_limit】')
    # 耗时
    df_panel = get_price(stocks, count = 1,end_date=end_date, frequency='daily', fields=['open', 'close','high_limit','money','pre_close','low'])
    df_close = df_panel['close']
    # log.info(df_close)
    df_open = df_panel['open']
    df_high_limit = df_panel['high_limit']
    df_low = df_panel['low']
    df_money = df_panel['money']
    df_pre_close = df_panel['pre_close']
    high_limit_stock = []
    for stock in (stocks):
        if(stock[0:2] == '30' or stock[0:2] == '68' or stock == 'nan'):
            continue
        _high_limit = (df_high_limit[stock].values)
        _close = (df_close[stock].values)
        _open = (df_open[stock].values)
        _pre_close = (df_pre_close[stock].values)
        _low = (df_low[stock].values)
        
        df_panel_50 = get_price(stock, count = 50,end_date=end_date, frequency='daily', fields=['open', 'close','high_limit','money','low'],skip_paused=True)
        sum_plus_max_50 = (df_panel_50.loc[:,'close'] == df_panel_50.loc[:,'high_limit']).sum()
        low_allday_50 = df_panel_50.loc[:,"close"].min()
        high_alldayy_50 = df_panel_50.loc[:,"close"].max()
        rate_50 = (high_alldayy_50 - low_allday_50) / low_allday_50
        
        df_panel_500 = get_price(stock, count = 300,end_date=end_date, frequency='daily', fields=['open', 'close','high_limit','money','low'],skip_paused=True)
        sum_plus_max_500 = (df_panel_500.loc[:,'close'] == df_panel_500.loc[:,'high_limit']).sum()
        #print(stock)
        # time_high = df_panel_500.dropna()['close'].idxmax()
        # df_panel_500.drop(index=time_high, inplace=True,axis=0)

        low_allday_500 = df_panel_500.loc[:,"close"].min()
        high_alldayy_500 = df_panel_500.loc[:,"close"].max()
        rate_500 = (high_alldayy_500 - low_allday_500) / low_allday_500
        df_panel_10 = get_price(stock, count = 10,end_date=end_date, frequency='daily', fields=['open', 'close','high_limit','money','low'],skip_paused=True)
        sum_plus_max_10 = (df_panel_10.loc[:,'close'] == df_panel_10.loc[:,'high_limit']).sum()
        high_allday_10 = df_panel_10.loc[:,"open"].max()
        low_allday_10 = df_panel_10.loc[:,"close"].min()
        rate_10 = (high_allday_10 - low_allday_10) / low_allday_10
        if stock == '002077.XSHE':
            print("--------high_alldayy_500----------")
            print(rate_10)
            #print(sum_plus_max_50)
            # print(_close * 1.2 > high_alldayy_500)
            # print(_close * 1.2 > high_allday_10)
            # print(_close < _high_limit)
            # print(sum_plus_max_50 <= 5)
            # print(sum_plus_max_10 <= 1)
            # print(df_panel_50[df_panel_50.loc[:,'close'] == df_panel_50.loc[:,'high_limit']])
        if _close * 1.2 > high_alldayy_500 and _close * 1.2 > high_alldayy_50 and _close * 1.1 > high_allday_10 and _close < _high_limit and rate_500 < 2 and rate_10 <= 0.5:
            high_limit_stock.append(stock)
    return high_limit_stock
#去除st的股票
def filter_st(codelist):
    current_data = get_current_data()
    codelist = [code for code in codelist if not current_data[code].is_st]
    return codelist

#过滤上市时间不满1080天的股票
def filter_stock_by_days(context, stock_list, days):
    tmpList = []
    for stock in stock_list :
        days_public=(context.current_dt.date() - get_security_info(stock).start_date).days 
        market_cap = get_circulating_market_cap(stock)
        market_cap_num = market_cap['circulating_market_cap'].values
        if days_public > days and market_cap_num < 150:
            tmpList.append(stock)
    return tmpList

# 获取个股流通市 值数据
def get_circulating_market_cap(stock_list):
    query_list = [stock_list]
    q = query(valuation.code,valuation.circulating_market_cap).filter(valuation.code.in_(query_list))
    market_cap = get_fundamentals(q)
    market_cap.set_index('code', inplace=True)
    return market_cap


## 收盘后运行函数
def after_market_close(context):
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    g.help_stock = []
    print("当天有多少"+str(len(g.help_stock_have)))
    print(g.help_stock_have)
    print("g.help_stock-重置之后---------------")
    print(g.help_stock)
    g.help_stock_have = []
    log.info('一天结束')
    log.info('##############################################################')


