# Clone from JoinQuant
# postId: 3a5ab0c1319f2c23a37a7f58ed646277
# backtestId: 5304eb76b9c15bceaa6ed19eb059fa4a
# title: 【策略组合】优质小市值周换手与ETF轮动策略组合

"""
双策略融合框架：小市值轮动 + ETF动量轮动
策略1：PB-同比增长为正小市值周轮动策略（带防御月份）
策略2：ETF收益率稳定性轮动策略（带多种技术指标过滤）
"""
import datetime
import math
import prettytable
import numpy as np
import pandas as pd
from datetime import timedelta
from jqdata import *
from jqfactor import *
from prettytable import PrettyTable


""" ====================== 基础配置 ====================== """

def initialize(context):
    """初始化策略."""
    set_backtest()
    set_params(context)
    set_strategy_params(context)
    log.set_level('order', 'error')


def set_params(context):
    """设置基础参数."""
    
    # ========== [配置] 资金分配比例 ==========
    # 格式: [策略1比例, 策略2比例]
    g.portfolio_value_proportion = [0.5, 0.5]  # 默认策略1占60%，策略2占40%
    
    # ========== [配置] 策略1空仓期资金动态分配 ==========
    g.enable_dynamic_proportion = True  # 是否启用动态分配
    #g.dynamic_proportion_base = [0, 1]  # 策略1空仓时，资金全部分配给策略2
    
    # ========== 全局内部状态变量初始化 ==========
    g.starting_cash = context.portfolio.total_value
    g.stock_strategy = {}
    g.strategy_holdings = {1: [], 2: []}
    g.portfolio_value_proportion_original = g.portfolio_value_proportion[:]
    g.strategy1_paused = False
    g.strategy_starting_cash = {
        1: g.starting_cash * g.portfolio_value_proportion[0],
        2: g.starting_cash * g.portfolio_value_proportion[1],
    }
    g.strategy_value_data = {}
    g.strategy_value = {
        1: g.strategy_starting_cash[1],
        2: g.strategy_starting_cash[2],
    }
    
    # 策略1特定变量
    g.high_limit_list = []  # 昨日涨停列表
    g.defensive_months = [1, 4]  # 防御月份
    g.defensive_asset = '518880.XSHG'  # 华安黄金ETF
    g.defensive_mode = 1  # 防御模式：0=空仓，1=买入防御性资产
    
    # 策略2特定变量
    g.position_highs = {}  # 记录持仓期间的最高价
    g.position_stop_prices = {}  # 记录持仓的ATR止损价


def set_strategy_params(context):
    """设置策略参数."""
    
    # ========== [配置] 策略1: 小市值轮动 参数 ==========
    g.stock_num = 10  # 持股数量
    
    # ========== [配置] 策略2: ETF动量轮动 参数 ==========
    # ETF池
    g.etf_pool = [
        #大宗商品ETF
        "518880.XSHG",  # 黄金ETF
        "159980.XSHE",  # 有色ETF（跟踪有色金属板块）
        "159985.XSHE",  # 豆粕ETF（跟踪豆粕期货价格）
        "501018.XSHG",  # 南方原油（投资原油相关资产）
        #国际ETF
        "513100.XSHG",  # 纳指ETF
        "513500.XSHG",  # 标普500ETF
        "513520.XSHG",  # 日经225ETF
        "513030.XSHG",  # 德国30ETF
        "513080.XSHG",  # 法国ETF
        #香港ETF
        "159920.XSHE",  # 恒生ETF
        #中国ETF
        "510300.XSHG",  # 沪深300ETF
        "510500.XSHG",  # 上证500ETF
        "510050.XSHG",  # 上证50ETF
        "510210.XSHG",  # 上证ETF
        "159915.XSHE",  # 创业板ETF
        "588080.XSHG",  # 科创50          
        "159995.XSHE",  # 芯片ETF             
        "513050.XSHG",  # 中概互联网             
        "159852.XSHE",  # 软件 
        "159845.XSHE",  # 华夏中证1000ETF
        "515030.XSHG",  # 华夏国证半导体ETF
        "159806.XSHE",  # 国泰中证新能源汽车ETF
        "516160.XSHG",  # 南方中证新能源ETF
        "159928.XSHE",  # 汇添富中证主要消费ETF
        #防御ETF
        "511010.XSHG",  # 国债ETF
        "511220.XSHG",  # 城投债ETF
    ]
    
    # 防御ETF
    g.defense_security = '511880.XSHG'   # 货币ETF
    
    # 动量参数
    g.lookback_days = 25  # 长期动量计算周期
    g.short_lookback_days = 10  # 短期动量计算周期
    g.min_score_threshold = 0.0  # 最低得分阈值
    g.max_score_threshold = 5.0  # 最高得分阈值
    
    # 技术指标参数
    g.use_rsi_filter = True  # 启用RSI过滤
    g.rsi_period = 6  # RSI计算周期
    g.rsi_lookback_days = 1  # 检查RSI的历史天数
    g.rsi_threshold = 95  # RSI阈值
    
    g.use_atr_stop_loss = True  # 启用ATR动态止损
    g.atr_period = 14  # ATR计算周期
    g.atr_multiplier = 2  # ATR倍数
    g.atr_trailing_stop = False  # 是否使用跟踪止损
    g.atr_exclude_defensive = True  # 防御ETF是否豁免ATR止损
    
    g.stop_loss = 0.95  # 固定止损线
    g.loss = 0.97  # 近3日跌幅止损线


