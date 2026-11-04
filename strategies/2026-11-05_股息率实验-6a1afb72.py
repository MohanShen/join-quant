# Clone from JoinQuant
# postId: 6a1afb7235a05f76846c4d6ee3a192eb
# backtestId: a4fd899fc4f6406e71970af91f95ab6b
# title: 股息率实验

##20170831，部分内容说明见高股息率策略
from jqdata import gta  #import输入
import numpy as np  #numpy 标准库
import pandas as pd  #pandas 标准库
import datetime
import time

##初始化方法，在整个回测、模拟实盘中最开始执行一次，用于初始一些全局变量
def initialize(context):
    
    ## 设置参数
    set_benchmark('000300.XSHG')
    run_monthly(Transfer, 1) 
    # 按月回测，每月第一个交易日;Transfer传递,后面自定义的函数，本例是每天交易
    
    ## 设置中间变量
    g.size_start = 1 #股息率从小到大排列，从g.size_start开始
    g.size_end=10 #股息率从小到大排列，一直排列到g.size_end开始
    #综合比较，10支较为合适
    #g.months = [5,9] #交易运行的月份
    g.months = [1,2,3,4,5,6,7,8,9,10,11,12] #交易运行的月份***最终选择***
    g.stocks=[] #stocks 股票
    g.div=3.5    #20170101-20170901，29.92%(回撤6.35%);27.08%(回撤6.35%);23.65%(回撤4.19%)
    #20110501-20170901 每月调，g.div=2.5->182.15%；g.div=3->203.04%；g.div=3.5->217.74%，[5，9]222.14%
    #20110501-20150101 每月调，g.div=2.5->60.32%；g.div=3->65.89%；g.div=3.5->81.33%，[5，9]85.61%
    #20110501-20140501 每月调，g.div=2.5->-2.27%；g.div=3->1.41%；g.div=3.5->10.53%，[5，9]15.39%
    #综合考虑，尤其是考虑2011-2014年情况，选g.div=3.5,每月调，按股息加权，不够10支保留相应现金。
    
    
    #连续5年分红,连续6,7,8,9,10年R>15%,
    g.security2010 = ['601699.XSHG','601666.XSHG','601166.XSHG','600997.XSHG','600970.XSHG','600519.XSHG','600508.XSHG','600348.XSHG','600309.XSHG','600276.XSHG','600150.XSHG','600123.XSHG','600067.XSHG','600066.XSHG','600048.XSHG','600036.XSHG','600000.XSHG','002081.XSHE','002065.XSHE','002022.XSHE','000983.XSHE','000937.XSHE','000933.XSHE','000895.XSHE','000869.XSHE','000726.XSHE','000550.XSHE','000538.XSHE','000069.XSHE','000022.XSHE']
    g.security2011 = ['601939.XSHG','601899.XSHG','601699.XSHG','601666.XSHG','601169.XSHG','601166.XSHG','601088.XSHG','600970.XSHG','600845.XSHG','600582.XSHG','600519.XSHG','600508.XSHG','600348.XSHG','600309.XSHG','600276.XSHG','600123.XSHG','600067.XSHG','600066.XSHG','600048.XSHG','600036.XSHG','600016.XSHG','600000.XSHG','002204.XSHE','002142.XSHE','002128.XSHE','002081.XSHE','002065.XSHE','002024.XSHE','002022.XSHE','000983.XSHE','000937.XSHE','000869.XSHE','000726.XSHE','000651.XSHE','000550.XSHE','000538.XSHE','000069.XSHE','000022.XSHE']
    g.security2012 = ['600519.XSHG','002236.XSHE','000651.XSHE','000869.XSHE','600309.XSHG','002081.XSHE','600066.XSHG','002128.XSHE','600582.XSHG','601166.XSHG','600016.XSHG','000538.XSHE','002022.XSHE','600036.XSHG','600067.XSHG','002252.XSHE','002244.XSHE','600276.XSHG','002065.XSHE','601939.XSHG','600048.XSHG','000069.XSHE','600123.XSHG','600000.XSHG','002142.XSHE','601088.XSHG','601899.XSHG','000550.XSHE','600845.XSHG','002250.XSHE','600348.XSHG','601169.XSHG','002242.XSHE','601699.XSHG','000937.XSHE','600970.XSHG']
    g.security2013 = ['600519.XSHG','000651.XSHE','002236.XSHE','600309.XSHG','002081.XSHE','600067.XSHG','000538.XSHE','002022.XSHE','600066.XSHG','002065.XSHE','600016.XSHG','600036.XSHG','600048.XSHG','002063.XSHE','601166.XSHG','600000.XSHG','002244.XSHE','601939.XSHG','600276.XSHG','002142.XSHE','000069.XSHE','000550.XSHE','600582.XSHG','600845.XSHG','002250.XSHE','601169.XSHG','601088.XSHG','000869.XSHE','002242.XSHE']
    g.security2014 = ['000651.XSHE','600519.XSHG','002081.XSHE','600066.XSHG','000538.XSHE','002022.XSHE','002236.XSHE','600309.XSHG','600048.XSHG','600276.XSHG','601166.XSHG','000550.XSHE','600000.XSHG','002065.XSHE','600016.XSHG','601939.XSHG','002142.XSHE','600036.XSHG','000069.XSHE','002250.XSHE','601169.XSHG','002242.XSHE']
    g.security2015 = ['600519.XSHG','000651.XSHE','600066.XSHG','002081.XSHE','002236.XSHE','000538.XSHE','601166.XSHG','600276.XSHG','000550.XSHE','600036.XSHG','002242.XSHE','600000.XSHG','600048.XSHG','601939.XSHG','600016.XSHG','002065.XSHE','002250.XSHE','000069.XSHE','002142.XSHE','601169.XSHG','002304.XSHE','002294.XSHE','601877.XSHG','002152.XSHE','002146.XSHE','002153.XSHE','002293.XSHE','600511.XSHG','600271.XSHG','601398.XSHG']
    g.security2016 = ['600066.XSHG','000651.XSHE','002236.XSHE','600519.XSHG','600276.XSHG','000538.XSHE','601166.XSHG','002081.XSHE','002142.XSHE','000069.XSHE','600000.XSHG','600036.XSHG','600048.XSHG','601939.XSHG','600016.XSHG','002294.XSHE','002304.XSHE','601877.XSHG','002146.XSHE','600271.XSHG','600511.XSHG','601398.XSHG','002415.XSHE','000848.XSHE','000423.XSHE','000540.XSHE','000887.XSHE','600436.XSHG','002262.XSHE']

    ## 设置回测条件
    set_option('use_real_price', True)
    #用真实价格交易 set_option - 设置其他项
    # 过滤掉order系列API产生的比error级别低的log
    log.set_level('order', 'error') 
    #log.set_level 设定log级别。level: 字符串, 必须是’debug’, ‘info’, ‘warning’, ‘error’中的一个, 级别: debug < info < warning < error
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时万佣金分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0008,close_commission=0.0008, close_today_commission=0, min_commission=5), type='stock')


