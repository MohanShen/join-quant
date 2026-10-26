# Clone from JoinQuant
# postId: cf1ec5bd80c4719365170ac995e38f8a
# backtestId: b0fc7e4df58d4e89910a2e099ad4921b
# title: 红利类型选股策略

# ============================================================================
# 四策略整合 V1.0  (聚宽平台,JoinQuant)
# ----------------------------------------------------------------------------
# 设计原则:
#   1. 每个子策略权重 25%,资金/持仓/调度 完全隔离,逻辑互不干扰
#   2. 采用"虚拟账户"机制(sub_cash + sub_holdings):
#      - 每个子策略只能花自己的钱、卖自己持有的份额
#      - 同一只股票被多策略同时持有时不会互相冲销
#   3. 严禁使用 order_target_value(stock, 0) 这类全量清仓调用
#      (会把其他策略的持仓也卖光),一律用 order_value(买) 和 order(-amount,卖)
# ----------------------------------------------------------------------------
# 子策略清单:
#   s1: ROIC 中等市值        (1 只股) 每月 1/11 日 10:45
#   s2: 高股息 + PEG(扣非)   (3 只股) 每月 1/11 日 9:40
#   s3: 大市值 PB<1 价值     (1 只股 + 国债 ETF 兜底) 每月 1/11 日 9:50 + 每日盘中
#   s4: 中证 500 高股息指增  (1 只股) 每周一 9:45,1/6 月更新选股
# ============================================================================

import pandas as pd
import numpy as np
import datetime
from jqdata import *
from jqfactor import *


# ============================================================================
# 初始化
# ============================================================================
def initialize(context):
    # ----- 系统设置 -----
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_benchmark('000300.XSHG')
    set_slippage(FixedSlippage(0.003))
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001,
                             open_commission=0.0003, close_commission=0.0003,
                             close_today_commission=0, min_commission=5), type='stock')
    set_order_cost(OrderCost(open_tax=0, close_tax=0.0005,
                             open_commission=0.0003, close_commission=0.0003,
                             close_today_commission=0, min_commission=5), type='fund')
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'info')

    # ----- 子策略权重(可调) -----
    g.strategy_weights = {
        's1': 0.25,
        's2': 0.25,
        's3': 0.25,
        's4': 0.25,
    }

    # ----- 虚拟账户:每个子策略独立的"资金/持仓"账本 -----
    g.sub_cash = {sid: 0.0 for sid in g.strategy_weights}
    g.sub_holdings = {sid: {} for sid in g.strategy_weights}   # {sid: {stock: amount}}
    g.first_day_init = False

    # ----- 子策略 1: ROIC 中等市值 -----
    g.s1_stock_num = 1

    # ----- 子策略 2: 高股息 + PEG(扣非) -----
    g.s2_stock_num = 3
    g.s2_high_limit_list = []

    # ----- 子策略 3: 大市值 PB<1 -----
    g.s3_stock_num = 1
    g.s3_etf = '511010.XSHG'           # 国债 ETF(空仓兜底)
    g.s3_check_out_lists = []
    g.s3_yesterday_HL_list = []

    # ----- 子策略 4: 中证 500 高股息指增 -----
    g.s4_stock_num = 1
    g.s4_stocks = []

    # ----- 调度任务 -----
    # 全局: 首日分配资金
    run_daily(daily_init, '9:00')

    # 子策略 1
    run_monthly(strategy_1_adjust, 1, '10:45')
    run_monthly(strategy_1_adjust, 11, '10:45')

    # 子策略 2
    run_daily(strategy_2_prepare, '9:05')
    run_monthly(strategy_2_trade, 1, '9:40')
    run_monthly(strategy_2_trade, 11, '9:40')

    # 子策略 3
    run_daily(strategy_3_before_market, '9:02')
    run_monthly(strategy_3_check_stocks, 1, '9:06')
    run_monthly(strategy_3_check_stocks, 11, '9:06')
    run_monthly(strategy_3_trade, 1, '9:50')
    run_monthly(strategy_3_trade, 11, '9:50')
    run_daily(strategy_3_check_limit_up, '14:00')
    run_daily(strategy_3_check_limit_up, '14:50')

    # 子策略 4
    run_weekly(strategy_4_trade, weekday=1, time='9:45')


# ============================================================================
# 虚拟账户核心工具
# ============================================================================

