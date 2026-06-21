# Clone from JoinQuant
# postId: b7269ff269212f891b2bdde52e401b3c
# backtestId: 4789a9dc801ca3ba6beb688575de1b8d
# title: KAMA 趋势策略「社区最牛的趋势交易-已被私募机构征用」

from jqdata import *
from jqfactor import *
import datetime as dt

import pandas as pd
import numpy as np
# -------------------------- 初始化函数 --------------------------
def initialize(context):
    """初始化函数"""
    # 避免使用未来数据
    set_option("avoid_future_data", True)             
    # 设置手续费与滑点
    set_slippage(FixedSlippage(0.00055))
    # 设置交易成本万分之三，不同滑点影响可在归因分析中查看
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0001, close_commission=0.0001,min_commission=5), type='stock')
    set_benchmark('000852.XSHG')                   
    # 持仓数量
    g.max_stock_count = 2
    g.stocks_pool = []
    g.stocks_all = []
    g.target_list = []
    g.loss_effect_history = []
    
    # 止盈止损
    g.MARKET_STATUS = '中性'
    g.TAKE_PROFIT_RATIOS = {'牛市':0.50, '中性':0.50, '熊市':0.40}
    g.MAX_DRAWDOWN_PCT = {'牛市':0.055, '中性':0.055, '熊市':0.055}
    g.STOP_LOSS_PCT = {'牛市':0.09, '中性':0.09, '熊市':0.09}

    # 仓位
    g.POSITION_RATIOS = {'牛市':1.00, '中性':1.00, '熊市':1.00}
    
    # 全局最高价记录（安全稳定）
    g.HIGHEST_PRICE = {}
    g.LOWEST_PRICE = {}
    # 上次止盈的成本价
    g.LAST_PROFIT_PRICE = {}
    
    # 定时任务
    run_daily(perpare, time='09:32:55')      # 开盘前准备
    run_daily(filter_target_list, time='09:33')  # 选股
    # run_daily(sell, time='09:33')
    run_daily(sell, time='11:25')
    run_daily(sell_limitup_broken, time='09:31') 
    run_daily(sell_limitup_broken, time='11:26') 
    # run_daily(buy, time='13:25')        # 交易
    run_daily(sell, time='14:55')
    # run_daily(buy, time='14:56')
    run_daily(sell_limitup_broken, time='14:57') 
    run_daily(record_highest_price, time='every_bar')
    run_daily(record_lowest_price, time='every_bar')

# -------------------------- 每日准备 --------------------------
def perpare(context):
    log.info("="*50)
    g.stocks_all = []
    g.target_list = []
    g.LOWEST_PRICE = dict()
    g.today_bought_stocks = dict()                      # 今天已买入
    # g.MARKET_STATUS = judge_market_status(context)
    log.info(f'当前市场走向: {g.MARKET_STATUS}')
    try:
        all = get_all_stocks(context)
        initial_list = filter_normal_stock(all)
        initial_list = filter_unst_stock(initial_list)
        initial_list = filter_unnew_stock(initial_list, context)
        g.stocks_pool = initial_list
        
        # ----- 1. 赚钱效应 -----
        win_effect, loss_effect = calculate_win_effect(context, all)
        
        # ----- 2. 亏钱效应 -----
        if loss_effect > 0.40:
            log.info(f"赚钱效应 {win_effect:.2%}, 亏钱效应 {loss_effect:.2%}, 不进行操作")
            return
    
        # 情绪过滤：冰点期空仓
        if is_trend_freeze(context):
            return
        
        initial_list = filter_market_cap(initial_list,context)
        initial_list = filter_hot_list(initial_list,context)
        g.stocks_all = initial_list
    except Exception as e:
        log.error(f"perpare异常: {str(e)}")
       
    
    log.info(f'原始股票池数量:{len(g.stocks_all)}')

def calculate_win_effect(context, initial_list):
    """
    计算中证1000赚钱效应：
        成分股中当前价 > 开盘价的股票数量 / 总有效样本数
    """
    up_count = 0
    loss_count = 0
    total_count = len(initial_list)
    current_data = get_current_data(initial_list)
    
    # 批量获取昨日收盘价（避免循环内逐只请求，减少网络IO）
    df_yest = get_price(initial_list, end_date=context.previous_date, count=1,
                        fields=['close'], panel=False, skip_paused=True)
    if df_yest.empty:
        return 1, 1
    
    # 构建 stock -> yesterday_close 的映射
    close_map = df_yest.set_index('code')['close'].to_dict()
    
    for stock in initial_list:
        yesterday_close = close_map.get(stock)
        if yesterday_close is None:
            continue
        current_price = current_data[stock].last_price
        if current_price > yesterday_close:
            up_count += 1
        if current_price < yesterday_close:
            loss_count += 1
    ratio1 = up_count / total_count if total_count > 0 else 1
    ratio2 = loss_count / total_count if total_count > 0 else 1
    return ratio1,ratio2

# -------------------------- 最高价记录 --------------------------
def record_highest_price(context):
    time_now = context.current_dt.strftime('%H:%M:%S')
    if time_now < '09:30:01' or time_now > '15:00:00':
        return    
    positions = context.portfolio.positions
    if not positions:
        return
    current_data = get_current_data(list(positions.keys()))

    for stock in positions:
        pos = positions[stock]
        if pos.closeable_amount == 0: continue

        last_price = current_data[stock].last_price
        avg_cost = pos.avg_cost
        # 更新全局最高价
        if stock not in g.HIGHEST_PRICE:
            g.HIGHEST_PRICE[stock] = last_price
        else:
            g.HIGHEST_PRICE[stock] = max(g.HIGHEST_PRICE[stock], last_price)

