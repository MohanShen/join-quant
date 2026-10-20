# Clone from JoinQuant
# postId: 4c82066d72b93d35d0031d662b09db7f
# backtestId: 672e94d0f041a3e5a2a29b7042574ba8
# title: 一起造个多因子指数增强策略吧

import pandas as pd
import numpy as np
import datetime as dt
from jqdata import *
import statsmodels.api as sm
import copy

# 初始化函数，设定基准等等
def initialize(context):
    #开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 过滤掉order系列API产生的比error级别低的log
    log.set_level('order', 'error')
    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    #参数设置部分
    g.benchmark = '000905.XSHG'
    g.max_hold_num = 100  #最大持仓股票
    g.count= 21         #因子统计长度
    g.tot_periods= 15     #因子统计期数
    g.days=0             #记录运行天数，用于调仓
    g.periods=0          #标记是否为初始化
    g.neu=True           #是否中性化
    #设置基准
    set_benchmark(g.benchmark)
    #策略定时任务
    #run_daily(func, time='open', reference_security='000300.XSHG')
    #run_weekly(func,1,time = 'open', reference_security=g.benchmark)
    run_monthly(main_func,1,time = 'open', reference_security=g.benchmark)
    #run_monthly(main_func,11,time = 'open', reference_security=g.benchmark)
#==============主体函数==================
#主循环函数
def main_func(context):
    g.stock_tobuy=get_stock_list(context)
    log.info('筛选出的股票列表个数：%s'%len(g.stock_tobuy))
    g.periods+=1
    trade1(context,g.stock_tobuy)
    
def get_stock_list(context):
    
    end_date=context.previous_date
    stock_list = get_index_stocks(g.benchmark, date=context.current_dt)
    print('成分股:%s只股票'%len(stock_list))
    stock_list=filter_new_stock(context,stock_list)
    stock_list=filter_paused_or_st(context,stock_list)
    print('过滤新股、st、停牌后剩下：%s只股票'%len(stock_list))
    count = g.count                    
    periods = g.tot_periods          
    IC=pd.DataFrame()
    rank=pd.DataFrame()
    IC_IR=pd.Series()
    IC['MC'],IC_IR['MC'],rank['MC']=calc_IC_continuous_MC(stock_list,end_date,count,periods)                
    IC['BP'],IC_IR['BP'],rank['BP']=calc_IC_continuous_BP(stock_list,end_date,count,periods)                
    IC['INCNP'],IC_IR['INCNP'],rank['INCNP']=calc_IC_continuous_INCNP(stock_list,end_date,count,periods)
    IC['ROE'],IC_IR['ROE'],rank['ROE']=calc_IC_continuous_ROE(stock_list,end_date,count,periods)
    
    IC_dict = {}
    for colu in IC.columns:
        IC_dict[colu] = IC[colu].mean()
        ic_mean = IC[colu].mean()
        if ic_mean<0:
            rank[colu] = rank[colu].rank(ascending=0)
            rank[colu] = rank[colu]#*abs(ic_mean)  #IC加强
    ic_df = pd.DataFrame(IC_dict,index=['IC_mean'])
    print('IC值说明',ic_df)
    weight=pd.DataFrame(IC_IR)
    #print('权重内容说明%s'%weight)
    #print('rank',rank)
    rank_tot=rank.dot([abs(v) for v in weight.values])      #加入IC_IR权重后打分
    rank_tot.columns=['point']       
    rank_tot['rank']=rank_tot['point'].rank(ascending=1) #多因子综合得分排序，rank参数1为相同排序逻辑，大为大，小为小
    rank_tot=rank_tot.sort('point',ascending=0)     #0为从大到小排序     
    #rank_tot_hs300=rank_tot.ix[get_index_stocks('000300.XSHG')].sort('point',ascending=0)
    rank_tot_zz500=rank_tot.ix[get_index_stocks('000905.XSHG')].sort('point',ascending=0)
    log.info('rank_tot',rank_tot.head())
    #log.info('rank_tot_hs300',rank_tot_hs300.head())
    stocks = rank_tot_zz500.index.tolist()[:g.max_hold_num]
    return stocks
    
