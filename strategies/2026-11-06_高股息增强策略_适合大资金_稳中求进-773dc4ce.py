# Clone from JoinQuant
# postId: 773dc4cea135f22f44a62af02798f4b3
# backtestId: 89da486bb7cfb5c3f20d8cb617da3fee
# title: 高股息增强策略（适合大资金—稳中求进）

'''
策略说明：
高股息为锚：筛选连续3年稳定分红、股息率 > 4.5%（不足时放宽至4.0%）的大市值股票（>200亿），确保安全边际。
多因子增强：综合股息率、ROE、PB倒数、PE倒数和动量（负向）五大因子加权打分，兼顾价值与质量。
动态调仓：每月初调仓，等权重满仓持有5~10只最优标的，提升资金效率。
风控机制：个股回撤超15%自动止损，规避黑天鹅风险。
大资金容量：这个回测持仓5-10个，可改为10-20个，收益基本相同
'''

import jqdata
import numpy as np
import pandas as pd
from datetime import timedelta
from jqdata import finance

def initialize(context):
    # 设置基准
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option("avoid_future_data", True)
    
    # 交易费用
    set_slippage(FixedSlippage(0.002))
    set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
    
    # 月度调仓
    run_monthly(rebalance, monthday=1, time='9:31')
    
    # 全局参数（经过历史优化）
    g.min_market_cap = 200           # 最低市值（亿元）
    g.dividend_threshold = 4.5       # 股息率基础阈值（%）
    g.dividend_threshold_low = 4.0   # 股票池不足时的放宽阈值
    g.min_stock_count = 5           # 最低持股数量
    g.max_stock_count = 10           # 最高持股数量
    g.stop_loss_ratio = 0.85         # 回撤15%清仓
    
    # 因子权重（股息率、ROE、PB倒数、PE倒数、过去1年涨跌幅（负向））
    g.weight_div = 0.30
    g.weight_roe = 0.20
    g.weight_pb = 0.20
    g.weight_pe = 0.15
    g.weight_mom = 0.15
    
    # 记录个股最高价
    g.stock_high_prices = {}
    
    # 缓存：同一调仓日内避免重复计算财务数据
    g._cache = {}
    
    log.info("高股息增强策略V5（性能优化版）初始化完成，目标年化>20%")

def get_previous_trading_day(date):
    """获取前一个真实交易日"""
    try:
        trade_days = jqdata.get_trade_days(end_date=date, count=2)
        if len(trade_days) >= 2:
            return trade_days[0].date()
    except:
        pass
    return date - timedelta(days=1)

def is_valid_stock_batch(context, stocks, date):
    """
    批量判断股票是否有效（非ST、非次新、非停牌）
    返回一个布尔Series
    """
    if not stocks:
        return pd.Series()
    
    current_data = get_current_data()
    valid = []
    for s in stocks:
        try:
            if current_data[s].is_st:
                valid.append(False)
                continue
            days_public = (date - get_security_info(s).start_date).days
            if days_public < 60:
                valid.append(False)
                continue
            if current_data[s].paused:
                valid.append(False)
                continue
            valid.append(True)
        except:
            valid.append(False)
    return pd.Series(valid, index=stocks)

