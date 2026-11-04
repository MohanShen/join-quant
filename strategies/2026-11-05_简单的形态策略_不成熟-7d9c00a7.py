# Clone from JoinQuant
# postId: 7d9c00a7f131ac5db9d43c148ee64c73
# backtestId: ef67e36b49d6410a8004da264c818f43
# title: 简单的形态策略（不成熟）

#enable_profile()

from sqlalchemy import desc
import numpy as np
import pandas as pd
from scipy import stats

def initialize(context):
    # 对比标的
    set_benchmark('000300.XSHG') 
    # 设置佣金
    set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0003, min_cost=5))
    set_option('use_real_price', True)
    
    g.stocks = []
    
    # 缓存股票持仓后的最高价
    g.last_high = {}
    # 缓存股票持仓后的持有时间
    g.hold_time = {}
    # 缓存股票的评分：包含分数 并在持有时间大于3天或者2天之后评分
    g.score = {}
    # 缓存股票的买入价
    g.cost = {} 
    # 缓存股票持仓后的收益率
    g.profit = {}
    g.cross_days = {}
    
    # 
    g.short_ma = 5
    # 买入时回踩但必须站住的均线
    g.stand_ma = 20
    # 长均线的走好
    g.stand_ma = 60 
    
    # 同时最多持有几支股票
    g.buy_stock_count  = 5
    # 多头趋势天数
    g.in_trend_days = 3
    # 止盈百分比
    g.down_percentage = 0.05
    # 止损百分比
    g.loss_percentage = 0.03#对5日线而言


#
def pop_stock(security):
    g.last_high.pop(security)
    g.hold_time.pop(security)
    g.score.pop(security)
    g.cost.pop(security)
    g.cross_days.pop(security)

# 计算移动平均线数据
# 输入：股票代码-字符串，移动平均线天数-整数
# 输出：算术平均值-浮点数
def get_MA(security_code,days):
    # 获得前days天的数据，详见API
    a=attribute_history(security_code, days, '1d', ('close'))
    # 定义一个局部变量sum，用于求和
    sum=0
    # 对前days天的收盘价进行求和
    for i in range(1,days+1):
        sum+=a['close'][-i]
    # 求和之后除以天数就可以的得到算术平均值啦
    return sum/days


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

#涨幅筛选
def ratio_filter(available_stocks, context):

    signal = []
    # 对于所有多头趋势股票
    for security in available_stocks:
        # 获取昨日信息
        previous_history = attribute_history(security, 1, '1d', ['close','open'])
        # 昨日收盘价
        current_price = previous_history['close'].iloc[0]
        # 昨日开盘价
        current_open = previous_history['open'].iloc[0]
        pre_close = getStockPrice(security,2)
        
        ratio = (current_price - pre_close)/pre_close*100
        
        prices = attribute_history(security, 60, '1d', 'close', skip_paused= True)
        ma_data = prices[-5: ]
        ma5 = sum(ma_data).iloc[0] / 5
        ma_data = prices[-20: ]
        ma20 = sum(ma_data).iloc[0] / 20
        #涨幅大于3 且ma5 > ma20
        if  ratio >=3 and current_price > current_open  and current_price>ma5 > ma20 and security not in context.portfolio.positions:
            # 加入信号list 
            signal.append(security)

    return(signal)

#长均线转折点计数
def get_trend_days(security, period):

    prices = attribute_history(security, period*2, '1d', 'close', skip_paused= True)
    
    count = 0
    for i in range(1,period):
        ma_data = prices[-period-i: -i]
        ma= sum(ma_data).iloc[0] / period
        ma_data = prices[-period-i-1: -i-1]
        ma_1= sum(ma_data).iloc[0] / period
        
        if ma > ma_1:
            count = count + 1
        else:
            break
        
    return (count)
    


