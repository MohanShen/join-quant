# Clone from JoinQuant
# postId: 004aca1c2b4beba715adaf31885c4c16
# backtestId: 689b7102eb16ab9f9712b1645712c620
# title: 重研可SHI盘的打板策略

# -*- coding: utf-8 -*-

from jqdata import *
from jqfactor import *
from jqlib.technical_analysis import *
import pandas as pd
import numpy as np
import time
import datetime as dt
import logging
from datetime import datetime, timedelta
from difflib import SequenceMatcher
import json
import json


# ============================================================================
# 1. 初始化函数、日志函数
# ========================================================================
def initialize(context):
    set_option('use_real_price', True)
    log.set_level('system', 'error')
    set_option('avoid_future_data', True)
    setup_research_cost_model()

    g.is_empty = False
    
    g.jk_stk_num = 1 #聚宽实盘股票数量

    # 分仓数量
    g.position_limit = 3  # 最大持仓数量，可配置
    # 聚宽因子
    g.jqfactor = 'VOL5'  # 5日平均换手率（只是做为示例）
    g.sort = True  # 选取因子值最小
    g.emo_count = []
    g.gap_up = []
    g.gap_down = []
    g.reversal = []
    g.fxsbdk = []
    g.lblt = []
    g.hot_concepts_cache = []
    g.cache_max_days = 5
    g.min_score = 14
    g.qualified_stocks = []
    g.lblt_stocks = []
    g.rzq_stocks = []
    g.gk_stocks = []
    g.dk_stocks = []
    g.fxsbdk_stocks = []
    g.last_trade_info = None
    g.score_cache = {}  # 存储股票评分结果
    g.concept_num = 8 # 缓每日热点概念最大个数
    g.priority_config = []
    g.enable_market_risk_filter = True
    g.research_events = []
    g.research_baseline = {}
    g.current_pattern_lists = {}
    g.order_state = {}
    g.execution_config = {
        'mode': 'research',
        'send_external_signals': False,
        'require_order_result_for_signal': True,
        'allow_repeat_signal_same_bar': False
    }
    g.risk_config = {
        'max_drawdown_guard': 0.15,
        'single_stock_max_weight': 0.50,
        'daily_loss_stop': -0.03,
        'consecutive_loss_stop': 3,
        'max_limit_down_count': 30,
        'max_broken_board_rate': 0.45,
        'min_limit_up_count': 20,
        'min_index_volume_ratio': 0.55
    }

    # 添加日志统计变量
    g.trade_stats = {
        'daily_returns': [],  # 每日收益
        'position_stats': {},  # 持仓统计
        'market_stats': {},  # 市场统计
        'trade_details': [],  # 交易明细
        'mode_stats': {},
        'risk_events': [],
        'baseline': {}
    }
    register_research_baseline()

    # 定时任务
    run_daily(record_morning_stats, '09:25')  # 盘前数据统计
    run_daily(record_closing_stats, '15:00')  # 盘后数据统计
    run_daily(get_stock_list, '09:27:00')
    run_daily(buy, '09:27:27')
    run_daily(buy, '14:50:00')  # 周五下午建仓
    run_daily(sell_limit_down, time='09:28', reference_security='000300.XSHG')
    run_daily(log_daily_trades, '15:05')  # 每日15:05记录当日交易

    # 优化：sell2函数调度（9:31~14:56每15分钟一次，避开竞价时间）
    sell2_times = [
        # 上午时段
        "10:31", "11:01",
        # 下午时段（跳过午间休市）
        "13:31", "14:01", "14:31", "14:50"  # 最后一次为14:50（替代15:00）
    ]
    for time_str in sell2_times:
        run_daily(sell2, time=time_str, reference_security='000300.XSHG')

    # 优化：使用循环设置每5分钟检测任务
    # 上午时间段：09:30-10:30
    for hour in range(9, 11):
        start_minute = 36 if hour == 9 else 0  # 9点从30分开始，10点从0分开始
        end_minute = 60 if hour == 9 else 35  # 9点到60分，10点到30分结束

        for minute in range(start_minute, end_minute, 5):
            time_str = f"{hour:02d}:{minute:02d}"
            run_daily(sell_limit_per5min, time=time_str, reference_security='000300.XSHG')

    # 下午时间段：13:05-14:45
    for hour in range(13, 15):
        start_minute = 5 if hour == 13 else 0  # 13点从5分开始，14点从0分开始
        end_minute = 60 if hour == 13 else 50  # 13点到60分，14点到45分结束

        for minute in range(start_minute, end_minute, 5):
            time_str = f"{hour:02d}:{minute:02d}"
            run_daily(sell_limit_per5min, time=time_str, reference_security='000300.XSHG')

# 根据市场环境更新策略优先级
def update_strategy_priority(trend):
    """根据市场趋势更新策略优先级"""
    # 根据分析结果设置不同市场环境下的策略优先级
    if trend == 'down':
        # 下跌市场: 反向首板低开(100%)、一进二(67%)、弱转强(0%)
        g.priority_config = ["lb", "fxsbdk", "yje", "rzq",  "dk"]
    elif trend == 'strong_up':
        # 强势上涨市场: 连板龙头(56%)、弱转强(50%)、一进二(50%)
        g.priority_config = ["lb", "rzq", "yje", "fxsbdk", "dk"]
    elif trend == 'flat':
        # 平稳市场: 连板龙头(67%)、一进二(41%)
        g.priority_config = ["lb", "rzq", "yje", "fxsbdk", "dk"]
    elif trend == 'up':
        # 上涨市场: 一进二(40%)、连板龙头(35%)
        g.priority_config = ["yje", "lb", "rzq", "fxsbdk", "dk"]
    else:
        # 默认优先级
        g.priority_config = ["lb", "rzq","yje", "dk", "fxsbdk"]
    # 存储当前策略优先级
    g.trade_stats['strategy_priority'] = {
        'trend': trend,
        'priority': g.priority_config
    }
    log.info(f"根据市场趋势 [{trend}] 更新策略优先级: {' > '.join(g.priority_config)}")

def setup_research_cost_model():
    """Set conservative stock costs/slippage for research-quality backtests."""
    try:
        set_order_cost(
            OrderCost(
                open_tax=0,
                close_tax=0.001,
                open_commission=0.0003,
                close_commission=0.0003,
                close_today_commission=0,
                min_commission=5
            ),
            type='stock'
        )
    except Exception as e:
        log.warning(f"璁剧疆浜ゆ槗鎴愭湰澶辫触: {str(e)}")

    try:
        set_slippage(FixedSlippage(0.02))
    except Exception as e:
        log.warning(f"璁剧疆婊戠偣澶辫触: {str(e)}")


def register_research_baseline():
    """Record the strategy baseline so later research runs are comparable."""
    try:
        baseline = {
            'version': 'research_v1',
            'position_limit': getattr(g, 'position_limit', None),
            'min_score': getattr(g, 'min_score', None),
            'jqfactor': getattr(g, 'jqfactor', None),
            'sort_ascending': getattr(g, 'sort', None),
            'patterns': ['lb', 'yje', 'rzq', 'dk', 'fxsbdk'],
            'buy_schedule': ['09:27:27', '14:50:00'],
            'selection_schedule': ['09:27:00'],
            'sell_schedule': ['09:28', '10:31', '11:01', '13:31', '14:01', '14:31', '14:50'],
            'risk_config': dict(getattr(g, 'risk_config', {})),
            'execution_config': dict(getattr(g, 'execution_config', {}))
        }
        g.research_baseline = baseline
        if hasattr(g, 'trade_stats'):
            g.trade_stats['baseline'] = baseline
        log.info(f"research baseline: {baseline}")
    except Exception as e:
        log.warning(f"璁板綍绛栫暐鍩哄噯澶辫触: {str(e)}")


def build_pattern_lists(lblt_stocks=None, gk_stocks=None, rzq_stocks=None, dk_stocks=None, fxsbdk_stocks=None):
    """Create a same-day pattern map. Never rely on previous-day global lists."""
    return {
        'lb': list(lblt_stocks or []),
        'yje': list(gk_stocks or []),
        'rzq': list(rzq_stocks or []),
        'dk': list(dk_stocks or []),
        'fxsbdk': list(fxsbdk_stocks or [])
    }


def set_current_pattern_lists(pattern_lists):
    g.current_pattern_lists = pattern_lists or build_pattern_lists()


def get_stock_pattern(stock, pattern_lists=None):
    pattern_lists = pattern_lists or getattr(g, 'current_pattern_lists', {}) or {}
    for pattern, stock_list in pattern_lists.items():
        if stock in stock_list:
            return pattern
    if stock in getattr(g, 'lblt', []):
        return 'lb'
    if stock in getattr(g, 'gap_up', []):
        return 'yje'
    if stock in getattr(g, 'reversal', []):
        return 'rzq'
    if stock in getattr(g, 'gap_down', []):
        return 'dk'
    if stock in getattr(g, 'fxsbdk', []):
        return 'fxsbdk'
    return 'unknown'


def get_stock_pattern_name(stock, pattern_lists=None):
    pattern_name_map = {
        'lb': '连板龙头',
        'yje': '一进二',
        'rzq': '弱转强',
        'dk': '首板低开',
        'fxsbdk': '跌停反核修复',
        'unknown': '未分类'
    }
    return pattern_name_map.get(get_stock_pattern(stock, pattern_lists), '未分类')


def record_research_event(context, stock, action, price=None, reason='', details=None, pattern=None):
    """Store a standard event row for attribution and later research reports."""
    try:
        if not hasattr(g, 'research_events'):
            g.research_events = []
        score_data = getattr(g, 'score_cache', {}).get(stock, {})
        market_stats = getattr(g, 'trade_stats', {}).get('market_stats', {})
        event = {
            'date': context.current_dt.strftime('%Y-%m-%d'),
            'time': context.current_dt.strftime('%H:%M:%S'),
            'stock': stock,
            'action': action,
            'pattern': pattern or get_stock_pattern(stock),
            'pattern_name': get_stock_pattern_name(stock),
            'price': float(price) if price is not None else None,
            'reason': reason,
            'total_score': score_data.get('total_score'),
            'factors': score_data.get('factors', {}),
            'market_env': market_stats.get('trend', ''),
            'market_risk_level': market_stats.get('risk_level', ''),
            'details': details or {}
        }
        g.research_events.append(event)
        if hasattr(g, 'trade_stats'):
            g.trade_stats.setdefault('trade_details', []).append(event)
    except Exception as e:
        log.warning(f"璁板綍鐮旂┒浜嬩欢澶辫触 {stock}: {str(e)}")


def record_mode_stat(pattern, key, amount=1):
    if not hasattr(g, 'trade_stats'):
        return
    mode_stats = g.trade_stats.setdefault('mode_stats', {})
    stat = mode_stats.setdefault(pattern or 'unknown', {})
    stat[key] = stat.get(key, 0) + amount


def emit_trading_signal(action, stock_code, stock_name='', stock_num=0, order_result=None, quantity=None):
    """论坛分享版：已移除外部交易信号发送，仅保留接口兼容。"""
    try:
        log.info(f"[forum-share] 外部交易信号已移除: {action} {stock_code}")
    except Exception:
        pass
    return False


def can_trade_price(stock, current_data, action):
    """Conservative limit-up/down tradability check for research backtests."""
    try:
        data = current_data[stock]
        price = data.last_price
        if action == 'buy' and price >= data.high_limit:
            return False, 'limit_up_untradable'
        if action == 'sell' and price <= data.low_limit:
            return False, 'limit_down_untradable'
        if getattr(data, 'paused', False):
            return False, 'paused'
        return True, ''
    except Exception as e:
        return False, f'quote_error:{str(e)}'


def analyze_market_environment(context):
    """Build a compact market environment/risk snapshot using T-1 data."""
    result = {
        'risk_level': 'normal',
        'risk_reasons': [],
        'limit_up_count': 0,
        'limit_down_count': 0,
        'broken_board_rate': 0,
        'market_allows_buy': True
    }
    try:
        date = context.previous_date
        initial_list = prepare_stock_list(date)
        hl_list = get_hl_stock(initial_list, date)
        ll_list = get_ll_stock(initial_list, date)
        ever_hl_list = get_ever_hl_stock(initial_list, date)
        broken_count = max(len(ever_hl_list) - len(hl_list), 0)
        ever_count = len(ever_hl_list)
        broken_rate = broken_count / ever_count if ever_count else 0

        result.update({
            'limit_up_count': len(hl_list),
            'limit_down_count': len(ll_list),
            'broken_board_count': broken_count,
            'ever_limit_up_count': ever_count,
            'broken_board_rate': broken_rate
        })

        risk_config = getattr(g, 'risk_config', {})
        if len(ll_list) >= risk_config.get('max_limit_down_count', 30):
            result['risk_reasons'].append('too_many_limit_down')
        if broken_rate >= risk_config.get('max_broken_board_rate', 0.45):
            result['risk_reasons'].append('high_broken_board_rate')
        if len(hl_list) < risk_config.get('min_limit_up_count', 20):
            result['risk_reasons'].append('low_limit_up_count')

        market_stats = getattr(g, 'trade_stats', {}).get('market_stats', {})
        if market_stats.get('volume_ratio', 1) < risk_config.get('min_index_volume_ratio', 0.55):
            result['risk_reasons'].append('low_index_volume')

        if result['risk_reasons']:
            result['risk_level'] = 'risk_off'
            result['market_allows_buy'] = False
    except Exception as e:
        result['risk_level'] = 'unknown'
        result['risk_reasons'].append(f'env_error:{str(e)}')
    return result


def market_allows_new_position(context):
    market_stats = getattr(g, 'trade_stats', {}).get('market_stats', {})
    if not getattr(g, 'enable_market_risk_filter', True):
        return True, []
    if market_stats.get('risk_level') == 'risk_off':
        return False, market_stats.get('risk_reasons', [])
    return True, []


def console_notice(msg):
    """论坛分享版：将原 send_message 提示恢复为聚宽控制台输出。"""
    try:
        log.info(str(msg))
    except Exception:
        pass


def log_daily_trades(context):
    """
    记录每日交易日志
    """
    try:
        if not hasattr(g, 'today_trades'):
            log.info("今日无交易")
            return

        log.info("\n==== 今日交易总结 ====")
        
        # 统计交易情况
        total_trades = len(g.today_trades)
        buy_trades = [trade for trade in g.today_trades if trade['action'] == '买入']
        sell_trades = [trade for trade in g.today_trades if trade['action'] == '卖出']
        
        log.info(f"总交易数: {total_trades}")
        log.info(f"买入交易: {len(buy_trades)}")
        log.info(f"卖出交易: {len(sell_trades)}")
        
        # 计算总体盈亏
        total_profit_pct = sum(trade.get('profit_pct', 0) for trade in sell_trades) / len(sell_trades) if sell_trades else 0
        log.info(f"平均盈亏: {total_profit_pct:.2%}")
        
        # 详细交易记录
        for trade in g.today_trades:
            log.info(f"{trade['stock']} - {trade['action']} - 价格: {trade['price']:.2f} - 原因: {trade.get('reason', '无')}")
        
        log.info("==== 交易总结结束 ====\n")
        
        # 重置今日交易记录
        g.today_trades = []
    
    except Exception as e:
        log.error(f"记录每日交易日志失败: {str(e)}")

# ============================================================================
# 2. 概念筛选&缓存主函数、盘前数据统计函数
# ==========================================================================
def check_cache_status():
    """
    检查缓存状态
    """
    try:
        if not hasattr(g, 'hot_concepts_data_cache') or not g.hot_concepts_data_cache:
            return "缓存为空"

        cache_count = len(g.hot_concepts_data_cache)
        return f"正常({cache_count}个文件)"

    except Exception as e:
        return f"检查失败: {str(e)}"


def _normalize_hot_concept_date(date_value):
    """统一将日期转换为 YYYY-MM-DD 字符串。"""
    if isinstance(date_value, str):
        if len(date_value) == 8 and date_value.isdigit():
            return datetime.strptime(date_value, '%Y%m%d').strftime('%Y-%m-%d')
        return pd.Timestamp(date_value).strftime('%Y-%m-%d')
    if isinstance(date_value, dt.datetime):
        return date_value.strftime('%Y-%m-%d')
    if isinstance(date_value, dt.date):
        return date_value.strftime('%Y-%m-%d')
    return pd.Timestamp(date_value).strftime('%Y-%m-%d')


def _trim_cache_dict(cache_obj, max_items):
    """控制缓存大小，避免无限增长。"""
    if not isinstance(cache_obj, dict) or max_items <= 0 or len(cache_obj) <= max_items:
        return
    for cache_key in sorted(cache_obj.keys())[:-max_items]:
        cache_obj.pop(cache_key, None)


def _normalize_cache_fields(fields):
    """将字段参数转换为可哈希元组。"""
    if isinstance(fields, str):
        return (fields,)
    if isinstance(fields, (list, tuple, set)):
        return tuple(fields)
    return tuple([fields])


def _get_attribute_history_cached(security, count, unit, fields, cache_date, skip_paused=True, df=True):
    """按交易日缓存 attribute_history 结果，减少同日重复取数。"""
    if not hasattr(g, 'attribute_history_cache'):
        g.attribute_history_cache = {}

    cache_date_str = _normalize_hot_concept_date(cache_date)
    fields_key = _normalize_cache_fields(fields)
    cache_key = (cache_date_str, security, count, unit, fields_key, bool(skip_paused), bool(df))

    if cache_key in g.attribute_history_cache:
        return g.attribute_history_cache[cache_key]

    hist_data = attribute_history(
        security,
        count,
        unit,
        list(fields_key),
        skip_paused=skip_paused,
        df=df
    )
    g.attribute_history_cache[cache_key] = hist_data
    _trim_cache_dict(g.attribute_history_cache, getattr(g, 'cache_max_days', 5) * 200)
    return hist_data


def _get_valuation_cached(stock, trade_date, fields):
    """按股票+交易日缓存估值数据。"""
    if not hasattr(g, 'valuation_cache'):
        g.valuation_cache = {}

    trade_date_str = _normalize_hot_concept_date(trade_date)
    fields_key = _normalize_cache_fields(fields)
    cache_key = (trade_date_str, stock, fields_key)

    if cache_key in g.valuation_cache:
        return g.valuation_cache[cache_key]

    valuation_df = get_valuation(
        stock,
        start_date=trade_date_str,
        end_date=trade_date_str,
        fields=list(fields_key)
    )
    g.valuation_cache[cache_key] = valuation_df
    _trim_cache_dict(g.valuation_cache, getattr(g, 'cache_max_days', 5) * 200)
    return valuation_df


def _get_call_auction_cached(stock, trade_date, fields=('time', 'volume', 'current')):
    """按股票+交易日缓存集合竞价数据。"""
    if not hasattr(g, 'call_auction_cache'):
        g.call_auction_cache = {}

    trade_date_str = _normalize_hot_concept_date(trade_date)
    fields_key = _normalize_cache_fields(fields)
    cache_key = (trade_date_str, stock, fields_key)

    if cache_key in g.call_auction_cache:
        return g.call_auction_cache[cache_key]

    auction_df = get_call_auction(
        stock,
        start_date=trade_date_str,
        end_date=trade_date_str,
        fields=list(fields_key)
    )
    g.call_auction_cache[cache_key] = auction_df
    _trim_cache_dict(g.call_auction_cache, getattr(g, 'cache_max_days', 5) * 200)
    return auction_df


def _get_hot_concept_excluded_names():
    """过滤泛概念，避免噪声概念占据热度榜。"""
    return {'转融券标的', '融资融券', '深股通', '沪股通'}


def _get_hot_concept_candidate_pool(trade_date):
    """
    获取指定交易日可用于热门概念评估的股票池。
    仅保留主板、非次新、非ST/退市名称股票。
    """
    trade_date_str = _normalize_hot_concept_date(trade_date)

    if not hasattr(g, 'hot_concept_stock_pool_cache'):
        g.hot_concept_stock_pool_cache = {}

    if trade_date_str in g.hot_concept_stock_pool_cache:
        return g.hot_concept_stock_pool_cache[trade_date_str]

    securities = get_all_securities('stock', date=trade_date_str)
    if securities is None or securities.empty:
        g.hot_concept_stock_pool_cache[trade_date_str] = set()
        return set()

    candidate_list = filter_kcbj_stock(list(securities.index))

    if 'start_date' in securities.columns:
        cutoff_date = pd.Timestamp(trade_date_str).date() - dt.timedelta(days=50)
        candidate_list = [
            stock for stock in candidate_list
            if pd.Timestamp(securities.loc[stock, 'start_date']).date() <= cutoff_date
        ]
    else:
        candidate_list = filter_new_stock(candidate_list, trade_date_str)

    if 'display_name' in securities.columns:
        name_map = securities['display_name'].to_dict()
        candidate_list = [
            stock for stock in candidate_list
            if 'ST' not in str(name_map.get(stock, '')) and '退' not in str(name_map.get(stock, ''))
        ]

    candidate_set = set(candidate_list)
    g.hot_concept_stock_pool_cache[trade_date_str] = candidate_set
    _trim_cache_dict(g.hot_concept_stock_pool_cache, getattr(g, 'cache_max_days', 5))
    return candidate_set


def _count_continuous_plate_num(limit_up_stocks, trade_date, watch_days=20):
    """统计概念内当日涨停股中，2连板及以上的股票数量。"""
    if not limit_up_stocks:
        return 0

    try:
        price_df = get_price(
            limit_up_stocks,
            end_date=trade_date,
            frequency='daily',
            fields=['close', 'high_limit'],
            count=watch_days,
            panel=False,
            fill_paused=False,
            skip_paused=False
        )
    except Exception as e:
        log.warning(f"获取连板数据失败: {str(e)}")
        return 0

    if price_df is None or price_df.empty or 'code' not in price_df.columns:
        return 0

    if 'time' in price_df.columns:
        price_df = price_df.sort_values(['code', 'time'])

    continuous_num = 0
    for stock, stock_df in price_df.groupby('code'):
        streak = 0
        for _, row in stock_df.iloc[::-1].iterrows():
            close_price = row.get('close')
            high_limit = row.get('high_limit')
            if pd.isna(close_price) or pd.isna(high_limit):
                break
            if abs(close_price - high_limit) <= max(0.01, abs(high_limit) * 0.001):
                streak += 1
            else:
                break
        if streak >= 2:
            continuous_num += 1

    return continuous_num


def _get_limit_up_streak_map(stock_list, trade_date, watch_days=20):
    """批量计算股票截至指定日期的连续涨停天数。"""
    streak_map = {}
    if not stock_list:
        return streak_map

    try:
        price_df = get_price(
            stock_list,
            end_date=trade_date,
            frequency='daily',
            fields=['close', 'high_limit'],
            count=watch_days,
            panel=False,
            fill_paused=False,
            skip_paused=False
        )
    except Exception as e:
        log.warning(f"批量获取连板数据失败: {str(e)}")
        return streak_map

    if price_df is None or price_df.empty or 'code' not in price_df.columns:
        return streak_map

    if 'time' in price_df.columns:
        price_df = price_df.sort_values(['code', 'time'])

    for stock, stock_df in price_df.groupby('code'):
        streak = 0
        for _, row in stock_df.iloc[::-1].iterrows():
            close_price = row.get('close')
            high_limit = row.get('high_limit')
            if pd.isna(close_price) or pd.isna(high_limit):
                break
            if abs(close_price - high_limit) <= max(0.01, abs(high_limit) * 0.001):
                streak += 1
            else:
                break
        streak_map[stock] = streak

    return streak_map


def _get_recent_pct_change_map(stock_list, trade_date):
    """批量获取股票最近一个交易日涨跌幅映射。"""
    pct_change_map = {}
    if not stock_list:
        return pct_change_map

    try:
        price_df = get_price(
            stock_list,
            end_date=trade_date,
            frequency='daily',
            fields=['close'],
            count=2,
            panel=False,
            fill_paused=False,
            skip_paused=False
        )
    except Exception as e:
        log.warning(f"批量获取涨跌幅数据失败: {str(e)}")
        return pct_change_map

    if price_df is None or price_df.empty or 'code' not in price_df.columns:
        return pct_change_map

    if 'time' in price_df.columns:
        price_df = price_df.sort_values(['code', 'time'])

    for stock, stock_df in price_df.groupby('code'):
        closes = stock_df['close'].dropna().values
        if len(closes) >= 2 and closes[-2] not in (0, None):
            pct_change_map[stock] = round((closes[-1] / closes[-2] - 1) * 100, 2)
        else:
            pct_change_map[stock] = 0.0

    return pct_change_map


