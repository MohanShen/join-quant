# Clone from JoinQuant
# postId: cb1d31c2f68bee81e421b072028ef9ee
# backtestId: a003a8f043d050efc37a811332f284d2
# title: 请教如何判断期货账户持仓？

import jqdata
def initialize(context):
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    #set_option('use_real_price', True)
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')
    # 输出内容到日志 log.info()
    ### 期货相关设定 ###
    set_subportfolios([SubPortfolioConfig(cash=context.portfolio.starting_cash, type='index_futures')])
    # 期货类每笔交易时的手续费是：买入时万分之0.23,卖出时万分之0.23,平今仓为万分之23
    set_order_cost(OrderCost(open_commission=0.000023, close_commission=0.000023,close_today_commission=0.0023), type='index_futures')
    # 设定保证金比例
    set_option('futures_margin_rate', 0.15)
def handle_data(context, data):
    main_contact=get_dominant_future('RB')
    order_target(main_contact, amount=1,style=None,side='short', pindex=0)
    #order_target(main_contact, 1 , side='short', pindex=1)
    a=context.portfolio.positions
    print(a)