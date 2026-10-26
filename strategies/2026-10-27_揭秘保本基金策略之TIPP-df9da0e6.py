# Clone from JoinQuant
# postId: df9da0e63c14173546b02acb9ed43c3d
# backtestId: d4c0b6ae39725ce240adc4031946d510
# title: 揭秘保本基金策略之TIPP

'''TIPP原理：

A_t= D_t+E_t
F_t=max⁡(A_tf,F_(t-1))
E_t=m(A_t-F_t)
At为t期的投资组合总价值；
D_t为t期的固定收益资产值；
E_t为t期的风险性资产价值；
F_t为t期的要保金额（Floor）;
f为固定的要保比率（Floor Percentage）；
Ft − 1为t一1期的要保金额（Floor）；
m为风险乘数，乘数愈大风险偏好程度愈高，且m > 1
'''

# 导入函数库
from jqdata import *

# 初始化函数，设定基准等等
def initialize(context):
    g.m = 6
    g.f = 0.9
    g.ft = context.portfolio.total_value * g.f
    
    # 设定沪深300作为基准
    g.risk_security = '510300.XSHG'
    g.riskless_security = '511880.XSHG'
    set_benchmark(g.risk_security)
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
    run_daily(market_open, time='open', reference_security='000300.XSHG')
      # 收盘后运行
    run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')

## 开盘前运行函数
def before_market_open(context):
    g.ft = max(g.ft,context.portfolio.total_value * g.f)
    #E_t=m(A_t-F_t)
    
    g.et = g.m * (context.portfolio.total_value - g.ft)
    g.dt = context.portfolio.total_value - g.et
    record(et=g.et)
    record(dt=g.dt)

## 开盘时运行函数
def market_open(context):
    for i in range(0,3):
        order_target_value(g.risk_security,g.et)
        order_target_value(g.riskless_security,g.dt)

## 收盘后运行函数
def after_market_close(context):
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    #得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    log.info('一天结束')
    log.info('##############################################################')