def set_backtest():
    """设置回测参数."""
    set_option('avoid_future_data', True)
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    
    # 滑点设置：固定滑点
    #set_slippage(FixedSlippage(0.002), type="stock")
    #set_slippage(FixedSlippage(0.001), type="fund")
    # 滑点设置：比例滑点
    set_slippage(PriceRelatedSlippage(0.002), type="stock")  # 0.2%的比例滑点
    set_slippage(PriceRelatedSlippage(0.001), type="fund")  # 0.2%的比例滑点
    # 交易成本:默认
    cost_configs_bak = [
        ("stock", 0.0005, 0.85 / 10000, 5),
        ("fund", 0, 0.5 / 10000, 5),
        ("mmf", 0, 0, 0)
    ]
    # 交易成本:或许更贴近实际
    cost_configs = [
        ("stock", 0.001, 2 / 10000, 5),
        ("fund", 0, 1 / 10000, 5),
        ("mmf", 0, 0, 0)
    ]
    for asset_type, close_tax, commission, min_comm in cost_configs:
        set_order_cost(OrderCost(
            open_tax=0, close_tax=close_tax,
            open_commission=commission, close_commission=commission,
            close_today_commission=0, min_commission=min_comm
        ), type=asset_type)


""" ====================== 策略1: 小市值轮动策略 ====================== """

def strategy1_is_defensive_month(context):
    """判断当前是否处于防御月份."""
    current_month = context.current_dt.month
    return current_month in g.defensive_months


def strategy1_get_stock_list(context):
    """策略1选股函数."""
    yesterday = context.previous_date
    
    # 获取全市场股票
    initial_list = get_all_securities().index.tolist()
    
    # 基础过滤
    initial_list = strategy1_filter_new_stock(context, initial_list)
    initial_list = strategy1_filter_kcbj_stock(initial_list)
    initial_list = strategy1_filter_st_stock(initial_list)
    
    # 价格过滤：取价格最低的10%
    df = get_price(initial_list, start_date=yesterday, end_date=yesterday, 
                   fields=['close'], fq='pre', panel=False)
    df = df.sort_values(by='close', ascending=True)
    price_list = list(df.code)[int(0*len(df)):int(0.1*len(df))]
    
    # 基本面筛选
    q = query(valuation.code, valuation.circulating_market_cap, 
              indicator.roe, indicator.gross_profit_margin,
              indicator.inc_total_revenue_year_on_year, 
              indicator.inc_net_profit_annual).filter(
        valuation.pb_ratio > 0,  # 筛选pb大于0的股票
        valuation.code.in_(price_list)
    ).order_by(valuation.circulating_market_cap.asc())
    
    df = get_fundamentals(q, date=yesterday)
    df = df[df['inc_total_revenue_year_on_year'] > 0]  # 总营收同比增长率大于0
    
    final_list = list(df.code)[:15]
    return final_list


