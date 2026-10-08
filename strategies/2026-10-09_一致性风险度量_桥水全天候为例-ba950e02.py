# Clone from JoinQuant
# postId: ba950e028c3d59322b3dcc83985319a8
# backtestId: 0f2b90b63317183858cbdb8382fdadfc
# title: 一致性风险度量（桥水全天候为例）

import numpy as np
import talib
import pandas
import scipy as sp
import scipy.optimize
import datetime as dt
from scipy import linalg as sla
from scipy import spatial

def initialize(context):
    set_benchmark('511010.XSHG')
    #设置买卖手续费，万三，最小 5 元
    set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0003, min_cost=5))
    set_slippage(FixedSlippage(0.002))
    set_option('use_real_price', True)

    # 关闭部分log
    log.set_level('order', 'error')
    context.transactionRecord,context.trade_ratio,context.position = {}, {}, {}
    context.hold_periods, context.hold_cycle = 0, 30
    context.lastPortfolioValue = context.portfolio.portfolio_value
    
    g.quantlib = quantlib()

# initialize parameters
def fun_initialize(context):
    '''
    因为模拟交易时，会保留参数历史赋值，重新赋值需改名。
    为了避免参数变更后在模拟交易里不生效，单独赋值一次，
    需保留状态的参数，不能放此函数内
    '''
    
    #context.equity = ['510300.XSHG','510500.XSHG','159915.XSHE','510050.XSHG']
    context.equity = ['510300.XSHG']
    #context.commodities = ['160216.XSHE','518880.XSHG','162411.XSHE']
    context.commodities = ['518880.XSHG']
    #context.bonds = ['511010.XSHG','511220.XSHG']
    context.bonds = ['511010.XSHG']
    #context.moneyfund = ['513100.XSHG','513500.XSHG']
    context.moneyfund = ['513100.XSHG']

    context.confidencelevel = 2.58

    # 上市不足 60 天的剔除掉
    context.equity = g.quantlib.fun_delNewShare(context, context.equity, 60)
    context.commodities = g.quantlib.fun_delNewShare(context, context.commodities, 60)
    context.bonds = g.quantlib.fun_delNewShare(context, context.bonds, 60)
    context.moneyfund = g.quantlib.fun_delNewShare(context, context.moneyfund, 60)

    context.pool = context.equity + context.commodities + context.bonds + context.moneyfund

    # 统计交易资料
    for stock in context.pool:
        if stock not in context.transactionRecord:
            g.quantlib.fun_createTransactionRecord(context, stock)

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

    context.message += g.quantlib.fun_print_transactionRecord(context)
    send_message(context.message)

def handle_data(context, data):

    context.tradeRecord = ""

    if context.hold_periods == 0 or needRebalance(context):
        rebalance(context)
        context.hold_periods = context.hold_cycle
    else:
        context.tradeRecord = ""
        context.hold_periods -= 1

    fun_trade(context, context.trade_ratio)

    if context.tradeRecord != "":    # 如果打印记录不为空，则发微信
        message = "\n 今日调仓 \n"
        message += context.tradeRecord
        send_message(message)


def rebalance(context):

    trade_ratio = fun_caltrade_ratio(context)

    context.trade_ratio = trade_ratio

    for stock in list(context.trade_ratio.keys()):
        context.position[stock] = context.portfolio.positions[stock].price

