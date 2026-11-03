# Clone from JoinQuant
# postId: 29a5e6079fd582bf61745caa58e34ac1
# backtestId: d086b50b36e1a31cf61d3a8fa461dcbf
# title: 为什么取MAC60指定值的股票为0？

#导入函数库
from jqdata import *
from jqfactor import get_factor_values
import numpy as np
import pandas as pd

#初始化函数 
def initialize(context):
    # set_benchmark('000905.XSHG')
    set_benchmark('000300.XSHG')
    # 用真实价格交易
    set_option('use_real_price', True)
    # 打开防未来函数
    set_option("avoid_future_data", True)
    # 将滑点设置为0
    set_slippage(FixedSlippage(0))
    # 设置交易成本万分之三
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003, close_today_commission=0, min_commission=5),type='fund')
    # 过滤order中低于error级别的日志
    log.set_level('order', 'error')
    #选股参数
    g.stock_num = 5 #持仓数
    g.watch_days = 61 #观察大跌已经持续几天，需要不小于2
    g.sold_stock = {} # 近期卖出的股票及卖出天数
    # 设置交易时间，每天运行
    run_daily(get_stock_list_twoline, time='09:10', reference_security='000300.XSHG')
    run_daily(my_trade, time='9:30', reference_security='000300.XSHG')
    run_daily(mybuy, '09:35')
    run_daily(print_trade_info, time='15:30', reference_security='000300.XSHG')



#2-1 选股模块
def get_factor_filter_list(context,stock_list,jqfactor,sort,p1,p2):
    yesterday = context.previous_date
    score_list = get_factor_values(stock_list, jqfactor, end_date=yesterday, count=1)[jqfactor].iloc[0].tolist()
    df = pd.DataFrame(columns=['code','score'])
    df['code'] = stock_list
    df['score'] = score_list
    df.dropna(inplace=True)
    df.sort_values(by='score', ascending=sort, inplace=True)
    filter_list = list(df.code)[int(p1*len(stock_list)):int(p2*len(stock_list))]
    return filter_list
    
#2-1 选股模块
def get_factor_filter_list_new(context,stock_list,jqfactor,sort,p1,p2):
    yesterday = context.previous_date
    score_list = get_factor_values(stock_list, jqfactor, end_date=yesterday, count=1)[jqfactor].iloc[0].tolist()
    df = pd.DataFrame(columns=['code','score'])
    df['code'] = stock_list
    df['score'] = score_list
    df.dropna(inplace=True)
    df.sort_values(by='score', ascending=sort, inplace=True)
    # filter_list = list(df[(df.score>p1) & df.score<p2].code)
    filter_list =list(df[(df.score>p1) & (df.score<p2)].code)
    # print('filter_list',df[(df.score>p1) & (df.score<p2)])
    return filter_list

#2-2 选股模块
def get_stock_list_twoline(context):
    stat_date = context.current_dt.strftime('%Y-%m-%d')
    initial_list = get_all_securities().index.tolist()
    # print('initial_list',initial_list)
    # print('len(initial_list)',len(initial_list))
    initial_list = filter_new_stock(context,initial_list)
    # initial_list = filter_kcb_stock(context, initial_list)
    initial_list = filter_st_stock(initial_list)
    print('initial_list2',len(initial_list))
    # print('initial_list2',initial_list)
    # initial_list2=initial_list.copy()
    # print('len(initial_list2)',len(initial_list2))
    
    # 最新收盘价在60日均线和年线之上(前复权)
    initial_list = get_factor_filter_list_new(context,initial_list, 'MAC60', True, 1/1.09, 1)
    # print('initial_list3',initial_list)
    print('initial_list3',len(initial_list))
    initial_list = get_factor_filter_list_new(context,initial_list, 'Price1Y', True, 0, 0.5)
    # print('initial_list4',initial_list)
    print('initial_list4',len(initial_list))
    # 获得40天内有大跌超过5%的个股
    continue_count_df = []
    days_count = g.watch_days
    try:
        initial_list = limit_count(context, initial_list, stat_date, days_count)
        # print('initial_list5',initial_list)
        print('len(initial_list5)',len(initial_list))
        # 突破60日均线大阳5%且不是一字涨停
        initial_list=dayangtupo(context,initial_list,40)
        print('initial_list6',initial_list)
        print('len(initial_list6)',len(initial_list))
        # yesterday = context.previous_date
        # score_list1 = get_factor_values(['002947.XSHE'], 'Price1Y', end_date=yesterday, count=1)['Price1Y']
        # print('score_list1',score_list1)
        # 买点：收盘价60日均线附近，至少2天上涨，10根K线不能破60日均线
        initial_list=xiadiebuy(context,initial_list)
        print('len(initial_list7)',len(initial_list))
        context.check_out_list=initial_list
    except:
        context.check_out_list=[]
    