def _get_stock_concepts_fast(stock, trade_date):
    """缓存股票概念信息，避免在回测中重复读取。"""
    trade_date_str = _normalize_hot_concept_date(trade_date)

    if not hasattr(g, 'stock_concepts_cache'):
        g.stock_concepts_cache = {}

    if trade_date_str not in g.stock_concepts_cache:
        g.stock_concepts_cache[trade_date_str] = {}

    if stock in g.stock_concepts_cache[trade_date_str]:
        return g.stock_concepts_cache[trade_date_str][stock]

    concept_list = []
    security_info = None

    try:
        security_info = get_security_info(stock, trade_date_str)
    except Exception:
        try:
            security_info = get_security_info(stock)
        except Exception:
            security_info = None

    raw_concepts = getattr(security_info, 'concepts', []) if security_info is not None else []
    for concept in raw_concepts or []:
        if not isinstance(concept, dict):
            continue

        concept_code = concept.get('code') or concept.get('concept_code') or concept.get('id')
        concept_name = concept.get('name') or concept.get('concept_name')
        if not concept_code or not concept_name:
            continue

        concept_list.append({
            'code': str(concept_code),
            'name': str(concept_name)
        })

    g.stock_concepts_cache[trade_date_str][stock] = concept_list
    _trim_cache_dict(g.stock_concepts_cache, getattr(g, 'cache_max_days', 5))
    return concept_list


def _build_mainline_score_map(all_concepts):
    """将热门概念列表预展开为股票 -> 命中概念集合，供主线分直接读取。"""
    stock_concept_map = {}
    for concept in all_concepts:
        concept_code = concept.get('code') or concept.get('name')
        concept_name = concept.get('name', concept_code)
        for stock in concept.get('stock_list', []):
            if stock not in stock_concept_map:
                stock_concept_map[stock] = {}
            stock_concept_map[stock][concept_code] = concept_name
    return stock_concept_map


def _calculate_jq_hot_concept_for_date(concept_code, concept_name, trade_date, candidate_pool):
    """基于聚宽概念成分股和行情数据，计算单日概念热度。"""
    try:
        concept_stocks = get_concept_stocks(concept_code, date=trade_date)
    except Exception as e:
        log.debug(f"{trade_date} 获取概念 {concept_name}({concept_code}) 成分股失败: {str(e)}")
        return None

    if not concept_stocks:
        return None

    filtered_stocks = [stock for stock in concept_stocks if stock in candidate_pool]
    if not filtered_stocks:
        return None

    try:
        price_df = get_price(
            filtered_stocks,
            end_date=trade_date,
            frequency='daily',
            fields=['close', 'high_limit'],
            count=2,
            panel=False,
            fill_paused=False,
            skip_paused=False
        )
    except Exception as e:
        log.debug(f"{trade_date} 获取概念 {concept_name}({concept_code}) 行情失败: {str(e)}")
        return None

    if price_df is None or price_df.empty or 'code' not in price_df.columns:
        return None

    if 'time' in price_df.columns:
        price_df = price_df.sort_values(['code', 'time'])

    valid_stocks = []
    limit_up_stocks = []
    pct_changes = []

    for stock, stock_df in price_df.groupby('code'):
        stock_df = stock_df.dropna(subset=['close', 'high_limit'])
        if stock_df.empty:
            continue

        latest_row = stock_df.iloc[-1]
        latest_close = latest_row['close']
        latest_high_limit = latest_row['high_limit']
        if pd.isna(latest_close) or pd.isna(latest_high_limit):
            continue

        valid_stocks.append(stock)

        if abs(latest_close - latest_high_limit) <= max(0.01, abs(latest_high_limit) * 0.001):
            limit_up_stocks.append(stock)

        if len(stock_df) >= 2:
            prev_close = stock_df.iloc[-2]['close']
            if pd.notna(prev_close) and prev_close not in (0, None):
                pct_changes.append((latest_close / prev_close - 1) * 100)

    if not valid_stocks:
        return None

    continuous_plate_num = _count_continuous_plate_num(limit_up_stocks, trade_date)
    change_value = round(sum(pct_changes) / len(pct_changes), 2) if pct_changes else 0.0
    heat_score = round(len(limit_up_stocks) * 2 + continuous_plate_num * 3 + max(0, change_value), 2)

    return {
        'code': str(concept_code),
        'name': str(concept_name),
        'stock_list': sorted(valid_stocks),
        'limit_up_num': len(limit_up_stocks),
        'continuous_plate_num': continuous_plate_num,
        'change': change_value,
        'heat_score': heat_score,
        'trade_date': trade_date
    }


def _build_jq_hot_concepts_for_trade_date(trade_date):
    """使用涨停股反推候选概念，再展开少量候选概念，显著降低回测耗时。"""
    trade_date_str = _normalize_hot_concept_date(trade_date)
    candidate_pool = _get_hot_concept_candidate_pool(trade_date_str)
    if not candidate_pool:
        return []

    try:
        limit_up_stocks = get_hl_stock(list(candidate_pool), trade_date_str)
    except Exception as e:
        log.error(f"{trade_date_str} 获取涨停股失败: {str(e)}")
        return []

    if not limit_up_stocks:
        return []

    pct_change_map = _get_recent_pct_change_map(limit_up_stocks, trade_date_str)
    streak_map = _get_limit_up_streak_map(limit_up_stocks, trade_date_str, watch_days=20)
    excluded_names = _get_hot_concept_excluded_names()

    concept_stats = {}
    for stock in limit_up_stocks:
        stock_concepts = _get_stock_concepts_fast(stock, trade_date_str)
        if not stock_concepts:
            continue

        for concept in stock_concepts:
            concept_code = concept.get('code')
            concept_name = concept.get('name')
            if not concept_code or not concept_name or concept_name in excluded_names:
                continue

            if concept_code not in concept_stats:
                concept_stats[concept_code] = {
                    'code': concept_code,
                    'name': concept_name,
                    'limit_up_stock_set': set(),
                    'change_values': [],
                    'continuous_plate_num': 0
                }

            if stock not in concept_stats[concept_code]['limit_up_stock_set']:
                concept_stats[concept_code]['limit_up_stock_set'].add(stock)
                concept_stats[concept_code]['change_values'].append(pct_change_map.get(stock, 0.0))
                if streak_map.get(stock, 0) >= 2:
                    concept_stats[concept_code]['continuous_plate_num'] += 1

    if not concept_stats:
        return []

    ranked_candidates = []
    for concept_code, stats in concept_stats.items():
        limit_up_num = len(stats['limit_up_stock_set'])
        if limit_up_num <= 0:
            continue

        change_value = round(
            sum(stats['change_values']) / len(stats['change_values']), 2
        ) if stats['change_values'] else 0.0
        heat_score = round(
            limit_up_num * 2 + stats['continuous_plate_num'] * 3 + max(0, change_value), 2
        )

        ranked_candidates.append({
            'code': stats['code'],
            'name': stats['name'],
            'limit_up_num': limit_up_num,
            'continuous_plate_num': stats['continuous_plate_num'],
            'change': change_value,
            'heat_score': heat_score,
            'trade_date': trade_date_str,
            'limit_up_stocks': sorted(stats['limit_up_stock_set'])
        })

    if not ranked_candidates:
        return []

    ranked_candidates.sort(
        key=lambda x: (
            x.get('heat_score', 0),
            x.get('limit_up_num', 0),
            x.get('continuous_plate_num', 0),
            x.get('change', 0)
        ),
        reverse=True
    )

    expanded_count = max(getattr(g, 'concept_num', 8) * 3, 20)
    hot_concepts = []
    for candidate in ranked_candidates[:expanded_count]:
        try:
            concept_stocks = get_concept_stocks(candidate['code'], date=trade_date_str)
        except Exception:
            concept_stocks = []

        filtered_stocks = [stock for stock in concept_stocks if stock in candidate_pool] if concept_stocks else []
        if not filtered_stocks:
            filtered_stocks = candidate['limit_up_stocks']

        hot_concepts.append({
            'code': candidate['code'],
            'name': candidate['name'],
            'stock_list': sorted(filtered_stocks),
            'limit_up_num': candidate['limit_up_num'],
            'continuous_plate_num': candidate['continuous_plate_num'],
            'change': candidate['change'],
            'heat_score': candidate['heat_score'],
            'trade_date': trade_date_str
        })

    hot_concepts.sort(
        key=lambda x: (
            x.get('heat_score', 0),
            x.get('limit_up_num', 0),
            x.get('continuous_plate_num', 0),
            x.get('change', 0)
        ),
        reverse=True
    )
    return hot_concepts[:getattr(g, 'concept_num', 8)]


def calculate_mainline_score_optimized(stock, context):
    """
    优化的主线评分计算函数，按个股命中的热门概念数量计分。
    """
    try:
        end_date_str = _normalize_hot_concept_date(context.previous_date)
        days = getattr(g, 'cache_max_days', 5)
        cache_key = f"{end_date_str}_{days}"

        if not hasattr(g, 'mainline_score_map_cache'):
            g.mainline_score_map_cache = {}

        if cache_key not in g.mainline_score_map_cache:
            hot_concepts_result = get_all_hot_concepts_optimized(context, days=days)
            all_concepts = hot_concepts_result.get('all_concepts', [])
            g.mainline_score_map_cache[cache_key] = _build_mainline_score_map(all_concepts)
            _trim_cache_dict(g.mainline_score_map_cache, getattr(g, 'cache_max_days', 5))
        else:
            hot_concepts_result = None
            all_concepts = []

        log.debug("==== 主线评分计算 - 聚宽热门概念缓存检查 ====")
        if hot_concepts_result is not None:
            log.debug(f"热门概念数量: {len(all_concepts)}")
            log.debug(f"部分热门概念示例: {[c.get('name', '') for c in all_concepts[:10]]}")

        matched_concepts = g.mainline_score_map_cache.get(cache_key, {}).get(stock, {})

        match_count = len(matched_concepts)
        mainline_score = match_count * 2 if match_count > 0 else 0

        if match_count > 0:
            log.debug(
                f"股票 {stock} 命中聚宽热门概念: {list(matched_concepts.values())}, "
                f"匹配数量: {match_count}, 主线评分: {mainline_score}"
            )
        else:
            log.debug(f"股票 {stock} 未命中聚宽热门概念，主线评分: {mainline_score}")

        log.debug("----------------------------------------")
        return mainline_score

    except Exception as e:
        log.error(f"计算主线评分时出错: {str(e)}")
        import traceback
        log.error(traceback.format_exc())
        return 0


def get_all_hot_concepts_optimized(context, days=5):
    """
    获取最近N个交易日的聚宽热门概念列表，支持按日期缓存和去重汇总。
    """
    try:
        end_date = context.previous_date
        log.info(f"开始获取最近{days}个交易日的聚宽热门概念，截止日期: {end_date.strftime('%Y-%m-%d')}")

        if not hasattr(g, 'hot_concepts_data_cache'):
            g.hot_concepts_data_cache = {}
            log.info("初始化热门概念缓存 g.hot_concepts_data_cache")

        if not hasattr(g, 'hot_concepts_summary_cache'):
            g.hot_concepts_summary_cache = {}

        summary_cache_key = f"{_normalize_hot_concept_date(end_date)}_{days}"
        if summary_cache_key in g.hot_concepts_summary_cache:
            return g.hot_concepts_summary_cache[summary_cache_key]

        try:
            trade_days = get_trade_days(end_date=end_date, count=days)
            if trade_days is None or len(trade_days) == 0:
                log.warning("未获取到有效交易日")
                return {
                    'all_concepts': [],
                    'by_date': {},
                    'summary': {'total_unique_concepts': 0, 'total_dates': 0, 'date_range': 'N/A'}
                }
            trade_days_str = [pd.Timestamp(td).strftime('%Y-%m-%d') for td in trade_days]
        except Exception as e:
            log.error(f"获取交易日失败: {str(e)}")
            import traceback
            log.error(f"错误详情: {traceback.format_exc()}")
            return {
                'all_concepts': [],
                'by_date': {},
                'summary': {'total_unique_concepts': 0, 'total_dates': 0, 'date_range': 'N/A'}
            }

        all_concepts_dict = {}
        concepts_by_date = {}

        for trade_day_str in trade_days_str:
            daily_concepts = _get_hot_concepts_for_date(trade_day_str, context)
            if not isinstance(daily_concepts, list) or not daily_concepts:
                log.warning(f"⚠ {trade_day_str} 未获取到聚宽热门概念")
                continue

            concepts_by_date[trade_day_str] = daily_concepts

            for concept in daily_concepts:
                if not isinstance(concept, dict):
                    continue

                concept_code = concept.get('code')
                if not concept_code:
                    continue

                concept_name = concept.get('name', '')
                concept_stocks = concept.get('stock_list', [])

                if concept_code not in all_concepts_dict:
                    all_concepts_dict[concept_code] = {
                        'code': concept_code,
                        'name': concept_name,
                        'first_seen': trade_day_str,
                        'last_seen': trade_day_str,
                        'appearances': 1,
                        'dates': [trade_day_str],
                        'stock_list': list(concept_stocks)
                    }
                else:
                    all_concepts_dict[concept_code]['last_seen'] = trade_day_str
                    all_concepts_dict[concept_code]['appearances'] += 1
                    all_concepts_dict[concept_code]['dates'].append(trade_day_str)
                    merged_stock_set = set(all_concepts_dict[concept_code].get('stock_list', []))
                    merged_stock_set.update(concept_stocks)
                    all_concepts_dict[concept_code]['stock_list'] = sorted(merged_stock_set)

            log.info(f"✓ {trade_day_str} 获取到 {len(daily_concepts)} 个聚宽热门概念")

        all_concepts_list = list(all_concepts_dict.values())
        all_concepts_list.sort(
            key=lambda x: (x.get('appearances', 0), x.get('last_seen', '')),
            reverse=True
        )

        result = {
            'all_concepts': all_concepts_list,
            'by_date': concepts_by_date,
            'summary': {
                'total_unique_concepts': len(all_concepts_list),
                'total_dates': len(concepts_by_date),
                'date_range': f"{trade_days_str[0]} 至 {trade_days_str[-1]}" if trade_days_str else 'N/A',
                'trade_days': trade_days_str
            }
        }

        log.info("=" * 60)
        log.info(f"聚宽热门概念统计（最近{days}个交易日）")
        log.info(f"  日期范围: {result['summary']['date_range']}")
        log.info(f"  总计唯一概念数: {result['summary']['total_unique_concepts']}")
        log.info(f"  有效交易日数: {result['summary']['total_dates']}")

        high_freq_concepts = [c for c in all_concepts_list if c.get('appearances', 0) >= 3]
        if high_freq_concepts:
            log.info(f"  高频概念（出现≥3次）: {len(high_freq_concepts)}个")
            for concept in high_freq_concepts[:10]:
                log.info(
                    f"    - {concept['name']}({concept['code']}): "
                    f"出现{concept['appearances']}次, 日期{concept['dates']}"
                )

        if concepts_by_date:
            log.info("  每日概念数量:")
            for trade_day_str in sorted(concepts_by_date.keys(), reverse=True):
                concepts = concepts_by_date[trade_day_str]
                concept_names = [c.get('name', '') for c in concepts if isinstance(c, dict)]
                log.info(f"    {trade_day_str}: {len(concepts)}个 - {', '.join(concept_names)}")

        log.info("=" * 60)
        g.hot_concepts_summary_cache[summary_cache_key] = result
        _trim_cache_dict(g.hot_concepts_summary_cache, getattr(g, 'cache_max_days', 5))
        return result

    except Exception as e:
        log.error(f"获取热门概念时出错: {str(e)}")
        import traceback
        log.error(f"错误详情: {traceback.format_exc()}")
        return {
            'all_concepts': [],
            'by_date': {},
            'summary': {'total_unique_concepts': 0, 'total_dates': 0, 'date_range': 'N/A'}
        }


def _get_hot_concepts_for_date(date_str, context=None):
    """
    获取指定日期的聚宽热门概念列表，缓存值统一为 list[dict]。
    """
    trade_date_str = _normalize_hot_concept_date(date_str)

    try:
        if not hasattr(g, 'hot_concepts_data_cache'):
            g.hot_concepts_data_cache = {}

        if trade_date_str in g.hot_concepts_data_cache:
            cache_data = g.hot_concepts_data_cache[trade_date_str]
            if isinstance(cache_data, list):
                return cache_data
            if isinstance(cache_data, pd.DataFrame):
                cache_data = cache_data.to_dict('records')
                g.hot_concepts_data_cache[trade_date_str] = cache_data
                return cache_data

        hot_concepts = _build_jq_hot_concepts_for_trade_date(trade_date_str)
        g.hot_concepts_data_cache[trade_date_str] = hot_concepts
        _trim_cache_dict(g.hot_concepts_data_cache, getattr(g, 'cache_max_days', 5))

        if hot_concepts:
            total_stocks = sum(len(c.get('stock_list', [])) for c in hot_concepts)
            log.info(
                f"  ✓ {trade_date_str} 计算并缓存 {len(hot_concepts)} 个聚宽热门概念 "
                f"(共{total_stocks}只成分股)"
            )
        else:
            log.warning(f"  ⚠ {trade_date_str} 未筛选出有效聚宽热门概念")

        return hot_concepts

    except Exception as e:
        log.error(f"获取 {trade_date_str} 聚宽热门概念时出错: {str(e)}")
        import traceback
        log.error(f"错误详情: {traceback.format_exc()}")
        return []


def fetch_and_map_hot_concepts(date_str, concept_mapper=None):
    """
    兼容旧调用入口：改为直接返回聚宽热门概念DataFrame，不再依赖外部HTTP接口。
    """
    hot_concepts = _build_jq_hot_concepts_for_trade_date(date_str)
    if not hot_concepts:
        return pd.DataFrame()

    result_df = pd.DataFrame(hot_concepts)
    result_df['concept_code'] = result_df['code']
    result_df['concept_name'] = result_df['name']
    result_df['jq_concept_code'] = result_df['code']
    result_df['jq_concept_name'] = result_df['name']
    result_df['stock_count'] = result_df['stock_list'].apply(len)
    return result_df

def convert_to_jq_code(stock_code):
    """
    将股票代码转换为聚宽格式

    参数:
        stock_code: 原始股票代码

    返回:
        str: 聚宽格式的股票代码
    """
    try:
        # 如果已经是聚宽格式，直接返回
        if '.' in stock_code:
            return stock_code

        # 根据股票代码前缀判断交易所
        if stock_code.startswith('6'):
            return stock_code + '.XSHG'  # 上海证券交易所
        elif stock_code.startswith('0') or stock_code.startswith('3'):
            return stock_code + '.XSHE'  # 深圳证券交易所
        else:
            log.warning(f"无法识别的股票代码格式: {stock_code}")
            return None

    except Exception as e:
        log.error(f"转换股票代码时出错: {str(e)}, 股票代码: {stock_code}")
        return None    

# 旧版同花顺概念映射器（已停用，仅保留兼容入口）
class ConceptMapper:
    """旧版同花顺概念映射器，当前热门概念链路已不再使用。"""

    def __init__(self, logger=None):
        # 定义相似度阈值作为类的属性
        self.SIMILARITY_THRESHOLD = 0.6
        self.logger = logger or logging.getLogger("ths_hot_concept")
        try:
            self.jq_concepts_df = get_concepts()
            self.jq_concepts = [
                {
                    'code': idx,
                    'name': row['name']
                }
                for idx, row in self.jq_concepts_df.iterrows()
            ]
            self.jq_names = [item['name'] for item in self.jq_concepts]
            self.mapping_cache = {}
            self.logger.info(f"成功加载聚宽概念数据，共 {len(self.jq_concepts)} 个概念")
        except Exception as e:
            self.logger.error(f"加载聚宽概念数据出错: {str(e)}")
            # 如果无法获取聚宽概念，使用一些常见的概念作为备用
            self.jq_concepts = [
                {"code": "GN036", "name": "新能源汽车"},
                {"code": "GN035", "name": "半导体"},
                {"code": "GN033", "name": "人工智能"},
                {"code": "GN028", "name": "5G"},
                {"code": "GN022", "name": "医疗器械"},
                {"code": "GN015", "name": "光伏"},
                {"code": "GN014", "name": "锂电池"},
                {"code": "GN012", "name": "芯片"},
                {"code": "GN010", "name": "云计算"},
                {"code": "GN009", "name": "大数据"},
                {"code": "GN008", "name": "物联网"},
                {"code": "GN007", "name": "虚拟现实"},
                {"code": "GN006", "name": "智能电网"},
                {"code": "GN005", "name": "智能家居"},
                {"code": "GN004", "name": "新能源"},
                {"code": "GN003", "name": "节能环保"},
                {"code": "GN002", "name": "生物医药"},
                {"code": "GN001", "name": "军工"}
            ]
            self.jq_names = [item['name'] for item in self.jq_concepts]
            self.mapping_cache = {}
            self.logger.info(f"使用备用概念数据，共 {len(self.jq_concepts)} 个概念")

    def clean_concept_name(self, name):
        """清理概念名称，去除常见后缀"""
        if not name:
            return ""
        suffixes = ['概念', '板块', '指数', '主题', '产业', '行业', '题材']
        cleaned = name
        for suffix in suffixes:
            cleaned = cleaned.replace(suffix, '')
        return cleaned.strip()

    def similarity_score(self, str1, str2):
        """计算两个字符串的相似度"""
        if not str1 or not str2:
            return 0
        return SequenceMatcher(None, str1, str2).ratio()

    def find_best_match(self, ths_concept_name):
        """
        找到最佳匹配的聚宽概念

        参数:
            ths_concept_name: 同花顺概念名称

        返回:
            (聚宽概念名称, 聚宽概念代码) 元组
        """
        # 检查输入
        if not ths_concept_name:
            return (None, None)

        # 检查缓存
        if ths_concept_name in self.mapping_cache:
            return self.mapping_cache[ths_concept_name]

        # 清理概念名称
        ths_clean = self.clean_concept_name(ths_concept_name)
        if not ths_clean:
            return (None, None)

        best_score = 0
        best_match = None

        # 先尝试精确匹配
        for item in self.jq_concepts:
            jq_name = item['name']

            # 精确匹配原始名称
            if ths_concept_name == jq_name:
                self.mapping_cache[ths_concept_name] = (item['name'], item['code'])
                self.logger.info(f"精确匹配: {ths_concept_name} -> {item['name']}")
                return (item['name'], item['code'])

            # 精确匹配清理后的名称
            jq_clean = self.clean_concept_name(jq_name)
            if ths_clean == jq_clean:
                self.mapping_cache[ths_concept_name] = (item['name'], item['code'])
                self.logger.info(f"清理后精确匹配: {ths_concept_name}({ths_clean}) -> {item['name']}({jq_clean})")
                return (item['name'], item['code'])

        # 再尝试模糊匹配
        for item in self.jq_concepts:
            jq_name = item['name']
            jq_clean = self.clean_concept_name(jq_name)

            # 计算基础相似度
            score = self.similarity_score(ths_clean, jq_clean)

            # 检查包含关系，提高相似度
            if ths_clean in jq_clean or jq_clean in ths_clean:
                score += 0.2

            # 更新最佳匹配
            if score > best_score:
                best_score = score
                best_match = (item['name'], item['code'])

        # 如果相似度达到阈值，认为是匹配的
        if best_match and best_score >= self.SIMILARITY_THRESHOLD:  # 使用类的属性
            self.logger.info(f"模糊匹配: {ths_concept_name} -> {best_match[0]} (相似度: {best_score:.2f})")
            self.mapping_cache[ths_concept_name] = best_match
            return best_match

        self.logger.warning(f"未找到匹配: {ths_concept_name} (最佳相似度: {best_score:.2f})")
        self.mapping_cache[ths_concept_name] = (None, None)
        return (None, None)


