# Clone from JoinQuant
# postId: ea19dc7a2773c2466111af0a5bbd80ac
# backtestId: f6d30e0af779bffb1f181dcc7243d102
# title: [原]四行代码打通聚宽到迅投(支持多策略)[最新版]

## ↓↓↓ 第300~1210行，为发送端tools_v6.3.py完整内容 ↓↓↓↓
## ↓↓↓ 第1300~4112行，为接收端recv6.5.3.py完整内容 ↓↓↓↓
# 详见 https://www.joinquant.com/view/community/detail/75424

import tools_v6
from jqdata import *

# 初始化函数，设定基准等等
def initialize(context):
    tools_v6.setup(context, '填你的策略名')
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    # 过滤掉order系列API产生的比error级别低的log
    log.set_level('order', 'error')

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
    g.security = '603629.XSHG'

## 开盘时运行函数
def market_open(context):
    log.info('函数运行时间(market_open):'+str(context.current_dt.time()))
    security = g.security
    # 获取股票的收盘价
    close_data = get_bars(security, count=5, unit='1d', fields=['close'])
    # 取得过去五天的平均价格
    MA5 = close_data['close'].mean()
    # 取得上一时间点价格
    current_price = close_data['close'][-1]
    # 取得当前的现金
    cash = context.portfolio.available_cash

    # 如果上一时间点价格高出五天平均价1%, 则全仓买入
    if (current_price > 1.01*MA5) and (cash > 0):
        # 记录这次买入
        log.info("价格高于均价 1%%, 买入 %s" % (security))
        # 用所有 cash 买入股票
        order_value(security, cash)
    # 如果上一时间点价格低于五天平均价, 则空仓卖出
    elif current_price < MA5 and context.portfolio.positions[security].closeable_amount > 0:
        # 记录这次卖出
        log.info("价格低于均价, 卖出 %s" % (security))
        # 卖出所有股票,使这只股票的最终持有量为0
        order_target(security, 0)

## 收盘后运行函数
def after_market_close(context):
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    #得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    log.info('一天结束')
    log.info('##############################################################')


## tools_v6.py工具在第300行
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
"""
    tools_v6.0版本的redis发送信号示例：
    ============================================================
    📩 [13:56:00.323] 收到交易信号
      策略: 你的牛逼策略
      标的: 159819.XSHE
      操作: 🔴 卖出
      数量: 124600股
      价格: 1.729元
      成交金额: 215433.4元
      目标仓位: 49.95%
      信号时间: 2026-04-29 13:56:00
      延迟: 聚宽→Redis 111.7 ms | Redis→本地 90.6 ms | 总计 202.3 ms
    ============================================================

"""
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓���↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓

## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓ 第300~1210行，为发送端tools_v6.3.py完整内容 ↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓


# =============================================================
# v6.3.3 变更:
#   - 信号传输方式: publish → rpush (Redis list + blpop，保证消息不丢)
# =============================================================
# 信号转发工具tools_v6.3（基于 v6.2 日志优化版）
# 原创：🐷猪头战法  From https://www.joinquant.com/view/community/detail/75424
# v5.4.2 修复：
#   - refresh 30秒去重保护（按策略名隔离）
#   - check_and_fix 轻量检测（严格检测user_code.order）
#   - 企微缓冲优化（5秒/10条/18次每分钟滑动窗口限频）
# v6.0 2026-05-12 功能：
#   - 支持企业微信/飞书/Redis(连接MiniQMT/QMT)三种信号推送
# v6.1 2026-05-13 变更（仅日志措辞优化，功能零改动）：
#   - 7处日志措辞优化，消除"失败"/"失效"/"严重错误"等误导性措辞
#   - check_and_fix 修复成功后新增 ✅ 确认日志
#   - 策略端精简：process_initialize 由工具端兜底，策略端无需再写 tools_v6.refresh()
#   - check_and_fix 静默化：user_code.order 有效时不再打印日志，仅失效/异常时输出
#   - run_daily 同分钟去重：09:30/13:00 同一分钟内只执行一次 refresh，避免日志刷屏
# v6.2 2026-05-23 变更：
#   - 策略名问题修复：解决老策略无法正常传递策略名的问题。
# v6.3 2026-05-24 变更：
#   - 对接直连：优化连接方式，适配WindowsServer版Redis-x64-5.0.14.1。
# =============================================================
import json, time, datetime, threading, requests, sys, redis

# ====================================================================================================== 配置开始
# ------------------------常用配置（必须改）------------------------------------------------------------
redis_enabled = True       # Redis 总开关：True=启用推送 | False=关闭
CONNECT_MODE = "direct"     # Redis连接方式："url"=URL连接（只需填下面的REDIS_URL）|"direct"=直连（需填下面的HOST/PORT/PASSWORD）
CHANNELS = ["jq_signals", "jq_signals_local"]       # 云服务器 + 本地Redis发布频道（接收端监听的频道名，两边必须一致）
# ---------------------------------------------------------------------------
# 【企业微信】填你的群机器人 Webhook 地址，获取方式：企业微信群 → 添加群机器人 → 复制 Webhook URL
wechat_enabled = True       # 企业微信总开关：True=启用 | False=关闭
WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=填你的群机器人Webhook 地址"
# ---------------------------------------------------------------------------
feishu_enabled = False      # 飞书总开关：True=启用 | False=关闭
FEISHU_WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/你的key"       # 【飞书】填你的群机器人 Webhook 地址（可选）
# ---------------------------------------------------------------------------
# 调试开关：
#   True = 打印详细诊断日志（测试期建议开，可看到 wrapper 自修复、绑定等信息）
#   False = 只打印关键日志（正式上线后建议关，减少日志噪音）
DEBUG = False
# ------------------------扩展配置（按需改）------------------------------------------------------------
# 【直连模式】参数（仅当 CONNECT_MODE="direct" 时生效）
REDIS_HOST, REDIS_PORT, REDIS_PASSWORD = "123.123.123.123", 1234, "123456"
# 【URL 模式】填你的 Upstash Redis 地址 | 格式：rediss://default:密码@主机:端口
REDIS_URL = "rediss://default:填你的 Upstash Redis 地址@主机.upstash.io:6379"
# ---------------------------------------------------------------------------
# 企业微信缓冲参数（v5.4 优化：降低单条合并上限、增加频率限制）
BUFFER_WAIT_TIME = 5  # 缓冲等待秒数（v5.4: 从2秒增至5秒，合并更多消息）
MAX_BUFFER_SIZE = 10  # 单条合并消息最大条数（v5.4: 从20降至10，避免超限）
MAX_SEND_PER_MINUTE = 18  # v5.4 新增：每分钟最多发送次数（企微限制20条，留2条余量）
# --------------------------------------------------------------------------------------------------
# ====================================================================================================== 配置结束


def _log(msg):
    print(f"[🐷tools] {msg}")


def _dbg(msg):
    if DEBUG:
        print(f"[🐷tools][dbg] {msg}")


# ---------- 状态存取 ----------
_ctx_cache = {}
_stock_name_cache = {}
_last_refresh_ts = {}
_last_morning_minute = None
_last_afternoon_minute = None


def _get_g():
    if 'kuanke.user_space_api' in sys.modules:
        return sys.modules['kuanke.user_space_api'].g
    return None


def _get_strategy_name():
    g = _get_g()
    if g and hasattr(g, '_strategy_name') and g._strategy_name and g._strategy_name != "未命名策略":
        return g._strategy_name

    # 新增：从调用模块的全局变量读取 STRATEGY_NAME
    try:
        import inspect
        frame = inspect.currentframe()
        while frame:
            module = inspect.getmodule(frame)
            if module and hasattr(module, 'STRATEGY_NAME'):
                return module.STRATEGY_NAME
            frame = frame.f_back
    except:
        pass

    return "未命名策略"


def _get_ctx():
    # 获取当前策略context（从g._tools_ctx读取，由wrapper每次order时更新）
    g = _get_g()
    if g and hasattr(g, '_tools_ctx') and g._tools_ctx is not None:
        return g._tools_ctx
    # 回退到 _ctx_cache
    name = _get_strategy_name()
    ctx = _ctx_cache.get(name)
    if ctx:
        return ctx
    # 如果通过名称找不到，尝试返回任何可用的 context（单策略场景）
    if _ctx_cache:
        return next(iter(_ctx_cache.values()))
    return None


def _get_stock_name(stock_code):
    if stock_code in _stock_name_cache:
        return _stock_name_cache[stock_code]
    try:
        from jqdata import get_security_info
        info = get_security_info(stock_code)
        name = getattr(info, 'display_name', '') or ''
        _stock_name_cache[stock_code] = name
        return name
    except Exception:
        _stock_name_cache[stock_code] = ''
        return ''


# ---------- Redis ----------
_redis_client = None


def _init_redis():
    global _redis_client
    if not redis_enabled or redis is None:
        return False
    try:
        if CONNECT_MODE == "direct":
            _redis_client = redis.Redis(
                host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD,
                decode_responses=True, socket_connect_timeout=5, socket_keepalive=True
            )
        else:
            _redis_client = redis.from_url(
                REDIS_URL, decode_responses=True,
                socket_connect_timeout=5, socket_timeout=5,
                retry_on_timeout=True, ssl_cert_reqs=None
            )
        _redis_client.ping()
        return True
    except Exception as e:
        _redis_client = None
        _log(f"Redis 连接失败: {e}")
        return False


def _ensure_redis():
    global _redis_client
    if not redis_enabled or redis is None:
        return False
    if _redis_client:
        try:
            _redis_client.ping()
            return True
        except Exception:
            _redis_client = None
            _dbg("Redis 连接已失效，准备重建")
    return _init_redis()


def _send_signal(code, action, amount, price, dt_str=None, weight=None, extra=None):
    global _redis_client
    if not _ensure_redis():
        return False
    if dt_str is None:
        dt_str = time.strftime("%Y-%m-%d %H:%M:%S")
    signal_id = f"{_get_strategy_name()}:{code}:{action}:{abs(int(amount))}:{int(time.time() * 1000)}"
    data = {
        "msg_version": "1.0",
        "signal_id": signal_id,
        "strategy_name": _get_strategy_name(),
        "security": str(code),
        "action": "buy" if action in ("buy", "买入") else "sell",
        "current_price": float(price),
        "amount_diff": abs(int(amount)),
        "trade_value": round(float(price) * int(amount), 2),
        "weight": weight or "N/A",
        "xdsj": dt_str,
        "current_time": time.time()
    }
    if extra and isinstance(extra, dict):
        data.update(extra)
    try:
        for ch in CHANNELS:
            result = _redis_client.rpush(ch, json.dumps(data, ensure_ascii=False))
            _log(f"rpush {ch} 结果: {result} (类型: {type(result).__name__})")
        return True
    except Exception as e:
        _redis_client = None
        _log(f"Redis 发送异常: {e}")
        return False


# ---------- 企业微信 ----------
_wechat_buffer = None


class _WeChatBuffer:
    def __init__(self, url, wait, max_size, max_per_minute=18):
        self.url, self.wait, self.max_size = url, wait, max_size
        self.max_per_minute = max_per_minute
        self.buf, self.timer, self.lock = [], None, threading.Lock()
        self.send_history = []  # 记录发送时间戳，用于滑动窗口频率限制

    def _can_send(self):
        now = time.time()
        # 清理1分钟前的记录
        self.send_history = [t for t in self.send_history if now - t < 60]
        return len(self.send_history) < self.max_per_minute

    def _send(self):
        with self.lock:
            if not self.buf:
                return
            # 检查频率限制
            if not self._can_send():
                _log("微信缓冲: 频率超限(>18条/分钟)，延迟到下一分钟发送")
                if self.timer:
                    self.timer.cancel()
                self.timer = threading.Timer(60, self._send)
                self.timer.start()
                return

            sep = "\n" + "-" * 28 + "\n"
            recent = self.buf[-self.max_size:]
            omitted = len(self.buf) - self.max_size
            if omitted > 0:
                parts = [f"...(前略 {omitted} 条)", sep, sep.join(recent)]
                merged = "\n".join(parts)
            else:
                merged = sep.join(recent)
            self.buf.clear()
            self.timer = None

        try:
            encoded = merged.encode('utf-8')
            if len(encoded) > 2048:
                truncated = encoded[:2048].decode('utf-8', errors='ignore')
                merged = truncated + "\n...[消息过长已截断]"
            resp = requests.post(
                self.url,
                json={"msgtype": "text", "text": {"content": merged}},
                timeout=5
            )
            if resp.status_code == 200:
                self.send_history.append(time.time())
                _dbg(f"微信发送成功，当前分钟已发 {len(self.send_history)} 次")
            return resp.status_code == 200
        except Exception:
            return False

    def add(self, content, ts=None):
        if ts is None:
            ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        force_send = False
        with self.lock:
            self.buf.append(f"[{ts}] {content}")
            # v5.4 强制发送：超过 max_size 立即发送，不等待 timer
            if len(self.buf) >= self.max_size:
                force_send = True
                if self.timer:
                    self.timer.cancel()
                    self.timer = None
            elif not self.timer:
                self.timer = threading.Timer(self.wait, self._send)
                self.timer.start()

        if force_send:
            self._send()

    def flush(self):
        if self.timer:
            self.timer.cancel()
            self.timer = None
        return self._send()


def _send_wechat(action, sec, amt, price, order_dt=None, weight=None, trade_val=None):
    if not wechat_enabled or not _wechat_buffer:
        return False
    emoji = "🔴" if action in ("buy", "买入") else "🟢"
    act_str = "买入" if action in ("buy", "买入") else "卖出"
    if isinstance(order_dt, datetime.datetime):
        xdsj = order_dt.strftime('%Y-%m-%d %H:%M:%S')
    elif isinstance(order_dt, str):
        xdsj = order_dt
    else:
        xdsj = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if trade_val is None:
        trade_val = round(price * abs(int(amt)), 2)
    content = (
        f"{emoji} {act_str} {sec}\n"
        f"策略: {_get_strategy_name()}\n"
        f"数量: {abs(int(amt))} 股\n"
        f"价格: {price:.3f} 元\n"
        f"成交金额: {trade_val:.2f} 元\n"
        f"目标仓位: {weight or 'N/A'}\n"
        f"信号时间: {xdsj}"
    )
    _wechat_buffer.add(content, ts=xdsj)
    return True


# ---------- 飞书 ----------
def _send_feishu(action, sec, amt, price, order_dt=None, weight=None, trade_val=None):
    if not feishu_enabled:
        return False
    emoji = "🟢" if action in ("buy", "买入") else "🔴"
    act_str = "买入" if action in ("buy", "买入") else "卖出"
    if isinstance(order_dt, datetime.datetime):
        xdsj = order_dt.strftime('%Y-%m-%d %H:%M:%S')
    elif isinstance(order_dt, str):
        xdsj = order_dt
    else:
        xdsj = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if trade_val is None:
        trade_val = round(price * abs(int(amt)), 2)
    content = (
        f"{emoji} **{act_str} {sec}**\n"
        f"策略: {_get_strategy_name()}\n"
        f"数量: {abs(int(amt))} 股\n"
        f"价格: {price:.3f} 元\n"
        f"成交金额: {trade_val:.2f} 元\n"
        f"目标仓位: {weight or '无'}\n"
        f"信号时间: {xdsj}"
    )
    try:
        data = {"msg_type": "text", "content": {"text": content}}
        r = requests.post(FEISHU_WEBHOOK_URL, json=data, timeout=3)
        if r.status_code == 200 and r.json().get("code") == 0:
            return True
    except Exception:
        pass
    return False


# ---------- 供外部策略使用的工具函数（tools 内部不调用） ----------
def _is_special_trading_time(context=None):
    '''判断当前是否为特殊时段（9:26-9:30 或 14:57-15:00）
    tools 内部（_report_order）和外部策略均可调用
    
    Args:
        context: 可选，回测时传入以使用逻辑时间（context.current_dt）
                实盘/实时模拟可不传，使用 datetime.now()
    '''
    try:
        from datetime import datetime, time
        
        # 优先使用 context 的逻辑时间（回测环境）
        if context is not None and hasattr(context, 'current_dt'):
            t = context.current_dt.time()
        else:
            t = datetime.now().time()
            
        if time(9, 26, 0) <= t <= time(9, 30, 0):
            return True
        if time(14, 57, 0) <= t <= time(15, 0, 0):
            return True
    except Exception:
        pass
    return False


# ---------- 统一订单上报（v6.3.4 修复版：兼容 9:26-9:30 集合竞价数据未就绪） ----------
def _report_order(order, weight=None, order_value=None):
    if order is None:
        return
    amt = order.amount
    if abs(amt) <= 0:
        _dbg(f"过滤零数量订单: {getattr(order, 'security', 'N/A')}")
        return

    # 【前置】先提取订单时间，后续多处使用
    order_time = getattr(order, 'add_time', None)

    # ========== 价格获取：兼容 9:26-9:30 集合竞价数据未就绪 ==========
    prc = 0.0

    # 1. 优先 order.price（委托价/成交价）
    try:
        if order.price and float(order.price) > 0:
            prc = float(order.price)
    except Exception:
        pass

    # 2. 其次 avg_cost（实际成交均价）—— 仅买入订单使用！
    # ⚠️ 卖出订单的 avg_cost 是持仓成本价，不能作为卖出价格
    if prc <= 0 and getattr(order, 'is_buy', False):
        try:
            avg_cost = float(getattr(order, 'avg_cost', 0) or 0)
            if avg_cost > 0:
                prc = avg_cost
                _dbg(f"avg_cost 买入成交: {order.security}={prc}")
        except Exception:
            pass

    # 3. 再试 get_current_data（需要从策略主模块获取全局函数）
    if prc <= 0:
        try:
            # get_current_data 是聚宽注入到 __main__ / user_code 的全局函数
            # tools 模块内不能直接访问，需通过 sys.modules 获取
            import sys
            gcd = None
            for mod_name in ('__main__', 'user_code', '__builtin__', 'builtins'):
                mod = sys.modules.get(mod_name)
                if mod and hasattr(mod, 'get_current_data'):
                    gcd = mod.get_current_data
                    break
            if gcd is None:
                # 回退到 globals()
                gcd = globals().get('get_current_data')
            if gcd:
                data = gcd()[order.security]
                # 9:26-9:30 集合竞价期间，day_open 比 last_price 更可靠
                # last_price 此时可能是昨收，不是开盘价
                for field in ['day_open', 'last_price', 'high_limit', 'low_limit']:
                    val = getattr(data, field, None)
                    if val and float(val) > 0:
                        prc = float(val)
                        break
        except Exception as e:
            _dbg(f"get_current_data 获取失败: {e}")

    # 3.5 尝试 get_call_auction（聚宽专门取集合竞价数据的 API）
    if prc <= 0:
        try:
            # 同样需要从主模块获取全局函数
            import sys
            gca = None
            for mod_name in ('__main__', 'user_code', '__builtin__', 'builtins'):
                mod = sys.modules.get(mod_name)
                if mod and hasattr(mod, 'get_call_auction'):
                    gca = mod.get_call_auction
                    break
            if gca is None:
                gca = globals().get('get_call_auction')
            if gca:
                today_str = order_time.strftime('%Y-%m-%d') if isinstance(order_time, datetime.datetime) else time.strftime('%Y-%m-%d')
                df = gca(order.security, start_date=today_str, end_date=today_str, fields=['current'])
                if df is not None and not df.empty:
                    price = float(df['current'].iloc[0])
                    if price > 0:
                        prc = price
                        _dbg(f"get_call_auction 兜底: {order.security}={prc}")
        except Exception as e:
            _dbg(f"get_call_auction 获取失败: {e}")

    # 4. 已删除：腾讯API兜底（已验证聚宽 day_open 在9:26可用，无需外部依赖）
    #    保留 get_call_auction 作为聚宽内部兜底

    # 5. 最终兜底：即使价格仍为 0，也强制发出信号（避免信号丢失）
    if prc <= 0:
        prc = 0.0
        _dbg(f"⚠️ 价格获取全部失败，强制 price=0: {order.security}")

    # ========== 订单信息组装 ==========
    # 价格字段为 0 也比"毛信号都没有"强，至少能知道发生了交易
    if prc <= 0:
        prc = 0.0
        _log(f"⚠️ 警告: {order.security} 未能获取有效价格，使用 0 作为 fallback，请检查数据接口")

    # ========== 后续逻辑保持 v6.3.3 原样 ==========
    s = str(order.security)
    a = "买入" if order.is_buy else "卖出"
    order_time = getattr(order, 'add_time', None)
    dt_str = order_time.strftime("%Y-%m-%d %H:%M:%S") if isinstance(order_time, datetime.datetime) else time.strftime("%Y-%m-%d %H:%M:%S")
    trade_val = round(prc * abs(amt), 2)
    _log(f"信号: {a} {s} {abs(amt)}股 @ {prc:.3f} | weight={weight or 'N/A'} | val={trade_val:.2f}")

    redis_ok = False
    wx_ok = False
    fs_ok = False
    redis_err = ""
    wx_err = ""
    fs_err = ""
    try:
        redis_ok = _send_signal(s, a, abs(amt), prc, dt_str=dt_str, weight=weight)
    except Exception as e:
        redis_err = str(e)
    try:
        wx_ok = _send_wechat(a, s, amt, prc, order_dt=order_time, weight=weight, trade_val=trade_val)
    except Exception as e:
        wx_err = str(e)
    try:
        fs_ok = _send_feishu(a, s, abs(amt), prc, order_dt=order_time, weight=weight, trade_val=trade_val)
    except Exception as e:
        fs_err = str(e)
    status = []
    if redis_ok:
        status.append("Redis ✓")
    else:
        status.append(f"Redis ✗ {redis_err}" if redis_err else "Redis ✗")
    if wx_ok:
        status.append("微信 ✓")
    else:
        status.append(f"微信 ✗ {wx_err}" if wx_err else "微信 ✗")
    if fs_ok:
        status.append("飞书 ✓")
    else:
        status.append(f"飞书 ✗ {fs_err}" if fs_err else "飞书 ✗")
    _log(f"推送结果: {' | '.join(status)}")


