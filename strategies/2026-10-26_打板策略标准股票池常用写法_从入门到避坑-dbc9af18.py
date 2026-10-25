# Clone from JoinQuant
# postId: dbc9af1853ad9c890aeccadfa28c3b8a
# backtestId: c44c89a5490ab742153c24ea1fb391b0
# title: 打板策略标准股票池常用写法：从入门到避坑

# -*- coding: utf-8 -*-
"""
基础股票池（最精简版）
========================
规则：沪深主板，剔除新股、ST、停牌
"""

from jqdata import *
import datetime as dt


def initialize(context):
    set_option("avoid_future_data", True)
    set_option('use_real_price', True)
    log.set_level('system', 'error')
    run_daily(build_pool, '09:01')


def build_pool(context):
    date = context.previous_date
    g.pool = get_base_pool(date)
    log.info("股票池: %d 只" % len(g.pool))


def get_base_pool(date):
    """沪深主板股票池"""
    # 全市场
    lst = get_all_securities('stock', date).index.tolist()
    # 剔除科创北交（4/8/68开头）+ 剔除创业板（300开头）
    lst = [s for s in lst if s[0] not in '48'
           and s[:2] != '68' and not s.startswith('300')]
    # 剔除新股（上市不足250天）
    d = transform_date(date, 'd')
    lst = [s for s in lst
           if d - get_security_info(s).start_date > dt.timedelta(days=250)]
    # 剔除ST
    names = get_all_securities('stock', date)['display_name']
    lst = [s for s in lst if 'ST' not in names.get(s, '')]
    # 剔除停牌
    df = get_price(lst, end_date=date, frequency='daily',
                   fields=['paused'], count=1, panel=False,
                   fill_paused=True, skip_paused=False)
    return list(df[df['paused'] == 0].code)


def transform_date(date, tp):
    if type(date) == str:
        s, d = date, dt.datetime.strptime(date, '%Y-%m-%d').date()
        dt_ = dt.datetime.strptime(date, '%Y-%m-%d')
    elif type(date) == dt.datetime:
        s, d, dt_ = date.strftime('%Y-%m-%d'), date.date(), date
    else:
        s = date.strftime('%Y-%m-%d')
        d, dt_ = date, dt.datetime.strptime(s, '%Y-%m-%d')
    return {'str': s, 'd': d, 'dt': dt_}[tp]