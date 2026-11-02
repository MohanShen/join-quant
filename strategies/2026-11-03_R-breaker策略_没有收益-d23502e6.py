# Clone from JoinQuant
# postId: d23502e69d0133cafd5ba3bd9c89ccbd
# backtestId: 7d8382a1e2825bb342b94367dc9e8074
# title: R-breaker策略，没有收益

# 导入函数库
from jqdata import *

## 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 过滤掉order系列API产生的比error级别低的log
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    # 输出内容到日志 log.info()
    # log.info('初始函数开始运行且全局只运行一次')

    ### 期货相关设定 ###
    # 设定账户为金融账户
    set_subportfolios([SubPortfolioConfig(cash=context.portfolio.starting_cash, type='futures')])
    # 期货类每笔交易时的手续费是：买入时万分之0.23,卖出时万分之0.23,平今仓为万分之23
    set_order_cost(OrderCost(open_commission=0.00023, close_commission=0.00023,close_today_commission=0.0023), type='futures')
    # 设定保证金比例
    set_option('futures_margin_rate', 0.30)
    # 设置期货交易的滑点
    set_slippage(StepRelatedSlippage(1))
    
    # 价格参数
    g.f1 = 0.03
    g.f2 = 0.07
    g.f3 = 0.20
    
    g.end_trading = False

    # 合约 
    # 螺纹 RB  焦煤 JM  动力煤 ZC  J
    # 沪铝  AL    白银  AG
    # 白糖 SR  玉米淀粉 CS  乙二醇  EG   玉米  C   豆一 A  豆油 Y   菜油  O  菜籽  RS
    # PVC：V  PTA TA
    g.future_index = 'J'
    g.last_future = None
    
    # 开盘前运行
    run_daily( before_market_open, time='before_open', reference_security=get_future_code(g.future_index))
    # 开盘时运行
    run_daily( market_open, time='every_bar', reference_security=get_future_code(g.future_index))
    # 夜盘收盘平仓
    #run_daily( close_order, '14:50')
    # 收盘后运行
    run_daily( after_market_close, time='after_close', reference_security=get_future_code(g.future_index))

## 开盘前运行函数
def before_market_open(context):
    # 输出运行时间
    log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))
    
    # 获取期货主力合约
    g.future = get_dominant_future(g.future_index)
    if g.last_future == None:
        g.last_future = g.future
    
    now = context.current_dt
    g.begin_time = datetime.datetime(now.year,now.month,now.day, 9, 0, 0)
    g.end_time = datetime.datetime(now.year,now.month,now.day, 14, 52, 0)

    # 前一天的价格
    hist = attribute_history(g.future, 1, '1d', ['open','close','high','low'], df=False)
    hist_high = hist['high'][0]
    hist_close = hist['close'][0]
    hist_low = hist['low'][0]
    
    # 观察买入价
    g.Bsetup = hist_low - g.f1 * (hist_high - hist_close)
    # 观察卖出价
    g.Ssetup = hist_high + g.f1 * (hist_close - hist_low)
    # 突破买入价
    g.Bbreak = g.Ssetup + g.f3 * (g.Ssetup - g.Bsetup)
    # 突破卖出价
    g.Sbreak = g.Bsetup - g.f3 * (g.Ssetup - g.Bsetup)
    # 反转卖出价
    g.Senter = (1.07/2) * (hist_high + hist_low) - 0.07 * hist_low
    # 反转买入价
    g.Benter = (1.07/2) * (hist_high + hist_low) - 0.07 * hist_high
    