#等权重交易  
def trade(context,stock_list):
    cash_value =context.portfolio.total_value/len(stock_list)
    print('每只股票应分仓为：%s'%cash_value)
    #卖出不在持仓列表中股票
    #调整已有持仓
    for stock in context.portfolio.positions.keys():
        if stock not in stock_list:
            order_target(stock, 0)
        elif context.portfolio.long_positions[stock].value>(1.2*cash_value):
            order_target_value(stock, cash_value)
        elif context.portfolio.long_positions[stock].value<(0.8*cash_value):
            order_target_value(stock, cash_value)
    #买入在持仓中股票
    for stock in stock_list:
        if stock not in context.portfolio.positions.keys():
            order_target_value(stock, cash_value)
#交易部分（权重分配        
def trade1(context,stock_list):
    cash_value_50 = context.portfolio.total_value*0.5
    cash_value_30 = context.portfolio.total_value*0.3
    cash_value_20 = context.portfolio.total_value*0.2
    stock_list_20 = stock_list[:20]
    stock_list_30 = stock_list[20:50]
    stock_list_50 = stock_list[50:]
    
    #卖出不在持仓列表中股票
    #调整已有持仓
    for stock in context.portfolio.positions.keys():
        if stock not in stock_list:
            order_target(stock, 0)
    trade3(context,stock_list_20,cash_value_50)
    trade3(context,stock_list_30,cash_value_30)
    trade3(context,stock_list_50,cash_value_20)

def trade3(context,stock_list,cash):
    cash_value = cash*1.0/len(stock_list)
    for stock in stock_list:
        if stock in context.portfolio.positions.keys():
            if context.portfolio.long_positions[stock].value>(1.2*cash_value):
                order_target_value(stock, cash_value)
            elif context.portfolio.long_positions[stock].value<(0.8*cash_value):
                order_target_value(stock, cash_value)
    #买入在持仓中股票
        else:
            order_target_value(stock, cash_value)
            
#==============工具方法===================
#获取股票涨跌幅
def pctchange(stock,end_date,count):
    try:
        pnl = get_price(stock,end_date=end_date,count=count,fields=['pre_close','close'],fq='post')
        price_start = pnl['pre_close'].fillna(method='bfill').ix[0]
        price_end = pnl['close'].fillna(method='bfill').ix[-1]

        pct= price_end/price_start-1
        pct= pct.fillna(0)
    except:
        print '输入有误，请检查输入参数======pctchange'
        pnl = get_price(stock,count=1,end_date='2017-01-01',fields=['pre_close','close'],fq='post')
        price_start = pnl['pre_close'].ix[0]
        price_end = price_start
        pct= price_end/price_start-1
        pct= pct.fillna(0)
    return pct
#获取指定交易日往前推count天交易日
def tradedays_before(date,count):
    date = get_price('000001.XSHG',end_date=date,count=count+1).index[0]
    return date
#返回股票为index，市值对数和行业哑变量
def get_industry_label(stock_list):
    q = query(valuation.code,valuation.circulating_market_cap).filter(valuation.code.in_(stock_list))
    df = get_fundamentals(q, date = None)
    df.index=df.code.values
    df.columns=['code','log_mc']
    df['log_mc']=np.log(df['log_mc'])
    industry_list = list(get_industries(name='sw_l1').index)
    for i in range(len(industry_list)):
        industry = get_industry_stocks(industry_list[i], date = None)
        s = pd.Series([0]*len(df), index=df.index)
        s[set(industry) & set(df.index)]=1
        df[industry_list[i]] = s
    ind = df.mean()!=0
    columns=ind[ind.values].index.tolist()
    df=df.ix[:,columns]

    return df
#过滤新股函数
def filter_new_stock(context,stock_list):
    tmpList = []
    for stock in stock_list :
        days_public=(context.current_dt.date() - get_security_info(stock).start_date).days
        if days_public > 252:
            tmpList.append(stock)
    return tmpList
