# Clone from JoinQuant
# postId: 529f8af659c17bf7e1993705d7ae0f02
# backtestId: f302f5d5c239b28948b44f8a343c10b9
# title: 11年36倍收益的四因子选股策略研究（1）

from sqlalchemy import desc
import numpy as np
import pandas as pd
from dateutil import relativedelta
def initialize(context):
    run_monthly(month_select, 1, time='before_open')
    context.last_update_dt = None
def check_date(context):
    if context.last_update_dt is None: return True
    delta = relativedelta.relativedelta(months=3)
    dt = context.last_update_dt + delta
    if context.current_dt.year == dt.year and context.current_dt.month == dt.month: return True
    else: return False
def month_select(context):
    if not check_date(context): return
    context.last_update_dt = context.current_dt
    print context.current_dt
    q = query(valuation)
    df = get_fundamentals(q)
    s_cmc = pd.Series(df['circulating_market_cap'].values, index=df['code'])
    s_cmc = s_cmc.dropna().argsort()

    s_pb = pd.Series(df['pb_ratio'].values, index=df['code'])
    s_pb = s_pb.dropna().argsort()
    
    stocks = get_all_securities(['stock']).index
    df = history(2, unit='120d', field='close', security_list=stocks)
    s_gain = (df.iloc[1] - df.iloc[0]) / df.iloc[0]
    s_gain = s_gain.dropna().argsort()

    s = 0.5 * s_cmc + 0.1* s_pb + 0.8* s_gain
    s = s.dropna()
    s.sort()
    #print(s)
    context.selected_stocks = s.index[:5]
    context.need_update = True
    print(context.selected_stocks)
def update_position(context):
    for p in context.portfolio.positions:
        if p not in context.selected_stocks:
            o = order_target(p, 0)
            if o: print('sell', p, o.amount)
    for s in context.selected_stocks:
        target_value = 0.2 * context.portfolio.portfolio_value
        o = order_target_value(s, target_value)
        if o: print('buy', s, o.amount)
    
# 每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)调用一次
def handle_data(context, data):
    if context.need_update is True:
        update_position(context)
        context.need_update = False
    pass