def strategy1_prepare(context):
    """策略1准备工作."""
    # 获取已持仓列表
    g.strategy_holdings[1] = []
    for position in list(context.portfolio.positions.values()):
        if g.stock_strategy.get(position.security) == 1:
            g.strategy_holdings[1].append(position.security)
    
    # 获取昨日涨停列表
    if g.strategy_holdings[1]:
        df = get_price(g.strategy_holdings[1], end_date=context.previous_date, 
                      frequency='daily', fields=['close','high_limit'], 
                      count=1, panel=False, fill_paused=False)
        df = df[df['close'] == df['high_limit']]
        g.high_limit_list = list(df.code)
    else:
        g.high_limit_list = []
    
    # 检查是否进入/退出防御月份并调整资金分配
    new_defensive_signal = strategy1_is_defensive_month(context)
    if hasattr(g, 'strategy1_paused'):
        if not g.strategy1_paused and new_defensive_signal:
            # 进入防御月份
            strategy1_adjust_proportion_pause()
        elif g.strategy1_paused and not new_defensive_signal:
            # 退出防御月份
            strategy1_restore_proportion_resume()
    else:
        if new_defensive_signal:
            strategy1_adjust_proportion_pause()
    
    g.strategy1_paused = new_defensive_signal


def strategy1_sell(context):
    """策略1卖出逻辑."""
    if not strategy1_is_defensive_month(context):
        # 非防御月份：正常调仓卖出
        target_list = strategy1_get_stock_list(context)
        target_list = strategy1_filter_paused_stock(target_list)
        target_list = strategy1_filter_limitup_stock(context, target_list)
        target_list = strategy1_filter_limitdown_stock(context, target_list)
        target_list = target_list[:min(g.stock_num, len(target_list))]
        
        # 卖出不在目标列表中的股票
        for stock in g.strategy_holdings[1]:
            if (stock not in target_list) and (stock not in g.high_limit_list):
                close_position(stock)
                log.info(f"策略1 卖出 {format_stock_code(stock)} 原因:不在目标池")
    else:
        # 防御月份：卖出所有股票（保留防御资产）
        for stock in g.strategy_holdings[1]:
            if stock != g.defensive_asset:
                close_position(stock)
                log.info(f"策略1 卖出 {format_stock_code(stock)} 原因:防御月份")


def strategy1_buy(context):
    """策略1买入逻辑."""
    if strategy1_is_defensive_month(context):
        # 防御月份：买入防御性资产
        if g.defensive_mode == 1 and g.defensive_asset:
            # 计算策略1可用资金
            strategy_value = context.portfolio.total_value * g.portfolio_value_proportion[0]
            current_value = sum([pos.value for pos in context.portfolio.positions.values() 
                                if g.stock_strategy.get(pos.security) == 1])
            available_cash = max(0, strategy_value - current_value)
            
            if available_cash > 5000:
                open_position(context, g.defensive_asset, available_cash, 1)
    else:
        # 非防御月份：正常买入股票
        target_list = strategy1_get_stock_list(context)
        target_list = strategy1_filter_paused_stock(target_list)
        target_list = strategy1_filter_limitup_stock(context, target_list)
        target_list = strategy1_filter_limitdown_stock(context, target_list)
        target_list = target_list[:min(g.stock_num, len(target_list))]
        
        # 计算需要买入的股票数量
        position_count = len(g.strategy_holdings[1])
        target_num = len(target_list)
        
        if target_num > position_count:
            # 计算策略1可用资金
            strategy_value = context.portfolio.total_value * g.portfolio_value_proportion[0]
            current_value = sum([pos.value for pos in context.portfolio.positions.values() 
                                if g.stock_strategy.get(pos.security) == 1])
            available_cash = max(0, strategy_value - current_value)
            
            if available_cash > 0:
                value = available_cash / (target_num - position_count)
                bought_num = 0
                
                for stock in target_list:
                    if stock not in g.strategy_holdings[1]:
                        if bought_num < (target_num - position_count):
                            open_position(context, stock, value, 1)
                            bought_num += 1
                            if len(g.strategy_holdings[1]) == target_num:
                                break


