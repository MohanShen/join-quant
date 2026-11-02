# Clone from JoinQuant
# postId: 4b6d969b4cdd19614f455ded091750f8
# backtestId: 9fd964ac3724e56d51ac76c5961d6d78
# title: 期货RU、CU个别时段回测不能开仓或者不能平仓是怎么回事

# 导入函数库
from jqdata import *
import json
from six import StringIO
from jqlib.technical_analysis import *
import pandas as pd
import numpy as np
import datetime

# 1. 入场条件：过去两天的价格波动幅度超过过去n天的平均真实波幅的1倍，认为达到入场条件。当天价格出现这一波动，立即下单，不用等到第二天。
#也就是说，入场是要在分钟级别进行检测。
# 2. 出场条件：
    #初始停价：买入价格基础上2倍真实波幅
    #跟踪止损：分钟级别按照最高价/最低价+/-2倍真实波幅作为跟踪止损。
#其他：出现合约移仓时，终止当前合约，以新的合约波动幅度信息重新进行开仓。这一动作在while_open函数下进行。
#开仓，平仓在running 函数下进行
#头寸计算：按照真实波幅计算，每次使用资金的1%。


## 初始化函数，设定基准等等
def initialize(context):
    # 设置参数
    set_params(context)
    # 初始化标的
    g.future_index = get_future_index(g.future_code)
    log.info('inital g.future_index is ',g.future_index)
    g.account_amount= context.portfolio.total_value
    # 设定沪深300作为基准
    set_benchmark(g.future_index)
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 过滤掉order系列API产生的比error级别低的log
    log.set_level('order', 'error')
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')

    ### 期货相关设定 ###
    
    # 设定账户为金融账户
    set_subportfolios([SubPortfolioConfig(cash=context.portfolio.starting_cash, type='index_futures')])
    # 期货类每笔交易时的手续费是：买入时万分之0.23,卖出时万分之0.23,平今仓为万分之23
    set_order_cost(OrderCost(open_commission=0.000023, close_commission=0.000023,close_today_commission=0.0023), type='index_futures')
    # 设定保证金比例
    set_option('futures_margin_rate', 0.15)

    # 设置期货交易的滑点
    set_slippage(StepRelatedSlippage(2))
    # 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'IF1512.CCFX'或'IH1602.CCFX'是一样的）
      # 开盘前运行
    run_daily( before_market_open, time='before_open', reference_security=get_future_index(g.future_code))
      # 盘中运行进行止损
    run_daily( running, time='every_bar', reference_security=get_future_index(g.future_code))  
      # 收盘后运行
    run_daily( after_market_close, time='after_close', reference_security=get_future_index(g.future_code))

def set_params(context):
    g.begindate= context.current_dt
    g.enddate= '2017-09-29'
    # 计算ATR的时间窗口
    g.window = 5
    # 最近一次交易的合约
    g.last_future = None
    # 合约 
    g.future_code = 'RU'
    # 记录每次交易交易合约、开仓日期、初始风险、平仓日期、平仓盈利情况、
    g.trade_history = pd.DataFrame(columns=['future', 'open_date', 'L/S','open_unit','open_price','init_R','account_total_open','close_date', 'clear_unit','clear_price', 'move', 'account_total_close'])
    g.Record = pd.DataFrame(columns=['future', 'open_date', 'L/S','open_unit','open_price','init_R','account_total_open','close_date', 'clear_unit','clear_price',  'move','account_total_close'])
    # 记录最近一次的管道突破趋势信号
    g.trend_signal= 0
    # 记录跟踪止损的最新价格
    g.follow_stop_price=0
    # 记录初始停价
    g.init_stop=0
    g.future=None
    #记录主力合约是否变更
    g.dom_change=0
    #记录每天开盘时计算的ATR值，用于不同函数之间
    g.ATR=0
    #记录移仓的平仓订单号
    g.move=[]
    g.unit=0
    #设置止盈启动价格水平
    g.stop_win_level=0
