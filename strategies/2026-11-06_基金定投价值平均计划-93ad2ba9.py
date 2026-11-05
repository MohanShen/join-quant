# Clone from JoinQuant
# postId: 93ad2ba99fb4f71cc30db795188e9450
# backtestId: f2b02d3ff6f6f2b7004362d522892d79
# title: 基金定投价值平均计划

import jqdata
from jqlib.technical_analysis import *
import datetime as dt
import numpy as np

def initialize(context): #用来写最开始要初始化的参数
    g.totalmoney = context.portfolio.available_cash
    months = (context.run_params.end_date.year - context.run_params.start_date.year)*12 + context.run_params.end_date.month - context.run_params.start_date.month + 1
    g.money = g.totalmoney/months
    print '每期投资金额：%.2f' % g.money
    #g.security = '510300.XSHG'  #300ETF
    g.security = '510300.OF'
    #g.security = '159915.OF' #创业板ETF
    g.r = 0 #基金单位净值收益率
    g.cost = 0 #用来计算持有成本
    g.count = 0 
    g.stopflag = 0 #判断当月是否止盈
    g.last_month_dwjz = 0
    g.last_month_value = 0
    g.new_dwjz = 0
    g.zhiyingshizhi = 0
    g.investments = np.array([])
    set_benchmark('000300.XSHG') #沪深300指数
    #设置基金申购赎回费用均为千一
    set_order_cost(OrderCost(open_commission=0.001, close_commission = 0.001, min_commission=0), type='stock_fund')
    # 初始化场外基金仓位
    set_subportfolios([SubPortfolioConfig(context.portfolio.cash, 'open_fund')])
    run_monthly(before_trading, 1, time='open-30m') #每月第一个交易日开盘前输出一些数据，用做检查，可以注释掉
    run_monthly(stop_profit, 1, time = 'open') #每月第一个交易日开盘时运行止盈函数
    run_monthly(target_mv, 1, time = 'open+30m') #每月第一个交易日开盘后半小时按照平均市值策略申购基金
    run_monthly(compute_value, 3, time = 'open+30m') #按照申购基金t+2到账，第三个交易日计算本月净值数据，给下个月使用
    run_monthly(compute_profit, -1, time = 'close')
#def handle_data(context, data): #用来写每天循环要做什么

def before_trading(context):
    log.info('当前持仓总市值(1st)%.2f'%context.portfolio.positions[g.security].value)
    log.info('当前持仓仓位(1st)%.2f'%context.portfolio.positions[g.security].total_amount)

def after_trading_end(context):
    #trades = get_trades()
    #for _trade in trades.values():
    #    g.cost = g.cost + _trade.price * _trade.amount
    if context.portfolio.positions[g.security].total_amount > 0:
        #g.r = 100*(context.portfolio.positions[g.security].value/g.cost - 1)
        dwjz = context.portfolio.positions[g.security].price
        g.r = 100*(dwjz/context.portfolio.positions[g.security].avg_cost - 1)
    elif context.portfolio.positions[g.security].total_amount == 0 :
        g.r = 0
    record(return_rate = g.r)
    #returnrate的曲线跳点是因为赎回场外基金那两天基金份额已扣但是总净值暂未从持仓中扣除,returnrate计算的是单位净值收益，不是策略总收益，总收益还要考虑止盈的部分
    #record(average_cost= context.portfolio.positions[g.security].avg_cost)

def stop_profit(context):
    if g.r > 20:
        #基金净值收益达到20%以上时进行止盈赎回操作
        zhiyingbili = 0.3
        amount = zhiyingbili*context.portfolio.positions[g.security].total_amount
        g.zhiyingshizhi = zhiyingbili * context.portfolio.positions[g.security].value
        redeem(g.security, amount)
        g.stopflag = 1
        log.info('当前持仓总市值(止盈后立刻)%.2f'%context.portfolio.positions[g.security].value)
        log.info('当前持仓仓位(止盈后立刻)%.2f'%context.portfolio.positions[g.security].total_amount)
    
def target_mv(context):
    if context.portfolio.positions[g.security].total_amount>0:
        g.new_dwjz = context.portfolio.positions[g.security].value/context.portfolio.positions[g.security].total_amount
    if g.count == 0:
        #order_value(g.security, g.money)
        purchase(g.security,g.money)
        g.investments = np.append(g.investments,-g.money)
        g.count = 1
    elif g.count<>0 and g.stopflag == 0:
        #当月未止盈的情况下正常使用价值平均策略申购基金
        thismonth = g.money - (context.portfolio.positions[g.security].value - g.last_month_value)
        if thismonth > 0:
            #净值增长不够平均市值增长
            log.info('当月净值涨幅不够平均市值增长111')
            purchase(g.security,thismonth)
            g.investments = np.append(g.investments,-thismonth)
        elif thismonth <= 0:
            g.investments = np.append(g.investments,0)
    elif g.count<>0 and g.stopflag == 1:
        #当月发生止盈情况的申购策略:申购额按照当前持仓数量*(当前单位净值-上月申购后单位净值)计算，扔遵循固定增值额度
        thismonth = g.money - (g.new_dwjz-g.last_month_dwjz)*context.portfolio.positions[g.security].total_amount
        if thismonth > 0:
            #净值增长不够平均市值增长
            log.info('当月净值涨幅不够平均市值增长222')
            purchase(g.security,thismonth)
            g.investments = np.append(g.investments,g.zhiyingshizhi-thismonth)
        elif thismonth <= 0:
            g.investments = np.append(g.investments,g.zhiyingshizhi)
        g.stopflag = 0
    
def compute_value(context):
    g.last_month_value = context.portfolio.positions[g.security].value  
    g.last_month_dwjz = context.portfolio.positions[g.security].value/context.portfolio.positions[g.security].total_amount
    log.info('当前持仓总市值(4th)%.2f'%g.last_month_value)
    log.info('当前持仓仓位(4th)%.2f'%context.portfolio.positions[g.security].total_amount)

def compute_profit(context):
    if context.run_params.end_date.year == context.current_dt.year and context.current_dt.month == context.run_params.end_date.month:
        g.investments = np.append(g.investments,context.portfolio.positions[g.security].value)
        irr = np.irr(g.investments)
        log.info(g.investments)
        log.info(len(g.investments))
        log.info('月度irr 为：%.4f'%irr)
        yearlyreturn = np.power(1+irr,12)-1
        log.info('策略年化收益率为：%.4f'%yearlyreturn)
    