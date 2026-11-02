# Clone from JoinQuant
# postId: c8e056adaf2aa7293eab276aa629d5e3
# backtestId: b94f36468c36e209760ea62432f6033a
# title: 基金分红后收益错误

# 导入函数库
from jqdata import *
import numpy as np
import pandas as pd
from pandas import DataFrame,Series
import scipy.stats as st
from scipy.stats import norm
from scipy.stats.mstats import gmean
import matplotlib.pyplot as plt

# 初始化函数，设定基准等等
def initialize(context):
    g.days = 0 #日期计数器
    g.ipush_days = 60 #定投间隔
    # 设定基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option("use_real_price", True)
    #set_order_cost(close_commission=0.0065, type='open_fund', ref=None)
    ### 场外基金相关设定 ###
    # 设置账户类型: 场外基金账户
    set_subportfolios([SubPortfolioConfig(context.portfolio.cash, 'open_fund')])
    # 设置赎回到账日
    set_redeem_latency(1,'open_fund')

    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
        # 开盘时运行
    run_daily(market_open, time='open', reference_security='000300.XSHG')
        # 收盘后运行
    run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')


def before_trading_start(context):
    g.if_trade=False 
    if g.days%g.ipush_days==0:
        #每g.tc天，交易一次行
        g.if_trade=True 
    g.days+=1
    

def market_open(context):
    if g.if_trade==True:
        year1=get_n_year_date(context,1)
        year2=get_n_year_date(context,2)
        before_yesterday= shift_trading_day(context.previous_date, shift = -100)
        #股票持仓超70%的基金
        q1=query(finance.FUND_PORTFOLIO.code,
                  finance.FUND_PORTFOLIO.name,
                  finance.FUND_PORTFOLIO.period_end,
        finance.FUND_PORTFOLIO.pub_date).filter(finance.FUND_PORTFOLIO.equity_rate>=60,
        ~finance.FUND_PORTFOLIO.name.contains('B'),~finance.FUND_PORTFOLIO.name.contains('C'),~finance.FUND_PORTFOLIO.name.contains('D'),
        ~finance.FUND_PORTFOLIO.name.contains('E'),~finance.FUND_PORTFOLIO.name.contains('球'),~finance.FUND_PORTFOLIO.name.contains('分级'),
        ~finance.FUND_PORTFOLIO.name.contains('定'),~finance.FUND_PORTFOLIO.name.contains('医'),~finance.FUND_PORTFOLIO.name.contains('消费'),
        ~finance.FUND_PORTFOLIO.name.contains('科技'),~finance.FUND_PORTFOLIO.name.contains('健康'),~finance.FUND_PORTFOLIO.name.contains('信息'),
        ~finance.FUND_PORTFOLIO.name.contains('指'),~finance.FUND_PORTFOLIO.name.contains('资源'),
        finance.FUND_PORTFOLIO.period_end<year1,finance.FUND_PORTFOLIO.pub_date<=context.previous_date, 
        ).order_by(finance.FUND_PORTFOLIO.pub_date.desc()).limit(3000)
        df1=finance.run_query(q1)
        df1=df1.drop_duplicates(subset=['code'],keep='first')
        
        q2=query(finance.FUND_PORTFOLIO.code,
                  finance.FUND_PORTFOLIO.name,
                  finance.FUND_PORTFOLIO.period_end,
        finance.FUND_PORTFOLIO.pub_date).filter(finance.FUND_PORTFOLIO.equity_rate>=60,
        ~finance.FUND_PORTFOLIO.name.contains('B'),~finance.FUND_PORTFOLIO.name.contains('C'),
        year1<finance.FUND_PORTFOLIO.period_end,finance.FUND_PORTFOLIO.pub_date<=context.previous_date,
        finance.FUND_PORTFOLIO.code.in_(df1.code)
        ).order_by(finance.FUND_PORTFOLIO.pub_date.desc()).limit(3000)
        df2=finance.run_query(q2)
        df2=df2.drop_duplicates(subset=['code'],keep='first')
        
        q3=query(finance.FUND_MAIN_INFO).filter(#~finance.FUND_MAIN_INFO.underlying_asset_type_id.contains('402002' or '402003' or '402005' or '402006' or '402007'),
        ~finance.FUND_MAIN_INFO.operate_mode_id.contains('401005'),~finance.FUND_MAIN_INFO.operate_mode_id.contains('401002'),~finance.FUND_MAIN_INFO.operate_mode_id.contains('401004'),
        ~finance.FUND_MAIN_INFO.operate_mode_id.contains('401003'),~finance.FUND_MAIN_INFO.operate_mode_id.contains('401006'),
        ~finance.FUND_MAIN_INFO.underlying_asset_type_id.contains('402002'),
        finance.FUND_MAIN_INFO.start_date<year2,finance.FUND_MAIN_INFO.end_date==None,finance.FUND_MAIN_INFO.main_code.in_(df2.code))
        df3=finance.run_query(q3)

        all_code=df3.main_code
        pa = pd.DataFrame(index=all_code,columns=['sharp'])
        #pa['sharp']=get_sharp(context,all_code)
        #pa['total_asset']=get_total_asset(context,all_code)   
        #pa['ret_down']=get_ret_down(context,all_code)
        pa=pa.dropna(axis=0,how='any')
        '''
        pa = pa.sort_values('total_asset',ascending=True)
        pa=pa.head(int(len(pa)*0.8))#过滤规模大的
        pa = pa.sort_values('total_asset',ascending=False)
        pa=pa.head(int(len(pa)*0.9))#过滤规模小的
        pa = pa.sort_values('ret_down',ascending=False)
        pa=pa.head(int(len(pa)*0.9))
        '''
        #pa = pa.sort_values('sharp',ascending=False)
        #print (pa)
        #g.ff=pa.index[:10].values
        g.ff=['163406']
        print(g.ff,context.portfolio.available_cash)
        FF=[i+'.OF' for i in g.ff]
        # 赎回基金
        order_fund_sell(context,FF)
    FF=[i+'.OF' for i in g.ff]
    if context.portfolio.available_cash>1000:# and (len(FF)-len(context.portfolio.positions))>0:
        # 申购基金
        order_fund_buy(context,FF)

    g.if_trade=False
    
