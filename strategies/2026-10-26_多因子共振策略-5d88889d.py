# Clone from JoinQuant
# postId: 5d88889d80fa69d9f630d452799827e1
# backtestId: 64d963e81a66bebd7d9020b788ae7cff
# title: 多因子共振策略



from jqdata import *
from jqfactor import *
import numpy as np
import pandas as pd
from datetime import time, timedelta
import talib  
from collections import defaultdict 

# ======== 策略常量与全局状态字典 ========
MARKET_INDEX = '399101.XSHE'

# 【关键修复】使用全局字典 g 替代 context.globals
g = {}

# ====================== 辅助工具函数 ======================
def filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]

def filter_st_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].is_st and 'ST' not in current_data[stock].name and '*' not in current_data[stock].name and '退' not in current_data[stock].name]

def filter_kcbj_stock(stock_list):
    return [stock for stock in stock_list if not (stock[0] == '4' or stock[0] == '8' or stock[:2] == '68' or stock[:2] == '30')]

def filter_limitup_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list if stock in context.portfolio.positions.keys() or last_prices[stock][-1] < current_data[stock].high_limit]

def filter_limitdown_stock(context, stock_list):
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list if (stock in context.portfolio.positions.keys() or last_prices[stock][-1] > current_data[stock].low_limit)]

def filter_new_stock(context, stock_list):
    yesterday = context.previous_date
    return [stock for stock in stock_list if not (yesterday - get_security_info(stock).start_date) < timedelta(days=375)]

def filter_not_buy_again(stock_list, not_buy_again):
    return [stock for stock in stock_list if stock not in not_buy_again]

def order_target_value_(security, value):
    return order_target_value(security, value)

def close_position(position):
    security = position.security
    order = order_target_value_(security, 0)
    if order is not None:
        if order.status == OrderStatus.held and order.filled == order.amount:
            return True
    return False

def open_position(security, value):
    order = order_target_value_(security, value)
    if order is not None and order.filled > 0:
        return True
    return False

def buy_security(context, target_list, cash=0, buy_number=0):
    global g
    position_count = len(context.portfolio.positions)
    target_num = g['stock_num']
    if cash == 0:
        cash = context.portfolio.total_value
    if buy_number == 0:
        buy_number = target_num
    bought_num = 0
    if target_num > position_count:
        value = cash / target_num
        if value < 2000:
            log.warning("单只股票分配资金不足2000元")
        
        for stock in target_list:
            if context.portfolio.positions[stock].total_amount == 0:
                if bought_num < buy_number:
                    if open_position(stock, value):
                        g['not_buy_again'].append(stock)
                        bought_num += 1
                        if len(context.portfolio.positions) == target_num:
                            break

def clean_expired_cache(context):
    global g
    current_date = context.previous_date
    expired_keys = []
    if 'cache' in g:
        for key, (cache_time, _) in g['cache'].items():
            if (current_date - cache_time).days >= g.get('cache_timeout', 3):
                expired_keys.append(key)
        for key in expired_keys:
            del g['cache'][key]

# ====================== 核心策略函数 ======================
def get_unified_stock_pool(context, top_n=200):
    pool = get_index_stocks(MARKET_INDEX)
    pool = filter_new_stock(context, pool)
    pool = filter_kcbj_stock(pool)
    pool = filter_st_stock(pool)
    pool = filter_paused_stock(pool)
    pool = filter_limitup_stock(context, pool)
    pool = filter_limitdown_stock(context, pool)
    
    q = query(valuation.code).filter(valuation.code.in_(pool)) \
        .order_by(valuation.circulating_market_cap.asc()).limit(top_n)
    df = get_fundamentals(q)
    return df['code'].tolist() if not df.empty else []

