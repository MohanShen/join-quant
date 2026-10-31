# Clone from JoinQuant
# postId: 054005e10a5dbd7b13c5d99135f79069
# backtestId: b27c95e6aacb4ea2922e7fb7f8a19ce8
# title: 悬赏哦：按天粒度回测速度超级慢的问题求助

#均线呈现多头排列（5》10》20》30），近10天多头排列的天数大于7天，第一次缩量（量小于5天均量）回踩21日线时买入（最低点触及21日线的上下2%，收星），
#第二天开盘买进去,5%止损，最高点回撤达到1个ATR止盈。
#5.28：之前结果太差，试试例子里的跌破13日线次日买入
#5.28:怎么定义上涨趋势，应该从时间和幅度两方面来定义，一个是时间上达到一定时长的多头排列，幅度上有一定涨幅但又不过大（考虑20-30%之间）
#来复盘一下选出来的股票： aqq
#000300.XSHG，399006.XSHE
#2018.2.1:极限这个策略吧，趋势30>20>10,过去30天中有大等于25天满足趋势，且最低价小于20线的天数<3，过去30天的累积涨幅小于35%，周线大趋势向
#上，周线DIF>0，周线DEA>0,周线DIF>周线DEA，后续要加上评分体系，按照分数优先级排列待选股票，当日不能有异常放量（当日量超过5日均量3倍）
#止损：下跌5个点，异常放量（当日量超过5日均量3倍,用get_price，参数带start_date和end_date），分时呈现锯齿形，特别是小盘庄股
#止盈：分级止盈，前面宽，后面小
#当盈利小于10%时，不止盈，股价连续三日在MA20下，卖出
#当盈利大于10%小于20%时，（最高价格-平均成本价）的最高点回撤50%止盈
#当盈利大于20%小于50%时，（最高价格-平均成本价）的最高点回撤30%止盈
#当盈利大于50%时，（最高价格-平均成本价）的最高点回撤20%止盈


import numpy as np
import pandas as pd
import talib as tl
from collections import Counter

'''
================================================================================
总体回测前
================================================================================
'''
def initialize(context):
	# 设置参数
	set_params()
	# 设置回测
	set_backtest()
	run_daily(before_trading_start,'06:00',reference_security='000001.XSHG')
	run_daily(after_trading_end,'17:00',reference_security='000001.XSHG')
# 设置参数
def set_params():
    # 设置股票池
    g.security = get_index_stocks('000300.XSHG')
    # 测试多头趋势的均线长度
    g.ma_lengths = [10,20,30]
    # 测试买入回踩的均线长度
    g.test_ma_length = 20

    # 同时最多持有几支股票
    g.num_stocks = 3
    # 多头趋势天数（10天内有7天）
    g.in_trend_days = 7
    # 止盈回撤（最高点回落一个ATR就止盈）
    g.cut_gain_percentage = 0.05
    # 止损百分比（5%止损）
    g.cut_loss_percentage = 0.05
    # 区间最高价
    g.summit = {}    
    # 未能成功清仓的股票列表
    g.bucket = []   
    # 可行股票池
    g.available_stocks = []
	#计算持仓股票的20ma，最高价格，平均成本价，连续收盘低于20ma天数
    g.highsincebuy={}
    g.avgcost={}
    g.bma20sincebuy_count={}
# 3
# 设置回测
def set_backtest():
    # 一律使用真实价格
    set_option('use_real_price', True)
    # 过滤log
    log.set_level('order', 'error')
    # 设置基准
    set_benchmark('000300.XSHG')

#设置滑点和手续费
def set_slip_fee(context):
    # 更新指数成分股

    set_slippage(PriceRelatedSlippage(0.002))
    # 根据不同的时间段设置手续费
    dt=context.current_dt
    
    if dt>datetime.datetime(2013,1, 1):
        set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003, close_today_commission=0, min_commission=5), type='stock')
        
    elif dt>datetime.datetime(2011,1, 1):
		set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.001, close_commission=0.002, close_today_commission=0, min_commission=5), type='stock')
            
    elif dt>datetime.datetime(2009,1, 1):
        set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.002, close_commission=0.003, close_today_commission=0, min_commission=5), type='stock')
                
    else:
        set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.003, close_commission=0.004, close_today_commission=0, min_commission=5), type='stock')


