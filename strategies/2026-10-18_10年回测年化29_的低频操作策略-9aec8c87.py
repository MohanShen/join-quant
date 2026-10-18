# Clone from JoinQuant
# postId: 9aec8c87e33c22d10deb8079573f8031
# backtestId: 4eab6bf194976b8e1d926192fad9f6db
# title: 10年回测年化29%的低频操作策略

# ============================================================================
# V4 最终定稿（停牌跳过版）：股息率 + 单年EPS增速（年度调仓，3只持仓）
# ============================================================================
# 【策略核心】
#   1. 每年5月第一个交易日，从31只精选蓝筹股中选出得分最高的3只
#   2. 得分 = TTM股息率 + 单年EPS增速（线性相加）
#   3. 同行业最多选1只（申万一级行业）
#   4. PE估值保护：剔除PE高于候选池中位数1.5倍的股票
#   5. ★ 停牌过滤：选股时自动跳过当日停牌的股票，保证买入执行
#
# 【风控机制】
#   1. 个股止损：单只股票亏损8%立即卖出（同只股票仅触发一次）
#   2. 分红复投：每日14:00，现金够买100股即按市值比例复投
# ============================================================================

import pandas as pd
import numpy as np
from jqdata import *
from datetime import timedelta


def initialize(context):
    set_option('use_real_price', True)
    
    # ============================================================
    # 31只精选蓝筹股池（按行业分类）
    # ============================================================
    g.stock_pool = [
        # ---- 公用事业/电力（5只）----
        '600900.XSHG',  # 长江电力
        '601985.XSHG',  # 中国核电
        '003816.XSHE',  # 中国广核
        '600025.XSHG',  # 华能水电
        '600886.XSHG',  # 国投电力
        # ---- 能源/石油（1只）----
        '600938.XSHG',  # 中国海油
        # ---- 能源/煤炭（1只）----
        '601088.XSHG',  # 中国神华
        # ---- 有色金属（1只）----
        '601899.XSHG',  # 紫金矿业
        # ---- 交运基础设施（7只）----
        '601000.XSHG',  # 唐山港
        '601006.XSHG',  # 大秦铁路
        '000429.XSHE',  # 粤高速A
        '600350.XSHG',  # 山东高速
        '600377.XSHG',  # 宁沪高速
        '600012.XSHG',  # 皖通高速
        '601919.XSHG',  # 中远海控
        # ---- 通信运营商（2只）----
        '600941.XSHG',  # 中国移动
        '601728.XSHG',  # 中国电信
        # ---- 金融（2只）----
        '601318.XSHG',  # 中国平安
        '600901.XSHG',  # 江苏金租
        # ---- 消费/食品饮料（7只）----
        '600887.XSHG',  # 伊利股份
        '603288.XSHG',  # 海天味业
        '000895.XSHE',  # 双汇发展
        '600600.XSHG',  # 青岛啤酒
        '600132.XSHG',  # 重庆啤酒
        '000858.XSHE',  # 五粮液
        '000568.XSHE',  # 泸州老窖
        # ---- 家电（2只）----
        '000333.XSHE',  # 美的集团
        '000651.XSHE',  # 格力电器
        # ---- 汽车（2只）----
        '600066.XSHG',  # 宇通客车
        '002594.XSHE',  # 比亚迪
        # ---- 科技/电子（1只）----
        '002415.XSHE',  # 海康威视
    ]
    
    # ============================================================
    # 策略核心参数
    # ============================================================
    g.num_stocks = 3
    g.min_eps_growth = 0.0
    g.max_payout_ratio = 1.00
    g.max_pe = 50.0
    g.pe_threshold_multiplier = 1.5
    
    g.stop_loss_threshold = -0.08
    g.stopped_stocks = set()
    
    # ============================================================
    # 定时任务
    # ============================================================
    run_monthly(rebalance, monthday=1, time='09:30')
    run_daily(buy_if_needed, time='13:00')
    run_daily(stop_loss_check, time='13:00')
    run_daily(reinvest_dividend, time='14:00')
    
    # ============================================================
    # 日志
    # ============================================================
    log.info(f'策略初始化完成，股票池共{len(g.stock_pool)}只，持仓{g.num_stocks}只（各33.33%）')
    log.info('【股票池】33只精选蓝筹股')
    log.info('【价格模式】真实价格（use_real_price=True）')
    log.info('【调仓频率】年度调仓：每年5月第一个交易日')
    log.info('【选股逻辑】score = TTM股息率 + 单年EPS增速')
    log.info('【行业分散】同一申万一级行业最多选1只')
    log.info(f'【估值保护】PE高于所有候选PE中位数×{g.pe_threshold_multiplier:.1f}倍时剔除')
    log.info('【分红复投】现金累积至足够买入100股时自动复投')
    log.info(f'【止损规则】单只股票亏损超过{g.stop_loss_threshold*100:.0f}%时立即卖出（同只股票仅触发一次）')
    log.info('【停牌处理】选股时自动跳过当日停牌股票，自动顺延至下一名')
    
    g.need_buy = False
    g.target_list = []