# -------------------------- 最低价记录 --------------------------
def record_lowest_price(context):
    time_now = context.current_dt.strftime('%H:%M:%S')
    if time_now < '09:30:01' or time_now > '15:00:00':
        return    
    if len(g.target_list)==0:
        return
    current_data = get_current_data(g.target_list)

    for stock in g.target_list:
        last_price = current_data[stock].last_price
        # 更新全局最低价
        if stock not in g.LOWEST_PRICE:
            g.LOWEST_PRICE[stock] = last_price
        else:
            g.LOWEST_PRICE[stock] = min(g.LOWEST_PRICE[stock], last_price)

    time_now = context.current_dt.strftime('%H:%M:%S')
    if time_now < '09:40:00' or time_now > '14:58:00':
        return  
    
    for stock in g.target_list:
        if stock in  g.today_bought_stocks:
            continue
        last_price = current_data[stock].last_price
        # 检查反弹幅度
        raise_ratio = (last_price - g.LOWEST_PRICE[stock]) / g.LOWEST_PRICE[stock] if g.LOWEST_PRICE[stock]>0 else 0
        if raise_ratio > 0.006:
            log.warn(f"反弹幅度检查 {stock} LOWEST_PRICE:{g.LOWEST_PRICE[stock]} last_price:{last_price} raise_ratio:{raise_ratio:.1%}")
            buy_one(context, stock)
# -------------------------- 核心选股 --------------------------
def today_between_season(context):
        today = context.current_dt.strftime('%m-%d')
        if ('01-15' <= today) and (today <= '01-31'):
            return True
        elif ('04-15' <= today) and (today <= '04-30'):
            return True     
        elif ('12-15' <= today) and (today <= '12-31'):
            return True 
        else:
            return False
    
# -------------------------- 终极版：横盘整理 + 均线高度粘合 + 尾部向上 --------------------------
def is_consolidation(context, stock_code, lookback_days=50, require_ma_convergence=True):
    try:
        # 批量获取数据（高性能）
        df = get_price(stock_code, end_date=context.previous_date, 
                            count=120+lookback_days, frequency='daily', fq='pre', 
                            fields=['close','high','low','volume'], panel=False, fill_paused=False, skip_paused=True)
        if len(df) < lookback_days:
            return False
        recent_df = df.tail(lookback_days).copy()
        # ====================== 条件1：价格横盘（任意连续5天振幅 ≤ 15%） ======================
        # 滑动窗口检查：任意连续5天内，最高最低波动不超过15%
        window_size = 5
        for i in range(len(recent_df) - window_size + 1):
            window = recent_df.iloc[i:i+window_size]
            window_high = window['close'].max()
            window_low = window['close'].min()
            if window_low <= 0:
                return False
            window_range = (window_high - window_low) / window_low * 100
            if window_range > 15:
                return False

        # ====================== 条件2：均线高度粘合（20/60/120） ======================
        if require_ma_convergence:
            temp_df = df.copy()
            temp_df['MA20'] = temp_df['close'].rolling(20).mean()
            temp_df['MA60'] = temp_df['close'].rolling(60).mean()
            temp_df['MA120'] = temp_df['close'].rolling(120).mean()
            temp_df = temp_df.dropna()
            if len(temp_df) < 1:
                return False

            ma_df = temp_df[['MA20', 'MA60', 'MA120']].tail(lookback_days).copy()
            valid_count = 0
            for i in range(len(ma_df)):
                ma20 = ma_df['MA20'].iloc[i]
                ma60 = ma_df['MA60'].iloc[i]
                ma120 = ma_df['MA120'].iloc[i]
                avg = (ma20 + ma60 + ma120) / 3

                dev20 = abs((ma20 - avg) / avg)
                dev60 = abs((ma60 - avg) / avg)
                dev120 = abs((ma120 - avg) / avg)
                max_dev = max(dev20, dev60, dev120)
                if max_dev <= 0.08:  # 10% 以内 = 高度粘合
                    valid_count += 1

            # 80% 时间粘合
            if valid_count / lookback_days < 0.88:
                return False
        return True

    except Exception as e:
        log.error(f"横盘判断异常: {str(e)}")
        return False