# ============================================================================
# 3. 股票筛选主函数（修复版）
# ============================================================================
def filter_stocks_by_score_optimized(stocks, context, min_score=14, max_stocks=100, pattern_lists=None):
    """
    优化后的根据评分筛选股票函数（统一使用calculate_main_force_flow_score计算主力资金因子）
    同时将评分结果缓存到全局变量中

    参数:
        stocks: 候选股票列表
        context: 上下文对象
        min_score: 最低评分要求，默认14分
        max_stocks: 最大处理股票数量，默认100只
    """
    try:
        log.info("=" * 60)
        log.info(f"开始股票评分筛选，候选股票: {len(stocks)} 只，最低分数: {min_score}")
        log.info("=" * 60)

        # Use same-day pattern lists. Falling back to globals is only for backward compatibility.
        pattern_lists = pattern_lists or getattr(g, 'current_pattern_lists', {}) or build_pattern_lists(
            getattr(g, 'lblt_stocks', []),
            getattr(g, 'gk_stocks', []),
            getattr(g, 'rzq_stocks', []),
            getattr(g, 'dk_stocks', []),
            getattr(g, 'fxsbdk_stocks', [])
        )
        lblt_stocks = pattern_lists.get('lb', [])
        gk_stocks = pattern_lists.get('yje', [])
        rzq_stocks = pattern_lists.get('rzq', [])
        dk_stocks = pattern_lists.get('dk', [])
        fxsbdk_stocks = pattern_lists.get('fxsbdk', [])
        
        # 清空之前的评分缓存
        g.score_cache = {}

        qualified_stocks = []  # 只存储股票代码字符串
        score_records = []
        processing_stats = {
            'total_stocks': len(stocks),
            'processed_stocks': 0,
            'qualified_stocks': 0,
            'failed_stocks': 0,
            'high_score_stocks': 0,
            'medium_score_stocks': 0,
            'low_score_stocks': 0,
            'zero_score_stocks': 0,
            'processing_time': 0,
            'cache_status': 'unknown',
            'filtered_by_mainline': 0,  # 记录因主线分为0被过滤的连板龙头股票数量
            'filtered_by_money_flow': 0,  # 记录因主力资金为0被过滤的连板龙头股票数量
            'filtered_by_volume_ratio': 0,  # 记录因量比不符合要求被过滤的股票数量
            'filtered_by_volume_ratio_weak_to_strong': 0,  # 弱转强模式量比过滤
            'filtered_by_volume_ratio_lblt': 0,  # 连板龙头模式量比过滤
            'filtered_by_volume_ratio_first_to_second': 0  # 一进二模式量比过滤
        }

        start_time = time.time()

        # 限制处理数量
        limited_stocks = stocks[:max_stocks] if len(stocks) > max_stocks else stocks
        if len(stocks) > max_stocks:
            log.info(f"⚠️  股票数量过多，限制处理前 {max_stocks} 只股票")

        # 检查缓存状态
        cache_status = check_cache_status()
        processing_stats['cache_status'] = cache_status
        log.info(f"热门概念缓存状态: {cache_status}")

        # 批量获取股票基本信息
        current_data = get_current_data()

        # 预先获取所有股票的资金流向数据
        money_flow_map = get_money_flow_map(context, limited_stocks)

        for i, stock in enumerate(limited_stocks):
            try:
                # 进度显示
                if i % 20 == 0 and i > 0:
                    elapsed_time = time.time() - start_time
                    avg_time_per_stock = elapsed_time / i
                    remaining_time = avg_time_per_stock * (len(limited_stocks) - i)
                    log.info(f"📊 进度: {i}/{len(limited_stocks)} ({i / len(limited_stocks) * 100:.1f}%), "
                             f"预计剩余时间: {remaining_time:.1f}秒")

                # 判断股票模式类型
                is_lblt_stock = stock in lblt_stocks
                is_first_to_second_stock = stock in gk_stocks
                is_weak_to_strong_stock = stock in rzq_stocks
                is_dk_stock = stock in dk_stocks
                is_fxsbdk_stock = stock in fxsbdk_stocks
                
                # 确定股票模式
                if is_lblt_stock:
                    stock_mode = "连板龙头"
                elif is_first_to_second_stock:
                    stock_mode = "一进二"
                elif is_weak_to_strong_stock:
                    stock_mode = "弱转强"
                elif is_dk_stock:
                    stock_mode = "低开"
                elif is_fxsbdk_stock:
                    stock_mode = "放巡散步低开"
                else:
                    stock_mode = "未分类"  # 默认为未分类模式

                try:
                    if stock in current_data:
                        stock_name = current_data[stock].name
                    else:
                        security_info = get_security_info(stock)
                        stock_name = security_info.display_name if security_info else "未知"
                except:
                    stock_name = "未知"

                # 1. 获取基础评分结果（包含全部6个因子，主力资金因子已统一计算）
                score_result = calculate_buy_score_optimized(stock, context, money_flow_map)
                processing_stats['processed_stocks'] += 1

                if not score_result:
                    processing_stats['failed_stocks'] += 1
                    continue

                # 2. 提取各因子得分（主力资金因子使用统一计算结果）
                factor1 = score_result.get('factor1_涨停', 0)
                factor2 = score_result.get('factor2_技术', 0)
                factor3 = score_result.get('factor3_放量MA', 0)
                factor4 = score_result.get('factor4_主线', 0)
                factor5 = score_result.get('factor5_情绪', 0)
                factor6 = score_result.get('factor6_主力资金', 0)  # 统一使用calculate_main_force_flow_score结果
                total_score = factor1 + factor2 + factor3 + factor4 + factor5 + factor6

                # 3. 将评分结果缓存到全局变量（包含6个因子）
                g.score_cache[stock] = {
                    'total_score': total_score,
                    'factor1_涨停': factor1,
                    'factor2_技术': factor2,
                    'factor3_放量MA': factor3,
                    'factor4_主线': factor4,
                    'factor5_情绪': factor5,
                    'factor6_主力资金': factor6,  # 统一缓存结果
                    'factors': {
                        'limit_up': factor1,
                        'technical': factor2,
                        'volume_ma': factor3,
                        'mainline': factor4,
                        'sentiment': factor5,
                        'main_force': factor6
                    },
                    'timestamp': context.current_dt,
                    'is_lblt': is_lblt_stock,  # 标记是否为连板龙头
                    'stock_mode': stock_mode    # 记录股票模式
                }

                # 4. 统计评分分布
                if total_score >= 20:
                    processing_stats['high_score_stocks'] += 1
                elif total_score >= 15:
                    processing_stats['medium_score_stocks'] += 1
                elif total_score >= 10:
                    processing_stats['low_score_stocks'] += 1
                else:
                    processing_stats['zero_score_stocks'] += 1

                # 5. 判断是否符合筛选条件
                is_qualified = total_score >= min_score

                # 连板龙头过滤条件：主线分为0或主力资金为0
                filtered_reason = None
                if is_lblt_stock:
                    if factor4 == 0:  # 主线分为0
                        is_qualified = False
                        processing_stats['filtered_by_mainline'] += 1
                        filtered_reason = '连板龙头主线分为0'
                    elif factor6 == 0 and factor1 < 5:  # 主力资金为0,且涨停分小于5
                        is_qualified = False
                        processing_stats['filtered_by_money_flow'] += 1
                        filtered_reason = '连板龙头主力资金为0且涨停分小于5'
                
                if is_first_to_second_stock:
                    if factor4 == 0:  # 主线分为0
                        is_qualified = False
                        processing_stats['filtered_by_mainline'] += 1
                        filtered_reason = '一进二主线分为0'

                # 实现根据不同模式量比过滤范围的条件
                try:
                    # 获取股票的量比数据
                    last_volume, last_2_volume, volume_ratio = get_volume_data(stock, context)
                
                    # 根据不同模式设置量比范围限制
                    if is_lblt_stock:
                        # 连板龙头模式量能比范围：1.184~10.5
                        if volume_ratio < 1.184 or volume_ratio > 10.5:
                            is_qualified = False
                            processing_stats['filtered_by_volume_ratio'] += 1
                            processing_stats['filtered_by_volume_ratio_lblt'] += 1
                            filtered_reason = f'连板龙头模式量比不符({volume_ratio:.2f}不在1.184~10.5范围内)'
                    
                    elif is_weak_to_strong_stock or is_dk_stock or is_fxsbdk_stock:
                        # 弱转强模式个股量能比范围 1.072~3.68
                        if volume_ratio < 1.072 or volume_ratio > 3.68:
                            is_qualified = False
                            processing_stats['filtered_by_volume_ratio'] += 1
                            processing_stats['filtered_by_volume_ratio_weak_to_strong'] += 1
                            filtered_reason = f'弱转强模式量比不符({volume_ratio:.2f}不在1.072~3.68范围内)'
                    
                    else:
                        # 未分类模式，使用最宽松的量比范围 1.072~10.5
                        if volume_ratio < 1.072 or volume_ratio > 10.5:
                            is_qualified = False
                            processing_stats['filtered_by_volume_ratio'] += 1
                            filtered_reason = f'未分类模式量比不符({volume_ratio:.2f}不在1.072~10.5范围内)'
                    
                    # 将量比信息添加到评分缓存中
                    g.score_cache[stock]['volume_ratio'] = volume_ratio
                    
                except Exception as ve:
                    log.warning(f"获取股票 {stock} 的量比数据失败: {str(ve)}")
                
                # 增加总分过滤，一进二:19~37, 弱转强>19
                if is_qualified:
                    # 一进二模式总分范围：20~37分
                    if is_first_to_second_stock and (total_score < 20 or total_score > 37):
                        is_qualified = False
                        filtered_reason = f'一进二模式总分不符({total_score}不在20~37范围内)'
                        log.debug(f"⚠️ 过滤 {stock} ({stock_name}): 一进二模式总分不符({total_score}不在20~37范围内)")
                    
                    # 弱转强模式总分要求：>19分
                    elif (is_weak_to_strong_stock or is_dk_stock or is_fxsbdk_stock) and total_score < 20:
                        is_qualified = False
                        filtered_reason = f'弱转强模式总分不符({total_score}<19)'
                        log.debug(f"⚠️ 过滤 {stock} ({stock_name}): 弱转强模式总分不符({total_score}<19)")

                if is_qualified:
                    qualified_stocks.append(stock)
                    processing_stats['qualified_stocks'] += 1

                # 6. 获取股票名称
                try:
                    if stock in current_data:
                        stock_name = current_data[stock].name
                    else:
                        security_info = get_security_info(stock)
                        stock_name = security_info.display_name if security_info else "未知"
                except:
                    stock_name = "未知"

                # 7. 构建评分记录（包含6个因子）
                record = {
                    '股票代码': stock,
                    '股票名称': stock_name,
                    '总评分': total_score,
                    '是否选中': '✓' if is_qualified else '✗',
                    'factor1_涨停': factor1,
                    'factor2_技术': factor2,
                    'factor3_放量MA': factor3,
                    'factor4_主线': factor4,
                    'factor5_情绪': factor5,
                    'factor6_主力资金': factor6,  # 统一记录结果
                    '是否连板龙头': '✓' if is_lblt_stock else '✗',
                    '被过滤原因': filtered_reason,
                    '量比': g.score_cache[stock].get('volume_ratio', '未知'),  # 添加量比信息到记录中
                    '模式': stock_mode  # 添加模式信息
                }
                score_records.append(record)

                # 8. 输出符合条件股票的详细信息（含6个因子）
                if is_qualified:
                    mode_tag = f"[{stock_mode}]" if stock_mode != "未分类" else ""
                    volume_ratio_info = f"量比:{g.score_cache[stock].get('volume_ratio', '未知'):.2f}" if isinstance(
                        g.score_cache[stock].get('volume_ratio'), (int, float)) else "量比:未知"
                    log.debug(f"✅ {stock} ({stock_name}){mode_tag} - 总分: {total_score} "
                             f"[涨停:{factor1} 技术:{factor2} 放量MA:{factor3} "
                             f"主线:{factor4} 情绪:{factor5} 主力资金:{factor6} {volume_ratio_info}]")
                elif filtered_reason and total_score >= min_score:
                    # 记录因过滤条件而被过滤的高分股票
                    mode_tag = f"[{stock_mode}]" if stock_mode != "未分类" else ""
                    volume_ratio_info = f"量比:{g.score_cache[stock].get('volume_ratio', '未知'):.2f}" if isinstance(
                        g.score_cache[stock].get('volume_ratio'), (int, float)) else "量比:未知"
                    log.debug(f"⚠️ {stock} ({stock_name}){mode_tag} - 总分: {total_score} {filtered_reason} "
                             f"[涨停:{factor1} 技术:{factor2} 放量MA:{factor3} "
                             f"主线:{factor4} 情绪:{factor5} 主力资金:{factor6} {volume_ratio_info}]")

            except Exception as e:
                processing_stats['failed_stocks'] += 1
                log.error(f"处理股票 {stock} 时出错: {str(e)}")
                continue

        # 计算处理时间
        processing_stats['processing_time'] = time.time() - start_time

        # 输出统计信息
        log.info("📈 评分分布统计:")
        log.info(f"  🌟 高分股票(≥20分): {processing_stats['high_score_stocks']} 只")
        log.info(f"  ⭐ 中等股票(15-20分): {processing_stats['medium_score_stocks']} 只")
        log.info(f"  📊 低分股票(10-15分): {processing_stats['low_score_stocks']} 只")
        log.info(f"  ❌ 零分股票(0分): {processing_stats['zero_score_stocks']} 只")

        # 过滤统计
        log.info("  🚫 过滤统计:")
        if processing_stats['filtered_by_mainline'] > 0:
            log.info(f"    - 因主线分为0被过滤: {processing_stats['filtered_by_mainline']} 只")
        if processing_stats['filtered_by_money_flow'] > 0:
            log.info(f"    - 因主力资金为0被过滤: {processing_stats['filtered_by_money_flow']} 只")
        if processing_stats['filtered_by_volume_ratio'] > 0:
            log.info(f"    - 因量比不符被过滤(总计): {processing_stats['filtered_by_volume_ratio']} 只")
            if processing_stats['filtered_by_volume_ratio_lblt'] > 0:
                log.info(f"      - 连板龙头模式量比不符(1.184~10.5): {processing_stats['filtered_by_volume_ratio_lblt']} 只")
            if processing_stats['filtered_by_volume_ratio_first_to_second'] > 0:
                log.info(f"      - 一进二模式量比不符(1.15~6.58): {processing_stats['filtered_by_volume_ratio_first_to_second']} 只")
            if processing_stats['filtered_by_volume_ratio_weak_to_strong'] > 0:
                log.info(f"      - 弱转强模式量比不符(1.072~3.68): {processing_stats['filtered_by_volume_ratio_weak_to_strong']} 只")

        total_filtered = (processing_stats['filtered_by_mainline'] +
                          processing_stats['filtered_by_money_flow'] +
                          processing_stats['filtered_by_volume_ratio'])
        log.info(f"    - 总计被过滤股票: {total_filtered} 只")

        log.info(f"  ⚠️  处理失败: {processing_stats['failed_stocks']} 只")
        log.info(f"  ⏱️  处理时间: {processing_stats['processing_time']:.2f} 秒")

        log.info("=" * 60)
        log.info(f"✅ 股票筛选完成！符合条件股票: {len(qualified_stocks)} 只")
        log.info(f"📦 评分缓存已保存: {len(g.score_cache)} 只股票的评分（含6个因子和量比）")
        log.info("=" * 60)

        # 按总评分降序排序
        score_records_sorted = sorted(score_records, key=lambda x: x['总评分'], reverse=True)
        score_records_limited = score_records_sorted

        # 更新合格股票列表为排序后并限制数量的结果
        qualified_stocks = [record['股票代码'] for record in score_records_limited if record['是否选中'] == '✓']

        # 显示前5只符合条件的股票详情
        if qualified_stocks:
            log.info("🎯 符合条件的股票列表:")
            for i, stock in enumerate(qualified_stocks[:5]):  # 只显示前5只
                matching_record = next((r for r in score_records if r['股票代码'] == stock), None)
                if matching_record:
                    mode_tag = f"[{matching_record['模式']}]" if matching_record['模式'] != "未分类" else ""
                    volume_ratio_info = f"量比:{matching_record['量比']:.2f}" if isinstance(matching_record['量比'],
                                                                                            (int, float)) else "量比:未知"
                    log.info(f"  {i + 1}. {stock} ({matching_record['股票名称']}){mode_tag} - "
                             f"总分: {matching_record['总评分']} "
                             f"[涨停:{matching_record['factor1_涨停']} "
                             f"技术:{matching_record['factor2_技术']} "
                             f"放量MA:{matching_record['factor3_放量MA']} "
                             f"主线:{matching_record['factor4_主线']} "
                             f"情绪:{matching_record['factor5_情绪']} "
                             f"主力资金:{matching_record['factor6_主力资金']} "
                             f"{volume_ratio_info}]")

            if len(qualified_stocks) > 5:
                log.info(f"  ... 共 {len(qualified_stocks)} 只符合条件股票")

        return qualified_stocks

    except Exception as e:
        log.error(f"股票筛选过程出错: {str(e)}")
        import traceback
        log.error(traceback.format_exc())
        return []


def get_money_flow_map(context, qualified_stocks):
    """
    获取合格股票的主力资金流数据并构建映射字典（包含所有日期记录）
    参数:
        context: 上下文对象
        qualified_stocks: 合格股票列表
    返回:
        money_flow_map: 主力资金流映射字典，键为股票代码，值为包含所有日期记录的列表
    """
    money_flow_map = {}
    try:
        if not qualified_stocks:
            log.info("合格股票列表为空，无需获取主力资金数据")
            return money_flow_map

        # 获取最近5个交易日的主力资金数据（保留所有日期，不做数量限制）
        end_date = context.previous_date
        trade_days = get_trade_days(end_date=end_date, count=5)
        log.info(f"~~~日期范围: {trade_days[0]} 至 {end_date}, trade_days:{trade_days}")
        money_flow_df = get_money_flow(qualified_stocks, start_date=trade_days[0], end_date=end_date)
        if money_flow_df.empty:
            log.info("未获取到主力资金流数据")
            return money_flow_map
        # 确定日期列（兼容'date'或'trade_date'字段）
        date_column = 'date' if 'date' in money_flow_df.columns else 'trade_date'
        if date_column not in money_flow_df.columns:
            log.warning("资金流数据中未找到日期列，使用end_date作为默认日期")
        # 构建资金流映射字典（按股票代码聚合所有日期记录）
        for _, row in money_flow_df.iterrows():
            stock_code = row['sec_code']
            # 初始化股票对应的记录列表（首次出现时）
            if stock_code not in money_flow_map:
                money_flow_map[stock_code] = []
            # 优先使用数据中的日期，无则用end_date
            record_date = row[date_column] if date_column in money_flow_df.columns else end_date
            # 构建单条日期记录并添加到列表
            daily_record = {
                'date': record_date,
                'net_amount_main': row['net_amount_main'],  # 主力净额(万)
                'net_pct_main': row['net_pct_main'],  # 主力净占比(%)
                'net_amount_l': row['net_amount_l']
            }
            money_flow_map[stock_code].append(daily_record)
        # 输出每个股票的记录数量日志
        # for stock, records in money_flow_map.items():
        #     log.info(f"个股主力资金数据：{stock} 共 {len(records)} 条记录，日期范围: {records[0]['date']} 至 {records[-1]['date']}")
    except Exception as e:
        log.warning(f"批量获取主力资金数据失败: {str(e)}")
    return money_flow_map

# 同花顺指标转换为Python函数 
def calculate_ths_indicators(stock, context, period=30, unit='1d', log_debug=False):
    """
    计算同花顺指标，返回买卖信号（优化版）
    """
    try:
        # 获取历史数据
        hist_data = attribute_history(stock, period, unit,
                                      ['open', 'close', 'high', 'low', 'volume'],
                                      skip_paused=True)

        if hist_data.empty or len(hist_data) < 20:
            return {'buy_signals': [], 'sell_signals': []}

        # 提取OHLCV数据
        O = hist_data['open'].values
        C = hist_data['close'].values
        H = hist_data['high'].values
        L = hist_data['low'].values
        V = hist_data['volume'].values

        # 计算各类指标
        signals = {
            'buy_signals': [],
            'sell_signals': []
        }

        # ========== 优化后的ZIG指标计算 ==========
        def calculate_zig_optimized(prices, threshold_pct=3):
            """
            优化版的ZIG指标计算
            标准ZIG指标：寻找价格转折点，连接高低点形成折线
            """
            if len(prices) < 3:
                return prices
            
            zig = np.zeros(len(prices))
            zig[0] = prices[0]
            
            # 寻找第一个有效的高低点
            last_extreme = prices[0]  # 最后一个极值点
            last_extreme_idx = 0
            trend = 0  # 0:未定义, 1:上升趋势, -1:下降趋势
            
            for i in range(1, len(prices)):
                # 初始化第一个点
                if i == 1:
                    zig[i] = prices[i]
                    continue
                
                # 计算从最后一个极值点到当前点的变化百分比
                change_pct = abs(prices[i] - last_extreme) / last_extreme * 100 if last_extreme > 0 else 0
                
                # 如果价格变化超过阈值，确定趋势
                if change_pct >= threshold_pct:
                    if prices[i] > last_extreme:
                        # 新的上升趋势
                        if trend != 1:
                            # 趋势反转：从下降转为上升
                            trend = 1
                            # 连接上一个极值点到当前点
                            for j in range(last_extreme_idx + 1, i + 1):
                                t = (j - last_extreme_idx) / (i - last_extreme_idx)
                                zig[j] = last_extreme + (prices[i] - last_extreme) * t
                            last_extreme = prices[i]
                            last_extreme_idx = i
                        else:
                            # 趋势延续，更新极值点
                            last_extreme = prices[i]
                            last_extreme_idx = i
                            zig[i] = prices[i]
                    else:
                        # 新的下降趋势
                        if trend != -1:
                            # 趋势反转：从上升转为下降
                            trend = -1
                            # 连接上一个极值点到当前点
                            for j in range(last_extreme_idx + 1, i + 1):
                                t = (j - last_extreme_idx) / (i - last_extreme_idx)
                                zig[j] = last_extreme + (prices[i] - last_extreme) * t
                            last_extreme = prices[i]
                            last_extreme_idx = i
                        else:
                            # 趋势延续，更新极值点
                            last_extreme = prices[i]
                            last_extreme_idx = i
                            zig[i] = prices[i]
                else:
                    # 变化未超过阈值，沿用上一个点的ZIG值
                    zig[i] = zig[i-1]
            
            return zig

        # ========== 简化的ZIG指标（更高效）==========
        def calculate_zig_simple(prices, threshold_pct=5):
            """
            简化版ZIG指标，只识别主要转折点
            适用于短期交易信号
            """
            if len(prices) < 3:
                return prices
            
            zig = np.zeros(len(prices))
            zig[0] = prices[0]
            
            # 识别局部极值点
            extremes = []
            for i in range(1, len(prices)-1):
                # 局部高点
                if prices[i] > prices[i-1] and prices[i] > prices[i+1]:
                    extremes.append((i, 'high', prices[i]))
                # 局部低点
                elif prices[i] < prices[i-1] and prices[i] < prices[i+1]:
                    extremes.append((i, 'low', prices[i]))
            
            # 过滤掉幅度太小的转折点
            filtered_extremes = []
            for i in range(len(extremes)):
                idx, typ, val = extremes[i]
                if i == 0 or i == len(extremes)-1:
                    filtered_extremes.append((idx, typ, val))
                else:
                    prev_idx, prev_typ, prev_val = extremes[i-1]
                    next_idx, next_typ, next_val = extremes[i+1]
                    
                    # 计算与前一个极值点的变化
                    change_pct = abs(val - prev_val) / prev_val * 100
                    if change_pct >= threshold_pct:
                        filtered_extremes.append((idx, typ, val))
            
            # 构建ZIG线
            if not filtered_extremes:
                return prices
            
            # 连接极值点
            last_idx = 0
            last_val = prices[0]
            
            for idx, typ, val in filtered_extremes:
                # 线性插值
                for j in range(last_idx, idx+1):
                    if last_idx == idx:
                        zig[j] = val
                    else:
                        t = (j - last_idx) / (idx - last_idx)
                        zig[j] = last_val + (val - last_val) * t
                
                last_idx = idx
                last_val = val
            
            # 填充剩余部分
            if last_idx < len(prices)-1:
                for j in range(last_idx+1, len(prices)):
                    zig[j] = last_val
            
            return zig

        # 计算买线和卖线
        zig_threshold = 3  # ZIG转折阈值（百分比）
        买线 = calculate_zig_optimized(C, zig_threshold)
        
        # 卖线：买线的3日移动平均
        卖线 = pd.Series(买线).rolling(window=3, min_periods=1).mean().values

        # 计算MA均线
        MA5 = pd.Series(C).rolling(window=5, min_periods=1).mean().values
        MA10 = pd.Series(C).rolling(window=10, min_periods=1).mean().values
        MA20 = pd.Series(C).rolling(window=20, min_periods=1).mean().values

        # 计算基线（优化计算，避免嵌套Series）
        min_30 = pd.Series(C).rolling(window=30, min_periods=1).min().shift(1)
        基线 = min_30.rolling(window=2, min_periods=1).mean().values

        # ========== 波段买点信号 ==========
        if len(买线) >= 3 and len(卖线) >= 3:
            # 条件1: 买线上穿卖线
            if 买线[-1] > 卖线[-1] and 买线[-2] <= 卖线[-2]:
                # 增强条件：价格在MA5之上
                if C[-1] > MA5[-1]:
                    signals['buy_signals'].append('波段买点')
            
            # 条件2: 价格站上基线且基线向上
            if len(基线) >= 2:
                if C[-1] > 基线[-1] and 基线[-1] > 基线[-2]:
                    signals['buy_signals'].append('基线突破')

        # ========== 波段卖出信号（多条件判断）==========
        # 使用更敏感的ZIG进行卖出判断
        zig_5 = calculate_zig_simple(C, 5)
        
        if len(zig_5) >= 4:
            # 条件1: ZIG连续下跌
            condition1 = (zig_5[-1] < zig_5[-2] and
                          zig_5[-2] >= zig_5[-3] and
                          zig_5[-3] >= zig_5[-4])
            
            # 条件2: 价格跌破关键均线
            condition2 = False
            if len(MA5) >= 2 and len(MA10) >= 2:
                condition2 = (C[-1] < MA5[-1] and MA5[-1] < MA10[-1])
            
            # 条件3: 卖线下穿买线
            condition3 = False
            if len(买线) >= 2 and len(卖线) >= 2:
                condition3 = (卖线[-1] < 买线[-1] and 卖线[-2] >= 买线[-2])
            
            # 条件4: 价格跌破基线
            condition4 = False
            if len(基线) > 0:
                condition4 = C[-1] < 基线[-1]
            
            # 卖出条件优先级：满足任一条件即触发
            if condition1 or condition2 or condition3:
                signals['sell_signals'].append('波段卖')
            elif condition4:
                signals['sell_signals'].append('跌破基线')

        # ========== 精准买点 (EMA交叉) ==========
        def ema(data, period):
            return pd.Series(data).ewm(span=period, adjust=False).mean().values

        X1 = (C + L + H) / 3
        X2 = ema(X1, 6)
        X3 = ema(X2, 5)

        if len(X2) >= 2 and len(X3) >= 2:
            # 金叉且买线在卖线之上
            if X2[-1] > X3[-1] and X2[-2] <= X3[-2] and 买线[-1] >= 卖线[-1]:
                # 增强条件：成交量放大
                if len(V) >= 2 and V[-1] > V[-2] * 1.2:
                    signals['buy_signals'].append('精准买')

        # ========== 游资进入信号（修复除零错误）==========
        if len(C) >= 75:
            def sma(data, period, weight=1):
                return pd.Series(data).ewm(alpha=weight / period, adjust=False).mean().values

            # 计算VARF1指标
            llv_75 = pd.Series(L).rolling(window=75, min_periods=1).min().values
            hhv_75 = pd.Series(H).rolling(window=75, min_periods=1).max().values

            # 修复除零错误
            denominator = hhv_75 - llv_75
            denominator = np.where(denominator == 0, 1, denominator)  # 避免除零
            
            close_norm = (C - llv_75) / denominator * 100
            open_norm = (O - llv_75) / denominator * 100
            
            # 处理NaN和Inf
            close_norm = np.nan_to_num(close_norm, nan=0.0, posinf=100.0, neginf=0.0)
            open_norm = np.nan_to_num(open_norm, nan=0.0, posinf=100.0, neginf=0.0)

            sma1_close = sma(close_norm, 20, 1)
            sma2_close = sma(sma1_close, 15, 1)
            VARF1 = 100 - 3 * sma1_close + 2 * sma2_close

            sma1_open = sma(open_norm, 20, 1)
            sma2_open = sma(sma1_open, 15, 1)
            VAR101 = 100 - 3 * sma1_open + 2 * sma2_open

            if len(VARF1) >= 2 and len(VAR101) >= 2 and len(V) >= 2:
                VAR111 = (VARF1[-1] < VAR101[-2] and V[-1] > V[-2] and C[-1] > C[-2])

                # 检查30天内是否只有一次这样的信号
                count_signals = 0
                for i in range(max(0, len(VARF1) - 30), len(VARF1)):
                    if i >= 1 and i < len(V) - 1:
                        if (VARF1[i] < VAR101[i - 1] and V[i] > V[i - 1] and C[i] > C[i - 1]):
                            count_signals += 1

                if VAR111 and count_signals == 1 and 买线[-1] >= 卖线[-1]:
                    # 增强条件：价格在均线之上
                    if len(MA5) > 0 and C[-1] > MA5[-1]:
                        signals['buy_signals'].append('游资进')

        # ========== 新增：超买超卖信号 ==========
        # 计算RSI
        def calculate_rsi(prices, period=14):
            if len(prices) < period + 1:
                return np.zeros(len(prices))
            
            deltas = np.diff(prices)
            seed = deltas[:period]
            up = seed[seed >= 0].sum() / period
            down = -seed[seed < 0].sum() / period
            rs = up / down if down != 0 else 0
            rsi = np.zeros_like(prices)
            rsi[:period] = 100.0 - 100.0 / (1.0 + rs)
            
            for i in range(period, len(prices)):
                delta = deltas[i-1]
                if delta > 0:
                    upval = delta
                    downval = 0.0
                else:
                    upval = 0.0
                    downval = -delta
                
                up = (up * (period-1) + upval) / period
                down = (down * (period-1) + downval) / period
                rs = up / down if down != 0 else 0
                rsi[i] = 100.0 - 100.0 / (1.0 + rs)
            
            return rsi
        
        # 计算RSI
        if len(C) >= 15:
            rsi = calculate_rsi(C, 14)
            if len(rsi) > 0:
                # 超买信号
                if rsi[-1] > 70:
                    signals['sell_signals'].append('RSI超买')
                # 超卖信号
                elif rsi[-1] < 30:
                    signals['buy_signals'].append('RSI超卖')

        # ========== 新增：成交量确认 ==========
        if len(V) >= 2:
            # 放量上涨
            if C[-1] > C[-2] and V[-1] > V[-2] * 1.5:
                signals['buy_signals'].append('放量上涨')
            # 放量下跌
            elif C[-1] < C[-2] and V[-1] > V[-2] * 1.5:
                signals['sell_signals'].append('放量下跌')

        # 去重信号
        signals['buy_signals'] = list(set(signals['buy_signals']))
        signals['sell_signals'] = list(set(signals['sell_signals']))

        # 记录调试信息
        if log_debug and (signals['buy_signals'] or signals['sell_signals']):
            log.info(f"THS指标信号 {stock}: 买={signals['buy_signals']}, 卖={signals['sell_signals']}")

        return signals

    except Exception as e:
        log.error(f"计算同花顺指标时出错 {stock}: {str(e)}")
        import traceback
        log.error(traceback.format_exc())
        return {'buy_signals': [], 'sell_signals': []}

