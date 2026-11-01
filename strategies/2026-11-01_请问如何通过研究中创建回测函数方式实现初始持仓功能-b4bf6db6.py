# Clone from JoinQuant
# postId: b4bf6db6239cd8db4899096c66bec3d7
# backtestId: d72e1888f2b0f75e864d23355e5d813a
# title: 请问如何通过研究中创建回测函数方式实现初始持仓功能

# 阈值为2%
# 当两股的股价比值超出价值中枢2%(阈值)时，执行卖出估价高的（security_high），买入股价低的（security_low）
# 当两股的股价比值低于价值中枢2%(阈值)时，执行买入估价高的（security_high），卖出股价低的（security_low）  
import scipy.stats as stats
import numpy as np
import pandas as pd
from pandas import DataFrame,Series
import statsmodels
from statsmodels.tsa.stattools import coint
from datetime import timedelta
# 第一步：设置基本参数
#设置检验协整关系的时间跨度
delta= timedelta(days=100)
#用一个列表来保存每个时间段内协整性最强的股票对
security=[]
#设置隔多长时间更新需要操作的股票对
T=30
#设置一个全局变量，记录策略运行了多少天
g.count=0
freq = 'daily'
threadhold = 0.02 # 阈值
#止损参数
stoploss=0.9
stock_amount = 1000
stock_high_amount = 500
stock_low_amount = 1500
#定义计算协整关系的函数
def Find_cointegrated_pairs(securities_panel):
    n = len(securities_panel.minor_axis)
    #原假设是股票间不存在协整关系，如果Pvalue<0.05则拒绝原假设
    pvalue_matrix = np.ones((n, n))  #定义出一个n*n的p值矩阵
    keys = securities_panel.keys #keys是股票代码
    #循环，计算两两股票间的协整关系，并将结果保存在矩阵中
    for i in range(n):
        for j in range(i+1,n):
            S1 = securities_panel.minor_xs(securities_panel.minor_axis[i])
            S2 = securities_panel.minor_xs(securities_panel.minor_axis[j])
            result = coint(S1, S2)
            #score用来判断股价是否是非平稳的，代表对股价进行单位根检定的t统计量
            score = abs(result[0]) #z score
            pvalue = result[1] #p值
            if score>3:
                pvalue_matrix[i, j] = pvalue
            else:
                pvalue_matrix[i, j] = 1 #Z score比较小的 p值一律定义为1
    return  pvalue_matrix  

#寻找协整性最强的股票
def Find_security(start,end):
    #取得沪深300股票列表
    #symbol= get_index_stocks('000300.XSHG')
    symbol=['600010.XSHG',
            '600019.XSHG',
            '000709.XSHE',
            '600005.XSHG',
            '600022.XSHG',
            '000898.XSHE',
            '600808.XSHG',
            '600307.XSHG',
            '000825.XSHE',
            '000959.XSHE']
    
    symbol_list=[]
    for i in range(0,len(symbol)):
        symbol_list.append(symbol[i])
    #取出沪深300股票的价格
    securities_panel = get_price(symbol_list,start_date=start,end_date=end,frequency=freq,fields=['close'])
    #取得pvalue矩阵
    pvalues = Find_cointegrated_pairs(securities_panel)
    #找出矩阵pvalue的对角线以上的部分最小值得坐标
    #由于对称关系，只需找对角线以上的就足够了
    index=(0,0)
    m=1
    num=len(symbol)
    for i in range(0,num):
        for j in range(i+1,num): 
            if pvalues[i,j]<m:
                index=(i,j)
                m=pvalues[i,j]
    #找出坐标后，根据坐标设置需要操作的两只股票
    security_high=symbol[index[0]]
    security_low=symbol[index[1]]
    return security_high,security_low

# 初始化函数，设定要操作的股票、基准等等
def initialize(context):
    initial_positions = [
        {
            'security':'600010.XSHG',
            'amount':'1000',
        },
        {
            'security':'600019.XSHG',
            'amount':'1000',
        },
        {
            'security':'000709.XSHE',
            'amount':'1000',
        },
        {
            'security':'600005.XSHG',
            'amount':'1000',
        },
        {
            'security':'600022.XSHG',
            'amount':'1000',
        },
        {
            'security':'000898.XSHE',
            'amount':'1000',
        },
        {
            'security':'600808.XSHG',
            'amount':'1000',
        },
        {
            'security':'600307.XSHG',
            'amount':'1000',
        },
        {
            'security':'000825.XSHE',
            'amount':'1000',
        },
        {
            'security':'000959.XSHE',
            'amount':'1000',
        },
    ]
   
 

