# Clone from JoinQuant
# postId: b7e45c0b998413c9b1337be4a6ed265d
# backtestId: 4b63859944a0a44ff590bd4b973c6e10
# title: 进程占用内存过大(3.1 GB), 被强制杀掉.

# 当日开盘5-10分钟涨幅>4-5%,开始关注，15分钟之内涨幅达到9.5%，买入
#数量n=10只
#择时，昨日跌停小于15只
#择股：去st，科创，创业板，连续涨停超过m=3板的不做

from jqdata import *
from jqfactor import *
import pandas as pd
from datetime import datetime,timedelta,date


################################### 初始化设置 #############################################
def initialize(context):
    set_option('use_real_price', True)
    log.set_level('system', 'error')
    set_option('avoid_future_data', True)
    g.n_days_limit_up_list = []   #重新初始化列表
    g.stocks=[]
    g.n=10

    run_daily(prepare_stock_list, '9:00')
    run_daily(check, '09:28')
    run_daily(conform, '09:39')
    run_daily(get_stock_list, time='9:40', reference_security='000300.XSHG')
    run_daily(buy, time='9:41', reference_security='000300.XSHG')
    run_daily(buy, time='9:42', reference_security='000300.XSHG')
    run_daily(buy, time='9:43', reference_security='000300.XSHG')
    run_daily(buy, time='9:44', reference_security='000300.XSHG')
    run_daily(buy, time='9:45', reference_security='000300.XSHG')
    run_daily(buy, time='9:46', reference_security='000300.XSHG')
    run_daily(buy, time='9:47', reference_security='000300.XSHG')
    run_daily(buy, time='9:48', reference_security='000300.XSHG')
    run_daily(buy, time='9:49', reference_security='000300.XSHG')
    run_daily(buy, time='9:50', reference_security='000300.XSHG')  
    run_daily(sell, time='11:28', reference_security='000300.XSHG')
    run_daily(sell, time='14:50', reference_security='000300.XSHG')

## 定义股票池      
def set_stockpool(context):
    yesterday = context.previous_date 
    initial_list = get_all_securities('stock', yesterday).index.tolist()
    return initial_list

##################################  交易函数群 ##################################
def check(context):
    #当日开盘10分钟涨幅>4-5%,作为观察标的，从9：41:9：50开始扫射9-9.5%以上涨幅的
    #当日开盘涨幅0-6%
    print("开盘筛选0-6%,剔除短期涨幅巨大的-4天30%以上")
    s=g.stocks
    df=[]
    current_data = get_current_data()
    prev_day_data = history(5, '1d','close',s, True)
    #print(prev_day_data)
    for stock in s:
        if 1.07>=current_data[stock].last_price/prev_day_data[stock][-1]>=1 and current_data[stock].last_price/prev_day_data[stock][-4]<1.3 :
            df.append(stock)
    g.stocks=df
def conform(context):
    #当日开盘10分钟涨幅>4-5%,作为观察标的，从9：41:9：50开始扫射9-9.5%以上涨幅的
    print("开盘10分钟筛选4-5%")
    s=g.stocks
    df=[]
    df1=[]
    current_data = get_current_data()
    prev_day_data = history(1, '1d','close',s, True)
    #print(prev_day_data)
    for stock in s:
        if 1.06>=current_data[stock].last_price/prev_day_data[stock][-1]>=1.03:
            df.append(stock)
    if (len(df)>100):
        #太多了
        for stock in df:
            if 1.06>=current_data[stock].last_price/prev_day_data[stock][-1]>1.05:
                df1.append(stock)
    g.stocks=df1

def buy(context):
    qualified_stocks = g.stocks  
    if len(qualified_stocks)>0:
        current_data = get_current_data()
        prev_day_data = history(1, '1d','close',qualified_stocks, True)
        value = context.portfolio.available_cash / g.n
        for s in qualified_stocks:
            # 下单   #至少够买1手
            if current_data[s].last_price/prev_day_data[s][-1]>=1.08 :
                order_value(s, value)
                g.stocks.remove(s)
                print('买入' + s)
                print('———————————————————————————————————')
        
def sell(context):
    stime = context.current_dt.strftime("%H%M")
    current_data = get_current_data()
    
    # 根据时间执行不同的卖出策略
    if stime == '1128':
        for s in list(context.portfolio.positions):  #上午有利润就跑
            if ((context.portfolio.positions[s].closeable_amount != 0) and (current_data[s].last_price < current_data[s].high_limit) and (current_data[s].last_price > 1*context.portfolio.positions[s].avg_cost)):#avg_cost当前持仓成本
                order_target_value(s, 0)
    elif stime == '1450':
        for s in list(context.portfolio.positions):
            if ((context.portfolio.positions[s].closeable_amount != 0) and (current_data[s].last_price < current_data[s].high_limit)):#closeable_amount可卖出的仓位
                order_target_value(s, 0)


