# Clone from JoinQuant
# postId: 39e18ad8415252955ee14375dcbfdc4c
# backtestId: 965e50777e7423d75628ad062cfc2eb6
# title: 请帮忙修改代码

from jqdata import *
def initialize(context):
    set_option('use_real_price', True)
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('history', 'error')
    g.buy_stock_count = 5
    g.stock_list = []
    run_monthly(get_stock_list,1,'09:01')
    run_daily(my_trade,'09:30')
def get_stock_list(context):
    stock_list = get_all_securities().index.tolist()
    g.stock_list = ffscore_stock(context,5,stock_list,context.current_dt.date())
    return g.stock_list
def my_trade(context):
    check_out_lists = g.stock_list
    q = query(valuation.code).filter(valuation.code.in_(check_out_lists)).order_by(valuation.circulating_market_cap.asc()).limit(g.buy_stock_count * 4)
    check_out_lists = list(get_fundamentals(q).code)
    check_out_lists = filter_new_stock(context, check_out_lists)  # 过滤新股
    check_out_lists = filter_st_stock(check_out_lists)  # 过滤ST股票
    check_out_lists = filter_paused_stock(check_out_lists)
    check_out_lists = filter_limitup_stock(context, check_out_lists)
    check_out_lists = filter_limitdown_stock(context, check_out_lists)
    check_out_lists = check_out_lists[:g.buy_stock_count]
    adjust_position(context, check_out_lists)
def open_position(security, value):
    order = order_target_value_(security, value)
    if order != None and order.filled > 0:
        return True
    return False
def close_position(position):
    security = position.security
    order = order_target_value_(security, 0)
    if order != None:
        if order.status == OrderStatus.held and order.filled == order.amount:
            return True    
    return False
def adjust_position(context, buy_stocks):
	for stock in context.portfolio.positions:
		if stock not in buy_stocks:
			log.info("持仓中的股票 [%s] 无法购买" % (stock))
			position = context.portfolio.positions[stock]
			close_position(position)
		else:
			log.info("股票 [%s] 已经在持仓中" % (stock))
	position_count = len(context.portfolio.positions)
	if g.buy_stock_count > position_count:
		value = context.portfolio.cash / (g.buy_stock_count - position_count)
		
		for stock in buy_stocks:
			if context.portfolio.positions[stock].total_amount == 0:
				if open_position(stock, value):
					if len(context.portfolio.positions) == g.buy_stock_count:
						break
def order_target_value_(security, value):
	if value == 0:
		log.debug("卖出 %s" % (security))
	else:
		log.debug("下单 %s" % (security))
	return order_target_value(security, value)
#2-1 过滤停牌股票
def filter_paused_stock(stock_list):
	current_data = get_current_data()
	return [stock for stock in stock_list if not current_data[stock].paused]
#2-2 过滤ST及其他具有退市标签的股票
def filter_st_stock(stock_list):
	current_data = get_current_data()
	return [stock for stock in stock_list
			if not current_data[stock].is_st
			and 'ST' not in current_data[stock].name
			and '*' not in current_data[stock].name
			and '退' not in current_data[stock].name]
#2-3 获取最近N个交易日内有涨停的股票
def get_recent_limit_up_stock(context, stock_list, recent_days):
    yesterday = context.previous_date
    h = get_price(stock_list, end_date=yesterday, frequency='daily', fields=['close', 'high_limit', 'paused'],
                  count=recent_days, panel=False)
    s_limit = h.query('close==high_limit and paused==0').groupby('code')['high_limit'].count()
    return s_limit.index.tolist()
#2-4 过滤涨停的股票
def filter_limitup_stock(context, stock_list):
	last_prices = history(1, unit='1m', field='close', security_list=stock_list)
	current_data = get_current_data()
	return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
			or last_prices[stock][-1] < current_data[stock].high_limit]
#2-5 过滤跌停的股票
def filter_limitdown_stock(context, stock_list):
	last_prices = history(1, unit='1m', field='close', security_list=stock_list)
	current_data = get_current_data()
	return [stock for stock in stock_list if stock in context.portfolio.positions.keys()
			or last_prices[stock][-1] > current_data[stock].low_limit]
#2-7 过滤次新股
def filter_new_stock(context,stock_list):
    yesterday = context.previous_date
    return [stock for stock in stock_list if not yesterday - get_security_info(stock).start_date < datetime.timedelta(days=12)]