# 每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)调用一次
def handle_data(context, data):

    if g.count==T: #T=30 ,当触及30天，即重新计算最佳协整对
        g.count=0
    if g.count==0:
        dt=context.current_dt  #当前时点
        start=dt-2*delta #delta为协整时间跨度
        end=dt-delta
        security_A,security_B=Find_security(start,end)
        security.append(security_A) #最佳协整对插到security的最后面，调取用-1、-2
        security.append(security_B)
       
        # 第二步：设置股票池
        set_universe(security)
        #取出两只股票的价格
        hist_high = get_price(security_A,start_date=start, end_date=end, frequency=freq, fields=None)['close']
        hist_low = get_price(security_B,start_date=start, end_date=end, frequency=freq, fields=None)['close']
            
        # 计算价值中枢（回测时间内股价比值的均值）
        g.mean = np.mean(hist_high.values/hist_low.values)
        g.std = np.std(hist_high.values/hist_low.values)
    g.count=g.count+1
    
    stop=0 #止损股票
    print security
    #for stock in context.portfolio.positions:
        #p=context.portfolio.positions[stock]
        #if p.price/p.avg_cost<=stoploss: #现价/买入成本 < 0.9 则止损
            #order_target(stock,0)
            #stop=stop+1
    security_high=security[-2]
    security_low=security[-1]
        #判断有无买卖操作
    if  context.portfolio.positions[security_high].closeable_amount!= stock_amount:
        stop = stop + 1
    if  context.portfolio.positions[security_low].closeable_amount!= stock_amount:
        stop = stop + 1
       #如果没有买卖操作     
    if stop<2:

        position=context.portfolio.positions #position:持仓量，头寸
        price_high = data[security_high].close
        price_low = data[security_low].close
        #log.info("price_Low:%f"%(price_low))
        #绘制 价值中枢直线
        record(mean=g.mean)
        #绘制 股价比值曲线
        record(price_ration = data[security_high].close / data[security_low].close)
        
        #如果已经持有股票头寸了，判断以前持有的股票与当前协整性最强的股票是否有重合，
        #如果不重合，则清空原来的头寸
        print security
        if len(security)>2:
            if security[-3]!=security_high and security[-3]!=security_low: #！=不等于
                order_target(security[-3], stock_amount)
            if security[-4]!=security_high and security[-4]!=security_low:
                order_target(security[-4], stock_amount)
        
        #两只股票的股价比值
        price_ration = price_high / price_low
        
        #当两股的股价比值超出价值中枢2%(阈值)时，执行卖出估价高的（security_high），买入股价低的（security_low)
        if price_ration > (1+threadhold)*g.mean:
            #卖出股价高的（security_high）买入股价低的（security_low）
            #卖出股价高的
            if context.portfolio.positions[security_high].closeable_amount == stock_amount:
                # 记录这次卖出
                log.info("Selling %s at price %s" % (security_high, price_high))
                # 全部卖出股价高的
                order_target(security_high, stock_high_amount)
                
            cash = context.portfolio.cash
            #买入股价低的
            if cash > price_low * (stock_low_amount-1000) :
                # 得到能够购买的股数
                #number_of_shares = int(cash/price_low)
                # 记录这次买入
                log.info("Buying %s at price %s" % (security_low, price_low))
                # 下买入单
                order_target(security_low, stock_low_amount)
                    
        #当两股的股价比值低于价值中枢2%(阈值)时，执行卖出估价低的（security_low），买入股价高的（security_high） 
        elif price_ration < (1-threadhold)*g.mean:
            #卖出股价低的（security_low）买入股价高的（security_high）
            #卖出股价低的
            if context.portfolio.positions[security_low].closeable_amount == stock_low_amount: #if中不允许赋值，==表示相等，=表示赋值
                # 记录这次卖出
                log.info("Selling %s at price %s" % (security_low, price_low))
                # 全部卖出股价低的
                order_target(security_low, stock_amount)
                
            #买入股价高的
            if context.portfolio.positions[security_high].closeable_amount == stock_high_amount:
                # 记录这次买入
                log.info("buying %s at price %s" % (security_high, price_high))
                # 全部买出股价高的
                order_target(security_high, stock_amount)
                
            
            
            #cash = context.portfolio.cash
            #if cash > price_high*100:
                # 记录这次买入
                #log.info("Buying %s at price %s" % ( security_high, price_high))
                # 下买入单
                #order_value(security_high, cash)