def fun_caltrade_ratio(context):
    def __fun_calStockWeight(stocklist):
        __ratio = {}
        for stock in stocklist:
            __ratio[stock] = 1 / len(stocklist)
        
        return __ratio

    def __fun_getdailyreturn(stock, freq, lag):
        hStocks = history(lag, freq, 'close', stock, df=True)
        dailyReturns = hStocks.resample('D',how='last').pct_change().fillna(value=0, method=None, axis=0).values

        return dailyReturns

    def __fun_get_portfolio_ES(ratio, freq, lag, confidencelevel):
        if confidencelevel == 1.96:
            a = (1 - 0.95)
        elif confidencelevel == 2.06:
            a = (1 - 0.96)
        elif confidencelevel == 2.18:
            a = (1 - 0.97)
        elif confidencelevel == 2.34:
            a = (1 - 0.98)
        elif confidencelevel == 2.58:
            a = (1 - 0.99)
        elif confidencelevel == 5:
            a = (1 - 0.99999)
        else:
            a = (1 - 0.95)
        #dailyReturns = g.quantlib.fun_get_portfolio_dailyreturn(ratio, freq, lag)
        ES = 0
        if ratio:
            dailyReturns = __fun_getdailyreturn(list(ratio.keys())[0], freq, lag)
            dailyReturns_sort =  sorted(dailyReturns)
    
            count = 0
            sum_value = 0
            for i in range(len(dailyReturns_sort)):
                if i < (lag * a):
                    sum_value += dailyReturns_sort[i]
                    count += 1
            if count == 0:
                ES = 0
            else:
                ES = -(sum_value / (lag * a))

        return ES

    def __fun_calstock_risk_VaR(stocklist):
        __portfolio_VaR = 0
        #__stock_ratio = g.quantlib.fun_calStockWeight(stocklist)
        __stock_ratio = {}
        if stocklist:
            __stock_ratio[stocklist[0]] = 1
            dailyReturns = __fun_getdailyreturn(stocklist[0], '1d', 120)
            __portfolio_VaR = 1 * context.confidencelevel * np.std(dailyReturns)

            if isnan(__portfolio_VaR):
                __portfolio_VaR = 0

        return __portfolio_VaR, __stock_ratio
    
    def __fun_calstock_risk_ES(stocklist):
        __stock_ratio = {}
        if stocklist:
            __stock_ratio[stocklist[0]] = 1
        hStocks = history(1, '1d', 'close', stocklist, df=False)

        __portfolio_ES = __fun_get_portfolio_ES(__stock_ratio, '1d', 120, context.confidencelevel)
        if isnan(__portfolio_ES):
            __portfolio_ES = 0

        return __portfolio_ES, __stock_ratio

    def __fun_caltraderatio(trade_ratio, stocklist, __equity_ratio, position, total_position):
        for stock in stocklist:
            if stock in trade_ratio:
                trade_ratio[stock] += round((__equity_ratio[stock] * position / total_position), 3)
            else:
                trade_ratio[stock] = round((__equity_ratio[stock] * position / total_position), 3)
        return trade_ratio
    
    equity_ES, equity_ratio = __fun_calstock_risk_ES(context.equity)
    commodities_ES, commodities_ratio = __fun_calstock_risk_ES(context.commodities)
    bonds_ES, bonds_ratio = __fun_calstock_risk_ES(context.bonds)
    moneyfund_ES, moneyfund_ratio = __fun_calstock_risk_ES(context.moneyfund)

    max_ES = max(equity_ES, commodities_ES, bonds_ES, moneyfund_ES)
    
    equity_position, commodities_position, bonds_position, moneyfund_position = 0, 0, 0, 0
    if equity_ES:
        equity_position = max_ES / equity_ES
    if commodities_ES:
        commodities_position = max_ES / commodities_ES
    if bonds_ES:
        bonds_position = max_ES / bonds_ES
    if moneyfund_ES:
        moneyfund_position = max_ES / moneyfund_ES
    
    total_position = equity_position + commodities_position + bonds_position + moneyfund_position
    
    __ratio = {}
    
    __ratio = __fun_caltraderatio(__ratio, context.equity, equity_ratio, equity_position, total_position)
    __ratio = __fun_caltraderatio(__ratio, context.commodities, commodities_ratio, commodities_position, total_position)
    __ratio = __fun_caltraderatio(__ratio, context.bonds, bonds_ratio, bonds_position, total_position)
    __ratio = __fun_caltraderatio(__ratio, context.moneyfund, moneyfund_ratio, moneyfund_position, total_position)

    print __ratio
    return __ratio

