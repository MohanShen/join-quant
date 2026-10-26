# Clone from JoinQuant
# postId: 6c923b7342771b50797fc26f11ac51b9
# backtestId: d25245fc1629d7e44a9f697ffb155036
# title: 小市值策略，请大家评价

# 小市值策略（最终稳定版 - 无科创板/北交所，有流动性过滤）
from jqdata import *
import numpy as np
import pandas as pd

def initialize(context):
    set_benchmark('399101.XSHE')
    set_option('use_real_price', True)
    set_slippage(FixedSlippage(0.002))
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    
    # 策略参数
    g.stock_num = 10                     # 持股数量
    g.rebalance_days = 21               # 调仓周期（交易日）
    g.min_daily_amount = 5e6            # 最小日均成交额 500万元
    g.min_listed_days = 60              # 上市最少天数
    g.cash_etf = '511880.XSHG'          # 货币ETF（备用）
    
    g.bar_count = 0
    run_daily(rebalance, time='14:45')
    
def rebalance(context):
    g.bar_count += 1
    if g.bar_count % g.rebalance_days != 0:
        return
        
    target_list = get_stock_list(context)
    if not target_list:
        # 无目标时，卖出所有股票，买入货币ETF（保守）
        for stock in list(context.portfolio.positions.keys()):
            if stock != g.cash_etf:
                order_target_value(stock, 0)
        if context.portfolio.cash > 1000:
            order_target_value(g.cash_etf, context.portfolio.cash)
        log.warning('无目标股票，全仓货币ETF')
        return

    # 卖出不在目标列表的持仓
    for stock in list(context.portfolio.positions.keys()):
        if stock != g.cash_etf and stock not in target_list:
            order_target_value(stock, 0)
            log.info('卖出 %s' % stock)

    # 等权重买入
    target_value = context.portfolio.total_value / len(target_list)
    for stock in target_list:
        current_price = get_current_data()[stock].last_price
        if current_price is None or current_price <= 0:
            continue
        min_lot_value = current_price * 100
        if target_value < min_lot_value:
            log.info('资金不足，跳过 %s (需要 %.2f, 可用 %.2f)' % (stock, min_lot_value, target_value))
            continue
        order_target_value(stock, target_value)
        log.info('买入 %s 至目标市值 %.2f' % (stock, target_value))

def get_stock_list(context):
    # 股票池：中证1000（数据稳定，覆盖小市值）
    stock_pool = get_index_stocks('000852.XSHG')
    if not stock_pool:
        stock_pool = get_index_stocks('000300.XSHG')
    
    if not stock_pool:
        log.error('无法获取股票池')
        return []
    
    # 获取估值数据（流通市值）
    q = query(valuation.code, valuation.circulating_market_cap).filter(valuation.code.in_(stock_pool))
    df_val = get_fundamentals(q, date=context.previous_date)
    if df_val.empty:
        return []
    
    # 获取近20日成交额数据用于流动性过滤
    price_data = get_price(df_val['code'].tolist(), end_date=context.previous_date,
                           frequency='daily', fields=['money'],
                           count=20, skip_paused=True, panel=False)
    if price_data is None or len(price_data) == 0:
        return []
    
    # 计算每只股票近20日均成交额
    money_sum = {}
    money_cnt = {}
    for _, row in price_data.iterrows():
        code = row['code']
        money = row['money']
        if np.isnan(money): continue
        money_sum[code] = money_sum.get(code, 0) + money
        money_cnt[code] = money_cnt.get(code, 0) + 1
    avg_money = {code: money_sum[code]/money_cnt[code] for code in money_sum if money_cnt[code] >= 15}
    
    current_data = get_current_data()
    valid_stocks = []
    for _, row in df_val.iterrows():
        stock = row['code']
        
        # 排除停牌
        if current_data[stock].paused: continue
        # 排除ST
        if current_data[stock].is_st: continue
        # 排除退市
        if '退' in current_data[stock].name: continue
        # 排除科创板(68开头)、北交所(8、4开头)、创业板(30开头保留)
        if stock.startswith(('68', '8', '4')): continue
        
        # 上市天数过滤
        start_date = get_security_info(stock).start_date
        if (context.previous_date - start_date).days < g.min_listed_days: continue
        
        # 流动性过滤
        if stock in avg_money:
            if avg_money[stock] < g.min_daily_amount: continue
        else:
            continue
        
        # 涨跌停过滤（未持仓的股票）
        last_price = get_price(stock, end_date=context.previous_date, count=1, fields='close', skip_paused=True, panel=False)
        if last_price is not None and len(last_price) > 0:
            last_close = last_price['close'].iloc[0]
            if stock not in context.portfolio.positions:
                if last_close >= current_data[stock].high_limit - 0.01: continue
                if last_close <= current_data[stock].low_limit + 0.01: continue
        
        valid_stocks.append(stock)
    
    if not valid_stocks:
        log.warning('无股票通过基础过滤')
        return []
    
    # 按流通市值升序排序，取最小的前g.stock_num只
    df_filtered = df_val[df_val['code'].isin(valid_stocks)].copy()
    df_filtered = df_filtered.sort_values('circulating_market_cap')
    target_list = df_filtered['code'].head(g.stock_num).tolist()
    
    log.info('选中 %d 只股票: %s' % (len(target_list), target_list))
    return target_list