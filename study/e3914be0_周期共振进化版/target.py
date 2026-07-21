# Clone from JoinQuant
# postId: e3914be0ecd2f01e5b24eca659adf168
# backtestId: c451a4b87274d4f580506f75b2818ae1
# title: 周期共振进化版

# 导入函数库
from jqdata import *

def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')

    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')

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
    # 要操作的股票：东方通信（g.为全局变量）
    g.security = '600776.XSHG'

## 开盘时运行函数
def market_open(context):
    log.info('函数运行时间(market_open):'+str(context.current_dt.time()))
    security = g.security
    
    close_data_day = get_bars(security, count=145, unit='1d', fields=['close'])
    MA3_today = close_data_day['close'][-3:].mean()
    MA21_today = close_data_day['close'][-21:].mean()
    MA144_today = close_data_day['close'][-144:].mean()
    MA3_yesterday = close_data_day['close'][-4:-1].mean()
    MA21_yesterday = close_data_day['close'][-22:-1].mean()
    MA144_yesterday = close_data_day['close'][-145:-1].mean()
    
    close_data_hour = get_bars(security, count=22, unit='60m', fields=['close'])
    MA3_hour = close_data_hour['close'][-3:].mean()
    MA21_hour = close_data_hour['close'][-21:].mean()
    MA3_lasthour = close_data_hour['close'][-4:-1].mean()
    MA21_lasthour = close_data_hour['close'][-22:-1].mean()
    
    #定义大周期上涨趋势
    Rise_A = MA3_today > MA21_today or MA3_today > MA144_today
    Rise_B = MA21_today > MA21_yesterday and MA144_today > MA144_yesterday
    Rise_day = Rise_A or Rise_B
    #定义大周期下跌趋势
    Fall_day = MA3_today < MA21_today
    
    #定义小周期金叉
    Golden_Cross_hour = MA3_hour> MA21_hour and MA3_lasthour < MA21_lasthour
    #定义小周期死叉
    Death_Cross_hour = MA3_hour < MA21_hour and MA3_lasthour > MA21_lasthour
    
    # 取得上一小时价格
    current_price = close_data_hour['close'][-1]
    # 取得当前现金
    cash = context.portfolio.available_cash

    # 如果大周期是上升趋势且小周期出现金叉, 则全仓买入
    if Rise_day and Golden_Cross_hour:
        # 记录这次买入
        log.info("日线趋势向好，小时级别金叉, 买入 %s" % (security))
        # 用所有 cash 买入股票
        order_value(security, cash)
    # 如果小周期出现死叉, 则空仓卖出
    elif Death_Cross_hour and context.portfolio.positions[security].closeable_amount > 0:
        # 记录这次卖出
        log.info("小时级别均线死叉，卖出 %s" % (security))
        # 卖出所有股票，最终持有量为0
        order_target(security, 0)

## 收盘后运行函数
def after_market_close(context):
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    #得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    log.info('让收益奔跑吧！')
    log.info('##############################################################')