#过滤停牌或者ST股票
def filter_paused_or_st(context,stock_list):
    tmpList=[]
    cd=get_current_data()
    for stock in stock_list:
        if not (cd[stock].paused or cd[stock].is_st):
            tmpList.append(stock)
    return tmpList
#中性化处理
def neutralize(df):
    ind_df = get_industry_label(list(df.index))
    est=sm.OLS(df['factor'],ind_df.iloc[:,1:]).fit()
    df['factor_ne']=est.resid
    return df
    
#==============因子计算模块=================
def calc_IC_continuous_BP(stock_list,end_date,count,periods):
    def calc_IC(stock_list,end_date,count):
        start_date=tradedays_before(end_date,count+1)
        q = query(valuation.code,1/valuation.pb_ratio).filter(valuation.code.in_(stock_list))
        df = get_fundamentals(q, date = start_date)
        df.index=df.code.values
        df = df.reindex(stock_list)
        df.code=df.index
        #log.info('len(df) in BP:',len(df),len(stock_list),start_date)
        df.columns=['code','factor']
        df['factor']=df['factor'].fillna(df['factor'].mean())
        if g.neu:
            df=neutralize(df)
            df['factor_rank']=df['factor_ne'].rank()
        else:
            df['factor_rank']=df['factor'].rank()
        pct = pctchange(stock_list,end_date,count)
        df['pct']=pct
        df['pct_rank']=df['pct'].rank()
        df=df.dropna()
        IC=np.corrcoef(df.factor_rank,df.pct_rank)[0][1]
        #print IC
        return IC
    
    def calc_rank(stock_list,end_date):
        start_date=end_date
        q = query(valuation.code,1/valuation.pb_ratio).filter(valuation.code.in_(stock_list))
        df = get_fundamentals(q, date = start_date)
        df.index=df.code.values
        df.columns=['code','factor']
        df['factor']=df['factor'].fillna(df['factor'].mean())
        if g.neu:
            df=neutralize(df)
            df['factor_rank']=df['factor_ne'].rank()
        else:
            df['factor_rank']=df['factor'].rank()
        return df.factor_rank
    rank=calc_rank(stock_list,end_date)
    #log.info('BP,rank',rank)
    if g.periods==0:
        df=pd.DataFrame()
        for i in range(periods):
            IC=calc_IC(stock_list,end_date,count)
            df.loc[i,'period']=i
            df.loc[i,'start_date']=tradedays_before(end_date,count)
            df.loc[i,'end_date']=end_date
            df.loc[i,'IC']=IC
            end_date=tradedays_before(end_date,count)
        df.index=df.end_date.values
        df=df.sort('period',ascending=0)
        g.df_BP=df
        IC_IR=df['IC'].mean()/df['IC'].std()
    else:
        log.info('BP,g.periods',g.periods)
        df_new=pd.DataFrame()
        IC=calc_IC(stock_list,end_date,count)
        df_new.loc[0,'period']=0
        df_new.loc[0,'start_date']=tradedays_before(end_date,count)
        df_new.loc[0,'end_date']=end_date
        df_new.loc[0,'IC']=IC
        end_date=tradedays_before(end_date,count)
        df_new.index=df_new.end_date.values
        #log.info('g.df_BP_1',g.df_BP)
        g.df_BP=pd.concat([g.df_BP.ix[1:],df_new],axis=0)
        #g.df_BP=g.df_BP.ix[1:]
        #log.info('g.df_BP_2',g.df_BP)
        g.df_BP['period']=range(periods-1,-1,-1)
        #log.info('df_new',df_new)
        #log.info('g.df_BP_3',g.df_BP)
        df=g.df_BP
        IC_IR=df['IC'].mean()/df['IC'].std()
    log.info('BP_IC done!')
    return df.IC,IC_IR,rank

