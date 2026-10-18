# Clone from JoinQuant
# postId: c083c1097dac0349b367aa4662deb203
# backtestId: 36d37533ce024eaf0c3da23891bbd778
# title: 头寸调整策略 —— 波动性百分比调仓

import numpy as np
import talib
import pandas
import scipy as sp
import scipy.optimize
import datetime as dt
from scipy import linalg as sla
from scipy import spatial

def initialize(context):
    #用沪深 300 做回报基准
    set_benchmark('159919.XSHE')
    #设置买卖手续费，万三，最小 5 元
    set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0003, min_cost=5))
    set_option('use_real_price', True)

    # 关闭部分log
    log.set_level('order', 'error')
    # 定义全局变量, 保存要操作的证券
    context.transactionRecord = {}

# initialize parameters
def fun_initialize(context):
    '''
    因为模拟交易时，会保留参数历史赋值，重新赋值需改名。
    为了避免参数变更后在模拟交易里不生效，单独赋值一次，
    需保留状态的参数，不能放此函数内
    '''
    context.positionAdjustFactor = 0.04
    # 定义股票池
    context.indexETF = ['159919.XSHE','159915.XSHE','518880.XSHG']

    # 上市不足 60 天的剔除掉
    context.indexETF = fun_delNewShare(context, context.indexETF, 100)

    context.pool = context.indexETF

    # 统计交易资料
    for stock in context.pool:
        if stock not in context.transactionRecord:
            context.transactionRecord[stock] = {'amount':0, 'avg_cost':0, 'buytimes':0, \
                'selltimes':0, 'win':0, 'loss':0, 'maxloss':0, 'maxlossdate':0, 'Margin':0, \
                'standPrice':0}

def before_trading_start(context):
    fun_initialize(context)
    
    # 此段代码仅用于发微信，可以跳过
    context.message = ""
    context.message += "Returns（盘前）：" + str(round(context.portfolio.returns,5)*100) + "%\n"
    context.hold = {}
    for stock in context.pool:
        context.hold[stock] = context.portfolio.positions[stock].total_amount

def after_trading_end(context):
    # 此段代码仅用于发微信，可以跳过
    message = ""
    for stock in context.pool:
        beforeAmount = context.hold[stock]
        afterAmount = context.portfolio.positions[stock].total_amount
        if beforeAmount == afterAmount:
            message += stock + " : " + str(afterAmount) + "\n"
        elif beforeAmount < afterAmount:
            message += stock + " : " + str(afterAmount) + "(+" + str(afterAmount - beforeAmount) + ")\n"
        else:
            message += stock + " : " + str(afterAmount) + "(" + str(afterAmount - beforeAmount) + ")\n"
            
    message += "Returns（盘后）：" + str(round(context.portfolio.returns,5)*100) + "%"
    context.message += message

    context.message += fun_print_transactionRecord(context)
    send_message(context.message)

def handle_data(context, data):
    buylist, selllist = fun_selectinETF(context)
    fun_sell_action(context, selllist)

    fun_tradeETF(context, buylist)
    
def fun_tradeETF(context, buylist):
    # 买入在 buylist 里的股票
    if buylist !=[]:
        fun_trade(context, buylist)

def fun_selectinETF(context):
    buylist, selllist = [],[]
    
    # 在 indexETF 里甄选
    for stock in context.indexETF:
        EMVFactor = fun_calEMV(stock)
        myValue = EMVFactor

        if myValue >= 1:
            buylist.append(stock)
        elif myValue <= -1:
            selllist.append(stock)
    
    myholdstock = list(context.portfolio.positions.keys())
    for stock in myholdstock:
        # 清掉不在股票池里的股票
        if stock not in context.pool:
            selllist.append(stock)
        # 补回不在买点，但已持有的
        elif (stock not in buylist) and (stock not in selllist):
            buylist.append(stock)

    return buylist, selllist

