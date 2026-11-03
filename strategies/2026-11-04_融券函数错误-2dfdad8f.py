# Clone from JoinQuant
# postId: 2dfdad8fca7c083aea2cf6642a021f4d
# backtestId: bc3a7d9b85cc7cf8c022c56d5133dad2
# title: 融券函数错误

# 导入函数库
from jqdata import *
import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.api import VAR
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import time
import warnings
warnings.filterwarnings("ignore")
# 初始化函数，设定基准等等
def initialize(context):
    init_cash = context.portfolio.starting_cash/2
    g.security = '600519.XSHG'
    # date3 = pd.to_datetime('09:32:00')
    # df1 = get_bars(g.security, count=1, unit='1m',fields=['open'],end_dt=date3,df = True)
    # openPrice = df1.iloc[0].values[0]
    # print("昨日收盘价:",openPrice)
    # g.todayOpenPrice = openPrice
    g.model = bulidModel(context.current_dt)
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # set_benchmark('000001.XSHE')
    set_option('t0_mode', 'True')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')
    set_subportfolios([SubPortfolioConfig(cash=init_cash, type='stock'),
                       SubPortfolioConfig(cash=init_cash, type='stock_margin')])
    set_option('marginsec_interest_rate', 0)
    set_option('marginsec_margin_rate', 0)
    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')

    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
      # 开盘前运行
    run_daily(before_market_open, time='before_open', reference_security='000300.XSHG')
      # 开盘时运行
    run_daily(market_open, time='every_bar', reference_security='000300.XSHG')
      # 收盘后运行
    run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')

def handle_data(context, data):
    d = data['600519.XSHG']
    # d是一个SecurityUnitData结构体，会画出每个单元时间(天或分钟)的平均价,开始价,结束价
    record(price=d.price, open=d.open, close=d.close)
    # 也可以画一条值为100的直线

## 开盘前运行函数
def before_market_open(context):
    # 输出运行时间
    g.model = bulidModel(context.current_dt)
    g.buyPrice = 0
    g.count = 0
    g.r = 0
    g.rPrice = 0
    log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))

    # 给微信发送消息（添加模拟交易，并绑定微信生效）
    # send_message('美好的一天~')

    # 要操作的股票：平安银行（g.为全局变量）
    
def different(buyPrice, closePrice, cash):
    if buyPrice == 0:
        return 0
    else:
        num = cash
        buyMoney = buyPrice*num*1.0003
        sellMoney = closePrice*num*0.9987
        if sellMoney < buyMoney * 0.995:
            return 1
        else:
            return 0


def bulidModel(today):
    # 建模
    date = today.date() - timedelta(days=10)
    # print(date)
    date1 = today.date()
    df = get_price(g.security, start_date=date, end_date=date1, frequency='minute',
               fields=['open', 'volume', 'money'])
    # print(df)
    df['entrustNum'] = abs(df['money'] // df['open'])
    index = df.index
    list = []
    for i in index:
        date = pd.to_datetime('09:40:00').time()
        date1 = pd.to_datetime('14:50:00').time()
        if i.time() < date or i.time() > date1:
            list.append(i)
    df = df.drop(index=list)
    ts = df[['open','volume','entrustNum']]
    ts.index = pd.DatetimeIndex(df.index)
    ts['open'] = np.log(ts['open'])
    model = sm.tsa.VAR(ts)
    result = model.fit(2)
    return result

def nextPrice(results, time1):
    date1 = pd.to_datetime('14:49:00').time()
    date2 = pd.to_datetime('09:40:00').time()
    ctime = time1.time()
    if ctime > date1:
        return None
    if ctime < date2:
        return None
    else:
        # date = time - timedelta(minutes=1)
        # date1 = time
        df = get_bars(g.security, count=4, unit='1m',fields=['open', 'volume', 'money'],
         end_dt=time1,df=True)
        df['entrustNum'] = abs(df['money'] // df['open'])
        # index = df.index
        ts = df[['open', 'volume', 'entrustNum']]
        # ts.index = pd.DatetimeIndex(df.index)
        # print(ts)
        ts['open'] = np.log(ts['open'])
        price = results.forecast(ts.values, 1)
        price[0][0] = np.exp(price[0][0])
        np.set_printoptions(precision=4)
        return price[0][0]

## 开盘时运行函数
def market_open(context):
    security = g.security
    
    date = pd.to_datetime('14:50:00').time()
    date1 = pd.to_datetime('09:40:00').time()
    ctime = context.current_dt.time()
    if date1 < ctime < date :
        df1 = []
        if str(ctime) == "13:00:00":
            date_new = pd.to_datetime(str(context.current_dt.date()) + ' 11:30:00')
            df1 = get_price(security, start_date=date_new, end_date=date_new, frequency='minute',
                   fields=['open'])
        else:
            df1 = get_price(security, start_date=context.current_dt, end_date=context.current_dt, frequency='minute',
                   fields=['open'])
                   
        closePrice = df1.values[0][0]
        # 取得预测价格
        price = nextPrice(g.model, context.current_dt)
        if price == None:
            price = closePrice
        else:
            price = price
        # 取得当前的现金
        if g.r == 0:
            if price < 0.995*closePrice:
                marginsec_open(g.security, 100, pindex=1)
                g.r = 1
                g.rPrice = closePrice
                log.info('购买了:'+g.r + '股'+ context.subportfolios[1].available_cash)
        if g.r == 1:
            if price > 1.005*closePrice:
                marginsec_close(g.security,100, pindex=1)
                g.r = 0
    if ctime >= date:
        if g.r == 1:
            marginsec_close(security,100,pindex=1)
    
    


## 收盘后运行函数
def after_market_close(context):
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    #得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    log.info('一天结束')
    log.info('##############################################################')