def calc_IC_continuous_MC(stock_list,end_date,count,periods):
    def calc_IC(stock_list,end_date,count):
        start_date=tradedays_before(end_date,count+1)
        q = query(valuation.code,valuation.circulating_market_cap).filter(valuation.code.in_(stock_list))
        df = get_fundamentals(q, date = start_date)
        df.index=df.code.values
        df = df.reindex(stock_list)
        df.code=df.index
        #log.info('len(df) in MC:',len(df),len(stock_list),start_date)
        pct = pctchange(stock_list,end_date,count)
        df['factor_rank']=df['circulating_market_cap'].rank()
        df['pct']=pct
        df['pct_rank']=df['pct'].rank()
        df=df.dropna()
        IC=np.corrcoef(df.factor_rank,df.pct_rank)[0][1]
        #print IC
        return IC
    def calc_rank(stock_list,end_date):
        start_date=end_date
        q = query(valuation.code,valuation.circulating_market_cap).filter(valuation.code.in_(stock_list))
        df = get_fundamentals(q, date = start_date)
        df.index=df.code.values
        df.columns=['code','factor']
        #df=neutralize(df)
        df['factor_rank']=df['factor'].rank()
        return df.factor_rank
    t0=dt.datetime.now()
    rank=calc_rank(stock_list,end_date) #市值rank序列     
    if g.periods==0:
        df=pd.DataFrame()
        for i in range(periods):
            IC=calc_IC(stock_list,end_date,count)
            df.loc[i,'period']=i
            df.loc[i,'start_date']=tradedays_before(end_date,count)
            df.loc[i,'end_date']=end_date
            df.loc[i,'IC']=IC
            end_date=tradedays_before(end_date,count)
        df.index=df.end_date.values
        df=df.sort('period',ascending=0)
        g.df_MC=df
        IC_IR=df['IC'].mean()/df['IC'].std()
    else:
        log.info('MC,g.periods',g.periods)
        df_new=pd.DataFrame()
        IC=calc_IC(stock_list,end_date,count)
        df_new.loc[0,'period']=0
        df_new.loc[0,'start_date']=tradedays_before(end_date,count)
        df_new.loc[0,'end_date']=end_date
        df_new.loc[0,'IC']=IC
        end_date=tradedays_before(end_date,count)
        df_new.index=df_new.end_date.values
        g.df_MC=pd.concat([g.df_MC.ix[1:],df_new],axis=0)
        g.df_MC['period']=range(periods-1,-1,-1)
        df=g.df_MC
        IC_IR=df['IC'].mean()/df['IC'].std()
    log.info('MC_IC done!')
    return df.IC,IC_IR,rank

def calc_IC_continuous_INCNP(stock_list,end_date,count,periods):
    def calc_IC(stock_list,end_date,count):
        start_date=tradedays_before(end_date,count+1)
        q = query(valuation.code,indicator.inc_net_profit_year_on_year).filter(valuation.code.in_(stock_list))
        df = get_fundamentals(q, date = start_date)
        df.index=df.code.values
        df = df.reindex(stock_list)
        df.code=df.index
        #log.info('len(df) in INCNP:',len(df),len(stock_list),start_date)
        df.columns=['code','factor']
        df['factor']=df['factor'].fillna(df['factor'].mean())
        if g.neu:
            df=neutralize(df)
            df['factor_rank']=df['factor_ne'].rank()
        else:
            df['factor_rank']=df['factor'].rank()
        pct = pctchange(stock_list,end_date,count)
        df['pct']=pct
        df['pct_rank']=df['pct'].rank()
        df=df.dropna()
        IC=np.corrcoef(df.factor_rank,df.pct_rank)[0][1]
        #print IC
        return IC
    
    def calc_rank(stock_list,end_date):
        start_date=end_date
        q = query(valuation.code,indicator.inc_net_profit_year_on_year).filter(valuation.code.in_(stock_list))
        df = get_fundamentals(q, date = start_date)
        df.index=df.code.values
        df.columns=['code','factor']
        df['factor']=df['factor'].fillna(df['factor'].mean())
        if g.neu:
            df=neutralize(df)
            df['factor_rank']=df['factor_ne'].rank()
        else:
            df['factor_rank']=df['factor'].rank()
        return df.factor_rank
    
    rank=calc_rank(stock_list,end_date)
    if g.periods==0:
        df=pd.DataFrame()
        for i in range(periods):
            IC=calc_IC(stock_list,end_date,count)
            df.loc[i,'period']=i
            df.loc[i,'start_date']=tradedays_before(end_date,count)
            df.loc[i,'end_date']=end_date
            df.loc[i,'IC']=IC
            end_date=tradedays_before(end_date,count)
        df.index=df.end_date.values
        df=df.sort('period',ascending=0)
        g.df_INCNP=df
        IC_IR=df['IC'].mean()/df['IC'].std()
    else:
        log.info('INCNP,g.periods',g.periods)
        df_new=pd.DataFrame()
        IC=calc_IC(stock_list,end_date,count)
        df_new.loc[0,'period']=0
        df_new.loc[0,'start_date']=tradedays_before(end_date,count)
        df_new.loc[0,'end_date']=end_date
        df_new.loc[0,'IC']=IC
        end_date=tradedays_before(end_date,count)
        df_new.index=df_new.end_date.values
        g.df_INCNP=pd.concat([g.df_INCNP.ix[1:],df_new],axis=0)
        g.df_INCNP['period']=range(periods-1,-1,-1)
        df=g.df_INCNP
        IC_IR=df['IC'].mean()/df['IC'].std()
    log.info('INCNP_IC done!')
    return df.IC,IC_IR,rank

