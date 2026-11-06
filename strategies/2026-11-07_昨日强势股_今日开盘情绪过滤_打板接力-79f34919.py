# Clone from JoinQuant
# postId: 79f349195511521982b6f9b1a11c2425
# backtestId: a23f91e2900dd00188c0dd8d62005103
# title: 昨日强势股 + 今日开盘情绪过滤 + 打板接力



# ==================== 导入模块 ====================
from jqdata import *
import datetime
import pandas as pd
import time
import numpy as np

# ==================== 【V2性能优化】批量行情与缓存辅助 ====================
_TRADE_DAYS_CACHE = {}

def get_trade_days_cached(end_date, count):
    """get_trade_days 的轻量缓存（键含日期，跨日安全），减少热路径中的重复调用"""
    key = (str(end_date), count)
    if key not in _TRADE_DAYS_CACHE:
        _TRADE_DAYS_CACHE[key] = get_trade_days(end_date=end_date, count=count)
    return _TRADE_DAYS_CACHE[key]

def batch_limit_up_strong_flags(stock_list, date, batch_size=800):
    """
    【V2优化】批量计算"昨日涨停 / 昨日强势"标记，替代逐股 is_limit_up_simple + is_strong_stock。
    判定逻辑与原单股函数完全一致：
      涨停: yc >= high_limit*0.995 且 (yc-pc)/pc*100 > limit_up_threshold
      强势: strong_stock_min <= (yc-pc)/pc*100 < strong_stock_max
    返回 {'limit_up': set, 'strong': set}
    """
    result = {'limit_up': set(), 'strong': set()}
    for i in range(0, len(stock_list), batch_size):
        batch = stock_list[i:i+batch_size]
        if not batch:
            continue
        try:
            df = get_price(batch, end_date=date, count=2, fields=['close', 'high_limit'],
                           frequency='daily', fq='pre', panel=False, skip_paused=False, fill_paused=False)
            if df is None or df.empty or 'code' not in df.columns:
                continue
            for code, sub in df.sort_values(['code', 'time']).groupby('code', sort=False):
                if len(sub) < 2:
                    continue
                yc = sub['close'].iloc[-1]
                yl = sub['high_limit'].iloc[-1]
                pc = sub['close'].iloc[-2]
                try:
                    if yc is None or yl is None or pc is None:
                        continue
                    if pd.isna(yc) or pd.isna(yl) or pd.isna(pc) or pc <= 0:
                        continue
                    change = (yc - pc) / pc * 100
                    if yc >= yl * 0.995 and change > g.limit_up_threshold:
                        result['limit_up'].add(code)
                    if g.strong_stock_min <= change < g.strong_stock_max:
                        result['strong'].add(code)
                except:
                    continue
        except:
            continue
    return result

def batch_st_set(stock_list, date):
    """【V2优化】批量获取历史ST标记（point-in-time，顺带消除名称检查的轻微前视），失败时降级为逐股名称判断"""
    try:
        df = get_extras('is_st', stock_list, start_date=date, end_date=date, df=True)
        df_t = df.T
        df_t.columns = ['is_st']
        return set(df_t[df_t['is_st'] == True].index)
    except:
        return set(s for s in stock_list if is_st_stock(s))

# ==================== 策略参数配置 ====================
STRATEGY_PARAMS = {
    # ---------- 空仓机制开关（四维度独立） ----------
    'enable_premarket_sentiment_check': True,   # 盘前情绪检查开关（基于昨日数据）
    'enable_realtime_sentiment_check': False,   # 开盘后实时情绪检查开关（涨跌停/2连板）
    'enable_weighted_avg_gain_check': True,     # 加权平均涨幅检查开关（<阈值则空仓）
    'enable_candidate_count_check': True,       # 【新增】候选股数量过滤开关（盘前/竞价后数量阈值）

    # ---------- 盘前检查参数（基于昨日数据） ----------
    'premarket_limit_up_threshold': 60,      # 昨日涨停数量低于此值则盘前条件不满足，65改60
    'premarket_limit_down_threshold': 45,    # 昨日跌停数量高于此值则盘前条件不满足，40改45
    'premarket_2board_threshold': 5,         # 昨日2连板数量低于此值则盘前条件不满足

    # ---------- 实时检查参数（基于当日开盘后数据） ----------
    'realtime_limit_up_threshold': 35,       # 当日涨停数量低于此值空仓
    'realtime_limit_down_threshold': 40,     # 当日跌停数量高于此值空仓
    'realtime_2board_threshold': 3,          # 当日2连板数量低于此值空仓

    # ---------- 【新增】候选股数量过滤参数 ----------
    'premarket_candidate_threshold': 70,    # 盘前核心选股后候选股数量低于此值则空仓，120改70
    'auction_candidate_threshold': 38,       # 竞价过滤后候选股数量低于此值则空仓，65改38

    # ---------- 【可调】加权平均涨幅阈值 ----------
    'weighted_avg_gain_threshold': -2.0,     # 加权平均涨幅低于此值则空仓（ -0.5 改-2）

    # ---------- 持仓管理 ----------
    'max_stock_num': 3,
    'max_buy_per_day': 3,
    'dynamic_asset_tiers': [
        (0, 100000, 2, 2),
        (100000, 300000, 3, 3),
        (300000, 1000000, 4, 4),
        (1000000, 5000000, 5, 5),
        (5000000, float('inf'), 8, 8)
    ],
    
    # ---------- 止损止盈 ----------
    'stop_loss_ratio': -4.0,
    'stop_profit_ratio': 19.0,
    'max_hold_days': 3,
    'break_drop_ratio': 1.5,
    
    # ---------- 买入条件 ----------
    'min_open_ratio': 0,
    'max_open_ratio': 8.0,
    'min_turnover_rate': 2,
    'min_volume_ratio': 1.2,
    'min_volume_growth': 1.0,
    'ma_period': 5,
    'premium_bull': 1.022,
    'premium_bear': 1.018,
    'premium_normal': 1.019,
    'auction_drop_threshold': 0.3,
    'open_drop_threshold': -0.5,
    
    # ---------- 选股过滤 ----------
    'filter_continuous_gain': {
        'main': {'days': 5, 'max_gain': 60.0},
        'gem': {'days': 3, 'max_gain': 72.0},
        'star': {'days': 3, 'max_gain': 72.0},
    },
    'filter_after_1430_gain': {
        'main': 5.0,
        'gem': 8.0,
        'star': 8.0,
    },
    'filter_amplitude': {
        'main': 16.0,
        'gem': 20.0,
        'star': 20.0,
    },
    'filter_turnover': {
        'main': 24.0,
        'gem': 28.0,
        'star': 28.0,
    },
    'limit_up_threshold': 8.5,
    'strong_stock_min': 6.0,
    'strong_stock_max': 8.5,
    'loose_limit_up_threshold': 8.0,
    'ultra_loose_threshold': 5.0,
    'filter_double_in_month': 95,
    'filter_shrink_rise': True,
    'filter_limit_down_3d': True,
    'filter_st_stock': True,
    'filter_beijing': True,
    'filter_kcb': True,
    'filter_risk_stock': True,
    'risk_open_threshold_main': 5.0,
    'risk_open_threshold_gem_star': 6.0,
    
    # ---------- 市场环境动态参数 ----------
    'market_env_adjust': {
        'bull': {
            'min_open_ratio_offset': 1,
            'max_open_ratio_offset': -1,
            'min_turnover_rate_offset': 1,
            'stop_profit_ratio_offset': 2,
        },
        'bear': {
            'min_open_ratio_offset': -0.5,
            'max_open_ratio_offset': 1,
            'min_turnover_rate_offset': -0.5,
            'stop_loss_ratio_offset': 1,
        }
    },
    'hs300_bull_threshold': 1,
    'hs300_bear_threshold': -1,
    'limit_up_count_bull': 80,
    'limit_up_count_bear': 30,
   
    # ---------- 时间参数 ----------
    'time_auction_filter': '09:26:00',
    'time_set_only_buy_false': '09:30:00',
    #'time_sell_only': '09:30:01',
    #'time_set_only_buy_true': '09:30:06',
    
    'time_sell_only': '09:31:01',
    'time_set_only_buy_true': '09:31:02',
    
    'time_buy_start': '09:32:35',
    'time_buy_fourth': '10:00:00',
    'time_buy_fifth': '10:29:00',
    'manual_signal_time': '09:30:16',
    'manual_buy_time': '09:33:16',
    'time_sell_check_interval': 2,
    'time_sell_check_exclude': [(14,56),(14,57),(14,58),(14,59)],
}

# ==================== 辅助函数（与参考策略一致，完整保留） ====================
def get_stock_industry_and_concept(stock_code, query_date):
    cache_key = f"{stock_code}_{query_date}"
    CACHE_TTL = 21600
    if hasattr(g, 'concept_cache') and cache_key in g.concept_cache:
        cached_data, cached_ts = g.concept_cache[cache_key]
        if time.time() - cached_ts < CACHE_TTL:
            return cached_data
    result = {'industry_name': '未知行业', 'concepts': [], 'display_str': '', 'industry_index_code': None}
    try:
        industry_df = get_industry(stock_code, date=query_date)
        if stock_code in industry_df:
            industry_info = industry_df[stock_code]
            sw_l1 = industry_info.get('sw_l1')
            if sw_l1:
                if isinstance(sw_l1, list) and len(sw_l1) > 0:
                    item = sw_l1[0]
                    if isinstance(item, dict):
                        name = item.get('industry_name')
                        code = item.get('industry_code')
                        if name:
                            result['industry_name'] = name
                        if code:
                            result['industry_index_code'] = f"{code}.SI"
                elif isinstance(sw_l1, dict):
                    name = sw_l1.get('industry_name')
                    code = sw_l1.get('industry_code')
                    if name:
                        result['industry_name'] = name
                    if code:
                        result['industry_index_code'] = f"{code}.SI"
            else:
                for level in ['sw_l3', 'sw_l2', 'jq_l2', 'jq_l1']:
                    val = industry_info.get(level)
                    if val:
                        if isinstance(val, str):
                            result['industry_name'] = val
                            break
                        elif isinstance(val, list) and len(val) > 0:
                            item = val[0]
                            if isinstance(item, dict):
                                name = item.get('industry_name')
                                if name:
                                    result['industry_name'] = name
                                    break
                        elif isinstance(val, dict):
                            name = val.get('industry_name')
                            if name:
                                result['industry_name'] = name
                                break
        concept_df = get_concept(stock_code, date=query_date)
        if stock_code in concept_df:
            concept_data = concept_df[stock_code].get('jq_concept', [])
            if concept_data:
                concepts = []
                for item in concept_data:
                    if isinstance(item, dict):
                        concept_name = item.get('concept_name')
                        if concept_name:
                            concepts.append(concept_name)
                    elif isinstance(item, str):
                        concepts.append(item)
                result['concepts'] = concepts[:5]
        concept_str = '、'.join(result['concepts']) if result['concepts'] else '无概念'
        result['display_str'] = f'[{result["industry_name"]}] [{concept_str}]'
    except:
        result['display_str'] = '[行业获取失败] [概念获取失败]'
    if not hasattr(g, 'concept_cache'):
        g.concept_cache = {}
    g.concept_cache[cache_key] = (result, time.time())
    return result

