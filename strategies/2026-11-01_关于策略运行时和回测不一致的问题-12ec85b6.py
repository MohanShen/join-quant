# Clone from JoinQuant
# postId: 12ec85b628f80a27404278883c4e3349
# backtestId: 21b5e27dcde8ab800f48c9c95ec74104
# title: 关于策略运行时和回测不一致的问题

from jqdata import *
from jqfactor import *
from jqlib.technical_analysis import *
import datetime as dt
import pandas as pd
from datetime import datetime
from datetime import timedelta

# 初始化函数
def initialize(context):
    set_option('use_real_price', True)
    log.set_level('system', 'error')
    set_option('avoid_future_data', True)
    run_daily(get_stock_list, '08:00:00')
    run_daily(buy, '09:26:01')
    run_daily(sell, time='11:28', reference_security='000300.XSHG')
    run_daily(sell, time='14:50', reference_security='000300.XSHG')
    g.unsold_stocks = []  # 初始化一个空列表来存储未卖出的股票

# 选股函数
def get_stock_list(context): 
    # 文本日期
    date = context.previous_date
    date = transform_date(date,'str')
    date_1 = get_shifted_date(date, -1, 'T')
    date_2 = get_shifted_date(date, -2, 'T')

    # 初始列表
    initial_list = prepare_stock_list(date)
    # 前日曾涨停
    h1_list = get_ever_hl_stock(initial_list, date)
    # 上上个交易日涨停过滤
    elements_to_remove = get_hl_stock(initial_list, date_1)
    
    # 过滤上上个交易日涨停、曾涨停
    all_list = [stock for stock in h1_list if stock not in elements_to_remove]
    
    g.target_list = all_list
    
    # 第二段代码的输出作为优先买入股票
    g.priority_list = get_priority_list(context)
    
    buy_str = ''
    for stock in g.target_list:
        # 条件一：均价，金额，市值，换手率
        prev_day_data = attribute_history(stock, 1, '1d', fields=['close', 'volume','money'], skip_paused=True)
        avg_price_increase_value = prev_day_data['money'][0] / prev_day_data['volume'][0] / prev_day_data['close'][0]  - 1
        if avg_price_increase_value < -0.04 or prev_day_data['money'][0] < 3e8 or prev_day_data['money'][0] > 19e8:
            continue
        turnover_ratio_data = get_valuation(stock, start_date=context.previous_date, end_date=context.previous_date, fields=['turnover_ratio','market_cap','circulating_market_cap'])
        if turnover_ratio_data.empty or turnover_ratio_data['market_cap'][0] < 70  or turnover_ratio_data['circulating_market_cap'][0] > 520 :
            continue
        
        # 条件二：左压
        zyts = calculate_zyts(stock, context)
        volume_data = attribute_history(stock, zyts, '1d', fields=['volume'], skip_paused=True)
        if len(volume_data) < 2 or volume_data['volume'][-1] <= max(volume_data['volume'][:-1]) * 0.9:
            continue
        buy_str += "%s%s;"%(stock, get_security_info(stock).display_name)
    send_message('可能买入股票：%s '%(buy_str))
    log.info('可能买入股票：%s '%(buy_str))