def get_stock_list_industry(context, base_pool):
    global g
    try:
        ind_results = get_industry(base_pool, date=context.current_dt.date())
        industry_map = {}
        for stock in base_pool:
            if stock in ind_results:
                name = ind_results[stock].get('sw_l2', {}).get('industry_name')
                if name:
                    if name not in industry_map:
                        industry_map[name] = stock
        return list(industry_map.values())[:g['stock_num_per_strategy']*2]
    except Exception as e:
        log.error(f"行业筛选出错: {e}")
        return base_pool[:g['stock_num_per_strategy']*2]

def get_stock_list_eps(context, base_pool):
    global g
    q = query(valuation.code, indicator.eps, valuation.market_cap) \
        .filter(valuation.code.in_(base_pool)) \
        .filter(indicator.eps > 0) \
        .order_by(valuation.market_cap.asc()) \
        .limit(100)
    df = get_fundamentals(q)
    if df.empty:
        return []
    df['market_cap_rank'] = df['market_cap'].rank(ascending=True)
    df['eps_rank'] = df['eps'].rank(ascending=False)
    df['composite_score'] = df['market_cap_rank'] * 0.6 + df['eps_rank'] * 0.4
    df = df.sort_values('composite_score', ascending=True)
    return df['code'].tolist()[:g['stock_num_per_strategy']*2]

def get_stock_list_moneyflow(context, base_pool):
    global g
    if not g.get('top_sectors'):
        return []
    try:
        ind_results = get_industry(base_pool, date=context.current_dt.date())
        filtered = []
        for stock in base_pool:
            if stock in ind_results:
                sw_l2_name = ind_results[stock].get('sw_l2', {}).get('industry_name')
                if sw_l2_name and sw_l2_name in g['top_sectors']:
                    filtered.append(stock)
        return filtered[:g['stock_num_per_strategy']*2]
    except Exception as e:
        log.error(f"资金流行业筛选出错: {e}")
        return []

def get_history_highlimit(context, stock_list, days=3*250, p=0.10):
    df = get_price(stock_list, end_date=context.previous_date, frequency="daily", fields=["close", "high_limit"], count=days, panel=False)
    if df.empty:
        return []
    df = df[df["close"] == df["high_limit"]]
    grouped_result = df.groupby('code').size().reset_index(name='count')
    grouped_result = grouped_result.sort_values(by=["count"], ascending=False)
    result_list = grouped_result["code"].tolist()[:max(1, int(len(grouped_result)*p))]
    return result_list

def get_start_point(context, stock_list, days=3*250):
    df = get_price(stock_list, end_date=context.previous_date, frequency="daily", fields=["open", "low", "close", "high_limit"], count=days, panel=False)
    if df.empty:
        return stock_list
    stock_start_point = {}
    current_data = get_current_data()
    for code, group in df.groupby('code'):
        group = group.sort_values('time')
        limit_hit_rows = group[group['close'] == group['high_limit']]
        if not limit_hit_rows.empty:
            latest_limit_index = limit_hit_rows.iloc[-1].name
            previous_rows = group[group.index <= latest_limit_index].iloc[::-1]
            for idx, row in previous_rows.iterrows():
                if row['close'] < row['open']:
                    stock_start_point[code] = row['low']
                    break
    stock_price_bias = {}
    for code, start_point in stock_start_point.items():
        if code in current_data and start_point > 0:
            stock_price_bias[code] = current_data[code].last_price / start_point
    sorted_list = sorted(stock_price_bias.items(), key=lambda x: x[1], reverse=False)
    result = [i[0] for i in sorted_list]
    return result if result else stock_list

