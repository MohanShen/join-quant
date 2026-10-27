# Clone from JoinQuant
# postId: e309bf89559b582dbdc732d27447be89
# backtestId: ec4ab6f26e69ab25d7df59e32ac63fd8
# title: 彼得·林奇多因子量化策略 V1.0

"""
彼得·林奇多因子量化交易策略
版本: V 1.0.0
作者：星
创建时间：2026-04-22
修改时间：2026-04-24

修改说明：
2026-04-24
1、按照“文件编号说明规则2026年4月24日”规则修改文件名称

彼得·林奇多因子量化交易策略
版本：V1.000
创建日期：2026-04-22
最后修改：2026-04-22


"""


from jqdata import *
import pandas as pd
import numpy as np

def initialize(context):
    g.stock_pool = get_index_stocks('000300.XSHG')  # 沪深300
    g.rebalance_days = 5
    g.counter = 0
    g.hold_num = 15
    set_benchmark('000300.XSHG')
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    set_option('use_real_price', True)
    set_slippage(FixedSlippage(0.01))
    run_daily(market_open, time='before_open')
    g.hold_stocks = {}

def market_open(context):
    g.counter += 1
    if g.counter % g.rebalance_days != 0:
        return
    current_date = context.current_dt.strftime('%Y-%m-%d')
    log.info('调仓日：%s' % current_date)
    buy_stocks, sell_stocks = select_stocks(context, g.stock_pool)
    execute_trades(context, buy_stocks, sell_stocks)

def select_stocks(context, stock_list):
    # 获取四个筛选条件的通过情况
    profit_pass = filter_tot_profit(stock_list, context.current_dt)
    cash_pass = filter_price_cash(stock_list, context.current_dt)
    debt_pass = filter_debt_ratio(stock_list, context.current_dt)
    pe_pass = filter_pe_growth(stock_list, context.current_dt)
    
    # 统计通过数量（安全计数方式）
    profit_count = sum(1 for v in profit_pass.values() if v)
    cash_count = sum(1 for v in cash_pass.values() if v)
    debt_count = sum(1 for v in debt_pass.values() if v)
    pe_count = sum(1 for v in pe_pass.values() if v)
    log.info('利润筛选通过: %d, 现金流筛选通过: %d, 负债率筛选通过: %d, PE/增长筛选通过: %d' % 
             (profit_count, cash_count, debt_count, pe_count))
    
    # 取交集
    candidate_dict = {}
    for stock in stock_list:
        if (profit_pass.get(stock, False) and 
            #cash_pass.get(stock, False) and 
            #pe_pass.get(stock, False) and 
            debt_pass.get(stock, False)):
            candidate_dict[stock] = True
        else:
            candidate_dict[stock] = False
    
    total_candidates = sum(1 for v in candidate_dict.values() if v)
    log.info('同时满足四个条件的股票数量: %d' % total_candidates)
    
    # 排序并选前30
    sorted_candidates = sort_by_ranking(stock_list, candidate_dict, context.current_dt)
    log.info('排序后候选股票数量: %d' % len(sorted_candidates))
    buy_list = sorted_candidates[:g.hold_num]
    if buy_list:
        log.info('买入列表前5只: %s' % buy_list[:5])
    
    # 卖出不在买入列表中的持仓
    sell_list = [stock for stock in context.portfolio.positions.keys() if stock not in buy_list]
    return buy_list, sell_list

def filter_tot_profit(stock_list, current_date):
    """单季净利润 > 1000万元"""
    result = {stock: False for stock in stock_list}
    try:
        q = query(income.code, income.net_profit).filter(income.code.in_(stock_list))
        df = get_fundamentals(q, date=current_date)
        if df.empty:
            log.warn('利润表无数据返回')
            return result
        for stock in stock_list:
            stock_data = df[df['code'] == stock]
            if not stock_data.empty:
                profit = stock_data.iloc[0]['net_profit']
                if profit > 10000000:   # 1000万元
                    result[stock] = True
    except Exception as e:
        log.warn('获取利润数据失败：%s' % e)
    return result

def filter_price_cash(stock_list, current_date):
    result = {stock: False for stock in stock_list}
    try:
        close_prices = get_current_data()
        q = query(cash_flow.code, cash_flow.net_operate_cash_flow, 
                  valuation.code, valuation.capitalization).filter(
                      cash_flow.code.in_(stock_list),
                      valuation.code.in_(stock_list))
        df = get_fundamentals(q, date=current_date)
        if df.empty:
            log.warn('现金流或估值表无数据返回')
            return result
        # 打印前5条数据样本
        log.info('现金流数据样例: %s' % df.head(2).to_string())
        for stock in stock_list:
            stock_data = df[df['code'] == stock]
            if not stock_data.empty:
                price = close_prices[stock].close if stock in close_prices else None
                net_cash = stock_data.iloc[0]['net_operate_cash_flow']
                cap = stock_data.iloc[0]['capitalization']
                if price and net_cash and cap:
                    free_cash_per_share = net_cash / cap
                    # 放宽条件：只要每股自由现金流为正就通过（先观察）
                    if free_cash_per_share > 0:
                        result[stock] = True
                        # 可选：打印满足条件的股票
                        # log.info('%s price=%.2f, free_cash=%.2f' % (stock, price, free_cash_per_share))
                else:
                    # 打印缺失原因
                    if not price:
                        log.debug('%s 无价格' % stock)
                    elif not net_cash:
                        log.debug('%s 无经营活动现金流' % stock)
                    elif not cap:
                        log.debug('%s 无总股本' % stock)
    except Exception as e:
        log.warn('获取现金流数据失败：%s' % e)
    return result

