# Clone from JoinQuant
# postId: 3fc17a2b6143772e0a54c295596c234e
# backtestId: 2d1873a0d611b93a2a87a10820245615
# title: 场外基金回测时的问题

# 导入函数库
from jqdata import *
import time
# 初始化函数，设定基准等等
def initialize(context):
    init_cash = context.portfolio.starting_cash
    set_subportfolios([SubPortfolioConfig(cash=init_cash, type='open_fund')])
    run_daily(calculate, time='every_bar')
    g.flag=False
    
def calculate(context):
    #print(context.current_dt.strftime("%Y-%m-%d"))
    '''stks=get_index_stocks('399922.XSHE', context.current_dt)
    q=query(valuation.day,valuation.code,valuation.pe_ratio).filter(valuation.code.in_(stks))
    res=get_fundamentals(q,context.current_dt)
    res1=res.sort(['pe_ratio'])
    res2=res1.iloc[10:90,2:3].mean()
    text=context.current_dt.strftime("%Y-%m-%d")+','+str(res2['pe_ratio'])+'\r\n'
    write_file('pe_399922.csv', text, append=True)
    print(text)'''
    m_lase=context.previous_date.strftime("%m")
    m_now=context.current_dt.strftime("%m")
    #如果上一个交易日的月份不等于当前交易日的月份则
    #将g.flag更新为False，表示还没有进行定投
    if m_lase!=m_now:
        g.flag=False
    d_now=context.current_dt.strftime("%d")
    if (g.flag==False) and (int(d_now)>5):
        g.flag=True
        print(context.current_dt.strftime("%Y-%m-%d"))
        #res=get_extras('unit_net_value', ['100032.OF'], start_date='2009-01-23', end_date='2009-01-24')
        #print res
        purchase('100032.OF', 1000)
        