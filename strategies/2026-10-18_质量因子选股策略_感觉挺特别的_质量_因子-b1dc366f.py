# Clone from JoinQuant
# postId: b1dc366fa1833e452009afb11e2018b0
# backtestId: 762f921cfb622de0e05949bdbd8776b2
# title: 质量因子选股策略~（感觉挺特别的“质量”因子）

# 导入聚宽函数库
import jqdata

# 初始化函数，设定基准等等
def initialize(context):
   list1 = list(get_index_stocks('000001.XSHG',date='2016-10-15'))
   list2 = list(get_index_stocks('000001.XSHG',date='2015-10-15'))
   list3 = list(get_index_stocks('000001.XSHG',date='2014-10-15'))
   list4 = list(get_index_stocks('000001.XSHG',date='2013-10-15'))
   list5 = list(get_index_stocks('000001.XSHG',date='2012-10-15'))
   list6 = list(get_index_stocks('000001.XSHG',date='2011-10-15'))
   list7 = list(get_index_stocks('000001.XSHG',date='2010-10-15'))
   list8 = list(get_index_stocks('000001.XSHG',date='2009-10-15'))
   list9 = list(get_index_stocks('000001.XSHG',date='2008-10-15'))
   list10 = list(get_index_stocks('000001.XSHG',date='2007-10-15'))
   list11 = list(get_index_stocks('000001.XSHG',date='2006-10-15'))
   g.stocks=list(set(list(set(list(set(list(set(list(set(list(set(list(set(list(set(list(set(list(set(list1).intersection(set(list2)))).intersection(set(list3)))).intersection(set(list4)))).intersection(set(list5)))).intersection(set(list6)))).intersection(set(list7)))).intersection(set(list8)))).intersection(set(list9)))).intersection(set(list10)))).intersection(set(list11)))
   
   

def handle_data(context, data):
    
    df = get_fundamentals(query(
             valuation.code,balance.total_assets,balance.total_liability,
             balance.longterm_loan,balance.longterm_account_payable,balance.bonds_payable,
             income.net_profit
             ).filter(
             valuation.code.in_(g.stocks)
             ).order_by(
             valuation.code
             ))
    
    prev_time=[]         
    for i in range(1,11):
        prev_time.append(str(context.current_dt.year-i) )    
   
    prev_net_profit=[]
    for i in prev_time:
        h = get_fundamentals(query(
        valuation.code,income.net_profit
        ).filter(
        valuation.code.in_(g.stocks)
        ).order_by(
        valuation.code
        ),statDate=i)
        # print h
        df[str(i)]=h['net_profit']
    # df  
    
    scores_=[]
    
    for i in df.index:
        scores=0
        if(df['total_assets'][i]>2*df['total_liability'][i]):
            scores=scores+1
            
        WCAP=df['total_assets'][i]-df['total_liability'][i]
        DLTT=df['longterm_loan'][i]+df['longterm_account_payable'][i]+df['bonds_payable'][i]
        if(WCAP>DLTT):
            scores=scores+1
            
        if(df['2015'][i]>0 and df['2014'][i]>0 and df['2013'][i]>0 and df['2012'][i]>0 and df['2011'][i]>0 and df['2010'][i]>0 and df['2009'][i]>0 and df['2008'][i]>0 and df['2007'][i]>0 and df['2006'][i]>0):
            scores=scores+1
        
        diff=(df['net_profit'][i]-df['2006'])/df['2006']-1    
        if(diff.iloc[0]>0.33):
            scores=scores+1
          
        scores_.append(scores)
    df['scores']=scores_
    
    df=df.sort(columns='scores',ascending=False)
   
    best=df[:235]['code'].values
    worst=df[-235:]['code'].values
    
    cash=context.portfolio.cash
        
    for i in best:
        order_value(i,cash/235)
    for i in worst:
        order_target(i,0)
        
        
        
        
        