#短均线金叉长均线的时间
def days_filter(available_stocks, context):
    #log.debug("涨幅筛选后备选股票: %s" %(available_stocks))
    signal = []
    # 对于所有涨幅满足的股票
    for security in available_stocks:
        # 获取历史收盘价
        prices = attribute_history(security, 23+16, '1d', 'close', skip_paused= True)
        
        count = 0
        flag = 0
        for i in range(1,13):
 
            ma_data = prices[-5-i: -i]
            ma5 = sum(ma_data).iloc[0] / 5
            ma_data = prices[-5-i-1: -i-1]
            ma5_1 = sum(ma_data).iloc[0] / 5
            ma_data = prices[-5-i-2: -i-2]
            ma5_2 = sum(ma_data).iloc[0] / 5
            
            ma_data = prices[-20-i: -i]
            ma20= sum(ma_data).iloc[0] / 20
            ma_data = prices[-20-i-1: -i-1]
            ma20_1= sum(ma_data).iloc[0] / 20
            ma_data = prices[-20-i-2: -i-2]
            ma20_2= sum(ma_data).iloc[0] / 20             
  
            if ma5 > ma20 :
                #记录短均线在长均线上的时间也即金叉时间
                count = count + 1

                if ma5_1 < ma20_1 and ma5_2 < ma20_2 and i == count :
                    flag = 1
                    break
            else :

                break

        if flag > 0 and i >= 7 :
  
            g.cross_days[security] = i
            count = get_trend_days(security, 20)
            #count2 = get_trend_days(security, 60)
            '''            
            if security =='000897.XSHE':
                log.debug("金叉筛选后备选股票之一: %s" %(security))
                log.debug("金叉间隔: %s" %(count))
            '''                
            #长均线 的拐点应发生在 附近
            if count < i*2 and count >= i/2 :
                signal.append(security)
            
    # 输出信号
    return(signal)


# 计算买入信号
# 输入所有多头趋势股票
# 返回一list，包含所有在趋势内但是回踩长均线的股票
def buy_signal(available_stocks, context):

    #log.debug("金叉筛选后备选股票: %s" %(available_stocks))
    signal = []
    # 对于所有多头趋势股票
    for security in available_stocks:
        # 获取历史收盘价
        prices = attribute_history(security, 8, '1d', 'close', skip_paused = True)
        
        p1 = getStockPrice(security,2)
        p2 = getStockPrice(security,3)
        
        # 计算均线
        ma_data = prices[2:7]
        ma5_1 = sum(ma_data).iloc[0] / 5
        ma_data = prices[1:6]
        ma5_2 = sum(ma_data).iloc[0] / 5 
        ma_data = prices[:5]
        ma5_3 = sum(ma_data).iloc[0] / 5 
    
        if  p1 < ma5_1 and p2 < ma5_2 and ma5_3 > ma5_2 > ma5_1:
            #log.debug("金叉筛选后备选股票之一: %s" %(security))
            signal.append(security)

    return(signal)



def Multi_Select_Stocks(context, data):
    stocks = get_all_securities(['stock'])
    #排除新股
    stocks = stocks[(context.current_dt.date() - stocks.start_date) > datetime.timedelta(60)].index
    #stocks  = stocks.index
    date=context.current_dt.strftime("%Y-%m-%d")
    st=get_extras('is_st', stocks, start_date=date, end_date=date, df=True)
    st=st.loc[date]
    stocks = list(st[st==False].index)
    stocks = unpaused(stocks)
    stocks = filterStarName(stocks)
    stocks = ratio_filter(stocks, context)    
    stocks = days_filter(stocks, context)
    stocks = buy_signal(stocks, context)
    
    

    num = len(stocks)
    if  num < 2 :
        return

    q = query(
        valuation.code,
        ).filter(
        #valuation.pe_ratio > 0,
        valuation.code.in_(stocks)
    ).order_by(
        # 按市值升序排列
        valuation.market_cap.asc()
    )
    
    df = get_fundamentals(q)
    stock_list = df.code.values
    stock_list = rank_stocks(data, stock_list)
    log.debug("买入后备选股票: %s" %(stock_list))
    return stock_list

