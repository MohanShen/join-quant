# Clone from JoinQuant
# postId: 269ddda14014a018e4715f41949c7c88
# backtestId: d24b985f9a75564068a7ad32944f00b3
# title: 一个仓位下买入同一个期货合约两次，平仓时系统计算的盈亏值问题

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
    run_daily(before_market_open, time='before_open', reference_security='A9999.XDCE') 
      # 开盘时或每分钟开始时运行
    run_daily(market_open, time='every_bar', reference_security='A9999.XDCE')
      # 收盘后运行
    run_daily(after_market_close, time='after_close', reference_security='A9999.XDCE')
    g.days_count = 0
    init_cash = context.portfolio.starting_cash
    set_subportfolios([SubPortfolioConfig(cash=init_cash, type='futures')])
    #g.ratio = 0.5
    #set_subportfolios([SubPortfolioConfig(cash=g.ratio*init_cash, type='futures'),\
    #                   SubPortfolioConfig(cash=g.ratio*init_cash, type='futures')])
    
## 开盘前运行函数     
def before_market_open(context):
    pass
    
## 开盘时运行函数
def market_open(context):
    if g.days_count < 2:
        order('A2301.XDCE', 1, side = 'long', pindex=0)
    elif g.days_count == 2:
        order('A2301.XDCE', -1, side = 'long', pindex=0)
        order('A2301.XDCE', -1, side = 'long', pindex=0)
    g.days_count = g.days_count + 1
    pass
 
## 收盘后运行函数  
def after_market_close(context):
    pass
