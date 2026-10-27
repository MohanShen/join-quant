# Clone from JoinQuant
# postId: 3ecb22c55ea4e64a38005f498d4fc731
# backtestId: 486768c49d3e89b0ac6c9c4e23400f47
# title: 查尔斯·布兰德斯价值投资策略

# 导入聚宽函数库
import jqdata
from jqdata import gta
import pandas as pd
import time

# 初始化函数，设定基准等等
def initialize(context):
    g.stocks = list(get_all_securities(['stock']).index)
   
def handle_data(context, data):
    
    now=context.current_dt.strftime("%m-%d")
    if (now=="04-01" or now=="07-01" or now=="10-01" or now=="01-01"):
        
 
        
        df = get_fundamentals(query(
             valuation.code,balance.total_liability,
             balance.total_owner_equities,valuation.pe_ratio,
             valuation.pb_ratio,valuation.pcf_ratio
             ).filter(
             valuation.code.in_(g.stocks)
             ).order_by(
             valuation.code
             ))
        
        avg_pe=sum(df['pe_ratio'])/len(df['pe_ratio'])
        avg_pb=sum(df['pb_ratio'])/len(df['pb_ratio'])
        avg_pcf=sum(df['pcf_ratio'])/len(df['pcf_ratio'])

        
    
        scores_=[]
        for i in df.index:
            scores=0
            tmp=df['total_liability'][i]/df['total_owner_equities'][i]
            if(tmp<0.8):
                scores=scores+1
            
            if(df['pe_ratio'][i]<=(avg_pe*1.5)):
                scores=scores+1
                
            if(df['pcf_ratio'][i]<=(avg_pcf*1.5)):
                scores=scores+1
        
            if(df['pb_ratio'][i]<=(avg_pb*1.5)):
                scores=scores+1
            
            if(df['pb_ratio'][i]<2):
                scores=scores+1
            
                    
            scores_.append(scores)
            
        df['scores']=scores_
        
        selected_stocks=[]
        for i in df.index:
            if(df['scores'][i]==5):
                selected_stocks.append(df['code'][i])
        
        cash=context.portfolio.cash
        for i in g.stocks:
            if i in selected_stocks:
                order_value(i,cash/len(selected_stocks))
            if i not in selected_stocks:
                order_target(i,0)
                
        