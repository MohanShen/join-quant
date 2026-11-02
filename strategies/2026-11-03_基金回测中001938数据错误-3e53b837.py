# Clone from JoinQuant
# postId: 3e53b837889a775d7886abc0d9e54903
# backtestId: 226d0be1c53bd96570b68a0dd3a7ffa9
# title: 基金回测中001938数据错误

# 导入函数库
from jqdata import *

# 初始化函数，设定基准等等
def initialize(context):
    # 设定基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    #set_option("use_real_price", True) # 对场外基金回测来说，现金分红
    set_option("use_real_price", False) # 对场外基金回测来说，分红再投资
    ### 场外基金相关设定 ###
    # 设置账户类型: 场外基金账户
    set_subportfolios([SubPortfolioConfig(context.portfolio.cash, 'open_fund')])
    # 设置赎回到账日
    set_redeem_latency(2, 'open_fund')
    set_redeem_latency(2, 'stock_fund')
    set_redeem_latency(2, 'mixture_fund')
    set_redeem_latency(2, 'QDII_fund')
    
    set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.001, close_commission=0.002, close_today_commission=0, min_commission=0), type='open_fund')

    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
        # 开盘时运行
    run_daily(market_open, time='open', reference_security='000300.XSHG')
    
        # 收盘后运行
#    run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')

def market_open(context):
    s1='001938.OF'
     
    
    today = context.current_dt
    Today = today.strftime('%Y-%m-%d')
    
    if Today == "2020-11-03":
        c=context.portfolio.cash
        purchase(s1,c)
    
    
