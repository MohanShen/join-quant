# Clone from JoinQuant
# postId: 8abdec9f53d5884d0a2f6d4fe4f75fee
# backtestId: d74e4a69ad2da392151c019e6e443088
# title:  【策略粉碎机】之模拟盘高开低开策略真面目

# enable_profile()
import talib
import numpy as np
import pandas as pd

def initialize(context):
    set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))	# 设置手续费
    set_benchmark('000300.XSHG')    # 策略参考标准
    g.choice = 300                  # 预选股票数
    g.amount = 7                    # 持仓股票数
    g.muster = []                   # 预选股票池
    g.summit = {}                   # 区间最高价
    set_slippage(PriceRelatedSlippage(0.00246))#没用的函数，不生效
def before_trading_start(context):
    # 取得当前日期
    g.today = context.current_dt.strftime('%Y-%m-%d')
    g.start = context.current_dt + datetime.timedelta(-2)
    # 选出所有的总市值最小的g.choice只股票
    storage = get_fundamentals(query(valuation.code, valuation.market_cap)) 
    storage = storage.dropna().sort(columns='market_cap',ascending=True)
    storage = storage.head(g.choice)
    # 选取上面的结果作为预选股票池
    g.muster = list(storage['code'])
    
    # 清理股票峰值信息
    for stock in g.summit.keys():
        if stock not in context.portfolio.positions: del g.summit[stock]

# 每个单位时间调用一次(如果按天回测,则每天调用一次,如果按分钟,则每分钟调用一次)
def handle_data(context, data):
    # 清仓操作==================================================================
    #for stock in g.bucket: order_target(stock,0)	# 清空未完成订单
    g.bucket=[]
    # --------------------------------------------------------------------------
    for stock in context.portfolio.positions:
        
        # SS、记录股票峰值信息
        if g.summit.get(stock, 0)<data[stock].high: g.summit[stock]=data[stock].high
        # S0、取得最近几天股票价格信息
        grid = get_price(stock, start_date=g.start, end_date=g.today, fields=['open', 'high', 'low', 'close', 'high_limit', 'paused'])
        # SP、跳过退市、停牌、无效数据
        if grid.paused[-1]: continue

        # S2、回撤10%则清仓
        if grid.open[-1]/g.summit[stock]<0.9:
            order_target(stock,0)
            log.info('回撤清仓：%s,当前价=%.2f' % (stock, grid.open[-1]))
        # S3、今日高开、今日未涨停则清仓
        if len(grid)>1 and grid.high[-2]<grid.open[-1] and grid.open[-1]<grid.high_limit[-1]:
            order_target(stock,0)
            log.info('止盈清仓：%s,昨高=%.2f,今开=%.2f,昨涨停=%.2f,今涨停=%.2f' % (stock, grid.high[-2], grid.open[-1], grid.high_limit[-2], grid.high_limit[-1]))
    # --------------------------------------------------------------------------

    # 建仓操作==================================================================
    margin = g.amount - len(context.portfolio.positions)
    if margin==0: return
    assign = context.portfolio.cash/margin
    for stock in g.muster:
        positionnum=len(context.portfolio.positions) 
        if positionnum==g.amount: break
        # BS、跳过ST，*ST
        extras=get_extras('is_st', [stock], start_date=g.start, end_date=g.today, df=False)
        if extras[stock][-1]: continue
    
        # B0、取得最近几天股票价格信息
        grid = get_price(stock, start_date=g.start, end_date=g.today, fields=['open', 'high', 'low', 'close', 'low_limit', 'paused'])
        # BP、跳过退市、停牌、无效数据
        if grid.paused[-1]: continue
    
        # B1、今日低开、今日未跌停则买入
        if len(grid)>1 and grid.low[-2]>grid.open[-1] and grid.open[-1]>grid.close[-2]*0.9:
            order(stock, int(assign/grid.open[-1]))
            log.info('低开建仓：%s,昨低=%.2f,今开=%.2f,昨跌停=%.2f,今跌停=%.2f' % (stock, grid.low[-2], grid.open[-1], grid.low_limit[-2], grid.low_limit[-1]))
            
            
            