'''
================================================================================
定义一些常用函数，包括过滤条件，价格计算等
================================================================================
'''	
#个股止损：下跌5个点，股价连续三日在MA20下
def stock_stop_loss(context, data):
	for stock in context.portfolio.positions.keys():
		avg_cost = context.portfolio.positions[stock].avg_cost
		cur_price = data[stock].close
		if cur_price / avg_cost < 0.95:
			order_target(stock,0)
			log.info('止损清仓：%s,现价=%.2f,成本价=%.2f' % \
			(stock, cur_price, avg_cost))
		if security in g.highsincebuy:
			g.highsincebuy.pop(security)
		if security in g.avgcost:
			g.avgcost.pop(security)
		if security in g.bma20sincebuy_count:
			g.bma20sincebuy_count.pop(security)
		
'''		
def close_position(position):
    security = position.security
    order = order_target_value_(security, 0) # 可能会因停牌失败
    if order != None:
        if order.filled > 0:
            # 只要有成交，无论全部成交还是部分成交，则统计盈亏
            g.trade_stat.watch(security, order.filled, position.avg_cost, position.price)

        if order.status == OrderStatus.held and order.filled == order.amount:
            # 全部成交则删除相关证券的相关信息字典
            if security in g.highsincebuy:
                g.highsincebuy.pop(security)
            if security in g.avgcost:
				g.avgcost.pop(security)
			if security in g.bma20sincebuy_count:
				g.bma20sincebuy_count.pop(security)
			else:
                log.warn("price info of %s not found" %(security))
            return True

    return False
'''
	
#阶梯止盈
#当盈利小于5%时，不止盈，股价连续三日在MA20下，卖出
#当盈利大于5%小于20%时，（最高价格-平均成本价）的最高点回撤50%止盈
#当盈利大于20%小于50%时，（最高价格-平均成本价）的最高点回撤30%止盈
#当盈利大于50%时，（最高价格-平均成本价）的最高点回撤20%止盈
def moving_stop_profit(context,data):

	# 分级移动止盈
	for stock in context.portfolio.positions.keys():
		avg_cost = context.portfolio.positions[stock].avg_cost #获取成本
		high_price = g.highsincebuy[stock]
		cur_price = data[stock].close
		profit_price=high_price-avg_cost
		if avg_cost>0:
			profit_level = high_price/avg_cost-1 #收益率
		
			# 根据盈利设定stopLoss_price
			if profit_level > 0.05 and profit_level < 0.2:
				stopLoss_price = high_price-(high_price-avg_cost)*0.5
			elif profit_level >= 0.2 and profit_level < 0.5:
				stopLoss_price = high_price-(high_price-avg_cost)*0.7
			elif profit_level >= 0.5:
				stopLoss_price = high_price-(high_price-avg_cost)*0.8
			# 判断
		if profit_level>0.05 and cur_price<stopLoss_price:
			order_target(stock, 0)
			log.info('止盈清仓：%s,现价=%.2f,成本价=%.2f,最高价=%.2f' % \
				(stock, cur_price, avg_cost,high_price))
			if security in g.highsincebuy:
				g.highsincebuy.pop(security)
			if security in g.avgcost:
				g.avgcost.pop(security)
			if security in g.bma20sincebuy_count:
				g.bma20sincebuy_count.pop(security)
				
# 买入股票,最多买3只股票，每分钟找买点，低于20天线的1.02位置就买入
def buy_stocks(context,data):
	if len(context.portfolio.positions) < 3 and len(g.available_stocks) > 0:
		assign = context.portfolio.cash/(3-len(context.portfolio.positions))#每只股票分到的金钱数
		df=filter_limitup_stock(g.available_stocks)
		df=filter_limitdown_stock(df)
		for security in df:
			current_data = get_current_data()
			if security not in context.portfolio.positions and data[security].close<stock_ma(security,20,'close')*1.02:
				order_value(security, assign)
				log.info('建仓: %s', security)

#计算个股的n日均价
def stock_ma(security,n=20,field='close'):
	df=attribute_history(security,n,'1d',fields = field, skip_paused=False,fq='pre',df=False)[field].mean()
	return df

# 过滤停牌股票，并过滤过去30天中停牌超过1天的股票
def filter_paused_stock(stock_list):
	current_data = get_current_data()
	s_list=[]
	for security in stock_list:
		past_prices = attribute_history(security, 30,'1d',fields = ['open','close','high','low','volume','pre_close'], skip_paused = False,fq='pre',df=False)
		d = Counter(past_prices['volume'])
		if d[0.0]>2 or (not current_data[security].paused):
			s_list.append(security)
	return s_list

	