# 高性能 选股主函数（稳定选出股票）
def filter_target_list(context):
    g.target_list = []
    backup = []
    if len(g.stocks_all) == 0:
        return

    # 批量获取数据（高性能）
    df_all = get_price(g.stocks_all, end_date=context.previous_date, 
                            count=61, frequency='daily', fq='pre', 
                            fields=['open','close','high','low','volume'], 
                            panel=False)
    
    # 预计算所有指标（提速20倍）
    df_all = df_all.sort_values(['code','time']).reset_index(drop=True)
    
    def calculate_indicators(df):
        # KAMA指标
        df['KAMA_FAST'] = kama(df.close, 5, 8, 30)
        df['KAMA_SLOW'] = kama(df.close, 10, 14, 57)
        return df
    
    df_all = df_all.groupby('code', group_keys=False).apply(calculate_indicators)
    
    # 开始选股
    for stock in g.stocks_all:
        try:
            df = df_all[df_all['code']==stock].copy()
            if len(df) < 60:  # 数据不足跳过
                continue
            # 最新数据
            MA60 = df['close'].tail(60).mean()
            MA10 = df['close'].tail(10).mean()
            VOL60 = df['volume'].tail(60).mean()
            VOL5 = df['volume'].tail(5).mean()
            latest_close = df['close'].iloc[-1]
            # ----------------------- 核心选股条件 -----------------------
            # # 条件0：股价在60日线附近（安全区间，不追高、不抄底）
            # if abs((latest_close - MA60) / MA60 * 100) > 10:
            #     continue

            # 条件1：昨收 < 5日均线
            if latest_close >= MA10*1.05:
                continue

            # # # 条件1：低波动（10日振幅 < 10%，排除暴涨暴跌）
            # high_10d = df['close'].tail(10).max()
            # low_10d = df['close'].tail(10).min()
            # amplitude = abs((high_10d - low_10d) / low_10d * 100)
            # if amplitude < 5 or amplitude > 15:
            #     continue

            # 条件3：温和放量（1.2~3倍，健康启动）
            if VOL5 < VOL60*1.4 or VOL5 > VOL60*10:
                continue
            
            # 条件3：周线不可以是绿线（根据本周是否已有交易日，正确选择比较的周）
            df['week_start'] = df['time'] - pd.to_timedelta(df['time'].dt.weekday, unit='d')
            weekly_open = df.groupby('week_start')['open'].first()
            weekly_close = df.groupby('week_start')['close'].last()
            # 获取 df 中最后一条日期所属的周开始日期
            last_date_in_df = df['time'].max()
            last_week_start = last_date_in_df - pd.to_timedelta(last_date_in_df.weekday(), unit='d')
            # 获取今天的周开始日期（统一转为 pd.Timestamp 以保持类型一致）
            today_week_start = pd.Timestamp(context.current_dt.date()) - pd.Timedelta(days=context.current_dt.weekday())
            if last_week_start == today_week_start:
                # 数据中已包含本周交易日（例如周二~周五），取上一周（倒数第二个）
                week_open = weekly_open.iloc[-2]
                week_close = weekly_close.iloc[-2]
            else:
                # 数据中不包含本周交易日（今天为本周第一个交易日），取最近一周（倒数第一个）
                week_open = weekly_open.iloc[-1]
                week_close = weekly_close.iloc[-1]
            if week_close < week_open:
                continue

            # 条件2：趋势多头（连续3天站稳 + 快线连续向上，彻底过滤假信号）
            fast_series = df['KAMA_FAST'].iloc[-3:]   # 最近3天 快线
            slow_series = df['KAMA_SLOW'].iloc[-3:]   # 最近3天 慢线
            close_series = df['close'].iloc[-3:]      # 最近3天 收盘价
            # 1. 连续3天：收盘价 > 快线（站稳，不留缺口）
            cond_close_above_fast = (close_series > fast_series).all()
            # 2. 连续3天：快线 > 慢线（真正多头排列）
            cond_fast_above_slow = (fast_series > slow_series).all()
            # 3. 快线连续3天 向上（趋势健康，不是脉冲）
            cond_fast_uptrend = (fast_series.diff().iloc[-2:] > 0).all()
            # 三个条件同时满足才通过，极稳
            if not (cond_close_above_fast and cond_fast_above_slow and cond_fast_uptrend):
                continue
        
            
            # 条件4：KAMA明确向上
            if not check_kama_up(df):
                continue

            if not is_consolidation(context, stock):
                continue

            backup.append(stock)
        except Exception as e:
            log.error(f"选股报错 {stock}: {e}")
    
    log.info(f"技术符合数量: {len(backup)}")
    
    # ======================== 新版：主升浪弹性打分 ========================
    candidates = []
    df_turnover_ratio = get_fundamentals(
        query(
            valuation.code, valuation.turnover_ratio
        ).filter(
            valuation.code.in_(backup)
        ),
        date = context.previous_date
    )
    turnover_dict = dict(zip(df_turnover_ratio['code'], df_turnover_ratio['turnover_ratio']))
    for stock in backup:
        # 换手率
        turnover = turnover_dict.get(stock)
        if turnover is None or turnover>20:
            continue
        candidates.append((stock, turnover))
    # ======================== 排序 ========================
    # 1. 按分数从高到低排序（最关键）
    candidates_sorted = sorted(candidates, key=lambda x: x[1], reverse=True)
    # 2. 剔除已持仓股票
    unhold_stocks = [s for s, turnover in candidates_sorted if s not in context.portfolio.positions][:g.max_stock_count]
    # 3. 赋值给目标列表（顺序100%正确：最高分在前）
    g.target_list = unhold_stocks
    log.info(f"最终目标股票: {g.target_list}")

def check_kama_up(df):
    """
    双KAMA判断：上涨趋势 = 快线上穿慢线 / 快线在慢线上方
    返回 True = 多头趋势
    """
    # 确保至少有2根K线用于判断方向
    if len(df) < 2:
        return False

    # 最新值（当前）
    fast_now = df['KAMA_FAST'].iloc[-1]
    slow_now = df['KAMA_SLOW'].iloc[-1]

    # 上一根值（前一根）
    fast_prev = df['KAMA_FAST'].iloc[-2]
    slow_prev = df['KAMA_SLOW'].iloc[-2]

    # === 核心判断：上涨趋势条件 ===
    # 条件1：当前 快线 > 慢线
    # 条件2：上一根 快线 <= 慢线（上穿信号）
    # 两个满足一个，就判定为上涨趋势
    is_uptrend = (fast_now > slow_now) and (fast_prev <= slow_prev or fast_now > slow_prev)

    return is_uptrend
    

# KAMA指标函数
def kama(prices, n=10, fast=2, slow=30):
    """
    卡曼过滤器(KAMA)指标
    prices: 价格序列
    n: 效率比率的周期
    fast: 快速EMA的周期参数
    slow: 慢速EMA的周期参数
    """
    close = prices.copy()
    
    # 计算效率比率(ER)
    # 价格变化绝对值（n期）
    change = (close - close.shift(n)).abs()
    # 波动率（n期价格差绝对值之和）
    volatility = close.diff().abs().rolling(window=n).sum()
    
    # 避免除以0
    er = (change / volatility).fillna(0.0)
    er = er.replace([np.inf, -np.inf], 0.0)
    
    # 计算平滑常数SC
    fast_sc = 2 / (fast + 1)
    slow_sc = 2 / (slow + 1)
    sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2
    
    # 计算KAMA
    kama_values = np.zeros(len(close))
    kama_values[:] = np.nan
    
    # 初始值设为n期简单平均
    if len(close) > n:
        kama_values[n-1] = close.iloc[:n].mean()
        
        for i in range(n, len(close)):
            if pd.notna(sc.iloc[i]) and pd.notna(close.iloc[i]):
                kama_values[i] = kama_values[i-1] + sc.iloc[i] * (close.iloc[i] - kama_values[i-1])
            else:
                kama_values[i] = kama_values[i-1]
    
    return pd.Series(kama_values, index=close.index, name='KAMA')

