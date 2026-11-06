# Clone from JoinQuant
# postId: 1cecd2d35a74374296c51c900a616c67
# backtestId: 108424f336f33795ebcd4b9a11f214a7
# title: 量化学习-KD指标量化交易策略 

'''
超买超卖型技术指标，即随机指标KD
实现K在20左右向上交叉D时，则全仓买入
K在80左右向下交叉D时，全仓卖出
'''

import jqdata
from jqlib.technical_analysis import *

def initialize(context):
    """初始化函数"""
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
    g.security = '000001.XSHE'
    

def market_open(context):
    """开盘时运行函数"""
    # 输出运行时间 
    log.info('market_open运行时间：'+str(context.current_dt.time()))
    security = g.security
    # 调用KD函数，获取该函数的K值和D值
    K1, D1 = KD(security, check_date=context.current_dt, N=9, M1=3, M2=3)
    # 取得当前的现金
    cash = context.portfolio.available_cash
    # 如果K在20左右向上交叉D时，则全仓买入
    if K1 >= 20 and K1 > D1:
        # 记录这次买入
        log.info('买入股票 %s' % (security))
        # 用所有cash买入股票
        order_value(security, cash)
    # 如果K在80左右向下交叉D，并且目前有头寸，则全仓卖出
    elif K1 < 80 and K1 < D1 and context.portfolio.positions[security].closeable_amount > 0:
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
    