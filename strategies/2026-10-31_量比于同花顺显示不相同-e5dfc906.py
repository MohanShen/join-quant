# Clone from JoinQuant
# postId: e5dfc9065253d3fda14854b6358f2c41
# backtestId: 12085b1450dfd74cff78fd9a2dd91b83
# title: 量比于同花顺显示不相同

import talib
def initialize(context):
    g.stocks=['000001.XSHG']
    set_universe=(g.stocks)
def handle_data(context,data):
    scu0 =list(get_all_securities(types=['stock']).index)
    g.stocks = scu0
    set_universe(g.stocks)
    date=context.current_dt.strftime("%Y-%m-%d")
    for security in g.stocks:
        Volume_rate_day_before=Volume_rate(security,context.current_dt.day-1,context)
        if Volume_rate_day_before>10:
            order(security,1000)
            log.info("Buying %s" % (security))
            print(Volume_rate_day_before)

            
def MACD(prices,fastperiod=12, slowperiod=26, signalperiod=9):
    '''
    参数设置:
        fastperiod = 12
        slowperiod = 26
        signalperiod = 9

    返回: macd - signal
    '''
    macd, signal, hist = talib.MACD(prices, 
                                    fastperiod=fastperiod, 
                                    slowperiod=slowperiod, 
                                    signalperiod=signalperiod)
    return macd[-1] - signal[-1]
    
def Volume_rate(sec,time_day,context):
	Volume_last_5_day=history(5,'1d','volume',sec).sum()[sec]
	#print '=====Volume_last_5_day=====%s=============='%sec
	#print Volume_last_5_day
	if time_day is context.current_dt.minute:
		volume_last_5_min=history(5,'1m','volume',sec).sum()[sec]
		#print '=====Volume_last_5_min==================='
		#print volume_last_5_min
		volume_rate_now=(float)(volume_last_5_min/5)/(Volume_last_5_day/(5*4*60))
		#print '=====Volume_rate_now==================='
		#print volume_rate_now
		return volume_rate_now
	Volume_last_1_day=history(1,'1d','volume',sec).sum()[sec]
	Volume_last_6_day=history(6,'1d','volume',sec).sum()[sec]
	#print '=====Volume_last_1_day==================='
	#print Volume_last_1_day
	#print '=====Volume_last_6_day==================='
	#print Volume_last_6_day
	if (Volume_last_6_day-Volume_last_1_day) == 0 : return 1
	Volume_rate_before= (float)(Volume_last_1_day/(4*60))\
				/((float)(Volume_last_6_day-Volume_last_1_day)/(5*4*60))
	#print '=====Volume_rate_before==================='
	#print Volume_rate_before
	return Volume_rate_before