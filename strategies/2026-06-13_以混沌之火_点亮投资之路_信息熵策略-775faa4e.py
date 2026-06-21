# Clone from JoinQuant
# postId: 775faa4e74dd72085c01e18cc3cfee6e
# backtestId: 392155cd456eb601c4c36c1663222708
# title: 以混沌之火，点亮投资之路——信息熵策略

import numpy as np
import pandas as pd
import datetime as dt

def initialize(context):
    # setting system
    log.set_level('order', 'error')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_subportfolios([
        SubPortfolioConfig(cash=context.portfolio.starting_cash, type='stock'),# 主仓
        SubPortfolioConfig(cash=0, type='index_futures'),# 备用
        SubPortfolioConfig(cash=0, type='stock_margin'),# 备用 
        ])
    g.days = 0

def after_code_changed(context):
    # setting strategy
    unschedule_all()
    run_daily(Update, time='before_open')
    run_daily(Trader, time='open')
    run_daily(Report, time='after_close')
    if context.portfolio.total_value < 123456789:
        inout_cash(123456789)#确保资金规模设置正确

def Update(context):
    # daily service
    g.days = g.days + 1
    log.info('running days', g.days)
    # update stocks and funds
    N = 100
    g.stocks = choice_stocks(context, N)
    g.position_size = 0.5/N * context.portfolio.total_value

def choice_stocks(context, nchoice):
    # stocks
    dt_now = context.current_dt.date()
    all_stock = get_all_securities('stock', dt_now)
    log.info('stocks', len(all_stock))
    # non-ST
    cdata = get_current_data()
    stocks = [s for s in all_stock.index if not cdata[s].is_st]
    log.info('non-ST stocks', len(stocks))
    # trinity
    df = get_fundamentals(query(
            valuation.code,
            valuation.market_cap,
            valuation.pb_ratio,
        ).filter(
            income.code.in_(stocks),
            valuation.pb_ratio > 0,
            indicator.inc_return > 0,
            indicator.ocf_to_revenue > 0,
        )).dropna().set_index('code')
    stocks = df.index.tolist()
    N = len(stocks)
    log.info('trinity stocks', N)
    # random choice
    choice = [s for s in context.portfolio.positions if s in stocks]
    nchoice = min(N, nchoice)
    while len(choice) < nchoice:
        k = np.random.randint(N)
        s = stocks[k]
        if s not in choice:
            choice.append(s)
    # report
    df = df.loc[choice].sort_values(by='market_cap', ascending=False)
    df['name'] = [cdata[s].name for s in df.index]
    log.info('choice stocks', len(choice), '\n', df.head())
    # result
    return choice

def Trader(context):
    # load data
    stocks = g.stocks
    funds = ['511010.XSHG', '511260.XSHG', '511130.XSHG'] # 3~5年国债，10年国债，30年国债
    position_size = g.position_size
    value_max = 3.0*position_size
    value_min = 0.3*position_size
    cash_max = 10*position_size # 5%
    cash_min =  2*position_size # 1%
    cdata = get_current_data()
    # Sell
    choice = stocks + funds
    for s in context.portfolio.positions:
        if cdata[s].paused:
            continue
        if s not in choice:
            log.info('sell', s, cdata[s].name)
            order_target(s, 0, MarketOrderStyle(0.99*cdata[s].last_price))
    # Buy stocks
    for s in stocks:
        if context.portfolio.available_cash < cash_min:
            break
        if cdata[s].paused:
            continue
        if s not in context.portfolio.positions:
            log.info('buy', s, cdata[s].name)
            order_target_value(s, position_size, MarketOrderStyle(1.01*cdata[s].last_price))
        elif context.portfolio.positions[s].value < value_min:
            log.info('balance+', s, cdata[s].name)
            order_target_value(s, position_size, MarketOrderStyle(1.01*cdata[s].last_price))
        elif context.portfolio.positions[s].value > value_max:
            log.info('balance-', s, cdata[s].name)
            order_target_value(s, position_size, MarketOrderStyle(0.99*cdata[s].last_price))
    # Money management
    for s in funds:
        if cdata[s].paused:
            continue
        if context.portfolio.available_cash > cash_max:
            log.info('save', s, cdata[s].name)
            order_value(s,  position_size, MarketOrderStyle(1.01*cdata[s].last_price))
        elif context.portfolio.available_cash < cash_min and\
            s in context.portfolio.positions:
            log.info('load', s, cdata[s].name)
            order_value(s, -position_size, MarketOrderStyle(1.01*cdata[s].last_price))

def Report(context):
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
    log.info('positions', len(ptable), '\n', ptable.head())
    log.info('total value %.2f, cash %.2f', \
            context.portfolio.total_value/10000, context.portfolio.available_cash/10000)
# end