def fun_trade(context, buylist):
    QuotaFactor = 0.2
    #Value = context.portfolio.portfolio_value / len(buylist)
    Value = fun_calPosition(context, buylist) / len(buylist)

    hStocks = history(1, '1m', 'close', buylist, df=False)
    for i in range(len(buylist)):
        stock = buylist[i]
        stockValue = context.portfolio.positions[stock].total_amount * hStocks[stock]
        # 交易金额小于预设值，则不交易，避免频繁调仓
        if abs(Value - stockValue) > Value * QuotaFactor:
            fun_setCommission(context, stock)
            order_target_value(stock, Value)
            fun_record(context, stock)

def fun_calPosition(context, buylist):
    # 每次调仓，用 positionAdjustFactor 来控制承受的风险，最大损失为总仓位 * positionAdjustFactor
    positionAdjustFactor = context.positionAdjustFactor
    positionAdjustValue = context.portfolio.portfolio_value * positionAdjustFactor

    hStocks = history(1, '1m', 'close', buylist, df=False)

    positionATR = 0
    positionPrice = 0
    curRisk = 0
    # 计算组合后的 ATR，此处假设资金是平均分配。
    for stock in buylist:
        curATR = 2*fun_getATR(stock)
        curAmount = 1 / (hStocks[stock] * len(buylist))    # 1个单位的资金，分配时，该股票可以买多少股
        curRisk += curAmount * curATR                    # 1单位资金时，该股票上的实际风险敞口

    positionValue = float(positionAdjustValue / curRisk)
    if positionValue > context.portfolio.portfolio_value:
        positionValue = context.portfolio.portfolio_value

    return positionValue

def fun_getATR(stock):
    ATRlag = 14

    # 计算ATR及Keltner Band 
    hStock = attribute_history(stock, ATRlag+10, '1d', ('close','high','low') , df=False)
    close_ATR = fun_normalizeData(hStock['close'], "list")
    high_ATR = fun_normalizeData(hStock['high'], "list")
    low_ATR = fun_normalizeData(hStock['low'], "list")
    ATR = talib.ATR(high_ATR, low_ATR, close_ATR, timeperiod=ATRlag)

    return ATR[-1]

# 卖股票函数
def fun_sell_action(context, selllist):
    myholdstock = list(context.portfolio.positions.keys())

    for stock in selllist:
        if stock in myholdstock:
            fun_setCommission(context, stock)
            order_target(stock, 0)
            fun_record(context, stock)
            print("Stoploss ", stock)
            
def fun_setCommission(context, stock):
    if (stock in context.indexETF) or (stock in context.commondityETF):
        set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0003, min_cost=5))
    elif (stock in context.moneyfund) or (stock in context.bonds):
        set_commission(PerTrade(buy_cost=0.0000, sell_cost=0.0000, min_cost=0))
    else:
        set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))

# 计算 EMV Factor
def fun_calEMV(stock):
    # 设定 EMV Factor
    n = 20
    m = 23
    EMVlag = 60
    
    hStock = attribute_history(stock, EMVlag, '1d', ('high','low','volume'), skip_paused=True)

    _EMList = []
    for i in range(EMVlag):
        if i > (n-1):
            high_today = hStock['high'][i]
            low_today = hStock['low'][i]
            volume_today = hStock['volume'][i]
            high_yesterday = hStock['high'][i-1]
            low_yesterday = hStock['low'][i-1]

            _tmpVolume = talib.SMA(np.array(hStock['volume'][(i-n+1):(i+1)]), n)[-1]/volume_today
                
            _MID = 100*(high_today + low_today - high_yesterday - low_yesterday)/(high_today + low_today)
            if high_today == low_today:
                _temp = 0
            else:
                _temp = _MID * _tmpVolume * (high_today-low_today)
            _high = talib.SMA(np.array(hStock['high'][(i-n+1):(i+1)]), n)[-1]
            _low = talib.SMA(np.array(hStock['low'][(i-n+1):(i+1)]), n)[-1]
            _EM = (_temp/(_high-_low))
                
        else:
            _EM = 0
        _EMList.append(_EM)

    hStock['_EM'] = _EMList
    hStock['_EMV'] = talib.SMA(np.array(hStock['_EM']), n)
        
    MAEMV = talib.SMA(np.array(hStock['_EMV']), m)[-1]

    EMVFactor = 0
    EMV = hStock['_EMV'][-1]
    oldEMV = hStock['_EMV'][-2]

    if EMV > 0 and oldEMV < 0 and MAEMV > 0:
        EMVFactor = 2
    elif EMV < 0 and oldEMV >0:
        EMVFactor = -2
    elif EMV < 0:
        EMVFactor = -1
    elif EMV > 0:
        EMVFactor = 1

    return EMVFactor

