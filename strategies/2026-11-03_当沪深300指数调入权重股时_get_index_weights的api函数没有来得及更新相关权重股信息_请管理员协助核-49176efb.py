# Clone from JoinQuant
# postId: 49176efb32b9afd12a39fc2eb6f6d4ae
# backtestId: 7b987d16236e1bb162aec2eb499f4851
# title: 当沪深300指数调入权重股时，get_index_weights的api函数没有来得及更新相关权重股信息，请管理员协助核实

# 克隆自聚宽文章：https://www.joinquant.com/post/2915
# 标题：金融期货策略研究框架介绍及Demo演示
# 作者：JoinQuant-PM

#股指期货和ETF-期现套利-用基差的标准差1.2倍上下轨套利--tqV2

#移植了基差参考标准差的模型
#https://www.joinquant.com/algorithm/index/edit?algorithmId=c32a16233b1a7ffa8dceb1b202d7318a&startTime=2014-01-01&endTime=2019-01-10&baseCapital=5000000&frequency=day&pyVersion=2

#已经实现一揽子股票和股指期货对冲，动态的STD开仓和固定平仓


import datetime

def initialize(context):
    #利润回归模型
    g.ma =80    #80个30m，40小时，约10天
    g.up_std = 1.5
    g.down_std=1.2
    g.state = 0
    g.Totle_trading_Weight=0
    g.Open_JC=0         #开仓时的基差
    g.Is_Holding=False  #是否持仓
    
    g.int_cash = 11000000
    g.Stop_Win=    g.int_cash *0.005
    
    g.Open_totle_stock_value=0
    g.Open_totle_future_value=0

    g.security = '000300.XSHG'
    # 设定基准
    #g.trading_list=get_stock_list(context)
    
    set_benchmark(g.security)
    # 关闭订单提醒
    log.set_level('order', 'error')
    # 设定保证金比例
    set_option('futures_margin_rate', 0.15)
    # 设定手续费
    # # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, \
                    close_commission=0.0003, min_commission=5), type='stock')
    # 金融期货close_today_commission可不用设定，平今仓默认0.0023
    set_order_cost(OrderCost(open_commission=0.000023, close_commission=0.000023, \
                    close_today_commission=0.0023
                    ), type='index_futures')
    

    # 设定两个账户（账户0为股票仓位，账户1为股指期货仓位）
    set_subportfolios([SubPortfolioConfig(cash= g.int_cash ,type='stock'),\
                       SubPortfolioConfig(cash=1620000,type='index_futures')])
    # log.info(context.subportfolios)

    # 运行函数（reference_security为运行时间的参考标的）
    run_daily(set_slip_fee, time='before_open', reference_security='000300.XSHG')
    run_daily(before_trading, time='before_open', reference_security='000300.XSHG')
    run_daily(transfer_cash_test, time='open', reference_security='000300.XSHG')
    run_daily(trading, time='every_bar', reference_security='000300.XSHG')
    run_daily(after_trading, time='after_close', reference_security='000300.XSHG')

    # 变量
    g.i = 0 # 表明持有天数
    g.maxJC = 0 # 最大基差值

def set_slip_fee(context):
    # 根据不同的时间段设置手续费
    dt=context.current_dt
    # 设定股指期货手续费
    if dt<datetime.datetime(2015,9,7):
        set_order_cost(OrderCost(open_commission=0.00023,close_commission=0.00023, \
        close_today_commission=0.00023), type='index_futures')
    else:
        if  dt<datetime.datetime(2018,12,3):
            set_order_cost(OrderCost(open_commission=0.000023,close_commission=0.00023, \
            close_today_commission=0.00069), type='index_futures')
        else:
            set_order_cost(OrderCost(open_commission=0.000023, close_commission=0.00023, \
            close_today_commission=0.00046), type='index_futures')

def before_trading(context):
    g.today_traded = False
        
def trading(context):
    if not g.today_traded:
        IF = get_stock_index_futrue_code(context,'IF',month='current_month')
        ETF = '510300.XSHG'
        # 赋值于全局变量
        g.IF = IF
        g.ETF = ETF
        now=context.current_dt.strftime('%Y-%m-%d %H:%M:%S')
        if '9:55:00' in now and '2018-11-01' in  now:
            log.info('开仓11手--------*********----------:',IF)
            order(IF, 11, side='short', pindex=1)
        
   
    
def after_trading(context):
    # 如果有持仓，持仓天数加一
    if len(context.portfolio.positions) > 0:
        g.i += 1
    

def transfer_cash_test(context):
    '''
    从序号为 from_pindex 的 subportfolio 转移 cash 到序号为 to_pindex 的 subportfolio
    '''
    if context.current_dt.date() == context.run_params.start_date:
        log.info('transfer_cash() 演示')
        log.info('转移前subportfolio[0]的可取资金：%s 元' %context.subportfolios[0].transferable_cash)
        log.info('转移前subportfolio[1]的可取资金：%s 元' %context.subportfolios[1].transferable_cash)
        log.info('从 1 向 0 转移 100000.0 元')
        transfer_cash(1, 0, 100000.0)
        log.info('转移后subportfolio[0]的可取资金：%s 元' %context.subportfolios[0].transferable_cash)
        log.info('转移后subportfolio[1]的可取资金：%s 元' %context.subportfolios[1].transferable_cash)
        log.info('从 1 向 0 转移 100000.0 元')
        transfer_cash(0, 1, 100000.0)
        log.info('转移后subportfolio[0]的可取资金：%s 元' %context.subportfolios[0].transferable_cash)
        log.info('转移后subportfolio[1]的可取资金：%s 元' %context.subportfolios[1].transferable_cash)
        log.info('transfer_cash() 演示完毕，开始交易')



def get_stock_index_futrue_code(context,symbol,month='current_month'):
    '''
    获取当天时间正在交易的股指期货合约。其中:
    symbol:
            'IF' #沪深300指数期货
            'IC' #中证500股指期货
            'IH' #上证50股指期货
    month:
            'current_month' #当月
            'next_month'    #隔月
            'next_quarter'  #下季
            'skip_quarter'  #隔季
    '''
    display_name_dict = {'IC':'中证500股指期货','IF':'沪深300指数期货','IH':'上证50股指期货'}
    month_dict = {'current_month':0, 'next_month':1, 'next_quarter':2, 'skip_quarter':3}

    display_name = display_name_dict[symbol]
    n = month_dict[month]
    dt = context.current_dt.date()
    a = get_all_securities(types=['futures'], date=dt)
    try:
        df = a[(a.display_name == display_name) & (a.start_date <= dt) & (a.end_date >= dt)]
        return df.index[n]
    except:
        return 'WARRING: 无此合约'