def get_dynamic_max_hold(total_asset):
    for low, high, max_num, buy_per_day in g.dynamic_asset_tiers:
        if low <= total_asset < high:
            return max_num, buy_per_day
    return g.max_stock_num, g.max_buy_per_day

def get_stock_board(stock):
    try:
        code = stock.split('.')[0]
        suffix = stock.split('.')[1] if '.' in stock else ''
        if (code.startswith('60') and suffix == 'XSHG') or \
           ((code.startswith('000') or code.startswith('001')) and suffix == 'XSHE'):
            return 'main'
        elif code.startswith(('300', '301', '302')) and suffix == 'XSHE':
            return 'gem'
        elif code.startswith('688') and suffix == 'XSHG':
            return 'star'
        else:
            return 'unknown'
    except:
        return 'unknown'

def calculate_continuous_gain(stock, end_date, days):
    try:
        hist = get_price(stock, end_date=end_date, count=days+1, fields=['close'], fq='pre', skip_paused=True)
        if len(hist) < days + 1:
            return -999
        start_price = hist['close'].iloc[0]
        end_price = hist['close'].iloc[-1]
        total_gain = (end_price - start_price) / start_price * 100
        return round(total_gain, 2)
    except:
        return -999

def filter_by_continuous_gain(stock, end_date):
    try:
        stock_name = get_security_info(stock).display_name
    except:
        stock_name = "未知名称"
    board = get_stock_board(stock)
    cfg = g.filter_continuous_gain.get(board)
    if not cfg:
        return True, "未知板块，跳过涨幅过滤", stock_name
    check_days = cfg['days']
    max_gain = cfg['max_gain']
    total_gain = calculate_continuous_gain(stock, end_date, check_days)
    if total_gain == -999:
        return True, f"无法计算{check_days}天涨幅，跳过过滤", stock_name
    elif total_gain > max_gain:
        return False, f"{board}连续{check_days}天涨幅{total_gain}% > {max_gain}%", stock_name
    else:
        return True, f"{board}连续{check_days}天涨幅{total_gain}% ≤ {max_gain}%", stock_name

def filter_after_1430_gain(stock, date):
    try:
        stock_name = get_security_info(stock).display_name
        board = get_stock_board(stock)
        gain_thresholds = g.filter_after_1430_gain
        if board not in gain_thresholds:
            return True, "未知板块，跳过尾盘涨幅过滤", stock_name
        threshold = gain_thresholds[board]
        date_obj = pd.Timestamp(date)
        time_1430 = pd.Timestamp.combine(date_obj.date(), pd.Timestamp('14:30:00').time())
        end_time = pd.Timestamp.combine(date_obj.date(), pd.Timestamp('15:00:00').time())
        min1_data = get_price(stock, start_date=time_1430, end_date=end_time, frequency='1m', fields=['close'], fq='pre', skip_paused=True)
        if min1_data.empty or len(min1_data) < 2:
            min5_data = get_price(stock, start_date=time_1430, end_date=end_time, frequency='5m', fields=['close'], fq='pre', skip_paused=True)
            if min5_data.empty or len(min5_data) < 2:
                daily_data = get_price(stock, end_date=date, count=1, fields=['open','close'], fq='pre')
                if daily_data.empty:
                    return True, "无尾盘数据，默认通过", stock_name
                price_1430 = daily_data['open'].iloc[0]
                price_close = daily_data['close'].iloc[0]
            else:
                price_1430 = min5_data['close'].iloc[0]
                price_close = min5_data['close'].iloc[-1]
        else:
            price_1430 = min1_data['close'].iloc[0]
            price_close = min1_data['close'].iloc[-1]
        gain = (price_close - price_1430) / price_1430 * 100
        gain = round(gain, 2)
        if gain > threshold:
            log.error(f"❌ 尾盘过滤淘汰: {stock} {stock_name} | {board} | 14:30后涨幅{gain}% > {threshold}%")
            return False, f"{board}14:30后涨幅{gain}% > {threshold}%", stock_name
        else:
            return True, f"{board}14:30后涨幅{gain}% ≤ {threshold}%", stock_name
    except:
        return True, f"过滤异常，默认通过", "未知名称"

def filter_by_amplitude(stock, date):
    try:
        stock_name = get_security_info(stock).display_name
        board = get_stock_board(stock)
        amp_thresholds = g.filter_amplitude
        if board not in amp_thresholds:
            return True, "未知板块，跳过振幅过滤", stock_name
        threshold = amp_thresholds[board]
        hist = attribute_history(stock, 1, '1d', fields=['high', 'low', 'close'], skip_paused=True, df=True)
        if hist.empty:
            return True, "无振幅数据", stock_name
        high = hist['high'].iloc[-1]
        low = hist['low'].iloc[-1]
        close = hist['close'].iloc[-1]
        if close == 0:
            return True, "昨日收盘价为0", stock_name
        amplitude = (high - low) / close * 100
        amplitude = round(amplitude, 2)
        if amplitude >= threshold:
            return False, f"{board}昨日振幅{amplitude}% ≥ {threshold}%", stock_name
        else:
            return True, f"{board}昨日振幅{amplitude}% < {threshold}%", stock_name
    except:
        return True, f"振幅异常", stock_name

def filter_by_turnover(stock, date):
    try:
        stock_name = get_security_info(stock).display_name
        turnover = None
        try:
            turnover_df = get_money_flow(stock, start_date=date, end_date=date)
            if not turnover_df.empty and 'turnover_rate' in turnover_df.columns:
                turnover = turnover_df['turnover_rate'].iloc[0]
        except:
            pass
        if turnover is None:
            try:
                vol_data = attribute_history(stock, 1, '1d', fields=['volume'], skip_paused=True, df=True)
                if vol_data.empty:
                    return False, "无成交量数据", stock_name
                volume = vol_data['volume'].iloc[-1]
                q = query(valuation.circulating_cap).filter(valuation.code == stock)
                df = get_fundamentals(q, date=date)
                if df.empty:
                    return False, "无流通股本", stock_name
                float_share = df['circulating_cap'].iloc[0] * 10000
                if float_share <= 0:
                    return False, "流通股本异常", stock_name
                turnover = volume / float_share * 100
            except:
                return False, "计算异常", stock_name
        if turnover is None:
            return False, "无法获取换手率", stock_name
        turnover = round(float(turnover), 2)
        if turnover < 3.0:
            return False, f"换手率{turnover}% < 3%（过于冷清）", stock_name
        if turnover > 45.0:
            return False, f"换手率{turnover}% > 45%（极度过热）", stock_name
        return True, f"换手率{turnover}% 符合区间", stock_name
    except:
        log.error(f"换手率过滤异常 {stock}")
        return False, "过滤异常", stock_name

def is_double_in_month(stock, context):
    try:
        trade_days = get_trade_days_cached(context.current_dt.date(), 2)
        if len(trade_days) < 2:
            return False
        yesterday = trade_days[0]
        hist = attribute_history(stock, 20, '1d', fields=['close'], skip_paused=True, df=True)
        if len(hist) < 20:
            return False
        old_price = hist['close'].iloc[0]
        today_price = hist['close'].iloc[-1]
        if old_price <= 0:
            return False
        gain = (today_price - old_price) / old_price * 100
        return gain >= g.filter_double_in_month
    except:
        return False

def has_limit_down_in_last_3days(stock, date):
    if not g.filter_limit_down_3d:
        return True, "未启用过滤", ""
    try:
        stock_name = get_security_info(stock).display_name
        hist = attribute_history(stock, 3, '1d', fields=['close', 'low_limit'], skip_paused=True, df=True)
        if len(hist) < 3:
            return True, "无足够数据", stock_name
        for i in range(len(hist)):
            close = hist['close'].iloc[i]
            low_limit = hist['low_limit'].iloc[i]
            if close <= low_limit * 1.005:
                return False, f"近3日有跌停", stock_name
        return True, "近3日无跌停", stock_name
    except:
        return True, f"跌停异常", stock_name

def is_continuous_shrink_rise(stock, date):
    if not g.filter_shrink_rise:
        return True, "未启用过滤", ""
    try:
        stock_name = get_security_info(stock).display_name
        hist = attribute_history(stock, 3, '1d', fields=['close', 'volume'], skip_paused=True, df=True)
        if len(hist) < 3:
            return True, "无足够数据", stock_name
        for i in range(1, 3):
            if hist['close'].iloc[i] <= hist['close'].iloc[i-1]:
                return True, "非连续上涨", stock_name
        for i in range(1, 3):
            if hist['volume'].iloc[i] >= hist['volume'].iloc[i-1]:
                return True, "非连续缩量", stock_name
        return False, "连续3日缩量上涨", stock_name
    except:
        return True, f"缩量异常", stock_name

def is_risk_stock(context, stock):
    if not g.filter_risk_stock:
        return False
    try:
        stock_name = get_security_info(stock).display_name
        trade_days = get_trade_days_cached(context.current_dt.date(), 2)
        if len(trade_days) < 2:
            return False
        yesterday = trade_days[0]
        df = attribute_history(stock, 3, '1d', fields=['close', 'volume', 'high_limit'], skip_paused=True, df=True)
        if df is None or len(df) < 3:
            return False
        close_yest = df['close'].iloc[-1]
        vol_yest = df['volume'].iloc[-1]
        vol_beyest = df['volume'].iloc[-2]
        high_limit = df['high_limit'].iloc[-1]
        is_limit_up = (close_yest >= high_limit - 0.01)
        is_vol_big = (vol_yest >= vol_beyest * 1.8)
        df20 = attribute_history(stock, 20, '1d', fields=['close'], skip_paused=True, df=True)
        if df20 is not None and len(df20) >= 20:
            rise_rate = (df20['close'].iloc[-1] / df20['close'].iloc[0] - 1)
        else:
            rise_rate = 0
        is_high = (rise_rate > 0.30)
        is_danger_yest = is_limit_up and is_vol_big and is_high
        if not is_danger_yest:
            return False
        current_data = get_current_data()[stock]
        open_price = current_data.day_open
        pre_close = close_yest
        open_rate = (open_price / pre_close - 1) * 100
        board = get_stock_board(stock)
        if board == 'main':
            threshold = g.risk_open_threshold_main
        else:
            threshold = g.risk_open_threshold_gem_star
        if open_rate >= threshold:
            log.info(f"⚠️ 风险股票 {stock} {stock_name}：昨日高位放量涨停+今日高开{open_rate:.1f}%")
            return True
        return False
    except:
        return False