def filter_debt_ratio(stock_list, current_date):
    """资产负债率 < 25%"""
    result = {stock: False for stock in stock_list}
    try:
        q = query(balance.code, balance.total_liability, balance.total_assets).filter(
            balance.code.in_(stock_list))
        df = get_fundamentals(q, date=current_date)
        if df.empty:
            log.warn('资产负债表无数据返回')
            return result
        for stock in stock_list:
            stock_data = df[df['code'] == stock]
            if not stock_data.empty:
                liability = stock_data.iloc[0]['total_liability']
                assets = stock_data.iloc[0]['total_assets']
                if assets > 0 and (liability / assets) < 0.25:
                    result[stock] = True
    except Exception as e:
        log.warn('获取资产负债率数据失败：%s' % e)
    return result

def filter_pe_growth(stock_list, current_date):
    result = {stock: False for stock in stock_list}
    try:
        q_pe = query(valuation.code, valuation.pe_ratio).filter(valuation.code.in_(stock_list))
        df_pe = get_fundamentals(q_pe, date=current_date)
        if df_pe.empty:
            log.warn('估值表无数据返回')
            return result
        pe_dict = dict(zip(df_pe['code'], df_pe['pe_ratio']))
        
        q_profit = query(income.code, income.net_profit, income.statDate).filter(income.code.in_(stock_list))
        df_profit = get_fundamentals(q_profit, date=current_date)
        if df_profit.empty:
            log.warn('利润表无数据返回')
            return result
        
        for stock in stock_list:
            stock_profit = df_profit[df_profit['code'] == stock].sort_values('statDate', ascending=False)
            if len(stock_profit) >= 2:
                cur = stock_profit.iloc[0]['net_profit']
                prev = stock_profit.iloc[1]['net_profit']
                if prev and prev != 0:
                    growth = (cur - prev) / abs(prev)
                else:
                    growth = None
            else:
                growth = None
            pe = pe_dict.get(stock)
            # 放宽条件：只要pe>0且growth>0就通过（先观察数量）
            if pe and growth and pe > 0 and growth > 0:
                # 打印比率以便分析
                # log.info('%s pe=%.2f, growth=%.2f, ratio=%.2f' % (stock, pe, growth, pe/growth))
                result[stock] = True
    except Exception as e:
        log.warn('获取市盈率/增长率数据失败：%s' % e)
    return result

def sort_by_ranking(stock_list, candidate_dict, current_date):
    """排序：存货周转率（升序）和预期营收增长率（降序）"""
    ranking_data = []
    try:
        # 获取通过初步筛选的股票
        filtered = [s for s, flag in candidate_dict.items() if flag]
        if not filtered:
            return []
        
        # 使用 indicator 表中的营业收入同比增长率（inc_revenue_year_on_year）作为排序因子
        q = query(indicator.code, indicator.inc_revenue_year_on_year).filter(indicator.code.in_(filtered))
        df = get_fundamentals(q, date=current_date)
        indicator_dict = {}
        for _, row in df.iterrows():
            code = row['code']
            val = row['inc_revenue_year_on_year']
            if pd.isna(val):
                val = 0
            indicator_dict[code] = val
        
        # 预期营收增长率（这里暂时用营业收入同比增长率代替，也可以使用其他因子）
        for stock in filtered:
            inv = indicator_dict.get(stock, 0)   # 营业收入同比增长率，值越大越好
            est = 0   # 预期营收增长率，暂缺数据，用0代替
            ranking_data.append({'code': stock, 'growth': inv, 'est': est})
        
        df_rank = pd.DataFrame(ranking_data)
        if len(df_rank) > 0:
            # 按 growth 降序（越大越好），est 降序
            df_rank = df_rank.sort_values(by=['growth', 'est'], ascending=[False, False])
            return df_rank['code'].tolist()
        else:
            return []
    except Exception as e:
        log.warn('排序数据获取失败：%s' % e)
        return []

def execute_trades(context, buy_list, sell_list):
    # 卖出
    for stock in sell_list:
        if stock in context.portfolio.positions and context.portfolio.positions[stock].total_amount > 0:
            order_target(stock, 0)
            log.info('卖出：%s' % stock)
    # 买入：等权重分配
    if len(buy_list) > 0:
        total_value = context.portfolio.total_value
        target_per_stock = total_value / len(buy_list)
        for stock in buy_list:
            order_target_value(stock, target_per_stock)
            log.info('买入：%s，目标仓位：%.2f元' % (stock, target_per_stock))