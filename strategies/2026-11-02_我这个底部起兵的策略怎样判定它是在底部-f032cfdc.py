# Clone from JoinQuant
# postId: f032cfdc1af83994031f0ea468e0116b
# backtestId: caf4bf1f6f578d725f09d8b55390ba32
# title: 我这个底部起兵的策略怎样判定它是在底部？

# 导入函数库
from jqdata import *

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
   
 #   run_daily(before_market_open, time='before_open', reference_security='000300.XSHG') 
      # 开盘时运行
    run_daily(market_sell, time='14:30', reference_security='000300.XSHG')
    run_daily(market_open1, time='09:35', reference_security='000300.XSHG')
    #run_daily(before_market_close, time='14:45', reference_security='000300.XSHG')
      # 收盘后运行
 #   run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
      # 开盘前运行
      
def get_fullist(context):
    stocks = get_index_stocks('000002.XSHG') + get_index_stocks('399106.XSHE')
    
    return list(stocks)
   
   # get_all_securities(['stock']).index  
      


## 开盘时运行函数
def market_open1(context):
    g.stocks = get_fullist(context)
    log.info('函数运行时间(market_open):'+str(context.current_dt.time()))
    current_data = get_current_data()
    cash = context.portfolio.total_value # 获取总资产
    temp = {}
    
   # for stock in g.stocks:
    #    security = g.security
    
    for stock in g.stocks:
        h = attribute_history(stock, 4, unit = '1d', 
        fields = ('open', 'close', 'high', 'low', 'volume'), skip_paused = True)
        t1_open=h.open[-1]
        t1_close=h.close[-1]
        t1_volume=h.volume[-1]
        
        t2_open=h.open[-2]
        t2_close=h.close[-2]
        t2_volume=h.volume[-2]       
        
        t3_open=h.open[-3]
        t3_close=h.close[-3]
        t3_volume=h.volume[-3]     
        
        t4_open=h.open[-4]
        t4_close=h.close[-4]
        t4_volume=h.volume[-4]   
        

        h1 = attribute_history(stock, 250, "1d", 
        ["close", "high","low"], df=False)
        t5_Low=h1["low"][-30:].min()
        t6_high=h1["high"][-30:].max()
        
        if t1_close<t1_open and t2_close>t2_open and t3_close>t3_open \
        and t4_close>t4_open and t3_volume*1.3<t2_volume>t3_volume \
        and t4_volume*1.3<t3_volume>t4_volume\
        and t3_open<t1_close<t3_open*1.05\
        and t6_high*0.5<t2_close>t5_Low*1.2:
       #     temp[change] = stock
     #   temp = [temp[change] 
      #  for change in sorted(temp.keys(), reverse = True)]
      #  for stock in temp:
            order_value(stock, cash/ 1)
    return g.stocks
    
def market_sell(context):
    current_data = get_current_data()
    for stock in context.portfolio.positions.keys():
        order_target(stock, 0)
     #   log.info("Selling %s" % (security))            
            
            