def is_limit_up_simple(stock, date):
    try:
        hist = get_price(stock, end_date=date, count=2, fields=['close','high_limit'], fq='pre')
        if len(hist) < 2:
            return False
        yc = hist['close'].iloc[-1]
        yl = hist['high_limit'].iloc[-1]
        pc = hist['close'].iloc[-2]
        change = (yc - pc)/pc*100
        if yc >= yl * 0.995 and change > g.limit_up_threshold:
            return True
        return False
    except:
        return False

def is_strong_stock(stock, date):
    try:
        hist = get_price(stock, end_date=date, count=2, fields=['close'], fq='pre')
        if len(hist) < 2:
            return False
        change = (hist['close'].iloc[-1] - hist['close'].iloc[-2])/hist['close'].iloc[-2] * 100
        return g.strong_stock_min <= change < g.strong_stock_max
    except:
        return False

def find_limit_up_loose(stocks, date):
    limit_stocks = []
    for stock in stocks:
        try:
            if g.filter_st_stock and is_st_stock(stock):
                continue
            if g.filter_beijing and '.BJ' in stock:
                continue
            if g.filter_kcb and get_stock_board(stock) == 'star':
                continue
            hist = get_price(stock, end_date=date, count=2, fields=['close','high'], fq='pre')
            if len(hist) < 2:
                continue
            yc = hist['close'].iloc[-1]
            yh = hist['high'].iloc[-1]
            pc = hist['close'].iloc[-2]
            change = (yc - pc)/pc*100
            if change > g.loose_limit_up_threshold or (abs(yh - yc)/yc < 0.01 and change > g.strong_stock_min):
                pass_filter, filter_msg, stock_name = filter_by_continuous_gain(stock, date)
                if not pass_filter:
                    continue
                pass_1430_filter, filter_1430_msg, stock_name = filter_after_1430_gain(stock, date)
                if not pass_1430_filter:
                    continue
                pass_amp_filter, amp_msg, stock_name = filter_by_amplitude(stock, date)
                if not pass_amp_filter:
                    continue
                pass_turnover_filter, turnover_msg, stock_name = filter_by_turnover(stock, date)
                if not pass_turnover_filter:
                    continue
                pass_limitdown_filter, limitdown_msg, stock_name = has_limit_down_in_last_3days(stock, date)
                if not pass_limitdown_filter:
                    continue
                pass_shrink_filter, shrink_msg, stock_name = is_continuous_shrink_rise(stock, date)
                if not pass_shrink_filter:
                    continue
                limit_stocks.append(stock)
        except:
            continue
    return limit_stocks

def find_limit_up_ultra_loose(stocks, date):
    limit_stocks = []
    for stock in stocks:
        try:
            if g.filter_st_stock and is_st_stock(stock):
                continue
            if g.filter_beijing and '.BJ' in stock:
                continue
            if g.filter_kcb and get_stock_board(stock) == 'star':
                continue
            hist = get_price(stock, end_date=date, count=2, fields=['close'], fq='pre')
            if len(hist) < 2:
                continue
            change = (hist['close'].iloc[-1] - hist['close'].iloc[-2])/hist['close'].iloc[-2] * 100
            if change > g.ultra_loose_threshold:
                pass_filter, filter_msg, stock_name = filter_by_continuous_gain(stock, date)
                if not pass_filter:
                    continue
                pass_1430_filter, filter_1430_msg, stock_name = filter_after_1430_gain(stock, date)
                if not pass_1430_filter:
                    continue
                pass_amp_filter, amp_msg, stock_name = filter_by_amplitude(stock, date)
                if not pass_amp_filter:
                    continue
                pass_turnover_filter, turnover_msg, stock_name = filter_by_turnover(stock, date)
                if not pass_turnover_filter:
                    continue
                pass_limitdown_filter, limitdown_msg, stock_name = has_limit_down_in_last_3days(stock, date)
                if not pass_limitdown_filter:
                    continue
                pass_shrink_filter, shrink_msg, stock_name = is_continuous_shrink_rise(stock, date)
                if not pass_shrink_filter:
                    continue
                limit_stocks.append(stock)
        except:
            continue
    return limit_stocks

def is_st_stock(stock):
    # 【V1说明】display_name 为最新证券名称，回测历史时点存在轻微前视（当时未ST、后来戴帽会被提前过滤）。
    # 如需严格 point-in-time 可改用 get_extras('is_st', ..., end_date=昨日)，但逐股调用在全市场循环中性能开销过大，
    # 权衡后保留现状；列表级过滤 get_stock_ref 中已有历史口径的 filter_st_stock_ref 兜底。
    try:
        name = get_security_info(stock).display_name
        return 'ST' in name or '*ST' in name or '退' in name
    except:
        return True

def is_limit_up_down(stock, context=None):
    try:
        # 【V1修复】显式传入 end_date，避免依赖 get_price 默认行为
        if context is not None:
            data = get_price(stock, end_date=context.current_dt, count=1, fields=['open','high_limit','low_limit'])
        else:
            data = get_price(stock, count=1, fields=['open','high_limit','low_limit'])
        if data.empty:
            return True
        op = data['open'][0]
        hl = data['high_limit'][0]
        ll = data['low_limit'][0]
        if abs(op - hl) < 0.001 or abs(op - ll) < 0.001:
            return True
        return False
    except:
        return True

def check_basic_quality(stock, context):
    try:
        if is_limit_up_down(stock, context):
            return False
        today_tick = get_price(stock, end_date=context.current_dt, count=1, fields=['open'], skip_paused=True)
        return not today_tick.empty
    except:
        return False

def calculate_turnover_rate(stock, date):
    try:
        vol_data = get_price(stock, end_date=date, count=1, fields=['volume'], fq='pre')
        if vol_data.empty:
            return 0.0
        volume = vol_data['volume'].iloc[0]
        stock_info = get_security_info(stock)
        float_share = stock_info.float_share if hasattr(stock_info, 'float_share') else 0
        if float_share == 0:
            return 0.0
        return (volume / (float_share * 10000)) * 100
    except:
        return 0.0

def check_turnover_volume(stock, context):
    try:
        trade_days = get_trade_days_cached(context.current_dt.date(), 3)
        if len(trade_days) < 3:
            return True, "无足够数据"
        yesterday = trade_days[0]
        day_before_yesterday = trade_days[1]
        turnover_df = get_money_flow(stock, start_date=yesterday, end_date=yesterday)
        if turnover_df.empty or 'turnover_rate' not in turnover_df.columns:
            turnover_rate = calculate_turnover_rate(stock, yesterday)
        else:
            turnover_rate = turnover_df['turnover_rate'].iloc[0]
        if 0 < turnover_rate < g.min_turnover_rate:
            return False, f"换手率{turnover_rate:.2f}% < {g.min_turnover_rate}%"
        vol_df = get_price(stock, start_date=day_before_yesterday, end_date=yesterday, fields=['volume'], fq='pre')
        if len(vol_df) < 2:
            return True, "无成交量数据"
        vol_growth = vol_df['volume'].iloc[-1] / vol_df['volume'].iloc[-2]
        if vol_growth < g.min_volume_growth:
            return False, f"成交量增长{vol_growth:.2f} < {g.min_volume_growth}"
        if context.current_dt.time() > datetime.time(9,30):
            try:
                today_vol = get_price(stock, end_date=context.current_dt, count=1, fields=['volume'], fq='pre')['volume'].iloc[0]
                avg_vol = get_price(stock, end_date=yesterday, count=5, fields=['volume'], fq='pre')['volume'].mean()
                if avg_vol > 0:
                    volume_ratio = today_vol / avg_vol
                    if 0 < volume_ratio < g.min_volume_ratio:
                        return False, f"量比{volume_ratio:.2f} < {g.min_volume_ratio}"
            except:
                pass
        return True, "量能达标"
    except:
        return True, "量能校验异常"

def get_current_change(stock, context):
    try:
        today_data = get_price(stock, end_date=context.current_dt, count=1, fields=['close'], fq='pre')
        trade_days = get_trade_days_cached(context.current_dt.date(), 2)
        if len(trade_days) < 2:
            return 0
        yesterday = trade_days[0]
        yesterday_data = get_price(stock, end_date=yesterday, count=1, fields=['close'], fq='pre')
        if today_data.empty or yesterday_data.empty:
            return 0
        current_price = today_data['close'].iloc[0]
        yesterday_close = yesterday_data['close'].iloc[0]
        return (current_price - yesterday_close) / yesterday_close * 100
    except:
        return 0

def is_real_time_drop(context, stock):
    try:
        stock_name = get_security_info(stock).display_name
        current_data = get_current_data()[stock]
        trade_days = get_trade_days_cached(context.current_dt.date(), 2)
        if len(trade_days) < 2:
            return False, "无昨日数据"
        yesterday_close = get_price(stock, end_date=trade_days[0], count=1, fields=['close'], fq='pre')['close'].iloc[0]
        open_price = current_data.day_open
        current_price = current_data.last_price
        if open_price <= 0 or current_price <= 0:
            return False, "价格异常"
        open_ratio = (open_price - yesterday_close) / yesterday_close * 100
        drop_ratio = (open_price - current_price) / open_price * 100
        if open_ratio > 0 and current_price < open_price and drop_ratio > g.auction_drop_threshold:
            log.debug(f"❌ 实时高开低走：{stock} {stock_name} 高开{open_ratio:.1f}%，开盘回落{drop_ratio:.1f}%")
            return True, f"回落{drop_ratio:.1f}%"
        return False, f"高开{open_ratio:.1f}%"
    except:
        return False, "检测异常"

def check_volume_drop(stock, context):
    try:
        trade_days = get_trade_days_cached(context.current_dt.date(), 2)
        if len(trade_days) < 2:
            return False, ""
        today_data = get_price(stock, end_date=context.current_dt, count=1, fields=['close','volume'], fq='pre')
        yesterday_data = get_price(stock, end_date=trade_days[0], count=1, fields=['volume'], fq='pre')
        if today_data.empty or yesterday_data.empty:
            return False, ""
        volume_ratio = today_data['volume'].iloc[0] / yesterday_data['volume'].iloc[0]
        today_change = get_current_change(stock, context)
        if volume_ratio > 1.5 and today_change < -2.0:
            return True, f"放量下跌（量比{volume_ratio:.2f}，跌幅{today_change:.2f}%）"
        return False, ""
    except:
        return False, ""

