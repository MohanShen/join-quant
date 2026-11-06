# Clone from JoinQuant
# postId: 6273835110bb70ceb99c53bf8215bb36
# backtestId: f66584d72d3498749e44955e20ceeb0f
# title: 给你们筛选好了，这个涨停股策略还是很不错的

# 克隆自聚宽文章：https://www.joinquant.com/post/81373
# 标题：连板龙头接力
# 作者：Kard

from jqdata import *
from jqfactor import *
from jqlib.technical_analysis import *
import datetime as dt
import pandas as pd
import numpy as np

def initialize(context):
    # 系统设置
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_option("match_by_signal", True)
    log.set_level('system', 'error')
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003,
                             close_today_commission=0, min_commission=5), type='stock')

    g.buy_pct = 2
    g.jqfactor = 'VOL5'  # 5日平均换手率（示例）
    g.sort = True        # 选取因子值最小
    g.emo_count = []
    
    # 每日运行
    run_daily(sell_check_open, '09:27')      # 竞价低开处理
    run_daily(get_stock_list, '09:25:45')
    run_daily(buy, '09:30:00')
    run_daily(sell_check_morning, '10:30')   # 10:30分时处理（含动态开板检查）
    run_daily(sell_check_afternoon, '14:30') # 尾盘处理（含动态开板检查）
    run_daily(print_position_info, '15:02')

# ---------- 选股 ----------
def get_stock_list(context): 
    # 文本日期
    date = context.previous_date
    date = transform_date(date, 'str')
    date_1 = get_shifted_date(date, -1, 'T')  # 保留，但不使用（可备后续扩展）
    date_now = context.current_dt.strftime("%Y-%m-%d")

    # 初始列表
    initial_list = prepare_stock_list(date)
    # 当日涨停
    hl_list = get_hl_stock(initial_list, date)
    # 全部连板股票
    ccd_hl = get_continue_count_df(hl_list, date, 20) if len(hl_list) != 0 else pd.DataFrame(index=[], data={'count':[],'extreme_count':[]})
    ccd_lb = ccd_hl[ccd_hl['count']>=2]
    lt_lb = list(ccd_lb.index) #龙头股
    dct = get_concept(lt_lb, date)   #涨停股票的概念字典
    hot_concepts = get_hot_concept(dct,ccd_lb,date)  #涨停数前3的热门概念

    stock_list = []  #买入股票池
    combined_df = pd.DataFrame(index=[], data={'count':[],'extreme_count':[]})
    for concept in hot_concepts:
        hot_stocks = get_stocks_by_concept_name(concept)   #热门概念所有股票  
        hot_stocks = filter_stock_list(hot_stocks, date)
        hl_hot_list = list(set(hl_list) & set(hot_stocks)) #概念涨停股
        
        ccd = ccd_hl[ccd_hl.index.isin(hl_hot_list)]
        combined_df = pd.concat([combined_df, ccd], ignore_index=False)

    # 统计每个股票代码出现的次数
    occurrence_count = combined_df.groupby(combined_df.index).size()
    
    final_df = combined_df[~combined_df.index.duplicated(keep='last')] # 保留最后一个
    final_df.loc[:, 'occurrence'] = final_df.index.map(occurrence_count)
    final_df = final_df[(final_df['occurrence']>=2) & (final_df['extreme_count']/final_df['count']<=0.66)]
    final_df = final_df.sort_values('count', ascending=False)
    log.info(final_df)
    lt = list(final_df.index)[:] #龙头股

    # 龙头特征选股
    condition_dct = {}
    current_data = get_current_data()
    for s in lt:
        try:
            hist = attribute_history(
                security=s,
                count=1,
                unit='1d',
                fields=('close', 'low', 'high', 'paused', 'high_limit'),
                skip_paused=False,
                df=False,
                fq='pre'
            )
            condition = ''
            pct_chg = (current_data[s].day_open - hist['close'][-1]) / hist['close'][-1]
            
            # 仅保留开盘涨幅处在 2%~8%之间的票
            if (pct_chg >= 0.02) and (pct_chg <= 0.08) and (current_data[s].day_open <= current_data[s].high_limit - 0.03):
                condition += '直接买入'
            if len(condition) != 0:
                condition_dct[s] = get_security_info(s, date).display_name + ' —— ' + condition
        except:
            pass
    stock_list = stock_list + list(condition_dct.keys())

    # 因子筛选
    df = get_factor_filter_df(context, stock_list, g.jqfactor, g.sort)
    stock_list = list(df.index)
    log.info('代码:{}'.format(stock_list))
    
    hold_list = list(context.portfolio.positions)
    g.target_list = [x for x in stock_list if x not in hold_list]
    g.target_list = g.target_list[:]