def ffscore_stock(context,score,security_list,date):
    my_watch_date = date
    one_year_ago = my_watch_date - datetime.timedelta(days=365)
    h = get_history_fundamentals(security_list,
                             [indicator.adjusted_profit,
                              balance.total_current_assets,
                              balance.total_assets,
                              balance.total_current_liability,
                              balance.total_non_current_liability,
                              cash_flow.net_operate_cash_flow,
                              income.operating_revenue,
                              income.operating_cost,
                              ],
                             watch_date=my_watch_date, count=5).dropna()                           
    def ttm_sum(x):
        return x.iloc[1:].sum()
    def ttm_avg(x):
        return x.iloc[1:].mean()
    def pre_ttm_sum(x):
        return x.iloc[:-1].sum()
    def pre_ttm_avg(x):
        return x.iloc[:-1].mean()    
    def val_1(x):
        return x.iloc[-1]    
    def val_2(x):
        if len(x.index) > 1:
            return x.iloc[-2]
        else:
            return nan
    adjusted_profit_ttm = h.groupby('code')['adjusted_profit'].apply(ttm_sum)
    adjusted_profit_ttm_pre = h.groupby('code')['adjusted_profit'].apply(pre_ttm_sum)    
    total_assets_avg = h.groupby('code')['total_assets'].apply(ttm_avg)
    total_assets_avg_pre = h.groupby('code')['total_assets'].apply(pre_ttm_avg)    
    net_operate_cash_flow_ttm = h.groupby('code')['net_operate_cash_flow'].apply(ttm_sum)    
    long_term_debt_ratio = h.groupby('code')['total_non_current_liability'].apply(val_1) / h.groupby('code')['total_assets'].apply(val_1)
    long_term_debt_ratio_pre = h.groupby('code')['total_non_current_liability'].apply(val_2) / h.groupby('code')['total_assets'].apply(val_2)    
    current_ratio = h.groupby('code')['total_current_assets'].apply(val_1) / h.groupby('code')['total_current_liability'].apply(val_1)
    current_ratio_pre = h.groupby('code')['total_current_assets'].apply(val_2) / h.groupby('code')['total_current_liability'].apply(val_2)    
    operating_revenue_ttm = h.groupby('code')['operating_revenue'].apply(ttm_sum)
    operating_revenue_ttm_pre = h.groupby('code')['operating_revenue'].apply(pre_ttm_sum)    
    operating_cost_ttm = h.groupby('code')['operating_cost'].apply(ttm_sum)
    operating_cost_ttm_pre = h.groupby('code')['operating_cost'].apply(pre_ttm_sum)    
    roa = adjusted_profit_ttm / total_assets_avg
    roa_pre = adjusted_profit_ttm_pre / total_assets_avg_pre    
    ocfoa = net_operate_cash_flow_ttm / total_assets_avg    
    roa_chg = roa - roa_pre    
    ocfoa_roa = ocfoa - roa    
    ltdr_chg = long_term_debt_ratio - long_term_debt_ratio_pre    
    cr_chg = current_ratio - current_ratio_pre    
    gpm_chg = operating_cost_ttm_pre/operating_revenue_ttm_pre - operating_cost_ttm/operating_revenue_ttm
    tat_chg = operating_revenue_ttm/total_assets_avg - operating_revenue_ttm_pre/total_assets_avg_pre
    spo_list = list(set(finance.run_query(
        query(
            finance.STK_CAPITAL_CHANGE.code
        ).filter(
            finance.STK_CAPITAL_CHANGE.code.in_(security_list),
            finance.STK_CAPITAL_CHANGE.pub_date.between(one_year_ago, my_watch_date),
            finance.STK_CAPITAL_CHANGE.change_reason_id == 306004)
    )['code']))    
    spo_score = pd.Series(True, index = security_list)
    if spo_list:
        spo_score[spo_list] = False        
    df_scores = pd.DataFrame(index=security_list)
    df_scores['roa'] = roa>0
    df_scores['ocfoa'] = ocfoa>0
    df_scores['roa_chg'] = roa_chg>0
    df_scores['ocfoa_roa'] = ocfoa_roa>0
    df_scores['ltdr_chg'] = ltdr_chg<=0
    df_scores['cr_chg'] = cr_chg>0
    df_scores['spo'] = spo_score>0
    df_scores['gpm_chg'] = gpm_chg>0
    df_scores['tat_chg'] = tat_chg>0
    df_scores = df_scores.dropna()
    df_scores['total'] = df_scores['roa'] + df_scores['ocfoa'] + df_scores['roa_chg'] + \
        df_scores['ocfoa_roa'] + df_scores['ltdr_chg'] + df_scores['cr_chg'] + \
        df_scores['spo'] + df_scores['gpm_chg'] + df_scores['tat_chg']
    res  = df_scores.loc[lambda df_scores: df_scores['total'] < score].sort_values(by = 'total',ascending=False).index
    q = get_fundamentals(query(
             indicator.code,indicator.roe
           ).filter(
             indicator.code.in_(res)
           ).order_by(indicator.roe.desc()).limit(len(res)))
    res = list(q['code'])
    return res