def fun_record(context, stock):
    tmpDict = context.transactionRecord.copy()
    myPrice = history(1, '1m', 'close', stock, df=False)[stock]
    myAmount = tmpDict[stock]['amount']
    newAmount = context.portfolio.positions[stock].total_amount
    myAvg_cost = tmpDict[stock]['avg_cost']
    if myAmount != newAmount:
        # 买入
        if myAmount <= newAmount:
            myAvg_cost = ((myAvg_cost * myAmount) + myPrice * (newAmount - myAmount)) / newAmount
            tmpDict[stock]['buytimes'] += 1
        # 卖光
        elif newAmount == 0:
            if myPrice >= myAvg_cost:
                tmpDict[stock]['win'] += 1
            else:
                tmpDict[stock]['loss'] += 1
            myMargin = (myPrice - myAvg_cost) * myAmount
            if myMargin <= tmpDict[stock]['maxloss']:
                tmpDict[stock]['maxloss'] = float(myMargin)
                tmpDict[stock]['maxlossdate'] = context.current_dt

            tmpDict[stock]['Margin'] += float(myMargin)
            tmpDict[stock]['selltimes'] += 1
        # 没卖光
        elif myAmount > newAmount:
            myAvg_cost = ((myAvg_cost * myAmount) - (myPrice * (myAmount - newAmount))) / newAmount
            tmpDict[stock]['selltimes'] += 1

    # renew after trade
    if newAmount == 0:
        myAvg_cost = 0
        tmpDict[stock]['standPrice'] = 0
    elif myAvg_cost > tmpDict[stock]['standPrice']:
        tmpDict[stock]['standPrice'] = float(myAvg_cost)

    myAmount = newAmount
    tmpDict[stock]['amount'] = float(myAmount)
    tmpDict[stock]['avg_cost'] = float(myAvg_cost)
    context.transactionRecord =  tmpDict.copy()

def fun_print_transactionRecord(context):
    tmpDict = context.transactionRecord.copy()
    tmpList = list(tmpDict.keys())
    message = ""
    message = "\n" + "stock, Win, loss, buytimes, selltimes, Margin, maxloss, maxlossdate\n"
    for stock in tmpList:
        message += stock + ", " + str(tmpDict[stock]['win']) + ", " + str(tmpDict[stock]['loss']) + " , "
        message += str(tmpDict[stock]['buytimes']) + ", " + str(tmpDict[stock]['selltimes']) + ", "
        message += str(tmpDict[stock]['Margin']) + ", "
        message += str(tmpDict[stock]['maxloss'])+ ", " + str(tmpDict[stock]['maxlossdate']) + "\n"
    print message
    return message

# 剔除上市时间较短的产品
def fun_delNewShare(context, equity, deltaday):
    deltaDate = context.current_dt.date() - dt.timedelta(deltaday)

    tmpList = []
    for stock in equity:
        if get_security_info(stock).start_date < deltaDate:
            tmpList.append(stock)

    return tmpList
    
def fun_normalizeData(myData, myType):
    # 去极值
    if myType == "list":
        std = np.std(myData)
        MA = np.mean(myData)
        for i in range(len(myData)):
            if myData[i] > MA + 3*std:
                myData[i] = MA + 3*std
            elif myData[i] < MA - 3*std:
                myData[i] = MA - 3*std
    
    if myType == "df":
        tmpList = list(myData.keys())
        for stock in tmpList:
            std = np.std(myData[stock])
            MA = np.mean(myData[stock])
            for i in range(len(myData)):
                if myData[stock][i] > MA + 3*std:
                    myData[stock][i] = MA + 3*std
                elif myData[stock][i] < MA - 3*std:
                    myData[stock][i] = MA - 3*std
    
    return myData