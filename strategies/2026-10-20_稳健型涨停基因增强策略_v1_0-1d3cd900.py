# Clone from JoinQuant
# postId: 1d3cd90089d8d974e7e8ca1e5f663052
# backtestId: 2bf5cdc0ee493073435a2db5d3bf782d
# title: 稳健型涨停基因增强策略 v1.0

# 克隆并重构自聚宽文章：https://www.joinquant.com/post/64877
# 标题：【2026新版】涨停基因+小市值增强策略（适应当前A股生态）
# 作者：Qwen（基于Loylee原版深度优化，修复valuation.avg_amount错误）

from jqdata import *
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

def initialize(context):
    set_option('avoid_future_data', True)
    set_benchmark('399852.XSHE')  # 中证1000
    set_option('use_real_price', True)
    set_slippage(PriceRelatedSlippage(0.002))
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0.0005,
            open_commission=0.0001,
            close_commission=0.0001,
            close_today_commission=0,
            min_commission=1,
        ),
        type='stock'
    )
    log.set_level('order', 'error')
    log.set_level('system', 'error')

    # === 全局参数 ===
    g.stock_num = 3
    g.max_stock_pool = 200
    g.min_list_days = 180
    g.max_price = 50
    g.min_money = 30000000  # 当日成交额 > 3000万元
    g.limit_up_count_window = 250
    g.min_limit_up_count = 2
    g.stoploss_limit = 0.91
    g.market_down_threshold = 0.98
    g.blacklist_days = 30
    g.pass_april = True

    # === 全局状态 ===
    g.hold_list = []
    g.target_list = []
    g.loss_black = {}
    g.no_trading_today = False

    # === 定时任务 ===
    run_daily(prepare_before_trading, time='09:00')
    run_weekly(trade_logic, 1, time='10:15')
    run_daily(sell_by_stoploss, time='11:25')
    run_daily(sell_by_stoploss, time='14:50')
    run_daily(check_limit_open, time='14:50')
    run_daily(handle_no_trading_month, time='14:55')


def prepare_before_trading(context):
    g.hold_list = list(context.portfolio.positions.keys())
    g.no_trading_today = is_no_trading_day(context)


def trade_logic(context):
    if g.no_trading_today:
        return

    current = context.current_dt
    g.loss_black = {s: d for s, d in g.loss_black.items() if (current - d).days <= g.blacklist_days}

    target_candidates = get_stock_pool(context)
    if not target_candidates:
        log.info("无符合条件股票")
        return

    target_list = select_by_industry_diversity(target_candidates, max_per_industry=1)
    g.target_list = target_list[:g.stock_num]
    log.info(f"本周目标池: {g.target_list}")

    # 卖出不在目标池且未涨停的股票
    current_data = get_current_data()
    for stock in g.hold_list:
        if stock not in g.target_list:
            if current_data[stock].last_price < current_data[stock].high_limit:
                order_target_value(stock, 0)
                log.info(f"调仓卖出: {stock}")

    buy_stocks_equal_weight(context, g.target_list)


def get_stock_pool(context):
    yesterday = context.previous_date
    all_stocks = list(get_all_securities(['stock'], date=yesterday).index)

    stocks = filter_paused(all_stocks)
    stocks = filter_st(stocks)
    stocks = filter_kcbj(stocks)
    stocks = filter_new(stocks, context, min_days=g.min_list_days)
    stocks = filter_high_price(stocks, context, max_price=g.max_price)
    stocks = filter_low_liquidity(stocks, context, min_money=g.min_money)
    stocks = filter_by_limit_up_history(stocks, context, window=g.limit_up_count_window, min_count=g.min_limit_up_count)
    stocks = filter_by_start_point(stocks, context, window=g.limit_up_count_window)

    q = query(valuation.code).filter(valuation.code.in_(stocks)).order_by(valuation.market_cap.asc())
    df = get_fundamentals(q, date=yesterday)
    return df['code'].tolist()[:g.max_stock_pool]


# === 过滤器 ===
def filter_paused(stock_list):
    current = get_current_data()
    return [s for s in stock_list if not current[s].paused]

def filter_st(stock_list):
    current = get_current_data()
    return [
        s for s in stock_list
        if not current[s].is_st
        and 'ST' not in current[s].name
        and '*' not in current[s].name
        and '退' not in current[s].name
    ]

def filter_kcbj(stock_list):
    return [s for s in stock_list if s[0] not in ['4', '8'] and not s.startswith('68')]

def filter_new(stock_list, context, min_days=180):
    yesterday = context.previous_date
    return [
        s for s in stock_list
        if (yesterday - get_security_info(s).start_date).days >= min_days
    ]

