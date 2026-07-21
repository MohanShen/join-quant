# Clone from JoinQuant
# postId: 02d397c0e54e8bb8415c3eaca0d7b2e1
# backtestId: 67c95fe8d56a17f92f8396bf7fc7c77a
# title: 简单的择时基金轮动策略

# 导入函数库
import jqdata
import pandas as pd
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
    
    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
  #设置观测指数:创业板，中证500，上证50，沪深300，医药
#    g.indexlist=['399006.XSHE','399905.XSHE','000016.XSHG','000300.XSHG','000991.XSHG']
  #设置观测指数对应的基金
#    g.fundlist = ['159915.XSHE','510500.XSHG','510050.XSHG','510300.XSHG','159938.XSHE']
    g.indexlist=['399006.XSHE','000016.XSHG','000991.XSHG']
    g.fundlist = ['159915.XSHE','510050.XSHG','159938.XSHE']
    g.inc_rat=[]
    g.df={'indexlist':pd.Series(g.indexlist),'fundlist':pd.Series(g.fundlist),'inc_rat':pd.Series(g.inc_rat)}
    g.index_fund=pd.DataFrame(g.df)
    #run_daily(before_market_open, time='before_open', reference_security='000300.XSHG') 
      # 开盘时运行
    run_daily(market_open, time='open', reference_security='000300.XSHG')

#计算过去n天涨幅   
def get_growth_rate(security, n=10):
#获取股票过去n天的收盘价
    close_data = attribute_history(security, n, '1d', ['close'])
    #获取n天前价格
    past_price=close_data['close'][0]
    #获取上一时间点价格
    current_price = close_data['close'][-1]
    a = past_price
    b = current_price
    if not isnan(a) and not isnan(b) and a != 0:
        return (b - a) / a
    else:
        log.error("非法, security: %s, %d日收盘价: %f, 当前价: %f" %(security, n, a, b))
        return 0    
    
## 开盘时运行函数
def market_open(context):
    log.info('函数运行时间(market_open):'+str(context.current_dt.time()))
    #获取观测指数过去N日涨幅
    for i in range(len(g.index_fund['indexlist'])):
        g.index_fund['inc_rat'][i]=get_growth_rate(g.index_fund['indexlist'][i],20)
   #按照过去N日涨幅进行倒序排列
    g.index_fund.sort_index(by='inc_rat',ascending=False,inplace=True)
    g.index_fund.index=range(0,len(g.index_fund))
    #如果所有指数涨幅均小于零，则清仓
    if g.index_fund['inc_rat'][0]<0:
        for i in range(len(g.index_fund['indexlist'])):
            order_target(g.index_fund['fundlist'][i], 0)
   #将涨幅非第一的指数基金清零，并买入涨幅第一的指数基金
    elif g.index_fund['inc_rat'][0]>0:
        i=1
        while i<len(g.index_fund['indexlist']):
            order_target(g.index_fund['fundlist'][i], 0)
            i=i+1
        cash = context.portfolio.available_cash
        order_value(g.index_fund['fundlist'][0], cash)

    

 

