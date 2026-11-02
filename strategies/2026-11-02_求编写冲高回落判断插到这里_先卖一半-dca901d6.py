# Clone from JoinQuant
# postId: dca901d6eadbdafced3adfbd0f3958a0
# backtestId: 16fc699ab145e2591552db87e15b8315
# title: 求编写冲高回落判断插到这里，先卖一半

from jqdata import *
import numpy as np
import pandas as pd
from six import BytesIO
import talib as tb
import jqdata
from jqlib.technical_analysis import *


def initialize(context):                      




    g.security_list= [ 
       '002938.XSHE', '002384.XSHE', '002463.XSHE', '603920.XSHG','002916.XSHE','600183.XSHG',
       '601138.XSHG', '002236.XSHE', '000049.XSHE', '002475.XSHE', '300433.XSHE', '000100.XSHE',
      ] 



    set_benchmark('000300.XSHG')              # 设定沪深300指数为基准
    set_option('use_real_price',True)         # 开启动态复权
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003, close_today_commission=0, min_commission=5), type='stock') 
    run_daily(run_func, 'every_bar',reference_security='000002.XSHG')
    g.run_num = -1                            #初始化计数器
    g.Contrast = '399006.XSHE'                  #参照对象




#盘中
def run_func(context):
    g.run_num += 1
    if g.run_num!=5:  #如果这次运行的次数不是15,打断此次运行
        return       
    else:
        g.run_num=0  #条件满足,计数器归零,继续后边的代码
    print('后边的代码将每隔15分钟运行一次')
   
    #控制参照对象
    Contrast_DIF,Contrast_DEA,Contrast_MACD = MACD(g.Contrast,check_date = context.current_dt,SHORT = 12,LONG = 26,MID = 9)

    #参照对象发生金叉
    if Contrast_DIF[g.Contrast] > Contrast_DEA[g.Contrast]:             

        for security in g.security_list: 
            
         
            #（把冲高回落判断插到这里，先卖一半）  
             
           #######################################################################################################
           #    price_close = attribute_history(security, 1, '1d', ('close'), True)['close'][0]      ( 昨天收盘价)
           #    price = context.portfolio.positions[security].price                                  （现价)  
           #    pri_1 = ((price - price_close) / price_close) * 100                                  （得到现在升幅）  
           # if pri > 5                                                                          （假如现在升幅超5个点）
           #    price_h = 获取这时刻之前的当天最高价 （注意不要获取未来函数的价）     
           #    pri_2 = ((price_h - price_close) / price_close) * 100                                （得到之前最高升幅）  
           #    if （pri_2 - pri_1）> 2                                                         （假如现在比最高升幅回落超2个点）
           #    order_target_value(security, 15000)                 # 把买入股票调整为1.5万  （卖出一半）
           #######################################################################################################
                  

            
            Stock_DIF,Stock_EDA,Stock_MACD = MACD(security,check_date = context.current_dt,SHORT = 12,LONG = 26,MID = 9)
            
            cash = context.portfolio.cash                        # 取得当前的现金
            buy_list = list(context.portfolio.positions.keys())  # 定义当前的持股池   
            sell_list= []                                        # 提前定义卖股池变量

            if (Stock_DIF[security]> Stock_EDA[security]) and (cash >10000) and (security not in sell_list):                  # 金叉买
                order_target_value(security, 30000)   # 把买入股票调整为3万
                buy_list.append(security)            #将股票增加到已买列表buy_list中      
                
            elif (Stock_DIF[security] < Stock_EDA[security]) and (security in buy_list):                # 死叉卖
                order_target_value(security, 0)                 # 将股票仓位调整到0，即全卖出
                sell_list.append(security)                #将股票增加到已卖列表sell_list中                                     
            
    else:
        buy_list = list(context.portfolio.positions.keys())  # 定义当前的持股池   
        for security in buy_list :            # 获取股票池中要操作的股票
            order_target_value(security, 0)                 # 将股票仓位调整到0，即全卖出
            #sell_list.append(security)                #将股票增加到已卖列表sell_list中            sell_list= []                                        # 提前定义卖股池变量    
