# Clone from JoinQuant
# postId: e7c95ca1f1e6363e12c45a0f8554eec4
# backtestId: d02db35a2c97481a0448b416147109bf
# title: 六因子选股版破净策略 附PT迁移版在各时期的回测截图

# 克隆自聚宽文章：https://www.joinquant.com/post/57664
# 标题：破净大杂烩,20年至今稳定盈利,年化38回撤26
# 作者：loolitaaa

# 导入函数库
from jqdata import *
from jqfactor import *
import datetime
import pandas as pd
import numpy as np


# 初始化函数，设定基准等等
def initialize(context):
    # 设定沪深300作为基准
    set_benchmark('000300.XSHG')
    # 开启动态复权模式(真实价格)
    set_option('use_real_price', True)
    # 防止未来函数
    set_option("avoid_future_data", True)
    # 日志级别设置
    log.set_level('order', 'error')
    
    # 滑点设置
    set_slippage(FixedSlippage(1/1000))
    set_slippage(PriceRelatedSlippage(6/1000))
    # 设置交易成本万分之三，不同滑点影响可在归因分析中查看
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=2.5/10000, close_commission=2.5/10000, close_today_commission=0, min_commission=5),type='stock')
    
    # 策略参数
    g.top_n = 1  # 每个维度筛选的股数
    g.min_roa = 1.5
    g.min_roe = 3.0
    g.min_net_profit = 1e6
    g.min_cash_flow = 1e6
    g.calm_down_period = 8  # 卖出冷静期
    g.if_check_calendar_effect = True  # 是否检查日历效应
    
    # 初始化
    g.calendar_signal = False  # 初始化日历信号
    g.target_list = []  # 初始化目标列表
    g.yesterday_HL_list = []  # 初始化昨日涨停列表
    g.just_sold = {}  # 初始化最近卖出字典
    
    # 运行函数
    run_daily(prepare_stock_list, time='9:00')
    # run_weekly(trade_func, 1, time='9:32')
    run_monthly(trade_func, 1, time='9:32')
    run_daily(check_limit_up, time="14:00")
    run_daily(check_limit_up, time="14:50")
    run_daily(update_just_sold_stocks, time='15:01')


#1-1 准备股票池
def prepare_stock_list(context):
    # 获取已持有列表
    g.high_limit_list = []   
    hold_list = list(context.portfolio.positions)
    # 获取昨日涨停列表
    if hold_list:
        df = get_price(hold_list, end_date=context.previous_date, frequency='daily',
                       fields=['close', 'high_limit'],
                       count=1, panel=False)
        g.high_limit_list = df[df['close'] == df['high_limit']]['code'].tolist()
    # 判断当前交易日是否存在日历效应
    if g.if_check_calendar_effect:
        g.calendar_signal = check_calendar_effect(context, check_interval=[('01-01', '01-31'), ('04-01', '04-30')])

#1-2 选股模块
def get_stock_list(context):
    # 获取当前交易日期
    current_date = context.current_dt.date()
    # 获取上一个交易日期
    previous_date = context.previous_date
    # 获取所有上市股票的列表
    # initial_list = get_all_securities('stock', date=previous_date).index.tolist()
    initial_list = get_index_stocks('000985.XSHG', date=previous_date)
    # 过滤股票
    initial_list = filter_stocks(context, initial_list)
    # 过滤最近卖出列表
    just_sold_list = list(g.just_sold.keys())
    initial_list = list(set(initial_list) - set(just_sold_list))

    # 筛选破净股
    q = query(
        valuation.code,
        valuation.market_cap,
        indicator.roa,
        ).filter(
        valuation.code.in_(initial_list),
        # valuation.market_cap > g.min_market_cap,
        valuation.pb_ratio.between(0, 1),
        income.np_parent_company_owners > 0,
        income.net_profit > g.min_net_profit,
        indicator.adjusted_profit > g.min_net_profit,
        # income.operating_revenue > 1e8,
        cash_flow.net_operate_cash_flow > g.min_cash_flow,
        cash_flow.subtotal_operate_cash_inflow > g.min_cash_flow,
        cash_flow.subtotal_operate_cash_inflow / indicator.adjusted_profit > 1,
        indicator.roa > g.min_roa,
        indicator.roe > g.min_roe,
        indicator.inc_return > 0,
        indicator.net_profit_margin > 5,
        indicator.inc_net_profit_year_on_year > 0,
        )
    stock_list = get_fundamentals(q, date=previous_date).code.tolist()
    
    if not stock_list:
        log.info("无符合条件的破净股票, 清空持仓")
        return {}
    
    # 多维指标筛选
    indicators = {
        'roa_top': get_roa_top(context, stock_list, top_n=g.top_n),
        'roag_top': get_roag_top(context, stock_list, top_n=g.top_n),
        'roic_top': get_roic_top(context, stock_list, top_n=g.top_n),
        'ebit_top': get_ebit_top(context, stock_list, p=0.5, top_n=g.top_n),
        'gross_margin_top': get_gross_margin_top(context, stock_list, top_n=g.top_n),
        'f_score_top': get_f_score_top(context, stock_list, top_n=g.top_n)
    }
    
    # 合并并统计权重
    targets = pd.Series([s for sublist in indicators.values() for s in sublist])
    targets = targets.value_counts() / targets.value_counts().sum()
    targets = targets.sort_values(ascending=False).to_dict()
    return targets

