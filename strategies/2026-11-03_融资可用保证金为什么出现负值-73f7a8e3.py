# Clone from JoinQuant
# postId: 73f7a8e39236eea6594839d7b5c66579
# backtestId: 931dbfd89195f7a40766834219887608
# title: 融资可用保证金为什么出现负值？

#EARL二八-仓位管理-杠杆-190417      1、优化20150526杠杆资金用完出错停止了后面的交易，收益停留在1120%。限制为4倍杠杆。
#                                   2、增加回撤5%止盈。
#EARL二八-仓位管理-融资-190420      在《EARL二八-仓位管理-杠杆-190417》基础上，改为融资融券策略
#EARL二八-仓位管理-融资-190609      total value改为net value
#EARL二八-仓位管理-融资-190609A     改为1、首仓回撤5%止盈；
#                                       2、二八转换买入时间改为'14:30:10'修正转换买卖的涨幅差异。
#                                       3、14:29的加减仓改为14:31执行
#EARL二八-仓位管理-融资-190609B     《EARL二八-仓位管理-融资-190609A》第二次以上的加仓不足翻倍，改为加仓后持仓翻倍。
#EARL二八-仓位管理-融资-190610      修正将加仓价值当作加仓数量的错误
#                                   
# 导入函数库
import jqdata
# import time

# 初始化函数，设定基准等等
def initialize(context):
    # 设定收益比较基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    ### 融资融券相关设定 ###
    # 设置账户类型: 融资融券账户
    set_subportfolios([SubPortfolioConfig(cash=context.portfolio.cash, type='stock_margin')])
    ## 融资相关设定
    # 设定融资利率: 年化8%, 默认8%
    set_option('margincash_interest_rate', 0.08)
    # 设置融资保证金比率: 150%, 默认100%
    set_option('margincash_margin_rate', 0.2)
    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.000, open_commission=0.0003, close_commission=0.0003, min_commission=0), type='fund')
    # 取得当前的总现金
    # init_cash = context.portfolio.available_cash
    # # 设定subportfolios[0]为 操作仓，初始资金为 2%总资金
    # # 设定subportfolios[1]为 备用资金，初始资金为 98%总资金
    # set_subportfolios([SubPortfolioConfig(cash=init_cash*1.00, type='stock'),\
    #                   SubPortfolioConfig(cash=init_cash*0, type='stock'),\
    #                   ])
    #全局变量
    # g.starting_cash = context.portfolio.subportfolios[0].inout_cash * 0.02    # 操作仓初始资金，即杠杆本金
    g.rate_HS300 = 0    #标的四周涨跌幅度
    g.rate_ZX300 = 0
    # g.total_in_cash = 0     #累计入金量
    # g.clean_lever = 0       #清除杠杆标志
    g.change_cash = 0       #28转换资金量
    g.change_28 = 0         #28转换标志
    # g.highest_positions_value = 0       #记录持仓新高
    g.highest_net_value = 0       #记录市值新高
    g.start_value = 0       #记录每次开仓或加仓初始市值
    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
    # run_daily(clean_lever, time='14:29', reference_security='000300.XSHG')      #归还杠杆资金
    run_weekly(market_open, weekday=-1, time='14:30', reference_security='000300.XSHG')     
    run_weekly(market_open, weekday=-1, time='14:30:10', reference_security='000300.XSHG')
    run_daily(add_reduce_position, time='10:00', reference_security='000300.XSHG')      #加减仓函数
    run_daily(add_reduce_position, time='11:00', reference_security='000300.XSHG')      #加减仓函数
    run_daily(add_reduce_position, time='13:30', reference_security='000300.XSHG')      #加减仓函数
    run_daily(add_reduce_position, time='14:31', reference_security='000300.XSHG')      #加减仓函数
    # run_daily(market_open, time='14:55', reference_security='000300.XSHG')
    # run_daily(market_open, time='14:56', reference_security='000300.XSHG')
    #收盘后运行
    run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')

    