# ---------- cancel_order ----------
def _report_cancel(order):
    if order is None:
        return
    try:
        s = str(order.security)
        oid = str(getattr(order, 'order_id', ''))
        dt_str = time.strftime("%Y-%m-%d %H:%M:%S")
        signal_id = f"cancel:{_get_strategy_name()}:{oid}:{int(time.time() * 1000)}"
        data = {
            "msg_version": "1.0",
            "signal_id": signal_id,
            "strategy_name": _get_strategy_name(),
            "security": s,
            "action": "cancel",
            "order_id": oid,
            "xdsj": dt_str,
            "current_time": time.time()
        }
        _log(f"信号: 撤单 {s} order_id={oid}")
        if _ensure_redis():
            for ch in CHANNELS:
                _redis_client.rpush(ch, json.dumps(data, ensure_ascii=False))
        _send_wechat("cancel", s, 0, 0, weight="撤单", trade_val=0)
        _send_feishu("cancel", s, 0, 0, weight="撤单", trade_val=0)
    except Exception as e:
        _log(f"撤单信号异常: {e}")


# ---------- 装饰器 ----------
def _make_wrapper(original_func, func_name):
    if getattr(original_func, '_tools_wrapped', False):
        original_func = original_func._tools_original

    def wrapper(*a, **k):
        # 每次order调用时，从调用栈获取最新context并更新g._tools_ctx
        #（解决聚宽回测中context.portfolio对象被替换导致g._tools_ctx指向旧对象的问题）
        try:
            import inspect
            frame = inspect.currentframe()
            while frame:
                if 'context' in frame.f_locals:
                    ctx = frame.f_locals['context']
                    if ctx and hasattr(ctx, 'portfolio'):
                        g = _get_g()
                        if g:
                            g._tools_ctx = ctx
                        break
                frame = frame.f_back
        except Exception:
            pass

        try:
            import jqdata
            current_jq = getattr(jqdata, func_name, None)
            if current_jq is not wrapper and not getattr(current_jq, '_tools_wrapped', False):
                _dbg(f"自修复: jqdata.{func_name} 被重置，重新绑定")
                setattr(jqdata, func_name, wrapper)
                um = _get_caller_module()
                if um and hasattr(um, func_name):
                    setattr(um, func_name, wrapper)
        except Exception:
            pass

        r = original_func(*a, **k)
        weight_str = "N/A"
        if func_name == 'order_target_percent':
            percent = a[1] if len(a) > 1 else k.get('percent', None)
            if percent is not None:
                weight_str = f"{percent * 100:.2f}%"
        elif func_name == 'order_target':
            target = a[1] if len(a) > 1 else k.get('amount', None)
            if target is not None:
                ctx = _get_ctx()
                if ctx and target >= 0:
                    try:
                        price = 0
                        # 1. 从订单结果获取价格
                        if r is not None:
                            orders = r if isinstance(r, list) else [r]
                            if orders and orders[0]:
                                price = float(orders[0].price) if orders[0].price else 0
                                if price <= 0:
                                    price = float(getattr(orders[0], 'avg_cost', 0) or 0)
                        # 2. 从持仓获取价格
                        if price <= 0:
                            try:
                                pos = ctx.portfolio.positions.get(a[0])
                                if pos:
                                    price = float(pos.price) if pos.price else 0
                            except Exception:
                                pass
                        # 3. 从 jqdata 获取当前价格
                        if price <= 0:
                            try:
                                from jqdata import get_current_data
                                data = get_current_data(a[0])
                                price = float(data.last_price) if data.last_price else 0
                            except Exception:
                                pass
                        if price > 0:
                            target_value = float(target) * price
                            total = ctx.portfolio.total_value
                            if total > 0:
                                weight_str = f"{(target_value / total) * 100:.2f}%"
                    except Exception:
                        pass

        elif func_name == 'order_target_value':
            target_value = a[1] if len(a) > 1 else k.get('value', None)
            if target_value is not None:
                ctx = _get_ctx()
                if ctx and ctx.portfolio.total_value > 0:
                    try:
                        weight_str = f"{(float(target_value) / ctx.portfolio.total_value) * 100:.2f}%"
                    except Exception:
                        pass

        else:
            ctx = _get_ctx()
            if ctx is not None and r is not None:
                orders = r if isinstance(r, list) else [r]
                if orders:
                    o = orders[0]
                    if o.is_buy:
                        try:
                            val = abs(o.amount) * o.price
                            # 9:26 集合竞价市价单，o.price 可能为 0，尝试获取价格
                            if val <= 0:
                                fp = float(getattr(o, 'avg_cost', 0) or 0)
                                if fp <= 0:
                                    try:
                                        import sys
                                        gcd = None
                                        for mod_name in ('__main__', 'user_code', '__builtin__', 'builtins'):
                                            mod = sys.modules.get(mod_name)
                                            if mod and hasattr(mod, 'get_current_data'):
                                                gcd = mod.get_current_data
                                                break
                                        if gcd is None:
                                            gcd = globals().get('get_current_data')
                                        if gcd:
                                            data = gcd()[o.security]
                                            for field in ['day_open', 'last_price']:
                                                fv = getattr(data, field, None)
                                                if fv and float(fv) > 0:
                                                    fp = float(fv)
                                                    break
                                    except:
                                        pass
                                val = abs(o.amount) * fp
                            total = ctx.portfolio.total_value
                            if val and total > 0:
                                weight_str = f"{(val / total) * 100:.2f}%"
                        except Exception:
                            pass
                    else:
                        try:
                            pos = ctx.portfolio.positions[o.security]
                            total_amount = pos.total_amount
                            if total_amount > 0:
                                ratio = abs(o.amount) / total_amount
                                weight_str = f"{min(100, ratio * 100):.2f}%"
                            else:
                                weight_str = "0%"
                        except Exception:
                            weight_str = "0%"
        if r is not None:
            if func_name == 'cancel_order':
                if isinstance(r, list):
                    for x in r:
                        _report_cancel(x)
                else:
                    _report_cancel(r)
            else:
                if isinstance(r, list):
                    for x in r:
                        _report_order(x, weight=weight_str)
                else:
                    _report_order(r, weight=weight_str)
        return r

    wrapper.__name__ = getattr(original_func, '__name__', func_name)
    wrapper.__qualname__ = getattr(original_func, '__qualname__', func_name)
    wrapper.__module__ = getattr(original_func, '__module__', 'jqdata')
    wrapper.__doc__ = getattr(original_func, '__doc__', None)
    wrapper._tools_wrapped = True
    wrapper._tools_original = original_func
    wrapper._tools_func_name = func_name
    return wrapper


def _patch_orders_in_module(module, force=False):
    TARGET = ['order', 'order_value', 'order_target', 'order_target_value', 'order_target_percent', 'cancel_order']
    count = 0
    for fn_name in TARGET:
        if hasattr(module, fn_name):
            current_func = getattr(module, fn_name)
            if not callable(current_func):
                continue
            if force and getattr(current_func, '_tools_wrapped', False):
                current_func = current_func._tools_original
            if not force and getattr(current_func, '_tools_wrapped', False):
                continue
            setattr(module, fn_name, _make_wrapper(current_func, fn_name))
            count += 1
    return count


def _get_caller_module():
    if 'user_code' in sys.modules:
        return sys.modules['user_code']
    import inspect
    frame = inspect.currentframe()
    try:
        while frame:
            module = inspect.getmodule(frame)
            if module and module.__name__ not in ('tools_v5', 'kuanke.user_space_api', __name__) \
                    and not module.__name__.startswith('_') \
                    and not module.__name__.startswith('jq'):
                return module
            frame = frame.f_back
    finally:
        del frame
    return None


# ==================== 模块顶层钩子（可序列化）====================
def _enhanced_process_initialize(ctx):
    # 进程重启时自动刷新，并调用用户原始函数
    _log("进程重启自动刷新注入...")
    refresh(ctx)
    um = sys.modules.get('user_code')
    if um:
        orig = getattr(um, '_tools_original_process_initialize', None)
        if orig:
            try:
                orig(ctx)
            except Exception as e:
                _log(f"用户 process_initialize 异常: {e}")


def _morning_refresh(context):
    global _last_morning_minute
    now_minute = time.strftime('%H:%M')
    if _last_morning_minute == now_minute:
        return
    _last_morning_minute = now_minute
    _log("09:30 开盘自动恢复...")
    refresh(context)


def _afternoon_refresh(context):
    global _last_afternoon_minute
    now_minute = time.strftime('%H:%M')
    if _last_afternoon_minute == now_minute:
        return
    _last_afternoon_minute = now_minute
    _log("13:00 下午开盘自动恢复...")
    refresh(context)


# ==================== 对外接口 ====================
def setup(context, name):
    global _wechat_buffer
    _ctx_cache[name] = context

    g = _get_g()
    if g:
        g._tools_ctx = context
        g._strategy_name = str(name)

    _init_redis()
    _wechat_buffer = _WeChatBuffer(WEBHOOK_URL, BUFFER_WAIT_TIME, MAX_BUFFER_SIZE, MAX_SEND_PER_MINUTE)

    strategy_module = _get_caller_module()
    try:
        import jqdata
        _patch_orders_in_module(jqdata)
    except Exception as e:
        # v6.1: "失败" → "异常"，加"将自动重试"
        _log(f"jqdata 注入异常: {e}，将自动重试")

    if strategy_module:
        _patch_orders_in_module(strategy_module)
        original_process = getattr(strategy_module, 'process_initialize', None)
        if original_process and not getattr(original_process, '_tools_wrapped', False):
            strategy_module._tools_original_process_initialize = original_process
        if not getattr(getattr(strategy_module, 'process_initialize', None), '_tools_wrapped', False):
            strategy_module.process_initialize = _enhanced_process_initialize
    else:
        # v6.1: "严重错误...可能失效" → "注意...研究环境正常"
        _log("注意：未检测到策略模块（研究环境正常），信号功能需手动调用 setup()")

    _try_register_run_daily()
    _log(
        f"策略 [{name}] 初始化完成 | Redis:{'ON' if redis_enabled else 'OFF'} | 微信:{'ON' if wechat_enabled else 'OFF'} | 飞书:{'ON' if feishu_enabled else 'OFF'}")


def refresh(context, name=None):
    global _wechat_buffer, _last_refresh_ts
    name = name or _get_strategy_name()
    now = time.time()
    if name in _last_refresh_ts and now - _last_refresh_ts[name] < 30:
        _dbg(f"refresh 去重: 策略 [{name}] 距上次刷新仅 {now - _last_refresh_ts[name]:.1f} 秒，跳过")
        return
    _last_refresh_ts[name] = now

    _ctx_cache[name] = context

    g = _get_g()
    if g:
        g._tools_ctx = context
        if name and name != "未命名策略":
            g._strategy_name = str(name)

    if wechat_enabled:
        _wechat_buffer = _WeChatBuffer(WEBHOOK_URL, BUFFER_WAIT_TIME, MAX_BUFFER_SIZE, MAX_SEND_PER_MINUTE)

    try:
        import jqdata
        _patch_orders_in_module(jqdata, force=True)
    except Exception as e:
        # v6.1: "失败" → "异常"，加"将自动重试"
        _log(f"jqdata 刷新异常: {e}，将自动重试")

    strategy_module = _get_caller_module()
    if not strategy_module and 'user_code' in sys.modules:
        strategy_module = sys.modules['user_code']
        _dbg("refresh: 通过 sys.modules 获取策略模块")

    if strategy_module:
        _patch_orders_in_module(strategy_module, force=True)
        try:
            import jqdata
            for fn_name in ['order', 'order_value', 'order_target', 'order_target_value', 'order_target_percent',
                            'cancel_order']:
                if hasattr(jqdata, fn_name):
                    jq_func = getattr(jqdata, fn_name)
                    if getattr(jq_func, '_tools_wrapped', False):
                        setattr(strategy_module, fn_name, jq_func)
        except Exception as e:
            # v6.1: "失败" → "异常"
            _dbg(f"强制同步异常: {e}")
    else:
        # v6.1: "无法获取策略模块，跳过 user_code 注入" → "策略模块未就绪，稍后 check_and_fix 会兜底"
        _dbg("策略模块未就绪，稍后 check_and_fix 会兜底")

    _log(f"策略 [{name}] 热更新恢复完成")


def _try_register_run_daily():
    try:
        uc = sys.modules.get('user_code')
        if uc and 'run_daily' in uc.__dict__:
            rd = uc.__dict__['run_daily']
        else:
            import inspect
            frame = inspect.currentframe()
            rd = None
            while frame:
                if 'run_daily' in frame.f_globals:
                    rd = frame.f_globals['run_daily']
                    break
                frame = frame.f_back
            if rd is None:
                raise NameError("run_daily not found")

        rd(_morning_refresh, time='09:30')
        rd(_afternoon_refresh, time='13:00')
        _dbg("已注册 09:30/13:00 自动恢复任务")
    except Exception as e:
        # v6.1: "注册失败" → "跳过（非 initialize 阶段，由 check_and_fix 兜底）"
        _dbg(f"run_daily 跳过（非 initialize 阶段，由 check_and_fix 兜底）")


def check_and_fix(context):
    try:
        uc = sys.modules.get('user_code')
        uc_order = getattr(uc, 'order', None) if uc else None
        uc_ok = getattr(uc_order, '_tools_wrapped', False) if uc_order else False

        if not uc_ok:
            # v6.1: "失效，触发 refresh" → "需要刷新 → 正在自动修复..."
            _log("🔄 wrapper 需要刷新 → 正在自动修复...")
            refresh(context)
            # v6.1 新增：修复成功确认
            _log("✅ 信号通道已就绪")
    except Exception as e:
        _dbg(f"check_and_fix 异常: {e}")


def flush():
    global _wechat_buffer
    if _wechat_buffer:
        ok = _wechat_buffer.flush()
        _log(f"微信缓冲强制刷出: {'成功' if ok else '失败/空'}")




## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓

## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
## ↓↓↓ 第1300~4112行，为接收端recv6.5.3.py完整内容 ↓↓↓↓
## ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓


# # !/usr/bin/env python3
# # -*- coding: utf-8 -*-
# """
# recv6.5.3.py — miniQMT 多策略信号接收端 (卖出Bug修复版)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# v6.5.3 修复内容:
#   1. [Bug Fix] 部分成交场景下卖出信号丢失 — 新增自动重试未成交部分
#   2. [Bug Fix] 卖出数量取整问题 — weight=1.0清仓时确保100%清仓
#   3. [Bug Fix] 持仓校验不足 — 卖出前双重校验total_volume和can_use_volume
#   4. [Bug Fix] 卖出后信号门唤醒 — _on_order_done失败时正确唤醒
#   5. [Bug Fix] 重试价格笼子 — 所有档位价格返回前经笼子校验
#   6. [Enhance] 卖出失败自动重试 — 最多MAX_RETRY次，每次升级对手档位
#   7. [Enhance] 完整异常捕获和日志记录

# 保留功能: weight目标仓位 | 信号门控 | 分级重试 | 价格笼子 | 自动拆单 | Redis list blpop
#         | 控制指令 | QMT健康检查 | 启动对账 | 持仓重建 | 手动指派 | 交叉验证 | 延迟统计
# """
# import os, json, time, redis, threading, sqlite3, random, requests
# from collections import defaultdict
# from queue import Queue, Empty, Full
# from xtquant import xtconstant, xtdata
# from xtquant.xttype import StockAccount
# from xtquant.xttrader import XtQuantTrader, XtQuantTraderCallback
# from datetime import datetime, time as dt_time
# from concurrent.futures import ThreadPoolExecutor

# # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# CONNECT_MODE = "direct"
# REDIS_URL = "rediss://default:填你的 Upstash Redis 地址@主机.upstash.io:6379"		# 【URL 模式】填你的 Upstash Redis 地址 | 格式：rediss://default:密码@主机:端口
# REDIS_HOST, REDIS_PORT, REDIS_PASSWORD = "123.123.123.123", 1234, "123456"	# 【直连模式】参数（仅当 CONNECT_MODE="direct" 时生效）
# CHANNEL_SIGNALS, CHANNEL_CONTROL = "cc_signals_local", "cc_control"		# 云服务器 + 本地Redis发布频道（接收端监听的频道名，两边必须一致）
# # --------------------------------------------------------------------------------------------------
# ACCOUNT_TYPE, MINI_PATH, ACCOUNT_ID = "STOCK", r"D:\国金QMT\userdata_mini", "8888800008"
# STRATEGY_INITIAL_CAPITAL = {"猪头战法1号": 550000.0, "猪头战法2号": 350000.0, "七星增强": 250000.0,  "手动": 450000.0}
# ACCOUNT_INITIAL_CAPITAL = 1800000              # 账户初始总入金，手动输入！算算你到底亏了多少钱！按实际修改！
# # --------------------------------------------------------------------------------------------------
# # ACCOUNT_INITIAL_CAPITAL = sum(STRATEGY_INITIAL_CAPITAL.values())    # 账户初始总入金，按策略配资合计进行计算！
# DB_DIR = r'D:\Code'	# 本地SQLITE库目录
# DB_PATH = os.path.join(DB_DIR, f"{ACCOUNT_ID}_v6.db")
# os.makedirs(DB_DIR, exist_ok=True)
# # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# # 是否记录回测信号（云服务器无MySQL/openpyxl时可设为False）
# ENABLE_BACKTEST = False  # 设为False时跳过回测记录、不引用MySQLdb和openpyxl
# # MySQL 配置 (用于回测记录查询股票名称)
# MYSQL_CONFIG = {'host': 'localhost', 'port': 3306, 'user': 'admin', 'passwd': 'admin123', 'db': 'pig', 'charset': 'utf8mb4'}
# # 回测记录目录
# BACKTEST_RECORD_DIR = os.path.join(DB_DIR, '回测记录')
# os.makedirs(BACKTEST_RECORD_DIR, exist_ok=True)
# # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# # 条件导入: 仅在回测启用时引用MySQLdb和openpyxl
# if ENABLE_BACKTEST:
#     import MySQLdb
#     from openpyxl import Workbook, load_workbook
#     from openpyxl.styles import Alignment, Font
# # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# INIT_BALANCE_MODE = "auto"
# WORK_START, WORK_END = "08:55", "15:15"
# TradeEnable, DEBUG_IGNORE_WORK_HOURS = True, True
# PRICE_MODE, OPPONENT_LEVEL, MAX_ORDER_VOL = "opponent", 1, 300000
# STOCK_COMMISSION_RATE, ETF_COMMISSION_RATE, MIN_COMMISSION = 0.0000854, 0.00005, 5.0
# # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# SELL_RETRY_TIERS = [
#     {"level": 1, "desc": "对手1档"}, {"level": 3, "desc": "对手3档"},
#     {"level": 5, "desc": "对手5档"}, {"cage": True, "desc": "笼子-2%边界"},
# ]
# BUY_RETRY_TIERS = [
#     {"level": 1, "desc": "对手1档"}, {"level": 3, "desc": "对手3档"},
#     {"level": 5, "desc": "对手5档"}, {"cage": True, "desc": "笼子+2%边界"},
# ]
# # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# CANCEL_WAIT_SEC, CANCEL_WAIT_SEC_AUCTION, CANCEL_SKIP_OPEN_SEC = 10, 60, 60
# MAX_RETRY, SIGNAL_DEDUP_WINDOW = 4, 30
# RECONNECT_INITIAL, RECONNECT_MAX, SIGNAL_GATE_TIMEOUT = 5, 60, 120
# PRE_CALL, CONTINUOUS, POST_CALL, CLOSED, NOON_BREAK = "pre_call", "continuous", "post_call", "closed", "noon_break"
# # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# # --- 企业微信 Debug 推送 ---
# WEWORK_DEBUG_ENABLED = True  # 开关
# WEWORK_DEBUG_KEY = "141e3521-ffe5-4086-8524-f5efa1f26cdd"  # 机器人 Webhook Key，填空则禁用推送
# WEWORK_DEBUG_URL = f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={WEWORK_DEBUG_KEY}" if WEWORK_DEBUG_KEY else ""
# WEWORK_DEBUG_MIN_INTERVAL = 2.0  # 最小发送间隔（秒），防止频率限制
# # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# #  全局状态
# xtdata.enable_hello = False
# xt_trader, _account, _qmt_connected = None, None, False
# shutdown_flag = threading.Event()
# _qmt_lock = threading.Lock()
# _trading_paused = threading.Event()
# _reconciling = threading.Event()
# _trading_paused_ts = 0