def get_industry_index_gain(stock, date, end_dt=None):
    try:
        info = get_stock_industry_and_concept(stock, date)
        index_code = info.get('industry_index_code')
        if not index_code:
            return None
        # 【V1修复】显式用 end_dt（context.current_dt）取实时指数行情：昨收+当日实时价，语义确定为"今日实时板块强度"
        hist = get_price(index_code, end_date=end_dt if end_dt is not None else date, count=2, fields=['close'], fq='pre', skip_paused=True)
        if len(hist) < 2:
            return None
        gain = (hist['close'].iloc[-1] - hist['close'].iloc[-2]) / hist['close'].iloc[-2] * 100
        return round(gain, 2)
    except:
        return None

# ==================== 参考策略统计函数（完整移植） ====================
def filter_paused_stock(initial_list, date):
    df = get_price(initial_list, end_date=date, frequency='daily',
                   fields=['paused'], count=1, panel=False, fill_paused=True)
    df = df[df['paused'] == 0]
    return list(df.code)

def filter_new_stock(initial_list, date, days=50):
    return [stock for stock in initial_list
            if date - get_security_info(stock).start_date > datetime.timedelta(days=days)]

def filter_st_stock_ref(initial_list, date):
    try:
        df = get_extras('is_st', initial_list, start_date=date, end_date=date, df=True)
        df = df.T
        df.columns = ['is_st']
        df = df[df['is_st'] == False]
        return list(df.index)
    except:
        return [s for s in initial_list if not is_st_stock(s)]

def filter_kcbj_stock(initial_list):
    return [stock for stock in initial_list
            if stock[0] != '4' and stock[0] != '8' and not stock.startswith('68')]

def get_stock_ref(today):
    in_list = get_all_securities(types=['stock'], date=today).index.tolist()
    in_list = filter_paused_stock(in_list, today)
    in_list = filter_st_stock_ref(in_list, today)
    in_list = filter_kcbj_stock(in_list)
    in_list = filter_new_stock(in_list, today)
    return in_list

def fl_list(in_list, today):
    price_df = get_price(in_list, end_date=today, frequency='daily',
                         fields=['high', 'high_limit', 'low_limit', 'close'],
                         skip_paused=False, fq='pre', count=20, panel=False, fill_paused=True)
    def get_label(row):
        if row['close'] >= row['high_limit']:
            return '今日涨停'
        elif row['close'] <= row['low_limit']:
            return '今日跌停'
        else:
            return '无'
    price_df['标识'] = price_df.apply(get_label, axis=1)
    return price_df[price_df['标识'] != '无']

def get_hl_stock(initial_list, date):
    df = get_price(initial_list, end_date=date, frequency='daily',
                   fields=['close', 'high_limit', 'low', 'low_limit'],
                   count=1, panel=False, fill_paused=False, skip_paused=False)
    df = df[df['close'] >= df['high_limit']].dropna(subset=['close', 'high_limit'])
    return list(df['code'])

def get_hl_count_df(hl_list, date, watch_days):
    if not hl_list:
        return pd.DataFrame(columns=['count', 'extreme_count'])
    df = get_price(hl_list, end_date=date, frequency='daily',
                   fields=['close', 'high_limit', 'low'],
                   count=watch_days, panel=False, fill_paused=False, skip_paused=False)
    df = df.set_index('code')
    hl_days = df[df['close'] >= df['high_limit']].groupby('code').size()
    extreme_hl_days = df[df['low'] >= df['high_limit']].groupby('code').size()
    hl_count = hl_days.reindex(hl_list, fill_value=0)
    extreme_count = extreme_hl_days.reindex(hl_list, fill_value=0)
    return pd.DataFrame({'count': hl_count, 'extreme_count': extreme_count})

def get_continue_count_df(hl_list, date, watch_days):
    if not hl_list:
        return pd.DataFrame(columns=['count', 'extreme_count'])
    df_list = []
    for d in range(2, watch_days + 1):
        tmp = get_hl_count_df(hl_list, date, d)
        tmp = tmp[tmp['count'] == d]
        if not tmp.empty:
            df_list.append(tmp)
    if not df_list:
        return pd.DataFrame(columns=['count', 'extreme_count'])
    ccd = pd.concat(df_list)
    ccd = ccd.groupby(ccd.index).agg({'count': 'max', 'extreme_count': 'max'})
    ccd = ccd.sort_values('count', ascending=False)
    return ccd

# ==================== 统计昨日数据（用于盘前检查和日志） ====================
def get_yesterday_market_stats(context, date):
    yesterday = date
    stock_list = get_stock_ref(yesterday)
    if not stock_list:
        return 0, 0, 0, []

    df = fl_list(stock_list, yesterday)
    if df.empty:
        return 0, 0, 0, []

    yest_df = df[df['time'] == pd.Timestamp(yesterday)]
    limit_up_cnt = len(yest_df[yest_df['标识'] == '今日涨停'])
    limit_down_cnt = len(yest_df[yest_df['标识'] == '今日跌停'])
    yest_up_codes = yest_df[yest_df['标识'] == '今日涨停']['code'].tolist()

    # 计算2连板（昨日涨停且前天涨停）
    trade_days = get_trade_days_cached(yesterday, 2)
    if len(trade_days) >= 2:
        day_before = trade_days[0]
        before_df = fl_list(stock_list, day_before)
        if not before_df.empty:
            before_up_codes = before_df[before_df['标识'] == '今日涨停']['code'].tolist()
            board2_codes = set(yest_up_codes).intersection(set(before_up_codes))
            board2_cnt = len(board2_codes)
        else:
            board2_cnt = 0
    else:
        board2_cnt = 0

    return int(limit_up_cnt), int(limit_down_cnt), int(board2_cnt), yest_up_codes

# ==================== 实时情绪计算（开盘后执行，仅统计涨跌停/2连板，不含加权平均） ====================
def calc_realtime_sentiment(context):
    """
    计算当日实时涨停、跌停、2连板数量，并判断是否满足实时开仓条件。
    注意：本函数不再包含加权平均涨幅计算，该部分已独立为 calc_weighted_avg_gain。
    """
    # 获取所有A股（应用策略过滤条件）
    all_stocks = get_all_securities(['stock'], date=context.current_dt.date()).index.tolist()
    # 过滤ST
    if g.filter_st_stock:
        all_stocks = [s for s in all_stocks if not is_st_stock(s)]
    # 过滤北交所
    if g.filter_beijing:
        all_stocks = [s for s in all_stocks if '.BJ' not in s]
    # 过滤科创板
    if g.filter_kcb:
        all_stocks = [s for s in all_stocks if get_stock_board(s) != 'star']

    if not all_stocks:
        log.warn("实时情绪计算：无有效股票")
        return False

    # 批量获取当前价格数据
    current_data = get_current_data()
    limit_up_cnt = 0
    limit_down_cnt = 0
    today_up_codes = []

    for stock in all_stocks:
        try:
            if stock not in current_data:
                continue
            data = current_data[stock]
            if data is None or data.last_price is None or data.high_limit is None or data.low_limit is None:
                continue
            # 涨停：当前价 >= 涨停价 * 0.995（考虑浮点误差）
            if data.last_price >= data.high_limit * 0.995:
                limit_up_cnt += 1
                today_up_codes.append(stock)
            # 跌停：当前价 <= 跌停价 * 1.005
            elif data.last_price <= data.low_limit * 1.005:
                limit_down_cnt += 1
        except:
            continue

    # 计算2连板：今日涨停且昨日涨停
    yesterday_up_codes = getattr(g, 'yesterday_full_limit_up_stocks', [])
    board2_codes = set(today_up_codes).intersection(set(yesterday_up_codes))
    board2_cnt = len(board2_codes)

    # 记录实时统计（供日志输出）
    g.realtime_limit_up_cnt = limit_up_cnt
    g.realtime_limit_down_cnt = limit_down_cnt
    g.realtime_board2_cnt = board2_cnt

    # 判断是否满足实时开仓条件
    realtime_ok = True
    reasons = []
    if limit_up_cnt < g.realtime_limit_up_threshold:
        realtime_ok = False
        reasons.append(f"涨停数 {limit_up_cnt} < {g.realtime_limit_up_threshold}")
    if limit_down_cnt > g.realtime_limit_down_threshold:
        realtime_ok = False
        reasons.append(f"跌停数 {limit_down_cnt} > {g.realtime_limit_down_threshold}")
    if board2_cnt < g.realtime_2board_threshold:
        realtime_ok = False
        reasons.append(f"2连板数 {board2_cnt} < {g.realtime_2board_threshold}")

    if not realtime_ok:
        log.warn(f"🚫 实时空仓条件触发：{'；'.join(reasons)}，实时维度禁止买入")
    else:
        log.info(f"✅ 实时情绪条件全部通过（涨停≥{g.realtime_limit_up_threshold}，跌停≤{g.realtime_limit_down_threshold}，2连板≥{g.realtime_2board_threshold}），实时维度允许买入")

    return realtime_ok


# ==================== 加权平均涨幅独立计算（新增，独立于实时检查） ====================
def calc_weighted_avg_gain(context):
    """
    独立计算昨日涨停股（成交额Top30）的今日加权平均涨幅。
    返回 (是否通过, 平均涨幅值)
    仅受 enable_weighted_avg_gain_check 控制，不受实时检查开关影响。
    """
    current_data = get_current_data()
    limit_up_list = getattr(g, 'yesterday_limit_up_stocks', [])
    amount_dict = getattr(g, 'yesterday_limit_up_amounts', {})

    if not limit_up_list:
        log.info("ℹ️ 昨日无涨停股（成交额Top30），加权平均涨幅跳过")
        return True, 0.0

    # 【V1修复】显式取昨日交易日，避免 end_date=当日日期 时取到当日未完成K线（close=实时价）导致涨幅恒≈0
    trade_days_tmp = get_trade_days_cached(context.current_dt.date(), 2)
    if len(trade_days_tmp) < 2:
        log.info("ℹ️ 无昨日交易日，加权平均涨幅跳过")
        return True, 0.0
    yesterday_for_wag = trade_days_tmp[0]

    total_weighted_gain = 0
    total_amount = 0
    count = 0

    for stock in limit_up_list:
        if stock not in current_data:
            continue
        try:
            price = current_data[stock].last_price
            # 【V1修复】昨日收盘价改用昨日交易日作为 end_date
            y_close = get_price(stock, end_date=yesterday_for_wag, count=1, fields=['close'], fq='pre')['close'].iloc[0]
            if y_close <= 0:
                continue
            gain = (price - y_close) / y_close * 100
            amount = amount_dict.get(stock, 1)
            total_weighted_gain += gain * amount
            total_amount += amount
            count += 1
        except:
            continue

    if count == 0 or total_amount == 0:
        log.info("ℹ️ 无足够数据计算加权平均涨幅，跳过")
        return True, 0.0

    avg_gain = total_weighted_gain / total_amount
    log.info(f"📊 昨日涨停股（成交额Top{count}）今日加权平均涨幅: {avg_gain:.2f}%")

    # ---- 使用参数化阈值（从 STRATEGY_PARAMS 读取） ----
    threshold = g.weighted_avg_gain_threshold
    if avg_gain < threshold:
        log.warn(f"🚫 加权平均涨幅 {avg_gain:.2f}% < {threshold}，触发空仓条件")
        return False, avg_gain
    else:
        log.info(f"✅ 加权平均涨幅 {avg_gain:.2f}% ≥ {threshold}，通过")
        return True, avg_gain


