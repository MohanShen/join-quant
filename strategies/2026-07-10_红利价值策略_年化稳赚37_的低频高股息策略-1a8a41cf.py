# Clone from JoinQuant
# postId: 1a8a41cf1a02b3e95414344931d866d4
# backtestId: 9d40ebfb2a5a77f183411716b0479c34
# title: 红利价值策略：年化稳赚37%的低频高股息策略

import pandas as pd
from jqdata import *


# 初始化函数 
def initialize(context):
    
    # 系统设置
    set_option("avoid_future_data", True)
    set_option('use_real_price', True)
    set_benchmark('000015.XSHG')
    # 将滑点设置为0.005
    set_slippage(FixedSlippage(0.005))
    # 设置交易成本万分之三
    set_order_cost(OrderCost(open_tax=0, close_tax=0.0005, open_commission=0.0003, close_commission=0.0003, close_today_commission=0, min_commission=5),type='fund')
    # 过滤order中低于error级别的日志
    
    log.set_level('order', 'error')
    log.set_level('history', 'error')
    log.set_level('system', 'error')
    
    # 全局变量
    g.sell_list = []
    g.buy_df = []
    g.stock_num = 5
    g.high_limit_list = []
    g.strategy = 'hongli'
    g.filename = '红利增强.csv' #入金配置文件名称

    g.first = 1
    g.out_cash = 0

    # 交易时间
    run_daily(prepare_stock_list, '09:00')
    run_monthly(get_stock_list, 1, '09:01')
    run_monthly(my_trade, 1 ,'09:30')
    run_daily(check_limit_up, '10:00')
    
    
# 准备股票池
def prepare_stock_list(context):
    
    # 获取昨日涨停列表
    g.high_limit_list = []
    g.hold_list = list(context.portfolio.positions)
    if len(g.hold_list) != 0:
        df = get_price(g.hold_list, end_date=context.previous_date, frequency='daily', fields=['close','high_limit'], count=1, panel=False, fill_paused=False, skip_paused=False).dropna()
        df = df[df['close'] == df['high_limit']]
        g.high_limit_list = list(df.code)


# 选股
def get_stock_list(context):
    
    # 基础信息
    g.buy_df = pd.DataFrame(index=[], columns=[ 'name', 'price', 'amount', 'value'])
    yesterday = str(context.previous_date)
    today = context.current_dt
    
    # 初始过滤
    initial_list = get_all_securities('stock', today).index.tolist()
    initial_list = filter_new_stock(context,initial_list)
    initial_list = filter_kcb_stock(initial_list)
    initial_list = filter_st_stock(initial_list)
    initial_list = filter_paused_stock(initial_list)
    
    
    # 红利价值
    stock_list = initial_list
    df = get_fundamentals(query(
            valuation.code,
        ).filter(
            valuation.code.in_(stock_list),
            #合理的财务指标，既避免价值陷阱，也防止畸高收益
            valuation.pe_ratio.between(5, 50), #市盈率
            indicator.inc_return.between(5, 100), #净资产收益率(扣除非经常损益)(%)
            indicator.inc_total_revenue_year_on_year.between(5, 100), #营业总收入同比增长率(%)
            indicator.inc_net_profit_year_on_year.between(10, 100), #净利润同比增长率(%)
        ))
    stock_list = list(df.code)
    stock_list = get_dividend_ratio_filter_list(context, stock_list, False, 0.00, 0.10, 0.03) #股息率最高的几只
    target_list = stock_list[:min(g.stock_num, len(stock_list))]
    
    g.sell_list = [s for s in g.hold_list if s not in target_list and s not in g.high_limit_list]
    buy_list = [s for s in target_list if s not in g.hold_list]
    
    #计算下单价格与数量
    value = context.portfolio.available_cash
    if len(g.sell_list) > 0:
        for s in g.sell_list:
            value += context.portfolio.positions[s].value
    
    if len(buy_list) > 0:
        value = value/len(buy_list)
        df = get_price(buy_list, end_date=yesterday, frequency='1d', count=1, fields=['close'], fq='pre', panel=False, skip_paused=False, fill_paused=True).set_index('code')
        df['today_hl_price'] = [0]*len(df)
        for s in list(df.index):
            if ((s[0] == '3') and (str(context.current_dt)[:10] >= '2020-08-24')):
                df.loc[s, 'today_hl_price'] = round(df.loc[s,'close']*1.05, 2)
            else:
                df.loc[s, 'today_hl_price'] = round(df.loc[s,'close']*1.05, 2)
        g.buy_df['name'] = [get_security_info(s, yesterday).display_name for s in buy_list]
        g.buy_df['price'] = [df.loc[s,'today_hl_price'] for s in buy_list]
        g.buy_df['amount'] = [100 * int(1.05*value / df.loc[s,'today_hl_price'] / 100) for s in buy_list]
        g.buy_df['value'] = g.buy_df['price'] * g.buy_df['amount']
        g.buy_df.index = buy_list

    #盘前打印
    print('卖出', g.sell_list)
    print('———————————————————————————————————')
    print('红利低波', g.buy_df)
    print('———————————————————————————————————')


