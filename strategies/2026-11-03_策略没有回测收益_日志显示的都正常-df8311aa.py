# Clone from JoinQuant
# postId: df8311aa9986cdbd9d9db93f36010dce
# backtestId: 7607d9ab5de30cf063d0b8342203022b
# title: 策略没有回测收益，日志显示的都正常

# 导入函数库
import jqdata
import talib
#import statsmodels.api as sm
#from statsmodels.tsa.stattools import adfuller

## 初始化函数，设定基准等等
def initialize(context):
    # 设置参数
    set_params(context)
    # 设定基准
    set_benchmark(get_future_code1(g.future_index[0]))
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 过滤掉order系列API产生的比error级别低的log
    log.set_level('order', 'error')
    # 初始化标的
    #g.future = get_future_code(g.future_index)
  
    ### 期货相关设定 ###
    # 设定账户为金融账户
    set_subportfolios([SubPortfolioConfig(cash=context.portfolio.starting_cash, type='index_futures')])
    # 期货类每笔交易时的手续费是：买入时万分之0.23,卖出时万分之0.23,平今仓为万分之23
    set_order_cost(OrderCost(open_commission=0.000023, close_commission=0.000023,close_today_commission=0.0023), type='index_futures')
    # 设定保证金比例
    set_option('futures_margin_rate', 0.15)

    # 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'IF1512.CCFX'或'IH1602.CCFX'是一样的）
      # 开盘前运行
    run_daily( before_market_open, time='before_open', reference_security=get_future_code1(g.future_index[0]))
      # 开盘时运行
    run_daily( while_open, time='open', reference_security=get_future_code1(g.future_index[0]))
      # 收盘后运行
    run_daily( after_market_close, time='after_close', reference_security=get_future_code1(g.future_index[0]))

def set_params(context):
    # 最近一次交易的合约
    g.future_index = ['RB','ZN','C','SR']
    # 设置唐奇安通道时间窗口
    g.window = 10
    # 最大unit数目
    g.limit_unit = 5
    # 每次交易unit数目，每个品种对应的数目
    g.unit = {}
    # 加仓次数，每个品种对应的加仓次数
    g.add_time = {}
    # 持仓状态
    g.position = {}
    
    # 最高价指标，用作移动止损
    g.price_mark = {}
    g.atr={}
    # 上一次交易的价格,字典格式是合约，对应的价格列表
    g.last_price = {}
    g.high_bop={}
    g.high_bops={}
    g.low_bop={}
    g.low_bops={}
    #是个字典
    g.DPP=get_future_coef(g.future_index)
    #进一步初始化
    for i in g.future_index:
        g.add_time[i]=0
        g.position[i]=0
        g.last_price[i]=[]
        g.unit[i]=0
        g.atr[i]=0
        g.high_bop[i]=0
        g.high_bops[i]=0
        g.low_bop[i]=0
        g.low_bops[i]=0
        
    g.future0=None
## 开盘前运行函数     
def before_market_open(context):
    ## 获取要操作的期货(g.为全局变量)
      # 获取当月期货合约
    for sec in g.future_index:
        #主力合约来计算确保数据连续性
        g.future0=get_future_code1(sec)
        seqdata = attribute_history(g.future0, 50, '1d', ['high','low','close'])
        high_seqdata = seqdata['high'].values
        low_seqdata = seqdata['low'].values
        close_seq = seqdata['close'].values
        atr = talib.ATR(high_seqdata,low_seqdata,close_seq,timeperiod = 20)
        #用作交易参考的atr
        g.atr[sec] = atr[-1]
       #用来开仓
        g.high_bop[sec]=high_seqdata[-20:].max()
        g.low_bop[sec]=low_seqdata[-20:].min()
        #用来止损
        g.high_bops[sec]=high_seqdata[-10:].max()
        g.low_bops[sec]=low_seqdata[-10:].min()