def fun_trade(context, buyDict):

    def __fun_tradeStock(context, stock, ratio):
        total_value = context.portfolio.portfolio_value
        if stock in context.moneyfund:
            g.quantlib.fun_tradeBond(context, stock, total_value * ratio)
        else:
            curPrice = history(1,'1d', 'close', stock, df=False)[stock][-1]
            curValue = context.portfolio.positions[stock].total_amount * curPrice
            Quota = total_value * ratio
            deltaValue = abs(Quota - curValue)
            if deltaValue / Quota >= 0.25 and deltaValue > 1000:
                if Quota > curValue:
                    avg_cost = context.transactionRecord[stock]['avg_cost']
                    if curPrice > avg_cost:     # 如果亏损，不加仓
                        cash = context.portfolio.cash
                        if cash >= Quota * 0.25:
                            g.quantlib.fun_trade(context, stock, Quota)
                else:
                    g.quantlib.fun_trade(context, stock, Quota)

    buylist = list(buyDict.keys())

    hStocks = history(1, '1d', 'close', buylist, df=False)

    myholdstock = list(context.portfolio.positions.keys())
    portfolioValue = context.portfolio.portfolio_value

    # 已有仓位
    holdDict = {}
    hholdstocks = history(1, '1d', 'close', myholdstock, df=False)
    for stock in myholdstock:
        tmpW = round((context.portfolio.positions[stock].total_amount * hholdstocks[stock])/portfolioValue, 2)
        holdDict[stock] = float(tmpW)

    # 对已有仓位做排序
    tmpDict = {}
    for stock in holdDict:
        if stock in buyDict:
            tmpDict[stock] = round((buyDict[stock] - holdDict[stock]), 2)
    tradeOrder = sorted(tmpDict.items(), key=lambda d:d[1], reverse=False)

    # 先卖掉持仓减少的标的
    _tmplist = []
    for idx in tradeOrder:
        stock = idx[0]
        __fun_tradeStock(context, stock, buyDict[stock])
        _tmplist.append(stock)

    # 交易其他股票
    for i in range(len(buylist)):
        stock = buylist[i]
        if len(_tmplist) != 0 :
            if stock not in _tmplist:
                __fun_tradeStock(context, stock, buyDict[stock])
        else:
            __fun_tradeStock(context, stock, buyDict[stock])

def needRebalance(context):
    myholdstock = list(context.portfolio.positions.keys())

    for stock in myholdstock:
        curPrice = context.portfolio.positions[stock].price
        oldPrice = context.position[stock]
        if oldPrice != 0:
            deltaprice = abs(curPrice - oldPrice)
            if deltaprice / oldPrice > 0.15:
                return True
        
