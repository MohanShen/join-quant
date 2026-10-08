# Clone from JoinQuant
# postId: 45fbd57db3ecc0e203a08c45defb4c87
# backtestId: f9a301de414880a3d8ae5f961012aa61
# title: 高股息低估值策略的上限在哪里？

# 克隆自聚宽文章：https://www.joinquant.com/post/45552
# 标题：高股息低市盈率高增长的价投策略
# 作者：芹菜1303

# 克隆自聚宽文章：https://www.joinquant.com/post/45552
# 标题：高估计低市盈率高增长的价投策略
# 作者：芹菜1303

'''
0、股票筛选所有股票，去科创板和北交所，去ST，去上市未满300天；
1、股票筛选和排序：最近3年平均分红股息率最大10%的股票，按分红/股价 从大到小排序；（股价上涨，会导致排名下跌）
2、股票筛选：PEG在0.08-2之间，市盈率：0~20之间，净资产收益率>3%,营业收入同比增长率>5%,净资产同比增长>11%;（股价上涨到PE超过25就会跌出股票池）
3、选取的股票：去停牌，去昨天涨停的，取前10个股票做为买入股票池（股价）
4、执行频率每月执行一次；
5、每天执行的是：如果昨天是涨停的，今天没有涨停，则卖出；
'''
import pandas as pd
import datetime
from jqdata import *


# 在聚宽策略代码里加代码

 


def initialize(context):
    set_benchmark('000300.XSHG') #000905.XSHG
    log.set_level('order', 'error')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)# 设置是否开启避免未来数据模式
    #set_slippage(FixedSlippage(0.02))# 设置滑点    
    # 可被 create_backtest(extras=...) 注入的参数（未注入时使用默认值）
    g.stock_num = int(getattr(g, 'stock_num', 4))
    g.pe_max = float(getattr(g, 'pe_max', 24.731))
    g.peg_min = float(getattr(g, 'peg_min', 0.20227))
    g.peg_max = float(getattr(g, 'peg_max', 1.33547))
    g.limitup_threshold = float(getattr(g, 'limitup_threshold', 0.97935))
    g.dividend_years = int(getattr(g, 'dividend_years', 3))
    g.dividend_top_pct = float(getattr(g, 'dividend_top_pct', 0.129236))
    g.roe_min = float(getattr(g, 'roe_min', 4.10208379))
    g.revenue_growth_min = float(getattr(g, 'revenue_growth_min', 5.378228))
    g.net_profit_growth_min = float(getattr(g, 'net_profit_growth_min', 16.42912))

    # 约束参数范围，避免异常参数导致回测报错
    g.stock_num = max(1, min(g.stock_num, 20))
    g.pe_max = max(0.0, g.pe_max)
    g.limitup_threshold = min(max(g.limitup_threshold, 0.90), 1.00)
    g.dividend_years = max(1, g.dividend_years)
    g.dividend_top_pct = min(max(g.dividend_top_pct, 0.0), 1.0)
    if g.peg_min > g.peg_max:
        g.peg_min, g.peg_max = g.peg_max, g.peg_min

    g.month=context.current_dt.month-1

# 开盘前运行，做为未来拓展的空间预留
def before_trading_start(context):
    # log.info(str(context.current_dt))
    prepare_stock_list(context)
    print(context.run_params.type) #模拟交易

# 开盘时运行函数
def handle_data(context,data):
    hour=context.current_dt.hour#读取当前时间-小时
    minute=context.current_dt.minute#读取当前时间-分钟
    #选股程序每月执行一次
    if context.current_dt.month !=g.month and hour==9 and minute==35:
        my_Trader(context)
        g.month=context.current_dt.month

    #-----------------------执行频率的设置和股票筛选程序----------------------
    if hour==14 and minute==0:  
        check_limit_up(context)#昨天涨停今天开板的卖出
    #显示可动用现金/总资产
    record(cash=context.portfolio.available_cash/context.portfolio.total_value*100)

