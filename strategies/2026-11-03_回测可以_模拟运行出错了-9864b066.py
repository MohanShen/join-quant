# Clone from JoinQuant
# postId: 9864b06644dc1c5f1f4dc269fa4b3de8
# backtestId: 66eb67ae3df4bb9d40989b4576706dae
# title: 回测可以，模拟运行出错了

# 克隆自聚宽文章：https://www.joinquant.com/post/1097
# 标题：基于凸组合优化的均线交叉策略
# 作者：Alphamon

import talib
import math
import numpy as np
import pandas as pd

#------------------------------------------
def initialize(context):
    log.set_level('order','error')
    # 定义一个全局变量, 保存要操作的证券
    g.index = '000001.XSHG'#
    g.stocks = ['600196.XSHG']
    
    # 设定全局参数--90-3-301-3-14最好---
    '''
    160601-170829:
    369%: 90-1-301-45-3-29
    363%: 90-1-301-30-3-15
    347%: 90-1-301-35-3-15
    329%: 90-1-301-40-3-15
    326%: 90-1-301-25-3-5
    322%: 90-1-301-25-3-15
    '''
    #-----------------------------
    #涨幅参数
    g.zhangfu_days = 90 #原基准日期#120#30#  #不能用40#60#
    g.zhangfu_topK = 1#2#3 # 原只操作topK只股票#4#5#10#2#
    #主要方式300（原来用）
    g.selectStockMethod = 3 #原选股方法参数 0#2#1#  (可选：0,1,2,3)
    g.closePositionMethod = 0 # 清仓方式参数(可选：0,1)
    g.stopLossMethod =1 #0#2#  止损方式参数(可选：0,1,2)
                        #---（选股方法3）---止损0最好1其次2最次

    g.refreshSign = 0 # 持仓条件更新参数

    #-----------------------------
    #成交量参数
    g.duanqi=3#5#原参数#2#
    g.changqi=45#30#原参数#
    #-----------------------------
    #流通市值分位数参数
    g.ltmarketcap_fenweishu = '25%'#原分位数(默认-50-对应此数字)#'30%'#
    #-----------------------------
    #均线止损参数
    g.jxdays = 29#14
    
    
    # 按周期选股
    #run_monthly(mainSelectStocks, 1, time='before_open') #160601-170706回测收益220%-最好
    #run_weekly(mainSelectStocks, 1, time='before_open') #160601-170706回测收益108%-第三
    run_daily(mainSelectStocks, time='before_open') #160601-170706回测收益190%-好
    #run_daily(mainSelectStocks, time='after_close') #160601-170706回测收益190%-好

#------------------------------------------
#def after_trading_end(context):
#    print(mainSelectStocks(context))

#------------------------------------------
def before_trading_start(context):
    #mainSelectStocks(context)
    g.yiyunxing=0

#------------------------------------------
# 每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)调用一次
def handle_data(context, data):
    # 获得当前时间
    hour = context.current_dt.hour
    minute = context.current_dt.minute
    
    # 每天下午14:56调仓
    if not (hour == 9 and minute == 30):
        return
    if g.yiyunxing == 1: return

    g.yiyunxing = 1
    # 买卖股票
    mainHandle(context,data,g.closePositionMethod)
    
#------------------------------------------
# 基础选股---取观察日内涨幅前topK的股票---根据涨幅筛选股票
def filtGain(stocks,pastDay):
    # 初始化参数信息
    numStocks = len(stocks)
    rankValue = []

    # 计算涨跌幅
    for security in stocks:
        # 获取过去pastDay的指数值
        stocksPrice = history(pastDay, '1d', 'close', [security])
        if len(stocksPrice)!=0:
            # 计算涨跌幅
            errCloseOpen = [(float(stocksPrice.iloc[-1]) - float(stocksPrice.iloc[0])) / float(stocksPrice.iloc[0])]
            rankValue += errCloseOpen
        else:
            rankValue += [0]

    # 根据周涨跌幅排名
    filtStocks = {'code':stocks,'rankValue':rankValue}
    filtStocks = pd.DataFrame(filtStocks)
    filtStocks = filtStocks.sort('rankValue',ascending = False)
    #print(filtStocks)
    print(filtStocks[:10])
    # 根据涨跌幅筛选
    filtStocks = filtStocks.head(g.zhangfu_topK)
    filtStocks = list(filtStocks['code'])
    tuzuhe3='凸'+'90'+'前三:'+str(filtStocks)
    print(tuzuhe3)
    send_message(tuzuhe3, channel='weixin')

    return filtStocks

