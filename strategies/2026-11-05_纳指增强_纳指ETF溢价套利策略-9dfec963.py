# Clone from JoinQuant
# postId: 9dfec96369836d9d308cc60f2f504ac9
# backtestId: c7ebc9a7ef5afa2dc59b9173213d78a7
# title: 【纳指增强】纳指ETF溢价套利策略

# 导入函数库
from jqdata import *

# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    g.st_code='513300.XSHG'
    g.st_code = '161130.XSHE'
    set_benchmark(g.st_code)
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    set_slippage(FixedSlippage(0),type=None, ref=None)
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')

    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    # set_order_cost(OrderCost(close_tax=0.00, open_commission=0.000, close_commission=0.000, min_commission=0), type='stock')

    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
      # 开盘前运行
    # run_daily(before_market_open, time='before_open', reference_security='000300.XSHG')
    #   # 开盘时运行
    # run_daily(market_open, time='open', reference_security='000300.XSHG')
    #   # 收盘后运行
    # run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')
        # 初始化策略
    run_daily(inday, time='11:25')  # 核心调度方式
    # run_daily(buy_back, time='14:55')     # 每日14:55执行买回操作
    context.sold_stocks = {}              # 记录卖出股票及数量
def inday(context):
    if context.portfolio.available_cash>10000:
        order_target_value('513300.XSHG', context.portfolio.available_cash)
        
    stock1='161130.XSHE'
    stock2='513300.XSHG'
    data1 = attribute_history(stock1, 20, unit='1d',
            fields=['close'],skip_paused=True, df=True, fq='pre')
    data2 = attribute_history(stock2, 20, unit='1d',
            fields=['close'],skip_paused=True, df=True, fq='pre')
    tt=(data1.pct_change()-data2.pct_change()).cumsum()
    # print('(tt-tt.rolling(5).mean()).iloc[-1]',(tt-tt.rolling(5).mean()),\
    # (tt-tt.rolling(5).mean()).iloc[-1]['close'])
    # print(str(data2.index[-1])[:10],str(data2.iloc[-1].index[0])[:10]=='2024-05-15')
    # if str(data2.index[-1])[:10]=='2024-05-15':
    #     print((tt-tt.rolling(5).mean())['close'])
    if (tt-tt.rolling(5).mean()).iloc[-1]['close']>0.005 and (tt-tt.rolling(5).mean())['close'].iloc[-2]<0.005:
        print('sell stock1,buy stock2',context.portfolio.positions.keys())
        print((tt-tt.rolling(5).mean())['close'])
        for stock in list(context.portfolio.positions.keys()):
            if stock == stock2:
                print('无需调仓')
                return
            order_target(stock, 0)
        print('context.portfolio.available_cash',context.portfolio.available_cash)
        order_target(stock2, context.portfolio.available_cash)
    
    
    if (tt-tt.rolling(5).mean())['close'].iloc[-1]<-0.005 and (tt-tt.rolling(5).mean())['close'].iloc[-2]>-0.005:
        print('sell stock2,buy stock1',context.portfolio.positions.keys())
        print((tt-tt.rolling(5).mean())['close'])
        for stock in list(context.portfolio.positions.keys()):
            if stock == stock1:
                print('无需调仓')
                return
            order_target(stock, 0)
        print('context.portfolio.available_cash',context.portfolio.available_cash)
        order_target(stock1, context.portfolio.available_cash)
       