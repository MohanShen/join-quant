# Clone from JoinQuant
# postId: 3fe362d602e7c4bebda37c5c3b8c8bd2
# backtestId: 18a08c2506fdcaed82a13e4caa7df64c
# title: 请教各位大神 “开仓数量不能小于100” 这个代码行在哪里？

# 导入函数库
import jqdata
from jqlib.technical_analysis import *

# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('399300.XSHE')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    # 过滤掉order系列API产生的比error级别低的log
    log.set_level('order', 'error')

    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0002, close_commission=0.0002, min_commission=5), type='stock')
    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
      # 开盘前运行
    run_daily(before_market_open, time='before_open', reference_security='000300.XSHG') 
      # 开盘时运行
    run_daily(market_open, time='close-10m', reference_security='000300.XSHG')
      # 收盘后运行
    run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')
    g.MA18_list = [0,0,0,0]
    g.security = '600516.XSHG'
    
def preMA18(context):
    g.MA18_list
    date = context.current_dt
    MA18 = get_price(g.security, end_date = date, frequency = '1d', count = 18)['close'].mean()
    g.MA18_list.append(MA18)
    
## 开盘前运行函数     
def before_market_open(context):
    # 输出运行时间
    log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))
    # 给微信发送消息（添加模拟交易，并绑定微信生效）
    send_message('美好的一天~')
    # 要操作的股票：天齐锂业（g.为全局变量）
    
## 开盘时运行函数
def market_open(context):
    preMA18(context)
    log.info('函数运行时间(market_open):'+str(context.current_dt.time()))
    print("收盘前十分钟交易")
    security = g.security
    # 获取股票的收盘价
    close_data = attribute_history(security, 18, '1d', ['close'])
    # 取得过去五天的平均价格
    MA18 = close_data['close'].mean()
    # 取得上一时间点价格
    current_price = attribute_history(security, 1, '1m', ['close'] )['close']
    # 取得当前的现金
    cash = context.portfolio.available_cash
    print((g.MA18_list[-1]-g.MA18_list[-3])/g.MA18_list[-1])
    if (g.MA18_list[-1] - g.MA18_list[-3])/g.MA18_list[-1] > 0:
        print("最新MA18 (%d) 大于前三日MA18的斜率  (%d) ，进行操作"%(g.MA18_list[-1],g.MA18_list[-3]))
        # 如果上一时间点价格高出五天平均价1%, 则全仓买入
        if current_price[-1] > 1.005*MA18:
            # 记录这次买入
            log.info("价格高于均价 0.5%%, 买入 %s" % (security))
            # 用所有 cash 买入股票
            order_value(security, cash)
        # 如果上一时间点价格低于五天平均价, 则空仓卖出
        elif current_price[-1] < MA18 and context.portfolio.positions[security].closeable_amount > 0:
            # 记录这次卖出
            log.info("价格低于均价, 卖出 %s" % (security))
            # 卖出所有股票,使这只股票的最终持有量为0
            order_target(security, 0)
    elif (g.MA18_list[-1] - g.MA18_list[-3])/g.MA18_list[-1] <= 0:
        order_target(g.security, 0)
        log.info("最新MA18 小于 前三天MA18的斜率，抛出股票，待最新的MA18大于前三天MA18斜率时，将会继续操作股票")
 
## 收盘后运行函数  
def after_market_close(context):
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    #得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    log.info('一天结束')
    log.info('##############################################################')