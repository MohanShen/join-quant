# Clone from JoinQuant
# postId: 9981752e4845e3005bcbb2a22affd33e
# backtestId: 2b762f6d36c0c68ae8944edbfdecf9f6
# title: 华泰高股息率选股模型

import pandas as pd
import numpy as np
import math
import talib as tl
from jqdata import gta
#from datetime import datetime, timedelta
def initialize(context):
    set_option('use_real_price', True)
    #----------------Settings--------------------------------------------------/
    g.baseIndex = '000300.XSHG'
    g.periodBullBear = 20
    g.periodBeta = 5
    g.daysDelta = timedelta(days = g.periodBeta + 60)
    g.poolSize = 20
    g.holdSize = 5
    g.maxDrawdown = 0.05
    
    g.meanList = []
    g.medianList = []
    
    
    # holds buffer
    g.stockBuyList = []
    g.bullOrBear = None
    
    
    g.f = 1.0/g.poolSize*2.0 
    g.apr_min_filter = 0.01
    g.apr_max_filter = 1.00
    #----------------Settings--------------------------------------------------/
    
    #run_weekly(checkWeekly, -1, time='after_close')
    #run_weekly(swapWeekly, 1, time='open')
    #run_daily(checkWeekly, time='before_open')
    #run_daily(swapWeekly, time='open')
    #run_daily(w300file, time='open')
    run_monthly(checkWeekly, 1, 'before_open')
    run_monthly(swapWeekly, 1, 'open')
    
    #run_weekly(checkBullOrBear, -1, time='after_close')
    #run_daily(dailyRun, time='open')
    
def dailyRun(context):
    
    g.bullOrBear = checkBullOrBear(g.baseIndex)

    flgbb = 0
    if g.bullOrBear == 'bear' :
        flgbb = -1
        swapWeekly(context)
    elif g.bullOrBear == 'bull' :
        flgbb = 1
    record(flgbb=flgbb)
    pass



def swapWeekly(context):
    
    # 取得牛熊标志位
    #g.bullOrBear = checkBullOrBear(g.baseIndex)
    if g.bullOrBear == 'bear' :
        g.stockBuyList = []
        pass
    
    have_set = set(context.portfolio.positions.keys())
    to_sell = set()
    to_buy = set()
    holdsFull = g.stockBuyList
    
    to_sell = have_set - set(holdsFull)
    
    num2Add = g.holdSize - len(context.portfolio.positions.keys()) + len(to_sell)
    
    for stock in to_sell:
        ret = order_target(stock, 0)
        if ret is not None and ret.status == OrderStatus.held:
            pass
            try :
                user.sell(stock[:6], price=10000, amount=(100 / g.holdSize)) #卖出N%
            except :
                pass
        else :
            # failed
            num2Add = num2Add - 1
    
    currentBalance = context.portfolio.cash
    current_data = get_current_data()
    #log.debug([num2Add])
    allValue = context.portfolio.portfolio_value
    for stock in holdsFull:
        
        if stock in have_set :
            continue
        
        if current_data[stock].paused :
            continue
        
        if num2Add == 0 :
            break

        #bs = checkBullOrBear(stock)
        #if bs == 'bear' :
        #    continue
        
        atrV = 0.000001
        pct = 1
        
        each = context.portfolio.cash/(num2Add)
        #each = context.portfolio.cash
        volumeAvg = int(each * pct/current_data[stock].high_limit/100) * 100
        volumeAtr = int((each * g.maxDrawdown / atrV) / 100) * 100
        #volumeAtr = volumeAvg
        volume = min(volumeAtr, volumeAvg)
        if volume > 0:
            ret = order_target(stock, volume)
            #ret = order_target_value(stock, allValue * pct)
            if ret is not None and ret.status == OrderStatus.held:
                num2Add = num2Add - 1
                try :
                    user.buy(stock[:6], price=10000, amount=(100 / g.holdSize)) #买入N%
                except :
                    pass
                pass

    g.holdSize = int(allValue / 20000)
    g.poolSize = g.holdSize + 50
    
