# Clone from JoinQuant
# postId: b5c0ce178ff660b916ecc327c8771e87
# backtestId: dc5ca9d3314251287b7812f0363eb3ea
# title: 严格约束选股条件 能否找到跑赢市场的好公司？

'''


@author: zhanghansheng

1.盈利强：roe_ttm>10%且ROE<60%；
2.可持续：roe_ttm连续两季度回升；净利润增速回升（单季度）；毛利率回升（单季度）；
3.资产优：负债率<60%；商誉比<10%，正经营现金流TTM；
4.估值合理：PE<50；
5.每月一次调仓；
'''


import pandas as pd
import datetime
import time
from jqfactor import get_factor_values



## 初始化函数，设定要操作的股票、基准等等
def initialize(context):
    # 设定指数
    g.stockindex = '000906.XSHG' 
    # 设定中证800作为基准
    set_benchmark(g.stockindex)
    # True为开启动态复权模式，使用真实价格交易
    set_option('use_real_price', True) 
    # 设定成交量比例
    set_option('order_volume_ratio', 1)
    # 股票类交易手续费是：买入时佣金万分之三，卖出时佣金万分之三加千分之一印花税, 每笔交易佣金最低扣5块钱
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, \
                             open_commission=0.0003, close_commission=0.0003,\
                             close_today_commission=0, min_commission=5), type='stock')
    # 最大持仓数量
    g.stocknum = 100

    ## 手动设定调仓月份（如需使用手动，注释掉上段）
    # g.Transfer_date = (3,9)
    
    #生成一个list，存放持股数量
    #holding_num = []

    ## 按日调用程序
    run_monthly(trade, monthday=1, time='open')


## 交易函数
def trade(context):

    # 获得Buylist
    Buylist = check_stocks(context)
    
    rebalance(context, Buylist)
    
    