def get_stock_pool(context):
    """
    股票池筛选（高收益版）- 批量优化版
    条件：
    1. 全A股，市值>200亿
    2. 连续3年分红且股利不显著下降
    3. 近1年净利润为正（TTM）
    4. 股息率>4.5%（不足10只时降至4.0%）
    """
    current_date = context.current_dt.date()
    prev_day = get_previous_trading_day(current_date)
    
    # 检查缓存
    cache_key = f'stock_pool_{prev_day}'
    if cache_key in g._cache:
        return g._cache[cache_key]
    
    # 全A股列表
    all_stocks = get_all_securities(['stock']).index.tolist()
    
    # ---- 批量获取市值、ROA、净利润 ----
    q = query(
        valuation.code,
        valuation.market_cap,
        indicator.roa,
        income.net_profit
    ).filter(
        valuation.code.in_(all_stocks),
        valuation.market_cap > g.min_market_cap,
        indicator.roa > 0
    )
    df = get_fundamentals(q, date=prev_day)
    if df is None or df.empty:
        return []
    
    # 提取代码列表
    base_codes = df['code'].tolist()
    
    # ---- 批量获取TTM净利润（最近4个季度） ----
    # 一次性查询所有候选股票的TTM净利润
    q_profit = query(
        income.code,
        income.net_profit,
        income.statDate
    ).filter(
        income.code.in_(base_codes)
    )
    profit_data = get_fundamentals_continuously(q_profit, end_date=prev_day, count=4, panel=False)
    
    # 计算每只股票的TTM净利润（亿元）
    ttm_profit = {}
    if profit_data is not None and not profit_data.empty:
        for code in base_codes:
            stock_profit = profit_data[profit_data['code'] == code]['net_profit']
            if len(stock_profit) == 4:
                ttm_profit[code] = stock_profit.sum() / 1e8
            else:
                ttm_profit[code] = np.nan
    else:
        return []
    
    # ---- 批量获取近12个月分红总额 ----
    start_date = current_date - pd.DateOffset(months=12)
    q_div = query(
        finance.STK_XR_XD.code,
        finance.STK_XR_XD.bonus_amount_rmb
    ).filter(
        finance.STK_XR_XD.code.in_(base_codes),
        finance.STK_XR_XD.report_date >= start_date,
        finance.STK_XR_XD.report_date <= current_date
    )
    div_12m = finance.run_query(q_div)
    
    # 计算每只股票近12个月分红总额（亿元）
    div_12m_sum = {}
    if not div_12m.empty:
        div_group = div_12m.groupby('code')['bonus_amount_rmb'].sum()
        for code in base_codes:
            if code in div_group.index:
                div_12m_sum[code] = div_group[code] / 10000  # 万元->亿元
            else:
                div_12m_sum[code] = 0
    else:
        for code in base_codes:
            div_12m_sum[code] = 0
    
    # ---- 批量获取过去3年分红数据（用于稳定性） ----
    start_3y = current_date - pd.DateOffset(years=3)
    q_div_3y = query(
        finance.STK_XR_XD.code,
        finance.STK_XR_XD.bonus_amount_rmb,
        finance.STK_XR_XD.report_date
    ).filter(
        finance.STK_XR_XD.code.in_(base_codes),
        finance.STK_XR_XD.report_date >= start_3y,
        finance.STK_XR_XD.report_date <= current_date
    ).order_by(finance.STK_XR_XD.report_date)
    div_3y_data = finance.run_query(q_div_3y)
    
    # 计算分红稳定性（过去3年每年都有分红，且下降不超过60%）
    div_stable = {}
    if not div_3y_data.empty:
        div_3y_data['year'] = pd.DatetimeIndex(div_3y_data['report_date']).year
        for code in base_codes:
            code_data = div_3y_data[div_3y_data['code'] == code]
            if len(code_data) >= 3:
                yearly = code_data.groupby('year')['bonus_amount_rmb'].sum()
                if len(yearly) >= 3:
                    vals = yearly.values
                    decline_ok = True
                    for i in range(1, len(vals)):
                        if vals[i] < vals[i-1] * 0.6:
                            decline_ok = False
                            break
                    div_stable[code] = decline_ok
                else:
                    div_stable[code] = False
            else:
                div_stable[code] = False
    else:
        for code in base_codes:
            div_stable[code] = False
    
    # ---- 有效股票筛选（ST/次新/停牌） ----
    valid_mask = is_valid_stock_batch(context, base_codes, current_date)
    valid_codes = [code for code, v in zip(base_codes, valid_mask) if v]
    
    # ---- 构建最终股票池 ----
    stock_pool = []
    for code in valid_codes:
        market_cap = df[df['code'] == code]['market_cap'].iloc[0] if code in df['code'].values else 0
        div_yield = (div_12m_sum.get(code, 0) / market_cap * 100) if market_cap > 0 else 0
        if div_yield > g.dividend_threshold and div_stable.get(code, False) and ttm_profit.get(code, 0) > 0:
            stock_pool.append(code)
    
    # 如果池子太小，放宽股息率阈值
    if len(stock_pool) < g.min_stock_count:
        log.warning(f"股票池仅{len(stock_pool)}只，放宽股息率至{g.dividend_threshold_low}%")
        for code in valid_codes:
            if code in stock_pool:
                continue
            market_cap = df[df['code'] == code]['market_cap'].iloc[0] if code in df['code'].values else 0
            div_yield = (div_12m_sum.get(code, 0) / market_cap * 100) if market_cap > 0 else 0
            if div_yield > g.dividend_threshold_low and div_stable.get(code, False) and ttm_profit.get(code, 0) > 0:
                stock_pool.append(code)
            if len(stock_pool) >= g.max_stock_count * 2:
                break
    
    log.info(f"最终股票池数量：{len(stock_pool)}")
    
    # 缓存结果
    g._cache[cache_key] = stock_pool
    return stock_pool