#------------------------------------------
# 根据成交量筛选股票---短期成交量均值大于长期成交量均值----
def filtVol(stocks):
    # 初始化返回数组
    returnStocks = []
    #print('成交量过滤')
    # 筛选
    for security in stocks:
        stockVol = history(g.changqi+1, '1d', 'volume', [security])
        if float(mean(stockVol.iloc[-g.duanqi:])) > float(mean(stockVol.iloc[-g.changqi:])):
            returnStocks += [security]
        else:
            continue
    return returnStocks

#------------------------------------------
# 根据流通市值筛选股票----
def filtMarketCap(context,stocks,index):
    # 初始化返回数组
    returnStocks = []

    # 计算指数的总流通市值
    oriStocks = get_index_stocks(index)
    indexMarketCap = get_fundamentals(query(valuation.circulating_market_cap).filter(valuation.code.in_(oriStocks)), date = context.current_dt)
    totalMarketCap = float(sum(indexMarketCap['circulating_market_cap']))
    
    # 计算个股流通市值占总市值百分比阈值：以四分位为阈值
    indexMarketCap = indexMarketCap.div(totalMarketCap,axis=0)
    #porThre = indexMarketCap.describe(40)#40--30%--; 50(默认)---25%--
    #print('porThre0:',porThre)
    porThre = indexMarketCap.describe()
    #print('porThre1:',porThre)
    porThre = float(porThre.loc[g.ltmarketcap_fenweishu])
    #print('porThre2:',porThre)

    # 筛选
    for security in stocks:
        stockMarketCap = get_fundamentals(query(valuation.circulating_market_cap).filter(valuation.code.in_([security])), date = context.current_dt)
        if float(stockMarketCap.iloc[0]) > totalMarketCap * porThre:
            #print('total:',totalMarketCap,'gaigu:',float(stockMarketCap.iloc[0]),'zhanbi:',float(stockMarketCap.iloc[0])/totalMarketCap,'porThre:',porThre)
            returnStocks += [security]
        else:
            continue
    return returnStocks
    
#------------------------------------------
# 寻找指数的龙头股
def findLeadStock(context,index,pastDay,method = 0):
    # 初始化参数
    topK = g.zhangfu_topK
    # 规则
    # 1.涨幅大于阈值的topK只股票；
    # 3.过去一周成交量大于过去两周成交量；
    # 4.个股流通市值占总市值百分比达到阈值
    # 取出该指数的股票:
    oriStocks = get_index_stocks(index)        
    # 过滤次新st等
    oriStocks=filter_st_300_cixin(context, oriStocks)
    # 根据个股涨幅筛选
    filtStocks = filtGain(oriStocks,pastDay)
    
    # 根据规则筛选绩优股
    if method == 0:
        # 基本限制
        return filtStocks
    elif method == 1:
        # 基本限制+成交量限制
        filtStocks = filtVol(filtStocks)
        return filtStocks
    elif method == 2:
        # 基本限制+流通市值限制
        filtStocks = filtMarketCap(context,filtStocks,index)
        return filtStocks
    elif method == 3:
        # 基本限制+流通市值限制+成交量限制
        filtStocks = filtVol(filtStocks)
        if len(filtStocks) != 0:
            filtStocks = filtMarketCap(context,filtStocks,index)
        else:
            pass
        return filtStocks
    else:
        return 'Error method order'
    
#------------------------------------------
# 按周期选股
def mainSelectStocks(context):
    index = g.index
    pastDay = g.zhangfu_days
    topK = g.zhangfu_topK
    #------------------------
    # 获取候选股票池
    stocks = findLeadStock(context,index,pastDay,method = g.selectStockMethod)
    tuzuhe3='合:'+str(stocks)
    print(tuzuhe3)
    send_message(tuzuhe3, channel='weixin')
#------------------------
    # 重置参数
    g.stocks = stocks
    #------------------------
    #返回候选股票
    return stocks
    
    