def my_Trader(context):
    dt_last = context.previous_date
    stocks = get_all_securities('stock', dt_last).index.tolist()#读取所有股票
    stocks = filter_kcbj_stock(stocks)  #去科创和北交所
    stocks = filter_st_stock(stocks)#去ST
    stocks = filter_new_stock(context, stocks)#去除上市未满300天
    stocks = choice_try_A(context,stocks)#基本面选股
    stocks = filter_paused_stock(stocks)#去停牌
    stocks = filter_limit_stock(context,stocks)[:g.stock_num]#去除涨停的
    cdata = get_current_data()
    slist(context,stocks)
    # Sell
    for s in context.portfolio.positions:
        if (s  not in stocks) and (cdata[s].last_price <  cdata[s].high_limit):
            log.info('Sell', s, cdata[s].name)
            order_target(s, 0)
    # buy
    position_count = len(context.portfolio.positions)
    if g.stock_num > position_count:
        psize = context.portfolio.available_cash/(g.stock_num - position_count)
        for s in stocks:
            if s not in context.portfolio.positions:
                log.info('buy', s, cdata[s].name)
                order_value(s, psize)
                if len(context.portfolio.positions) == g.stock_num:
                    break
    
#显示筛查出股票的：名称，代码，市值
def slist(context,stock_list):    
    current_data = get_current_data()
    for stock in stock_list:
        df = get_fundamentals(query(valuation).filter(valuation.code == stock))
        print('股票代码：{0},  名称：{1},  总市值:{2:.2f},  流通市值:{3:.2f},  PE:{4:.2f},股价：{5:.2f}'.format(stock,get_security_info(stock).display_name,df['market_cap'][0],df['circulating_market_cap'][0],df['pe_ratio'][0],current_data[stock].last_price))

#1-1 准备股票池
# 如果持有股票昨天处于涨停的，则放入涨停列表，只要今天打开涨停就卖出，这个每天执行
def prepare_stock_list(context):
    #获取已持有列表
    g.hold_list= []
    g.high_limit_list=[]
    for position in list(context.portfolio.positions.values()):
        stock = position.security
        g.hold_list.append(stock)
    #获取昨日涨停列表
    if g.hold_list != []:
        for stock in g.hold_list:
            df = get_price(stock, end_date=context.previous_date, frequency='daily', fields=['close','high_limit'], count=1)
            if df['close'][0] >= df['high_limit'][0] * g.limitup_threshold:#如果昨天有股票涨停，则放入列表
                g.high_limit_list.append(stock)
    
#1-5 调整昨日涨停股票
def check_limit_up(context):
    now_time = context.current_dt
    if g.high_limit_list != []:
        #对昨日涨停股票观察到尾盘如不涨停则提前卖出，如果涨停即使不在应买入列表仍暂时持有
        for stock in g.high_limit_list:
            current_data = get_current_data()
            if current_data[stock].last_price <   current_data[stock].high_limit:
                log.info("[%s]涨停打开，卖出" % (stock))
                order_target(stock, 0)
            else:
                log.info("[%s]涨停，继续持有" % (stock))            
 
# 过滤科创北交股票
def filter_kcbj_stock(stock_list):
    for stock in stock_list[:]:
        if stock[0] == '4' or stock[0] == '8' or stock[:2] == '68':
            stock_list.remove(stock)
    return stock_list

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
def filter_limit_stock(context, stock_list):
	last_prices = history(1, unit='1m', field='close', security_list=stock_list)
	current_data = get_current_data()
	# 已存在于持仓的股票即使涨停也不过滤，避免此股票再次可买，但因被过滤而导致选择别的股票
	return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
			or current_data[stock].low_limit < last_prices[stock][-1] < current_data[stock].high_limit]

