# Clone from JoinQuant
# postId: 0940ee77827a02a06e07f803b8685a8a
# backtestId: ed0fd291bbaff7c1a36f550582271b49
# title: 冰晶龙的策略[帮忙实现]

def lowpe_imst():
    '''
    找出市盈率大于1小于20非ST的股票
    '''
    df = get_fundamentals(query(
            valuation.code, valuation.pe_ratio
        ).filter(
        valuation.pe_ratio > 1.0,
        valuation.pe_ratio < 20,
        ))
    # 市盈率从小到大排列
    df = df.dropna().sort(columns='pe_ratio',ascending=True)
    # df = df.head(300)
    temp = list(df['code'])
    # 找出当天的ST股票
    ST = get_all_securities()
    ST = [code for code in ST.index if ST['display_name'][code].upper().startswith('*') or ST['display_name'][code].upper().startswith('ST')]
    # 将ST股票从股票池中删除
    # print len(ST)
    current_security = temp[:]
    for i in current_security:
        if i in ST:
            current_security.remove(i)
    return temp,current_security

def initialize(context):
    # 策略参考标准
    set_benchmark('000300.XSHG')
    # 设置手续费，买入时万分之三，卖出时万分之三加千分之一印花税, 每笔交易最低扣5块钱
    set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
    g.stocknum = 10 #购买股票数
    g.day_num = {}

def before_trading_start(context):
    # 找出市盈率大于1小于20非ST的股票
    [g.security,g.current_security] = lowpe_imst()
    g.buylist = []
    # 股价大于5.3小于53，振幅大于0%小于8.2%
    for stock in g.current_security:
        hist = attribute_history(stock, 2, '1d', ('high','low','close','open'))
        high = hist['high'][-1]
        low = hist['low'][-1]
        open = hist['open'][-1]
        close2 = hist['close'][-2]
        close1 = hist['close'][-1]
        if (5.3 < open < 53) and (0<(high-low)/close2<0.082):
            g.buylist.append(stock)
            # # 可测试条件有无上影线
            # if high > max(open,close1)*1.005:
            #     g.buylist.append(stock)

def handle_data(context, data):
    # buylist = g.buylist.reverse()
    # 分配资金
    if len(context.portfolio.positions) < g.stocknum :
        Num = g.stocknum  - len(context.portfolio.positions)
        Cash = context.portfolio.cash/Num
    else: 
        Cash = context.portfolio.cash
        
    # 买入
    for stock in g.buylist:
        if stock not in context.portfolio.positions.keys() and data[stock].paused == False:
            order_value(stock,Cash)
            g.day_num[stock] = 1
    
    # 止损
    date = context.current_dt.strftime("%Y-%m-%d")
    for stock in context.portfolio.positions.keys():
        price = data[stock].open
        # opens = get_price([stock],date,date,'daily',['open'])
        # price = opens['open'][stock][date]
        avg_cost = context.portfolio.positions[stock].avg_cost
        if (price-avg_cost)/avg_cost <= -0.2 and data[stock].paused == False:
            order_target(stock, 0)
            # del g.day_num[stock]
    
    # 统计持股天数并卖出持股五天的股票
    for stock in g.day_num.keys():
        if g.day_num[stock] > 5 and data[stock].paused == False:
            order_target(stock, 0)
            # del g.day_num[stock]
        else:
            g.day_num[stock] += 1
        

