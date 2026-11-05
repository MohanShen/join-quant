# Clone from JoinQuant
# postId: d40cbb6a060455fb3a45a4507fb5fc31
# backtestId: 66b78f1e9e149ad8f29743f2f08cfca6
# title: 回测年化174%的创业板活跃股策略

# 这是聚宽的文件单回测代码，拷过去即可，运行前注意文件依赖
# 注意，这个回测依赖研究环境 res_data/sel_cyb.csv 文件，一定要先上传选股结果文件
# 导入函数库
from jqdata import *
from datetime import date, timedelta, datetime
import pandas as pd
from six import BytesIO
import json

# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 买卖各多一分，固定值滑点
    set_slippage(FixedSlippage(0.01), type='stock')
    # 如果使用卖一价买，则动态设置滑点
    g.df_all = None
    g.to_sell = []
    # 不要超过0.5
    g.buy_position_everyday = 0.5

    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 过滤掉order系列API产生的比error级别低的log
    log.set_level('order', 'error')
    init_data(context)
    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费
    set_order_cost(OrderCost(
        close_tax=0.0005, 
        open_commission=0.0001, 
        close_commission=0.0001, 
        min_commission=5), 
        type='stock'
    )
    run_daily(buy_point, time='09:31', reference_security='000300.XSHG')
    run_daily(sell_all, time='14:40', reference_security='000300.XSHG')
    run_daily(after_close, time='after_close', reference_security='000300.XSHG')
    
    
    
def init_data(context):
    df= pd.read_csv(BytesIO(read_file('res_data/sel_cyb.csv')),index_col=0)
    g.df_all = df
    
    
def clear_to_sell(context):
    for code in g.to_sell:
        order_target_value(code, 0)
    g.to_sell = []


def buy_point(context):
    clear_to_sell(context)
    df = g.df_all
    day = context.current_dt.strftime("%Y-%m-%d")
    res = df[ (df.trade_date==day)]
    to_buy = res.code.tolist()
    if len(to_buy)>0:
        cash = min(context.portfolio.available_cash,
                context.portfolio.total_value*g.buy_position_everyday)
        # 每个票买入的金额
        pos = cash/len(to_buy)
        for code in to_buy:
            order_value(code, pos)


## 清仓
def sell_all(context):
    for code, position in context.portfolio.long_positions.items():
        if position.closeable_amount>0:
            order_target_value(code, 0)
            

def after_close(context):
    # 得到当前未完成订单
    orders = get_open_orders()
    # 循环，撤销订单
    for _order in orders.values():
        cancel_order(_order)
    g.to_sell = []
    # 如果跌停，会卖不出去，这里记录该卖但卖不出去但，次日买入前卖掉
    for code, position in context.portfolio.long_positions.items():
        if position.closeable_amount>0:
            g.to_sell.append(code)
            print('====%s to sell'%code)

