# Clone from JoinQuant
# postId: cf5cbac2d157b0b87ffbaf8868713226
# backtestId: 4b6dfbd136721cfcf65e6800575ce94c
# title: 单股2014.01.01-2016.08.01，收益6508%，年化386%

#策略概述：《小市值策略改进版》
#https://www.joinquant.com/post/2035?tag=new
#1.选择eps>0的所有股票，按市值从小到大排序，选择前100支候选
#2.剔除创业板，ST,*,退，停牌等股票
#3.选择市值最小的20只（前20只）候选
#4.给候选股票评分, 每天下午2点50分执行。
#lowPrice130 = 前130天内最低价格
#highPrice130 = 前130天内最高价格
#avg15 = 前15天均价
#currPrice = 当前价格
#score = (currPrice-lowPrice130)+(currPrice-highPrice130)+(currPrice-avg15)
#5.将候选股票的score得分，从小到大排序。选择最小的4支持仓。
#6.持股3天轮换，如果一样的就继续持有，不一样的就换掉。
#7.大盘止损使用上证50，与中小板R 指数。如果都小于20天前的101%，则清空仓位不交易。
#2016/8/9
#关于止损策略，我有点说漏了。
#仓位股票使用跟踪止损，每分钟监测，如果有更高价则记录之，如果从最高价回撤9.9%，则抛掉，当天14：50马上重新选股持仓。
#8.识别大盘“三只乌鸦”的形态，如果发现，当天就清仓。

from sqlalchemy import desc
import numpy as np
import pandas as pd
from scipy import stats
import tradestat

def initialize(context):
    # 对比标的
    set_benchmark('000300.XSHG') 
    # 设置佣金
    set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0003, min_cost=5))
    g.stocks = []
    g.stockCount = 1
    g.buyStockCount = 10
    g.days = 2
    g.period = 3
    g.high={}
    g.pct_change = {}
    g.trade_stat = tradestat.trade_stat()
    
def stock_stop_loss(context, data):
    for stock in context.portfolio.positions.keys():
        cur_price = data[stock].close

        if g.high[stock] < cur_price:
            g.high[stock] = cur_price

        threshold = get_stop_loss_threshold(stock, g.period)
        #log.debug("个股止损阈值, stock: %s, threshold: %f" %(stock, threshold))
        if cur_price < g.high[stock] * (1 - threshold):
            log.info("==> 个股止损, stock: %s, cur_price: %f, high: %f, threshold: %f" 
                %(stock, cur_price, g.high[stock], threshold))

            position = context.portfolio.positions[stock]
            if close_position(position):
                g.day_count = 0

                
def get_stop_loss_threshold(security, n = 3):
    pct_change = get_pct_change(security, 250, n)
    #log.debug("pct of security [%s]: %s", pct)
    maxd = pct_change.min()
    #maxd = pct[pct<0].min()
    avgd = pct_change.mean()
    #avgd = pct[pct<0].mean()
    # maxd和avgd可能为正，表示这段时间内一直在增长，比如新股
    bstd = (maxd + avgd) / 2

    # 数据不足时，计算的bstd为nan
    if not isnan(bstd):
        if bstd != 0:
            return abs(bstd)
        else:
            # bstd = 0，则 maxd <= 0
            if maxd < 0:
                # 此时取最大跌幅
                return abs(maxd)

    return 0.099 # 默认配置回测止损阈值最大跌幅为-9.9%，阈值高貌似回撤降低

    
def get_pct_change(security, n, m):
    pct_change = None
    if security in g.pct_change.keys():
        pct_change = g.pct_change[security]
    else:
        h = attribute_history(security, n, unit='1d', fields=('close'), skip_paused=True)
        pct_change = h['close'].pct_change(m) # 3日的百分比变比（即3日涨跌幅）
        g.pct_change[security] = pct_change
    return pct_change
    
def close_position(position):
    security = position.security
    order = order_target_value_(security, 0) # 可能会因停牌失败
    if order != None:
        if order.filled > 0:
            # 只要有成交，无论全部成交还是部分成交，则统计盈亏
            g.trade_stat.watch(security, order.filled, position.avg_cost, position.price)

        if order.status == OrderStatus.held and order.filled == order.amount:
            # 全部成交则删除相关证券的最高价缓存
            if security in g.high:
                g.high.pop(security)
            else:
                log.warn("last high price of %s not found" %(security))
            return True

    return False
    
