# Clone from JoinQuant
# postId: 319acd07cebeed34aa61aead213186f4
# backtestId: 1967226a05886ac1f4dde64af3119006
# title: 为什么在程序里面设置了过滤涨停股，回测时却还是买到了涨停股？

#二八轮动小市值动量策略。
#沪深300指数表征大盘 二，中证500表征中小盘 八。
#7月1日修改：增加大盘小盆切换判断，收益降低，回撤减小。
#7月4日测试调仓频率与最大持股数目。
#7.5日测试满仓情况
#7.19修改
import pandas as pd 
import talib as tl  
def initialize(context):
    # 设置手续费率
    set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
    set_slippage(PriceRelatedSlippage(0.002))
    # 设置基准指数：沪深300指数 '000300.XSHG'
    set_benchmark('000300.XSHG')
    # 使用真实价格回测(模拟盘推荐如此，回测请注释)
    set_option('use_real_price', True)
    g.stocks = []
    g.stockCount = 60
    g.buyStockCount = 15
    g.period = 15 #调仓频率
    g.days = 0 # 计时器


def getStockPrice(stock, interval):
    h = attribute_history(stock, interval, unit='1d', fields=('close'), skip_paused=True)
    return h['close'].values[0]


    
def handle_data(context, data):
    # 获得当前时间
    hour = context.current_dt.hour
    minute = context.current_dt.minute
    day=context.current_dt.day
    month=context.current_dt.month
    # 每天下午14:53调仓
    if hour ==14 and minute==53:
        lag = 20 # 回看前20天
        # 获得当前总资产
        value = context.portfolio.portfolio_value
        
        zs2 =  '000300.XSHG' #300指数
        zs8 =  '000905.XSHG'#500指数
   
        hs300 = getStockPrice(zs2, lag)
        zz500 = getStockPrice(zs8, lag)
        hs3001 = getStockPrice(zs2, 6)
        zz5001 = getStockPrice(zs8, 6)
        cp300 = data[zs2].close
        cp500 = data[zs8].close
        ret300 = (cp300 - hs300) / hs300;
        ret500 = (cp500 - zz500) / zz500;
        ret3001 = (cp300 - hs3001) / hs3001;
        ret5001 = (cp500 - zz5001) / zz5001;

        if (ret300 <= 0 and ret500 <= 0) or(ret3001 <= 0 and ret5001 <= 0):
            sell_all_stocks(context)
        elif  (ret500 > 0 or ret300 > 0) :
            if (day==31 or day==30 or day==29) and month==12:
                sell_all_stocks(context)
            else:
                if ret3001-ret5001>0.03:
                    buy_max_stocks(context)
                buy_min_stocks(context)
            g.days += 1
        

def sell_all_stocks(context):
    for stock in context.portfolio.positions.keys():
            order_target_value(stock, 0)
    g.days = 0

def buy_min_stocks(context):
    g.run_today = g.days % g.period == 0
    if g.run_today == False:
        return
    scu0 = get_index_stocks('000001.XSHG')
    scu3 = get_index_stocks('399001.XSHE')
    scu2 = get_index_stocks('000300.XSHG')
    scu = scu0+scu3
    set_universe(scu)
    
    df = get_fundamentals(query(
        valuation.code, valuation.market_cap
    ).order_by(valuation.market_cap.asc()).limit(g.stockCount))
    
    date=context.current_dt.strftime("%Y-%m-%d")
    #print(list(df['market_cap']))
    buylist=list(df['code'])
    # 去除ST，*ST
    current_data = get_current_data()
    buylist=[stock for stock in buylist if not current_data[stock].paused and not current_data[stock].is_st 
        and 'ST' not in current_data[stock].name and '*' not in current_data[stock].name and '退' not in current_data[stock].name]


    #剔除掉涨停的股票
    g.stocks = []
    for stock in buylist:
        prices = history(1, unit='1m', field='close', security_list=stock)
        if prices[stock][-1] < get_current_data(stock)[stock].high_limit:
            g.stocks.append(stock)
            
    g.stocks = g.stocks[:g.buyStockCount]
    set_universe(g.stocks)

    for stock in context.portfolio.positions.keys():
        if stock not in g.stocks:
            order_target_value(stock, 0)
    
    valid_count = 0
    for stock in context.portfolio.positions.keys():
        if context.portfolio.positions[stock].total_amount > 0:
            valid_count = valid_count + 1
   
    if len(g.stocks) == 0 or valid_count == len(g.stocks):
        return
    if g.buyStockCount<=valid_count:
        return
    weight = 1.0/(g.buyStockCount-valid_count)
    cashe=context.portfolio.cash*0.8
    for stock in g.stocks:
        order_target_value(stock, cashe*weight)
    
def buy_max_stocks(context):
    g.run_today = g.days % g.period == 0
    if g.run_today == False:
        return
    scu = get_index_stocks('000300.XSHG')
    set_universe(scu)
    df = get_fundamentals(query(
        valuation.code, valuation.market_cap
    ).order_by(
        # 按市值降序排列
        valuation.market_cap.desc()
    ).limit(
        g.stockCount
    ))
    date=context.current_dt.strftime("%Y-%m-%d")
    # 去除停牌
    buylist=list(df['code'])
    # 去除ST，*ST
    current_data = get_current_data()
    buylist=[stock for stock in buylist if not current_data[stock].paused and not current_data[stock].is_st 
        and 'ST' not in current_data[stock].name and '*' not in current_data[stock].name and '退' not in current_data[stock].name]

    
    
    #剔除掉涨停的股票
    g.stocks = []
    for stock in buylist:
        prices = history(1, unit='1m', field='close', security_list=stock)
        if prices[stock][-1] < get_current_data(stock)[stock].high_limit:
            g.stocks.append(stock)
    
    g.stocks = g.stocks[20:g.buyStockCount+20]
    set_universe(g.stocks)
 
    for stock in context.portfolio.positions.keys():
        if stock not in g.stocks:
            order_target_value(stock, 0)
    
    valid_count = 0
    for stock in context.portfolio.positions.keys():
        if context.portfolio.positions[stock].total_amount > 0:
            valid_count = valid_count + 1
   
    if len(g.stocks) == 0 or valid_count == len(g.stocks):
        return
    if g.buyStockCount<=valid_count:
        return
    weight = 1.0/(g.buyStockCount-valid_count)
    cashe=context.portfolio.cash*0.8
    for stock in g.stocks:
        order_target_value(stock, cashe*weight)
    
