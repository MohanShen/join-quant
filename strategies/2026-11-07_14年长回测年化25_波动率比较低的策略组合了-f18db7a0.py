# Clone from JoinQuant
# postId: f18db7a07dce064bb757b39198416b7c
# backtestId: f41305d8c523a94d06248cf9859ea96c
# title: 14年长回测年化25，波动率比较低的策略组合了

# ========== 导入函数库 ==========
import numpy as np
import pandas as pd
import math
import datetime
from jqdata import *
from jqfactor import get_factor_values


# ========== 初始化函数 ==========
def initialize(context):
    # 全局系统设置
    set_option("avoid_future_data", True)
    set_option('use_real_price', True)
    set_benchmark('000300.XSHG')
    log.set_level('order', 'error')
    log.set_level('history', 'error')
    log.set_level('system', 'error')
    
    # ========== 策略C：红利指数增强 参数 ==========
    g.sell_list_C = []
    g.buy_df_C = pd.DataFrame()
    g.target_num_C = [5, 3]
    g.hold_list_C = []
    g.high_limit_list_C = []
    g.cash_C = 0          # 策略C独立可用现金
    g.initial_done_C = False  # C策略是否完成初始建账
    
    # ========== 策略D：ETF核心资产轮动 参数 ==========
    g.etf_pool_D = [
        '518880.XSHG',  # 黄金ETF
        '513100.XSHG',  # 纳指100
        '159915.XSHE',  # 创业板100
        '510180.XSHG',  # 上证180
    ]
    g.m_days_D = 25
    g.cash_D = 0          # 策略D独立可用现金
    g.initial_done_D = False  # D策略是否完成初始建账
    
    # 初始资金分配比例（仅首日生效，之后不再调整）
    g.allocation_ratio = 0.5  # C占初始总资金比例
    
    # ========== 定时任务 ==========
    run_daily(prepare_stock_list_C, '09:00')
    run_monthly(get_stock_list_C, 1, '09:01')
    run_monthly(rebalance_trade_C, 1, '09:30')
    run_daily(check_limit_up_C, '10:00')
    run_daily(trade_D, '09:30')
    run_daily(print_position_all, '15:10')


# ==================== 通用：初始资金拆分 ====================
def split_initial_capital(context):
    """首日一次性拆分资金，之后不再调整"""
    total_cash = context.portfolio.available_cash
    g.cash_C = total_cash * g.allocation_ratio
    g.cash_D = total_cash * (1 - g.allocation_ratio)
    g.initial_done_C = True
    g.initial_done_D = True
    print(f'初始资金拆分完成 | 总资金:{total_cash:.2f} | C:{g.cash_C:.2f} | D:{g.cash_D:.2f}')


# ==================== 策略C：红利指数增强 完整模块 ====================

def prepare_stock_list_C(context):
    g.high_limit_list_C = []
    g.hold_list_C = list(context.portfolio.positions)
    # 过滤掉ETF持仓，只保留股票
    g.hold_list_C = [s for s in g.hold_list_C if s not in g.etf_pool_D]
    
    if len(g.hold_list_C) != 0:
        df = get_price(g.hold_list_C, end_date=context.previous_date, 
                       frequency='daily', fields=['close','high_limit'], 
                       count=1, panel=False, fill_paused=False, skip_paused=False).dropna()
        df = df[df['close'] == df['high_limit']]
        g.high_limit_list_C = list(df.code)

