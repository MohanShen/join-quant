# Clone from JoinQuant
# postId: f3daf01b2d024426045c1283d6dd851a
# backtestId: 0a45eb88eaaca1818271c0e05f01d460
# title: 求助！最近在学习研究期货的策略编写，系统自带的期货标准策略运行回测结果中无交易，不知道哪里出问题了？

# 导入函数库
import jqdata

## 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')

    ### 期货相关设定 ###
    # 设定账户为金融账户
    set_subportfolios([SubPortfolioConfig(cash=context.portfolio.starting_cash, type='index_futures')])
    # 期货类每笔交易时的手续费是：买入时万分之0.23,卖出时万分之0.23,平今仓为万分之23
    set_order_cost(OrderCost(open_commission=0.000023, close_commission=0.000023,close_today_commission=0.0023), type='index_futures')
    # 设定保证金比例
    set_option('futures_margin_rate', 0.15)

    # 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'IF1512.CCFX'或'IH1602.CCFX'是一样的）
      # 开盘前运行
    run_daily( before_market_open, time='before_open', reference_security='IF1512.CCFX')
      # 开盘时运行
    run_daily( market_open, time='open', reference_security='IF1512.CCFX')
      # 收盘后运行
    run_daily( after_market_close, time='after_close', reference_security='IF1512.CCFX')

    
## 开盘前运行函数     
def before_market_open(context):
    # 输出运行时间
    log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))

    # 给微信发送消息（添加模拟交易，并绑定微信生效）
    send_message('美好的一天~')

    ## 获取要操作的股票(g.为全局变量)
      # 获取当月沪深300指数期货合约
    g.IF_current_month = get_stock_index_futrue_code(context,'IF',month='current_month')
      # 获取下季沪深300指数期货合约
    g.IF_next_quarter = get_stock_index_futrue_code(context,'IF',month='next_quarter')
    
## 开盘时运行函数
def market_open(context):
    log.info('函数运行时间(market_open):'+str(context.current_dt.time()))

    ## 交易
    
    # 当月合约
    IF_current_month = g.IF_current_month
    # 下季合约
    IF_next_quarter = g.IF_next_quarter

    # 合约列表
    stock_list = [IF_current_month, IF_next_quarter]
    # 获取数据
    hist = history(1, '1d', 'close', stock_list)
    # 当月合约价格
    IF_current_month_close = hist[IF_current_month][0]
    # 下季合约价格
    IF_next_quarter_close = hist[IF_next_quarter][0]
    
    # 计算差值
    CZ  = IF_current_month_close - IF_next_quarter_close

    # 获取当月合约交割日期
    end_data = get_CCFX_end_date(IF_current_month)
    
    # 判断差值大于80，且空仓，则做空当月合约、做多下季合约；当月合约交割日当天不开仓
    if (CZ > 80):
        if (context.current_dt.date() == end_data):
            # return
            pass
        else:
            if (len(context.portfolio.short_positions) == 0) and (len(context.portfolio.long_positions) == 0):
                log.info('开仓---差值：', CZ)
                # 做空1手当月合约
                order(IF_current_month, 1, side='short')
                # 做多1手下季合约
                order(IF_next_quarter, 1, side='long')
    # 如有持仓，并且基差缩小至70内，则平仓  
    if (CZ < 70):
        if(len(context.portfolio.short_positions) > 0) and (len(context.portfolio.long_positions) > 0):
            log.info('平仓---差值：', CZ)
            # 平仓当月合约
            order_target(IF_current_month, 0, side='short')
            # 平仓下季合约
            order_target(IF_next_quarter, 0, side='long')

## 收盘后运行函数  
def after_market_close(context):
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    # 得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    log.info('一天结束')
    log.info('##############################################################')



########################## 获取期货合约信息，请保留 #################################

# 获取当天时间正在交易的股指期货合约
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

# 获取当天时间正在交易的国债期货合约
def get_treasury_futrue_code(context,symbol,month='current'):
    '''
    获取当天时间正在交易的国债期货合约。其中:
    symbol:
            'T' #10年期国债期货
            'TF' #5年期国债期货
    month:
            'current' #最近期
            'next'    #次近期
            'skip'    #最远期
    '''
    display_name_dict = {'T':'10年期国债期货','TF':'5年期国债期货'}
    month_dict = {'current':0, 'next':1, 'skip':2}

    display_name = display_name_dict[symbol]
    n = month_dict[month]
    dt = context.current_dt.date()
    a = get_all_securities(types=['futures'], date=dt)
    try:
        df = a[(a.display_name == display_name) & (a.start_date <= dt) & (a.end_date >= dt)]
        return df.index[n]
    except:
        return 'WARRING: 无此合约'

# 获取金融期货合约到期日
def get_CCFX_end_date(fature_code):
    # 获取金融期货合约到期日
    return get_security_info(fature_code).end_date
