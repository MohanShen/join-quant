# Clone from JoinQuant
# postId: df3d10a3449c8a62585d62202e72ef09
# backtestId: 0fa94b001494ceb9634dbe54bfd68311
# title: 投资者情绪类型划分与情绪指数构建在交易策略中的应用

# 导入聚宽函数库
import jqdata 
import pandas as pd
import numpy as np
from sklearn import svm


# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 输出内容到日志 log.info()
    log.info('初始函数开始运行且全局只运行一次')
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')
        

    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    
    ## 选取股票池
    g.stock_list = ['600302.XSHG','600303.XSHG','600309.XSHG']
    g.Turnover_Ratio_df = {'aaa':0}
    g.tr_ratio_threhold = 0.2
    g.To_But_Stock_list = []
    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
   
    # 开盘时运行
    run_daily(market_open, time='every_bar', reference_security='000300.XSHG')
   
   
   
'''-------以换手率作为非理性情绪的代理变量-------'''     
def GetSentiData(context):
    g.Turnover_Ratio_df.clear()
    To_But_Stock_list = []
   
    ######非理性情绪指标换手率
    stock_list = g.stock_list
    
    for s in stock_list:
        q = query(valuation.code, valuation.turnover_ratio).filter(
                valuation.code == s)
    
        today = context.current_dt
        trade_days = jqdata.get_trade_days(end_date = today,count = 61)
        turnover_ratio_60 = []
    
        for trade in trade_days[:-2]:
            df= get_fundamentals(q, trade)
            if len(df['turnover_ratio']) > 0:
                tr = df['turnover_ratio'][0]
            else:
                tr = 0
            turnover_ratio_60.append(tr)
        
        #print(turnover_ratio_60)
    
        STD = np.std(turnover_ratio_60)
        mean = np.mean(turnover_ratio_60)
        CurrTurnOver=  get_fundamentals(q, trade_days[-1])['turnover_ratio']
        #标准化后换手率
        Trunover_Index = (CurrTurnOver-mean)/STD
        print(Trunover_Index[0])

        if Trunover_Index[0]>g.tr_ratio_threhold:
            g.Turnover_Ratio_df[s] = Trunover_Index[0]

            To_But_Stock_list.append(s)

    g.To_But_Stock_list = To_But_Stock_list

    return 
'''------------------------------------------------------'''     


'''-----------------------大盘止损-----------------------'''   
def stop(context):
    Code = '000300.XSHG'
    MyPrice = attribute_history(Code,60,'1d', ['close'])
    ma_60 = MyPrice['close'][-60].mean()
    ma_30 = MyPrice['close'][-30].mean()
    ma_10 = MyPrice['close'][-10].mean()
    if ma_30<ma_60 or ma_10<0.95 * ma_30:
        return False;
    else:
        return True
'''------------------------------------------------------'''     


## 开盘时运行函数
def market_open(context):

    ## 大盘止损
    if stop(context)==False:
        #卖掉所有股票
        for key in context.portfolio.positions:
            order_target(key, amount = 0)
        return 
    
    GetSentiData(context)
    #print(g.To_But_Stock_list)
    #print(g.CCI_Index)


    ## 计算调仓方案
    price_list = []
    for s in g.stock_list:
        if s in g.To_But_Stock_list:
            MyPrice = attribute_history(s,20,'1d', ['close'])
            ma_5 = MyPrice['close'][-5].mean()
            ma_10 = MyPrice['close'][-10].mean()
            if ma_5 > ma_10:
                price = MyPrice['close'][-1]
                price_list.append(price)
        elif s not in g.To_But_Stock_list and context.portfolio.positions[s].closeable_amount > 0:
            order_target(s, 0)
    
    # 取得当前的现金，计算购买量
    cash = context.portfolio.available_cash
    total_price = sum(price_list)
    volume = cash/total_price

    # 下单
    for s in g.To_But_Stock_list: #s是代码
        order_target(s, volume)
    
    