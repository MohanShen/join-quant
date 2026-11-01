# Clone from JoinQuant
# postId: b5705b08f4cd9e1dc73d92c37c692d51
# backtestId: a7bf82a21f1d2582ad21dd43aa26bcf9
# title: get_valuation存在的一个问题

# 导入函数库
from jqdata import *

# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')
    
    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    
    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
      # 开盘前运行
    run_daily(before_market_open, time='before_open', reference_security='000300.XSHG') 
      # 开盘时或每分钟开始时运行
    run_daily(market_open, time='every_bar', reference_security='000300.XSHG')
      # 收盘后运行
    run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')
    
## 开盘前运行函数     
def before_market_open(context):
    pass
    
## 开盘时运行函数
def market_open(context):
    # dfe=get_valuation('300002.XSHE', end_date=context.current_dt, count=5, fields=['turnover_ratio'])
    # print('hsv45: \n%s' % dfe['turnover_ratio'])
    # # hsv20=np.array(dfe['turnover_ratio'])#换手率(%)
    # mahsv45=dfe['turnover_ratio'].mean()
    # print('mahsv: %s' % mahsv45)
    
    # df2=finance.run_query(query(finance.STK_HOLDER_NUM.code,finance.STK_HOLDER_NUM.a_share_holders,finance.STK_HOLDER_NUM.pub_date,finance.STK_HOLDER_NUM.end_date
    #         ).filter(finance.STK_HOLDER_NUM.code=='300002.XSHE',finance.STK_HOLDER_NUM.pub_date<=context.current_dt
    #         ).order_by(finance.STK_HOLDER_NUM.end_date.desc()
    #         ).limit(2))
    # print(df2)
    
    # df4a=get_valuation('300002.XSHE', start_date=None, end_date=context.current_dt, fields=['circulating_cap'], count=1)
    # df4b=get_fundamentals(query(valuation.code,valuation.circulating_cap).filter(valuation.code=='300002.XSHE'))
    # print(df4a)
    # print(df4b)
    
    # cc= get_bars('300002.XSHE', count=20, unit='1d', fields=['close'])
    # zhangfu0=cc['close'][-1]/cc['close'][0]
    # print(cc)
    # print('c0:%s' % cc[0])
    # print('c1:%s' % cc[-1])
    # print('zf:%s' % zhangfu0)
    
    # dfe=get_valuation('300002.XSHE', end_date=context.current_dt, count=20, fields=['turnover_ratio'])
    # cc= get_bars('300002.XSHE', count=20, unit='1d', fields=['close'])
    # # hsv20=np.array(dfe['turnover_ratio'])
    # hsv20=dfe['turnover_ratio']
    # c20=cc['close']
    # print(type(hsv20))
    # print(type(c20))
    
    # dfe=get_valuation('300002.XSHE', end_date=context.current_dt, count=20, fields=['turnover_ratio'])
    # mahsv0=dfe['turnover_ratio'].mean()
    # print(dfe)
    # print(mahsv0)
    
    # px=[]
    # stocks=['300002.XSHE','603618.XSHG','603681.XSHG']
    # for i in stocks:
    #     df4=get_price(i,end_date=context.current_dt,frequency='daily',fields=['money','volume'],skip_paused=False,fq='pre',count=30,panel=False)
    #     df5=get_bars(i, count=20, unit='1d', fields=['close'])
    #     df6=get_fundamentals(query(valuation.pe_ratio,indicator.inc_net_profit_to_shareholders_year_on_year).filter(valuation.code==i))
    #     df7=finance.run_query(query(finance.STK_HOLDER_NUM.code,finance.STK_HOLDER_NUM.a_share_holders
    #         ).filter(finance.STK_HOLDER_NUM.code==i,finance.STK_HOLDER_NUM.pub_date<=context.current_dt
    #         ).order_by(finance.STK_HOLDER_NUM.end_date.desc()
    #         ).limit(1))
    #     pegi=df6['pe_ratio'][0]/df6['inc_net_profit_to_shareholders_year_on_year'][0]
    #     zf20i=df5['close'][-1]/df5['close'][0]*10
    #     cje20=df4['money'].mean()/100000000
    #     cjl30=df4['volume'].mean()/10000000
    #     holderi=df7['a_share_holders'][0]/3000
    #     px0=cje20+cjl30+zf20i+pegi+holderi
        # px.append(px0)
    
    # stocks=['300002.XSHE','603618.XSHG','603681.XSHG']
    # for i in stocks:
    #     df3=get_price(i,end_date=context.current_dt,frequency='daily',fields=['money','volume'],skip_paused=False,fq='pre',count=30,panel=False)
    #     # df3=get_bars(i, count=20, unit='1d', fields=['close'])
    #     cje30=df3['money'].mean()#没有[0]会显示数据类型信息，得不到计算结果
    #     cjl20=df3['volume'][11:31].mean()
    #     # print(cje30)
    #     print(cjl20)
    # security = list(get_all_securities(['stock']).index)
    # df3=get_fundamentals(query(valuation.code,valuation.circulating_cap,valuation.capitalization#流通市值，单位：亿
    # ).filter(valuation.code.in_(security),valuation.circulating_market_cap<30 #对于多只股票集，这里不要用==，要用.in_()
    # ).order_by(valuation.circulating_market_cap.asc()
    # ).limit(10))
    # print(df3)
    
    # df3 = get_valuation('300002.XSHE', end_date=context.current_dt, count=20, fields=['circulating_market_cap'])
    # print(df3)
    # cv = get_bars('300002.XSHE', count=20, unit='1d', fields=['close'])
    # c1=cv['close'][-1]
    # print(cv)
    # print(type(df3))
    # print(type(cv))
    
    # a = [1,3,2,5,4]
    # print(a)
    # print(list(reversed(a)))
    
    df3 = get_valuation('300002.XSHE', end_date=context.current_dt, count=20, fields=['turnover_ratio'])
    print(df3)
    hsv20a=np.array(df3['turnover_ratio'])
    hsv20=list(reversed(hsv20a))
    print(hsv20a)
    print(hsv20)
 
## 收盘后运行函数  
def after_market_close(context):
    pass
