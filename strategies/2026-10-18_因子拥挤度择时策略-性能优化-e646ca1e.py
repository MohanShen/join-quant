# Clone from JoinQuant
# postId: e646ca1e6aedf533ad6d36ad685f81b3
# backtestId: b20ee4f0d92e95a150bef9b292bd2444
# title: 因子拥挤度择时策略-性能优化

import numpy as np
import pandas as pd
import datetime
import math
from jqdata import *
from jqfactor import *
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta

# 初始化函数
def initialize(context):
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('history', 'error')
    set_option('use_real_price', True)
    set_option("avoid_future_data", True)
    
    g.sorted_stocks = []
    g.just_sold = []
    g.stock_num = 10
    g.high_limit_list = []
    g.max_stock_price = 9    
    g.risk_control_executed = False
    g.today_trade_allowed = True
    
    g.factor_threshold_results = {}
    g.last_factor_analysis_date = None
    
    g.buy_thresholds = {
        'momentum_20': 1.6242,
        'turnover_ratio': 1.2591,
        'pe_ratio': 0.6478,
        'pb_ratio': 1.2716
    }
    
    g.sell_thresholds = {
        'momentum_20': 1.4326,
        'pcf_ratio': 0.6007,
        'pb_ratio': 1.3846,
        'volatility_20': 1.7698
    }
    
    g.hold_ranges = {
        'momentum_20': (1.4709, 1.5859),
        'turnover_ratio': (1.1447, 1.2591),
        'pe_ratio': (0.6478, 0.7553)
    }
    
    g.buy_signal_required = 1
    g.sell_signal_required = 4
    
    g.ban_trade_start_date = None
    g.ban_trade_days = 0
    g.ban_trade_period = 5
    
    g.dbl = []
    g.dixl = []
    
    run_daily(prepare_stock_list, '09:00:00')
    run_daily(dapan, '09:30')
    run_daily(check_factor_threshold, '09:31')
    run_monthly(monthly_adjustment, 1, '09:35')
    run_daily(check_limit_up_and_buy, '14:50')

# ==================== 核心选股与交易逻辑 ====================

def monthly_adjustment(context):
    if not g.today_trade_allowed:
        return
        
    daily_my_Trader_1(context)
    
    cdata = get_current_data()
    positions = context.portfolio.positions
    
    # 卖出不在列表中的股票
    for s in list(positions.keys()):
        if s not in g.sorted_stocks:
            close_position(positions[s])
    
    available_cash = context.portfolio.available_cash
    position_count = len(positions)
    if len(g.sorted_stocks) <= position_count or available_cash <= 0:
        return
        
    psize = available_cash / (len(g.sorted_stocks) - position_count)
    for s in g.sorted_stocks:
        if (s not in positions 
            and cdata[s].last_price < cdata[s].high_limit
            and cdata[s].last_price > cdata[s].low_limit
            and not cdata[s].paused
            and s not in g.just_sold
        ):
            if open_position(s, psize):
                available_cash -= psize
            if available_cash <= 0 or len(context.portfolio.positions) >= g.stock_num:
                break

def daily_my_Trader_1(context):
    yesterday = context.previous_date
    stocks = get_all_securities('stock', yesterday).index.tolist()
    stocks = filter_kcbj_stock(stocks)
    stocks = get_dividend_ratio_filter_list(context, stocks, False, 0, 0.25)
    stocks = get_peg(context, stocks)
    stocks = filter_all_stock(context, stocks)
    stocks = filter_highprice_stock(context, stocks)
    
    if not stocks:
        g.sorted_stocks = []
        return g.sorted_stocks
        
    df = get_fundamentals(
        query(valuation.code, valuation.market_cap)
        .filter(valuation.code.in_(stocks))
        .order_by(valuation.market_cap.asc(), valuation.code.asc())
    )
    g.sorted_stocks = list(df.code)[:g.stock_num]
    return g.sorted_stocks

def open_position(security, value):
    order = order_target_value(security, value)
    return order is not None and order.filled > 0

def close_position(position):
    security = position.security
    order = order_target_value(security, 0)
    g.just_sold.append(security)
    return order is not None and order.filled > 0

# ==================== 涨停处理与补仓 ====================