def calc_IC_continuous_ROE(stock_list,end_date,count,periods):
    def calc_IC(stock_list,end_date,count):
        start_date=tradedays_before(end_date,count+1)
        q = query(valuation.code,indicator.roe).filter(valuation.code.in_(stock_list))
        df = get_fundamentals(q, date = start_date)
        df.index=df.code.values
        df = df.reindex(stock_list)
        df.code=df.index
        df.columns=['code','factor']
        df['factor']=df['factor'].fillna(df['factor'].mean())
        if g.neu:
            df=neutralize(df)
            df['factor_rank']=df['factor_ne'].rank()
        else:
            df['factor_rank']=df['factor'].rank()
        pct = pctchange(stock_list,end_date,count)
        df['pct']=pct
        df['pct_rank']=df['pct'].rank()
        df=df.dropna()
        IC=np.corrcoef(df.factor_rank,df.pct_rank)[0][1]
        #print IC
        return IC

    def calc_rank(stock_list,end_date):
        start_date=end_date
        q = query(valuation.code,indicator.roe).filter(valuation.code.in_(stock_list))
        df = get_fundamentals(q, date = start_date)
        df.index=df.code.values
        df.columns=['code','factor']
        df['factor']=df['factor'].fillna(df['factor'].mean())
        if g.neu:
            df=neutralize(df)
            df['factor_rank']=df['factor_ne'].rank()
        else:
            df['factor_rank']=df['factor'].rank()
        return df.factor_rank
    
    
    rank=calc_rank(stock_list,end_date)
    if g.periods==0:
        df=pd.DataFrame()
        for i in range(periods):
            IC=calc_IC(stock_list,end_date,count)
            df.loc[i,'period']=i
            df.loc[i,'start_date']=tradedays_before(end_date,count)
            df.loc[i,'end_date']=end_date
            df.loc[i,'IC']=IC
            end_date=tradedays_before(end_date,count)
        df.index=df.end_date.values
        df=df.sort('period',ascending=0)
        g.df_ROE=df
        IC_IR=df['IC'].mean()/df['IC'].std()
    else:
        log.info('ROE,g.periods',g.periods)
        df_new=pd.DataFrame()
        IC=calc_IC(stock_list,end_date,count)
        df_new.loc[0,'period']=0
        df_new.loc[0,'start_date']=tradedays_before(end_date,count)
        df_new.loc[0,'end_date']=end_date
        df_new.loc[0,'IC']=IC
        end_date=tradedays_before(end_date,count)
        df_new.index=df_new.end_date.values
        g.df_ROE=pd.concat([g.df_ROE.ix[1:],df_new],axis=0)
        g.df_ROE['period']=range(periods-1,-1,-1)
        df=g.df_ROE
        IC_IR=df['IC'].mean()/df['IC'].std()
    log.info('ROE_IC done!')
    return df.IC,IC_IR,rank



    
        
