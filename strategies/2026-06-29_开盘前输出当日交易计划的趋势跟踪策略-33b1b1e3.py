# Clone from JoinQuant
# postId: 33b1b1e340034a24a150c10749260a0e
# backtestId: 35450f326e25f0a5b9fd0ee2dd2306c5
# title: 开盘前输出当日交易计划的趋势跟踪策略

import numpy as np
import pandas as pd
from jqdata import *

def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    log.info('初始化RPS多周期策略（含大盘趋势控制）[效率优化版]')
    
    # 交易成本及滑点
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.00025, close_commission=0.00025, min_commission=5), type='stock')
    
    # 策略参数
    g.N = 20
    g.M = 5
    g.day_rps_low = 85
    g.day_rps_high = 92
    g.week_rps_threshold = 80
    g.month_rps_threshold = 75
    g.sell_rps_high = 96
    g.sell_rps_low = 80
    g.index_code = '000300.XSHG'
    g.ma_period = 20
    
    # 运行时间
    run_daily(pre_trade_report, time='08:00')   # 新增：盘前预览
    run_daily(before_market_open, time='09:00')
    run_daily(market_open, time='09:30')
    
    # 缓存变量
    g.buy_list = []
    g.rps_data = {}
    g.last_calc_date = None
    g.market_trend_bull = False
    
    log.info('策略初始化完成，即将开始每日运行')
def pre_trade_report(context):
    """08:00 运行，输出当日交易计划预览"""
    # 调用统一计算函数（若今日已计算则跳过）
    calculate_signals(context)
    
    current_date = context.current_dt.date()
    log.info('='*50)
    log.info(f'【{current_date} 盘前交易计划预览】')
    log.info(f'大盘状态：{"多头" if g.market_trend_bull else "空头"} (收盘价>MA{g.ma_period})')
    
    stock_pool = getattr(g, 'stock_pool', [])
    log.info(f'有效股票池数量：{len(stock_pool)}')
    
    # 卖出计划
    current_holdings = list(context.portfolio.positions.keys())
    positions_to_sell = []
    day_rps = g.rps_data.get('day', {})
    for stock in current_holdings:
        rps = day_rps.get(stock, 50)
        if rps > g.sell_rps_high:
            positions_to_sell.append(f"{stock}(RPS={rps:.1f}>96)")
        elif rps < g.sell_rps_low:
            positions_to_sell.append(f"{stock}(RPS={rps:.1f}<80)")
    
    if positions_to_sell:
        log.info(f'今日计划卖出：{", ".join(positions_to_sell)}')
    else:
        log.info('今日计划卖出：无')
    
    # 买入计划
    if g.market_trend_bull and g.buy_list:
        buy_candidates = [item for item in g.buy_list if item['stock'] not in current_holdings]
        num_to_buy = g.M - len(current_holdings) + len(positions_to_sell)  # 考虑卖出后释放的仓位
        target_buy = buy_candidates[:num_to_buy]
        if target_buy:
            buy_str = ', '.join([f"{item['stock']}(斜率{item['slope']:.4f}, RPS{item['day_rps']:.1f})" for item in target_buy])
            log.info(f'今日计划买入：{buy_str}')
        else:
            log.info('今日计划买入：无（无符合条件的候选或已达持仓上限）')
    else:
        if not g.market_trend_bull:
            log.info('今日计划买入：无（大盘空头禁止建仓）')
        else:
            log.info('今日计划买入：无（无候选股票）')
    
    log.info('='*50)

