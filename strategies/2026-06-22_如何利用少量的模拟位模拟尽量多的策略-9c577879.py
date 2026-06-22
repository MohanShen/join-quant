# Clone from JoinQuant
# postId: 9c577879427eea846aa0c9efc808a142
# backtestId: 42572f97dcd52b77ec87bdf395ae1c9b
# title: 如何利用少量的模拟位模拟尽量多的策略

# -*- coding: utf-8 -*-
"""
多组合五策略合并 - 18_多组合五策略合并.py
结构模板：02_三马105-七星1.72.py 的多策略资金隔离思路

子组合分配（当前小市值关闭，前四个子组合各25%）：
  pindex=0: 七星1.7 大池 (七星1.7大小池切换, etf_pool_mode='large')
  pindex=1: 七星1.7 小池 (七星1.7大小池切换, etf_pool_mode='small')
  pindex=2: 五福3.5   (五福3.5.py)
  pindex=3: 七星改版+etf   (七星改版+行业etf)
  pindex=4: 小市值    (三马小市值策略.py)

初始资金：小市值关闭时 P0-P3 各25%，P4 为0
可选再平衡：默认关闭；如需月度再平衡，可将 g.rebalance_enabled 改为 True
内存清理：每日15:10 daily_memory_cleanup
"""

from jqdata import *
import numpy as np
import pandas as pd
import datetime
import math
import gc
import re
import prettytable
from prettytable import PrettyTable

# ==================== 模块级缓存（不参与pickle） ====================
__all_securities_cache = {'data': None, 'etf_data': None, 'date': None}
_SECURITY_NAME_CACHE = {}
_SECURITY_NAME_CACHE_MAX = 300


# ==================== 策略启用与资金分配（只改这里） ====================
# enabled=False 表示该策略不分配资金、不注册交易任务。
# weight 为启用时的目标资金权重；所有启用策略的 weight 会自动归一化。
STRATEGY_CONFIG = {
    0: {'enabled': True,  'weight': 1, 'name': '七星1.7大池'},
    1: {'enabled': True,  'weight': 1, 'name': '七星1.7小池'},
    2: {'enabled': True,  'weight': 1, 'name': '五福3.5'},
    3: {'enabled': True,  'weight': 1, 'name': '七星520'},
    4: {'enabled': False, 'weight': 0, 'name': '小市值'},
}


def _strategy_enabled(pindex):
    return STRATEGY_CONFIG.get(pindex, {}).get('enabled', False)


def _strategy_ratios():
    weights = [STRATEGY_CONFIG.get(i, {}).get('weight', 0) if _strategy_enabled(i) else 0 for i in range(5)]
    total = sum(weights)
    if total <= 0:
        raise ValueError('STRATEGY_CONFIG 至少需要启用一个策略且 weight > 0')
    return [w / total for w in weights]


def _get_all_securities_info():
    today = datetime.date.today()
    if __all_securities_cache['data'] is not None and __all_securities_cache['date'] == today:
        return __all_securities_cache['data'], __all_securities_cache['etf_data']
    etf_data = get_all_securities(['etf'])
    fund_data = get_all_securities(['etf', 'fund'])
    __all_securities_cache['data'] = fund_data
    __all_securities_cache['etf_data'] = etf_data
    __all_securities_cache['date'] = today
    return fund_data, etf_data


def _get_security_name(code):
    if code in _SECURITY_NAME_CACHE:
        return _SECURITY_NAME_CACHE[code]
    try:
        name = get_current_data()[code].name
    except Exception:
        try:
            name = get_security_info(code).display_name
        except Exception:
            name = code
    if len(_SECURITY_NAME_CACHE) >= _SECURITY_NAME_CACHE_MAX:
        keys = list(_SECURITY_NAME_CACHE.keys())[:50]
        for k in keys:
            del _SECURITY_NAME_CACHE[k]
    _SECURITY_NAME_CACHE[code] = name
    return name


# ==================== 初始化 ====================
def initialize(context):
    unschedule_all()
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    log.set_level('order', 'error')
    set_slippage(PriceRelatedSlippage(0.0001), type='fund')
    set_slippage(FixedSlippage(0.02), type='stock')
    set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.0001,
                             close_commission=0.0001, close_today_commission=0.0001,
                             min_commission=5), type='fund')
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003,
                             close_commission=0.0003, close_today_commission=0,
                             min_commission=5), type='stock')

    starting_cash = context.portfolio.starting_cash
    ratios = _strategy_ratios()
    sub_cash = [round(starting_cash * r, 2) for r in ratios]
    sub_cash[-1] = round(starting_cash - sum(sub_cash[:-1]), 2)

    set_subportfolios([
        SubPortfolioConfig(cash=sub_cash[0], type='stock'),   # pindex=0 七星大池
        SubPortfolioConfig(cash=sub_cash[1], type='stock'),   # pindex=1 七星小池
        SubPortfolioConfig(cash=sub_cash[2], type='stock'),   # pindex=2 五福3.5
        SubPortfolioConfig(cash=sub_cash[3], type='stock'),   # pindex=3 七星520
        SubPortfolioConfig(cash=sub_cash[4], type='stock'),   # pindex=4 小市值
    ])

    g.strategy_enabled = [_strategy_enabled(i) for i in range(5)]
    g.subportfolio_cash = sub_cash
    g.strategy_starting_cash = {i: sub_cash[i] for i in range(5)}
    g.strategy_history = {0: [], 1: [], 2: [], 3: [], 4: []}
    g.strategy_value_data = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
    g.rebalance_enabled = False
    g.rebalance_pending = False
    g.rebalance_config = {
        'base_ratios': ratios,
        'deviation_trigger': 0.10,
        'min_transfer': 1000,
        'enabled': g.rebalance_enabled,
    }
    g.run_days = 0

    _get_all_securities_info()
    init_strategies(context)
    wufu_init_range_bound_status(context, g.wufu_strategy)
    setup_schedule(context)
    log.info("[多组合]" + f'[初始化] 组合初始化完成，各子组合资金: {sub_cash}')


def init_strategies(context):
    # ==================== P0: 七星1.7 大池 ====================
    g.qx_large_strategy = {
        'name': 'P0_七星1.7大池', 'pindex': 0,
        'etf_pool_mode': 'large',
        'etf_pool_small': [
            '518880.XSHG', '159985.XSHE', '501018.XSHG', '161226.XSHE',
            '513100.XSHG', '159915.XSHE', '511220.XSHG',
        ],
        'etf_pool_large': [
            '518880.XSHG', '159980.XSHE', '159985.XSHE', '501018.XSHG',
            '161226.XSHE', '159981.XSHE', '513100.XSHG', '159509.XSHE',
            '513290.XSHG', '513500.XSHG', '159529.XSHE', '513400.XSHG',
            '513520.XSHG', '513030.XSHG', '513080.XSHG', '513310.XSHG',
            '513730.XSHG', '159792.XSHE', '513130.XSHG', '513050.XSHG',
            '159920.XSHE', '513690.XSHG', '510300.XSHG', '510500.XSHG',
            '510050.XSHG', '510210.XSHG', '159915.XSHE', '588080.XSHG',
            '512100.XSHG', '563360.XSHG', '563300.XSHG', '512890.XSHG',
            '159967.XSHE', '512040.XSHG', '159201.XSHE', '511380.XSHG',
            '511010.XSHG', '511220.XSHG',
        ],
        'lookback_days': 25, 'holdings_num': 1,
        'defensive_etf': '511880.XSHG', 'min_money': 1000,
        'loss': 0.97, 'min_score_threshold': 0, 'max_score_threshold': 100.0,
        'enable_volume_check': True, 'volume_lookback': 5, 'volume_threshold': 2,
        'volume_return_limit': 1,
        'use_short_momentum_filter': True, 'short_lookback_days': 10,
        'short_momentum_threshold': 0.0,
        'enable_profit_protection': True, 'profit_protection_lookback': 1,
        'profit_protection_threshold': 0.05,
        'enable_premium_filter': True, 'premium_threshold': 0.20,
        'premium_max_back_days': 5,
        'rankings_cache': {'date': None, 'pool_mode': None, 'data': None},
        'etf_pool': [],
        'all_etf_pool': [],
        'rebalance_cap': None,
    }

    # ==================== P1: 七星1.7 小池 ====================
    g.qx_small_strategy = {
        'name': 'P1_七星1.7小池', 'pindex': 1,
        'etf_pool_mode': 'small',
        'etf_pool_small': [
            '518880.XSHG', '159985.XSHE', '501018.XSHG', '161226.XSHE',
            '513100.XSHG', '159915.XSHE', '511220.XSHG',
        ],
        'etf_pool_large': [
            '518880.XSHG', '159980.XSHE', '159985.XSHE', '501018.XSHG',
            '161226.XSHE', '159981.XSHE', '513100.XSHG', '159509.XSHE',
            '513290.XSHG', '513500.XSHG', '159529.XSHE', '513400.XSHG',
            '513520.XSHG', '513030.XSHG', '513080.XSHG', '513310.XSHG',
            '513730.XSHG', '159792.XSHE', '513130.XSHG', '513050.XSHG',
            '159920.XSHE', '513690.XSHG', '510300.XSHG', '510500.XSHG',
            '510050.XSHG', '510210.XSHG', '159915.XSHE', '588080.XSHG',
            '512100.XSHG', '563360.XSHG', '563300.XSHG', '512890.XSHG',
            '159967.XSHE', '512040.XSHG', '159201.XSHE', '511380.XSHG',
            '511010.XSHG', '511220.XSHG',
        ],
        'lookback_days': 25, 'holdings_num': 1,
        'defensive_etf': '511880.XSHG', 'min_money': 1000,
        'loss': 0.97, 'min_score_threshold': 0, 'max_score_threshold': 100.0,
        'enable_volume_check': True, 'volume_lookback': 5, 'volume_threshold': 2,
        'volume_return_limit': 1,
        'use_short_momentum_filter': True, 'short_lookback_days': 10,
        'short_momentum_threshold': 0.0,
        'enable_profit_protection': True, 'profit_protection_lookback': 1,
        'profit_protection_threshold': 0.05,
        'enable_premium_filter': True, 'premium_threshold': 0.20,
        'premium_max_back_days': 5,
        'rankings_cache': {'date': None, 'pool_mode': None, 'data': None},
        'etf_pool': [],
        'all_etf_pool': [],
        'rebalance_cap': None,
    }

    # 初始化两个七星池子的 etf_pool
    for s in [g.qx_large_strategy, g.qx_small_strategy]:
        qx17_apply_pool_config(s)

    # ==================== P2: 五福3.5 ====================
    g.wufu_strategy = {
        'name': 'P2_五福3.5', 'pindex': 2,
        'fixed_etf_pool': [
            '518880.XSHG', '161226.XSHE', '159980.XSHE', '501018.XSHG', '159985.XSHE',
            '513100.XSHG', '159509.XSHE', '513290.XSHG', '513500.XSHG', '159518.XSHE',
            '159502.XSHE', '159529.XSHE', '513400.XSHG', '520830.XSHG', '513520.XSHG',
            '513030.XSHG', '513090.XSHG', '513180.XSHG', '513120.XSHG', '513330.XSHG',
            '513750.XSHG', '159892.XSHE', '159605.XSHE', '513190.XSHG', '510900.XSHG',
            '513630.XSHG', '513920.XSHG', '159323.XSHE', '513970.XSHG',
            '510500.XSHG', '512100.XSHG', '563300.XSHG', '510300.XSHG', '512050.XSHG',
            '510760.XSHG', '159915.XSHE', '159949.XSHE', '159967.XSHE', '588080.XSHG',
            '588220.XSHG', '511380.XSHG',
            '513310.XSHG', '588200.XSHG', '159852.XSHE', '512880.XSHG', '159206.XSHE',
            '512400.XSHG', '512980.XSHG', '159516.XSHE', '512480.XSHG', '515880.XSHG',
            '562500.XSHG', '159218.XSHE', '159869.XSHE', '159870.XSHE', '159326.XSHE',
            '159851.XSHE', '560860.XSHG', '159363.XSHE', '588170.XSHG', '159755.XSHE',
            '512170.XSHG', '512800.XSHG', '159819.XSHE', '512710.XSHG', '159638.XSHE',
            '517520.XSHG', '515980.XSHG', '159995.XSHE', '159227.XSHE', '512660.XSHG',
            '512690.XSHG', '516150.XSHG', '512890.XSHG', '588790.XSHG', '159992.XSHE',
            '512070.XSHG', '562800.XSHG', '512010.XSHG', '515790.XSHG', '510880.XSHG',
            '159928.XSHE', '159883.XSHE', '159998.XSHE', '515220.XSHG', '561980.XSHG',
            '515400.XSHG', '515120.XSHG', '159566.XSHE', '515050.XSHG', '516510.XSHG',
            '159256.XSHE', '159766.XSHE', '512200.XSHG', '513350.XSHG', '159583.XSHE',
            '159732.XSHE', '516160.XSHG', '516520.XSHG', '562590.XSHG', '515030.XSHG',
            '512670.XSHG', '561330.XSHG', '516190.XSHG', '159840.XSHE', '159611.XSHE',
            '159981.XSHE', '159865.XSHE', '561360.XSHG', '159667.XSHE', '515170.XSHG',
            '513360.XSHG', '159825.XSHE', '515210.XSHG',
        ],
        'filtered_fixed_pool': [], 'dynamic_etf_pool': [], 'merged_etf_pool': [],
        'ranked_etfs_result': [], 'target_etfs_list': [],
        'etf_names_dict': {}, 'cache_date': None, 'yesterday_close_cache': {},
        'avg_etf_money_threshold': None,
        'holdings_num': 1, 'defensive_etf': '511880.XSHG', 'min_money': 10,
        'lookback_days': 25, 'min_score_threshold': 0, 'max_score_threshold': 5,
        'score_threshold_ratio': 0.9,
        'use_short_momentum_period': False,
        'short_momentum_lookback': 21, 'short_momentum_min_score': 0,
        'short_momentum_max_score': 6,
        'enable_r2_filter': True, 'r2_threshold': 0.4,
        'enable_volume_check': True, 'volume_lookback': 5, 'volume_threshold': 1.8,
        'enable_loss_filter': True, 'loss': 0.97,
        'enable_premium_filter': False, 'max_premium_rate': 30,
        'laplace_s_param': 0.05, 'laplace_min_slope': 0.002,
        'gaussian_sigma': 1.2, 'gaussian_min_slope': 0.002,
        'enable_range_bound_mode': True,
        'current_filter': '正常期', 'risk_state': '正常期',
        'lookback_high_low_days': 20, 'risk_benchmark': '510300.XSHG',
        'enable_bias_trigger': True, 'bias_threshold': 0.08, 'ma_period': 20,
        'enable_rsi_trigger': True, 'rsi_overbought': 70, 'rsi_pullback': 65,
        'previous_rsi': None,
        'enable_stop_loss_trigger': True, 'stop_loss_triggered_today': False,
        'enable_low_point_rise_trigger': True, 'low_point_rise_threshold': 0.04,
        'enable_stable_signal_trigger': True, 'drawdown_recovery': 0.02,
        'max_range_bound_days': 20, 'stable_days': 0,
        'filter_switch_cooldown': 3, 'last_switch_date': None,
        'range_bound_start_date': None, 'range_bound_days_count': 0,
        'previous_drawdown': None,
        'max_portfolio_value': 0, 'drawdown_threshold': 0.03, 'drawdown_records': [],
        'use_fixed_stop_loss': True, 'fixedStopLossThreshold': 0.95,
        'use_pct_stop_loss': False, 'pct_stop_loss_threshold': 0.95,
        'etf_yesterday_close_batch': {}, 'etf_yesterday_nav_batch': {},
        'rebalance_cap': None,
    }

    # ==================== P3: 七星520 ====================
    g.q520_strategy = {
        'name': 'P3_七星+行业ETF', 'pindex': 3,
        'etf_pool': [
            '518880.XSHG', '161226.XSHE', '159980.XSHE', '501018.XSHG', '159985.XSHE',
            '159981.XSHE', '513100.XSHG', '159509.XSHE', '513290.XSHG', '513500.XSHG',
            '159502.XSHE', '513400.XSHG', '520830.XSHG', '513520.XSHG', '513030.XSHG',
            '513730.XSHG', '513080.XSHG', '513310.XSHG',
            '513180.XSHG', '513330.XSHG', '513750.XSHG', '159605.XSHE', '510900.XSHG',
            '513630.XSHG', '513920.XSHG',
            '510500.XSHG', '510300.XSHG', '512050.XSHG', '510760.XSHG', '159915.XSHE',
            '159949.XSHE', '588080.XSHG', '511380.XSHG', '511010.XSHG', '511220.XSHG',
            '588200.XSHG', '512880.XSHG', '159206.XSHE', '512400.XSHG', '515880.XSHG',
            '562500.XSHG', '159870.XSHE', '159326.XSHE', '159755.XSHE', '512170.XSHG',
            '512890.XSHG',
        ],
        'lookback_days': 25, 'holdings_num': 1,
        'defensive_etf': '511880.XSHG', 'min_money': 5000,
        'enable_profit_protection': True, 'profit_protection_lookback': 1,
        'profit_protection_threshold': 0.05,
        'profit_protection_check_times': ['11:00'],
        'loss': 0.97, 'min_score_threshold': 0, 'max_score_threshold': 100.0,
        'enable_volume_check': True, 'volume_lookback': 5, 'volume_threshold': 2,
        'volume_return_limit': 1,
        'use_short_momentum_filter': True, 'short_lookback_days': 10,
        'short_momentum_threshold': 0.0,
        'enable_premium_filter': True, 'premium_threshold': 0.20,
        'rankings_cache': {'date': None, 'data': None},
        'enable_range_bound_mode': True,
        'current_filter': '正常期', 'risk_state': '正常期',
        'lookback_high_low_days': 20, 'risk_benchmark': '510300.XSHG',
        'laplace_s_param': 0.05, 'laplace_min_slope': 0.001,
        'gaussian_sigma': 1.2, 'gaussian_min_slope': 0.002,
        'enable_bias_trigger': True, 'bias_threshold': 0.10, 'ma_period': 20,
        'enable_rsi_trigger': True, 'rsi_overbought': 75, 'rsi_pullback': 60,
        'previous_rsi': None,
        'enable_stop_loss_trigger': False, 'stop_loss_triggered_today': False,
        'stop_loss_triggered_date': None,
        'enable_low_point_rise_trigger': True, 'low_point_rise_threshold': 0.03,
        'enable_stable_signal_trigger': True, 'drawdown_recovery': 0.03,
        'max_range_bound_days': 15, 'stable_days': 0,
        'filter_switch_cooldown': 2, 'last_switch_date': None,
        'range_bound_start_date': None, 'range_bound_days_count': 0,
        'previous_drawdown': None,
        'rebalance_cap': None,
    }

    # ==================== P4: 小市值 ====================
    g.small_strategy = {
        'name': 'P4_小市值', 'pindex': 4,
        'filter_market_cap_min': 10, 'filter_market_cap_max': 100,
        'max_stock_price': 50, 'min_listed_days': 375,
        'max_position_count': 5, 'min_buy_amount': 5000,
        'enable_dynamic_stock_num': True,
        'defensive_etf': '511880.XSHG',
        'stoploss_limit': 0.09, 'stoploss_market': 0.05, 'stoploss_strategy': 3,
        'yesterday_HL_list': [], 'stocks': [], 'days': 0, 'first_run': True,
        'enable_atr_stop_loss': True, 'atr_period': 14, 'atr_multiplier': 2.0,
        'atr_stop_prices': {},
        'enable_cost_protection': True,
        'cost_protection_profit_threshold_1': 0.15,
        'cost_protection_profit_threshold_2': 0.30,
        'cost_protection_stop_line_1': 0.00,
        'cost_protection_stop_line_2': 0.10,
        'DBL_control': True, 'dbl': [], 'check_macd_divergence_days': 10,
        'enable_audit_filter': True, 'enable_bonus_filter': True,
        'audit_tolerance': 2,
        'enable_cooldown': True, 'cooldown_days': 2, 'no_buy_stocks': {},
        'log_trade_detail': True, 'log_filter_detail': True,
        'rebalance_cap': None,
    }