##################################  选股函数群 ##################################   
# 选股
def get_stock_list(context): 
    print("价量精确筛选")
    target_list = g.stocks
    qualified_stocks = [] 
    current_data = get_current_data()
    date_now = context.current_dt.strftime("%Y-%m-%d")
    mid_time1 = ' 09:30:00'
    end_times1 =  ' 09:40:00'
    start = date_now + mid_time1
    end = date_now + end_times1
    for s in target_list:

        prev_day_data = attribute_history(s, 1, '1d', fields=['close', 'volume', 'money'], skip_paused=True)
        # 高开放量
        auction_data = get_ticks(security=s, start_dt=start, end_dt=end, fields=['time','volume', 'current'])
        #print(auction_data)
        #print(sum(auction_data['volume'][0:-1]) / prev_day_data['volume'][-1])
        if auction_data['volume'][-1] / prev_day_data['volume'][-1] < 0.06:
            continue
        current_ratio = auction_data['current'][0] / prev_day_data['close'][-1]
        if current_ratio<=1 or current_ratio>=1.0602:
            continue        

        # 如果股票满足所有条件，则添加到列表中  
        qualified_stocks.append(s)
        g.stocks=qualified_stocks
        print(len(g.stocks))
    

# 每日初始股票池
def prepare_stock_list(context):
    print("初步剔除")
    today = context.current_dt.date()
    yesterday = context.previous_date
    initial_list = set_stockpool(context)
    initial_list = filter_kcbj_stock(initial_list)
    initial_list = filter_st_paused_stock(initial_list, today)
    initial_list = filter_new_stock(initial_list, today)
    # 首次运行，添加前2天的数据
    if not g.n_days_limit_up_list:
        days = get_trade_days( end_date = yesterday, count=3)[:-1]
        for day in days:
            g.n_days_limit_up_list.append(get_hl_stock(initial_list, day,1))

    hl_list = get_hl_stock(initial_list, yesterday,1)     # 昨日涨停
    dl_list = get_dl_stock(initial_list, yesterday,1)     #昨日跌停
    total=len(initial_list)
    g.n_days_limit_up_list.append(hl_list) 
    if len(hl_list)/total > 0.01 and len(dl_list) < 15:
        g.zeshi=1
    else:
        g.zeshi=0

    hl2_list = set(g.n_days_limit_up_list[-2] + g.n_days_limit_up_list[-3])      # 前2日曾涨停
    hl_list = [stock for stock in hl_list if stock in hl2_list] #选出连续3天涨停的作为剔除

    initial_list=[stock for stock in initial_list if stock not in hl_list]
    g.n_days_limit_up_list.pop(0)  # 移除无用的数据
    print("去除st科创京三板：%s个"%len(initial_list))
    g.stocks=initial_list



###################################  其它函数群 ##################################

# 筛选出某一日涨停的股票
def get_hl_stock(stock_list, date1,days):
    if not stock_list:return []
    h_s = get_price(stock_list, end_date=date1, frequency='daily', fields=['close', 'high_limit', 'paused'],
                  count=days, panel=False, fill_paused=False, skip_paused=True
                  ).query('close==high_limit and paused==0').groupby('code').size()
    return h_s.index.tolist()
def get_dl_stock(stock_list, date1,days):
    if not stock_list:return []
    l_s = get_price(stock_list, end_date=date1, frequency='daily', fields=['close', 'low_limit', 'paused'],
                  count=days, panel=False, fill_paused=False, skip_paused=True
                  ).query('close==low_limit and paused==0').groupby('code').size()
    return l_s.index.tolist()
# 过滤函数
def filter_new_stock(initial_list, date, days=50):
    return [stock for stock in initial_list if get_security_info(stock).start_date < date - timedelta(days=days)]

def filter_st_paused_stock(initial_list, date):
    current_data = get_current_data()
    return [stock for stock in initial_list if not (
            current_data[stock].is_st or 
            current_data[stock].paused or 
            '退' in current_data[stock].name)]


def filter_kcbj_stock(initial_list):
    return [stock for stock in initial_list if stock[0] != '4' and stock[0] != '8' and stock[0] != '3' and stock[:2] != '68']


### end ###