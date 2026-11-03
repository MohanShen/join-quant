# Clone from JoinQuant
# postId: df116e09f2c5d975066dd11cb11aa714
# backtestId: e7cfb63080ecbcce8379bbf4674a489b
# title: 一创平台策略问题

#-*- coding: utf-8 -*-

# 导入函数库
from jqdata import *
import pandas as pd
from jqlib.technical_analysis import *  #技术指标因子库
from jqfactor import get_factor_values #聚宽因子库

from mdu_func import *   #自定义函数
from kuanke.user_space_api import *

#月线反转按RPS从高到低排序
#剔除最近5天内涨幅超过30%的
#初始建仓，选出10个股票，若不足10个，则全部买。
#   后面几天有新的标的，则继续买，买到10个为止。
#   若有调出，则从月线反转清单里补充。
#   持仓维持10个股票
#止盈条件：盈利大于10%，且从高点回撤7%
#止损条件：第二次收在20日线下
#   (若第一次破20日线后，再创新高且高点比第一次破20日均线前高点高5%以上，则重新计算)
#
#月线反转，增加关注研究机构>5，且 最近30天研报大于8份
#

# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')

    g.security = []

    # 设置持仓股票数量
    g.stockcount_max=10
    print("持仓股票数量上限 %d" % (g.stockcount_max))

    # 设置股票最大持仓比例
    g.holdshare_max=0.25
    print("单个股票最大持仓比例 %f" % (g.holdshare_max))

    #个股从高点回撤XXX即减仓
    g.stock_max_lost=0.07

    g.df_stock_info =pd.DataFrame(columns=('buy_date','avg_cost','high_price','sale_flag','ma20_lowdate','ma20_lowdate_highprice'))

    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')

    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
      # 开盘前运行
    run_daily(before_market_open, time='9:00', reference_security='000300.XSHG')
      # 开盘时运行
    run_daily(market_open, time='open', reference_security='000300.XSHG')
      # 收盘后运行
    run_daily(after_market_close,time='after_close', reference_security='000300.XSHG')


