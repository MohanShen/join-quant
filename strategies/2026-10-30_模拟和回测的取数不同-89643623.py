# Clone from JoinQuant
# postId: 89643623da402bd0bf1c7ca4dce6072a
# backtestId: 00a084b51690ed6f4cdff0f842f31014
# title: 模拟和回测的取数不同？

from jqfactor import get_factor_values
from pandas.core.frame import DataFrame
import pandas as pd
from jqdata import *
def initialize(context):
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('history', 'error')
    set_option('use_real_price', True)
    g.stocks = []
    g.just_sold = []
    g.stock_num =8
    run_daily(prepare_stock_list,'9:15')
    run_daily(daily_my_Trader,'9:26')
    run_monthly(my_Trader, 1 ,'9:30') 
    run_monthly(go_Trader, 1 ,'9:30') 
    run_daily(check_limit_up_and_buy,'14:00')
    g.order_info_dict = {}
    run_daily(print_position_info, '15:10')
    g.previous_portfolio_value = context.portfolio.starting_cash
#1-1 根据最近一年分红除以当前总市值计算股息率并筛选    
def get_dividend_ratio_filter_list(context, stock_list, sort, p1, p2):
    time1 = context.previous_date
#    time0 = time1 - datetime.timedelta(days=365)
    time0=datetime.date(time1.year-1,time1.month,1)
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
    dividend = dividend.groupby('code').sum()
    temp_list = list(dividend.index) #query查询不到无分红信息的股票，所以temp_list长度会小于stock_list
    #获取市值相关数据
    q = query(valuation.code,valuation.market_cap).filter(valuation.code.in_(temp_list))
    cap = get_fundamentals(q, date=time1)
    cap = cap.set_index('code')
    #计算股息率
    DR = pd.concat([dividend, cap] ,axis=1, sort=False)
    DR['dividend_ratio'] = (DR['bonus_amount_rmb']/10000) / DR['market_cap']
    #排序并筛选
    DR = DR.sort_values(by=['dividend_ratio'], ascending=sort)
    final_list = list(DR.index)[int(p1*len(DR)):int(p2*len(DR))]
    return final_list
def daily_my_Trader(context):
    # all stocks
    dt_last = context.previous_date
    stocks = get_all_securities('stock', dt_last).index.tolist()
    stocks = filter_kcbj_stock(stocks)
    print('科创北交过滤后还剩: %s' % len(stocks))
     #高股息(全市场最大25%)
    stocks = get_dividend_ratio_filter_list(context, stocks, False, 0, 0.25)
    stocks = get_peg(context,stocks)
    print('股息和基本面过滤后还剩: %s' % len(stocks))
    stocks = filter_all_stock(context, stocks)
    print('ST、停牌、涨跌停过滤后还剩: %s' % len(stocks))
    stocks = filter_highprice_stock(context,stocks)
    print('大于9元过滤后还剩: %s' % len(stocks))
    g.stocks = stocks[:g.stock_num] #选前前N只票
    log.info("——————————————————————————————————")
    for i, stock in enumerate(stocks):
        rank = i + 1
        name = get_security_info(stock).display_name
        print("今日股票池第 {}：{} {}".format(rank,stock,name))
        if i > 20:
            break
    log.info("——————————————————————————————————")
def my_Trader(context):
    # all stocks
    dt_last = context.previous_date
    stocks = get_all_securities('stock', dt_last).index.tolist()
    stocks = filter_kcbj_stock(stocks)
     #高股息(全市场最大25%)
    stocks = get_dividend_ratio_filter_list(context, stocks, False, 0, 0.25)
    stocks = get_peg(context,stocks)
    stocks = filter_all_stock(context, stocks)
    stocks = filter_highprice_stock(context,stocks)
    g.stocks = stocks[:g.stock_num] #选前前N只票

def go_Trader(context):
    g.just_sold = []  # 每月清零一次 g.just_sold 防止其中内容一直膨胀
    cdata = get_current_data()
    stocks = g.stocks
    # Sell
    for s in context.portfolio.positions:
        if s not in stocks:
            log.info('Sell', s, cdata[s].name)
            order_target(s, 0)  # 如果跌停怎么办？
            g.just_sold.append(s)  # 将卖出的股票添加到 g.just_sold 列表中
    # buy
    position_count = len(context.portfolio.positions)
    if g.stock_num > position_count:
        psize = context.portfolio.available_cash / (g.stock_num - position_count)
        for s in stocks:
            if s not in context.portfolio.positions and s not in g.just_sold:
                log.info('buy', s, cdata[s].name)
                order_value(s, psize)  # 这里如果涨停怎么办？
                if len(context.portfolio.positions) == g.stock_num:
                    break
def get_peg(context,stocks):
    df = get_fundamentals(query(valuation.code).filter(valuation.code.in_(stocks),income.np_parent_company_owners > 0,income.net_profit > 0,income.operating_revenue > 1e8,indicator.roe>0,indicator.roa>0).order_by(valuation.market_cap.asc()))
    stocks = list(df.code)
    return stocks