# ---------- 买入 ----------
def buy(context):
    current_data = get_current_data()
    if len(g.target_list) > 0:
        value1 = context.portfolio.total_value / g.buy_pct
        value = min(context.portfolio.available_cash, value1) / len(g.target_list)
    
        for s in g.target_list:
            if current_data[s].paused or 'ST' in current_data[s].name or '退' in current_data[s].name:
                log.info(f'跳过买入: {s} ({current_data[s].name}) 停牌或ST/退市')
                continue
                
            if context.portfolio.available_cash / current_data[s].last_price > 100: 
                order_value(s, value, LimitOrderStyle(current_data[s].day_open))
                log.info('买入' + s)
                log.info('———————————————————————————————————')

# ---------- 工具函数 ----------
def extract_concepts(data_dict):
    all_concepts = set()
    for stock_code, info in data_dict.items():
        if 'jq_concept' in info:
            for concept_dict in info['jq_concept']:
                all_concepts.add(concept_dict['concept_name'])
    return list(all_concepts)

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
    dct = {'str': str_date, 'dt': dt_date, 'd': d_date}
    return dct[date_type]

def get_shifted_date(date, days, days_type='T'):
    """
    健壮的日期偏移函数，自动扩大缓冲区直到成功
    days_type: 'N' 自然日偏移, 'T' 交易日偏移
    """
    d_date = transform_date(date, 'd')
    if days_type == 'N':
        shifted = d_date + dt.timedelta(days=days)
        return transform_date(shifted, 'str')
    else:  # 交易日偏移
        buffer = abs(days) + 50  # 初始 buffer
        while True:
            start = d_date - dt.timedelta(days=buffer)
            end = d_date + dt.timedelta(days=buffer)
            trade_days = list(get_trade_days(start_date=start, end_date=end))
            if len(trade_days) == 0:
                buffer += 10
                continue
            # 如果基准日期不是交易日，向前找到最近一个交易日
            base_date = d_date
            if base_date not in trade_days:
                found = False
                for i in range(1, buffer + 1):
                    candidate = d_date - dt.timedelta(days=i)
                    if candidate in trade_days:
                        base_date = candidate
                        found = True
                        break
                if not found:
                    buffer += 10
                    continue
            try:
                idx = trade_days.index(base_date)
            except ValueError:
                buffer += 10
                continue
            shifted_idx = idx + days
            if shifted_idx < 0 or shifted_idx >= len(trade_days):
                buffer += 10
                continue
            shifted_date = trade_days[shifted_idx]
            return shifted_date.strftime('%Y-%m-%d')

# ---------- 股票过滤 ----------
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
    return list(df.index)

def filter_kcbj_stock(initial_list):
    return [stock for stock in initial_list if stock[0] != '4' and stock[0] != '8' and stock[:2] != '68']

def filter_paused_stock(initial_list, date):
    df = get_price(initial_list, end_date=date, frequency='daily', fields=['paused'], count=1, panel=False, fill_paused=True)
    df = df[df['paused'] == 0]
    return list(df.code)

def filter_name_stock(initial_list):
    current_data = get_current_data()
    filtered_list = []
    for s in initial_list:
        name = current_data[s].name
        if 'ST' not in name and '※ST' not in name and '退' not in name:
            filtered_list.append(s)
    return filtered_list

def filter_stock_list(stock_list, date):
    if not stock_list:
        return []
    stock_list = filter_kcbj_stock(stock_list)
    stock_list = filter_new_stock(stock_list, date)
    stock_list = filter_st_stock(stock_list, date)
    stock_list = filter_paused_stock(stock_list, date)
    stock_list = filter_name_stock(stock_list)
    return stock_list

def prepare_stock_list(date): 
    initial_list = get_all_securities('stock', date).index.tolist()
    return filter_stock_list(initial_list, date)

# ---------- 情绪与概念 ----------
def get_init_emo_count(context, date):
    d1 = get_shifted_date(date, -3)
    d2 = get_shifted_date(date, -2)
    date_list = [d1, d2]
    emo_count = []
    for date in date_list:
        initial_list = prepare_stock_list(date)
        hl_list = get_hl_stock(initial_list, date)
        CCD = get_continue_count_df(hl_list, date, 20) if len(hl_list) != 0 else pd.DataFrame(index=[], data={'count':[],'extreme_count':[]})
        M = CCD['count'].max() if len(CCD) != 0 else 0
        emo_count.append(M)
    return emo_count