def calculate_signals(context):
    """统一的计算函数：大盘趋势、RPS、选股，每日只执行一次"""
    current_date = context.current_dt.date()
    if g.last_calc_date == current_date:
        return
    
    log.info(f'>>> 开始计算信号，日期: {current_date}')
    
    try:
        # 1. 大盘趋势
        g.market_trend_bull = check_market_trend(current_date)
        
        # 2. 股票池
        stock_pool = get_stock_pool(context)
        g.stock_pool = stock_pool  # 保存供报告使用
        if not stock_pool:
            log.warning("股票池为空")
            g.buy_list = []
            g.rps_data = {}
            g.last_calc_date = current_date
            return
        
        # 3. 批量获取价格数据
        total_days_needed = 20 * 22 + 50
        df_close = get_batch_close_prices(stock_pool, current_date, total_days_needed)
        if df_close.empty:
            log.warning("批量价格数据获取失败")
            g.buy_list = []
            g.rps_data = {}
            g.last_calc_date = current_date
            return
        
        # 4. 计算RPS和斜率
        day_rps = calculate_rps_from_df(df_close, '20d')
        week_rps = calculate_rps_from_df(df_close, '20w')
        month_rps = calculate_rps_from_df(df_close, '20m')
        slopes = calculate_slopes_from_df(df_close, g.N)
        
        # 5. 筛选候选
        candidates = []
        for stock in stock_pool:
            if stock in day_rps and stock in week_rps and stock in month_rps and stock in slopes:
                d_rps = day_rps[stock]
                w_rps = week_rps[stock]
                m_rps = month_rps[stock]
                slope = slopes[stock]
                if (g.day_rps_low < d_rps < g.day_rps_high and 
                    w_rps > g.week_rps_threshold and 
                    m_rps > g.month_rps_threshold):
                    candidates.append({
                        'stock': stock,
                        'day_rps': d_rps,
                        'week_rps': w_rps,
                        'month_rps': m_rps,
                        'slope': slope
                    })
        
        candidates.sort(key=lambda x: x['slope'])
        g.buy_list = candidates[:g.M]
        g.rps_data = {'day': day_rps, 'week': week_rps, 'month': month_rps}
        g.last_calc_date = current_date
        
        log.info(f'选股完成，候选池: {len(candidates)}, 可买入: {len(g.buy_list)}')
        for item in g.buy_list[:3]:
            log.info(f"  {item['stock']} - 斜率:{item['slope']:.4f}, 日RPS:{item['day_rps']:.1f}")
            
    except Exception as e:
        log.error(f"信号计算出错: {str(e)}")
        g.buy_list = []
        g.market_trend_bull = False

def before_market_open(context):
    """09:00 运行，仅调用统一计算函数"""
    calculate_signals(context)

def market_open(context):
    """09:30 交易执行"""
    current_data = get_current_data()
    current_date = context.current_dt.date()
    
    # 平仓
    positions_to_sell = []
    day_rps = g.rps_data.get('day', {})
    for position in context.portfolio.positions.values():
        stock = position.security
        rps = day_rps.get(stock, calculate_single_rps(stock, current_date, g.N))
        if rps > g.sell_rps_high or rps < g.sell_rps_low:
            positions_to_sell.append({
                'stock': stock,
                'reason': f'RPS={rps:.1f}({">96" if rps > g.sell_rps_high else "<80"})'
            })
    
    for item in positions_to_sell:
        stock = item['stock']
        if not current_data[stock].paused:
            log.info(f'卖出 {stock}, 原因: {item["reason"]}')
            order_target(stock, 0)
    
    # 开仓
    current_holdings = list(context.portfolio.positions.keys())
    num_holding = len(current_holdings)
    num_to_buy = g.M - num_holding
    
    if not g.market_trend_bull:
        if num_to_buy > 0:
            log.info(f'大盘趋势不满足（收盘价<MA{g.ma_period}），禁止新建仓')
        return
    
    if num_to_buy > 0 and g.buy_list:
        buy_candidates = [item for item in g.buy_list if item['stock'] not in current_holdings]
        target_list = buy_candidates[:num_to_buy]
        if not target_list:
            return
        
        cash_per = context.portfolio.available_cash / len(target_list)
        for item in target_list:
            stock = item['stock']
            if current_data[stock].paused or current_data[stock].is_st:
                continue
            price = current_data[stock].day_open
            if price > 0:
                shares = int(cash_per / price / 100) * 100
                if shares >= 100:
                    log.info(f'买入 {stock}, 数量:{shares}, 斜率:{item["slope"]:.4f}, 日RPS:{item["day_rps"]:.1f}')
                    order(stock, shares)

