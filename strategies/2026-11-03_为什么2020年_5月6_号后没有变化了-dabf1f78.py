# Clone from JoinQuant
# postId: dabf1f782ce568388161d4225d56845a
# backtestId: 57c9bd878874bc90021b5a679f631c01
# title: 为什么2020年 5月6 号后没有变化了

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
      # 开盘时或每分钟开始时运行
    run_daily(market_open, time='every_bar', reference_security='000300.XSHG')
    
    # 存入 的股票代码
    g.security_n = ['000917.XSHG','000910.XSHG','000909.XSHG','000908.XSHG']
    g.security_y = ['000911.XSHG','000912.XSHG','000916.XSHG','000915.XSHG']
    

## 开盘时运行函数
def market_open(context):
    dateNow = context.current_dt
    if dateNow < datetime.datetime(year=2020,month=4,day=1):
        cash = context.portfolio.cash
        per_cash = cash/len(g.security_n)
        for i in g.security_n:
             order_value(i, per_cash)
    else:
        for i in g.security_n:
             order_target_value(i, 0)
        cash = context.portfolio.cash
        print(cash)
        per_cash = cash / len(g.security_y)
        for i in g.security_y:
            order_value(i, per_cash)
            print(get_current_tick(i))
        #  get_bars(g.security_y, end_dt=datetime.datetime.now(), count=1)
        

