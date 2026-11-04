# Clone from JoinQuant
# postId: c4fc448c21048c80eae714850294883a
# backtestId: 2852a3fa34d4568d1cd6ec1d1b1e0d3e
# title: 以混沌之火，点亮投资之路——信息熵策略

import numpy as np
import pandas as pd
import datetime as dt
from jqdata import *

def initialize(context):
    # setting system
    log.set_level('order', 'error')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    # setting strategy
    run_daily(iUpdate, time='before_open')
    run_daily(iTrader, time='10:45')
    run_daily(iReport, time='after_close')

def iUpdate(context):
    # daily update
    g.nchoice = 100 # number of stocks
    m = int(1.2*g.nchoice) # 20% buffer
    g.stocks = small_stocks(context, m)
    g.funds = choice_QDII(context)
    g.position_size = 0.5/g.nchoice * context.portfolio.total_value

def iTrader(context):
    # load data
    stocks = choice_stocks(context, g.stocks, g.nchoice)
    funds = g.funds
    position_size = g.position_size
    cdata = get_current_data()
    # sell
    choice = stocks + funds
    for s in context.portfolio.positions:
        if cdata[s].paused:
            continue
        if s not in choice:
            log.info('sell', s, cdata[s].name)
            order_target(s, 0, MarketOrderStyle(0.99*cdata[s].last_price))
    # buy
    for s in choice:
        if context.portfolio.available_cash < position_size:
            break
        if cdata[s].paused:
            continue
        if s not in context.portfolio.positions:
            log.info('buy', s, cdata[s].name)
            order_target_value(s, position_size, MarketOrderStyle(1.01*cdata[s].last_price))
    # save
    cash_max = 10*position_size
    cash_min =  3*position_size
    for s in funds:
        if cdata[s].paused:
            continue
        if context.portfolio.available_cash > cash_max:
            log.info('save', s, cdata[s].name)
            order_value(s, position_size, MarketOrderStyle(1.01*cdata[s].last_price))
        elif context.portfolio.available_cash < cash_min and\
            s in context.portfolio.positions:
            log.info('load', s, cdata[s].name)
            order_value(s,-position_size, MarketOrderStyle(1.01*cdata[s].last_price)) 

def iReport(context):
    # load data
    cdata = get_current_data()
    tvalue = context.portfolio.total_value
    # table of positions
    ptable = pd.DataFrame(columns=['amount', 'value', 'weight', 'name'])
    for s in context.portfolio.positions:
        ps = context.portfolio.positions[s]
        ptable.loc[s] = [ps.total_amount, int(ps.value), 100*ps.value/tvalue, cdata[s].name]
    ptable = ptable.sort_values(by='weight', ascending=False)
    # daily report
    pd.set_option('display.max_rows', None)
    log.info('  positions', len(ptable), '\n', ptable.head())
    log.info('  total value %.2f, cash %.2f', \
            context.portfolio.total_value/10000, context.portfolio.available_cash/10000)

def small_stocks(context, nchoice):
    # stocks
    index = '399317.XSHE'
    dt_last = context.previous_date
    stocks = get_index_stocks(index, dt_last)
    # non-ST
    cdata = get_current_data()
    stocks = [s for s in stocks if not cdata[s].is_st]
    # trinity stocks
    df = get_fundamentals(query(
            valuation.code,
            valuation.capitalization,
        ).filter(
            valuation.code.in_(stocks),
            valuation.pb_ratio.between(0, 10.0),
            indicator.inc_return > 0,
            indicator.ocf_to_revenue > 0,
        ).order_by(valuation.market_cap.asc()
        ).limit(nchoice)
        ).dropna().set_index('code')
    # result
    return df.capitalization

def choice_stocks(context, cap, nchoice):
    # small
    p = history(1, '1m', 'close', cap.index).iloc[0]
    v = (p*cap).sort_values()
    # choice stocks
    stocks_0 = [s for s in v.index if s in context.portfolio.positions]
    stocks_1 = [s for s in v.index if s not in context.portfolio.positions]
    stocks = (stocks_0 + stocks_1)[:nchoice]
    # report
    log.info('small-value stocks', len(stocks))
    # reuslt
    return stocks

def choice_QDII(context):
    # parameters
    index = '000300.XSHG'
    nday = 150
    keys = ['美国', '标普', '纳指', '纳斯达克', '法国', '德国', '巴西', \
            '亚太', '亚洲', '东南亚', '日本', '日经', '印度', '沙特']
    black_list = ['562060.XSHG']
    white_list = ['513310.XSHG']
    # all funds
    dt_last = context.previous_date
    all_fund = get_all_securities('fund', dt_last)
    # onlist 1-year
    dt_1y = dt_last - dt.timedelta(days=365)
    funds = all_fund[all_fund.start_date < dt_1y].index.tolist()
    # filter, liquid
    xm = 1e-6*history(nday, '1d', 'money', index)[index].mean()
    hm = history(nday, '1d', 'money', funds).mean()
    funds = hm[hm > xm].index.tolist()
    # filter, up-trend
    h = history(nday, '1d', 'close', funds).dropna(axis=1)
    R = 100*h.iloc[-1]/h.mean() - 100
    funds = R[R > 0].index.tolist()
    # key funds
    choice = [s for k in keys for s in funds if k in all_fund.display_name[s]]
    # black list
    choice = [s for s in choice if s not in black_list]
    # white list
    choice = choice + [s for s in white_list if s in funds]
    # premium
    r = pd.Series()
    if len(choice) > 0:
        # net value
        dt_T2 = h.index[-2]
        value = get_net_value(choice, dt_T2)
        # price
        price = history(1, '1m', 'close', choice).iloc[0]
        # low premium
        r = 100*price/value - 100
        r = r[r < 10.0].sort_values()
        # report
        log.info('QDII funds', len(r))
        for s in r.index:
            log.info(s, all_fund.display_name[s], '%.3f'%r[s])
    choice = r.index.tolist()
    # append treasury
    if len(choice) < 3:
        bonds = ['511010.XSHG', '511260.XSHG', '000012.XSHG']
        choice = choice + bonds
    log.info('funds', len(choice))
    # result
    return choice

def get_net_value(funds, day):
    # convert c11 code to c6
    c6_funds = [s[:6] for s in funds]
    # index c6 code back c11
    f_f = pd.Series(funds, c6_funds)
    # get net value
    q = query(
            finance.FUND_NET_VALUE
        ).filter(
            finance.FUND_NET_VALUE.code.in_(c6_funds),
            finance.FUND_NET_VALUE.day == day,
        )
    ff = finance.run_query(q)
    # convert index to c11
    c11_index = [f_f[ff.code[i]] for i in ff.index]
    ff['fund'] = c11_index
    ff = ff.set_index('fund')
    # net value
    return ff.net_value
# end