# Clone from JoinQuant
# postId: e73c9d8957f151678e4648e15319e532
# backtestId: 5f6f22fb30b97ef1f5206f4d4711a3c4
# title: 无未来，26年回撤10%，收益100%+的打板策略

from jqdata import *
from jqfactor import *
from jqlib.technical_analysis import *
import datetime as dt
import pandas as pd
from datetime import datetime
from datetime import timedelta

g.strategy = 'dragon'

g.stock_pick_records = {
    'candidates': [],       # 昨日涨停候选
    'qualified': [],         # 最终买入
    'eliminated': {}         # 淘汰股票及原因: {stock: [reason1, reason2, ...]}
}


def initialize(context):
    set_option('use_real_price', True)
    log.set_level('system', 'error')
    set_option('avoid_future_data', True)
    run_daily(get_stock_list, '9:05')
    run_daily(buy, '09:28')
    run_daily(sell, time='11:28', reference_security='000300.XSHG')
    run_daily(sell, time='14:50', reference_security='000300.XSHG')
    run_daily(after_market_close, time='15:01')



# 选股
def get_stock_list(context): 
    # 文本日期
    date = context.previous_date
    date = transform_date(date, 'str')
    date_1=get_shifted_date(date, -1, 'T')
    date_2=get_shifted_date(date, -2, 'T')

    # 初始列表
    initial_list = prepare_stock_list(date)
    # 昨日涨停
    hl_list = get_hl_stock(initial_list, date)
    # 前日曾涨停
    hl1_list = get_ever_hl_stock(initial_list, date_1)
    # 前前日曾涨停
    hl2_list = get_ever_hl_stock(initial_list, date_2)
    # 合并 hl1_list 和 hl2_list 为一个集合，用于快速查找需要剔除的元素  
    elements_to_remove = set(hl1_list + hl2_list)  
    # 使用列表推导式来剔除 hl_list 中存在于 elements_to_remove 集合中的元素  
    hl_list = [stock for stock in hl_list if stock not in elements_to_remove] 
    
    g.target_list = hl_list
    g.stock_pick_records['candidates'] = hl_list



