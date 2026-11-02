# Clone from JoinQuant
# postId: 15582f8d340448954f358bc781dcd55b
# backtestId: f1f03e18d13787b559f8c1adf53c0732
# title: 请教一下策略始终执行不了的问题

# 最终修复版：有效池为0问题根因修正
# 核心改变：get_all_securities(['stock']) 不传date参数，自动适配备测当日的股票列表

from jqdata import *
import pandas as pd
import numpy as np
import datetime as dt

# ==================== 参数区 ====================
MAX_PORTFOLIO_PCT  = 0.7
SINGLE_STOCK_PCT   = 0.30
MAX_PE             = 150
MIN_MARKET_CAP     = 15e8
MAX_MARKET_CAP     = 250e8
MIN_PROFIT_GROWTH  = -0.10
MAX_CHASE_PCT      = 0.09
STOP_LOSS_PCT      = -0.05
MAX_HOLD_DAYS      = 5
MIN_HOLD_DAYS      = 1

# ==================== 初始化 ====================
def initialize(context):
    set_order_cost(OrderCost(close_tax=0.001,
                             open_commission=0.0003,
                             close_commission=0.0003,
                             min_commission=5), type='stock')
    set_benchmark('000300.XSHG')
    set_option('avoid_future_data', True)

    g.last_buy_date   = {}
    g.entry_price     = {}
    g.lock_today      = False
    g.max_pos_pct     = MAX_PORTFOLIO_PCT
    g.single_pct      = SINGLE_STOCK_PCT
    g.max_hold_days   = MAX_HOLD_DAYS
    g.min_hold_days   = MIN_HOLD_DAYS
    g.debug_info      = []

    # 定时任务
    run_daily(pre_market_selection, time='9:05')
    run_daily(trade_open, time='9:31')
    run_daily(afternoon_check, time='14:30')
    run_daily(print_debug, time='15:10')

    g.candidate_pool = []
    pre_market_selection(context)

# ==================== 辅助函数 ====================
def is_valid_stock(symbol):
    try:
        info = get_security_info(symbol)
        if info is None:
            return False
        name = info.display_name
        if 'ST' in name or '*' in name:
            return False
        days_since_ipo = (context.current_dt.date() - info.start_date).days
        if days_since_ipo < 60:
            return False
        # 剔除北交所
        if symbol.startswith('8'):
            return False
        return True
    except:
        return False

def get_limit_up_stocks(context):
    today = context.current_dt.date()
    yesterday = today - dt.timedelta(days=1)

    # 🔧 核心修正：不传date参数，由回测引擎自动给出当时存活的股票
    all_stocks = list(get_all_securities(['stock']).index)
    valid_stocks = [s for s in all_stocks if is_valid_stock(s)]
    g.debug_info.append(f"有效池: {len(valid_stocks)}")

    if not valid_stocks:
        return []

    # 获取过去2日的收盘价，用于手动计算涨停阈值
    try:
        df_hist = history(2, unit='1d', field='close',
                         security_list=valid_stocks,
                         skip_paused=True, fq='pre')
    except Exception as e:
        g.debug_info.append(f"history异常: {e}")
        return []

    if df_hist is None or df_hist.empty or len(df_hist) < 2:
        g.debug_info.append("K线不足2日")
        return []

    limit_up_codes = []
    for s in valid_stocks:
        try:
            closes = df_hist[s]
            if len(closes) < 2:
                continue
            prev_close = closes.iloc[0]         # 前日收盘价
            yesterday_close = closes.iloc[1]    # 昨日收盘价
            if pd.isna(prev_close) or pd.isna(yesterday_close) or prev_close <= 0:
                continue

            # 涨跌幅限制
            if s.startswith('688') or s.startswith('300'):
                limit_pct = 1.20
            else:
                limit_pct = 1.10
            limit_price = prev_close * limit_pct

            # 昨日收盘价 ≥ 涨停价*0.995 视为涨停
            if yesterday_close >= limit_price * 0.995:
                limit_up_codes.append(s)
        except:
            continue

    g.debug_info.append(f"涨停股: {len(limit_up_codes)}")
    if not limit_up_codes:
        return []

    # 财务过滤
    try:
        q = query(valuation.code,
                  valuation.market_cap, valuation.pe_ratio,
                  indicator.inc_net_profit_year_on_year
                 ).filter(valuation.code.in_(limit_up_codes))
        df_fund = get_fundamentals(q, date=yesterday)
        if df_fund is not None and not df_fund.empty:
            df_fund['pe_ratio'] = df_fund['pe_ratio'].fillna(999)
            df_fund['inc_net_profit_year_on_year'] = df_fund['inc_net_profit_year_on_year'].fillna(0)
            df_filter = df_fund[(df_fund['market_cap'] >= MIN_MARKET_CAP) &
                                (df_fund['market_cap'] <= MAX_MARKET_CAP) &
                                (df_fund['pe_ratio'] > 0) &
                                (df_fund['pe_ratio'] < MAX_PE) &
                                (df_fund['inc_net_profit_year_on_year'] > MIN_PROFIT_GROWTH)]
            g.debug_info.append(f"财务后候选: {len(df_filter)}")
            if not df_filter.empty:
                df_sorted = df_filter.sort_values('market_cap', ascending=True)
                return df_sorted.head(10)['code'].tolist()
    except Exception as e:
        g.debug_info.append(f"财务异常: {e}")

    # 兜底：按代码排序取前10只涨停股
    fallback = sorted(limit_up_codes)[:10]
    g.debug_info.append(f"兜底候选: {len(fallback)}")
    return fallback