## 开盘时运行函数
def market_open(context):
    log.info('函数运行时间(market_open):'+str(context.current_dt.time()))
    
    # 是否开仓  止损判断
    
    # 判断交易时间
    bar_hist = get_bars(g.future, 1, unit='1d',fields=['date', 'open','high','low','close'],include_now=True, end_dt=None, fq_ref_date=None)
    current_price = get_current_data()[g.future].last_price
    today_high = bar_hist['high']
    today_low = bar_hist['low']
    
    log.info('current_price', current_price, '突破买入价' ,g.Bbreak, '是否大于', current_price > g.Bbreak)
    log.info('current_price', current_price, '突破卖出价' ,g.Sbreak, '是否小于', current_price < g.Sbreak)
    now = context.current_dt.timestamp()
    if now > g.begin_time.timestamp() and now < g.end_time.timestamp():
        # 空仓做多
        if current_price > g.Bbreak and context.portfolio.long_positions[g.last_future].total_amount == 0 :
            if context.portfolio.short_positions[g.last_future].total_amount > 0:
                close_order(context, g.last_future, 'short')
                log.info("***空仓做多，平空仓！***", g.last_future, "short")
            
            order(g.future, 1, side='long')
            g.last_future = g.future
        # 空仓做空
        elif current_price < g.Sbreak and context.portfolio.short_positions[g.last_future].total_amount == 0 :
            if context.portfolio.long_positions[g.last_future].total_amount > 0:
                close_order(context, g.last_future, 'long')
                log.info("***空仓做空，平多仓！***", g.last_future, "long")
            
            order(g.future, 1, side='short')
            g.last_future = g.future
        # 多单反转
        elif context.portfolio.long_positions[g.last_future].total_amount > 1 and today_high > g.Ssetup and current_price < g.Senter:
            close_order(context, g.last_future, 'long')
            log.info("***多单反转，平多仓！***", g.last_future, "long")
            if context.portfolio.long_positions[g.last_future].total_amount == 0:
                order(g.future, 1, side='short')
                g.last_future = g.future
        # 空单反转
        elif context.portfolio.short_positions[g.last_future].total_amount > 1 and today_low < g.Bsetup and current_price > g.Benter:
            close_order(context, g.last_future, 'short')
            log.info("***空单反转，平空仓！***", g.last_future, "short")
            if context.portfolio.short_positions[g.last_future].total_amount == 0:
                order(g.future, 1, side='long')
                g.last_future = g.future
        
    if now > g.end_time.timestamp():
        if context.portfolio.short_positions[g.last_future].total_amount > 0:
            close_order(context, g.last_future, 'short')
            log.info("***收盘前，平空仓！***", g.last_future, "short")
        if context.portfolio.long_positions[g.last_future].total_amount > 0:
            close_order(context, g.last_future, 'long')
            log.info("***收盘前，平多仓！***", g.last_future, "long")

## 收盘后运行函数
def after_market_close(context):
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    # 得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    log.info('#####################一天结束######################')

########################## 常用函数，请保留 #################################
# 平仓函数
def close_order(context, future, side):
    if side == 'long':
        order_target(future, 0, side='long')
        if context.portfolio.long_positions[future].total_amount == 0:
            g.position = 0
            log.info( '多头平仓成功:',context.current_dt.time(),future)
            log.info('----------------------------------------------------------')
    elif side == 'short':
        order_target(future, 0, side='short')
        if context.portfolio.short_positions[future].total_amount == 0:
            g.position = 0
            log.info( '空头平仓成功:',context.current_dt.time(),future)
            log.info('----------------------------------------------------------')
            
# 获取连续合约code
def get_future_code(symbol):
    future_code_list = {'A':'A9999.XDCE', 'AG':'AG9999.XSGE', 'AL':'AL9999.XSGE', 'AU':'AU9999.XSGE',
                        'B':'B9999.XDCE', 'BB':'BB9999.XDCE', 'BU':'BU9999.XSGE', 'C':'C9999.XDCE', 
                        'CF':'CF9999.XZCE', 'CS':'CS9999.XDCE', 'CU':'CU9999.XSGE', 'ER':'ER9999.XZCE', 
                        'FB':'FB9999.XDCE', 'FG':'FG9999.XZCE', 'FU':'FU9999.XSGE', 'GN':'GN9999.XZCE', 
                        'HC':'HC9999.XSGE', 'I':'I9999.XDCE', 'IC':'IC9999.CCFX', 'IF':'IF9999.CCFX', 
                        'IH':'IH9999.CCFX', 'J':'J9999.XDCE', 'JD':'JD9999.XDCE', 'JM':'JM9999.XDCE', 
                        'JR':'JR9999.XZCE', 'L':'L9999.XDCE', 'LR':'LR9999.XZCE', 'M':'M9999.XDCE', 
                        'MA':'MA9999.XZCE', 'ME':'ME9999.XZCE', 'NI':'NI9999.XSGE', 'OI':'OI9999.XZCE', 
                        'P':'P9999.XDCE', 'PB':'PB9999.XSGE', 'PM':'PM9999.XZCE', 'PP':'PP9999.XDCE', 
                        'RB':'RB9999.XSGE', 'RI':'RI9999.XZCE', 'RM':'RM9999.XZCE', 'RO':'RO9999.XZCE', 
                        'RS':'RS9999.XZCE', 'RU':'RU9999.XSGE', 'SF':'SF9999.XZCE', 'SM':'SM9999.XZCE', 
                        'SN':'SN9999.XSGE', 'SR':'SR9999.XZCE', 'T':'T9999.CCFX', 'TA':'TA9999.XZCE', 
                        'TC':'TC9999.XZCE', 'TF':'TF9999.CCFX', 'V':'V9999.XDCE', 'WH':'WH9999.XZCE', 
                        'WR':'WR9999.XSGE', 'WS':'WS9999.XZCE', 'WT':'WT9999.XZCE', 'Y':'Y9999.XDCE', 
                        'ZC':'ZC9999.XZCE', 'ZN':'ZN9999.XSGE'}
    try:
        return future_code_list[symbol]
    except:
        return 'WARNING: 无此合约'
        
