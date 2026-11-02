# Clone from JoinQuant
# postId: 6f398ce93791679cf079ee2b015ccd78
# backtestId: 02fa9b9ffefd0a20586336dfb74b3a0b
# title: 为什么看不到当日的实时调仓？

# -*- coding: utf-8 -*-
"""
聚宽平台 Fama-French 三因子（动量替代版）策略 - 日志精简版
"""

import numpy as np
import pandas as pd
from datetime import datetime

def initialize(context):
    set_params(context)
    set_backtest(context)
    run_daily(trade, 'open')

def set_params(context):
    context.index_symbol = '000852.XSHG'
    context.rebalance_rule = 'daily'
    context.lookback_days = 60
    context.mv_quantile = 0.50
    context.momentum_low_q = 0.30
    context.momentum_high_q = 0.70
    context.select_count = 20
    context.select_method = 'min'
    context.max_position_ratio = 1.0
    context.last_rebalance_date = None
    context.blacklist = set()

def set_backtest(context):
    set_benchmark('000852.XSHG')
    set_slippage(FixedSlippage(0.002))
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, 
                            open_commission=0.0003, close_commission=0.0003,
                            min_commission=5), type='stock')

def trade(context):
    current_date = context.current_dt.date()
    
    if not is_rebalance_day(context, current_date):
        return
    
    # --- 精简：只保留调仓日期提示 ---
    print(f">>> 调仓日：{current_date}")
    
    stocks = get_stock_pool(context)
    stocks = filter_stocks_all_boards(context, stocks)
    
    if len(stocks) == 0:
        print("  警告：股票池为空")
        return
    
    stock_data = get_stock_data_safe(context, stocks)
    if stock_data is None or len(stock_data) < 20:
        print("  警告：数据不足")
        return
    
    alpha_data = calculate_alpha(context, stock_data)
    if alpha_data is None or alpha_data.empty:
        return
    
    # --- 核心输出1：显示符合条件的股票 ---
    target_stocks = select_stocks(context, alpha_data)
    
    rebalance_portfolio_with_min_lot(context, target_stocks)
    context.last_rebalance_date = current_date
    print("")  # 空行分隔

# --- 辅助函数（保持原有逻辑，仅移除内部print）---
def is_rebalance_day(context, current_date):
    rule = context.rebalance_rule
    if rule == 'daily':
        return True
    elif rule == 'weekly':
        return current_date.weekday() == 0
    elif rule == 'monthly':
        if context.last_rebalance_date is None:
            return True
        return current_date.month != context.last_rebalance_date.month
    return True

def get_stock_pool(context):
    try:
        return get_index_stocks(context.index_symbol)
    except:
        return []

def filter_stocks_all_boards(context, stock_list):
    filtered = []
    for stock in stock_list:
        if stock in context.blacklist:
            continue
        try:
            stock_info = get_security_info(stock)
            if stock_info is not None and stock_info.display_name and 'ST' in stock_info.display_name.upper():
                context.blacklist.add(stock)
                continue
        except:
            pass
        try:
            price_data = attribute_history(stock, 1, '1d', ['close'], skip_paused=True, df=True)
            if price_data.empty or price_data['close'].iloc[0] <= 0:
                context.blacklist.add(stock)
                continue
        except:
            context.blacklist.add(stock)
            continue
        filtered.append(stock)
    return filtered

def get_stock_data_safe(context, stock_list):
    if len(stock_list) == 0:
        return None
    data = []
    lookback = context.lookback_days
    for stock in stock_list:
        try:
            price_data = attribute_history(stock, lookback + 1, '1d', ['close', 'volume'], skip_paused=True, df=True)
            if price_data is None or len(price_data) < 2:
                continue
            returns = price_data['close'].iloc[-1] / price_data['close'].iloc[0] - 1.0
            momentum_lookback = min(20, len(price_data))
            momentum = price_data['close'].iloc[-1] / price_data['close'].iloc[-momentum_lookback] - 1.0
            if len(price_data) >= 2:
                daily_returns = price_data['close'].pct_change().dropna()
                volatility = daily_returns.std()
            else:
                volatility = 0.0
            if len(price_data) >= 20:
                recent_volume = price_data['volume'].iloc[-5:].mean()
                previous_volume = price_data['volume'].iloc[-20:-5].mean()
                volume_ratio = recent_volume / (previous_volume + 0.0001)
            else:
                volume_ratio = 1.0
            volatility_inverse = 1.0 / (volatility + 0.0001) if volatility > 0 else 0
            momentum_factor = 0.5 * momentum + 0.3 * volatility_inverse + 0.2 * volume_ratio
            market_cap = price_data['close'].iloc[-1] * 1e8
            data.append({
                'symbol': stock,
                'return': returns,
                'momentum_value': momentum_factor,
                'market_cap': market_cap,
                'price': price_data['close'].iloc[-1]
            })
        except:
            continue
    if len(data) == 0:
        return None
    return pd.DataFrame(data)

