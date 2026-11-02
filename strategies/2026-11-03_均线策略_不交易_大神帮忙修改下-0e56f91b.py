# Clone from JoinQuant
# postId: 0e56f91b3e3590b1ab2eb95f3f46ea51
# backtestId: 3b4d3324b1e1d899df031a31f31920fc
# title: 均线策略，不交易，大神帮忙修改下。

# 期货策略模版
# 导入库包
import talib
import numpy as np
import pandas as pd
# 初始化函数,全局只运行一次
def init(context):

    #设立商品期货子账户,其中stock为0，future为100000
    set_subportfolios([{"cash": 0, "type": 'stock'},{"cash": 1000000, "type": "future"}])

    # 打印日志
    log.info('策略开始运行,初始化函数全局只运行一次')

    # 设置期货每笔交易的手续费为十万分之四十五(按成交额计算并扣除,期货交易不需要缴纳税费)
    set_commission(PerShare(type='future',cost=0.000045))

    # 设置期货保证金,第一个参数做多保证金8%，第二个参数做空保证金9%
    set_margin_rate('NI',0.08,0.09)

    # 螺纹钢主连作为基准
    set_benchmark("NI2003")

    # 回测区间、初始资金、运行频率请在右上方设置,设置子账户后,初始资金必须等于总账户资金之和

#每日开盘前被调用一次,用于储存自定义参数、全局变量等,注意：商品期货和股指期货的开盘时间并非相同
    
# 该函数用来定时执行买卖条件，每个交易频率（日/分钟）自动调用一次.
def handle_bar(context, bar_dict):
    code="NI2003"
    # order_future(code, 1,"open" ,"short")
    # print(context.portfolio.positions)
    # print(context.portfolio.positions[code])
    currentTime=get_datetime()
    currentMin=int(currentTime.strftime("%M"))
    if currentMin%15==0:
        
        print(context.portfolio.positions)
        print(context.portfolio.positions[code])
        #如果是满足15分钟间隔，检测交易
        priceDF=get_price_future(code,start_date=None,end_date=currentTime,fre_step="15m", fields=["high","low","close"],bar_count =150, is_panel = 0)
        priceDF["ma10"]=priceDF.close.rolling(10).mean()
        priceDF["ma30"]=priceDF.close.rolling(30).mean()
        priceDF["ma120"]=priceDF.close.rolling(120).mean()
        highList=priceDF.high.tolist()
        lowList=priceDF.low.tolist()
        closeList=priceDF.close.tolist()
        ma10List=priceDF["ma10"].tolist()
        ma30List=priceDF["ma30"].tolist()
        ma120List=priceDF["ma120"].tolist()
        print(context.portfolio.positions)
        if len(context.portfolio.positions)>0:
            if closeList[-1]<lowList[-2] and context.portfolio.positions[code].market_value>0:
                print("当前价小于前k最低价，且是多单，平仓")
                order_future(code, 1,"close" ,"long")
            elif closeList[-1]>highList[-2] and context.portfolio.positions[code].market_value<0:
                print("当前价高于前k最高价，且是空单，平仓")
                order_future(code, 1,"close" ,"short")
            else:
                pass
        else:
            #如果多头排列，最高价比前最高多，开多
            if ma10List[-1]>ma30List[-1] and ma30List[-1]>ma120List[-1] and closeList[-1]>highList[-2]:
                print("多头排列，当前价比前最高多，开多")
                order_future(code, 1,"open" ,"long")
            #如果空头排列，当前价小于前最低价，开空
            elif ma10List[-1]<ma30List[-1] and ma30List[-1]<ma120List[-1] and closeList[-1]<lowList[-1]:
                print("空头排列，当前价小于前最低价，开空")
                order_future(code, 1,"open" ,"short")