# 第二段代码的输出作为优先买入股票
def get_priority_list(context):
    date = context.previous_date
    date = transform_date(date,'str')
    date_1 = get_shifted_date(date, -1, 'T')
    date_2 = get_shifted_date(date, -2, 'T')

    initial_list = prepare_stock_list(date)
    hl_list = get_hl_stock(initial_list, date)
    hl1_list = get_ever_hl_stock(initial_list, date_1)
    hl2_list = get_ever_hl_stock(initial_list, date_2)
    elements_to_remove = set(hl1_list + hl2_list)  
    hl_list = [stock for stock in hl_list if stock not in elements_to_remove] 
    
    qualified_stocks = [] 
    current_data = get_current_data()
    for s in hl_list:
        prev_day_data = attribute_history(s, 1, '1d', fields=['close', 'volume','money'], skip_paused=True)
        avg_price_increase_value = prev_day_data['money'][0] / prev_day_data['volume'][0] / prev_day_data['close'][0] * 1.1 - 1
        if avg_price_increase_value < 0.07 or prev_day_data['money'][0] < 7e8 or prev_day_data['money'][0] > 20e8:
            continue
        turnover_ratio_data=get_valuation(s, start_date=context.previous_date, end_date=context.previous_date, fields=['turnover_ratio','market_cap'])
        if turnover_ratio_data.empty or turnover_ratio_data['market_cap'][0] < 70:
            continue
        
        zyts = calculate_zyts(s, context)
        volume_data = attribute_history(s, zyts, '1d', fields=['volume'], skip_paused=True)
        if len(volume_data) < 2 or volume_data['volume'][-1] <= max(volume_data['volume'][:-1]) * 0.9:
            continue
        
        qualified_stocks.append(s)
        
    return qualified_stocks