# strategy_queues, strategy_workers = {}, {}
# strategy_cache, cache_lock = {}, threading.Lock()
# strategy_gates, strategy_pending_buys, gate_lock = {}, {}, threading.RLock()
# seq_map, seq_lock = {}, threading.RLock()  # v6.5.1 修复: RLock支持重入，避免_cleanup_seq_map死锁
# _strategies_reset = set()

# # 6.4.1: QMT全局API网关 — 单线程串行化所有xt_trader调用，禁止其他线程直接调QMT API
# QMT_GATEWAY = ThreadPoolExecutor(max_workers=1, thread_name_prefix="qmt-gw")

# # 6.4.1性能优化: 待成交卖出计数器，避免_has_pending_sells全表扫描
# _pending_sell_count = defaultdict(int)  # {strategy_name: int}
# _pending_sell_lock = threading.Lock()

# # v6.5新增: 部分成交卖出重试队列 — 用于自动重试未成交的卖出股份
# _partial_sell_retry_queue = Queue(maxsize=1000)  # F1修复: 限制队列大小，防止OOM
# _partial_sell_retry_thread = None
# _partial_sell_retry_lock = threading.Lock()

# # 企微 Debug 速率控制
# _wework_queue = Queue(maxsize=200)
# _wework_last_ts = 0
# _wework_lock = threading.Lock()
# _wework_thread = None
# # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════


# def _safe_get_tick(codes):
#     try:
#         return xtdata.get_full_tick(codes)
#     except Exception:
#         return {}


# # v6.5.1 F1修复: 部分成交重试队列入队辅助函数（满时丢弃最早消息）
# def _partial_sell_retry_put(item):
#     """
#     将任务放入部分成交重试队列。
#     如果队列已满，丢弃最早的消息并记录日志，确保新任务入队。
#     防止极端行情下队列无限增长导致OOM。
#     """
#     if _partial_sell_retry_queue.full():
#         try:
#             dropped = _partial_sell_retry_queue.get_nowait()
#             print(f"  ⚠️ 部分成交重试队列已满(maxsize=1000)，丢弃最早任务: "
#                   f"{dropped.get('sec_qmt', '?')} 剩余{dropped.get('remaining_qty', 0)}股")
#             debug_wework("SKIP", dropped.get('strategy', ''), dropped.get('sec_qmt', ''),
#                          f"重试队列溢出，丢弃最早任务 | 剩余{dropped.get('remaining_qty', 0)}股")
#         except Empty:
#             pass
#     try:
#         _partial_sell_retry_queue.put_nowait(item)
#         return True
#     except Full:
#         print(f"  ❌ 部分成交重试队列仍然满，无法入队: {item.get('sec_qmt', '?')}")
#         return False


# # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# #  企业微信 Debug 推送
# # ═════════════════════════════════════════════════════════════════════════════════════��════════════════════════════════
# def _wework_worker():
#     global _wework_last_ts
#     if not WEWORK_DEBUG_ENABLED or not WEWORK_DEBUG_URL:
#         return
#     while True:
#         text = _wework_queue.get()
#         if text is None:
#             break
#         with _wework_lock:
#             now = time.time()
#             gap = WEWORK_DEBUG_MIN_INTERVAL - (now - _wework_last_ts)
#             if gap > 0:
#                 _wework_last_ts = now + gap
#             else:
#                 _wework_last_ts = now
#         if gap > 0:
#             time.sleep(gap)
#         try:
#             resp = requests.post(
#                 WEWORK_DEBUG_URL,
#                 json={"msgtype": "markdown", "markdown": {"content": text}},
#                 timeout=5
#             )
#             if resp.status_code != 200:
#                 print(f"  ⚠️ 企微推送失败: HTTP {resp.status_code} {resp.text[:80]}")
#         except Exception as e:
#             print(f"  ⚠️ 企微推送异常: {e}")


# def debug_wework(action, strategy, stock, detail, status="INFO"):
#     if not WEWORK_DEBUG_ENABLED:
#         return
#     now = datetime.now().strftime("%H:%M:%S")
#     icon_map = {
#         "SELL": "🟢", "BUY": "🔴", "FILL": "✅", "CANCEL": "🔄", "ERROR": "❌",
#         "RETRY": "🔄", "PENDING": "⏳", "TIMEOUT": "⏰", "SKIP": "⏭️",
#         "INFO": "ℹ️", "RECONNECT": "🔌",
#     }
#     icon = icon_map.get(action, "📌")
#     msg = f"━━ **<font color=\"warning\">recv接收端</font>** · {icon} **{action}** · {now} ━━\n"
#     msg += f"> 策略: <font color=\"comment\">{strategy}</font>\n"
#     if stock:
#         msg += f"> 标的: <font color=\"comment\">{stock}</font>\n"
#     msg += f"> {detail}"
#     try:
#         _wework_queue.put_nowait(msg)
#     except Full:
#         pass


# # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# #  DatabaseManager (与6.4.1一致)
# # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# class DatabaseManager:
#     def __init__(self, db_path):
#         self.db_path = db_path
#         self._init()

#     def _connect(self):
#         conn = sqlite3.connect(self.db_path, check_same_thread=False)
#         conn.execute("PRAGMA journal_mode=WAL")
#         conn.row_factory = sqlite3.Row
#         return conn

#     def _init(self):
#         with self._connect() as conn:
#             conn.executescript("""
#                 CREATE TABLE IF NOT EXISTS strategy_funds (
#                     strategy_name TEXT PRIMARY KEY, initial_capital REAL NOT NULL,
#                     available_cash REAL NOT NULL DEFAULT 0, enabled INTEGER DEFAULT 1,
#                     created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
#                 CREATE TABLE IF NOT EXISTS strategy_positions (
#                     strategy_name TEXT NOT NULL, stock_code TEXT NOT NULL,
#                     volume INTEGER NOT NULL DEFAULT 0, avg_cost REAL DEFAULT 0,
#                     PRIMARY KEY (strategy_name, stock_code));
#                 CREATE TABLE IF NOT EXISTS pending_orders (
#                     seq INTEGER PRIMARY KEY, order_id TEXT, strategy_name TEXT NOT NULL,
#                     stock_code TEXT NOT NULL, direction TEXT NOT NULL, order_qty INTEGER NOT NULL,
#                     order_price REAL NOT NULL, frozen_cash REAL DEFAULT 0, filled_qty INTEGER DEFAULT 0,
#                     submit_ts REAL NOT NULL, retry_count INTEGER DEFAULT 0, status TEXT DEFAULT 'submitted',
#                     target_amount REAL DEFAULT 0);
#                 CREATE TABLE IF NOT EXISTS signal_dedup (
#                     signal_key TEXT PRIMARY KEY, strategy_name TEXT, ts REAL NOT NULL);
#                 CREATE TABLE IF NOT EXISTS trade_records (
#                     id INTEGER PRIMARY KEY AUTOINCREMENT, strategy_name TEXT NOT NULL,
#                     stock_code TEXT NOT NULL, action TEXT NOT NULL, traded_price REAL NOT NULL,
#                     traded_volume INTEGER NOT NULL, traded_amount REAL NOT NULL, commission REAL DEFAULT 0,
#                     trade_time TEXT NOT NULL, order_id TEXT, order_remark TEXT);
#                 CREATE TABLE IF NOT EXISTS transfer_log (
#                     id INTEGER PRIMARY KEY AUTOINCREMENT, from_strategy TEXT, to_strategy TEXT,
#                     amount REAL NOT NULL, from_balance_before REAL, to_balance_before REAL,
#                     from_balance_after REAL, to_balance_after REAL, transfer_time TEXT NOT NULL,
#                     source TEXT DEFAULT 'redis_control');
#                 CREATE TABLE IF NOT EXISTS control_log (
#                     id INTEGER PRIMARY KEY AUTOINCREMENT, cmd TEXT NOT NULL, params TEXT,
#                     success INTEGER DEFAULT 0, result_msg TEXT, ts TEXT NOT NULL);
#             """)
#             conn.commit()
#             for sql in [
#                 "ALTER TABLE trade_records ADD COLUMN order_id TEXT",
#                 "ALTER TABLE trade_records ADD COLUMN order_remark TEXT",
#                 "ALTER TABLE pending_orders ADD COLUMN target_amount REAL DEFAULT 0",
#             ]:
#                 try:
#                     conn.execute(sql)
#                 except Exception:
#                     pass

#     # --- 策略资金 ---
#     def get_strategy_funds(self, s):
#         with self._connect() as c:
#             r = c.execute("SELECT * FROM strategy_funds WHERE strategy_name=?", (s,)).fetchone()
#             return dict(r) if r else None

#     def set_strategy_funds(self, s, cap, cash):
#         now = datetime.now().isoformat()
#         with self._connect() as c:
#             c.execute("INSERT OR REPLACE INTO strategy_funds VALUES(?,?,?,1,?,?)", (s, cap, cash, now, now))
#             c.commit()

#     def update_available_cash(self, s, delta):
#         now = datetime.now().isoformat()
#         with self._connect() as c:
#             c.execute("UPDATE strategy_funds SET available_cash=available_cash+?, updated_at=? WHERE strategy_name=?",
#                       (delta, now, s))
#             c.commit()

#     def set_strategy_enabled(self, s, e):
#         now = datetime.now().isoformat()
#         with self._connect() as c:
#             c.execute("UPDATE strategy_funds SET enabled=?, updated_at=? WHERE strategy_name=?",
#                       (1 if e else 0, now, s))
#             c.commit()

#     # --- 持仓 ---
#     def get_position(self, s, code):
#         with self._connect() as c:
#             r = c.execute("SELECT volume, avg_cost FROM strategy_positions WHERE strategy_name=? AND stock_code=?",
#                           (s, code)).fetchone()
#             return (r[0], r[1]) if r else (0, 0.0)

#     def get_all_positions(self, s):
#         with self._connect() as c:
#             rows = c.execute("SELECT stock_code, volume, avg_cost FROM strategy_positions WHERE strategy_name=?",
#                              (s,)).fetchall()
#             return {r[0]: {"volume": r[1], "avg_cost": r[2]} for r in rows}

#     def update_position(self, s, code, dv, price):
#         with self._connect() as c:
#             r = c.execute("SELECT volume, avg_cost FROM strategy_positions WHERE strategy_name=? AND stock_code=?",
#                           (s, code)).fetchone()
#             if r:
#                 ov, oc = r[0], r[1]
#                 nv = ov + dv
#                 if nv <= 0:
#                     c.execute("DELETE FROM strategy_positions WHERE strategy_name=? AND stock_code=?", (s, code))
#                 else:
#                     nc = (ov * oc + dv * price) / nv if dv > 0 else oc
#                     c.execute(
#                         "UPDATE strategy_positions SET volume=?, avg_cost=? WHERE strategy_name=? AND stock_code=?",
#                         (nv, nc, s, code))
#             elif dv > 0:
#                 c.execute("INSERT INTO strategy_positions VALUES(?,?,?,?)", (s, code, dv, price))
#             c.commit()

#     # --- 挂单 ---
#     def add_pending(self, seq, s, stock, d, qty, price, frozen, ts, status='submitted', ta=0.0):
#         with self._connect() as c:
#             c.execute(
#                 "INSERT OR REPLACE INTO pending_orders(seq,order_id,strategy_name,stock_code,direction,"
#                 "order_qty,order_price,frozen_cash,filled_qty,submit_ts,retry_count,status,target_amount) "
#                 "VALUES(?,NULL,?,?,?,?,?,?,0,?,0,?,?)",
#                 (seq, s, stock, d, qty, price, frozen, ts, status, ta))
#             c.commit()

#     def retry_pending(self, old_seq, np, nf, nt, new_qmt_seq=None, remark=None):
#         with self._connect() as c:
#             cur = c.execute(
#                 "UPDATE pending_orders SET order_id=NULL, order_price=?, frozen_cash=?, status='submitted', "
#                 "submit_ts=?, retry_count=retry_count+1 WHERE seq=? AND status NOT IN ('filled','cancelled')",
#                 (np, nf, nt, old_seq))
#             c.commit()
#             return cur.rowcount > 0

#     def update_pending_order_id(self, seq, oid, status='acked'):
#         with self._connect() as c:
#             c.execute("UPDATE pending_orders SET order_id=?, status=? WHERE seq=?", (str(oid), status, seq))
#             c.commit()

#     def update_pending_filled(self, seq, av):
#         with self._connect() as c:
#             c.execute("UPDATE pending_orders SET filled_qty=filled_qty+?, "
#                       "status=CASE WHEN filled_qty+?>=order_qty THEN 'filled' ELSE 'partial' END WHERE seq=?",
#                       (av, av, seq))
#             c.commit()

#     def update_pending_retry(self, seq, rc):
#         with self._connect() as c:
#             cur = c.execute("UPDATE pending_orders SET retry_count=? WHERE seq=?", (rc, seq))
#             c.commit()
#             return cur.rowcount > 0

#     def update_pending_status(self, seq, st):
#         with self._connect() as c:
#             c.execute("UPDATE pending_orders SET status=? WHERE seq=?", (st, seq))
#             c.commit()

#     def delete_pending(self, seq):
#         with self._connect() as c:
#             c.execute("DELETE FROM pending_orders WHERE seq=?", (seq,))
#             c.commit()

#     def get_all_pending(self):
#         with self._connect() as c: return [dict(r) for r in c.execute("SELECT * FROM pending_orders").fetchall()]

#     def get_pending_by_seq(self, seq):
#         with self._connect() as c:
#             r = c.execute("SELECT * FROM pending_orders WHERE seq=?", (seq,)).fetchone()
#             return dict(r) if r else None

#     def get_pending_by_order_id(self, oid):
#         with self._connect() as c:
#             r = c.execute("SELECT * FROM pending_orders WHERE order_id=?", (str(oid),)).fetchone()
#             return dict(r) if r else None

#     def try_claim_for_retry(self, seq):
#         with self._connect() as c:
#             return c.execute(
#                 "UPDATE pending_orders SET status='retrying' WHERE seq=? AND status IN ('submitted','partial','acked')",
#                 (seq,)).rowcount > 0

#     def claim_for_cancel(self, seq):
#         with self._connect() as c:
#             return c.execute(
#                 "UPDATE pending_orders SET status='cancelled' WHERE seq=? AND status NOT IN ('cancelled','retrying')",
#                 (seq,)).rowcount > 0

#     # --- 去重 ---
#     def is_signal_dup(self, key, window=SIGNAL_DEDUP_WINDOW):
#         with self._connect() as c:
#             r = c.execute("SELECT ts FROM signal_dedup WHERE signal_key=?", (key,)).fetchone()
#             if r and (time.time() - r[0]) < window: return True
#             c.execute("INSERT OR REPLACE INTO signal_dedup VALUES(?,?,?)", (key, '', time.time()))
#             c.execute("DELETE FROM signal_dedup WHERE ts<?", (time.time() - window * 2,))
#             c.commit()
#             return False

#     # --- 成交记录 ---
#     def add_trade(self, s, code, action, price, vol, amt, comm, ts, oid='', remark=''):
#         with self._connect() as c:
#             c.execute("INSERT INTO trade_records VALUES(NULL,?,?,?,?,?,?,?,?,?,?)",
#                       (s, code, action, price, vol, amt, comm, ts, oid, remark))
#             c.commit()

#     def get_trade_by_remark(self, remark, code, vol, price):
#         with self._connect() as c:
#             return c.execute(
#                 "SELECT id FROM trade_records WHERE order_remark=? AND stock_code=? AND traded_volume=? AND traded_price=?",
#                 (remark, code, vol, price)).fetchone() is not None

#     # --- 转账/控制日志 ---
#     def add_transfer_log(self, fs, ts, amt, fb, tb, fa, ta, src='redis_control'):
#         now = datetime.now().isoformat()
#         with self._connect() as c:
#             c.execute("INSERT INTO transfer_log(from_strategy,to_strategy,amount,from_balance_before,"
#                       "to_balance_before,from_balance_after,to_balance_after,transfer_time,source) "
#                       "VALUES(?,?,?,?,?,?,?,?,?)", (fs, ts, amt, fb, tb, fa, ta, now, src))
#             c.commit()

#     def add_control_log(self, cmd, params, ok, msg):
#         now = datetime.now().isoformat()
#         with self._connect() as c:
#             c.execute("INSERT INTO control_log(cmd,params,success,result_msg,ts) VALUES(?,?,?,?,?)",
#                       (cmd, json.dumps(params, ensure_ascii=False) if isinstance(params, dict) else str(params),
#                       ok, msg, now))
#             c.commit()


# db = DatabaseManager(DB_PATH)


# # ═══════════════════════════════════════════════════════════
# #  QMT 回调 (v6.5/v6.5.1: 修复部分成交处理 + 信号门唤醒 + F1F2F3修复)
# # ═══════════════════════════════════════════════════════════
# class _CB(XtQuantTraderCallback):
#     def on_disconnected(self):
#         global _qmt_connected
#         _qmt_connected = False
#         print(f"{datetime.now()} ⚠️ QMT连接断开")

#     def on_order_stock_async_response(self, resp):
#         seq = getattr(resp, 'seq', 0)
#         order_id = getattr(resp, 'order_id', '')
#         if seq and order_id:
#             with seq_lock:
#                 info = seq_map.get(seq)
#             retry_of = info.get('retry_of') if info else None
#             target_seq = retry_of if retry_of else seq
#             db.update_pending_order_id(target_seq, order_id, 'acked')
#             with seq_lock:
#                 if seq in seq_map:
#                     seq_map[seq]['order_id'] = str(order_id)
#             extra = f" (重试映射→{retry_of})" if retry_of else ""
#             print(f"  ✅ 异步确认: 订单号={seq} 委托编号={order_id}{extra}")

#     def on_stock_trade(self, trade):
#         code = trade.stock_code
#         vol = trade.traded_volume
#         price = trade.traded_price
#         flag = trade.offset_flag
#         oid = str(getattr(trade, 'order_id', '') or '')
#         remark = str(getattr(trade, 'order_remark', '') or '')

#         # 成交去重
#         dedup_key = f"{oid}_{vol}_{price}"
#         with seq_lock:
#             td = seq_map.setdefault('_trade_dedup', {})
#             if dedup_key in td and (time.time() - td[dedup_key]) < 300:
#                 return
#             td[dedup_key] = time.time()

#         # 通过order_id查找挂单记录
#         info = db.get_pending_by_order_id(oid) if oid else None
#         seq = info.get('seq') if info else None

#         # 兜底: 通过remark匹配
#         if not info and remark:
#             try:
#                 pendings = db.get_all_pending()
#                 tdir = 'buy' if flag == 48 else ('sell' if flag == 49 else None)
#                 for p in pendings:
#                     if p['stock_code'] == code and p['direction'] == tdir and p['status'] not in (
#                             'filled', 'cancelled'):
#                         info, seq = p, p['seq']
#                         break
#             except Exception:
#                 pass

#         if not info:
#             return

#         s_name = info.get('strategy_name')
#         direction = info.get('direction', 'buy' if flag == 48 else 'sell')
#         frozen = info.get('frozen_cash', 0)

#         # 佣金计算
#         if frozen > 0 and info.get('order_qty', 0) > 0:
#             op = info.get('order_price', 0)
#             if op > 0:
#                 fps = frozen / info['order_qty']
#                 cps = max(0, fps - op)
#                 commission = round(cps * vol, 2)
#             else:
#                 commission = get_commission(code, vol, price)
#         else:
#             commission = get_commission(code, vol, price)

