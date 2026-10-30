# Clone from JoinQuant
# postId: cb3edbf2888adcc6393d4c2796533ffc
# backtestId: 69350f802d70bfad3d1332762007d695
# title: 求教！求问大神们哪里有错误？

##策略说明：
#本策略是基于商品期货的跨品种交易策略。
#跨品种套利是指利用两种不同、但相互关联的资产间的价格差异进行套利交易。
#跨品种套利的逻辑在于寻找不同品种但具有一定相关性的商品。
#当价差从偏离区域回到正常区间过程中有对冲套利的可能。
#品种选择的要求有:两个品种的价格走势相关性高;基本面上两者有一定的逻辑联系。
#本策略选取的两种期货：小麦、玉米。

# 导入函数库
import jqdata
import os

## 初始化函数，设定基准等等
def initialize(context):
    # 设定玉米油期货作为基准标的
    set_benchmark('C9999.XDCE')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)

    ### 期货相关设定 ###
    # 设定账户为金融账户
    set_subportfolios([SubPortfolioConfig(cash=context.portfolio.starting_cash, type='index_futures')])
    # 期货类每笔交易时的手续费是：买入时万分之0.23,卖出时万分之0.23,平今仓为万分之23
    set_order_cost(OrderCost(open_commission=0.000023, close_commission=0.000023,close_today_commission=0.0023), type='index_futures')
    # 设定保证金比例
    set_option('futures_margin_rate', 0.15)
    log.set_level('order', 'error')
    
    run_daily(market_open, time='open', reference_security = 'C9999.XDCE')

## 开盘前运行函数
def market_open(context):
    #取数据的长度为20天
    g.span = 20
    #取两只商品期货，分别是小麦期货、玉米期货
    stock_list = ['WH9999.XZCE','C9999.XDCE']
    #获取数据
    hist = history(g.span, '1d', 'close', stock_list)
    XM = hist[stock_list[0]]
    YM = hist[stock_list[1]]
    
    #看一下价格走势的吻合程度，发现涨跌规律一致。
    #也能发现这两种期货之间的价格较为固定。
    #XM期货价格>YM期货价格。
    record(XM = XM[-1])
    record(YM = YM[-1])

    #计算价格比值
    bz = XM/YM
    current_bz = bz[-1]
    
    future_xm = get_dominant_future('XM')
    future_ym = get_dominant_future('YM')
    
     #如果最近该指数在上涨，那么认为相对于YM，XM被高估
    #所以策略是long YM，short XM
    if (current_bz > 1.35):
        order(future_ym, 0.3*context.portfolio.available_cash/(0.15*10*YM[-1]), side = 'long', pindex = 0)
        order(future_xm, 0.3*context.portfolio.available_cash/(0.15*10*XM[-1]), side = 'short', pindex = 0)

    #如果最近该指数在下降，那么认为相对于YM，XM被低估
    #所以策略是long XM，short YM
    elif (current_bz < 1.20):
        order(future_ym, 0.3*context.portfolio.available_cash/(0.15*10*YM[-1]), side = 'short', pindex = 0)
        order(future_xm, 0.3*context.portfolio.available_cash/(0.15*10*XM[-1]), side = 'long', pindex = 0)
    
    #如果该指数比较平稳，那么平仓，赚取之前策略的收益
    elif (current_bz < 1.32 and current_bz > 1.23):
        order_target(future_ym, 0, side = 'long', pindex = 0)
        order_target(future_xm, 0, side = 'short', pindex = 0)
        order_target(future_ym, 0, side = 'short', pindex = 0)
        order_target(future_xm, 0, side = 'long', pindex = 0)