# 交易函数
def buy(context):
    if g.unsold_stocks:  # 如果有未卖出的股票
        print("有未卖出的股票，不允许买入")
        return  # 直接返回，不允许买入
    
    qualified_stocks = [] 
    current_data = get_current_data()
    date_now = context.current_dt.strftime("%Y-%m-%d")
    mid_time1 ='09:15:00'
    end_times1 = '09:26:01'
    start = date_now + mid_time1
    end = date_now + end_times1
    
    # 先购买第二段代码选出的票
    for s in g.priority_list:
        # 过滤前面三天涨幅超过28%的票
        price_data = attribute_history(s, 4, '1d', fields=['close'], skip_paused=True)
        if len(price_data) < 4:
            continue
        increase_ratio = (price_data['close'][-1] - price_data['close'][0]) / price_data['close'][0]
        if increase_ratio > 0.23:
            continue
        
        # 过滤前一日收盘价小于开盘价5%以上的票
        prev_day_data = attribute_history(s, 1, '1d', fields=['open', 'close'], skip_paused=True)
        if len(prev_day_data) < 1:
            continue
        open_close_ratio = (prev_day_data['close'][0] - prev_day_data['open'][0]) / prev_day_data['open'][0]
        if open_close_ratio < -0.05:
            continue
        
        prev_day_data = attribute_history(s, 1, '1d', fields=['close', 'volume','money'], skip_paused=True)
        avg_price_increase_value = prev_day_data['money'][0] / prev_day_data['volume'][0] / prev_day_data['close'][0]  - 1
        if avg_price_increase_value < -0.04 or prev_day_data['money'][0] < 3e8 or prev_day_data['money'][0] > 19e8:
            continue
        turnover_ratio_data = get_valuation(s, start_date=context.previous_date, end_date=context.previous_date, fields=['turnover_ratio','market_cap','circulating_market_cap'])
        if turnover_ratio_data.empty or turnover_ratio_data['market_cap'][0] < 50  or turnover_ratio_data['circulating_market_cap'][0] > 520 :
            continue
        
        zyts = calculate_zyts(s, context)
        volume_data = attribute_history(s, zyts, '1d', fields=['volume'], skip_paused=True)
        if len(volume_data) < 2 or volume_data['volume'][-1] <= max(volume_data['volume'][:-1]) * 0.9:
            continue
        
        auction_data = get_call_auction(s, start_date=start, end_date=end, fields=['time','volume', 'current'])
        
        if auction_data.empty or auction_data['volume'][0] / volume_data['volume'][-1] < 0.03:
            continue
        current_ratio = auction_data['current'][0] / (current_data[s].high_limit/1.1)
        if current_ratio <= 0.98 or current_ratio >= 1.09:
            continue
        
        qualified_stocks.append(s)
        
        # 如果第二段代码的输出不为空，则直接购买，不再考虑第一段代码的输出
        if len(qualified_stocks) > 0:
            value = context.portfolio.available_cash / len(qualified_stocks)
            for s in qualified_stocks:
                if context.portfolio.available_cash/current_data[s].last_price > 100: 
                    order_value(s, value, MarketOrderStyle(current_data[s].day_open))
                    g.unsold_stocks.append(s)  # 添加到未卖出列表
                    print('买入股票：%s%s'%(s, get_security_info(s).display_name))
                    print('———————————————————————————————————')
            return
    
    # 如果第二段代码的输出为空，则购买第一段代码的输出
    for s in g.target_list:
        # 过滤前面三天涨幅超过28%的票
        price_data = attribute_history(s, 4, '1d', fields=['close'], skip_paused=True)
        if len(price_data) < 4:
            continue
        increase_ratio = (price_data['close'][-1] - price_data['close'][0]) / price_data['close'][0]
        if increase_ratio > 0.28:
            continue
        
        # 过滤前一日收盘价小于开盘价5%以上的票
        prev_day_data = attribute_history(s, 1, '1d', fields=['open', 'close'], skip_paused=True)
        if len(prev_day_data) < 1:
            continue
        open_close_ratio = (prev_day_data['close'][0] - prev_day_data['open'][0]) / prev_day_data['open'][0]
        if open_close_ratio < -0.05:
            continue
        
        prev_day_data = attribute_history(s, 1, '1d', fields=['close', 'volume','money'], skip_paused=True)
        avg_price_increase_value = prev_day_data['money'][0] / prev_day_data['volume'][0] / prev_day_data['close'][0]  - 1
        if avg_price_increase_value < -0.04 or prev_day_data['money'][0] < 3e8 or prev_day_data['money'][0] > 19e8:
            continue
        turnover_ratio_data = get_valuation(s, start_date=context.previous_date, end_date=context.previous_date, fields=['turnover_ratio','market_cap','circulating_market_cap'])
        if turnover_ratio_data.empty or turnover_ratio_data['market_cap'][0] < 50  or turnover_ratio_data['circulating_market_cap'][0] > 520 :
            continue
        
        zyts = calculate_zyts(s, context)
        volume_data = attribute_history(s, zyts, '1d', fields=['volume'], skip_paused=True)
        if len(volume_data) < 2 or volume_data['volume'][-1] <= max(volume_data['volume'][:-1]) * 0.9:
            continue
        
        auction_data = get_call_auction(s, start_date=start, end_date=end, fields=['time','volume', 'current'])
        
        if auction_data.empty or auction_data['volume'][0] / volume_data['volume'][-1] < 0.03:
            continue
        current_ratio = auction_data['current'][0] / (current_data[s].high_limit/1.1)
        if current_ratio <= 0.98 or current_ratio >= 1.09:
            continue
        
        qualified_stocks.append(s)
    
    if len(qualified_stocks)!= 0:
        value = context.portfolio.available_cash / len(qualified_stocks)
        for s in qualified_stocks[:1]:  # 只买入一个股票
            if context.portfolio.available_cash/current_data[s].last_price > 100: 
                order_value(s, value, MarketOrderStyle(current_data[s].day_open))
                g.unsold_stocks.append(s)  # 添加到未卖出列表
                print('买入股票：%s%s'%(s, get_security_info(s).display_name))
                print('———————————————————————————————————')

# 处理日期相关函数
def transform_date(date, date_type):
    if type(date) == str:
        str_date = date
        dt_date = dt.datetime.strptime(date, '%Y-%m-%d')
        d_date = dt_date.date()
    elif type(date) == dt.datetime:
        str_date = date.strftime('%Y-%m-%d')
        dt_date = date
        d_date = dt_date.date()
    elif type(date) == dt.date:
        str_date = date.strftime('%Y-%m-%d')
        dt_date = dt.datetime.strptime(str_date, '%Y-%m-%d')
        d_date = date
    dct = {'str':str_date, 'dt':dt_date, 'd':d_date}
    return dct[date_type]

