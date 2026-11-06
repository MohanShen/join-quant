# Clone from JoinQuant
# postId: c1966f8ec979c7d62f8112f831a114bb
# backtestId: a8e6a5b1061eee271678a2ab8ef0a63a
# title: 【开源分享】年化590% ETF溢价套利策略，2年64倍

# 克隆自聚宽文章：https://www.joinquant.com/post/51024
# 标题：社区策略汇总分类
# 作者：策略评价官

# 克隆自聚宽文章：https://www.joinquant.com/post/48975
# 标题：推荐一个根据ETF溢价的交易策略
# 作者：ljf1888


# 导入函数库
from jqdata import *

# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启异步报单
    set_option('async_order', True)
     # 打开防未来函数
    set_option("avoid_future_data", True)
    # 将滑点设置为0
    set_slippage(FixedSlippage(0.002))
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    set_order_cost(OrderCost(close_tax=0.000, open_commission=0.00025, close_commission=0.00025, min_commission=5), type='fund')
    #run_daily(before_market_open, '09:20', reference_security='000300.XSHG')
    run_daily(before_market_open, '09:02', reference_security='000300.XSHG')
    #run_daily(weekly_adjustment0,'9:06')
    run_daily(market_open, '09:30', reference_security='000300.XSHG')
    run_daily(after_market_close, '15:00', reference_security='000300.XSHG')

def before_market_open(context):
    # 获取基金
    fund_list = get_all_securities(['etf'], context.previous_date).index.tolist()
    # 成交额过滤
    df = history(count=1, unit='1d', field="volume", security_list=fund_list).T
    df.columns=['volume']
    df = df[df.volume > 2e6]
    # 获取净值
    df = get_extras('unit_net_value',df.index.tolist(),end_date=context.previous_date, df=True, count=1).T
    df.columns=['unit_net_value']
    g.fund_list = df


    
def market_open(context):
    df = g.fund_list
    current = get_current_data()
    ## 获得基金最新价
    df['last_price'] = [current[c].last_price for c in df.index.tolist()]
    ## 计算溢价
    df['premium'] = (df.last_price / df.unit_net_value - 1) * 100
    ## 根据溢价大小排序
    df = df.sort_values(['premium'], ascending = True)
    df = df[(df.premium < 0)]
    order_fund = df[:5].index.tolist()
    g.max_position = len(order_fund)
    log.info(order_fund)
    # 卖出
    for fund in context.portfolio.positions.keys():
        # 卖出不在股票池或节假日前清仓
        if fund not in order_fund:
        #if fund not in order_fund :
            order_target_value(fund, 0)
    for fund in order_fund:
        now_position = g.max_position - len(context.portfolio.positions)
        if now_position == 0:
            continue
        if fund not in context.portfolio.positions.keys():
            position = context.portfolio.available_cash / now_position
            order_target_value(fund, position)


## 收盘后运行函数
def after_market_close(context):
    pass