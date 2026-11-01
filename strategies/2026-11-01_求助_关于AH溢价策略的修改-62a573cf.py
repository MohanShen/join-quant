# Clone from JoinQuant
# postId: 62a573cfc1ad17491d330142893790dd
# backtestId: 435a13f989016c8ab63dc5ade713dceb
# title: 求助：关于AH溢价策略的修改

# 克隆自聚宽文章：https://www.joinquant.com/post/27312
# 标题：AH股比价策略
# 作者：周喆颋

'''
每隔refresh_rate天进行一次调仓，选择AH股比价最低的N只股票买进
'''
from jqdata import finance
#import jqdata
#from jqdata import *

## 初始化函数，设定要操作的股票、基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # True为开启动态复权模式，使用真实价格交易
    set_option('use_real_price', True) 
    # 设定成交量比例
    set_option('order_volume_ratio', 1)
    # 股票类交易手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, \
                             open_commission=0.0003, close_commission=0.0003,\
                             close_today_commission=0, min_commission=5), type='stock')
    # 持仓数量
    g.stocknum = 4 
    # 交易日计时器
    g.days = 0 
    # 调仓频率
    g.refresh_rate = 1
    # 运行函数
#    run_daily(trade, 'every_bar')
    run_monthly(trade, monthday=-1, time='14:45')
#    run_weekly(trade, weekday=-1, time='14:45')
## 选出AH比价最低的股票
def check_stocks(context):
    # 设定查询条件
    df = finance.run_query(query(finance.STK_AH_PRICE_COMP.a_code, \
                finance.STK_AH_PRICE_COMP.h_a_comp).\
                filter(finance.STK_AH_PRICE_COMP.day==context.current_dt.date()).\
                order_by(finance.STK_AH_PRICE_COMP.h_a_comp).\
                limit(6))

    buylist =list(df['a_code'])
    print (df)
    # 过滤停牌股票
    buylist = filter_paused_stock(buylist)
    buylist = filter_is_st(buylist)
    buylist = filter_qd(buylist)

    return buylist[:g.stocknum]
  
## 交易函数
def trade(context):
    if g.days%g.refresh_rate == 0:

        ## 获取持仓列表
        sell_list = list(context.portfolio.positions.keys())
        # 如果有持仓，则卖出
        if len(sell_list) > 0 :
            for stock in sell_list:
                order_target_value(stock, 0)

        ## 分配资金
        if len(context.portfolio.positions) < g.stocknum :
            Num = g.stocknum - len(context.portfolio.positions)
            Cash = context.portfolio.cash/Num
        else: 
            Cash = 0

        ## 选股
        stock_list = check_stocks(context)
        print(stock_list)

        ## 买入股票
        for stock in stock_list:
            if len(context.portfolio.positions.keys()) < g.stocknum:
                order_value(stock, Cash)

        # 天计数加一
        g.days = 1
    else:
        g.days += 1

# 过滤停牌股票
def filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]

def filter_is_st(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].is_st]

def filter_qd(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not ('青岛银行' in current_data[stock].name)]



#def filter_specials(context, n=60):
    # type: (Context, int) -> list
    """
    过滤掉：1）三停：涨停、跌停、停牌；2）三特：st, *st, 退；3）科创、创业; 4）次新；
    适用于开盘前选股，如果是盘中，用curr_data[security].last_price替代curr_data[stock].day_open
    :param n: 获取n个交易日之前上市的股票
    """
    #     获取交易日
#    trd_days = get_trade_days(end_date='3019-10-10', count=n)
    #     获取n个交易日之前前上市股票【即过滤掉次新股】
#    stock_list = get_all_securities('stock', trd_days[0]).index.tolist()
    #
#    curr_data = get_current_data()
#    stock_list = [stock for stock in stock_list if not (
#            (curr_data[stock].day_open == curr_data[stock].high_limit) or   # 涨停开盘
#            (curr_data[stock].day_open == curr_data[stock].low_limit) or    # 跌停开盘
#            curr_data[stock].paused or  # 停牌
#            curr_data[stock].is_st or   # ST
#            ('ST' in curr_data[stock].name) or
#            ('*' in curr_data[stock].name) or
#            ('退' in curr_data[stock].name) or
#            ('青岛' in curr_data[stock].name)
#            (stock.startswith('300')) or    # 创业
#            (stock.startswith('688'))   # 科创
#    )]
    #
    return stock_list