def get_factor_data_batch(context, stocks):
    """
    批量获取因子所需数据：PB、PE、ROE、动量因子
    返回DataFrame，索引为股票代码
    """
    current_date = context.current_dt.date()
    prev_day = get_previous_trading_day(current_date)
    
    if not stocks:
        return pd.DataFrame()
    
    # ---- 批量获取PB、PE、ROE ----
    q = query(
        valuation.code,
        valuation.pb_ratio,
        valuation.pe_ratio,
        indicator.roe
    ).filter(
        valuation.code.in_(stocks)
    )
    df_fund = get_fundamentals(q, date=prev_day)
    if df_fund is None or df_fund.empty:
        return pd.DataFrame()
    
    df_fund.set_index('code', inplace=True)
    df_fund = df_fund[~df_fund.index.duplicated(keep='first')]
    
    # ---- 批量获取动量因子（过去250个交易日涨跌幅） ----
    # get_price支持多股票，返回MultiIndex DataFrame，性能远优于循环
    try:
        price_data = get_price(stocks, end_date=prev_day, frequency='daily', 
                               fields=['close'], count=250, skip_paused=True, panel=False)
        # price_data是MultiIndex，level0为code，level1为日期
        mom_list = []
        for code in stocks:
            if code in price_data.index.get_level_values(0):
                code_data = price_data.xs(code, level=0)
                if len(code_data) >= 20:
                    price_now = code_data['close'].iloc[-1]
                    price_1y_ago = code_data['close'].iloc[0]
                    mom = (price_now / price_1y_ago - 1) * 100 if price_1y_ago > 0 else 0
                else:
                    mom = 0
            else:
                mom = 0
            mom_list.append(mom)
    except:
        mom_list = [0] * len(stocks)
    
    # 合并数据
    result = pd.DataFrame(index=stocks)
    result['pb'] = df_fund['pb_ratio']
    result['pe'] = df_fund['pe_ratio']
    result['roe'] = df_fund['roe']
    result['momentum'] = mom_list
    
    return result

def multi_factor_scoring(context, stocks):
    """
    多因子打分（排名归一化，反转因子越低越好）- 批量优化版
    """
    if not stocks:
        return pd.DataFrame()
    
    # 获取股息率（从缓存或重新计算）
    # 因为get_stock_pool已经计算过股息率，我们可以从缓存中提取，避免重复计算
    # 但为了解耦，这里直接重新计算股息率（批量方式）
    current_date = context.current_dt.date()
    prev_day = get_previous_trading_day(current_date)
    
    # 批量获取市值和分红数据（简化版，与get_stock_pool类似但只针对stocks）
    # 市值
    q_val = query(
        valuation.code,
        valuation.market_cap
    ).filter(
        valuation.code.in_(stocks)
    )
    df_val = get_fundamentals(q_val, date=prev_day)
    if df_val is None or df_val.empty:
        return pd.DataFrame()
    df_val.set_index('code', inplace=True)
    
    # 近12个月分红
    start_date = current_date - pd.DateOffset(months=12)
    q_div = query(
        finance.STK_XR_XD.code,
        finance.STK_XR_XD.bonus_amount_rmb
    ).filter(
        finance.STK_XR_XD.code.in_(stocks),
        finance.STK_XR_XD.report_date >= start_date,
        finance.STK_XR_XD.report_date <= current_date
    )
    div_data = finance.run_query(q_div)
    div_sum = {}
    if not div_data.empty:
        div_group = div_data.groupby('code')['bonus_amount_rmb'].sum()
        for code in stocks:
            div_sum[code] = div_group.get(code, 0) / 10000  # 亿元
    else:
        for code in stocks:
            div_sum[code] = 0
    
    # 计算股息率
    div_yield_list = []
    for code in stocks:
        market_cap = df_val.loc[code, 'market_cap'] if code in df_val.index else np.nan
        if pd.isna(market_cap) or market_cap <= 0:
            div_yield = 0
        else:
            div_yield = (div_sum[code] / market_cap * 100)
        div_yield_list.append(div_yield)
    
    # 获取其他因子数据
    factor_df = get_factor_data_batch(context, stocks)
    if factor_df.empty:
        return pd.DataFrame()
    
    # 构建完整因子DataFrame
    df = pd.DataFrame(index=stocks)
    df['dividend_yield'] = div_yield_list
    df['roe'] = factor_df['roe']
    df['pb_inverse'] = 1.0 / factor_df['pb']
    df['pe_inverse'] = 1.0 / factor_df['pe']
    df['momentum'] = factor_df['momentum']
    
    # 处理无效值
    df = df.replace([np.inf, -np.inf], np.nan).fillna(0)
    
    # 排名归一化（0-1）
    for col in ['dividend_yield', 'roe', 'pb_inverse', 'pe_inverse']:
        if df[col].nunique() == 1:
            df[col + '_rank'] = 0.5
        else:
            df[col + '_rank'] = df[col].rank(pct=True).fillna(0.5)
    
    # 反转因子：越小排名越高
    if df['momentum'].nunique() == 1:
        df['momentum_rank'] = 0.5
    else:
        df['momentum_rank'] = 1 - df['momentum'].rank(pct=True).fillna(0.5)
    
    # 加权得分
    df['score'] = (
        df['dividend_yield_rank'] * g.weight_div +
        df['roe_rank'] * g.weight_roe +
        df['pb_inverse_rank'] * g.weight_pb +
        df['pe_inverse_rank'] * g.weight_pe +
        df['momentum_rank'] * g.weight_mom
    )
    
    return df