#===================================================================================================================================================================    
## 开盘前运行函数。     
#===================================================================================================================================================================
def before_market_open(context):
    # 输出运行时间
    g.future_index = get_future_index(g.future_code)
    log.info('函数运行时间(before_market_open)：'+ str(context.current_dt.time()))

    #计算ATR
    future = get_dominant_future(g.future_code)
    #获取当天持仓信息，如果持仓为空，则所有信息返回为0
    current_short_position = context.portfolio.short_positions#[future].total_amount
    current_short_side = context.portfolio.short_positions#[future].side
    current_long_position = context.portfolio.long_positions#[future].total_amount
    current_long_side = context.portfolio.long_positions#[future].side
    log.info('current_long_position',current_long_position)
    log.info('current_short_position',current_short_position)
#

#===================================================================================================================================================================        
## 盘中运行开仓、止损、止盈函数
#===================================================================================================================================================================
def running(context):
    date2= context.current_dt
    future = get_dominant_future(g.future_code)

    month =  context.current_dt.month
    day = context.current_dt.day
    hour = context.current_dt.hour
    minute = context.current_dt.minute
    current_data= get_current_data()
    if month==4 and day == 21 and hour==9 and minute==8:
        log.info('aaa')
        new_order=order_target(future,1, side='short' )
        log.info (new_order)
        
    if month==8 and day== 13 and hour== 9 and minute==2:
        log.info('bbb')
        new_order2 = order_target(future,1,side='long')
        log.info (new_order2)
    g.init_stop= 18800.7452
    if month==8 and day== 17:
        if current_data[future].last_price < g.init_stop:
            close_order=order_target(future,0,side='long')
            if future not in context.portfolio.long_positions.keys():
                log.info( '多头初始止损成功:',context.current_dt.time(),future)
                log.info('----------------------------------------------------------')
            else:
                log.info('!!!!! 多头初始止损平仓不成功')    

#===================================================================================================================================================================        
## 收盘后运行函数
#     g.trade_history=  pd.DataFrame(columns=['future', 'open_date', 'L/S','open_unit','open_price','init_R','account_total_open','close_date',
#     'clear_unit','clear_price', 'account_total_close'])
#===================================================================================================================================================================
def after_market_close(context):

    log.info('end of the day')
#===================================================================================================================================================================
########################## 自定义函数 #################################
#   records=  pd.DataFrame(columns=['future', 'open_date', 'L/S','open_unit','open_price','init_R',
#                                   'account_total_open','close_date', 'clear_unit','price', 'account_total_close'])
#===================================================================================================================================================================

def get_ATR(price_list,T):
    TR_list = [
        max(
            price_list['high'].iloc[i]-price_list['low'].iloc[i],
            abs(price_list['high'].iloc[i]-price_list['close'].iloc[i-1]),
            abs(price_list['close'].iloc[i-1]-price_list['low'].iloc[i])
            ) for i in range(1,T+1)] 
            # price_list中包括了前n+1天的价格数据。第一个i=1,取了前n天的高低价之差，以及高低价分别于前n+1天的收盘
            #使用[] 直接得到了一个列表
    
    ATR = np.array(TR_list).mean()
    return ATR

def get_unit(cash,ATR,future):
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
    #log.info('future_coef_list[symbol]=',future_coef_list[symbol])
    contract_unit =  get_CMValue(future)
    unit=cash*0.01/(2*ATR*contract_unit)
    #unit=cash*0.01/(2*ATR*future_coef_list[symbol])
    #log.info('unit=',unit)
    return unit
########################## 获取期货合约信息，请保留 #################################
# 获取当天时间正在交易的期货主力合约
def get_future_index(symbol):
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
                        'ZC':'ZC8888.XZCE', 'ZN':'ZN8888.XSGE'}
    try:
        return future_code_list[symbol]
    except:
        return 'WARNING: 无此合约'

# 获取当前交易合约的合约乘数（合约交易单位）
def get_CMValue(future):
    """获取期货合约的合约乘数，郑商所编码不同，需要处理"""
    from jqdata import jy
    if future[-4:] != 'XZCE':
        future = future[:-5]
    else:
        future = future[:-9] + future[-8:-5]
    q = query(jy.Fut_ContractMain.CMValue).filter(jy.Fut_ContractMain.ContractCode == future)
    result = jy.run_query(query_object=q).to_dict("record")
    #log.info(result[0]['CMValue'])
    contract_unit = result[0]['CMValue']
    return contract_unit

# 获取金融期货合约到期日
def get_CCFX_end_date(future_code):
    # 获取金融期货合约到期日
    return get_security_info(future_code).end_date