# 交易
def buy(context):
    qualified_stocks = [] 
    current_data = get_current_data()
    date_now = context.current_dt.strftime("%Y-%m-%d")
    mid_time1 = ' 09:15:00'
    end_times1 =  ' 09:26:00'
    start = date_now + mid_time1
    end = date_now + end_times1
    
    # 大盘情绪择时：上证指数开盘涨幅低于-1%时，不买入
    index_code = '000001.XSHG'
    index_data = attribute_history(index_code, 1, '1d', fields=['open', 'close'], skip_paused=True)
    yesterday_close = index_data['close'][0]
    current_price = index_data['open'][0]  # 使用开盘价，而非当前价
    index_open_ratio = (current_price - yesterday_close) / yesterday_close
    log.info(f'【大盘择时】上证指数开盘涨幅: {index_open_ratio:.2%}')
    if index_open_ratio < -0.01:
        log.info(f'【大盘择时】上证指数开盘涨幅{index_open_ratio:.2%} < -1%，今日不买入')
        g.stock_pick_records['qualified'] = []
        return
    
    g.stock_pick_records['eliminated'] = {}  # 重置淘汰记录
    
    for s in g.target_list:
        stock_name = get_security_info(s).display_name
        # 条件一：均价，金额，市值，换手率
        prev_day_data = attribute_history(s, 1, '1d', fields=['close', 'volume', 'money'], skip_paused=True)
        avg_price_increase_value = prev_day_data['money'][0] / prev_day_data['volume'][0] / prev_day_data['close'][0] * 1.1 - 1
        if avg_price_increase_value < 0.055:
            log.info(f'【淘汰】{s} {stock_name} 条件一: 均价涨幅{avg_price_increase_value:.2%} < 6.5%')
            _record_elimination(s, f"均价涨幅{avg_price_increase_value:.2%} < 6.5%")
            continue
        if prev_day_data['money'][0] < 3e8:
            log.info(f'【淘汰】{s} {stock_name} 条件一: 成交额{int(prev_day_data["money"][0]/1e8)}亿 < 4亿')
            _record_elimination(s, f"成交额{int(prev_day_data['money'][0]/1e8)}亿 < 4亿")
            continue
        if prev_day_data['money'][0] > 25e8:
            log.info(f'【淘汰】{s} {stock_name} 条件一: 成交额{int(prev_day_data["money"][0]/1e8)}亿 > 25亿')
            _record_elimination(s, f"成交额{int(prev_day_data['money'][0]/1e8)}亿 > 25亿")
            continue
        turnover_ratio_data=get_valuation(s, start_date=context.previous_date, end_date=context.previous_date, fields=['turnover_ratio', 'market_cap','circulating_market_cap'])
        if turnover_ratio_data.empty:
            log.info(f'【淘汰】{s} {stock_name} 条件一: 换手率数据为空')
            _record_elimination(s, "换手率数据为空")
            continue
        if turnover_ratio_data['market_cap'][0] < 30:
            log.info(f'【淘汰】{s} {stock_name} 条件一: 总市值{int(turnover_ratio_data["market_cap"][0])}亿 < 70亿')
            _record_elimination(s, f"总市值{int(turnover_ratio_data['market_cap'][0])}亿 < 70亿")
            continue
        if turnover_ratio_data['circulating_market_cap'][0] > 520:
            log.info(f'【淘汰】{s} {stock_name} 条件一: 流通市值{int(turnover_ratio_data["circulating_market_cap"][0])}亿 > 520亿')
            _record_elimination(s, f"流通市值{int(turnover_ratio_data['circulating_market_cap'][0])}亿 > 520亿")
            continue
        
        
        # 条件二：左压
        zyts = calculate_zyts(s, context)
        volume_data = attribute_history(s, zyts, '1d', fields=['volume'], skip_paused=True)
        if len(volume_data) < 2:
            log.info(f'【淘汰】{s} {stock_name} 条件二: 左压数据不足{len(volume_data)}天')
            _record_elimination(s, f"左压数据不足{len(volume_data)}天")
            continue
        max_volume = max(volume_data['volume'][:-1])
        if volume_data['volume'][-1] <= max_volume * 0.9:
            log.info(f'【淘汰】{s} {stock_name} 条件二: 今日量{int(volume_data["volume"][-1])} <= 左压{max_volume}*0.9={int(max_volume*0.9)}')
            _record_elimination(s, f"左压不足(量{int(volume_data['volume'][-1])} <= {int(max_volume*0.9)})")
            continue
        
        # 条件三：高开,开比
        log.info(f'【检查】{s} {stock_name} 开始集合竞价检查')
        auction_data = get_call_auction(s, start_date=start, end_date=end, fields=['time','volume', 'current'])
        log.info(f'【竞价数据】{s} {stock_name}: {auction_data}')
        if auction_data.empty:
            log.info(f'【淘汰】{s} {stock_name} 条件三: 集合竞价数据为空')
            _record_elimination(s, "集合竞价数据为空")
            continue
        auction_data = auction_data.sort_values('time')
        auction_last = auction_data.tail(1)
        yesterday_volume = volume_data['volume'][-1]
        auction_ratio = auction_last['volume'].values[0] / yesterday_volume
        if auction_ratio < 0.025:
            log.info(f'【淘汰】{s} {stock_name} 条件三: 竞价量比{auction_ratio:.2%} < 2.5% (竞价{auction_last["volume"].values[0]} / 昨日{yesterday_volume})')
            _record_elimination(s, f"竞价量比{auction_ratio:.2%} < 2.5%")
            continue
        high_limit = current_data[s].high_limit / 1.1
        current_ratio = auction_last['current'].values[0] / high_limit
        if current_ratio <= 1.01:
            log.info(f'【淘汰】{s} {stock_name} 条件三: 高开幅度{current_ratio:.2%} <= 101%')
            _record_elimination(s, f"高开幅度{current_ratio:.2%} <= 101%")
            continue
        log.info(f'【通过】{s} {stock_name} 竞价量比{auction_ratio:.2%}, 高开幅度{current_ratio:.2%}')
        
        # 如果股票满足所有条件，则添加到列表中  
        qualified_stocks.append(s)
        
    log.info(f'============= 今日一进二选股结束 =============')
    log.info(f'【昨日涨停候选】共{len(g.target_list)}只')
    stock_names = [get_security_info(s).display_name for s in qualified_stocks]
    log.info(f'【最终选中】共{len(qualified_stocks)}只: {qualified_stocks} | {stock_names}')
    
    # 记录买入股票（晋级成功）
    g.stock_pick_records['qualified'] = qualified_stocks
    
    if len(qualified_stocks)!=0:
        max_stocks = 3  # 最多持仓3只
        max_single_value = context.portfolio.total_value / 3  # 单只股票最大买入金额为总资金的1/3
        stocks_to_buy = qualified_stocks[:max_stocks]  # 最多买入3只
        for s in stocks_to_buy:
            stock_name = get_security_info(s).display_name
            if context.portfolio.available_cash/current_data[s].last_price>100: 
                order_value(s, max_single_value)
                log.info(f'【买入成功】{s} {stock_name} 买入金额: {int(max_single_value)}')


