# Clone from JoinQuant
# postId: fd55765f0e3458a24b0bb8f0b58a478b
# backtestId: c86073a2275828d8939798461c2f3ff0
# title: 全天候策略增强：A股风格轮动

#全天候策略增强A股风格轮动
# 聚宽策略：四资产判断是否进攻 A 股，A 股内部用创业红利轮动替代沪深300。

# -*- coding: utf-8 -*-
"""
策略名称：全天候策略A股风格轮动
"""
from jqdata import *
import datetime
import numpy as np
import pandas as pd


def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)

    set_slippage(PriceRelatedSlippage(0.001))
    set_order_cost(OrderCost(open_tax=0, close_tax=0,
                             open_commission=0.00015, close_commission=0.00015,
                             close_today_commission=0, min_commission=5),
                   type='fund')
    log.set_level('order', 'error')

    g.model_name = 'EarlETF_四资产增强A股风格轮动'
    g.lookback_days = 20
    g.min_list_days = 120
    g.target_position = 0.98
    g.a_share_model = 'growth_dividend'

    g.outer_groups = [
        {
            'slot': 'a_share',
            'label': 'A股入口-沪深300ETF',
            'candidates': ['510300.XSHG', '159919.XSHE', '510330.XSHG'],
        },
        {
            'slot': 'bond',
            'label': '5年国债ETF',
            'candidates': ['511010.XSHG'],
        },
        {
            'slot': 'nasdaq',
            'label': '纳指ETF',
            'candidates': ['513100.XSHG', '159941.XSHE', '513300.XSHG'],
        },
        {
            'slot': 'gold',
            'label': '黄金ETF',
            'candidates': ['518880.XSHG', '159934.XSHE', '518800.XSHG'],
        },
    ]

    g.a_share_groups = {
        'growth_dividend': [
            {
                'slot': 'growth',
                'label': '创业板ETF',
                'candidates': ['159915.XSHE', '159977.XSHE', '159948.XSHE'],
            },
            {
                'slot': 'dividend',
                'label': '中证红利ETF',
                'candidates': ['510880.XSHG', '515080.XSHG', '159905.XSHE'],
            },
        ],
        'large_small': [
            {
                'slot': 'large',
                'label': '沪深300ETF',
                'candidates': ['510300.XSHG', '159919.XSHE', '510330.XSHG'],
            },
            {
                'slot': 'small',
                'label': '中证2000ETF',
                'min_list_days': 60,
                'candidates': [
                    '563300.XSHG', '159531.XSHE', '159532.XSHE', '562660.XSHG',
                    '560220.XSHG', '159536.XSHE', '159533.XSHE', '159535.XSHE',
                    '561370.XSHG', '563200.XSHG',
                ],
            },
        ],
    }

    g.asset_names = {}
    g.last_outer_rank = pd.DataFrame()
    g.last_inner_rank = pd.DataFrame()
    g.target_asset = None
    g.target_source = ''

    run_weekly(weekly_rebalance, 1, '9:45')
    run_daily(record_status, '14:55')


def weekly_rebalance(context):
    end_date = context.previous_date
    outer_rank = get_group_rank(g.outer_groups, end_date, '外层')
    if outer_rank is None or len(outer_rank) == 0:
        log.info('外层无可交易ETF，清仓等待')
        g.target_asset = None
        g.target_source = 'empty'
        rebalance_to_target(context, None)
        return

    g.last_outer_rank = outer_rank
    outer_top = outer_rank.iloc[0]
    outer_target = outer_rank.index[0]
    log.info('%s 外层20日动量排名: %s' % (g.model_name, format_rank(outer_rank)))

    if outer_top['slot'] == 'a_share':
        target = select_a_share_target(context, end_date, outer_target)
    else:
        target = outer_target
        g.target_source = outer_top['slot']
        g.last_inner_rank = pd.DataFrame()

    g.target_asset = target
    record_selection(outer_rank, g.last_inner_rank, target)
    rebalance_to_target(context, target)


def select_a_share_target(context, end_date, fallback_asset):
    inner_groups = g.a_share_groups.get(g.a_share_model, g.a_share_groups['growth_dividend'])
    inner_rank = get_group_rank(inner_groups, end_date, 'A股内层')
    g.last_inner_rank = inner_rank

    if inner_rank is None or len(inner_rank) == 0:
        log.info('A股内层无可交易ETF，回退到外层沪深300ETF: %s' % fallback_asset)
        g.target_source = 'a_share_fallback'
        return fallback_asset

    target = inner_rank.index[0]
    g.target_source = 'a_share_' + inner_rank.iloc[0]['slot']
    log.info('%s A股内层20日动量排名: %s' % (g.model_name, format_rank(inner_rank)))
    return target