def strategy1_check_limit_up(context):
    """检查昨日涨停股今日表现."""
    now_time = context.current_dt
    if g.high_limit_list and not strategy1_is_defensive_month(context):
        for stock in g.high_limit_list:
            if stock in g.strategy_holdings[1]:
                current_data = get_price(stock, end_date=now_time, frequency='1m', 
                                        fields=['close','high_limit'], skip_paused=False, 
                                        fq='pre', count=1, panel=False, fill_paused=True)
                if current_data.iloc[0,0] < current_data.iloc[0,1]:
                    close_position(stock)
                    log.info(f"策略1 卖出 {format_stock_code(stock)} 原因:涨停打开")


""" ====================== 策略1过滤函数 ====================== """

def strategy1_filter_paused_stock(stock_list):
    """过滤停牌股票."""
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]


def strategy1_filter_st_stock(stock_list):
    """过滤ST股票."""
    current_data = get_current_data()
    return [stock for stock in stock_list
            if not current_data[stock].is_st
            and 'ST' not in current_data[stock].name
            and '*' not in current_data[stock].name
            and '退' not in current_data[stock].name]


def strategy1_filter_kcbj_stock(stock_list):
    """过滤科创北交股票."""
    filtered_list = []
    for stock in stock_list:
        if not (stock[0] == '4' or stock[0] == '8' or stock[:2] == '68'):
            filtered_list.append(stock)
    return filtered_list


def strategy1_filter_new_stock(context, stock_list):
    """过滤次新股."""
    yesterday = context.previous_date
    filtered_list = []
    for stock in stock_list:
        try:
            start_date = get_security_info(stock).start_date
            if (yesterday - start_date).days >= 250:
                filtered_list.append(stock)
        except:
            continue
    return filtered_list


def strategy1_filter_limitup_stock(context, stock_list):
    """过滤涨停股票."""
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list 
            if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] < current_data[stock].high_limit]


def strategy1_filter_limitdown_stock(context, stock_list):
    """过滤跌停股票."""
    last_prices = history(1, unit='1m', field='close', security_list=stock_list)
    current_data = get_current_data()
    return [stock for stock in stock_list 
            if stock in context.portfolio.positions.keys()
            or last_prices[stock][-1] > current_data[stock].low_limit]


""" ====================== 策略2: ETF动量轮动策略 ====================== """

def strategy2_calculate_momentum_metrics(etf):
    """计算ETF动量指标."""
    try:
        # 获取历史价格数据
        lookback = max(g.lookback_days, g.short_lookback_days, g.rsi_period) + 20
        prices = attribute_history(etf, lookback, '1d', ['close', 'high'])
        current_data = get_current_data()
        
        if len(prices) < g.lookback_days:
            return None
            
        # 获取当前价格并添加到价格序列
        current_price = current_data[etf].last_price
        price_series = np.append(prices["close"].values, current_price)
        
        # 计算RSI指标
        rsi_filter_pass = True
        current_rsi = 0
        if g.use_rsi_filter and len(price_series) >= g.rsi_period + g.rsi_lookback_days:
            rsi_values = strategy2_calculate_rsi(price_series, g.rsi_period)
            if len(rsi_values) >= g.rsi_lookback_days:
                recent_rsi = rsi_values[-g.rsi_lookback_days:]
                rsi_ever_above_threshold = np.any(recent_rsi > g.rsi_threshold)
                if rsi_ever_above_threshold:
                    rsi_filter_pass = False
                current_rsi = recent_rsi[-1] if len(recent_rsi) > 0 else 0
        
        if not rsi_filter_pass:
            return None
        
        # 计算长期动量得分
        recent_price_series = price_series[-(g.lookback_days + 1):]
        y = np.log(recent_price_series)
        x = np.arange(len(y))
        weights = np.linspace(1, 2, len(y))
        
        # 计算年化收益率
        slope, intercept = np.polyfit(x, y, 1, w=weights)
        annualized_returns = math.exp(slope * 250) - 1
        
        # 计算R²
        ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
        ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot else 0
        
        # 综合得分
        score = annualized_returns * r_squared
        
        # 短期风控：过滤近3日跌幅
        if len(price_series) >= 4:
            day1_ratio = price_series[-1] / price_series[-2]
            day2_ratio = price_series[-2] / price_series[-3]
            day3_ratio = price_series[-3] / price_series[-4]
            if min(day1_ratio, day2_ratio, day3_ratio) < g.loss:
                score = 0
        
        return {
            'etf': etf,
            'annualized_returns': annualized_returns,
            'r_squared': r_squared,
            'score': score,
            'current_price': current_price,
            'current_rsi': current_rsi
        }
    except Exception as e:
        log.warn(f"计算{etf}动量指标时出错: {e}")
        return None


