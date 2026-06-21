# Clone from JoinQuant
# postId: 23b0cbdc6ab1f0fb90dfbaed43c09d5d
# backtestId: b33a29307a1392db52c5cd52d41b3bec
# title: 【经典策略系列】之周规则交易策略（使用分级移动止盈、移动止盈方法，以及新api--run_daily等的用法）

from mylib import dp_stoploss #导入止损

def initialize(context):
    g.stockindex = '000300.XSHG' # 指数
    g.security = get_index_stocks(g.stockindex)
    set_universe(g.security)
    set_benchmark('000300.XSHG')
    # run_daily(update_benchmark, time='before_open')
    set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
    g.HighAfterEntry = {} #存放持仓股票历史最高价
    g.stocknum = 20 # 持股数
    g.week = 4 # 调仓频率，单位为周
    g.count = 0 # 计数
    # 是否止损
    g.should_stop_loss = False #True:开启止损,False:关闭止损
    if g.should_stop_loss:
        run_daily(stop_loss)
    # 程序运行
    run_daily(update_HighAfterEntry, time='before_open')# 开盘前更新 g.HighAfterEntry
    run_weekly(weekly_rule_algorithm,1)# 周规则函数
    # run_daily(sell_stock)# 出售股票，但在此策略中略显多余
    run_daily(moving_stop_profit)# 分级移动止盈
    run_daily(add_HighAfterEntry, time='after_close')# 收盘后，根据成交订单将新买入的股票加入g.HighAfterEntry

def update_benchmark(context):
    g.stockindex = '000300.XSHG' # 指数
    g.security = get_index_stocks(g.stockindex)
    set_universe(g.security)
    set_benchmark('000300.XSHG')

def stop_loss(context):
    # 止损
    d = dp_stoploss(kernel=2, n=10, zs=0.08)
    if d:
        if len(context.portfolio.positions)>0:
            for stock in list(context.portfolio.positions.keys()):
                order_target(stock, 0)
        g.count = 0
        return

def update_HighAfterEntry(context):
    # 更新 g.HighAfterEntry
        if len(g.HighAfterEntry) > 0:
            for stock in g.HighAfterEntry.keys():
                temp_close = attribute_history(stock, 1, '1d','close',df=False)
                if g.HighAfterEntry[stock] < temp_close['close'][-1]:
                    g.HighAfterEntry[stock] = temp_close['close'][-1]
                else:
                    pass

def weekly_rule_algorithm(context):
    # 周规则函数
    security = g.security
    if g.count % g.week == 0:
        ## 分配资金
        if len(context.portfolio.positions) < g.stocknum :
            Num = g.stocknum  - len(context.portfolio.positions)
            Cash = context.portfolio.cash/Num
        else: 
            Cash = context.portfolio.cash

        # 周规则交易构建
        Buylist = {}
        n = g.week*5 + 1
        hist = history(n,'1d', 'high', df=False)
        hist2 = history(1,'1d', 'close', df=False)
        for stock in security:
            UpBand = max(hist[stock][:-1]) #定义上界为前n天的最高价
            Close = hist2[stock][-1]
            # 价格突破上界的股票的加入Buylist
            if Close > UpBand:
                Buylist[stock] = Close - UpBand

        # 根据权重排序进行买入
        if len(Buylist)>0:
            b1 = sorted(Buylist.iteritems(),key=lambda t:t[1],reverse=False)
            for n in range(25):
                try:
                    b2 = b1.pop()[0]
                except:
                    pass
                order_value(b2,Cash)
    g.count += 1 #计数

def sell_stock(context):
    # 持仓且价格跌破止损线的立即卖出
    n = g.week*5 + 1
    for stock in list(context.portfolio.positions.keys()):
        his = history(n,'1d', 'high', df=False)
        his2 = history(1,'1d', 'close', df=False)
        Close = his2[stock][-1]
        StopLoss = max(his[stock][(n/2):-1]) #定义止损线为前n/2天的最高价
        if Close <= StopLoss:
            order_target(stock, 0)

def moving_stop_profit(context,kernel = 1):
    '''run_daily接受的函数只接受context参数，
    所以如要选择何种止盈手段，需要再次修改kernel
    kernel==1 为分级移动止盈
    kernel==2 为移动止盈
    其中具体参数需要针对不同环境、不同交易品种进行设立。
    '''
    if kernel == 1:
        # 分级移动止盈
        for stock in list(g.HighAfterEntry.keys()):
            avg_cost = context.portfolio.positions[stock].avg_cost #获取成本
            high_price = g.HighAfterEntry[stock]
            profit_level = high_price/avg_cost-1 #收益率
            # 根据盈利设定stopLoss_price
            if profit_level < 0.2:
                stopLoss_price = high_price*0.5
            elif 0.5 > profit_level > 0.2:
                stopLoss_price = high_price*0.7
            elif profit_level >= 0.5:
                stopLoss_price = high_price*0.9
            # 判断
            temp_close2 = attribute_history(stock, 1, '1d','close',df=False)
            close2 = temp_close2['close'][-1]
            if close2 <= stopLoss_price:
                order_target(stock, 0)
    elif kernel == 2:
        # 移动止盈
        for stock in list(g.HighAfterEntry.keys()):
            temp_close2 = attribute_history(stock, 1, '1d','close',df=False)
            if temp_close2['close'][-1] <= g.HighAfterEntry[stock]*0.8:
                order_target(stock, 0)

def add_HighAfterEntry(context):
    # 将新买入的股票加入g.HighAfterEntry
    trades=get_orders()
    for t in trades.values():
        if t.is_buy and t.filled>0:
            x = str(t.security)
            g.HighAfterEntry[x] = t.price
        elif not t.is_buy and t.filled>0:
            xx = str(t.security)
            try:
                del g.HighAfterEntry[xx]
            except:
                g.HighAfterEntry[xx] = 0
    pass