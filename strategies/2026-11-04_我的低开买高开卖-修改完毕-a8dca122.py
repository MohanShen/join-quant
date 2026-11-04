# Clone from JoinQuant
# postId: a8dca122bf3d0a9e49b30fd610a0d6ed
# backtestId: 091b8d09a3cf260f7a9ea7888555f7e3
# title: 我的低开买高开卖-修改完毕

'''
==========================================================================================
买卖策略
------------------------------------------------------------------------------------------
买入：
9:20 准备候选股票，按市值【升序】排列，选前300支，剔除掉ST和停牌的股票，清洗干净后放入“候选池”。
9:40 "候选池"中股票若能同时满足以下3个条件： 
    1)低开(今天开盘价格低于昨天的最低价)
    2)且昨天没有触及跌停
    3)今天不是跌停开盘
    则放入”目标池“中，目标股票7支。等卖出股票，倒出仓位后，买入“目标池”中的股票。
------------------------------------------------------------------------------------------
卖出：
情形1：止盈卖出。回撤10%，止盈。
情形2：止损卖出。亏损10%，止损。
情形3：非候卖出。不在今天“候选池”中的股票，卖出。
情形4：高开卖出。若同时满足3个条件则卖出1）今天开盘价超过了昨天的最高价；
                                        2）昨天没有触及涨停；
                                        3）今天不是涨停开盘。
情形5：危险卖出。若快跌停了（再下跌2%就要跌停了），卖出。为忠实原作者的思想，第5种情形注释掉了。
==========================================================================================
流程
------------------------------------------------------------------------------------------
卖出流程：
频率：分钟。 每1分钟记录一次持仓股票的股价峰值，用于止盈。
频率：5分钟。每5分钟检查是否符合情形1、2、5（止盈、止损、危险），如果是则卖出。
频率：每天。9:40,卖出符合情形3、4的股票。
------------------------------------------------------------------------------------------
买入流程：
频率：每天。9:40,执行完卖出流程后，若有仓位空出，则按顺序买入“目标池”中的股票，持仓达到7支股票为止。
==========================================================================================
'''

# 初始化函数，设定要操作的股票、基准等等
def initialize(context):
    # 使用真实价格回测
    set_option('use_real_price', True)
    # 交易成本
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003, 
        close_today_commission=0, min_commission=5), type='stock')
    # 设定滑点为固定值:1分钱
    set_slippage(FixedSlippage(0.01))
    #设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 清洗干净的小市值股票,候选池
    g.candidateStocks=[]
    # 准备买入的股票池
    g.ready2buys = []
    # 记录当天买入的股票, 避免T+1不能卖出，却不断尝试止损
    g.todayBuys = []
    # 持仓股票股价峰值，用于回撤止盈
    g.stockMaxPrice = {}
    
    # 市值升序初选股票支数
    g.init_stock_num = 300
    # 计划持仓股票支数
    g.buy_stock_count = 7
    # 止损线,止盈线
    g.stopLossline = 10      # 代表10%，止损
    g.stopProfitline = 10   # 代表10%，止盈
    
# 9:20 准备小市值升序、非ST、非停牌的股票，放入“候选池”g.candidateStocks
def before_trading_start(context):
    log.info('----------------------------------------------')
    g.candidateStocks=candidate_stocks(context)  #取候选股票
    g.ready2buys = []   # 重置“目标池”股票

# 每日收盘后
# 清理不在仓位中的股价峰值记录
def after_trading_end(context):
    holdings=context.portfolio.positions.keys()
    for stock in g.stockMaxPrice.keys():
        if stock not in holdings:
            g.stockMaxPrice.pop(stock)  #剔除已不再持仓的股价峰值记录
    g.todayBuys = []    # 重置: 今天买入的股票列表
    
# 按分钟回测
def handle_data(context, data):
    # 每1分钟记录股票价格峰值
    for stock in context.portfolio.positions.keys():
        if data[stock].high > g.stockMaxPrice.get(stock,0):
            g.stockMaxPrice[stock] = data[stock].high
            
    # 每5分钟检查一次：1）回撤超10%，则止盈；2）亏损达10%，则止损；5）距跌停价仅2%，则出逃
    if context.current_dt.minute%5 == 0:
        stopLossPro(context, data)
    
    # 9：40 卖出股票：3）非候；4）高开
    #       再买入”目标池“内的股票    
    if context.current_dt.hour ==9 and context.current_dt.minute == 40:
        # 准备股票“目标池”
        g.ready2buys = getReady2buys(context, data)
        # 卖出持仓中第3、4类股票
        sellDontWants(context, data)
        # 买入目标股票
        buyIWants(context, data)

# 买入“目标池”内的股票
def buyIWants(context, data):
    for stock in g.ready2buys:
        position_count = len(context.portfolio.positions)
        if position_count < g.buy_stock_count:  # 还有仓位
            if context.portfolio.positions[stock].total_amount == 0:    # 原持仓中没有这一支
                value = context.portfolio.cash / (g.buy_stock_count - position_count)
                log.info("买入: %s" %(stock))
                g.todayBuys.append(stock)   #记录今天买入的股票
                order_target_value(stock, value) #买入
        else: #没有仓位，买够了
            break

