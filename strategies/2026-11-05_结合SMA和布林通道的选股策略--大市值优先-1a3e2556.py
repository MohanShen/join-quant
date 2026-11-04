# Clone from JoinQuant
# postId: 1a3e2556385d294274abc50d51e1c75b
# backtestId: a9b97e52fc7d97f60d9ad2b4e2e9ea72
# title: 结合SMA和布林通道的选股策略--大市值优先

# 导入函数库
from jqdata import *
import pandas as pd

# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')

    g.hold_days = {}
    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')

    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
      # 开盘前运行
    run_daily(before_market_open, time='before_open', reference_security='000300.XSHG')
      # 开盘时运行
    run_daily(market_open, time='open', reference_security='000300.XSHG')
      # 收盘后运行
    run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')

## 开盘前运行函数
def before_market_open(context):
    # 输出运行时间=
    g.canbuy = choose_stocks(context.current_dt)
    log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))
    log.info(g.canbuy)
    # 给微信发送消息（添加模拟交易，并绑定微信生效）
    # send_message('美好的一天~')

    # 要操作的股票：平安银行（g.为全局变量）
    g.security = '000001.XSHE'

## 开盘时运行函数
def market_open(context):
    log.info('函数运行时间(market_open):'+str(context.current_dt.time()))
    log.info(context.portfolio)
    log.info(g.hold_days)
    security = g.security
    # 获取股票的收盘价
    close_data = get_bars(security, count=5, unit='1d', fields=['close'])
    # 取得过去五天的平均价格
    MA5 = close_data['close'].mean()
    # 取得上一时间点价格
    current_price = close_data['close'][-1]
    # 取得当前的现金
    cash = context.portfolio.available_cash
    
    sell_list = list(context.portfolio.positions.keys())
    if len(sell_list) > 0 :
        for stock in sell_list:
            if should_sell_stock(stock, context.current_dt) or g.hold_days[stock] > 15:
                if can_trade(stock):
                    order_target(stock, 0)
                    del g.hold_days[stock]
    
    buylist = [item for item in g.canbuy if item not in sell_list and can_trade(item)]
    count = len(sell_list)
    
    if buylist is not None and len(buylist) > 0 and count < 3:
        cnt = 3 - count if 3 - count < len(buylist) else len(buylist)
        for stock in buylist[:cnt]:
            order_value(stock, cash / (3-count))
            g.hold_days[stock] = 0
    log.info(g.hold_days)
    add_hold_days(g.hold_days)

## 收盘后运行函数
def after_market_close(context):
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    #得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    log.info('一天结束')
    log.info('##############################################################')
    
def choose_stocks(today):
    df0 = get_all_securities(date=today.strftime("%Y-%m-%d"))
    ss = list(df0.index)
    l = []
    for s in ss:
        x, y, z = should_buy_stock(s, today)
        if x > 0:
            l.append(s)
    return sort_stocks(l, today)
    
def sort_stocks(l, today):
    if len(l) == 0:
        return l
    df = get_fundamentals(query(
        valuation, income
    ).filter(
        # 这里不能使用 in 操作, 要使用in_()函数
        valuation.code.in_(l)
    ), date=today.strftime("%Y-%m-%d"))
    df1 = df[["code","market_cap"]].sort('market_cap', ascending=False)
    return list(df1["code"])
    
def add_hold_days(m):
    if not m:
        return
    for item in m.keys():
        m[item] = m[item] + 1
    
def show_bollinger_bands(code, window, start, end, draw=False):
#     data = ts.get_k_data(code, start, end)
#     data = data.set_index("date")
    data = get_price(code, start_date=start, end_date=end, frequency='daily', fields=None, skip_paused=True, fq='pre')
    if data.empty or len(data) < 22:
#         print("not enough data for %s" % code)
        return
    # data["rolling mean"] = data[["close"]].rolling(window=20, center=False).mean()
    # data["rolling std"] = data[["close"]].rolling(window=20, center=False).std()
    
    data["rolling mean"] = pd.rolling_mean(data["close"], window=20)
    data["rolling std"] = pd.rolling_std(data["close"], window=20)
    data["upper bands"] = data["rolling mean"] + 2 * data["rolling std"]
    data["lower bands"] = data["rolling mean"] - 2 * data["rolling std"]
    if draw:
        ax = data[["close", "rolling mean", "upper bands", "lower bands"]].plot(figsize=(30,15), grid=True, title=code, fontsize=20)
        ax.legend(loc = 0, ncol = 2, prop={'size': 20})
#     plyo.iplot(data[["close", "rolling mean", "upper bands", "lower bands"]].iplot(asFigure=True, theme="polar", title="time Series bollinger"), filename="ply_01")
    return data[["close", "rolling mean", "upper bands", "lower bands"]]
    
def show_rolling_sma(code, start, end, draw=False):
#     data = ts.get_k_data(code, start, end)
#     data = data.set_index("date")
    data = get_price(code, start_date=start, end_date=end, frequency='daily', fields=None, skip_paused=True, fq='pre')
    if data.empty or len(data) < 22:
#         print("not enough data for %s" % code)
        return
    # data["sma42"] = data["close"].rolling(window=42).mean()
    # data["sma252"] = data["close"].rolling(window=252).mean()
    data["sma42"] = pd.rolling_mean(data["close"], window=10)
    data["sma252"] = pd.rolling_mean(data["close"], window=66)
    d1 = data[["close", "sma42", "sma252"]].dropna()
    if draw and not d1.empty:
        d1.plot(figsize=(30,15), grid=True, title=code, fontsize=20)
#     plyo.iplot(d1.iplot(asFigure=True, theme="polar", title="time Series sma"), filename="ply_01")
    return d1

def should_buy_stock(code, today, draw=False):
    start = (today - datetime.timedelta(days=200)).strftime("%Y-%m-%d")
    end = (today - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    boll = show_bollinger_bands(code, 20, start, end, draw)
    sma = show_rolling_sma(code, start, end, draw)
    if boll is None or sma is None or boll.empty or sma.empty:
        return -101, boll, sma
    
    if np.any(boll["close"][-2:] > boll["upper bands"][-2:]):
        return -100, boll, sma
    if np.any(sma["close"][-3:] < sma["sma42"][-3:]):
        return -1, boll, sma
    if np.any(sma["sma42"][-3:] < sma["sma252"][-3:]):
        return -2, boll, sma
    if np.all(sma["sma42"][-10:-3] > sma["sma252"][-10:-3]):
        return -3, boll, sma
    if np.any(boll["close"][-5:] < boll["lower bands"][-5:]):
        return -4, boll, sma
    return 1, boll, sma
    
def should_sell_stock(code, today, draw=False):
    start = (today - datetime.timedelta(days=200)).strftime("%Y-%m-%d")
    end = (today - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    boll = show_bollinger_bands(code, 20, start, end, draw)
    sma = show_rolling_sma(code, start, end, draw)
    if np.all(sma["close"][-3:] < sma["sma42"][-3:]) or np.any(sma["close"][-3:] < sma["sma252"][-3:]) or np.any(sma["sma42"][-3:] < sma["sma252"][-3:]):
        return 1
    if np.any(boll["close"][-3:] < boll["lower bands"][-3:]):
        return 1
    return 0
    
def can_trade(stock):
    data = get_current_data()
    sd = data[stock]
    return not sd.paused and not sd.is_st