def strategy2_calculate_rsi(prices, period=6):
    """计算RSI指标."""
    if len(prices) < period + 1:
        return []
    
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    
    avg_gains = np.zeros_like(prices)
    avg_losses = np.zeros_like(prices)
    
    avg_gains[period] = np.mean(gains[:period])
    avg_losses[period] = np.mean(losses[:period])
    
    rsi_values = np.zeros(len(prices))
    rsi_values[:period] = 50
    
    for i in range(period + 1, len(prices)):
        avg_gains[i] = (avg_gains[i-1] * (period - 1) + gains[i-1]) / period
        avg_losses[i] = (avg_losses[i-1] * (period - 1) + losses[i-1]) / period
        
        if avg_losses[i] == 0:
            rsi_values[i] = 100
        else:
            rs = avg_gains[i] / avg_losses[i]
            rsi_values[i] = 100 - (100 / (1 + rs))
    
    return rsi_values[period:]


def strategy2_calculate_atr(security, period=14):
    """计算ATR指标."""
    try:
        needed_days = period + 20
        hist_data = attribute_history(security, needed_days, '1d', 
                                     ['high', 'low', 'close'])
        
        if len(hist_data) < period + 1:
            return 0, False
        
        high_prices = hist_data['high'].values
        low_prices = hist_data['low'].values
        close_prices = hist_data['close'].values
        
        tr_values = np.zeros(len(high_prices))
        for i in range(1, len(high_prices)):
            tr1 = high_prices[i] - low_prices[i]
            tr2 = abs(high_prices[i] - close_prices[i-1])
            tr3 = abs(low_prices[i] - close_prices[i-1])
            tr_values[i] = max(tr1, tr2, tr3)
        
        atr_values = np.zeros(len(tr_values))
        for i in range(period, len(tr_values)):
            atr_values[i] = np.mean(tr_values[i-period+1:i+1])
        
        current_atr = atr_values[-1] if len(atr_values) > 0 else 0
        return current_atr, True
    except Exception as e:
        log.warn(f"计算{security} ATR时出错: {e}")
        return 0, False


def strategy2_get_ranked_etfs():
    """获取ETF排名."""
    etf_metrics = []
    for etf in g.etf_pool:
        metrics = strategy2_calculate_momentum_metrics(etf)
        if metrics is not None:
            if 0 < metrics['score'] < g.max_score_threshold:
                etf_metrics.append(metrics)
    
    etf_metrics.sort(key=lambda x: x['score'], reverse=True)
    return etf_metrics


def strategy2_check_atr_stop_loss(context):
    """检查ATR止损."""
    if not g.use_atr_stop_loss:
        return
    
    current_data = get_current_data()
    for security in g.strategy_holdings[2]:
        if security not in context.portfolio.positions:
            continue
            
        position = context.portfolio.positions[security]
        if position.total_amount <= 0:
            continue
        
        # 防御ETF豁免检查
        if g.atr_exclude_defensive and security == g.defense_security:
            continue
        
        try:
            current_price = current_data[security].last_price
            if current_price == 0:
                continue
            
            cost_price = position.avg_cost
            
            # 更新最高价
            if security not in g.position_highs:
                g.position_highs[security] = current_price
            else:
                g.position_highs[security] = max(g.position_highs[security], current_price)
            
            # 计算ATR
            current_atr, success = strategy2_calculate_atr(security, g.atr_period)
            if not success:
                continue
            
            # 计算止损价
            if g.atr_trailing_stop:
                atr_stop_price = g.position_highs[security] - g.atr_multiplier * current_atr
            else:
                atr_stop_price = cost_price - g.atr_multiplier * current_atr
            
            g.position_stop_prices[security] = atr_stop_price
            
            # 检查止损
            if current_price <= atr_stop_price:
                close_position(security)
                if security in g.position_highs:
                    del g.position_highs[security]
                if security in g.position_stop_prices:
                    del g.position_stop_prices[security]
        except Exception as e:
            log.warn(f"检查{security} ATR止损时出错: {e}")