def _record_elimination(stock, reason):
    """记录股票淘汰原因"""
    if stock not in g.stock_pick_records['eliminated']:
        g.stock_pick_records['eliminated'][stock] = []
    g.stock_pick_records['eliminated'][stock].append(reason)


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



# 过滤函数
def filter_new_stock(initial_list, date, days=50):
    d_date = transform_date(date, 'd')
    return [stock for stock in initial_list if d_date - get_security_info(stock).start_date > dt.timedelta(days=days)]

def filter_st_stock(initial_list, date):
    str_date = transform_date(date, 'str')
    if get_shifted_date(str_date, 0, 'N') != get_shifted_date(str_date, 0, 'T'):
        str_date = get_shifted_date(str_date, -1, 'T')
    df = get_extras('is_st', initial_list, start_date=str_date, end_date=str_date, df=True)
    df = df.T
    df.columns = ['is_st']
    df = df[df['is_st'] == False]
    filter_list = list(df.index)
    return filter_list

def filter_kcbj_stock(initial_list):
    return [stock for stock in initial_list if stock[0] != '4' and stock[0] != '8' and stock[0] != '3' and stock[:2] != '68']

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
    df = get_price(initial_list, end_date=date, frequency='daily', fields=['high','high_limit'], count=1, panel=False, fill_paused=False, skip_paused=False)
    df = df.dropna() #去除停牌
    df = df[df['high'] == df['high_limit']]
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
    date = transform_date(context.previous_date, 'str')
    current_data = get_current_data()
    
    # 根据时间执行不同的卖出策略
    if str(context.current_dt)[-8:] == '11:28:00':
        for s in list(context.portfolio.positions):
            if ((context.portfolio.positions[s].closeable_amount != 0) and (current_data[s].last_price < current_data[s].high_limit) and (current_data[s].last_price > 1*context.portfolio.positions[s].avg_cost)):#avg_cost当前持仓成本
                order_target_value(s, 0)
                #print( '止盈卖出', [s,get_security_info(s, date).display_name])
                #print('———————————————————————————————————')
    
    if str(context.current_dt)[-8:] == '14:50:00':
        for s in list(context.portfolio.positions):
            if ((context.portfolio.positions[s].closeable_amount != 0) and (current_data[s].last_price < current_data[s].high_limit)):#closeable_amount可卖出的仓位
                order_target_value(s, 0)
                #print( '止损卖出', [s,get_security_info(s, date).display_name])
                #print('—————————————————————————————���—————')


def after_market_close(context):
    """收盘后打印选股汇总"""
    _print_stock_pick_summary(context)  


def _print_stock_pick_summary(context):
    """打印当日选股汇总"""
    log.info("=" * 60)
    log.info("============= 一进二选股汇总 =============")
    
    candidates = g.stock_pick_records.get('candidates', [])
    qualified = g.stock_pick_records.get('qualified', [])
    eliminated = g.stock_pick_records.get('eliminated', {})
    
    log.info(f"【昨日涨停候选】共{len(candidates)}只")
    
    if candidates:
        candidate_names = [get_security_info(s).display_name for s in candidates]
        log.info(f"候选股票: {candidate_names}")
    
    log.info(f"【晋级成功(买入)】共{len(qualified)}只")
    if qualified:
        qualified_names = [get_security_info(s).display_name for s in qualified]
        log.info(f"晋级成功: {qualified_names}")
    
    # 找出晋级成功但未买入的股票
    yesterday = context.previous_date
    today = context.current_dt.strftime('%Y-%m-%d')
    
    # 昨日涨停候选中，当日也涨停的 = 晋级成功
    if candidates:
        today_hl = get_price(candidates, end_date=today, frequency='daily', 
                           fields=['close', 'high_limit'], count=1, panel=False, fill_paused=False)
        if today_hl is not None and not today_hl.empty:
            success_list = today_hl[today_hl['close'] == today_hl['high_limit']]['code'].tolist()
            
            # 排除已买入的
            not_bought = [s for s in success_list if s not in qualified]
            
            log.info(f"【晋级成功但未买入】共{len(not_bought)}只")
            if not_bought:
                not_bought_names = [get_security_info(s).display_name for s in not_bought]
                log.info(f"未买入: {not_bought_names}")
                
                # 打印这些股票被淘汰的原因
                for stock in not_bought:
                    if stock in eliminated:
                        try:
                            stock_name = get_security_info(stock).display_name
                        except:
                            stock_name = stock
                        log.info(f"  {stock}({stock_name}): {'; '.join(eliminated[stock])}")
    
    log.info("=" * 60)  