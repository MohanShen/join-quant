# Clone from JoinQuant
# postId: 0054dc92eb02c74788c30f2d0116c3eb
# backtestId: 7d09fa11bed2d60f8bcff81b5ba46ce0
# title: 在每分钟回测时限价单按市价单成交的问题

import jqdata

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
    
  
    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
      # 开盘前运行
    run_daily(before_market_open, time='before_open', reference_security='000300.XSHG') 
      # 开盘时运行
    run_daily(market_open, time='every_bar', reference_security='000300.XSHG')
      # 收盘后运行
    run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')
    
## 开盘前运行函数     
def before_market_open(context):
   
    # 要操作的股票：平安银行（g.为全局变量）
    g.security = '000001.XSHE'
    #是否已经买入
    g.isbuy='1'
    
## 开盘时运行函数
def market_open(context):
    log.info('函数运行时间(market_open):'+str(context.current_dt.time()))
    
    #获取当前分钟的最新价格
    current_data = get_current_data()
    
    High_Limit_1=current_data[g.security].high_limit
    print High_Limit_1
    if g.isbuy=='1':
        order(g.security, 100, LimitOrderStyle(High_Limit_1))
        g.isbuy='0'

## 收盘后运行函数  
def after_market_close(context):
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    