def strategy2_sell(context):
    """策略2卖出逻辑."""
    # 检查固定止损
    for security in g.strategy_holdings[2]:
        if security not in context.portfolio.positions:
            continue
            
        position = context.portfolio.positions[security]
        if position.total_amount > 0:
            current_price = position.price
            cost_price = position.avg_cost
            
            if current_price <= cost_price * g.stop_loss:
                close_position(security)
                log.info(f"策略2 止损 {format_stock_code(security)} 亏损超过{g.stop_loss*100-100:.0f}%")
    
    # 获取ETF排名
    ranked_etfs = strategy2_get_ranked_etfs()
    
    # 确定目标ETF
    target_etf = None
    if ranked_etfs and ranked_etfs[0]['score'] >= g.min_score_threshold:
        target_etf = ranked_etfs[0]['etf']
    else:
        target_etf = '511880.XSHG'  # 防御ETF
    
    target_etfs = [target_etf] if target_etf else []
    
    # 卖出不在目标列表中的ETF
    for security in g.strategy_holdings[2]:
        if security not in target_etfs:
            close_position(security)


def strategy2_buy(context):
    """策略2买入逻辑."""
    # 获取ETF排名
    ranked_etfs = strategy2_get_ranked_etfs()
    
    # 确定目标ETF
    target_etf = None
    if ranked_etfs and ranked_etfs[0]['score'] >= g.min_score_threshold:
        target_etf = ranked_etfs[0]['etf']
        log.info(f"策略2 选择ETF: {format_stock_code(target_etf)} 得分: {ranked_etfs[0]['score']:.4f}")
    else:
        target_etf = '511220.XSHG'  # 防御ETF
        log.info(f"策略2 进入防御模式，选择ETF: {format_stock_code(target_etf)}")
    
    if target_etf:
        # 计算策略2可用资金
        strategy_value = context.portfolio.total_value * g.portfolio_value_proportion[1]
        current_value = sum([pos.value for pos in context.portfolio.positions.values() 
                            if g.stock_strategy.get(pos.security) == 2])
        available_cash = max(0, strategy_value - current_value)
        
        if available_cash > 5000:
            open_position(context, target_etf, available_cash, 2)


""" ====================== 资金动态分配 ====================== """

def strategy1_adjust_proportion_pause():
    """策略1防御月份时将资金分配给策略2."""
    if not g.enable_dynamic_proportion:
        return
    if g.strategy1_paused:
        return

    strategy1_proportion = g.portfolio_value_proportion_original[0]
    if strategy1_proportion == 0:
        return

    # 将策略1的资金全部分配给策略2
    g.portfolio_value_proportion = [0]
    g.portfolio_value_proportion.append(g.portfolio_value_proportion_original[1] + strategy1_proportion)

    g.strategy1_paused = True
    print(f"📊 策略1 进入防御月份 资金重新分配")
    print(f"   原始比例:{' '.join([f'{x:.2%}' for x in g.portfolio_value_proportion_original])}")
    print(f"   调整后比例:{' '.join([f'{x:.2%}' for x in g.portfolio_value_proportion])}")


def strategy1_restore_proportion_resume():
    """策略1退出防御月份时还原资金比例."""
    if not g.enable_dynamic_proportion:
        return
    if not g.strategy1_paused:
        return

    g.portfolio_value_proportion = g.portfolio_value_proportion_original[:]
    g.strategy1_paused = False
    print(f"📊 策略1 退出防御月份 资金比例还原")
    print(f"   当前比例:{' '.join([f'{x:.2%}' for x in g.portfolio_value_proportion])}")


