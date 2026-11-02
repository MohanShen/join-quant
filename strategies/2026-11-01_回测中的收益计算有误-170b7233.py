# Clone from JoinQuant
# postId: 170b723320b48f7576ffc171b2d26da9
# backtestId: f9261178ea7fd7a3b5f13f0d246be8e0
# title: 回测中的收益计算有误

# 导入函数库
from jqdata import *

g_test_symbol = '600519.XSHG'

# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark(g_test_symbol)
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')

    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')

    
    show_bonus_info(context)
    run_daily(market_open, time='open', reference_security='000300.XSHG')


## 开盘时运行函数
def market_open(context):
    security = g_test_symbol
    if security not in [position.security for position in list(context.portfolio.positions.values())]:
        order_target_value(security, context.portfolio.total_value)

    if get_current_data()[security].paused:
        log.info('%s 今日停牌' % security)

def show_bonus_info(context):
    stmt = query(finance.STK_XR_XD).filter(finance.STK_XR_XD.code == g_test_symbol
        ).filter(finance.STK_XR_XD.distributed_share_base_board != None).order_by(finance.STK_XR_XD.report_date)
    
    rslt = get_fundamentals(stmt)
    log.info(rslt[['a_registration_date', 'implementation_bonusnote']])
    #log.info(rslt[['company_name', 'a_registration_date', 'implementation_bonusnote', 'dividend_ratio', 'transfer_ratio', 'bonus_ratio_rmb']].values.tolist())

