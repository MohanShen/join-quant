# Clone from JoinQuant
# postId: 1b0b018d3708272993b0f2bf8a3c3772
# backtestId: 8c4141e1bc9435becefdb7cd1bf423b0
# title: 以csv格式保存order、trade、position对象

# 每日定时调用write_logs
# 支持股票、期货策略
# 支持每日、分钟策略
# 支持回测、模拟交易
# 测试时：日度策略可以适度放大回测时间段，分钟级策略避免时间过长，建议选择2日
# 本回测采用期货分钟级策略演示

import pandas as pd
# 初始化函数，设定要操作的股票、基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    
    init_cash = context.portfolio.starting_cash 
    # 设定账户为金融账户，初始资金为 init_cash 变量代表的数值（如不使用设置多账户，默认只有subportfolios[0]一个账户，Portfolio 指向该账户。）
    set_subportfolios([SubPortfolioConfig(cash=init_cash, type='futures')])
    
    run_daily(func, time='every_bar',reference_security='CU9999.XSGE')
    
    run_daily(write_logs, time='15:00:00',reference_security='CU9999.XSGE')

def process_initialize(context):
    ls=['security']
    g.__df1 = pd.DataFrame(columns=ls)
    g.__df2 = pd.DataFrame(columns=ls)
    g.__df3 = pd.DataFrame(columns=ls)

def func(context):
    f = get_dominant_future('CU')
    if f not in context.portfolio.positions:
        order(f, 10)
    else:
        order(f, -2)
    
def write_logs(context):
    ########## Orders ##############
    orders = get_orders()
    i=0
    ls1 = ['order_id','status','security','price','amount',\
            'avg_cost','Time','is_buy','filled','side','action']
    df1 = pd.DataFrame(columns=ls1)
    for _orders in orders.values():
        df1.loc[i,'order_id'] = _orders.order_id
        df1.loc[i,'status'] = _orders.status
        df1.loc[i, 'security'] = _orders.security
        df1.loc[i,'price'] = _orders.price
        df1.loc[i,'amount'] = _orders.amount
        df1.loc[i,'avg_cost'] = _orders.avg_cost
        df1.loc[i, 'Time'] = _orders.add_time
        df1.loc[i, 'is_buy'] = _orders.is_buy
        df1.loc[i, 'filled'] = _orders.filled
        df1.loc[i, 'side'] = _orders.side
        df1.loc[i, 'action'] = _orders.action
        i=i+1
    df1.set_index('Time',drop=True,inplace=True)
    g.__df1 = g.__df1.append(df1)
    #print(g._df1)
    write_file('orders.csv', g.__df1.to_csv())
    ############# Trades ####################
    trades = get_trades()
    i=0
    ls2 = ['Time','order_id','trade_id','security','price','amount']
    df2 = pd.DataFrame(columns=ls2)
    for _trades in trades.values():
        df2.loc[i,'Time'] = _trades.time
        df2.loc[i,'order_id'] = _trades.order_id
        df2.loc[i, 'trade_id'] = _trades.trade_id
        df2.loc[i,'security'] = _trades.security
        df2.loc[i,'price'] = _trades.price
        df2.loc[i,'amount'] = _trades.amount
        i=i+1
    df2.set_index('Time',drop=True,inplace=True)
    g.__df2 = g.__df2.append(df2)
    #print(g._df2)
    write_file('trade.csv', g.__df2.to_csv())
    
    ############### Position ################
    position = context.portfolio.positions.keys()
    i=0
    ls3 = ['security','price','acc_avg_cost','avg_cost','Time','transact_time','total_amount',\
        'closeable_amount','today_amount','locked_amount','value','side']
    df3 = pd.DataFrame(columns=ls3)
    for stock in position:
        df3.loc[i,'security']=context.portfolio.positions[stock].security
        df3.loc[i,'price'] = context.portfolio.positions[stock].price
        df3.loc[i,'acc_avg_cost'] = context.portfolio.positions[stock].acc_avg_cost
        df3.loc[i,'avg_cost'] = context.portfolio.positions[stock].avg_cost
        df3.loc[i, 'Time'] = context.portfolio.positions[stock].init_time
        df3.loc[i,'transact_time'] = context.portfolio.positions[stock].transact_time
        df3.loc[i,'total_amount'] = context.portfolio.positions[stock].total_amount
        df3.loc[i,'closeable_amount'] = context.portfolio.positions[stock].closeable_amount
        df3.loc[i,'today_amount'] = context.portfolio.positions[stock].today_amount
        df3.loc[i,'locked_amount'] = context.portfolio.positions[stock].locked_amount
        df3.loc[i,'value'] = context.portfolio.positions[stock].value
        df3.loc[i,'side'] = context.portfolio.positions[stock].side
        i=i+1
    df3.set_index('Time',drop=True,inplace=True)
    g.__df3 = g.__df3.append(df3)
    #print(g._df3)
    write_file('position.csv', g.__df3.to_csv())
    