class quantlib():
    
    def __init__(self, _period = '1d'):
        '''
        周期 period  （支持’Xd’,’Xm’, X是一个正整数）
        '''
        
        #self.period = _period
        
        #self.context = None
        #self.data = None
        pass

    def fun_tradeBond(self, context, stock, Value):
        hStocks = history(1, '1d', 'close', stock, df=False)
        curPrice = hStocks[stock]
        curValue = float(context.portfolio.positions[stock].total_amount * curPrice)
        deltaValue = abs(Value - curValue)
        if deltaValue > (curPrice*100):
            if Value > curValue:
                cash = context.portfolio.cash
                if cash > (curPrice*100):
                    self.fun_trade(context, stock, Value)
            else:
                # 如果是银华日利，多卖 100 股，避免个股买少了
                if stock == '511880.XSHG':
                    Value -= curPrice*100
                self.fun_trade(context, stock, Value)

    # 剔除上市时间较短的产品
    def fun_delNewShare(self, context, equity, deltaday):
        deltaDate = context.current_dt.date() - dt.timedelta(deltaday)
    
        tmpList = []
        for stock in equity:
            if get_security_info(stock).start_date < deltaDate:
                tmpList.append(stock)
    
        return tmpList

    def fun_trade(self, context, stock, value):
        context.tradeRecord += stock + " 调仓到 " + str(round(value, 2)) + "\n"
        self.fun_setCommission(context, stock)
        order_target_value(stock, value)
        self.fun_record(context, stock)

    def fun_setCommission(self, context, stock):
        if stock in context.equity or stock in context.commodities:
            set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0003, min_cost=5))
        elif (stock in context.moneyfund) or (stock in context.bonds):
            set_commission(PerTrade(buy_cost=0.0000, sell_cost=0.0000, min_cost=0))
        else:
            set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))

    def fun_record(self, context, stock):
        tmpDict = context.transactionRecord.copy()
        #myPrice = history(1, '1d', 'close', stock, df=False)[stock]
        myPrice = context.portfolio.positions[stock].price
        myAmount = tmpDict[stock]['amount']
        newAmount = context.portfolio.positions[stock].total_amount
        myAvg_cost = tmpDict[stock]['avg_cost']
        if myAmount != newAmount:
            # 买入
            if myAmount <= newAmount:
                myAvg_cost = ((myAvg_cost * myAmount) + myPrice * (newAmount - myAmount)) / newAmount
                #context.position[stock] = context.portfolio.positions[stock].price
                tmpDict[stock]['buytimes'] += 1
            # 卖光
            elif newAmount == 0:
                if myPrice >= myAvg_cost:
                    tmpDict[stock]['win'] += 1
                else:
                    tmpDict[stock]['loss'] += 1
                myMargin = (myPrice - myAvg_cost) * myAmount
                if myMargin < 0:
                    #tmpDict[stock]['totalloss'] + float(round(myMargin, 2))
                    if myMargin <= tmpDict[stock]['maxloss']:
                        tmpDict[stock]['maxloss'] = float(round(myMargin, 2))
                        tmpDict[stock]['maxlossdate'] = context.current_dt
    
                tmpDict[stock]['Margin'] += float(round(myMargin,2))
                tmpDict[stock]['selltimes'] += 1
            # 没卖光
            elif myAmount > newAmount:
                myAvg_cost = ((myAvg_cost * myAmount) - (myPrice * (myAmount - newAmount))) / newAmount
                #context.position[stock] = context.portfolio.positions[stock].price
                tmpDict[stock]['selltimes'] += 1
    
        context.tradeRecord += stock + " 持股从 " + str(myAmount) + " 变为 " + str(newAmount) + \
                                " 占比 " + str(100 * round((myPrice * newAmount) / context.portfolio.portfolio_value,2)) + "%\n"
        
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
        
    def fun_createTransactionRecord(self, context, stock):
        context.transactionRecord[stock] = {'amount':0, 'avg_cost':0, 'buytimes':0, \
                'selltimes':0, 'win':0, 'loss':0, 'maxloss':0, 'maxlossdate':0, 'Margin':0, \
                'standPrice':0}
    
    def fun_print_transactionRecord(self, context):
        tmpDict = context.transactionRecord.copy()
        tmpList = list(tmpDict.keys())
        message = ""
        message = "\n" + "stock, Win, loss, buytimes, selltimes, Margin, maxloss, maxlossdate, avg_cost\n"
        for stock in tmpList:
            message += stock + ", "
            message += str(tmpDict[stock]['win']) + ", " + str(tmpDict[stock]['loss']) + " , "
            message += str(tmpDict[stock]['buytimes']) + ", " + str(tmpDict[stock]['selltimes']) + ", "
            message += str(tmpDict[stock]['Margin']) + ", "
            message += str(tmpDict[stock]['maxloss'])+ ", " + str(tmpDict[stock]['maxlossdate']) + ", "
            message += str(tmpDict[stock]['avg_cost']) + "\n"
        message += "Returns = " + str(round(context.portfolio.returns, 5) * 100) + "%\n"
        
        context.transactionRecord = tmpDict.copy()
        #print message
        return message