# 计算指定日期的月线反转名单
def get_yxfz_stocklist(test_flag,test_code,enddate): 

    #（1）50日的RPS大于90；
    #（2)日线收盘价站上年线；
    #（3）一月内曾创50日新高；
    #（4）收盘价站上年线的天数大于2，小于30；
    #（5）最高价距离120日内的最高价不到10%；
    
    # 1、选择所有股票（代码、名称、简称）-------------------------------------------
    stocklist =get_all_securities(types=['stock'], date=enddate)
    stocklist.drop(columns=['name','end_date', 'type'], inplace = True)

    # 最新收盘价及最高价
    stocklist_lastquo=get_lastquo(stocklist,enddate)
    stocklist = pd.concat([stocklist, stocklist_lastquo], axis=1, join='inner')
    stocklist_lastquo=get_lastquo_high(stocklist,enddate)
    stocklist = pd.concat([stocklist, stocklist_lastquo], axis=1, join='inner')

    # 股票筛选
    # 股票筛选-1 剔除上市一年以内新股
    firstDate =enddate + datetime.timedelta(days=-365)
    firstDate=datetime.datetime.utcfromtimestamp(time.mktime(firstDate.timetuple()))
    firstDate=datetime.datetime.date(firstDate)
    stocklist=stocklist[stocklist['start_date']<firstDate]

    # 股票筛选-2 50日的RPS大于90；
    startdate=get_trade_date(enddate,50)
    stocklist_rps=calc_rps(stocklist,startdate,enddate)
    stocklist = pd.concat([stocklist, stocklist_rps], axis=1, join='inner')
    stocklist.rename(columns={'RPS':'RPS50'},inplace=True)
    if test_flag==0:
        stocklist=stocklist[stocklist['RPS50']>90]

    #startdate=get_trade_date(enddate,120)
    #stocklist_rps=calc_rps(stocklist,startdate,enddate)
    #stocklist = pd.concat([stocklist, stocklist_rps], axis=1, join='inner')
    #stocklist.rename(columns={'RPS':'RPS120'},inplace=True)

    if test_flag==1:
        stocklist=stocklist[stocklist.index==test_code]

    # 股票筛选-3 日线收盘价站上年线
    stocklist_ma=get_ma(stocklist,enddate,250)
    stocklist = pd.concat([stocklist, stocklist_ma], axis=1, join='inner')
    stocklist.rename(columns={'MA':'MA250'},inplace=True)
    if test_flag==0:
        stocklist=stocklist[stocklist['lastclose']>stocklist['MA250']] #收盘价超过年线
        
    # 股票筛选-4 剔除深股通/沪股通 持股金额小于3000万的
    stock_cnt=stocklist.shape[0]
    if stock_cnt>0:    
        str_qdate=query(finance.STK_HK_HOLD_INFO).filter(
            finance.STK_HK_HOLD_INFO.day<=enddate,
            ).order_by(
                finance.STK_HK_HOLD_INFO.day.desc()
            ).limit(1)
        df_date=finance.run_query(str_qdate)
        hkdate=df_date.loc[0,'day']
        str_quo=query(finance.STK_HK_HOLD_INFO).filter(
            finance.STK_HK_HOLD_INFO.day==hkdate
            ).order_by(
                finance.STK_HK_HOLD_INFO.link_id
        )
    df_hkhold=finance.run_query(str_quo)
    df_hkhold.set_index(['code'], inplace = True) 
    df_hkhold.drop(columns=['id','day','link_id','link_name','name','share_ratio'], inplace = True)
    df_hkhold.rename(columns={df_hkhold.columns[0]:'hk_holdnum'},inplace=True)
    stocklist = pd.concat([stocklist, df_hkhold], axis=1, join='inner')
    stocklist['hk_holdamount']=stocklist['hk_holdnum']*stocklist['lastclose']/10000.0
    if test_flag==0:
        stocklist=stocklist[stocklist['hk_holdamount']>=3000]

    # 股票筛选-5 剔除ST股票
    stock_cnt=stocklist.shape[0]
    if stock_cnt>0:    
        lose = get_extras('is_st', list(stocklist.index), enddate, enddate, df=True)
        lose = lose.T
        lose.rename(columns={lose.columns[0]:'is_st'}, inplace=True)
        stocklist = pd.concat([stocklist, lose], axis=1, join='inner')
        stocklist = stocklist[stocklist.is_st  == False]
        stocklist=stocklist.drop(columns=['is_st'])
    
    #（3）一月内曾创50日(交易日)新高
    stock_cnt=stocklist.shape[0]
    if stock_cnt>0:
        stocklist_highdate=get_highprice_info(stocklist,enddate,49)
        stocklist_highdate.drop(columns=['high_price'], inplace = True)
        stocklist_highdate.rename(columns={'high_date':'high_date_50'},inplace=True)
        stocklist = pd.concat([stocklist, stocklist_highdate], axis=1, join='inner')
        checkDate =enddate + datetime.timedelta(days=-30)
        checkDate=datetime.datetime.utcfromtimestamp(time.mktime(checkDate.timetuple()))
        if test_flag==0:
            stocklist=stocklist[stocklist['high_date_50']>checkDate]

    #（4）收盘价站上年线的天数大于2，小于30；
    stock_cnt=stocklist.shape[0]
    if stock_cnt>0:    
        stocklist['ma_count']=0.0
        stocklist['net_amount_main']=0.0
        for index, row  in stocklist.iterrows():
            countflag=get_ma250_count(index, enddate, 29)
            net_amount_main=get_net_buy_amount(index,enddate,20)
            stocklist.loc[index,'ma_count']=countflag
            stocklist.loc[index,'net_amount_main']=net_amount_main
        if test_flag==0:
            stocklist=stocklist[stocklist['net_amount_main']>0]
            stocklist=stocklist[stocklist['ma_count']>3]
            stocklist=stocklist[stocklist['ma_count']<30]

    #（5）最高价距离120日内的最高价不到10%；
    stock_cnt=stocklist.shape[0]
    if stock_cnt>0:    
        stocklist_highprice=get_highprice_info(stocklist,enddate,119)
        stocklist_highprice.drop(columns=['high_date'], inplace = True)
        stocklist_highprice.rename(columns={'high_price':'high_price_120'},inplace=True)
        stocklist = pd.concat([stocklist, stocklist_highprice], axis=1, join='inner')
        if test_flag==0:
            stocklist=stocklist[(stocklist['high']/stocklist['high_price_120'])>0.9]

    # 最近30天北向资金增仓0.5% 以上的
    stock_cnt=stocklist.shape[0]
    if stock_cnt>0:    
        startdate=get_trade_date(enddate,30)
        df_hk_hold_change=get_hk_hold_change(startdate,enddate)
        df_hk_hold_change=df_hk_hold_change[df_hk_hold_change['hk_holdamount_change']>0]
        stocklist = pd.concat([stocklist, df_hk_hold_change], axis=1, join='inner')
        df_stockshare=get_stockshare(stocklist,enddate) 
        stocklist = pd.concat([stocklist, df_stockshare], axis=1, join='inner')
        stocklist['hk_holdamount_change_pct']=stocklist['hk_holdamount_change']/stocklist['share_trade_total']/100
        stocklist=stocklist[stocklist['hk_holdamount_change_pct']>0.5]

    # 最近5天涨幅超过30%的
    stock_cnt=stocklist.shape[0]
    if stock_cnt>0:
        startdate=get_trade_date(enddate,5)
        log.info(str('  取行情日:'+str(startdate)))
        log.info(str('  取行情日:'+str(enddate)))
        stocklist_quo1=get_lastquo(stocklist,startdate)
        stocklist_quo2=get_lastquo(stocklist,enddate)
        stocklist_quo1.rename(columns={'lastclose':'lastclose1'},inplace=True)
        stocklist_quo2.rename(columns={'lastclose':'lastclose2'},inplace=True)
        stocklist_quo1 = pd.concat([stocklist_quo1, stocklist_quo2], axis=1, join='inner')
        stocklist_quo1['markup']=stocklist_quo1['lastclose2']/stocklist_quo1['lastclose1']*100-100
        stocklist_quo1=stocklist_quo1[stocklist_quo1['markup']<30]    
        stocklist = pd.concat([stocklist, stocklist_quo1], axis=1, join='inner')
    
    stocklist['calc_date']=enddate

    stocklist=stocklist.dropna()
    #stocklist.sort_values(by='RPS50',ascending=False)    

    return stocklist.sort_values(by='RPS50',ascending=False)   