def filter_recent_extreme_movements(context, stock_list):
    if not stock_list:
        return []
    end_date = context.previous_date
    df = get_price(stock_list, end_date=end_date, frequency='daily', fields=['close', 'high_limit', 'low_limit', 'volume'], count=3, panel=False, fill_paused=False)
    exclude_stocks = set()
    for stock in stock_list:
        stock_data = df[df['code'] == stock]
        if len(stock_data) < 3:
            exclude_stocks.add(stock)
            continue
            
        has_limit = (stock_data['close'] == stock_data['high_limit']).any() or (stock_data['close'] == stock_data['low_limit']).any()
        yesterday_not_limit = stock_data.iloc[-1]['close'] != stock_data.iloc[-1]['high_limit']
        if has_limit and yesterday_not_limit:
            exclude_stocks.add(stock)
            continue
            
        if yesterday_not_limit:
            vol_bars = get_bars(stock, count=120, unit='1d', fields=['volume'], include_now=False, df=True)
            if len(vol_bars) > 20:
                max_vol_120 = vol_bars['volume'].max()
                avg_vol_20 = vol_bars['volume'].iloc[-20:].mean()
                yesterday_vol = stock_data.iloc[-1]['volume']
                
                cond_huge_vol = yesterday_vol > 0.9 * max_vol_120
                cond_abnormal_vol = yesterday_vol > 2.0 * avg_vol_20
                
                if cond_huge_vol or cond_abnormal_vol:
                    exclude_stocks.add(stock)
                    
    return [s for s in stock_list if s not in exclude_stocks]

def get_stock_list_limitgene(context, base_pool):
    global g
    pool = base_pool[:g['init_stock_count']]
    pool = get_history_highlimit(context, pool, g['limit_days_window'])
    pool = get_start_point(context, pool, g['limit_days_window'])
    pool = filter_recent_extreme_movements(context, pool)
    return pool[:g['stock_num_per_strategy']*2]

def multi_strategy_get_stock_list(context):
    global g
    current_date = context.previous_date
    cache_key = f"multi_strategy_{current_date}"
    
    if 'cache' in g and cache_key in g['cache']:
        cache_time, cached_data = g['cache'][cache_key]
        if (current_date - cache_time).days < g.get('cache_timeout', 3):
            return cached_data
    
    base_pool = get_unified_stock_pool(context, top_n=200)
    scores = defaultdict(float)
    
    # 1. 涨停基因策略（权重 1.5）
    if g['enable_limitgene']:
        genes = get_stock_list_limitgene(context, base_pool)
        for stock in genes[:g['stock_num_per_strategy']]:
            scores[stock] += 1.5

    # 2. 资金流入策略（权重 1.4）
    if g['enable_moneyflow']:
        flows = get_stock_list_moneyflow(context, base_pool)
        for stock in flows[:g['stock_num_per_strategy']]:
            scores[stock] += 1.4

    # 3. EPS策略（权重 1.2）
    if g['enable_eps']:
        eps_list = get_stock_list_eps(context, base_pool)
        for stock in eps_list[:g['stock_num_per_strategy']]:
            scores[stock] += 1.2

    # 4. 行业分散（权重 1.0）
    if g['enable_industry']:
        ind_list = get_stock_list_industry(context, base_pool)
        for stock in ind_list[:g['stock_num_per_strategy']]:
            scores[stock] += 1.0

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    final_list = [s for s, _ in ranked[:g['stock_num'] * 2]]
    
    if 'cache' in g:
        g['cache'][cache_key] = (current_date, final_list)
    
    return final_list

def huanshoulv(context, stock, is_avg=False):
    if is_avg:
        end_date = context.previous_date
        df_volume = get_price(stock, end_date=end_date, frequency='daily', fields=['volume'], count=20)
        df_cap = get_valuation(stock, end_date=end_date, fields=['circulating_cap'], count=1)
        circulating_cap = df_cap['circulating_cap'].iloc[0] if not df_cap.empty else 0
        if circulating_cap == 0:
            return 0.0
        df_volume['turnover_ratio'] = df_volume['volume'] / (circulating_cap * 10000)
        return df_volume['turnover_ratio'].mean()
    else:
        date_now = context.current_dt
        df_vol = get_price(stock, start_date=date_now.date(), end_date=date_now, frequency='1m', fields=['volume'],
                           skip_paused=False, fq='pre', panel=True, fill_paused=False)
        volume = df_vol['volume'].sum() if not df_vol.empty else 0
        date_pre = context.previous_date
        df_circulating_cap = get_valuation(stock, end_date=date_pre, fields=['circulating_cap'], count=1)
        circulating_cap = df_circulating_cap['circulating_cap'].iloc[0] if not df_circulating_cap.empty else 0
        if circulating_cap == 0:
            return 0.0
        turnover_ratio = volume / (circulating_cap * 10000)
        return turnover_ratio