# ## 开盘前运行函数     
# def before_market_open(context):
#     # 输出运行时间
#     #log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))
#     # 给微信发送消息（添加模拟交易，并绑定微信生效）
#     send_message('美好的一天~')
## 盘中运行函数
def market_open(context):

    # 获取4周前和本周收盘价
    close_data_HS300 = get_bars('000300.XSHG', 5, unit='1w',fields=['close'],include_now=True)
    close_before_4W_HS300 = close_data_HS300['close'][-5]
    close_current_HS300 = close_data_HS300['close'][-1]
    rate_HS300 = (close_current_HS300 - close_before_4W_HS300) / close_before_4W_HS300
    g.rate_HS300 = rate_HS300
    # log.error("close_before_4W=%s,close_current=%s,%s" % (close_before_4W_HS300,close_current_HS300,rate_HS300))
    
    close_data_ZX300 = get_bars('399905.XSHE', 5, unit='1w',fields=['close'],include_now=True)
    close_before_4W_ZX300 = close_data_ZX300['close'][-5]
    close_current_ZX300 = close_data_ZX300['close'][-1]
    rate_ZX300 = (close_current_ZX300 - close_before_4W_ZX300) / close_before_4W_ZX300
    g.rate_ZX300 = rate_ZX300
    # log.error("close_before_4W=%s,close_current=%s,%s" % (close_before_4W_ZX300,close_current_ZX300,rate_ZX300))
    # record(close_current_HS300=close_current_HS300)
    # record(close_current_ZX300=close_current_ZX300)
   
    # current_stock = ['NULL']

    #如果有持仓，且需要转换，则卖出
    if context.portfolio.subportfolios[0].positions_value > 0:
        current_stock = context.portfolio.positions.keys()
        # g.current_stock = current_stock
        #log.error("current_stock=" , current_stock)
        if rate_HS300 < 0 and rate_ZX300 < 0:
            if current_stock[0] != '000012.XSHG':
                # g.starting_cash = context.portfolio.subportfolios[0].positions_value - g.total_in_cash       #更新本金
                order_target(current_stock[0], 0)
                g.start_value = context.portfolio.subportfolios[0].net_value           
                print "g.start_value=%s" % g.start_value       
                g.change_cash = 0                
                print "g.change_cash=%s" % g.change_cash
                g.highest_net_value =  context.portfolio.subportfolios[0].net_value 
                print "g.highest_net_value=%s" % g.highest_net_value
                # margincash_close(current_stock[0], 100000000000000)
                # order_value('511660.XSHG', cash)
                #print "IF1卖出%s" % current_stock[0]
                # g.highest_positions_value = 0   #记录持仓新高
                # g.clean_lever = 1       #置位清除杠杆标志
                # clean_lever(context)    #归还杠杆资金
            return
        if rate_HS300 > rate_ZX300:
            if current_stock[0] != '000300.XSHG':
                g.change_cash = context.portfolio.subportfolios[0].positions_value
                g.change_28 = 1     #置位28转换标志
                order_target(current_stock[0], 0)               
                # margincash_close(current_stock[0], 100000000000000)
                # order_value('000300.XSHG', cash)
                #print "IF2卖出%s" % current_stock[0]
            return
        if rate_HS300 < rate_ZX300:
            if current_stock[0] != '399905.XSHE':
                g.change_cash = context.portfolio.subportfolios[0].positions_value
                g.change_28 = 1     #置位28转换标志
                order_target(current_stock[0], 0)               
                # margincash_close(current_stock[0], 100000000000000)
                # order_value('159902.XSHE', cash)
                #print "IF3卖出%s" % current_stock[0]
            return

    #如果空仓，则买入四周涨幅较大且为正的标的
    if context.portfolio.subportfolios[0].positions_value == 0:
        # if g.change_28 == 0:
        #     cash = g.starting_cash          #非28转换，开仓资金为本金
        # if g.change_28 == 1:
        #     cash = g.change_cash             # 28转换资金量
        #     g.change_28 = 0     #复位28转换标志
        cash = context.portfolio.subportfolios[0].available_cash
        margin_cash = g.change_cash - cash
        current_data = get_current_data()        
        # current_stock = context.portfolio.positions.keys()    
        print "cash=%s" % cash
        print "margin_cash=%s" % margin_cash
        if rate_HS300 < 0 and rate_ZX300 < 0:
            # order_value('000012.XSHG', cash)
            # print "空仓"
            return
        if rate_HS300 > rate_ZX300:
            if g.change_28 == 1:       
                price = current_data['000300.XSHG'].last_price
                margin_count = margin_cash / price
                print "price=%s" % price
                print "margin_count=%s" % margin_count                
                margincash_open('000300.XSHG', margin_count)
            order_value('000300.XSHG', cash)
            print "买入510300"
            # return
        if rate_HS300 < rate_ZX300:
            if g.change_28 == 1:
                price = current_data['399905.XSHE'].last_price
                margin_count = margin_cash / price
                print "price=%s" % price
                print "margin_count=%s" % margin_count                
                margincash_open('399905.XSHE', margin_count)        
            order_value('399905.XSHE', cash)
            print "买入510500"
            # return
        if g.change_28 == 0:    #首仓记录市值
            g.highest_net_value =  context.portfolio.subportfolios[0].net_value 
            g.start_value = context.portfolio.subportfolios[0].net_value
            print "g.highest_net_value=%s" % g.highest_net_value
            print "g.start_value=%s" % g.start_value
        if g.change_28 == 1:
            g.change_28 = 0     #复位28转换标志           
            