def filter_high_price(stock_list, context, max_price=50):
    prices = history(1, '1m', 'close', security_list=stock_list, df=False)
    current = get_current_data()
    return [
        s for s in stock_list
        if s in context.portfolio.positions or prices[s][-1] <= max_price
    ]

def filter_low_liquidity(stock_list, context, min_money=30000000):
    """使用当日成交额（indicator.money）过滤低流动性股票"""
    if not stock_list:
        return []
    try:
        q = query(indicator.code, indicator.money).filter(indicator.code.in_(stock_list))
        df = get_fundamentals(q, date=context.previous_date)
        valid_codes = df[df['money'] > min_money]['code'].tolist()
        return [s for s in stock_list if s in valid_codes]
    except Exception as e:
        log.error(f"流动性过滤出错: {e}")
        return stock_list  # 容错：返回原列表


def filter_by_limit_up_history(stock_list, context, window=250, min_count=2):
    df = get_price(
        stock_list,
        end_date=context.previous_date,
        frequency='daily',
        fields=['close', 'high_limit'],
        count=window,
        panel=False
    )
    df = df[df['close'] == df['high_limit']]
    counts = df.groupby('code').size()
    return counts[counts >= min_count].index.tolist()

def filter_by_start_point(stock_list, context, window=250):
    df = get_price(
        stock_list,
        end_date=context.previous_date,
        frequency='daily',
        fields=['open', 'close', 'low', 'high_limit', 'volume'],
        count=window,
        panel=False
    )
    valid_stocks = []
    for code, group in df.groupby('code'):
        group = group.sort_values('time')
        limit_hits = group[group['close'] == group['high_limit']]
        if limit_hits.empty:
            continue
        latest_limit_time = limit_hits['time'].max()
        before_limit = group[group['time'] < latest_limit_time].sort_values('time', ascending=False)
        if not before_limit.empty:
            recent = before_limit.iloc[0]
            avg_vol = before_limit['volume'].mean()
            if recent['close'] < recent['open'] and recent['volume'] < avg_vol * 0.8:
                valid_stocks.append(code)
    return valid_stocks


def select_by_industry_diversity(stock_list, max_per_industry=1):
    if not stock_list:
        return []
    try:
        sw_info = get_industry(security=stock_list)
        industry_map = {}
        result = []
        used_industries = set()
        for stock in stock_list:
            ind = sw_info.get(stock, {}).get('sw_l1', {}).get('industry_name', '未知')
            if ind not in used_industries:
                used_industries.add(ind)
                result.append(stock)
                if len(result) >= 10:
                    break
        return result
    except Exception as e:
        log.error(f"行业分散出错: {e}")
        return stock_list[:10]


def buy_stocks_equal_weight(context, target_list):
    current_positions = set(context.portfolio.positions.keys())
    to_buy = [s for s in target_list if s not in current_positions and s not in g.loss_black]
    if not to_buy:
        return

    cash = context.portfolio.cash
    per_value = cash / len(to_buy)
    for stock in to_buy:
        order_target_value(stock, per_value)
        log.info(f"买入: {stock}, 目标市值: {per_value:.2f}")


def sell_by_stoploss(context):
    if g.no_trading_today:
        return

    # 市场风险：中证1000单日跌幅 > 2%
    idx = '399852.XSHE'
    try:
        idx_df = get_price(idx, end_date=context.previous_date, frequency='daily', fields=['open', 'close'], count=1, panel=False)
        if not idx_df.empty:
            ratio = idx_df.iloc[0]['close'] / idx_df.iloc[0]['open']
            if ratio < g.market_down_threshold:
                log.info(f"中证1000大跌{1-ratio:.2%}，清仓避险")
                for stock in list(context.portfolio.positions.keys()):
                    order_target_value(stock, 0)
                    g.loss_black[stock] = context.current_dt
                return
    except Exception as e:
        log.error(f"大盘判断出错: {e}")

    # 个股止损
    for stock in list(context.portfolio.positions.keys()):
        pos = context.portfolio.positions[stock]
        if pos.price < pos.avg_cost * g.stoploss_limit:
            order_target_value(stock, 0)
            log.info(f"个股止损卖出: {stock}")
            g.loss_black[stock] = context.current_dt


def check_limit_open(context):
    current_data = get_current_data()
    for stock in list(context.portfolio.positions.keys()):
        if stock not in g.target_list:
            if current_data[stock].last_price < current_data[stock].high_limit:
                order_target_value(stock, 0)
                log.info(f"尾盘非目标池且未涨停，卖出: {stock}")


def is_no_trading_day(context):
    return g.pass_april and context.current_dt.month == 4

def handle_no_trading_month(context):
    if g.no_trading_today and len(context.portfolio.positions) > 0:
        log.info("4月空仓，清仓")
        for stock in list(context.portfolio.positions.keys()):
            order_target_value(stock, 0)