# -------------------------- 过滤函数 --------------------------
# 获取集合竞价涨停股
def get_morning_auction(context):
    if not g.stocks_pool:
        return [], []
    stock_list = g.stocks_pool
    # 1. 直接使用策略的当前日期
    start_date = pd.to_datetime(context.current_dt).normalize()
    # 2. 批量获取股票实时数据（关键：一次调用）
    current_data_dict = get_current_data(stock_list)

    # 3. 批量获取集合竞价数据（关键：一次调用，传入整个列表）
    auction_df = get_call_auction(
        security=stock_list,  # 核心：批量查询
        start_date=start_date,
        end_date=context.current_dt,
        fields=['time', 'current']
    )

    # 检查竞价数据是否有效
    if auction_df is None or auction_df.empty:
        log.info("当日无集合竞价数据。")
        return []

    # 4. 批量提取涨停价，并与竞价数据合并
    # 4.1 从实时数据中提取涨停价，构建Series
    high_limit_series = pd.Series(
        {code: current_data_dict[code].high_limit for code in stock_list if current_data_dict.get(code)}
    )
    low_limit_series = pd.Series(
        {code: current_data_dict[code].low_limit for code in stock_list if current_data_dict.get(code)}
    )
    # 4.2 将涨停价映射到竞价数据框
    auction_df['high_limit'] = auction_df['code'].map(high_limit_series)
    auction_df['low_limit'] = auction_df['code'].map(low_limit_series)

    # 5. 向量化判断与筛选
    # 5.1 判断每一行是否触及涨停（使用容差避免浮点误差）
    auction_df['is_high'] = (auction_df['current'] - auction_df['high_limit']).abs() < 0.001
    auction_df['is_low'] = (auction_df['current'] - auction_df['low_limit']).abs() < 0.001

    # 5.2 按股票代码分组，只要该股票在竞价时段任意时刻满足条件，即视为涨停
    limit_up_series = auction_df.groupby('code')['is_high'].any()
    limit_down_series = auction_df.groupby('code')['is_low'].any()

    # 获取最终列表
    limit_up_stocks = limit_up_series[limit_up_series].index.tolist()
    limit_down_stocks = limit_down_series[limit_down_series].index.tolist()
    return limit_up_stocks,limit_down_stocks

def get_limit_count(context):
    if not g.stocks_pool:
        return [], []

    df = get_price(g.stocks_pool, end_date=context.previous_date, count=1,
                   fields=['close','high_limit','low_limit'], panel=False)
    if df.empty:
        return [], []
    limit_up_list = df[df.close == df.high_limit]['code'].unique()
    limit_down_list = df[df.close == df.low_limit]['code'].unique()
    return list(limit_up_list), list(limit_down_list)

def filter_limitup_lastdays(context, stock_list):
    if not stock_list:
        return [], []
    today = context.previous_date
    df = get_price(stock_list, end_date=today, frequency='daily', count=10,
                   fields=['close', 'high_limit'], panel=False, fill_paused=False, skip_paused=True)
    if df.empty:
        return [], []

    list_good = df[(df['close'] > df['high_limit']/1.1*1.08)]['code'].unique().tolist()
    list_bad = df[(df['close'] < df['high_limit'] / 1.1 * 0.92)]['code'].unique().tolist()

    return list_good,  list_bad

def filter_hot_list(initial_list,context):
    list1,  low1 = filter_limitup_lastdays(context, initial_list)
    hot_concepts = []
    if len(list1)>0:
        concept_dict = get_concept(list1, context.current_dt)
        limitup_stats = pd.DataFrame(index=list1, data={'count': 1})
        hot_concepts = get_hot_concept(concept_dict, limitup_stats)[:7]

    crush_concepts = []
    if len(low1)>0:
        concept_dict = get_concept(low1, context.current_dt)
        limitdown_stats = pd.DataFrame(index=low1, data={'count': 1})
        crush_concepts = get_hot_concept(concept_dict, limitdown_stats)[:2]
    
    if len(crush_concepts)>0:
        crush_concepts = set(crush_concepts)
        hot_concepts = [x for x in hot_concepts if x not in crush_concepts]
    log.info(f'当前热门概念:{hot_concepts} 已剔除{crush_concepts}')

    hot_stocks = []
    if hot_concepts:
        all_concepts = get_concepts()
        for concept in hot_concepts:
            concept_stocks = get_stocks_by_concept_name(all_concepts, concept)
            hot_stocks = hot_stocks + concept_stocks
    initial_list = list(set(initial_list) & set(hot_stocks))
    return initial_list

def get_limitup_many(hl_list, date, watch_days=20):
    if not hl_list:
        return pd.DataFrame(columns=['count', 'extreme_count'])
    df = get_price(hl_list, end_date=date, frequency='daily',
                   fields=['close', 'high_limit', 'low'], count=watch_days,
                   panel=False, fill_paused=False, skip_paused=False)
    if df.empty:
        return pd.DataFrame(columns=['count', 'extreme_count'])

    results = []
    for stock in hl_list:
        stock_df = df[df['code'] == stock].sort_values('time', ascending=False).reset_index(drop=True)
        consecutive = 0
        for i, row in stock_df.iterrows():
            if row['close'] == row['high_limit']:
                consecutive += 1
            else:
                break
        if consecutive == 0:
            continue
        extreme = (stock_df['low'] == stock_df['high_limit']).sum()
        results.append({'code': stock, 'count': consecutive, 'extreme_count': extreme})
    result_df = pd.DataFrame(results)
    if not result_df.empty:
        result_df.set_index('code', inplace=True)
    return result_df