## 月线反转选股名单
def calc_stocklist_buy(context,buy_count):
    
    enddate=context.previous_date
    #月线反转选股名单
    df_stocklist=get_yxfz_stocklist(0,'',enddate)

    return(list(df_stocklist.head(buy_count).index))

## 止损或止盈
## 每天收盘后计算
def calc_stocklist_sale(context):
    
    stock_count=len(context.portfolio.positions)
    if stock_count==0:
        return([])
    enddate=context.previous_date
    reason=''

    for security in context.portfolio.positions:
        if security not in list(g.df_stock_info.index):
            stock_info_new ={
                    'buy_date':enddate,
                    'avg_cost':0,
                    'high_price':0,
                    'sale_flag':0,
                    'ma20_lowdate':'2000-1-1', # ma20_lowdate 第一次跌破20日均线日期
                    'ma20_lowdate_highprice':0 # ma20_lowdate_highprice 第一次跌破20日均线日期前最近一次最高价
                }
            series = pd.Series(stock_info_new,name=security)
            g.df_stock_info = g.df_stock_info.append(series)
        # 更新持仓成本
        g.df_stock_info.loc[security,'avg_cost']=context.portfolio.positions[security].avg_cost

    # 针对当前持仓，判断是否需要调出
    for index, row in g.df_stock_info.iterrows():
        price=context.portfolio.positions[index].price
        dict_ma=MA(index, check_date=enddate, timeperiod=20)
        ma20=dict_ma[index]
        reason=''
        
        #如果低于20日均线
        if price<ma20:
            #如果不是第一次低于20日均线，则调出
            #如果是第一次低于20日均线，则记录日期。且记住最近一次最高价
            if g.df_stock_info.loc[index,'ma20_lowdate_highprice']>0:
                g.df_stock_info.loc[index,'sale_flag']=1
                reason='第二次破60日均线'
            else:
                g.df_stock_info.loc[index,'ma20_lowdate']=enddate
                g.df_stock_info.loc[index,'ma20_lowdate_highprice']=g.df_stock_info.loc[index,'high_price']

        df_high = get_price(index, enddate, enddate, fields=['high'])
        high_price=df_high.loc[enddate,'high']
        
        #如果之前发生过低于20日均线情况，则判断当前收盘价是否高于之前的最高价5%
        #若高于，则重新初始化20日均线记录
        if g.df_stock_info.loc[index,'ma20_lowdate_highprice']>0:
            last_highprice=g.df_stock_info.loc[index,'ma20_lowdate_highprice']
            if (high_price/last_highprice-1)>0.05:
                g.df_stock_info.loc[index,'ma20_lowdate']='2000-1-1'
                g.df_stock_info.loc[index,'ma20_lowdate_highprice']=0

        if price>g.df_stock_info.loc[index,'high_price']:
            g.df_stock_info.loc[index,'high_price']=price
        
        # 高点回撤XXX 则调出
        if (price/g.df_stock_info.loc[index,'high_price'])<(1-g.stock_max_lost):
            g.df_stock_info.loc[index,'sale_flag']=1
            reason='高点回撤7% 当前价格：' + str(price) + '  前高点价格：' +  str(g.df_stock_info.loc[index,'high_price'])

        if g.df_stock_info.loc[index,'sale_flag']==1:
            print("调出 %s %s" % (index,reason))
        
        g.df_stock_info.loc[index,'reason']=reason

    #pd.set_option('display.height',1000)
    pd.set_option('display.max_rows',500)
    pd.set_option('display.max_columns',500)
    pd.set_option('display.width',1000)
    print(g.df_stock_info)

    df_sale=g.df_stock_info[g.df_stock_info['sale_flag']>0]
    g.df_stock_info=g.df_stock_info[g.df_stock_info['sale_flag']==0]

    return(list(df_sale.index))
    