def get_stock_list_C(context):
    # 首日先拆分资金
    if not g.initial_done_C:
        split_initial_capital(context)
    
    g.buy_df_C = pd.DataFrame(index=[], columns=['name', 'price', 'amount', 'value'])
    yesterday = str(context.previous_date)
    today = context.current_dt

    initial_list = get_all_securities('stock', today).index.tolist()
    initial_list = filter_new_stock_C(context, initial_list)
    initial_list = filter_kcb_stock_C(initial_list)
    initial_list = filter_stock_C(initial_list)
    initial_list = filter_paused_stock_C(initial_list)

    # 红利低波线
    stock_list = initial_list
    stock_list = get_dividend_ratio_filter_list_C(context, stock_list, False, 0.00, 0.10, 0.03)
    stock_list = get_factor_filter_list_C(context, stock_list, 'beta', True, 0.00, 0.50)
    HLDB_list = stock_list[:min(g.target_num_C[0], len(stock_list))]

    # 红利价值线
    stock_list = initial_list
    df = get_fundamentals(query(
        valuation.code,
    ).filter(
        valuation.code.in_(stock_list),
        valuation.pe_ratio.between(5, 50),
        indicator.inc_return.between(5, 100),
        indicator.inc_total_revenue_year_on_year.between(5, 100),
        indicator.inc_net_profit_year_on_year.between(10, 100),
    ))
    stock_list = list(df.code)
    stock_list = get_dividend_ratio_filter_list_C(context, stock_list, False, 0.00, 0.10, 0.03)
    HLJZ_list = stock_list[:min(g.target_num_C[1], len(stock_list))]

    target_list = list(set(HLDB_list).union(set(HLJZ_list)))
    
    g.sell_list_C = [s for s in g.hold_list_C if s not in target_list and s not in g.high_limit_list_C]
    buy_list = [s for s in target_list if s not in g.hold_list_C]

    # 计算卖出回款，加入C策略现金池
    sell_value = 0
    for s in g.sell_list_C:
        if s in context.portfolio.positions:
            sell_value += context.portfolio.positions[s].value
    g.cash_C += sell_value

    # 用C自己的现金买入新股
    if len(buy_list) > 0 and g.cash_C > 0:
        value_per = g.cash_C / len(buy_list)
        df = get_price(buy_list, end_date=yesterday, frequency='1d', count=1, 
                       fields=['close'], fq='pre', panel=False, skip_paused=False, fill_paused=True).set_index('code')
        df['today_hl_price'] = [0] * len(df)
        for s in list(df.index):
            df.loc[s, 'today_hl_price'] = round(df.loc[s, 'close'] * 1.05, 2)
        
        g.buy_df_C['name'] = [get_security_info(s, yesterday).display_name for s in buy_list]
        g.buy_df_C['price'] = [df.loc[s, 'today_hl_price'] for s in buy_list]
        g.buy_df_C['amount'] = [100 * int(1.05 * value_per / df.loc[s, 'today_hl_price'] / 100) for s in buy_list]
        g.buy_df_C['value'] = g.buy_df_C['price'] * g.buy_df_C['amount']
        g.buy_df_C.index = buy_list

    print('【策略C】卖出', g.sell_list_C)
    print('————————————————')
    print('【策略C】目标买入', g.buy_df_C)
    print('————————————————')

def rebalance_trade_C(context):
    current_data = get_current_data()
    
    # 先卖出，回款自动计入现金池
    for s in g.sell_list_C:
        if s in context.portfolio.positions and current_data[s].last_price < current_data[s].high_limit:
            order_target_value(s, 0)
    
    # 再买入，只花C自己的钱
    df = g.buy_df_C
    for s in list(df.index):
        if s not in context.portfolio.positions or context.portfolio.positions[s].total_amount == 0:
            print('【策略C】买入', [s, df.loc[s, 'name']])
            order(s, df.loc[s, 'amount'], LimitOrderStyle(df.loc[s, 'price']))
            print('————————————————')

def check_limit_up_C(context):
    current_data = get_current_data()
    if g.high_limit_list_C:
        for s in g.high_limit_list_C:
            if s not in context.portfolio.positions:
                continue
            if current_data[s].last_price < current_data[s].high_limit:
                # 涨停打开卖出，回款回到C现金池
                sell_value = context.portfolio.positions[s].value
                order_target_value(s, 0)
                g.cash_C += sell_value
                print(s, '【策略C】涨停打开，卖出')
                print('————————————————')

# 辅助过滤函数
def filter_paused_stock_C(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]

def filter_stock_C(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list
            if not current_data[stock].is_st
            and 'ST' not in current_data[stock].name
            and '*' not in current_data[stock].name
            and '退' not in current_data[stock].name]

def filter_kcb_stock_C(stock_list):
    return [stock for stock in stock_list 
            if ((stock[0] != '4') and (stock[0] != '8') and (stock[0:2] != '68'))]

def filter_new_stock_C(context, stock_list):
    yesterday = context.previous_date
    return [stock for stock in stock_list 
            if not yesterday - get_security_info(stock).start_date < datetime.timedelta(days=250)]

def get_dividend_ratio_filter_list_C(context, stock_list, sort, p1, p2, threshold):
    time1 = context.previous_date
    time0 = time1 - datetime.timedelta(days=365)
    interval = 1000
    list_len = len(stock_list)
    
    q = query(finance.STK_XR_XD.code, finance.STK_XR_XD.a_registration_date, finance.STK_XR_XD.bonus_amount_rmb
    ).filter(
        finance.STK_XR_XD.a_registration_date >= time0,
        finance.STK_XR_XD.a_registration_date <= time1,
        finance.STK_XR_XD.code.in_(stock_list[:min(list_len, interval)]))
    df = finance.run_query(q)
    
    if list_len > interval:
        df_num = list_len // interval
        for i in range(df_num):
            q = query(finance.STK_XR_XD.code, finance.STK_XR_XD.a_registration_date, finance.STK_XR_XD.bonus_amount_rmb
            ).filter(
                finance.STK_XR_XD.a_registration_date >= time0,
                finance.STK_XR_XD.a_registration_date <= time1,
                finance.STK_XR_XD.code.in_(stock_list[interval*(i+1):min(list_len, interval*(i+2))]))
            temp_df = finance.run_query(q)
            df = df.append(temp_df)
    
    dividend = df.fillna(0).set_index('code').groupby('code').sum()
    temp_list = list(dividend.index)
    
    q = query(valuation.code, valuation.market_cap).filter(valuation.code.in_(temp_list))
    cap = get_fundamentals(q, date=time1).set_index('code')
    
    df = pd.concat([dividend, cap], axis=1, sort=False)
    df['dividend_ratio'] = (df['bonus_amount_rmb'] / 1000) / df['market_cap']
    df = df.sort_values(by=['dividend_ratio'], ascending=sort)
    df = df[int(p1*len(df)):int(p2*len(df))]
    df = df[df['dividend_ratio'] > threshold]
    return list(df.index)

