# Clone from JoinQuant
# postId: 6f297177c5f041e520dd0803e0bf8ba1
# backtestId: 007efa47b3b42948b241fd1811184329
# title: 能帮我看看这个数据正常吗？为什么夏普比率这么高

# 导入函数库
from jqdata import *
import numpy as np
import tushare as ts
import datetime
i=0
arr=np.array([0,0,1,1,1,1,0,1,0,1,0,1,1,1,0,0,1,1,1,1,0,0,0,1,1,0,1,0,1,0,0,0,0,1,0,0
,0,1,1,1,0,0,0,0,0,0,1,1,1,0,0,0,1,0,0,1,1,1,0,0,0,1,0,0,1,0,0,1,1,1,1,0,0
,0,0,1,0,0,1,0,0,0,0,1,1,0,1,1,0,0,1,0,0,1,1,1,0,0,1,0,0,1,0,1,1,0,0,0,1,0
,1,1,0,1,1,0,1,1,1,0,0,1,1,0,1,0,0,1,0,1,0,0,1,0,0,0,0,1,1,0,0,0,0,0,1,1,1
,0,1,1,1,0,1,1,1,0,1,1,0,1,0,0,1,1,0,0,0,0,1,0,0,1,1,0,1,0,0,0,1,0,0,0,1,1
,0,1,1,0,1,0,0,0,1,0,0,0,1,1,1,1,1,1,0,0,0,0,0,1,1,1,1,0,0,0,0,0,0,0,1,0,0
,0,0,0,0,1,1,0,1,0,1,1,0,1,1,0,1,1,1,0,1,1,1,0])
# 1表示应该全部买入，0表示应该全部卖出
def initialize(context):
     # 设定沪深300作为基准
    set_benchmark("000300.XSHG")
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 输出内容到日志 log.info()
    #set_order_cost(OrderCost(close_tax=0, open_commission=0, close_commission=0, min_commission=0), type='stock')
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    log.info('初始函数开始运行且全局只运行一次')
      # 开盘前运行
    run_daily(before_market_open, time='before_open', reference_security='000300.XSHG')
      # 开盘时运行
    run_daily(market_open, time='open', reference_security='000300.XSHG')
      # 收盘后运行
    run_daily(add,time='after_close', reference_security='000300.XSHG')
    run_daily(after_market_close, time='after_close',reference_security='000300.XSHG')
def before_market_open(context):
    global i
    log.info('第',i+1,'天开始了')
    # 要操作的股票：平安银行（g.为全局变量）
    g.security = '600809.XSHG'
    


def market_open(context):
    stock = g.security
    global i

    log.info('正在运行')
    log.info("######################预测的标签是:",arr[i])
    
    cash = context.portfolio.available_cash
    log.info(cash)
    if arr[i]==1 and cash > 0:
        # 用所有资金买入股票
        order_value(stock, cash)
        # 输出买入信息
        log.info(">>> %s 买入 %d 股 %s" % (str(context.current_dt), 
        context.portfolio.positions[stock].today_amount, stock))
        
    if arr[i]==0 and context.portfolio.positions[stock].closeable_amount > 0:
        # 输出卖出信息
        log.info("<<< %s 卖出 %d 股 %s" % (str(context.current_dt), 
        context.portfolio.positions[stock].total_amount, stock))
        # 卖出所有股票,使这只股票的最终持有量为0
        order_target(stock, 0)

def after_market_close(context):
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    # 得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    log.info('一天结束')



def add(context):
    global i
    i=i+1

