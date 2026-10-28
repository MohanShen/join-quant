# Clone from JoinQuant
# postId: 717484258fcd8c14850e478e77867d0e
# backtestId: 145335d6749918b2aae7442fc95d3743
# title: 银行股搬砖轮动+300指数对冲策略

import datetime
from dateutil import relativedelta   

def initialize(context):
    g.security = '000300.XSHG'
    # 设定基准
    set_benchmark(g.security)
    # 关闭订单提醒
    log.set_level('order', 'error')
    # 设定保证金比例
    set_option('futures_margin_rate', 0.15)
    # 设定手续费
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, \
                    close_commission=0.0003, min_commission=5), type='stock')
    # # 金融期货close_today_commission可不用设定，2015-09-07 之前不分平今平昨，之后平今仓默认0.00023
    set_order_cost(OrderCost(open_commission=0.000023, close_commission=0.000023, \
                    ), type='index_futures')
    
    # 设定两个账户（账户0为股票仓位，账户1为股指期货仓位）
    set_subportfolios([SubPortfolioConfig(cash=2000000,type='stock'),\
                       SubPortfolioConfig(cash=1000000,type='index_futures')])
    # log.info(context.subportfolios)

    # 运行函数（reference_security为运行时间的参考标的）
    run_daily(before_trading, time='before_open', reference_security='000300.XSHG')
    run_daily(trading, time='09:40', reference_security='000300.XSHG')
    run_daily(liquidation, time='14:45', reference_security='000300.XSHG')

    # 变量
    g.firstDay= False

def before_trading(context):
    g.stocks = get_index_stocks('000951.XSHG')
    #找出最低市净率的股票
    g.df = get_fundamentals(
        query(
            valuation.code,valuation.pb_ratio
        ).filter(
            valuation.code.in_(g.stocks)
        ).order_by(
            valuation.pb_ratio.asc()
        )
    )
    
def trading(context):
    if not g.firstDay:
        code = get_current_month_future(context, 'IF')
        hist = history(1, '1m', 'close', [code])
        IF_close = hist[code][0]
        amount = int(context.subportfolios[1].available_cash / (IF_close * 300 * 0.3))
        order(code, 2, side='short', pindex=1)
        g.firstDay=True
    if context.current_dt.isoweekday()!=1:
        return
    code = g.df['code'][0]
    for position in context.subportfolios[0].long_positions.values():
        if position.security!=code:
            order_target(position.security,0)
    #持仓该股票
    order_value(code,context.subportfolios[0].cash)
    
def liquidation(context):
    '''
    在到期日平仓
    '''
    # log.info(context.subportfolios[1].is_dangerous(0.2))
    code = get_current_month_future(context, 'IF')
    codeNext = get_next_month_future(context, 'IF')
    end_data = get_CCFX_end_date(code)
    if context.current_dt.date() == end_data:
        log.info('交割日:', context.current_dt.date())
        if len(context.portfolio.positions) > 0:
            log.info('交割日平仓')
            order_target(code, 0, side='short', pindex=1)
            hist = history(1, '1m', 'close', [codeNext])
            IF_close = hist[codeNext][0]
            amount = int(context.subportfolios[1].available_cash / (IF_close * 300 * 0.3))
            order(codeNext, 2, side='short', pindex=1)

def get_current_month_future(context, symbol):
    '''
    取当月连续string，symbol是'IF','IC','IF'
    输出例如'IF1508.CCFX'
    '''
    dt = context.current_dt
    week_day_ord = (dt.isoweekday()+1)%7 +1
    threshold = dt.day - week_day_ord - 14
    # 如果没过第三个星期五
    if threshold<=0:
        year = str(dt.year)[2:]
        month = str(dt.month)
    else:
        year = str(dt.year+dt.month//12)[2:]
        month = str(dt.month%12+1)
    if len(month)==1:
        month = '0'+month
    return(symbol+year+month+'.CCFX')

def get_next_month_future(context, symbol):
    dt = context.current_dt
    week_day_ord = (dt.isoweekday()+1)%7 +1
    threshold = dt.day - week_day_ord - 14
    # 如果没过第三个星期五
    if threshold<=0:
        year = str(dt.year+dt.month//12)[2:]
        month = str(dt.month%12+1)
    else:
        next_dt = dt + relativedelta.relativedelta(months=2)
        year = str(dt.year+(dt.month+1)//12)[2:]
        month = str((dt.month+1)%12+1)
    if len(month)==1:
        month = '0'+month
    return(symbol+year+month+'.CCFX')

def get_CCFX_end_date(fature_code):
    return get_security_info(fature_code).end_date