def check_limit_up_and_buy(context):
    if g.risk_control_executed:
        return
        
    current_data = get_current_data()
    sold_stocks = []
    
    # 卖出打开涨停的股票（即使禁止交易也允许）
    for stock in g.high_limit_list.copy():
        if current_data[stock].last_price < current_data[stock].high_limit:
            if stock in context.portfolio.positions:
                close_position(context.portfolio.positions[stock])
                sold_stocks.append(stock)
                g.high_limit_list.remove(stock)
                
    if not g.today_trade_allowed:
        return
        
    if not sold_stocks:
        return
        
    daily_my_Trader_1(context)
    valid_stocks = [s for s in g.sorted_stocks if s not in g.just_sold]
    
    available_cash = context.portfolio.available_cash
    position_count = len(context.portfolio.positions)
    need_buy_num = max(0, g.stock_num - position_count)
    
    if need_buy_num <= 0 or available_cash <= 0:
        return
        
    psize = available_cash / need_buy_num
    bought = 0
    for s in valid_stocks:
        if (s not in context.portfolio.positions 
            and current_data[s].last_price < current_data[s].high_limit
            and current_data[s].last_price > current_data[s].low_limit
            and not current_data[s].paused
        ):
            if open_position(s, psize):
                bought += 1
            if bought >= need_buy_num:
                break

def prepare_stock_list(context):
    g.just_sold = []
    g.risk_control_executed = False
    g.high_limit_list = []
    hold_list = list(context.portfolio.positions)
    if hold_list:
        df = get_price(hold_list, end_date=context.previous_date, frequency='daily',
                       fields=['close', 'high_limit'], count=1, panel=False)
        if not df.empty:
            g.high_limit_list = df[df['close'] == df['high_limit']]['code'].tolist()

# ==================== 大盘 MACD 背离风控 ====================

def dapan(context):
    if g.risk_control_executed:
        return
        
    if g.ban_trade_start_date is not None:
        trade_days = get_trade_days(start_date=g.ban_trade_start_date, end_date=context.current_dt.date())
        ban_trade_days = len(trade_days) - 1
        if ban_trade_days >= g.ban_trade_period:
            g.ban_trade_start_date = None
            g.ban_trade_days = 0
            
    if not g.today_trade_allowed and g.ban_trade_start_date is not None:
        return
        
    top_divergence, bottom_divergence = detect_divergences('399303.XSHE', context)
    
    if top_divergence:
        g.dbl.append(True)
        g.today_trade_allowed = False    
        g.ban_trade_start_date = context.current_dt.date()
        g.risk_control_executed = True
        
        current_data = get_current_data()
        for stock in list(context.portfolio.positions.keys()):
            if current_data[stock].last_price < current_data[stock].high_limit:
                close_position(context.portfolio.positions[stock])
    
    if bottom_divergence:
        g.dixl.append(True)

# ==================== MACD 背离检测 ====================

def EMA(series, N):
    return pd.Series.ewm(series, span=N, min_periods=N-1, adjust=False).mean()

def MACD(close, SHORT=12, LONG=26, M=9):
    DIF = EMA(close, SHORT) - EMA(close, LONG)
    DEA = EMA(DIF, M)
    MACD_val = (DIF - DEA) * 2
    return DIF, DEA, MACD_val

def detect_divergences(stock, context):
    fast, slow, sign = 12, 26, 9
    rows = (fast + slow + sign) * 5
    
    try:
        grid = attribute_history(stock, rows, fields=['close'])
        if grid is None or len(grid) < rows:
            return False, False
    except:
        return False, False
        
    try:
        grid['dif'], grid['dea'], grid['macd'] = MACD(grid.close, fast, slow, sign)
        
        dead_cross = (grid['macd'] < 0) & (grid['macd'].shift(1) > 0)
        gold_cross = (grid['macd'] > 0) & (grid['macd'].shift(1) < 0)
        dead_points = dead_cross[dead_cross].index
        gold_points = gold_cross[gold_cross].index
        
        top_divergence = False
        if len(dead_points) >= 2:
            k2, k1 = dead_points[-2], dead_points[-1]
            price_ok = grid.close[k2] < grid.close[k1]
            dif_ok = grid.dif[k2] > grid.dif[k1] > 0
            macd_ok = grid.macd.iloc[-2] > 0 > grid.macd.iloc[-1]
            if price_ok and dif_ok and macd_ok and len(grid) > 20:
                recent_avg = grid['dif'].iloc[-10:].mean()
                prev_avg = grid['dif'].iloc[-20:-10].mean()
                top_divergence = recent_avg < prev_avg
                
        bottom_divergence = False
        if len(gold_points) >= 2:
            k2, k1 = gold_points[-2], gold_points[-1]
            price_ok = grid.close[k2] > grid.close[k1]
            dif_ok = grid.dif[k2] < grid.dif[k1] < 0
            macd_ok = grid.macd.iloc[-2] < 0 < grid.macd.iloc[-1]
            if price_ok and dif_ok and macd_ok and len(grid) > 20:
                recent_avg = grid['dif'].iloc[-10:].mean()
                prev_avg = grid['dif'].iloc[-20:-10].mean()
                bottom_divergence = recent_avg > prev_avg
                
        return top_divergence, bottom_divergence
        
    except:
        return False, False

# ==================== 因子择时系统 ====================