def detect_divergence(stock, context):
    fast, slow, sign = 12, 26, 9
    rows = (fast + slow + sign) * 5
    grid = attribute_history(stock, rows, fields=['close']).dropna()
    if len(grid) < rows:
        return False
    
    try:
        diff, dea, macd_hist = talib.MACD(grid['close'].values, fastperiod=fast, slowperiod=slow, signalperiod=sign)
        grid['dif'] = diff
        grid['dea'] = dea
        grid['macd'] = macd_hist * 2
        
        mask = (grid['macd'] < 0) & (grid['macd'].shift(1) >= 0)
        if mask.sum() < 2:
            return False
        
        key2, key1 = mask[mask].index[-2], mask[mask].index[-1]
        
        price_cond = grid.close[key2] < grid.close[key1]
        dif_cond = grid.dif[key2] > grid.dif[key1] > 0
        macd_cond = grid.macd.iloc[-2] > 0 > grid.macd.iloc[-1]
        
        if len(grid['dif']) > 20:
            recent_avg = grid['dif'].iloc[-10:].mean()
            prev_avg = grid['dif'].iloc[-20:-10].mean()
            trend_cond = recent_avg < prev_avg
        else:
            trend_cond = False
            
        return price_cond and dif_cond and macd_cond and trend_cond
        
    except Exception as e:
        log.error(f"{stock} 顶背离检测错误: {e}")
        return False

# ====================== 定时任务函数 ======================
def prepare_stock_pool(context):
    global g
    g['hold_list'] = [pos.security for pos in context.portfolio.positions.values()]
    
    if g['hold_list']:
        df = get_price(g['hold_list'], end_date=context.previous_date, frequency='daily',
                       fields=['close', 'high_limit'], count=1, panel=False)
        g['yesterday_HL_list'] = df[df['close'] == df['high_limit']]['code'].tolist()
    else:
        g['yesterday_HL_list'] = []

def before_market_open(context):
    global g
    if g.get('before_market_open_executed', False):
        return
    g['before_market_open_executed'] = True
    
    current_date = context.current_dt.date()
    cache_key = f"top_sectors_{current_date}"
    if 'cache' in g and cache_key in g['cache']:
        g['top_sectors'] = g['cache'][cache_key][1]
        log.info(f"使用缓存的行业数据: {g['top_sectors']}")
        return
        
    try:
        sw_level2 = get_industries(name='sw_l2', date=current_date)
        if isinstance(sw_level2, pd.DataFrame):
            sw_code_to_name = pd.Series(sw_level2['name'].values, index=sw_level2.index).to_dict()
        else:
            g['top_sectors'] = []
            return
            
        index_stocks = get_index_stocks('399101.XSHE')
        if not index_stocks:
            g['top_sectors'] = []
            return
            
        previous_trade_day = get_trade_days(end_date=current_date, count=2)[0]
        ind_results = get_industry(index_stocks, date=previous_trade_day)
        
        stock_sector_map = {}
        for stock in index_stocks:
            if stock in ind_results:
                info = ind_results[stock].get('sw_l2', {})
                code = info.get('industry_code')
                name = info.get('industry_name')
                if code and code in sw_code_to_name:
                    stock_sector_map[stock] = sw_code_to_name[code]
                elif name and name in sw_code_to_name.values():
                    stock_sector_map[stock] = name
        
        if not stock_sector_map:
            g['top_sectors'] = []
            return

        all_stocks = list(stock_sector_map.keys())
        prev_trade_days = get_trade_days(end_date=current_date, count=2)
        if len(prev_trade_days) < 2:
            g['top_sectors'] = []
            return
        end_date = prev_trade_days[-2]
        
        batch_size = 500
        money_flow_batches = []
        for i in range(0, len(all_stocks), batch_size):
            batch_stocks = all_stocks[i:i+batch_size]
            batch_df = get_money_flow(
                security_list=batch_stocks,
                end_date=end_date,
                count=1,
                fields=['sec_code', 'net_amount_main']
            )
            if isinstance(batch_df, pd.DataFrame) and not batch_df.empty:
                money_flow_batches.append(batch_df)
        
        if money_flow_batches:
            money_flow_df = pd.concat(money_flow_batches, ignore_index=True)
            sector_mapping_df = pd.DataFrame(list(stock_sector_map.items()), columns=['sec_code', 'sector_name'])
            merged_df = pd.merge(money_flow_df, sector_mapping_df, on='sec_code', how='inner')
            sector_fund_flow = merged_df.groupby('sector_name')['net_amount_main'].sum().sort_values(ascending=False)
            g['top_sectors'] = sector_fund_flow.index[:10].tolist()
            if 'cache' in g:
                g['cache'][cache_key] = (current_date, g['top_sectors'])
            log.info(f"资金流入前10行业: {g['top_sectors']}")
        else:
            g['top_sectors'] = []
            
    except Exception as e:
        log.error(f"获取行业资金流出错: {str(e)}")
        g['top_sectors'] = []

