# Clone from JoinQuant
# postId: def077698a85c2db33b2044033c97f4c
# backtestId: 6a34a270f7716b90a142fe9032a3efce
# title: 请问策略回测时间巨长是怎么回事？

# 导入函数库
import jqdata
from jqlib.technical_analysis import *


# 初始化函数，设定基准等等
def initialize(context):
    run_daily(period,time='every_bar')
    set_benchmark('000300.XSHG')   # 设定沪深300作为基准
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')

    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    set_slippage(PriceRelatedSlippage(0.00246), type='stock')   # 跳数滑点设置为期货专用，此处设定系统默认滑点
    g.security = get_index_stocks('000300.XSHG')    # 设定沪深300成分股为股票池
    g.stocksnum = 10   # 设定要交易的股票数量
    g.period = 22    # 设定调仓周期
    g.days = 0    # 记录策略运行天数




def period(context):
    security = g.security
    hs_security = HSL(security, check_date = context.current_dt, N=22)[1]
    value_hs_security = sorted(hs_security.values())
    Hs_security = sorted(hs_security.items(), key = lambda d: d[1], reverse=False)
    stock_list = []
    for i in Hs_security[:9]:
        stock_list.append(i[0])
    if g.days % g.period == 0:
        stocknum = len(stock_list)
        for stock in context.portfolio.positions:
            if stock not in stock_list:
                order_target_value(stock, 0)
            else:
                stock_list.remove(stock)
                stocknum = len(stock_list) - 1
        cash = context.portfolio.available_cash / stocknum
        for stock in stock_list:
            order_value(stock, cash)
    g.days += 1
        







    
   