def calculate_technical_indicators(stock, date):
    try:
        trade_days = get_trade_days(end_date=date, count=60)
        if len(trade_days) < 20:
            return None, None
        start_date = trade_days[0].strftime('%Y-%m-%d')
        prices = get_price(stock, start_date=start_date, end_date=date, frequency='daily', fields=['close'], skip_paused=True)
        if prices is None or len(prices) < 21:
            return None, None
        closes = prices['close']
        momentum_20 = (closes.iloc[-1] / closes.iloc[-21] - 1) * 100
        returns = closes.pct_change().dropna()
        volatility_20 = returns.tail(20).std() * np.sqrt(252) * 100 if len(returns) >= 20 else np.nan
        return momentum_20, volatility_20
    except:
        return None, None

def analyze_market_factors(date):
    try:
        stocks = get_all_securities(['stock'], date).index.tolist()
        if len(stocks) < 100:
            return {}, "hold"
            
        st_info = get_extras('is_st', stocks, start_date=date, end_date=date, df=True)
        if not st_info.empty:
            non_st = st_info.columns[st_info.iloc[0] == False].tolist()
            stocks = [s for s in stocks if s in non_st]
            
        filtered_stocks = [s for s in stocks if not s.startswith(('300', '688'))]
        if len(filtered_stocks) < 100:
            filtered_stocks = stocks
            
        q = query(
            valuation.code,
            valuation.pe_ratio,
            valuation.pb_ratio,
            valuation.pcf_ratio,
            valuation.turnover_ratio,
            valuation.market_cap
        ).filter(valuation.code.in_(filtered_stocks))
        
        df = get_fundamentals(q, date)
        if df is None or df.empty:
            return {}, "hold"
        df.set_index('code', inplace=True)
        df = df.dropna()
        if df.empty:
            return {}, "hold"
            
        df_sorted = df.sort_values(by='market_cap', ascending=True)
        sample_stocks = df_sorted.index[:500].tolist()
        
        tech_data = []
        for stock in sample_stocks:
            mom, vol = calculate_technical_indicators(stock, date)
            if mom is not None and vol is not None:
                tech_data.append({'stock': stock, 'momentum_20': mom, 'volatility_20': vol})
                
        if tech_data:
            tech_df = pd.DataFrame(tech_data).set_index('stock')
            merged_df = df.join(tech_df, how='inner').dropna()
        else:
            merged_df = df.dropna()
            
        if merged_df.empty:
            return {}, "hold"
            
        factor_medians = {}
        for col in ['pe_ratio', 'pb_ratio', 'pcf_ratio', 'turnover_ratio', 'momentum_20', 'volatility_20']:
            if col in merged_df.columns:
                vals = merged_df[col].dropna()
                if len(vals) >= 10:
                    factor_medians[col] = np.median(vals)
                    
        signal = generate_trading_signal(factor_medians)
        return factor_medians, signal
        
    except:
        return {}, "hold"

def generate_trading_signal(factor_medians):
    if not factor_medians:
        return "hold"
        
    buy_met = sum([
        factor_medians.get('momentum_20', -np.inf) >= g.buy_thresholds['momentum_20'],
        factor_medians.get('turnover_ratio', -np.inf) >= g.buy_thresholds['turnover_ratio'],
        factor_medians.get('pe_ratio', np.inf) <= g.buy_thresholds['pe_ratio'],
        factor_medians.get('pb_ratio', np.inf) <= g.buy_thresholds['pb_ratio']
    ])
    
    sell_met = sum([
        factor_medians.get('momentum_20', np.inf) <= g.sell_thresholds['momentum_20'],
        factor_medians.get('pcf_ratio', np.inf) <= g.sell_thresholds['pcf_ratio'],
        factor_medians.get('pb_ratio', -np.inf) >= g.sell_thresholds['pb_ratio'],
        factor_medians.get('volatility_20', -np.inf) >= g.sell_thresholds['volatility_20']
    ])
    
    buy_signal = buy_met >= g.buy_signal_required
    sell_signal = sell_met >= g.sell_signal_required
    
    if buy_signal and not sell_signal:
        return "buy"
    elif sell_signal and not buy_signal:
        return "sell"
    else:
        hold_met = 0
        if 'momentum_20' in factor_medians:
            v = factor_medians['momentum_20']
            if g.hold_ranges['momentum_20'][0] <= v <= g.hold_ranges['momentum_20'][1]:
                hold_met += 1
        if 'turnover_ratio' in factor_medians:
            v = factor_medians['turnover_ratio']
            if g.hold_ranges['turnover_ratio'][0] <= v <= g.hold_ranges['turnover_ratio'][1]:
                hold_met += 1
        if 'pe_ratio' in factor_medians:
            v = factor_medians['pe_ratio']
            if g.hold_ranges['pe_ratio'][0] <= v <= g.hold_ranges['pe_ratio'][1]:
                hold_met += 1
        return "hold"