#         # 资金 & 持仓更新
#         if direction == 'buy':
#             actual_cost = vol * price + commission
#             refund = (frozen / info['order_qty']) * vol - actual_cost if frozen > 0 and info[
#                 'order_qty'] > 0 else -actual_cost
#             db.update_available_cash(s_name, refund)
#             with cache_lock:
#                 if s_name in strategy_cache:
#                     strategy_cache[s_name]['available_cash'] += refund
#             db.update_position(s_name, code, vol, price)
#             print(f"  ✅ 成交(买): {code} {vol}股@{price:.3f} 佣={commission:.2f} 解冻={refund:.2f}")
#             debug_wework("FILL", s_name, code,
#                          f"买入成交 {vol}股 @ {price:.3f} | 佣金={commission:.2f} | 解冻={refund:+.2f}")
#         else:
#             # v6.5.1 修正: 卖出时加上印花税（股票卖出才有，ETF没有）
#             stamp_duty = _get_stamp_duty(code, vol, price)
#             total_fee = commission + stamp_duty
#             proceeds = vol * price - total_fee
#             db.update_available_cash(s_name, proceeds)
#             with cache_lock:
#                 if s_name in strategy_cache:
#                     strategy_cache[s_name]['available_cash'] += proceeds
#             db.update_position(s_name, code, -vol, price)
#             fee_detail = f"佣={commission:.2f}"
#             if stamp_duty > 0:
#                 fee_detail += f" 印={stamp_duty:.2f}"
#             print(f"  ✅ 成交(卖): {code} {vol}股@{price:.3f} {fee_detail} 回款={proceeds:.2f}")
#             debug_wework("FILL", s_name, code,
#                          f"卖出成交 {vol}股 @ {price:.3f} | {fee_detail} | 回款={proceeds:+.2f}")
#             # 更新trade记录中的总费用
#             commission = total_fee

#         db.add_trade(s_name, code, direction, price, vol, vol * price, commission, datetime.now().isoformat(), oid,
#                      remark)

#         # 更新挂单状态
#         if seq:
#             db.update_pending_filled(seq, vol)
#             updated = db.get_pending_by_seq(seq)
#             new_filled = updated.get("filled_qty", 0) if updated else 0
#             oq = info.get("order_qty", 0)
#             if 0 < oq <= new_filled:
#                 print(f"  ✅ 订单完成: 订单号={seq} {new_filled}/{oq}")
#                 if direction == 'sell':
#                     _decr_pending_sells(s_name)
#                     _wake_signal_gate(s_name)
#             else:
#                 # v6.5: 部分成交时，检查是否需要自动重试未成交部分
#                 remaining = oq - new_filled
#                 print(f"  📊 部分成交: 订单号={seq} {new_filled}/{oq} 剩余{remaining}股")
#                 if direction == 'sell' and remaining > 0:
#                     # 将未成交部分加入重试队列（异步处理，避免阻塞回调线程）
#                     # v6.5.1 F2修复: 入队时递增retry_count，确保每次重试升级对手档位
#                     rc = info.get('retry_count', 0) + 1
#                     ok = _partial_sell_retry_put({
#                         "strategy": s_name,
#                         "sec_qmt": code,
#                         "remaining_qty": remaining,
#                         "price_signal": price,  # 用成交价作为参考价
#                         "retry_count": rc,
#                         "original_seq": seq,
#                         "timestamp": time.time(),
#                     })
#                     if ok:
#                         print(f"  🔄 部分成交已入重试队列: {code} 剩余{remaining}股 retry_count={rc}")
#                     else:
#                         print(f"  ⚠️ 部分成交重试队列已满，丢弃: {code} 剩余{remaining}股")

#     def on_stock_order(self, order):
#         oid = str(getattr(order, 'order_id', '') or '')
#         status = order.order_status
#         info = db.get_pending_by_order_id(oid) if oid else None
#         # 兜底匹配：order_id 可能已被重试清空，按策略名+标的+方向查找
#         if not info:
#             try:
#                 sn = str(getattr(order, 'strategy_name', '') or '')
#                 sc = str(getattr(order, 'stock_code', '') or '')
#                 of = getattr(order, 'offset_flag', 0)
#                 od2 = 'buy' if of == 48 else 'sell'
#                 if sn and sc:
#                     for p in db.get_all_pending():
#                         if p['strategy_name'] == sn and p['stock_code'] == sc and p['direction'] == od2 \
#                                 and p['status'] not in ('filled', 'cancelled'):
#                             info = p
#                             break
#             except Exception:
#                 pass
#         if not info:
#             return
#         seq = info.get('seq')
#         s_name = info.get('strategy_name')

#         if status in (53, 54, 57):  # 部撤/已撤/废单
#             direction = info.get('direction')
#             frozen = info.get('frozen_cash', 0)
#             with seq_lock:
#                 seq_map.pop(seq, None)
#             if direction == 'buy' and frozen > 0:
#                 if db.claim_for_cancel(seq):
#                     oq = info.get('order_qty', 0)
#                     fq = info.get('filled_qty', 0)
#                     release = frozen * (oq - fq) / oq if oq > 0 else frozen
#                     if release > 0:
#                         db.update_available_cash(s_name, release)
#                         with cache_lock:
#                             if s_name in strategy_cache:
#                                 strategy_cache[s_name]['available_cash'] += release
#                         print(f"  ⛔ 订单终结(买): 订单号={seq} 解冻={release:.2f}")
#                         debug_wework("CANCEL", s_name, info['stock_code'],
#                                      f"买单废单/撤单 seq={seq} | 解冻={release:.2f} | 状态码={status}")
#                     ta_retry = info.get('target_amount', 0)
#                     if ta_retry > 0:
#                         stock_jq = convert_qmt_to_jq(info['stock_code'])
#                         lp = 0.0
#                         try:
#                             tks = _safe_get_tick([info['stock_code']])
#                             if tks and info['stock_code'] in tks:
#                                 tick = tks[info['stock_code']]
#                                 lp = tick.get('lastPrice', 0) or tick.get('lastClose', 0) or 0
#                         except Exception:
#                             pass
#                         retry_buy = {
#                             'security': stock_jq, 'action': 'buy',
#                             'current_price': lp or info.get('order_price', 0),
#                             'weight': '', '_target_amount': ta_retry,
#                             '_is_retry': True, 'amount_diff': info.get('order_qty', 0),
#                         }
#                         with gate_lock:
#                             if s_name not in strategy_pending_buys:
#                                 strategy_pending_buys[s_name] = []
#                             strategy_pending_buys[s_name].append(retry_buy)
#                         print(f"  🔄 废单重排: {info['stock_code']} 目标金额={ta_retry:.2f} 已加入待买队列")
#                         debug_wework("RETRY", s_name, info['stock_code'],
#                                      f"废单自动重买 | 目标金额={ta_retry:.2f} | 已加入待买队列")
#                 db.update_pending_status(seq, 'cancelled')
#             else:
#                 db.update_pending_status(seq, 'cancelled')

#             if direction == 'sell':
#                 # v6.5: 卖单终结时，检查是否还有未成交部分需要处理
#                 oq = info.get('order_qty', 0)
#                 fq = info.get('filled_qty', 0)
#                 remaining = oq - fq
#                 if remaining > 100:
#                     # 部撤/废单但还有剩余股份，触发重试
#                     # v6.5.1 F1+F2修复: 使用辅助函数入队（防OOM+retry_count递增已存在）
#                     rc = info.get('retry_count', 0) + 1
#                     print(f"  🔄 卖单终结但有剩余: 订单号={seq} 已成交{fq}/{oq} 剩余{remaining}股 将自动重试 retry_count={rc}")
#                     _partial_sell_retry_put({
#                         "strategy": s_name,
#                         "sec_qmt": info['stock_code'],
#                         "remaining_qty": remaining,
#                         "price_signal": info.get('order_price', 0),
#                         "retry_count": rc,
#                         "original_seq": seq,
#                         "timestamp": time.time(),
#                     })
#                 _decr_pending_sells(s_name)
#                 _wake_signal_gate(s_name)
#                 debug_wework("CANCEL", s_name, info['stock_code'],
#                              f"卖单订单终结 seq={seq} | 状态码={status} | 已成交{fq}/{oq} | 唤醒信号门")

#     def on_order_error(self, oe):
#         oid = str(getattr(oe, 'order_id', '') or '')
#         print(f"  ❌ 订单错误: 委托编号={oid} {oe.error_msg}")
#         info = db.get_pending_by_order_id(oid) if oid else None
#         if not info:
#             return
#         seq = info.get("seq")
#         s_name = info.get("strategy_name")
#         direction = info.get("direction")
#         debug_wework("ERROR", s_name, info.get('stock_code', '?'),
#                      f"QMT报错 oid={oid} | {oe.error_msg} | seq={seq}")
#         frozen = info.get("frozen_cash", 0)
#         with seq_lock:
#             _cleanup_seq_map(seq)
#         if not db.claim_for_cancel(seq):
#             return
#         if direction == "buy" and frozen > 0:
#             oq = info.get("order_qty", 0)
#             fq = info.get("filled_qty", 0)
#             release = frozen * (oq - fq) / oq if oq > 0 else frozen
#             if release > 0:
#                 db.update_available_cash(s_name, release)
#                 with cache_lock:
#                     if s_name in strategy_cache:
#                         strategy_cache[s_name]["available_cash"] += release
#         db.delete_pending(seq)
#         if direction == "sell":
#             _decr_pending_sells(s_name)
#             # v6.5 Fix: 订单错误时也要唤醒信号门（Bug 4修复）
#             _wake_signal_gate(s_name)
#             debug_wework("ERROR", s_name, info.get('stock_code', '?'),
#                          f"卖单错误已释放并唤醒信号门 | seq={seq}")

#     def on_cancel_error(self, ce):
#         print(f"  ❌ 撤单错误: 委托编号={getattr(ce, 'order_id', '')} {ce.error_msg}")


# # ═══════════════════════════════════════════════════════════
# #  工具函数 (与6.4.1一致)
# # ═══════════════════════════════════════════════════════════
# def convert_stock_code(jq_code):
#     if not jq_code:
#         return jq_code
#     parts = jq_code.split('.')
#     if len(parts) != 2:
#         return jq_code
#     code, market = parts[0], parts[1].upper()
#     m = {'XSHG': 'SH', 'XSHE': 'SZ', 'BJSE': 'BJ', 'BSE': 'BJ', 'BJ': 'BJ'}
#     return f"{code}.{m[market]}" if market in m else jq_code


# def convert_qmt_to_jq(qmt_code):
#     if not qmt_code or '.' not in qmt_code:
#         return qmt_code
#     parts = qmt_code.split('.')
#     if len(parts) != 2:
#         return qmt_code
#     code, market = parts[0], parts[1].upper()
#     m = {'SH': 'XSHG', 'SZ': 'XSHE', 'BJ': 'BJSE'}
#     return f"{code}.{m[market]}" if market in m else qmt_code


# def get_trading_phase(now=None):
#     if now is None:
#         now = datetime.now()
#     t = now.time()
#     if now.weekday() >= 5:
#         return CLOSED
#     if dt_time(9, 15) <= t < dt_time(9, 25): return PRE_CALL
#     if dt_time(9, 25) <= t < dt_time(9, 30): return CONTINUOUS
#     if dt_time(9, 30) <= t < dt_time(11, 30): return CONTINUOUS
#     if dt_time(11, 30) <= t < dt_time(13, 0): return NOON_BREAK
#     if dt_time(13, 0) <= t < dt_time(14, 57): return CONTINUOUS
#     if dt_time(14, 57) <= t < dt_time(15, 0): return POST_CALL
#     return CLOSED


# def is_work_time():
#     now = datetime.now()
#     if now.weekday() >= 5:
#         return False
#     t = now.time()
#     return dt_time.fromisoformat(WORK_START) <= t <= dt_time.fromisoformat(WORK_END)


# def get_commission(stock_code, volume, price):
#     """
#     v6.5.1 修正: 按实际截图确认费用结构。
#     所有交易(ETF和股票): 佣金双向收，最低5元，超过按费率
#     股票卖出: 加印花税0.05% (ETF不收)
#     无过户费/经手费/征管费
#     """
#     qmt_code = convert_stock_code(stock_code)
#     code_only = qmt_code.split('.')[0] if '.' in qmt_code else qmt_code
#     etf_prefixes = ('510', '511', '512', '513', '515', '516', '517', '518', '560', '561', '562', '563',
#                     '564', '565', '566', '567', '568', '569', '588', '589', '159', '508')
#     rate = ETF_COMMISSION_RATE if code_only.startswith(etf_prefixes) else STOCK_COMMISSION_RATE
#     return max(volume * price * rate, MIN_COMMISSION)  # 所有交易都有最低5元


# def _is_etf(stock_code):
#     """判断是否为ETF/基金"""
#     qmt_code = convert_stock_code(stock_code)
#     code_only = qmt_code.split('.')[0] if '.' in qmt_code else qmt_code
#     etf_prefixes = ('510', '511', '512', '513', '515', '516', '517', '518', '560', '561', '562', '563',
#                     '564', '565', '566', '567', '568', '569', '588', '589', '159', '508')
#     return code_only.startswith(etf_prefixes)


# def _get_stamp_duty(stock_code, volume, price):
#     """卖出印花税: 0.05% (万分之5)。ETF和买入不收。"""
#     if _is_etf(stock_code):
#         return 0.0
#     return volume * price * 0.0005  # 0.05% = 0.0005


# def redis_conn_factory():
#     if CONNECT_MODE == "direct":
#         return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD,
#                           decode_responses=True, socket_connect_timeout=10, socket_timeout=30,
#                           socket_keepalive=True, health_check_interval=30)
#     return redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=10, socket_timeout=30,
#                           socket_keepalive=True, ssl_cert_reqs=None, health_check_interval=30)


# def format_latency(ms):
#     if ms is None:
#         return "N/A"
#     if ms < 1:
#         return f"{ms * 1000:.1f} us"
#     if ms < 1000:
#         return f"{ms:.1f} ms"
#     return f"{ms / 1000:.2f} s"


# # v6.5.1 F3修复: 查询QMT实际持仓和可用持仓（走_safe_qmt_query保护，线程安全）
# def _get_qmt_position_volume(sec_qmt):
#     """
#     查询QMT实际持仓中的总持仓和可用持仓。
#     返回: (total_volume, can_use_volume) 或 (0, 0) 表示无持仓/查询失败

#     v6.5.1修复: 所有xt_trader查询接口统一走_safe_qmt_query保护，
#     避免多线程直接调用QMT API导致的线程安全问题。
#     被3个线程调用: 策略Worker线程、cancel_watcher线程、partial_sell_retry线程
#     """
#     if not _qmt_connected or not xt_trader:
#         return 0, 0
#     # F3修复: 通过_safe_qmt_query调用，统一异常处理和线程保护
#     pos = _safe_qmt_query(xt_trader.query_stock_position, _account, sec_qmt)
#     if pos:
#         try:
#             total = getattr(pos, 'volume', 0)
#             can_use = getattr(pos, 'can_use_volume', 0)
#             return int(total), int(can_use)
#         except Exception as e:
#             print(f"  ⚠️ QMT持仓数据解析异常 {sec_qmt}: {e}")
#     return 0, 0


# # ═══════════════════════════════════════════════════════════
# #  价格计算 (v6.5/v6.5.1: 所有价格返回前经笼子校验 — Bug 5修复)
# # ═══════════════════════════════════════════════════════════
# def apply_price_cage(action, qmt_code, target_price, tick_data):
#     try:
#         ask = tick_data.get('askPrice', [])
#         bid = tick_data.get('bidPrice', [])
#         lp = tick_data.get('lastPrice', 0)
#         lc = tick_data.get('lastClose', 0)
#         base = (ask[0] if ask and ask[0] > 0 else (bid[0] if bid and bid[0] > 0 else (lp or lc))) if action == 'buy' \
#             else (bid[0] if bid and bid[0] > 0 else (ask[0] if ask and ask[0] > 0 else (lp or lc)))
#         info = xtdata.get_instrument_detail(qmt_code)
#         pt = info.get("PriceTick", 0.01) if info else 0.01
#         final = max(min(target_price, base * 1.02), base * 0.98) if action == "buy" \
#             else min(max(target_price, base * 0.98), base * 1.02)
#         final = round(final / pt) * pt
#         if info:
#             us, ds = info.get("UpStopPrice", 0), info.get("DownStopPrice", 0)
#             if us > 0:
#                 final = min(final, us)
#             if ds > 0:
#                 final = max(final, ds)
#         if final != target_price:
#             print(f"  🔒 价格笼子: {target_price:.3f} → {final:.3f}")
#         return final
#     except Exception:
#         return target_price


# # v6.5新增: 对价格进行笼子校验（所有档位价格返回前强制校验）
# def _enforce_price_cage(action, qmt_code, price, tick_data):
#     """
#     强制对价格进行笼子校验，确保不超出±2%范围。
#     用于所有重试等级的价格返回前。
#     """
#     if not tick_data or price <= 0:
#         return price
#     try:
#         caged = apply_price_cage(action, qmt_code, price, tick_data)
#         if caged != price:
#             print(f"  🔒 价格笼子校正: {action} {qmt_code} {price:.3f} → {caged:.3f}")
#         return caged
#     except Exception as e:
#         print(f"  ⚠️ 价格笼子校验异常 {qmt_code}: {e}")
#         return price


# def get_real_price(sec_qmt, action, signal_price, retry_count=0):
#     phase = get_trading_phase()
#     if phase == CLOSED:
#         return signal_price
#     tick_data = None
#     try:
#         tks = _safe_get_tick([sec_qmt])
#         if sec_qmt in tks:
#             tick_data = tks[sec_qmt]
#     except Exception:
#         pass

#     tiers = BUY_RETRY_TIERS if action == 'buy' else SELL_RETRY_TIERS
#     rc = min(retry_count, len(tiers) - 1)
#     tier = tiers[rc]
#     target = signal_price

#     if rc == 0 and PRICE_MODE in ('opponent', 'best'):
#         level = OPPONENT_LEVEL
#         if tick_data:
#             try:
#                 if action == 'buy':
#                     a = tick_data.get('askPrice', [])
#                     if a and len(a) >= level and a[level - 1] > 0:
#                         target = a[level - 1]
#                 else:
#                     b = tick_data.get('bidPrice', [])
#                     if b and len(b) >= level and b[level - 1] > 0:
#                         target = b[level - 1]
#                 print(f"  💰 初始定价({tier['desc']}): {target:.3f}")
#             except Exception:
#                 pass
#     elif tier.get('cage'):
#         if tick_data:
#             target = apply_price_cage(action, sec_qmt, signal_price, tick_data)
#             print(f"  🔄 重试定价({tier['desc']}): {target:.3f}")
#     else:
#         level = tier['level']
#         if tick_data:
#             try:
#                 if action == 'buy':
#                     a = tick_data.get('askPrice', [])
#                     if a and len(a) >= level and a[level - 1] > 0:
#                         target = a[level - 1]
#                 else:
#                     b = tick_data.get('bidPrice', [])
#                     if b and len(b) >= level and b[level - 1] > 0:
#                         target = b[level - 1]
#                 print(f"  🔄 重试定价({tier['desc']}): {target:.3f}")
#             except Exception:
#                 pass

#     if PRICE_MODE == "best" and phase == CONTINUOUS:
#         target = apply_price_cage(action, sec_qmt, target, tick_data)

#     # v6.5 Fix (Bug 5): 所有价格返回前强制经过笼子校验
#     # 对手档位价在市场波动大时可能超出笼子范围，此处兜底
#     target = _enforce_price_cage(action, sec_qmt, target, tick_data)
#     return target


# # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# #  信号门控 (v6.5/v6.5.1: 修复唤醒条件 — Bug 4修复)
# # ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
# def _get_signal_gate(strategy):
#     with gate_lock:
#         if strategy not in strategy_gates:
#             strategy_gates[strategy] = threading.Event()
#             strategy_gates[strategy].set()
#         return strategy_gates[strategy]


# def _has_pending_sells(strategy):
#     """O(1)内存计数器，避免全表扫描"""
#     with _pending_sell_lock:
#         return _pending_sell_count.get(strategy, 0) > 0


# def _incr_pending_sells(strategy):
#     with _pending_sell_lock:
#         cnt = _pending_sell_count.get(strategy, 0)
#         _pending_sell_count[strategy] = cnt + 1
#         print(f"  📊 卖单计数 [{strategy}]: {cnt}→{cnt + 1}")


# def _decr_pending_sells(strategy):
#     with _pending_sell_lock:
#         cnt = _pending_sell_count.get(strategy, 0)
#         if cnt > 0:
#             _pending_sell_count[strategy] = cnt - 1
#             print(f"  📊 卖单计数 [{strategy}]: {cnt}→{cnt - 1}")
#         else:
#             print(f"  ⚠️ 卖单计数 [{strategy}]: 已是0，无法递减！")


# def _wake_signal_gate(strategy):
#     """
#     v6.5: 修复信号门唤醒逻辑。
#     唤醒条件：1) 没有待成交卖单  2) 有待执行的买单
#     Bug 4修复：即使pending_buys为空也set()信号门，避免死锁。
#               空的pending_buys不会导致错误执行（_try_execute_pending_buys会检查）。
#     """
#     if _has_pending_sells(strategy):
#         print(f"  ⏳ 信号门 [{strategy}]: 仍有卖出挂单，暂不唤醒")
#         return
#     with gate_lock:
#         gate = _get_signal_gate(strategy)
#         gate.set()
#         print(f"  🚦 信号门唤醒: {strategy}（全部卖出完毕）")


