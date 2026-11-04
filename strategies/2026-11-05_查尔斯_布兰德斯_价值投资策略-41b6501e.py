# Clone from JoinQuant
# postId: 41b6501e61becd5896b9f04ed2ef1189
# backtestId: c59a1334995b602b43a7377e5e8bd350
# title: 查尔斯·布兰德斯 价值投资策略

'''
策略思路：
如标题，作者从三个角度对投资标的进行要求，分别是强力的资产负债表，合理的估值，公司经营阶层具备诚信且持股充足
围绕这三个角度，提出了6个具体的选股准则，用市盈率、市现率、市净率、相对市场平均值来衡量估值水平，要求股票的价格尽量便宜，用负债净资产比限制公司的财务杠杆，要求
企业具备健康的财务状况，用懂监视会持股比例来衡量管理层的诚信和管理水平具体指标如下：

1.股票最近一季负债净值比小于80%(未做判断)
2.董监事会持股比例不低于市场平均值50%（未实现）
3.股票的市盈率不高于市场平均值1.5倍
4.股票的股价/近四季现金流量（市现率）不高于市场平均值的1.5倍
5.股票的市净率不高于市场平均值的1.5倍
6.股票的市净率小于2.0倍

'''
import pandas as pd
import numpy as np
import jqdata
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
    #策略参数设置
    #行业内最大持仓股数
    g.max_hold_stocknum = 20
    #操作的股票列表
    g.buy_list = []
    ### 股票相关设定 ###
    # 股票类每笔交易时的手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    
    # 每月第一个交易日进行操作
    # 开盘前运行
    run_monthly(before_market_open,5,time='before_open', reference_security='000300.XSHG') 
    # 开盘时运行
    run_monthly(market_open,5,time='open', reference_security='000300.XSHG')
    
## 开盘前运行函数     
def before_market_open(context):
    #获取要操作的股票列表
    temp_list = get_stock_list(context)
    #剔除停牌股
    all_data = get_current_data()
    temp_list = [stock for stock in temp_list if not all_data[stock].paused]
    #获取满足条件的股票列表
    temp_list = get_stock_list(context)
    log.info('满足条件的股票有%s只'%len(temp_list))
    #按市值进行排序
    g.buy_list = get_check_stocks_sort(context,temp_list)
    
## 开盘时运行函数
def market_open(context):
    #卖出不在买入列表中的股票
    sell(context,g.buy_list)
    #买入不在持仓中的股票，按要操作的股票平均资金
    buy(context,g.buy_list)
#交易函数 - 买入
def buy(context, buy_lists):
    # 获取最终的 buy_lists 列表
    Num = g.max_hold_stocknum - len(context.portfolio.positions.keys())
    buy_lists = buy_lists[:Num]
    # 买入股票
    if len(buy_lists)>0:
        # 分配资金
        cash = context.portfolio.total_value/(len(g.buy_list)*1.0)
        # 进行买入操作
        for s in buy_lists:
            order_value(s,cash)
       
# 交易函数 - 出场
def sell(context, buy_lists):
    # 获取 sell_lists 列表
    hold_stock = context.portfolio.positions.keys()
    for s in hold_stock:
        #卖出不在买入列表中的股票
        if s not in buy_lists:
            order_target_value(s,0)   

#按市值进行排序   
#从大到小
def get_check_stocks_sort(context,check_out_lists):
    df = get_fundamentals(query(valuation.circulating_cap,valuation.pe_ratio,valuation.code).filter(valuation.code.in_(check_out_lists)),date=context.previous_date)
    #asc值为0，从大到小
    df = df.sort('circulating_cap',ascending=0)
    out_lists = list(df['code'].values)[:g.max_hold_stocknum]
    return out_lists
    
#获取满足财务指标的股票列表
#3.股票的市盈率不高于市场平均值1.5倍
#4.股票的股价/近四季现金流量（市现率）不高于市场平均值的1.5倍
#5.股票的市净率不高于市场平均值的1.5倍
#6.股票的市净率小于2.0倍
def get_stock_list(context):
    #获取财务数据
    df_cw = get_fundamentals(query(valuation.code,valuation.pe_ratio,valuation.pb_ratio,valuation.pcf_ratio))
    df_cw.index = df_cw.code
    df_pe_se = winsorize(df_cw['pe_ratio'])
    df_pb_se = winsorize(df_cw['pb_ratio'])
    df_pcf_se = winsorize(df_cw['pcf_ratio'])
    df_pe = pd.DataFrame(df_pe_se)
    df_pb = pd.DataFrame(df_pb_se)
    df_pcf = pd.DataFrame(df_pcf_se)
    #进行条件筛选
    df_pb_list = df_pb[(df_pb['pb_ratio']>0) & (df_pb['pb_ratio']<2) & (df_pb['pb_ratio']<(1.5*df_pb['pb_ratio'].mean()))]
    df_pcf_list = df_pcf[(df_pcf['pcf_ratio']>0) & (df_pcf['pcf_ratio']<(1.5*df_pcf['pcf_ratio'].mean()))]
    df_pe_list = df_pe[(df_pe['pe_ratio']>0) & (df_pb['pb_ratio']<(1.5*df_pe['pe_ratio'].mean()))]
    buy_list = list(set(df_pb_list.index) & set(df_pcf_list.index) & set(df_pe_list.index))
    return buy_list
#去极值（分位数法）  
def winsorize(se):
    q = se.quantile([0.025, 0.975])
    if isinstance(q, pd.Series) and len(q) == 2:
        se[se < q.iloc[0]] = q.iloc[0]
        se[se > q.iloc[1]] = q.iloc[1]
    return se
    
    
    
    