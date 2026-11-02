# Clone from JoinQuant
# postId: a215f65388f6592c1fd69a00541951c1
# backtestId: 0fe7f3e9d05892612cbabf322b8cf019
# title: 回测的BUG

from jqdata import *
import datetime
def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', False)
    g.t = 0
    log.set_level('order', 'warning')
    g.pool = ['000111.OF','000112.OF']
    set_subportfolios([SubPortfolioConfig(context.portfolio.cash, 'open_fund')])
    set_redeem_latency(3, 'QDII_fund')
    run_daily(f1,  time='9:30', reference_security='000300.XSHG')
def f1(context):
    if g.t == 0:
        g.t = 1
        targetvalue = context.portfolio.total_value / 2
        for pool in g.pool :
            o1 = purchase(pool,targetvalue)