def order_fund_sell(context,funds):
    # 对于不需要持仓的股票，卖出可卖出的基金份额
    for fund in context.portfolio.positions:
        #除去排名前g.N个股票（选股！）
        if fund not in funds:
            print(fund,context.portfolio.positions[fund].closeable_amount)
            redeem(fund, context.portfolio.positions[fund].closeable_amount)
    return 

#输入：context, data，已排序股票列表stock_sort-list类型
def order_fund_buy(context,funds):
    print(len(context.portfolio.positions))
    everyStock=context.portfolio.available_cash / (len(funds)-len(context.portfolio.positions))
    for fund in funds:
        if fund not in context.portfolio.positions:
            print(fund,everyStock)
            purchase(fund, everyStock)
    return 
        
#获取n年前的今天
def get_n_year_date(context,n):
    now = context.previous_date  #context.current_dt
    last_one_year = int(now.year) - n
    now_date = now.strftime("%Y-%m-%d")[-6:]
    last_year_date =  str(last_one_year) + now_date
    return last_year_date
    
    
def get_MTM3(stock_list,end,n,m):
    #(n+61)天前日期
    days_before= shift_trading_day(end, shift = -(n+m))
    #(n+61)天前价格
    days_before_price = get_price(list(stock_list), start_date=days_before, 
            end_date=days_before,frequency='daily',fields='close')['close'].T
    #n天前的日期(较新的日期)
    days= shift_trading_day(end, shift = -n)
    # # n天前的价格
    days_price=get_price(list(stock_list), start_date=days, 
            end_date=days, frequency='daily', fields='close')['close'].T
    #n天这段时间的收益率,Series
    Series_mtm3=(days_price.iloc[:,0]-days_before_price.iloc[:,0])/days_before_price.iloc[:,0]
    # 生成dataframe格式
    df_MTM3 = pd.DataFrame({'MTM3':Series_mtm3})
    df_MTM3=df_MTM3.fillna(0)
    #排序打分
    #df_MTM3['MTM3'] = df_MTM3['MTM3'].rank(ascending = True, method = 'dense')
    # 排序给出排序打分，MTM3
    return df_MTM3

#逆势(大盘下跌时)收益
def get_ret_down(context,all_code):
    #指数下跌月份
    index='000300.XSHG'
    days_before= shift_trading_day(context.previous_date, shift = -800)
    #作天的价格
    days_price=get_price(index,start_date=days_before, end_date=context.previous_date, 
                       frequency='20d', fields='close')['close'].T
    days_price2=days_price.pct_change()*100
    days_price2=days_price2.sort_index(ascending=False)#[:-1]
    #print(days_price2)
    #小于0.5%的日期
    days_price2=days_price2[days_price2.values<0.5]
    
    #指数下跌月份，基金的收益
    pa = pd.DataFrame(index=all_code,columns=['ret_down'])
    for i in all_code:
        #df3所有月份
        q3 = query(finance.FUND_NET_VALUE.code,finance.FUND_NET_VALUE.refactor_net_value,finance.FUND_NET_VALUE.day,
        ).filter(finance.FUND_NET_VALUE.code==i,finance.FUND_NET_VALUE.day.in_(days_price.index)).order_by(finance.FUND_NET_VALUE.day.asc()).limit(1000)
        df3=finance.run_query(q3)
        #df4下跌月份
        q4 = query(finance.FUND_NET_VALUE.code,finance.FUND_NET_VALUE.refactor_net_value,finance.FUND_NET_VALUE.day,
        ).filter(finance.FUND_NET_VALUE.code==i,finance.FUND_NET_VALUE.day.in_(days_price2.index)).order_by(finance.FUND_NET_VALUE.day.asc()).limit(1000)
        df4=finance.run_query(q4)
        df3['ret']=df3['refactor_net_value'].pct_change()+1
        #选出指数下跌的月份
        df5=df3[df3['day'].isin(df4.day)]
        df5=df5.sort_values(by='day',ascending=False)
        df5=df5.head(12)
        #print(days_price2,df5)
        pa.loc[i,'ret_down']=gmean(df5['ret'])#几何平均值
    return pa['ret_down']

