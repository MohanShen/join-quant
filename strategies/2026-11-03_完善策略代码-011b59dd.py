# Clone from JoinQuant
# postId: 011b59ddb5dabde78fe845133afc85ea
# backtestId: e1780277750cad795684859fe5fc9bae
# title: 完善策略代码

import pandas as pd

def initialize(context):
    # setting
    log.set_level('order', 'error')
    set_option('use_real_price', True)
    set_benchmark('000905.XSHG')
    # strategy
    g.stock_num = 10
    run_daily(prepare_stock_list, time='9:05', reference_security='000300.XSHG')
    run_monthly(my_Trader, 1 ,time='9:30')
    run_daily(check_limit_up, time='14:00')

def sorted_by_circulating_market_cap(stock_list, n_limit_top=5):
    q = query(
        valuation.code,
    ).filter(
        valuation.code.in_(stock_list),
        #indicator.eps > 0, #税后每股收益
        #indicator.roe > 0, #roe
        #indicator.roa > 0, #roa
        #indicator.inc_revenue_year_on_year>8, #年营收增长大于8%,add by 2022/1/6
    ).order_by(
        valuation.circulating_market_cap.asc()
    ).limit(
        n_limit_top
    )
    return get_fundamentals(q)['code'].tolist()

                
def my_Trader(context):
    # all stocks
    dt_last = context.previous_date
    stocks = get_all_securities('stock', dt_last).index.tolist()
    # filter, ST
    stocks = filter_kcbj_stock(stocks)
    stocks = filter_st_stock(stocks)
    # fuandamental data
    df = get_fundamentals(query(
            valuation.code,
            valuation.pb_ratio,
            indicator.inc_return,
            indicator.inc_total_revenue_year_on_year,
            indicator.inc_net_profit_year_on_year,
            indicator.ocf_to_operating_profit,
            valuation.market_cap,
            indicator.eps, #税后每股收益
            indicator.roa, 
        ).filter(
            valuation.code.in_(stocks),
            #valuation.pb_ratio > 0,
            indicator.inc_return >0,
            indicator.inc_total_revenue_year_on_year>0,
            indicator.inc_net_profit_year_on_year>0,
            indicator.ocf_to_operating_profit>5,
        ).order_by(
            valuation.market_cap.asc()
		).limit(
		    g.stock_num
	    ))
	    
    #df['total_score'] = 0.1 * df['inc_total_revenue_year_on_year'] + 0.35 * df['inc_net_profit_year_on_year'] + 0.15 * df[
    #    'inc_return']  + 0.2 * (1/df['market_cap'])
    #ms_list = df.sort_values(by=['total_score'], ascending=False).index[:int(g.stock_num*1.5)].tolist()
    #ms_list = sorted_by_circulating_market_cap(ms_list,int(g.stock_num))
    #choice = ms_list #list(df.code)
    
    choice = list(df.code)
    print('选股数量：',len(choice))
    # Sell
    for s in context.portfolio.positions:
        if (s  not in choice) and (s not in g.high_limit_list):
            order_target(s, 0)
    # buy
    psize = 1.0/g.stock_num * context.portfolio.total_value
    for s in choice:
        if context.portfolio.available_cash < psize:
            break
        if s not in context.portfolio.positions:
            order_value(s, psize)
            

#1-3 准备股票池
def prepare_stock_list(context):
    #获取已持有列表
    g.high_limit_list = []
    hold_list = list(context.portfolio.positions)
    if hold_list:
        df = get_price(hold_list, end_date=context.previous_date, frequency='daily',
                       fields=['close', 'high_limit', 'paused'],count=1)
        
        pa=pd.DataFrame(index=df['close'].T.index,columns=[])
        pa['close']=df['close'].T
        pa['high_limit']=df['high_limit'].T
        pa['paused']=df['paused'].T
        pa['code']=df['close'].T.index
        #print(111,pa)               
        g.high_limit_list = pa.query('close==high_limit and paused==0')['code'].tolist()
        
# 1-5 调整昨日涨停股票
def check_limit_up(context):
     # 获取持仓的昨日涨停列表
    current_data = get_current_data()
    if g.high_limit_list:
        for stock in g.high_limit_list:
            if current_data[stock].last_price < current_data[stock].high_limit:
                log.info("[%s]涨停打开，卖出" % stock)
                order_target(stock, 0)
            else:
                log.info("[%s]涨停，继续持有" % stock)
 
 
#2-6 过滤科创北交股票
def filter_kcbj_stock(stock_list):
    for stock in stock_list[:]:
        if stock[0] == '4' or stock[0] == '8' or stock[:2] == '68':
            stock_list.remove(stock)
    return stock_list

# 2-2 过滤ST及其他具有退市标签的股票
def filter_st_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not (
            current_data[stock].is_st or
            'ST' in current_data[stock].name or
            '*' in current_data[stock].name or
            '退' in current_data[stock].name)]
            
# end