# 交易
def my_trade(context):
    
    #基础信息，获取当前单位时间（当天/当前分钟）的涨跌停价, 是否停牌，当天的开盘价等。
    current_data = get_current_data()
    
    #卖出
    for s in g.sell_list:
        if current_data[s].last_price < current_data[s].high_limit:
            order_target_value(s, 0)
    
    #买入
    df = g.buy_df
    for s in list(df.index):
        print('买入', [s, df.loc[s,'name']])
        order(s, df.loc[s,'amount'], LimitOrderStyle(df.loc[s, 'price']))
        print('———————————————————————————————————')


# 调整昨日涨停股票
def check_limit_up(context):
    current_data = get_current_data()
    
    #对昨日涨停股票观察到尾盘如不涨停则提前卖出，如果涨停即使不在应买入列表仍暂时持有
    if g.high_limit_list != []:
        for s in g.high_limit_list:
            if current_data[s].last_price < current_data[s].high_limit:
                order_target_value(s, 0)
                print(s, '涨停打开，卖出')
                print('———————————————————————————————————')
            else:
                print(s, '涨停，继续持有')
                print('———————————————————————————————————')


############################################################################################################################################################################

# 过滤函数
def filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]

def filter_st_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list
            if not current_data[stock].is_st
            and 'ST' not in current_data[stock].name
            and '*' not in current_data[stock].name
            and '退' not in current_data[stock].name]

def filter_kcb_stock(stock_list):
    return [stock for stock in stock_list  if ((stock[0] != '4') and (stock[0] != '8') and (stock[0:2] != '68'))]

def filter_new_stock(context, stock_list):
    yesterday = context.previous_date
    return [stock for stock in stock_list if not yesterday - get_security_info(stock).start_date < datetime.timedelta(days=250)]

# 根据最近一年分红除以当前总市值计算股息率并筛选    
def get_dividend_ratio_filter_list(context, stock_list, sort, p1, p2, threshold):
    time1 = context.previous_date
    time0 = time1 - datetime.timedelta(days=365)
    #获取分红数据，由于finance.run_query最多返回4000行，以防未来数据超限，最好把stock_list拆分后查询再组合
    interval = 1000 #某只股票可能一年内多次分红，导致其所占行数大于1，所以interval不要取满4000
    list_len = len(stock_list)
    #截取不超过interval的列表并查询
    q = query(finance.STK_XR_XD.code, finance.STK_XR_XD.a_registration_date, finance.STK_XR_XD.bonus_amount_rmb
    ).filter(
        finance.STK_XR_XD.a_registration_date >= time0,
        finance.STK_XR_XD.a_registration_date <= time1,
        finance.STK_XR_XD.code.in_(stock_list[:min(list_len, interval)]))
    df = finance.run_query(q)
    #对interval的部分分别查询并拼接
    if list_len > interval:
        df_num = list_len // interval
        for i in range(df_num):
            q = query(finance.STK_XR_XD.code, finance.STK_XR_XD.a_registration_date, finance.STK_XR_XD.bonus_amount_rmb
            ).filter(
                finance.STK_XR_XD.a_registration_date >= time0,
                finance.STK_XR_XD.a_registration_date <= time1,
                finance.STK_XR_XD.code.in_(stock_list[interval*(i+1):min(list_len,interval*(i+2))]))
            temp_df = finance.run_query(q)
            df = df.append(temp_df)
    dividend = df.fillna(0)
    dividend = dividend.set_index('code')
    dividend = dividend.groupby('code').sum()
    temp_list = list(dividend.index) #query查询不到无分红信息的股票，所以temp_list长度会小于stock_list
    #获取市值相关数据
    q = query(valuation.code,valuation.market_cap).filter(valuation.code.in_(temp_list))
    cap = get_fundamentals(q, date=time1)
    cap = cap.set_index('code')
    #计算股息率
    df = pd.concat([dividend, cap] ,axis=1, sort=False)
    df['dividend_ratio'] = (df['bonus_amount_rmb']/10000) / df['market_cap']
    #排序并筛选
    df = df.sort_values(by=['dividend_ratio'], ascending=sort)
    df = df[int(p1*len(df)):int(p2*len(df))]
    df = df[df['dividend_ratio'] > threshold]
    return list(df.index)


def another_trade(context):
    #获取选股列表并过滤掉:st,st*,退市,涨停,跌停,停牌  
    check_out_list = get_stock_list(context)  
    check_out_list = filter_limitup_stock(context, check_out_list)  
    check_out_list = filter_limitdown_stock(context, check_out_list)  
    check_out_list = filter_paused_stock(check_out_list)  
    #check_out_list = filter_highprice_stock(context,check_out_list)
    rank = check_out_list[:g.rank] 
    buy_stocks = check_out_list[:g.stock_num]  
    print('今日自选股:{}'.format(buy_stocks))  

    for stock in list(context.portfolio.positions.keys()):
        if (stock not in rank) and (stock not in g.high_limit_list):
            order_target_value(stock, 0) 
  
    # 根据股票数量分仓  
    # 此处只根据可用金额平均分配购买，不能保证每个仓位平均分配  
    position_count = len(context.portfolio.positions)  
    if g.stock_num > position_count:  
        value = (context.portfolio.cash+g.out_cash) / (g.stock_num - position_count)  
        for stock in buy_stocks:  
            if context.portfolio.positions[stock].total_amount == 0:  
                order_target_value(stock, value)