# ============================================================================
# 止损检查函数（每天13:00执行）
# ============================================================================
def stop_loss_check(context):
    current_date = context.current_dt.date()
    to_sell = []
    
    for stock in context.portfolio.positions:
        pos = context.portfolio.positions[stock]
        if stock in g.stopped_stocks:
            continue
        if pos.total_amount == 0:
            continue
        avg_cost = pos.avg_cost
        if avg_cost <= 0:
            continue
        price_data = get_price(stock, count=1, end_date=current_date,
                               frequency='daily', fields=['close'])
        if price_data.empty:
            continue
        current_price = float(price_data['close'].iloc[-1])
        if current_price <= 0:
            continue
        profit_rate = (current_price - avg_cost) / avg_cost
        if profit_rate < g.stop_loss_threshold:
            g.stopped_stocks.add(stock)
            to_sell.append((stock, profit_rate))
    
    for stock, profit_rate in to_sell:
        order_target_value(stock, 0)
        log.info(f'【止损卖出】{get_security_info(stock).display_name}({stock}) '
                 f'亏损率{profit_rate*100:.2f}% ≤ {g.stop_loss_threshold*100:.0f}%，已清仓，加入黑名单')


# ============================================================================
# 获取指定报告期的EPS
# ============================================================================
def get_eps_for_period(code, end_date_str, current_date):
    try:
        q = query(
            finance.STK_INCOME_STATEMENT.basic_eps,
            finance.STK_INCOME_STATEMENT.end_date,
            finance.STK_INCOME_STATEMENT.pub_date
        ).filter(
            finance.STK_INCOME_STATEMENT.code == code,
            finance.STK_INCOME_STATEMENT.end_date == end_date_str,
            finance.STK_INCOME_STATEMENT.report_type == 0,
            finance.STK_INCOME_STATEMENT.pub_date <= current_date
        ).order_by(
            finance.STK_INCOME_STATEMENT.pub_date.desc()
        ).limit(1)
        df = finance.run_query(q)
        if df.empty:
            return np.nan
        return float(df['basic_eps'].iloc[0])
    except:
        return np.nan


# ============================================================================
# 获取指定年份的每股分红
# ============================================================================
def get_dividend_per_share(code, year):
    q = query(
        finance.STK_XR_XD.bonus_ratio_rmb,
        finance.STK_XR_XD.report_date
    ).filter(
        finance.STK_XR_XD.code == code,
        finance.STK_XR_XD.report_date >= f'{year}-01-01',
        finance.STK_XR_XD.report_date <= f'{year}-12-31'
    )
    df = finance.run_query(q)
    if df.empty:
        return 0.0
    df_sorted = df.sort_values('report_date', ascending=False)
    last_row = df_sorted.iloc[0]
    if pd.isna(last_row['bonus_ratio_rmb']):
        return 0.0
    return float(last_row['bonus_ratio_rmb']) / 10.0


# ============================================================================
# 获取股票的申万一级行业
# ============================================================================
def get_sw_industry(code, date):
    try:
        industry_dict = get_industry(code, date=date)
        if code in industry_dict and 'sw_l1' in industry_dict[code]:
            return industry_dict[code]['sw_l1']['industry_code']
        return None
    except:
        return None


# ============================================================================
# 估值保护
# ============================================================================
def apply_valuation_protection(candidates_df, multiplier=1.5):
    if candidates_df.empty or len(candidates_df) < g.num_stocks + 1:
        return candidates_df
    valid_pe = candidates_df[candidates_df['pe'] > 0]['pe']
    if valid_pe.empty:
        return candidates_df
    pe_median = valid_pe.median()
    pe_threshold = pe_median * multiplier
    mask = (candidates_df['pe'] <= pe_threshold) | (candidates_df['pe'] <= 0)
    removed = candidates_df[~mask]
    for _, row in removed.iterrows():
        log.info(f'【估值保护】{row["code"]} PE:{row["pe"]:.1f} > 阈值:{pe_threshold:.1f}，剔除')
    return candidates_df[mask].copy()


