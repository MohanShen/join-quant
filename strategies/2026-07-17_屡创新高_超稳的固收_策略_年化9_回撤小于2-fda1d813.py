# Clone from JoinQuant
# postId: fda1d8139aba6571e9228e71ab9739b3
# backtestId: 4e497c466ced1626b80ca91131ade2db
# title: 屡创新高,超稳的固收+策略,年化9%,回撤小于2%

'''
'''

import pandas as pd
import numpy as np
from jqdata import *
from jqlib.technical_analysis import *

#初始化函数 
def initialize(context):
    # 启用“真实价格”模式，避免前复权带来的交易价格偏差
    set_option('use_real_price', True)
# 开启防未来函数（当不小心取未来数据时抛异常或剔除）
    set_option('avoid_future_data', True)
    set_option("match_by_signal", True) #强制撮合
    # 设定基准
    set_benchmark('000300.XSHG')
    # 用真实价格交易
    set_option('use_real_price', True)
    # 设置滑点 
    set_slippage(FixedSlippage(0.000))
    # 设置交易成本
    set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.00000, close_commission=0.00000, close_today_commission=0, min_commission=0.0), type='fund')
    # 过滤一定级别的日志
    log.set_level('system', 'error')
    #每周第1个交易日早盘时运行
    run_monthly(on_start,1,'9:35')
#防止偷窥,拉到最下面










































#防止偷窥,拉到最下面








































#防止偷窥,拉到最下面















































#防止偷窥,拉到最下面



















































#防止偷窥,拉到最下面















































#防止偷窥,拉到最下面

















































#防止偷窥,拉到最下面
















#防止偷窥,拉到最下面






























#防止偷窥,拉到最下面
























#防止偷窥,拉到最下面


























#防止偷窥,拉到最下面






























#防止偷窥,拉到最下面
































#防止偷窥,拉到最下面






























#防止偷窥,拉到最下面












































#防止偷窥,拉到最下面





































#防止偷窥,拉到最下面












































#防止偷窥,拉到最下面











































#防止偷窥,拉到最下面


def on_start(context):
    #年度再平衡
    if year_start(context)==1:
        for s in context.portfolio.positions:
            order_target(s, 0)
    stocks=[]
    fg='518880.XSHG'#黄金
    f1='511090.XSHG'#国债
    #f1='161716.XSHE'#国债
    f2='511260.XSHG'#10年国债
    f3='160323.XSHE'#固收+
    vg=context.portfolio.total_value*0.1;
    v1=context.portfolio.total_value*0.30;
    v2=context.portfolio.total_value*0.30;
    order_target_value(fg, vg)
    order_target_value(f1, v1)
    order_target_value(f2, v1)
    order_target_value(f3, v2)


def year_start(context):
    #return False#不做年度调整
    # 回测当前时间获取
    year= context.current_dt.year
    month = context.current_dt.month
    day = context.current_dt.day
    # 获取该年份的所有交易日
    trade_days = get_trade_days(start_date=str(year) + '-01-01', end_date=str(year) + '-12-31')
    # 返回第一个交易日
    trade_days=trade_days[0]
    trade_days=trade_days.day
    star=0
    if month==1 and day==trade_days:
        star=1
    return star
