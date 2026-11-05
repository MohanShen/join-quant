# Clone from JoinQuant
# postId: 9466f6f63aaee5f8ce038dbcc548ee6b
# backtestId: 9b27e6d5f33344862beabe33aafb6fa6
# title: 预期PEG：分析师预测包含了增量信息

# 导入函数库
import jqdata
from six import StringIO
import pandas as pd
from datetime import datetime
# 初始化函数，设定基准等等
def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    log.info('初始函数开始运行且全局只运行一次')

    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    
    run_monthly(selection,1, time='before_open', reference_security='000300.XSHG') 
    run_monthly(rebalance,1, time='open', reference_security='000300.XSHG')
  
## 开盘前运行函数     
def selection(context):
    scandate = context.previous_date
    print(scandate)
    #读取两年复合增长率预测数据-月底
    body=read_file("NPG2Y_fwd.csv")
    df = pd.read_csv(StringIO(body))
    df.set_index('Date',inplace = True)
    cols = df.columns
    cols_ =[]
    for col in cols:
        if col[0]==6:
            stock = col[:6]+'.XSHG'
        else:
            stock = col[:6]+'.XSHE'
        cols_.append(stock) 
    df.columns = cols_

    df = df[df.index == datetime.strftime(scandate,'%Y-%m-%d')].T
    df = df[(df >0) & (df < 50)]  #不合理的复合预期增长蕴含风险
    df.dropna(inplace = True)
    df.columns = ['npg']

    #提取pe构造peg
    q = query(valuation.code,valuation.pe_ratio,valuation.ps_ratio,indicator.adjusted_profit,indicator.inc_net_profit_to_shareholders_year_on_year).filter(valuation.code.in_(df.index.tolist()))
    _df = get_fundamentals(q, scandate)
    _df.set_index('code',inplace = True)
    df = pd.concat([df,_df],axis = 1,join ='inner')
    df['peg'] = df['pe_ratio']/df['npg']
    #df['peg_r'] = df['pe_ratio']/df['inc_net_profit_to_shareholders_year_on_year']
    
    df = df[(df['pe_ratio'] < 30) & (df['ps_ratio'] < 3)]
    df = df[df['peg'] > 0]
    df.sort('peg',ascending = True,inplace = True)
    print(df.head(20))
    
    stocklist = df.index.tolist()
    #过滤停牌/st
    cur_date = get_current_data()
    stocklist = [stock for stock in stocklist if (not cur_date[stock].is_st) and (not cur_date[stock].paused)]
    print('stocklist:',len(stocklist))
    context.buylist = stocklist[:10]
    
def rebalance(context):
    cur_data = get_current_data()
    buylist_tradable = [stock for stock in context.buylist if not (cur_data[stock].paused or cur_data[stock].day_open >cur_data[stock].high_limit*0.985)]
    
    print(len(buylist_tradable))
    if  len(buylist_tradable) != 0:
        weight = 1.00/len(buylist_tradable)

    for stock in context.portfolio.positions.keys():
        if stock not in context.buylist:
            order_target(stock,0)
            
    t_value = 0.99*context.portfolio.total_value
    for stock in buylist_tradable:
        order_target_value(stock,weight*t_value)
   