# ============================================================================
# 分红复投
# ============================================================================
def reinvest_dividend(context):
    cash = context.portfolio.available_cash
    if cash <= 0:
        return
    positions = context.portfolio.positions
    holdings = [stock for stock in positions
                if positions[stock].total_amount > 0 and stock in g.stock_pool]
    if not holdings:
        return
    current_date = context.current_dt.date()
    current_prices = {}
    for stock in holdings:
        price_data = get_price(stock, count=1, end_date=current_date,
                               frequency='daily', fields=['close'])
        if price_data.empty:
            return
        current_prices[stock] = float(price_data['close'].iloc[-1])
    min_price = min(current_prices.values())
    if cash < min_price * 100:
        return
    total_hold_value = sum(
        positions[stock].total_amount * current_prices[stock]
        for stock in holdings
    )
    if total_hold_value <= 0:
        return
    for stock in holdings:
        stock_value = positions[stock].total_amount * current_prices[stock]
        ratio = stock_value / total_hold_value
        allocated_cash = cash * ratio
        if allocated_cash >= current_prices[stock] * 100:
            shares = int(allocated_cash / current_prices[stock] / 100) * 100
            if shares > 0:
                order_value(stock, shares * current_prices[stock])
                log.info(f'【分红复投】用现金 {shares * current_prices[stock]:.2f} '
                         f'买入 {get_security_info(stock).display_name}({stock}) {shares}股')