# 60个交易日内有大跌5%的个股，且低于过60日均线当前收盘价大于60日均线且收盘价不大于60日均线的1.09且最近10个交易日收盘价大于60日
def limit_count(context, stock_list, stat_date, watch_days):
    yesterday = context.previous_date
    df = get_price(stock_list, end_date=yesterday, frequency='daily', fields=['close','low_limit'], count=watch_days, panel=False, fill_paused=False)
    df['limit'] = df['low_limit']
    # print('df',df)
    df.index = df.code
    count_list = []
    ma60_list=[]
    factor_data = get_factor_values(securities=stock_list, factors=['MAC60'], start_date=None, end_date=yesterday,count=watch_days)['MAC60']
    # factor_data1 = get_factor_values(securities=stock_list[:1000], factors=['MAC60'], start_date=None, end_date=stat_date,count=watch_days)['MAC60']
    # factor_data2= get_factor_values(securities=stock_list[1000:2000], factors=['MAC60'], start_date=None, end_date=stat_date,count=watch_days)['MAC60']
    # factor_data3 = get_factor_values(securities=stock_list[2000:3000], factors=['MAC60'], start_date=None, end_date=stat_date,count=watch_days)['MAC60']
    # factor_data4 = get_factor_values(securities=stock_list[3000:4000], factors=['MAC60'], start_date=None, end_date=stat_date,count=watch_days)['MAC60']
    # factor_data5 = get_factor_values(securities=stock_list[4000:], factors=['MAC60'], start_date=None, end_date=stat_date,count=watch_days)['MAC60']
    # factor_data_tmp=pd.merge(factor_data1,factor_data2, left_index=True, right_index=True) 
    # factor_data_tmp=pd.merge(factor_data_tmp,factor_data3, left_index=True, right_index=True) 
    # factor_data_tmp=pd.merge(factor_data_tmp,factor_data4, left_index=True, right_index=True) 
    # factor_data_tmp=pd.merge(factor_data_tmp,factor_data5, left_index=True, right_index=True) 
    # factor_data=factor_data_tmp
    # print('factor_data',factor_data)
    for stock in stock_list:
        # df_sub = df.loc[stock]
        df_sub=df[df.code==stock]
        # print('df_sub',df_sub)
        # limit_days = df_sub[df_sub.close==df_sub.limit].close.count()
        limit_days=len(df[df.close.pct_change()<-0.05])
        # print('low_limit',df_sub[df_sub.close==df_sub.low_limit])
        # print('limit_days',limit_days)#获得股票涨停次数
        # ma60=1 if len(factor_data[stock]>1) and list(factor_data[stock])[-1]<1 and (1/list(factor_data[stock])[-1]<1.09)  else 0
        ma60=1 if len(factor_data[stock]>1) and list(factor_data[stock])[-1]<1 and (1/list(factor_data[stock])[-1]<1.09) and (len(factor_data[stock][-10:][factor_data[stock][-10:]>1].dropna())==0) else 0
        count_list.append(limit_days)   
        ma60_list.append(ma60)
    df = pd.DataFrame(columns=['code','count'])
    df['code'] = stock_list
    # print('df',df)
    df['count'] = count_list
    df['ma60']=ma60_list
    df = df.dropna()
    # print('df',df)
    # return list(df[df['count']>0]['code'].values)
    # 收盘价在年线之上
    try:
        stock_list_new=list(df[(df['count']>0) & (df['ma60']>0)].code)
        ss = get_factor_values(securities=stock_list_new, factors=['Price1Y'], start_date=None, end_date=yesterday,count=1)['Price1Y']
        ss=ss[ss>0]
        print('stock_list_new',len(list(ss.dropna(axis=1).columns)))
        return list(ss.dropna(axis=1).columns)
    except:
        return 
    