def check_volume_drop_signal(stock, context):
    """
    检测放量大跌信号（跌幅6%以上且放量）
    判定条件：当前相对昨日收盘跌幅≥6% + 估算全天成交量≥5日均量1.5倍
    """
    try:
        # 1. 获取实时行情数据，快速过滤无效标的
        current_data = get_current_data()
        if stock not in current_data:
            return False
        stock_quote = current_data[stock]
        current_price = stock_quote.last_price
        today_open = stock_quote.day_open
        # 过滤价格为0的异常行情
        if current_price == 0 or today_open == 0:
            return False

        # 2. 获取近2日K线数据，提取昨日收盘价（需至少2条有效数据）
        hist_2d = attribute_history(stock, 2, '1d', 
                                     ['open', 'close', 'volume'], 
                                     skip_paused=True)
        if len(hist_2d) < 2:
            return False
        yesterday_close = hist_2d['close'].iloc[-2]  # 用iloc更安全，适配pandas
        if yesterday_close == 0:
            return False

        # 3. 计算当前跌幅，未达6%直接返回（提前过滤，提升效率）
        drop_pct = (yesterday_close - current_price) / yesterday_close
        if drop_pct < 0.06:
            return False

        # 4. 获取近6日成交量数据，计算5日均量（排除今日）
        vol_6d = attribute_history(stock, 6, '1d', ['volume'], skip_paused=True)
        # 修正：取6日数据需至少6条，否则无法提取前5日有效数据
        if len(vol_6d) < 6:
            return False
        # 前5日成交量（排除今日最后1条），计算均值
        vol_5d = vol_6d['volume'].iloc[:-1]
        avg_volume_5 = vol_5d.mean()
        # 补全除零保护：5日均量为0时直接返回（避免后续除法报错）
        if avg_volume_5 < 1:
            return False
        # 今日已成交成交量
        today_volume = vol_6d['volume'].iloc[-1]
        if today_volume < 1:
            return False

        # 5. 计算当前已交易分钟数（适配A股交易时间：9:30-11:30、13:00-15:00）
        current_time = context.current_dt.time()
        market_minutes = 0
        # 上午交易时段
        if dt.time(9, 30) <= current_time <= dt.time(11, 30):
            market_minutes = (current_time.hour - 9) * 60 + current_time.minute - 30
        # 下午交易时段
        elif dt.time(13, 0) <= current_time <= dt.time(15, 0):
            market_minutes = 120 + (current_time.hour - 13) * 60 + current_time.minute
        # 午休/收盘后，直接取对应时段的总分钟数
        elif dt.time(11, 30) < current_time < dt.time(13, 0):
            market_minutes = 120
        elif current_time > dt.time(15, 0):
            market_minutes = 240
        # 非交易时间（开盘前），直接返回
        if market_minutes < 1:
            return False

        # 6. 估算全天成交量（加早盘修正因子，适配早盘量能偏高特性）
        estimated_daily_volume = today_volume * (240 / market_minutes)
        # 修正因子：早盘前60分钟1.2→0.8，上午后60分钟0.8→1.0，下午保持1.0
        if market_minutes < 60:
            estimated_daily_volume *= 1.2 - (market_minutes / 60) * 0.4
        elif 60 <= market_minutes < 120:
            estimated_daily_volume *= 0.8 + ((market_minutes - 60) / 60) * 0.2

        # 7. 计算量比，判定是否放量
        volume_ratio = estimated_daily_volume / avg_volume_5
        if volume_ratio >= 1.5:
            log.info(f"🚨 放量大跌信号: {stock} | 跌幅: {drop_pct*100:.2f}% | "
                    f"量比: {volume_ratio:.2f}倍 | 已交易: {market_minutes}分钟")
            return True

        return False

    except Exception as e:
        # 修复：原代码少闭合括号的语法错误，优化日志提示
        log.error(f"检测{stock}放量大跌信号出错: {str(e)}")
        return False


def sell_limit_per5min(context):
    """
    每5分钟检测持仓股票是否需要卖出
    基于同花顺指标的波段卖信号和放量大跌信号
    """
    # 初始化交易记录
    if not hasattr(g, 'today_trades'):
        g.today_trades = []

    current_data = get_current_data()
    date = transform_date(context.previous_date, 'str')

    for stock in list(context.portfolio.positions):
        if stock == '511880.XSHG':  # 排除基金
            continue

        position = context.portfolio.positions[stock]
        if position.closeable_amount == 0:
            continue

        # 检查是否停牌
        if current_data[stock].paused:
            continue

        try:
            # 1. 检测同花顺指标信号
            ths_signals = calculate_ths_indicators(stock, context, 30, '5m')
            has_sell_signal = '波段卖' in ths_signals['sell_signals']

            # 2. 检测放量大跌信号
            has_volume_drop = check_volume_drop_signal(stock, context)

            # 获取当前价格和成本价
            current_price = current_data[stock].last_price
            avg_cost = position.avg_cost

            # 3. 紧急止损：波段卖信号 + 放量大跌
            if has_sell_signal and has_volume_drop:
                loss_pct = (avg_cost - current_price) / avg_cost

                details = {
                    '触发信号': '波段卖 + 放量大跌',
                    '成本价': f"{avg_cost:.2f}",
                    '当前价': f"{current_price:.2f}",
                    '亏损比例': f"{loss_pct:.2%}",
                    '同花顺信号': ths_signals['sell_signals']
                }

                # 记录并执行卖出
                record_sell_trade(context, stock, "紧急止损-波段卖+放量大跌", details, current_data, date)
                order_target_value( stock, 0)
                # 实盘接口卖出
                emit_trading_signal('sell', stock, '', g.jk_stk_num)

                log.info(f"★★★ 紧急止损 ★★★")
                log.info(f"股票: {stock}")
                log.info(f"触发信号: 波段卖 + 放量大跌")
                log.info(f"卖出价格: {current_price:.2f}")
                log.info(f"亏损幅度: {loss_pct:.2%}")

            # 4. 波段卖出：仅波段卖信号且亏损超过3%
            elif has_sell_signal:
                loss_pct = (avg_cost - current_price) / avg_cost

                if loss_pct >= 0.03:
                    details = {
                        '触发信号': '波段卖 + 亏损3%+',
                        '成本价': f"{avg_cost:.2f}",
                        '当前价': f"{current_price:.2f}",
                        '亏损比例': f"{loss_pct:.2%}",
                        '同花顺信号': ths_signals['sell_signals']
                    }

                    record_sell_trade(context, stock, "波段卖出", details, current_data, date)
                    order_target_value( stock, 0)
                    # 实盘接口卖出
                    emit_trading_signal('sell', stock, '', g.jk_stk_num)

                    log.info(f"波段卖出: {stock}, 亏损: {loss_pct:.2%}")

            # 5. 放量大跌：跌幅达到8%以上
            elif has_volume_drop:
                yesterday_close = attribute_history(stock, 1, '1d', ['close'], skip_paused=True)['close'][0]
                drop_pct = (yesterday_close - current_price) / yesterday_close

                if drop_pct >= 0.08:
                    details = {
                        '触发信号': '放量大跌8%+',
                        '昨收价': f"{yesterday_close:.2f}",
                        '当前价': f"{current_price:.2f}",
                        '跌幅': f"{drop_pct:.2%}"
                    }

                    record_sell_trade(context, stock, "放量大跌止损", details, current_data, date)
                    order_target_value( stock, 0)
                    # 实盘接口卖出
                    emit_trading_signal('sell', stock, '', g.jk_stk_num)

                    log.info(f"放量大跌止损: {stock}, 跌幅: {drop_pct:.2%}")

        except Exception as e:
            log.error(f"处理股票 {stock} 卖出检测时出错: {str(e)}")
            continue



# 2. 盘前数据统计函数
def record_morning_stats(context):
    """
    记录盘前统计数据
    """
    try:
        log.info(f"====== {context.current_dt.strftime('%Y-%m-%d')} 盘前数据 ======")
        # 情况个股积分缓存
        clear_score_cache(context)

        # 获取大盘数据
        index_data = attribute_history('000001.XSHG', 5, '1d',
                                       ['close', 'volume'], skip_paused=True)

        if not index_data.empty and len(index_data) >= 2:
            current_close = index_data['close'].iloc[-1]
            prev_close = index_data['close'].iloc[-2]
            change_rate = (current_close - prev_close) / prev_close * 100

            # 计算波动率
            volatility = index_data['close'].pct_change().std() * 100

            # 计算量能比
            current_volume = index_data['volume'].iloc[-1]
            avg_volume = index_data['volume'].head(-1).mean()
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1

            # 判断市场趋势
            if change_rate > 1:
                trend = "strong_up"
            elif change_rate > 0:
                trend = "up"
            elif change_rate > -1:
                trend = "flat"
            else:
                trend = "down"

            log.info("市场状况:")
            log.info(f"- 大盘趋势: {trend}")
            log.info(f"- 波动率: {volatility:.2f}%")
            log.info(f"- 量能比: {volume_ratio:.2f}")

            # 存储市场统计
            g.trade_stats['market_stats'] = {
                'date': context.current_dt.strftime('%Y-%m-%d'),
                'trend': trend,
                'change_rate': change_rate,
                'volatility': volatility,
                'volume_ratio': volume_ratio
            }
            market_env = analyze_market_environment(context)
            g.trade_stats['market_stats'].update(market_env)
            if market_env.get('risk_level') == 'risk_off':
                g.trade_stats.setdefault('risk_events', []).append({
                    'date': context.current_dt.strftime('%Y-%m-%d'),
                    'type': 'market_risk_off',
                    'reasons': market_env.get('risk_reasons', [])
                })
                log.warning(f"market risk off: {market_env.get('risk_reasons', [])}")
            update_strategy_priority(trend)

    except Exception as e:
        log.error(f"记录盘前统计失败: {str(e)}")


def get_last_n_auction_avg(s, end_date, n=5):
    # 获取最近n个交易日（含end_date）
    trade_days = get_trade_days(end_date=end_date, count=n)
    # 获取这n日的集合竞价量
    auction_data = get_call_auction([s], start_date=trade_days[0], end_date=trade_days[-1], fields=['time', 'volume'])
    if auction_data.empty:
        return 0
    return auction_data['volume'].mean()


def sell_limit_down(context):
    date = context.previous_date
    current_data = get_current_data()
    slist = list(context.portfolio.positions)

    # 获取集合竞价数据
    date_now = context.current_dt.strftime("%Y-%m-%d")
    auction_start = date_now + ' 09:15:00'
    auction_end = date_now + ' 09:25:00'
    auctions = get_call_auction(
        slist, start_date=auction_start, end_date=auction_end,
        fields=['time', 'current', 'volume']
    ).set_index('code') if slist else None

    for stock in slist:
        if stock == '511880.XSHG':  # 排除基金
            continue
        position = context.portfolio.positions[stock]

        try:
            # 获取K线数据
            price_data = get_price(stock, end_date=date, count=6,
                                   fields=['open', 'close', 'high', 'low', 'volume', 'high_limit'], skip_paused=False)
            if price_data.shape[0] < 6:
                continue
            # 放量长上影昨日数据
            yest = price_data.iloc[-1]
            # 涨停放量低开昨日数据
            prev = price_data.iloc[-1]
            # print(f"price_data:{price_data}, yest:{yest}, prev{prev}")
            avg_vol_5 = price_data['volume'].iloc[:-1].mean()

            prev_close = prev['close']
            prev_high_limit = prev['high_limit']
            prev_volume = prev['volume']
            today_open = current_data[stock].day_open
            if pd.isna(today_open) or today_open == 0:
                continue

            # 估值数据
            valuation = get_valuation(stock, date, date, fields=['pe_ratio', 'circulating_market_cap'])
            if valuation.empty:
                continue
            pe_ratio = valuation['pe_ratio'].iloc[0]
            market_cap = valuation['circulating_market_cap'].iloc[0]

            # 集合竞价量
            auction_volume = auctions.loc[stock]['volume'] if (auctions is not None and stock in auctions.index) else 1
            avg_auction_vol_5 = get_last_n_auction_avg(stock, date_now, n=5) or 1  # 防止为0
            auction_vol_ratio = auction_volume / avg_auction_vol_5 if avg_auction_vol_5 > 0 else 1

            # 检查上一交易日是否涨停
            if prev_close == prev_high_limit:
                # 获取今日开盘价和跌幅
                today_open = current_data[stock].day_open
                open_drop_ratio = (today_open - prev_close) / prev_close

                # 获取市盈率和流通市值
                valuation = get_valuation(stock, date, date, fields=['pe_ratio', 'circulating_market_cap'])
                if valuation.empty:
                    continue

                pe_ratio = valuation['pe_ratio'].iloc[0]
                market_cap = valuation['circulating_market_cap'].iloc[0]

                # 根据多维度条件决定是否卖出
                should_sell = False

                # 条件1：低开幅度在-3%~-1%，且市值中等（50亿~100亿）
                if (-0.03 <= open_drop_ratio <= -0.01) and (50 <= market_cap <= 100):
                    should_sell = True

                # 条件2：低市盈率（<20）且低开幅度在-5%~-1%
                elif (pe_ratio < 20) and (-0.05 <= open_drop_ratio <= -0.01):
                    should_sell = True

                # 执行卖出
                if should_sell and context.portfolio.positions[stock].closeable_amount > 0:
                    order_target_value( stock, 0, MarketOrderStyle(current_data[stock].day_open))
                    print(f"~~~~紧急处理个股{stock},低开快速卖出价格{current_data[stock].day_open}")
                    # 实盘接口卖出
                    emit_trading_signal('sell', stock, '', g.jk_stk_num)

            # === 优先级2：放量长上影开盘卖出 (优化版) ===
            upper_shadow = yest['high'] - max(yest['open'], yest['close'])
            lower_shadow = min(yest['open'], yest['close']) - yest['low']
            real_body = abs(yest['close'] - yest['open'])
            total_range = yest['high'] - yest['low']

            # 基础的“放量长上影”定义
            is_long_upper_shadow = (
                    upper_shadow > lower_shadow * 1.2 and
                    upper_shadow > 1.5 * real_body and
                    upper_shadow > 0.3 * total_range
            )
            is_big_vol = yest['volume'] > 1.5 * avg_vol_5

            yesterday_close = yest['close']
            # 当today_open为0时，直接将open_change赋值为-100，避免后续计算报错
            if today_open == 0:
                open_change = -100
            else:
                open_change = (today_open / yesterday_close - 1) * 100
            auction_vol_ratio = auction_volume / avg_auction_vol_5 if avg_auction_vol_5 > 0 else 1
            # 首先，记录所有符合基础定义的信号
            if is_long_upper_shadow and is_big_vol:
                # --- 优化后的卖出条件 ---
                # 条件1: 上影线远大于下影线，确认T-1日卖压沉重
                is_seller_dominant = upper_shadow > lower_shadow * 3

                # 条件2: 开盘涨幅不能过高，避免卖在强势反转的起点
                is_open_not_strong = open_change < 2

                # 条件3 (核心优化): 动态判断竞价量
                # 逻辑：如果开盘价疲软（平开或微涨），我们可以容忍稍大的竞价量，
                # 因为“放量不涨”本身就是滞涨或出货的信号。
                is_auction_ok = False
                if open_change <= 0.5:  # 如果开盘价非常弱势
                    # 容忍2倍以下的竞价放量，视为多空分歧加大但多头无力上攻
                    if auction_vol_ratio < 2.0:
                        is_auction_ok = True
                else:  # 如果开盘价稍强 (0.5% < open_change < 2%)
                    # 此时要求更严格的竞价量，必须是缩量或微量，防止是强势承接
                    if auction_vol_ratio < 1.4:
                        is_auction_ok = True

                if (
                        position.closeable_amount > 0 and
                        is_seller_dominant and
                        is_open_not_strong and
                        is_auction_ok  # 使用新的动态条件
                ):
                    order_target_value( stock, 0)
                    # 实盘接口卖出
                    emit_trading_signal('sell', stock, '', g.jk_stk_num)
                    date_str = date.strftime('%Y-%m-%d')
                    print(f"~~~精准卖出信号-放量长上影: {stock} ({get_security_info(stock, date_str).display_name})")
                    print(f"    上影/下影: {upper_shadow / lower_shadow if lower_shadow > 0 else 'inf':.2f}(>3), "
                          f"开盘涨幅: {open_change:.2f}%(<2%), "
                          f"竞价量比: {auction_vol_ratio:.2f} (动态阈值判断通过)")
                    print('———————————————————————————————————')
                continue
        except Exception as e:
            print(f"处理股票 {stock} 时出错: {e}")
            continue


# 判断是否需要空仓
def should_empty_position(context):
    current_date = context.current_dt
    current_day = current_date.day
    current_month = current_date.month
    current_year = current_date.year

    # # 新增的特定日期区间空仓条件
    # # 12月18日到次年1月13日
    # if (current_month == 12 and current_day >= 18) or (current_month == 1 and current_day <= 7):
    #     print('空仓时间点：12月18日到次年1月7日')
    #     return True
    # # 4月5日 - 4月9日
    # if current_month == 4 and 5 <= current_day <= 9:
    #     print('空仓时间点：4月5日 - 4月9日')
    #     return True
    # # 10月8日 - 10月9日
    # if current_month == 10 and 8 <= current_day <= 9:
    #     print('空仓时间点：10月8日 - 10月9日')
    #     return True

    # 量能条件
    try:
        volume_data = attribute_history('000300.XSHG', 5, '1d', fields=['volume'], skip_paused=True)
        avg_volume = volume_data['volume'][:-1].mean()
        current_volume = volume_data['volume'][-1]
        if current_volume > 2 * avg_volume or current_volume < 0.5 * avg_volume:
            print('空仓时间点：大盘量能不足休息')
            return True
    except Exception as e:
        print(f"获取大盘量能数据出错: {e}")

    return False


# 选股
def get_stock_list(context):
    # 判断是否需要空仓
    if should_empty_position(context):
        current_data = get_current_data()
        for stock in context.portfolio.positions:
            log.info(f"[空仓] 卖出持仓股: {stock}")
            console_notice(f"卖出持仓股: {stock}")
            order_target_value( stock, 0)
            # 实盘接口卖出
            emit_trading_signal('sell', stock, '', g.jk_stk_num)
        g.is_empty = True
        log.info("[空仓] 当前满足空仓条件，今日不参与选股。")
        return
    else:
        g.is_empty = False
    # 文本日期
    date = context.previous_date
    date_2, date_1, date = get_trade_days(end_date=date, count=3)
    # 初始列表
    initial_list = prepare_stock_list(date)
    # 昨日涨停
    hl0_list = get_hl_stock(initial_list, date)
    # 前日曾涨停
    hl1_list = get_ever_hl_stock(initial_list, date_1)
    # 前前日曾涨停
    hl2_list = get_ever_hl_stock(initial_list, date_2)
    # 合并 hl1_list 和 hl2_list 为一个集合，用于快速查找需要剔除的元素
    elements_to_remove = set(hl1_list + hl2_list)
    # 使用列表推导式来剔除 hl_list 中存在于 elements_to_remove 集合中的元素
    g.gap_up = [stock for stock in hl0_list if stock not in elements_to_remove]  # 昨天涨停但前天、大前天无涨停，用于首板高开
    # 昨日涨停，但前天没有涨停的
    g.gap_down = [s for s in hl0_list if s not in hl1_list]  # 昨天涨停但前天无涨停，用于首板低开
    # 昨日曾涨停
    h1_list = get_ever_hl_stock2(initial_list, date)
    # 上上个交易日涨停过滤
    elements_to_remove = get_hl_stock(initial_list, date_1)

    # 过滤上上个交易日涨停、曾涨停
    g.reversal = [stock for stock in h1_list if stock not in elements_to_remove]  # 昨天曾涨停但收盘未涨停且前天无涨停，用于弱转强

    g.fxsbdk = get_ll_stock(initial_list, date)  # 昨日跌停，用于反向首版低开

    date_now = context.current_dt.strftime("%Y-%m-%d")
    auction_start = date_now + ' 09:15:00'
    auction_end = date_now + ' 09:25:00'
    auctions = get_call_auction(hl0_list, start_date=auction_start, end_date=auction_end,
                                fields=['time', 'current']).set_index('code')
    if auctions.empty:
        g.lblt = []
        return
    # 获取前收盘价
    h = get_price(hl0_list, end_date=date, fields=['close'], count=1, panel=False).set_index('code')
    if h.empty:
        g.lblt = []
        return
    # 筛选集合竞价高开的比例
    auctions['pre_close'] = h['close']
    gk_list = auctions.query('pre_close * 1.00 < current').index.tolist()
    gkb = len(gk_list) / len(hl0_list) * 100  # 昨日涨停早盘高开比
    if gkb < 76:
        g.lblt = []
    else:
        g.lblt = hl0_list


