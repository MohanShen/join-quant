# Clone from JoinQuant
# postId: bc245606de0dfec03e486d4c610dcef6
# backtestId: 3e06561da91d55707dc8a3e5f19e60b9
# title: 期限结构Carry收益 期货多品种对冲模型

# 期货多品种展期收益率
# 建议给予10000000元，2014年1月1日至今回测
# 导入函数库
from jqdata import * 
import talib
import re


def initialize(context):
    # 设置参数
    set_parameter(context)
    # 价格列表初始化
    set_future_list(context)
    # 设定基准银华日利，在多品种的回测当中基准没有参考意义
    set_benchmark('511880.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 过滤掉order系列API产生的比error级别低的log
    log.set_level('order', 'error')
    ### 期货相关设定 ###
    # 设定账户为金融账户
    set_subportfolios([SubPortfolioConfig(cash=context.portfolio.starting_cash, type='futures')])
    # 期货类每笔交易时的手续费是：买入时万分之1,卖出时万分之1,平今仓为万分之1
    set_order_cost(OrderCost(open_commission=0.0001, close_commission=0.0001,close_today_commission=0.0001), type='index_futures')
    # 设定保证金比例
    set_option('futures_margin_rate', 0.15)
    # 设置滑点（单边万5，双边千1）
    set_slippage(PriceRelatedSlippage(0.001),type='future')
    # 开盘前运行
    run_daily( before_market_open, time='before_open', reference_security=get_future_code('RB'))
    # 开盘时运行
    run_weekly( market_open, 1,time='open', reference_security=get_future_code('RB'))
    # 交易运行 
    run_weekly( Trade, 1, time='open', reference_security=get_future_code('RB'))
    # 收盘后运行
    run_daily( after_market_close, time='after_close', reference_security=get_future_code('RB'))


# 参数设置函数
def set_parameter(context):
    # 历史上的每个合约主力月份
    g.domMonth = {
        'MA': ['01', '05', '09'],
		'IC':['01','02','03','04','05','06','07','08','09','10','11','12'],
		'IF':['01','02','03','04','05','06','07','08','09','10','11','12'],
		'IH':['01','02','03','04','05','06','07','08','09','10','11','12'],
		'TF':['03','06','09','12'],
		'T':['03','06','09','12'],
		'CU':['01','02','03','04','05','06','07','08','09','10','11','12'],
		'AL':['01','02','03','04','05','06','07','08','09','10','11','12'],
		'ZN':['01','02','03','04','05','06','07','08','09','10','11','12'],
		'PB':['01','02','03','04','05','06','07','08','09','10','11','12'],
		'NI':['01', '05', '09'],
		'SN':['01', '05', '09'],
		'AU':['06', '12'],
		'AG':['06', '12'],
		'RB':['01', '05', '10'],
		'HC':['01', '05', '10'],
		'BU':['06', '09', '12'],
		'RU':['01', '05', '09'],
		'M':['01', '05', '09'],
		'Y':['01', '05', '09'],
		'A':['01', '05', '09'],
		'P':['01', '05', '09'],
		'C':['01', '05', '09'],
		'CS':['01', '05', '09'],
		'JD':['01', '05', '09'],
		'L':['01', '05', '09'],
		'V':['01', '05', '09'],
		'PP':['01', '05', '09'],
		'J':['01', '05', '09'],
		'JM':['01', '05', '09'],
		'I':['01', '05', '09'],
		'SR':['01', '05', '09'],
		'CF':['01', '05', '09'],
		'ZC':['01', '05', '09'],
		'FG':['01', '05', '09'],
		'TA':['01', '05', '09'],
		'MA':['01', '05', '09'],
		'OI':['01', '05', '09'],
		'RM':['01', '05', '09'],
		'SF':['01', '05', '09'],
		'SM':['01', '05', '09'],
		'AP':['01', '05', '10'],
    }
    
    #######变量设置########

    g.TradeLots = {}  # 各品种的交易手数信息
    g.Price_dict = {} # 各品种价格列表字典
    g.MappingReal = {} # 真实合约映射（key为symbol，value为主力合约）
    g.MappingIndex = {} # 指数合约映射 （key为 symbol，value为指数合约）
    g.MappingNext = {} # 远月合约映射 （key为symbol，value为远月合约）
    g.StatusTimer = {} # 当前状态计数器
    g.ATR = {}
    g.CurrentPrice = {}
    g.Price_DaysAgo = {}
    g.Momentum = {}
    g.ClosePrice = {}
    g.MarginRate = 0.1
    g.NextPrice = {}
    g.RealPrice = {}
    g.RY = {}
 

    #######参数设置########
    g.NATRstop = 2     # ATR追踪止损
    g.BackWindow = 20  # 回溯窗口长度
    # 交易的期货品种信息
    # g.instruments = ['A', 'AG', 'AL', 'AU', 'C', 'CF', 'CS', 'CU', 'FG', 'I', 'J', 'JD', 'JM', 'L', 'M','MA', 'NI', 'OI', 'P', 'PP', 'RB', 'RM', 'RU', 'SR', 'TA', 'V', 'Y', 'ZC', 'ZN']
    g.instruments = ['AL','NI','CU','PB','AG',
                     'RU','MA','PP','TA','L','V',
                     'M','P','Y','OI','C','CS','JD','SR',
                     'HC','J','I','SF','RB','ZC','FG']
    
# 价格列表初始化
def set_future_list(context):
    for ins in g.instruments:
        # 获取远期合约
        get_nextDom(context,ins)
        # 填充映射字典
        dom = get_dominant_future(ins)
        g.MappingReal[ins] = dom


'''
换月模块逻辑（ins是期货品种的symbol（如‘RB’），dom或future指合约（如'RB1610.XSGE'）,idx指指数合约（如’RB8888.XSGE‘）
    1.在第一天开始时，将所有期货品种最初的主力合约写入MappingReal与MappingIndex当中
    2.每天开盘获取一遍ins对应的主力合约，判断是否在MappingReal中，若不在，则执行replace模块
    3.replace模块中，卖出原来持有的主力合约，等量买入新合约；修改MappingReal
'''
## 开盘前运行函数
def before_market_open(context):
            
    # 输出运行时间
    log.info('函数运行时间(before_market_open)：'+str(context.current_dt.time()))
    send_message('开始交易')
    
    # 过滤无主力合约的品种，传入并修改期货字典信息
    for ins in g.instruments:
        
        dom = get_dominant_future(ins)
        if dom == '':
            pass
        else:
            # 判断是否执行replace_old_futures
            if dom == g.MappingReal[ins]:
                pass
            else:
                replace_old_futures(context,ins,dom)
                g.MappingReal[ins] = dom 
            
            # 获取远期合约
            get_nextDom(context,ins)
            g.TradeLots[dom] = get_lots(context.portfolio.starting_cash/len(g.instruments),ins)
    

## 开盘时运行函数，计算展期收益率，并分组
def market_open(context):
    # 输出函数运行时间
    #log.info('函数运行时间(market_open):'+str(context.current_dt.time()))
    g.RYB = {}
    g.RYS = {}
    # 以下是主循环
    for ins in g.instruments:
        # 过滤空主力合约品种
        try:
            attribute_history(g.MappingNext[ins],1,'1d',['close'])['close'][-1]
            go = True
        except:
            go = False
        if g.MappingReal[ins] != '' and  go:
            RealFuture = g.MappingReal[ins]
            NextFuture = g.MappingNext[ins]
            # 获取当月合约交割日期
            end_date = get_CCFX_end_date(RealFuture)
            # 当月合约交割日当天不开仓
            if (context.current_dt.date() == end_date):
                return
            else:
                g.NextPrice[NextFuture] = attribute_history(NextFuture,1,'1d',['close','open','high','low'])
                g.RealPrice[RealFuture] = attribute_history(RealFuture,g.BackWindow,'1d',['close','open','high','low'])

                # 如果没有数据，返回
                if len(g.RealPrice[RealFuture]) < 1:
                    return
                else:
                    # 远月价格 和 当月价格
                    g.PriceNext = g.NextPrice[NextFuture]['close'][-1]
                    g.PriceCurrent = g.RealPrice[RealFuture]['close'][-1]
                    
                    NextDate = re.findall(r"\d+\d*",NextFuture)
                    RealDate = re.findall(r"\d+\d*",RealFuture)
                    
                    
                    if NextDate[0][:2]>RealDate[0][:2]:
                        g.DM = int(NextDate[0][-2:])+12 - int(RealDate[0][-2:])
                    else:
                        g.DM = int(NextDate[0][-2:])-int(RealDate[0][-2:])
                        
                    # 展期收益率
                    g.RY[ins] = (g.PriceCurrent-g.PriceNext)/g.PriceNext/g.DM
                    # 分为升水RYS，贴水两组RYB
                    if g.RY[ins] < 0:
                        g.RYS[ins] = g.RY[ins]
                    elif g.RY[ins] > 0:
                        g.RYB[ins] = g.RY[ins]
                    
                    # 计算ATR，本程序中没有用到ATR值
                    g.close = np.array(g.RealPrice[RealFuture]['close'])
                    g.high = np.array(g.RealPrice[RealFuture]['high'])
                    g.low = np.array(g.RealPrice[RealFuture]['low'])
                    g.ATR[RealFuture] = talib.ATR(g.high,g.low,g.close, g.BackWindow)[-1]


## 收盘后运行函数
def after_market_close(context):
    log.info(str('函数运行时间(after_market_close):'+str(context.current_dt.time())))
    # 得到当天所有成交记录
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：'+str(_trade))
    log.info('一天结束')
    log.info('##############################################################')


## 交易模块 
def Trade(context):
    # 多头部分的品种，展期收益率大于0
    a = sorted(g.RYB.items(), key=lambda x: x[1],reverse = True)
    # 空头部分的品种，展期收益率小于0
    b = sorted(g.RYS.items(), key=lambda x: x[1],reverse = False)
    print(a,b)
    BuyList = []
    SellList = []
    
    # 将字典进行排序，各买入50%，或者全部交易
    for i in range(int(len(a)*1)):
        BuyList.append(a[i][0])
    for i in range(int(len(b)*1)):
        SellList.append(b[i][0])
       
    # 每个品种单独交易
    for ins in g.instruments:
        RealFuture = g.MappingReal[ins]
        if RealFuture in g.RealPrice.keys():
            
            if ins in BuyList and context.portfolio.long_positions[RealFuture].total_amount == 0 :
                order_target(RealFuture,0,side='short')
                order_target(RealFuture,g.TradeLots[RealFuture],side='long')
                log.info('正常买多合约：%s'%(RealFuture))
        
            elif ins in SellList and context.portfolio.short_positions[RealFuture].total_amount == 0:
                order_target(RealFuture,0,side ='long')
                order_target(RealFuture,g.TradeLots[RealFuture],side='short')
                log.info('正常卖空合约：%s'%(RealFuture))
            
            # 上次持仓的品种，如果已被移出BuyList和SellList，则平仓
            elif ins not in BuyList and RealFuture in context.portfolio.long_positions.keys():
                order_target(RealFuture,0,side ='long')
            elif ins not in SellList and RealFuture in context.portfolio.short_positions.keys():
                order_target(RealFuture,0,side ='short')


# 移仓模块：当主力合约更换时，平当前持仓，更换为最新主力合约        
def replace_old_futures(context,ins,dom):
    
    LastFuture = g.MappingReal[ins]
    
    if LastFuture in context.portfolio.long_positions.keys():
        lots_long = context.portfolio.long_positions[LastFuture].total_amount
        order_target(LastFuture,0,side='long')
        order_target(dom,lots_long,side='long')
        print('主力合约更换，平多仓换新仓')
    
    if LastFuture in context.portfolio.short_positions.keys():
        lots_short = context.portfolio.short_positions[dom].total_amount
        order_target(LastFuture,0,side='short')
        order_target(dom,lots_short,side='short')
        print('主力合约更换，平空仓换新仓')


# 获得当前远月合约
def get_nextDom(context,ins):
    # 获取当月主力合约
    dom = get_dominant_future(ins)
    if dom !='':
        # 获取合约交割月份时间，如['1601'] 
        YD = re.findall(r"\d+\d*",dom)
        try:
            # 获取远月合约——读取“历史上的每个合约主力月份”，读取月份后两位，往后移一位
            nextDomMonth = g.domMonth[ins][g.domMonth[ins].index(YD[0][-2:])+1]
            # 替换远月合约日期，合成远月合约名，如['RB1601.XSGE'] 
            g.MappingNext[ins]=dom.replace(YD[0][-2:],nextDomMonth)
        except:
            nextDomMonth = g.domMonth[ins][0]
            nextDom = dom.replace(YD[0][:2],str(int(YD[0][:2])+1))
            g.MappingNext[ins] = nextDom.replace(YD[0][-2:],g.domMonth[ins][0])
    else:
        pass
    
    
# 获取当天时间正在交易的期货主力合约函数
def get_future_code(symbol):
    future_code_list = {'A':'A8888.XDCE', 'AG':'AG8888.XSGE', 'AL':'AL8888.XSGE', 'AU':'AU8888.XSGE',
                        'B':'B8888.XDCE', 'BB':'BB8888.XDCE', 'BU':'BU8888.XSGE', 'C':'C8888.XDCE', 
                        'CF':'CF8888.XZCE', 'CS':'CS8888.XDCE', 'CU':'CU8888.XSGE', 'ER':'ER8888.XZCE', 
                        'FB':'FB8888.XDCE', 'FG':'FG8888.XZCE', 'FU':'FU8888.XSGE', 'GN':'GN8888.XZCE', 
                        'HC':'HC8888.XSGE', 'I':'I8888.XDCE', 'IC':'IC8888.CCFX', 'IF':'IF8888.CCFX', 
                        'IH':'IH8888.CCFX', 'J':'J8888.XDCE', 'JD':'JD8888.XDCE', 'JM':'JM8888.XDCE', 
                        'JR':'JR8888.XZCE', 'L':'L8888.XDCE', 'LR':'LR8888.XZCE', 'M':'M8888.XDCE', 
                        'MA':'MA8888.XZCE', 'ME':'ME8888.XZCE', 'NI':'NI8888.XSGE', 'OI':'OI8888.XZCE', 
                        'P':'P8888.XDCE', 'PB':'PB8888.XSGE', 'PM':'PM8888.XZCE', 'PP':'PP8888.XDCE', 
                        'RB':'RB8888.XSGE', 'RI':'RI8888.XZCE', 'RM':'RM8888.XZCE', 'RO':'RO8888.XZCE', 
                        'RS':'RS8888.XZCE', 'RU':'RU8888.XSGE', 'SF':'SF8888.XZCE', 'SM':'SM8888.XZCE', 
                        'SN':'SN8888.XSGE', 'SR':'SR8888.XZCE', 'T':'T8888.CCFX', 'TA':'TA8888.XZCE', 
                        'TC':'TC8888.XZCE', 'TF':'TF8888.CCFX', 'V':'V8888.XDCE', 'WH':'WH8888.XZCE', 
                        'WR':'WR8888.XSGE', 'WS':'WS8888.XZCE', 'WT':'WT8888.XZCE', 'Y':'Y8888.XDCE', 
                        'ZC':'ZC8888.XZCE', 'ZN':'ZN8888.XSGE','AP':'AP8888.XZCE'}
    try:
        return future_code_list[symbol]
    except:
        return 'WARNING: 无此合约'


# # 获取交易手数函数(无ATR版本）
def get_lots(cash,symbol):
    # 获取合约规模(Contract Size)，也称交易单位
    future_Contract_Size = {'A':10, 'AG':15, 'AL':5, 'AU':1000,
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
                        'ZC':100, 'ZN':5,'AP':10}
    future = get_dominant_future(symbol)
    # 获取价格list
    Price_dict = attribute_history(future,10,'1d',['open'])
    # 如果没有数据，返回
    if len(Price_dict) == 0:
        return
    else:
        # 获得最新开盘价，计算能够下单多少手
        open_price = Price_dict.iloc[-1]
    # 返回手数（价格*合约规模=名义价值）
    # 保证金使用，控制在33%
    # 合约保证金的表达式是：open_price*future_Contract_Size[symbol]*g.MarginRate
    return cash*0.33/(open_price*future_Contract_Size[symbol]*g.MarginRate)


# 获取金融期货合约到期日
def get_CCFX_end_date(fature_code):
    # 获取金融期货合约到期日
    return get_security_info(fature_code).end_date