# # ═══════════════════════════════════════════════════════════
# #  v6.5.1 F1F2修复: 部分成交卖出重试线程 — Bug 1修复核心(队列有界+retry_count递增)
# #  持续监控队列，对部分成交的卖单自动提交未成交部分
# # ═══════════════════════════════════════════════════════════
# # v6.5.1 F2修复: 重试计数器正确递增 + MAX_RETRY清仓处理
# def _partial_sell_retry_worker():
#     """
#     后台线程：处理部分成交卖出的自动重试。
#     当卖单部分成交后，未成交部分被放入队列，此线程负责重新提交。
#     最多重试MAX_RETRY次，每次升级对手档位。

#     v6.5.1修复:
#     1. retry_count正确递增（每次取出后+1）
#     2. 超过MAX_RETRY时以笼子极限价清仓（而非放弃）
#     3. 新retry_count通过remark传递，供on_stock_trade回调解析
#     4. 更新数据库中的retry_count
#     """
#     print("🟢 部分成交卖出重试线程已启动")
#     while not shutdown_flag.is_set():
#         try:
#             task = _partial_sell_retry_queue.get(timeout=1.0)
#         except Empty:
#             continue
#         if task is None:
#             break

#         strategy = task.get("strategy", "")
#         sec_qmt = task.get("sec_qmt", "")
#         remaining_qty = task.get("remaining_qty", 0)
#         price_signal = task.get("price_signal", 0)
#         retry_count = task.get("retry_count", 0)
#         original_seq = task.get("original_seq", 0)

#         if remaining_qty <= 0 or not strategy or not sec_qmt:
#             continue

#         # v6.5.1 F2修复: 取出任务后递增retry_count
#         # 队列入队时retry_count已+1（on_stock_trade/on_stock_order中）
#         # 但worker消费时需要再次+1，因为队列中的是"上一次的retry_count"
#         task_retry_count = retry_count + 1

#         if task_retry_count >= MAX_RETRY:
#             # v6.5.1 F2修复: 超过MAX_RETRY时以笼子极限价清仓，而非放弃
#             print(f"  ⚠️ 部分成交重试将达上限 [{strategy}] {sec_qmt}: 剩余{remaining_qty}股将以极限价清仓")
#             debug_wework("RETRY", strategy, sec_qmt,
#                          f"重试将达上限({task_retry_count}/{MAX_RETRY}) | 剩余{remaining_qty}股将以笼子极限价清仓")

#         # 延迟重试，避免过于频繁
#         sleep_sec = min(2 ** max(retry_count, 0), 30)  # 指数退避上限30秒
#         time.sleep(sleep_sec)

#         if shutdown_flag.is_set():
#             break

#         try:
#             # 重新校验持仓
#             positions = db.get_all_positions(strategy)
#             local_hold = positions.get(sec_qmt, {}).get('volume', 0)
#             # v6.5.1 F3修复: 通过_safe_qmt_query调用QMT持仓查询
#             qmt_total, qmt_can_use = _get_qmt_position_volume(sec_qmt)
#             actual_hold = min(local_hold, qmt_total, qmt_can_use)
#             sell_qty = min(remaining_qty, actual_hold)
#             sell_qty = int(sell_qty / 100) * 100  # 取整到100的倍数

#             if sell_qty <= 0:
#                 print(f"  ❌ 部分成交重试跳过 [{strategy}] {sec_qmt}: 实际可卖{sell_qty}股")
#                 _decr_pending_sells(strategy)
#                 _wake_signal_gate(strategy)
#                 continue

#             # v6.5.1 F2修复: 计算价格，超过MAX_RETRY时使用笼子极限价
#             if task_retry_count >= MAX_RETRY:
#                 # 清仓处理: 以笼子-2%边界价（最低允许价）挂出，确保成交
#                 tick_data = _safe_get_tick([sec_qmt]).get(sec_qmt, {})
#                 last_price = tick_data.get('lastPrice', 0) or price_signal
#                 # 跌停价或-2%边界
#                 new_price = last_price * 0.98 if last_price > 0 else price_signal * 0.98
#                 new_price = max(new_price, 0.01)  # 最低0.01元
#                 new_price = _enforce_price_cage('sell', sec_qmt, new_price, tick_data)
#                 print(f"  🔥 清仓极限价 [{strategy}] {sec_qmt}: {new_price:.3f} (基于{last_price:.3f}的-2%笼子)")
#             else:
#                 new_price = get_real_price(sec_qmt, 'sell', price_signal, retry_count=task_retry_count)

#             if new_price <= 0:
#                 print(f"  ❌ 部分成交重试价格异常 [{strategy}] {sec_qmt}")
#                 _decr_pending_sells(strategy)
#                 _wake_signal_gate(strategy)
#                 continue

#             # v6.5.1 F2修复: remark中嵌入递增后的retry_count，供on_stock_trade回调解析
#             remark = (f"{strategy}_{sec_qmt}_sell_retry{task_retry_count}_"
#                       f"{sell_qty}股@{new_price:.3f}_{int(time.time() * 1000000)}")
#             print(f"  🔄 部分成交重试提交 [{strategy}] {sec_qmt}: {sell_qty}股@{new_price:.3f} "
#                   f"(retry_count={task_retry_count} 第{task_retry_count + 1}次)")
#             debug_wework("RETRY", strategy, sec_qmt,
#                          f"卖出部分成交重试 | {sell_qty}股 @ {new_price:.3f} | "
#                          f"retry_count={task_retry_count} 第{task_retry_count + 1}次")

#             # v6.5.1 F2修复: 更新数据库中原订单的retry_count
#             if original_seq:
#                 db.update_pending_retry(original_seq, task_retry_count)

#             # 拆单提交
#             remaining = sell_qty
#             while remaining > 0:
#                 vol = min(remaining, MAX_ORDER_VOL)
#                 submit_order_async(strategy, sec_qmt, 'sell', vol, new_price, remark, frozen_cash=0.0)
#                 remaining -= vol

#         except Exception as e:
#             print(f"  ❌ 部分成交重试异常 [{strategy}] {sec_qmt}: {e}")
#             debug_wework("ERROR", strategy, sec_qmt, f"部分成交重试异常: {e}")
#             _decr_pending_sells(strategy)
#             _wake_signal_gate(strategy)

#     print("🛑 部分成交卖出重试线程已停止")


# def _start_partial_sell_retry_thread():
#     """启动部分成交卖出重试后台线程"""
#     global _partial_sell_retry_thread
#     with _partial_sell_retry_lock:
#         if _partial_sell_retry_thread is None or not _partial_sell_retry_thread.is_alive():
#             _partial_sell_retry_thread = threading.Thread(
#                 target=_partial_sell_retry_worker, daemon=True, name="partial-sell-retry"
#             )
#             _partial_sell_retry_thread.start()


# # ═══════════════════════════════════════════════════════════
# #  6.5核心: QMT下单网关 — 仅下单需串行化(DB写入原子) [v6.5.1 F3: 查询也走_safe_qmt_query]
# #  查询/撤单直接调用xt_trader，不经过网关
# # ═══════════════════════════════════════════════════════════

# def _gateway_submit_order(fn, *args, **kwargs):
#     """提交下单任务到网关线程，返回Future"""
#     return QMT_GATEWAY.submit(fn, *args, **kwargs)


# def _safe_qmt_query(fn, *args):
#     """直接调用QMT查询/撤单接口，带异常保护"""
#     try:
#         return fn(*args)
#     except Exception as e:
#         print(f"  ⚠️ QMT调用异常 [{fn.__name__}]: {e}")
#         return None


# def _gw_shutdown_timeout(timeout=30):
#     global QMT_GATEWAY
#     gw = QMT_GATEWAY

#     def _do():
#         gw.shutdown(wait=True, cancel_futures=False)

#     t = threading.Thread(target=_do, daemon=True)
#     t.start()
#     t.join(timeout=timeout)
#     if t.is_alive():
#         print(f"  ⚠️ QMT网关关闭超时({timeout}s)，强制退出")


# def _do_submit_order(strategy, sec_qmt, direction, qty, price, remark, frozen_cash, target_amount=0.0,
#                      retry_seq=None, old_frozen=0.0):
#     if not _qmt_connected or not xt_trader:
#         return None, "qmt_disconnected"
#     if _trading_paused.is_set():
#         return None, "trading_paused"

#     order_type = xtconstant.STOCK_BUY if direction == 'buy' else xtconstant.STOCK_SELL

#     if retry_seq is not None:
#         old_fz = old_frozen
#         net_delta = frozen_cash - old_fz
#         if not db.retry_pending(retry_seq, price, frozen_cash, time.time(), remark=remark):
#             return None, "retry_already_filled"
#         seq = xt_trader.order_stock_async(_account, sec_qmt, order_type, qty, xtconstant.FIX_PRICE, price, strategy,
#                                           remark)
#         if seq > 0:
#             if net_delta != 0:
#                 db.update_available_cash(strategy, -net_delta)
#                 with cache_lock:
#                     if strategy in strategy_cache:
#                         strategy_cache[strategy]['available_cash'] -= net_delta
#             with seq_lock:
#                 seq_map[seq] = {"strategy": strategy, "stock": sec_qmt, "direction": direction, "retry_of": retry_seq}
#             print(f"    📝 订单号={seq} {'买入' if direction == 'buy' else '卖出'} {qty}股@{price:.3f} 冻结={frozen_cash:.2f}")
#             return seq, None
#         else:
#             return None, f"order_stock_async returned {seq}"
#     else:
#         seq = xt_trader.order_stock_async(_account, sec_qmt, order_type, qty, xtconstant.FIX_PRICE, price, strategy,
#                                           remark)
#         if seq > 0:
#             db.update_available_cash(strategy, -frozen_cash)
#             db.add_pending(seq, strategy, sec_qmt, direction, qty, price, frozen_cash, time.time(), ta=target_amount)
#             with seq_lock:
#                 seq_map[seq] = {"strategy": strategy, "stock": sec_qmt, "direction": direction}
#             print(f"    📝 订单号={seq} {'买入' if direction == 'buy' else '卖出'} {qty}股@{price:.3f} 冻结={frozen_cash:.2f}")
#             return seq, None
#         else:
#             return None, f"order_stock_async returned {seq}"


# def _on_order_done(strategy, stock, frozen_cash, future, is_retry=False, direction=None):
#     try:
#         seq, err = future.result()
#     except Exception as e:
#         seq, err = None, str(e)
#     if err:
#         if not is_retry and frozen_cash > 0:
#             with cache_lock:
#                 if strategy in strategy_cache:
#                     strategy_cache[strategy]['available_cash'] += frozen_cash
#             print(f"  ❌ 下单失败 [{strategy}] {stock}: {err}  已回滚{frozen_cash:.2f}")
#             debug_wework("ERROR", strategy, stock,
#                          f"网关下单失败: {err} | 已回滚={frozen_cash:.2f}")
#         else:
#             print(f"  ❌ 下单失败 [{strategy}] {stock}: {err}  (重试/无冻结，不回滚)")
#             debug_wework("ERROR", strategy, stock,
#                          f"网关下单失败: {err} | 重试/无冻结，不回滚")
#         # v6.5 Fix (Bug 4): 卖出失败时也要递减计数器并唤醒信号门
#         if direction == 'sell':
#             _decr_pending_sells(strategy)
#             _wake_signal_gate(strategy)
#             print(f"  🚦 卖出失败已唤醒信号门 [{strategy}]")
#     # 成功: 资金已在网关线程 _do_submit_order 中扣除，无需操作


# def submit_order_async(strategy, sec_qmt, direction, qty, price, remark, frozen_cash=0.0, target_amount=0.0,
#                       retry_seq=None, old_frozen=0.0):
#     """
#     非阻塞提交到QMT网关。Worker预扣资金后再调用。
#     返回的Future绑定done_callback用于失败回滚。
#     retry_seq: 若不为None → 重试场景，_do_submit_order会更新原记录而非插入新行。
#     """
#     if direction == 'sell':
#         _incr_pending_sells(strategy)
#     future = _gateway_submit_order(
#         _do_submit_order, strategy, sec_qmt, direction, qty, price, remark, frozen_cash, target_amount,
#         retry_seq, old_frozen
#     )
#     future.add_done_callback(
#         lambda fut, s=strategy, st=sec_qmt, fz=frozen_cash, ir=(retry_seq is not None), d=direction:
#         _on_order_done(s, st, fz, fut, ir, d)
#     )
#     return future


# # ═══════════════════════════════════════════════════════════
# #  交易核心 (v6.5/v6.5.1: 全面重构卖出逻辑 — Bug 1/2/3修复 + F1F2F3致命问题修复)
# # ═══════════════════════════════════════════════════════════
# def _calculate_buy_target(strategy, data):
#     sec_qmt = convert_stock_code(data['security'])
#     price_signal = data['current_price']
#     weight_str = data.get('weight', '')
#     if not weight_str or weight_str.strip() in ('0%', '0', '0.0', ''):
#         return None, "weight zero or empty, skip buy"
#     try:
#         ws = weight_str.strip()
#         weight = float(ws[:-1]) / 100.0 if ws.endswith("%") else float(ws)
#     except ValueError:
#         return None, f"bad weight: {weight_str}"

#     if weight > 1.0:
#         print(f"  ⚠️ weight原值:{weight}   截断为:100%")
#         weight = 1.0
#     elif weight <= 0.005:
#         print(f"  ⚠️ weight原值:{weight}   截断为:0%")
#         weight = 0.0

#     with cache_lock:
#         available = strategy_cache.get(strategy, {}).get('available_cash', 0)
#     positions = db.get_all_positions(strategy)
#     pos_value = 0.0
#     if positions:
#         try:
#             ticks = _safe_get_tick(list(positions.keys()))
#             for sc, info in positions.items():
#                 p = ticks.get(sc, {}).get('lastPrice', 0) if ticks else 0
#                 pos_value += info['volume'] * p
#         except Exception:
#             pass
#     total_equity = available + pos_value
#     target_value = total_equity * weight
#     current_hold = positions.get(sec_qmt, {}).get('volume', 0)
#     current_value = current_hold * price_signal
#     diff = target_value - current_value
#     if diff <= 0:
#         return None, f"diff<=0 (target={target_value:.2f} cur={current_value:.2f})"
#     return diff, None


# def _execute_sell(strategy, data):
#     """
#     v6.5 全面重构的卖出执行函数。
#     修复Bug 1(部分成交丢失), Bug 2(清仓取整为0), Bug 3(持仓校验不足)。
#     """
#     sec_qmt = convert_stock_code(data['security'])
#     price_signal = data['current_price']

#     weight_str = str(data.get('weight', '')).strip()
#     signal_amount = data.get('amount', 0) or data.get('volume', 0) or 0
#     target_qty = None
#     weight = None
#     is_liquidation = False

#     if not weight_str or weight_str in ('0%', '0', '0.0'):
#         weight = 0.0
#         is_liquidation = True
#     else:
#         try:
#             weight = float(weight_str[:-1]) / 100.0 if weight_str.endswith("%") else float(weight_str)
#         except ValueError:
#             if signal_amount > 0:
#                 pass  # 使用信号amount模式
#             else:
#                 print(f"  ❌ 卖出跳过: {sec_qmt} 仓位解析失败: {weight_str}")
#                 return

#     # ═══════════════════════════════════════════════════
#     # v6.5 Fix (Bug 3): 双重持仓校验
#     # 1. 本地数据库持仓
#     positions = db.get_all_positions(strategy)
#     local_hold = positions.get(sec_qmt, {}).get('volume', 0)
#     if local_hold <= 0:
#         print(f"  ❌ 卖出跳过: {sec_qmt} 无本地持仓")
#         return

#     # 2. QMT实际总持仓和可用持仓（T+1校验）
#     qmt_total, qmt_can_use = _get_qmt_position_volume(sec_qmt)

#     # 实际可卖 = 本地持仓, QMT总持仓, QMT可用持仓 三者取最小
#     # qmt_can_use=0意味着T+1限制（当日买入不可卖出）
#     actual_hold = min(local_hold, qmt_total) if qmt_total > 0 else local_hold

#     if qmt_can_use <= 0 and qmt_total > 0:
#         print(f"  ⚠️ 卖出警告: {sec_qmt} QMT可用持仓为0，可能受T+1限制 (总持仓{qmt_total}股)")
#         debug_wework("SKIP", strategy, sec_qmt,
#                      f"卖出跳过: T+1限制 | 总持仓{qmt_total}股 可用0股")
#         # 仍尝试卖出（可能可用持仓查询失败或为0），但实际可卖量设为0
#         actual_hold = 0
#     elif qmt_can_use > 0:
#         actual_hold = min(actual_hold, qmt_can_use)

#     if actual_hold <= 0:
#         print(f"  ❌ 卖出跳过: {sec_qmt} 实际可卖持仓为0 (本地{local_hold}/QMT总{qmt_total}/可用{qmt_can_use})")
#         return

#     # 如果本地持仓与QMT持仓不一致，发出警告
#     if abs(local_hold - qmt_total) > 100 and qmt_total > 0:
#         print(f"  ⚠️ 持仓差异警告: {sec_qmt} 本地{local_hold}股 vs QMT{qmt_total}股，以较小值为准")
#     # ═══════════════════════════════════════════════════

#     # ═══════════════════════════════════════════════════
#     # v6.5.1+ 兼容修复: 支持直接使用信号中的 amount 字段作为卖出数量
#     # ═══════════════════════════════════════════════════
#     if is_liquidation:
#         # 清仓模式：卖出全部实际可卖持仓
#         sell_qty = int(actual_hold / 100) * 100
#         print(f"  🏷️ 清仓模式: {sec_qmt} 目标仓位={weight_str} 清仓卖出{sell_qty}股")
#     elif signal_amount > 0 and weight is None:
#         # 信号数量模式: 直接使用信号中的 amount 作为卖出数量
#         sell_qty = min(signal_amount, actual_hold)
#         sell_qty = int(sell_qty / 100) * 100
#         print(f"  🏷️ 信号数量模式: {sec_qmt} 信号{signal_amount}股 实际可卖{sell_qty}股")
#     elif weight is not None:
#         # 原有比例模式
#         is_liquidation = (weight >= 0.995)
#         if weight > 1.0:
#             print(f"  ⚠️ weight原值:{weight}   截断为:100%")
#             weight = 1.0
#         elif weight <= 0.005:
#             weight = 0.0
#             is_liquidation = True

#         if is_liquidation:
#             sell_qty = int(actual_hold / 100) * 100
#             print(f"  🏷️ 清仓模式: {sec_qmt} 目标仓位={weight_str} 清仓卖出{sell_qty}股")
#         else:
#             raw_qty = (1 - weight) * actual_hold
#             sell_qty = int(raw_qty / 100) * 100
#             if sell_qty <= 0 and raw_qty > 0:
#                 if actual_hold <= 200:
#                     sell_qty = int(actual_hold / 100) * 100
#                     print(f"  🏷️ 小持仓全部卖出: {sec_qmt} 原始计算{raw_qty:.0f}股不足1手，改为清仓{sell_qty}股")
#                 else:
#                     sell_qty = 100
#                     print(f"  🏷️ 最小卖出: {sec_qmt} 原始计算不足1手，改为卖100股")
#     else:
#         print(f"  ❌ 卖出跳过: {sec_qmt} 无法计算卖出数量")
#         return
#     # ═══════════════════════════════════════════════════

#     if sell_qty <= 0:
#         print(f"  ❌ 卖出跳过: {sec_qmt} 目标仓位={weight_str} 无需卖出 (可卖{actual_hold}股)")
#         return

#     final_price = get_real_price(sec_qmt, 'sell', price_signal)
#     if final_price <= 0:
#         print(f"  ❌ 卖出跳过: {sec_qmt} 价格异常")
#         _wake_signal_gate(strategy)  # v6.5: 即使跳过也要唤醒，避免阻塞
#         return

#     remark = f"{strategy}_{sec_qmt}_sell_{sell_qty}股@{final_price:.3f}_{int(time.time() * 1000000)}"
#     print(f"  🔴 卖出提交: {sec_qmt} {sell_qty}股@{final_price:.3f} (本地{local_hold}/QMT总{qmt_total}/可用{qmt_can_use})")
#     debug_wework("SELL", strategy, sec_qmt,
#                  f"提交卖出 {sell_qty}股 @ {final_price:.3f} | 信号价={price_signal:.3f} | "
#                  f"本地{local_hold}股 QMT总{qmt_total}股 可用{qmt_can_use}股")

#     # 拆单提交
#     remaining = sell_qty
#     while remaining > 0:
#         vol = min(remaining, MAX_ORDER_VOL)
#         submit_order_async(strategy, sec_qmt, 'sell', vol, final_price, remark, frozen_cash=0.0)
#         remaining -= vol