#1-3 调仓函数
def trade_func(context):
    # 获取持有列表
    hold_list = list(context.portfolio.positions)
    if not g.calendar_signal:
        # 获取最近卖出列表
        just_sold_list = list(g.just_sold.keys())
        # 筛选股票池
        target_dict = get_stock_list(context)
        print("筛选结果:", target_dict)
        g.target_list = list(target_dict.keys())
        buy_list = [s for s in g.target_list if s not in just_sold_list]
        # 卖出目标以为的股票
        sell_list = [s for s in hold_list if s not in buy_list and s not in g.high_limit_list]
        sell_stocks(context, sell_list)
        # 买入目标股票
        buy_stocks(context, buy_list)
    else:
        sell_stocks(context, hold_list)


#2-1 卖出昨日涨停但今日未继续涨停的股票
def check_limit_up(context):
    # 获取当前的市场数据
    current_data = get_current_data()
    sell_list = []
    # 检查是否已有昨日涨停的股票列表
    if len(g.high_limit_list) > 0:  
        for stock in g.high_limit_list:
            if current_data[stock].last_price < current_data[stock].high_limit:
                log.info("[%s]涨停打开，考虑卖出" % current_data[stock].name)
                sell_list.append(stock)
                g.just_sold[stock] = 0
            else:
                log.info("[%s]涨停，继续持有" % current_data[stock].name)
    # 如果卖出列表不为空，执行卖出操作
    if sell_list:
        sell_stocks(context, sell_list)

#2-2 更新最近卖出字典
def update_just_sold_stocks(context):
    # 更新最近卖出股票的冷静期
    for s in list(g.just_sold.keys()):
        if g.just_sold[s] >= g.calm_down_period:
            del g.just_sold[s]
        else:
            g.just_sold[s] += 1  


#3-1 买入股票函数
def buy_stocks(context, buy_list):
    # 获取当前的市场数据
    current_data = get_current_data()
    # 计算每只股票的购买金额，即总可用资金除以剩余需要购买的股票数量
    target_value = context.portfolio.available_cash / len(buy_list)
    for s in buy_list:
        # 如果股票不在当前持仓中，则执行购买
        if s not in context.portfolio.positions:
            # 记录买入操作
            log.info('买入:', s, current_data[s].name)
            order_value(s, target_value)

#3-2 卖出股票函数
def sell_stocks(context, sell_list):
    # 获取当前的市场数据
    current_data = get_current_data()
    # 检查是否有股票需要卖出
    if len(sell_list) > 0:
        for s in sell_list:
            # 记录卖出操作
            log.info('卖出:', s, current_data[s].name)
            # # 设置限价单的价格为当前价格的95%或当天跌停价中的较高者
            # limit_price = max(current_data[s].last_price * 0.95, current_data[s].low_limit)
            # # 下达限价卖出指令，目标是将该股票的持仓数量降至0
            # limit_order = order_target_value(s, 0, LimitOrderStyle(limit_price))
            limit_order = order_target_value(s, 0)
            # 如果下单失败，记录失败信息
            if limit_order is None:     
                log.info("卖出失败 %s" % (current_data[s].name))


## 指标选股函数
def get_roa_top(context, stock_list, top_n):
    # 筛选ROA最高的若干只股票
    previous_date = context.previous_date
    q = query(
        valuation.code,
        valuation.market_cap,
        indicator.roa).filter(
            valuation.code.in_(stock_list))
    df = get_fundamentals(q, date=previous_date)
    df = df.sort_values(by=['roa', 'market_cap'], ascending=[False, False])
    return df.code.tolist()[:top_n]