# 股票评分
def rank_stocks(data, stock_list):
    dst_stocks = {}
    count = 0
    log.debug("参加评分的备选股票: %s" %(stock_list))
    for stock in stock_list:
       
        count = count + 1
        cross_days = g.cross_days[stock]
                
        h = attribute_history(stock, 20, unit='1d', fields=('close'), skip_paused=True)
        cross_close = h['close'][-cross_days]
        high_price_20 = h['close'].max()
        prices = attribute_history(stock, cross_days, unit='1d', fields=('close'), skip_paused=True)
        low_price = prices['close'].min()

        for i in range(1,cross_days):
            price = h['close'][-i]
            if price == high_price_20:
                break
        
        ratio_ascend = (high_price_20-cross_close)/cross_close*100/(cross_days-i)
        ratio_descend = (high_price_20-low_price)/high_price_20*100
        #市值打分
        if count <= 9:
            score = count
        else:
            score = 9
        #上升幅度打分
        if ratio_ascend > 4:
            score = score+100
        elif ratio_ascend > 3:
            score = score+200
        elif ratio_ascend > 2:
            score = score+300
        elif ratio_ascend > 1.5:
            score = score+400
        else:
            pass
            
        #下降幅度打分
        if ratio_descend >= 30 and ratio_descend < 40:
            score = score+10
        elif ratio_descend >= 20 and ratio_descend < 30:
            score = score+20
        elif ratio_descend >= 9 and ratio_descend < 20:
            score = score+30
        else:
            score = score + 40
            
        g.score[stock] = score
        dst_stocks[stock] = score
        
    df = pd.DataFrame(dst_stocks.values(), index=dst_stocks.keys())
    df.columns = ['score']
    df = df.sort(columns='score', ascending=True)
    return df.index

# 获取前n个单位时间当时的收盘价
def get_close_price(security, n, unit='1d'):
    return attribute_history(security, n, unit, ('close'), True)['close'][0]


def moving_stop_profit(context,kernel = 1):
    '''run_daily接受的函数只接受context参数，
    所以如要选择何种止盈手段，需要再次修改kernel
    kernel==1 为分级移动止盈
    kernel==2 为移动止盈
    其中具体参数需要针对不同环境、不同交易品种进行设立。
    '''
    if kernel == 1:
        
        # 分级移动止盈
        for stock in list(g.last_high.keys()):
            if g.hold_time[stock] >= 3:
                check_sellable(stock)
                '''
                avg_cost = context.portfolio.positions[stock].avg_cost #获取成本
                high_price = g.last_high[stock]
                profit_level = high_price/avg_cost-1 #收益率
                # 根据盈利设定stopLoss_price
                stopLoss_price = 0
                if profit_level < 0.1:
                    stopLoss_price = high_price*0.5
                elif 0.5 > profit_level > 0.2:
                    stopLoss_price = high_price*0.7
                elif profit_level >= 0.5:
                    stopLoss_price = high_price*0.9
                # 判断
                temp_close2 = attribute_history(stock, 1, '1d','close',df=False)
                close2 = temp_close2['close'][-1]
                if close2 <= stopLoss_price:
                    log.debug("moving_stop_profit 1 卖出股票: %s" %(stock))
                    pop_stock(stock)
                    order_target(stock, 0)
                '''
    elif kernel == 2:
        # 移动止盈
        for stock in list(g.last_high.keys()):
            temp_close2 = attribute_history(stock, 1, '1d','close',df=False)
            if temp_close2['close'][-1] <= g.last_high[stock]*0.8:
                log.debug("moving_stop_profit 2 卖出股票: %s" %(stock))
                order_target(stock, 0)



def check_sellable(stock):
    prices = attribute_history(stock, 5, '1d', 'close', skip_paused = True)    
    last_price = attribute_history(stock, 1, '15m', 'close', skip_paused = True)['close'][0]        
    mean21 =  sum(prices).iloc[0] / 5
    #pre_low = attribute_history(stock, 1, unit='1d', fields=('low'), skip_paused=True)['low'][0]

    cur_price = get_close_price(stock, 1, '1m')
    #是否要添加力度判断来止赢
    if last_price <= mean21*0.99 : #or cur_price < g.cost[stock]*0.95 :#or cur_price < g.last_high[stock]-0.05*g.cost[stock]
        log.debug("check_sellable 卖出股票: %s" %(stock))
        pop_stock(stock)
        order_target_value(stock, 0)