def get_shifted_date(date, days, days_type='T'):
    #获取上一个自然日
    d_date = transform_date(date, 'd')
    yesterday = d_date + dt.timedelta(-1)
    #移动days个自然日
    if days_type == 'N':
        shifted_date = yesterday + dt.timedelta(days+1)
    #移动days个交易日
    if days_type == 'T':
        all_trade_days = [i.strftime('%Y-%m-%d') for i in list(get_all_trade_days())]
        #如果上一个自然日是交易日，根据其在交易日列表中的index计算平移后的交易日        
        if str(yesterday) in all_trade_days:
            shifted_date = all_trade_days[all_trade_days.index(str(yesterday)) + days + 1]
        #否则，从上一个自然日向前数，先找到最近一个交易日，再开始平移
        else:
            for i in range(100):
                last_trade_date = yesterday - dt.timedelta(i)
                if str(last_trade_date) in all_trade_days:
                    shifted_date = all_trade_days[all_trade_days.index(str(last_trade_date)) + days + 1]
                    break
    return str(shifted_date)

# 处于近n天的低位
def get_relative_position_df(stock_list, date, watch_days, ratio):
    if stock_list:
        df = get_price(stock_list, end_date=date, fields=['high', 'low', 'close'], count=watch_days, fill_paused=False, skip_paused=False, panel=False).dropna()
        close = df.groupby('code')['close'].last()
        high = df.groupby('code')['high'].max()
        low = df.groupby('code')['low'].min()
        result = pd.DataFrame({
            'rp': (close - low) / (high - low)
        }, index=close.index)
    else:
        result = pd.DataFrame(columns=['rp'])
    result = result[result['rp'] <= ratio]
    low_n_pos_list = list(result.index)
    return low_n_pos_list

# 过滤函数
def filter_new_stock(initial_list, date, days=50):
    d_date = transform_date(date, 'd')
    return [stock for stock in initial_list if d_date - get_security_info(stock).start_date > dt.timedelta(days=days)]

def filter_st_stock(initial_list, date):
    str_date = transform_date(date,'str')
    if get_shifted_date(str_date, 0, 'N')!= get_shifted_date(str_date, 0, 'T'):
        str_date = get_shifted_date(str_date, -1, 'T')
    df = get_extras('is_st', initial_list, start_date=str_date, end_date=str_date, df=True)
    df = df.T
    df.columns = ['is_st']
    df = df[df['is_st'] == False]
    filter_list = list(df.index)
    return filter_list

def filter_kcbj_stock(initial_list):
    return [stock for stock in initial_list if not (stock.startswith('30') or stock.startswith('68') or stock.startswith('4') or stock.startswith('8') or stock[:2] == '68')]

def filter_paused_stock(initial_list, date):
    df = get_price(initial_list, end_date=date, frequency='daily', fields=['paused'], count=1, panel=False, fill_paused=True)
    df = df[df['paused'] == 0]
    paused_list = list(df.code)
    return paused_list

# 每日初始股票池
def prepare_stock_list(date): 
    initial_list = get_all_securities('stock', date).index.tolist()
    initial_list = filter_kcbj_stock(initial_list)
    initial_list = filter_new_stock(initial_list, date)
    initial_list = filter_st_stock(initial_list, date)
    initial_list = filter_paused_stock(initial_list, date)
    return initial_list

# 计算左压天数
def calculate_zyts(s, context):
    high_prices = attribute_history(s, 101, '1d', fields=['high'], skip_paused=True)['high']
    prev_high = high_prices.iloc[-1]
    zyts_0 = next((i-1 for i, high in enumerate(high_prices[-3::-1], 2) if high >= prev_high), 100)
    zyts = zyts_0 + 5
    return zyts

