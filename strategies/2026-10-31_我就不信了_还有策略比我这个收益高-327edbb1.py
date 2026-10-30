# Clone from JoinQuant
# postId: 327edbb1c921cb288c7435af4b4742b4
# backtestId: 8dba0fdaa527b6d53012009cd0df0323
# title: 我就不信了，还有策略比我这个收益高！

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

    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
      # 开盘前运行
    run_daily(before_market_open, time='before_open', reference_security='000300.XSHG')
      # 开盘时运行
    run_daily(market_open, time='open', reference_security='000300.XSHG')
      # 收盘后运行
    run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')

## 开盘前运行函数
def before_market_open(context):
    # 输出运行时间
    log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))

    # 给微信发送消息（添加模拟交易，并绑定微信生效）
    # send_message('美好的一天~')

    # 要操作的股票：平安银行（g.为全局变量）
    g.securitys = ['510210.XSHG','512170.XSHG','159909.XSHE','510230.XSHG']

## 开盘时运行函数
def market_open(context):
    cash = context.portfolio.available_cash
    
    log.info('####聚宽数据真搞笑#############################################')
    if context.current_dt.year==2020 and context.current_dt.month==8 and context.current_dt.day==12 :
        order_target_value('510230.XSHG',cash)
        
    if context.current_dt.year==2020 and context.current_dt.month==8 and context.current_dt.day==13 :
        order_target_value('510230.XSHG',0)
        
    if context.current_dt.year==2021 and context.current_dt.month==1 and context.current_dt.day==20 :
        order_target_value('510210.XSHG',cash)
        
    if context.current_dt.year==2021 and context.current_dt.month==1 and context.current_dt.day==21 :
        order_target_value('510210.XSHG',0)
    
    if context.current_dt.year==2021 and context.current_dt.month==2 and context.current_dt.day==22 :
        order_target_value('512170.XSHG',cash)
        
    if context.current_dt.year==2021 and context.current_dt.month==2 and context.current_dt.day==23 :
        order_target_value('512170.XSHG',0)
        
    if context.current_dt.year==2021 and context.current_dt.month==3 and context.current_dt.day==9 :
        order_target('159909.XSHE',3000)
        
    if context.current_dt.year==2021 and context.current_dt.month==3 and context.current_dt.day==10 :
        order_target('159909.XSHE',0)   
    '''
    cash = context.portfolio.available_cash
    for security in g.securitys:
        if security not in context.portfolio.positions:
            order(security, 1000)
   '''

## 收盘后运行函数
def after_market_close(context):
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    #得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    log.info('一天结束')
    log.info('##############################################################')