def dayangtupo(context,stock_list,watch_days):
    stock_list2=[]
    yesterday = context.previous_date
    factor_data = get_factor_values(securities=stock_list, factors=['MAC60'], start_date=None, end_date=yesterday,count=watch_days)['MAC60']
    for stock in stock_list:
        # print('stock',stock)
        for i in range(len(factor_data[stock])-1,0,-1):
    #         print(i)
    #         print('date',factor_data[stock].keys()[i])
            if factor_data[stock][i]>1:
                # print('60日均线值',factor_data[stock][i])
                date_jc=factor_data[stock].keys()[i+1]
                # print('股价上穿的日期',date_jc)
                break
            else:
                continue
        # print('股价上穿的日期2',date_jc)
        try:
            df = get_price(stock, end_date=yesterday, frequency='daily', fields=['close','low','open','high_limit'], count=watch_days, panel=False, fill_paused=False)
        # df
            MAold60=mean(get_price(stock, end_date=date_jc, frequency='daily', fields=['close'], count=60, panel=False, fill_paused=False).close)
            # factor_data['600114.XSHG'].iloc[-2]
            if (df.open[date_jc]>MAold60) &(df.close.pct_change()[date_jc]>0.05) & (df.low[date_jc]!=df.high_limit[date_jc]):
                # print('stock',stock)
                # print('突破60日均线大阳的时间',date_jc)
                # print('突破60日均线的涨幅',df.close.pct_change()[date_jc])
                # print('60日均线',MAold60)
                # print('%s开盘价高于60日均线且上穿60天均线当日大涨且不是一字涨板'%stock)
                stock_list2.append(stock)
            else:
        #         print('%s开盘价低于60日均线或或上穿60天均线当日没有大涨或是一字涨停'%stock)
                pass
        except:
            continue
    return stock_list2
    
def xiadiebuy(context,stock_list):
    # stock_list=initial_list
    stock_list2=[]
    for stock in stock_list:
        stock_close=attribute_history(stock, 3, '1d', 'close')
        if (stock_close.close.pct_change()[-1]<0) & (stock_close.close.pct_change()[-2]<0):
            stock_list2.append(stock)
    return stock_list2

#3-1 过滤模块-过滤停牌股票
#输入选股列表，返回剔除停牌股票后的列表
def filter_paused_stock(stock_list):
	current_data = get_current_data()
	return [stock for stock in stock_list if not current_data[stock].paused]

#3-2 过滤模块-过滤ST及其他具有退市标签的股票
#输入选股列表，返回剔除ST及其他具有退市标签股票后的列表
def filter_st_stock(stock_list):
	current_data = get_current_data()
	return [stock for stock in stock_list
			if not current_data[stock].is_st
			and 'ST' not in current_data[stock].name
			and '*' not in current_data[stock].name
			and '退' not in current_data[stock].name]

#3-3 过滤模块-过滤涨停的股票
#输入选股列表，返回剔除未持有且已涨停股票后的列表
def filter_limitup_stock(context, stock_list):
	last_prices = history(1, unit='1m', field='close', security_list=stock_list)
	current_data = get_current_data()
	# 已存在于持仓的股票即使涨停也不过滤，避免此股票再次可买，但因被过滤而导致选择别的股票
	return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
			or last_prices[stock][-1] < current_data[stock].high_limit]

#3-4 过滤模块-过滤跌停的股票
#输入股票列表，返回剔除已跌停股票后的列表
def filter_limitdown_stock(context, stock_list):
	last_prices = history(1, unit='1m', field='close', security_list=stock_list)
	current_data = get_current_data()
	return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
			or last_prices[stock][-1] > current_data[stock].low_limit]

#3-5 过滤模块-过滤科创板
#输入股票列表，返回剔除科创板后的列表
def filter_kcb_stock(context, stock_list):
    return [stock for stock in stock_list  if stock[0:3] != '688']

#3-6 过滤次新股
#输入股票列表，返回剔除上市日期不足250日股票后的列表
def filter_new_stock(context,stock_list):
    yesterday = context.previous_date
    return [stock for stock in stock_list if not yesterday - get_security_info(stock).start_date < datetime.timedelta(days=250)]