def check_factor_threshold(context):
    if g.risk_control_executed:
        return
        
    current_date = context.current_dt.date()
    yesterday = context.previous_date
    
    ban_period_ended = False
    if g.ban_trade_start_date is not None:
        trade_days = get_trade_days(start_date=g.ban_trade_start_date, end_date=current_date)
        if len(trade_days) - 1 >= g.ban_trade_period:
            ban_period_ended = True
            g.ban_trade_start_date = None
            g.ban_trade_days = 0
            
    if g.last_factor_analysis_date == yesterday:
        return
        
    factor_medians, signal = analyze_market_factors(yesterday)
    
    if signal == "buy":
        g.today_trade_allowed = True
        if ban_period_ended:
            execute_recovery_buying(context)
    elif signal == "sell":
        current_data = get_current_data()
        for stock in list(context.portfolio.positions.keys()):
            if current_data[stock].last_price < current_data[stock].high_limit:
                close_position(context.portfolio.positions[stock])
        g.today_trade_allowed = False
        g.ban_trade_start_date = current_date
        g.risk_control_executed = True
    else:
        g.today_trade_allowed = True
        if ban_period_ended:
            execute_recovery_buying(context)
            
    g.last_factor_analysis_date = yesterday
    g.factor_threshold_results[yesterday] = {'factors': factor_medians, 'signal': signal}

def execute_recovery_buying(context):
    try:
        daily_my_Trader_1(context)
        current_data = get_current_data()
        available_cash = context.portfolio.available_cash
        pos_count = len(context.portfolio.positions)
        to_buy = min(len(g.sorted_stocks), g.stock_num - pos_count)
        if to_buy <= 0 or available_cash <= 0:
            return
        psize = available_cash / to_buy
        bought = 0
        for stock in g.sorted_stocks:
            if (bought >= to_buy or 
                stock in context.portfolio.positions or
                current_data[stock].last_price >= current_data[stock].high_limit or
                current_data[stock].last_price <= current_data[stock].low_limit or
                current_data[stock].paused):
                continue
            if open_position(stock, psize):
                bought += 1
            if bought >= to_buy:
                break
    except:
        pass

# ==================== 过滤函数 ====================

def filter_kcbj_stock(stock_list):
    return [s for s in stock_list if not (s.startswith(('4', '8', '68')))]

def filter_highprice_stock(context, stock_list):
    # 使用前一日收盘价
    prices = history(1, '1d', 'close', stock_list, df=True)
    if prices.empty:
        return []
    prices = prices.iloc[0]
    return [s for s in stock_list if s in context.portfolio.positions or prices.get(s, np.inf) < g.max_stock_price]

def filter_all_stock(context, stocks):
    curr_data = get_current_data()
    valid = []
    for s in stocks:
        try:
            d = curr_data[s]
            if (not d.paused and not d.is_st and 'ST' not in d.name and '*' not in d.name and '退' not in d.name
                and d.low_limit < d.last_price < d.high_limit):
                valid.append(s)
        except:
            continue
    return valid

def get_dividend_ratio_filter_list(context, stock_list, sort, p1, p2):
    time1 = context.previous_date
    time0 = time1 - relativedelta(years=1)
    
    cap = get_fundamentals(query(valuation.code, valuation.market_cap).filter(valuation.code.in_(stock_list)), date=time1)
    if cap.empty:
        return []
    cap.set_index('code', inplace=True)
    
    df = finance.run_query(query(finance.STK_XR_XD.code, finance.STK_XR_XD.bonus_amount_rmb)
                           .filter(finance.STK_XR_XD.a_registration_date >= time0,
                                   finance.STK_XR_XD.a_registration_date <= time1,
                                   finance.STK_XR_XD.code.in_(stock_list)))
    if df.empty:
        return []
        
    dividend = df.groupby('code')['bonus_amount_rmb'].sum().to_frame()
    DR = dividend.join(cap, how='inner')
    DR['dividend_ratio'] = (DR['bonus_amount_rmb'] / 1e8) / DR['market_cap']
    DR = DR.sort_values(by='dividend_ratio', ascending=sort)
    n = len(DR)
    start, end = int(p1 * n), int(p2 * n)
    return DR.index[start:end].tolist()

def get_peg(context, stocks):
    query_date = context.previous_date
    df = get_fundamentals(
        query(valuation.code)
        .filter(valuation.code.in_(stocks),
                income.np_parent_company_owners > 0,
                income.net_profit > 0,
                income.operating_revenue > 1e8,
                indicator.roe > 0,
                indicator.roa > 0),
        date=query_date
    )
    return list(df.code) if df is not None and not df.empty else []