#计算每日持仓基金收益
def get_ret(context,fund):
    before_yesterday= shift_trading_day(context.previous_date, shift = -1)
    pa = pd.DataFrame(index=fund,columns=['ret'])
    for i in fund:
        q3 = query(finance.FUND_NET_VALUE.code,finance.FUND_NET_VALUE.refactor_net_value,finance.FUND_NET_VALUE.day,
        ).filter(finance.FUND_NET_VALUE.code==i,finance.FUND_NET_VALUE.day <= context.previous_date,before_yesterday <= finance.FUND_NET_VALUE.day
        ).order_by(finance.FUND_NET_VALUE.day.desc()).limit(100)
        df3=finance.run_query(q3)
        if len(df3)>0:
            #print(fund,df3)
            pa.loc[i,'ret']=df3.iloc[0,1] / df3.iloc[-1,1]
        #print(df3)
    #print(pa['ret'])
    pa=pa.dropna(axis=0,how='any')
    return pa['ret']

#计算基金规模
def get_total_asset(context,all_code):
    #取前len(all_code)个数据，即所有的基金最新一次总资产数据
    pa = pd.DataFrame(index=all_code,columns=['total_asset'])
    q=query(finance.FUND_PORTFOLIO.code,
            finance.FUND_PORTFOLIO.name,finance.FUND_PORTFOLIO.total_asset,
            #会获取到最新数据，pub_date
            ).filter(finance.FUND_PORTFOLIO.code.in_(all_code),finance.FUND_PORTFOLIO.pub_date<=context.previous_date
    ).order_by(finance.FUND_PORTFOLIO.pub_date.desc()).limit(len(all_code)*1.2)
    df=finance.run_query(q)
    df=df.drop_duplicates(subset=['code'],keep='first')
    df=df.set_index('code')
    pa['total_asset']=df['total_asset']
    return pa['total_asset']

#计算夏普、标准差
#Rp=((1+P)**(250/n)−1)∗100%    sharp=(Rp-0.04/年化波动率)
def get_sharp(context,all_code):
    pa = pd.DataFrame(index=all_code,columns=['sharp'])
    L_N=243
    for i in all_code:
        #，净值开始日期没设置？
        q3 = query(finance.FUND_NET_VALUE.code,finance.FUND_NET_VALUE.refactor_net_value,finance.FUND_NET_VALUE.day,
        ).filter(finance.FUND_NET_VALUE.code==i,finance.FUND_NET_VALUE.day <= context.previous_date).order_by(finance.FUND_NET_VALUE.day.desc()).limit(L_N)
        df3=finance.run_query(q3)
        #print(i,df3)
        #除法有问题，需要前移一位
        df3['diff']=df3['refactor_net_value'].diff(-1)/df3['refactor_net_value']
        #print (i,df3)
        #只保留净值数量大于L_N的基金，不足的可能是定开的
        if len(df3.refactor_net_value)<L_N:
            aaa=1#print (i)
        if len(df3.refactor_net_value)==L_N and -0.09<df3['diff'].max() <0.09:
            df3=df3.head(L_N-1)
            pa.loc[i,'sharp']=(((df3.iloc[0,1] / df3.iloc[-1,1] )** (250 / L_N))-1-0.04)/ (df3['diff'].std()* np.sqrt(250))
            pa.loc[i,'std']=df3['diff'].std()* np.sqrt(250)
            #print(i,(((df3.iloc[0,1] / df3.iloc[-1,1] )** (250 / L_N))-1-0.04),(df3['diff'].std()* np.sqrt(250)))

    pa=pa.dropna(axis=0,how='any')
    return pa['sharp']

def shift_trading_day(date,shift):
    # 获取所有的交易日，返回一个包含所有交易日的 list,元素值为 datetime.date 类型.
    tradingday = get_all_trade_days()
    # 得到date之后shift天那一天在列表中的行标号 返回一个数
    shiftday_index = list(tradingday).index(date)+shift
    # 根据行号返回该日日期 为datetime.date类型
    return tradingday[shiftday_index]
## 收盘后运行函数
def after_market_close(context):
    # 查看融资融券账户相关相关信息(更多请见API-对象-SubPortfolio)
    p = context.portfolio.available_cash
    #if p>1000:
    #    print (p)