#4-1 交易模块-自定义下单
#报单成功返回报单(不代表一定会成交),否则返回None,应用于
def order_target_value_(security, value):
	if value == 0:
		log.debug("Selling out %s" % (security))
	else:
		log.debug("Order %s to value %f" % (security, value))
	# 如果股票停牌，创建报单会失败，order_target_value 返回None
	# 如果股票涨跌停，创建报单会成功，order_target_value 返回Order，但是报单会取消
	# 部成部撤的报单，聚宽状态是已撤，此时成交量>0，可通过成交量判断是否有成交
	return order_target_value(security, value)

#4-2 交易模块-开仓
#买入指定价值的证券,报单成功并成交(包括全部成交或部分成交,此时成交量大于0)返回True,报单失败或者报单成功但被取消(此时成交量等于0),返回False
def open_position(security, value):
	order = order_target_value_(security, value)
	if order != None and order.filled > 0:
		return True
	return False

#4-3 交易模块-平仓
#卖出指定持仓,报单成功并全部成交返回True，报单失败或者报单成功但被取消(此时成交量等于0),或者报单非全部成交,返回False
def close_position(position):
	security = position.security
	order = order_target_value_(security, 0)  # 可能会因停牌失败
	if order != None:
		if order.status == OrderStatus.held and order.filled == order.amount:
			return True
	return False

#4-4 交易模块-调仓
#当择时信号为买入时开始调仓，输入过滤模块处理后的股票列表，执行交易模块中的开平仓操作
def adjust_position(context,hold_stocks):
    # print('buy_stocks2',buy_stocks)
    # log.info("buy_stocks2",buy_stocks)
# 	for stock in context.portfolio.positions:
# 		if stock not in buy_stocks:
# 			log.info("[%s]已不在应买入列表中" % (stock))
# 			position = context.portfolio.positions[stock]
# 			close_position(position)
# 		else:
# 			log.info("[%s]已经持有无需重复买入" % (stock))
# 	# 根据股票数量分仓
# 	# 此处只根据可用金额平均分配购买，不能保证每个仓位平均分配
# 	position_count = len(context.portfolio.positions)
# 	if g.stock_num > position_count:
# 		value = context.portfolio.cash / (g.stock_num - position_count)
# 		for stock in buy_stocks:
# 		  #  log.info("%s" % (stock))
# 		  #  try:
#     #             print('stock2',stock)
#     #         except:
#     #             pass
# 			if context.portfolio.positions[stock].total_amount == 0:
# 				if open_position(stock, value):
# 					if len(context.portfolio.positions) == g.stock_num:
# 						break
    # print('len(context.check_out_list)',len(buy_stocks))

    # if len(buy_stocks)> position_count:
	   # value = context.portfolio.cash / (len(buy_stocks) - position_count)
    # 	for stock in buy_stocks:
    # 		if context.portfolio.positions[stock].total_amount == 0:
    # 			if open_position(stock, value):
    # 				if len(context.portfolio.positions) == len(buy_stocks):
    # 					break
    # for stock in context.portfolio.positions.keys():
    #     # print('stock',stock)
    #     # print("context.portfolio.positions",context.portfolio.positions)
    #     current_data = get_current_data()
    #     # print('current_data[stock].name',current_data[stock].name)
    #     price1d = get_close_price(stock, 1)
    #     nosell_1 = context.portfolio.positions[stock].price >= current_data[stock].high_limit
    #     # print("context.portfolio.positions[stock].price",context.portfolio.positions[stock].price)
    #     # print('current_data[stock].high_limit',current_data[stock].high_limit)
    #     sell_2 = stock not in hold_stocks
    #     if sell_2 and not nosell_1:
    #         close_position(stock)
    # 跌破60日均线及5日均线止损
    for stock in hold_stocks:
        # print('stock',stock)
        # print("context.portfolio.positions",context.portfolio.positions)
        current_data = get_current_data()
        # print('current_data[stock].name',current_data[stock].name)
        price1d = get_close_price(stock, 1)
        nosell_1 = context.portfolio.positions[stock].price >= current_data[stock].high_limit
        # print("context.portfolio.positions[stock].price",context.portfolio.positions[stock].price)
        # print('current_data[stock].high_limit',current_data[stock].high_limit)
        sell_2 = stock in hold_stocks
        if sell_2 and not nosell_1:
            # if stock[0:3] == '688' and stock[0:3] =='689':
            #     # order('688003.XSHG', 200, MarketOrderStyle(200))
            #     order(stock,-context.portfolio.positions[stock].total_amount, MarketOrderStyle(current_data[stock].low_limit))
            # else:
            close_position(stock)

    # 不在买入股票池卖出
    
    # for stock in context.portfolio.positions.keys():
    #     current_data = get_current_data()
    #     price1d = get_close_price(stock, 1)
    #     nosell_1 = context.portfolio.positions[stock].price >= current_data[stock].high_limit
    #     sell_2 = stock not in hold_stocks
    #     if sell_2 and not nosell_1:
    #         close_position(stock)
        
        