# 过滤新股
def filter_new_stock(context,stock_list):
	#current_data = get_current_data()
	#stocks = get_all_securities(['stock'])
	return [stock for stock in stock_list if (context.current_dt.date() - get_security_info(stock).start_date) > datetime.timedelta(300)]
	
# 过滤ST及其他具有退市标签的股票
def filter_st_stock(stock_list):
	current_data = get_current_data()
	return [stock for stock in stock_list 
		if not current_data[stock].is_st 
		and 'ST' not in current_data[stock].name 
		and '*' not in current_data[stock].name 
		and '退' not in current_data[stock].name]


				
# 过滤涨停的股票
def filter_limitup_stock(security_list):
	#last_prices = history(1, unit='1m', field='close', security_list=se)
	current_data = get_current_data()
	# 已存在于持仓的股票即使涨停也不过滤，避免此股票再次可买，但因被过滤而导致选择别的股票
	return [stock for stock in security_list if current_data[stock].last_price < current_data[stock].high_limit*0.9]

# 过滤跌停的股票
def filter_limitdown_stock(stock_list):
	#last_prices = history(1, unit='1m', field='close', security_list=stock_list)
	current_data = get_current_data()
	return [stock for stock in stock_list if current_data[stock].last_price > current_data[stock].low_limit*1.01]
		
# 获取前n个单位时间当时的收盘价
def get_close_price(security, n, unit='1d'):
	return attribute_history(security, n, unit, fields = ['close'], skip_paused=False,fq='pre',df=False)['close'][0]
	
# 获取n个单位时间至今的最高收盘价
def get_hhv_price(security, n, unit='1d'):
	return attribute_history(security, n, unit, fields = ['close'], skip_paused=False,fq='pre',df=False)['close'].max()
	
# 获取n个单位时间至今的最低收盘价
def get_llv_price(security, n, unit='1d'):
	return attribute_history(security, n, unit, fields = ['close'], skip_paused=False,fq='pre',df=False)['close'].min()
	
# 获取股票n日以来涨幅，根据n日内最低收盘价到最高收盘价计算,n默认为20
def get_growth_rate(security, n=20):
	min = get_llv_price(security,n,'1d')
	max = get_hhv_price(security,1,'1d')
	if not isnan(min) and not isnan(max) and min != 0:
		return (max - min) / min
	else:
		log.error("数据非法, security: %s, %d日收盘价: %f, 当前价: %f" %(security, n, lc, c))
		return 0

#获取某个股票前n个单位时间至今是否有m天停牌,返回TRUE或者FALSE
def get_everpaused(security,n,m):
	past_prices = attribute_history(security, n,'1d',fields = ['volume'], skip_paused = False,fq='pre',df=False)
	d = Counter(past_prices['volume'])
	if d[0.0]>m:
		return True
	else:
		return False

'''
# 自定义下单
# 根据Joinquant文档，当前报单函数都是阻塞执行，报单函数（如order_target_value）返回即表示报单完成
# 报单成功返回报单（不代表一定会成交），否则返回None
def order_target_value_(security, value):
	if value == 0:
		log.debug("Selling out %s" % (security))
	else:
		log.debug("Order %s to value %f" % (security, value))
		# 如果股票停牌，创建报单会失败，order_target_value 返回None
	# 如果股票涨跌停，创建报单会成功，order_target_value 返回Order，但是报单会取消
	# 部成部撤的报单，聚宽状态是已撤，此时成交量>0，可通过成交量判断是否有成交
	return order_target_value(security, value)
'''
	
#计算MACD
def MACD_CN(close, fastperiod, slowperiod, signalperiod) :
	macdDIFF, macdDEA, macd = tl.MACDEXT(close, fastperiod=fastperiod, fastmatype=1, slowperiod=slowperiod, slowmatype=1, signalperiod=signalperiod, signalmatype=1)
	macd = macd * 2
	return macdDIFF, macdDEA, macd
	