#加减仓函数
def add_reduce_position(context):
    #判断持仓的累计收益，累计收益>=20%加仓(此时加仓后涨幅10%)；加仓后累计收益<=5%清仓(此时加仓后涨幅-5%)。
    if context.portfolio.subportfolios[0].positions_value > 0:
        # print "positions_value=%s" % context.portfolio.subportfolios[0].positions_value
        # print "g.starting_cash=%s" % g.starting_cash
        # print "g.total_in_cash=%s" % g.total_in_cash
        # print "g.highest_positions_value=%s" % g.highest_positions_value
        current_stock = context.portfolio.positions.keys()    
        net_value = context.portfolio.subportfolios[0].net_value
        print "net_value=%s" % net_value
        
        #减仓
        if context.portfolio.subportfolios[0].cash_liability >= 0:    #所有仓位回撤5%止盈
            #回撤大于5%，则清理加仓，
            if (net_value < 0.95 * g.highest_net_value):  
                print context.portfolio
                # g.starting_cash = context.portfolio.subportfolios[0].positions_value - g.total_in_cash       #更新本金
                margincash_close(current_stock[0], 100000000000000)     
                g.start_value = context.portfolio.subportfolios[0].net_value           
                print "g.start_value=%s" % g.start_value       
                net_value = context.portfolio.subportfolios[0].net_value
                print "net_value=%s" % net_value
                g.highest_net_value =  context.portfolio.subportfolios[0].net_value 
                print "g.highest_net_value=%s" % g.highest_net_value
                # order_target(current_stock[0], 0)           #清仓
                # g.highest_positions_value = 0   #记录持仓新高
                # g.clean_lever = 1       #置位清除杠杆标志
                # clean_lever(context)    #归还杠杆资金 
                    
        #加仓
        # zhangfu = 1.2       #底仓涨幅要求1.2
        # if context.portfolio.subportfolios[0].cash_liability > 0:    #已加过杠杆,涨幅要求1.1
        #     zhangfu = 1.1 
        if net_value >= 1.1 * g.start_value:   #满足涨幅要求则加仓
            # loss = (net_value - g.start_value )   #设定止损额=当次盈利的100%（相当于累计盈利的50%）
            # # print "loss=%s" % loss
            # loss_rate = 0.05     #止损比例5%
            # in_cash = loss/loss_rate - context.portfolio.subportfolios[0].positions_value   #需要加仓的资金量
            current_data = get_current_data()
            price = current_data[current_stock[0]].last_price
            # in_count = in_cash / price #context.portfolio.positions[current_stock[0]].price        #需要加仓的数量
            # print "loss=%s" % loss
            # print "in_cash=%s" % in_cash   
            # print "price=%s" % price  
            # print "in_count=%s" % in_count
            in_cash = context.portfolio.subportfolios[0].positions_value   #加仓的资金量，加一倍杠杆
            in_count = in_cash / price #context.portfolio.positions[current_stock[0]].price        #需要加仓的数量
            print context.portfolio
            # if cash >= 0:           #避开聚宽bug：available_cash会变成负数，
            margincash_open(current_stock[0], in_count)
            # g.highest_total_value =  context.portfolio.subportfolios[0].total_value
            g.start_value = context.portfolio.subportfolios[0].net_value            
            print "g.start_value=%s" % g.start_value
            # if g.rate_HS300 > g.rate_ZX300:
            #     margincash_open('000300.XSHG', in_count)
            #     print "加仓510300"
            #     # return
            # elif g.rate_HS300 < g.rate_ZX300:
            #     margincash_open('399905.XSHE', in_count)
            #     print "加仓510500"
                    # return
        #记录持仓新高
        if context.portfolio.subportfolios[0].net_value > g.highest_net_value:
            g.highest_net_value =  context.portfolio.subportfolios[0].net_value 
            print "g.highest_net_value=%s" % g.highest_net_value
            
# #归还杠杆资金函数               
# def clean_lever(context):
#     if g.clean_lever == 1:
#         # g.starting_cash = context.portfolio.subportfolios[0].positions_value - g.total_in_cash       #更新本金
#         # transfer_cash(from_pindex=0, to_pindex=1, cash=g.total_in_cash)     #归还杠杆资金
#         g.total_in_cash = 0     #清零累计入金量
#         g.clean_lever = 0       #复位清除杠杆标志
    
## 收盘后运行函数  
def after_market_close(context):
    #log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    # orders = get_orders()
    # for _order in orders.values():
    #     log.info('成交记录：'+str(_order))
    # #得到当天所有成交记录
    # trades = get_trades()
    # for _trade in trades.values():
    #     log.info('成交记录：'+str(_trade))
    print "g.start_value=%s" % g.start_value
    print "g.highest_net_value=%s" % g.highest_net_value
    log.info(context.portfolio)
    log.info('##############################################################')
