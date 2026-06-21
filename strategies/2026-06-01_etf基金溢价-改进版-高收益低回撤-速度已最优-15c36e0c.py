# Clone from JoinQuant
# postId: 15c36e0ce892a62b264d518d2aa5df31
# backtestId: 12ef917dcc3f9cd5a610d0efb64f1068
# title: etf基金溢价-改进版-高收益低回撤-速度已最优

# 导入函数库
from jqdata import *

# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启异步报单
    set_option('async_order', True)
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 是否未来函数
    set_option("avoid_future_data", True)
    # 过滤掉order系列API产生的比error级别低的log
    log.set_level('order', 'error')
    g.holiday = ['2010-02-12','2010-04-30','2010-09-30','2011-02-01','2011-04-29','2011-09-30','2012-01-20','2012-04-27','2012-09-28','2013-02-08','2013-04-26','2013-09-30','2014-01-30','2014-04-30','2014-09-30','2015-02-17','2015-04-30','2015-09-30','2016-02-05','2016-04-29','2016-09-30','2017-01-26','2017-04-28','2017-09-29','2018-02-14','2018-04-27','2018-09-28','2019-02-01','2019-04-30','2019-09-30','2020-01-23','2020-04-30','2020-09-30','2021-02-10','2021-04-30']
    set_order_cost(OrderCost(close_tax=0.000, open_commission=0.00025, close_commission=0.00025, min_commission=0), type='fund')
    run_daily(after_market_open, '09:20', reference_security='000300.XSHG')
    run_daily(market_open, '09:30', reference_security='000300.XSHG')

def after_market_open(context):
    # 获取基金
    fund_list = get_all_securities(['lof', 'etf'], context.previous_date).index.tolist()
    # 成交额过滤
    df = history(count=1, unit='1d', field="volume", security_list=fund_list).T
    df.columns=['volume']
    df = df[df.volume > 2e6]
    # 获取净值
    df = get_extras('unit_net_value', df.index.tolist(), end_date=context.previous_date, df=True, count=1).T
    df.columns=['unit_net_value']
    g.fund_list = df
    log.info('开盘前记录净值...')

def market_open(context):
    df = g.fund_list
    current = get_current_data()
    ## 获得基金最新价
    df['last_price'] = [current[c].last_price for c in df.index.tolist()]
    ## 计算溢价
    df['premium'] = (df.last_price / df.unit_net_value - 1) * 100
    ## 根据溢价大小排序
    if hasattr(df, 'sort'):
        df = df.sort(['premium'], ascending = True)
    else:
        df = df.sort_values(['premium'], ascending = True)
    
    df = df[(df.premium < 0)]

    order_fund = df[:5].index.tolist()
    g.max_position = len(order_fund)

    # 卖出
    for fund in context.portfolio.positions.keys():
        # 卖出不在股票池或节假日前清仓
        if fund not in order_fund or str(context.current_dt.date()) in g.holiday:
            order_target_value(fund, 0)

    # 买入, 节假日前不开仓
    if str(context.current_dt.date()) not in g.holiday:
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
