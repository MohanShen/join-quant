# Clone from JoinQuant
# postId: a7bb87c84bb9f8d96954ae6d99f834be
# backtestId: 13ea939830f365cc00325c785414a261
# title: 请问为什么这个沪深300等权策略收益几乎是 -100%？

# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')
    
    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0, open_commission=0, close_commission=0, min_commission=0), type='stock')
      # 开盘时运行
    run_daily(market_open, time='every_bar', reference_security='000300.XSHG')
    
    # g.status = 0
    
## 开盘时运行函数
def market_open(context):
    security = get_index_stocks('000300.XSHG')
    log.info(security)
    # move_in = list(set(security).difference(set(context.portfolio.positions.keys())))
    # if len(move_in) != 0:
    #     move_out = list(set(context.portfolio.positions.keys()).difference(set(security)))
        
    #     for stock in move_out:
    #         order_target(stock, 0)
    #     # if g.status == 0:
        
    #     current_data = get_current_data()
    #     for i in range(len(move_in)-1, -1, -1):
    #         if current_data[move_in[i]].paused:
    #             move_in.pop(i)
    #     num_stock_left = len(move_in)
    #     for stock in move_in:
    #         cash = context.portfolio.available_cash
    #         log.info(cash, stock)
    #         order_value(stock, cash/num_stock_left)
    #         num_stock_left -= 1
        # g.status = 1
    
    current_data = get_current_data()
    for i in range(len(security)-1, -1, -1):
        # if context.current_dt.date() - get_security_info(stock_list[i]).start_date < dt.timedelta(90) or current_data[stock_list[i]].paused:
        if current_data[security[i]].paused:
            security.pop(i)
    
    for stock in context.portfolio.positions:
        order_target(stock, 0)
        log.info("Selling %s" % (stock))

        
    # elif g.day%(5*240) == 1:
    
    cash = context.portfolio.available_cash
    amount_stock_left = len(security)
    for stock in security:
        order_value(stock, cash/amount_stock_left)
        cash = context.portfolio.available_cash
        amount_stock_left -= 1