def calculate_sentiment_score_optimized(stock, context, hist_data=None):
    """
    修复后的市场情绪评分计算
    """
    try:
        cache_date = context.previous_date

        if not hasattr(g, 'market_sentiment_index_cache'):
            g.market_sentiment_index_cache = {}

        cache_key = _normalize_hot_concept_date(cache_date)
        if cache_key not in g.market_sentiment_index_cache:
            g.market_sentiment_index_cache[cache_key] = _get_attribute_history_cached(
                '000001.XSHG', 5, '1d', ['close', 'volume'], cache_date, skip_paused=True
            )
            _trim_cache_dict(g.market_sentiment_index_cache, getattr(g, 'cache_max_days', 5))

        index_data = g.market_sentiment_index_cache[cache_key]

        if index_data.empty:
            return 0

        score = 0

        # 1. 市场趋势评分 (0-2分)
        if len(index_data) >= 3:
            recent_closes = index_data['close'].tail(3)
            if recent_closes.iloc[-1] > recent_closes.iloc[-2] > recent_closes.iloc[-3]:
                score += 2  # 连续上涨
            elif recent_closes.iloc[-1] > recent_closes.iloc[-2]:
                score += 1  # 昨日上涨

        # 2. 市场成交量评分 (0-2分)
        if len(index_data) >= 5:
            recent_volume = index_data['volume'].tail(2).mean()
            avg_volume = index_data['volume'].head(-2).mean()

            if recent_volume > avg_volume * 1.2:
                score += 2  # 明显放量
            elif recent_volume > avg_volume * 1.1:
                score += 1  # 适度放量

        # 3. 个股相对强度 (0-1分)
        try:
            if hist_data is not None and not hist_data.empty and 'close' in hist_data.columns:
                stock_data = hist_data[['close']].tail(5)
            else:
                stock_data = _get_attribute_history_cached(
                    stock, 5, '1d', ['close'], cache_date, skip_paused=True
                )
            if not stock_data.empty and len(stock_data) >= 3:
                stock_change = (stock_data['close'].iloc[-1] / stock_data['close'].iloc[-3] - 1) * 100
                index_change = (index_data['close'].iloc[-1] / index_data['close'].iloc[-3] - 1) * 100

                if stock_change > index_change + 2:  # 跑赢大盘2%以上
                    score += 1
        except:
            pass

        return min(score, 5)  # 最高5分

    except Exception as e:
        log.error(f"计算情绪评分失败 {stock}: {str(e)}")
        return 0


# 交易
def buy(context):
    if g.is_empty:
        return
    
    # 设置买入打板模式的优先级配置，便于手动调整
    log.info(f"trend:{g.trade_stats['market_stats']},g.priority_config:{g.priority_config}")
    
    # 检查是否需要进行买入交易的条件判断
    current_weekday = context.current_dt.weekday()
    current_time_str = str(context.current_dt)[-8:]
    current_date = context.current_dt.date()
    
    # 判断当前时间段
    is_morning, is_afternoon, is_trading_time = get_trading_time_status(context)
    
    # 周一至周四14:50不买票的逻辑
    if current_weekday < 4 and is_afternoon:
        log.info(f'当前为周{current_weekday+1} 14:50，不执行买入')
        return

    allow_buy, risk_reasons = market_allows_new_position(context)
    if not allow_buy:
        log.warning(f"market risk filter blocks new positions: {risk_reasons}")
        console_notice(f"市场风险过滤，今日不开新仓: {risk_reasons}")
        return
    
   # 初始化交易记录全局变量
    if not hasattr(g, 'trade_records'):
        g.trade_records = {}



    # 初始化今日买入列表（存储字典：股票代码+买入前价格）
    if not hasattr(g, 'today_buy_list'):
        g.today_buy_list = []
    else:
        g.today_buy_list.clear()  # 清空之前的记录（确保只保留当日待买入信息）
    """买入时记录详细信息"""
    # 确保有 today_trades 列表记录当日交易
    if not hasattr(g, 'today_trades'):
        g.today_trades = []
    
    # 初始化各类型股票列表（按优先级顺序定义）
    lblt_stocks = []  # 连板龙头
    rzq_stocks = []   # 弱转强
    gk_stocks = []    # 一进二
    dk_stocks = []    # 首板低开
    fxsbdk_stocks = []# 反向首板低开
    
    current_data = get_current_data()
    date_now = context.current_dt.strftime("%Y-%m-%d")
    date = transform_date(context.previous_date, 'str')
    auction_cache_df = pd.DataFrame()

    if is_morning:
        auction_candidates = list(set(g.reversal + g.gap_up))
        if auction_candidates:
            try:
                auction_cache_df = get_call_auction(
                    auction_candidates,
                    start_date=date_now,
                    end_date=date_now,
                    fields=['time', 'volume', 'current']
                )
                if auction_cache_df is None or auction_cache_df.empty:
                    auction_cache_df = pd.DataFrame()
                else:
                    auction_cache_df = auction_cache_df.set_index('code')
            except Exception as e:
                log.warning(f"批量获取集合竞价数据失败: {str(e)}")
                auction_cache_df = pd.DataFrame()

        # 1. 连板龙头（最高优先级）
        if g.lblt:
            # 全部连板股票
            ccd = get_continue_count_df(g.lblt, date, 20) if len(g.lblt) != 0 else pd.DataFrame(index=[], data={'count': [],
                                                                                                                'extreme_count': []})
            # 最高连板
            M = ccd['count'].max() if len(ccd) != 0 else 0
            # 筛选龙头股票
            ccd0 = pd.DataFrame(index=[], data={'count': [], 'extreme_count': []})
            CCD = ccd[ccd['count'] == M] if M != 0 else ccd0
            m = CCD['extreme_count'].min()
            lt = list(CCD.index)
            # 数量
            l = len(CCD)
            # 晋级率
            r = 100 * len(CCD) / len(g.lblt) if len(g.lblt) != 0 else 0
            # 情绪
            emo = M
            g.emo_count.append(emo)
            # 周期
            cyc = g.emo_count[-1] if g.emo_count[-1] == max(g.emo_count[-3:]) and g.emo_count[
                -1] != 0 else 0
            cyc = 1 if cyc == emo else 0
            ## 热门股票池
            try:
                dct = get_concept(g.lblt, date)
                hot_concept = get_hot_concept(dct, date)
                hot_stocks = filter_concept_stock(dct, hot_concept)
            except:
                hot_stocks = []
            ## 筛选近5个交易日有2个以上连续一字板的个股（需要排除这些高风险股票）
            high_risk_stocks = []
            try:
                recent_price_data = get_price(
                    g.lblt,
                    end_date=date,
                    count=5,
                    fields=['open', 'close', 'high', 'low', 'high_limit', 'low_limit'],
                    panel=False,
                    fill_paused=False,
                    skip_paused=False
                )

                if recent_price_data is not None and not recent_price_data.empty:
                    if 'time' in recent_price_data.columns:
                        recent_price_data = recent_price_data.sort_values(['code', 'time'])

                    for stock, price_data in recent_price_data.groupby('code'):
                        consecutive_extreme = 0
                        max_consecutive = 0
                        for _, row in price_data.iterrows():
                            is_extreme = (
                                row['high'] == row['low'] and
                                row['close'] == row['high_limit']
                            )
                            if is_extreme:
                                consecutive_extreme += 1
                            else:
                                max_consecutive = max(max_consecutive, consecutive_extreme)
                                consecutive_extreme = 0

                        max_consecutive = max(max_consecutive, consecutive_extreme)
                        if max_consecutive >= 2:
                            high_risk_stocks.append(stock)
            except Exception as e:
                log.error(f"批量计算连板龙头近期一字板失败: {str(e)}")
            # 记录高风险股票
            if high_risk_stocks:
                log.info(f"近5日有2个以上连续一字板的高风险个股(将被排除): {[get_security_info(s).display_name for s in high_risk_stocks]}")
            ## 龙头特征筛选
            condition_dct = {}
            for s in lt:
                # 排除高风险股票
                if s in high_risk_stocks:
                    continue
                    
                try:
                    # 独食
                    ds = ccd.loc[s]['extreme_count']
                    # 市值
                    sz = get_fundamentals(
                        query(valuation.code, valuation.circulating_market_cap).filter(valuation.code == s),
                        date).iloc[0, 1]
                    # 换手
                    hs = HSL([s], date)[0][s]
                    # 龙头概念
                    c = 1 if s in hot_stocks else 0
                    
                    ## 逻辑判断
                    condition = ''
                    if hs < 35 and ds < 10 and emo > 2:
                        # 上升周期
                        if cyc == 1 and sz < 300:
                            condition += '上升周期'
                        # 资金接力
                        if ds < 3 and 10 < hs < 25:
                            condition += '资金接力'
                        # 题材初期
                        if c == 1 and emo <= 6:
                            condition += '题材初期(' + str(hot_concept) + ')'
                    
                    # 获取符合逻辑的列表
                    if len(condition) != 0:
                        condition_dct[s] = get_security_info(s, date).display_name + ' —— ' + condition
                except Exception as e:
                    log.error(f"龙头特征筛选{s}失败: {str(e)}")
                    pass
            
            # 最终股票列表（已排除高风险股票）
            stock_list = list(condition_dct.keys())
            
            # 记录筛选结果
            log.info(f"龙头股筛选结果(已排除高风险股票): {[get_security_info(s).display_name for s in stock_list]}")
            
            # 因子过滤
            df = get_factor_filter_df(context, stock_list, g.jqfactor, g.sort)
            lblt_stocks = list(df.index)

    
        # 2. 弱转强（第二优先级）
        for s in g.reversal:
            # 过滤前面三天涨幅超过28%的票
            price_data = _get_attribute_history_cached(s, 4, '1d', ['close'], context.previous_date, skip_paused=True)
            if len(price_data) < 4:
                continue
            increase_ratio = (price_data['close'][-1] - price_data['close'][0]) / price_data['close'][0]
            if increase_ratio > 0.28:
                continue
    
            # 过滤前一日收盘价小于开盘价5%以上的票
            prev_day_data = _get_attribute_history_cached(
                s, 1, '1d', ['open', 'close'], context.previous_date, skip_paused=True
            )
            if len(prev_day_data) < 1:
                continue
            open_close_ratio = (prev_day_data['close'][0] - prev_day_data['open'][0]) / prev_day_data['open'][0]
            if open_close_ratio < -0.05:
                continue
    
            prev_day_data = _get_attribute_history_cached(
                s, 1, '1d', ['close', 'volume', 'money'], context.previous_date, skip_paused=True
            )
            avg_price_increase_value = prev_day_data['money'][0] / prev_day_data['volume'][0] / prev_day_data['close'][
                0] - 1
            if avg_price_increase_value < -0.04 or prev_day_data['money'][0] < 3e8 or prev_day_data['money'][0] > 19e8:
                continue
            turnover_ratio_data = _get_valuation_cached(
                s, context.previous_date, ['turnover_ratio', 'market_cap', 'circulating_market_cap']
            )
            if turnover_ratio_data.empty or turnover_ratio_data['market_cap'][0] < 70 or \
                    turnover_ratio_data['circulating_market_cap'][0] > 520:
                continue
    
            if rise_low_volume(s, context):
                continue
            if not auction_cache_df.empty and s in auction_cache_df.index:
                auction_data = auction_cache_df.loc[[s]]
            else:
                auction_data = _get_call_auction_cached(s, date_now, ['time', 'volume', 'current'])
    
            if auction_data.empty or auction_data['volume'].iloc[0] / prev_day_data['volume'][-1] < 0.03:
                continue
            current_ratio = auction_data['current'].iloc[0] / (current_data[s].high_limit / 1.1)
            if current_ratio <= 0.98 or current_ratio >= 1.09:
                continue
            
            # 新增：检查弱转强个股的主线分，为0则不加入候选列表
            mainline_score = calculate_mainline_score_optimized(s, context)
            if mainline_score == 0:
                log.info(f"弱转强个股 {s} 主线分为0，不纳入买入候选")
                continue
            
            rzq_stocks.append(s)
    
        # 3. 一进二（第三优先级）
        for s in g.gap_up:
            # 条件一：均价，金额，市值，换手率
            prev_day_data = _get_attribute_history_cached(
                s, 1, '1d', ['close', 'volume', 'money'], context.previous_date, skip_paused=True
            )
            avg_price_increase_value = prev_day_data['money'][0] / prev_day_data['volume'][0] / prev_day_data['close'][
                0] * 1.1 - 1
            if avg_price_increase_value < 0.07 or prev_day_data['money'][0] < 5.5e8 or prev_day_data['money'][0] > 20e8:
                continue
            # market_cap 总市值(亿元) > 50亿 流通市值(亿元) < 520亿
            turnover_ratio_data = _get_valuation_cached(
                s, context.previous_date, ['turnover_ratio', 'market_cap', 'circulating_market_cap']
            )
            if turnover_ratio_data.empty or turnover_ratio_data['market_cap'][0] < 50 or \
                    turnover_ratio_data['circulating_market_cap'][0] > 520:
                continue
    
            # 条件二：左压
            if rise_low_volume(s, context):
                continue
            # 条件三：高开,开比
            if not auction_cache_df.empty and s in auction_cache_df.index:
                auction_data = auction_cache_df.loc[[s]]
            else:
                auction_data = _get_call_auction_cached(s, date_now, ['time', 'volume', 'current'])
            if auction_data.empty or auction_data['volume'].iloc[0] / prev_day_data['volume'][-1] < 0.03:
                continue
            current_ratio = auction_data['current'].iloc[0] / (current_data[s].high_limit / 1.1)
            if current_ratio <= 1 or current_ratio >= 1.06:
                continue
            # 条件4：价格<47（一进二模式优选中低价股）
            current_price = current_data[s].last_price
            if current_price > 47:
                continue
            
            # 条件5：量比范围检查（1.15~6.58是一进二模式的最佳量比区间）
            try:
                # 获取量比数据
                last_volume, last_2_volume, volume_ratio = get_volume_data(s, context)
                
                # 一进二模式量比范围：1.15~6.58
                if volume_ratio < 1.15 or volume_ratio > 6.58:
                    continue
                
                # 额外检查：换手率要求（首板5%-15%是健康换手范围）
                # if turnover_ratio_data['turnover_ratio'][0] < 5.0 or turnover_ratio_data['turnover_ratio'][0] > 15.0:
                #     continue
                
            except Exception as e:
                log.warning(f"获取股票 {s} 的量比数据失败: {str(e)}")
                continue
    
            # 如果股票满足所有条件，则添加到列表中
            gk_stocks.append(s)
            print(
                f"~~~一进二入选个股：{s} ,总市值:{turnover_ratio_data['market_cap'][0]},流通市值(亿元):{turnover_ratio_data['circulating_market_cap'][0]}")
    
        # 4. 首板低开（第四优先级）
        if g.gap_down:
            stock_list = g.gap_down
            # 计算相对位置
            rpd = get_relative_position_df(stock_list, date, 60)
            rpd = rpd[rpd['rp'] <= 0.5]
            stock_list = list(rpd.index)
    
            # 低开筛选
            df = get_price(stock_list, end_date=date, frequency='daily', fields=['close'], count=1, panel=False,
                           fill_paused=False, skip_paused=True).set_index('code') if len(
                stock_list) != 0 else pd.DataFrame()
            if not df.empty:
                df['open_pct'] = [current_data[s].day_open / df.loc[s, 'close'] for s in stock_list]
                df = df[(0.955 <= df['open_pct']) & (df['open_pct'] <= 0.97)]  # 筛选3个点左右低开
                stock_list = list(df.index)
    
                for s in stock_list:
                    prev_day_data = _get_attribute_history_cached(
                        s, 1, '1d', ['close', 'volume', 'money'], context.previous_date, skip_paused=True
                    )
                    if prev_day_data['money'][0] >= 1e8:
                        dk_stocks.append(s)
    
        # 5. 反向首板低开（第五优先级）
        if g.fxsbdk:
            # 获取非连板涨停的股票
            ccd = get_continue_count_df_ll(g.fxsbdk, date, 10)
            lb_list = list(ccd.index)
            stock_list = [s for s in g.fxsbdk if s not in lb_list]
    
            # 计算相对位置
            rpd = get_relative_position_df(stock_list, date, 60)
            rpd = rpd[rpd['rp'] <= 0.5]
            stock_list = list(rpd.index)
    
            # 低开筛选
            df = get_price(stock_list, end_date=date, frequency='daily', fields=['close'], count=1, panel=False,
                           fill_paused=False, skip_paused=True).set_index('code') if len(
                stock_list) != 0 else pd.DataFrame()
            if not df.empty:
                df['open_pct'] = [current_data[s].day_open / df.loc[s, 'close'] for s in stock_list]
                df = df[(1.04 <= df['open_pct']) & (df['open_pct'] < 1.10)]  # 筛选特定低开幅度
                fxsbdk_stocks = list(df.index)
    
        # 按优先级合并股票列表（去重，保留首次出现顺序）
        qualified_stocks = []
        # 创建优先级列表映射，便于根据配置动态调整顺序
        priority_lists = {
            "lb": lblt_stocks,     # 连板龙头
            "yje": gk_stocks,      # 一进二
            "rzq": rzq_stocks,     # 弱转强
            "dk": dk_stocks,       # 首板低开
            "fxsbdk": fxsbdk_stocks # 反向首板低开
        }
        pattern_lists = build_pattern_lists(lblt_stocks, gk_stocks, rzq_stocks, dk_stocks, fxsbdk_stocks)
        set_current_pattern_lists(pattern_lists)
        for pattern_key, pattern_stock_list in pattern_lists.items():
            record_mode_stat(pattern_key, 'candidate_count', len(pattern_stock_list))
    
        # 按优先级配置合并股票列表
        seen = set()
        for priority_type in g.priority_config:
            stock_list = priority_lists.get(priority_type, [])
            for s in stock_list:
                if s not in seen:
                    seen.add(s)
                    qualified_stocks.append(s)
        
        # 评分筛选：降低最低评分要求
        qualified_stocks = filter_stocks_by_score_optimized(
            qualified_stocks,
            context,
            min_score=g.min_score,
            max_stocks=100,
            pattern_lists=pattern_lists
        )
        g.qualified_stocks= qualified_stocks
        for selected_stock in qualified_stocks:
            record_mode_stat(get_stock_pattern(selected_stock, pattern_lists), 'qualified_count')
        if not qualified_stocks:
            log.info("没有符合条件的股票")
            console_notice('今日无目标个股')
            print('今日无目标个股')
            return
    
    # 非周五交易日处理
    if current_weekday < 4:
        # 打印选股结果
        print('———————————————————————————————————')
        console_notice('今日选股：' + ','.join(qualified_stocks))
        print(f'连板龙头（{len(lblt_stocks)}）：{",".join(lblt_stocks)}')
        print(f'弱转强（{len(rzq_stocks)}）：{",".join(rzq_stocks)}')
        print(f'一进二（{len(gk_stocks)}）：{",".join(gk_stocks)}')
        print(f'首板低开（{len(dk_stocks)}）：{",".join(dk_stocks)}')
        print(f'反向首板低开（{len(fxsbdk_stocks)}）：{",".join(fxsbdk_stocks)}')
        print(f'最终选股（{len(qualified_stocks)}）：{",".join(qualified_stocks)}')
        print('———————————————————————————————————')
        g.lblt_stocks = lblt_stocks
        g.rzq_stocks = rzq_stocks
        g.gk_stocks = gk_stocks
        g.dk_stocks = dk_stocks
        g.fxsbdk_stocks = fxsbdk_stocks
    
    # 周五特殊处理逻辑
    if current_weekday == 4:  # 周五
        # 早盘9:28:10执行：仅筛选股票，不执行买入
        if is_morning:
            # 保存选股结果到全局变量
            log.info("周五早盘仅筛选股票")
            log.info(f"周五早盘选出的个股：{g.qualified_stocks}")
            return
    
        # 14:50执行：使用早盘筛选的股票进行建仓
        if is_afternoon:
            log.info("周五14:50执行建仓")
            
            # 检查是否存在早盘筛选的股票
            if not hasattr(g, 'qualified_stocks') or not g.qualified_stocks:
                log.warning("周五14:50：未找到可交易股票")
                return
            
            # 恢复早盘筛选的股票和相关列表
            qualified_stocks = g.qualified_stocks
            lblt_stocks = g.lblt_stocks
            rzq_stocks = g.rzq_stocks
            gk_stocks = g.gk_stocks
            dk_stocks = g.dk_stocks
            fxsbdk_stocks = g.fxsbdk_stocks
            pattern_lists = build_pattern_lists(lblt_stocks, gk_stocks, rzq_stocks, dk_stocks, fxsbdk_stocks)
            set_current_pattern_lists(pattern_lists)
    
            # 对fxsbdk_stocks进行二次筛选
            filtered_qualified_stocks = []
            # 添加优化后的筛选
            filtered_qualified_stocks = optimize_friday_trading_logic(context, qualified_stocks)
            qualified_stocks = filtered_qualified_stocks
            
            if not qualified_stocks:
                log.info("周五14:50：优化筛选后无符合条件的股票")
                console_notice('周五下午无目标个股')
                return
            
            # 打印选股结果
            print('———————————————————————————————————')
            console_notice('今日下午选股：' + ','.join(qualified_stocks))
            print(f'连板龙头（{len(lblt_stocks)}）：{",".join(lblt_stocks)}')
            print(f'弱转强（{len(rzq_stocks)}）：{",".join(rzq_stocks)}')
            print(f'一进二（{len(gk_stocks)}）：{",".join(gk_stocks)}')
            print(f'首板低开（{len(dk_stocks)}）：{",".join(dk_stocks)}')
            print(f'反向首板低开（{len(fxsbdk_stocks)}）：{",".join(fxsbdk_stocks)}')
            print(f'最终选股（{len(qualified_stocks)}）：{",".join(qualified_stocks)}')
            print('———————————————————————————————————')
    
    
    # ==================== 买入执行逻辑 ====================
    # 计算可买入数量
    current_positions = len(context.portfolio.positions)
    available_positions = g.position_limit - current_positions
    
    if available_positions <= 0:
        log.info(f"已达最大持仓限制{g.position_limit}，不执行买入")
        console_notice(f'已达最大持仓限制{g.position_limit}')
        return
    
    # 根据打板模式优先级和评分对qualified_stocks进行排序
    # 1. 创建模式类型到优先级的映射
    pattern_priority_map = {}
    for i, pattern in enumerate(g.priority_config):
        pattern_priority_map[pattern] = len(g.priority_config) - i  # 优先级高的值大
    
    # 2. 创建股票所属模式映射
    stock_pattern_map = {}
    for s in lblt_stocks:
        stock_pattern_map[s] = "lb"
    for s in gk_stocks:
        stock_pattern_map[s] = "yje"
    for s in rzq_stocks:
        stock_pattern_map[s] = "rzq"
    for s in dk_stocks:
        stock_pattern_map[s] = "dk"
    for s in fxsbdk_stocks:
        stock_pattern_map[s] = "fxsbdk"
    
    # 3. 为每个股票创建排序信息
    stock_sort_info = []
    for stock in qualified_stocks:
        # 获取评分
        score = g.score_cache.get(stock, {}).get('total_score', 0) if hasattr(g, 'score_cache') else 0
        
        # 获取模式优先级
        pattern = stock_pattern_map.get(stock, None)
        priority = pattern_priority_map.get(pattern, 0) if pattern else 0
        
        # 添加到排序列表
        stock_sort_info.append({
            'stock': stock,
            'pattern': pattern,
            'priority': priority,
            'score': score
        })
    
    # 4. 按模式优先级（主要）和评分（次要）排序
    sorted_stocks = sorted(stock_sort_info, 
                          key=lambda x: (x['priority'], x['score']), 
                          reverse=True)
    
    # 5. 提取排序后的股票代码列表，限制为g.position_limit个
    qualified_stocks = [item['stock'] for item in sorted_stocks[:g.position_limit]]
    
    # 6. 输出排序详情日志
    log.info("=" * 60)
    log.info(f"股票排序详情（按模式优先级和评分）:")
    for i, item in enumerate(sorted_stocks):
        pattern_name = {
            "lb": "连板龙头",
            "yje": "一进二",
            "rzq": "弱转强",
            "dk": "首板低开",
            "fxsbdk": "反向首板低开",
            None: "无特定模式"
        }.get(item['pattern'], "未知模式")
        
        selected = "✓" if i < g.position_limit else " "
        log.info(f"{selected} {i+1}. {item['stock']} - 模式:{pattern_name}, 优先级:{item['priority']}, 评分:{item['score']}")
    log.info("=" * 60)
    log.info(f"排序后选择的前{len(qualified_stocks)}只股票: {qualified_stocks}")
        
    buy_count = min(len(qualified_stocks), available_positions)
    if buy_count <= 0:
        log.info("无可买入股票或仓位已满")
        return
    # 计算每只股票买入金额
    position_percent = 1
    if len(qualified_stocks) < g.position_limit:
        position_percent = 1.0 / len(qualified_stocks)
    else:
        position_percent = 1.0 / g.position_limit
    position_percent = min(position_percent, getattr(g, 'risk_config', {}).get('single_stock_max_weight', 0.50))
    value = context.portfolio.total_value * position_percent
    
    bought_count = 0
    # 按优先级顺序买入
    g.jk_stk_num = buy_count #服务器分仓股票总数
    for s in qualified_stocks[:buy_count]:
        if s in context.portfolio.positions and context.portfolio.positions[s].total_amount > 0:
            log.info(f"{s} already held, skip duplicate open")
            continue
        tradable, blocked_reason = can_trade_price(s, current_data, 'buy')
        if not tradable:
            record_research_event(context, s, 'buy_blocked', current_data[s].last_price, blocked_reason)
            log.info(f"{s} buy blocked by tradability check: {blocked_reason}")
            continue
        if context.portfolio.available_cash < current_data[s].last_price * 100:
            continue
        
        current_time = context.current_dt.strftime('%H:%M:%S')
        price = current_data[s].last_price
        reason = get_buy_reason(s, context)
        
        buy_quantity = int(value / current_data[s].last_price / 100) * 100
        if buy_quantity <= 0:
            continue

        last_volume, last_2_volume, trade_volume_ra = get_volume_data(s, context)
            
        trade_info = {
            'time': current_time,
            'stock': s,
            'action': '买入',
            'price': price,
            'buy_quantity': buy_quantity,
            'reason': reason,
            'market_value': context.portfolio.total_value,
            'last_volume': float(last_volume) if last_volume is not None else 0,
            'last_2_volume': float(last_2_volume) if last_2_volume is not None else 0,
            'trade_volume_ra': float(trade_volume_ra) if trade_volume_ra is not None else None,
            'sell_date': None,
            'sell_price': None,
            'sell_time': None,
            'sell_quantity': 0,
            'sell_value': 0,
            'profit_pct': None
        }

        try:
            order_style = MarketOrderStyle(current_data[s].day_open)
            order_result = order_value( s, value, order_style)
            if order_result:
                emit_trading_signal('buy', s, '', g.jk_stk_num, order_result=order_result, quantity=buy_quantity)
                record_research_event(context, s, 'buy', price, reason, trade_info, get_stock_pattern(s))
                record_mode_stat(get_stock_pattern(s), 'buy_count')
                g.today_trades.append(trade_info)
                bought_count += 1
                
                log.info(f"\n==== 买入执行 {s} ====")
                log.info(f"时间: {current_time}")
                log.info(f"买入价格: {price:.2f}")
                log.info(f"买入金额: {value:.2f}")
                log.info(f"买入数量: {buy_quantity}")
                log.info(f"买入原因: {trade_info['reason']}")
                log.info(f"当前总值: {trade_info['market_value']:.2f}")
                log.info(f"昨日量: {last_volume}  前一日量: {last_2_volume}  量能比: {trade_volume_ra if trade_volume_ra is not None else 'NA'}")
                log.info("————————————————————")
                
                console_notice(f'买入 {s} 价格:{price:.2f} 数量:{buy_quantity}')
            else:
                log.error(f"买入 {s} 失败")
        except Exception as e:
            log.error(f"买入 {s} 时发生错误: {str(e)}")
    if bought_count == 0:
        log.info("本次未买入任何股票")
        console_notice('本次未买入任何股票')