## 开盘时运行函数
def while_open(context):
    for sec in g.future_index:
        # 当月合约
        future =get_future_code1(sec)
        # 获取当月合约交割日期
        end_date = get_CCFX_end_date(future)
        # 当月合约交割日当天不开仓
        if (context.current_dt.date() == end_date):
            return
        if g.atr[sec]==0:
            return
        g.unit[sec]=int((0.01*context.portfolio.total_value) / (g.atr[sec]*g.DPP[sec]))
        close= get_bars(future, 5, unit='1m',fields='close',include_now=True)['close'][-1]
        open_signal = check_break(close,g.high_bop[sec],g.low_bop[sec])
        stop_signal = check_break(close,g.high_bops[sec],g.low_bops[sec])
        # 先判断是否持仓，没有持仓则开仓
        if g.position[sec]==0:
            if open_signal ==1:
            #开多仓
                order(future,g.unit[sec],side='long')
                log.info('多头建仓成功:%s,%s',context.current_dt,g.unit[sec])
                g.position[sec] = 1
                g.add_time[sec] = 1
                g.last_price[sec].append(close)
                log.info('多头建仓成功:%s,%s,%s',context.current_dt,g.unit[sec],g.last_price[sec])
            elif open_signal ==-1:
                #开空仓
                order(future,g.unit[sec],side='short')
                log.info( '空头建仓成功:%s,%s',context.current_dt,g.unit[sec])
                g.position[sec] = -1
                g.add_time[sec] = 1
                g.last_price[sec].append(close)   
        if g.position[sec]==1 and stop_signal ==-1:
            #持有多头的情况下，平多头
            order_target(future,0,side='long')
            log.info( '平多头:%s',context.current_dt)
            g.last_price[sec]=[]
            g.position[sec]=0
            g.add_time[sec]=0
        if g.position[sec]==-1 and stop_signal ==1:
            #持有空头的情况下，平空头
            order_target(future,0,side='short')
            log.info( '平空头:%s',context.current_dt)
            g.last_price[sec]=[]
            g.position[sec]=0
            g.add_time[sec]=0
        #有持仓，判断加仓或止损
        if g.position[sec] != 0 : 
            signal = get_next_signal(close,g.last_price[sec][-1],g.atr[sec],g.position[sec])   
            # 判断加仓且持仓没有达到上限
            if signal == 1 and g.add_time[sec] <= g.limit_unit:  
            # 多头加仓
                if g.position[sec] == 1: 
                    order(future,g.unit[sec],side='long')
                    log.info( '多头加仓成功:%s,%s',context.current_dt,g.unit[sec])
                    g.add_time[sec] += 1
                    g.last_price[sec].append(close)
                    log.info('g.last_price:%s,%s,%s',g.last_price[sec],close,g.add_time[sec])
                    log.info(g.last_price[sec])
                elif g.position[sec] == -1: 
                    order(future,g.unit[sec],side='short')
                    log.info( '空头加仓成功:%s,%s',context.current_dt,g.unit[sec])
                    g.last_price[sec].append(close)
                    g.add_time[sec] += 1
                # 判断平仓止损
            elif signal == -1:
                # 多头平仓
                if g.position[sec] == 1:
                    order_target(future,0,side='long')
                    g.position[sec] = 0
                    g.add_time[sec] = 0
                    g.last_price[sec]=[]
                    log.info( '多头止损成功:%s',context.current_dt)
               
                # 空头平仓
                elif g.position[sec] == -1:  
                    order_target(future,0,side='short')
                    g.position[sec] = 0
                    g.add_time[sec] = 0
                    g.last_price[sec]=[]
                    log.info( '空头止损成功:%s',context.current_dt)
   
## 收盘后运行函数  
def after_market_close(context):
    pass
########################## 自定义函数 #################################
# 重置参数
def re_set():
    # 每次交易unit数目
    g.unit = 0
    # 加仓次数
    g.add_time = 0
    # 持仓状态
    g.position = 0
#突破函数
def check_break(close,high_bop,low_bop):
    
    #high_bop = history_bars(context.s, 20, '1d', 'high').max()
    #low_bop = history_bars(context.s, 20, '1d', 'low').min()
    if close >= high_bop:
        signal = 1
    elif close <= low_bop:
        signal = -1
    else:
        signal = 0
    return signal
    
def get_next_signal(price,last_price,ATR,position):# 加仓或止损
    if (price >= last_price + 0.5*ATR and position==1) or (price <= last_price - 0.5*ATR and position==-1): # 多头加仓或空头加仓
        return 1
    elif (price <= last_price - 2*ATR and position==1) or (price >= last_price + 2*ATR and position==-1):  # 多头止损或空头止损
        return -1
    else:
        return 0 
        
def get_ATR(price_list,T):
    TR_list = [max(price_list['high'].iloc[i]-price_list['low'].iloc[i],abs(price_list['high'].iloc[i]-price_list['close'].iloc[i-1]),abs(price_list['close'].iloc[i-1]-price_list['low'].iloc[i])) for i in range(1,T+1)]
    ATR = np.array(TR_list).mean()
    return ATR

'''
def get_position(context): # 0为未持仓，1为持多，-1为持空 
    try:
        tmp = context.portfolio.positions.keys()[0]
        if not context.portfolio.long_positions[tmp].total_amount and not context.portfolio.short_positions[tmp].total_amount:
            return 0
        elif context.portfolio.long_positions[tmp].total_amount:
            return 1
        elif context.portfolio.short_positions[tmp].total_amount:
            return -1
        else:
            return 0
    except:
        return 0
'''
def get_unit(cash,ATR,symbol):
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
    return (cash*0.01/ATR)/future_coef_list[symbol]

def set_price_mark(context,future):
    if g.position == -1:
        g.price_mark = min(context.portfolio.short_positions[future].price,g.price_mark)
    elif g.position == 1:
        g.price_mark = max(context.portfolio.long_positions[future].price,g.price_mark)
                
def get_risk_signal(context,future):
    if g.position == -1:
        if context.portfolio.short_positions[future].price >=1.05*g.price_mark:
            log.info("空头仓位止损，时间： "+str(context.current_dt.time()))
            return True
        else:
            return False
    elif g.position == 1:
        if context.portfolio.long_positions[future].price <= 0.95*g.price_mark:
            log.info("多头仓位止损，时间： "+str(context.current_dt.time()))
            return True
        else:
            return False

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
    dtlist=[]
    try:
        for sc in symbol:
            dtlist.append(future_code_list[sc])
        return dtlist
    except:
        return 'WARNING: 合约有误'

# 获取当天时间正在交易的期货主力合约
def get_future_coef(symbol):
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
    dtlist={}
    try:
        for sc in symbol:
            dtlist[sc]=future_coef_list[sc]
        return dtlist
    except:
        return 'WARNING: 合约有误'
        
# 获取当天时间正在交易的期货主力合约
def get_future_code1(symbol):
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