def daily_init(context):
    """首日开盘前按权重把总资产切分到 4 个虚拟子账户"""
    if not g.first_day_init:
        total = context.portfolio.total_value
        for sid in g.strategy_weights:
            g.sub_cash[sid] = total * g.strategy_weights[sid]
        g.first_day_init = True
        log.info("[初始化] 总资产=%.2f, 分配: %s" % (
            total,
            ", ".join(["%s=%.2f" % (sid, g.sub_cash[sid]) for sid in g.sub_cash])
        ))


def get_sub_value(context, sid):
    """子策略当前总资产 = 虚拟现金 + 虚拟持仓市值"""
    value = g.sub_cash[sid]
    cd = get_current_data()
    for stock, amount in g.sub_holdings[sid].items():
        if amount > 0:
            value += amount * cd[stock].last_price
    return value


def sub_buy(context, sid, stock, value):
    """
    子策略买入: 用 value 金额买入 stock
    会从虚拟现金扣除,加到虚拟持仓
    """
    if value <= 0 or g.sub_cash[sid] <= 100:
        return False
    if value > g.sub_cash[sid]:
        value = g.sub_cash[sid]
    if value < 500:                  # 太小可能买不到 1 手
        return False

    before = context.portfolio.positions[stock].total_amount if stock in context.portfolio.positions else 0
    od = order_value(stock, value)
    if od is None or od.filled <= 0:
        return False

    after = context.portfolio.positions[stock].total_amount
    actual_amount = after - before
    if actual_amount <= 0:
        return False

    actual_cost = actual_amount * od.price
    fee = max(5, actual_cost * 0.0003)
    g.sub_cash[sid] = max(0, g.sub_cash[sid] - actual_cost - fee)
    g.sub_holdings[sid][stock] = g.sub_holdings[sid].get(stock, 0) + actual_amount
    log.info("[%s][买入] %s amt=%d px=%.2f val=%.2f" %
             (sid, stock, actual_amount, od.price, actual_cost))
    return True


def sub_sell(context, sid, stock, amount=None):
    """
    子策略卖出: 卖出 amount 股 stock(默认全卖)
    会从虚拟持仓减除,加回虚拟现金
    """
    held = g.sub_holdings[sid].get(stock, 0)
    if held <= 0:
        return False
    if stock not in context.portfolio.positions:
        g.sub_holdings[sid].pop(stock, None)
        return False

    closeable = context.portfolio.positions[stock].closeable_amount
    if closeable <= 0:
        log.warn("[%s][卖出] %s 当日不可卖(T+1或停牌)" % (sid, stock))
        return False

    if amount is None or amount > held:
        amount = held
    amount = min(amount, closeable)
    if amount <= 0:
        return False

    before = context.portfolio.positions[stock].total_amount
    od = order(stock, -amount)
    if od is None:
        return False
    after = context.portfolio.positions[stock].total_amount if stock in context.portfolio.positions else 0
    actual_sold = before - after
    if actual_sold <= 0:
        return False

    proceeds = actual_sold * od.price
    fee = max(5, proceeds * 0.0013)   # 佣金 + 印花税近似
    g.sub_cash[sid] += (proceeds - fee)
    g.sub_holdings[sid][stock] -= actual_sold
    if g.sub_holdings[sid][stock] <= 0:
        g.sub_holdings[sid].pop(stock, None)
    log.info("[%s][卖出] %s amt=%d px=%.2f val=%.2f" %
             (sid, stock, actual_sold, od.price, proceeds))
    return True


# ============================================================================
# 子策略 1: ROIC 中等市值
# ============================================================================