# 开仓，买入指定价值的证券
# 报单成功并成交（包括全部成交或部分成交，此时成交量大于0），返回True
# 报单失败或者报单成功但被取消（此时成交量等于0），返回False
def open_position(security, value):
    order = order_target_value(security, value)
    if order != None and order.filled > 0:
        log.debug("买入股票: %s" %(security))
        log.debug("股票得分: %s" %(g.score[security]))
        # 报单成功并有成交则初始化最高价
        cur_price = get_close_price(security, 1, '1m')
        g.last_high[security] = cur_price
        g.hold_time[security] = 1
        g.cost[security] = cur_price
        return True
    return False

# 根据待买股票创建或调整仓位
# 对于因停牌等原因没有卖出的股票则继续持有
# 始终保持持仓数目为g.buy_stock_count
def adjust_position(context, buy_stocks):
    # 根据股票数量分仓
    # 此处只根据可用金额平均分配购买，不能保证每个仓位平均分配
    position_count = len(context.portfolio.positions)
    buy_count = (g.buy_stock_count-position_count)
    if buy_count >= len(buy_stocks) > 0:
        value = context.portfolio.cash / len(buy_stocks)
    else:
        value = context.portfolio.cash/buy_count
        
    for stock in buy_stocks:
        buy_count = buy_count - 1
        if buy_count >= 0:
            open_position(stock, value)



    
def buy_stocks(context, data):

    buylist = Multi_Select_Stocks(context, data)
    
    if buylist is None:
        return
    
    stocks = []
    #获取当日股票开盘价、涨跌停价
    current_data = get_current_data()
    for stock in buylist:
        #上一分钟的价格
        cur_price = get_close_price(stock, 1, '1m')
        #昨日收盘价
        pre_price = attribute_history(stock, 1, unit='1d', fields=('close'), skip_paused=True)['close'][0]
        #今日开盘价
        c_open= current_data[stock].day_open
        #今日涨停价
        c_hlimit = current_data[stock].high_limit
        
        #昨日ma5
        prices = attribute_history(stock, 5, '1d', 'close', skip_paused = True)        
        mean5 =  sum(prices).iloc[0] / 5
        #涨幅限制条件
        pre_limit = pre_price*1.01
        
        if cur_price > pre_limit and cur_price > mean5 and c_hlimit > cur_price > c_open :
            stocks.append(stock)
    log.info("选股后可买股票: %s" %(stocks))
    adjust_position(context, stocks)

    
# 平仓，卖出指定持仓
# 平仓成功并全部成交，返回True
# 报单失败或者报单成功但被取消（此时成交量等于0），或者报单非全部成交，返回False
def close_position(position):
    security = position.security
    log.debug("close_position 卖出股票: %s" %(stock))
    order = order_target_value_(security, 0) # 可能会因停牌失败
    if order != None:
        if order.filled > 0:
            # 只要有成交，无论全部成交还是部分成交，则统计盈亏
            g.trade_stat.watch(security, order.filled, position.avg_cost, position.price)

        if order.status == OrderStatus.held and order.filled == order.amount:
            # 全部成交则删除相关证券的最高价缓存
            g.last_high.pop(security)
            return True

    return False    
# 个股止损
def stock_stop_loss(context, data):
    for stock in context.portfolio.positions.keys():
        cur_price = get_close_price(stock, 1, '1m')
        if g.last_high[stock] < cur_price:
            g.last_high[stock] = cur_price
            
    moving_stop_profit(context)

    
# 每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)调用一次
def handle_data(context, data):
    
    stock_stop_loss(context, data)
        
    '''
    if amount > 0:
        #log.debug("持仓股票: %s" %(stocks))
        check_sellable_stock(context, data)
    '''
    hour = context.current_dt.hour
    minute = context.current_dt.minute
    
    if hour == 9 and minute == 31:
        for stock in context.portfolio.positions.keys():
            g.hold_time[stock] = g.hold_time[stock] + 1
    
    # 每天下午14:53调仓
    if hour ==10 and minute==10:
        buy_stocks(context, data)