#------------------------------------------
# 止损---均线筛股
def stopLoss(security,method = 0):
    stocksPrice = history(g.jxdays,'1d','avg',[security])
    if method == 0:
        errPrice = float((stocksPrice.iloc[-1] - stocksPrice.iloc[0])/stocksPrice.iloc[0])
        if errPrice < 0.02:
            return True
        else:
            return False
    elif method == 1:
        stocksPrice = list(stocksPrice[security])
        gainSign = [1 for i in range(1,len(stocksPrice)) if (stocksPrice[i] - stocksPrice[i-1])/stocksPrice[i] > 0]
        if float(len(gainSign))/float(len(stocksPrice)) > 0.5:
            return False
        else:
            return True
    elif method == 2:
        return False
    else:
        return 'Error method order'
    
#------------------------------------------
# 买卖股票函数
def mainHandle(context,data,method = 0):
    # 获取全局参数值
    pastDay = g.zhangfu_days
    stocks = g.stocks
    
    # 买卖操作
    if len(stocks) != 0:
        # 等权分配资金
        cash = context.portfolio.cash
        cash = cash/len(stocks)
        for i,security in enumerate(stocks):
            # 获取股票基本信息：是否停牌、是否ST,持股头寸、股价等
            currentData = get_current_data()
            pauseSign = currentData[security].paused
            STInfo = get_extras('is_st',security,start_date = context.current_dt, end_date=context.current_dt)
            STSign = STInfo.iloc[-1]
            if not pauseSign and not STSign.bool():
                stockPrice = history(pastDay, '1d', 'close', [security])
                if not math.isnan(stockPrice[security][0]): 
                    # 计算KDJ 
                    macd, signal, hist = talib.MACD(stockPrice[security].values, 
                                        fastperiod = 5, 
                                        slowperiod = 30, 
                                        signalperiod = 5)
                                        
                    macdSign = macd[-1] - signal[-1]
    
                    # 获取持仓成本
                    avgCost = context.portfolio.positions[security].avg_cost
                    price = context.portfolio.positions[security].price
        
                    # 判断&交易
                    if macdSign > 0:
                        # 金叉信号
                        if method == 0:
                            # 根据持仓成本更新标记符更新持仓成本
                            if g.refreshSign == 1:
                                #context.portfolio.positions[security].avg_cost = price
                                g.refreshSign = 0
                                continue
                            else:
                                pass
                            # 判断凸组合条件
                            if price >= avgCost and stopLoss(security,g.stopLossMethod) == False:
                                order(security,int(cash/data[security].avg))
                                # order_target_value(security,cash)
                                print("Buying %s" % (security))
                            else:
                                order_target(security, 0)
                                print("Selling %s" % (security))
                        elif method == 1:
                            order(security,int(cash/data[security].avg))
                            # order_target_value(security,cash)
                            print("Buying %s" % (security))
                        else:
                            print("Error method order")
        
                    elif macdSign < 0 and context.portfolio.positions[security].sellable_amount > 0:
                        # 死叉信号
                        if method == 0:
                            if price >= avgCost and stopLoss(security,g.stopLossMethod) == False:
                                # 更新持仓成本标记符
                                g.refreshSign = 1
                            else:
                                order_target(security, 0)
                                print("Selling %s" % (security))
                        elif method == 1:
                            order_target(security, 0)
                            print("Selling %s" % (security))
                        else:
                            print("Error method order")
        
                    else:
                        continue
                else:
                    continue
            else:
                continue
    else:
        for security in context.portfolio.positions.keys():
            order_target(security,0)
            print("Selling %s" %(security))

#---过滤 st,创业板,次新-------------------------- and (1-is_suspended(s))
def filter_st_300_cixin(context, stocklist_chushi):
    current_data = get_current_data()
    MY_EXCLUDE_STOCKS = ["000638.XSHE","600213.XSHG",'000033.XSHE']
    stocks_list = [s for s in stocklist_chushi if ('ST' not in current_data[s].
        name and '*' not in current_data[s].name and '退' not in current_data[s].name) 
        and (s[0] != '3') and  ((context.current_dt.date() - get_security_info(s).start_date).days>180) and (s not in MY_EXCLUDE_STOCKS)]
    return stocks_list