def get_factor_filter_list_C(context, stock_list, jqfactor, sort, p1, p2):
    yesterday = context.previous_date
    score_list = get_factor_values(stock_list, jqfactor, end_date=yesterday, count=1)[jqfactor].iloc[0].tolist()
    df = pd.DataFrame(columns=['code', 'score'])
    df['code'] = stock_list
    df['score'] = score_list
    df = df.dropna()
    df.sort_values(by='score', ascending=sort, inplace=True)
    final_list = list(df.code)[int(p1*len(df)):int(p2*len(df))]
    return final_list


# ==================== 策略D：ETF核心资产轮动 完整模块 ====================

def get_rank_D():
    score_list = []
    for etf in g.etf_pool_D:
        df = attribute_history(etf, g.m_days_D, '1d', ['close'])
        df['log'] = np.log(df['close'])
        y = df['log']
        x = np.arange(len(df))
        
        slope, intercept = np.polyfit(x, y, 1)
        annualized_returns = math.pow(math.exp(slope), 250) - 1
        r_squared = 1 - (sum((y - (slope * x + intercept))**2) / ((len(y) - 1) * np.var(y, ddof=1)))
        score = annualized_returns * r_squared
        score_list.append(score)
    
    df = pd.DataFrame(index=g.etf_pool_D, data={'score': score_list})
    df = df.sort_values(by='score', ascending=False)
    rank_list = list(df.index)
    
    print(df)
    record(黄金=round(df.loc['518880.XSHG'], 2))
    record(纳指=round(df.loc['513100.XSHG'], 2))
    record(成长=round(df.loc['159915.XSHE'], 2))
    record(价值=round(df.loc['510180.XSHG'], 2))
    return rank_list

def trade_D(context):
    # 首日先拆分资金
    if not g.initial_done_D:
        split_initial_capital(context)
    
    target_num = 1
    target_list = get_rank_D()[:target_num]
    if not target_list:
        return
    
    target_etf = target_list[0]
    hold_etfs = [s for s in context.portfolio.positions if s in g.etf_pool_D]
    
    # 卖出非目标ETF，回款回到D现金池
    for etf in hold_etfs:
        if etf != target_etf:
            sell_value = context.portfolio.positions[etf].value
            order_target_value(etf, 0)
            g.cash_D += sell_value
            print('【策略D】卖出' + str(etf))
    
    # 买入目标ETF，全仓花D自己的现金
    if target_etf not in context.portfolio.positions or context.portfolio.positions[target_etf].total_amount == 0:
        if g.cash_D > 0:
            order_target_value(target_etf, g.cash_D)
            g.cash_D = 0  # 全仓买入后现金归零
            print('【策略D】全仓买入' + str(target_etf))


# ==================== 收盘复盘打印 ====================
def print_position_all(context):
    print('=' * 60)
    print(f'账户总净值: {context.portfolio.total_value:.2f}')
    
    # 统计C部分市值+现金
    stock_value = 0
    for pos in context.portfolio.positions.values():
        if pos.security not in g.etf_pool_D:
            stock_value += pos.value
    c_total = stock_value + g.cash_C
    print(f'策略C（红利增强）权益: {c_total:.2f} | 持仓:{stock_value:.2f} 现金:{g.cash_C:.2f} | 占比: {c_total/context.portfolio.total_value*100:.1f}%')
    
    # 统计D部分市值+现金
    etf_value = 0
    for etf in g.etf_pool_D:
        if etf in context.portfolio.positions:
            etf_value += context.portfolio.positions[etf].value
    d_total = etf_value + g.cash_D
    print(f'策略D（ETF轮动）权益: {d_total:.2f} | 持仓:{etf_value:.2f} 现金:{g.cash_D:.2f} | 占比: {d_total/context.portfolio.total_value*100:.1f}%')
    
    print('=' * 60)