def strategy_1_adjust(context):
    sid = 's1'
    yesterday = context.previous_date

    initial_list = get_all_securities().index.tolist()
    initial_list = filter_new_stock(context, initial_list)
    initial_list = filter_paused_stock(initial_list)
    initial_list = filter_kcbj_stock(initial_list)
    initial_list = filter_st_stock(initial_list)

    if '600519.XSHG' in initial_list:
        initial_list.remove('600519.XSHG')

    try:
        df = get_fundamentals(
            query(
                valuation.code, valuation.market_cap, valuation.pe_ratio,
                indicator.roa,
                balance.total_liability, balance.total_sheet_owner_equities,
                indicator.inc_total_revenue_year_on_year,
                indicator.inc_revenue_year_on_year,
                indicator.inc_net_profit_year_on_year,
                balance.retained_profit
            ).filter(
                valuation.code.in_(initial_list),
                valuation.market_cap > 100,
                valuation.pe_ratio.between(0, 50),
                indicator.roa > 0.15,
                (balance.total_liability / balance.total_sheet_owner_equities) < 0.5,
                indicator.inc_total_revenue_year_on_year > 0.3,
                indicator.inc_revenue_year_on_year > 0.2,
                balance.retained_profit > 0,
            ).order_by(balance.retained_profit.desc()
            ).limit(g.s1_stock_num * 3)
        )
    except Exception as e:
        log.warn("[s1] 基本面查询失败: %s" % str(e))
        return

    if df is None or df.empty:
        log.info("[s1] 候选池为空")
        return

    # ROIC 过滤
    code_list = list(df['code'])
    filtered = []
    for stock in code_list:
        try:
            roic = get_factor_values(stock, 'roic_ttm',
                                     end_date=yesterday, count=1)['roic_ttm'].iloc[0, 0]
            if pd.notna(roic) and roic > 0.06:
                filtered.append(stock)
        except:
            continue

    df = df[df['code'].isin(filtered)]
    df = df.sort_values(by='roa', ascending=False)
    final_list = list(df['code'])[:g.s1_stock_num]
    log.info("[s1] 目标股票: %s" % final_list)

    # 卖出非目标
    for stock in list(g.sub_holdings[sid].keys()):
        if stock not in final_list:
            sub_sell(context, sid, stock)

    # 买入目标
    to_buy = [s for s in final_list if s not in g.sub_holdings[sid]]
    if to_buy:
        sub_value = get_sub_value(context, sid)
        value_per = min(g.sub_cash[sid] / len(to_buy), sub_value / len(final_list))
        for stock in to_buy:
            sub_buy(context, sid, stock, value_per)


# ============================================================================
# 子策略 2: 高股息 + PEG(扣非净利)
# ============================================================================

def strategy_2_prepare(context):
    """每日 9:05: 更新 s2 持仓的昨日涨停标记"""
    sid = 's2'
    g.s2_high_limit_list = []
    held = list(g.sub_holdings[sid].keys())
    if held:
        for stock in held:
            try:
                df = get_price(stock, end_date=context.previous_date, frequency='daily',
                               fields=['close', 'high_limit'], count=1)
                if df['close'][0] >= df['high_limit'][0] * 0.98:
                    g.s2_high_limit_list.append(stock)
            except:
                continue


def _s2_calc_adj_profit_yoy(codes, ref_date):
    """计算扣非净利同比增速(%) - 用 indicator.adjusted_profit 当前 vs 365 天前"""
    if not codes:
        return {}
    q_now = query(indicator.code, indicator.adjusted_profit).filter(indicator.code.in_(codes))
    df_now = get_fundamentals(q_now, date=ref_date)
    now_map = ({r['code']: r['adjusted_profit'] for _, r in df_now.iterrows()}
               if (df_now is not None and not df_now.empty) else {})

    past_date = ref_date - datetime.timedelta(days=365)
    q_old = query(indicator.code, indicator.adjusted_profit).filter(indicator.code.in_(codes))
    df_old = get_fundamentals(q_old, date=past_date)
    old_map = ({r['code']: r['adjusted_profit'] for _, r in df_old.iterrows()}
               if (df_old is not None and not df_old.empty) else {})

    yoy = {}
    for c in codes:
        cur = now_map.get(c)
        old = old_map.get(c)
        if cur is None or old is None or old <= 0:
            yoy[c] = None
        else:
            try:
                yoy[c] = (cur - old) / abs(old) * 100.0
            except:
                yoy[c] = None
    return yoy


def _s2_peg_filter(context, stock_list, pegmin, pegmax):
    if not stock_list:
        return []
    q = query(valuation.code, valuation.pe_ratio).filter(valuation.code.in_(stock_list))
    df_pe = get_fundamentals(q, date=context.previous_date)
    if df_pe is None or df_pe.empty:
        return []
    pe_map = {r['code']: r['pe_ratio'] for _, r in df_pe.iterrows()}
    yoy_map = _s2_calc_adj_profit_yoy(stock_list, context.previous_date)

    res = []
    for code in stock_list:
        pe = pe_map.get(code)
        gr = yoy_map.get(code)
        if pe is None or gr is None or gr <= 0:
            continue
        try:
            peg = pe / gr
            if pegmin < peg < pegmax:
                res.append(code)
        except:
            continue
    return res