'''
=================================================
每天开盘前
=================================================
'''
#每天开盘前要做的事情
def before_trading_start(context):
    current_data = get_current_data() #获取当前时间数据
    
    date = context.current_dt.date()
    ## 取初始（initia）数据
    if date > datetime.date(2011,05,01):
        g.stocks = g.security2010
        if date > datetime.date(2012,05,01):
            g.stocks = g.security2011
            if date > datetime.date(2013,05,01):
                g.stocks = g.security2012
                if date > datetime.date(2014,05,01):
                    g.stocks = g.security2013
                    if date > datetime.date(2015,05,01):
                        g.stocks = g.security2014
                        if date > datetime.date(2016,05,01):
                            g.stocks = g.security2015
                            if date > datetime.date(2017,05,01):
                                g.stocks = g.security2016
    initial_stocks=g.stocks
    
    '''
    ##  设置可行股票池：过滤掉当日停牌的股票
    paused_info = [] #paused 暂停
    for i in initial_stocks:
        paused_info.append(current_data[i].paused)
    df_paused_info = pd.DataFrame({'paused_info':paused_info},index = initial_stocks)
    #pd pandas是python环境下最有名的数据统计包，而DataFrame翻译为数据框，是一种数据组织方式
    #HTTP://jingyan.baidu.com/article/4b07be3c64483b48b280f35e.html
    #可以使用字典{}来创建数据框
    #'paused_info' 列的标识
    #index 索引
    g.stocks =list(df_paused_info.index[df_paused_info.paused_info == False])
    '''

'''
=================================================
每日交易时
=================================================
''' 

def Transfer(context):
    #在指定月份（指定月份在g.months这一list中设定）卖卖股票
    if context.current_dt.month in g.months: #如果当前月在指定月
        get_signal(context,g.stocks)
        '''
        tobuy=get_signal(context,g.stocks)  #6得交易信号
        sell_the_stocks(context,tobuy) #7 卖出股票
        buy_the_stocks(context,tobuy)#8 买入股票
        '''
