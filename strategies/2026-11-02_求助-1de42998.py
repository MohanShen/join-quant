# Clone from JoinQuant
# postId: 1de42998437944acde36ace8cf88f73a
# backtestId: d2c5be65955a555d66a98c2323b7f989
# title: 求助~~~

from jqlib.technical_analysis import *
import pandas as pd  
import numpy as np    
from sklearn.svm import SVR 
from sklearn.tree import DecisionTreeClassifier
import jqdata
import datetime  
def initialize(context):
    set_params()
    set_backtest()
    set_variables()
def set_params():
    g.tc=10  
    g.stocknum=5  
    g.ret=-0.05  
def set_backtest():
    set_benchmark('000001.XSHG')
    set_option('use_real_price',True)
    log.set_level('order','error')
def set_variables():
    g.days=0   
    g.if_trade=False  
def before_trading_start(context):#
    if g.days%g.tc==0:
        g.if_trade=True  
        set_slip_fee(context)  
        g.stocks=get_index_stocks('000300.XSHG')
        g.feasible_stocks=set_feasible_stocks(g.stocks,context)
    g.days+=1  
def set_feasible_stocks(initial_stocks,context):#没问题
    paused_info=[]
    current_data=get_current_data()
    for i in initial_stocks:
        paused_info.append(current_data[i].paused)
        df_paused_info=pd.DataFrame({'paused_info':paused_info},index=
initial_stocks)
    stock_list=list(df_paused_info.index[df_paused_info.paused_info==
False])
    return stock_list 
def set_slip_fee(context):
    set_slippage(FixedSlippage(0))
    set_commission(PerTrade(buy_cost=0.003,sell_cost=0.004,min_cost=5))
def handle_data(context,data):#没问题
    if g._trade==True:
        list_to_buy=stocks_to_buy(context) 
        list_to_sell=stocks_to_sell(context,list_to_buy)
        sell_operation(list_to_sell)
        buy_operation(context,list_to_buy)
    g.if_trade=False
def get_svr(context,stock_list):#没问题
    q=query(valuation.code,valuation.market_cap,balance.total_current_assets-
     balance.total_current_liability,
     balance.total_liability-balance.total_assets,balance.total_liability/balance.equities_parent_company_owners,#
     (balance.total_assets-balance.total_current_assets)/balance.total_assets,
     balance.equities_parent_company_owners/balance.total_assets,
     indicator.inc_total_revenue_year_on_year,valuation.turnover_ratio,
valuation.pe_ratio,valuation.pb_ratio,valuation.ps_ratio,indicator.roa).filter(valuation.code.in_(stock_list))
    df=get_fundamentals(q,date=None)
    df.columns=['code','市值','运营资本','净债务','产权比率','非流动资产比率','股东权益比率','营收增长率','换手率','PB','PS','总资产收益率']
    df.index=df.code.values
    del df['code']
    start=context.current_dt
    delta50=datetime.timedelta(days=50) 
    delta1=datetime.timedelta(days=1) 
    today=start-delta1
    preday=start-delta50
    df['动量线']=list(MIM(df.index,today,timeperiod=10,unit='1d',include_now=True,
                       fq_ref_date=None).values())
    df['成交量']=list(VOL(df.index,today,M1=10,unit='1d',include_now=True,
                      fq_ref_date=None)[0].values())
    df['累计能量线']=list(OBV(df.index,check_date=today,timeperiod=10).values())
    df['资金流量指标']=list(MFT(df.index,today,timeperiod=10,unit='1d',
                             include_now=True,fq_ref_date=None).values())
    df['平均差']=list(DMA(df.index,today,N1=10,unit='1d',
                      include_now=True,fq_ref_date=None)[0].values())
    df['指数移动平均']=list(EMA(df.index,today,timeperiod=10,unit='1d',
                             include_now=True,fq_ref_date=None).values())
    df['移动平均']=list(MA(df.index,today,timeperiod=10,unit='1d',
                            include_now=True,fq_ref_date=None).values())
    df['乖离率']=list(BIAS(df.index,today,N1=10,unit='1d',include_now=True,
                       fq_ref_date=None)[0].values())
    df.fillna(0,inplace=True)
    df['close1']=get_price(stock_list,start_date=today,
                             end_date=today,fq='pre',panel=False)['close'].T
    df['close2']=get_price(stock_list,start_date=preday,
                             end_date=preday,fq='pre',panel=False)['close'].T
    df['return']=df['close1']/df['close2']-1
    df['signal']=np.where(df['return']<df['return'].mean(),0,1)
    x=df.drop(['close1','close2','return','signal'])
    y=df[['signal']]
    x=x.fillna(0)
    y=y.fillna(0)
    tree=DecisionTreeClassifier()
    tree.fit(x,y)
    model_cs=pd.DataFrame({'feature':list(x.columns),'importance':tree.feature_importances_}).sort_values('importance',ascending=False)
    features=model_cs['feature'][:5]
    df2=df[features]     
    df2['市值']=df['市值']
    X=df[features] 
    Y=df['市值']
    X=X.fillna(0)
    Y=Y.fillna(0)
    svr=SVR()
    model=svr.fit(X,Y)
    factor=Y-pd.DataFrame(svr.predict(X),index=Y.index,columns=['市值'])
    factor=factor.sort_values(by='市值')
    return factor#没问题
def stocks_to_buy(context):
    list_to_buy=[]
    day1=context.current_dt
    day2=day1-datetime.timedelta(days=5)
    hs300_close=get_price('000300.XSHG',day2,day1,fq='pre')['close']
    hs300_ret=hs300_close[-1]/hs300_close[0]-1  
    if hs300_ret>g.ret:
        factor=get_svr(context,g.feasible_stocks)
        list_to_buy=list(factor.index[:g.stocknum])
    else:
        pass        
    return list_to_buy
def stocks_to_sell(context,list_to_buy):#没问题
    list_to_sell=[]
    day1=context.current_dt
    day2=day1-datetime.timedelta(days=5)  
    hs300_close=get_price('000300.XSHG',day2,day1,fq='pre')['close']
    hs300_ret=hs300_close[-1]/hs300_close[0]-1   
    for stock_sell in context.portfolio.positions:
        if hs300_ret<=g.ret:
            list_to_sell.append(stock_sell)
        else:
            if.context.portfolio.positions[stock_sell].price/context.portfolio.positions[stock_sell].avg_cost<0.95 or stock_sell not in list_to_buy:
                list_to_sell.append(stock_sell)
    return list_to_sell
def buy_operation(context,list_to_buy):#没错
    if len(context.portfolio.positions)<g.stocknum:
        num=g.stocknum-len(context.portfolio.positions)
        cash=context.portfolio.cash/num   
    else:
        cash=0 
        num=0  
    for stock_sell in list_to_buy[:num+1]:
            order_target_value(stock_sell,cash)
            num=num-1
            if num==0:
                break  
    else:
        pass        
def sell_operation(list_to_sell):
    for stock_sell in list_to_sell:
        order_target_value(stock_sell,0)