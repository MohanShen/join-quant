# Clone from JoinQuant
# postId: 68a9fe59553afec5f02c09817470d601
# backtestId: 7f1c1db2d6ee5be6df76c9e297da6f43
# title: 因子BIAS5在指定的钢铁股票池里回测，为啥效果那么好

# 导入函数库
from jqdata import *
from six import BytesIO
import pandas as pd
from jqfactor import get_factor_values

# 初始化函数，设定基准等等
def initialize(context):

    # 设定ZZ500作为基准
    set_benchmark('000905.XSHG')
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
    run_weekly(before_market_open, weekday = 1, time='9:15', reference_security='000300.XSHG')
      # 开盘时运行
    run_weekly(market_open, weekday = 1,  time='9:30', reference_security='000300.XSHG')
      # 收盘后运行
    run_weekly(after_market_close, weekday = 1,  time='after_close', reference_security='000300.XSHG')

## 开盘前运行函数
def before_market_open(context):
    # 输出运行时间
    log.info('函数运行时间(before_market_open)：' + str(context.current_dt.time()))

    # 给微信发送消息（添加模拟交易，并绑定微信生效）
    # send_message('美好的一天~')

    # 要操作的股票：（g.为全局变量）
    g.security = ["600808.XSHG", "600782.XSHG", "000959.XSHE",
                  "000932.XSHE", "000717.XSHE", "000825.XSHE",
                  "600282.XSHG", "600307.XSHG", "600019.XSHG",
                  "000898.XSHE", "002110.XSHE", "601005.XSHG", 
                  "600010.XSHG", "000709.XSHE", "002075.XSHE"]
    factor = "BIAS5"
    g.N = 5
    df_factor = get_factor_values(g.security, factor, context.run_params.start_date, context.run_params.end_date)
    g.topN_stocks = df_factor[factor].loc[context.current_dt.date()].sort_values(ascending=False)[:g.N].index.tolist()
    print(df_factor[factor].loc[context.current_dt.date()].sort_values(ascending=False)[:g.N])
## 开盘时运行函数
def market_open(context):
    log.info('函数运行时间(market_open):'+str(context.current_dt.time()))
    cash = context.portfolio.available_cash
    # 如果目前组合为空，用所有cash买入因子值前五的股票
    if not context.portfolio.positions:
        for security in g.topN_stocks:
            log.info(f"买入{security}")
            order_value(security, cash/g.N)
    else:
        # 进行换仓动作，如果现有组合跟下一期股票清单是一致的，则pass不进行操作
        if g.topN_stocks.index == context.portfolio.positions.keys():
            pass
        else:
            i = 0
            #对于已经不再出现在新的交易清单里的股票进行清仓，并确定有多少个
            for security in context.portfolio.positions.keys():
                if security not in g.topN_stocks:
                    log.info(f"卖出{security}")
                    order_target(security, 0)
                    i = i + 1
            remaining_cash = context.portfolio.available_cash
            #对于出现在新的交易清单，但不在原来组合里的股票进行建仓
            for security in g.topN_stocks:
                if security not in context.portfolio.positions.keys():
                    log.info(f"买入{security}")
                    order_value(security, remaining_cash/i)

## 收盘后运行函数
def after_market_close(context):
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    #得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    log.info('一天结束')
    log.info('##############################################################')