# 获取期货合约到期日
def get_CCFX_end_date(fature_code):
    return get_security_info(fature_code).end_date

## 获取当天时间正在交易的期货合约   get_dominant_future('IF')
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
    display_name_dict = {'IF':'沪深300指数期货','IC':'中证500股指期货','IH':'上证50股指期货'}
    month_dict = {'current_month':0, 'next_month':1, 'next_quarter':2, 'skip_quarter':3}

    display_name = display_name_dict[symbol]
    n = month_dict[month]
    dt = context.current_dt.date()
    a = get_all_securities(types=['futures'], date=dt)
    try:
        df = a[(a.display_name == display_name) & (a.start_date <= dt) & (a.end_date >= dt)]
        if (len(df)>4) and (month in ('next_quarter','skip_quarter')):
            return df.index[n+1]
        else:
            return df.index[n]
    except:
        return 'WARRING: 无此合约'

########################## 自动移仓换月函数 #################################
def position_auto_switch(context,pindex=0,switch_func=None, callback=None):
    """
    期货自动移仓换月。默认使用市价单进行开平仓。
    :param context: 上下文对象
    :param pindex: 子仓对象
    :param switch_func: 用户自定义的移仓换月函数.
        函数原型必须满足：func(context, pindex, previous_dominant_future_position, current_dominant_future_symbol)
    :param callback: 移仓换月完成后的回调函数。
        函数原型必须满足：func(context, pindex, previous_dominant_future_position, current_dominant_future_symbol)
    :return: 发生移仓换月的标的。类型为列表。
    """
    import re
    subportfolio = context.subportfolios[pindex]
    symbols = set(subportfolio.long_positions.keys()) | set(subportfolio.short_positions.keys())

    switch_result = []
    for symbol in symbols:
        log.info(symbol)
        match = re.match(r"(?P<underlying_symbol>[A-Z]{1,})", symbol)
        if not match:
            raise ValueError("未知期货标的：{}".format(symbol))
        else:
            dominant = get_dominant_future(match.groupdict()["underlying_symbol"])
            cur = get_current_data()
            symbol_last_price = cur[symbol].last_price
            dominant_last_price = cur[dominant].last_price
            log.info(dominant)
            if dominant > symbol:
                for p in (subportfolio.long_positions.get(symbol, None), subportfolio.short_positions.get(symbol, None)):
                    if p is None:
                        continue
                    if switch_func is not None:
                        switch_func(context, pindex, p, dominant)
                    else:
                        amount = p.total_amount
                        # 跌停不能开空和平多，涨停不能开多和平空。
                        if p.side == "long":
                            symbol_low_limit = cur[symbol].low_limit
                            dominant_high_limit = cur[dominant].high_limit
                            if symbol_last_price <= symbol_low_limit:
                                log.warning("标的{}跌停，无法平仓。移仓换月取消。".format(symbol))
                                continue
                            elif dominant_last_price >= dominant_high_limit:
                                log.warning("标的{}涨停，无法开仓。移仓换月取消。".format(symbol))
                                continue
                            else:
                                log.info("进行移仓换月：({0},long) -> ({1},long)".format(symbol, dominant))
                                order_target(symbol,0,side='long')
                                order_target(dominant,amount,side='long')
                                switch_result.append({"before": symbol, "after":dominant, "side": "long"})
                            if callback:
                                callback(context, pindex, p, dominant)
                        if p.side == "short":
                            symbol_high_limit = cur[symbol].high_limit
                            dominant_low_limit = cur[dominant].low_limit
                            if symbol_last_price >= symbol_high_limit:
                                log.warning("标的{}涨停，无法平仓。移仓换月取消。".format(symbol))
                                continue
                            elif dominant_last_price <= dominant_low_limit:
                                log.warning("标的{}跌停，无法开仓。移仓换月取消。".format(symbol))
                                continue
                            else:
                                log.info("进行移仓换月：({0},short) -> ({1},short)".format(symbol, dominant))
                                order_target(symbol,0,side='short')
                                order_target(dominant,amount,side='short')
                                switch_result.append({"before": symbol, "after": dominant, "side": "short"})
                                if callback:
                                    callback(context, pindex, p, dominant)
    return switch_result