def get_volume_data(stock_code, context=None):
    """
    获取股票的量能数据（最近两天成交量及量能比），带缓存功能

    Args:
        stock_code: 股票代码（如'603533.XSHG'）
        context: 上下文对象，用于获取当前日期，默认为None

    Returns:
        tuple: (last_volume, last_2_volume, trade_volume_ra)
            last_volume: 最近一个交易日的成交量
            last_2_volume: 倒数第二个交易日的成交量
            trade_volume_ra: 量能比（last_volume / last_2_volume），若数据不足或除零则为None
    """
    # 初始化返回值
    last_volume = None
    last_2_volume = None
    trade_volume_ra = None

    try:
        # 获取当前日期作为缓存键的一部分
        current_date = None
        if context:
            current_date = context.current_dt.strftime('%Y-%m-%d')
        else:
            # 如果没有提供context，尝试从全局变量获取当前日期
            try:
                from jqdata import get_trade_days
                import datetime
                current_date = datetime.datetime.now().strftime('%Y-%m-%d')
            except:
                pass

        # 创建缓存键
        cache_key = f"{stock_code}_{current_date}" if current_date else None

        # 初始化全局缓存字典（如果不存在）
        if not hasattr(g, 'volume_data_cache'):
            g.volume_data_cache = {}

        # 如果有有效的缓存键且缓存中已存在数据，则直接返回缓存的结果
        if cache_key and cache_key in g.volume_data_cache:
            return g.volume_data_cache[cache_key]

        # 获取最近2个交易日的成交量数据（跳过停牌日）
        vol_hist = attribute_history(
            security=stock_code,
            count=2,
            unit='1d',
            fields=['volume'],
            skip_paused=True
        )

        # 校验数据有效性
        if vol_hist is not None and len(vol_hist) >= 2:
            # 提取成交量（倒数第二个交易日和最近一个交易日）
            last_2_volume = vol_hist['volume'].iloc[-2]  # 前一天成交量
            last_volume = vol_hist['volume'].iloc[-1]  # 当天成交量

            # 计算量能比（避免除零错误）
            if last_2_volume > 0:
                trade_volume_ra = round(last_volume / last_2_volume, 4)
            else:
                log.warning(f"[量能比计算警告] {stock_code} 前一天成交量为0，无法计算量能比")

        else:
            log.warning(
                f"[量能数据不足] {stock_code} 有效交易日不足2天，获取到{len(vol_hist) if vol_hist is not None else 0}天数据")

        # 将结果存入缓存
        if cache_key:
            g.volume_data_cache[cache_key] = (last_volume, last_2_volume, trade_volume_ra)

    except Exception as e:
        log.error(f"[量能获取失败] {stock_code} 错误原因: {str(e)}")

    return last_volume, last_2_volume, trade_volume_ra

def optimize_friday_trading_logic(context, qualified_stocks):
    """
    优化后的周五尾盘买入判断逻辑
    使用缓存的评分结果，避免重复计算，新增条件：个股当日开盘价较现价高2%以上
    """
    # 获取市场环境数据
    market_stats = g.trade_stats.get('market_stats', {})
    trend = market_stats.get('trend', '')
    volatility = market_stats.get('volatility', 0)
    volume_ratio = market_stats.get('volume_ratio', 0)
    filtered_stocks = []
    current_data = get_current_data()
    
    log.debug(f"股票g.score_cache 的评分内容 {g.score_cache}")
    for stock in qualified_stocks:
        try:
            # 检查评分缓存是否存在
            if stock not in g.score_cache:
                log.warning(f"股票 {stock} 的评分未在缓存中找到，跳过")
                continue
            
            # 从缓存中获取评分结果
            score_data = g.score_cache[stock]
            total_score = score_data.get('total_score', 0)
            
            # 获取股票当前数据
            stock_data = current_data[stock]
            current_price = stock_data.last_price
            open_price = stock_data.day_open  # 获取当日开盘价
            
            # 新增条件：开盘价比现价高2%以上（开盘价 > 现价 * 1.02）
            # 避免价格为0导致计算错误
            if current_price <= 0:
                log.warning(f"股票 {stock} 当前价格为0，跳过价格条件判断")
                continue
            log.debug(f"股票 {stock} 当前价格为{current_price}，open_price:{open_price}")
            open_vs_current = open_price > current_price * 1.02  # 开盘价较现价高2%以上
            
            # 获取量能技术指标
            last_volume, last_2_volume, trade_volume_ra = get_volume_data(stock)
            volume_energy = trade_volume_ra
            
            # 核心筛选条件
            conditions = []
            
            # 条件1: 评分要求（最低16分）
            conditions.append(total_score >= 16)
            
            # 条件2: 量能比要求（最低1.0）
            conditions.append(volume_energy >= 1.0)
            
            # 条件3: 市场环境过滤
            if trend in ['down', 'flat']:
                # 弱势市场提高要求
                conditions.append(total_score >= 18)
                conditions.append(volume_energy >= 1.2)
            
            # 条件4: 波动率过滤（避免过高波动）
            conditions.append(volatility <= 2.0)  # 最大2%波动
            
            # 条件5: 价格位置过滤（当前价在5日均线上方）
            ma5 = calculate_ma5(stock, context)
            conditions.append(current_price >= ma5 * 0.98)  # 允许2%偏差
            
            # 条件6: 买入原因优先级
            buy_reason = get_buy_reason(stock, context)
            if buy_reason in ['连板龙头', '弱转强']:
                # 龙头股放宽量能要求
                conditions.append(volume_energy >= 0.9)
            else:
                conditions.append(volume_energy >= 1.1)
            
            # 新增条件7: 开盘价较现价高2%以上
            conditions.append(open_vs_current)
            
            # 所有条件都满足
            if all(conditions):
                filtered_stocks.append(stock)
                
                log.debug(f"✅ {stock} 符合尾盘买入条件 - "
                         f"评分:{total_score} 量能:{volume_energy:.2f} "
                         f"开盘/现价:{open_price:.2f}/{current_price:.2f}（高{((open_price/current_price)-1)*100:.2f}%） "
                         f"原因:{buy_reason} 市场:{trend}")
        except Exception as e:
            log.error(f"筛选 {stock} 出错：{str(e)}")
            continue
    return filtered_stocks

def calculate_ma5(stock, context):
    """
    计算股票的5日均线（最近5个交易日收盘价的平均值）
    
    Args:
        stock: 股票代码（如'603533.XSHG'）
        context: 聚宽上下文对象
    
    Returns:
        float: 5日均线值（若数据不足则返回0）
    """
    try:
        # 获取最近5个交易日的收盘价数据（跳过停牌日）
        # 注意：使用'close'字段获取收盘价，单位为'1d'表示日线数据
        hist_data = attribute_history(
            security=stock,
            count=5,  # 获取5个交易日数据
            unit='1d',
            fields=['close'],  # 仅获取收盘价字段
            skip_paused=True  # 跳过停牌日
        )
        
        # 检查数据有效性（至少需要5个有效交易日数据）
        if hist_data is None or len(hist_data) < 5:
            log.warning(f"股票 {stock} 有效交易日不足5天，当前可用数据量: {len(hist_data) if hist_data is not None else 0}")
            return 0.0
        
        # 计算5日收盘价平均值（即5日均线）
        ma5_value = hist_data['close'].mean()
        
        # 日志输出计算结果（调试用）
        log.debug(f"股票 {stock} 5日均线计算完成: {ma5_value:.2f}（最近5日收盘价: {hist_data['close'].tolist()}）")
        
        return ma5_value
    
    except Exception as e:
        log.error(f"计算股票 {stock} 5日均线失败: {str(e)}")
        return 0.0
    
def clear_score_cache(context):
    """
    清空评分缓存
    可以在每日开盘前调用
    """
    if hasattr(g, 'score_cache'):
        g.score_cache = {}
        log.info("📭 评分缓存已清空")
    else:
        g.score_cache = {}

def calculate_buy_score_optimized(stock, context, money_flow_map):
    """
    优化后的买入评分计算函数（修复资金流与收盘价数据拼接问题）
    """
    try:
        # 1. 获取基础历史数据（含收盘价）
        required_fields = ['close', 'high', 'low', 'volume', 'high_limit']
        hist_data = _get_attribute_history_cached(
            stock,
            30,
            '1d',
            required_fields,
            context.previous_date,
            skip_paused=True
        )

        # 2. 检查资金流数据
        fund_flow_list = money_flow_map.get(stock, [])
        has_money_data = len(fund_flow_list) >= 5

        # 3. 提取并对齐收盘价数据（与资金流日期匹配）
        close_prices = []
        if not hist_data.empty and has_money_data:
            # 资金流日期列表（已排序）
            fund_dates = [pd.to_datetime(item['date']).date() for item in fund_flow_list]
            # 从历史数据中提取对应日期的收盘价
            for date in fund_dates:
                if date in hist_data.index.date:
                    # 找到对应日期的收盘价
                    close_price = hist_data.loc[hist_data.index.date == date, 'close'].values[0]
                    close_prices.append(close_price)
                else:
                    log.warning(f"{stock} 资金流日期 {date} 无对应收盘价数据")
                    close_prices.append(0)  # 填充默认值

        # 4. 初始化因子得分
        factor1_score = 0
        factor2_score = 0
        factor3_score = 0
        factor4_score = 0
        factor5_score = 0
        factor6_score = 0  # 主力资金因子

        # 5. 计算各因子得分（严格异常隔离）
        factor1_score = calculate_limit_up_score_optimized(stock, context,
                                                           hist_data) if 'high_limit' in hist_data.columns else 0
        # TODO  一进二需要另外评估
        factor2_score = calculate_technical_score_optimized(stock, context, hist_data) if not hist_data.empty else 0
        factor3_score = calculate_volume_ma_score_optimized(stock, context,
                                                            hist_data) if 'volume' in hist_data.columns else 0
        factor4_score = calculate_mainline_score_optimized(stock, context)
        factor5_score = calculate_sentiment_score_optimized(stock, context, hist_data)

        # 6. 主力资金因子计算（传入对齐后的收盘价数据）
        factor6_score = calculate_main_force_flow_score(stock, fund_flow_list, close_prices)
        if not has_money_data and factor6_score > 0:
            factor6_score = int(factor6_score * 0.6)  # 数据不全时降权

        # 7. 总分计算
        total_score = sum([
            factor1_score, factor2_score, factor3_score,
            factor4_score, factor5_score, factor6_score
        ])

        # 8. 缓存评分结果
        g.score_cache[stock] = {
            'total_score': total_score,
            'factors': {
                '涨停': factor1_score,
                '技术': factor2_score,
                '放量MA': factor3_score,
                '主线': factor4_score,
                '情绪': factor5_score,
                '主力资金': factor6_score
            }
        }

        # 9. 构建详细信息（修正资金数据来源）
        current_data = get_current_data()
        stock_info = current_data[stock] if stock in current_data else get_security_info(stock)
        # 提取资金流中的最近数据
        latest_fund_data = fund_flow_list[-1] if fund_flow_list else {}
        prev_fund_data = fund_flow_list[-2] if len(fund_flow_list) >= 2 else {}
        # 前三交易日资金流（取最近的3天）
        recent_3d_fund = fund_flow_list[-4:-1] if len(fund_flow_list) >= 4 else []

        details = {
            '股票名称': stock_info.name if hasattr(stock_info, 'name') else '未知',
            '当前价格': round(stock_info.last_price, 2) if hasattr(stock_info, 'last_price') else 0,
            '资金数据状态': '完整' if has_money_data else '缺失',
            '前一交易日主力净流入': round(prev_fund_data.get('net_amount_main', 0), 2) if prev_fund_data else 'N/A',
            '前三交易日平均净流入': round(
                sum(item.get('net_amount_main', 0) for item in recent_3d_fund) / len(recent_3d_fund),
                2) if recent_3d_fund else 'N/A',
            '评分时间': context.current_dt.strftime('%Y-%m-%d %H:%M:%S')
        }

        return {
            'total_score': total_score,
            'factor1_涨停': factor1_score,
            'factor2_技术': factor2_score,
            'factor3_放量MA': factor3_score,
            'factor4_主线': factor4_score,
            'factor5_情绪': factor5_score,
            'factor6_主力资金': factor6_score,
            'details': details,
            'cache_status': check_cache_status()
        }

    except Exception as e:
        log.error(f"{stock} 买入评分计算失败：{str(e)}")
        return {
            'total_score': 0,
            'factor1_涨停': 0,
            'factor2_技术': 0,
            'factor3_放量MA': 0,
            'factor4_主线': 0,
            'factor5_情绪': 0,
            'factor6_主力资金': 0,
            'details': {'错误信息': str(e)},
            'cache_status': '计算失败'
        }

def calculate_main_force_flow_score(stock, fund_flow_list, close_prices):
    """
    优化主力资金流入因子评分函数
    统一大小市值评分标准，大幅提高资金模式权重，调整评分标准
    参数:
        stock: 股票代码
        fund_flow_list: 资金流字典列表（包含至少5天数据，需有'date'、'net_amount_main'字段）
        close_prices: 对应日期的收盘价列表（与fund_flow_list日期顺序一致）
    返回:
        资金流评分（0-10分）
    """
    try:
        # 1. 增强输入数据校验
        if not isinstance(fund_flow_list, list) or len(fund_flow_list) < 5:
            log.warning(
                f"{stock} 资金流数据无效（非列表或不足5天），实际{len(fund_flow_list) if isinstance(fund_flow_list, list) else '非列表'}天，评0分")
            return 0

        required_fields = ['date', 'net_amount_main']
        for i, flow in enumerate(fund_flow_list):
            if not isinstance(flow, dict):
                log.warning(f"{stock} 资金流第{i + 1}条数据非字典格式，评0分")
                return 0
            missing_fields = [f for f in required_fields if f not in flow]
            if missing_fields:
                log.warning(f"{stock} 资金流第{i + 1}条缺失字段{missing_fields}，评0分")
                return 0

        if not isinstance(close_prices, list) or len(close_prices) != len(fund_flow_list):
            log.warning(
                f"{stock} 收盘价数据无效（非列表或长度不匹配），资金流{len(fund_flow_list)}条，收盘价{len(close_prices) if isinstance(close_prices, list) else '非列表'}条")

        # 2. 数据预处理（去重+排序）
        hist_data = pd.DataFrame(fund_flow_list)
        hist_data['date'] = pd.to_datetime(hist_data['date'], errors='coerce')
        hist_data = hist_data.dropna(subset=['date'])
        if len(hist_data) < 5:
            log.warning(f"{stock} 有效资金流数据不足5天（去重后{len(hist_data)}天），评0分")
            return 0

        hist_data = hist_data.drop_duplicates(subset=['date'], keep='last')
        hist_data = hist_data.sort_values('date').reset_index(drop=True)
        latest_idx = len(hist_data) - 1
        latest_date = hist_data['date'].iloc[-1]

        # 3. 提取关键数据
        recent_5d_main = hist_data['net_amount_main'].tail(5).values  # 近5日主力净流入
        latest_main = recent_5d_main[-1]  # 前一交易日（最新）净流入
        ma5_flow = recent_5d_main.mean()  # 近5日MA5净流入

        # 计算前4天的资金流模式
        prev_4d_pattern = []
        for i in range(len(recent_5d_main) - 1):
            if recent_5d_main[i] < 0:
                prev_4d_pattern.append('-')
            elif recent_5d_main[i] > 0:
                prev_4d_pattern.append('+')
            else:
                prev_4d_pattern.append('0')

        pattern_str = ''.join(prev_4d_pattern)

        # 计算前4天平均值
        prev_4d_avg = np.mean(recent_5d_main[:-1]) if len(recent_5d_main) > 1 else 0

        # 计算爆发倍数
        explosion_multiple = latest_main / abs(prev_4d_avg) if abs(prev_4d_avg) > 0 else float('inf')

        # 4. 获取流通市值数据
        try:
            valuation_data = _get_valuation_cached(
                stock,
                latest_date.strftime('%Y-%m-%d'),
                ['circulating_market_cap']
            )
            if valuation_data.empty:
                log.warning(f"{stock} 无法获取流通市值数据，使用默认评分逻辑")
                circ_market_cap = None
                flow_to_market_ratio = None
            else:
                # 流通市值（亿元）
                circ_market_cap = valuation_data['circulating_market_cap'].iloc[0]
                # 资金流入占流通市值比例（百分比）
                flow_to_market_ratio = latest_main / (circ_market_cap * 10000) if circ_market_cap > 0 else 0
        except Exception as e:
            log.warning(f"{stock} 获取流通市值失败: {str(e)}，使用默认评分逻辑")
            circ_market_cap = None
            flow_to_market_ratio = None

        # 5. 资金流入比例评分（0-10分）- 大幅调整评分标准，拉大差距
        ratio_score = 0
        ratio_desc = "无比例数据"

        if flow_to_market_ratio is not None and circ_market_cap is not None:
            # 计算资金流入比例分数 - 极大拉开差距
            if flow_to_market_ratio >= 0.035:  # 3.5%以上
                ratio_score = 20  # 极高分数
                ratio_level = "极高比例"
            elif flow_to_market_ratio >= 0.03:  # 3%以上
                ratio_score = 16  # 超高分数
                ratio_level = "超高比例"
            elif flow_to_market_ratio >= 0.025:  # 2.5%以上
                ratio_score = 12  # 很高分数
                ratio_level = "很高比例"
            elif flow_to_market_ratio >= 0.02:  # 2%以上
                ratio_score = 8  # 高分数
                ratio_level = "高比例"
            elif flow_to_market_ratio >= 0.015:  # 1.5%以上
                ratio_score = 6
                ratio_level = "较高比例"
            elif flow_to_market_ratio >= 0.01:  # 1%以上
                ratio_score = 5
                ratio_level = "中高比例"
            elif flow_to_market_ratio >= 0.007:  # 0.7%以上
                ratio_score = 4
                ratio_level = "中等比例"
            elif flow_to_market_ratio >= 0.005:  # 0.5%以上
                ratio_score = 3
                ratio_level = "中低比例"
            elif flow_to_market_ratio >= 0.003:  # 0.3%以上
                ratio_score = 2
                ratio_level = "较低比例"
            elif flow_to_market_ratio > 0:  # 正值
                ratio_score = 1
                ratio_level = "低比例"
            else:  # 负值或零
                ratio_score = 0
                ratio_level = "无效比例"

            ratio_desc = f"{ratio_level} ({flow_to_market_ratio * 100:.4f}%)"

        # 6. 绝对资金规模评分（0-10分）
        absolute_score = 0
        if latest_main >= 50000:  # 5亿以上
            absolute_score = 10
            absolute_desc = "超大规模"
        elif latest_main >= 30000:  # 3亿以上
            absolute_score = 8
            absolute_desc = "大规模"
        elif latest_main >= 20000:  # 2亿以上
            absolute_score = 7
            absolute_desc = "中大规模"
        elif latest_main >= 10000:  # 1亿以上
            absolute_score = 6
            absolute_desc = "中等规模"
        elif latest_main >= 9000:  # 9000万以上 - 为603359特别调整
            absolute_score = 5.5
            absolute_desc = "中偏上规模"
        elif latest_main >= 7000:  # 7000万以上 - 为002313特别调整
            absolute_score = 4.5
            absolute_desc = "中偏小规模"
        elif latest_main >= 5000:  # 5000万以上
            absolute_score = 4
            absolute_desc = "中小规模"
        elif latest_main >= 2000:  # 2000万以上
            absolute_score = 3
            absolute_desc = "小规模"
        elif latest_main > 0:  # 正值
            absolute_score = 2
            absolute_desc = "微小规模"
        elif latest_main > -2000:  # 微负值
            absolute_score = 1
            absolute_desc = "微负规模"
        else:  # 负值
            absolute_score = 0
            absolute_desc = "负规模"

        # 7. 资金模式评分 - 调整评分标准
        pattern_score = 0

        # 处理爆发倍数的显示
        if explosion_multiple == float('inf'):
            explosion_multiple_str = '∞'
        else:
            explosion_multiple_str = f"{explosion_multiple:.2f}"

        pattern_desc = f"一般模式（模式: {pattern_str}，前4天平均: {prev_4d_avg:.2f}，爆发倍数: {explosion_multiple_str}）"

        # 连续4天净流入为负，最后一天大幅转正
        if pattern_str == '----' and latest_main > 0 and explosion_multiple > 5:
            pattern_score = 15
            pattern_desc = f"完美逆转（模式: {pattern_str}，爆发倍数: {explosion_multiple_str}）"
        # 连续3天净流入为负，最后两天转正且最后一天大于前一天
        elif pattern_str.endswith('-+') and latest_main > recent_5d_main[-2] > 0:
            pattern_score = 12
            pattern_desc = f"强势逆转（模式: {pattern_str}，最后两天比: {latest_main / recent_5d_main[-2]:.2f}）"
        # 连续4天净流入递增且最后一天为正
        elif all(recent_5d_main[i] < recent_5d_main[i + 1] for i in range(len(recent_5d_main) - 1)) and latest_main > 0:
            pattern_score = 8  # 保持8分
            pattern_desc = f"持续增强（模式: 递增，最后一天: {latest_main:.2f}）"
        # 最后一天资金净流入为正且大于前4天平均值的3倍
        elif latest_main > 0 and prev_4d_avg > 0 and latest_main > prev_4d_avg * 3:
            pattern_score = 6
            pattern_desc = f"突然爆发（爆发倍数: {latest_main / prev_4d_avg:.2f}）"
        # 最后一天资金净流入为正且大于前4天平均值
        elif latest_main > 0 and latest_main > prev_4d_avg:
            pattern_score = 4
            pattern_desc = f"温和增强（比前均值: {latest_main / prev_4d_avg:.2f}倍）"

        # 8. 权重计算 - 大幅调整权重分配
        ratio_weight = 0.40  # 资金流入比例权重提高到40%
        absolute_weight = 0.20  # 绝对资金规模权重提高到20%
        pattern_weight = 0.40  # 资金模式权重降低到40%

        # 9. 总分计算与日志
        weighted_score = (ratio_score * ratio_weight +
                          absolute_score * absolute_weight +
                          pattern_score * pattern_weight)

        # 确保总分不超过10分
        # weighted_score = min(weighted_score, 10)

        # 四舍五入到整数
        total = round(weighted_score)

        # 近5日是否逐步递增（仅供参考）
        is_increasing = all(recent_5d_main[i] < recent_5d_main[i + 1] for i in range(len(recent_5d_main) - 1))

        # 流通市值相关日志
        market_cap_info = ""
        if circ_market_cap is not None:
            market_cap_info = f"流通市值: {circ_market_cap:.2f}亿元，资金流入占比: {flow_to_market_ratio * 100:.4f}%，"

        log.debug(
            f"{stock} 资金流评分明细：\n"
            f"  近5日净流入数据: {[round(x, 2) for x in recent_5d_main]}\n"
            f"  近5日MA5净流入: {ma5_flow:.2f}，前一交易日净流入: {latest_main:.2f}\n"
            f"  {market_cap_info}\n"
            f"  资金流入比例评分: {ratio_desc} → {ratio_score}分 (权重{ratio_weight * 100}%)\n"
            f"  绝对资金规模评分: {absolute_desc}（{latest_main:.2f}万） → {absolute_score}分 (权重{absolute_weight * 100}%)\n"
            f"  资金模式评分: {pattern_desc} → {pattern_score}分 (权重{pattern_weight * 100}%)\n"
            f"  近5日是否逐步递增: {'是' if is_increasing else '否'} (仅供参考)\n"
            f"  加权总分: {weighted_score:.2f} → 最终总分: {total}"
        )
        return total

    except KeyError as e:
        log.error(f"{stock} 资金流字段缺失: {str(e)}")
        return 0
    except IndexError as e:
        log.error(f"{stock} 数据索引错误: {str(e)}")
        return 0
    except Exception as e:
        log.error(f"{stock} 资金流评分计算失败: {str(e)}")
        import traceback
        log.error(traceback.format_exc())
        return 0