def setup_schedule(context):
    # ---- P0/P1 七星1.7（大池、小池共用调度时间，函数内区分） ----
    if _strategy_enabled(0):
        run_daily(qx17_check_positions_large, '09:10')
        run_daily(qx17_profit_protection_check_large, '11:00')
        run_daily(qx17_sell_trade_large, '14:00')
        run_daily(qx17_buy_trade_large, '14:01')

    if _strategy_enabled(1):
        run_daily(qx17_check_positions_small, '09:11')
        run_daily(qx17_profit_protection_check_small, '11:01')
        run_daily(qx17_sell_trade_small, '14:02')
        run_daily(qx17_buy_trade_small, '14:03')

    # ---- P2 五福3.5 ----
    if _strategy_enabled(2):
        run_daily(wufu_morning_routine, '09:00')
        run_daily(wufu_afternoon_routine, '13:10')
        run_daily(wufu_reset_daily_flags, '15:10')
        run_daily(wufu_minute_stop_loss, 'every_bar')
        run_daily(wufu_minute_pct_stop_loss, 'every_bar')

    # ---- P3 七星520 ----
    if _strategy_enabled(3):
        run_daily(q520_check_positions, '09:12')
        run_daily(q520_profit_protection_check, '11:02')
        run_daily(q520_check_range_bound, '13:05')
        run_daily(q520_sell_trade, '13:10')
        run_daily(q520_buy_trade, '13:11')
        run_daily(q520_reset_range_bound_daily, '15:10')

    # ---- P4 小市值（当前关闭） ----
    if _strategy_enabled(4):
        run_daily(small_before_trading, 'before_open')
        run_daily(small_check_macd_divergence_daily, '09:31')
        run_weekly(small_iSell, 2, '09:40')
        run_weekly(small_iBuy, 2, '09:45')
        run_daily(small_daily_stoploss, '10:00')
        run_daily(small_update_atr_stop_prices, '10:30')
        run_daily(small_update_atr_stop_prices, '14:00')
        run_daily(small_check_limit_up, '14:00')

    # ---- 共用 ----
    run_daily(record_daily_performance, 'after_close')
    run_daily(daily_memory_cleanup, '15:10')
    run_monthly(rebalance_evaluate, 1, '09:25')
    run_monthly(rebalance_transfer_cash, 3, '14:50')


def process_initialize(context):
    unschedule_all()
    setup_schedule(context)
    log.info('[process_initialize] 进程重启，恢复调度')
    _get_all_securities_info()
    _safe_reinit_strategies(context)


def after_code_changed(context):
    unschedule_all()
    setup_schedule(context)
    _safe_reinit_strategies(context)
    log.info('[after_code_changed] 代码变更，安全重初始化完成')


def _safe_reinit_strategies(context):
    saved = {}
    for attr in ['qx_large_strategy', 'qx_small_strategy', 'wufu_strategy',
                 'q520_strategy', 'small_strategy']:
        if hasattr(g, attr):
            saved[attr] = dict(getattr(g, attr))
    init_strategies(context)
    for attr in saved:
        current = getattr(g, attr)
        for key, val in current.items():
            if key not in saved[attr]:
                saved[attr][key] = val
                log.info("[多组合]" + f'[代码变更] 新增参数: {attr}["{key}"] = {val}')
        setattr(g, attr, saved[attr])
    # 再平衡配置
    if not hasattr(g, 'rebalance_config'):
        g.rebalance_config = {
            'base_ratios': _strategy_ratios(),
            'deviation_trigger': 0.10,
            'min_transfer': 1000,
        }
    else:
        g.rebalance_config['base_ratios'] = _strategy_ratios()
    if not hasattr(g, 'rebalance_pending'):
        g.rebalance_pending = False
    if not hasattr(g, 'strategy_starting_cash'):
        g.strategy_starting_cash = {i: context.subportfolios[i].total_value for i in range(5)}
    if not hasattr(g, 'strategy_history'):
        g.strategy_history = {0: [], 1: [], 2: [], 3: [], 4: []}
    if not hasattr(g, 'strategy_value_data'):
        g.strategy_value_data = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
    if hasattr(g, 'wufu_strategy'):
        wufu_rebuild_after_hot_update(context, g.wufu_strategy)


# ============================================================
#  通用工具函数
# ============================================================

def _laplace_filter(price, s=0.05):
    alpha = 1 - np.exp(-s)
    L = np.zeros(len(price))
    L[0] = price[0]
    for t in range(1, len(price)):
        L[t] = alpha * price[t] + (1 - alpha) * L[t - 1]
    return L


def _gaussian_filter_last_two(price, sigma=1.2):
    n = len(price)
    if n < 2:
        return 0, 0
    idx_1 = np.arange(n)
    w1 = np.exp(-((idx_1 + 1) ** 2) / (2 * sigma ** 2))[::-1]
    w1 /= np.sum(w1)
    g1 = np.sum(price * w1)
    price_2 = price[:-1]
    idx_2 = np.arange(n - 1)
    w2 = np.exp(-((idx_2 + 1) ** 2) / (2 * sigma ** 2))[::-1]
    w2 /= np.sum(w2)
    g2 = np.sum(price_2 * w2)
    return g1, g2


def _calculate_rsi(close, period=14):
    try:
        if len(close) < period + 1:
            return None
        deltas = np.diff(close)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        if avg_loss == 0:
            return 100
        return 100 - (100 / (1 + avg_gain / avg_loss))
    except Exception:
        return None


def _mcad(close, short=12, long=26, m=9):
    def ema(s, n):
        return pd.Series.ewm(s, span=n, min_periods=n - 1, adjust=False).mean()
    dif = ema(close, short) - ema(close, long)
    dea = ema(dif, m)
    return dif, dea, (dif - dea) * 2


# ============================================================
#  P0 / P1 —— 七星1.7（大/小池）通用函数
# ============================================================

def qx17_apply_pool_config(strategy):
    mode = strategy['etf_pool_mode']
    pools = {'small': strategy['etf_pool_small'], 'large': strategy['etf_pool_large']}
    if mode not in pools:
        strategy['etf_pool_mode'] = 'small'
        mode = 'small'
    strategy['etf_pool'] = list(pools[mode])
    strategy['all_etf_pool'] = sorted(set(strategy['etf_pool_small'] + strategy['etf_pool_large']))


def qx17_get_managed_universe(strategy):
    universe = set(strategy['all_etf_pool'])
    universe.add(strategy['defensive_etf'])
    return universe


def qx17_check_profit_protection(security, strategy):
    if not strategy['enable_profit_protection']:
        return False
    lookback = strategy['profit_protection_lookback']
    threshold = strategy['profit_protection_threshold']
    try:
        hist = attribute_history(security, lookback, '1d', ['high'])
        if hist.empty or len(hist) < lookback:
            return False
        max_high = hist['high'].max()
        current_price = get_current_data()[security].last_price
        return current_price <= max_high * (1 - threshold)
    except Exception:
        return False


def qx17_get_premium_rate(code, date, max_back_days=5):
    try:
        price_data = get_price(code, start_date=date, end_date=date,
                               frequency='daily', fields=['close'])
        if price_data.empty:
            return None, None, None
        price = price_data['close'].iloc[0]
        net_value = None
        start_dt = date - datetime.timedelta(days=max_back_days * 2)
        trade_days = get_trade_days(start_date=start_dt, end_date=date)
        trade_days = [pd.to_datetime(d).date() for d in trade_days]
        for dt in reversed(trade_days):
            if dt > date:
                continue
            net_data = get_extras('unit_net_value', code, start_date=dt, end_date=dt, df=True)
            if not net_data.empty and not pd.isna(net_data[code].iloc[0]):
                net_value = net_data[code].iloc[0]
                break
            try:
                q = query(finance.FUND_NET_VALUE).filter(
                    finance.FUND_NET_VALUE.code == code,
                    finance.FUND_NET_VALUE.day == dt,
                )
                net_df = finance.run_query(q)
                if not net_df.empty:
                    net_value = net_df['net_value'].iloc[0]
                    break
            except Exception:
                continue
        if net_value is None or net_value == 0:
            return None, None, None
        return (price - net_value) / net_value, price, net_value
    except Exception:
        return None, None, None


def qx17_get_volume_ratio(context, security, strategy):
    lookback = strategy['volume_lookback']
    threshold = strategy['volume_threshold']
    try:
        hist = attribute_history(security, lookback, '1d', ['volume'])
        if hist.empty or len(hist) < lookback:
            return None
        avg_vol = hist['volume'].mean()
        today = context.current_dt.date()
        df_vol = get_price(security, start_date=today, end_date=context.current_dt,
                           frequency='1m', fields=['volume'], skip_paused=False, fq='pre')
        if df_vol is None or df_vol.empty:
            return None
        current_vol = df_vol['volume'].sum()
        ratio = current_vol / avg_vol if avg_vol > 0 else 0
        return ratio if ratio > threshold else None
    except Exception:
        return None


def qx17_calculate_momentum_metrics(context, etf, strategy):
    try:
        lookback = max(strategy['lookback_days'], strategy['short_lookback_days']) + 20
        prices = attribute_history(etf, lookback, '1d', ['close', 'high'])
        if len(prices) < strategy['lookback_days']:
            return None
        current_price = get_current_data()[etf].last_price
        price_series = np.append(prices['close'].values, current_price)

        if qx17_check_profit_protection(etf, strategy):
            return None

        if strategy['enable_premium_filter']:
            prev_date = get_trade_days(end_date=context.current_dt.date(), count=2)[0]
            premium, _, _ = qx17_get_premium_rate(etf, prev_date,
                                                   strategy['premium_max_back_days'])
            if premium is not None and premium > strategy['premium_threshold']:
                return None

        if strategy['enable_volume_check']:
            vol_ratio = qx17_get_volume_ratio(context, etf, strategy)
            if vol_ratio is not None:
                recent_lb = price_series[-(strategy['lookback_days'] + 1):]
                y = np.log(recent_lb)
                x = np.arange(len(y))
                w = np.linspace(1, 2, len(y))
                slope, _ = np.polyfit(x, y, 1, w=w)
                ann = math.exp(slope * 250) - 1
                if ann > strategy['volume_return_limit']:
                    return None

        if len(price_series) >= strategy['short_lookback_days'] + 1:
            short_ret = price_series[-1] / price_series[-(strategy['short_lookback_days'] + 1)] - 1
            short_ann = (1 + short_ret) ** (250 / strategy['short_lookback_days']) - 1
        else:
            short_ann = 0
        if strategy['use_short_momentum_filter'] and short_ann < strategy['short_momentum_threshold']:
            return None

        recent = price_series[-(strategy['lookback_days'] + 1):]
        y = np.log(recent)
        x = np.arange(len(y))
        weights = np.linspace(1, 2, len(y))
        slope, intercept = np.polyfit(x, y, 1, w=weights)
        annualized_returns = math.exp(slope * 250) - 1
        ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
        ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot != 0 else 0
        score = annualized_returns * r_squared

        if len(price_series) >= 4:
            if min(price_series[-1] / price_series[-2],
                   price_series[-2] / price_series[-3],
                   price_series[-3] / price_series[-4]) < strategy['loss']:
                return None

        return {
            'etf': etf, 'score': score, 'current_price': current_price,
            'annualized_returns': annualized_returns, 'r_squared': r_squared,
            'short_annualized': short_ann,
        }
    except Exception as e:
        log.debug(f'[qx17] {etf} 计算异常: {e}')
        return None


def qx17_get_cached_rankings(context, strategy):
    qx17_apply_pool_config(strategy)
    today = context.current_dt.date()
    cache = strategy['rankings_cache']
    if cache.get('date') != today or cache.get('pool_mode') != strategy['etf_pool_mode']:
        etf_metrics = []
        current_data = get_current_data()
        for etf in strategy['etf_pool']:
            if current_data[etf].paused:
                continue
            m = qx17_calculate_momentum_metrics(context, etf, strategy)
            if m is not None and strategy['min_score_threshold'] < m['score'] < strategy['max_score_threshold']:
                etf_metrics.append(m)
        etf_metrics.sort(key=lambda x: x['score'], reverse=True)
        strategy['rankings_cache'] = {
            'date': today, 'pool_mode': strategy['etf_pool_mode'], 'data': etf_metrics
        }
    return strategy['rankings_cache']['data']


def qx17_check_defensive_etf_available(strategy):
    data = get_current_data()
    etf = strategy['defensive_etf']
    if data[etf].paused:
        return False
    if pd.notna(data[etf].high_limit) and data[etf].high_limit > 0 and data[etf].last_price >= data[etf].high_limit:
        return False
    if pd.notna(data[etf].low_limit) and data[etf].low_limit > 0 and data[etf].last_price <= data[etf].low_limit:
        return False
    return True


