# Clone from JoinQuant
# postId: b508712e8d6cbcbdb606e1d189f71b2e
# backtestId: c0da463e8afcd053609ff300d9490956
# title: 双线RSI择时轮动策略

import math
import talib as tl

fastRSI = 20
slowRSI = 60

# 策略参考标准
set_benchmark('000300.XSHG')
# 设置手续费，买入时万分之三，卖出时万分之三加千分之一印花税, 每笔交易最低扣5块钱
set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))

def initialize(context):
    # 定义轮动的股票A是做空，B是做多
    g.securityA = '511010.XSHG' #150144.XSHE
    g.securityB = '150019.XSHE'
    # 设置我们要操作的股票池
    set_universe([g.securityB, g.securityA])

# 每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)调用一次
def handle_data(context, data):
    securityA = g.securityA
    securityB = g.securityB
    # 取得历史收盘价格
    hData = history(max(slowRSI, fastRSI)*2, '1d', 'close', [securityB])
    
    # 计算快慢RSI的值
    hData['RSI_F'] = tl.RSI(hData[securityB].values, timeperiod=fastRSI)
    hData['RSI_S'] = tl.RSI(hData[securityB].values, timeperiod=slowRSI)
    hData['isFgtS'] = hData['RSI_F'] > hData['RSI_S']
    
    '''
    慢速RSI 在55以上时，单边上涨市场，快速RSI上穿慢速RSI即可建仓
    慢速RSI 在55以下时，调整震荡市场，谨慎入市，取连续N天快速RSI大于慢速RSI建仓
    慢速RSI 在60以上时，牛市，无需减仓操作持仓即可
    '''
    rsiS = hData.iloc[-1].RSI_S
    rsiF = hData.iloc[-1].RSI_F
    bsFlag = ''
    if rsiS > 55 and hData.iloc[-1].isFgtS:
        bsFlag = '+'
    elif rsiS <= 55 \
        and hData.iloc[-1].isFgtS and hData.iloc[-2].isFgtS \
        and hData.iloc[-3].isFgtS and hData.iloc[-4].isFgtS \
        and hData.iloc[-5].isFgtS :
        bsFlag = '+'
    elif hData.iloc[-1].isFgtS == False and rsiS < 60 :
        bsFlag = '-'
    
    # 取得当前价格
    current_priceA = data[securityA].price
    current_priceB = data[securityB].price
    # 当前持仓量
    currentBalanceA = context.portfolio.positions[securityA].amount
    currentBalanceB = context.portfolio.positions[securityB].amount

    if bsFlag == '+' and currentBalanceB == 0 and currentBalanceA > 0:
        # 如果A有持仓，清空
        order_target(securityA, 0)
        # 记录这次卖出
        log.info("Selling %s" % (securityA))

    # 取得当前的现金
    cash = context.portfolio.cash
    
    # 全仓买入B
    if bsFlag == '+' and currentBalanceB == 0:
        # 计算可以买多少只股票
        number_of_shares = int(cash/current_priceB)
        # 购买量大于0时，下单
        if number_of_shares > 0:
            # 买入股票
            order(securityB, +number_of_shares)
            # 记录这次买入
            log.info("Buying %s" % (securityB))
    elif bsFlag == '-' and currentBalanceB > 0:
        # 卖出B
        # 卖出所有股票,使这只股票的最终持有量为0
        order_target(securityB, 0)
        # 记录这次卖出
        log.info("Selling %s" % (securityB))
        
    if bsFlag <> '+' and currentBalanceA == 0:
        # 轮换A
        cash = context.portfolio.cash
        if math.isnan(current_priceA) :
            current_priceA = cash
        #cash = 0
        # 计算可以买多少只股票
        number_of_shares = int(cash/current_priceA)
        # 购买量大于0时，下单
        if number_of_shares > 0:
            # 买入股票
            order(securityA, +number_of_shares)
            # 记录这次买入
            log.info("Buying %s" % (securityA))
            
    # 画出当前的价格
    record(rsiS=rsiS, rsiF=rsiF)
    #record(current_priceA=current_priceA, current_priceB=current_priceB)
