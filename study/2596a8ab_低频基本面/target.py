# Clone from JoinQuant
# postId: 2596a8ab9fe4fe80fbebf1588991f4a4
# backtestId: 312dca96baf9282b6d936d5f029cb7f9
# title: 慢就是快，低频交易也能博得高收益

# 克隆自聚宽文章：https://www.joinquant.com/post/27994
# 标题：红利搬砖，年化29%
# 作者：Gyro

# 引入库函数
import numpy as np
import pandas as pd
import datetime as dt
from jqdata import *

def initialize(context):
    # 设置系统
    set_option('use_real_price', True)
    # 设置信息格式
    log.set_level('order', 'error')
    pd.set_option('display.max_rows', 100)
    pd.set_option('display.max_columns', 10)
    pd.set_option('display.width', 500)
    # 设置策略
    #run_weekly(handle_trader,4, time='before_open', reference_security='000300.XSHG')
    run_monthly(handle_trader,2, '14:45')
    run_monthly(handle_trader,5, '14:45')
    run_monthly(handle_trader,6, '14:45')
    run_monthly(handle_trader,7, '14:45')
    run_monthly(handle_trader,8, '14:45')
    run_monthly(handle_trader,11, '14:45')
    run_monthly(handle_trader,12, '14:45')
    #run_daily(handle_trader, '10:30')
    # 设置参数
    g.index = '000300.XSHG' #投资指数
    g.num = 1 #选股数
    g.stocks = [] #股票池

def handle_trader(context):
    # 按年更新
    if context.current_dt.month in [1,2,3,4,5,6,7,8,9,10,11,12]:
        g.stocks = choice_stocks(context, g.index, g.num)
    # 卖出
    cdata = get_current_data()
    for s in context.portfolio.positions:
        if s not in g.stocks and not cdata[s].paused:
            log.info('sell', s, cdata[s].name)
            order_target(s, 0)
    # 买进
    position = 0.99*context.portfolio.total_value / max(1, len(g.stocks))
    for s in g.stocks:
        if s not in context.portfolio.positions and not cdata[s].paused and\
            context.portfolio.available_cash > position:
            log.info('buy', s, cdata[s].name)
            order_value(s, position)

def choice_stocks(context, index, num):
    # 股票池
    stocks = get_index_stocks(index)
    # 提取市值，基本面过滤
    sdf = get_fundamentals(query(
            valuation.code,
            valuation.market_cap, #单位，亿元
        ).filter(
            valuation.code.in_(stocks),
            valuation.pb_ratio > 0,
            valuation.pe_ratio > 0,
            valuation.pcf_ratio > 0,
            valuation.pb_ratio > 0.15*valuation.pe_ratio,
        )).dropna().set_index('code')
    stocks = list(sdf.index)
    # 最近三年的股息
    dt_3y = context.current_dt.date() - dt.timedelta(days=3*365)
    ddf = finance.run_query(query(
            finance.STK_XR_XD.code,
            finance.STK_XR_XD.company_name,
            finance.STK_XR_XD.board_plan_pub_date,
            finance.STK_XR_XD.bonus_amount_rmb, #单位，万元
        ).filter(
            finance.STK_XR_XD.code.in_(stocks),
            finance.STK_XR_XD.board_plan_pub_date > dt_3y,
            finance.STK_XR_XD.bonus_amount_rmb > 0
        )).dropna()
    stocks = list(set(ddf.code))
    # 累计分红
    divy = pd.Series(data=zeros(len(stocks)), index=stocks)
    for k in ddf.index:
        s = ddf.code[k]
        divy[s] += ddf.bonus_amount_rmb[k]
    # 建立数据表
    sdf = sdf.reindex(stocks)
    sdf['div_3y'] = divy
    # 计算股息率
    sdf['div_ratio'] = 1e-2 * sdf.div_3y / sdf.market_cap
    # report
    sdf['name'] = [get_security_info(s).display_name for s in sdf.index]
    sdf = sdf.sort_values(by='div_ratio', ascending=False)
    #log.info('\n', sdf[:10])
    return list(sdf.head(num).index)
# end
# ===== AUTORESEARCH NORMALIZATION OVERRIDE (appended; strategies/ file untouched) =====
__jq_set_slippage = set_slippage
def set_slippage(*a, **k):
    __jq_set_slippage(FixedSlippage(0))
__jq_set_commission = set_commission
def set_commission(*a, **k):
    __jq_set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
try:
    __jq_orig_initialize = initialize
    def initialize(context):
        __jq_orig_initialize(context)
        set_option('use_real_price', True)
        set_slippage(FixedSlippage(0))
        set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
except NameError:
    pass
# ===== END OVERRIDE =====