""" ====================== 公共函数 ====================== """

def my_order_target_value(security, value):
    """封装下单函数并打印交易信息."""
    o = order_target_value(security, value)
    if o:
        if o.is_buy:
            if o.price * o.amount > 0:
                print(f"📦 建仓 {format_stock_code(security)} 买价:{o.price:.3f} 买量:{o.amount} 价值:{o.price * o.amount:.2f}")
                return o
        else:
            if o.price * o.amount > 0:
                profit = (o.price - o.avg_cost) * o.amount
                profit_pct = (o.price - o.avg_cost) / o.avg_cost * 100
                profit_icon = "↑" if profit > 0 else "↓"
                print(f"📤 平仓 {format_stock_code(security)} 卖价:{o.price:.3f} 成本:{o.avg_cost:.3f} 卖量:{o.amount} 盈亏:{profit:+.2f} ({profit_pct:+.2f}%) {profit_icon}")
                return o


def open_position(context, security, value, strategy_id):
    """开仓买入并记录策略持仓."""
    if value <= 5000:
        return

    if security in context.portfolio.positions:
        security_value = context.portfolio.positions[security].value
        if abs(value - security_value) < 5000:
            return

    order = my_order_target_value(security, value)
    if order:
        security not in g.strategy_holdings[strategy_id] and g.strategy_holdings[strategy_id].append(security)
        g.stock_strategy[security] = strategy_id
    return order


def close_position(security):
    """平仓卖出并清空策略持仓."""
    order = my_order_target_value(security, 0)
    if order:
        strategy_id = g.stock_strategy[security]
        security in g.strategy_holdings[strategy_id] and g.strategy_holdings[strategy_id].remove(security)
        pnl_value = (order.price - order.avg_cost) * order.amount
        g.strategy_value[strategy_id] += pnl_value
        
        # 清除策略2的止损记录
        if strategy_id == 2:
            if security in g.position_highs:
                del g.position_highs[security]
            if security in g.position_stop_prices:
                del g.position_stop_prices[security]
    return order


def format_stock_code(stock_code):
    """格式化股票代码显示."""
    try:
        stock_info = get_security_info(stock_code)
        if stock_info is None:
            return f"{stock_code[:6]}"
        return f"{stock_code[:6]}({stock_info.display_name})"
    except Exception:
        return f"{stock_code[:6]}"


""" ====================== 定时任务 ====================== """

def after_code_changed(context):
    """配置定时任务."""
    unschedule_all()

    # ========== 策略1定时任务 ==========
    if g.portfolio_value_proportion[0] > 0:
        run_daily(strategy1_prepare, '9:05')                  # 准备工作
        run_weekly(strategy1_sell, 1, '9:30')                 # 每周一卖出
        run_weekly(strategy1_buy, 1, '10:00')                 # 每周一买入
        run_daily(strategy1_check_limit_up, time='14:00')     # 检查涨停打开

    # ========== 策略2定时任务 ==========
    if g.portfolio_value_proportion[1] > 0:
        run_daily(strategy2_sell, '14:20')                    # 卖出
        run_daily(strategy2_buy, '14:21')                     # 买入
        run_daily(strategy2_check_atr_stop_loss, '9:35')      # ATR止损检查

    # ========== 公共定时任务 ==========
    run_daily(make_record, '15:01')
    run_daily(print_summary, '15:02')