def _s2_dividend_filter(context, stock_list, sort, p1, p2):
    time1 = context.previous_date
    time0 = time1 - datetime.timedelta(days=365 * 2)
    interval = 1000
    list_len = len(stock_list)

    q = query(finance.STK_XR_XD.code,
              finance.STK_XR_XD.a_registration_date,
              finance.STK_XR_XD.bonus_amount_rmb
              ).filter(
        finance.STK_XR_XD.a_registration_date >= time0,
        finance.STK_XR_XD.a_registration_date <= time1,
        finance.STK_XR_XD.code.in_(stock_list[:min(list_len, interval)])
    )
    df = finance.run_query(q)

    if list_len > interval:
        df_num = list_len // interval
        for i in range(df_num):
            q = query(finance.STK_XR_XD.code,
                      finance.STK_XR_XD.a_registration_date,
                      finance.STK_XR_XD.bonus_amount_rmb
                      ).filter(
                finance.STK_XR_XD.a_registration_date >= time0,
                finance.STK_XR_XD.a_registration_date <= time1,
                finance.STK_XR_XD.code.in_(stock_list[interval * (i + 1):min(list_len, interval * (i + 2))])
            )
            temp_df = finance.run_query(q)
            df = df.append(temp_df)

    if df is None or df.empty:
        return []
    dividend = df.fillna(0).groupby('code').sum()
    temp_list = list(dividend.index)
    q = query(valuation.code, valuation.market_cap).filter(valuation.code.in_(temp_list))
    cap = get_fundamentals(q, date=time1)
    if cap is None or cap.empty:
        return []
    cap = cap.set_index('code')
    DR = pd.concat([dividend, cap], axis=1).dropna()
    DR['dividend_ratio'] = (DR['bonus_amount_rmb'] / 10000) / DR['market_cap']
    DR = DR.sort_values(by=['dividend_ratio'], ascending=sort)
    return list(DR.index)[int(p1 * len(DR)):int(p2 * len(DR))]


def strategy_2_trade(context):
    sid = 's2'
    dt_last = context.previous_date
    stocks = get_all_securities('stock', dt_last).index.tolist()

    choice = filter_kcbj_stock(stocks)
    choice = filter_st_stock(choice)
    choice = filter_paused_stock(choice)
    choice = _s2_filter_limitup(context, choice)
    choice = _s2_filter_limitdown(context, choice)

    # 高股息(前10%)
    stock_list = _s2_dividend_filter(context, choice, False, 0, 0.1)
    # PEG 合理区间(扣非)
    stock_list = _s2_peg_filter(context, stock_list, 0.1, 2)
    # 排除房地产
    stock_list = _s2_filter_excluded_industries(stock_list)

    if not stock_list:
        log.info("[s2] 候选池为空")
        return

    # 业绩筛选(收入增速 + ROE)
    q = query(valuation.code,
              indicator.inc_total_revenue_year_on_year,
              indicator.inc_return
              ).filter(
        valuation.code.in_(stock_list),
        indicator.inc_total_revenue_year_on_year > 4,
        indicator.inc_return > 4.5
    )
    df = get_fundamentals(q)
    if df is None or df.empty:
        log.info("[s2] 业绩筛选无标的")
        return

    # 扣非净利增速 > 8%
    yoy_map = _s2_calc_adj_profit_yoy(list(df['code']), context.previous_date)
    df = df[df['code'].apply(
        lambda c: yoy_map.get(c) is not None and yoy_map.get(c) > 8.0)].copy()
    if df.empty:
        log.info("[s2] 扣非净利增速>8%筛选后无标的")
        return

    final_list = list(df['code'])[:g.s2_stock_num]
    log.info("[s2] 目标股票: %s" % final_list)

    cd = get_current_data()
    # 卖出: 非目标 且 非昨日涨停
    for stock in list(g.sub_holdings[sid].keys()):
        if stock in final_list:
            continue
        if stock in g.s2_high_limit_list:
            continue
        if cd[stock].last_price < cd[stock].high_limit:
            sub_sell(context, sid, stock)

    # 买入新目标
    to_buy = [s for s in final_list if s not in g.sub_holdings[sid]]
    if to_buy:
        sub_value = get_sub_value(context, sid)
        value_per = min(g.sub_cash[sid] / len(to_buy), sub_value / len(final_list))
        for stock in to_buy:
            sub_buy(context, sid, stock, value_per)


# ============================================================================
# 子策略 3: 大市值 PB<1 价值 + 国债 ETF 兜底
# ============================================================================

