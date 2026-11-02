# Clone from JoinQuant
# postId: 92a611f89bec552c0281038c00269667
# backtestId: 0d5ac220158aeb33a1b6c2cb403a04fe
# title: 这个策略为何回测正确,模拟就不对?

from jqdata import *
import pandas as pd

def initialize(context):
    g.select_stocks = []
    g.buy_stocks = []

def before_trading_start(context):
    #获取最近的40个交易日内上市的股票
    start = get_trade_days(end_date=datetime.datetime.now(), count=40)[0]
    df = get_all_securities('stock')
    stock_list = df[df['start_date']>start].index
    g.select_stocks = []
    g.buy_stocks = []
    #查找还未开板的股票
    for stock in stock_list:
        h = attribute_history(stock, 60, unit='1d', fields=('open', 'close', 'low', 'high'), skip_paused=True).dropna()
        kb = 0
        for i in range(1,len(h['close'])):
            if(h['low'][i]>=h['close'][i-1]*1.0994 and h['high'][i]>=h['close'][i-1]*1.0994):
                kb+=1
                continue
            else:
                break
        if kb==len(h['close'])-1:
            g.select_stocks.append(stock)
    print("今日未开板新股:")
    print(g.select_stocks)

def handle_data(context, data):
    #g.select_stocks = ['002826.XSHE']
    if context.current_dt.hour==9 and context.current_dt.minute==30:
        return
    curr_data = get_current_data()
    for stock in g.select_stocks:
        #h = attribute_history(stock, 1, unit='1m', fields=('close'), skip_paused=True).dropna()
        if data[stock].paused==False and data[stock].close<curr_data[stock].high_limit:
            g.buy_stocks.append(stock)
            g.select_stocks.remove(stock)
            h2 = attribute_history(stock, 1, unit='1d', fields=('close'), skip_paused=True).dropna()
            print('开板新股%s,涨幅%f%%'%(stock, (data[stock].close-h2.close[-1])/h2.close[-1]*100))
            #send_message('开板新股%s,涨幅%f%%'%(stock, (data[stock].close-h2.close[-1])/h2.close[-1]*100))