def get_open_price(symbol):
    try:
        return get_current_data()[symbol].day_open
    except:
        return None

def get_prev_close(symbol):
    try:
        df = attribute_history(symbol, count=2, unit='1d', fields=['close'], skip_paused=True)
        if len(df) >= 2:
            return df['close'].iloc[-2]
    except:
        pass
    return None

def can_buy_today(symbol):
    if context.portfolio.positions.get(symbol):
        return False
    if g.lock_today:
        return False
    open_price = get_open_price(symbol)
    prev_close = get_prev_close(symbol)
    if open_price is None or prev_close is None or prev_close <= 0:
        return False
    if (open_price - prev_close) / prev_close > MAX_CHASE_PCT:
        return False
    return True

def should_sell_for_risk(symbol, current_price):
    pos = context.portfolio.positions.get(symbol)
    if not pos or pos.closeable_amount == 0:
        return False
    entry = g.entry_price.get(symbol)
    if entry is None or entry <= 0:
        return False
    if (current_price - entry) / entry <= STOP_LOSS_PCT:
        g.debug_info.append(f"止损 {symbol}")
        return True
    last_buy = g.last_buy_date.get(symbol)
    if last_buy:
        hold_days = (context.current_dt.date() - last_buy).days
        if hold_days >= g.max_hold_days:
            g.debug_info.append(f"到期 {symbol}")
            return True
    return False

# ==================== 核心交易函数 ====================
def pre_market_selection(context):
    g.candidate_pool = get_limit_up_stocks(context)

def trade_open(context):
    # 先止损
    for symbol in list(context.portfolio.positions.keys()):
        try:
            cur_price = get_current_data()[symbol].last_price
            if should_sell_for_risk(symbol, cur_price):
                order_target(symbol, 0)
        except:
            pass
    if g.lock_today:
        return
    if not hasattr(g, 'candidate_pool') or not g.candidate_pool:
        return

    current_value = context.portfolio.positions_value
    total_value = context.portfolio.total_value
    current_pct = current_value / total_value if total_value > 0 else 0
    available_pct = g.max_pos_pct - current_pct
    if available_pct <= 0:
        return

    for symbol in g.candidate_pool:
        if available_pct <= 0:
            break
        if not can_buy_today(symbol):
            continue
        buy_value = total_value * min(available_pct, g.single_pct)
        order_target_value(symbol, buy_value)
        g.last_buy_date[symbol] = context.current_dt.date()
        try:
            g.entry_price[symbol] = get_current_data()[symbol].last_price
        except:
            g.entry_price[symbol] = get_open_price(symbol)
        available_pct -= g.single_pct

def afternoon_check(context):
    pass

def print_debug(context):
    if g.debug_info:
        for msg in g.debug_info[-10:]:
            log.info(msg)
    g.debug_info = []