# ==================== 开仓买入条件（A1：单一指数趋势条件） ====================
def check_market_sentiment(context):
    """
    【A1】开仓买入条件整体替换为单一指数趋势条件（原四维情绪闸门停用，不再拦截买入）：
        昨日上证指数收盘价 >= 上证指数10日均线 × 98%
    10日均线 = 截至昨日（含昨日）最近10个交易日的收盘价均值。
    其余选股过滤、竞价过滤、卖出逻辑、时间窗口均保持不变。
    异常/数据不足时保守处理：禁止买入（fail-closed）。
    """
    try:
        yesterday = context.previous_date  # 上一交易日
        df = get_price('000001.XSHG', end_date=yesterday, count=10, fields=['close'])
        if df is None or len(df) < 10:
            log.warn("🚫 【A1开仓条件】上证指数10日数据不足，保守禁止买入")
            return False
        close_yest = float(df['close'].iloc[-1])
        ma10 = float(df['close'].mean())
        threshold = ma10 * 0.98
        if close_yest >= threshold:
            log.info("✅ 【A1开仓条件】上证昨收 %.2f ≥ 10日线 %.2f × 98%% = %.2f，允许买入"
                     % (close_yest, ma10, threshold))
            return True
        else:
            log.warn("🚫 【A1开仓条件】上证昨收 %.2f < 10日线 %.2f × 98%% = %.2f，禁止买入"
                     % (close_yest, ma10, threshold))
            return False
    except Exception as e:
        log.error(f"【A1开仓条件】计算异常，保守禁止买入: {str(e)[:50]}")
        return False


# ==================== 买入条件检查（与原策略一致） ====================
def check_buy_condition(stock, context):
    try:
        trade_days = get_trade_days_cached(context.current_dt.date(), 2)
        if len(trade_days) < 2:
            return False, "无昨日数据", {}
        yesterday = trade_days[0]
        yesterday_data = get_price(stock, end_date=yesterday, count=1, fields=['close'], fq='pre')
        today_data = get_price(stock, end_date=context.current_dt, count=1, fields=['open','close'], fq='pre', skip_paused=True)
        if today_data.empty or yesterday_data.empty:
            return False, "无数据/停牌", {}
        open_p = today_data['open'].iloc[0]
        last_p = today_data['close'].iloc[0]
        yes_close = yesterday_data['close'].iloc[0]
        open_ratio = (open_p - yes_close) / yes_close * 100
        current_ratio = (last_p - yes_close) / yes_close * 100
        
        vol_ok, vol_msg = check_turnover_volume(stock, context)
        if not vol_ok:
            return False, vol_msg, {}
        
        is_drop, drop_msg = is_real_time_drop(context, stock)
        if is_drop:
            return False, f"高开低走 {drop_msg}", {}
        
        if not (g.min_open_ratio <= open_ratio <= g.max_open_ratio):
            return False, f"开盘涨幅{open_ratio:.2f}% 不在区间", {}
        
        if current_ratio > g.max_open_ratio + 2:
            return False, f"实时涨幅{current_ratio:.2f}% > {g.max_open_ratio+2}%", {}
        
        if is_double_in_month(stock, context):
            return False, "近一个月翻倍", {}
        
        try:
            # 【V1修复】改用昨日完整资金流：当日盘中 get_money_flow 口径在回测/实盘可能不一致（实盘收盘后才有完整数据）
            flow = get_money_flow(stock, start_date=yesterday, end_date=yesterday)
            if not flow.empty and 'net_inflow' in flow.columns and 'amount' in flow.columns:
                net_inflow = flow['net_inflow'].iloc[-1]
                amount = flow['amount'].iloc[-1]
                if amount > 0:
                    inflow_ratio = (net_inflow / amount) * 100
                    if inflow_ratio < 3.0:
                        return False, f"主力净流入占比{inflow_ratio:.1f}% < 3%", {}
        except:
            pass
        
        board = get_stock_board(stock)
        cfg = g.filter_continuous_gain.get(board)
        if cfg:
            check_days = cfg['days']
            max_gain = cfg['max_gain']
            total_gain = calculate_continuous_gain(stock, yesterday, check_days)
            if total_gain != -999 and total_gain > max_gain:
                try:
                    today_turnover = calculate_turnover_rate(stock, context.current_dt.date())
                    yesterday_turnover = calculate_turnover_rate(stock, yesterday)
                    if yesterday_turnover > 0 and today_turnover >= yesterday_turnover:
                        return False, f"连续{check_days}天涨幅{total_gain}%超限且未缩量", {}
                except:
                    return False, f"连续{check_days}天涨幅超限，无法判断量能", {}
        
        industry_gain = get_industry_index_gain(stock, context.current_dt.date(), end_dt=context.current_dt)
        if industry_gain is not None and industry_gain <= 0:
            return False, f"所属行业指数涨幅{industry_gain:.2f}% ≤ 0", {}
        
        extra = {
            'open_ratio': open_ratio,
            'current_ratio': current_ratio,
            'yesterday_close': yes_close,
            'open_price': open_p,
            'current_price': last_p,
            'vol_msg': vol_msg,
        }
        if g.market_env == "bull":
            extra['premium'] = g.premium_bull
        elif g.market_env == "bear":
            extra['premium'] = g.premium_bear
        else:
            extra['premium'] = g.premium_normal
        return True, "满足买入条件", extra
    except Exception as e:
        return False, f"检查异常:{str(e)[:30]}", {}

# ==================== 手动跟单提示（不变） ====================
def manual_signal(context):
    if not g.candidate_stocks:
        log.info("⚠️ 【手动跟单】当前无候选股，跳过输出")
        return
    
    log.info("=" * 60)
    log.info(f"📢 【手动跟单提示】时间: {context.current_dt.strftime('%H:%M:%S')}")
    log.info("下面列出满足实时买入条件的股票（前12只），可手动下单（策略也将自动买入部分）")
    log.info("-" * 60)
    
    buy_list = []
    query_date = context.current_dt.date()
    for stock in g.candidate_stocks:
        if stock in context.portfolio.positions or stock in g.bought_stocks:
            continue
        can_buy, reason, extra = check_buy_condition(stock, context)
        if not can_buy:
            continue
        try:
            stock_name = get_security_info(stock).display_name
            board = get_stock_board(stock)
            current_data = get_current_data()[stock]
            current_price = current_data.last_price
            high_limit = current_data.high_limit
            suggested_limit = min(current_price * extra['premium'], high_limit)
            concept_info = get_stock_industry_and_concept(stock, query_date)
            concept_display = concept_info['display_str']
            try:
                trade_days = get_trade_days_cached(context.current_dt.date(), 2)
                yesterday = trade_days[0]
                today_vol = get_price(stock, end_date=context.current_dt, count=1, fields=['volume'], fq='pre')['volume'].iloc[0]
                avg_vol = get_price(stock, end_date=yesterday, count=5, fields=['volume'], fq='pre')['volume'].mean()
                volume_ratio = today_vol / avg_vol if avg_vol > 0 else 0
            except:
                volume_ratio = 0
            buy_list.append({
                'code': stock,
                'name': stock_name,
                'board': board,
                'price': current_price,
                'open_price': extra['open_price'],
                'gain': extra['current_ratio'],
                'open_gain': extra['open_ratio'],
                'volume_ratio': volume_ratio,
                'suggested_limit': suggested_limit,
                'high_limit': high_limit,
                'concept': concept_display,
                'reason': reason
            })
        except Exception as e:
            continue
    buy_list.sort(key=lambda x: x['gain'] - x['open_gain'], reverse=True)
    
    if not buy_list:
        log.info("✅ 暂无股票满足实时买入条件")
        log.info("=" * 60)
        return
    
    display_limit = 12
    total = len(buy_list)
    log.info(f"🎯 共筛选出 {total} 只可买入股票（按拉升强度排序），仅显示前 {display_limit} 只:")
    for idx, item in enumerate(buy_list[:display_limit], 1):
        log.info(f"【{idx}】{item['code']} {item['name']:4s} | 涨幅:{item['gain']:5.2f}% (开:{item['open_gain']:5.2f}%) | 量比:{item['volume_ratio']:5.2f} 开盘:{item['open_price']:.2f} 现价:{item['price']:.2f} | {item['concept']}")
    
    if total > display_limit:
        log.info(f"  ... 其余 {total - display_limit} 只已省略")
    
    log.info("💡 提示: 策略将自动买入部分股票，也可根据上述信息手动下单")
    log.info("=" * 60)

# ==================== 分批止盈函数（P1） ====================
def execute_partial_sell(stock, context):
    try:
        pos = context.portfolio.positions[stock]
        if pos is None or pos.total_amount == 0:
            return
        
        trade_days = get_trade_days_cached(context.current_dt.date(), 2)
        if len(trade_days) < 2:
            return
        yesterday = trade_days[0]
        yes_close = get_price(stock, end_date=yesterday, count=1, fields=['close'], fq='pre')['close'].iloc[0]
        open_price = get_current_data()[stock].day_open
        if yes_close <= 0 or open_price <= 0:
            return
        
        open_gain = (open_price - yes_close) / yes_close * 100
        stock_name = get_security_info(stock).display_name
        
        if open_gain >= 6:
            sell_ratio = 0.5
            log.info(f"📤 【分批止盈】{stock} {stock_name} 高开{open_gain:.1f}% ≥ 6%，卖出50%")
        elif open_gain >= 3:
            sell_ratio = 0.3
            log.info(f"📤 【分批止盈】{stock} {stock_name} 高开{open_gain:.1f}% 在3%~6%，卖出30%")
        else:
            sell_ratio = 1.0
            log.info(f"📤 【分批止盈】{stock} {stock_name} 高开{open_gain:.1f}% < 3%，全部卖出")
            order_target(stock, 0)
            if stock in g.pending_sell:
                del g.pending_sell[stock]
            return
        
        target_amount = int(pos.total_amount * (1 - sell_ratio))
        order_target(stock, target_amount)
        if sell_ratio < 1.0:
            g.pending_sell[stock] = True
            log.info(f"⏳ 剩余{int((1-sell_ratio)*100)}%仓位待观察，10:00决定是否清仓")
        else:
            if stock in g.pending_sell:
                del g.pending_sell[stock]
    except Exception as e:
        log.error(f"分批止盈异常 {stock}: {str(e)[:30]}")

