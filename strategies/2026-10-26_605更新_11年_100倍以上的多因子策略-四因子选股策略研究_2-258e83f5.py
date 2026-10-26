# Clone from JoinQuant
# postId: 258e83f5cdd80b9f098598bf33658c39
# backtestId: e62e771c9921d5efc272c21a97a990bb
# title: 605更新：11年 100倍以上的多因子策略-四因子选股策略研究（2）

from sqlalchemy import desc
import numpy as np
import pandas as pd
from dateutil import relativedelta
def initialize(context):
    run_monthly(month_select, 1, time='before_open')
    context.last_update_dt = None
def check_date(context):
    if context.last_update_dt is None: return True
    delta = relativedelta.relativedelta(months=1)
    dt = context.last_update_dt + delta
    if context.current_dt.year == dt.year and context.current_dt.month == dt.month: return True
    else: return False
def get_avg(context, weeks, security):
    delta = relativedelta.relativedelta(weeks=-weeks)
    start_date = context.current_dt + delta
    end_date = context.current_dt
    df = get_price(security, start_date, end_date,fields=['close'])
    return df.mean()['close']
def check_avg(context):
    ref_security = '000300.XSHG'
    if get_avg(context, 6, ref_security) < get_avg(context, 12, ref_security):
        context.selected_stocks = []
        #段均线小于长均线，清空股票
        print('均线小于长均线，清空股票')
        return False
    else: return True

def unpaused(stockspool):
    current_data=get_current_data()
    return [s for s in stockspool if not current_data[s].paused]
def get_stocks(context):
    stocks = get_all_securities(['stock'])
    #stocks = stocks[stocks['end_date'] > context.current_dt.date()].index
    stocks  = stocks.index
    date=context.current_dt.strftime("%Y-%m-%d")
    st=get_extras('is_st', stocks, start_date=date, end_date=date, df=True)
    st=st.loc[date]
    stocks=list(st[st==False].index)
    
    return unpaused(stocks)
def assign_order(s):
    s.dropna(inplace=True)
    arg_sort = s.argsort()
    s[arg_sort] = np.arange(len(arg_sort))
def month_select(context):
    print('month_select', context.current_dt)
    if not check_date(context): return
    context.last_update_dt = context.current_dt
    context.need_update = True
    stocks = get_stocks(context)
    
    q = query(valuation).filter(valuation.code.in_(stocks))
    df = get_fundamentals(q)
    s_cmc = pd.Series(df['market_cap'].values, index=df['code'])
    assign_order(s_cmc)

    s_pb = pd.Series(df['pb_ratio'].values, index=df['code'])
    assign_order(s_pb)
    
    df = history(2, unit='120d', field='close', security_list=stocks)
    s_gain = (df.iloc[1] - df.iloc[0]) / df.iloc[0]
    assign_order(s_gain)

    s = 1 * s_cmc +0* s_pb +1.1* s_gain
    s = s.dropna()
    s.sort()
    context.selected_stocks = s.index[:5]

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
        print('handle_data', context.current_dt)
        update_position(context)
        context.need_update = False