# 筛选出某一日涨停的股票
def get_hl_stock(initial_list, date):
    df = get_price(initial_list, end_date=date, frequency='daily', fields=['close','high_limit'], count=1, panel=False, fill_paused=False, skip_paused=False)
    df = df.dropna() #去除停牌
    df = df[df['close'] == df['high_limit']]
    hl_list = list(df.code)
    return hl_list

# 筛选曾涨停
def get_ever_hl_stock(initial_list, date):
    df = get_price(initial_list, end_date=date, frequency='daily', fields=['close','high','high_limit'], count=1, panel=False, fill_paused=False, skip_paused=False)
    df = df.dropna() #去除停牌
    cd1 = df['high'] == df['high_limit'] 
    cd2 = df['close']!= df['high_limit']
    df = df[cd1 & cd2]
    hl_list = list(df.code)
    return hl_list

# 计算涨停数
def get_hl_count_df(hl_list, date, watch_days):
    # 获取watch_days的数据
    df = get_price(hl_list, end_date=date, frequency='daily', fields=['close','high_limit','low'], count=watch_days, panel=False, fill_paused=False, skip_paused=False)
    df.index = df.code
    #计算涨停与一字涨停数，一字涨停定义为最低价等于涨停价
    hl_count_list = []
    extreme_hl_count_list = []
    for stock in hl_list:
        df_sub = df.loc[stock]
        hl_days = df_sub[df_sub.close==df_sub.high_limit].high_limit.count()
        extreme_hl_days = df_sub[df_sub.low==df_sub.high_limit].high_limit.count()
        hl_count_list.append(hl_days)
        extreme_hl_count_list.append(extreme_hl_days)
    #创建df记录
    df = pd.DataFrame(index=hl_list, data={'count':hl_count_list, 'extreme_count':extreme_hl_count_list})
    return df

# 计算昨涨幅
def get_index_increase_ratio(index_code, context):
    # 获取指数昨天和前天的收盘价
    close_prices = attribute_history(index_code, 2, '1d', fields=['close'], skip_paused=True)
    if len(close_prices) < 2:
        return 0  # 如果数据不足，返回0
    day_before_yesterday_close = close_prices['close'][0]
    yesterday_close = close_prices['close'][1]
    
    # 计算涨幅
    increase_ratio = (yesterday_close - day_before_yesterday_close) / day_before_yesterday_close
    return increase_ratio

#上午有利润就跑
def sell(context):
    # 基础信息
    date = transform_date(context.previous_date,'str')
    current_data = get_current_data()
    
    # 根据时间执行不同的卖出策略
    if str(context.current_dt)[-8:] == '11:28:00':
        for s in list(context.portfolio.positions):
            if ((context.portfolio.positions[s].closeable_amount!= 0) and (current_data[s].last_price < current_data[s].high_limit) and (current_data[s].last_price > 1*context.portfolio.positions[s].avg_cost)):#avg_cost当前持仓成本
                order_target_value(s, 0)
                if s in g.unsold_stocks:  # 检查是否存在于未卖出列表中
                    g.unsold_stocks.remove(s)  # 从未卖出列表中移除
                print('止盈卖出股票：%s%s'%(s, get_security_info(s, date).display_name))
                print('———————————————————————————————————')
    
    if str(context.current_dt)[-8:] == '14:50:00':
        for s in list(context.portfolio.positions):
            if ((context.portfolio.positions[s].closeable_amount!= 0) and (current_data[s].last_price < current_data[s].high_limit)):#closeable_amount可卖出的仓位
                order_target_value(s, 0)
                if s in g.unsold_stocks:  # 检查是否存在于未卖出列表中
                    g.unsold_stocks.remove(s)  # 从未卖出列表中移除
                print('止损卖出股票：%s%s'%(s, get_security_info(s, date).display_name))
                print('———————————————————————————————————')
    
    # 更新未卖出列表
    g.unsold_stocks = [s for s in context.portfolio.positions if context.portfolio.positions[s].closeable_amount > 0]