def check_pending_sell(context):
    current_time = context.current_dt.time()
    if current_time.hour != 10 or current_time.minute > 5:
        return
    
    for stock in list(g.pending_sell.keys()):
        try:
            pos = context.portfolio.positions.get(stock)
            if pos is None or pos.total_amount == 0:
                del g.pending_sell[stock]
                continue
            
            current_data = get_current_data()[stock]
            current_price = current_data.last_price
            high_limit = current_data.high_limit
            is_limit = (current_price >= high_limit - 0.01)
            
            if is_limit:
                log.info(f"✅ {stock} 已涨停，继续持有剩余仓位")
                del g.pending_sell[stock]
            else:
                log.info(f"📤 【10:00】{stock} 未涨停，清仓剩余仓位")
                order_target(stock, 0)
                del g.pending_sell[stock]
        except Exception as e:
            log.error(f"检查pending卖出异常 {stock}: {str(e)[:30]}")

# ==================== 自动交易函数（buy_decision 等） ====================
def buy_decision(context):
    if not check_market_sentiment(context):
        log.warn("🚫 情绪过滤器阻止买入，今日暂停买入")
        g.candidate_stocks = []
        g.rebuy_candidates = []
        return
    
    cash = context.portfolio.available_cash
    hold_num = len(context.portfolio.positions)
    if hold_num >= g.max_stock_num or cash < 1000:
        return
    if g.bought_today_count >= g.max_buy_per_day:
        return
    available_stocks = [s for s in g.rebuy_candidates if s not in context.portfolio.positions and s not in g.bought_stocks]
    if not available_stocks:
        return
    buy_candidates = []
    for stock in available_stocks:
        # 【V2优化】移除重复预检：check_buy_condition 内部已含 is_double_in_month 与 is_real_time_drop 判断
        buy_signal, reason, extra = check_buy_condition(stock, context)
        if buy_signal:
            buy_candidates.append((stock, reason, extra))
    if not buy_candidates:
        return
    def get_gain_diff(item):
        stock, _, extra = item
        return extra.get('current_ratio', 0) - extra.get('open_ratio', 0)
    buy_candidates.sort(key=get_gain_diff, reverse=True)
    remain_buy_num = g.max_stock_num - hold_num
    remain_buy_today = g.max_buy_per_day - g.bought_today_count
    final_buy_num = min(remain_buy_num, remain_buy_today)
    
    for i, (stock, reason, extra) in enumerate(buy_candidates[:final_buy_num]):
        execute_buy(stock, context, extra)

def execute_buy(stock, context, extra):
    try:
        if stock in context.portfolio.positions or stock in g.bought_stocks:
            return False
        current_data = get_current_data()[stock]
        current_price = current_data.last_price
        high_limit = current_data.high_limit
        if current_price >= high_limit - 0.001:
            stock_name = get_security_info(stock).display_name
            log.info(f"🚫 放弃买入 {stock} {stock_name}：已涨停")
            return False
        if current_price <= 0:
            return False
        available_cash = context.portfolio.available_cash
        current_hold = len(context.portfolio.positions)
        remain_buy = g.max_stock_num - current_hold
        if remain_buy <= 0 or available_cash < 100:
            return False
        target_cash = available_cash / remain_buy
        buy_amount = int(target_cash / current_price / 100) * 100
        if buy_amount < 100:
            return False
        premium = extra.get('premium', g.premium_normal)
        limit_price = min(current_price * premium, high_limit)
        order_id = order(stock, buy_amount, LimitOrderStyle(limit_price))
        if order_id:
            stock_name = get_security_info(stock).display_name
            log.info(f"📥 买入: {stock} {stock_name} | {buy_amount}股 @ 限价{limit_price:.3f}")
            g.hold_days[stock] = 0
            g.bought_stocks.add(stock)
            g.bought_today_count += 1
            return True
        return False
    except Exception as e:
        log.error(f"❌ 买入失败{stock}: {str(e)[:30]}")
        return False

# ==================== 策略初始化 ====================
def initialize(context):
    log.info("="*50)
    log.info("🚀 策略名称：强者恒强（情绪加权过滤 + 分批止盈 + 多维度空仓）")
    log.info("✅ 集成：成交额加权情绪过滤 | 分批止盈 | 换手率区间 | 大单净流入 | 板块强度")
    log.info("✅ 四维度独立并行：盘前检查 | 实时检查 | 加权平均涨幅检查 | 候选股数量过滤")
    log.info("✅ 加权平均涨幅阈值可调（STRATEGY_PARAMS 中的 weighted_avg_gain_threshold）")
    log.info("="*50)
    
    for key, value in STRATEGY_PARAMS.items():
        if key == 'dynamic_asset_tiers':
            g.dynamic_asset_tiers = value
        elif key == 'filter_continuous_gain':
            g.filter_continuous_gain = value
        elif key == 'filter_after_1430_gain':
            g.filter_after_1430_gain = value
        elif key == 'filter_amplitude':
            g.filter_amplitude = value
        elif key == 'filter_turnover':
            g.filter_turnover = value
        elif key == 'market_env_adjust':
            g.market_env_adjust = value
        elif key == 'time_sell_check_exclude':
            g.time_sell_check_exclude = value
        else:
            setattr(g, key, value)
    
    g.limit_up_cnt_yest = 0
    g.limit_down_cnt_yest = 0
    g.board2_cnt_yest = 0
    g.yesterday_full_limit_up_stocks = []
    
    g.concept_cache = {}
    g.pending_sell = {}
    g.yesterday_limit_up_stocks = []
    g.yesterday_limit_up_amounts = {}
    
    # 【新增】候选股数量过滤标志初始化
    g.candidate_count_premarket_ok = True
    g.candidate_count_auction_ok = True
    
    context.order_cost = OrderCost(
        open_tax=0,
        close_tax=0.001,
        open_commission=0.0003,
        close_commission=0.0003,
        close_today_commission=0,
        min_commission=5
    )
    set_slippage(PriceRelatedSlippage(0.002))
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    
    g.candidate_stocks = []
    g.hold_days = {}
    g.has_limit_up = set()
    g.bought_stocks = set()
    g.rebuy_candidates = []
    g.bought_today_count = 0
    g.market_env = "normal"
    g.only_buy = False
    g.break_limit_sold_stocks = []
    g.sold_today = []
    g.checked_today = {}
    g.debug = True
    
    run_daily(before_market_open, time='before_open')
    run_daily(auction_filter, time=g.time_auction_filter)
    run_daily(set_only_buy_False, time=g.time_set_only_buy_false)
    run_daily(sell_only_930, time=g.time_sell_only)
    run_daily(set_only_buy_True, time=g.time_set_only_buy_true)
    run_daily(manual_signal, time=g.manual_signal_time)
    run_daily(manual_signal, time=g.manual_buy_time)
    run_daily(market_open, time=g.time_buy_start)
    run_daily(market_open, time=g.time_buy_fourth)
    run_daily(market_open, time=g.time_buy_fifth)
    run_daily(check_pending_sell, time='10:00:00')
    for hour in range(10, 15):
        for minute in range(0, 60, g.time_sell_check_interval):
            if (hour, minute) in g.time_sell_check_exclude:
                continue
            run_daily(check_break_limit_drop_for_long_hold, time=f"{hour:02d}:{minute:02d}")
    run_daily(after_market_close, time='after_close')

def set_only_buy_True(context):
    g.only_buy = True

def set_only_buy_False(context):
    g.only_buy = False

# ==================== 动态参数调整 ====================
def adjust_params_by_market(context):
    try:
        trade_days = get_trade_days_cached(context.current_dt.date(), 2)
        if len(trade_days) < 2:
            raise ValueError("无足够交易日")
        yesterday = trade_days[0]
        day_before = trade_days[1] if len(trade_days) > 1 else yesterday
        hs300_yest = get_price('000300.XSHG', end_date=yesterday, count=1, fields=['close'], fq='pre')
        hs300_before = get_price('000300.XSHG', end_date=day_before, count=1, fields=['close'], fq='pre')
        if hs300_yest.empty or hs300_before.empty:
            raise ValueError("沪深300数据缺失")
        hs300_change = (hs300_yest['close'].iloc[0] - hs300_before['close'].iloc[0]) / hs300_before['close'].iloc[0] * 100
        all_stocks = [code for code in get_all_securities(['stock']).index if '.BJ' not in code]
        # 【V2优化】批量计算昨日涨停数（原逐股500次get_price）
        flags_adj = batch_limit_up_strong_flags(all_stocks[:500], yesterday)
        limit_up_count = len(flags_adj['limit_up'])
        if hs300_change > g.hs300_bull_threshold and limit_up_count > g.limit_up_count_bull:
            g.market_env = "bull"
            adj = g.market_env_adjust['bull']
            g.min_open_ratio = max(0, STRATEGY_PARAMS['min_open_ratio'] + adj['min_open_ratio_offset'])
            g.max_open_ratio = STRATEGY_PARAMS['max_open_ratio'] + adj['max_open_ratio_offset']
            g.min_turnover_rate = max(1, STRATEGY_PARAMS['min_turnover_rate'] + adj['min_turnover_rate_offset'])
            g.stop_profit_ratio = STRATEGY_PARAMS['stop_profit_ratio'] + adj['stop_profit_ratio_offset']
            g.stop_loss_ratio = STRATEGY_PARAMS['stop_loss_ratio']
        elif hs300_change < g.hs300_bear_threshold and limit_up_count < g.limit_up_count_bear:
            g.market_env = "bear"
            adj = g.market_env_adjust['bear']
            g.min_open_ratio = max(0, STRATEGY_PARAMS['min_open_ratio'] + adj['min_open_ratio_offset'])
            g.max_open_ratio = STRATEGY_PARAMS['max_open_ratio'] + adj['max_open_ratio_offset']
            g.min_turnover_rate = max(1, STRATEGY_PARAMS['min_turnover_rate'] + adj['min_turnover_rate_offset'])
            g.stop_loss_ratio = STRATEGY_PARAMS['stop_loss_ratio'] + adj['stop_loss_ratio_offset']
            g.stop_profit_ratio = STRATEGY_PARAMS['stop_profit_ratio']
        else:
            g.market_env = "normal"
            g.min_open_ratio = STRATEGY_PARAMS['min_open_ratio']
            g.max_open_ratio = STRATEGY_PARAMS['max_open_ratio']
            g.stop_loss_ratio = STRATEGY_PARAMS['stop_loss_ratio']
            g.stop_profit_ratio = STRATEGY_PARAMS['stop_profit_ratio']
            g.min_turnover_rate = STRATEGY_PARAMS['min_turnover_rate']
        log.info(f"市场环境：{g.market_env} | 开盘涨幅：{g.min_open_ratio}%~{g.max_open_ratio}% | 换手率：{g.min_turnover_rate}%")
    except Exception as e:
        log.warn(f"动态参数调整失败，使用默认参数：{str(e)[:50]}")
        g.market_env = "normal"
        g.min_open_ratio = STRATEGY_PARAMS['min_open_ratio']
        g.max_open_ratio = STRATEGY_PARAMS['max_open_ratio']
        g.stop_loss_ratio = STRATEGY_PARAMS['stop_loss_ratio']
        g.stop_profit_ratio = STRATEGY_PARAMS['stop_profit_ratio']
        g.min_turnover_rate = STRATEGY_PARAMS['min_turnover_rate']