## 选股函数
def check_stocks(context):
    # 获取中证成分股
    security_list = get_index_stocks(g.stockindex)
    
    q = query(
        valuation.code,
        valuation.pe_ratio,
        valuation.pb_ratio,
        #income.net_profit,
        #indicator.roe,
        indicator.gross_profit_margin,
        indicator.inc_net_profit_year_on_year,
        balance.total_assets,
        balance.total_liability,
        balance.good_will
        ).filter(
            valuation.code.in_(security_list)
            #balance.total_liability/balance.total_assets < 0.6,
            #balance.good_will/balance.total_assets < 0.1,
            #valuation.pe_ratio < 50
            )
    
    #获取本期时间
    today = context.current_dt - datetime.timedelta(days=1)
    month = today.month
    
    # 上期时间（上一季度）
    if (month > 3):
        pre_date = datetime.datetime(year = today.year, month = today.month-3, day = 1)
        if (pre_date.month > 3):
            pre_pre_date = datetime.datetime(year = pre_date.year, month = pre_date.month-3, day = 1)
        if (pre_date.month <= 3):
            pre_pre_date = datetime.datetime(year = pre_date.year-1, month = pre_date.month+9, day = 1)
    if (month <= 3):
        pre_date = datetime.datetime(year = today.year-1, month = today.month+9, day = 1)
        pre_pre_date = datetime.datetime(year = today.year-1, month = today.month+6, day = 1)
    
    #获取本期财务数据
    Stocks = get_fundamentals(q,date = today)
    Stocks.index = Stocks['code']
    
    #获取上期财务数据
    Stocks_pre = get_fundamentals(q,date = pre_date)
    Stocks_pre.index = Stocks_pre['code']
    Stocks_pre = Stocks_pre.loc[:,['inc_net_profit_year_on_year','gross_profit_margin']]
    Stocks_pre.columns = ['inc_net_profit_year_on_year_pre','gross_profit_margin_pre']
    
    #获取本期roe_ttm因子数据
    factor_data_roe = get_factor_values(security_list,factors = ['roe_ttm'],end_date = today,count = 1)
    factor_data_roe = factor_data_roe['roe_ttm'].T
    factor_data_roe.columns = ['roe_ttm']
    
    #获取上期roe_ttm因子数据
    factor_data_roe_pre = get_factor_values(security_list,factors = ['roe_ttm'],end_date = pre_date,count = 1)
    factor_data_roe_pre = factor_data_roe_pre['roe_ttm'].T
    factor_data_roe_pre.columns = ['roe_ttm_pre']
    
    #获取上上期roe_ttm因子数据
    factor_data_roe_pre_pre = get_factor_values(security_list,factors = ['roe_ttm'],end_date = pre_pre_date,count = 1)
    factor_data_roe_pre_pre = factor_data_roe_pre_pre['roe_ttm'].T
    factor_data_roe_pre_pre.columns = ['roe_ttm_pre_pre']
    
    #roe_ttm因子数据合并
    roe_ttm = pd.concat([factor_data_roe,factor_data_roe_pre,factor_data_roe_pre_pre],axis = 1)
    roe_ttm['roe_1s'] = pd.Series(roe_ttm['roe_ttm'] > roe_ttm['roe_ttm_pre'])
    roe_ttm['roe_2s'] = pd.Series(pd.Series(roe_ttm['roe_ttm_pre'] > roe_ttm['roe_ttm_pre_pre']) & roe_ttm['roe_1s'])
    
    #获取本期net_operate_cash_flow_ttm因子数据
    factor_data_net_operate_cash_flow_ttm = get_factor_values(security_list,factors = ['net_operate_cash_flow_ttm'],end_date = today,count = 1)
    factor_data_net_operate_cash_flow_ttm = factor_data_net_operate_cash_flow_ttm['net_operate_cash_flow_ttm'].T
    factor_data_net_operate_cash_flow_ttm.columns = ['net_operate_cash_flow_ttm']
    
    #多表合并
    Stocks = pd.concat([Stocks,Stocks_pre,roe_ttm,factor_data_net_operate_cash_flow_ttm],axis = 1)
    Stocks['d_a'] = Stocks['total_liability']/Stocks['total_assets']
    Stocks['g_a'] = Stocks['good_will']/Stocks['total_assets']
    Stocks['code'] = Stocks.index
    
    #约束部分
    #筛选出d/a小于0.6的
    Stocks = Stocks[Stocks['d_a'] < 0.6]
    
    #筛选出g/a小于0.1的
    Stocks = Stocks[Stocks['g_a'] < 0.1]
    
    #筛选出pe_ratio小于50的
    Stocks = Stocks[Stocks['pe_ratio'] < 50]
    
    #筛选出roe_ttm属于（0.1,0.6）的
    Stocks = Stocks[Stocks['roe_ttm']>0.1]
    Stocks = Stocks[Stocks['roe_ttm']<0.6]
    
    #筛选出roe_2s的
    Stocks = Stocks[Stocks['roe_2s']]
    
    #筛选出净利润增速回升的
    Stocks = Stocks[pd.Series(Stocks['inc_net_profit_year_on_year'] > Stocks['inc_net_profit_year_on_year_pre'])]
    
    #筛选出毛利率回升的
    Stocks = Stocks[pd.Series(Stocks['gross_profit_margin'] > Stocks['gross_profit_margin_pre'])]
    
    #筛选出经营现金流ttm为正的
    Stocks = Stocks[Stocks['net_operate_cash_flow_ttm']>0]
    
    #按roe_ttm降序排序，取roe_ttm最高的前100个,不足100个就全要
    Stocks = Stocks.sort(['roe_ttm'],axis = 0,ascending = False)
    
    if len(Stocks)>=g.stocknum:
        Codes = Stocks[:g.stocknum].code
        print(Codes)
        return list(Codes)
    else:
        Codes = Stocks['code']
        print(Codes)
        return list(Codes)


#买入和卖出的函数
def rebalance(context, holding_list):
    if len(holding_list)==0:
        every_stock = 0
    else:
        every_stock = context.portfolio.portfolio_value/len(holding_list)
# 空仓只有买入操作
    if len(list(context.portfolio.positions.keys()))==0:
        for stock_to_buy in holding_list: 
            order_target_value(stock_to_buy, every_stock)
    else :
        # 不是空仓先卖出持有但是不在购买名单中的股票
        for stock_to_sell in list(context.portfolio.positions.keys()):
            if stock_to_sell not in holding_list:
                order_target_value(stock_to_sell, 0)
        stock_number = len(holding_list) - len(list(context.portfolio.positions.keys()))
        if stock_number>0:
            stock_cash = context.portfolio.available_cash/stock_number
        else:
            stock_cash = 0
        #将剩余的金额分配给新进入的股票
        for stock in holding_list:
            if stock not in list(context.portfolio.positions.keys()):
                order_target_value(stock, stock_cash)
    print('hold_stocks:',len(context.portfolio.positions))
    