def make_record(context):
    """记录各策略每日收益."""
    positions = context.portfolio.positions
    if not positions:
        return

    current_data = get_current_data()

    # 初始化策略价值数据
    g.strategy_value_data = {1: 0, 2: 0}
    copy_strategy_value = {
        1: g.strategy_value[1],
        2: g.strategy_value[2],
    }

    # 计算各策略的盈亏
    for stock, pos in positions.items():
        strategy_id = g.stock_strategy[stock]
        current_value = pos.total_amount * current_data[stock].last_price
        cost_value = pos.total_amount * pos.avg_cost
        pnl_value = current_value - cost_value

        copy_strategy_value[strategy_id] += pnl_value
        g.strategy_value_data[strategy_id] += current_value

    # 计算各策略的基准资金
    base_cash_1 = g.starting_cash * g.portfolio_value_proportion_original[0]
    base_cash_2 = g.starting_cash * g.portfolio_value_proportion_original[1]

    # 记录策略收益率
    if base_cash_1 > 0:
        record(小市值轮动=round(copy_strategy_value[1] / base_cash_1 * 100 - 100, 2))

    if base_cash_2 > 0:
        record(ETF轮动=round(copy_strategy_value[2] / base_cash_2 * 100 - 100, 2))


def print_summary(context):
    """打印当前投资组合的总资产和持仓详情."""
    total_value = round(context.portfolio.total_value, 2)
    current_stocks = context.portfolio.positions

    if not current_stocks:
        print(f"🚤 当前总资产:{total_value} 状态:休息中")
        return

    # 创建持仓表格
    table = PrettyTable([
        "所属策略",
        "股票代码",
        "股票名称",
        "持仓数量",
        "持仓价格",
        "当前价格",
        "盈亏数额",
        "盈亏比例",
        "股票市值",
        "仓位占比"])
    table.hrules = prettytable.ALL

    total_market_value = 0

    for stock in current_stocks:
        current_shares = current_stocks[stock].total_amount
        current_price = round(get_current_data()[stock].last_price, 3)
        avg_cost = round(current_stocks[stock].avg_cost, 3)

        profit_ratio = (current_price - avg_cost) / avg_cost if avg_cost != 0 else 0
        profit_ratio_percent = f"{profit_ratio * 100:.2f}%"
        profit_ratio_percent += f" {'↑' if profit_ratio > 0 else '↓'}"

        profit_amount = round((current_price - avg_cost) * current_shares, 2)
        market_value = round(current_shares * current_price, 2)
        total_market_value += market_value

        stock_code = stock.split(".")[0]

        try:
            stock_info = get_security_info(stock)
            stock_name = stock_info.display_name if stock_info else stock_code
        except Exception:
            stock_name = stock_code

        strategy_names = {1: "小市值轮动", 2: "ETF轮动"}
        table.add_row([
            strategy_names[g.stock_strategy[stock]],
            stock_code,
            stock_name,
            current_shares,
            avg_cost,
            current_price,
            profit_amount,
            profit_ratio_percent,
            market_value,
            f"{market_value / context.portfolio.total_value * 100:.2f}%"
        ])

    total_value = context.portfolio.total_value
    if g.strategy_value_data[1]:
        table.add_row(["小市值轮动", "", "", "", "", "", "", "", f"{g.strategy_value_data[1]:.2f}",
                       f"{g.strategy_value_data[1] / total_value * 100:.2f}%"])
    if g.strategy_value_data[2]:
        table.add_row(["ETF轮动", "", "", "", "", "", "", "", f"{g.strategy_value_data[2]:.2f}",
                       f"{g.strategy_value_data[2] / total_value * 100:.2f}%"])

    table.add_row(["总市值", "", "", "", "", "", "", "", f"{total_market_value:.2f}", ""])
    table.add_row(["总资产", "", "", "", "", "", "", "", f"{total_value:.2f}", ""])

    print(f'当前总资产\n{table}')
# ===== AUTORESEARCH NORMALIZATION OVERRIDE (appended; strategies/ file untouched) =====
# research/harness.md §2 — force zero slippage + frozen commission regardless of
# what the raw strategy sets, even if it re-sets costs every bar.
__jq_set_slippage = set_slippage
def set_slippage(*a, **k):
    __jq_set_slippage(FixedSlippage(0))
__jq_set_commission = set_commission
def set_commission(*a, **k):
    __jq_set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
try:
    __jq_orig_initialize = initialize
    def initialize(context):
        __jq_orig_initialize(context)
        set_option('use_real_price', True)
        set_slippage(FixedSlippage(0))
        set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
except NameError:
    pass
# ===== END OVERRIDE =====