def order_target_value_(security, value):
    if value == 0:
        log.debug("Selling out %s" % (security))
    else:
        log.debug("Order %s to value %f" % (security, value))
        
    # 如果股票停牌，创建报单会失败，order_target_value 返回None
    # 如果股票涨跌停，创建报单会成功，order_target_value 返回Order，但是报单会取消
    # 部成部撤的报单，聚宽状态是已撤，此时成交量>0，可通过成交量判断是否有成交
    return order_target_value(security, value)


def getStockPrice(stock, interval):
    h = attribute_history(stock, interval, unit='1d', fields=('close'), skip_paused=True)
    return h['close'].values[0]

def unpaused(stockspool):
    current_data=get_current_data()
    return [s for s in stockspool if not current_data[s].paused]    

#过滤掉带*或者ST类股票
def filterStarName(stock_list):
    curr_data = get_current_data()
    return  [stock for stock in stock_list if 'ST' not in curr_data[stock].name and
        '*' not in curr_data[stock].name and '退' not in curr_data[stock].name]

def sell_all_stocks(context):
    for stock in context.portfolio.positions.keys():
            order_target_value(stock, 0)
            print('Sell: ',stock)
    #很关键！第一次写程序的时候没有这一句，会造成下面的无法买入。
    g.days = 0          
    
def isThreeBlackCrows(stock, data):
    his =  attribute_history(stock, 2, '1d', ('close','open'), skip_paused=True, df=False)
    closeArray = list(his['close'])
    closeArray.append(data[stock].close)
    openArray = list(his['open'])
    openArray.append(get_current_data()[stock].day_open)
    if closeArray[0]<openArray[0] and closeArray[1]<openArray[1] and closeArray[2]<openArray[2]:
        if closeArray[-1]/closeArray[0]-1>-0.045:
            his =  attribute_history(stock, 4, '1d', ('close','open'), skip_paused=True, df=False)
            closeArray1 = his['close']
            if closeArray[0]/closeArray1[0]-1>0:
                return True
    return False
    
def filter_gem_stock(context, stock_list):
    return [stock for stock in stock_list if stock[0:3] != '300']
    
def filter_paused_and_st_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused and not current_data[stock].is_st 
        and 'ST' not in current_data[stock].name and '*' not in current_data[stock].name and '退' not in current_data[stock].name]

def Multi_Select_Stocks(context, data):
    #stocks = get_all_securities(['stock'])
    #排除新股
    #stocks = stocks[(context.current_dt.date() - stocks.start_date) > datetime.timedelta(60)].index
    #stocks  = stocks.index
    #date=context.current_dt.strftime("%Y-%m-%d")
    #st=get_extras('is_st', stocks, start_date=date, end_date=date, df=True)
    #st=st.loc[date]
    #stocks = list(st[st==False].index)
    #stocks = unpaused(stocks)
    #stocks = filterStarName(stocks)
    
    q = query(
        valuation.code,
        ).filter(
        indicator.eps > 0,
        valuation.pe_ratio > 0,
        #valuation.pe_ratio < 200
        #valuation.code.in_(stocks)
    ).order_by(
        # 按市值升序排列
        valuation.market_cap.asc()
    ).limit(
        # 最多返回20个
        100
    )
    df = get_fundamentals(q)
    stocks = df.code.values
    stocks=filter_paused_and_st_stock(stocks)
    stocks=filter_gem_stock(context,stocks)
    
    if len(stocks)>=20:
        stocks=stocks[:20]
    else:
        stocks=stocks[:len(stocks)]
    stock_select={}
    for s in stocks:
        h = attribute_history(s, 130, unit='1d', fields=('close', 'high', 'low'), skip_paused=True)
        lowPrice130 = h.low.min()
        highPrice130 = h.high.max()
        avg15 = data[s].mavg(15,field='close')
        currPrice = data[s].close
        score = (currPrice-lowPrice130)+(currPrice-highPrice130)+(currPrice-avg15)
        stock_select[s] = score
        
    dfs = pd.DataFrame(stock_select.values(),index=stock_select.keys())
    dfs.columns=['score']
    dfs=dfs.sort(columns='score',ascending=True)
    return dfs.index[:g.stockCount]

# 每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)调用一次
def handle_data(context, data):
    #stock_stop_loss(context, data)
    #stock_stop_profit(context, data)
    # 获得当前时间
    hour = context.current_dt.hour
    minute = context.current_dt.minute
    
    h = attribute_history('000001.XSHG', 130, unit='1d', fields=('close', 'high', 'low'), skip_paused=True)
