# Clone from JoinQuant
# postId: d34bfc49fa8e88efd56e1b1be28f1955
# backtestId: 01c4802358350122ded6a65bc4f82164
# title: 低回撤投资

from __future__ import division 

def initialize(context):
    set_benchmark('000001.XSHG')
    g.CN10y_bond=0.03
    g.Test_index='159912.XSHE'      #pour acheter les actions
    g.Test_bond='511210.XSHG'       #pour acheter les bonds
    g.HoldLevel=0
    g.LastHoldLevel=0
    g.cal_pe_index='399300.XSHE'        #pour calculer le ratio PE
    
    g.MaxRatio=4        
    g.MinRatio=2
    
    g.MinHoldLevel=0
    g.MaxHoldLevel=1

def Relation(n):
    if n>g.MaxRatio:
        g.HoldLevel=g.MaxHoldLevel
    elif (n<g.MinRatio):
        g.HoldLevel=g.MinHoldLevel
    else:
        k=(g.MaxHoldLevel-g.MinHoldLevel)/(g.MaxRatio-g.MinRatio)
        b=g.MaxHoldLevel-g.MaxRatio*k
        g.HoldLevel=k*n+b
    #Debug:
    #print 'k=(' +str(g.MaxHoldLevel)+'-'+str(g.MinHoldLevel) + ')/' +\
    #'('+str(g.MaxRatio)+'-'+str(g.MinRatio)+')'+' = '+str(k)
    #print 'HoldLevel=' +str(k) + '*N' + '+' +str(b)
   
def PeRatio(date):#Calculer le ratio PE pour index
    code=g.cal_pe_index
    stocks = get_index_stocks(code, date)
    q = query(valuation,income).filter(valuation.code.in_(stocks))
    df = get_fundamentals(q, date)
    sum_p = 0
    sum_e = 0
    pe2=0
    for i in range(0, len(df)):
        sum_p = sum_p + df['market_cap'][i]
        sum_e = sum_e +  df['market_cap'][i] / df['pe_ratio'][i]
        if sum_e > 0:
            pe2 = sum_p / sum_e
        else:
            pe2 = float('NaN')
    #pe2='%.2f'%pe2
    return pe2
    
def ChangeHoldLevel(NewHoldLevel,AllMoney):
    order_target_value(g.Test_index,NewHoldLevel*AllMoney,None)
    order_target_value(g.Test_bond,(1-NewHoldLevel)*AllMoney,None)

def handle_data(context, data):
    if context.current_dt.isoweekday()!=1:      #ne Marcher que Lundi. 
        return
    N= (1/PeRatio(get_current_data()))/g.CN10y_bond
    Relation(N)
    ChangeHoldLevel(g.HoldLevel,context.portfolio.total_value)
    print 'PE:%.2f'%N
    print g.HoldLevel
    
    record(name=g.HoldLevel)
