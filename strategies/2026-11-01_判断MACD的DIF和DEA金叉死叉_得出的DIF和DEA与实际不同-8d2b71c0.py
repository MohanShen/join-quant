# Clone from JoinQuant
# postId: 8d2b71c01104030af61953d00462b6df
# backtestId: 2b27c7fed7f7351d76e69f47369b6e2d
# title: 判断MACD的DIF和DEA金叉死叉 ，得出的DIF和DEA与实际不同

import talib
import numpy as np
import pandas as pd

def initialize(context):
    g.security = '002108.XSHE'
    set_universe(g.security)
    set_benchmark(g.security)
    set_option('use_real_price', True)

def before_trading_start(context):
    g.security = '002108.XSHE'

def handle_data(context, data):
    cash = context.portfolio.cash
    info = attribute_history(g.security, 40, '1d',fields= ('close'),skip_paused=True,df=True)
    macd,signal,hist = talib.MACD(info['close'].values, fastperiod=12, slowperiod=26, signalperiod=9)
    today_macd = macd[-1]
    today_signal = signal[-1]
    current_positions = context.portfolio.positions[g.security].sellable_amount
    current_price = data[g.security].close
    print 'macd',today_macd
    print 'signal',today_signal
    if today_macd < today_signal and current_positions > 0 :
        order_target(g.security, 0)
        log.info("Selling %s" % (g.security))
    elif today_macd > today_signal and current_positions == 0 :
        cw = int(cash/current_price)
        if cw > 0 :
            order(g.security, +cw)
            log.info("Buying %s" % (g.security))