# ============================================================================
# 年度调仓主函数（每年5月第一个交易日09:30执行）
# ============================================================================
def rebalance(context):
    current_date = context.current_dt.date()
    month = context.current_dt.month
    if month != 5:
        return
    
    log.info(f'=== {current_date} 09:30 年度调仓开始 ===')
    g.stopped_stocks = set()
    
    stock_list = g.stock_pool
    year = current_date.year
    prev_year = year - 1
    prev_prev_year = year - 2
    current_end = f'{prev_year}-12-31'
    prev_end = f'{prev_prev_year}-12-31'
    log.info(f'【数据来源】使用 {prev_year}年年报：{current_end} vs {prev_end}')
    
    # ---- Step 1: 获取PE ----
    q_valuation = query(valuation.code, valuation.pe_ratio).filter(valuation.code.in_(stock_list))
    df_valuation = get_fundamentals(q_valuation)
    pe_dict = dict(zip(df_valuation['code'], df_valuation['pe_ratio'])) if not df_valuation.empty else {}
    
    # ---- Step 2: 获取EPS ----
    eps_cur = {}
    eps_prev = {}
    for stock in stock_list:
        eps_cur[stock] = get_eps_for_period(stock, current_end, current_date)
        eps_prev[stock] = get_eps_for_period(stock, prev_end, current_date)
    
    # ---- Step 3: 获取当前价格 ----
    trade_days = get_trade_days(start_date=current_date - timedelta(days=10), end_date=current_date)
    price_date = trade_days[-1] if len(trade_days) >= 1 else current_date
    prices = {}
    for stock in stock_list:
        try:
            price_data = get_price(stock, count=1, end_date=price_date,
                                   frequency='daily', fields=['close'])
            if not price_data.empty:
                prices[stock] = float(price_data['close'].iloc[-1])
            else:
                prices[stock] = np.nan
        except:
            prices[stock] = np.nan
    
    # ---- Step 4: 筛选候选股票（★ 停牌过滤）----
    current_data = get_current_data()   # 获取当日实时数据
    candidates = []
    for stock in stock_list:
        eps = eps_cur.get(stock, np.nan)
        eps_prev_val = eps_prev.get(stock, np.nan)
        pe = pe_dict.get(stock, np.nan)
        price = prices.get(stock, np.nan)
        
        # 数据完整性
        if np.isnan(eps) or np.isnan(eps_prev_val) or np.isnan(price) or price <= 0 or eps_prev_val <= 0:
            continue
        
        # ★ 停牌过滤：若当日停牌，直接跳过
        if current_data[stock].paused:
            log.info(f'【停牌跳过】{get_security_info(stock).display_name}({stock}) 今日停牌，顺延至下一名')
            continue
        
        # EPS增速 > 0
        eps_growth = (eps - eps_prev_val) / eps_prev_val * 100
        if eps_growth <= g.min_eps_growth:
            continue
        
        # PE ≤ 50
        if not np.isnan(pe) and pe > g.max_pe and pe > 0:
            continue
        
        # 有分红
        div_per_share = get_dividend_per_share(stock, prev_year)
        if div_per_share <= 0:
            continue
        
        # 股利支付率 ≤ 100%
        payout_ratio = div_per_share / eps if eps > 0 else np.inf
        if payout_ratio > g.max_payout_ratio:
            continue
        
        # 计算得分
        dividend_yield = div_per_share / price * 100
        score = dividend_yield + eps_growth
        industry = get_sw_industry(stock, current_date)
        
        candidates.append({
            'code': stock,
            'name': get_security_info(stock).display_name,
            'score': score,
            'dividend_yield': dividend_yield,
            'eps_growth': eps_growth,
            'pe': pe,
            'price': price,
            'eps': eps,
            'industry': industry
        })
    
    if not candidates:
        log.info('无股票通过过滤，本次不调仓')
        g.need_buy = False
        return
    
    # ---- Step 5: 排序 + 估值保护 ----
    candidates_df = pd.DataFrame(candidates)
    candidates_df = candidates_df.sort_values('score', ascending=False)
    candidates_df = apply_valuation_protection(candidates_df, g.pe_threshold_multiplier)
    
    if candidates_df.empty:
        log.info('所有股票被估值保护剔除，本次不调仓')
        g.need_buy = False
        return
    
    # ---- Step 6: 行业去重 ----
    selected_df = pd.DataFrame()
    used_industries = set()
    
    for _, row in candidates_df.iterrows():
        industry = row['industry']
        if industry is None:
            selected_df = pd.concat([selected_df, row.to_frame().T])
            if len(selected_df) >= g.num_stocks:
                break
            continue
        if industry not in used_industries:
            used_industries.add(industry)
            selected_df = pd.concat([selected_df, row.to_frame().T])
            if len(selected_df) >= g.num_stocks:
                break
    
    if len(selected_df) < g.num_stocks:
        remaining = candidates_df[~candidates_df['code'].isin(selected_df['code'].values)]
        need = g.num_stocks - len(selected_df)
        if len(remaining) > 0:
            selected_df = pd.concat([selected_df, remaining.head(need)])
    
    selected = selected_df.head(g.num_stocks)
    
    log.info(f'本次选中 {len(selected)} 只股票：')
    for _, row in selected.iterrows():
        industry_name = row['industry'] if pd.notna(row['industry']) else '未知'
        log.info(f"  {row['name']}({row['code']}) | 行业:{industry_name} | "
                 f"得分:{row['score']:.2f} | 股息率:{row['dividend_yield']:.2f}% | "
                 f"EPS增速:{row['eps_growth']:.2f}% | PE:{row['pe']:.1f}")
    
    # ---- Step 7: 卖出不在目标名单的持仓 ----
    target_codes = selected['code'].values
    for stock in list(context.portfolio.positions.keys()):
        if stock not in target_codes and stock in g.stock_pool:
            order_target_value(stock, 0)
            log.info(f'卖出 {get_security_info(stock).display_name}({stock})')
    
    # ---- Step 8: 记录目标，13:00买入 ----
    g.target_list = list(target_codes)
    g.need_buy = True
    log.info(f'=== {current_date} 09:30 卖出完成，13:00买入 {len(g.target_list)} 只（各33.33%） ===')


# ============================================================================
# 买入函数（每天13:00执行，仅调仓日买入）
# ============================================================================
def buy_if_needed(context):
    if not g.need_buy:
        return
    if len(g.target_list) == 0:
        g.need_buy = False
        return
    
    current_date = context.current_dt.date()
    log.info(f'=== {current_date} 13:00 买入阶段开始 ===')
    
    total_value = context.portfolio.total_value
    target_value = total_value / len(g.target_list)
    
    for stock in g.target_list:
        order_target_value(stock, target_value)
        log.info(f'买入 {get_security_info(stock).display_name}({stock}) '
                 f'目标市值:{target_value:.2f} (占总仓位{100/len(g.target_list):.0f}%)')
    
    g.need_buy = False
    g.target_list = []
    log.info(f'=== {current_date} 13:00 买入完成 ===')