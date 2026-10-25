# Clone from JoinQuant
# postId: 923d3903537dfbd36c774d4733be7c6b
# backtestId: 1c5967ab57f389322973ce9347025349
# title: “十字星”策略研究

from jqdata import *
import numpy as np 
import pandas as pd 
import datetime as datetime
import time as time

def initialize(context):
    g.security = '000905.XSHG'
    set_universe([g.security])
    g.stocks_hold = 0
    set_backtest()
    g.star_amount = 0
    g.h = 30
    g.a = 0.8
    g.b = 1.0
    
def set_backtest():
    set_benchmark('000905.XSHG')
    set_option('use_real_price', True) #使用真实价格
    log.set_level('order', 'error') #设置报错

def handle_data(context, data):
    stock = g.security
    position = context.portfolio.positions
    cash = context.portfolio.cash
    
    if position.has_key('000905.XSHG') == True:
        g.stocks_hold += 1
    
    df = attribute_history(stock, 21, '1d', ['open','close','high','low','money'])
    openprice = df['open']
    closeprice = df['close']
    high = df['high']
    low = df['low']

    length = [0]*21 #length为每根蜡烛实体柱长度
    up = [0]*21  #up为上影线长度
    down = [0]*21  #down为下影线长度
    for n in range(21):
        if openprice[-n] > closeprice[-n]:
            length[-n] = openprice[-n] - closeprice[-n]
            up[-n] = high[-n] - openprice[-n]
            down[-n] = closeprice[-n] - low[-n]
        else:
            length[-n] = closeprice[-n] - openprice[-n]
            up[-n] = high[-n] - closeprice[-n]
            down[-n] = openprice[-n] - low[-n]
    
    present = context.current_dt
    if (present.day==1) and ((present.month==1) or (present.month==4) or (present.month==7) or (present.month==10)):
        print(optimize())
        if (up[-1]>optimize()[1]*length[-1]) and (down[-1]>optimize()[2]*length[-1]) and (closeprice[-1]<closeprice[-21]) and (length[-1]<optimize()[0]) and (position.has_key('000905.XSHG') == False):
            print(optimize())
            order_target_value(stock,cash)
            log.info("Buying %s" % (stock))
            g.star_amount += 1
        elif g.stocks_hold == 20:
            order_target(stock, 0)
            log.info("Selling %s" % (stock))
            g.stocks_hold = 0
    else:
        if (up[-1]>g.a*length[-1]) and (down[-1]>g.b*length[-1]) and (closeprice[-1]<closeprice[-21]) and (length[-1]<g.h) and (position.has_key('000905.XSHG') == False):
            print(g.h,g.a,g.b)
            order_target_value(stock,cash)
            log.info("Buying %s" % (stock))
            g.star_amount += 1
        elif g.stocks_hold == 20:
            order_target(stock, 0)
            log.info("Selling %s" % (stock))
            g.stocks_hold = 0

def optimize():
    stock = g.security
    df = attribute_history(stock, count=200, unit='1d', fields=['open','close','high','low','money'])
    openprice = df['open']
    closeprice = df['close']
    high = df['high']
    low = df['low']

    length = [0]*200 #length为每根蜡烛实体柱长度
    up = [0]*200  #up为上影线长度
    down = [0]*200  #down为下影线长度
    for n in range(200):
        if openprice[-n] > closeprice[-n]:
            length[-n] = openprice[-n] - closeprice[-n]
            up[-n] = high[-n] - openprice[-n]
            down[-n] = closeprice[-n] - low[-n]
        else:
            length[-n] = closeprice[-n] - openprice[-n]
            up[-n] = high[-n] - closeprice[-n]
            down[-n] = openprice[-n] - low[-n]

    c = 0
    x = [g.h,g.a,g.b]
    for k in range(10,41,1):
        for j in frange(0.8,2.1,0.1):
            for m in frange(0.8,2.1,0.1):
                count_bottom_star = 0
                proceeds_20 = [0]*21
                for i in range(20,180):
                    if (up[-i-1]>(j*length[-i-1])) and (down[-i-1]>(m*length[-i-1])) and (closeprice[-i-1]<closeprice[-i-21]) and (length[-i-1]<k):
                        count_bottom_star += 1
                        for n in range(1,21):
                            proceeds_20[n] = (proceeds_20[n]*(count_bottom_star-1)+(closeprice[-i-1+n]-closeprice[-i-1])/closeprice[-i-1])/count_bottom_star
                if sum(proceeds_20)>c:
                    c = sum(proceeds_20)
                    g.h = k
                    g.a = j
                    g.b = m
                    x = [g.h,g.a,g.b]

    return x

def frange(start, end=None, inc=None):
    #"A range function, that does accept float increments..."
    if end == None:
        end = start + 0.0
        start = 0.0
    else: start += 0.0 # force it to be a float
    if inc == None:
        inc = 1.0
        
    count = int((end - start) / inc)
    if start + count * inc != end:
        # need to adjust the count.
        # AFAIKT, it always comes up one short.
        count += 1

    L = [None,] * count
    for i in xrange(count):
        L[i] = start + i * inc

    return L