# def _execute_buy(strategy, data, max_amount):
#     """买入: Worker预扣资金后提交网关，done_callback回滚失败"""
#     sec_qmt = convert_stock_code(data['security'])
#     price_signal = data['current_price']
#     final_price = get_real_price(sec_qmt, 'buy', price_signal)
#     if final_price <= 0:
#         print(f"  ❌ 买入跳过: {sec_qmt} 价格异常")
#         return False
#     qty = int(max_amount // final_price // 100) * 100
#     if qty <= 0:
#         print(f"  ❌ 买入跳过: {sec_qmt} 不足1手")
#         return False
#     while qty >= 100:
#         comm = get_commission(data['security'], qty, final_price)
#         if qty * final_price + comm <= max_amount:
#             break
#         qty -= 100
#     if qty <= 0:
#         print(f"  ❌ 买入跳过: {sec_qmt} 扣佣后不足")
#         return False

#     remark = f"{strategy}_{sec_qmt}_buy_{qty}股@{final_price:.3f}_{int(time.time() * 1000000)}"
#     ta = data.get('_target_amount', 0.0)

#     # 先计算拆单方案，再预扣真实总冻结（避免拆单后佣金最低5元导致的冻结不足）
#     sub_orders = []
#     remaining = qty
#     while remaining > 0:
#         vol = min(remaining, MAX_ORDER_VOL)
#         sub_frozen = vol * final_price + get_commission(data['security'], vol, final_price)
#         sub_orders.append((vol, sub_frozen))
#         remaining -= vol
#     total_frozen = sum(fz for _, fz in sub_orders)

#     # Worker预扣资金: 网关成功则保留扣减，失败则done_callback回滚
#     with cache_lock:
#         if strategy in strategy_cache:
#             av = strategy_cache[strategy]['available_cash']
#             if total_frozen > av:
#                 print(f"  💸 资金不足: {sec_qmt} 需={total_frozen:.2f} 有={av:.2f}")
#                 debug_wework("SKIP", strategy, sec_qmt, f"买入跳过: 资金不足 | 需={total_frozen:.2f} 有={av:.2f}")
#                 return False
#             strategy_cache[strategy]['available_cash'] -= total_frozen
#     print(f"  🟢 买入提交: {sec_qmt} {qty}股@{final_price:.3f} 预扣={total_frozen:.2f}")
#     debug_wework("BUY", strategy, sec_qmt,
#                  f"提交买入 {qty}股 @ {final_price:.3f} | 预扣={total_frozen:.2f} | 信号价={price_signal:.3f}")

#     for vol, sub_frozen in sub_orders:
#         submit_order_async(strategy, sec_qmt, 'buy', vol, final_price, remark, frozen_cash=sub_frozen, target_amount=ta)
#     return True


# def _try_execute_pending_buys(strategy):
#     """尝试执行缓存的买单"""
#     with gate_lock:
#         buys = list(strategy_pending_buys.get(strategy, []))
#     if not buys:
#         return
#     with cache_lock:
#         available = strategy_cache.get(strategy, {}).get('available_cash', 0)
#     remaining_buys = []
#     for bd in buys:
#         ta = bd.get('_target_amount', 0)
#         if ta <= 0:
#             continue
#         affordable = min(ta, available)
#         if _execute_buy(strategy, bd, affordable):
#             available -= affordable
#             print(f"  ✅ 执行缓存买单: {bd.get('security', '?')} ≈{affordable:.2f}")
#         else:
#             remaining_buys.append(bd)
#     with gate_lock:
#         strategy_pending_buys[strategy] = remaining_buys


# # ═══════════════════════════════════════════════════════════
# #  策略 Worker (纯决策层，不再直接调用QMT API)
# # ═══════════════════════════════════════════════════════════
# class StrategyWorker(threading.Thread):
#     def __init__(self, name):
#         super().__init__(name=f"Worker-{name}", daemon=True)
#         self.strategy_name = name
#         self.q = strategy_queues[name]

#     def run(self):
#         print(f"🟢 WORKER [{self.strategy_name}] 已启动")
#         while not shutdown_flag.is_set():
#             try:
#                 data = self.q.get(timeout=0.5)
#             except Empty:
#                 # 空闲时检查是否有缓存买单可执行
#                 with gate_lock:
#                     has_pending = bool(strategy_pending_buys.get(self.strategy_name))
#                 if has_pending and not _has_pending_sells(self.strategy_name):
#                     _try_execute_pending_buys(self.strategy_name)
#                 continue

#             if data is None:
#                 break
#             with cache_lock:
#                 enabled = strategy_cache.get(self.strategy_name, {}).get('enabled', True)
#             if not enabled:
#                 continue
#             # 批量收集
#             batch = [data]
#             t0 = time.time()
#             while time.time() - t0 < 0.2:
#                 try:
#                     batch.append(self.q.get_nowait())
#                 except Empty:
#                     break

#             if _trading_paused.is_set() or _reconciling.is_set():
#                 # v6.5.1+ 修复: batch 被拦截时重新放入队列，避免信号静默丢失
#                 for item in batch:
#                     try:
#                         self.q.put(item, block=False)
#                     except Full:
#                         print(f"⚠️ 重新入队失败 [{self.strategy_name}]: 队列已满，信号丢失")
#                         debug_wework("ERROR", self.strategy_name, item.get('security', '?'), "batch重新入队失败: 队列已满")
#                 print(f"⏸️ [{self.strategy_name}] 交易暂停/对账中，{len(batch)}笔信号已重新入队")
#                 continue
#             self._process_batch(batch)
#         print(f"🛑 WORKER [{self.strategy_name}] 已停止")

#     def _process_batch(self, batch):
#         sells = [s for s in batch if s.get('action') == 'sell']
#         buys = [s for s in batch if s.get('action') == 'buy']
#         print(f"\n📦 批处理 [{self.strategy_name}]: 卖{len(sells)} 买{len(buys)}")

#         # 1. 预计算买入目标
#         precomputed = []
#         for b in buys:
#             target, err = _calculate_buy_target(self.strategy_name, b)
#             if err:
#                 print(f"  ⏭️ 跳过买入: {b.get('security', '?')} {err}")
#             else:
#                 b['_target_amount'] = target
#                 precomputed.append(b)
#                 print(f"  🎯 目标买入: {b['security']} ≈{target:.2f}")

#         # 2. 提交卖出(非阻塞)
#         for s in sells:
#             _execute_sell(self.strategy_name, s)

#         if not precomputed:
#             return

#         # 3. 信号门: 有未完成的卖出则等待
#         if _has_pending_sells(self.strategy_name):
#             print(f"  🚦 信号门 [{self.strategy_name}]: {len(precomputed)}笔买单等待卖出完成")
#             with gate_lock:
#                 strategy_pending_buys[self.strategy_name] = precomputed
#             gate = _get_signal_gate(self.strategy_name)
#             gate.clear()
#             deadline = time.time() + SIGNAL_GATE_TIMEOUT
#             exit_reason = "timeout"
#             while not shutdown_flag.is_set() and time.time() < deadline:
#                 if not _has_pending_sells(self.strategy_name):
#                     _try_execute_pending_buys(self.strategy_name)
#                     with gate_lock:
#                         rem = strategy_pending_buys.get(self.strategy_name, [])
#                     if not rem:
#                         exit_reason = "done"
#                         break
#                     exit_reason = "no_funds"
#                     break
#                 if gate.wait(timeout=0.5):
#                     _try_execute_pending_buys(self.strategy_name)
#                     with gate_lock:
#                         rem = strategy_pending_buys.get(self.strategy_name, [])
#                     if not rem:
#                         exit_reason = "done"
#                         break
#                     if not _has_pending_sells(self.strategy_name):
#                         exit_reason = "no_funds"
#                         break
#                     gate.clear()
#             with gate_lock:
#                 rem = strategy_pending_buys.get(self.strategy_name, [])
#             if rem:
#                 stocks = ', '.join(set(b.get('security', '?') for b in rem))
#                 if exit_reason == "no_funds":
#                     print(f"  💸 资金不足放弃 [{self.strategy_name}]: {len(rem)}笔 ({stocks})  ⚠️ 卖出回款仍不够买入目标！")
#                     debug_wework("SKIP", self.strategy_name, None,
#                                  f"卖出完毕但资金不足: {len(rem)}笔买单放弃 ({stocks})")
#                 else:
#                     print(f"  ⏰ 信号门超时 [{self.strategy_name}]: {len(rem)}笔买单已放弃 ({stocks})  ⚠️ 卖出挂单未完成！")
#                     debug_wework("TIMEOUT", self.strategy_name, None,
#                                  f"信号门超时: {len(rem)}笔买单放弃 ({stocks})  ⚠️ 挂单未完成！")
#                 strategy_pending_buys[self.strategy_name] = []
#         else:
#             # 4. 直接执行买入
#             with cache_lock:
#                 available = strategy_cache.get(self.strategy_name, {}).get('available_cash', 0)
#             for b in precomputed:
#                 ta = b.get('_target_amount', 0)
#                 if ta <= available:
#                     if _execute_buy(self.strategy_name, b, ta):
#                         available -= ta
#                 else:
#                     print(f"  💸 资金不足: {b.get('security', '?')} 需={ta:.2f} 有={available:.2f}")


# # ═══════════════════════════════════════════════════════════
# #  撤单监控 (v6.5/v6.5.1: 卖出重试价格笼子校验增强 + F3持仓查询线程安全)
# # ═══════════════════════════════════════════════════════════
# def _cleanup_seq_map(seq):
#     with seq_lock:
#         seq_map.pop(seq, None)
#         for k in [k for k, v in list(seq_map.items())
#                   if k != "_trade_dedup" and isinstance(v, dict) and v.get("db_seq") == seq]:
#             seq_map.pop(k, None)


# def cancel_watcher():
#     _last_empty_log = 0
#     _skipped_seq_logged = set()
#     while not shutdown_flag.is_set():
#         time.sleep(5)
#         if _trading_paused.is_set() or not _qmt_connected or not xt_trader:
#             continue
#         orders = _safe_qmt_query(xt_trader.query_stock_orders, _account)
#         if orders is None:
#             now = time.time()
#             if now - _last_empty_log > 300:
#                 print("⚠️ 撤单监控: query_stock_orders 返回空列表（网关调用）")
#                 _last_empty_log = now
#             continue
#         if not orders:
#             _last_empty_log = 0
#             continue
#         _last_empty_log = 0

#         now = time.time()
#         phase = get_trading_phase()
#         is_just_opened = False
#         if phase == CONTINUOUS:
#             nd = datetime.now()
#             od = nd.replace(hour=9, minute=30, second=0, microsecond=0)
#             if 0 <= (nd - od).total_seconds() < CANCEL_SKIP_OPEN_SEC:
#                 is_just_opened = True

#         cancel_candidates = []

#         for o in orders:
#             oid = str(getattr(o, 'order_id', '') or '')
#             info = db.get_pending_by_order_id(oid) if oid and oid != '0' else None
#             if not info:
#                 sn = str(getattr(o, 'strategy_name', '') or '')
#                 sc = str(getattr(o, 'stock_code', '') or '')
#                 of = getattr(o, 'offset_flag', 0)
#                 od2 = 'buy' if of == 48 else 'sell'
#                 if sn and sc:
#                     for p in db.get_all_pending():
#                         if p['strategy_name'] == sn and p['stock_code'] == sc and p['direction'] == od2 \
#                                 and p['status'] not in ('filled', 'cancelled'):
#                             info = p
#                             break
#             if not info:
#                 continue

#             seq = info.get('seq')
#             live = db.get_pending_by_seq(seq)
#             if not live or live.get('status') in ('filled', 'cancelled'):
#                 if seq not in _skipped_seq_logged:
#                     print(f"⚠️ 撤单监控: 订单号={seq} 已成交/废单(竞态)，跳过")
#                     _skipped_seq_logged.add(seq)
#                 if len(_skipped_seq_logged) > 500:
#                     _skipped_seq_logged.clear()
#                 continue

#             if o.order_status not in (49, 50, 55):
#                 continue
#             age = now - info.get('submit_ts', now)
#             ws = CANCEL_WAIT_SEC_AUCTION if phase == PRE_CALL else CANCEL_WAIT_SEC
#             if is_just_opened and age < CANCEL_SKIP_OPEN_SEC:
#                 continue
#             if age < ws:
#                 continue

#             retry = info.get('retry_count', 0)
#             oid2 = info.get("order_id") or str(o.order_id)

#             if retry >= MAX_RETRY:
#                 print(f"❌ 撤单监控: 订单号={seq} 达最大重试，放弃")
#                 direction = info.get('direction')
#                 frozen = info.get('frozen_cash', 0)
#                 sn = info.get('strategy_name')
#                 with seq_lock:
#                     _cleanup_seq_map(seq)
#                 if direction == 'buy' and frozen > 0:
#                     oq = info.get('order_qty', 0)
#                     fq = info.get('filled_qty', 0)
#                     rel = frozen * (oq - fq) / oq if oq > 0 else frozen
#                     if rel > 0:
#                         db.update_available_cash(sn, rel)
#                         with cache_lock:
#                             if sn in strategy_cache:
#                                 strategy_cache[sn]['available_cash'] += rel
#                 db.delete_pending(seq)
#                 if direction == 'sell':
#                     _decr_pending_sells(sn)
#                     _wake_signal_gate(sn)
#                 debug_wework("ERROR", sn, info.get('stock_code', '?'),
#                              f"撤单达最大重试(>{MAX_RETRY}) seq={seq} | 方向={direction} | 放弃并释放资金")
#                 continue

#             if not oid2 or oid2 == '0':
#                 print(f"⚠️ 撤单监控: 订单号={seq} 委托编号无效={oid2}，无法撤单")
#                 continue

#             print(f"🔄 撤单提交: {o.stock_code} 订单号={seq} 委托编号={oid2} 重试次数={retry}")
#             _safe_qmt_query(xt_trader.cancel_order_stock, _account, int(oid2))
#             cancel_candidates.append({"info": info, "oid2": oid2, "seq": seq, "stock": o.stock_code, "retry": retry})

#         if not cancel_candidates:
#             continue

#         time.sleep(1)
#         oa = _safe_qmt_query(xt_trader.query_stock_orders, _account)
#         active_ids = {str(x.order_id) for x in (oa or []) if x.order_status in (49, 50)}

#         for c in cancel_candidates:
#             info, oid2, seq, stock, retry = c["info"], c["oid2"], c["seq"], c["stock"], c["retry"]
#             if oid2 in active_ids:
#                 print(f"⚠️ 撤单未生效: 委托编号={oid2} 订单号={seq}")
#                 db.update_pending_retry(seq, retry + 1)
#                 continue

#             ic = db.get_pending_by_seq(seq)
#             if not ic or ic.get('status') in ('filled', 'cancelled'):
#                 sta = ic.get('status') if ic else '已删除'
#                 sta_cn = {'filled': '已成交', 'cancelled': '已撤单'}.get(sta, sta)
#                 msg = f"回调已处理（状态={sta_cn}），跳过重试"
#                 print(f"⚠️ 撤单重试: 订单号={seq} {msg}")
#                 continue

#             strategy = info['strategy_name']
#             direction = info['direction']
#             new_price = get_real_price(stock, direction, info['order_price'], retry_count=retry + 1)

#             if direction == 'buy':
#                 if not db.try_claim_for_retry(seq):
#                     print(f"⚠️ 撤单重试(买): 订单号={seq} 状态锁定失败，可能已被回调修改")
#                     continue
#                 ic = db.get_pending_by_seq(seq)
#                 if not ic:
#                     print(f"⚠️ 撤单重试(买): 订单号={seq} 记录已被删除，跳过")
#                     continue
#                 of2 = ic.get('frozen_cash', 0)
#                 fq2 = ic.get('filled_qty', 0)
#                 oq2 = ic.get('order_qty', 0)
#                 rq = oq2 - fq2
#                 if rq < 100:
#                     print(f"⚠️ 撤单重试(买): 订单号={seq} 剩余{rq}股不足1手，放弃")
#                     db.delete_pending(seq)
#                     _cleanup_seq_map(seq)
#                     continue
#                 rel = of2 * rq / oq2 if oq2 > 0 else of2
#                 nf = rq * new_price + get_commission(stock, rq, new_price)
#                 with cache_lock:
#                     avail = strategy_cache.get(strategy, {}).get('available_cash', 0)
#                 if nf > avail + rel:
#                     print(f"💸 重试资金不足: {strategy} 订单号={seq}")
#                     db.delete_pending(seq)
#                     _cleanup_seq_map(seq)
#                     continue
#                 remark = f"{strategy}_{stock}_buy_{rq}股@{new_price:.3f}_{int(time.time() * 1000000)}"
#                 submit_order_async(strategy, stock, 'buy', rq, new_price, remark,
#                                   frozen_cash=nf, retry_seq=seq, old_frozen=rel)
#                 print(f"✅ 重试提交: {stock} 买入 {rq}股@{new_price:.3f} 重试次数={retry + 1}")
#                 debug_wework("RETRY", strategy, stock,
#                              f"买入重试 订单号={seq} {rq}股 @ {new_price:.3f} 重试次数={retry + 1}")
#             else:
#                 if not db.try_claim_for_retry(seq):
#                     print(f"⚠️ 撤单重试(卖): 订单号={seq} 状态锁定失败，可能已被回调修改")
#                     continue
#                 ic = db.get_pending_by_seq(seq)
#                 if not ic:
#                     print(f"⚠️ 撤单重试(卖): 订单号={seq} 记录已被删除，跳过")
#                     continue
#                 rq = ic.get('order_qty', 0) - ic.get('filled_qty', 0)
#                 if rq < 100:
#                     print(f"⚠️ 撤单重试(卖): 订单号={seq} 剩余{rq}股不足1手，放弃")
#                     db.delete_pending(seq)
#                     _cleanup_seq_map(seq)
#                     continue

#                 # v6.5 Fix (Bug 3): 卖出重试前也进行可用持仓校验
#                 _, qmt_can_use = _get_qmt_position_volume(stock)
#                 if qmt_can_use > 0:
#                     rq = min(rq, int(qmt_can_use / 100) * 100)
#                 if rq < 100:
#                     print(f"⚠️ 撤单重试(卖): 订单号={seq} 可用持仓不足，放弃")
#                     db.delete_pending(seq)
#                     _cleanup_seq_map(seq)
#                     _decr_pending_sells(strategy)
#                     _wake_signal_gate(strategy)
#                     continue

#                 # v6.5 Fix (Bug 5): new_price已经经过get_real_price的笼子校验
#                 remark = f"{strategy}_{stock}_sell_{rq}股@{new_price:.3f}_{int(time.time() * 1000000)}"
#                 submit_order_async(strategy, stock, 'sell', rq, new_price, remark,
#                                   retry_seq=seq, old_frozen=0.0)
#                 print(f"✅ 重试提交: {stock} 卖出 {rq}股@{new_price:.3f} 重试次数={retry + 1}")
#                 debug_wework("RETRY", strategy, stock,
#                              f"卖出重试 订单号={seq} {rq}股 @ {new_price:.3f} 重试次数={retry + 1}")


# # ═══════════════════════════════════════════════════════════
# #  Redis 监听 & 信号分发 (v6.5.2: 线程池 + 细化异常)
# # ═══════════════════════════════════════════════════════════
# # 全局线程池: 控制指令最多10个并发线程，防止线程爆炸
# _control_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="ctrl-")
# # 信号分发线程池: 最多20个并发，防止_dispatch_signal阻塞主监听
# _signal_executor = ThreadPoolExecutor(max_workers=20, thread_name_prefix="sig-")


# def _redis_listener():
#     delay = RECONNECT_INITIAL
#     r = None
#     retry_count = 0  # v6.5.2: 重连次数计数
#     MAX_RETRIES = 30  # 最多重试30次，约30分钟后退出
#     while not shutdown_flag.is_set() and retry_count < MAX_RETRIES:
#         try:
#             if r is None:
#                 print(f"[{datetime.now()}] 🔌 Redis 连接中... (重试 {retry_count}/{MAX_RETRIES})")
#                 r = redis_conn_factory()
#                 r.ping()
#                 print(f"[{datetime.now()}] ✅ Redis 已连接，监听 list: {CHANNEL_SIGNALS} + {CHANNEL_CONTROL}")
#                 retry_count = 0  # 连接成功重置计数
#                 delay = RECONNECT_INITIAL
#             while not shutdown_flag.is_set():
#                 result = r.blpop([CHANNEL_SIGNALS, CHANNEL_CONTROL], timeout=1)
#                 if result is None:
#                     continue
#                 ch, raw_data = result
#                 if isinstance(ch, bytes):
#                     ch = ch.decode()
#                 if isinstance(raw_data, bytes):
#                     raw_data = raw_data.decode()
#                 try:
#                     data = json.loads(raw_data)
#                 except json.JSONDecodeError:
#                     continue
#                 if ch == CHANNEL_CONTROL:
#                     # v6.5.2: 线程池替代无限new Thread，防止线程爆炸
#                     _control_executor.submit(_handle_control_safe, data)
#                 elif ch == CHANNEL_SIGNALS:
#                     # v6.5.2: 线程池提交信号分发，防止阻塞监听线程
#                     _signal_executor.submit(_dispatch_signal_safe, data, r)
#         except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
#             retry_count += 1
#             print(f"[{datetime.now()}] ⚠️ Redis 断开: {e} (重试 {retry_count}/{MAX_RETRIES})")
#         except Exception as e:
#             # v6.5.2: 业务异常不触发重连，只记录日志
#             print(f"[{datetime.now()}] ❌ 业务处理异常: {e}")
#             # 不重连，继续循环尝试读取
#         if r:
#             try:
#                 r.close()
#             except Exception:
#                 pass
#             r = None
#         if not shutdown_flag.is_set() and retry_count < MAX_RETRIES:
#             print(f"[{datetime.now()}] ⏳ Redis {delay}s后重连...")
#             time.sleep(delay)
#             delay = min(delay * 2, RECONNECT_MAX)
#     if retry_count >= MAX_RETRIES:
#         print(f"[{datetime.now()}] 🛑 Redis 重试次数耗尽({MAX_RETRIES})，监听线程退出")


