# Clone from JoinQuant
# postId: 1fdfd9da4dfcf843f474636756e52289
# backtestId: 0af8f7985cd7e705022293dcb1d3ca86
# title: 想问下期货平仓的问题

import jqdata
import statsmodels.api as sm
from statsmodels.tsa.stattools import adfuller

## 初始化函数，设定基准等等
def initialize(context):
    # 设置参数
    set_params(context)
    set_benchmark(get_future_code(g.future_symbol))
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 过滤掉order系列API产生的比error级别低的log
    log.set_level('order', 'error')
    # 初始化标的
    g.future = get_future_code(g.future_symbol)
    g.last_future = None
    
    ### 期货相关设定 ###
    # 设定账户为金融账户
    set_subportfolios([SubPortfolioConfig(cash=context.portfolio.starting_cash, type='index_futures')])
    # 期货类每笔交易时的手续费是：买入时万分之0.23,卖出时万分之0.23,平今仓为万分之23
    set_order_cost(OrderCost(open_commission=0.000023, close_commission=0.000023,close_today_commission=0.0023), type='index_futures')
    # 设定保证金比例
    set_option('futures_margin_rate', 0.15)

    # 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'IF1512.CCFX'或'IH1602.CCFX'是一样的）
      # 开盘前运行
    run_daily( before_market_open, time='before_open', reference_security=get_future_code(g.future_symbol))
      # 开盘时运行
    run_daily( while_open, time='every_bar', reference_security=get_future_code(g.future_symbol))
      # 收盘后运行
    run_daily( after_market_close, time='after_close', reference_security=get_future_code(g.future_symbol))


def set_params(context):
    # 设置BOLL时间窗口
    g.window = 9
    # 设置BOLL波动系数
    g.devk = 2
    g.devp = 1
    # 最高价指标，用作移动止损
    g.price_mark = 0
    # 设置合约简称
    g.future_symbol = 'RB'
    
    ## 设置两个指标判断多空仓位情况
      # 多头仓位
    g.long_position = False
      # 空头仓位
    g.short_position = False
    

    
## 开盘前运行函数     
def before_market_open(context):
    ## 获取要操作的标的 
    g.future = get_dominant_future(g.future_symbol)
    
    
## 开盘时运行函数
def while_open(context):
    # 当月合约
    future = g.future
    # 如果期货标的改变，重置参数
    if g.last_future == None:
        g.last_future = g.future
    elif g.last_future != g.future:
        if g.long_position:
            order_target(g.last_future, 0, side = 'long')
            g.long_position = False
        elif g.short_position:
            order_target(g.last_future, 0, side = 'short')
            g.short_position = False
        g.last_future = g.future
        g.price_mark = 0
        log.info("主力合约改变，平仓！")
    ## boll开仓
    future_up,future_mid,future_down,future_close = get_bollk(context.current_dt,future,g.window,g.devk)
    future_upp,future_midp,future_downp,future_close = get_bollp(context.current_dt,future,g.window,g.devp)
    # 前一bar收盘价高于布林带上线，且没有多头仓位 
    if future_close>future_up:
        # 如果持仓空头
        if g.short_position:
            log.info('###############################################################')
            order_target(future, 0, side='short')
            g.short_position = False
            g.price_mark = 0
            log.info("空头仓位平仓成功！future_up: {},future_close: {}".format(future_up,future_close))
        # 创建多头仓位
        else:
            log.info('--------------------------------------------------------------')
            current_buy = get_amount(context,future_close)
            order(future, current_buy, side='long')
            if context.portfolio.positions[future].total_amount > 0:
                g.long_position = True
                g.price_mark = context.portfolio.long_positions[future].price
                log.info("收盘价高于上线，future_up: {},future_close: {}".format(future_up,future_close))
                log.info("创建多头仓位成功，时间： "+str(context.current_dt.time()))
    # 前一bar收盘价低于布林带下线，且没有空头仓位
    if future_close<future_down:
        # 如果持仓多头
        if g.long_position:
            log.info('###############################################################')
            order_target(future, 0, side='long')
            g.long_position = False
            g.price_mark = 0
            log.info("多头仓位平仓成功！future_down: {},future_close: {}".format(future_down,future_close))
        # 创建空头仓位
        else:
            log.info('--------------------------------------------------------------')
            current_buy = get_amount(context,future_close)
            order(future, current_buy, side='short')
            if context.portfolio.short_positions[future].total_amount > 0:
                g.short_position = True
                g.price_mark = context.portfolio.short_positions[future].price
                log.info("收盘价低于下线，future_down: {},future_close: {}".format(future_down,future_close))
                log.info("创建空头仓位成功，时间： "+str(context.current_dt.time()))
    ## boll平仓
    if future_close > future_upp:
        if g.short_position:
            order_target(future, 0, side = 'short')
            order_target(future, 0, side = 'long')
            g.short_position = False
            g.price_mark = 0
            log.info('空平 ')
            return
    if future_close < future_downp:
        if g.long_position:
            order_target(future, 0, side = 'long')
            g.long_position = False
            g.price_mark = 0
            log.info('多平 ')
            return
    if g.short_position == True or g.long_position == True:
        # 判断今日是否出现最高价
        set_price_mark(context,future)
        # 得到止损信号
        signal = get_risk_signal(context,future)
        # 止损平仓
        if signal:
            order_target(future, 0, side='short')
            order_target(future, 0, side='long')
            g.long_position = False
            g.short_position = False
            g.price_mark = 0
    

