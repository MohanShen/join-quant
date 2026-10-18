# Clone from JoinQuant
# postId: d2aa73992810721e6aa2bc814474bb6a
# backtestId: 6b09f8c812384fd89f642cf29347cc6a
# title: 扒一扒常见技术指标的大盘择时效果

# 导入函数库
from jqdata import *
from jqlib.technical_analysis import *

# 初始化函数，设定基准等等
def initialize(context):
    g.stock = '000905.XSHG'
    # 设定沪深300作为基准
    set_benchmark(g.stock)
    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.0, open_commission=0.0, close_commission=0.0, min_commission=5), type='stock')
    # 设定滑点
    set_slippage(FixedSlippage(0.0))
    # 开盘时运行
    run_daily(market_open, time='open', reference_security=g.stock)
    g.tech = 'EMA'
    g.para1 = 21
    g.para2 = 3
    g.para3 = 3
## 开盘时运行函数
def market_open(context):
    #security_list1 = get_index_stocks('000016.XSHG')
    security_list1 = g.stock
    # 计算并输出当前的市场多空信号
    signal = get_signal(context,security_list1)
    total_value = context.portfolio.total_value
    
    if signal > 0:
        print('%s指标满足开仓条件'%g.tech)
        order_target_value(security_list1, total_value)
    elif signal < 0:
        print('%s指标满足空仓条件'%g.tech)
        order_target_value(security_list1, 0)
    
def get_signal(context,stock):
    #获取最新价格
    all_data = get_current_data()
    price_now = all_data[stock].last_price
    
    #满仓状态
    if g.tech == 'None':
        return 1
    
    #macd指标
    elif g.tech == 'MACD':
        macd = MACD(stock, check_date=context.previous_date,SHORT=11,LONG=21,MID=9)
        macd_v = macd[2][stock]
        if macd_v > 0:
            return -1
        elif macd_v<0:
            return 1
        else:
            return 0
            
    #kdj指标择时
    elif g.tech == 'KDJ':
        K,D,J = KDJ(stock, check_date=context.previous_date, N =g.para1, M1=g.para2, M2=g.para3) 
        K,D,J = K[stock],D[stock],J[stock]
        print(K,D,J)
        if K > D:
            return -1
        elif K<D:
            return 1
        else:
            return 0
            
    #CCI指标进行择时
    elif g.tech == 'CCI':
        cci = CCI(stock, check_date=context.previous_date, N=14)
        cci =  cci[stock]
        if cci > 60:
            return 1
        elif cci <-60:
            return -1
        else:
            return 0
            
    #RSI指标进行择时
    elif g.tech == 'RSI':
        rsi = RSI(stock, check_date=context.previous_date, N1=14)
        rsi =  rsi[stock]
        if rsi > 60:
            return 1
        elif rsi <40:
            return -1
        else:
            return 0
            
    #布林带指标择时
    elif g.tech == 'BOLL':
        upperband, middleband, lowerband = Bollinger_Bands(stock, check_date=context.previous_date, timeperiod=int(g.para1), nbdevup=2, nbdevdn=2)
        if price_now > upperband[stock]:
            return 1
        elif price_now < middleband[stock]:
            return -1
        else:
            return 0
            
    #指数单均线指标择时
    elif g.tech == 'EMA':
        ema = EMA(stock, check_date=context.previous_date, timeperiod=int(g.para1))
        if price_now > ema[stock]:
            return 1
        elif price_now < ema[stock]:
            return -1
        else:
            return 0
            
    #指数双均线指标择时
    elif g.tech == 'EMA1':
        ema_long = EMA(stock, check_date=context.previous_date, timeperiod=30)
        ema_short = EMA(stock, check_date=context.previous_date, timeperiod=11)
        if ema_short[stock] > ema_long[stock]:
            return 1
        elif ema_short[stock] < ema_long[stock]:
            return -1
        else:
            return 0
            
    #简单单均线指标择时
    elif g.tech == 'MA':
        ma = MA(stock, check_date=context.previous_date, timeperiod=21)
        if price_now > ma[stock]:
            return 1
        elif price_now < ma[stock]:
            return -1
        else:
            return 0
            
    #简单双均线指标择时
    elif g.tech == 'MA1':
        ma_long = MA(stock, check_date=context.previous_date, timeperiod=21)
        ma_short = MA(stock, check_date=context.previous_date, timeperiod=5)
        if ma_short[stock] > ma_long[stock]:
            return 1
        elif ma_short[stock] < ma_long[stock]:
            return -1
        else:
            return 0
            
    #简单双均线指标择时
    elif g.tech == 'TRIX':
        trix,matrix = TRIX(stock, check_date=context.previous_date, N = 12, M = 9)
        if trix[stock] > matrix[stock]:
            return 1
        elif trix[stock] < matrix[stock]:
            return -1
        else:
            return 0
    
    #乖离率指标
    elif g.tech == 'BIAS':
        trix,matrix = TRIX(stock, check_date=context.previous_date, N = 12, M = 9)
        if trix[stock] > matrix[stock]:
            return 1
        elif trix[stock] < matrix[stock]:
            return -1
        else:
            return 0

    #PSY心理线指标
    elif g.tech == 'PSY':
        psy = PSY(stock,check_date=context.previous_date, timeperiod=14)[stock]
    
        if psy<40:
            return 1
        elif psy >60:
            return -1  
        else:
            return 0

    #BBI指标择时
    elif g.tech == 'BBI':
        bbi = BBI(stock, check_date=context.previous_date, timeperiod1=3, timeperiod2=6, timeperiod3=12, timeperiod4=24)
        if price_now > bbi[stock]:
            return 1
        elif price_now < bbi[stock]:
            return -1
        else:
            return 0