def rebalance(context):
    """月度调仓，满仓操作 - 逻辑不变"""
    current_date = context.current_dt.date()
    log.info(f"===== 调仓日：{current_date} =====")
    
    # 1. 获取股票池
    stock_pool = get_stock_pool(context)
    if len(stock_pool) < g.min_stock_count:
        log.warning(f"股票池数量{len(stock_pool)}不足{g.min_stock_count}，不调仓")
        return
    
    # 2. 多因子打分
    score_df = multi_factor_scoring(context, stock_pool)
    if score_df.empty:
        log.warning("因子打分失败，不调仓")
        return
    
    # 3. 选股：取前 max_stock_count 只
    selected = score_df.sort_values('score', ascending=False).head(g.max_stock_count)
    selected_stocks = selected.index.tolist()
    # 若不足最小持股数，扩充至最小持股数
    if len(selected_stocks) < g.min_stock_count:
        selected_stocks = score_df.sort_values('score', ascending=False).head(g.min_stock_count).index.tolist()
        selected = score_df.loc[selected_stocks]
    
    log.info(f"选中股票：{selected_stocks}")
    log.info(f"得分详情：\n{selected[['score']].round(3)}")
    
    # 4. 仓位分配：等权满仓
    stock_count = len(selected_stocks)
    per_stock_weight = 1.0 / stock_count
    
    # 5. 卖出不在持仓中的股票
    for stock in list(context.portfolio.positions.keys()):
        if stock == '511880.XSHG':
            order_target_value(stock, 0)
            continue
        if stock not in selected_stocks:
            order_target_value(stock, 0)
            log.info(f"卖出 {stock}")
    
    # 6. 买入选中股票
    for stock in selected_stocks:
        adjust_position_by_percent(context, stock, per_stock_weight)
        log.info(f"买入 {stock}，目标权重 {per_stock_weight:.2%}")
    
    # 清理缓存（调仓完成后可清空，避免占用内存）
    g._cache.clear()
    
    log.info("调仓完成")

def adjust_position_by_percent(context, stock, target_percent):
    """按目标百分比调整持仓（使用 order_target_value）"""
    try:
        total_value = context.portfolio.total_value
        target_value = total_value * target_percent
        
        current_data = get_current_data()
        price = current_data[stock].last_price
        if np.isnan(price) or price <= 0:
            return
        
        target_amount = int(target_value / price / 100) * 100
        order_target_value(stock, target_amount * price)
    except Exception as e:
        log.error(f"调整{stock}持仓出错：{str(e)}")

def before_trading_start(context):
    """盘前更新最高价"""
    current_data = get_current_data()
    for stock in context.portfolio.positions:
        if context.portfolio.positions[stock].total_amount > 0:
            price = current_data[stock].last_price
            if not np.isnan(price) and price > 0:
                if stock not in g.stock_high_prices:
                    g.stock_high_prices[stock] = price
                else:
                    if price > g.stock_high_prices[stock]:
                        g.stock_high_prices[stock] = price

def handle_data(context, data):
    """盘中实时更新最高价，并触发止损"""
    current_data = get_current_data()
    for stock in list(context.portfolio.positions.keys()):
        pos = context.portfolio.positions[stock]
        if pos.total_amount == 0:
            if stock in g.stock_high_prices:
                del g.stock_high_prices[stock]
            continue
        
        price = current_data[stock].last_price
        if np.isnan(price) or price <= 0:
            continue
        
        # 更新最高价
        if stock not in g.stock_high_prices:
            g.stock_high_prices[stock] = price
        else:
            if price > g.stock_high_prices[stock]:
                g.stock_high_prices[stock] = price
        
        # 止损检查
        high = g.stock_high_prices[stock]
        if high > 0 and price / high < g.stop_loss_ratio:
            order_target_value(stock, 0)
            log.info(f"止损清仓：{stock}，回撤{(1-price/high):.2%}，价格{price:.2f}")
            if stock in g.stock_high_prices:
                del g.stock_high_prices[stock]

def after_trading_end(context):
    """盘后清理"""
    pass