# ==================== 盘前处理（统计昨日数据，计算盘前情绪条件） ====================
def before_market_open(context):
    log.info("="*50)
    log.info(f"📅 新交易日开始：{context.current_dt.strftime('%Y-%m-%d')}")
    log.info("盘前选股开始，并计算盘前情绪条件（基于昨日数据）")
    
    # 重置相关变量
    g.pending_sell = {}
    g.candidate_stocks = []
    g.has_limit_up.clear()
    g.bought_stocks.clear()
    g.rebuy_candidates = []
    g.bought_today_count = 0
    g.only_buy = False
    g.break_limit_sold_stocks = []
    g.sold_today = []
    if hasattr(g, 'checked_today'):
        del g.checked_today
    g.checked_today = {}
    adjust_params_by_market(context)
    total_asset = context.portfolio.total_value
    g.max_stock_num, g.max_buy_per_day = get_dynamic_max_hold(total_asset)
    log.info(f"盘前动态配置：总资产{total_asset:.2f} → 最大持仓{g.max_stock_num}只，单日买入{g.max_buy_per_day}只")
    
    trade_days = get_trade_days_cached(context.current_dt.date(), 2)
    if len(trade_days) < 2:
        log.info("无昨日交易日，今日跳过选股，且盘前条件默认不满足")
        g.premarket_sentiment_ok = False
        # 候选股数量标志置为不满足
        g.candidate_count_premarket_ok = False
        return
    yesterday = trade_days[0]
    log.info(f"使用前一个交易日数据: {yesterday}")
    
    # ----- 统计昨日数据（用于盘前检查和日志） -----
    limit_up_cnt, limit_down_cnt, board2_cnt, yest_up_codes = get_yesterday_market_stats(context, yesterday)
    g.yesterday_full_limit_up_stocks = yest_up_codes  # 保存完整列表供实时2连板使用
    log.info(f"📊 【盘前统计·昨日数据】涨停 {limit_up_cnt} 只，跌停 {limit_down_cnt} 只，2连板 {board2_cnt} 只")
    
    # 计算盘前情绪条件是否满足
    premarket_ok = True
    pre_reasons = []
    if limit_up_cnt < g.premarket_limit_up_threshold:
        premarket_ok = False
        pre_reasons.append(f"涨停数 {limit_up_cnt} < {g.premarket_limit_up_threshold}")
    if limit_down_cnt > g.premarket_limit_down_threshold:
        premarket_ok = False
        pre_reasons.append(f"跌停数 {limit_down_cnt} > {g.premarket_limit_down_threshold}")
    if board2_cnt < g.premarket_2board_threshold:
        premarket_ok = False
        pre_reasons.append(f"2连板数 {board2_cnt} < {g.premarket_2board_threshold}")
    g.premarket_sentiment_ok = premarket_ok
    if not premarket_ok:
        log.warn(f"🚫 盘前情绪条件不满足：{'；'.join(pre_reasons)}，盘前维度禁止买入")
    else:
        log.info(f"✅ 盘前情绪条件全部通过（涨停≥{g.premarket_limit_up_threshold}，跌停≤{g.premarket_limit_down_threshold}，2连板≥{g.premarket_2board_threshold}），盘前维度允许买入")
    
    # 获取今日可交易股票池（用于选股）
    current_tradable_stocks = [
        code for code in get_all_securities(['stock'], date=context.current_dt.date()).index
        if (not g.filter_beijing or '.BJ' not in code)
    ]
    current_tradable_stocks = [
        code for code in current_tradable_stocks
        if (get_stock_board(code) in ("main", "gem")) or (not g.filter_kcb and get_stock_board(code) == "star")
    ]
    log.info("今日可交易A股数量: {}".format(len(current_tradable_stocks)))
    
    # ----- 【V2优化】批量计算昨日涨停/强势标记与ST集合（原逐股约2.5万次API/天，现压缩为个位数批量调用） -----
    st_set = batch_st_set(current_tradable_stocks, yesterday) if g.filter_st_stock else set()
    flags = batch_limit_up_strong_flags(current_tradable_stocks, yesterday)
    limit_up_set = flags['limit_up']
    strong_set = flags['strong']
    log.info(f"【V2】批量标记完成：昨日涨停 {len(limit_up_set)} 只，昨日强势 {len(strong_set)} 只，历史ST {len(st_set)} 只")

    # ----- 获取昨日涨停股（成交额Top30，用于加权平均情绪）【V2：批量取成交额】 -----
    limit_up_candidates = []
    lu_list = [s for s in current_tradable_stocks
               if s in limit_up_set and not (g.filter_st_stock and s in st_set) and '.BJ' not in s]
    if lu_list:
        money_map = {}
        try:
            money_df = get_price(lu_list, end_date=yesterday, count=1, fields=['money'], fq='pre', panel=False)
            if money_df is not None and not money_df.empty:
                for _, row in money_df.iterrows():
                    money_map[row['code']] = row['money']
        except:
            money_map = {}
        for s in lu_list:
            try:
                amount = money_map.get(s)
                if amount is None or pd.isna(amount):
                    # 降级：逐股获取成交额（仅涨停股，数量有限）
                    vol_data = get_price(s, end_date=yesterday, count=1, fields=['money'], fq='pre')
                    amount = vol_data['money'].iloc[0] if not vol_data.empty else None
                if amount is not None and not pd.isna(amount) and amount > 1e7:
                    limit_up_candidates.append({'code': s, 'amount': amount})
            except:
                continue
    limit_up_candidates.sort(key=lambda x: x['amount'], reverse=True)
    top30 = limit_up_candidates[:30]
    g.yesterday_limit_up_stocks = [item['code'] for item in top30]
    g.yesterday_limit_up_amounts = {item['code']: item['amount'] for item in top30}
    log.info(f"昨日涨停股（成交额Top{len(top30)}）: {len(g.yesterday_limit_up_stocks)}只（用于加权平均涨幅）")
    
    # ----- 盘前选股（强势股筛选）【V2：初筛门控改用批量标记，过滤链逻辑不变】 -----
    limit_up_stocks = []
    batch_size = 1000
    for i in range(0, len(current_tradable_stocks), batch_size):
        batch_stocks = current_tradable_stocks[i:i+batch_size]
        for stock in batch_stocks:
            try:
                if g.filter_st_stock and stock in st_set:
                    continue
                if g.filter_kcb and get_stock_board(stock) == 'star':
                    continue
                if stock in limit_up_set or stock in strong_set:
                    pass_filter, filter_msg, stock_name = filter_by_continuous_gain(stock, yesterday)
                    if not pass_filter:
                        continue
                    pass_1430_filter, filter_1430_msg, stock_name = filter_after_1430_gain(stock, yesterday)
                    if not pass_1430_filter:
                        continue
                    pass_amp_filter, amp_msg, stock_name = filter_by_amplitude(stock, yesterday)
                    if not pass_amp_filter:
                        continue
                    pass_turnover_filter, turnover_msg, stock_name = filter_by_turnover(stock, yesterday)
                    if not pass_turnover_filter:
                        continue
                    pass_limitdown_filter, limitdown_msg, stock_name = has_limit_down_in_last_3days(stock, yesterday)
                    if not pass_limitdown_filter:
                        continue
                    pass_shrink_filter, shrink_msg, stock_name = is_continuous_shrink_rise(stock, yesterday)
                    if not pass_shrink_filter:
                        continue
                    limit_up_stocks.append(stock)
            except:
                continue
    log.info("核心识别强势股: {}只".format(len(limit_up_stocks)))
    if len(limit_up_stocks) == 0:
        limit_up_stocks = find_limit_up_loose(current_tradable_stocks[:1500], yesterday)
        log.info("宽松识别后强势股: {}只".format(len(limit_up_stocks)))
    if len(limit_up_stocks) == 0:
        limit_up_stocks = find_limit_up_ultra_loose(current_tradable_stocks[:1500], yesterday)
        log.info("超宽松识别后强势股: {}只".format(len(limit_up_stocks)))
    g.candidate_stocks = limit_up_stocks.copy()
    g.rebuy_candidates = limit_up_stocks.copy()
    
    if g.candidate_stocks:
        log.info(f"📋 【盘前候选股名单】共 {len(g.candidate_stocks)} 只")
    else:
        log.info("⚠️ 盘前未选出任何候选股")

    # ----- 【新增】盘前候选股数量检查 -----
    pre_count = len(g.candidate_stocks)
    if pre_count < g.premarket_candidate_threshold:
        g.candidate_count_premarket_ok = False
        log.warn(f"🚫 盘前候选股数量 {pre_count} < {g.premarket_candidate_threshold}，候选股数量维度盘前条件不满足")
    else:
        g.candidate_count_premarket_ok = True
        log.info(f"✅ 盘前候选股数量 {pre_count} ≥ {g.premarket_candidate_threshold}，盘前条件满足")