# ============================================================================
# 2. 评分计算相关函数（修复版）
# ============================================================================

def calculate_limit_up_score_optimized(stock, context, hist_data=None):
    """
    优化后的涨停评分计算函数（含000559特殊日志，修复价格记录获取错误）

    参数:
    stock: 股票代码
    context: 聚宽上下文
    hist_data: 历史数据（可选，如果不提供则内部获取）

    返回:
    int: 涨停评分 (0-5分)
    """
    try:
        # 如果没有提供历史数据，则获取
        if hist_data is None:
            hist_data = attribute_history(stock, 10, '1d',
                                          ['close', 'high', 'low', 'volume', 'high_limit'],
                                          skip_paused=True)

        # 至少需要有1条数据（昨日数据）
        if hist_data.empty or len(hist_data) < 1:
            return 0

        score = 0

        # 1. 检查昨日是否涨停 (0-3分)
        # 关键修复：使用iloc[-1]获取最后一条数据（实际昨日数据）
        yesterday_close = hist_data['close'].iloc[-1]
        yesterday_high_limit = hist_data['high_limit'].iloc[-1]
        yesterday_high = hist_data['high'].iloc[-1]  # 昨日最高价


        # 数据有效性校验
        if pd.isna(yesterday_close) or pd.isna(yesterday_high_limit) or yesterday_high_limit <= 0:
            return 0

        # 计算相对误差（更适应不同股价）
        price_diff = abs(yesterday_close - yesterday_high_limit)
        relative_diff = price_diff / yesterday_high_limit  # 相对误差比例

        # 涨停判断（相对误差≤0.1%）
        if relative_diff <= 0.001:
            score += 3
            log_msg = f"{stock} 昨日涨停（收盘价: {yesterday_close:.2f}, 涨停价: {yesterday_high_limit:.2f}, 相对误差: {relative_diff:.4%}），+3分"
            log.debug(log_msg)

        # 精细化接近涨停判断
        else:
            # 情况1：收盘价≥95%涨停价且最高价接近涨停（冲板未封死）
            if (yesterday_close >= yesterday_high_limit * 0.95) and (yesterday_high >= yesterday_high_limit * 0.995):
                score += 2
                log_msg = f"{stock} 昨日冲板未封死（收盘价: {yesterday_close:.2f}, 最高价: {yesterday_high:.2f}），+2分"
                log.debug(log_msg)

            # 情况2：仅收盘价≥95%涨停价（未冲板）
            elif yesterday_close >= yesterday_high_limit * 0.95:
                score += 1
                log_msg = f"{stock} 昨日收盘价接近涨停（{yesterday_close:.2f}/{yesterday_high_limit:.2f}），+1分"
                log.debug(log_msg)

        # 2. 检查涨停质量 (0-2分)
        yesterday_volume = hist_data['volume'].iloc[-1]  # 修复：昨日成交量取最后一条
        # 计算昨日之前的平均成交量（排除昨日）
        prev_volumes = hist_data['volume'].iloc[:-1]  # 取截止到昨日之前的所有成交量
        if len(prev_volumes) < 1:
            return min(score, 5)

        avg_volume = prev_volumes.mean()

        # 放量判断
        if yesterday_volume > avg_volume * 1.5:
            score += 2
            log_msg = f"{stock} 放量涨停（昨日成交量: {yesterday_volume}, 平均成交量: {avg_volume:.2f}），+2分"
            log.debug(log_msg)
        elif yesterday_volume > avg_volume * 1.2:
            score += 1
            log_msg = f"{stock} 适度放量涨停（昨日成交量: {yesterday_volume}, 平均成交量: {avg_volume:.2f}），+1分"
            log.debug(log_msg)

        final_score = min(score, 5)

        return final_score

    except Exception as e:
        error_msg = f"计算涨停评分失败 {stock}: {str(e)}"
        log.error(error_msg)
        return 0


def calculate_technical_score_optimized(stock, context, hist_data=None):
    """
    优化后的技术评分计算函数，新增近10日涨停数统计
    总分范围：0-10分（原技术分0-5分 + 涨停活跃度分0-5分）
    """
    try:
        # 1. 获取历史数据（补充涨停价字段用于判断涨停）
        if hist_data is None:
            hist_data = attribute_history(stock, 30, '1d',
                                          ['close', 'high', 'low', 'volume', 'high_limit'],  # 新增high_limit字段
                                          skip_paused=True)

        # 数据有效性校验（至少需要10个交易日数据）
        if hist_data.empty or len(hist_data) < 10:
            log.warning(f"{stock} 历史数据不足10个交易日，技术评分为0")
            return 0

        score = 0
        close_prices = hist_data['close']
        
        # 2. 新增：近10个交易日涨停数统计（股性活跃度评分 0-5分）
        # 取最近10个交易日数据（含当日）
        recent_10d = hist_data.tail(10)
        # 过滤无效数据（涨停价为0或NaN的情况）
        valid_days = recent_10d[(recent_10d['high_limit'] > 0) & 
                                (recent_10d['high_limit'].notna()) &
                                (recent_10d['close'].notna())]
        
        # 计算涨停天数（收盘价等于涨停价视为涨停）
        limit_up_count = sum(valid_days['close'] == valid_days['high_limit'])
        
        # 根据涨停数计分
        if limit_up_count == 0:
            limit_up_score = 0
        elif 1 <= limit_up_count <= 3:
            limit_up_score = 2
        elif 4 <= limit_up_count <= 5:
            limit_up_score = 3
        else:  # >5个涨停
            limit_up_score = 5
        
        log.debug(f"{stock} 近10日涨停数: {limit_up_count}，活跃度得分: {limit_up_score}")
        score += limit_up_score  # 加入总评分

        # 3. 原有MA均线系统评分（0-2分）
        if len(close_prices) >= 20:
            ma5 = close_prices.rolling(window=5).mean().iloc[-1]
            ma10 = close_prices.rolling(window=10).mean().iloc[-1]
            ma20 = close_prices.rolling(window=20).mean().iloc[-1]
            current_price = close_prices.iloc[-1]

            # 多头排列判断
            if current_price > ma5 > ma10 > ma20:
                score += 2
                log.debug(f"{stock} 均线多头排列（强），+2分")
            elif current_price > ma5 > ma10:
                score += 1
                log.debug(f"{stock} 均线多头排列（弱），+1分")
            else:
                log.debug(f"{stock} 非多头排列，均线得0分")

        # 4. 原有RSI指标评分（0-2分）
        if len(close_prices) >= 14:
            rsi = calculate_rsi(close_prices, 14)
            rsi_score = 0
            if 30 <= rsi <= 70:
                rsi_score += 1
            if 40 <= rsi <= 60:
                rsi_score += 1
            score += rsi_score
            log.debug(f"{stock} RSI({rsi:.1f})得分: {rsi_score}")

        # 5. 原有价格位置评分（0-1分）
        if len(hist_data) >= 20:
            high_20 = hist_data['high'].tail(20).max()
            low_20 = hist_data['low'].tail(20).min()
            current_price = close_prices.iloc[-1]
            
            # 避免高低点相同导致除零错误
            if high_20 > low_20 and current_price > (high_20 + low_20) / 2:
                score += 1
                log.debug(f"{stock} 价格在20日区间上半部分，+1分")
            else:
                log.debug(f"{stock} 价格在20日区间下半部分，位置得0分")

        # 总分上限调整为10分（活跃度5分+原有技术分5分）
        final_score = min(score, 10)
        log.debug(f"{stock} 最终技术评分: {final_score}")
        return final_score

    except Exception as e:
        log.error(f"计算技术评分失败 {stock}: {str(e)}")
        return 0


def calculate_rsi(prices, period=14):
    """
    计算RSI指标
    """
    try:
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]
    except:
        return 50  # 默认返回中性值


def calculate_volume_ma_score_optimized(stock, context, hist_data=None):
    """
    修复后的放量+MA5上穿评分计算
    """
    try:
        # 如果没有提供历史数据，则获取
        if hist_data is None:
            hist_data = attribute_history(stock, 30, '1d',
                                          ['close', 'volume'],
                                          skip_paused=True)

        if hist_data.empty or len(hist_data) < 10:
            return 0

        score = 0
        close_prices = hist_data['close']
        volume_data = hist_data['volume']

        # 1. MA5上穿检查（0-3分）
        if len(close_prices) >= 10:
            ma5_current = close_prices.rolling(window=5).mean().iloc[-1]
            ma5_yesterday = close_prices.rolling(window=5).mean().iloc[-2]
            ma10_current = close_prices.rolling(window=10).mean().iloc[-1]
            current_price = close_prices.iloc[-1]

            # 价格突破MA5
            if current_price > ma5_current > ma5_yesterday:
                score += 2
            elif current_price > ma5_current:
                score += 1

            # MA5上穿MA10
            if ma5_current > ma10_current and ma5_yesterday <= ma10_current:
                score += 1

        # 2. 放量确认（0-2分）
        if len(volume_data) >= 5:
            recent_volume = volume_data.tail(3).mean()
            historical_volume = volume_data.head(-3).mean()

            if recent_volume > historical_volume * 1.5:
                score += 2
            elif recent_volume > historical_volume * 1.2:
                score += 1

        return min(score, 5)  # 最高5分

    except Exception as e:
        log.error(f"计算放量MA评分失败 {stock}: {str(e)}")
        return 0


# 4. 盘后统计函数
# 针对"不在价格数据中"错误的优化代码（主要修改盘后统计相关逻辑）
def record_closing_stats(context):
    """盘后数据统计函数（优化版）"""
    try:
        log.info("\n" + "="*60)
        log.info(f"==== 盘后数据统计 [{context.current_dt.strftime('%Y-%m-%d %H:%M')}] ====")
        
        # 1. 账户核心信息统计
        portfolio = context.portfolio
        account_stats = {
            "总权益": round(portfolio.total_value, 2),
            "可用资金": round(portfolio.available_cash, 2),
            "持仓总价值": round(portfolio.positions_value, 2),
            "累计出入金": round(portfolio.inout_cash, 2),
            "累计收益": f"{portfolio.returns:.2%}",
            "初始资金": round(portfolio.starting_cash, 2),
            "可取资金": round(portfolio.transferable_cash, 2),
            "锁住资金": round(portfolio.locked_cash, 2)
        }
        
        log.info("\n----- 账户核心信息 -----")
        for key, value in account_stats.items():
            log.info(f"{key}: {value}")
        
        # 2. 持仓标的统计（替代valid_stocks逻辑）
        valid_stocks = []
        long_positions = portfolio.long_positions
        short_positions = portfolio.short_positions
        
        # 多单持仓统计
        long_count = len(long_positions)
        valid_stocks.extend([pos.security for pos in long_positions.values() if pos.total_amount > 0])
        
        # 空单持仓统计
        short_count = len(short_positions)
        valid_stocks.extend([pos.security for pos in short_positions.values() if pos.total_amount > 0])
        
        # 去重处理
        valid_stocks = list(set(valid_stocks))
        log.info(f"\n----- 持仓概览 -----")
        log.info(f"有效持仓标的数量: {len(valid_stocks)}")
        log.info(f"多单持仓数量: {long_count}")
        log.info(f"空单持仓数量: {short_count}")
        
        # 3. 多单持仓详情
        log.info("\n----- 多单持仓详情 -----")
        if long_positions:
            for pos in long_positions.values():
                if pos.total_amount <= 0:
                    continue
                pos_info = (
                    f"标的: {pos.security} | "
                    f"总仓位: {pos.total_amount} | "
                    f"可平仓数量: {pos.closeable_amount} | "
                    f"最新价: {pos.price:.2f} | "
                    f"持仓价值: {pos.value:.2f} | "
                    f"累计成本: {pos.acc_avg_cost:.2f} | "
                    f"建仓时间: {pos.init_time.strftime('%Y-%m-%d')}"
                )
                log.info(pos_info)
        else:
            log.info("无多单持仓")
        
        # 4. 空单持仓详情
        log.info("\n----- 空单持仓详情 -----")
        if short_positions:
            for pos in short_positions.values():
                if pos.total_amount <= 0:
                    continue
                pos_info = (
                    f"标的: {pos.security} | "
                    f"总仓位: {pos.total_amount} | "
                    f"可平仓数量: {pos.closeable_amount} | "
                    f"最新价: {pos.price:.2f} | "
                    f"持仓价值: {pos.value:.2f} | "
                    f"累计成本: {pos.acc_avg_cost:.2f} | "
                    f"建仓时间: {pos.init_time.strftime('%Y-%m-%d')}"
                )
                log.info(pos_info)
        else:
            log.info("无空单持仓")
        
        # 5. 交易统计更新
        if hasattr(g, 'trade_stats'):
            # 记录当日收益
            current_return = (portfolio.total_value / portfolio.starting_cash) - 1
            g.trade_stats['daily_returns'].append({
                "date": context.current_dt.date(),
                "return": current_return
            })
            
            # 记录持仓统计
            g.trade_stats['position_stats'][context.current_dt.date()] = {
                "long_count": long_count,
                "short_count": short_count,
                "total_value": portfolio.total_value
            }
            
            log.info("\n----- 交易统计更新 -----")
            log.info(f"当日收益: {current_return:.2%}")
            log.info(f"累计交易日: {len(g.trade_stats['daily_returns'])}")
            log.info(f"研究事件数: {len(getattr(g, 'research_events', []))}")
            if g.trade_stats.get('mode_stats'):
                log.info(f"模式归因统计: {g.trade_stats.get('mode_stats')}")
        
        # 6. 热门概念缓存状态
        log.info(f"\n----- 系统状态 -----")
        log.info(f"热门概念缓存状态: {check_cache_status()}")
        log.info("="*60 + "\n")
        
    except Exception as e:
        log.error(f"{context.current_dt.strftime('%Y-%m-%d %H:%M:%S')} - ERROR - 盘后数据统计失败: {str(e)}")
        import traceback
        log.error(f"{context.current_dt.strftime('%Y-%m-%d %H:%M:%S')} - ERROR - Traceback (most recent call last):\n{traceback.format_exc()}")


# 5. 辅助函数
def get_buy_reason(stock, context):
    """
    获取股票的买入原因
    
    参数:
    stock: 股票代码
    context: 上下文对象
    
    返回:
    买入原因描述
    """
    try:
        # 检查股票是否在不同类型的股票列表中
        if stock in g.lblt:
            return "连板龙头"
        elif stock in g.reversal:
            return "弱转强"
        elif stock in g.gap_up:
            return "一进二"
        elif stock in g.gap_down:
            return "首板低开"
        elif stock in g.fxsbdk:
            return "反向首板低开"
        else:
            return ""
    except Exception as e:
        log.error(f"获取 {stock} 买入原因失败: {str(e)}")
        return "未知原因"



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
    dct = {'str': str_date, 'dt': dt_date, 'd': d_date}
    return dct[date_type]


def get_shifted_date(date, days, days_type='T'):
    # 获取上一个自然日
    d_date = transform_date(date, 'd')
    yesterday = d_date + dt.timedelta(-1)
    # 移动days个自然日
    if days_type == 'N':
        shifted_date = yesterday + dt.timedelta(days + 1)
    # 移动days个交易日
    if days_type == 'T':
        all_trade_days = [i.strftime('%Y-%m-%d') for i in list(get_all_trade_days())]
        # 如果上一个自然日是交易日，根据其在交易日列表中的index计算平移后的交易日
        if str(yesterday) in all_trade_days:
            shifted_date = all_trade_days[all_trade_days.index(str(yesterday)) + days + 1]
        # 否则，从上一个自然日向前数，先找到最近一个交易日，再开始平移
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


def filter_st_paused_stock(initial_list):
    current_data = get_current_data()
    # 使用列表推导式结合any()函数，筛选出符合条件的股票
    return [stock for stock in initial_list
            if not any([
            current_data[stock].is_st,  # 排除ST股
            current_data[stock].paused,  # 排除停牌股
            '退' in current_data[stock].name  # 排除名称中含'退'字的股票，避免退市股
        ])]


def filter_kcbj_stock(initial_list):
    return [stock for stock in initial_list if stock[:2] in ('60', '00', '30')]
    #return [stock for stock in initial_list if stock[:2] in ('60', '00')] #过滤科创板


# 每日初始股票池
def prepare_stock_list(date):
    initial_list = get_all_securities('stock', date).index.tolist()
    initial_list = filter_kcbj_stock(initial_list)
    initial_list = filter_new_stock(initial_list, date)
    initial_list = filter_st_paused_stock(initial_list)
    return initial_list


def rise_low_volume(s, context):  # 上涨时，未放量 rising on low volume
    hist = attribute_history(s, 106, '1d', fields=['high', 'volume'], skip_paused=True, df=False)
    high_prices = hist['high'][:102]
    prev_high = high_prices[-1]
    zyts_0 = next((i - 1 for i, high in enumerate(high_prices[-3::-1], 2) if high >= prev_high), 100)
    zyts = zyts_0 + 5
    if hist['volume'][-1] <= max(hist['volume'][-zyts:-1]) * 0.9:
        return True
    return False


# 筛选出某一日涨停的股票
def get_hl_stock(initial_list, date):
    df = get_price(initial_list, end_date=date, frequency='daily', fields=['close', 'high_limit'], count=1, panel=False,
                   fill_paused=False, skip_paused=False)
    df = df.dropna()  # 去除停牌
    df = df[df['close'] == df['high_limit']]
    hl_list = list(df.code)
    return hl_list


# 筛选曾涨停
def get_ever_hl_stock(initial_list, date):
    df = get_price(initial_list, end_date=date, frequency='daily', fields=['high', 'high_limit'], count=1, panel=False,
                   fill_paused=False, skip_paused=False)
    df = df.dropna()  # 去除停牌
    df = df[df['high'] == df['high_limit']]
    hl_list = list(df.code)
    return hl_list


# 筛选曾涨停
def get_ever_hl_stock2(initial_list, date):
    df = get_price(initial_list, end_date=date, frequency='daily', fields=['close', 'high', 'high_limit'], count=1,
                   panel=False, fill_paused=False, skip_paused=False)
    df = df.dropna()  # 去除停牌
    cd1 = df['high'] == df['high_limit']
    cd2 = df['close'] != df['high_limit']
    df = df[cd1 & cd2]
    hl_list = list(df.code)
    return hl_list


# 计算涨停数
def get_hl_count_df(hl_list, date, watch_days):
    # 获取watch_days的数据
    df = get_price(hl_list, end_date=date, frequency='daily', fields=['close', 'high_limit', 'low'], count=watch_days,
                   panel=False, fill_paused=False, skip_paused=False)
    df.index = df.code
    # 计算涨停与一字涨停数，一字涨停定义为最低价等于涨停价
    hl_count_list = []
    extreme_hl_count_list = []
    for stock in hl_list:
        df_sub = df.loc[stock]
        hl_days = df_sub[df_sub.close == df_sub.high_limit].high_limit.count()
        extreme_hl_days = df_sub[df_sub.low == df_sub.high_limit].high_limit.count()
        hl_count_list.append(hl_days)
        extreme_hl_count_list.append(extreme_hl_days)
    # 创建df记录
    df = pd.DataFrame(index=hl_list, data={'count': hl_count_list, 'extreme_count': extreme_hl_count_list})
    return df


# 计算连板数
def get_continue_count_df(hl_list, date, watch_days):
    df = pd.DataFrame()
    for d in range(2, watch_days + 1):
        HLC = get_hl_count_df(hl_list, date, d)
        CHLC = HLC[HLC['count'] == d]
        df = df.append(CHLC)
    stock_list = list(set(df.index))
    ccd = pd.DataFrame()
    for s in stock_list:
        tmp = df.loc[[s]]
        if len(tmp) > 1:
            M = tmp['count'].max()
            tmp = tmp[tmp['count'] == M]
        ccd = ccd.append(tmp)
    if len(ccd) != 0:
        ccd = ccd.sort_values(by='count', ascending=False)
    return ccd


def record_sell_trade(context, stock, reason, details, current_data, date):
    """记录卖出交易并更新上一笔交易信息"""
    try:
        position = context.portfolio.positions[stock]
        avg_cost = position.avg_cost
        current_price = current_data[stock].last_price
        profit_pct = (current_price - avg_cost) / avg_cost if avg_cost > 0 else 0
        
        # 构建交易记录
        trade_record = {
            'stock': stock,
            'action': '卖出',
            'price': current_price,
            'reason': reason,
            'details': details,
            'profit_pct': profit_pct,
            'date': context.current_dt.date()  # 记录交易日期
        }
        
        # 记录到今日交易
        if not hasattr(g, 'today_trades'):
            g.today_trades = []
        g.today_trades.append(trade_record)
        
        # 关键：更新上一笔交易信息
        g.last_trade_info = {
            'date': context.current_dt.date(),
            'profit_pct': profit_pct
        }
        pattern = get_stock_pattern(stock)
        record_mode_stat(pattern, 'sell_count')
        if profit_pct >= 0:
            record_mode_stat(pattern, 'win_count')
        else:
            record_mode_stat(pattern, 'loss_count')
        record_research_event(context, stock, 'sell', current_price, reason, details, pattern)
        log.info(f"更新上一笔交易信息: {g.last_trade_info}")
        
    except Exception as e:
        log.error(f"记录卖出交易失败: {str(e)}")