def market_signal(context):
    prices = attribute_history('000300.XSHG', 60, '1d', fields=['close'], skip_paused=True)
    if len(prices) < 60:
        return False
    ma5 = prices['close'].rolling(window=5).mean()
    ma20 = prices['close'].rolling(window=20).mean()
    return (ma5[-1] > ma20[-1] and prices['close'][-1] > ma5[-1])

def get_hot_concept(dct, ccd, date):
    concept_count = {}
    for key in dct:
        lb_count = ccd[ccd.index == key]['count'].iloc[0] 
        for i in dct[key]['jq_concept']:
            if i['concept_name'] in concept_count.keys():
                concept_count[i['concept_name']] += lb_count
            else:
                if i['concept_name'] not in ['转融券标的', '融资融券', '深股通', '沪股通', '国企改革']:
                    concept_count[i['concept_name']] = 1
    df = pd.DataFrame(list(concept_count.items()), columns=['concept_name', 'concept_count'])
    df = df.set_index('concept_name')
    df = df.sort_values(by='concept_count', ascending=False)
    concept = list(df.index)[0:5]
    log.info('*******************************')
    log.info(concept)
    return concept

def get_stocks_by_concept_name(concept_name):
    df_concepts = get_concepts()
    concept_code = df_concepts[df_concepts['name'] == concept_name].index
    if len(concept_code) == 0:
        log.info(f"警告：概念 '{concept_name}' 不存在，已跳过")
        return []
    try:
        stocks = get_concept_stocks(str(concept_code[0]))
        return stocks
    except Exception as e:
        error_type = type(e).__name__
        log.info(f"[错误] 获取概念股票失败 | 概念: {concept_name} | 错误类型: {error_type} | 详情: {str(e)}")
        return []

def get_hl_stock(initial_list, date):
    df = get_price(initial_list, end_date=date, frequency='daily', fields=['close', 'high_limit'], count=1, panel=False, fill_paused=False, skip_paused=False)
    df = df.dropna()
    df = df[df['close'] == df['high_limit']]
    return list(df.code)

def get_continue_count_df(hl_list, date, watch_days):
    if not hl_list:
        return pd.DataFrame(columns=['count', 'extreme_count'])
    df = get_price(hl_list, end_date=date, frequency='daily', 
                   fields=['close', 'high_limit', 'low'], count=watch_days, 
                   panel=False, fill_paused=False, skip_paused=False)
    if df.empty:
        return pd.DataFrame(columns=['count', 'extreme_count'])
    results = []
    for stock in hl_list:
        stock_df = df[df['code'] == stock].copy()
        stock_df = stock_df.sort_values('time', ascending=False)
        stock_df.reset_index(drop=True, inplace=True)
        consecutive_count = 0
        extreme_count = 0
        for i in range(len(stock_df)):
            row = stock_df.iloc[i]
            if row['close'] == row['high_limit']:
                consecutive_count += 1
                if row['low'] == row['high_limit']:
                    extreme_count += 1
            else:
                break
        if consecutive_count > 0:
            results.append({
                'code': stock, 
                'count': consecutive_count, 
                'extreme_count': extreme_count
            })
    result_df = pd.DataFrame(results)
    if not result_df.empty:
        result_df.set_index('code', inplace=True)
    return result_df

def get_factor_filter_df(context, stock_list, jqfactor, sort):
    if len(stock_list) != 0:
        yesterday = context.previous_date
        score_list = get_factor_values(stock_list, jqfactor, end_date=yesterday, count=1)[jqfactor].iloc[0].tolist()
        df = pd.DataFrame(index=stock_list, data={'score': score_list}).dropna()
        df = df.sort_values(by='score', ascending=sort)
    else:
        df = pd.DataFrame(index=[], data={'score': []})
    return df

# ---------- 辅助函数：获取当日最高价（分钟数据）----------
def get_today_high(stock, context):
    """
    获取股票当天截至当前时间的最高价
    """
    # 获取当天从开盘到现在的分钟数据
    df = get_price(stock, start_date=context.current_dt.date(), end_date=context.current_dt, 
                   frequency='1m', fields=['high'], skip_paused=True, panel=False)
    if df is not None and not df.empty:
        return df['high'].max()
    else:
        # 如果没有分钟数据（可能刚开盘或停牌），返回当前价
        return get_current_data()[stock].last_price