# 判断牛熊市场
def checkBullOrBear(stock) :
    
    hData = attribute_history(stock, g.periodBullBear + 60, unit='1d'
                    , fields=('close', 'volume', 'open', 'high', 'low')
                    , skip_paused=True
                    , df=False)
    
    volume = hData['volume']
    volume = np.array(volume, dtype='f8')
    close = hData['close']
    open = hData['open']
    high = hData['high']
    low = hData['low']
    
    ma = tl.MA(close, timeperiod=20)
    rsiS = tl.RSI(close, timeperiod=20)
    #if rsiS[-1] < 55 or np.isnan(rsiS[-1]):
    if ma[-1] < ma[-2] :
        ret = 'bear'
    else :
        ret = 'bull'
    return ret

# 判断牛熊，根据牛熊取得相应的标的物
def checkWeekly(context) :
    
    log.debug('checkWeekly')
    allValue = context.portfolio.portfolio_value
    g.holdSize = int(allValue / 20000)
    g.poolSize = g.holdSize + 50
    # 取得牛熊标志位
    #g.bullOrBear = checkBullOrBear(g.baseIndex)
    #g.bullOrBear = 'bull'
    
    # 取得目标交易标的
    df = get_all_securities(['stock'])
    #获得基金列表 : 'etf' 'fja' 'fjb'
    #df = df[df['type']=='etf']
    df = df[df['start_date'] < (context.current_dt - g.daysDelta).date()]
    # 去除ST股票
    df = df[~df['display_name'].str.contains('ST|退|\*')]
    # 去除不必要的列
    df = df.drop(['start_date', 'end_date', 'type', 'name'], 1)
    
    stockList = list(df.index)
    
    # 去除停牌的股票
    current_data = get_current_data()
    df['paused'] = map(lambda x : current_data[x].paused, stockList)
    df = df[df['paused'] == False]
    stockList = list(df.index)
    
    '''
    1) 总市值全市场从大到小前80%
    2）市盈率全市场从小到大前40%（剔除市盈率为负的股票）
    3）市收率小于2.5
    4）同时满足上述3条的股票，按照股息率从大到小排序，选出股息率最高的50只股票
       等权构建组合
    '''
    
    # 1) 总市值全市场从大到小前80%
    fCap = get_fundamentals(
        query(valuation.code)
        .filter(valuation.code.in_(stockList))
        .order_by(valuation.market_cap.desc())
        .limit(int(len(stockList) * 0.8))
    )
    sListCap = list(fCap['code'])
    log.debug(len(sListCap))
    
    # 2）市盈率全市场从小到大前40%（剔除市盈率为负的股票）
    fPE = get_fundamentals(
        query(valuation.code)
        .filter(valuation.code.in_(stockList), valuation.pe_ratio > 0)
        .order_by(valuation.pe_ratio.asc())
        .limit(int(len(stockList) * 0.4))
    )
    sListPE = list(fPE['code'])
    log.debug(len(sListPE))
    
    # 3）市收率小于2.5
    fPS = get_fundamentals(
        query(valuation.code)
        .filter(valuation.code.in_(stockList)
        , valuation.ps_ratio < 2.5)
    )
    sListPS = list(fPS['code'])
    log.debug(len(sListPS))
    
    stockList = list(set(sListCap) & set(sListPE) & set(sListPS))
    log.debug(len(stockList))
    
    # 4）同时满足上述3条的股票，按照股息率从大到小排序，选出股息率最高的50只股票
    fDivid = get_fundamentals(
        query(cash_flow.code, cash_flow.dividend_interest_payment)
        .filter(cash_flow.code.in_(stockList))
    )
    # 股息率
    fMerge = getDivid(context, stockList)
    
    # 按照股息率从大到小排序
    fMerge = fMerge.sort(['divpercent'], ascending=[False])
    
    
    # ***************************
    #fDivid['GuxiLv'] = map(lambda x : cal_guxilv(x, context.current_dt), fDivid['code'])
    #fDivid = fDivid.sort(['GuxiLv'], ascending=[False])
    #fDivid = fDivid.dropna()
    #fDivid = fDivid.head(g.poolSize)
    ##fMerge = fDivid
    #log.debug([fMerge, fDivid])
    # ***************************
    
    fMerge = fMerge.head(g.poolSize)
    g.stockBuyList = list(fMerge['code'])


def before_trading_start(context):
    
    set_universe(g.stockBuyList)
    pass