# def _handle_control_safe(data):
#     """v6.5.2: 安全包装，防止异常逃逸到线程池"""
#     try:
#         _handle_control(data)
#     except Exception as e:
#         print(f"[{datetime.now()}] ❌ 控制指令处理异常: {e}")


# def _dispatch_signal_safe(data, rc=None):
#     """v6.5.2: 安全包装，防止异常逃逸到线程池"""
#     try:
#         _dispatch_signal(data, rc)
#     except Exception as e:
#         print(f"[{datetime.now()}] ❌ 信号分发异常: {e}")


# def _get_stock_name_from_mysql(code6):
#     """从MySQL home_ashareuniverse表查询股票名称（仅回测启用时有效）"""
#     if not ENABLE_BACKTEST:
#         return ""
#     try:
#         conn = MySQLdb.connect(**MYSQL_CONFIG)
#         cursor = conn.cursor()
#         cursor.execute("SELECT name FROM home_ashareuniverse WHERE symbol = %s", (code6,))
#         row = cursor.fetchone()
#         cursor.close()
#         conn.close()
#         if row:
#             return row[0]
#     except Exception as e:
#         print(f"⚠️ 查询股票名称失败[{code6}]: {e}")
#     return ""


# def _get_backtest_filename(strategy, date_str):
#     """生成回测记录文件名: 策略名_年月日.xlsx"""
#     safe_strategy = strategy.replace("/", "_").replace("\\", "_").replace(":", "_")
#     filename = f"{safe_strategy}_{date_str}.xlsx"
#     return os.path.join(BACKTEST_RECORD_DIR, filename)


# def _write_backtest_excel(record):
#     """将回测信号写入Excel文件（同一策略同一天追加到同一文件）"""
#     if not ENABLE_BACKTEST:
#         return
#     strategy = record.get('strategy', '')
#     sec = record.get('sec', '')
#     action = record.get('action', '')
#     qty = record.get('qty', 0)
#     price = record.get('price', 0)
#     amount = record.get('amount', 0)
#     xdsj_str = record.get('xdsj_str', '')

#     # 解析日期和时间
#     signal_date = ""
#     signal_time = ""
#     if xdsj_str:
#         try:
#             dt_obj = datetime.strptime(xdsj_str, "%Y-%m-%d %H:%M:%S")
#             signal_date = dt_obj.strftime("%Y-%m-%d")
#             signal_time = dt_obj.strftime("%H:%M:%S")
#         except Exception:
#             pass

#     # 提取6位代码并查询名称
#     code6 = sec.split('.')[0] if '.' in sec else sec
#     stock_name = _get_stock_name_from_mysql(code6)
#     # 标的格式: 新华制药(000756.XSHE)
#     biaodi = f"{stock_name}({sec})" if stock_name else sec

#     # 交易类型
#     trade_type = "卖" if action == 'sell' else "买"

#     # 成交数量/金额: 卖出为负
#     qty_signed = -abs(qty) if action == 'sell' else abs(qty)
#     amount_signed = -abs(amount) if action == 'sell' else abs(amount)

#     # 生成文件名 (YYYYMMDD格式，使用今天日期)
#     date_str = datetime.now().strftime("%Y%m%d")
#     filepath = _get_backtest_filename(strategy, date_str)

#     # 表头
#     headers = [
#         "日期", "委托时间", "品种", "标的", "交易类型", "下单类型",
#         "成交数量", "成交价", "成交额", "委托数量", "委托价格",
#         "平仓盈亏", "手续费", "状态", "最后更新时间"
#     ]

#     # 数据行
#     now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#     row_data = [
#         signal_date,  # 日期
#         signal_time,  # 委托时间
#         "股票",  # 品种
#         biaodi,  # 标的
#         trade_type,  # 交易类型
#         "市价单",  # 下单类型
#         qty_signed,  # 成交数量
#         price,  # 成交价
#         amount_signed,  # 成交额
#         qty,  # 委托数量
#         None,  # 委托价格 (空)
#         None,  # 平仓盈亏 (空)
#         None,  # 手续费 (空)
#         "全部成交",  # 状态
#         now_str,  # 最后更新时间
#     ]

#     # 列宽
#     col_widths = [12, 10, 8, 28, 8, 10, 12, 10, 14, 12, 10, 10, 10, 10, 20]

#     if os.path.exists(filepath):
#         # 文件已存在，追加行
#         wb = load_workbook(filepath)
#         ws = wb.active
#         next_row = ws.max_row + 1
#         for col_idx, val in enumerate(row_data, 1):
#             cell = ws.cell(row=next_row, column=col_idx, value=val)
#             cell.alignment = Alignment(horizontal='center', vertical='center')
#         wb.save(filepath)
#         print(f"✅ 回测记录已追加: {filepath} (第{next_row - 1}行)")
#     else:
#         # 文件不存在，创建新文件
#         wb = Workbook()
#         ws = wb.active
#         ws.title = "回测记录"

#         # 写入表头
#         for col_idx, header in enumerate(headers, 1):
#             cell = ws.cell(row=1, column=col_idx, value=header)
#             cell.font = Font(bold=True)
#             cell.alignment = Alignment(horizontal='center', vertical='center')

#         # 写入第一行数据
#         for col_idx, val in enumerate(row_data, 1):
#             cell = ws.cell(row=2, column=col_idx, value=val)
#             cell.alignment = Alignment(horizontal='center', vertical='center')

#         # 调整列宽
#         for i, w in enumerate(col_widths, 1):
#             ws.column_dimensions[chr(64 + i)].width = w

#         wb.save(filepath)
#         print(f"✅ 回测记录已创建: {filepath} (第1行)")


# def _dispatch_signal(data, rc=None):
#     t_recv = time.time()
#     send_ts = data.get('current_time', 0)
#     xdsj_str = data.get('xdsj', '')
#     signal_ts = None
#     if xdsj_str:
#         try:
#             signal_ts = datetime.strptime(xdsj_str, "%Y-%m-%d %H:%M:%S").timestamp()
#         except Exception:
#             pass
#     is_backtest = signal_ts and (signal_ts < time.time() - 7200)

#     jq2redis = r2local = None
#     if rc:
#         try:
#             res = rc.time()
#             rs = res[0] + res[1] / 1e6
#             jq2redis = max(0, (rs - send_ts) * 1000) if send_ts else None
#         except Exception:
#             pass
#         try:
#             t0 = time.time()
#             rc.ping()
#             t1 = time.time()
#             r2local = (t1 - t0) * 500
#         except Exception:
#             pass
#     total_ms = (jq2redis or 0) + (r2local or 0)
#     if total_ms == 0 and send_ts:
#         total_ms = (t_recv - send_ts) * 1000

#     strategy = data.get('strategy_name', '')
#     if not strategy:
#         return print("⚠️ 信号缺少strategy_name")

#     sec = data.get('security', '-')
#     action = data.get('action', '')
#     emoji = '🟢 卖出' if action == 'sell' else '🔴 买入'
#     qty = data.get('amount_diff', 0)
#     price = data.get('current_price', 0)
#     amount = qty * price
#     weight = data.get('weight', 'N/A')

#     print(f"\n{'=' * 75}")
#     print(f"📩 [{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] 收到交易信号")
#     print(f"  策略: {strategy}")
#     print(f"  标的: {sec}")
#     print(f"  操作: {emoji}")
#     print(f"  数量: {qty}股")
#     print(f"  价格: {price}元")
#     print(f"  成交金额: {amount:.1f}元")
#     print(f"  目标仓位: {weight}")
#     if xdsj_str:
#         print(f"  信号时间: {xdsj_str}")

#     jq_str = f"{jq2redis:.1f} ms" if jq2redis is not None else "N/A"
#     r2l_str = f"{r2local:.1f} us" if r2local is not None else "N/A"
#     total_str = f"{total_ms:.1f} ms"
#     print(f"  延迟: 聚宽→Redis {jq_str} | Redis→本地 {r2l_str} | 总计 {total_str}")

#     if is_backtest:
#         print(f"🚩  回测信号不交易！{'已开启回测记录，将以表格形式存入本地！' if ENABLE_BACKTEST else '未开启回测记录功能，跳过'}")
#         try:
#             _write_backtest_excel({
#                 'strategy': strategy,
#                 'sec': sec,
#                 'action': action,
#                 'qty': qty,
#                 'price': price,
#                 'amount': amount,
#                 'xdsj_str': xdsj_str,
#             })
#         except Exception as e:
#             print(f"🚩  回测记录写入失败: {e}")
#         return
#     if not DEBUG_IGNORE_WORK_HOURS and not is_work_time():
#         return print("⏱️ 非工作时间跳过")

#     sec_qmt = convert_stock_code(data.get('security', ''))
#     dk = f"{strategy}|{sec_qmt}|{action}|{data.get('amount_diff')}|{data.get('current_price')}"
#     if db.is_signal_dup(dk):
#         return print("⏩ 重复信号跳过")
#     if strategy not in strategy_queues:
#         return print(f"⚠️ 未知策略[{strategy}] 已知:{list(strategy_queues.keys())}")

#     if TradeEnable:
#         try:
#             strategy_queues[strategy].put(data, block=False)
#         except Full:
#             print("⚠️ 队列已满丢弃")
#     else:
#         print("⚠️ TradeEnable=False")


# # ═══════════════════════════════════════════════════════════
# #  控制通道 (与6.4.1一致)
# # ═══════════════════════════════════════════════════════════
# def _handle_control(data):
#     cmd = data.get('cmd', '')
#     params = {k: v for k, v in data.items() if k != 'cmd'}
#     print(f"\n📋 控制指令: {cmd}")
#     if cmd == 'transfer':
#         _cmd_transfer(data)
#     elif cmd == 'query':
#         _cmd_query(data)
#     elif cmd == 'pause':
#         _cmd_pause(data, False)
#     elif cmd == 'resume':
#         _cmd_pause(data, True)
#     else:
#         db.add_control_log(cmd, params, 0, f"unknown: {cmd}")


# def _cmd_transfer(data):
#     fs, ts = data.get('from', ''), data.get('to', '')
#     try:
#         amt = float(data.get('amount', 0))
#     except Exception:
#         return print("  ❌ 无效金额")
#     if amt <= 0 or fs == ts or fs not in strategy_cache or ts not in strategy_cache:
#         return print("  ❌ 参数无效")
#     with cache_lock:
#         fb = strategy_cache[fs]["available_cash"]
#         tb = strategy_cache[ts]["available_cash"]
#         if amt > fb:
#             return print(f"  ❌ [{fs}] 余额不足 {fb:.2f}")
#         strategy_cache[fs]["available_cash"] -= amt
#         strategy_cache[ts]["available_cash"] += amt
#         fa, ta = strategy_cache[fs]["available_cash"], strategy_cache[ts]["available_cash"]
#     db.update_available_cash(fs, -amt)
#     db.update_available_cash(ts, amt)
#     db.add_transfer_log(fs, ts, amt, fb, tb, fa, ta)
#     db.add_control_log('transfer', data, 1, f"OK")
#     print(f"  ✅ [{fs}] {fb:.2f}→{fa:.2f} | [{ts}] {tb:.2f}→{ta:.2f}")


# def _cmd_query(data):
#     results = {}
#     with cache_lock:
#         snap = {s: {'cap': c['initial_capital'], 'cash': round(c['available_cash'], 2),
#                     'en': bool(c.get('enabled', True))} for s, c in strategy_cache.items()}
#     for s, v in snap.items():
#         pos = db.get_all_positions(s)
#         pv = 0.0
#         if pos:
#             try:
#                 tks = _safe_get_tick(list(pos.keys()))
#                 for sc, info in pos.items():
#                     pv += info['volume'] * (tks.get(sc, {}).get('lastPrice', 0) if tks else 0)
#             except Exception:
#                 pass
#         results[s] = {'cap': v['cap'], 'cash': v['cash'], 'mkt': round(pv, 2),
#                       'eq': round(v['cash'] + pv, 2), 'en': v['en']}
#     db.add_control_log('query', data, 1, json.dumps(results, ensure_ascii=False))
#     print("📊 资金查询:")
#     for s, r in results.items():
#         pnl = r['eq'] - r['cap']
#         print(
#             f"  [{'ON' if r['en'] else 'OFF'}] {s} cap={r['cap']:.0f} cash={r['cash']:.0f} mkt={r['mkt']:.0f} eq={r['eq']:.0f} pnl={pnl:+.0f}")


# def _cmd_pause(data, enable):
#     s = data.get('strategy_name', '')
#     if s not in strategy_cache:
#         return print(f"  ❌ 策略未找到: {s}")
#     db.set_strategy_enabled(s, enable)
#     with cache_lock:
#         strategy_cache[s]['enabled'] = enable
#     act = 'resume' if enable else 'pause'
#     db.add_control_log(act, data, 1, f"{s} {'on' if enable else 'off'}")
#     print(f"  ✅ {act.upper()} [{s}]")


# # ═══════════════════════════════════════════════════════════
# #  QMT 健康检查 & 清理 (与6.4.1一致)
# # ═══════════════════════════════════════════════════════════
# def _qmt_health_checker():
#     global _qmt_connected, xt_trader, _account, _trading_paused_ts, QMT_GATEWAY
#     while not shutdown_flag.is_set():
#         time.sleep(10)
#         if not xt_trader:
#             continue
#         a = _safe_qmt_query(xt_trader.query_stock_asset, _account)
#         if a:
#             if not _qmt_connected and not _trading_paused.is_set():
#                 _qmt_connected = True
#                 print(f"[{datetime.now()}] ✅ QMT 重连成功")
#         else:
#             if _qmt_connected:
#                 _qmt_connected = False
#                 print(f"[{datetime.now()}] ⚠️ QMT 资产为空")
#             if not shutdown_flag.is_set():
#                 print(f"[{datetime.now()}] 🔄 QMT 重连中...")
#                 _trading_paused.set()
#                 _trading_paused_ts = time.time()
#                 print(f"[{datetime.now()}] ⏳ 排空QMT网关...")
#                 _gw_shutdown_timeout(30)
#                 QMT_GATEWAY = ThreadPoolExecutor(max_workers=1, thread_name_prefix="qmt-gw")
#                 print(f"[{datetime.now()}] ✅ 网关已排空并重建")
#                 try:
#                     with _qmt_lock:
#                         try:
#                             xt_trader.stop()
#                         except Exception:
#                             pass
#                         time.sleep(1)
#                         sid = random.randint(100000, 999999)
#                         xt_trader = XtQuantTrader(MINI_PATH, sid)
#                         xt_trader.register_callback(_CB())
#                         xt_trader.start()
#                         if xt_trader.connect() == 0:
#                             if xt_trader.subscribe(_account) == 0:
#                                 _qmt_connected = True
#                                 reconcile_on_startup()
#                                 _trading_paused.clear()
#                                 _trading_paused_ts = 0
#                                 print(f"[{datetime.now()}] ✅ QMT 重连成功")
#                             else:
#                                 for _ in range(3):
#                                     time.sleep(5)
#                                     if xt_trader.subscribe(_account) == 0:
#                                         _qmt_connected = True
#                                         reconcile_on_startup()
#                                         _trading_paused.clear()
#                                         break
#                         else:
#                             time.sleep(30)
#                 except Exception as re:
#                     print(f"[{datetime.now()}] ❌ 重连异常: {re}")
#                     time.sleep(30)
#         if _trading_paused.is_set() and _trading_paused_ts > 0 and time.time() - _trading_paused_ts > 120:
#             print(f"[{datetime.now()}] ⚠️ 暂停超120s强制重连")
#             _qmt_connected = False
#             _trading_paused_ts = time.time()


# def _cleanup_watcher():
#     while not shutdown_flag.is_set():
#         time.sleep(300)
#         now = time.time()
#         with seq_lock:
#             td = seq_map.get("_trade_dedup", {})
#             for k in [k for k, t in td.items() if now - t > 300]:
#                 del td[k]
#             orphans = [k for k in list(seq_map.keys()) if k != "_trade_dedup"
#                       and (not db.get_pending_by_seq(k) or
#                             (db.get_pending_by_seq(k) or {}).get('submit_ts', 0) < now - 14400)]
#             for k in orphans:
#                 seq_map.pop(k, None)
#         if orphans:
#             print(f"🧹 清理{len(orphans)}条无效订单记录")


# # ═══════════════════════════════════════════════════════════
# #  初始化 & 对账 (与6.4.1一致)
# # ═══════════════════════════════════════════════════════════
# def init_qmt():
#     global xt_trader, _account, _qmt_connected
#     sid = random.randint(100000, 999999)
#     xt_trader = XtQuantTrader(MINI_PATH, sid)
#     _account = StockAccount(ACCOUNT_ID, ACCOUNT_TYPE)
#     xt_trader.register_callback(_CB())
#     xt_trader.start()
#     if xt_trader.connect() != 0:
#         return print("❌ QMT连接失败") or False
#     if xt_trader.subscribe(_account) != 0:
#         return print("❌ QMT订阅失败") or False
#     _qmt_connected = True
#     print(f"✅ QMT启动成功! {MINI_PATH} {ACCOUNT_ID}")
#     return True


# def _warmup_gateway():
#     try:
#         asset = _safe_qmt_query(xt_trader.query_stock_asset, _account)
#         if asset:
#             print(f"🔥 网关预热成功，实盘总资产: {getattr(asset, 'total_asset', 0):,.2f}")
#         else:
#             print("  ⚠️ 网关预热返回空")
#     except Exception as e:
#         print(f"  ⚠️ 网关预热异常: {e}")


# def init_strategy_funds():
#     for sn, cap in STRATEGY_INITIAL_CAPITAL.items():
#         row = db.get_strategy_funds(sn)
#         if row and INIT_BALANCE_MODE == "auto":
#             with cache_lock:
#                 strategy_cache[sn] = {'available_cash': row['available_cash'],
#                                       'initial_capital': row['initial_capital'],
#                                       'enabled': bool(row['enabled'])}
#             print(f"  [{sn}] 恢复: 本金={row['initial_capital']:.2f} 闲置={row['available_cash']:.2f}")
#         else:
#             c = row['initial_capital'] if row else cap
#             db.set_strategy_funds(sn, c, c)
#             with cache_lock:
#                 strategy_cache[sn] = {'initial_capital': c, 'available_cash': c, 'enabled': True}
#             print(f"  [{sn}] 重置: {c:.2f}")


# def reconcile_trades_from_qmt():
#     trades = _safe_qmt_query(xt_trader.query_stock_trades, _account)
#     if trades is None:
#         return print(f"⚠️ 对账失败: 网关查询异常") or 0
#     n = 0
#     for t in trades:
#         code, vol, price = t.stock_code, t.traded_volume, t.traded_price
#         flag = getattr(t, 'offset_flag', 0)
#         oid = str(getattr(t, 'order_id', '') or '')
#         remark = str(getattr(t, 'order_remark', '') or '')
#         sn = str(getattr(t, 'strategy_name', '') or '')
#         if not sn:
#             continue
#         if db.get_trade_by_remark(remark, code, vol, price):
#             continue
#         action = "buy" if flag == 48 else "sell"
#         comm = get_commission(code, vol, price)
#         if action == 'buy':
#             cost = vol * price + comm
#             db.update_available_cash(sn, -cost)
#             with cache_lock:
#                 if sn in strategy_cache: strategy_cache[sn]['available_cash'] -= cost
#             db.update_position(sn, code, vol, price)
#         else:
#             proc = vol * price - comm
#             db.update_available_cash(sn, proc)
#             with cache_lock:
#                 if sn in strategy_cache: strategy_cache[sn]['available_cash'] += proc
#             db.update_position(sn, code, -vol, price)
#         db.add_trade(sn, code, action, price, vol, vol * price, comm, datetime.now().isoformat(), oid, remark)
#         n += 1
#     return n


