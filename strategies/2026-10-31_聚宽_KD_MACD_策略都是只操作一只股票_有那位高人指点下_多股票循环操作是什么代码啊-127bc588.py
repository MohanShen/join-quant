# Clone from JoinQuant
# postId: 127bc5881e992bbd75540b07c8560a70
# backtestId: bc1af19f6c3cc1f2ed11d91499352b1a
# title: 聚宽 KD MACD  策略都是只操作一只股票，有那位高人指点下，多股票循环操作是什么代码啊？

# 克隆自聚宽文章：https://www.joinquant.com/post/15078
# 标题：KD指标量化交易策略
# 作者：mxh

#https://www.joinquant.com/post/15018?tag=algorithm
'''
超买超卖型技术指标，即随机指标KD
金叉向上交叉D时，则全仓买入
死叉向下交叉D时，全仓卖出
'''

import jqdata
from jqlib.technical_analysis import *

def initialize(context):
    g.stocks = ['300015.XSHE','000002.XSHE','000004.XSHE','601318.XSHG']  
    set_universe(g.stocks)
    """初始化函数"""
    set_slippage(FixedSlippage(0.02))
    # 设定基准
    set_benchmark('000300.XSHG')
    # 开启动态复权
    set_option('use_real_price', True)
    # 股票类每笔交易时的手续费是：
    # 买入时佣金万分之三
    # 卖出时佣金万分之三加千分之一的印税
    # 每笔交易最低扣5元钱
    set_order_cost(OrderCost(
        open_tax=0, 
        close_tax=0.001, 
        open_commission=0.0003, 
        close_commission=0.0003, 
        close_today_commission=0, 
        min_commission=5
        ), type='stock')
    # 开盘前运行
    run_daily(before_market_open, time='before_open', reference_security='000300.XSHG')
    # 开盘时运行
    run_daily(market_open, time='open', reference_security='000300.XSHG')
    # 收盘后运行
    run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')
    
    
def before_market_open(context):
    """开盘前运行函数"""
    # 输出运行时间 
    log.info('before_market_open运行时间：'+str(context.current_dt.time()))
    # 给微信发送消息
    send_message('美好的一天，祝佻交易顺利')
    # 保存要损伤的股票
    g.security = '300015.XSHE'
    

def market_open(context):
    """开盘时运行函数"""
    # 输出运行时间 
    log.info('market_open运行时间：'+str(context.current_dt.time()))
    log.info('previous_dae',context.previous_date)
    # def handle_data(context, data):
    # 循环每只股票
    for security in g.stocks:
    # 调用KD函数，获取该函数的K值和D值
         K1, D1 = KD(security, check_date=context.current_dt, N=9, M1=3, M2=3)
         K2, D2 = KD(security, check_date=context.previous_date-datetime.timedelta(days=1),N=9,M1=3,M2=3)
    # 取得当前的现金
    cash = context.portfolio.available_cash
    # 形成金叉，则全仓买入
    if  K1>D1 and K2 <=D2:
        # 记录这次买入
        log.info('买入股票 %s' % (security))
        # 用所有cash买入股票
        order_value(security, cash)
    # 形成死叉，并且目前有头寸,有可卖出股票，则全仓卖出
    elif  K1<=D1 and K2 >D2  and context.portfolio.positions[security].closeable_amount > 0:
        # 记录这次卖出
        log.info('卖出股票 %s' % (security))
        # 卖出所有股票，使这只股票的最终持有量为0
        order_target(security, 0)
        
def after_market_close(context):
    """收盘后运行函数"""
    # 输出运行时间 
    log.info('after_market_close运行时间：'+str(context.current_dt.time()))
    # 得到当天的所有成效记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    log.info('一天的交易结束，祝你心情愉快')
    