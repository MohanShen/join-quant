# Clone from JoinQuant
# postId: 508126a0427c09c6bd154ab95424dcce
# backtestId: f8ea3f68d8a63e46e59eba0f39f565ee
# title: 一个可行的框架测试中持续更新

# 导入函数库
from jqdata import *

# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    
    # 过滤掉order系列API产生的比error级别低的log
    # log.set_level('order', 'error')
    
    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    
    ## 运行函数（reference_security为运行时间的参考标的；传入的标的只做种类区分，因此传入'000300.XSHG'或'510300.XSHG'是一样的）
      # 开盘前运行
    run_daily(before_market_open, time='before_open', reference_security='000300.XSHG') 
      # 开盘时或每分钟开始时运行
    run_daily(market_open, time='every_bar', reference_security='000300.XSHG')
      # 收盘后运行
    run_daily(after_market_close, time='after_close', reference_security='000300.XSHG')
    
## 开盘前运行函数     
def before_market_open(context):
    pass
    
## 开盘时运行函数
def market_open(context):
    pass
 
## 收盘后运行函数  
def after_market_close(context):
    pass

# from sklearn import linear_model
# import numpy as np
# import pandas as pd
# import time
# import re
# from datetime import date
# import talib
# import sys
# import globalvar as gl

# gl._init()
# gl.set_value('to_init', g.look_back_day)
# gl.set_value('listed', g.listed)
# from jqdata import *
# from jqlib.alpha191 import *
# from stringtrans import *
# from function import *

# g.factor_list = []
# for factor in factor_list:
#     factor = body(factor)
#     factor = repair(factor)
#     g.factor_list.append(factor)
# gl.set_value('factor_list', g.factor_list)
# from MClearning import *
# # 初始化函数，设定基准等等
# def initialize(context):
#     factor = g.fac
#     print('initial factor is :')
#     print(factor)
#     factor = body(factor)
#     print('factor after compiling is :')
#     print (factor)
#     g.factor = repair(factor)

#     set_option('use_real_price', True)  # 用真实价格交易
#     log.set_level('order','error')
#     set_slippage(FixedSlippage(0))  # 将滑点设置为0
#      # 股票类交易手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
# #    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
#     set_benchmark('000905.XSHG')  # 中证500为业绩基准
#     set_variables()  # 初始化所要调用的函数
#     # 选股范围为全市场选股：上证+深证股票
#     g.stockrange = get_index_stocks('000001.XSHG') + get_index_stocks('399106.XSHE')
#     g.banchmark = '000905.XSHG'