#做价格的周期转换，比如日-周-月
def get_period_price_wjlec(stock, rule='W', start_date=None, end_date=None, frequency='daily', fields=None, \
                           skip_paused=True, fq='pre', count=None):
    '''
            极简方法获取真实的日线、周线、月线或其他周期数据，本函数考虑了假期情况，不会列出不交易的日期。
    参数：
        stock : 证券代码
        rule : K线类别，默认是周线'W'，月线是'M',季度线是'Q',年线是'A'。期间代码也可以使用周K（'W-FRI'）、月K（'BM'）、
        年K（'A-DEC'）
        end_date : 默认None, 对应使用attribute_history; 否则使用get_price
        其他参数：同get_price
    返回：
        dataframe: index:时间序列 
    范例：
        df=get_period_price_wjlec('601668.XSHG', start_date='2017-1-1', end_date='2017-5-31')#获取周线
        df=get_period_price_wjlec('601668.XSHG', rule='W', count=120, end_date='2017-6-1')#获取周线
        df=get_period_price_wjlec('601668.XSHG', rule='M', start_date='2017-1-1', end_date='2017-5-31')#获取月线
        df=get_period_price_wjlec('601668.XSHG', rule='M', count=1000, end_date='2017-5-31')#获取月线
    '''
    #设定转换周期period_type  转换为周是'W',月'M',季度线'Q',五分钟'5min',12天'12D'
    period_type = rule
    if "attribute_history" not in dir() or end_date:
        stock_data = get_price(stock, start_date=start_date, end_date=end_date, frequency=frequency, fields=\
                       ['open','high','low','close', 'volume', 'money'], skip_paused=skip_paused, fq=fq, count=count)
    else:
        stock_data = attribute_history(stock, count=count, unit=frequency, fields=['open','high','low','close', 'volume', 'money'], \
                               skip_paused=skip_paused, fq=fq)
    #记录每个周期中最后一个交易日
    stock_data['date']=stock_data.index
    period_type=rule
    #进行转换，周线的每个变量都等于那一周中最后一个交易日的变量值
    period_stock_data=stock_data.resample(period_type,how='last')
    #周线的open等于那一周中第一个交易日的open
    period_stock_data['open'] = stock_data['open'].resample(period_type,how='first')
    #周线的high等于那一周中的high的最大值
    period_stock_data['high'] = stock_data['high'].resample(period_type,how='max')
    #周线的low等于那一周中的low的最大值
    period_stock_data['low'] = stock_data['low'].resample(period_type,how='min')
    #周线的volume和money等于那一周中volume和money各自的和
    period_stock_data['volume'] = stock_data['volume'].resample(period_type,how='sum')
    period_stock_data['money'] = stock_data['money'].resample(period_type,how='sum')
    # 剔除整个周期都休盘或停牌的数据
    period_stock_data = period_stock_data.dropna()
    period_stock_data.set_index('date',inplace=True)
    return period_stock_data

# 选取有效股票，输出一list，返回所有满足条件的股票池
def get_available_stocks(context):

	# 备选股list 
	available_stocks = []
	# 获取现在数据
	current_data = get_current_data(security_list=None)
	# 对于股票池里的所有股票,剔除停牌，ST，上市不超过300天的股票
	filter_security=filter_paused_stock(g.security)
	print len(filter_security)
	filter_security=filter_new_stock(context,filter_security)
	filter_security=filter_st_stock(filter_security)
	
	for security in filter_security:
		#跳过停牌设置为否，为了统计过去30天内是否停牌
		past_prices = attribute_history(security, 70,'1d',fields = ['open','close','high','low','volume','pre_close'], skip_paused = False,fq='pre',df=False)
		last_ma20=past_prices['close'][-20:].mean()#昨日的20日均线，比较常用，单独保存
		last_volume5=past_prices['volume'][-5:].mean()#昨日的5日均量
		
		#计算周线MACD的DEA和DIF,条件W_MACD：df['dif'][-1]>0 and df['dea']>0 and df['dif']>df['dea']
		df=get_period_price_wjlec(security, rule='W', count=300, end_date=context.current_dt.date())
		df['dif'], df['dea'], df['macd'] = MACD_CN(df['close'].values, 12, 26, 9)
		W_MACD=df['dif'][-1]>0 and df['dea'][-1]>0 and df['dif']>df['dea']
		
		#计算过去30天中满足多头排列条件的天数count_up,算过去30天里每天的10,20,30日收盘均价，存在mas里，df设置为False，加快回测速度
		#并计算过去15天里最低价小于20日均线*1.02的次数count_down
		mas = []
		count_up=0
		count_down=0
		for day in range(1,30):#0到29

			past_close = past_prices['close'][:-day]#把后面day天的数据去掉
			past_ma20=past_close[-20:].mean()#每一个day天算的20日均线价格
			past_low=past_prices['low'][:-day][-1]#每一个day天算的当日最低价
			
			if day<=15:#过去15天要算count_up和count_down
				for length in g.ma_lengths:
					# 截取相应数据
					ma_data = past_close[-length:]
					# 算均值
					ma = ma_data.mean()
					# 计入list 
					mas.append(ma)
					# 从大到小排列均值list 
				mas1 = sorted(mas,reverse = True)
				if mas == mas1: count_up+=1
				if past_low<past_ma20*1.02: count_down+=1
					
			elif day>15:#15天以上只要算是否多头排列
				for length in g.ma_lengths:
					# 截取相应数据
					ma_data = past_close[-length:]
					# 算均值
					ma = ma_data.mean()
					# 计入list 
					mas.append(ma)
					# 从大到小排列均值list 
				mas1 = sorted(mas,reverse = True)
				if mas == mas1: count_up+=1
        
		#判断昨日是否缩量(量小于5天均量)
		volume_decade = past_prices['volume'][-1:]< last_volume5
		growth_ok=get_growth_rate(security, 20)<0.35
		#判断是否满足均线多头,第一次缩量（量小于5天均量）回踩21日线时买入（最低点触及21日线的上下2%，收星）,剔除停牌，ST，涨停，跌停
		if count_up>=25:   # and count_down<3 and volume_decade and growth_ok and W_MACD
			#满足条件则加入股票池
			available_stocks.append(security)
	#print available_stocks
	# 返回list，按照市值从小到大排序
	df = get_fundamentals(query(
		valuation, income
	).filter(
		# 这里不能使用 in 操作, 要使用in_()函数
		valuation.code.in_(available_stocks)
	).order_by(
		valuation.market_cap.asc()))
	print df['code']
	return(df['code'])    