def cal_guxilv(stock,current_dt):
	
	t_up=current_dt-datetime.timedelta(1)
	t_down=current_dt-datetime.timedelta(30*6)
	
	stocklist=[stock[:6]]
	q=query(gta.STK_MKT_DIVIDENT) \
		.filter(gta.STK_MKT_DIVIDENT.DECLAREDATE<=str(t_up), \
				gta.STK_MKT_DIVIDENT.DECLAREDATE>=str(t_down), \
				gta.STK_MKT_DIVIDENT.SYMBOL.in_(stocklist)) \
		.order_by(gta.STK_MKT_DIVIDENT.PAYMENTDATE.desc())
	df = gta.run_query(q)
	if len(df['DIVIDENTAT'])<=0:
		return None
	meigufenhong=df['DIVIDENTAT'][0]
	if meigufenhong==None:
		return None
	price=attribute_history(stock, 1, '1d', ('close'))['close'][-1]
	return float(meigufenhong)/price
	
# 取得股息率
def getDivid(context,stocks):
    year = context.current_dt.year-1
    
    #将当前股票池转换为国泰安的6位股票池
    stocks_symbol=[]
    for s in stocks:
        stocks_symbol.append(s[0:6])

        
    #如果知道前一年的分红，那么得到前一年的分红数据
    df1 = gta.run_query(query(
            gta.STK_DIVIDEND.SYMBOL,#股票代码
            gta.STK_DIVIDEND.DIVIDENTBT,#股票分红
            gta.STK_DIVIDEND.DECLAREDATE#分红消息的时间
        ).filter(
            gta.STK_DIVIDEND.ISDIVIDEND == 'Y',#有分红的股票
            gta.STK_DIVIDEND.DIVDENDYEAR == year,
           #且分红信息在上一年度
            gta.STK_DIVIDEND.SYMBOL.in_(stocks_symbol)
        )).dropna(axis=0)
    
    stocks_symbol_this_year=list(df1['SYMBOL'])
    
    #如果前一年的分红不知道，那么知道前两年的分红数据
    df2 = gta.run_query(query(
        gta.STK_DIVIDEND.SYMBOL,#股票代码
        gta.STK_DIVIDEND.DIVIDENTBT,#股票分红
        gta.STK_DIVIDEND.DECLAREDATE#分红消息的时间
    ).filter(
        gta.STK_DIVIDEND.ISDIVIDEND == 'Y',#有分红的股票
        gta.STK_DIVIDEND.DIVDENDYEAR == year-1,
       #且分红信息在上一年度
        gta.STK_DIVIDEND.SYMBOL.in_(stocks_symbol),
        gta.STK_DIVIDEND.SYMBOL.notin_(stocks_symbol_this_year)
    )).dropna(axis=0)
    
    df= pd.concat((df2,df1))
    # 下面四行代码用于选择在当前时间内能已知去年股息信息的股票
    df['pubtime'] = map(lambda x: int(x.split('-')[0]+x.split('-')[1]+x.split('-')[2]),df['DECLAREDATE'])
    currenttime  = int(str(context.current_dt)[0:4]+str(context.current_dt)[5:7]+str(context.current_dt)[8:10])
    
    # 筛选出pubtime小于当前时期的股票，然后剔除'DECLAREDATE','pubtime','SYMBOL'三列
    # 并且将DIVIDENTBT 列转换为float
    df = df[(df.pubtime < currenttime)]
    
    df['SYMBOL']=map(normalize_code,list(df['SYMBOL']))
    df.index=list(df['SYMBOL'])
    
    df=df.drop(['SYMBOL','pubtime','DECLAREDATE'],axis=1)

    df['DIVIDENTBT'] = map(float, df['DIVIDENTBT'])
    
    #接下来这一步是考虑多次分红的股票，因此需要累加股票的多次分红
    #按照股票代码分堆
    df = df.groupby(df.index).sum()
    
    #得到当前股价
    Price=history(1, unit='1d', field='close', security_list=list(df.index), df=True, skip_paused=False, fq='pre')
    Price=Price.T
    df['pre_close']=Price

    
    #计算股息率 = 股息/股票价格
    df['divpercent']=df['DIVIDENTBT']/df['pre_close']
    
    df['code'] = np.array(df.index)
    
    return df

    
    