def reset_before_market_status(context):
    global g
    g['before_market_open_executed'] = False
    clean_expired_cache(context)

def check_market_divergence(context):
    global g
    g['dbl'] = g.get('dbl', [])
    if detect_divergence(MARKET_INDEX, context):
        g['dbl'].append(True)
        log.warning("⚠️ 检测到大盘顶背离信号")
        current_data = get_current_data()
        for stock in list(g.get('hold_list', [])):
            if current_data[stock].last_price < current_data[stock].high_limit:
                close_position(context.portfolio.positions[stock])
    else:
        g['dbl'].append(False)

def sell_stocks(context):
    global g
    # 个股止损
    for stock in list(context.portfolio.positions.keys()):
        pos = context.portfolio.positions[stock]
        if pos.price < pos.avg_cost * g['stoploss_limit']:
            order_target_value(stock, 0)
            log.info(f"止损卖出: {stock}")

    # 市场级风控：仅减仓50%
    market_df = get_price('399101.XSHE', end_date=context.previous_date, 
                          frequency='daily', fields=['close', 'open'], count=1)
    if not market_df.empty:
        down_ratio = market_df['close'].iloc[0] / market_df['open'].iloc[0]
        if down_ratio <= g['stoploss_market_threshold']:
            log.info("市场大跌，执行减仓")
            for stock in list(context.portfolio.positions.keys()):
                pos = context.portfolio.positions[stock]
                order_target_value(stock, pos.value * 0.5)

def trade_afternoon(context):
    global g
    check_limit_up(context)
    if g.get('HV_control', False):
        check_high_volume(context)
    huanshou(context)
    check_remain_amount(context)

def check_limit_up(context):
    global g
    now_time = context.current_dt
    if g.get('yesterday_HL_list'):
        for stock in g['yesterday_HL_list']:
            if context.portfolio.positions[stock].closeable_amount > 0:
                current_data = get_price(stock, end_date=now_time, frequency='1m', fields=['close', 'high_limit'],
                                         skip_paused=False, fq='pre', count=1, panel=False, fill_paused=True)
                if not current_data.empty and current_data.iloc[0, 0] < current_data.iloc[0, 1]:
                    close_position(context.portfolio.positions[stock])