# 止盈止损程序：第1，2, 5类卖出 
def stopLossPro(context, data):
    for stock in context.portfolio.positions.keys():
        myPosition = context.portfolio.positions[stock]
        nowPrice = myPosition.price     # 现价
        current_data = get_current_data()
        # 能止损的：非(当天买入的股票，停牌的，跌停的)
        if not((stock in g.todayBuys) or current_data[stock].paused or (nowPrice == current_data[stock].low_limit)):
            # 1)回撤10%止盈
            peakPrice = g.stockMaxPrice.get(stock,0)    #峰值
            if nowPrice < peakPrice*(1-g.stopProfitline/100.0):  #回落10%  （100.0 而不是100，避免整除问题）
                log.info("止盈卖出: %s, 峰值: %.2f, 现价: %.2f" % (stock, peakPrice, nowPrice))
                order_target_value(stock, 0)   # 卖出1
                continue
            
            # 2)亏损10%止损
            avgCost = myPosition.avg_cost   #持仓成本
            if nowPrice < avgCost*(1-g.stopLossline/100.0):   #亏损10%
                log.info("止损卖出: %s, 成本: %.2f, 现价: %.2f" %(stock, avgCost, nowPrice))
                order_target_value(stock, 0)   # 卖出2
                continue
            
            '''
            # 5)距离跌停价2%，危险，出逃
            lowLimit = current_data[stock].low_limit
            if nowPrice < (1.02 * lowLimit):
                log.info("巨跌卖出: %s, 跌停价: %.2f, 现价: %.2f" %(stock, lowLimit, nowPrice))
                order_target_value(stock, 0)   # 卖出5
                continue
            '''
    return

# 卖出不要的股票：第3，4类卖出
def sellDontWants(context, data):
    # 3）非候选:不在买入目标股票池内; 4)高开:今日开盘价>昨最高价 & 昨天未涨停 & 今天不是涨停开盘的
    # 这是开盘后就可以确定的两类卖出，故9:40处理
    current_data = get_current_data()
    for stock in context.portfolio.positions.keys():
        # 3) 非候
        if stock not in g.candidateStocks:
            # 不是“候选池”中的
            log.info("非候选，卖出: %s" %(stock))
            order_target_value(stock, 0)   # 卖出3
            continue

        # 4) 高开
        h = attribute_history(security=stock, count=1, unit='1d', fields=('high', 'high_limit'))
        mOpenToday = current_data[stock].day_open
        mHighlimitToday = current_data[stock].high_limit
        # 今日开盘价>昨最高价 & 昨天未触及涨停 & 今天不是涨停开盘
        if mOpenToday>=h.high[0] and h.high[0] < h.high_limit[0] and mOpenToday<mHighlimitToday:
            log.info("高开卖出: %s, 今开: %.2f, 昨高: %.2f, 昨涨停价: %.2f, 今涨停价: %.2f" % 
                (stock, mOpenToday, h.high[0], h.high_limit[0], mHighlimitToday))
            order_target_value(stock, 0)   # 卖出4
            continue
        
# 准备买入的股票池        
def getReady2buys(context, data):
    dst_Stocks = []
    current_data = get_current_data()
    for stock in g.candidateStocks:
        mOpenToday = current_data[stock].day_open
        mLowlimitToday = current_data[stock].low_limit
        h = attribute_history(security=stock, count=1, unit='1d', fields=('low', 'low_limit'))
        # 买入条件: 1)低开(今天开盘价格低于昨天的最低价),2）且昨天没有触及跌停，3）今天不是跌停开盘
        if mOpenToday<=h.low[0] and h.low[0]>h.low_limit[0] and mOpenToday>mLowlimitToday:
            log.info('目标股票:%s, 今开:%.2f, 昨低:%.2f, 昨跌停价:%.2f, 今跌停价:%.2f' % 
                (stock, mOpenToday,h.low[0],h.low_limit[0],mLowlimitToday))
            dst_Stocks.append(stock)    #纳入“目标池”的
            if len(dst_Stocks)>=g.buy_stock_count:   #达到计划持仓股票支数
                break
    log.info('选入股票:%s' % (dst_Stocks))
    return dst_Stocks
    
# 小市值升序300支(g.init_stock_num)，滤掉st，停牌   
def candidate_stocks(context):
    q = query(valuation.code
            ).order_by(
                valuation.market_cap.asc()
            ).limit(
                g.init_stock_num
            ) #初步筛选300支
    df = get_fundamentals(q)
    stock_list = list(df['code'])
    # 滤去
    stock_list = filter_special_stocks(context, stock_list)
    log.info('候选的股票支数:%d' % len(stock_list)) 
    return stock_list

# 过滤ST,停牌
def filter_special_stocks(context, stock_list):
    cur_data = get_current_data()
    # 非停牌、非ST
    stock_list = [stock for stock in stock_list if 
                  (not cur_data[stock].paused) and 
                  (not cur_data[stock].is_st) and 
                  ('ST' not in cur_data[stock].name) and 
                  ('*' not in cur_data[stock].name) and 
                  ('退' not in cur_data[stock].name)]
    
    return stock_list

    