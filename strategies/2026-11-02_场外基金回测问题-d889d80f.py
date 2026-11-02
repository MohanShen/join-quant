# Clone from JoinQuant
# postId: d889d80fbf9ba3c6f37911c5bb3924bb
# backtestId: 9c3cd283869d5868a86528513f1055b9
# title: 场外基金回测问题

# 导入函数库
from jqdata import *

# 初始化函数，设定基准等等
def initialize(context):
    # 设定基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option("use_real_price", True)

    ### 场外基金相关设定 ###
    # 设置账户类型: 场外基金账户
    set_subportfolios([SubPortfolioConfig(context.portfolio.cash, 'open_fund')])
    # 设置赎回到账日
    set_redeem_latency(3, 'QDII_fund')

    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
        # 开盘时运行
    run_daily(market_open, time='open', reference_security='000300.XSHG')
        # 收盘后运行
#    run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')

def market_open(context):
    s1=['001387.OF', '002028.OF']
    s2=['110022.OF', '001740.OF']
    
    today = context.current_dt
    Today = today.strftime('%Y-%m-%d')
    
    if Today == "2017-05-02":
        c=context.portfolio.cash
        for i in range(len(s1)):
            purchase(s1[i], c/len(s1))
            
    
    if Today == "2017-05-24": 
        for s in context.portfolio.positions:
            n=context.portfolio.positions[s].closeable_amount
            redeem(s, n)
            
    if Today == "2017-06-02":        
        c=context.portfolio.cash
        for i in range(len(s2)):
            purchase(s2[i], c/len(s2))
            
            
