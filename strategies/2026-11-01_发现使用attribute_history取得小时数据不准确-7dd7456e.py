# Clone from JoinQuant
# postId: 7dd7456ec61f9166386cd76557b71eb3
# backtestId: afe31b77432b00f00041bbd42bff4cf7
# title: 发现使用attribute_history取得小时数据不准确

import talib as tl
def initialize(context):
    log.info("start---")
    # 定义一个全局变量, 保存要操作的股票
    g.security = '002594.XSHE'
    g.period = 110
    # 0=SMA 1=EMA 2=WMA 3=DEMA 4=TEMA 5=TRIMA 6=KAMA 7=MAMA 8=T3
    g.maType = 0
    # 初始化此策略
    # 设置我们要操作的股票池, 这里我们只操作一支股票
    set_universe([g.security])

    run_daily(runHour, '09:30')
    run_daily(runHour, '10:30')
    run_daily(runHour, '11:30')
    run_daily(runHour, '14:00')

def runHour(context):
    log.info("----------------runHour---")
    stock = g.security
    hData = attribute_history(stock, g.period, unit='60m',
            fields=('close', 'volume', 'open', 'high', 'low'), skip_paused=True, df=False)
    
    close = hData['close']
    current_price = close[-1]
    print hData['open'], hData['high'], hData['low'], hData['close']
    log.info("--------------- O: %s  H: %s  L: %s  C: %s ",hData['open'][-1], hData['high'][-1], hData['low'][-1], hData['close'][-1])