# def reconstruct_positions_from_trade_records():
#     print("🔨 从交易记录重建持仓...")
#     with db._connect() as c:
#         rows = c.execute("SELECT strategy_name, stock_code, action, SUM(traded_volume) as nv "
#                          "FROM trade_records GROUP BY strategy_name, stock_code, action").fetchall()
#     for sn in STRATEGY_INITIAL_CAPITAL:
#         for code in db.get_all_positions(sn):
#             db.update_position(sn, code, -db.get_all_positions(sn)[code]["volume"], 0)
#     net = defaultdict(int)
#     for r in rows:
#         v = r["nv"] if r["action"] == "buy" else -r["nv"]
#         net[(r["strategy_name"], r["stock_code"])] += v
#     rc = 0
#     for (sn, code), vol in net.items():
#         if sn not in STRATEGY_INITIAL_CAPITAL or vol <= 0: continue
#         ac = 0.0
#         with db._connect() as c:
#             r2 = c.execute(
#                 "SELECT AVG(traded_price) FROM trade_records WHERE strategy_name=? AND stock_code=? AND action='buy'",
#                 (sn, code)).fetchone()
#             if r2 and r2[0]:
#                 ac = r2[0]
#         db.update_position(sn, code, vol, ac)
#         rc += 1
#     # 现金重建
#     print("💰 从交易记录重建现金...")
#     with db._connect() as c:
#         cur = c.execute("SELECT strategy_name, action, SUM(traded_amount) as ta, SUM(commission) as tc "
#                         "FROM trade_records WHERE strategy_name IN ({}) GROUP BY strategy_name, action".format(
#             ",".join("?" * len(STRATEGY_INITIAL_CAPITAL))), tuple(STRATEGY_INITIAL_CAPITAL.keys()))
#         ts2 = {s: {"buy": 0.0, "sell": 0.0, "comm": 0.0} for s in STRATEGY_INITIAL_CAPITAL}
#         for r in cur.fetchall():
#             sn = r["strategy_name"]
#             if r["action"] == "buy":
#                 ts2[sn]["buy"] = r["ta"] or 0
#             else:
#                 ts2[sn]["sell"] = r["ta"] or 0
#             ts2[sn]["comm"] += r["tc"] or 0
#         trs = {s: {"in": 0.0, "out": 0.0} for s in STRATEGY_INITIAL_CAPITAL}
#         for r in c.execute(
#                 "SELECT from_strategy, to_strategy, SUM(amount) FROM transfer_log GROUP BY from_strategy, to_strategy"):
#             if r[0] in trs:
#                 trs[r[0]]["out"] += r[2] or 0
#             if r[1] in trs:
#                 trs[r[1]]["in"] += r[2] or 0
#     for sn, cap in STRATEGY_INITIAL_CAPITAL.items():
#         dr = db.get_strategy_funds(sn)
#         capital = dr['initial_capital'] if dr else cap
#         t = ts2.get(sn, {})
#         tr = trs.get(sn, {})
#         nc = capital + t.get("sell", 0) - t.get("buy", 0) - t.get("comm", 0) + tr.get("in", 0) - tr.get("out", 0)
#         with cache_lock:
#             oc = strategy_cache.get(sn, {}).get("available_cash", capital)
#         if abs(nc - oc) > 0.01:
#             db.set_strategy_funds(sn, capital, nc)
#             with cache_lock:
#                 if sn in strategy_cache:
#                     strategy_cache[sn]["available_cash"] = nc
#                     strategy_cache[sn]["initial_capital"] = capital
#             print(f"  现金修正: [{sn}] {oc:,.2f}→{nc:,.2f}")
#     print(f"✅ 重建完成: {rc}个持仓")


# def manual_position_attribution():
#     # 核心判断：trade_records 为空 = 首次运行/数据重置，必须全量指派
#     with db._connect() as c:
#         trade_count = c.execute("SELECT COUNT(*) FROM trade_records").fetchone()[0]
#     force_all = (trade_count == 0)

#     try:
#         qp = _safe_qmt_query(xt_trader.query_stock_positions, _account)
#     except Exception as e:
#         return print(f"⚠️ QMT持仓查询失败: {e}")
#     if qp is None:
#         return print(f"⚠️ QMT持仓查询失败: 网关返回None")

#     if not qp:
#         if force_all:
#             print("ℹ️ 首次运行但账户无持仓，无需指派")
#         return

#     qm = {}
#     for p in qp:
#         vol = getattr(p, "volume", 0)
#         if vol > 0:
#             qm[p.stock_code] = qm.get(p.stock_code, 0) + vol

#     if force_all:
#         unclaimed = dict(qm)
#     else:
#         dm = {}
#         for sn in STRATEGY_INITIAL_CAPITAL:
#             for c, i in db.get_all_positions(sn).items():
#                 dm[c] = dm.get(c, 0) + i["volume"]
#         unclaimed = {c: qm[c] - dm.get(c, 0) for c in qm if qm[c] > dm.get(c, 0)}

#     if not unclaimed:
#         if force_all:
#             print("ℹ️ 首次运行检查完毕，账户无待指派持仓")
#         return

#     strategies = list(STRATEGY_INITIAL_CAPITAL.keys())
#     print(f"\n{'=' * 75}")
#     if force_all:
#         print("  🆕 检测到交易记录为空，需将实盘全部持仓重新指派！")
#         print("  ⚠️  不指派会导致后续买卖信号无法匹配持仓和资金")
#     else:
#         print("  ⚠️ 检测到未归属持仓，需手动指派")
#     print(f"{'=' * 75}")

#     while True:
#         unclaimed = {k: v for k, v in unclaimed.items() if v > 0}
#         if not unclaimed:
#             print("\n✅ 所有持仓指派完毕！")
#             break

#         print(f"\n📋 待指派持仓 ({len(unclaimed)}只):")
#         items = list(unclaimed.items())
#         for i, (code, vol) in enumerate(items, 1):
#             print("  {}. {}  {}股".format(i, code, vol))

#         try:
#             ch = input("\n请输入要指派的编号 (输入q退出): ").strip()
#             if ch.lower() == 'q':
#                 if force_all:
#                     print("⚠️ 未完成全部指派，未指派的持仓将无法参与交易！")
#                 break

#             idx = int(ch) - 1
#             if idx < 0 or idx >= len(items):
#                 print("❌ 编号超出范围")
#                 continue

#             code, rem = items[idx]
#             vs = input("  请输入指派股数 (当前剩余{}股, 回车=全部): ".format(rem)).strip()
#             av = rem if not vs else int(vs)
#             if av <= 0 or av > rem:
#                 print("❌ 股数无效")
#                 continue

#             print("  可选策略:")
#             for i, s in enumerate(strategies, 1):
#                 print("    {}. {}".format(i, s))
#             si = int(input("  请输入策略编号: ").strip()) - 1
#             if si < 0 or si >= len(strategies):
#                 print("❌ 策略编号无效")
#                 continue
#             ts = strategies[si]

#             rp = 0.0
#             try:
#                 tks = _safe_get_tick([code])
#                 if tks and code in tks:
#                     rp = tks[code].get("lastPrice", 0)
#             except Exception:
#                 pass

#             mkv = av * rp if rp > 0 else 0.0
#             if mkv > 0:
#                 ps = input(
#                     "  当前价={:.3f} 市值={:.2f}  请输入盈利金额(正=盈利,负=亏损,回车=盈亏0): ".format(rp, mkv)).strip()
#                 pnl = 0.0 if not ps else float(ps)
#                 total_buy = mkv - pnl
#                 cp_est = total_buy / av
#                 comm = get_commission(code, av, cp_est)
#                 cost = total_buy - comm
#                 cp = cost / av
#                 tc = total_buy
#             else:
#                 ps = input("  无法获取市价，请输入成本价: ").strip()
#                 cp = float(ps)
#                 cost = av * cp
#                 comm = get_commission(code, av, cp)
#                 tc = cost + comm

#             db.update_available_cash(ts, -tc)
#             with cache_lock:
#                 if ts in strategy_cache:
#                     strategy_cache[ts]["available_cash"] -= tc
#             db.update_position(ts, code, av, cp)
#             db.add_trade(ts, code, "buy", cp, av, cost, comm,
#                          datetime.now().isoformat(), "MANUAL", "MANUAL_ATTRIBUTION")

#             unclaimed[code] -= av
#             print("  ✅ 成功: [{}] {} {}股 @ {:.3f}  扣减现金={:.2f}".format(ts, code, av, cp, tc))

#         except (ValueError, IndexError):
#             print("❌ 输入格式错误，请重新输入")
#         except (EOFError, KeyboardInterrupt):
#             print("\n⚠️ 用户中断指派")
#             break


# def reconcile_on_startup():
#     _reconciling.set()
#     try:
#         print("🔍 启动对账: 清理遗留挂单...")
#         print("  ⏳ 查询QMT订单列表...")
#         orders = _safe_qmt_query(xt_trader.query_stock_orders, _account)
#         if orders is None:
#             return print(f"  ⚠️ 对账查询失败: 网关返回None")
#         print(f"  ✅ 查询到 {len(orders) if orders else 0} 条QMT订单")
#         om = {str(o.order_id): o for o in (orders or []) if o.order_id}
#         for p in db.get_all_pending():
#             dir_cn = {'buy': '买入', 'sell': '卖出'}.get(p['direction'], p['direction'])
#             sta_cn = {'filled': '已成交', 'cancelled': '已撤单', 'submitted': '已提交',
#                       'acked': '已确认', 'retrying': '重试中', 'partial': '部分成交'}.get(p['status'], p['status'])
#             print(f"  🔍 对账处理: 订单号={p['seq']} 委托编号={p.get('order_id', '无')} "
#                   f"标的={p['stock_code']} 状态={sta_cn} 方向={dir_cn}")
#             seq, oid = p['seq'], str(p.get('order_id') or '')
#             sn, d, fz = p['strategy_name'], p['direction'], p.get('frozen_cash', 0)
#             o = om.get(oid) if oid else None
#             if not o and not oid:
#                 for qo in (orders or []):
#                     if str(getattr(qo, "strategy_name", "")) == sn and str(getattr(qo, "stock_code", "")) == p.get(
#                             "stock_code", ""):
#                         qd = "buy" if getattr(qo, "offset_flag", 0) == 48 else "sell"
#                         if qd == d:
#                             qoid = str(getattr(qo, "order_id", ""))
#                             if qoid and qoid != "0":
#                                 oid, o = qoid, qo
#                                 db.update_pending_order_id(seq, qoid)
#                                 break
#             if not o or o.order_status in (53, 54, 57):
#                 if d == 'buy' and fz > 0:
#                     oq, fq = p.get('order_qty', 0), p.get('filled_qty', 0)
#                     rel = fz * (oq - fq) / oq if oq > 0 else fz
#                     if rel > 0:
#                         db.update_available_cash(sn, rel)
#                         with cache_lock:
#                             if sn in strategy_cache:
#                                 strategy_cache[sn]['available_cash'] += rel
#                 if d == 'sell':
#                     _decr_pending_sells(sn)
#                 db.delete_pending(seq)
#                 with seq_lock:
#                     _cleanup_seq_map(seq)
#             elif o.order_status in (49, 50, 51, 52, 55):
#                 db.update_pending_status(seq, 'partial' if o.order_status in (50, 51, 52, 55) else 'submitted')
#                 with seq_lock:
#                     seq_map[seq] = {'strategy': sn, 'stock': p['stock_code'], 'direction': d, 'order_id': oid}
#             elif o.order_status == 56:
#                 if d == "buy" and fz > 0:
#                     db.update_available_cash(sn, fz)
#                     with cache_lock:
#                         if sn in strategy_cache:
#                             strategy_cache[sn]["available_cash"] += fz
#                 if d == 'sell':
#                     _decr_pending_sells(sn)
#                 db.delete_pending(seq)
#                 with seq_lock:
#                     _cleanup_seq_map(seq)
#         print("  ✅ 对账循环结束，开始清理...")
#         print("✅ 对账完成")
#     finally:
#         _reconciling.clear()


# def _cross_validate_strategies():
#     try:
#         asset = _safe_qmt_query(xt_trader.query_stock_asset, _account)
#         at = getattr(asset, "total_asset", 0) if asset else 0
#     except Exception:
#         return
#     if not at:
#         return
#     te = 0.0
#     for sn in STRATEGY_INITIAL_CAPITAL:
#         with cache_lock:
#             cash = strategy_cache.get(sn, {}).get("available_cash", 0)
#         pos = db.get_all_positions(sn)
#         pv = 0.0
#         if pos:
#             try:
#                 tks = _safe_get_tick(list(pos.keys()))
#                 for sc, i in pos.items():
#                     pv += i["volume"] * (tks.get(sc, {}).get("lastPrice", 0) if tks else 0)
#             except Exception:
#                 pass
#         te += cash + pv
#     if te <= at * 1.02:
#         return
#     print(f"\n⚠️ 策略总权益({te:,.2f})超账户({at:,.2f})，修正...")
#     for sn in STRATEGY_INITIAL_CAPITAL:
#         with cache_lock:
#             cash = strategy_cache.get(sn, {}).get("available_cash", 0)
#             cap = strategy_cache.get(sn, {}).get("initial_capital", 0)
#         if not cap:
#             continue
#         if not db.get_all_positions(sn) and cash > cap * 1.5:
#             with db._connect() as c:
#                 hs = c.execute("SELECT SUM(traded_amount) FROM trade_records WHERE strategy_name=? AND action='sell'",
#                               (sn,)).fetchone()
#                 ht = c.execute("SELECT SUM(amount) FROM transfer_log WHERE to_strategy=?", (sn,)).fetchone()
#             if not (hs and hs[0] and hs[0] > 0) and not (ht and ht[0] and ht[0] > 0):
#                 print(f"  🔧 [{sn}] {cash:,.2f}→{cap:,.2f}")
#                 db.set_strategy_funds(sn, cap, cap)
#                 with cache_lock:
#                     if sn in strategy_cache: strategy_cache[sn]["available_cash"] = cap


# # ═══════════════════════════════════════════════════════════
# #  启动摘要 & 主控 (v6.5.1: 启动部分成交重试线程 + F1F2F3修复验证)
# # ═══════════════════════════════════════════════════════════
# def _print_startup_summary():
#     print(f"\n{'=' * 75}\n策略启动摘要:")
#     # 从QMT仓位查询直接获取每只股票的市值，不依赖xtdata行情
#     qmt_mkt = {}
#     # v6.5.1 F3修复: 走_safe_qmt_query保护，避免直接调用QMT API
#     try:
#         qp = _safe_qmt_query(xt_trader.query_stock_positions, _account)
#         if qp:
#             for p in qp:
#                 sc = getattr(p, 'stock_code', '')
#                 vol = getattr(p, 'volume', 0)
#                 mv = getattr(p, 'market_value', 0)
#                 if sc and vol > 0:
#                     qmt_mkt[sc] = (vol, mv)
#     except Exception:
#         pass

#     tc = te = 0.0
#     for sn in STRATEGY_INITIAL_CAPITAL:
#         with cache_lock:
#             c = strategy_cache.get(sn, {})
#         cap, cash = c.get('initial_capital', 0), c.get('available_cash', 0)
#         tc += cap
#         pos = db.get_all_positions(sn)
#         pv = 0.0
#         if pos:
#             for sc, i in pos.items():
#                 qinfo = qmt_mkt.get(sc)
#                 if qinfo:
#                     qvol, qmv = qinfo
#                     if qvol > 0:
#                         pv += i['volume'] * (qmv / qvol)
#                 else:
#                     # 兜底：QMT无此股（罕见），尝试xtdata
#                     try:
#                         tks = _safe_get_tick([sc])
#                         pv += i['volume'] * (tks.get(sc, {}).get('lastPrice', 0) if tks else 0)
#                     except Exception:
#                         pass
#         eq = cash + pv
#         te += eq
#         pnl = ((eq - cap) / cap * 100) if cap > 0 else 0
#         status = '\u25b6\ufe0f' if c.get('enabled', True) else '\u23f8\ufe0f'
#         print(
#             f"{status}-> {sn}:\n  本金:{cap:,.2f}(剩余:{eq:,.2f}) | 闲置:{cash:,.2f} | 持仓:{pv:,.2f} | 盈亏:{eq - cap :,.2f}({pnl:+.2f}%)")
#         if pos:
#             pos_str = ' | '.join(f"{sc}({info['volume']}股)" for sc, info in pos.items())
#             print(f"  持仓: {pos_str}")
#         else:
#             print(f"  持仓: (空仓)")
#     print(f"  总计:{len(STRATEGY_INITIAL_CAPITAL)}个策略 | 总配资:{tc:,.2f} | 现市值:{te:,.2f} | 持仓参考盈亏:{te - tc:+,.2f}")
#     try:
#         a = _safe_qmt_query(xt_trader.query_stock_asset, _account)
#         if a:
#             at = getattr(a, 'total_asset', 0)
#             total_pnl = at - ACCOUNT_INITIAL_CAPITAL
#             total_pnl_pct = (total_pnl / ACCOUNT_INITIAL_CAPITAL * 100) if ACCOUNT_INITIAL_CAPITAL > 0 else 0
#             print(
#                 f"  实盘总资产:{at:,.2f} | 账户初始入金:{ACCOUNT_INITIAL_CAPITAL:,.2f} | 总盈亏:{total_pnl:+,.2f}({total_pnl_pct:+.2f}%)")
#     except Exception:
#         pass
#     print(f"{'=' * 75}\n")


# class Receiver:
#     def start(self):
#         print(f"\n{'=' * 75}\n🚀 recv6.5.1 启动 (F1/F2/F3致命问题修复版)\n{'=' * 75}")
#         global _wework_thread
#         if WEWORK_DEBUG_ENABLED:
#             _wework_thread = threading.Thread(target=_wework_worker, daemon=True, name="wework")
#             _wework_thread.start()
#         if not init_qmt():
#             return print("❌ QMT初始化失败")
#         _warmup_gateway()
#         init_strategy_funds()
#         with db._connect() as c:
#             cnt = c.execute("SELECT COUNT(*) FROM trade_records").fetchone()[0]
#         first = (cnt == 0)
#         if first:
#             print("🆕 首次运行，跳过对账")
#         else:
#             reconcile_on_startup()
#             reconstruct_positions_from_trade_records()

#         # ═══════════════════════════════════════════════════
#         # v6.5.1 F2修复: 强制同步QMT历史成交，防止程序重启后持仓/资金不一致
#         n_sync = reconcile_trades_from_qmt()
#         if n_sync > 0:
#             print(f"  ✅ 同步QMT历史成交: {n_sync}条")
#             # 重新重建持仓和资金，确保与QMT完全一致
#             reconstruct_positions_from_trade_records()
#         # ═══════════════════════════════════════════════════

#         if os.environ.get("AUTO_SKIP_MANUAL", "").strip() != "1":
#             manual_position_attribution()
#         _cross_validate_strategies()

#         # v6.5: 启动部分成交卖出重试后台线程
#         _start_partial_sell_retry_thread()

#         for sn in STRATEGY_INITIAL_CAPITAL:
#             strategy_queues[sn] = Queue(maxsize=1000)
#             w = StrategyWorker(sn)
#             strategy_workers[sn] = w
#             w.start()
#         time.sleep(0.3)
#         _print_startup_summary()

#         threading.Thread(target=cancel_watcher, daemon=True, name="cancel-watcher").start()
#         threading.Thread(target=_qmt_health_checker, daemon=True, name="qmt-health").start()
#         threading.Thread(target=_cleanup_watcher, daemon=True, name="cleanup").start()

#         try:
#             _redis_listener()
#         except KeyboardInterrupt:
#             pass
#         finally:
#             self.stop()

#     def stop(self):
#         print("\n🛑 停止...")
#         shutdown_flag.set()
#         # v6.5: 停止部分成交重试线程
#         try:
#             _partial_sell_retry_queue.put_nowait(None)
#         except Full:
#             pass
#         if _wework_thread and _wework_thread.is_alive():
#             try:
#                 _wework_queue.put_nowait(None)
#             except Full:
#                 pass
#         for q in strategy_queues.values():
#             q.put(None)
#         for w in strategy_workers.values():
#             w.join(timeout=5)
#         print("⏳ 等待QMT网关完成剩余订单...")
#         _gw_shutdown_timeout(30)
#         if xt_trader:
#             try:
#                 xt_trader.stop()
#             except Exception:
#                 pass
#         print("🏁 已退出")


# def main():
#     Receiver().start()


# if __name__ == "__main__":
#     main()



# 感谢你的克隆! 🐷🐷🐷🐷🐷🐷🐷🐷🐷🐷🐷🐷🐷🐷🐷🐷🐷🐷🐷🐷🐷🐷🐷🐷🐷🐷🐷🐷🐷🐷🐷🐷🐷🐷🐷🐷🐷🐷🐷🐷🐷🐷🐷🐷🐷
# 有策略相关开发经验的朋友，欢迎加入QQ群： 1107114272  一起研究策略，共同学习进步，申请时请务必备注聚宽ID哦