#4-5 交易模块-择时交易
#结合择时模块综合信号进行交易
def my_trade(context):
    #获取选股列表并过滤掉:st,st*,退市,涨停,跌停,停牌
    # check_out_list = get_stock_list(context)
    # check_out_list = filter_limitup_stock(context, check_out_list)
    # check_out_list = filter_limitdown_stock(context, check_out_list)
    # check_out_list = filter_paused_stock(check_out_list)
    # check_out_list = check_out_list[:g.stock_num]
    print('今日自选股:{}'.format(context.check_out_list))
    print('len(context.check_out_list)',len(context.check_out_list))
    # print('type(context.check_out_list)',type(context.check_out_list))
    # print('context.check_out_list',context.check_out_list)
    # context.rr=context.check_out_list
    # print('context.rr',context.rr)
    # adjust_position(context, context.check_out_list)
    
    # 卖点：60日均线的止损，或5日均线卖出
    sell_stocks=[i for i in context.portfolio.positions.keys()]
    print('sell_stocks',sell_stocks)
    # 最新收盘价在60日均线和年线之上(前复权)
    try:
        sell_stocks = get_factor_filter_list_new(context,sell_stocks, 'MAC60', True, 1, 10)
    except:
        sell_stocks=[]
    print('sell_stocks2',sell_stocks)
    # print('sell_stocks',len(sell_stocks))
    # # 5日移动均线 / 今日收盘价
    try:
        sell_stocks = get_factor_filter_list_new(context,sell_stocks, 'MAC5', True, 1, 10)
    except:
        sell_stocks=[]
    print('sell_stocks3',sell_stocks)
    adjust_position(context, sell_stocks)
    
    # print('len(rr)',len(rr))
    # for stock in context.portfolio.positions.keys():
    # print('len(context.portfolio.positions)',len(context.portfolio.positions))
    # print('context.portfolio.positions',context.portfolio.positions)
#     if len(context.portfolio.positions)!=0:
        
#     for stock in context.portfolio.positions:
#         print('stock3',stock)
#             print('222')
# 		if stock not in ss:
# 			log.info("[%s]已不在应买入列表中11" % (stock))
# 			position = context.portfolio.positions[stock]
# 			close_position(position)
# 		else:
# 			log.info("[%s]已经持有无需重复买入11" % (stock))
# 	# 根据股票数量分仓
# # 	# 此处只根据可用金额平均分配购买，不能保证每个仓位平均分配
# 	position_count = len(context.portfolio.positions)
# 	if len(rr) > position_count:
# 		value = context.portfolio.cash / (len(rr) - position_count)
# 		for stock in rr:
#             # print('stock2',stock)
# 			if context.portfolio.positions[stock].total_amount == 0:
# 				if open_position(stock, value):
# 					if len(context.portfolio.positions) == len(rr):
# 						break
#     print('len(context.check_out_list)',len(context.check_out_list))
 