## 计算调仓
def before_market_open(context):
    # 输出运行时间
    log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))

    # 给微信发送消息（添加模拟交易，并绑定微信生效）
    # send_message('美好的一天~')

    sell_list=calc_stocklist_sale(context)
    buy_count=g.stockcount_max - len(g.security) + len(sell_list)
    buy_list=calc_stocklist_buy(context,buy_count)
    
    # 计算新的股票池
    #g.security = set(context.portfolio.positions.keys()) + set(buy_list) - set(sell_list)
    for security in buy_list:
        if security not in g.security:
            g.security.append(security)

    for security in sell_list:
        if security in g.security:
            g.security.remove(security)
        
    print(g.security)
    print('调出清单：')
    print(sell_list)
    print('调入清单：')
    print(buy_list)
    
## 开盘时运行函数
def market_open(context):
    log.info('函数运行时间(market_open):'+str(context.current_dt.time()))
    
    # 股票池内股票数量
    stock_count=len(g.security)
    sale_flag=0

    #卖出不在最新股票池里的持仓
    for security in context.portfolio.positions:
        if security not in g.security:
            order_target(security, 0)
            sale_flag=1
            # 记录这次卖出
            print("Selling %s" % (security))

    if stock_count>0:
        holdshare=1.0/stock_count
        if holdshare>g.holdshare_max:
            holdshare=g.holdshare_max
    
        # 调整持仓，按市值平均分配
        stock_value=context.portfolio.total_value*holdshare
        print("目前总市值 %f ,股票数量 %f ,每个股票可分配资金 %f" % (context.portfolio.total_value,stock_count,stock_value))
        for security in g.security:
            order_target_value(security, stock_value)

## 收盘后运行函数
def after_market_close(context):
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    #得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    
    log.info('一天结束')
    log.info('##############################################################')
