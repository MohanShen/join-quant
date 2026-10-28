# Clone from JoinQuant
# postId: 48c30615354b5eb630f34e865c90b21a
# backtestId: bf7e8f96fcea0a4358eacd16b5c31487
# title: 市销率与毛利率策略，简单实用

# 初始化函数，设定要操作的股票、基准等等
import pandas as pd
from jqdata import *
import matplotlib.pyplot as plt
import bisect
import numpy as np
from time import *
from datetime import *
from six import StringIO

def initialize(context):
    #g.benchmark='000300.XSHG'
    g.benchmark='399934.XSHE'
    set_benchmark(g.benchmark)
    g.stocknum = 10# 持股数
    ## 自动设定调仓月份（如需使用自动，注销下段）
    i = 12 # 调仓频率
    log.info(range(1,13,12/i))
    g.Transfer_date = range(1,13,12/i)
    g.new_turn=True
    ## 手动设定调仓月份（如需使用手动，注销上段）
    # g.Transfer_date = (3,9)
    
    ## 按月调用程序
    run_monthly(Transfer,1)
    #run_weekly(Transfer,4)
    #run_daily(stop_loss)
def get_stock(context):
    g.security = get_index_stocks(g.benchmark)
    set_universe(g.security)
    #-----------todo:定义第一个因子-----------------------#
    q1=query(valuation.code,valuation.ps_ratio,indicator.gross_profit_margin).filter(valuation.code.in_(g.security))
    df1=get_fundamentals(q1)
    df1=df1.sort('ps_ratio',ascending=True)
    df1=df1.head(len(df1.index)/10)
    df1=df1.sort('gross_profit_margin',ascending=False)
    buy_list=list(df1['code'])
    #print(df_buy)
    return buy_list
def Transfer(context):
    months = context.current_dt.month
    if months in g.Transfer_date or len(context.portfolio.positions) == 0:
        '''
        low_pos=70
        high_pos=90
        cost=0
        end_date=context.current_dt
        start_date=str(end_date.year-5)+'-'+str(end_date.month)+'-'+str(end_date.day)
        pos=get_divid(g.benchmark,'PE',start_date,end_date)
        if pos>high_pos:g.new_turn=False
        if pos<low_pos and not g.new_turn:g.new_turn=True
        if not g.new_turn:
            for stock in context.portfolio.positions:
                order_target(stock,0)
        else:
        '''
        ##获得Buylist
        Buylist = get_stock(context)
        #print(Buylist)
        if len(Buylist)>g.stocknum:
            Buylist=Buylist[:g.stocknum]
        ## 卖出
        if len(context.portfolio.positions) > 0:
            for stock in context.portfolio.positions.keys():
                if stock not in Buylist:
                    order_target(stock, 0)
        buy_count=len(Buylist)
        hold_count=len(context.portfolio.positions)
        to_buy_count=buy_count-hold_count#需要买的票数量
        ## 分配资金
        if to_buy_count>0:
            Cash = context.portfolio.cash/to_buy_count
        else: 
            Cash = 0
        
        
        ## 买入
        if len(Buylist) > 0:
            for stock in Buylist:
               if stock not in context.portfolio.positions.keys():
                   order_value(stock,Cash)

    # 止损
def stop_loss(context):
    c=history(10,security_list=['399300.XSHE'])
    c1=c['399300.XSHE'][-1]
    c2=c['399300.XSHE'][0]
    if c1<c2*0.9:
        for stock in context.portfolio.positions:
            order_target(stock,0)
    #个股低于成本10%的平仓
    for stock in context.portfolio.positions:
        p = context.portfolio.positions[stock]
        if p.price/p.avg_cost < 0.9:
            order_target(stock,0)
#=========================估值分析===============================
#获取当前指数成份股
def get_index_stock(index_code,q_date):
    stocks = get_index_stocks(index_code, q_date)
    return stocks

#获取当前成分股pe(等权,剔除pe<0的股票)
def get_stock_pe(code,q_date):
    stocks = get_index_stocks(code, q_date)
    q = query(valuation).filter(valuation.code.in_(stocks)).filter(valuation.pe_ratio>0)
    df = get_fundamentals(q, q_date)
    if len(df)>0:
        pe = len(df)/sum([1/p if p>0 else 0 for p in df.pe_ratio])
        return pe
    else:
        return float('NaN')
#获取当前成分股pe(市值加权,剔除pe<0的股票)
def get_stock_pe1(code,q_date):
    stocks = get_index_stocks(code, q_date)
    q = query(valuation).filter(valuation.code.in_(stocks)).filter(valuation.pe_ratio>0)
    df = get_fundamentals(q, q_date)
    df['eps']=df.market_cap/df.pe_ratio#单个股票总收益
    marketcap=df.market_cap.sum()
    eps=df.eps.sum()
    if eps>0:
        pe=marketcap/eps
    else:
        pe=float('NaN')
    return pe
#获取指定指数各项估值历史指标
#code:指数
#index:指标
def get_valuation(index,code,start_date,end_date):
    file_name='ETF/PE全.csv'
    body=read_file(file_name)
    df=pd.read_csv(StringIO(body))
    #df=pd.DataFrame.from_csv(file_name)
    #print(df['日期'])
    pe_slice=df[df['日期']>str(start_date)]
    pe_slice=pe_slice[pe_slice['日期']<str(end_date)]
    s=pe_slice[code]
    return list(s)

#获取当前估值分位
#code:指数
#index:指标
#data:要处理的序列
#result:返回结果字典
def get_divid(code,index,start_date,end_date):
    result={}
    data=get_valuation(index,code,start_date,end_date)
    data_now=get_stock_pe(code,end_date)
    data.append(data_now+1)
    s_data=pd.Series(data)
    q_pes = [s_data.quantile(i/10.0)  for i in range(11)]    
    idx = bisect.bisect(q_pes,data_now)
    quantile = idx-(q_pes[idx]-data_now)/(q_pes[idx]-q_pes[idx-1]) 
    result['分位数']=quantile*10
    result['当前估值']=data_now
    return result['分位数']