# ==================== 竞价过滤（不变） ====================
def auction_filter(context):
    log.info("="*50)
    log.info("9:26 竞价过滤")
    if g.filter_kcb:
        g.candidate_stocks = [s for s in g.candidate_stocks if get_stock_board(s) != 'star']
    
    final_stocks = []
    range_filter_count = 0
    risk_filter_count = 0
    other_filter_count = 0
    current_date = context.current_dt.date()
    
    for stock in g.candidate_stocks:
        if not check_basic_quality(stock, context):
            other_filter_count += 1
            continue
        stock_name = get_security_info(stock).display_name if get_security_info(stock) else "未知"
        is_risk = False
        try:
            board = get_stock_board(stock)
            trade_days = get_trade_days_cached(current_date, 2)
            if len(trade_days) < 2:
                other_filter_count += 1
                continue
            yesterday = trade_days[0]
            hist = get_price(stock, end_date=yesterday, count=1, fields=['close'], fq='pre')
            if hist.empty:
                other_filter_count += 1
                continue
            close_yest = hist['close'].iloc[0]
            current_data = get_current_data()[stock]
            open_price = current_data.day_open
            open_ratio = (open_price - close_yest) / close_yest * 100
            
            if not (g.min_open_ratio <= open_ratio <= g.max_open_ratio):
                is_risk = True
                range_filter_count += 1
            
            if not is_risk:
                vol_hist = attribute_history(stock, 3, '1d', fields=['close', 'volume', 'high_limit'], skip_paused=True, df=True)
                if len(vol_hist) >= 3:
                    vol_yest = vol_hist['volume'].iloc[-1]
                    vol_beyest = vol_hist['volume'].iloc[-2]
                    high_limit = vol_hist['high_limit'].iloc[-1]
                    is_limit_up = abs(close_yest - high_limit) / high_limit < 0.006
                    is_vol_big = vol_yest >= vol_beyest * 1.8
                    if is_limit_up and is_vol_big:
                        if board == 'main':
                            threshold = g.risk_open_threshold_main
                        else:
                            threshold = g.risk_open_threshold_gem_star
                        if open_ratio >= threshold:
                            is_risk = True
                            risk_filter_count += 1
        except:
            is_risk = True
            other_filter_count += 1
        
        if not is_risk:
            industry_gain = get_industry_index_gain(stock, current_date, end_dt=context.current_dt)
            if industry_gain is not None and industry_gain <= 0:
                is_risk = True
                other_filter_count += 1
        
        if not is_risk:
            final_stocks.append(stock)
    
    g.candidate_stocks = final_stocks.copy()
    g.rebuy_candidates = final_stocks.copy()
    log.info(f"竞价过滤统计：通过 {len(final_stocks)} 只 | 区间不符 {range_filter_count} | 风险股 {risk_filter_count} | 其他 {other_filter_count}")
    
    if final_stocks:
        log.info(f"🎯 【最终候选股名单】共 {len(final_stocks)} 只")
    else:
        log.info("⚠️ 竞价过滤后无候选股")

    # ----- 【新增】竞价后候选股数量检查 -----
    auction_count = len(g.candidate_stocks)
    if auction_count < g.auction_candidate_threshold:
        g.candidate_count_auction_ok = False
        log.warn(f"🚫 竞价后候选股数量 {auction_count} < {g.auction_candidate_threshold}，候选股数量维度竞价后条件不满足")
    else:
        g.candidate_count_auction_ok = True
        log.info(f"✅ 竞价后候选股数量 {auction_count} ≥ {g.auction_candidate_threshold}，竞价后条件满足")

# ==================== 卖出相关（不变） ====================
def sell_only_930(context):
    log.info("=== 9:30 专属卖出（含分批止盈） ===")
    total_asset = context.portfolio.total_value
    g.max_stock_num, g.max_buy_per_day = get_dynamic_max_hold(total_asset)
    
    for stock in list(context.portfolio.positions.keys()):
        hold_days = g.hold_days.get(stock, 0)
        if hold_days == 1:
            execute_partial_sell(stock, context)
        else:
            if stock in g.bought_stocks:
                continue
            try:
                current_data = get_current_data()[stock]
                if current_data is None:
                    continue
                hl = current_data.high_limit
                op = current_data.day_open
                if hl > 0 and abs(op - hl) / hl > 0.005:
                    log.info("📤 9:30 开盘未涨停卖出（>1天持仓）：" + stock)
                    execute_sell(stock, context)
            except:
                continue
    
    sell_decision(context)
    log.info(f"卖出后可用资金：{context.portfolio.available_cash:.2f}")

def check_break_limit_drop_for_long_hold(context):
    for stock in list(context.portfolio.positions.keys()):
        hold_days = g.hold_days.get(stock, 0)
        if hold_days <= 1:
            continue
        try:
            current_data = get_current_data()[stock]
            if current_data is None:
                continue
            current_price = current_data.last_price
            today_high = current_data.high
            high_limit = current_data.high_limit
            if today_high >= high_limit * 0.995:
                g.has_limit_up.add(stock)
            if stock in g.has_limit_up:
                drop_ratio = (today_high - current_price) / today_high * 100
                if drop_ratio >= g.break_drop_ratio:
                    execute_sell(stock, context)
                    if stock not in g.break_limit_sold_stocks:
                        g.break_limit_sold_stocks.append(stock)
        except:
            continue

def check_break_limit_drop(context):
    for stock in list(context.portfolio.positions.keys()):
        if stock in g.bought_stocks:
            continue
        try:
            current_data = get_current_data()[stock]
            if current_data is None:
                continue
            current_price = current_data.last_price
            today_high = current_data.high
            high_limit = current_data.high_limit
            if today_high >= high_limit * 0.995:
                g.has_limit_up.add(stock)
            if stock in g.has_limit_up:
                drop_ratio = (today_high - current_price) / today_high * 100
                if drop_ratio >= g.break_drop_ratio:
                    execute_sell(stock, context)
                    if stock not in g.break_limit_sold_stocks:
                        g.break_limit_sold_stocks.append(stock)
        except:
            continue

def sell_decision(context):
    for stock in list(context.portfolio.positions.keys()):
        if stock in g.bought_stocks:
            continue
        if should_sell(stock, context):
            execute_sell(stock, context)

def should_sell(stock, context):
    try:
        price_data = get_price(stock, end_date=context.current_dt, count=1, fields=['close'], fq='pre')
        if price_data.empty:
            return True
        pos = context.portfolio.positions[stock]
        if pos.avg_cost <= 0:
            return True
        current_price = price_data['close'].iloc[0]
        profit_ratio = (current_price - pos.avg_cost) / pos.avg_cost * 100
        vdrop, _ = check_volume_drop(stock, context)
        if vdrop:
            return True
        if profit_ratio <= g.stop_loss_ratio:
            return True
        if profit_ratio >= g.stop_profit_ratio and stock not in g.has_limit_up:
            return True
        if g.hold_days.get(stock,0) >= g.max_hold_days and stock not in g.has_limit_up:
            return True
        return False
    except:
        return True

def execute_sell(stock, context):
    try:
        for od in get_open_orders():
            if od.security == stock and od.status == OrderStatus.NOT_FILLED:
                cancel_order(od.order_id)
    except:
        pass
    try:
        price_data = get_price(stock, end_date=context.current_dt, count=1, fields=['close'], fq='pre')
        if price_data.empty:
            return False
        current_price = price_data['close'].iloc[0]
        pos = context.portfolio.positions.get(stock)
        if pos is None:
            return False
        avg_cost = pos.avg_cost
        hold_days = g.hold_days.get(stock, 0) + 1
        profit_ratio = (current_price - avg_cost) / avg_cost * 100 if avg_cost > 0 else 0
        stock_name = get_security_info(stock).display_name
        order_target(stock, 0)
        if stock in g.pending_sell:
            del g.pending_sell[stock]
        g.sold_today.append({
            'code': stock,
            'name': stock_name,
            'cost': avg_cost,
            'sell_price': current_price,
            'profit_ratio': profit_ratio,
            'hold_days': hold_days,
            'sell_time': context.current_dt.strftime('%H:%M:%S')
        })
        log.info(f"📤 卖出成功: {stock} {stock_name} @ {current_price:.3f} 收益:{profit_ratio:.2f}%")
        if stock in g.hold_days:
            del g.hold_days[stock]
        if stock not in g.rebuy_candidates:
            g.rebuy_candidates.append(stock)
        return True
    except Exception as e:
        log.error(f"❌ 卖出失败{stock}: {str(e)[:30]}")
        return False

def market_open(context):
    check_pending_sell(context)
    
    total_asset = context.portfolio.total_value
    g.max_stock_num, g.max_buy_per_day = get_dynamic_max_hold(total_asset)
    if not g.only_buy:
        check_break_limit_drop(context)
        for stock in list(context.portfolio.positions.keys()):
            if stock in g.bought_stocks:
                continue
            try:
                current_data = get_current_data()[stock]
                if current_data is None:
                    continue
                hl = current_data.high_limit
                op = current_data.day_open
                if abs(op - hl) / hl > 0.005:
                    log.info("📤 开盘未涨停卖出: {}".format(stock))
                    execute_sell(stock, context)
            except:
                continue
        sell_decision(context)
    buy_decision(context)
    update_hold_status(context)

def update_hold_status(context):
    for stock in context.portfolio.positions:
        try:
            current_data = get_current_data()[stock]
            if current_data is None:
                continue
            high = current_data.high
            high_limit = current_data.high_limit
            if high >= high_limit * 0.995 and stock not in g.has_limit_up:
                g.has_limit_up.add(stock)
                stock_name = get_security_info(stock).display_name
                log.info("✅ 标记涨停: {} {}".format(stock, stock_name))
        except:
            continue

def after_market_close(context):
    log.info("="*50)
    today = context.current_dt.date()
    log.info("收盘总结: {}".format(today))
    for stock in context.portfolio.positions:
        if stock not in g.bought_stocks:
            g.hold_days[stock] = g.hold_days.get(stock, 0) + 1
    if len(g.sold_today) > 0:
        log.info(f"📤 今日卖出：{len(g.sold_today)}只")
        for sell in g.sold_today:
            log.info(f"  {sell['code']} {sell['name']} | 成本:{sell['cost']:.3f} | 卖出:{sell['sell_price']:.3f} | 收益:{sell['profit_ratio']:.2f}% | 持有{sell['hold_days']}天")
    hold_stocks = list(context.portfolio.positions.keys())
    log.info(f"📈 最终持仓：{len(hold_stocks)}只")
    for stock in hold_stocks:
        try:
            pos = context.portfolio.positions[stock]
            stock_name = get_security_info(stock).display_name
            profit_ratio = (pos.price - pos.avg_cost) / pos.avg_cost * 100 if pos.avg_cost > 0 else 0
            days = g.hold_days.get(stock, 0)
            flag = "✅" if stock in g.has_limit_up else "❌"
            log.info(f"  {stock} {stock_name} | 成本:{pos.avg_cost:.3f} | 当前:{pos.price:.3f} | 收益:{profit_ratio:.2f}% | 持有{days}天 | 涨停:{flag}")
        except:
            log.info(f"  {stock} | 持仓信息获取失败")
    total_asset = context.portfolio.total_value
    cash = context.portfolio.available_cash
    log.info(f"💵 总资产：{total_asset:.2f} | 可用资金：{cash:.2f}")
    log.info("="*50)