def get_hot_concept(concept_dict, limitup_stats_df):
    concept_count = {}
    for stock in concept_dict:
        lb_count = 1
        if stock in limitup_stats_df.index:
            lb_count = limitup_stats_df.loc[stock, 'count']
        for concept in concept_dict[stock]['jq_concept']:
            concept_name = concept['concept_name']
            if concept_name in ['转融券标的', '融资融券', '深股通', '沪股通', '国企改革']:
                continue
            if concept_name in concept_count:
                concept_count[concept_name] += lb_count
            else:
                concept_count[concept_name] = lb_count
    df = pd.DataFrame(list(concept_count.items()), columns=['concept_name', 'concept_count'])
    df.set_index('concept_name', inplace=True)
    df.sort_values(by='concept_count', ascending=False, inplace=True)
    hot_concepts = list(df.index)[:8]
    return hot_concepts

def get_stocks_by_concept_name(all_concepts, concept_name):
    df_concepts = all_concepts
    concept_code = df_concepts[df_concepts['name'] == concept_name].index
    if len(concept_code) == 0:
        log.info(f"警告：概念 '{concept_name}' 不存在，已跳过")
        return []
    try:
        stocks = get_concept_stocks(str(concept_code[0]))
        return stocks
    except Exception as e:
        log.info(f"[错误] 获取概念股票失败 | 概念: {concept_name} | 详情: {str(e)}")
        return []

def get_all_stocks(context):
    initial_list = get_all_securities('stock', context.previous_date).index.tolist()
    return initial_list

def filter_normal_stock(initial_list):
    return [s for s in initial_list if s[:2] in ('00','60','30')]

def filter_unnew_stock(initial_list, context, days=100):
    end_dt = context.current_dt.date()
    return [s for s in initial_list if get_security_info(s).start_date < end_dt-dt.timedelta(days=days)]

def filter_unst_stock(initial_list):
    c = get_current_data(initial_list)
    return [s for s in initial_list if not c[s].is_st and not c[s].paused and '退' not in c[s].name]

def filter_market_cap(stock_list, context, min_cap=40, max_cap=300):
    if today_between_season(context):
        df = get_fundamentals(
        query(
            valuation.code
        ).filter(
            valuation.code.in_(stock_list),
            valuation.market_cap.between(min_cap, max_cap),
            valuation.circulating_market_cap.between(min_cap, max_cap),
            valuation.pe_ratio>0,
            indicator.roa>0
        ),date = context.previous_date)
    else:
        df = get_fundamentals(
        query(
            valuation.code
        ).filter(
            valuation.code.in_(stock_list),
            valuation.market_cap.between(min_cap, max_cap),
            valuation.circulating_market_cap.between(min_cap, max_cap),
            # valuation.pe_ratio>0,
            # indicator.roa>0
        ),date = context.previous_date)
    return list(df['code'])