def mybuy(context):
    # print('是否有持仓',not g.nohold)
    # if not g.nohold:
        # 避免卖出的股票马上买入
        # hold_stocks = filter_buyagain(g.chosen_stock_list)
    hold_stocks=context.check_out_list
    
    log.info("待买股票列表：%s" %(context.check_out_list))
        # if g.choose_time_signal and (not g.isbull):
        #     free_value = context.portfolio.total_value * g.bearpercent
        #     minpercent = 0.7 / g.stocknum * g.bearpercent
        # else:
        #     free_value = context.portfolio.total_value
        #     minpercent = 0.7 / g.stocknum
    free_cash = context.portfolio.total_value - context.portfolio.positions_value
    # print('len(context.check_out_list)',len(context.check_out_list))
    # print('context.portfolio.positions.keys()',context.portfolio.positions.keys())
    stock_buy=[i for i in context.check_out_list if i not in context.portfolio.positions.keys()]
    print('stock_buy',stock_buy)
    print('len(stock_buy)',len(stock_buy))
    current_data = get_current_data()
    for i in range(len(hold_stocks)):
        if hold_stocks[i] in context.portfolio.positions.keys():
            log.info("已经持有股票：[%s]" %(hold_stocks[i]))
        else:
            tobuy = free_cash/len(stock_buy)
            if hold_stocks[i][0:3] == '688' or hold_stocks[i][0:3] =='689':
                current_data = get_current_data()
                # order_value(hold_stocks[i],floor(tobuy*0.01/current_data[hold_stocks[i]].high_limit), LimitOrderStyle(current_data[stock].high_limit))
                # order_value(hold_stocks[i],floor(tobuy*0.01/current_data[hold_stocks[i]].high_limit), MarketOrderStyle(current_data[stock].high_limit))
                # order(hold_stocks[i],context.portfolio.positions[stock].total_amount, LimitOrderStyle(current_data[stock].low_limit))
                order_value(hold_stocks[i], tobuy, MarketOrderStyle(current_data[hold_stocks[i]].high_limit))
            else:
                order_value(hold_stocks[i], tobuy)
        
    
        # for i in range(min(g.buyrank, len(hold_stocks))):
        #     free_cash = free_value - context.portfolio.positions_value
        #     # if hold_stocks[i] not in get_blacklist() and free_cash > context.portfolio.total_value / (g.stocknum * 10): # 黑名单里的股票不买
        #     if free_cash > context.portfolio.total_value / (g.stocknum * 10): # 黑名单里的股票不买
        #         if hold_stocks[i] in context.portfolio.positions.keys():
        #             log.info("已经持有股票：[%s]" %(hold_stocks[i]))
        #             current_percent = context.portfolio.positions[hold_stocks[i]].value / context.portfolio.total_value
        #             if  current_percent >= minpercent:continue
        #             tobuy = min(free_cash, buycash - context.portfolio.positions[hold_stocks[i]].value)
        #             # print("hold_stocks",hold_stocks)
        #         else:
        #             tobuy = min(buycash, free_cash)
        #         order_value(hold_stocks[i], tobuy)

# 获取前n个单位时间当时的收盘价
def get_close_price(security, n, unit='1d'):
    # print('get_close_price1',),attribute_history(security, n, unit, 'close')['close']
    return attribute_history(security, n, unit, 'close')['close'][0]

# 平仓，卖出指定持仓
def close_position(security):
    if security[0:3] == '688' or security[0:3] =='689':
        current_data = get_current_data()
                # order('688003.XSHG', 200, MarketOrderStyle(200))
        # order(stock,-context.portfolio.positions[stock].total_amount, MarketOrderStyle(current_data[stock].low_limit))
        order = order_target_value(security, 0, MarketOrderStyle(current_data[security].low_limit))
    else:
        order = order_target_value(security, 0) # 可能会因停牌或跌停失败
    if order != None and order.status == OrderStatus.held:
        g.sold_stock[security] = 0
        
#5-1 复盘模块-打印
#打印每日持仓信息
def print_trade_info(context):
    #打印当天成交记录
    trades = get_trades()
    for _trade in trades.values():
        print('成交记录：'+str(_trade))
    #打印账户信息
    for position in list(context.portfolio.positions.values()):
        securities=position.security
        cost=position.avg_cost
        price=position.price
        ret=100*(price/cost-1)
        value=position.value
        amount=position.total_amount    
        print('代码:{}'.format(securities))
        print('成本价:{}'.format(format(cost,'.2f')))
        print('现价:{}'.format(price))
        print('收益率:{}%'.format(format(ret,'.2f')))
        print('持仓(股):{}'.format(amount))
        print('市值:{}'.format(format(value,'.2f')))
        print('———————————————————————————————————')
    print('———————————————————————————————————————分割线————————————————————————————————————————')