def strategy_3_before_market(context):
    """每日 9:02: 更新 s3 持仓的昨日涨停标记"""
    sid = 's3'
    held = [s for s in g.sub_holdings[sid] if s != g.s3_etf]
    g.s3_yesterday_HL_list = []
    if held:
        try:
            df = get_price(held, end_date=context.previous_date, frequency='daily',
                           fields=['close', 'high_limit'], count=1,
                           panel=False, fill_paused=False)
            df = df[df['close'] == df['high_limit']]
            g.s3_yesterday_HL_list = list(df.code)
        except:
            pass


def strategy_3_check_stocks(context):
    """每月 1/11 日 9:06: 选出 s3 的候选股池"""
    cd = get_current_data()
    check_date = context.previous_date - datetime.timedelta(days=200)
    all_stocks = list(get_all_securities(date=check_date).index)

    all_stocks = [s for s in all_stocks if not (
        cd[s].paused or cd[s].is_st or
        ('退' in cd[s].name) or
        s.startswith('68') or s.startswith('8') or s.startswith('4')
    )]
    blacklist = ['600519.XSHG']
    all_stocks = [s for s in all_stocks if s not in blacklist]

    try:
        q = query(
            valuation.code, valuation.market_cap, valuation.pe_ratio,
            income.total_operating_revenue, indicator.roa,
            indicator.inc_net_profit_year_on_year, income.net_profit,
            cash_flow.net_operate_cash_flow
        ).filter(
            valuation.pb_ratio < 1,
            cash_flow.net_operate_cash_flow > 0.8 * income.net_profit,
            cash_flow.subtotal_operate_cash_inflow > 1e6,
            indicator.adjusted_profit > 1e6,
            indicator.roa > 0.15,
            indicator.inc_net_profit_year_on_year > 5,
            valuation.code.in_(all_stocks)
        ).order_by(indicator.roa.desc()).limit(g.s3_stock_num * 3)
        check_out = list(get_fundamentals(q).code)
    except Exception as e:
        log.warn("[s3] 基本面查询失败: %s" % str(e))
        return

    g.s3_check_out_lists = check_out[:g.s3_stock_num]
    log.info("[s3] 选股池: %s" % g.s3_check_out_lists)


def strategy_3_trade(context):
    """每月 1/11 日 9:50: 调仓"""
    sid = 's3'
    target_list = g.s3_check_out_lists[:]
    target_list = _s3_filter_limitup(context, target_list)
    target_list = _s3_filter_limitdown(context, target_list)

    cd = get_current_data()

    # 1) 卖出: 若选出了股票,先卖国债 ETF 腾出资金;卖出非目标个股
    for stock in list(g.sub_holdings[sid].keys()):
        if stock == g.s3_etf:
            if target_list:
                sub_sell(context, sid, stock)
            continue
        if stock in target_list:
            continue
        if stock in g.s3_yesterday_HL_list:
            continue
        if cd[stock].last_price < cd[stock].high_limit:
            sub_sell(context, sid, stock)

    # 2) 买入新目标
    if target_list:
        to_buy = [s for s in target_list if s not in g.sub_holdings[sid]]
        if to_buy:
            sub_value = get_sub_value(context, sid)
            value_per = min(g.sub_cash[sid] / len(to_buy), sub_value / len(target_list))
            for stock in to_buy:
                sub_buy(context, sid, stock, value_per)


def strategy_3_check_limit_up(context):
    """每日 14:00 / 14:50: 涨停打开则卖,余钱买国债 ETF"""
    sid = 's3'
    cd = get_current_data()

    # 检查涨停打开
    for stock in g.s3_yesterday_HL_list[:]:
        if stock not in g.sub_holdings[sid]:
            continue
        if cd[stock].last_price < cd[stock].high_limit:
            log.info("[s3] %s 涨停打开,卖出" % stock)
            sub_sell(context, sid, stock)
            g.s3_yesterday_HL_list.remove(stock)

    # 余钱买国债 ETF(兜底)
    cash = g.sub_cash[sid]
    if cash < 1000:
        return
    if g.s3_etf in g.sub_holdings[sid] and cash < 5000:
        return
    sub_buy(context, sid, g.s3_etf, cash)


# ============================================================================
# 子策略 4: 中证 500 高股息指增
# ============================================================================