# -------------------------- 交易 --------------------------
def buy(context):
    if not g.target_list:
        return
    position_ratio = g.POSITION_RATIOS[g.MARKET_STATUS]
    target_value = context.portfolio.total_value * position_ratio

    per_stock_value = target_value / g.max_stock_count
    current_data = get_current_data(g.target_list)
    filter_result = [s for s in g.target_list if not current_data[s].is_st and not current_data[s].paused and '退' not in current_data[s].name][:g.max_stock_count]
    for stock in filter_result:
        if len(context.portfolio.positions) >= g.max_stock_count: 
            break
        if stock in context.portfolio.positions: 
            continue
        if current_data[stock].paused: 
            continue
        if current_data[stock].last_price >= current_data[stock].high_limit:
            log.info(f"{stock} 涨停，跳过买入")
            continue
        trend_broken, fast_broken = is_trend_broken(stock, context)
        if trend_broken or fast_broken:
            continue
        volume = int((per_stock_value / current_data[stock].last_price) // 100) * 100
        if volume > 0:
            log.info(f"买入 {stock} 数量:{volume} {current_data[stock].last_price}")
            order(stock, volume)
            g.HIGHEST_PRICE[stock] = current_data[stock].last_price

def get_rest(context):
    sell_count = 0
    # for task_id, task in list(g.order_tasks.items()):
    #     if task.get('status') == 0 and task.get('direction') == "sell":
    #         sell_count += 1
    rest = g.max_stock_count - len(context.portfolio.positions) + sell_count
    return rest

def buy_one(context, s):
    current_data = get_current_data([s])
    g.today_bought_stocks[s] = current_data[s].last_price
    time_at = context.current_dt.strftime('%Y-%m-%d %H:%M:%S')
    position_ratio = g.POSITION_RATIOS[g.MARKET_STATUS]
    # 计算可用资金和可买数量
    rest = get_rest(context)
    if rest == 0:
        return
    if s in context.portfolio.positions: 
        return
    if current_data[s].paused: 
        return
    if current_data[s].last_price >= current_data[s].high_limit:
        log.info(f"{s} 涨停，跳过买入")
        return

    base_position = context.portfolio.available_cash / rest
    cash_per_stock = base_position * position_ratio
    if cash_per_stock < 20000:
        return
    
    last_price = current_data[s].last_price
    long_price = np.round(max(last_price * 1.02, last_price + 0.02), 2)
    trade_price = min(long_price, current_data[s].high_limit)
    volume = int((cash_per_stock / trade_price) // 100) * 100
    if volume == 0:
        return
    
    # if g.run_mode == "正式环境":
    #     log.info(f'买入{s}价格计算：last_price:{last_price} long_price:{long_price} high_limit:{current_data[s].high_limit} 计算结果:{trade_price}')
    #     call_qmt_order_volume(context, s, "buy", trade_price, volume, True)
    # else:
    #     order(s, volume)
    order(s, volume)
    simple_code = s.split('.')[0]
    logstr = f'模拟买入: {simple_code} {current_data[s].name} high_limit:{current_data[s].high_limit} trade_price:{trade_price}'
    log.info(logstr)
    # send_feishu_message(logstr, time_at)

# -------------------------- 止盈止损 --------------------------
def sell(context, want_clear = False):
    current_data = get_current_data(list(context.portfolio.positions.keys()))
    take_profit_ratio = g.TAKE_PROFIT_RATIOS[g.MARKET_STATUS]

    # 尾盘条件卖出
    for stock, pos in context.portfolio.positions.items():
        if pos.closeable_amount == 0:
            continue

        curr_price = current_data[stock].last_price
        avg_cost = pos.avg_cost
        profit_rate = (curr_price - avg_cost) / avg_cost if avg_cost != 0 else -999
        hold_days = (context.current_dt - pos.init_time).days

        # 市场危险信号
        if want_clear:
            order_target_value(stock, 0)
            log.info(f"连续亏钱效应 清仓卖出 {stock} {curr_price}")
            if stock in g.HIGHEST_PRICE:del g.HIGHEST_PRICE[stock]
            if stock in g.LAST_PROFIT_PRICE:del g.LAST_PROFIT_PRICE[stock]
            continue
    
        # 趋势破位
        trend_broken, fast_broken = is_trend_broken(stock, context)
        if trend_broken and fast_broken and not is_60d_broken(stock, context):
            order_target_value(stock, 0)
            log.info(f"[尾盘] 趋势破位卖出 {stock} {curr_price}")
            if stock in g.HIGHEST_PRICE:del g.HIGHEST_PRICE[stock]
            if stock in g.LAST_PROFIT_PRICE:del g.LAST_PROFIT_PRICE[stock]
            continue

        # 止盈
        if profit_rate > take_profit_ratio:
            if stock not in g.LAST_PROFIT_PRICE.keys():
                # 止盈一半
                g.LAST_PROFIT_PRICE[stock] = curr_price
                target_amount = int(pos.closeable_amount / 2 / 100) * 100
                if target_amount * curr_price<30000:
                    order_target_value(stock, 0)
                    if stock in g.HIGHEST_PRICE:del g.HIGHEST_PRICE[stock]
                    if stock in g.LAST_PROFIT_PRICE:del g.LAST_PROFIT_PRICE[stock]
                    log.info(f"止盈全部 {stock} | 盈利:{profit_rate:.2%}")
                    continue
                else:
                    order(stock, -target_amount)
                    log.info(f"止盈一半 {stock} | 盈利:{profit_rate:.2%}")
            else:
                # 止盈全部
                profit_rate = (curr_price - g.LAST_PROFIT_PRICE[stock]) / g.LAST_PROFIT_PRICE[stock] if g.LAST_PROFIT_PRICE[stock] != 0 else -999
                if profit_rate > take_profit_ratio / 2:
                    order_target_value(stock, 0)
                    log.info(f"止盈全部 {stock} | 盈利:{profit_rate:.2%}")
                    if stock in g.HIGHEST_PRICE:del g.HIGHEST_PRICE[stock]
                    if stock in g.LAST_PROFIT_PRICE:del g.LAST_PROFIT_PRICE[stock]
                    continue

        # 止损
        if profit_rate < - g.STOP_LOSS_PCT[g.MARKET_STATUS]:
            order_target_value(stock, 0)
            log.info(f"止损 {stock} | 盈利:{profit_rate:.2%}")
            if stock in g.HIGHEST_PRICE:del g.HIGHEST_PRICE[stock]
            if stock in g.LAST_PROFIT_PRICE:del g.LAST_PROFIT_PRICE[stock]
            continue


        # 实时高点回落卖出
        highest = g.HIGHEST_PRICE[stock]
        max_profit_rate = (highest - avg_cost) / avg_cost if avg_cost != 0 else 0
        if profit_rate > 0:
            if (max_profit_rate - profit_rate) > g.MAX_DRAWDOWN_PCT[g.MARKET_STATUS]:
                target_value = context.portfolio.total_value * g.POSITION_RATIOS[g.MARKET_STATUS]
                per_stock_value = target_value / g.max_stock_count
                target_amount = max(int(pos.closeable_amount / 2 / 100) * 100, 500)
                if per_stock_value* 3 / 4 < pos.value:
                    order(stock, -target_amount)
                    log.info(f"[实时回落卖出] {stock} | 最高:{highest:.2f} → 现价:{curr_price:.2f} | 回撤:{(max_profit_rate - profit_rate):.1%}")
                else:
                    order_target_value(stock, 0)
                    log.info(f"[实时回落卖出] {stock} | 最高:{highest:.2f} → 现价:{curr_price:.2f} | 回撤:{(max_profit_rate - profit_rate):.1%}")
                    if stock in g.HIGHEST_PRICE: del g.HIGHEST_PRICE[stock]
                    if stock in g.LAST_PROFIT_PRICE:del g.LAST_PROFIT_PRICE[stock]

        # 持仓超时
        if hold_days > 12 and profit_rate < take_profit_ratio / 4:
            order_target_value(stock, 0)
            log.info(f"[尾盘] 持仓超时 {stock}")
            if stock in g.HIGHEST_PRICE: del g.HIGHEST_PRICE[stock]
            if stock in g.LAST_PROFIT_PRICE: del g.LAST_PROFIT_PRICE[stock]

        # 指标止损
        crack_rate = (curr_price - highest) / curr_price if curr_price != 0 else -999
        if crack_rate < - g.STOP_LOSS_PCT[g.MARKET_STATUS] * 3/4:
            df_stock = get_price(stock, end_date=context.previous_date, 
                                    count=20, frequency='daily', fq='pre', 
                                    fields=['close'], 
                                    panel=False)
            MA20 = df_stock['close'].tail(20).mean()
            if curr_price < MA20:
                order_target_value(stock, 0)
                log.info(f"止损 {stock} | 盈利:{profit_rate:.2%}")
                if stock in g.HIGHEST_PRICE:del g.HIGHEST_PRICE[stock]
                if stock in g.LAST_PROFIT_PRICE:del g.LAST_PROFIT_PRICE[stock]
                continue


def sell_limitup_broken(context):
    """
    11:30 卖出规则：
    遍历所有持仓，若昨日涨停（昨收 >= 昨日涨停价 * 0.999）且今日未涨停（当前价 < 今日涨停价 * 0.999）
    且当前股价小于昨日收盘价，则卖出；否则不操作。
    """
    positions = context.portfolio.positions
    current_data = get_current_data(positions)
    time_now = context.current_dt.strftime('%H:%M:%S')
    for stock, pos in positions.items():
        if pos.total_amount == 0 or pos.closeable_amount == 0:
            continue
        try:
            hist_yesterday = get_price(stock, end_date=context.previous_date, count=1,
                                    fields=['close','low','high_limit'])
            yesterday_close = hist_yesterday['close'][0]
            yesterday_low = hist_yesterday['low'][0]
            yesterday_high_limit = hist_yesterday['high_limit'][0]
        except Exception as e:
            log.error(f"无法获取 {stock} 昨日数据：{e}")
            continue

        current_price = current_data[stock].last_price
        today_high_limit = current_data[stock].high_limit
        stock_name = current_data[stock].name

        is_limit_up_yestoday = (yesterday_close >= yesterday_high_limit * 0.999)
        is_limit_up_wholeday = (yesterday_close >= yesterday_high_limit * 0.999 and yesterday_close-yesterday_low<0.05)
        is_limit_up_today = (current_price >= today_high_limit * 0.999)

        
        # 一字板的变动
        if is_limit_up_wholeday and not is_limit_up_today:
            order_target_value(stock, 0)
            log.info(f"一字破板卖出{stock_name}({stock})")
        # 跌破开盘价
        if is_limit_up_yestoday and not is_limit_up_today and current_price < current_data[stock].day_open:
            order_target_value(stock, 0)
            log.info(f"破板低于开盘价卖出{stock_name}({stock})")
        if time_now < '13:00:00':
            continue  
        # 卖出条件：昨日涨停、今日未涨停、且当前价低于昨日收盘价
        if is_limit_up_yestoday and not is_limit_up_today:
            order_target_value(stock, 0)
            log.info(f"破板卖出{stock_name}({stock})")

def is_60d_broken(stock, context):
    try:
        # 1. 获取60日收盘价数据（包含最新实时价）
        df = get_bars(
            security=stock,           
            count=60,                 # 取60根K线
            unit='1d',                # 日线级别
            fields=['close'],         
            include_now=True,         # 包含盘中实时价格
            end_dt=context.current_dt,
            fq_ref_date=context.current_dt.date(),
            df=True                   
        )
        
        # 数据校验：确保取到了有效数据
        if df.empty or len(df) < 60:
            return False
        
        # 2. 计算60日均线
        ma60 = df['close'].mean()
        
        # 3. 获取当前最新价格（最后一行就是最新价）
        current_price = df['close'].iloc[-1]
        
        # 4. 判断：当前价格 < 60日均线 → 视为跌破
        is_broken = current_price < ma60
        
        return is_broken

    except Exception as e:
        # 异常处理：数据获取失败、停牌等情况
        print(f"[{stock}] 60日均线判断异常: {str(e)}")
        return False

def is_trend_broken(stock, context):
    try:
        # 1. 获取盘中实时价格
        df = get_bars(
            security=stock,           
            count=60,                 
            unit='1d',                
            fields=['close'],         
            include_now=True,         
            end_dt=context.current_dt,
            fq_ref_date=context.current_dt.date(),
            df=True                   
        )

        # 计算指标
        df['KAMA_FAST'] = kama(df.close, 5, 8, 30)
        df['KAMA_SLOW'] = kama(df.close, 10, 14, 57)

        # ============= 两个判断 =============
        # 1. 原逻辑：KAMA整体趋势是否走坏（True=破位）
        trend_broken = not check_kama_up(df)

        # 2. 新增：当前价 是否 跌破 KAMA快线（True=跌破快线）
        current_price = df['close'].iloc[-1]
        kama_fast = df['KAMA_FAST'].iloc[-1]
        fast_broken = current_price < kama_fast*0.95  # 收盘价 < 快线 = 破位
        # 返回两个布尔值：(整体趋势破位, 跌破快线)
        return trend_broken, fast_broken
    except Exception as e:
        log.error(f"趋势破位异常 {stock}: {str(e)}")
        # 异常时默认返回：趋势没破, 没破快线
        return False, False
    
def judge_market_status(context, index_code='000852.XSHG', sensitivity='medium'):
    """
    判断市场状态 - 只返回'牛市'/'熊市'/'中性'
    
    参数:
    sensitivity: 'high' - 高灵敏度, 'medium' - 中灵敏度, 'low' - 低灵敏度
    """
    try:
        # 使用 get_bars 获取数据，include_now=True 包含当天未完结数据
        bars = get_bars(
            security=index_code,           
            count=120,                 # 取60根K线
            unit='1d',                # 日线级别
            fields=['close', 'volume'],         
            include_now=True,         # 包含盘中实时价格
            end_dt=context.current_dt,
            fq_ref_date=context.current_dt.date(),
            df=True                   
        )
        
        if bars is None or len(bars) < 60:
            # 降级方案
            df = get_price(index_code, count=120, fields=['close'], panel=False)
            close_data = df['close']
            volume_data = None
        else:
            df_bars = pd.DataFrame(bars)
            close_data = df_bars['close']
            volume_data = df_bars['volume'] if 'volume' in df_bars.columns else None
        
        # 根据灵敏度调整参数
        if sensitivity == 'high':
            fast_n, fast_ema, slow_n, slow_ema = 8, 2, 15, 40
            recent_days = 3
            trend_days = 5
            ma_short, ma_long = 10, 20
            
        elif sensitivity == 'low':
            fast_n, fast_ema, slow_n, slow_ema = 12, 3, 25, 60
            recent_days = 8
            trend_days = 12
            ma_short, ma_long = 15, 30
            
        else:  # medium
            fast_n, fast_ema, slow_n, slow_ema = 10, 2, 20, 50
            recent_days = 5
            trend_days = 10
            ma_short, ma_long = 12, 24
        
        # 创建DataFrame
        df = pd.DataFrame({'close': close_data})
        if volume_data is not None:
            df['volume'] = volume_data
        
        # 计算KAMA
        df['KAMA_FAST'] = kama(df['close'], n=fast_n, fast=fast_ema, slow=slow_ema)
        df['KAMA_SLOW'] = kama(df['close'], n=slow_n, fast=fast_ema, slow=slow_ema)
        
        # === 核心判断指标 ===
        
        # 1. 价格与KAMA的位置关系
        close_ma = df['close'].rolling(window=recent_days).mean().iloc[-1]
        kama_fast_ma = df['KAMA_FAST'].rolling(window=recent_days).mean().iloc[-1]
        kama_slow_ma = df['KAMA_SLOW'].rolling(window=recent_days).mean().iloc[-1]
        
        price_above_fast = close_ma > kama_fast_ma
        fast_above_slow = kama_fast_ma > kama_slow_ma
        
        # 2. 趋势方向
        if len(df) >= trend_days:
            kama_fast_trend = df['KAMA_FAST'].iloc[-1] > df['KAMA_FAST'].iloc[-trend_days]
        else:
            kama_fast_trend = False
        
        # 3. 均线系统
        ma_short_ma = df['close'].rolling(window=ma_short).mean()
        ma_long_ma = df['close'].rolling(window=ma_long).mean()
        ma_trend_up = ma_short_ma.iloc[-1] > ma_short_ma.iloc[-trend_days] if len(ma_short_ma) >= trend_days else False
        
        # 4. 中期动量
        if len(df) >= 20:
            price_momentum = (df['close'].iloc[-1] - df['close'].iloc[-20]) / df['close'].iloc[-20]
        else:
            price_momentum = 0
        
        # === 简化评分系统 ===
        bullish_score = 0
        bearish_score = 0
        
        # 核心条件（权重高）
        if price_above_fast:
            bullish_score += 2
        else:
            bearish_score += 2
            
        if fast_above_slow:
            bullish_score += 2
        else:
            bearish_score += 2
        
        # 趋势条件
        if kama_fast_trend:
            bullish_score += 1.5
        else:
            bearish_score += 1.5
        
        # 均线条件
        if ma_trend_up:
            bullish_score += 1
        else:
            bearish_score += 1
        
        # 动量条件
        if price_momentum > 0.01:
            bullish_score += 0.5
        elif price_momentum < -0.01:
            bearish_score += 0.5
        
        # === 最终判断 ===
        # 根据灵敏度设置阈值
        if sensitivity == 'high':
            threshold = 5.0
        elif sensitivity == 'low':
            threshold = 7.0
        else:  # medium
            threshold = 6.0
        
        # 判断
        if bullish_score >= threshold and bullish_score > bearish_score:
            return '牛市'
        elif bearish_score >= threshold and bearish_score > bullish_score:
            return '熊市'
        else:
            return '中性'
            
    except Exception as e:
        log.error(f"判断市场状态出错: {e}")
        return '中性'

def is_trend_freeze(context):
    # 是否冰点期
    list1, list2 = get_limit_count(context)
    list3, list4 = get_morning_auction(context)
    if get_market_emotion(len(list1), len(list2),len(list3), len(list4), context) == "冰点期":
        return True
    return False

def get_market_emotion(high_num, low_num, morning_high, morning_low, context):
    """
    纯阈值版情绪判断（无打分、无加权、不过拟合、最实盘）
    """
    yest_data = attribute_history('000001.XSHG', 2, '1d', ['close'], skip_paused=True)
    time_at = context.current_dt.strftime('%Y-%m-%d %H:%M:%S')
    ticks = get_ticks("000001.XSHG", end_dt=time_at, count=1,fields=['time','open','current'])
    open0 = ticks[-1]['open']
    close1 = yest_data['close'].iloc[-1] 
    close2 = yest_data['close'].iloc[-2] 
    # 两天跌幅之和
    pct_change =  (open0 - close2) / close2 * 100 if close2>0 else -999
    # 1. 【冰点期】：极端恐慌 → 空仓
    if (low_num >= 40 or                  # 跌停炸锅
        morning_low - morning_high >= 10 or  # 竞价核按钮
        high_num - low_num <= 10 or
        (pct_change < -3.5 or (open0 < close1 and pct_change<-2))):
        log.warn(f"❄️冰点期：high_num:{high_num} low_num:{low_num} 两天跌幅:{pct_change:.2f}%")
        return "冰点期"

    return "其他期"