#1-1 根据最近三年分红除以当前总市值计算股息率并筛选(代码修改，可以再一创运行）
def get_dividend_ratio_filter_list(context, stock_list, sort, p1, p2):
    time1 = context.previous_date
    time0 = time1 - datetime.timedelta(days=365 * g.dividend_years)#最近N年分红
    #获取分红数据，由于finance.run_query最多返回4000行，以防未来数据超限，最好把stock_list拆分后查询再组合
    interval = 1000 #某只股票可能一年内多次分红，导致其所占行数大于1，所以interval不要取满4000
    list_len = len(stock_list)
    #截取不超过interval的列表并查询
    q = query(finance.STK_XR_XD.code, finance.STK_XR_XD.a_registration_date, finance.STK_XR_XD.bonus_amount_rmb
    ).filter(
        finance.STK_XR_XD.a_registration_date >= time0,
        finance.STK_XR_XD.a_registration_date <= time1,
        finance.STK_XR_XD.code.in_(stock_list[:min(list_len, interval)]))
    df = finance.run_query(q)
    #对interval的部分分别查询并拼接
    if list_len > interval:
        df_num = list_len // interval
        for i in range(df_num):
            q = query(finance.STK_XR_XD.code, finance.STK_XR_XD.a_registration_date,  finance.STK_XR_XD.bonus_amount_rmb
            ).filter(
                finance.STK_XR_XD.a_registration_date >= time0,
                finance.STK_XR_XD.a_registration_date <= time1,
                finance.STK_XR_XD.code.in_(stock_list[interval*(i+1):min(list_len,interval*(i+2))]))
            temp_df = finance.run_query(q)
            df = df.append(temp_df)
    dividend = df.fillna(0)#df.fillna() 是一个 Pandas 数据处理库中的函数，它可以用来填充数据框中的空值
    dividend = dividend.groupby('code').sum()
    temp_list = list(dividend.index) #query查询不到无分红信息的股票，所以temp_list长度会小于stock_list
    # #获取市值相关数据
    q = query(valuation.code,valuation.market_cap).filter(valuation.code.in_(temp_list))
    cap = get_fundamentals(q, date=time1)
    cap = cap.set_index('code')
    # #计算股息率
    cap['dividend_ratio']=(dividend['bonus_amount_rmb']/10000)/cap['market_cap']
    # #排序并筛选
    cap = cap.sort_values(by=['dividend_ratio'], ascending=sort)
    final_list = list(cap.index)[int(p1*len(cap)):int(p2*len(cap))]
    # print("近3年累计分红率排名前{0:.2%}的股有{1}只".format(p2,len(final_list)))
    return final_list
	
# 过滤次新股
def filter_new_stock(context, stock_list):
    return [stock for stock in stock_list if (context.previous_date - datetime.timedelta(days=300)) > get_security_info(stock).start_date]
    
def choice_try_A(context,stocks):
    stocks = get_dividend_ratio_filter_list(context, stocks, False, 0, g.dividend_top_pct)    #True股息率排序
    # 获取基本面数据
    df = get_fundamentals(query(
            valuation.code,
            valuation.circulating_market_cap,
        ).filter(
            valuation.code.in_(stocks),
            
            valuation.pe_ratio.between(0,g.pe_max),#市盈率上限
            indicator.inc_return > g.roe_min,#净资产收益率(扣除非经常损益)(%)
            indicator.inc_total_revenue_year_on_year > g.revenue_growth_min,#营业总收入同比增长率(%)
            indicator.inc_net_profit_year_on_year > g.net_profit_growth_min,#净利润同比增长率。
            valuation.pe_ratio / indicator.inc_net_profit_year_on_year>g.peg_min,#PEG下限
            valuation.pe_ratio / indicator.inc_net_profit_year_on_year<g.peg_max,#PEG上限
            
            ))
    stocks = list(df.code) 
    print("分红比率筛选后的股票有：{}".format(len(stocks)))
    # print(df)
    return stocks
