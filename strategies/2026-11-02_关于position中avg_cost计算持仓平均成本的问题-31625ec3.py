# Clone from JoinQuant
# postId: 31625ec3d2713deee4ea01678770f239
# backtestId: 09a999d14fa9d36462c104977665c186
# title: 关于position中avg_cost计算持仓平均成本的问题

import jqdata
import datetime as dt
import numpy as np

def initialize(context): #用来写最开始要初始化的参数
    g.totalmoney = context.portfolio.available_cash
    months = (context.run_params.end_date.year - context.run_params.start_date.year)*12 + context.run_params.end_date.month - context.run_params.start_date.month + 1
    g.money = g.totalmoney/months
    print '每期投资金额：%.2f' % g.money
    g.security = '159915.OF' #创业板ETF
    set_benchmark('399006.XSHE') #创业板指数
    g.r = 0 #基金单位净值收益率
    g.cost = 0 #用来计算持有成本
    g.count = 0 
    g.investments = np.array([])
    g.sum_amount = 0
    #设置基金申购赎回费用均为千一
    set_order_cost(OrderCost(open_commission=0.001, close_commission = 0.001, min_commission=0), type='stock_fund')
    # 初始化场外基金仓位
    set_subportfolios([SubPortfolioConfig(context.portfolio.cash, 'open_fund')])
    run_monthly(value_avg, 1, time = 'open+30m') #每月第一个交易日开盘后半小时按照平均市值策略申购基金
    run_monthly(compute_value, 3, time = 'open+30m') #按照申购基金t+2到账，第三个交易日计算本月净值数据，给下个月使用
    run_monthly(compute_profit, -1, time = 'close')
    
def value_avg(context):
    purchase(g.security,g.money)
    g.investments = np.append(g.investments,-g.money)
    
def compute_value(context):
    log.info('当前持仓总市值(3rd day)%.2f'%context.portfolio.positions[g.security].value)

def compute_profit(context):
    if context.run_params.end_date.year == context.current_dt.year and context.current_dt.month == context.run_params.end_date.month:
        g.investments = np.append(g.investments,context.portfolio.positions[g.security].value)
        irr = np.irr(g.investments)
        dwjz = context.portfolio.positions[g.security].price
        totalamount = context.portfolio.positions[g.security].total_amount
        totalcost = sum(g.investments[:-1])
        cost1 = context.portfolio.positions[g.security].avg_cost
        cost2 = -totalcost/totalamount
        log.info(g.investments)
        log.info(len(g.investments),dwjz,cost1,cost2,totalamount,-totalcost)
        #申购价格是按照申购当日收盘价计算，没有问题，但是最后自带的avg_cost计算成本存在误差，并且误差不小。

    