def set_price_mark(context,future):
    if g.short_position == True:
        g.price_mark = min(context.portfolio.short_positions[future].price,g.price_mark)
    elif g.long_position == True:
        g.price_mark = max(context.portfolio.long_positions[future].price,g.price_mark)
                
def get_risk_signal(context,future):
    if g.short_position == True:
        if context.portfolio.short_positions[future].price >=1.15*g.price_mark:
            log.info("空头仓位止损，时间： "+str(context.current_dt.time()))
            return True
        else:
            return False
    elif g.long_position == True:
        if context.portfolio.long_positions[future].price <= 0.85*g.price_mark:
            log.info("多头仓位止损，时间： "+str(context.current_dt.time()))
            return True
        else:
            return False
        
def get_bollk(dt,future,win,d):
    # 当月合约价格
    future_close = history(win, '1d', 'close', future)[future]
    # 计算过去20日的移动平均线作为中轨
    mid=np.mean(future_close)
    # 计算昨日20日的标准差
    std=np.std(future_close)
    #用up来保存昨日的上轨线
    up=mid+g.devk*std
    #用down来保存昨日的下轨线
    down=mid-g.devk*std
    return up,mid,down,future_close[-1]
def get_bollp(dt,future,win,d):
    # 当月合约价格
    future_close = history(win, '1d', 'close', future)[future]
    # 计算过去20日的移动平均线作为中轨
    mid=np.mean(future_close)
    # 计算昨日20日的标准差
    std=np.std(future_close)
    #用up来保存昨日的上轨线
    up=mid+g.devp*std
    #用down来保存昨日的下轨线
    down=mid-g.devp*std
    return up,mid,down,future_close[-1]

def get_amount(context,price):
    future_coef_list = {'A':10, 'AG':15, 'AL':5, 'AU':1000,
                        'B':10, 'BB':500, 'BU':10, 'C':10, 
                        'CF':5, 'CS':10, 'CU':5, 'ER':10, 
                        'FB':500, 'FG':20, 'FU':50, 'GN':10, 
                        'HC':10, 'I':100, 'IC':200, 'IF':300, 
                        'IH':300, 'J':100, 'JD':5, 'JM':60, 
                        'JR':20, 'L':5, 'LR':10, 'M':10, 
                        'MA':10, 'ME':10, 'NI':1, 'OI':10, 
                        'P':10, 'PB':5, 'PM':50, 'PP':5, 
                        'RB':10, 'RI':20, 'RM':10, 'RO':10, 
                        'RS':10, 'RU':10, 'SF':5, 'SM':5, 
                        'SN':1, 'SR':10, 'T':10000, 'TA':5, 
                        'TC':100, 'TF':10000, 'V':5, 'WH':20, 
                        'WR':10, 'WS':50, 'WT':10, 'Y':10, 
                        'ZC':100, 'ZN':5}
    return 0.85*context.portfolio.available_cash/(0.15*future_coef_list[g.future_symbol]*price)
    

## 收盘后运行函数  
def after_market_close(context):
    pass



########################## 获取期货合约信息，请保留 #################################

# 获取当天时间正在交易的期货主力合约
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