def strategy_4_trade(context):
    sid = 's4'
    # 1/6 月或首次运行: 重新选股
    if context.current_dt.month in [1, 6] or not g.s4_stocks:
        g.s4_stocks = _s4_choice_stocks(context, g.s4_stock_num)

    target_list = g.s4_stocks[:]
    if not target_list:
        return
    log.info("[s4] 目标股票: %s" % target_list)

    cd = get_current_data()
    # 卖出非目标
    for stock in list(g.sub_holdings[sid].keys()):
        if stock not in target_list and not cd[stock].paused:
            sub_sell(context, sid, stock)

    # 买入新目标
    to_buy = [s for s in target_list if s not in g.sub_holdings[sid] and not cd[s].paused]
    if to_buy:
        sub_value = get_sub_value(context, sid)
        value_per = min(0.99 * sub_value / len(target_list),
                        g.sub_cash[sid] / len(to_buy))
        for stock in to_buy:
            sub_buy(context, sid, stock, value_per)


def _s4_choice_stocks(context, num):
    stocks = get_index_stocks('000905.XSHG')
    try:
        sdf = get_fundamentals(query(
            valuation.code, valuation.market_cap,
        ).filter(
            valuation.code.in_(stocks),
            valuation.pb_ratio > 0,
            indicator.roe < 20,
            indicator.roa > 2,
            valuation.ps_ratio > 0,
            valuation.pe_ratio < 80,
            valuation.pcf_ratio > 0,
            indicator.inc_revenue_year_on_year > 0.15,
        )).dropna().set_index('code')
    except Exception as e:
        log.warn("[s4] 基本面查询失败: %s" % str(e))
        return []

    stocks = list(sdf.index)
    if not stocks:
        return []

    dt_3y = context.current_dt.date() - datetime.timedelta(days=365)
    try:
        ddf = finance.run_query(query(
            finance.STK_XR_XD.code,
            finance.STK_XR_XD.bonus_amount_rmb,
        ).filter(
            finance.STK_XR_XD.code.in_(stocks),
            finance.STK_XR_XD.board_plan_pub_date > dt_3y,
            finance.STK_XR_XD.bonus_amount_rmb > 0
        )).dropna()
    except:
        return []

    if ddf is None or ddf.empty:
        return []

    stocks = list(set(ddf.code))
    if not stocks:
        return []

    divy = pd.Series(data=np.zeros(len(stocks)), index=stocks)
    for k in ddf.index:
        s = ddf.code[k]
        divy[s] += ddf.bonus_amount_rmb[k]

    sdf = sdf.reindex(stocks)
    sdf['div_3y'] = divy
    sdf['div_ratio'] = 1e-2 * sdf.div_3y / sdf.market_cap
    sdf = sdf.sort_values(by='div_ratio', ascending=False)
    return list(sdf.head(num).index)


# ============================================================================
# 通用过滤函数
# ============================================================================

def filter_new_stock(context, stock_list):
    yesterday = context.previous_date
    return [s for s in stock_list
            if not yesterday - get_security_info(s).start_date < datetime.timedelta(days=375)]


def filter_st_stock(stock_list):
    cd = get_current_data()
    return [s for s in stock_list
            if not cd[s].is_st
            and 'ST' not in cd[s].name
            and '*' not in cd[s].name
            and '退' not in cd[s].name]


def filter_kcbj_stock(stock_list):
    return [s for s in stock_list
            if not (s.startswith('4') or s.startswith('8') or s.startswith('68'))]


def filter_paused_stock(stock_list):
    cd = get_current_data()
    return [s for s in stock_list if not cd[s].paused]


def _s2_filter_limitup(context, stock_list):
    cd = get_current_data()
    held = list(context.portfolio.positions.keys())
    return [s for s in stock_list
            if s in held or cd[s].day_open < cd[s].high_limit]


def _s2_filter_limitdown(context, stock_list):
    cd = get_current_data()
    held = list(context.portfolio.positions.keys())
    return [s for s in stock_list
            if s in held or cd[s].day_open > cd[s].low_limit]


def _s2_filter_excluded_industries(stock_list):
    """排除房地产(申万一级 801180)"""
    try:
        excluded = set(get_industry_stocks('801180'))
        return [s for s in stock_list if s not in excluded]
    except:
        return stock_list


def _s3_filter_limitup(context, stock_list):
    cd = get_current_data()
    held = list(context.portfolio.positions.keys())
    return [s for s in stock_list
            if s in held or cd[s].last_price < cd[s].high_limit]


def _s3_filter_limitdown(context, stock_list):
    cd = get_current_data()
    held = list(context.portfolio.positions.keys())
    return [s for s in stock_list
            if s in held or cd[s].last_price > cd[s].low_limit]