def get_group_rank(groups, end_date, name):
    rows = []
    for group in groups:
        asset = select_tradeable_fund(group['candidates'], end_date,
                                      group.get('min_list_days', g.min_list_days))
        if asset is None:
            log.info('%s资产组无可交易ETF: %s' % (name, group['label']))
            continue
        ret20 = calculate_return(asset, end_date, g.lookback_days)
        if ret20 is None:
            continue
        rows.append((asset, group['label'], group['slot'], ret20))

    if not rows:
        return pd.DataFrame(columns=['label', 'slot', 'ret20'])

    df = pd.DataFrame(rows, columns=['asset', 'label', 'slot', 'ret20']).set_index('asset')
    return df.sort_values(by='ret20', ascending=False)


def select_tradeable_fund(candidates, end_date, min_list_days):
    try:
        all_funds = get_all_securities(types='fund', date=end_date)
    except Exception:
        all_funds = pd.DataFrame(index=candidates)

    current_data = get_current_data()
    valid = []
    for code in candidates:
        if code not in all_funds.index:
            continue
        try:
            start_date = all_funds.loc[code, 'start_date']
            if end_date - start_date < datetime.timedelta(days=min_list_days):
                continue
            if current_data[code].paused:
                continue
            df = get_price(code, end_date=end_date, frequency='daily',
                           fields=['close', 'money'], count=g.lookback_days + 1,
                           panel=False)
        except Exception:
            continue
        if df is None or len(df) < g.lookback_days + 1:
            continue
        closes = df['close'].values
        if np.any(pd.isna(closes)) or np.any(closes <= 0):
            continue
        avg_money = df['money'].tail(g.lookback_days).mean() if 'money' in df.columns else 0
        valid.append((avg_money, code))
        try:
            g.asset_names[code] = all_funds.loc[code, 'display_name']
        except Exception:
            g.asset_names[code] = code

    if not valid:
        return None
    valid = sorted(valid, key=lambda x: x[0], reverse=True)
    return valid[0][1]


def calculate_return(asset, end_date, days):
    df = get_price(asset, end_date=end_date, frequency='daily',
                   fields=['close'], count=days + 1, panel=False)
    if df is None or len(df) < days + 1:
        return None
    closes = df['close'].values
    if np.any(pd.isna(closes)) or np.any(closes <= 0):
        return None
    return closes[-1] / closes[0] - 1


def record_selection(outer_rank, inner_rank, target):
    outer_top = outer_rank.index[0]
    selected_code = int(target.split('.')[0]) if target else 0
    outer_code = int(outer_top.split('.')[0])
    outer_ret = round(outer_rank.loc[outer_top, 'ret20'] * 100, 2)
    inner_ret = 0
    if inner_rank is not None and len(inner_rank) > 0:
        inner_top = inner_rank.index[0]
        inner_ret = round(inner_rank.loc[inner_top, 'ret20'] * 100, 2)

    record(selected_code=selected_code,
           outer_code=outer_code,
           outer_ret20=outer_ret,
           inner_ret20=inner_ret,
           outer_candidate_num=len(outer_rank),
           inner_candidate_num=0 if inner_rank is None else len(inner_rank))


def rebalance_to_target(context, target):
    for asset in list(context.portfolio.positions.keys()):
        if asset != target:
            submit_target_value_order(asset, 0, 'sell')
            log.info('卖出: %s %s' % (asset, g.asset_names.get(asset, '')))

    if target is None:
        return

    target_value = context.portfolio.total_value * g.target_position
    submit_target_value_order(target, target_value, 'buy')
    log.info('目标持仓: %s %s source=%s value=%.2f' %
             (target, g.asset_names.get(target, ''), g.target_source, target_value))


def record_status(context):
    if g.target_asset is None:
        record(pos=0)
    else:
        record(pos=round(context.portfolio.positions_value / context.portfolio.total_value * 100, 2))


def build_limit_order_style(asset, side):
    data = get_current_data()[asset]
    price = data.last_price
    if price is None or price <= 0:
        return None

    buffer = 0.01
    if side == 'buy':
        limit_price = price * (1 + buffer)
        if data.high_limit is not None and data.high_limit > 0:
            limit_price = min(limit_price, data.high_limit)
    else:
        limit_price = price * (1 - buffer)
        if data.low_limit is not None and data.low_limit > 0:
            limit_price = max(limit_price, data.low_limit)

    limit_price = min(max(limit_price, 0.01), 9999.99)
    return LimitOrderStyle(round(limit_price, 3))


def submit_target_value_order(asset, target_value, side):
    style = build_limit_order_style(asset, side)
    if style is None:
        log.info('skip order %s: no valid price' % asset)
        return None
    return order_target_value(asset, target_value, style=style)


def format_rank(rank_df):
    parts = []
    for asset, row in rank_df.iterrows():
        parts.append('%s/%s: %.2f%%' %
                     (row['label'], asset, row['ret20'] * 100))
    return ' | '.join(parts)
