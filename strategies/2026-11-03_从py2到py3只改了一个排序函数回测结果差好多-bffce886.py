# Clone from JoinQuant
# postId: bffce88654f04b8f25185b2a064ddaa7
# backtestId: 8673cd1a6b8306c1b51b15d246117bcb
# title: 从py2到py3只改了一个排序函数回测结果差好多

# 导入函数库
from jqdata import *
from jqlib.alpha101 import *

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
    run_monthly(before_market_open, monthday = 1,  time='before_open', reference_security='000300.XSHG')
      # 开盘时运行
    run_monthly(market_open, monthday = 1,  time='open', reference_security='000300.XSHG')
      # 收盘后运行
    run_monthly(after_market_close, monthday = 1,  time='after_close', reference_security='000300.XSHG')

## 开盘前运行函数
def before_market_open(context):
    # 输出运行时间
    log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))
    current_stock = list(context.portfolio.positions.keys())
    current_date = context.previous_date
    print(current_date)
    # code = list(get_all_securities(['stock'],date=current_date).index)
    code = '000300.XSHG'
    alpha = alpha_022(current_date, code).dropna().order(ascending = False)
    print(alpha)
    alpha_head = list(alpha.index)
    alpha_head = alpha_head[:5]
    
    # g.stock_to_buy = alpha_head
    
    g.stock_to_buy = list( set(alpha_head) - set(current_stock) )
    g.stock_to_sell = list( set(current_stock) - set(alpha_head) )
    
    
   #  print(alpha)


## 开盘时运行函数
def market_open(context):
    log.info('函数运行时间(market_open):'+str(context.current_dt.time()))
    
    # 取得当前的现金
    cash = context.portfolio.available_cash

    for stock in g.stock_to_sell:
        order_target(stock, 0)
        log.info("卖出 %s" % (stock) )
        
    try: 
        g.cash = cash/len(g.stock_to_buy)
    except:
        g.cash = 0
        
    for stock in g.stock_to_buy:
        order_target(stock, g.cash)
        log.info("买入 %s" % (stock) )     
        
## 收盘后运行函数
def after_market_close(context):
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))

    #得到当天所有成交记录
    trades = get_trades()
    for _trade in list(trades.values()):
        log.info('成交记录：'+str(_trade))
    log.info('一天结束')
    log.info('##############################################################')