def calculate_alpha(context, stock_data):
    df = stock_data.copy()
    mv_threshold = df['market_cap'].quantile(context.mv_quantile)
    df['mv_tag'] = df['market_cap'].apply(lambda x: 2.0 if x >= mv_threshold else 1.0)
    momentum_low = df['momentum_value'].quantile(context.momentum_low_q)
    momentum_high = df['momentum_value'].quantile(context.momentum_high_q)
    def get_momentum_tag(val):
        if val <= momentum_low:
            return 1.0
        elif val <= momentum_high:
            return 2.0
        else:
            return 3.0
    df['momentum_tag'] = df['momentum_value'].apply(get_momentum_tag)
    def group_return(mv_tag, momentum_tag):
        group = df[(df['mv_tag'] == mv_tag) & (df['momentum_tag'] == momentum_tag)]
        if len(group) == 0 or group['market_cap'].sum() == 0:
            return 0.0
        weights = group['market_cap'] / group['market_cap'].sum()
        return (group['return'] * weights).sum()
    smb_small = (group_return(1.0, 1.0) + group_return(1.0, 2.0) + group_return(1.0, 3.0)) / 3.0
    smb_big = (group_return(2.0, 1.0) + group_return(2.0, 2.0) + group_return(2.0, 3.0)) / 3.0
    smb = smb_small - smb_big
    hml_high = (group_return(1.0, 3.0) + group_return(2.0, 3.0)) / 2.0
    hml_low = (group_return(1.0, 1.0) + group_return(2.0, 1.0)) / 2.0
    hml = hml_high - hml_low
    market_return = df['return'].mean()
    df['alpha'] = df['return'] - (market_return + smb + hml)
    return df

def select_stocks(context, alpha_data):
    if context.select_method == 'min':
        selected = alpha_data.nsmallest(context.select_count, 'alpha')
    else:
        selected = alpha_data.nlargest(context.select_count, 'alpha')
    
    target_stocks = selected['symbol'].tolist()
    # --- 核心输出1：显示符合条件的股票 ---
    print(f"  符合条件股票({len(target_stocks)}只): {target_stocks}")
    return target_stocks

def rebalance_portfolio_with_min_lot(context, target_stocks):
    current_positions = list(context.portfolio.positions.keys())
    
    # --- 核心输出2：显示卖出记录 ---
    stocks_to_sell = [s for s in current_positions if s not in target_stocks]
    if stocks_to_sell:
        for stock in stocks_to_sell:
            print(f"  卖出: {stock}")
            place_safe_order_fixed(context, stock, 0, "卖出")
    
    if target_stocks:
        total_available = context.portfolio.available_cash
        for pos in context.portfolio.positions.values():
            total_available += pos.value
        target_value_per_stock = total_available * context.max_position_ratio / len(target_stocks)
        orders = []
        for stock in target_stocks:
            try:
                current_data = get_current_data()[stock]
                current_price = current_data.last_price
                if current_price <= 0:
                    continue
                if stock.startswith('688'):
                    min_lot = 200
                else:
                    min_lot = 100
                target_amount = int(target_value_per_stock / current_price / min_lot) * min_lot
                if target_amount == 0:
                    target_amount = min_lot
                required_cash = target_amount * current_price
                orders.append({
                    'stock': stock,
                    'target_amount': target_amount,
                    'current_price': current_price,
                    'required_cash': required_cash,
                    'min_lot': min_lot
                })
            except:
                continue
        total_required = sum([o['required_cash'] for o in orders])
        if total_required > context.portfolio.available_cash:
            scale_factor = context.portfolio.available_cash / total_required
            for order_info in orders:
                adjusted_amount = int(order_info['target_amount'] * scale_factor / order_info['min_lot']) * order_info['min_lot']
                if adjusted_amount < order_info['min_lot']:
                    adjusted_amount = order_info['min_lot']
                order_info['target_amount'] = adjusted_amount
                order_info['required_cash'] = adjusted_amount * order_info['current_price']
        # --- 核心输出3：显示买入记录 ---
        for order_info in orders:
            stock = order_info['stock']
            target_amount = order_info['target_amount']
            current_price = order_info['current_price']
            min_lot = order_info['min_lot']
            current_data = get_current_data()[stock]
            limit_price = current_price * 1.015
            if hasattr(current_data, 'high_limit') and current_data.high_limit > 0:
                limit_price = min(limit_price, current_data.high_limit)
            if stock.startswith('688') and limit_price > 10000:
                limit_price = 9999.99
            try:
                order(stock, target_amount, style=LimitOrderStyle(limit_price))
                print(f"  买入: {stock}")
            except Exception as e:
                print(f"  买入 {stock} 失败: {e}")

def place_safe_order_fixed(context, symbol, target_value, side="买入"):
    try:
        current_data = get_current_data()[symbol]
        current_price = current_data.last_price
        if current_price <= 0:
            return False
        if symbol.startswith('688'):
            min_lot = 200
        else:
            min_lot = 100
        if target_value <= 0:
            if symbol in context.portfolio.positions:
                current_pos = context.portfolio.positions[symbol]
                target_amount = -current_pos.total_amount
            else:
                target_amount = 0
        else:
            target_amount = int(target_value / current_price / min_lot) * min_lot
            if target_amount == 0 and target_value > 0:
                target_amount = min_lot
        if target_amount == 0:
            return True
        if side == "买入":
            limit_price = current_price * 1.015
            if hasattr(current_data, 'high_limit') and current_data.high_limit > 0:
                limit_price = min(limit_price, current_data.high_limit)
        else:
            limit_price = current_price * 0.985
            if hasattr(current_data, 'low_limit') and current_data.low_limit > 0:
                limit_price = max(limit_price, current_data.low_limit)
        if symbol.startswith('688') and limit_price > 10000:
            limit_price = 9999.99
        order(symbol, target_amount, style=LimitOrderStyle(limit_price))
        return True
    except:
        return False