def get_roag_top(context, stock_list, top_n):
    # 筛选ROA加权平均增长率最高的若干只股票
    previous_date = context.previous_date
    df = get_history_fundamentals(
        stock_list, fields=[
            indicator.code, indicator.roa],
            watch_date=previous_date, count=5, interval='1q')
    df = df.groupby('code').apply(lambda group: group.reset_index()).roa.unstack()
    df['past_growth_rate'] = 0.1 * df.iloc[:,0] + 0.2 * df.iloc[:,1] + 0.3 * df.iloc[:,2] + 0.4 * df.iloc[:,3]
    df['current_growth_rate'] = 0.1 * df.iloc[:,1] + 0.2 * df.iloc[:,2] + 0.3 * df.iloc[:,3] + 0.4 * df.iloc[:,4]
    df['delta_growth_rate'] = df['current_growth_rate'] - df['past_growth_rate']
    df.dropna(inplace=True)
    df.sort_values(by='delta_growth_rate', ascending=False, inplace=True)
    return list(df.index)[:top_n]

def get_roic_top(context, stock_list, top_n):
    # 筛选投入资本回报率最高的若干只股票
    previous_date = context.previous_date
    # 获取最新的投入资本数据
    q = query(
        balance.code,
        balance.total_owner_equities,  # 股东权益合计
        balance.non_current_liability_in_one_year,  # 一年内到期的非流动负债
        balance.longterm_loan,  # 长期借款
        balance.bonds_payable,  # 应付债券
        balance.longterm_account_payable,  # 长期应付款
        ).filter(
            balance.code.in_(stock_list))
    roic_data = get_fundamentals(q, date=previous_date).set_index('code')
    roic_data.fillna(0, inplace=True)  # 以0来填充缺失值
    # 计算投入资本
    roic_data['investment_capital'] = roic_data['total_owner_equities'] + roic_data['non_current_liability_in_one_year'] + \
        roic_data['longterm_loan'] + roic_data['bonds_payable'] + roic_data['longterm_account_payable']
    # 获取过去4个季度的息税前利润数据
    ebit_data = get_history_fundamentals(
        stock_list, fields=[
            indicator.adjusted_profit,  # 扣非净利润
            income.income_tax_expense,  # 所得税费用
            income.financial_expense,  # 财务费用
            ], 
        watch_date=previous_date, interval='1q', count=4, stat_by_year=False)
    ebit_data = ebit_data.groupby('code').sum()
    # 计算息税前利润
    ebit_data['ebit'] = ebit_data['adjusted_profit'] + ebit_data['income_tax_expense'] + ebit_data['financial_expense']
    # 合并数据
    roic_data = pd.concat([roic_data, ebit_data], axis=1)
    # 计算投入资本回报率
    roic_data['roic'] = roic_data['ebit'] / roic_data['investment_capital']
    # 过滤ROIC为空值或无穷大的股票
    roic_data = roic_data.replace([np.inf, -np.inf], np.nan).dropna()
    if roic_data.empty:
        log.info("ROIC计算结果为空")
        return []
    roic_data = roic_data.sort_values(by='roic', ascending=False)
    return roic_data.index.tolist()[:top_n]

def get_ebit_top(context, stock_list, p, top_n):
    # 筛选息税前利润率最高的若干只股票
    previous_date = context.previous_date
    q = query(
        income.code,
        indicator.adjusted_profit,  # 扣非净利润
        income.income_tax_expense,  # 所得税费用
        income.financial_expense,  # 财务费用
        income.operating_revenue,  # 营业收入
        ).filter(
            income.code.in_(stock_list))
    ebit_data = get_fundamentals(q, date=previous_date).set_index('code')
    # 计算息税前利润
    ebit_data['ebit'] = ebit_data['adjusted_profit'] + ebit_data['income_tax_expense'] + ebit_data['financial_expense']
    ebit_data = ebit_data[ebit_data['ebit'] > 0]
    ebit_data = ebit_data.sort_values(by='ebit', ascending=False)[:int(p * len(stock_list))]
    ebit_data['ebit_ratio'] = ebit_data['ebit'] / ebit_data['operating_revenue']
    ebit_data = ebit_data.sort_values(by='ebit_ratio', ascending=False)
    return ebit_data.index.tolist()[:top_n]

def get_gross_margin_top(context, stock_list, top_n):
    # 筛选毛利率最高的若干只股票
    previous_date = context.previous_date
    q = query(
        indicator.code,
        indicator.gross_profit_margin
        ).filter(
            indicator.code.in_(stock_list)
            ).order_by(indicator.gross_profit_margin.desc()).limit(top_n)
    return get_fundamentals(q, date=previous_date).code.tolist()