# ==================== 以下函数保持不变 ====================
def get_batch_close_prices(stock_list, end_date, days_needed):
    batch_size = 100
    all_dfs = []
    for i in range(0, len(stock_list), batch_size):
        batch = stock_list[i:i+batch_size]
        try:
            # 添加 panel=False，返回长格式 DataFrame
            prices = get_price(batch, end_date=end_date, count=days_needed,
                              frequency='1d', fields=['close'], skip_paused=False,
                              panel=False)
            if prices.empty:
                continue
            # pivot 成宽表：行=日期，列=股票代码，值=收盘价
            df_wide = prices.pivot(index='time', columns='code', values='close')
            all_dfs.append(df_wide)
        except Exception as e:
            log.warning(f"批量获取股票价格失败，批次{i}: {str(e)}")
            continue
    
    if not all_dfs:
        return pd.DataFrame()
    
    df_all = pd.concat(all_dfs, axis=1).sort_index()
    return df_all.dropna(axis=1, how='all')

def calculate_rps_from_df(df_close, period):
    if df_close.empty:
        return {}
    if period == '20d':
        ret_df = df_close.pct_change(20).iloc[-1] * 100
    elif period == '20w':
        week_close = df_close.resample('W').last().dropna(how='all')
        if len(week_close) < 20:
            return {}
        ret_df = week_close.pct_change(20).iloc[-1] * 100
    elif period == '20m':
        month_close = df_close.resample('M').last().dropna(how='all')
        if len(month_close) < 20:
            return {}
        ret_df = month_close.pct_change(20).iloc[-1] * 100
    else:
        return {}
    returns = ret_df.dropna()
    if len(returns) == 0:
        return {}
    rank_pct = returns.rank(pct=True) * 100
    return rank_pct.to_dict()

def calculate_slopes_from_df(df_close, N):
    if df_close.empty or len(df_close) < N:
        return {}
    recent = df_close.iloc[-N:]
    slopes = {}
    for stock in recent.columns:
        series = recent[stock].dropna()
        if len(series) < N:
            continue
        try:
            log_prices = np.log(series.values)
            x = np.arange(len(log_prices))
            slope, _ = np.polyfit(x, log_prices, 1)
            slopes[stock] = slope
        except:
            continue
    return slopes

def check_market_trend(end_date):
    try:
        # 添加 panel=False
        prices = get_price(g.index_code, end_date=end_date, count=g.ma_period+5,
                          fields=['close'], skip_paused=True, panel=False)
        if len(prices) < g.ma_period:
            log.warning("大盘数据不足，默认空头")
            return False
        # panel=False 时返回的 DataFrame 只有一列 'close'
        close_series = prices['close']
        ma20 = close_series.rolling(window=g.ma_period).mean().iloc[-1]
        current_close = close_series.iloc[-1]
        log.info(f'大盘{g.index_code}: 收盘价={current_close:.2f}, MA{g.ma_period}={ma20:.2f}')
        return current_close > ma20
    except Exception as e:
        log.error(f"大盘趋势计算错误: {str(e)}")
        return False


def get_stock_pool(context):
    stocks = get_index_stocks('000300.XSHG', context.current_dt)
    current_data = get_current_data()
    filtered = []
    current_date = context.current_dt.date()
    for stock in stocks:
        try:
            info = get_security_info(stock)
            if info is None:
                continue
            listing_days = (current_date - info.start_date).days
            if (not current_data[stock].is_st and 
                not current_data[stock].paused and 
                current_data[stock].day_open > 0 and
                listing_days > 250):
                filtered.append(stock)
        except:
            continue
    return filtered
def calculate_single_rps(stock, end_date, N):
    try:
        # 添加 panel=False
        prices = get_price(stock, end_date=end_date, count=N+10,
                          fields=['close'], skip_paused=True, panel=False)
        if len(prices) < N:
            return 50
        close_series = prices['close']
        current_return = (close_series.iloc[-1] / close_series.iloc[-N] - 1) * 100
        
        index_prices = get_price('000300.XSHG', end_date=end_date, count=N,
                                fields=['close'], panel=False)
        index_close = index_prices['close']
        index_return = (index_close.iloc[-1] / index_close.iloc[0] - 1) * 100
        
        if current_return > index_return:
            return min(85 + (current_return - index_return) * 5, 99)
        else:
            return max(50, 85 - (index_return - current_return) * 5)
    except:
        return 50

def after_trading_end(context):
    record(持仓数量=len(context.portfolio.positions))
    record(总资产=context.portfolio.total_value)
    record(大盘多头=1 if g.market_trend_bull else 0)