# ==============================================================================
# 1. 竞价低开卖出（09:27）
# ==============================================================================
def sell_check_open(context):
    current_data = get_current_data()
    for stock in context.portfolio.positions:
        amount = context.portfolio.positions[stock].closeable_amount
        if amount == 0: continue
        
        open_price = current_data[stock].day_open
        hist = attribute_history(stock, 1, '1d', ['close'], skip_paused=False)
        if len(hist) == 0:
            continue
        prev_close = hist['close'][0]
        
        if open_price < prev_close and open_price > current_data[stock].low_limit:
            log.info(f"【竞价止损】{stock} 低开 (开: {open_price}, 昨: {prev_close})，直接卖出")
            order_target(stock, 0)
        elif abs(open_price - current_data[stock].low_limit) < 0.001:
            log.info(f"【竞价止损】{stock} 跌停，无法卖出")

# ==============================================================================
# 2. 早盘卖出（10:30）- 增加动态开板止盈
# ==============================================================================
def sell_check_morning(context):
    current_data = get_current_data()
    for stock in context.portfolio.positions:
        amount = context.portfolio.positions[stock].closeable_amount
        if amount == 0: continue
        
        curr_price = current_data[stock].last_price
        high_limit = current_data[stock].high_limit
        low_limit  = current_data[stock].low_limit
        avg_cost = context.portfolio.positions[stock].avg_cost
        
        # 获取当日最高价
        day_high = get_today_high(stock, context)
        
        # --- 动态止盈：涨停开板即卖 ---
        # 如果当日曾涨停（最高价接近涨停价），且当前价回落超过3分钱，视为开板
        if day_high >= high_limit - 0.01 and curr_price < high_limit - 0.03:
            log.info(f"【动态止盈】{stock} 涨停开板，立即卖出")
            order_target(stock, 0)
            continue
        
        # --- 原有10:30逻辑 ---
        is_limit = curr_price >= (high_limit - 0.01)
        if is_limit:
            log.info(f"【10:30持仓】{stock} 封板中，继续持有")
            continue
        else:
            pnl_ratio = (curr_price - avg_cost) / avg_cost
            if abs(curr_price - low_limit) < 0.001:
                log.info(f"{stock} 跌停，无法卖出")
                continue
            if pnl_ratio < 0:
                log.info(f"【10:30止损】{stock} 未涨停且亏损 ({pnl_ratio:.2%})，清仓")
                order_target(stock, 0)
            else:
                target_amount = int(amount / 2 / 100) * 100
                if target_amount < 100:
                    order_target(stock, 0)
                    log.info(f"【10:30止盈】{stock} 盈利且股数过少，全卖")
                else:
                    order_target(stock, target_amount)
                    log.info(f"【10:30止盈】{stock} 未涨停但盈利 ({pnl_ratio:.2%})，卖出一半")

# ==============================================================================
# 3. 尾盘卖出（14:30）- 增加动态开板检查（防止开板后被动持有）
# ==============================================================================
def sell_check_afternoon(context):
    current_data = get_current_data()
    for stock in context.portfolio.positions:
        amount = context.portfolio.positions[stock].closeable_amount
        if amount == 0: continue
        
        curr_price = current_data[stock].last_price
        high_limit = current_data[stock].high_limit
        low_limit  = current_data[stock].low_limit
        
        # 获取当日最高价
        day_high = get_today_high(stock, context)
        
        # 同样检查开板情况（尾盘开板更要走）
        if day_high >= high_limit - 0.01 and curr_price < high_limit - 0.03:
            log.info(f"【尾盘动态】{stock} 涨停开板，清仓")
            order_target(stock, 0)
            continue
        
        is_limit = curr_price >= (high_limit - 0.01)
        if is_limit:
            log.info(f"【14:30持仓】{stock} 尾盘封板，持有过夜")
        else:
            if abs(curr_price - low_limit) < 0.001:
                log.info(f"{stock} 跌停，无法卖出")
                continue
            log.info(f"【14:30清仓】{stock} 尾盘未封板，离场")
            order_target(stock, 0)

# ==============================================================================
# 4. 打印持仓信息
# ==============================================================================
def print_position_info(context):
    position_percent = 100 * context.portfolio.positions_value / context.portfolio.total_value
    all_value = context.portfolio.total_value
    for position in list(context.portfolio.positions.values()):
        securities = position.security
        cost = position.avg_cost
        price = position.price
        ret = 100 * (price / cost - 1)
        value = position.value
        amount = position.total_amount
        hold_pct = amount / all_value
        log.info('代码:{}'.format(securities))
        log.info('成本价:{}'.format(format(cost, '.2f')))
        log.info('现价:{}'.format(price))
        log.info('收益率:{}%'.format(format(ret, '.2f')))
        log.info('持仓(股):{}'.format(amount))
        log.info('市值:{}'.format(format(value, '.2f')))
        log.info('———————————————————————————————————')
    log.info('———————————————————————————————————————分割线————————————————————————————————————————')