# Clone from JoinQuant
# postId: 65f61366dfac86711f8159133355fc4f
# backtestId: d5cbd903f9c34e4eb3111b1cb0896eb4
# title: 基于阻力的市场投资策略 -- 国泰君安量化报告的代码实现

import pandas as pd
import numpy as np
import math
import talib as tl
from datetime import datetime, timedelta
def initialize(context):
    # 定义一个全局变量, 保存要操作的股票
    g.security = '510300.XSHG'
    
    # 初始化此策略
    g.periodN = 120
    # 设置我们要操作的股票池, 这里我们只操作一支股票
    set_universe([g.security])
    
def isBullOrBear(stock) :
    hData = attribute_history(stock, g.periodN, unit='1d'
                    , fields=('close', 'volume', 'open', 'high', 'low')
                    , skip_paused=True
                    , df=False)
    
    volume = hData['volume']
    volume = np.array(volume, dtype='f8')
    close = hData['close']
    open = hData['open']
    high = hData['high']
    low = hData['low']
    
    pSum = 1
    nSum = 1
    lastClose = close[-1]
    for i, c in enumerate(close):
        v = volume[i]
        try :
            w1 = math.log(1/(abs(c - lastClose)/lastClose))
            w2 = math.log(1 + i) / math.log(1 + g.periodN)
            if c > lastClose :
                pSum = pSum + v * w1 * w2
            elif c < lastClose :
                nSum = nSum + v * w1 * w2
        except Exception as exc :
            # exclude the case price equal
            pass
            
    zuli = pSum / nSum
    if zuli > 1 :
        zuli = 1
        
    ret = None
    if zuli < 0.55 :
        ret = 'bull'
    elif zuli > 0.9 :
        ret = 'bear'
    
    return ret
    
# 每个单位时间(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)调用一次
def handle_data(context, data):
    security = g.security
    
    ret = isBullOrBear(security)
    
    # 取得当前的现金
    cash = context.portfolio.cash

    # 如果上一时间点价格高出五天平均价1%, 则全仓买入
    if context.portfolio.positions[security].total_amount == 0 and ret == 'bull':
        # 用所有 cash 买入股票
        order_value(security, cash)
        # 记录这次买入
        log.info("Buying %s" % (security))
    # 如果上一时间点价格低于五天平均价, 则空仓卖出
    elif context.portfolio.positions[security].total_amount > 0 and ret == 'bear':
        # 卖出所有股票,使这只股票的最终持有量为0
        order_target(security, 0)
        # 记录这次卖出
        log.info("Selling %s" % (security))