#    lowPrice130 = h.low.min()
#    highPrice130 = h.high.max()
#    if highPrice130>lowPrice130:
#        sell_all_stocks(context) 
#        return
    if isThreeBlackCrows('000001.XSHG',data):
        print('清仓')
        sell_all_stocks(context)   
        return
    
    for stock in context.portfolio.positions.keys():
        if g.high[stock]<data[stock].close:
            g.high[stock]=data[stock].close
        if data[stock].close<0.901*g.high[stock]:
            if order_target_value(stock, 0)!=None:
                print('code',stock,'high:',g.high[stock],'now:',data[stock].close)
                g.days=0
                #g.high.pop(stock)
                g.high[stock]=0
                
    # 每天下午14:53调仓
    if hour ==14 and minute==50:
        lag = 20 # 回看前20天
        # 获得当前总资产
        value = context.portfolio.portfolio_value
        #if isThreeBlackCrows('000001.XSHG',data):
        #    print('清仓')
        #    sell_all_stocks(context)   
        #    return
        zs2 =  '000016.XSHG' #上证50指数
        zs8 =  '399333.XSHE' #创业板指数
        
        hs2 = getStockPrice(zs2, lag)
        hs8 = getStockPrice(zs8, lag)
        cp2 = data[zs2].close
        cp8 = data[zs8].close
        
        if (not isnan(hs2)) and (not isnan(cp2)):
            ret2 = (cp2 - hs2) / hs2;
        else:
            ret2 = 0
        if (not isnan(hs8)) and (not isnan(cp8)):
            ret8 = (cp8 - hs8) / hs8;
        else:
            ret8 = 0
        #print(ret2,ret8)
        print('sz50:',ret2,'zxb:',ret8)  
        #奇怪，低于101%时清仓，回测效果出奇得好。
        buy_stocks(context, data)
        '''
        if ret2>0.00 or ret8>0.00 :   
            print('持有，每3天进行调仓')
            buy_stocks(context, data)
        else :
            print('清仓')
            sell_all_stocks(context)        
        '''
            

def buy_stocks(context, data):
    g.days += 1
    if g.days % g.period == 1:            
            
        buylist = Multi_Select_Stocks(context, data)
        
        #排除涨停、跌停股
        g.stocks = []
        for stock in buylist:
            if data[stock].low_limit*1.005 < data[stock].close < data[stock].high_limit*0.995 :
                g.stocks.append(stock)
            #已持有的涨停股，继续持有    
            elif (data[stock].close >= 0.995*data[stock].high_limit) and (stock in context.portfolio.positions.keys()):
                g.stocks.append(stock)
            if len(g.stocks)>=g.buyStockCount:
                break
        #print(g.stocks)
        set_universe(g.stocks)
        
        # close stock positions not in the current universe
        cntSuspension=0
        remainvalue=0
        for stock in context.portfolio.positions.keys():
            if stock not in g.stocks:
                print('Rank Outof 10, Sell: ',stock)
                if order_target_value(stock, 0)==None :
                    cntSuspension +=1
                    remainvalue=remainvalue+data[stock].close*context.portfolio.positions[stock].total_amount
        #g.stocks = g.stocks[:len(g.stocks)-cntSuspension]
        
        #valid_count = 0
        #for stock in context.portfolio.positions.keys():
        #    if context.portfolio.positions[stock].total_amount > 0:
        #        valid_count = valid_count + 1
        # place equally weighted orders
        #if len(g.stocks) == 0 or valid_count >= len(g.stocks):
        #    return
        
        #for stock in g.stocks:
        #    if context.portfolio.positions[stock].total_amount <= 0:
        #        g.high[stock]=data[stock].close
        #    #order_target_value(stock, (context.portfolio.portfolio_value-remainvalue)/len(g.stocks))
        #    order_target_value(stock, context.portfolio.portfolio_value/len(g.stocks))
    position_count = len(context.portfolio.positions)
    if g.stockCount > position_count:
        value = context.portfolio.cash / (g.stockCount - position_count)
        for stock in g.stocks:
            if context.portfolio.positions[stock].total_amount <= 0:
                g.high[stock]=data[stock].close
            if context.portfolio.positions[stock].total_amount == 0:
                order_target_value(stock, value)
                if len(context.portfolio.positions) == g.stockCount:
                    break