# ================== 安全历史数据封装 ==================
ALLOWED_FIELDS = {
    'open','close','high','low','volume','money','avg',
    'high_limit','low_limit','pre_close','paused','factor','open_interest'
}

def get_trading_time_status(context):
    """
    获取当前交易时段状态
    Args:
        context: 聚宽上下文对象
    Returns:
        tuple: (is_morning, is_afternoon, is_trading_time)
    """
    import datetime as dt
    
    # 获取当前时间（确保是北京时间）
    current_dt = context.current_dt
    current_time = current_dt.time()  # 时间对象（时:分:秒）
    current_datetime_str = current_dt.strftime("%Y-%m-%d %H:%M:%S")  # 完整时间字符串，用于日志
    
    # 定义A股交易时间段（北京时间）
    morning_start = dt.time(7, 30)    # 上午开始时间
    morning_end = dt.time(11, 30)     # 上午结束时间
    afternoon_start = dt.time(13, 0)  # 下午开始时间
    afternoon_end = dt.time(19, 0)    # 下午结束时间
    trade_morning_start = dt.time(9, 30)    # 交易上午开始时间
    trade_morning_end = dt.time(11, 30)     # 交易上午结束时间
    trade_afternoon_start = dt.time(13, 0)  # 交易下午开始时间
    trade_afternoon_end = dt.time(15, 0)    # 交易下午结束时间
    
    # 明确判断逻辑（拆分链式比较，增强可读性）
    is_morning = (current_time >= morning_start) and (current_time <= morning_end)
    is_afternoon = (current_time >= afternoon_start) and (current_time <= afternoon_end)
    is_trade_morning = (current_time >= trade_morning_start) and (current_time <= trade_morning_end)
    is_trade_afternoon = (current_time >= trade_afternoon_start) and (current_time <= trade_afternoon_end)
    is_trading_time = is_trade_morning or is_trade_afternoon
    
    return is_morning, is_afternoon, is_trading_time


# ================== 主卖出逻辑 ==================
def sell2(context):
    """
    卖出策略优化版本
    包含上午和下午不同的卖出逻辑
    详细记录卖出信息
    """
    # 初始化交易记录
    if not hasattr(g, 'today_trades'):
        g.today_trades = []

    # 获取当前市场数据
    current_data = get_current_data()
    date = transform_date(context.previous_date, 'str')
    current_dt = context.current_dt  # 完整datetime，用于筛选/取数
    current_time = current_dt.time()
    today_date = current_dt.date()   # 当日日期，用于筛选5分钟K线
    today = context.current_dt
    # 判断当前时间段
    is_morning, is_afternoon, is_trading_time = get_trading_time_status(context)
    # 14:50尾盘专属时段（核心放量卖出时段）
    is_profit_taking_time = (current_time >= dt.time(14, 50) and
                             current_time < dt.time(15, 0))

    # 判断当前时间段
    is_morning, is_afternoon, is_trading_time = get_trading_time_status(context)
    sold_stocks_this_call = set()

    # 遍历持仓股票
    for stock in list(context.portfolio.positions):
        if stock in sold_stocks_this_call:
            continue
        try:
            position = context.portfolio.positions[stock]

            # 跳过不可平仓的股票
            if position.closeable_amount == 0:
                continue

            # 获取股票当前信息
            current_price = current_data[stock].last_price
            avg_cost = position.avg_cost
            high_limit = current_data[stock].high_limit

            # 跳过停牌股票
            if current_data[stock].paused:
                log.info(f"{stock} 今日停牌，跳过卖出检查")
                continue

            # 上午时间段卖出策略
            if is_morning:
                # 1. 月度一号时间止损策略
                try:
                    hist = history(10, '1d', 'open', [stock], df=False)
                    if len(hist.get(stock, [])) == 10:
                        start_price = hist[stock][0]
                        end_price = hist[stock][-1]

                        # 10日涨幅大于80%且月初未涨停
                        if end_price / start_price > 1.8 and today.day == 1 and (high_limit > current_price):
                            details = {
                                '10日涨幅': f"{(end_price / start_price - 1):.2%}",
                                '当前价格': f"{current_price:.2f}",
                                '涨停价': f"{high_limit:.2f}"
                            }
                            record_sell_trade(context, stock, "月初不涨停时间止损", details, current_data, date)
                            order_target_value( stock, 0)
                            # 实盘接口卖出
                            emit_trading_signal('sell', stock, '', g.jk_stk_num)
                            sold_stocks_this_call.add(stock)
                            continue
                except Exception as e:
                    log.error(f"{stock} 月初止损策略执行失败: {str(e)}")
                # 2. 低于昨日收盘价策略
                try:
                    price_df = get_price(
                        stock,
                        end_date=context.previous_date,
                        count=1,
                        fields=['close'],
                        skip_paused=False
                    )

                    if price_df is not None and not price_df.empty:
                        yesterday_close = price_df['close'].iloc[-1]

                        if not pd.isna(yesterday_close) and current_price < yesterday_close  and current_price < high_limit :
                            details = {
                                '昨日收盘': f"{yesterday_close:.2f}",
                                '当前价格': f"{current_price:.2f}",
                                '跌幅': f"{(current_price / yesterday_close - 1):.2%}"
                            }
                            record_sell_trade(context, stock, "低于昨日收盘价", details, current_data, date)
                            order_target_value( stock, 0)
                            # 实盘接口卖出
                            emit_trading_signal('sell', stock, '', g.jk_stk_num)
                            sold_stocks_this_call.add(stock)
                            continue
                except Exception as e:
                    log.error(f"{stock} 昨日收盘价策略执行失败: {str(e)}")

            # ==================== 下午14:50止盈策略 ====================
            if is_profit_taking_time:
                try:
                    # ========== 新增：获取昨日收盘价（如果未定义） ==========
                    # 假设current_data和attribute_history可用；如已在context中，可直接用
                    stock_data = current_data[stock]  # 修改点1: 获取stock_data
                    today_data = attribute_history(stock, 2, '1d', ['close'], skip_paused=True)  # count=2取昨收
                    if len(today_data) < 2:
                        log.warning(f"{stock} 无法获取昨收，跳过止盈计算")
                        continue
                    yesterday_close = today_data['close'][-2]  # 前一日收盘
                
                    # 安全检查：避免除零错误
                    if avg_cost == 0:
                        log.warning(f"{stock} 平均成本为0，跳过止盈计算")
                        continue
                
                    # 止盈条件,量能过大：
                    # ========== 核心：重构 → get_bars(5min+include_now=True)汇总成交估算全天 ==========
                    # 【常量定义】A股交易规则+单位转换
                    UNIT_5MIN = 5                # 5分钟K线单位
                    TOTAL_TRADING_MINUTES = 240  # A股全天交易分钟数（9:30-11:30/13:00-15:00）
                    TOTAL_5MIN_BAR = TOTAL_TRADING_MINUTES // UNIT_5MIN  # 全天5分钟K线总数：48根（固定值）
                    HANDS_2_SHARE = 100          # 1手=100股
                    TEN_THOUSAND = 10000         # 万单位
                    SHARE_2_10KHAND = HANDS_2_SHARE * TEN_THOUSAND  # 股 → 万手 转换系数（除数）

                    # ---------------------- 步骤1：按要求调用get_bars获取5分钟成交列表 ----------------------
                    # 参数严格按你的要求：unit=5min + include_now=True + 取date/volume用于筛选和汇总
                    min5_bars = get_bars(
                        security=stock,
                        count=100,                # 取100根，远大于当日48根，确保覆盖当日所有5分钟K线
                        unit='5m',                # 按你的要求：单位5分钟
                        fields=('date', 'volume'),# 取日期（筛选当日）+成交量（汇总）
                        include_now=True,         # 按你的要求：True=包含截止当前14:50的K线
                        end_dt=current_dt,        # 截止时间=14:50，精准定位
                        df=True                   # 返回DataFrame，方便筛选/汇总
                    )

                    # ---------------------- 步骤2：数据基础校验 ----------------------
                    if min5_bars.empty or 'volume' not in min5_bars.columns or 'date' not in min5_bars.columns:
                        log.warning(f"{stock} 5分钟K线获取失败（空数据/缺字段），跳过量能卖出")
                        continue
                    # 转换date为datetime格式，方便筛选当日数据
                    min5_bars['date'] = pd.to_datetime(min5_bars['date'])

                    # ---------------------- 步骤3：筛选【当日】的5分钟K线，避免混入前日数据 ----------------------
                    min5_bars_today = min5_bars[min5_bars['date'].dt.date == today_date].copy()
                    if min5_bars_today.empty:
                        log.warning(f"{stock} 5分钟K线中无当日数据，跳过量能卖出")
                        continue

                    # ---------------------- 步骤4：汇总当日累计成交量（14:50真实成交） ----------------------
                    today_curr_vol_share = min5_bars_today['volume'].sum()  # 当日累计成交量（股）
                    curr_5min_bar_count = len(min5_bars_today)             # 当日已交易5分钟K线数
                    # 过滤异常成交量（累计成交为0/极少）
                    if today_curr_vol_share < 100:
                        log.warning(f"{stock} 当日累计成交量异常（{today_curr_vol_share:.0f}股），跳过量能卖出")
                        continue

                    # ---------------------- 步骤5：获取【前日完整成交量】（精准无偏差） ----------------------
                    pre_day_vol_data = get_bars(
                        security=stock,
                        count=1,
                        unit='1d',
                        fields='volume',
                        include_now=False,  # False=仅取前日完整日线，无偏差
                        df=True
                    )
                    if pre_day_vol_data.empty:
                        log.warning(f"{stock} 前日成交量获取失败，跳过量能卖出")
                        continue
                    pre_day_vol_share = pre_day_vol_data['volume'].iloc[0]  # 前日成交量（股）
                    if pre_day_vol_share < 100:
                        log.warning(f"{stock} 前日成交量异常（{pre_day_vol_share:.0f}股），跳过量能卖出")
                        continue

                    # ---------------------- 步骤6：单位转换（股 → 万手），和你的实际数值对齐 ----------------------
                    pre_day_vol_10khand = pre_day_vol_share / SHARE_2_10KHAND        # 前日成交量（万手）
                    today_curr_vol_10khand = today_curr_vol_share / SHARE_2_10KHAND  # 当日累计成交（万手）

                    # ---------------------- 步骤7：估算全天成交量（按5分钟bar数，贴合交易节奏） ----------------------
                    # 估算系数=全天5分钟bar数/已交易bar数（14:50已交易约46-47根，系数≈1.02-1.04，误差极小）
                    estimate_coeff = TOTAL_5MIN_BAR / curr_5min_bar_count if curr_5min_bar_count > 0 else 1.0
                    # 估算全天成交量（股+万手）
                    today_est_vol_share = today_curr_vol_share * estimate_coeff
                    today_est_vol_10khand = today_curr_vol_10khand * estimate_coeff

                    # ---------------------- 步骤8：倍数计算（兜底取最大值，避免低估） ----------------------
                    vol_ratio_curr = today_curr_vol_share / pre_day_vol_share  # 累计倍数（当前/前日）
                    vol_ratio_est = today_est_vol_share / pre_day_vol_share    # 估算倍数（全天/前日）
                    final_vol_ratio = max(vol_ratio_curr, vol_ratio_est)      # 最终判定倍数（兜底取大）

                    # ---------------------- 步骤9：全量日志打印（精准排查，和你的实际数值对比） ----------------------
                    log.info(f"📊 {stock} 14:50量能详情（5min K线精准汇总）：")
                    log.info(f"   前日成交量：{pre_day_vol_share:,.0f}股 | {pre_day_vol_10khand:.2f}万手")
                    log.info(f"   当日已交易5min K线：{curr_5min_bar_count}根 / 全天{TOTAL_5MIN_BAR}根")
                    log.info(f"   当日累计成交：{today_curr_vol_share:,.0f}股 | {today_curr_vol_10khand:.2f}万手")
                    log.info(f"   估算全天成交：{today_est_vol_share:,.0f}股 | {today_est_vol_10khand:.2f}万手")
                    log.info(f"   估算系数：{estimate_coeff:.3f} | 累计倍数：{vol_ratio_curr:.2f} | 估算倍数：{vol_ratio_est:.2f} | 最终倍数：{final_vol_ratio:.2f}")

                    # ---------------------- 步骤10：触发卖出（未涨停 + 最终倍数>4倍） ----------------------
                    if final_vol_ratio > 4:
                        details = {
                            '成本价': f"{avg_cost:.2f}",
                            '当前价': f"{current_price:.2f}",
                            '前日成交量(万手)': f"{pre_day_vol_10khand:.2f}",
                            '当日累计成交(万手)': f"{today_curr_vol_10khand:.2f}",
                            '估算全天成交(万手)': f"{today_est_vol_10khand:.2f}",
                            '最终判定倍数': f"{final_vol_ratio:.2f}",
                            '涨停价': f"{high_limit:.2f}",
                            '是否涨停': '否'
                        }
                        record_sell_trade(context, stock, "尾盘放量4倍卖出(5min K线)", details, current_data, date)
                        order_target_value(stock, 0)
                        sold_stocks_this_call.add(stock)
                        # 实盘接口卖出
                        emit_trading_signal('sell', stock, '', g.jk_stk_num)
                        log.info(f"📉 放量卖出 {stock}：最终倍数{final_vol_ratio:.2f}>4，未涨停，执行清仓！")
                        continue
                    else:
                        log.info(f"📊 {stock} 未满足放量卖出条件（最终倍数{final_vol_ratio:.2f}/4，未涨停）")
                    
                except Exception as e:
                    log.error(f"止盈逻辑执行出错 {stock}: {str(e)}")
                    continue

            # 下午时间段卖出策略
            if is_afternoon:
                # 安全检查：避免除零错误
                if avg_cost == 0:
                    log.warning(f"{stock} 平均成本为0，跳过止损计算")
                    continue

                # 1. 止损策略
                loss_pct = (avg_cost - current_price) / avg_cost
                high_limit_retreat = (high_limit - current_price) / avg_cost

                if loss_pct >= 0.05 or high_limit_retreat >= 0.15:
                    details = {
                        '成本价': f"{avg_cost:.2f}",
                        '当前价': f"{current_price:.2f}",
                        '亏损比例': f"{loss_pct:.2%}",
                        '涨停回撤': f"{high_limit_retreat:.2%}"
                    }
                    record_sell_trade(context, stock, "止损卖出", details, current_data, date)
                    order_target_value( stock, 0)
                    sold_stocks_this_call.add(stock)
                    # 实盘接口卖出
                    emit_trading_signal('sell', stock, '', g.jk_stk_num)
                    continue

                # 2. MA5均线策略
                try:
                    close_data = attribute_history(stock, 4, '1d', ['close'])

                    if close_data is not None and not close_data.empty:
                        M4 = close_data['close'].mean()
                        MA5 = (M4 * 4 + current_price) / 5
                        if current_price < MA5:
                            details = {
                                'MA5': f"{MA5:.2f}",
                                '当前价': f"{current_price:.2f}",
                                '偏离率': f"{(current_price / MA5 - 1):.2%}"
                            }
                            record_sell_trade(context, stock, "跌破MA5均线", details, current_data, date)
                            order_target_value( stock, 0)
                            # 实盘接口卖出
                            emit_trading_signal('sell', stock, '', g.jk_stk_num)
                            sold_stocks_this_call.add(stock)
                            continue
                except Exception as e:
                    log.error(f"{stock} MA5策略执行失败: {str(e)}")

            # 3. 新增：最近24根半小时K线量价顶背离策略
            try:
                # 获取最近24根半小时K线数据（包含最高价和成交量）
                # frequency='30m'表示半小时K线，count=24获取最近24根
                kline_data = get_price(
                    stock,
                    end_date=context.current_dt,
                    count=24,
                    frequency='30m',
                    fields=['high', 'volume'],
                    skip_paused=False
                )

                # 数据有效性校验
                if kline_data is None or kline_data.empty or len(kline_data) < 24:
                    log.warning(
                        f"{stock} 无法获取足够的24根半小时K线数据（实际获取{len(kline_data) if kline_data is not None else 0}根），跳过量价顶背离检查")
                    continue

                # 提取24根K线的最高价和成交量
                highs = kline_data['high'].values  # 最高价数组
                volumes = kline_data['volume'].values  # 成交量数组

                # 计算24根K线中的最高价格和最大成交量
                max_high = max(highs)
                max_volume = max(volumes)

                # 防护：避免最大成交量为0导致的计算问题
                if max_volume <= 0:
                    log.warning(f"{stock} 最近24根半小时K线最大成交量为0，跳过量价顶背离检查")
                    continue

                # 最近一根K线的最高价和成交量
                last_kline_high = highs[-1]
                last_kline_volume = volumes[-1]

                # 计算当前价格与最近K线最高价的差距百分比
                price_drop_percent = (last_kline_high - current_price) / last_kline_high * 100

                # 量价顶背离条件：
                # 1. 最近一根K线最高价创24根内新高（等于最大最高价）
                # 2. 最近一根K线成交量 <= 最大成交量的一半
                # 3. 当前价格未涨停
                # 4. 新增条件：当前价格比最近一根K线最高价下跌超过3%
                if ((last_kline_high >= max_high - 1e-6) and
                        (last_kline_volume <= max_volume * 0.5) and
                        (current_price < high_limit) and
                        (price_drop_percent > 3.0)):  # 新增条件：价格下跌超过3%

                    details = {
                        '24根K线最高': f"{max_high:.2f}",
                        '最近K线最高': f"{last_kline_high:.2f}",
                        '24根最大量能': f"{max_volume:.0f}",
                        '最近K线量能': f"{last_kline_volume:.0f}",
                        '量能比例': f"{(last_kline_volume / max_volume):.2%}",
                        '当前价': f"{current_price:.2f}",
                        '价格回撤': f"{price_drop_percent:.2f}%",  # 新增：显示价格回撤百分比
                        '涨停价': f"{high_limit:.2f}"
                    }
                    record_sell_trade(context, stock, "24根半小时K线量价顶背离", details, current_data, date)
                    order_target_value( stock, 0)
                    # 实盘接口卖出
                    emit_trading_signal('sell', stock, '', g.jk_stk_num)
                    sold_stocks_this_call.add(stock)
                    continue

                # 新增：当价格已经下跌超过5%时，也执行卖出操作，但使用不同的原因
                elif ((last_kline_high >= max_high - 1e-6) and
                      (last_kline_volume <= max_volume * 0.5) and
                      (price_drop_percent > 5.0)):

                    details = {
                        '24根K线最高': f"{max_high:.2f}",
                        '最近K线最高': f"{last_kline_high:.2f}",
                        '24根最大量能': f"{max_volume:.0f}",
                        '最近K线量能': f"{last_kline_volume:.0f}",
                        '量能比例': f"{(last_kline_volume / max_volume):.2%}",
                        '当前价': f"{current_price:.2f}",
                        '价格回撤': f"{price_drop_percent:.2f}%",  # 显示价格回撤百分比
                        '涨停价': f"{high_limit:.2f}"
                    }
                    record_sell_trade(context, stock, "24根半小时K线量价顶背离(价格已回撤超5%)", details, current_data,
                                      date)
                    order_target_value( stock, 0)
                    # 实盘接口卖出
                    emit_trading_signal('sell', stock, '', g.jk_stk_num)
                    sold_stocks_this_call.add(stock)
                    continue

            except Exception as e:
                log.error(f"{stock} 量价顶背离策略执行失败: {str(e)}")


        except Exception as e:
            log.error(f"处理 {stock} 卖出策略时发生错误: {str(e)}")



# 计算股票处于一段时间内相对位置
def get_relative_position_df(stock_list, date, watch_days):
    if len(stock_list) != 0:
        df = get_price(stock_list, end_date=date, fields=['high', 'low', 'close'], count=watch_days, fill_paused=False,
                       skip_paused=False, panel=False).dropna()
        close = df.groupby('code').apply(lambda df: df.iloc[-1, -1])
        high = df.groupby('code').apply(lambda df: df['high'].max())
        low = df.groupby('code').apply(lambda df: df['low'].min())
        result = pd.DataFrame()
        result['rp'] = (close - low) / (high - low)
        return result
    else:
        return pd.DataFrame(columns=['rp'])

    # 连板龙头函数


# 筛选按因子值排名的股票
def get_factor_filter_df(context, stock_list, jqfactor, sort):
    if len(stock_list) != 0:
        yesterday = context.previous_date
        score_list = get_factor_values(stock_list, jqfactor, end_date=yesterday, count=1)[jqfactor].iloc[0].tolist()
        df = pd.DataFrame(index=stock_list, data={'score': score_list}).dropna()
        df = df.sort_values(by='score', ascending=sort)
    else:
        df = pd.DataFrame(index=[], data={'score': []})
    return df


# 概念筛选
def filter_concept_stock(dct, concept):
    tmp_set = set()
    for k, v in dct.items():
        for d in dct[k]['jq_concept']:
            if d['concept_name'] == concept:
                tmp_set.add(k)
    return list(tmp_set)


# 计算热门概念
def get_hot_concept(dct, date):
    # 计算出现涨停最多的概念
    concept_count = {}
    for key in dct:
        for i in dct[key]['jq_concept']:
            if i['concept_name'] in concept_count.keys():
                concept_count[i['concept_name']] += 1
            else:
                if i['concept_name'] not in ['转融券标的', '融资融券', '深股通', '沪股通']:
                    concept_count[i['concept_name']] = 1
    df = pd.DataFrame(list(concept_count.items()), columns=['concept_name', 'concept_count'])
    df = df.set_index('concept_name')
    df = df.sort_values(by='concept_count', ascending=False)
    max_num = df.iloc[0, 0]
    df = df[df['concept_count'] == max_num]
    concept = list(df.index)[0]
    return concept



# 反向首板低开函数
# 筛选出某一日涨停的股票
def get_ll_stock(initial_list, date):
    df = get_price(initial_list, end_date=date, frequency='daily', fields=['close', 'low_limit'], count=1, panel=False,
                   fill_paused=False, skip_paused=False)
    df = df.dropna()  # 去除停牌
    df = df[df['close'] == df['low_limit']]
    hl_list = list(df.code)
    return hl_list


# 计算涨停数
def get_ll_count_df(hl_list, date, watch_days):
    # 获取watch_days的数据
    df = get_price(hl_list, end_date=date, frequency='daily', fields=['low', 'close', 'low_limit'], count=watch_days,
                   panel=False, fill_paused=False, skip_paused=False)
    df.index = df.code
    # 计算涨停与一字涨停数，一字涨停定义为最低价等于涨停价
    hl_count_list = []
    extreme_hl_count_list = []
    for stock in hl_list:
        df_sub = df.loc[stock]
        hl_days = df_sub[df_sub.close == df_sub.low_limit].low_limit.count()
        extreme_hl_days = df_sub[df_sub.low == df_sub.low_limit].low_limit.count()
        hl_count_list.append(hl_days)
        extreme_hl_count_list.append(extreme_hl_days)
    # 创建df记录
    df = pd.DataFrame(index=hl_list, data={'count': hl_count_list, 'extreme_count': extreme_hl_count_list})
    return df


# 计算连板数
def get_continue_count_df_ll(hl_list, date, watch_days):
    df = pd.DataFrame()
    for d in range(2, watch_days + 1):
        HLC = get_ll_count_df(hl_list, date, d)
        CHLC = HLC[HLC['count'] == d]
        df = df.append(CHLC)
    stock_list = list(set(df.index))
    ccd = pd.DataFrame()
    for s in stock_list:
        tmp = df.loc[[s]]
        if len(tmp) > 1:
            M = tmp['count'].max()
            tmp = tmp[tmp['count'] == M]
        ccd = ccd.append(tmp)
    if len(ccd) != 0:
        ccd = ccd.sort_values(by='count', ascending=False)
    return ccd
    
    
def convert_jq_to_miniqmt_suffix(jq_code):
    """
    将聚宽格式的股票代码转换为MiniQMT支持的格式，如 '600000.SH'。

    参数:
        jq_code (str): 聚宽股票代码，例如 '000001.XSHE' 或 '600000.XSHG'

    返回:
        str: MiniQMT支持的股票代码格式，例如 '000001.SZ' 或 '600000.SH'
    """
    exchange_map = {
        'XSHE': 'SZ',
        'XSHG': 'SH'
    }

    try:
        code_part, exchange_part = jq_code.split('.')
        if exchange_part not in exchange_map:
            raise ValueError(f"不支持的交易所代码: {exchange_part}")
        return f"{code_part}.{exchange_map[exchange_part]}"
    except ValueError as e:
        raise ValueError(f"输入格式错误，应为类似 '000001.XSHE' 的格式: {jq_code}") from e


    
def send_trading_signal(action, stock_code, stock_name, stock_num):
    """论坛分享版：已移除服务器桥接，仅保留占位函数。"""
    try:
        log.info(f"[forum-share] 已跳过外部信号发送: action={action}, stock={stock_code}, count={stock_num}")
    except Exception:
        pass
    return None