#6 获得交易信号
#（在这里即是获得高息股的股票list，记为Buylist）
#注：为了减少重复计算，本函数没有输出，而是将Buylist设置为全局变量
def get_signal(context,stocks):
    year = context.current_dt.year-1
    
    #将当前股票池转换为国泰安的6位股票池
    stocks_symbol=[]
    for s in stocks:
        stocks_symbol.append(s[0:6]) #append 添加

    #如果知道前一年的分红，那么得到前一年的分红数据
    #gta.run_query - 查询国泰安数据,返回一个pandas.DataFrame
    df1 = gta.run_query(query(
            gta.STK_DIVIDEND.SYMBOL,#股票代码
            gta.STK_DIVIDEND.DIVIDENTBT,#股票分红
            gta.STK_DIVIDEND.DECLAREDATE#分红消息的时间
        ).filter(
            #filter 过滤
    gta.STK_DIVIDEND.ISDIVIDEND == 'Y',#有分红的股票
            gta.STK_DIVIDEND.DIVDENDYEAR == year,
           #且分红信息在上一年度
            gta.STK_DIVIDEND.SYMBOL.in_(stocks_symbol)
        )).dropna(axis=0)
        #dropna(axis=0)选择删除带有缺失值的行，使用参数axis=0，
        #这是最常用的方法
    
    stocks_symbol_this_year=list(df1['SYMBOL'])
    
    #如果前一年的分红不知道，那么知道前两年的分红数据
    df2 = gta.run_query(query(
        gta.STK_DIVIDEND.SYMBOL,#股票代码
        gta.STK_DIVIDEND.DIVIDENTBT,#股票分红
        gta.STK_DIVIDEND.DECLAREDATE#分红消息的时间
    ).filter(
        gta.STK_DIVIDEND.ISDIVIDEND == 'Y',#有分红的股票
        gta.STK_DIVIDEND.DIVDENDYEAR == year-1,
       #且分红信息在上一年度
        gta.STK_DIVIDEND.SYMBOL.in_(stocks_symbol),
        gta.STK_DIVIDEND.SYMBOL.notin_(stocks_symbol_this_year)
    )).dropna(axis=0)
    
    df= pd.concat((df2,df1))  #concat() 方法用于连接两个或多个数组
    
    # 下面四行代码用于选择在当前时间内能已知去年股息信息的股票
    df['pubtime'] = map(lambda x: 
    int(x.split('-')[0]+x.split('-')[1]+x.split('-')[2]),df['DECLAREDATE'])#split切割
    #map()是 Python 内置的高阶函数，它接收一个函数 f 和一个 list，
    #并通过把函数 f 依次作用在 list 的每个元素上，得到一个新的 list 并返回。
    #lambda x:f(X) 相当于x=f(x)函数
    #上面两行就是在df增加pubtime列，值='DECLAREDATE'的数字形式
    currenttime  = int(str(context.current_dt)[0:4]+str(context.current_dt)[5:7]+str(context.current_dt)[8:10])
    
    # 筛选出pubtime小于当前时期的股票，然后剔除'DECLAREDATE','pubtime','SYMBOL'三列
    # 并且将DIVIDENTBT 列转换为float
    #df = df[(df.pubtime < currenttime)]
    
    
    df['SYMBOL']=map(normalize_code,list(df['SYMBOL']))
    df.index=list(df['SYMBOL'])
    
    df=df.drop(['SYMBOL','pubtime','DECLAREDATE'],axis=1)

    df['DIVIDENTBT'] = map(float, df['DIVIDENTBT'])
    
    #接下来这一步是考虑多次分红的股票，因此需要累加股票的多次分红
    #按照股票代码分堆
    df = df.groupby(df.index).sum()

    #得到当前股价
    Price=history(1, unit='1d', field='close', security_list=list(df.index), df=True, skip_paused=False, fq='pre')
    Price=Price.T
    df['pre_close']=Price

    #计算股息率 = 股息/股票价格
    df['divpercent']=df['DIVIDENTBT']/df['pre_close']*10
    df = df[(df.divpercent > g.div)]#取股息率大于
    df=df.sort(columns=['divpercent'], axis=0, ascending=False)#将股息率排序，
    #log.info(df)
    
    df=df[g.size_start-1:g.size_end]#取指定几行数据

    a=df.describe()
    a_count=int(a.iat[0,0]) #第一行第一列
    a_total=a.iat[0,0]*a.iat[1,2] #第一行第一列*第二行第三列 股息率求和
    df['weight']=df['divpercent']/a_total*a_count/(g.size_end-g.size_start+1)
    
    #log.info(a,df)
    
    Buylist =list(df.index)[g.size_start-1:g.size_end]
    #log.info(Buylist)
    #return Buylist
    
    #7 卖出股票
    #def sell_the_stocks(context,Buylist):
    #如果有持仓，就卖掉那些不在上面buylist中的股票
    if len(context.portfolio.positions) != 0:#账户持仓
        for stock in context.portfolio.positions.keys():
            if stock not in Buylist:
                order_target(stock, 0)

    
    #8 买入股票
    value_sum=context.portfolio.portfolio_value#持仓价值+可用资金
    #+context.portfolio.available_cash
    if  len(Buylist)>0:
        for i in range(0,a_count):
            stock=Buylist[i]
            value=value_sum*df.iat[i,3]
            order_target_value(stock,value)
            log.info(i,stock,value)