def check_high_volume(context):
    global g
    current_data = get_current_data()
    for stock in context.portfolio.positions:
        if current_data[stock].paused:
            continue
        if current_data[stock].last_price == current_data[stock].high_limit:
            continue
        if context.portfolio.positions[stock].closeable_amount == 0:
            continue
        
        df_volume = get_bars(stock, count=g['HV_duration'], unit='1d', fields=['volume'], include_now=True, df=True)
        if not df_volume.empty:
            result = df_volume['volume'].values[-1] > g['HV_ratio'] * df_volume['volume'].values.max()
            if result:
                close_position(context.portfolio.positions[stock])

def huanshou(context):
    global g
    current_data = get_current_data()
    expand = 0.1
    for stock in context.portfolio.positions:
        if current_data[stock].paused:
            continue
        if current_data[stock].last_price >= current_data[stock].high_limit * 0.97:
            continue
        if context.portfolio.positions[stock].closeable_amount == 0:
            continue
        rt = huanshoulv(context, stock, False)
        avg = huanshoulv(context, stock, True)
        if avg == 0:
            continue
        r = rt / avg
        if avg < 0.003:
            pass
        elif rt > expand and r > 2:
            close_position(context.portfolio.positions[stock])

def check_remain_amount(context):
    global g
    g['hold_list'] = [pos.security for pos in context.portfolio.positions.values()]
    if len(g['hold_list']) < g['stock_num']:
        target_list = multi_strategy_get_stock_list(context)
        target_list = filter_not_buy_again(target_list, g.get('not_buy_again', []))
        target_list = target_list[:min(g['stock_num'], len(target_list))]
        buy_security(context, target_list)

def close_account(context):
    pass

def multi_strategy_adjustment(context):
    global g
    if any(g.get('dbl', [])[-5:]):
        log.info("近5日大盘顶背离，暂停调仓")
        return
        
    g['target_list'] = multi_strategy_get_stock_list(context)
    target_set = set(g['target_list'][:g['stock_num'] * 2])
    
    for stock in g.get('hold_list', []):
        if stock not in target_set and stock not in g.get('yesterday_HL_list', []):
            close_position(context.portfolio.positions[stock])
    
    buy_security(context, g['target_list'])

# ====================== 初始化函数 ======================
def initialize(context):
    # 开启防未来函数
    set_option('avoid_future_data', True)
    set_benchmark(MARKET_INDEX)
    set_option('use_real_price', True)
    set_slippage(FixedSlippage(3 / 10000))
    set_order_cost(OrderCost(open_tax=0, close_tax=0.0005, open_commission=1 / 10000, close_commission=1 / 10000,
                             close_today_commission=0, min_commission=0), type='stock')
    
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'info')
    
    # 【关键修复】初始化全局字典 g
    global g
    g.clear()  # 防止多次运行残留
    g['enable_industry'] = True      
    g['enable_eps'] = True           
    g['enable_moneyflow'] = True     
    g['enable_limitgene'] = True     
    
    g['stock_num_per_strategy'] = 6
    g['stock_num'] = 3    
    
    g['limit_days_window'] = 3 * 250 
    g['init_stock_count'] = 1000 
    
    g['top_sectors'] = []
    g['target_list'] = []
    g['hold_list'] = []
    g['yesterday_HL_list'] = []
    g['not_buy_again'] = []
    g['dbl'] = []
    
    # 风控参数
    g['stoploss_limit'] = 0.91    
    g['stoploss_market_threshold'] = 0.95
    g['HV_control'] = True
    g['HV_duration'] = 120  
    g['HV_ratio'] = 0.9  
    
    # 缓存
    g['cache'] = {}
    g['cache_timeout'] = 3
    g['before_market_open_executed'] = False
    
    # 定时任务
    
    run_daily(reset_before_market_status, time='09:00')  
    run_daily(before_market_open, time='09:01')   
    run_daily(prepare_stock_pool, '09:05')
    run_daily(check_market_divergence, '09:30')  
    run_daily(sell_stocks, time='11:25')  
    run_daily(trade_afternoon, time='10:30')  
    run_daily(trade_afternoon, time='14:30')  
    run_daily(close_account, '14:55')
    run_weekly(multi_strategy_adjustment, 1, '10:15')