def qx17_smart_order_target_value(security, target_value, context, strategy):
    pindex = strategy['pindex']
    data = get_current_data()
    if data[security].paused:
        return False
    price = data[security].last_price
    if price == 0:
        return False
    target_amount = int(target_value / price)
    target_amount = (target_amount // 100) * 100
    if target_amount <= 0 and target_value > 0:
        target_amount = 100

    sub = context.subportfolios[pindex]
    cur_pos = sub.positions.get(security, None)
    cur_amount = cur_pos.total_amount if cur_pos else 0
    diff = target_amount - cur_amount

    high_limit = data[security].high_limit
    low_limit = data[security].low_limit
    if diff > 0 and pd.notna(high_limit) and high_limit > 0 and price >= high_limit:
        return False
    if diff < 0 and pd.notna(low_limit) and low_limit > 0 and price <= low_limit:
        return False

    trade_val = abs(diff) * price
    if 0 < trade_val < strategy['min_money']:
        return False
    if diff < 0:
        closeable = cur_pos.closeable_amount if cur_pos else 0
        if closeable == 0:
            return False
        diff = -min(abs(diff), closeable)

    if diff != 0:
        o = order(security, diff, pindex=pindex)
        if o:
            return True
    return False


def _qx17_profit_protection_check(context, strategy):
    if not strategy['enable_profit_protection']:
        return
    pindex = strategy['pindex']
    managed = qx17_get_managed_universe(strategy)
    for sec in list(context.subportfolios[pindex].positions.keys()):
        if sec not in managed:
            continue
        pos = context.subportfolios[pindex].positions[sec]
        if pos.total_amount > 0 and qx17_check_profit_protection(sec, strategy):
            qx17_smart_order_target_value(sec, 0, context, strategy)


def _qx17_check_positions(context, strategy):
    pindex = strategy['pindex']
    managed = qx17_get_managed_universe(strategy)
    for sec in context.subportfolios[pindex].positions:
        if sec not in managed:
            continue
        pos = context.subportfolios[pindex].positions[sec]
        if pos.total_amount > 0:
            log.info("[多组合]" + f"[{strategy['name']}] 持仓: {sec} {_get_security_name(sec)} "
                     f"数量{pos.total_amount} 成本{pos.avg_cost:.3f} 现价{pos.price:.3f}")


def _qx17_sell_trade(context, strategy):
    pindex = strategy['pindex']
    ranked = qx17_get_cached_rankings(context, strategy)
    target_etfs = []
    for m in ranked[:strategy['holdings_num']]:
        if m['score'] >= strategy['min_score_threshold']:
            target_etfs.append(m['etf'])
    if not target_etfs and qx17_check_defensive_etf_available(strategy):
        target_etfs = [strategy['defensive_etf']]
    target_set = set(target_etfs)
    managed = qx17_get_managed_universe(strategy)

    for sec in list(context.subportfolios[pindex].positions.keys()):
        if sec not in managed:
            continue
        if sec not in target_set:
            pos = context.subportfolios[pindex].positions[sec]
            if pos.total_amount > 0:
                qx17_smart_order_target_value(sec, 0, context, strategy)

    if strategy['enable_premium_filter']:
        prev_date = get_trade_days(end_date=context.current_dt.date(), count=2)[0]
        for sec in list(context.subportfolios[pindex].positions.keys()):
            if sec not in managed:
                continue
            pos = context.subportfolios[pindex].positions[sec]
            if pos.total_amount > 0:
                premium, _, _ = qx17_get_premium_rate(sec, prev_date,
                                                       strategy['premium_max_back_days'])
                if premium is not None and premium > strategy['premium_threshold']:
                    qx17_smart_order_target_value(sec, 0, context, strategy)


def _qx17_buy_trade(context, strategy):
    pindex = strategy['pindex']
    ranked = qx17_get_cached_rankings(context, strategy)
    target_etfs = []
    for m in ranked:
        if len(target_etfs) >= strategy['holdings_num']:
            break
        if m['score'] >= strategy['min_score_threshold']:
            target_etfs.append(m['etf'])
    if not target_etfs:
        if qx17_check_defensive_etf_available(strategy):
            target_etfs = [strategy['defensive_etf']]
        else:
            return

    managed = qx17_get_managed_universe(strategy)
    current_etf_pos = [s for s in context.subportfolios[pindex].positions
                       if s in managed]
    to_sell = [s for s in current_etf_pos if s not in target_etfs]
    if to_sell:
        return

    sub = context.subportfolios[pindex]
    total_val = sub.total_value
    target_per_etf = total_val / len(target_etfs)
    # 再平衡截流
    if strategy.get('rebalance_cap') is not None:
        cap_per_etf = strategy['rebalance_cap'] / len(target_etfs)
        if target_per_etf > cap_per_etf:
            target_per_etf = cap_per_etf

    for etf in target_etfs:
        cur_val = 0
        pos = sub.positions.get(etf, None)
        if pos and pos.total_amount > 0:
            cur_val = pos.total_amount * pos.price
        if abs(cur_val - target_per_etf) > target_per_etf * 0.05 or cur_val == 0:
            qx17_smart_order_target_value(etf, target_per_etf, context, strategy)


# ---- 大池调度包装 ----
def qx17_check_positions_large(context):
    _qx17_check_positions(context, g.qx_large_strategy)

def qx17_profit_protection_check_large(context):
    _qx17_profit_protection_check(context, g.qx_large_strategy)

def qx17_sell_trade_large(context):
    _qx17_sell_trade(context, g.qx_large_strategy)

def qx17_buy_trade_large(context):
    _qx17_buy_trade(context, g.qx_large_strategy)

# ---- 小池调度包装 ----
def qx17_check_positions_small(context):
    _qx17_check_positions(context, g.qx_small_strategy)

def qx17_profit_protection_check_small(context):
    _qx17_profit_protection_check(context, g.qx_small_strategy)

def qx17_sell_trade_small(context):
    _qx17_sell_trade(context, g.qx_small_strategy)

def qx17_buy_trade_small(context):
    _qx17_buy_trade(context, g.qx_small_strategy)


# ============================================================
#  P2 —— 五福3.5
# ============================================================

def wufu_morning_routine(context):
    s = g.wufu_strategy
    wufu_monitor_drawdown(context, s)
    wufu_calculate_global_etf_threshold(context, s)
    wufu_update_sector_pool(context, s)
    wufu_filter_fixed_pool_by_volume(context, s)
    wufu_daily_merge_etf_pools(context, s)


def wufu_rebuild_after_hot_update(context, s):
    try:
        s['cache_date'] = None
        s['ranked_etfs_result'] = []
        s['target_etfs_list'] = []
        s['etf_yesterday_close_batch'] = {}
        s['etf_yesterday_nav_batch'] = {}
        s['filtered_fixed_pool'] = []
        s['dynamic_etf_pool'] = []
        s['merged_etf_pool'] = []
        s['avg_etf_money_threshold'] = None
        wufu_init_range_bound_status(context, s, force=True)
        wufu_morning_routine(context)
        log.info(f"[{s['name']}] 热更新后已重建五福状态与ETF池")
    except Exception as e:
        log.warning(f"[{s['name']}] 热更新后重建五福状态异常: {e}")


def wufu_afternoon_routine(context):
    s = g.wufu_strategy
    if not s.get('merged_etf_pool'):
        # 盘中热更新或重启后，若错过 09:00 早盘池初始化，这里补跑一次
        wufu_morning_routine(context)
    wufu_check_and_exit_range_bound_mode(context, s)
    wufu_check_and_enter_range_bound_mode(context, s)
    wufu_calculate_and_rank_etfs(context, s)
    wufu_execute_sell_trades(context, s)
    wufu_execute_buy_trades(context, s)


def wufu_reset_daily_flags(context):
    s = g.wufu_strategy
    s['cache_date'] = None
    s['yesterday_close_cache'] = {}
    if s['current_filter'] == '震荡期' and s['range_bound_start_date'] is not None:
        trade_days = get_trade_days(start_date=s['range_bound_start_date'],
                                    end_date=context.current_dt.date())
        s['range_bound_days_count'] = len(trade_days) - 1


def wufu_init_range_bound_status(context, s, force=True):
    """Align 五福3.5 startup risk-state initialization with the standalone strategy."""
    if not s['enable_range_bound_mode']:
        return
    if not force and s.get('last_switch_date') is not None:
        return
    try:
        if context.previous_date is None:
            return
        end_date = context.previous_date
        lookback = max(s['ma_period'], s['lookback_high_low_days']) + 30
        df = get_price(s['risk_benchmark'], end_date=end_date, count=lookback,
                       frequency='daily', fields=['close', 'high', 'low'], panel=False)
        if df is None or len(df) < max(s['ma_period'], s['lookback_high_low_days']):
            return
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        cur_price = close[-1]
        if len(close) >= s['lookback_high_low_days']:
            recent_high = np.max(high[-s['lookback_high_low_days']:])
            recent_low = np.min(low[-s['lookback_high_low_days']:])
        else:
            recent_high = np.max(high)
            recent_low = np.min(low)
        ma = np.mean(close[-s['ma_period']:])
        bias = (cur_price - ma) / ma if ma > 0 else 0
        rsi = _calculate_rsi(close)
        signals = []
        if s['enable_bias_trigger'] and bias > s['bias_threshold']:
            signals.append(f"乖离率{bias:.2%}>{s['bias_threshold']:.0%}")
        if s['enable_rsi_trigger'] and rsi is not None and len(close) >= 15:
            prev_rsi = _calculate_rsi(close[:-1])
            if prev_rsi is not None and prev_rsi > s['rsi_overbought'] and rsi < s['rsi_pullback']:
                signals.append(f"RSI超买回落{prev_rsi:.1f}->{rsi:.1f}")
        if signals:
            s['current_filter'] = '震荡期'
            s['risk_state'] = '震荡期'
            s['range_bound_start_date'] = end_date
            s['range_bound_days_count'] = 0
            log.info(f"[{s['name']}] 首次运行初始化进入震荡期: {'; '.join(signals)}")
        else:
            s['current_filter'] = '正常期'
            s['risk_state'] = '正常期'
            s['previous_drawdown'] = (recent_high - cur_price) / recent_high if recent_high > 0 else 0
            s['previous_rsi'] = rsi
            rise = (cur_price - recent_low) / recent_low if recent_low > 0 else 0
            log.info(f"[{s['name']}] 首次运行初始状态: 正常期, 乖离率: {bias:.2%}, "
                     f"RSI: {rsi:.1f}, 从低点涨幅: {rise:.2%}")
    except Exception as e:
        log.warning(f"[{s['name']}] 首次运行初始化震荡期状态异常: {e}")


def wufu_monitor_drawdown(context, s):
    pindex = s['pindex']
    try:
        current_value = context.subportfolios[pindex].total_value
        if current_value > s['max_portfolio_value']:
            s['max_portfolio_value'] = current_value
        if s['max_portfolio_value'] > 0:
            dd = (s['max_portfolio_value'] - current_value) / s['max_portfolio_value']
            if dd >= s['drawdown_threshold']:
                log.info("[多组合]" + f"[{s['name']}] 回撤预警: {dd:.2%}")
    except Exception as e:
        log.debug(f"[wufu] 回撤监控异常: {e}")


def wufu_calculate_global_etf_threshold(context, s):
    try:
        df_etf = get_all_securities(['etf'], date=context.current_dt)
        etf_list = df_etf.index.tolist()
        if not etf_list:
            s['avg_etf_money_threshold'] = 10000000
            return
        trade_days = get_trade_days(end_date=context.previous_date, count=3)
        start_day = trade_days[0]
        df = get_price(security=etf_list, start_date=start_day, end_date=context.previous_date,
                       frequency='daily', fields=['money'], panel=False, skip_paused=True)
        if df is None or df.empty:
            s['avg_etf_money_threshold'] = 10000000
            return
        daily_totals = df.groupby('time')['money'].sum()
        if len(daily_totals) < 3:
            s['avg_etf_money_threshold'] = 10000000
            return
        avg_total = daily_totals.mean()
        s['avg_etf_money_threshold'] = avg_total / 20000
    except Exception as e:
        log.debug(f"[wufu] 阈值计算异常: {e}")
        s['avg_etf_money_threshold'] = 10000000


def wufu_update_sector_pool(context, s):
    """更新行业ETF动态池：对齐单独版五福3.5的分组、清洗和流动性逻辑。"""
    log.info(f"[{s['name']}][动态池更新] 开始执行")
    if s['avg_etf_money_threshold'] is None:
        wufu_calculate_global_etf_threshold(context, s)
    FUND_COMPANIES = sorted(list(set([
        '易方达', '广发', '华夏', '华安', '嘉实', '富国', '招商', '鹏华', '南方', '汇添富', '国泰', '平安',
        '银华', '天弘', '建信', '工银', '华泰柏瑞', '博时', '景顺长城', '景顺', '华宝', '申万菱信', '万家', '中欧',
        '兴证全球', '浙商', '诺安', '前海开源', '泰康', '泰达宏利', '农银汇理', '交银', '东方红', '财通', '华商',
        '国联', '永赢', '金鹰', '德邦', '创金合信', '西部利得', '圆信永丰', '泓德', '汇安', '诺德', '恒生前海',
        '华润元大', '大成', '海富通', '摩根', '华泰', '中信', '中银', '兴全', '国信', '长城', '中金', '浙商证券',
        '东海', '东吴', '浦银安盛', '信达澳亚', '中加', '中航', '中融', '中邮', '中庚', '中信保诚', '中信建投',
        '中银国际', '中银证券', '九泰', '交银施罗德', '光大保德信', '兴银', '农银', '国投瑞银', '国海富兰克林',
        '国联安', '国金', '太平', '方正富邦', '民生加银', '汇丰晋信', '银河', '长信', '长安', '长盛', '长江证券', '鹏扬'
    ])), key=len, reverse=True)
    NOISE_WORDS = sorted(list(set([
        '6666', '8888', '9999', 'A类', 'AH', 'B', 'BS', 'C', 'C类', 'CS', 'DB', 'E', 'E类',
        'ETF', 'ETF基金', 'ETF联接', 'FG', 'G60', 'GF', 'GT', 'HGS', 'LOF', 'LOF基金', 'LOF联接',
        'SG', 'SZ', 'TF', 'TK', 'WJ', 'YH', 'ZS', 'ZZ', '板块', '策略', '产业', '场内', '场外', '低波',
        '基本面', '基金', '精选', '联接', '联接基金', '量化', '龙头', '民企', '民营', '国企', '央企', '智能',
        '全指', '上市开放式', '指基', '指增', '指数', '指数A', '指数C', '指数ETF', '指数基金', '主题', '增强',
        '上海', '黄', '30', '50', '100', '300', '500', '1000', '2000', '大', '新', '四川', '浙江', '湖北',
    ])), key=len, reverse=True)
    SPECIAL_GROUPS = sorted([
        {'name': '香港组', 'keywords': sorted(['恒生', '恒指', '港股', '港股通', 'H股', '香港', '港', 'HKC', 'HK', 'HGS', 'H', '中概', 'HS科技'], key=len, reverse=True),
         'remove_words': sorted(['恒生', '恒指', '港股', '港股通', 'H股', '香港', '港', 'HKC', 'HK', 'HGS', 'H', '中概', 'HS'], key=len, reverse=True)},
        {'name': '科创组', 'keywords': sorted(['科创', '科创板', '科综', 'KC', 'K C', '双创', '科创创业', '创创'], key=len, reverse=True),
         'remove_words': sorted(['科创', '科创板', '科综', 'KC', 'K C', '双创', '科创创业', '创创', '债券', '债汇', '债指', '债沪', '债易', '债基', '债兴', '债摩', '债', 'AAA'], key=len, reverse=True)},
        {'name': '创业组', 'keywords': sorted(['创业板', '创业', '创板', '创成长'], key=len, reverse=True),
         'remove_words': sorted(['创业板', '创业', '创板', '创成长'], key=len, reverse=True)},
        {'name': '美指组', 'keywords': sorted(['标普', '纳指', '纳斯达克'], key=len, reverse=True),
         'remove_words': sorted(['标普', '纳指', '纳斯达克'], key=len, reverse=True)}
    ], key=lambda x: max(len(kw) for kw in x['keywords']), reverse=True)
    exclude_keywords = sorted(list(set([
        '300', '500', '1000', '2000', '800', '30', '50', '100', '180', '200',
        '沪深', '中证', '上证', '深证', '深成', 'A50', 'A100', 'A500', '深100',
        '短融', '可转债', '转债', '双债', '利率债', '国债', '地债', '政金债', '国开债', '基准国债', '新综债',
        '信用债', '企业债', '公司债', '城投债', '城投', '美元债', '沪公司债', '科创债', '科债', '科创AAA',
        '自由现金流', '现金流', '现金流E', '现金流基', '现金流TF', '现金流全', '300现金流', '800现金流',
        '货币', '现金', '快线', '快钱', '中银现金', '500现金', '800现金', '现金800', '现金自由', '现金指数',
        '全指现金', '现金全指', 'ESG', 'MSCI', 'MS', '债',
    ])), key=len, reverse=True)

    def contains_keyword(name, keywords):
        for k in keywords:
            if not k:
                continue
            try:
                if k in name:
                    return True
            except Exception:
                continue
        return False

    try:
        df_etf = get_all_securities(['etf'])
        etf_list = df_etf.index.tolist()
        s['etf_names_dict'] = df_etf['display_name'].to_dict()
    except Exception as e:
        log.warning(f"[{s['name']}][动态池更新] 获取全市场ETF列表失败: {e}")
        return
    log.info(f"[{s['name']}][动态池更新] 全市场ETF总数: {len(etf_list)}只")
    normal_etfs = []
    special_etfs = []
    special_group_map = {}
    excluded_count = 0
    for code in etf_list:
        try:
            name = s['etf_names_dict'].get(code, str(code))
            is_special = False
            matched_group = None
            for group in SPECIAL_GROUPS:
                if contains_keyword(name, group['keywords']):
                    is_special = True
                    matched_group = group['name']
                    break
            if contains_keyword(name, exclude_keywords):
                excluded_count += 1
                continue
            if is_special:
                special_etfs.append(code)
                special_group_map[code] = matched_group
            else:
                normal_etfs.append(code)
        except Exception:
            continue

    if etf_list and excluded_count >= len(etf_list) * 0.9:
        log.warning(f"[{s['name']}][动态池更新] 排除比例异常({excluded_count}/{len(etf_list)})，"
                    "重试时跳过排除词，避免动态池被清空")
        normal_etfs = []
        special_etfs = []
        special_group_map = {}
        excluded_count = 0
        for code in etf_list:
            try:
                name = s['etf_names_dict'].get(code, str(code))
                is_special = False
                matched_group = None
                for group in SPECIAL_GROUPS:
                    if contains_keyword(name, group['keywords']):
                        is_special = True
                        matched_group = group['name']
                        break
                if is_special:
                    special_etfs.append(code)
                    special_group_map[code] = matched_group
                else:
                    normal_etfs.append(code)
            except Exception:
                continue
    group_counts = {}
    for code in special_etfs:
        group_name = special_group_map.get(code, '未知')
        group_counts[group_name] = group_counts.get(group_name, 0) + 1
    log.info(f"[{s['name']}][动态池更新] 特别组分布: {group_counts}")
    log.info(f"[{s['name']}][动态池更新] 进入特别组: {len(special_etfs)}只")
    log.info(f"[{s['name']}][动态池更新] 进入普通组: {len(normal_etfs)}只")
    log.info(f"[{s['name']}][动态池更新] 排除ETF: {excluded_count}只")

    end_date = context.previous_date
    threshold = s['avg_etf_money_threshold']
    if threshold is None:
        threshold = 10000000

    def filter_by_liquidity(etf_codes, group_name):
        if not etf_codes:
            return pd.Series(dtype=float)
        try:
            price_data = get_price(etf_codes, end_date=end_date, count=3,
                                   frequency='daily', fields=['money'], panel=False)
            if price_data is None or price_data.empty:
                return pd.Series(dtype=float)
            total_money = price_data.groupby('code')['money'].sum()
            avg_daily = total_money / 3
            return avg_daily[avg_daily > threshold].sort_values(ascending=False)
        except Exception as e:
            log.warning(f"[{s['name']}][动态池更新] {group_name}流动性过滤异常: {e}")
            return pd.Series(dtype=float)

    normal_qualified = filter_by_liquidity(normal_etfs, '普通组')
    special_qualified = filter_by_liquidity(special_etfs, '特别组')
    log.info(f"[{s['name']}][动态池更新] 特别组流动性过滤: {len(special_etfs)}->{len(special_qualified)}只")
    log.info(f"[{s['name']}][动态池更新] 普通组流动性过滤: {len(normal_etfs)}->{len(normal_qualified)}只")
    if normal_qualified.empty and special_qualified.empty:
        log.warning(f"[{s['name']}][动态池更新] 无ETF通过流动性过滤，动态池为空")
        s['dynamic_etf_pool'] = []
        return

    def get_remove_words_for_etf(is_special, matched_group_name):
        if not is_special:
            return []
        for group in SPECIAL_GROUPS:
            if group['name'] == matched_group_name:
                return group['remove_words']
        return []

    def clean_name(original_name, is_special=False, matched_group_name=None):
        cleaned = original_name
        for company in FUND_COMPANIES:
            cleaned = cleaned.replace(company, '')
        for word in get_remove_words_for_etf(is_special, matched_group_name):
            cleaned = cleaned.replace(word, '')
        for noise in NOISE_WORDS:
            cleaned = cleaned.replace(noise, '')
        return cleaned.strip()

    final_pool_info = []
    normal_groups = {}
    for code in normal_qualified.index.tolist():
        try:
            original_name = s['etf_names_dict'].get(code, str(code))
            cleaned = clean_name(original_name)
            if cleaned == '':
                continue
            key = cleaned[:2] if len(cleaned) >= 2 else cleaned
            normal_groups.setdefault(key, []).append((code, original_name, cleaned, normal_qualified[code]))
        except Exception:
            continue
    for items in normal_groups.values():
        code, original_name, cleaned, money = sorted(items, key=lambda x: x[3], reverse=True)[0]
        final_pool_info.append({'code': code, 'original_name': original_name, 'cleaned_name': cleaned, 'money': money})

    special_groups = {}
    for code in special_qualified.index.tolist():
        try:
            original_name = s['etf_names_dict'].get(code, str(code))
            matched_group = special_group_map.get(code, '未知')
            cleaned = clean_name(original_name, is_special=True, matched_group_name=matched_group)
            if cleaned == '':
                continue
            key = cleaned[:2] if len(cleaned) >= 2 else cleaned
            group_key = f"{matched_group}_{key}"
            special_groups.setdefault(group_key, []).append((code, original_name, cleaned, special_qualified[code]))
        except Exception:
            continue
    for items in special_groups.values():
        code, original_name, cleaned, money = sorted(items, key=lambda x: x[3], reverse=True)[0]
        final_pool_info.append({'code': code, 'original_name': original_name, 'cleaned_name': cleaned, 'money': money})

    final_pool_info = sorted(final_pool_info, key=lambda x: x['money'], reverse=True)
    if final_pool_info:
        s['dynamic_etf_pool'] = [item['code'] for item in final_pool_info[:100]]
    else:
        qualified = pd.concat([normal_qualified, special_qualified]).sort_values(ascending=False)
        s['dynamic_etf_pool'] = qualified.index.tolist()[:100]
        log.warning(f"[{s['name']}][动态池更新] 分组清洗结果为空，使用流动性排序前100兜底")
    log.info(f"[{s['name']}][动态池更新完成] 动态池共{len(s['dynamic_etf_pool'])}只ETF")


def wufu_filter_fixed_pool_by_volume(context, s):
    if not s['fixed_etf_pool']:
        return
    threshold = s.get('avg_etf_money_threshold', 10000000)
    end_date = context.previous_date
    try:
        price_data = get_price(s['fixed_etf_pool'], end_date=end_date, count=3,
                               frequency='daily', fields=['money'], panel=False)
        if price_data is None or price_data.empty:
            s['filtered_fixed_pool'] = s['fixed_etf_pool'][:]
            return
        total_money = price_data.groupby('code')['money'].sum()
        avg_daily = total_money / 3
        qualified = avg_daily[avg_daily > threshold]
        s['filtered_fixed_pool'] = qualified.index.tolist()
    except Exception:
        s['filtered_fixed_pool'] = s['fixed_etf_pool'][:]


def wufu_daily_merge_etf_pools(context, s):
    merged = list(set(s['filtered_fixed_pool'] + s['dynamic_etf_pool']))
    merged.sort()
    s['merged_etf_pool'] = merged
    log.info("[多组合]" + f"[{s['name']}] 合并池: 固定{len(s['filtered_fixed_pool'])} + "
             f"动态{len(s['dynamic_etf_pool'])} = 合并{len(merged)}")


def wufu_calculate_momentum_score(price_series, lookback_days):
    if len(price_series) < lookback_days + 1:
        return None, None, None
    recent = price_series[-(lookback_days + 1):]
    y = np.log(recent)
    x = np.arange(len(y))
    weights = np.linspace(1, 2, len(y))
    W = weights ** 2
    W_sum = np.sum(W)
    x_bar = np.sum(W * x) / W_sum
    y_bar = np.sum(W * y) / W_sum
    dx, dy = x - x_bar, y - y_bar
    var_x = np.sum(W * dx ** 2)
    if var_x == 0:
        return 0, 0, 0
    slope = np.sum(W * dx * dy) / var_x
    intercept = y_bar - slope * x_bar
    ann = math.exp(slope * 250) - 1
    y_pred = slope * x + intercept
    ss_res = np.sum(weights * (y - y_pred) ** 2)
    ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
    r2 = 1 - ss_res / ss_tot if ss_tot else 0
    return ann * r2, ann, r2


def wufu_calculate_and_rank_etfs(context, s):
    if not s['merged_etf_pool']:
        s['ranked_etfs_result'] = []
        return
    etf_set = list(s['merged_etf_pool'])
    end_date = context.previous_date
    today = context.current_dt.date()
    lookback = max(s['lookback_days'], s['short_momentum_lookback'], s['volume_lookback']) + 20
    current_data = get_current_data()
    try:
        hist_df = get_price(etf_set, count=lookback + 20, end_date=end_date,
                            frequency='1d', fields=['close', 'volume'], panel=False)
        today_vol_df = get_price(etf_set, start_date=today, end_date=context.current_dt,
                                  frequency='1m', fields=['volume'], panel=False, fill_paused=False)
        if hist_df is None or hist_df.empty:
            s['ranked_etfs_result'] = []
            return
        # batch nav/close
        try:
            y_price_df = get_price(etf_set, start_date=end_date, end_date=end_date,
                                    fields=['close'], panel=False)
            s['etf_yesterday_close_batch'] = y_price_df.groupby('code')['close'].last().to_dict() \
                if y_price_df is not None and not y_price_df.empty else {}
            nav_df = get_extras('unit_net_value', etf_set, start_date=end_date, end_date=end_date)
            s['etf_yesterday_nav_batch'] = nav_df.iloc[-1].to_dict() \
                if nav_df is not None and not nav_df.empty else {}
        except Exception:
            s['etf_yesterday_close_batch'] = {}
            s['etf_yesterday_nav_batch'] = {}
        today_vols = today_vol_df.groupby('code')['volume'].sum() \
            if today_vol_df is not None and not today_vol_df.empty else pd.Series(dtype=float)
        close_pivot = hist_df.pivot(index='time', columns='code', values='close')
        vol_pivot = hist_df.pivot(index='time', columns='code', values='volume')
        all_metrics = []
        for etf in etf_set:
            if current_data[etf].paused or etf not in close_pivot.columns:
                continue
            raw_closes = close_pivot[etf].values
            raw_vols = vol_pivot[etf].values
            valid = (~np.isnan(raw_vols)) & (raw_vols > 0)
            hist_closes = raw_closes[valid][-lookback:]
            hist_vols = raw_vols[valid][-lookback:]
            if len(hist_closes) < max(s['lookback_days'], s['short_momentum_lookback']):
                continue
            cur_price = current_data[etf].last_price
            tv = today_vols.get(etf, 0)
            m = wufu_calc_metrics(etf, hist_closes, hist_vols, cur_price, tv, context, s)
            if m:
                all_metrics.append(m)
        # sort + filter
        use_short = s['use_short_momentum_period']
        score_key = 'short_momentum_score' if use_short else 'momentum_score'
        for item in all_metrics:
            if item[score_key] is None or (isinstance(item[score_key], float) and np.isnan(item[score_key])):
                item[score_key] = float('-inf')
        all_metrics.sort(key=lambda x: x.get(score_key, float('-inf')), reverse=True)
        filtered = wufu_apply_filters(all_metrics, s)
        filtered.sort(key=lambda x: x.get(score_key, float('-inf')), reverse=True)
        top_10 = filtered[:10]
        if not top_10:
            s['ranked_etfs_result'] = []
            log.info(f"[{s['name']}] 无符合全部过滤条件的ETF")
            return

        if len(top_10) >= s['holdings_num']:
            reference_score = top_10[s['holdings_num'] - 1].get(score_key, float('-inf'))
            score_threshold = reference_score * s['score_threshold_ratio']
            candidate_pool = [item for item in top_10 if item.get(score_key, float('-inf')) >= score_threshold]
        else:
            candidate_pool = top_10[:]

        pindex = s['pindex']
        current_holdings = [sec for sec, pos in context.subportfolios[pindex].positions.items()
                            if pos.total_amount > 0]
        candidate_dict = {item['etf']: item for item in candidate_pool}
        retained = [candidate_dict[etf] for etf in current_holdings if etf in candidate_dict]
        if len(retained) >= s['holdings_num']:
            final_result = sorted(retained, key=lambda x: x.get(score_key, float('-inf')), reverse=True)[:s['holdings_num']]
        else:
            need = s['holdings_num'] - len(retained)
            retained_codes = {item['etf'] for item in retained}
            additional = [item for item in candidate_pool if item['etf'] not in retained_codes][:need]
            final_result = retained + additional

        s['ranked_etfs_result'] = final_result
        if final_result:
            log.info(f"[{s['name']}] 目标ETF: " +
                     ', '.join(f"{m['etf']} {_get_security_name(m['etf'])}" for m in final_result))
    except Exception as e:
        log.warn(f"[wufu] 排名计算异常: {e}")
        s['ranked_etfs_result'] = []


def wufu_calc_metrics(etf, hist_closes, hist_vols, cur_price, today_vol, context, s):
    try:
        price_series = np.append(hist_closes, cur_price)
        ms, ann, r2 = wufu_calculate_momentum_score(price_series, s['lookback_days'])
        sms, _, _ = wufu_calculate_momentum_score(price_series, s['short_momentum_lookback'])
        if ms is None:
            return None
        passed_m = s['min_score_threshold'] <= ms <= s['max_score_threshold']
        passed_sm = (s['short_momentum_min_score'] <= sms <= s['short_momentum_max_score']) \
            if sms is not None else False
        # volume ratio
        lookback_v = s['volume_lookback']
        avg_vol = np.mean(hist_vols[-lookback_v:]) if len(hist_vols) >= lookback_v else None
        vol_ratio = None
        if avg_vol and avg_vol > 0 and today_vol > 0:
            now = context.current_dt
            elapsed = (now.hour - 9) * 60 + now.minute - 30
            if now.hour >= 13:
                elapsed -= 90
            elapsed = max(1, min(elapsed, 240))
            proj = today_vol * (240.0 / elapsed)
            vol_ratio = proj / avg_vol
        passed_vol = vol_ratio is not None and vol_ratio < s['volume_threshold']
        # loss filter
        passed_loss = True
        if len(price_series) >= 4:
            if min(price_series[-1] / price_series[-2],
                   price_series[-2] / price_series[-3],
                   price_series[-3] / price_series[-4]) < s['loss']:
                passed_loss = False
        # filters
        passed_r2 = r2 > s['r2_threshold']
        # laplace / gaussian
        lv, ls, pla, gv, gs, pga = 0, 0, False, 0, 0, False
        if len(price_series) >= 10:
            try:
                laplace_vals = _laplace_filter(price_series, s=s['laplace_s_param'])
                if len(laplace_vals) >= 2:
                    lv = laplace_vals[-1]
                    ls = laplace_vals[-1] - laplace_vals[-2]
                    pla = cur_price > lv and ls > s['laplace_min_slope']
                g1, g2 = _gaussian_filter_last_two(price_series, s['gaussian_sigma'])
                gv, gs = g1, g1 - g2
                pga = cur_price > g1 and gs > s['gaussian_min_slope']
            except Exception:
                pass
        if s['current_filter'] == '正常期':
            passed_filter = pla
        else:
            passed_filter = pga
        # premium
        passed_premium = True
        if s['enable_premium_filter']:
            try:
                ep = s['etf_yesterday_close_batch'].get(etf)
                nav = s['etf_yesterday_nav_batch'].get(etf)
                if ep and nav and nav > 0:
                    pr = (ep - nav) / nav * 100
                    passed_premium = pr <= s['max_premium_rate']
            except Exception:
                pass
        return {
            'etf': etf, 'momentum_score': ms, 'short_momentum_score': sms,
            'annualized_returns': ann, 'r_squared': r2, 'current_price': cur_price,
            'volume_ratio': vol_ratio,
            'passed_momentum': passed_m, 'passed_short_momentum': passed_sm,
            'passed_r2': passed_r2, 'passed_volume': passed_vol,
            'passed_loss': passed_loss, 'passed_premium': passed_premium,
            'passed_laplace': pla, 'passed_gaussian': pga,
            'passed_filter': pla if s['current_filter'] == '正常期' else pga,
        }
    except Exception as e:
        log.debug(f"[wufu] {etf} 指标计算异常: {e}")
        return None


def wufu_apply_filters(metrics_list, s):
    use_short = s['use_short_momentum_period']
    steps = [
        ('动量得分', lambda m: m['passed_momentum'], not use_short),
        ('短期动量', lambda m: m['passed_short_momentum'], use_short),
        ('R²', lambda m: m['passed_r2'], s['enable_r2_filter']),
        ('成交量', lambda m: m['passed_volume'], s['enable_volume_check']),
        ('短期风控', lambda m: m['passed_loss'], s['enable_loss_filter']),
        ('溢价率', lambda m: m['passed_premium'], s['enable_premium_filter']),
        ('动态滤波', lambda m: m['passed_filter'], s['enable_range_bound_mode']),
    ]
    filtered = metrics_list[:]
    for name, cond, enabled in steps:
        if enabled:
            filtered = [m for m in filtered if cond(m)]
    return filtered


def wufu_execute_sell_trades(context, s):
    pindex = s['pindex']
    ranked = s['ranked_etfs_result']
    target_etfs = [m['etf'] for m in ranked[:s['holdings_num']]] if ranked else []
    if not target_etfs:
        data = get_current_data()
        def_etf = s['defensive_etf']
        if not data[def_etf].paused:
            target_etfs = [def_etf]
    s['target_etfs_list'] = target_etfs
    target_set = set(target_etfs)
    for sec in list(context.subportfolios[pindex].positions.keys()):
        pos = context.subportfolios[pindex].positions[sec]
        if pos.total_amount > 0 and sec not in target_set:
            wufu_smart_order(sec, 0, context, s)


def wufu_execute_buy_trades(context, s):
    pindex = s['pindex']
    target_etfs = s.get('target_etfs_list', [])
    if not target_etfs:
        return
    current_pos = set(context.subportfolios[pindex].positions.keys())
    to_buy = [e for e in target_etfs if e not in current_pos]
    already = len(current_pos)
    max_buy = max(0, s['holdings_num'] - already)
    if max_buy <= 0:
        return
    to_buy = to_buy[:max_buy]
    available = context.subportfolios[pindex].available_cash
    alloc = available // len(to_buy) if to_buy else 0
    if alloc < s['min_money']:
        return
    # rebalance cap
    if s.get('rebalance_cap') is not None:
        cap_alloc = s['rebalance_cap'] / len(to_buy) if to_buy else 0
        if cap_alloc < alloc:
            alloc = cap_alloc
    for i, etf in enumerate(to_buy):
        val = alloc if i < len(to_buy) - 1 else context.subportfolios[pindex].available_cash
        wufu_smart_order(etf, val, context, s)


def wufu_smart_order(security, target_value, context, s):
    pindex = s['pindex']
    data = get_current_data()
    if data[security].paused:
        return False
    price = data[security].last_price
    if price <= 0:
        return False
    high_limit = data[security].high_limit
    low_limit = data[security].low_limit
    if pd.notna(high_limit) and high_limit > 0 and price >= high_limit:
        log.info(f"[{s['name']}] {security} {_get_security_name(security)} 涨停，跳过交易")
        return False
    if pd.notna(low_limit) and low_limit > 0 and price <= low_limit:
        log.info(f"[{s['name']}] {security} {_get_security_name(security)} 跌停，跳过交易")
        return False
    target_amount = int(target_value / price)
    target_amount = (target_amount // 100) * 100
    if target_amount <= 0 and target_value > 0:
        target_amount = 100
    sub = context.subportfolios[pindex]
    cur_pos = sub.positions.get(security, None)
    cur_amount = cur_pos.total_amount if cur_pos else 0
    diff = target_amount - cur_amount
    trade_val = abs(diff) * price
    if 0 < trade_val < s['min_money']:
        return False
    if diff < 0:
        closeable = cur_pos.closeable_amount if cur_pos else 0
        if closeable == 0:
            return False
        diff = -min(abs(diff), closeable)
    if diff != 0:
        o = order(security, diff, pindex=pindex)
        if o:
            action = '买入' if diff > 0 else '卖出'
            log.info(f"[多组合][交易][{s['name']}][pindex={pindex}] {action} "
                     f"{security} {_get_security_name(security)} 数量{abs(diff)} 目标金额{target_value:.2f}")
            return True
        log.info(f"[多组合][交易][{s['name']}][pindex={pindex}] 下单失败 "
                 f"{security} {_get_security_name(security)} 数量{diff}")
        return False
    return False


def wufu_check_and_enter_range_bound_mode(context, s):
    if not s['enable_range_bound_mode']:
        return
    if s['current_filter'] == '震荡期':
        return
    if s['last_switch_date'] is not None:
        days_since = len(get_trade_days(start_date=s['last_switch_date'],
                                         end_date=context.current_dt.date())) - 1
        if days_since < s['filter_switch_cooldown']:
            return
    risk_signals = []
    try:
        lookback = max(s['ma_period'], s['lookback_high_low_days']) + 10
        df = get_price(s['risk_benchmark'], end_date=context.previous_date, count=lookback,
                       frequency='daily', fields=['close'], panel=False)
        if df is not None and len(df) >= max(s['ma_period'], s['lookback_high_low_days']):
            close = df['close'].values
            cur_price = close[-1]
            if s['enable_bias_trigger']:
                ma = np.mean(close[-s['ma_period']:])
                bias = (cur_price - ma) / ma if ma > 0 else 0
                if bias > s['bias_threshold']:
                    risk_signals.append(f"乖离率({bias:.2%})")
            if s['enable_rsi_trigger']:
                cur_rsi = _calculate_rsi(close)
                if len(close) >= 15 and cur_rsi is not None:
                    prev_rsi = _calculate_rsi(close[:-1])
                    if prev_rsi is not None and prev_rsi > s['rsi_overbought'] \
                       and cur_rsi < s['rsi_pullback'] and cur_rsi < prev_rsi:
                        risk_signals.append(f"RSI超买回落({prev_rsi:.1f}->{cur_rsi:.1f})")
    except Exception as e:
        log.debug(f"[wufu] 震荡期进入检查异常: {e}")
    if s['enable_stop_loss_trigger'] and s['stop_loss_triggered_today']:
        risk_signals.append("今日触发止损")
        s['stop_loss_triggered_today'] = False
    if risk_signals:
        s['current_filter'] = '震荡期'
        s['risk_state'] = '震荡期'
        s['last_switch_date'] = context.current_dt.date()
        s['range_bound_start_date'] = context.current_dt.date()
        s['range_bound_days_count'] = 0
        s['stable_days'] = 0
        log.info(f"[{s['name']}] 进入震荡期: {'; '.join(risk_signals)}")
    else:
        log.info(f"[{s['name']}] 保持正常期")


def wufu_check_and_exit_range_bound_mode(context, s):
    if not s['enable_range_bound_mode'] or s['current_filter'] != '震荡期':
        return
    try:
        lookback = max(s['ma_period'], s['lookback_high_low_days']) + 10
        df = get_price(s['risk_benchmark'], end_date=context.previous_date, count=lookback,
                       frequency='daily', fields=['close', 'high', 'low'], panel=False)
        if df is None or len(df) < max(s['ma_period'], s['lookback_high_low_days']):
            return
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        cur_price = close[-1]
        recent_high = np.max(high[-s['lookback_high_low_days']:])
        recent_low = np.min(low[-s['lookback_high_low_days']:])
        cur_dd = (recent_high - cur_price) / recent_high if recent_high > 0 else 0
        rise = (cur_price - recent_low) / recent_low if recent_low > 0 else 0
        cur_rsi = _calculate_rsi(close)
        recovery = []
        if s['enable_low_point_rise_trigger'] and rise >= s['low_point_rise_threshold']:
            recovery.append(f"从低点涨{rise:.2%}")
        if s['enable_stable_signal_trigger']:
            ma = np.mean(close[-s['ma_period']:])
            if cur_price > ma:
                recovery.append("站上均线")
            if cur_dd < s['drawdown_recovery']:
                s['stable_days'] += 1
            else:
                s['stable_days'] = 0
        range_days = 0
        if s['range_bound_start_date']:
            range_days = len(get_trade_days(start_date=s['range_bound_start_date'],
                                             end_date=context.current_dt.date())) - 1
        if range_days >= s['max_range_bound_days']:
            recovery.append(f"震荡期满{range_days}天")
        low_cond = s['enable_low_point_rise_trigger'] and rise >= s['low_point_rise_threshold']
        stable_cond = s['enable_stable_signal_trigger'] and cur_dd < s['drawdown_recovery'] \
            and len(recovery) >= 2 and s['stable_days'] >= 2
        force_cond = range_days >= s['max_range_bound_days']
        if low_cond or stable_cond or force_cond:
            if s['last_switch_date'] is not None:
                days_since = len(get_trade_days(start_date=s['last_switch_date'],
                                                 end_date=context.current_dt.date())) - 1
                if days_since < s['filter_switch_cooldown']:
                    return
            s['current_filter'] = '正常期'
            s['risk_state'] = '正常期'
            s['last_switch_date'] = context.current_dt.date()
            s['range_bound_start_date'] = None
            s['range_bound_days_count'] = 0
            s['stable_days'] = 0
            log.info(f"[{s['name']}] 退出震荡期: {'; '.join(recovery)}")
        s['previous_drawdown'] = cur_dd
        s['previous_rsi'] = cur_rsi
    except Exception as e:
        log.debug(f"[wufu] 震荡期退出异常: {e}")


def wufu_minute_stop_loss(context):
    s = g.wufu_strategy
    if not s['use_fixed_stop_loss']:
        return
    cur_time = context.current_dt.strftime('%H:%M')
    if not (('09:25' < cur_time < '11:30') or ('13:00' < cur_time < '14:57')):
        return
    pindex = s['pindex']
    data = get_current_data()
    for sec in list(context.subportfolios[pindex].positions.keys()):
        pos = context.subportfolios[pindex].positions[sec]
        if pos.total_amount <= 0 or pos.closeable_amount <= 0:
            continue
        price = data[sec].last_price
        if price <= 0 or pos.avg_cost <= 0:
            continue
        if price <= pos.avg_cost * s['fixedStopLossThreshold']:
            if wufu_smart_order(sec, 0, context, s) and s['enable_stop_loss_trigger']:
                s['stop_loss_triggered_today'] = True


def wufu_minute_pct_stop_loss(context):
    s = g.wufu_strategy
    if not s['use_pct_stop_loss']:
        return
    cur_time = context.current_dt.strftime('%H:%M')
    if not (('09:25' < cur_time < '11:30') or ('13:00' < cur_time < '14:57')):
        return
    pindex = s['pindex']
    data = get_current_data()
    cur_date = context.current_dt.date()
    if s.get('cache_date') != cur_date:
        s['yesterday_close_cache'] = {}
        s['cache_date'] = cur_date
    for sec in list(context.subportfolios[pindex].positions.keys()):
        pos = context.subportfolios[pindex].positions[sec]
        if pos.total_amount <= 0 or pos.closeable_amount <= 0:
            continue
        yc = s['yesterday_close_cache'].get(sec)
        if yc is None:
            try:
                h = attribute_history(sec, 1, '1d', ['close'], skip_paused=False)
                if not h['close'].empty:
                    yc = h['close'][-1]
                    if yc > 0:
                        s['yesterday_close_cache'][sec] = yc
            except Exception:
                continue
        if not yc or yc <= 0:
            continue
        price = data[sec].last_price
        if price <= 0:
            continue
        if price <= yc * s['pct_stop_loss_threshold']:
            if wufu_smart_order(sec, 0, context, s) and s['enable_stop_loss_trigger']:
                s['stop_loss_triggered_today'] = True


# ============================================================
#  P3 —— 七星520
# ============================================================

def q520_check_profit_protection(security, s):
    if not s['enable_profit_protection']:
        return False
    lookback = s['profit_protection_lookback']
    threshold = s['profit_protection_threshold']
    try:
        hist = attribute_history(security, lookback, '1d', ['high'])
        if hist.empty or len(hist) < lookback:
            return False
        max_high = hist['high'].max()
        return get_current_data()[security].last_price <= max_high * (1 - threshold)
    except Exception:
        return False


def q520_get_premium_rate(code, date, max_back_days=5):
    return qx17_get_premium_rate(code, date, max_back_days)


def q520_get_volume_ratio(context, security, s):
    lookback = s['volume_lookback']
    threshold = s['volume_threshold']
    try:
        hist = attribute_history(security, lookback, '1d', ['volume'])
        if hist.empty or len(hist) < lookback:
            return None
        avg_vol = hist['volume'].mean()
        today = context.current_dt.date()
        df_vol = get_price(security, start_date=today, end_date=context.current_dt,
                           frequency='1m', fields=['volume'], skip_paused=False, fq='pre')
        if df_vol is None or df_vol.empty:
            return None
        ratio = df_vol['volume'].sum() / avg_vol if avg_vol > 0 else 0
        return ratio if ratio > threshold else None
    except Exception:
        return None


def q520_calculate_momentum_metrics(context, etf, s):
    try:
        lookback = max(s['lookback_days'], s['short_lookback_days']) + 20
        prices = attribute_history(etf, lookback, '1d', ['close', 'high'])
        if len(prices) < s['lookback_days']:
            return None
        cur_price = get_current_data()[etf].last_price
        price_series = np.append(prices['close'].values, cur_price)

        if q520_check_profit_protection(etf, s):
            return None
        if s['enable_premium_filter']:
            prev_date = get_trade_days(end_date=context.current_dt.date(), count=2)[0]
            premium, _, _ = q520_get_premium_rate(etf, prev_date)
            if premium is not None and premium > s['premium_threshold']:
                return None
        if s['enable_volume_check']:
            vol = q520_get_volume_ratio(context, etf, s)
            if vol is not None:
                recent_lb = price_series[-(s['lookback_days'] + 1):]
                y = np.log(recent_lb)
                x = np.arange(len(y))
                w = np.linspace(1, 2, len(y))
                slope, _ = np.polyfit(x, y, 1, w=w)
                ann = math.exp(slope * 250) - 1
                if ann > s['volume_return_limit']:
                    return None
        if len(price_series) >= s['short_lookback_days'] + 1:
            short_ret = price_series[-1] / price_series[-(s['short_lookback_days'] + 1)] - 1
            short_ann = (1 + short_ret) ** (250 / s['short_lookback_days']) - 1
        else:
            short_ann = 0
        if s['use_short_momentum_filter'] and short_ann < s['short_momentum_threshold']:
            return None
        recent = price_series[-(s['lookback_days'] + 1):]
        y = np.log(recent)
        x = np.arange(len(y))
        weights = np.linspace(1, 2, len(y))
        slope, intercept = np.polyfit(x, y, 1, w=weights)
        ann_ret = math.exp(slope * 250) - 1
        ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
        ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot != 0 else 0
        score = ann_ret * r2
        if len(price_series) >= 4:
            if min(price_series[-1] / price_series[-2],
                   price_series[-2] / price_series[-3],
                   price_series[-3] / price_series[-4]) < s['loss']:
                return None
        # dynamic filter
        if s['enable_range_bound_mode'] and len(price_series) >= 10:
            try:
                lv = _laplace_filter(price_series, s=s['laplace_s_param'])
                ls = lv[-1] - lv[-2] if len(lv) >= 2 else 0
                passed_la = cur_price > lv[-1] and ls > s['laplace_min_slope']
                g1, g2 = _gaussian_filter_last_two(price_series, s['gaussian_sigma'])
                gs = g1 - g2
                passed_ga = cur_price > g1 and gs > s['gaussian_min_slope']
                if s['current_filter'] == '正常期' and not passed_la:
                    return None
                if s['current_filter'] == '震荡期' and not passed_ga:
                    return None
            except Exception:
                pass
        return {'etf': etf, 'score': score, 'current_price': cur_price,
                'short_annualized': short_ann}
    except Exception as e:
        log.debug(f"[q520] {etf} 计算异常: {e}")
        return None


def q520_get_cached_rankings(context, s):
    today = context.current_dt.date()
    if s['rankings_cache']['date'] != today:
        etf_metrics = []
        data = get_current_data()
        checked_count = 0
        for etf in s['etf_pool']:
            if data[etf].paused:
                continue
            checked_count += 1
            m = q520_calculate_momentum_metrics(context, etf, s)
            if m is not None and s['min_score_threshold'] < m['score'] < s['max_score_threshold']:
                etf_metrics.append(m)
        etf_metrics.sort(key=lambda x: x['score'], reverse=True)
        s['rankings_cache'] = {'date': today, 'data': etf_metrics}
        if etf_metrics:
            top = etf_metrics[0]
            log.info(f"[{s['name']}] 排名完成: 检查{checked_count}只, 入选{len(etf_metrics)}只, "
                     f"第一名 {top['etf']} {_get_security_name(top['etf'])} 得分{top['score']:.4f}")
        else:
            log.info(f"[{s['name']}] 排名完成: 检查{checked_count}只, 入选0只, 准备使用防御ETF")
    return s['rankings_cache']['data']


def q520_check_range_bound(context):
    s = g.q520_strategy
    if not s['enable_range_bound_mode']:
        return
    q520_check_and_exit_range_bound_mode(context, s)
    q520_check_and_enter_range_bound_mode(context, s)
    s['rankings_cache'] = {'date': None, 'data': None}


def q520_check_and_enter_range_bound_mode(context, s):
    if not s['enable_range_bound_mode'] or s['current_filter'] == '震荡期':
        return
    if s['last_switch_date'] is not None:
        days_since = len(get_trade_days(start_date=s['last_switch_date'],
                                         end_date=context.current_dt.date())) - 1
        if days_since < s['filter_switch_cooldown']:
            return
    risk_signals = []
    try:
        req = max(s['ma_period'], s['lookback_high_low_days'])
        df = get_price(s['risk_benchmark'], end_date=context.previous_date,
                       count=req + 30, frequency='daily',
                       fields=['close', 'high', 'low'], panel=False)
        if df is not None and len(df) >= req:
            close = df['close'].values
            cur_price = close[-1]
            if s['enable_bias_trigger']:
                ma = np.mean(close[-s['ma_period']:])
                bias = (cur_price - ma) / ma if ma > 0 else 0
                if bias > s['bias_threshold']:
                    risk_signals.append(f"乖离率({bias:.2%})")
            if s['enable_rsi_trigger']:
                cur_rsi = _calculate_rsi(close)
                if len(close) >= 15 and cur_rsi is not None:
                    prev_rsi = _calculate_rsi(close[:-1])
                    if prev_rsi is not None and prev_rsi > s['rsi_overbought'] \
                       and cur_rsi < s['rsi_pullback'] and cur_rsi < prev_rsi:
                        risk_signals.append(f"RSI超买回落({prev_rsi:.1f}->{cur_rsi:.1f})")
    except Exception as e:
        log.debug(f"[q520] 震荡期进入检查异常: {e}")
    stop_signal = False
    if s['enable_stop_loss_trigger']:
        sd = s.get('stop_loss_triggered_date')
        if sd is not None:
            today = context.current_dt.date()
            prev = getattr(context, 'previous_date', None)
            if sd == today or (prev is not None and sd == prev):
                stop_signal = True
            else:
                s['stop_loss_triggered_today'] = False
                s['stop_loss_triggered_date'] = None
    if stop_signal:
        risk_signals.append("盈利保护触发止损")
    if risk_signals:
        s['current_filter'] = '震荡期'
        s['risk_state'] = '震荡期'
        s['last_switch_date'] = context.current_dt.date()
        s['range_bound_start_date'] = context.current_dt.date()
        s['range_bound_days_count'] = 0
        s['stable_days'] = 0
        s['stop_loss_triggered_today'] = False
        s['stop_loss_triggered_date'] = None
        log.info(f"[{s['name']}] 进入震荡期: {'; '.join(risk_signals)}")
    else:
        log.info(f"[{s['name']}] 保持正常期")


def q520_check_and_exit_range_bound_mode(context, s):
    if not s['enable_range_bound_mode'] or s['current_filter'] != '震荡期':
        return
    try:
        req = max(s['ma_period'], s['lookback_high_low_days'])
        df = get_price(s['risk_benchmark'], end_date=context.previous_date,
                       count=req + 30, frequency='daily',
                       fields=['close', 'high', 'low'], panel=False)
        if df is None or len(df) < req:
            return
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        cur_price = close[-1]
        recent_high = np.max(high[-s['lookback_high_low_days']:])
        recent_low = np.min(low[-s['lookback_high_low_days']:])
        cur_dd = (recent_high - cur_price) / recent_high if recent_high > 0 else 0
        rise = (cur_price - recent_low) / recent_low if recent_low > 0 else 0
        cur_rsi = _calculate_rsi(close)
        recovery = []
        if s['enable_low_point_rise_trigger'] and rise >= s['low_point_rise_threshold']:
            recovery.append(f"从低点涨{rise:.2%}")
        if s['enable_stable_signal_trigger']:
            ma = np.mean(close[-s['ma_period']:])
            if cur_price > ma:
                recovery.append("站上均线")
            if cur_dd < s['drawdown_recovery']:
                s['stable_days'] += 1
            else:
                s['stable_days'] = 0
        range_days = 0
        if s['range_bound_start_date']:
            range_days = len(get_trade_days(start_date=s['range_bound_start_date'],
                                             end_date=context.current_dt.date())) - 1
        if range_days >= s['max_range_bound_days']:
            recovery.append(f"震荡期满{range_days}天")
        low_cond = s['enable_low_point_rise_trigger'] and rise >= s['low_point_rise_threshold']
        stable_cond = s['enable_stable_signal_trigger'] and cur_dd < s['drawdown_recovery'] \
            and len(recovery) >= 2 and s['stable_days'] >= 2
        force_cond = range_days >= s['max_range_bound_days']
        if low_cond or stable_cond or force_cond:
            if s['last_switch_date'] is not None:
                days_since = len(get_trade_days(start_date=s['last_switch_date'],
                                                 end_date=context.current_dt.date())) - 1
                if days_since < s['filter_switch_cooldown']:
                    return
            s['current_filter'] = '正常期'
            s['risk_state'] = '正常期'
            s['last_switch_date'] = context.current_dt.date()
            s['range_bound_start_date'] = None
            s['range_bound_days_count'] = 0
            s['stable_days'] = 0
            log.info(f"[{s['name']}] 退出震荡期: {'; '.join(recovery)}")
        s['previous_drawdown'] = cur_dd
        s['previous_rsi'] = cur_rsi
    except Exception as e:
        log.debug(f"[q520] 震荡期退出异常: {e}")


def q520_check_defensive_available(s):
    data = get_current_data()
    etf = s['defensive_etf']
    if data[etf].paused:
        log.info(f"[{s['name']}] 防御ETF {etf} {_get_security_name(etf)} 停牌，无法买入")
        return False
    if data[etf].last_price <= 0:
        log.info(f"[{s['name']}] 防御ETF {etf} {_get_security_name(etf)} 价格无效，无法买入")
        return False
    # 511880 等货币/债券类防御标的在聚宽中可能出现 last_price == high_limit。
    # 防御兜底不能因此长期空仓，只要未停牌且价格有效就允许作为现金替代持有。
    return True


def q520_smart_order_target_value(security, target_value, context, s):
    pindex = s['pindex']
    data = get_current_data()
    if data[security].paused:
        return False
    price = data[security].last_price
    if price <= 0:
        return False
    high_limit = data[security].high_limit
    low_limit = data[security].low_limit
    is_defensive = security == s.get('defensive_etf')
    if (not is_defensive and target_value > 0 and pd.notna(high_limit)
            and high_limit > 0 and price >= high_limit):
        log.info(f"[{s['name']}] {security} {_get_security_name(security)} 涨停，跳过买入")
        return False
    if target_value == 0 and pd.notna(low_limit) and low_limit > 0 and price <= low_limit:
        log.info(f"[{s['name']}] {security} {_get_security_name(security)} 跌停，跳过卖出")
        return False
    target_amount = int(target_value / price)
    target_amount = (target_amount // 100) * 100
    if target_amount <= 0 and target_value > 0:
        target_amount = 100
    sub = context.subportfolios[pindex]
    cur_pos = sub.positions.get(security, None)
    cur_amount = cur_pos.total_amount if cur_pos else 0
    diff = target_amount - cur_amount
    trade_val = abs(diff) * price
    if 0 < trade_val < s['min_money']:
        return False
    if diff < 0:
        closeable = cur_pos.closeable_amount if cur_pos else 0
        if closeable == 0:
            return False
        diff = -min(abs(diff), closeable)
    if diff != 0:
        o = order(security, diff, pindex=pindex)
        if o:
            action = '买入' if diff > 0 else '卖出'
            log.info(f"[多组合][交易][{s['name']}] {action} {security} {_get_security_name(security)} "
                     f"数量{abs(diff)} 目标金额{target_value:.2f}")
            return True
        log.info(f"[多组合][交易][{s['name']}] 下单失败 {security} {_get_security_name(security)} 数量{diff}")
        return False
    return False


def q520_check_positions(context):
    s = g.q520_strategy
    pindex = s['pindex']
    for sec in context.subportfolios[pindex].positions:
        pos = context.subportfolios[pindex].positions[sec]
        if pos.total_amount > 0:
            log.info("[多组合][持仓]" + f"[{s['name']}] 持仓: {sec} {_get_security_name(sec)} 数量{pos.total_amount} 成本{pos.avg_cost:.3f} 现价{pos.price:.3f}")


def q520_profit_protection_check(context):
    s = g.q520_strategy
    if not s['enable_profit_protection']:
        return
    pindex = s['pindex']
    for sec in list(context.subportfolios[pindex].positions.keys()):
        if sec not in s['etf_pool'] and sec != s['defensive_etf']:
            continue
        pos = context.subportfolios[pindex].positions[sec]
        if pos.total_amount > 0 and q520_check_profit_protection(sec, s):
            if q520_smart_order_target_value(sec, 0, context, s):
                log.info("[多组合][卖出]" + f"[{s['name']}] 盈利保护卖出: {sec}")
                if s['enable_stop_loss_trigger']:
                    s['stop_loss_triggered_today'] = True
                    s['stop_loss_triggered_date'] = context.current_dt.date()


def q520_sell_trade(context):
    s = g.q520_strategy
    pindex = s['pindex']
    ranked = q520_get_cached_rankings(context, s)
    target_etfs = [m['etf'] for m in ranked[:s['holdings_num']]
                   if m['score'] >= s['min_score_threshold']]
    if not target_etfs and q520_check_defensive_available(s):
        target_etfs = [s['defensive_etf']]
        log.info(f"[{s['name']}] 无目标ETF，卖出检查使用防御ETF: {s['defensive_etf']} {_get_security_name(s['defensive_etf'])}")
    target_set = set(target_etfs)
    for sec in list(context.subportfolios[pindex].positions.keys()):
        if sec not in s['etf_pool'] and sec != s['defensive_etf']:
            continue
        pos = context.subportfolios[pindex].positions[sec]
        if pos.total_amount > 0 and sec not in target_set:
            q520_smart_order_target_value(sec, 0, context, s)
    # premium check on existing positions
    if s['enable_premium_filter']:
        prev_date = get_trade_days(end_date=context.current_dt.date(), count=2)[0]
        for sec in list(context.subportfolios[pindex].positions.keys()):
            pos = context.subportfolios[pindex].positions[sec]
            if pos.total_amount > 0:
                premium, _, _ = q520_get_premium_rate(sec, prev_date)
                if premium is not None and premium > s['premium_threshold']:
                    q520_smart_order_target_value(sec, 0, context, s)


def q520_buy_trade(context):
    s = g.q520_strategy
    pindex = s['pindex']
    ranked = q520_get_cached_rankings(context, s)
    target_etfs = []
    for m in ranked:
        if len(target_etfs) >= s['holdings_num']:
            break
        if m['score'] >= s['min_score_threshold']:
            target_etfs.append(m['etf'])
    if target_etfs:
        log.info(f"[{s['name']}] 目标ETF: " +
                 ', '.join(f"{e} {_get_security_name(e)}" for e in target_etfs))
    if not target_etfs:
        if q520_check_defensive_available(s):
            target_etfs = [s['defensive_etf']]
            log.info(f"[{s['name']}] 无目标ETF，进入防御模式: {s['defensive_etf']} {_get_security_name(s['defensive_etf'])}")
        else:
            log.info(f"[{s['name']}] 无目标ETF且防御ETF不可用，保持现金")
            return
    sub = context.subportfolios[pindex]
    current_pos = []
    for sec, pos in sub.positions.items():
        if pos.total_amount > 0 and (sec in s['etf_pool'] or sec == s['defensive_etf']):
            current_pos.append(sec)
    to_sell = [sec for sec in current_pos if sec not in target_etfs]
    if len(to_sell) > 0:
        log.info(f"[{s['name']}] 尚有非目标持仓待卖出，等待下一次买入: {to_sell}")
        return
    total_val = sub.total_value
    per_etf = total_val / len(target_etfs)
    if s.get('rebalance_cap') is not None:
        cap_per = s['rebalance_cap'] / len(target_etfs)
        if cap_per < per_etf:
            per_etf = cap_per
    for etf in target_etfs:
        cur_val = 0
        pos = sub.positions.get(etf, None)
        if pos and pos.total_amount > 0:
            cur_val = pos.total_amount * pos.price
        if abs(cur_val - per_etf) > per_etf * 0.05 or cur_val == 0:
            ok = q520_smart_order_target_value(etf, per_etf, context, s)
            if not ok:
                log.info(f"[{s['name']}] 买入/调仓未成交: {etf} {_get_security_name(etf)} 目标金额{per_etf:.2f}")


def q520_reset_range_bound_daily(context):
    s = g.q520_strategy
    if s['current_filter'] == '震荡期' and s['range_bound_start_date'] is not None:
        trade_days = get_trade_days(start_date=s['range_bound_start_date'],
                                     end_date=context.current_dt.date())
        s['range_bound_days_count'] = len(trade_days) - 1


# ============================================================
#  P4 —— 小市值
# ============================================================

def small_before_trading(context):
    s = g.small_strategy
    s['days'] = s.get('days', 0) + 1
    pindex = s['pindex']
    s['yesterday_HL_list'] = []
    positions = context.subportfolios[pindex].positions
    if positions:
        stocks = list(positions.keys())
        try:
            df = get_price(stocks, end_date=context.previous_date,
                           fields=['close', 'high_limit'], frequency='daily', count=1,
                           panel=False)
            s['yesterday_HL_list'] = list(
                df[df['close'] == df['high_limit']]['code'].unique())
        except Exception:
            pass


def small_check_macd_divergence_daily(context):
    s = g.small_strategy
    if not s['DBL_control']:
        return
    if not s['dbl'] and '9:31' in str(context.current_dt.time()):
        return
    result = 1 if small_detect_macd_divergence(context) else 0
    s['dbl'].append(result)
    if len(s['dbl']) > 200:
        s['dbl'] = s['dbl'][-200:]
    if result:
        pindex = s['pindex']
        data = get_current_data()
        for stock in list(context.subportfolios[pindex].positions.keys()):
            pos = context.subportfolios[pindex].positions[stock]
            if pos.closeable_amount > 0 and data[stock].last_price < data[stock].high_limit:
                order_target(stock, 0, pindex=pindex)


def small_detect_macd_divergence(context, end_days=0):
    try:
        fast, slow, sign = 12, 26, 9
        rows = (fast + slow + sign) * 5
        grid = attribute_history('399101.XSHE', rows + 10, fields=['close']).dropna()
        if end_days < 0:
            grid = grid.iloc[:end_days]
        if len(grid) < rows:
            return False
        dif, dea, macd = _mcad(grid.close, fast, slow, sign)
        mask = (macd < 0) & (macd.shift(1) >= 0)
        if mask.sum() < 2:
            return False
        k2, k1 = mask[mask].index[-2], mask[mask].index[-1]
        price_cond = grid.close[k2] < grid.close[k1]
        dif_cond = dif[k2] > dif[k1] > 0
        macd_cond = macd.iloc[-2] > 0 > macd.iloc[-1]
        trend_cond = dif.iloc[-10:].mean() < dif.iloc[-20:-10].mean() if len(dif) > 20 else False
        return price_cond and dif_cond and macd_cond and trend_cond
    except Exception:
        return False


def small_iSell(context):
    s = g.small_strategy
    pindex = s['pindex']
    if s['DBL_control'] and len(s['dbl']) < 10:
        for i in range(9, -1, -1):
            s['dbl'].append(1 if small_detect_macd_divergence(context, end_days=0 - i) else 0)
    if s['DBL_control'] and 1 in s['dbl'][-s['check_macd_divergence_days']:]:
        log.info("[多组合][风险]" + f"[{s['name']}] 顶背离模式，暂停卖出")
        return
    if s['enable_dynamic_stock_num']:
        try:
            today = context.previous_date
            start_date = today - datetime.timedelta(days=20)
            index_df = get_price('399101.XSHE', start_date=start_date, end_date=today, frequency='daily')
            index_df['ma'] = index_df['close'].rolling(10).mean()
            diff = index_df.iloc[-1]['close'] - index_df.iloc[-1]['ma']
            s['max_position_count'] = 3 if diff >= 200 else 4 if diff >= -200 else \
                5 if diff >= -500 else 6
        except Exception:
            pass
    target_list = small_get_stocks_v3(context, s)
    s['stocks'] = target_list
    hl_list = s['yesterday_HL_list']
    for stock in list(context.subportfolios[pindex].positions.keys()):
        pos = context.subportfolios[pindex].positions[stock]
        if pos.total_amount > 0 and stock not in target_list and stock not in hl_list:
            if pos.closeable_amount > 0:
                order_target(stock, 0, pindex=pindex)
            else:
                log.info("[多组合][风险]" + f"[{s['name']}] {stock} T+1 不可卖")


def small_iBuy(context):
    s = g.small_strategy
    pindex = s['pindex']
    if s['DBL_control'] and 1 in s['dbl'][-s['check_macd_divergence_days']:]:
        log.info("[多组合][风险]" + f"[{s['name']}] 顶背离模式，暂停买入")
        return
    current_positions = context.subportfolios[pindex].positions
    target_list = s.get('stocks', [])
    buy_list = [st for st in target_list if st not in current_positions
                or current_positions[st].total_amount == 0]
    available = context.subportfolios[pindex].available_cash
    position_size = available / len(buy_list) if buy_list else 0
    if s.get('rebalance_cap') is not None and buy_list:
        cap = s['rebalance_cap']
        existing = sum(pos.value for pos in current_positions.values())
        max_buy = max(0, cap - existing) / len(buy_list)
        if max_buy < position_size:
            position_size = max_buy
    data = get_current_data()
    for stock in buy_list:
        if available < 100 * data[stock].last_price:
            break
        if data[stock].paused:
            continue
        buy_val = position_size
        if buy_val < s['min_buy_amount']:
            continue
        if not data[stock].paused and data[stock].last_price < data[stock].high_limit:
            o = order_target_value(stock, buy_val, pindex=pindex)
            if o:
                available -= buy_val
    small_update_atr_stop_prices(context)


def small_daily_stoploss(context):
    s = g.small_strategy
    if s['enable_atr_stop_loss']:
        small_check_atr_stop_loss(context, s)
    if s['stoploss_strategy'] in [1, 3]:
        small_check_cost_protection_stop_loss(context, s)
    if s['stoploss_strategy'] in [2, 3]:
        small_check_market_stop_loss(context, s)


def small_check_limit_up(context):
    s = g.small_strategy
    pindex = s['pindex']
    for stock in list(s['yesterday_HL_list']):
        if stock in context.subportfolios[pindex].positions:
            try:
                data = get_current_data()
                if data[stock].last_price < data[stock].high_limit:
                    log.info("[多组合][卖出]" + f"[{s['name']}] {stock} 涨停打开，清仓")
                    pos = context.subportfolios[pindex].positions[stock]
                    if pos.closeable_amount > 0:
                        order_target(stock, 0, pindex=pindex)
            except Exception:
                pass


def small_update_atr_stop_prices(context):
    s = g.small_strategy
    small_update_atr_stop_prices_impl(context, s)


def small_update_atr_stop_prices_impl(context, s):
    pindex = s['pindex']
    positions = context.subportfolios[pindex].positions
    for stock in positions.keys():
        atr = small_calculate_atr(stock, context, s['atr_period'])
        if atr:
            if stock not in s['atr_stop_prices']:
                s['atr_stop_prices'][stock] = positions[stock].avg_cost - s['atr_multiplier'] * atr
            else:
                trailing = positions[stock].price - s['atr_multiplier'] * atr
                if trailing > s['atr_stop_prices'][stock]:
                    s['atr_stop_prices'][stock] = trailing


def small_calculate_atr(security, context, period=14):
    try:
        df = get_price(security, end_date=context.previous_date, count=period + 1,
                       frequency='daily', fields=['high', 'low', 'close'])
        if len(df) < period + 1:
            return None
        df['pre_close'] = df['close'].shift(1)
        df['tr'] = df[['high', 'low', 'pre_close']].apply(
            lambda x: max(x[0] - x[1], abs(x[0] - x[2]), abs(x[1] - x[2])), axis=1)
        return df['tr'].iloc[-period:].mean()
    except Exception:
        return None


def small_check_atr_stop_loss(context, s):
    pindex = s['pindex']
    positions = context.subportfolios[pindex].positions
    for stock in list(positions.keys()):
        if stock in s['atr_stop_prices'] and positions[stock].price <= s['atr_stop_prices'][stock]:
            if positions[stock].closeable_amount > 0:
                order_target(stock, 0, pindex=pindex)
                if s['enable_cooldown']:
                    s['no_buy_stocks'][stock] = context.current_dt.date()
            del s['atr_stop_prices'][stock]


def small_check_cost_protection_stop_loss(context, s):
    pindex = s['pindex']
    positions = context.subportfolios[pindex].positions
    for stock in list(positions.keys()):
        price = positions[stock].price
        avg_cost = positions[stock].avg_cost
        if avg_cost <= 0:
            continue
        ratio = (price - avg_cost) / avg_cost
        if price >= avg_cost * 2:
            if positions[stock].closeable_amount > 0:
                order_target(stock, 0, pindex=pindex)
            s['atr_stop_prices'].pop(stock, None)
            continue
        stop_line = -s['stoploss_limit']
        if ratio >= s['cost_protection_profit_threshold_2']:
            stop_line = s['cost_protection_stop_line_2']
        elif ratio >= s['cost_protection_profit_threshold_1']:
            stop_line = s['cost_protection_stop_line_1']
        if ratio < stop_line:
            if positions[stock].closeable_amount > 0:
                order_target(stock, 0, pindex=pindex)
            if s['enable_cooldown']:
                s['no_buy_stocks'][stock] = context.current_dt.date()
            s['atr_stop_prices'].pop(stock, None)


def small_check_market_stop_loss(context, s):
    try:
        df = get_price(security=get_index_stocks('399101.XSHE'), end_date=context.previous_date,
                       frequency='daily', fields=['close', 'open'], count=1, panel=False)
        avg_change = (df['close'] / df['open'] - 1).mean()
        if avg_change <= -s['stoploss_market']:
            pindex = s['pindex']
            log.warn("[多组合][风险]" + f"[{s['name']}] 大盘暴跌 {avg_change:.2%}，市场止损")
            for stock in list(context.subportfolios[pindex].positions.keys()):
                pos = context.subportfolios[pindex].positions[stock]
                if pos.closeable_amount > 0:
                    order_target(stock, 0, pindex=pindex)
                s['atr_stop_prices'].pop(stock, None)
    except Exception as e:
        log.debug(f"[small] 市场止损检查异常: {e}")


def small_get_stocks_v3(context, s):
    try:
        initial_list = small_filter_basic_stocks(context, s,
                                                  get_index_stocks('399101.XSHE'))
        q = query(valuation.code, valuation.market_cap, income.net_profit,
                  income.operating_revenue).filter(
            valuation.code.in_(initial_list),
            valuation.market_cap.between(s['filter_market_cap_min'], s['filter_market_cap_max']),
            income.operating_revenue > 1e8,
            indicator.roe > 0, indicator.roa > 0, income.net_profit > 2000000
        ).order_by(valuation.market_cap.asc()).limit(s['max_position_count'] * 5)
        candidate_list = list(get_fundamentals(q, date=context.previous_date).code)
        start_audit = datetime.date(2025, 1, 1)
        if context.current_dt.date() > start_audit:
            audited = small_apply_nine_point_audit(context, s, candidate_list)
        else:
            audited = small_filter_audit(context, s, candidate_list)
        final = small_bonus_filter(context, s, audited)
        final = small_filter_cooldown_stocks(context, s, final)
        if not final:
            return [s['defensive_etf']]
        last_prices = history(1, unit='1d', field='close', security_list=final)
        pindex = s['pindex']
        positions = context.subportfolios[pindex].positions
        return [st for st in final
                if st in positions or last_prices[st][-1] <= s['max_stock_price']
                ][:s['max_position_count']]
    except Exception as e:
        log.warn("[多组合][选股]" + f"[{s['name']}] 选股异常: {e}")
        return []


def small_filter_basic_stocks(context, s, stock_list):
    data = get_current_data()
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    positions = context.subportfolios[s['pindex']].positions
    result = []
    for stock in stock_list:
        if data[stock].paused or data[stock].is_st or '退' in data[stock].name:
            continue
        code = stock.split('.')[0]
        if code.startswith(('30', '68', '8', '4')):
            continue
        if not (stock in positions or last_prices[stock][-1] < data[stock].high_limit):
            continue
        if not (stock in positions or last_prices[stock][-1] > data[stock].low_limit):
            continue
        si = get_security_info(stock)
        if si is None:
            continue
        start_date = si.start_date
        if hasattr(start_date, 'date'):
            start_date = start_date.date()
        if context.previous_date - start_date < datetime.timedelta(days=s['min_listed_days']):
            continue
        result.append(stock)
    return result


def small_apply_nine_point_audit(context, s, stock_list):
    if not stock_list:
        return []
    yesterday = context.previous_date
    curr_year, curr_month = yesterday.year, yesterday.month
    report_year = curr_year - 2 if curr_month <= 4 else curr_year - 1
    report_date_str = f"{report_year}-12-31"
    q = query(
        valuation.code, indicator.adjusted_profit, income.net_profit,
        cash_flow.subtotal_operate_cash_inflow, cash_flow.subtotal_operate_cash_outflow,
        balance.good_will, balance.equities_parent_company_owners,
        balance.total_liability, balance.total_assets,
        balance.shortterm_loan, balance.cash_equivalents
    ).filter(valuation.code.in_(stock_list))
    fund_df = get_fundamentals(q, date=yesterday)
    if fund_df.empty:
        return stock_list
    fund_df = fund_df.set_index('code').fillna(0)
    final_list = []
    max_tol = s.get('audit_tolerance', 2)
    for stock in stock_list:
        score, reasons = 0, []
        try:
            sname = get_security_info(stock).display_name if get_security_info(stock) else ''
            if hasattr(finance, 'STK_INCOME_STATEMENT'):
                q_t = query(finance.STK_INCOME_STATEMENT.pub_date).filter(
                    finance.STK_INCOME_STATEMENT.code == stock,
                    finance.STK_INCOME_STATEMENT.end_date == report_date_str,
                    finance.STK_INCOME_STATEMENT.pub_date <= yesterday).limit(1)
                t_df = finance.run_query(q_t)
                if not t_df.empty:
                    ad = t_df['pub_date'].iloc[0]
                    if isinstance(ad, str):
                        ad = datetime.datetime.strptime(ad, '%Y-%m-%d').date()
                    elif hasattr(ad, 'date'):
                        ad = ad.date()
                    if ad and ad > datetime.date(report_year + 1, 4, 20):
                        score += 1; reasons.append('年报迟发')
            if hasattr(finance, 'STK_FIN_FORCAST'):
                q_f = query(finance.STK_FIN_FORCAST).filter(
                    finance.STK_FIN_FORCAST.code == stock,
                    finance.STK_FIN_FORCAST.end_date == report_date_str,
                    finance.STK_FIN_FORCAST.pub_date <= yesterday).limit(1)
                f_df = finance.run_query(q_f)
                if not f_df.empty and f_df['type_id'].iloc[0] in [3, 4, 5, 9, 10]:
                    score += 1; reasons.append('业绩预告不良')
            if hasattr(finance, 'STK_AUDIT_OPINION'):
                q_a = query(finance.STK_AUDIT_OPINION).filter(
                    finance.STK_AUDIT_OPINION.code == stock,
                    finance.STK_AUDIT_OPINION.end_date == report_date_str,
                    finance.STK_AUDIT_OPINION.pub_date <= yesterday).limit(1)
                a_df = finance.run_query(q_a)
                if not a_df.empty and a_df['opinion_type_id'].iloc[0] in [3, 4, 5]:
                    continue
            if stock in fund_df.index:
                row = fund_df.loc[stock]
                if row['adjusted_profit'] < 0 or (row['net_profit'] != 0 and
                   row['adjusted_profit'] / row['net_profit'] < 0.5):
                    score += 1; reasons.append('主业存疑')
                if row['net_profit'] > 0 and (row['subtotal_operate_cash_inflow'] -
                   row['subtotal_operate_cash_outflow']) < 0:
                    score += 1; reasons.append('现金流异常')
                if row['equities_parent_company_owners'] > 0 and \
                   row['good_will'] / row['equities_parent_company_owners'] > 0.3:
                    score += 1; reasons.append('高危资产')
                dr = row['total_liability'] / row['total_assets'] if row['total_assets'] > 0 else 0
                if dr > 0.70 or row['shortterm_loan'] > row['cash_equivalents']:
                    score += 1; reasons.append(f'资金链({dr:.0%})')
            if hasattr(finance, 'STK_SHARES_PLEDGE'):
                q_p = query(finance.STK_SHARES_PLEDGE).filter(
                    finance.STK_SHARES_PLEDGE.code == stock,
                    finance.STK_SHARES_PLEDGE.pub_date <= yesterday
                ).order_by(finance.STK_SHARES_PLEDGE.pub_date.desc()).limit(1)
                p_df = finance.run_query(q_p)
                if not p_df.empty:
                    rc = 'pledge_proportion' if 'pledge_proportion' in p_df.columns else \
                         'pledge_ratio' if 'pledge_ratio' in p_df.columns else None
                    if rc and p_df[rc].iloc[0] > 80:
                        score += 1; reasons.append('大股东高质押')
            if hasattr(finance, 'STK_INVESTIGATION'):
                q_i = query(finance.STK_INVESTIGATION).filter(
                    finance.STK_INVESTIGATION.code == stock,
                    finance.STK_INVESTIGATION.pub_date >= f"{curr_year-1}-01-01",
                    finance.STK_INVESTIGATION.pub_date <= yesterday).limit(1)
                if not finance.run_query(q_i).empty:
                    score += 1; reasons.append('曾遭监管立案')
            if score > 0 and s.get('log_filter_detail', True):
                log.info(f"[{s['name']}][排雷] {stock}({sname}) 踩雷{score}项: "
                         f"{' | '.join(reasons)}")
            if score < max_tol:
                final_list.append(stock)
        except Exception as e:
            log.debug(f"[small] 排雷 {stock} 异常: {e}")
            final_list.append(stock)
    return final_list


def small_filter_audit(context, s, code_list):
    final = []
    for stock in code_list:
        try:
            prev = context.previous_date
            last_year = (prev.replace(year=prev.year - 3, month=1, day=1)).strftime('%Y-%m-%d')
            q = query(finance.STK_AUDIT_OPINION.code).filter(
                finance.STK_AUDIT_OPINION.code == stock,
                finance.STK_AUDIT_OPINION.pub_date >= last_year,
                finance.STK_AUDIT_OPINION.pub_date <= prev
            )
            df = finance.run_query(q)
            if df.empty or not df['opinion_type_id'].isin([3, 4, 5, 7]).any() \
               if 'opinion_type_id' in df.columns else True:
                final.append(stock)
        except Exception:
            final.append(stock)
    return final


def small_bonus_filter(context, s, stock_list):
    if not s.get('enable_bonus_filter'):
        return stock_list
    try:
        year = context.previous_date.year
        end_date = context.previous_date
        start_date = datetime.datetime(year=year, month=1, day=1)
        if end_date.month in [5]:
            q = query(finance.STK_XR_XD.code, finance.STK_XR_XD.bonus_amount_rmb,
                      finance.STK_XR_XD.bonus_ratio_rmb).filter(
                finance.STK_XR_XD.board_plan_pub_date > start_date,
                finance.STK_XR_XD.implementation_pub_date <= end_date,
                finance.STK_XR_XD.bonus_ratio_rmb > 0,
                finance.STK_XR_XD.code.in_(stock_list),
            )
            expected_bonus = finance.run_query(q)
            if len(expected_bonus) > 0:
                bonus_list = expected_bonus['code'].unique().tolist()
                price_df = history(1, unit='1d', field='close', security_list=bonus_list,
                                   df=True, skip_paused=False, fq=None).T
                price_df.rename(columns={price_df.columns[0]: 'Close_now'}, inplace=True)
                price_df['code'] = price_df.index
                expected_bonus = pd.merge(expected_bonus, price_df, on=('code',), how='left')
                expected_bonus['bonus_ratio'] = expected_bonus['bonus_ratio_rmb'] / expected_bonus['Close_now']
                expected_bonus = expected_bonus.sort_values(by='bonus_ratio', ascending=True)
                bonus_list = expected_bonus['code'].unique().tolist()
            else:
                bonus_list = []
        else:
            report_date = datetime.datetime(year=year - 1, month=12, day=31)
            q = query(finance.STK_XR_XD.code).filter(
                finance.STK_XR_XD.report_date == report_date,
                finance.STK_XR_XD.bonus_type == '年度分红',
                finance.STK_XR_XD.implementation_pub_date <= end_date,
                finance.STK_XR_XD.board_plan_bonusnote == '不分配不转增',
                finance.STK_XR_XD.code.in_(stock_list),
            )
            no_bonus = finance.run_query(q)['code'].unique().tolist()
            bonus_list = [code for code in stock_list if code not in no_bonus]
            bonus_list = small_short_by_market_cap(context, bonus_list)
        if len(bonus_list) < s['max_position_count']:
            bonus_list.extend([x for x in small_short_by_market_cap(context, stock_list)
                               if x not in bonus_list][:s['max_position_count'] - len(bonus_list)])
        return bonus_list
    except Exception:
        return stock_list


def small_short_by_market_cap(context, stock_list):
    q = query(valuation.code, valuation.market_cap).filter(
        valuation.code.in_(stock_list),
        valuation.day == context.previous_date,
    ).order_by(valuation.market_cap.asc())
    df = get_fundamentals(q)
    return df['code'].unique().tolist()


def small_filter_cooldown_stocks(context, s, stock_list):
    if not s.get('enable_cooldown'):
        return stock_list
    cur_date = context.current_dt.date()
    valid = []
    for stock in stock_list:
        if stock in s['no_buy_stocks']:
            passed = len(get_trade_days(start_date=s['no_buy_stocks'][stock],
                                         end_date=cur_date)) - 1
            if passed < s.get('cooldown_days', 2):
                continue
            del s['no_buy_stocks'][stock]
        valid.append(stock)
    return valid


# ============================================================
#  再平衡
# ============================================================

def _get_rebalance_config():
    if not hasattr(g, 'rebalance_config'):
        g.rebalance_config = {
            'base_ratios': _strategy_ratios(),
            'deviation_trigger': 0.10,
            'min_transfer': 1000,
            # Added flag to control rebalancing globally
            'enabled': getattr(g, 'rebalance_enabled', False),
        }
    else:
        g.rebalance_config['base_ratios'] = _strategy_ratios()
    return g.rebalance_config


def rebalance_evaluate(context):
    """每月1号09:25评估资金偏离，设置截流上限"""
    # Rebalancing disabled by user request
    if not getattr(g, 'rebalance_enabled', False):
        log.info("[再平衡] 已取消，跳过评估")
        return
    cfg = _get_rebalance_config()
    base = cfg['base_ratios']
    trigger = cfg['deviation_trigger']
    total_value = sum(context.subportfolios[i].total_value for i in range(5))
    if total_value <= 0:
        return
    strategies = [g.qx_large_strategy, g.qx_small_strategy, g.wufu_strategy,
                  g.q520_strategy, g.small_strategy]
    log.info('=' * 70)
    log.info('[再平衡] 每月评估开始')
    max_dev = 0.0
    targets = []
    for i in range(5):
        cur = context.subportfolios[i].total_value
        cur_ratio = cur / total_value
        target_ratio = base[i]
        target_val = target_ratio * total_value
        dev = abs(cur_ratio - base[i]) / base[i]
        if dev > max_dev:
            max_dev = dev
        targets.append(target_val)
        log.info(f"  {strategies[i]['name']}: 当前{cur/10000:.1f}万({cur_ratio:.1%}) "
                 f"→ 目标{target_val/10000:.1f}万({target_ratio:.1%}) [偏离{dev:+.0%}]")
    log.info(f"  最大偏离: {max_dev:.0%}, 触发阈值: {trigger:.0%}")
    if max_dev < trigger:
        log.info('[再平衡] 偏离未达阈值，无需再平衡')
        g.rebalance_pending = False
        for s in strategies:
            s['rebalance_cap'] = None
        return
    g.rebalance_pending = True
    log.info('[再平衡] 偏离超过阈值，启动再平衡！')
    for i in range(5):
        cur = context.subportfolios[i].total_value
        target_val = targets[i]
        if cur > target_val * 1.02:
            strategies[i]['rebalance_cap'] = target_val
            log.info(f"  {strategies[i]['name']} 设截流上限: {target_val/10000:.1f}万")
        else:
            strategies[i]['rebalance_cap'] = None
    log.info('=' * 70)


def rebalance_transfer_cash(context):
    """每月3号14:50执行资金转移"""
    # Rebalancing disabled by user request
    if not getattr(g, 'rebalance_enabled', False):
        log.info("[再平衡] 已取消，跳过转移")
        return
    if not getattr(g, 'rebalance_pending', False):
        return
    cfg = _get_rebalance_config()
    base = cfg['base_ratios']
    min_transfer = cfg['min_transfer']
    total_value = sum(context.subportfolios[i].total_value for i in range(5))
    if total_value <= 0:
        return
    strategies = [g.qx_large_strategy, g.qx_small_strategy, g.wufu_strategy,
                  g.q520_strategy, g.small_strategy]
    log.info('=' * 70)
    log.info('[再平衡] 资金转移开始')
    over_funded = []
    under_funded = []
    for i in range(5):
        cur = context.subportfolios[i].total_value
        target = base[i] * total_value
        cash = context.subportfolios[i].available_cash
        if cur > target + min_transfer:
            over_funded.append((i, cur - target, cash))
        elif cur < target - min_transfer:
            under_funded.append((i, target - cur))
    if not over_funded or not under_funded:
        log.info('[再平衡] 无可转移资金')
        g.rebalance_pending = False
        for s in strategies:
            s['rebalance_cap'] = None
        log.info('=' * 70)
        return
    total_under = sum(u[1] for u in under_funded)
    for from_idx, over_amount, available in over_funded:
        transferable = min(over_amount, available)
        if transferable < min_transfer:
            continue
        for to_idx, under_amount in under_funded:
            share = transferable * (under_amount / total_under)
            if share < min_transfer:
                continue
            actual = min(share, under_amount)
            actual = min(actual, context.subportfolios[from_idx].available_cash)
            if actual >= min_transfer:
                try:
                    transfer_cash(from_idx, to_idx, actual)
                    log.info(f"  转移 {actual/10000:.2f}万: "
                             f"{strategies[from_idx]['name']} → {strategies[to_idx]['name']}")
                except Exception as e:
                    log.error(f"  转移失败: {e}")
    # 检查是否完成
    all_balanced = True
    for i in range(5):
        cur = context.subportfolios[i].total_value
        target = base[i] * total_value
        if abs(cur - target) / total_value > 0.05:
            all_balanced = False
            break
    if all_balanced:
        g.rebalance_pending = False
        for s in strategies:
            s['rebalance_cap'] = None
        log.info('[再平衡] 完成，截流标志已清除')
    else:
        # 重新设置截流
        for i in range(5):
            cur = context.subportfolios[i].total_value
            target = base[i] * total_value
            if cur <= target * 1.02:
                strategies[i]['rebalance_cap'] = None
        log.info('[再平衡] 部分偏离仍存在，截流标志保留至下月')
    log.info('=' * 70)


# ============================================================
#  每日绩效记录 & 内存清理
# ============================================================

def record_daily_performance(context):
    if not hasattr(g, 'strategy_history'):
        g.strategy_history = {0: [], 1: [], 2: [], 3: [], 4: []}
    if not hasattr(g, 'strategy_value_data'):
        g.strategy_value_data = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}

    total = sum(context.subportfolios[i].total_value for i in range(5))
    strategies = [g.qx_large_strategy, g.qx_small_strategy, g.wufu_strategy,
                  g.q520_strategy, g.small_strategy]
    for i, s in enumerate(strategies):
        val = context.subportfolios[i].total_value
        g.strategy_value_data[i] = val
        g.strategy_history.setdefault(i, []).append(val)

    print_strategy_performance(context)
    print_position_summary(context)


def _format_stock_code(stock_code):
    try:
        info = get_security_info(stock_code)
        return f"{stock_code[:6]}({info.display_name})"
    except Exception:
        return stock_code[:6]


def _get_all_subportfolio_positions(context):
    positions = []
    strategies = [g.qx_large_strategy, g.qx_small_strategy, g.wufu_strategy,
                  g.q520_strategy, g.small_strategy]
    for i, s in enumerate(strategies):
        sub = context.subportfolios[i]
        for stock, pos in sub.positions.items():
            if pos.total_amount > 0:
                positions.append((i, s['name'], stock, pos))
    return positions


def print_position_summary(context):
    """打印与三马105-七星1.72.py一致风格的持仓表。"""
    total_value = sum(context.subportfolios[i].total_value for i in range(5))
    all_positions = _get_all_subportfolio_positions(context)
    strategies = [g.qx_large_strategy, g.qx_small_strategy, g.wufu_strategy,
                  g.q520_strategy, g.small_strategy]
    if not all_positions:
        log.info(f"[持仓] 当前总资产: {total_value:.2f} 休息ing")
        return

    table = PrettyTable([
        " 所属策略 ",
        " 股票代码 ",
        " 股票名称 ",
        " 持仓数量 ",
        " 持仓价格 ",
        " 当前价格 ",
        " 盈亏数额 ",
        " 盈亏比例 ",
        " 股票市值 ",
        " 仓位占比 ",
    ])
    table.hrules = prettytable.ALL

    current_data = get_current_data()
    total_market_value = 0
    duplicate_map = {}
    for sid, _, stock, pos in all_positions:
        sub_value = context.subportfolios[sid].total_value
        current_shares = pos.total_amount
        duplicate_map.setdefault(stock, []).append((strategies[sid]['name'], current_shares, pos.avg_cost))
        current_price = round(current_data[stock].last_price, 3)
        avg_cost = round(pos.avg_cost, 3)
        profit_ratio = (current_price - avg_cost) / avg_cost if avg_cost else 0
        profit_ratio_percent = f"{profit_ratio * 100:.2f}% {'↑' if profit_ratio > 0 else '↓'}"
        profit_amount = round((current_price - avg_cost) * current_shares, 2)
        market_value = round(current_shares * current_price, 2)
        total_market_value += market_value
        table.add_row([
            strategies[sid]['name'].split('_', 1)[-1],
            stock.split('.')[0],
            _format_stock_code(stock),
            current_shares,
            avg_cost,
            current_price,
            profit_amount,
            profit_ratio_percent,
            market_value,
            f"{market_value / sub_value * 100:.2f}%" if sub_value else "0.00%",
        ])

    for i, s in enumerate(strategies):
        val = g.strategy_value_data.get(i, context.subportfolios[i].total_value)
        if val:
            table.add_row([
                s['name'].split('_', 1)[-1], "", "", "", "", "", "", "",
                f"{val:.2f}",
                f"{val / total_value * 100:.2f}%" if total_value else "0.00%",
            ])
    table.add_row(["总市值", "", "", "", "", "", "", "", f"{total_market_value:.2f}", ""])
    table.add_row(["总资产", "", "", "", "", "", "", "", f"{total_value:.2f}", ""])

    log.info(f"[持仓] 当前总资产\n{table}")
    overlaps = []
    for stock, holders in duplicate_map.items():
        if len(holders) > 1:
            detail = ', '.join(f"{name}: {amount}股@{avg_cost:.3f}" for name, amount, avg_cost in holders)
            overlaps.append(f"{stock} {_get_security_name(stock)} -> {detail}")
    if overlaps:
        log.info("[持仓归属] 同一标的多子账户持有\n" + "\n".join(overlaps))


def print_strategy_performance(context):
    """打印各子策略的业绩统计（当日、累计、年化、回撤）。"""
    table = PrettyTable([" 策略名称 ", " 当日收益 ", " 累计收益 ", " 年化收益 ", " 最大回撤 "])
    table.hrules = prettytable.ALL
    strategies = [g.qx_large_strategy, g.qx_small_strategy, g.wufu_strategy,
                  g.q520_strategy, g.small_strategy]
    for sid, s in enumerate(strategies):
        history = g.strategy_history.get(sid, [])
        if not history:
            continue
        start_val = g.strategy_starting_cash.get(sid, 0)
        if len(history) >= 2 and history[-2] != 0:
            daily_ret = (history[-1] - history[-2]) / history[-2]
        elif start_val != 0:
            daily_ret = (history[-1] - start_val) / start_val
        else:
            daily_ret = 0
        if start_val == 0:
            continue
        total_ret = (history[-1] - start_val) / start_val
        days = len(history)
        ann_ret = (1 + total_ret) ** (250.0 / days) - 1 if days > 0 and total_ret > -1 else 0
        max_drawdown = 0
        peak = start_val
        for val in history:
            if val > peak:
                peak = val
            if peak > 0:
                dd = (peak - val) / peak
                if dd > max_drawdown:
                    max_drawdown = dd
        table.add_row([
            s['name'].split('_', 1)[-1],
            f"{daily_ret * 100:+.2f}%",
            f"{total_ret * 100:+.2f}%",
            f"{ann_ret * 100:.2f}%",
            f"{max_drawdown * 100:.2f}%",
        ])
    log.info(f"[业绩统计] 子策略表现一览\n{table}")


def daily_memory_cleanup(context):
    """每日15:10内存清理，防止pickle序列化错误"""
    # 清理五福的批量缓存
    try:
        s = g.wufu_strategy
        s['etf_yesterday_close_batch'] = {}
        s['etf_yesterday_nav_batch'] = {}
        # 限制drawdown_records长度
        if len(s['drawdown_records']) > 30:
            s['drawdown_records'] = s['drawdown_records'][-30:]
    except Exception:
        pass
    # 清理七星ranking缓存（防止date对象累积）
    for s in [g.qx_large_strategy, g.qx_small_strategy]:
        try:
            if s['rankings_cache'].get('date') is not None:
                s['rankings_cache'] = {'date': None, 'pool_mode': None, 'data': None}
        except Exception:
            pass
    try:
        s = g.q520_strategy
        if s['rankings_cache'].get('date') is not None:
            s['rankings_cache'] = {'date': None, 'data': None}
    except Exception:
        pass
    # 清理ATR止损价记录中已离场的股票
    try:
        s = g.small_strategy
        pindex = s['pindex']
        pos_codes = set(context.subportfolios[pindex].positions.keys())
        expired = [k for k in list(s['atr_stop_prices'].keys()) if k not in pos_codes]
        for k in expired:
            del s['atr_stop_prices'][k]
        # 限制dbl长度
        if len(s['dbl']) > 200:
            s['dbl'] = s['dbl'][-200:]
        # 清理冷却期过期记录
        cur_date = context.current_dt.date()
        expired_nb = [k for k, v in s['no_buy_stocks'].items()
                      if len(get_trade_days(start_date=v, end_date=cur_date)) - 1
                      >= s.get('cooldown_days', 2) + 5]
        for k in expired_nb:
            del s['no_buy_stocks'][k]
    except Exception:
        pass
    # 清理模块级名称缓存过大
    global _SECURITY_NAME_CACHE
    if len(_SECURITY_NAME_CACHE) > _SECURITY_NAME_CACHE_MAX:
        keys = list(_SECURITY_NAME_CACHE.keys())
        for k in keys[:100]:
            del _SECURITY_NAME_CACHE[k]
    gc.collect()
    log.info('[内存清理] 每日清理完成')