'''
================================================================================
每日收盘后（统计交易信息，更新g.portfolio_info表，获取当天未完成的订单，将自选股清空）
========================================================= =======================
'''
def after_trading_end(context):#更新持仓股票的g.avgcost，g.highsincebuy，g.bma20sincebuy_count
	for stock in context.portfolio.positions:
		if stock != None:
			
			cur_price=context.portfolio.positions[stock].price
			avgcost=context.portfolio.positions[stock].avg_cost
			g.avgcost[stock]=avgcost# g.avgcost保存该股票成本价
			if stock not in g.highsincebuy:
				g.highsincebuy[stock] = cur_price# g.highsincebuy缓存股票持仓后的最高价格
				if cur_price < stock_ma(stock,20,'close'):
					g.bma20sincebuy_count[stock]=1
				else:
					g.bma20sincebuy_count[stock]=0
			else:
				if g.highsincebuy[stock] < cur_price:
					g.highsincebuy[stock] = cur_price
				if cur_price < stock_ma(stock,20,'close'):
					g.bma20sincebuy_count[stock]+=1
				else:
					g.bma20sincebuy_count[stock]=0#判断没有连续低于MA20，那么就将该股票之前的计数清零
	orders=get_open_orders()	# 获得每天未成功卖出股票
	g.bucket += [item.security for item in orders if not item.is_buy]
	log.info('今日未完成之卖出: %s', g.bucket)
	g.available_stocks=[]
'''
================================================================================
每日开市前（确定是否有股票停牌，要选出多头排列的股票(趋势30>20>10,过去30天中有大等于27天满足趋势，且最低价小于20线的天数<3，过去30天的累积涨幅小于35%，周线大趋势向
上，周线DIF>0，周线DEA>0,周线DIF>周线DEA)）
================================================================================
'''


def before_trading_start(context):
    # 设置滑点、手续费和指数成分股
    set_slip_fee(context)
    # 选取有效股票
    g.available_stocks = get_available_stocks(context)
    

	


 

'''
================================================================================
每天交易时（开盘清空昨天未完成的订单，按照ma20*1.02挂单自选股中前三只股票，14:50执行止损和止盈）
================================================================================
'''
# 每个回测单位
def handle_data(context, data):
	for stock in g.bucket:
		order_target_value(stock,0)
	buy_stocks(context,data)	
	
	#14:50之后操作，止盈止损，			
	# 获得当前时间
	hour = context.current_dt.hour
	minute = context.current_dt.minute
	# 每天下午14:50，先止损，再止盈
	if hour == 14 and minute == 50:
		stock_stop_loss(context, data)
		moving_stop_profit(context,data)