def get_factor_filter_list(context,stock_list,jqfactor,sort,p1,p2):
    yesterday = context.previous_date
    score_list = get_factor_values(stock_list, jqfactor, end_date=yesterday, count=1)[jqfactor].iloc[0].tolist()
    df = pd.DataFrame(columns=['code','score'])
    df['code'] = stock_list
    df['score'] = score_list
    df = df.dropna()
    df.sort_values(by='score', ascending=sort, inplace=True)
    filter_list = list(df.code)[int(p1*len(df)):int(p2*len(df))]
    return filter_list
# 准备股票池
def prepare_stock_list(context):
    #获取已持有列表
    g.high_limit_list = []
    hold_list = list(context.portfolio.positions)
    if hold_list:
        df = get_price(hold_list, end_date=context.previous_date, frequency='daily',
                       fields=['close', 'high_limit'],
                       count=1, panel=False)
        g.high_limit_list = df[df['close'] == df['high_limit']]['code'].tolist()
#  调整昨日涨停股票
def check_limit_up_and_buy(context):
     # 获取持仓的昨日涨停列表
    current_data = get_current_data()
    if g.high_limit_list:
        for stock in g.high_limit_list:
            if current_data[stock].last_price < current_data[stock].high_limit:
                log.info("[%s]涨停打开，卖出" % stock)
                dt_last = context.previous_date
                stocks = get_all_securities('stock', dt_last).index.tolist()
                order_target(stock, 0)
                g.just_sold.append(stock) 
                #过滤掉刚刚卖掉的股票
                stocks = filter_kcbj_stock(stocks)
                 #高股息(全市场最大25%)
                stocks = get_dividend_ratio_filter_list(context, stocks, False, 0, 0.25)
                stocks = get_peg(context,stocks)
                stocks = filter_all_stock(context, stocks)
                stocks = filter_highprice_stock(context,stocks)
                stocks = filter_buyagain(stocks)
                g.stocks = stocks[:g.stock_num] #选前前N只票
                cdata = get_current_data()
                # buy
                position_count = len(context.portfolio.positions)
                if g.stock_num > position_count:
                    psize = context.portfolio.available_cash/(g.stock_num - position_count)
                    for s in stocks:
                        if s not in context.portfolio.positions:
                            log.info('buy', s, cdata[s].name)
                            order_value(s, psize)
                            if len(context.portfolio.positions) == g.stock_num:
                                break
            else:
                log.info("[%s]涨停，继续持有" % stock)
def filter_buyagain(stock_list):
    return [stock for stock in stock_list if stock not in g.just_sold]
# 过滤科创北交股票
def filter_kcbj_stock(stock_list):
    for stock in stock_list[:]:
        if stock[0] == '4' or stock[0] == '8' or stock[:2] == '68':
            stock_list.remove(stock)
    return stock_list
def filter_all_stock(context, stocks):
    curr_data = get_current_data()
    return [stock for stock in stocks if not (
#           stock.startswith(('3', '68', '4', '8')) or  # 创业，科创，北交所
            curr_data[stock].paused or
            curr_data[stock].is_st or  # ST
            ('ST' in curr_data[stock].name) or
            ('*' in curr_data[stock].name) or
            ('退' in curr_data[stock].name) or
            (curr_data[stock].day_open == curr_data[stock].high_limit) or  # 涨停开盘, 其它时间用last_price
            (curr_data[stock].day_open == curr_data[stock].low_limit) or # 跌停开盘, 其它时间用last_price
            (curr_data[stock].last_price == curr_data[stock].high_limit) or  # 涨停开盘, 其它时间用last_price
            (curr_data[stock].last_price == curr_data[stock].low_limit)  # 跌停开盘, 其它时间用last_price
    )]
#2-4 过滤股价高于9元的股票	
def filter_highprice_stock(context,stock_list):
	last_prices = history(1, unit='1m', field='close', security_list=stock_list)
	return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
			or last_prices[stock][-1] < 9]
def print_position_info(context):
    log.info("——————————————————————————————————")
    print('证券名称\t买入日期\t买入价格\t现价\t持仓收益率')
    for position in list(context.portfolio.positions.values()):
        security = position.security
        name = get_security_info(security).display_name
        order_info = {}
        order_info['security'] = name
        order_info['买入日期'] = position.init_time.date()
        order_info['买入价格'] = position.avg_cost
        order_info['现价'] = position.price
        order_info['持仓收益率'] = (position.price / position.avg_cost - 1) * 100
        key = '{}:{}'.format(order_info['买入日期'], name)
        g.order_info_dict[key] = order_info
        print('{:<0}\t{}\t{:.2f}\t{:.2f}\t{:.2f}%'.format(
            order_info['security'],
            order_info['买入日期'],
            order_info['买入价格'],
            order_info['现价'],
            order_info['持仓收益率']
        ))
    log.info("——————————————————————————————————")
    # 计算累计总收益率
    g.total_return_rate = (context.portfolio.portfolio_value - context.portfolio.starting_cash) / context.portfolio.starting_cash * 100
    print('累计收益率={:.2f}%'.format(g.total_return_rate))
    
    # 计算并输出今日持仓收益率
    if g.previous_portfolio_value:
        daily_return_rate = (context.portfolio.portfolio_value / g.previous_portfolio_value - 1) * 100
        print('今日收益率={:.2f}%'.format(daily_return_rate))
    
    # 保存当前的投资组合价值以供下次计算使用
    g.previous_portfolio_value = context.portfolio.portfolio_value

    log.info("——————————————————————————————————")