def get_f_score_top(context, stock_list, top_n):
    # 筛选FScore最高的若干只股票
    previous_date = context.previous_date
    df = get_history_fundamentals(
        stock_list, fields=[
            indicator.roe,  # 净资产收益率
            indicator.roa,  # 总资产收益率
            indicator.gross_profit_margin,  # 毛利率
            income.operating_revenue,  # 营业收入
            income.total_profit,  # 利润总额
            income.financial_expense,  # 财务费用
            cash_flow.net_operate_cash_flow,  # 经营活动产生的现金流量净额
            balance.total_assets,  # 总资产
            balance.total_current_assets,  # 流动资产
            balance.total_non_current_assets,  # 非流动资产
            balance.total_current_liability,  # 流动负债
            balance.total_non_current_liability,  # 非流动负债
            balance.paidin_capital,  # 实收资本
            ], 
        watch_date=previous_date, interval='1q', count=5, stat_by_year=False)
    df = df.groupby('code').filter(lambda group: len(group) >= 5)
    df = df.sort_values(by=['code', 'statDate'], ascending=[True, True])
    df['weighted_total_current_assets'] = df.groupby('code')['total_current_assets'].rolling(2, min_periods=2).mean().reset_index(level=0, drop=True)
    df['ebit'] = df['total_profit'] + df['financial_expense']
    df['ebit_ratio'] = df['ebit'] / df['weighted_total_current_assets']
    df['cfo'] = df['net_operate_cash_flow'] / df['total_assets']
    df['accrual'] = df['cfo'] - 0.01 * df['roa']
    df['lever'] = df['total_non_current_liability'] / df['total_non_current_assets']
    df['liquid'] = df['total_current_assets'] / df['total_current_liability']
    df['caturn'] = df['operating_revenue'] / df['weighted_total_current_assets']
    stats = pd.DataFrame({
        'last_roe': df.groupby('code')['roe'].last(),
        'last_roa': df.groupby('code')['roa'].last(),
        'delta_roe': df.groupby('code')['roe'].apply(lambda group: group.iloc[-1] - group.iloc[-4]),
        'delta_roa': df.groupby('code')['roa'].apply(lambda group: group.iloc[-1] - group.iloc[-4]),
        'last_ebit_ratio': df.groupby('code')['ebit_ratio'].last(),
        'delta_ebit_ratio': df.groupby('code')['ebit_ratio'].apply(lambda group: group.iloc[-1] - group.iloc[-4]),
        'last_cfo': df.groupby('code')['cfo'].last(),
        'last_accrual': df.groupby('code')['accrual'].last(),
        'delta_lever': df.groupby('code')['lever'].apply(lambda group: group.iloc[-4] - group.iloc[-1]),
        'delta_liquid': df.groupby('code')['liquid'].apply(lambda group: group.iloc[-1] - group.iloc[-4]),
        'delta_margin': df.groupby('code')['gross_profit_margin'].apply(lambda group: group.iloc[-1] - group.iloc[-4]),
        'eq_offser': df.groupby('code')['paidin_capital'].apply(lambda group: group.iloc[-1] - group.iloc[-4]),
        'delta_caturn': df.groupby('code')['caturn'].apply(lambda group: group.iloc[-1] - group.iloc[-4]),
        })
    stats['f_score'] = (stats > 0).sum(axis=1)
    stats = stats.sort_values(by=['f_score', 'last_roa'], ascending=[False, False])
    return stats.index.tolist()[:top_n]


## 过滤各种股票
def filter_stocks(context, stock_list):
    current_data = get_current_data()
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    filtered_stocks = []
    for stock in stock_list:
        # # 过滤科创北交股票
        if stock.startswith('68') or stock.startswith('8') or stock.startswith('4'):
            continue
        # 过滤停牌股票
        if current_data[stock].paused:
            continue
        # 过滤ST及其他具有退市标签的股票
        if current_data[stock].is_st:
            continue
        if '退' in current_data[stock].name or '*' in current_data[stock].name or '退' in current_data[stock].name:
            continue
        # 过滤涨停的股票
        if not (stock in context.portfolio.positions or last_prices[stock][-1] < current_data[stock].high_limit):
            continue
        # 过滤跌停的股票
        if not (stock in context.portfolio.positions or last_prices[stock][-1] > current_data[stock].low_limit):
            continue
        # 过滤次新股
        start_date = get_security_info(stock).start_date
        if context.previous_date - start_date < timedelta(days=252):
            continue
        filtered_stocks.append(stock)
    return filtered_stocks


## 判断当前交易日是否存在日历效应
def check_calendar_effect(context, check_interval):
    today = context.current_dt.strftime('%m-%d')
    for start_date, end_date in check_interval:
        if (start_date <= today) and (today <= end_date):
            return True
    else:
        return False
    