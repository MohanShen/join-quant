# Clone from JoinQuant
# postId: 6a0e4b0fc083c6e71b3617dc8a7c1346
# backtestId: 38632f3c925ca54f672964c65a2534d8
# title: 高成长基本面共振策略分享：2026实测收益最高

# 克隆自聚宽文章：https://www.joinquant.com/post/72559
# 标题：收藏的各种好策略，分享
# 作者：灯火辉煌牛气冲天

# -*- coding: utf-8 -*-
"""
高成长基本面共振策略 V1.6.0（攻击增强版 - 止损简化版）
基于原版，简化止损止盈逻辑，降低单日止损阈值至5%左右
"""
# 聚宽买卖信号同步到9db智能体量化策略竞技场 https://www.9db.com
from arena_9db import (
    set_config,
    set_order_reason,
    order_trade as order,
    order_target_trade as order_target,
    order_value_trade as order_value,
    order_target_value_trade as order_target_value
)
# 以下配置为系统自动生成，不能修改
# user_token：用户唯一标识，已由系统自动生成
# tradeorder_id：交割单ID，通过智能体名称自动生成，智能体名称：高成长基本面共振策略 V1.6
set_config(user_token="BE1B0B13-C2B2-4FDF-939A-F3227BC3BC08", tradeorder_id="ed250a61-bc96-4900-acbc-08ad99ceecf3")

from jqdata import *
import numpy as np
import pandas as pd
from datetime import timedelta, datetime

enable_profile()

NEW_QUALITY_KEYWORDS = {
    '半导体': ['半导体', '芯片', '集成电路', '晶圆', '光刻', 'EDA', 'IP核', 'Chiplet'],
    '人工智能': ['AI', '人工智能', '机器学习', '深度学习', '大模型', '算力'],
    '高端制造': ['机器人', '工业母机', '数控机床', '自动化'],
    '生物医药': ['创新药', 'CXO', '医疗器械', '基因', '抗体', '疫苗'],
    '新能源': ['光伏', '储能', '氢能', '锂电', '固态电池'],
    '新材料': ['稀土', '石墨烯', '碳纤维', '光刻胶'],
    '数字经济': ['数据', '数字', '通信', '网络', '物联网', '5G'],
}

CORE_TECH_SECTORS = ['半导体','人工智能','计算机','通信','电子','算力','光模块','软件服务','电力设备']

ALL_SECTORS = {
    '电子': '801080',
    '计算机': '801750',
    '通信': '801760',
    '电力设备': '801730',
    '国防军工': '801740',
    '机械设备': '801890',
    '食品饮料': '801230',
    '医药生物': '801150',
    '非银金融': '801190',
    '银行': '801180',
    '有色金属': '801050',
    '化工': '801030',
    '汽车': '801090',
    '家用电器': '801120',
    '建筑装饰': '801710',
}

TECH_INDEX = '000993.XSHG'

CONFIG = {
    'top_n_stocks': 25,
    'min_market_cap': 15,
    'max_market_cap': 1200,
    'min_pe_ratio': 0,
    'max_pe_ratio': 200,
    'max_peg': 3.5,
    'min_listing_days': 180,
    'min_avg_turnover': 5000,
    
    'min_roe': 0,
    'min_net_profit': 1e7,
    'min_cash_flow_ratio': 0.3,
    'min_revenue_growth': 0.05,
    
    'vol_window': 20,
    'min_atr_ratio': 0.008,
    'max_atr_ratio': 0.15,
    
    'momentum_window': 60,
    'min_momentum_return': 0.08,
    
    'max_position_weight': 0.20,
    'max_industry_weight': 0.38,
    
    # ---------- 简化后的止损止盈参数 ----------
    'stop_loss_atr_multiplier': 2.5,          # 统一ATR止损乘数
    'stop_loss_single_day': -0.05,            # 单日大跌 -5% 止损
    'trailing_stop_pct': 0.05,                # 最高点回撤5%止盈
    
    'target_volatility': 0.18,
    'volatility_adjust_window': 20,
    'volatility_upper_bound': 1.8,
    'volatility_lower_bound': 0.5,
    
    'ema_base_window': 120,
    'ema_min_window': 30,
    'ema_max_window': 250,
    'atr_lookback_days': 60,
    'atr_low_quantile': 0.20,
    'atr_high_quantile': 0.80,
    'atr_extreme_threshold': 3.0,
    'bull_min_weight': 0.90,
    'bear_max_weight': 0.60,
    'sleep_mode_weight': 0.20,
    
    'market_filter_enabled': True,
    'bear_market_max_position': 0.30,
    'bull_market_min_position': 0.90,
    
    'sector_momentum_window': 20,
    'num_top_sectors': 3,
    
    'emergency_buy_threshold': 0.40,
    'emergency_buy_min_stocks': 3,
    
    'momentum_threshold': 0.10,
    'volatility_threshold': 0.02,
}

def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    
    set_order_cost(OrderCost(
        open_tax=0.001, 
        close_tax=0.001,
        open_commission=0.0003, 
        close_commission=0.0003,
        close_today_commission=0,
        min_commission=5
    ), type='stock')
    
    set_slippage(FixedSlippage(0.002))
    
    run_weekly(build_stock_pool, 4, time='9:00')
    run_daily(check_emergency_buy, time='9:15')
    run_daily(rebalance_portfolio, time='9:30')
    run_daily(check_stop_loss, time='14:30')
    run_daily(check_portfolio_drawdown, time='14:45')
    run_daily(record_data, time='15:00')
    
    context.stock_pool = []
    context.position_cost = {}        # 不再使用，改为直接读取 avg_cost
    context.highest_prices = {}
    context.position_dates = {}
    context.last_rebalance = None
    context.stock_industry_map = {}
    context.stock_fundamentals = {}
    context._market_ratio_cache = (None, 1.0)
    context._market_regime_cache = (None, "SAFE")
    context.risk_adjust_ratio = 1.0
    context.current_top_sectors = []
    
    log.info("高成长基本面共振策略 V1.6.0（攻击增强版 - 止损简化）初始化完成")

def check_market_environment(context):
    if not CONFIG['market_filter_enabled']:
        return 1.0
    
    try:
        current_date = context.current_dt.date()
        
        df_hs300 = get_price('000300.XSHG', count=250,
                             end_date=current_date - timedelta(days=1),
                             frequency='daily', fields=['close'], panel=False)
        
        df_tech = get_price(TECH_INDEX, count=250,
                            end_date=current_date - timedelta(days=1),
                            frequency='daily', fields=['close'], panel=False)
        
        if df_hs300 is None or len(df_hs300) < 200 or df_tech is None or len(df_tech) < 200:
            return 1.0
        
        hs300_price = df_hs300['close'].iloc[-1]
        hs300_ma = df_hs300['close'].mean()
        hs300_status = 1.0 if hs300_price >= hs300_ma else 0.6
        
        tech_price = df_tech['close'].iloc[-1]
        tech_ma = df_tech['close'].mean()
        tech_status = 1.0 if tech_price >= tech_ma else 0.8
        
        final_ratio = tech_status * 0.6 + hs300_status * 0.4
        final_ratio = min(1.0, max(0.3, final_ratio))
        
        log.info(f"【双基准择时】沪深300={hs300_status:.0%}, 科技指数={tech_status:.0%}, 最终仓位={final_ratio:.0%}")
        return final_ratio
        
    except Exception as e:
        log.error(f"检查大盘环境失败: {e}")
        return 1.0

def get_sector_momentum(context):
    try:
        current_date = context.current_dt.date()
        sector_returns = {}
        
        for sector_name, sector_code in ALL_SECTORS.items():
            try:
                df = get_price(sector_code + '.CSI', count=CONFIG['sector_momentum_window'],
                              end_date=current_date - timedelta(days=1),
                              frequency='daily', fields=['close'], panel=False)
                if df is not None and len(df) >= CONFIG['sector_momentum_window']:
                    momentum = (df['close'].iloc[-1] - df['close'].iloc[0]) / df['close'].iloc[0]
                    sector_returns[sector_name] = momentum
            except:
                continue
        
        sorted_sectors = sorted(sector_returns.items(), key=lambda x: x[1], reverse=True)
        top_sectors = [sector[0] for sector in sorted_sectors[:CONFIG['num_top_sectors']]]
        
        log.info(f"【行业动量】当前最强行业: {top_sectors}")
        return top_sectors
    except Exception as e:
        log.error(f"计算行业动量失败: {e}")
        return CORE_TECH_SECTORS

def calculate_atr_index(context):
    current_date = context.current_dt.date()
    
    df_tech = get_price(TECH_INDEX, count=CONFIG['atr_lookback_days'] + 20,
                        end_date=current_date - timedelta(days=1), frequency='daily',
                        fields=['high', 'low', 'close'], panel=False)
    
    if df_tech is None or len(df_tech) < 20:
        df_tech = get_price('000300.XSHG', count=CONFIG['atr_lookback_days'] + 20,
                           end_date=current_date - timedelta(days=1), frequency='daily',
                           fields=['high', 'low', 'close'], panel=False)
    
    if df_tech is None or len(df_tech) < 20:
        return 0.02, np.array([0.02])
    
    df = df_tech.copy()
    df['tr'] = np.max([
        df['high'] - df['low'],
        np.abs(df['high'] - df['close'].shift(1)),
        np.abs(df['low'] - df['close'].shift(1))
    ], axis=0)
    df['atr'] = df['tr'].rolling(14).mean()
    df['atr_ratio'] = df['atr'] / df['close']
    
    recent_atr_ratio = df['atr_ratio'].iloc[-1]
    
    historical_atr = df['atr_ratio'].values
    valid_mask = ~np.isnan(historical_atr) & ~np.isinf(historical_atr)
    historical_atr = historical_atr[valid_mask]
    historical_atr = historical_atr[historical_atr > 0]
    
    if len(historical_atr) == 0:
        historical_atr = np.array([0.02])
    
    if np.isnan(recent_atr_ratio) or np.isinf(recent_atr_ratio) or recent_atr_ratio <= 0:
        recent_atr_ratio = 0.02
    
    return recent_atr_ratio, historical_atr

def calculate_adaptive_ema(recent_atr_ratio, historical_atr, context):
    current_date = context.current_dt.date()
    
    if len(historical_atr) < 20:
        ema_window = CONFIG['ema_base_window']
    else:
        atr_mean = np.mean(historical_atr)
        volatility_factor = min(3.0, max(0.3, recent_atr_ratio / (atr_mean + 1e-6)))
        ema_window = int(CONFIG['ema_base_window'] / volatility_factor)
        ema_window = max(CONFIG['ema_min_window'], min(CONFIG['ema_max_window'], ema_window))
    
    df_tech = get_price(TECH_INDEX, count=ema_window + 20,
                        end_date=current_date - timedelta(days=1), frequency='daily',
                        fields=['close'], panel=False)
    
    if df_tech is None or len(df_tech) < ema_window:
        df_tech = get_price('000300.XSHG', count=ema_window + 20,
                            end_date=current_date - timedelta(days=1), frequency='daily',
                            fields=['close'], panel=False)
    
    if df_tech is None or len(df_tech) < ema_window:
        return 0, 0, 0
    
    df = df_tech.copy()
    df['ema'] = df['close'].ewm(span=ema_window, adjust=False).mean()
    current_price = df['close'].iloc[-1]
    current_ema = df['ema'].iloc[-1]
    
    if len(df) >= ema_window + 5:
        ema_slope = (current_ema - df['ema'].iloc[-6]) / df['ema'].iloc[-6]
    else:
        ema_slope = 0
    
    return current_price, current_ema, ema_slope

def get_market_position_ratio(context):
    """三层仓位控制（带EMA乘数化）"""
    current_date = context.current_dt.date()
    if context._market_ratio_cache[0] == current_date:
        return context._market_ratio_cache[1]
    
    recent_atr_ratio, historical_atr = calculate_atr_index(context)
    current_price, current_ema, ema_slope = calculate_adaptive_ema(recent_atr_ratio, historical_atr, context)
    
    atr_low_threshold = np.percentile(historical_atr, CONFIG['atr_low_quantile'] * 100) if len(historical_atr) > 0 else 0.01
    atr_high_threshold = np.percentile(historical_atr, CONFIG['atr_high_quantile'] * 100) if len(historical_atr) > 0 else 0.05
    
    atr_mean = np.mean(historical_atr) if len(historical_atr) > 0 else 0.02
    is_atr_extreme = recent_atr_ratio > atr_mean * CONFIG['atr_extreme_threshold']
    
    price_above_ema = current_price > current_ema and current_ema > 0
    ema_slope_positive = ema_slope > 0.001
    
    is_low_volatility = recent_atr_ratio < atr_low_threshold
    is_high_volatility = recent_atr_ratio > atr_high_threshold
    
    trend_bullish = price_above_ema and ema_slope_positive
    
    if is_atr_extreme:
        base_ratio = CONFIG['sleep_mode_weight']
        log.info(f"【风控模式】ATR异常暴涨({recent_atr_ratio:.4f})，仓位上限{base_ratio:.0%}")
    elif is_low_volatility:
        base_ratio = CONFIG['sleep_mode_weight']
        log.info(f"【休眠模式】ATR低位({recent_atr_ratio:.4f})，仓位上限{base_ratio:.0%}")
    elif is_high_volatility and ema_slope_positive:
        base_ratio = CONFIG['bull_min_weight']
        log.info(f"【战斗模式】高波动上行，ATR={recent_atr_ratio:.4f}，EMA斜率{ema_slope:.2%}，仓位{base_ratio:.0%}")
    elif trend_bullish:
        base_ratio = CONFIG['bull_min_weight']
        log.info(f"【牛市】趋势向好，仓位{base_ratio:.0%}")
    else:
        base_ratio = (CONFIG['bull_min_weight'] + CONFIG['bear_max_weight']) / 2
        log.info(f"【中性】无明确信号，仓位{base_ratio:.0%}")
    
    trend_factor = _calculate_trend_factor(price_above_ema, ema_slope)
    adjusted_ratio = base_ratio * trend_factor
    
    market_env_ratio = check_market_environment(context)
    final_ratio = min(adjusted_ratio, market_env_ratio) if market_env_ratio < adjusted_ratio else max(adjusted_ratio, market_env_ratio)
    final_ratio = max(CONFIG['bear_market_max_position'], min(CONFIG['bull_market_min_position'], final_ratio))
    
    context._market_ratio_cache = (current_date, final_ratio)
    return final_ratio

def _calculate_trend_factor(price_above_ema, ema_slope):
    """计算趋势强度系数（0.5~1.0）"""
    if price_above_ema and ema_slope > 0.001:
        return 1.0
    elif price_above_ema and 0 < ema_slope <= 0.001:
        return 0.9
    elif price_above_ema and ema_slope <= 0:
        return 0.8
    elif not price_above_ema and ema_slope > 0.001:
        return 0.6
    elif not price_above_ema and 0 < ema_slope <= 0.001:
        return 0.55
    else:
        return 0.5

def get_market_regime(context):
    """判定市场状态（疯牛/安全）"""
    current_date = context.current_dt.date()
    
    if context._market_regime_cache[0] == current_date:
        return context._market_regime_cache[1]
    
    try:
        df_tech = get_price(TECH_INDEX, count=60,
                           end_date=current_date - timedelta(days=1),
                           fields=['close', 'high', 'low'], panel=False)
        
        if df_tech is None or len(df_tech) < 20:
            df_tech = get_price('000300.XSHG', count=60,
                               end_date=current_date - timedelta(days=1),
                               fields=['close', 'high', 'low'], panel=False)
        
        if df_tech is None or len(df_tech) < 20:
            context._market_regime_cache = (current_date, "SAFE")
            return "SAFE"
        
        df = df_tech.copy()
        price_momentum = (df['close'].iloc[-1] / df['close'].iloc[-20]) - 1
        
        df['tr'] = np.max([
            df['high'] - df['low'],
            np.abs(df['high'] - df['close'].shift(1)),
            np.abs(df['low'] - df['close'].shift(1))
        ], axis=0)
        volatility = df['tr'][-20:].mean() / df['close'][-20:].mean()
        
        if price_momentum > CONFIG['momentum_threshold'] and volatility > CONFIG['volatility_threshold']:
            log.info(f"【市场状态】疯牛模式：20日涨幅{price_momentum:.1%} | 波动率{volatility:.1%}")
            context._market_regime_cache = (current_date, "BULL")
            return "BULL"
        else:
            log.info(f"【市场状态】安全模式：20日涨幅{price_momentum:.1%} | 波动率{volatility:.1%}")
            context._market_regime_cache = (current_date, "SAFE")
            return "SAFE"
    except Exception as e:
        log.error(f"获取市场状态失败: {e}")
        context._market_regime_cache = (current_date, "SAFE")
        return "SAFE"

def get_dynamic_weights(context):
    """获取动态权重配置"""
    regime = get_market_regime(context)
    if regime == "BULL":
        return {
            'vol_weight': 0.10,
            'momentum_weight': 0.40,
            'quality_weight': 0.15,
            'match_weight': 0.35,
        }
    else:
        return {
            'vol_weight': 0.20,
            'momentum_weight': 0.25,
            'quality_weight': 0.40,
            'match_weight': 0.15,
        }

def get_fundamentals_criteria(context):
    """获取动态基本面筛选标准（V1.3.5优化：软调节）"""
    regime = get_market_regime(context)
    if regime == "BULL":
        return {
            'min_roe': -10.0,
            'min_cash_flow_ratio': -1.0,
            'min_revenue_growth': 0,
            'max_peg': 10.0,
            'min_net_profit': 1e6,
        }
    else:
        return {
            'min_roe': 5.0,
            'min_cash_flow_ratio': 0.3,
            'min_revenue_growth': 0.05,
            'max_peg': 5.0,
            'min_net_profit': 1e7,
        }

def calculate_portfolio_volatility(context):
    current_date = context.current_dt.date()
    
    df_tech = get_price(TECH_INDEX, count=CONFIG['volatility_adjust_window'] + 1,
                        end_date=current_date - timedelta(days=1), frequency='daily',
                        fields=['close'], panel=False)
    
    if df_tech is None or len(df_tech) < CONFIG['volatility_adjust_window']:
        df_tech = get_price('000300.XSHG', count=CONFIG['volatility_adjust_window'] + 1,
                           end_date=current_date - timedelta(days=1), frequency='daily',
                           fields=['close'], panel=False)
    
    if df_tech is None or len(df_tech) < CONFIG['volatility_adjust_window']:
        return CONFIG['target_volatility']
    
    daily_returns = df_tech['close'].pct_change().dropna()
    daily_volatility = daily_returns.std()
    return daily_volatility * np.sqrt(252)

def check_portfolio_drawdown(context):
    current_volatility = calculate_portfolio_volatility(context)
    target_vol = CONFIG['target_volatility']
    volatility_ratio = current_volatility / target_vol
    
    if volatility_ratio > CONFIG['volatility_upper_bound']:
        new_ratio = max(CONFIG['volatility_lower_bound'], 1.0 / volatility_ratio)
    elif volatility_ratio < CONFIG['volatility_lower_bound']:
        new_ratio = min(1.0, volatility_ratio / CONFIG['volatility_lower_bound'])
    else:
        new_ratio = 1.0
    
    new_ratio = max(0.3, min(1.0, new_ratio))
    
    if abs(new_ratio - context.risk_adjust_ratio) > 0.05:
        log.info(f"【波动率目标管理】当前波动率{current_volatility:.2%}, 目标{target_vol:.2%}, 风险系数 {context.risk_adjust_ratio:.2f} → {new_ratio:.2f}")
        context.risk_adjust_ratio = new_ratio

def calculate_quality_score(fund, criteria):
    score = 0
    roe = fund.get('roe', 0)
    score += max(0, min(roe / 10 * 20, 20))
    profit_growth = max(0, fund.get('net_profit_growth', 0))
    score += min(profit_growth * 30, 30)
    cf_ratio = fund.get('cf_ratio', 0)
    if cf_ratio > 0:
        score += min(cf_ratio * 20, 20)
    peg = fund.get('peg', 2.0)
    score += max(0, (1 - min(peg / criteria['max_peg'], 2.0)) * 30)
    return min(score, 100)

def calculate_match_score(stock_name, industry_name):
    score = 0
    core_sectors = {
        '电子': 60, '计算机': 60, '通信': 50,
        '电力设备': 50, '国防军工': 45, '机械设备': 40,
        '食品饮料': 55, '医药生物': 55, '汽车': 50,
        '有色金属': 45, '化工': 40,
    }
    if industry_name in core_sectors:
        score += core_sectors[industry_name]
    
    if stock_name:
        all_keywords = [kw for sublist in NEW_QUALITY_KEYWORDS.values() for kw in sublist]
        score += min(sum(1 for kw in all_keywords if kw in str(stock_name)) * 8, 40)
    
    return min(score, 100) if score >= 50 else 0

def calculate_atr(df):
    try:
        df = df.tail(CONFIG['vol_window']).copy()
        df['tr'] = np.max([
            df['high'] - df['low'],
            np.abs(df['high'] - df['close'].shift(1)),
            np.abs(df['low'] - df['close'].shift(1))
        ], axis=0)
        return df['tr'].mean()
    except:
        return None

def check_trend_confirmation(df, regime):
    if len(df) < 60:
        return regime == "BULL"
    ma20 = df['close'].iloc[-20:].mean()
    ma60 = df['close'].iloc[-60:].mean()
    return ma20 > ma60

def check_liquidity_filter(stock, context):
    try:
        current_date = context.current_dt.date()
        df = get_price(stock, start_date=current_date - timedelta(days=20),
                       end_date=current_date - timedelta(days=1),
                       frequency='daily', fields=['money'], panel=False)
        if df is None or len(df) < 10:
            return False
        avg_turnover = df['money'].mean()
        return not pd.isna(avg_turnover) and avg_turnover >= CONFIG['min_avg_turnover']
    except:
        return False

def build_stock_pool(context):
    current_date = context.current_dt.date()
    prev_date = current_date - timedelta(days=1)
    
    regime = get_market_regime(context)
    dynamic_weights = get_dynamic_weights(context)
    criteria = get_fundamentals_criteria(context)
    
    context.current_top_sectors = get_sector_momentum(context)
    
    log.info(f"{'='*60}")
    log.info(f"开始构建股票池: {current_date} | 模式: {regime}")
    log.info(f"当前最强行业: {context.current_top_sectors}")
    log.info(f"动态权重: 波动率{dynamic_weights['vol_weight']:.0%} | 动量{dynamic_weights['momentum_weight']:.0%} | 基本面{dynamic_weights['quality_weight']:.0%} | 匹配{dynamic_weights['match_weight']:.0%}")
    
    target_sectors = set(CORE_TECH_SECTORS)
    target_sectors.update(context.current_top_sectors)
    
    target_stocks = set()
    for sector_name in target_sectors:
        if sector_name in ALL_SECTORS:
            try:
                stocks = get_industry_stocks(ALL_SECTORS[sector_name])
                if stocks:
                    target_stocks.update(stocks)
                    for stock in stocks:
                        context.stock_industry_map[stock] = sector_name
            except:
                continue
    
    log.info(f"目标行业股票总数: {len(target_stocks)}只")
    if not target_stocks:
        return
    
    try:
        q = query(
            valuation.code,
            valuation.market_cap,
            valuation.pe_ratio,
            indicator.roe,
            indicator.inc_net_profit_year_on_year,
            indicator.inc_total_revenue_year_on_year,
            income.net_profit,
            cash_flow.net_operate_cash_flow,
        ).filter(
            valuation.code.in_(list(target_stocks)),
            valuation.market_cap >= CONFIG['min_market_cap'],
            valuation.market_cap <= CONFIG['max_market_cap'],
            valuation.pe_ratio <= CONFIG['max_pe_ratio'],
        )
        fundamentals = get_fundamentals(q, date=prev_date)
        log.info(f"财务数据加载: {len(fundamentals)}条")
        
        context.stock_fundamentals = {}
        high_confidence_stocks = []
        low_confidence_stocks = []
        
        for _, row in fundamentals.iterrows():
            try:
                pe = row['pe_ratio']
                if pe <= 0 or pe > CONFIG['max_pe_ratio']:
                    continue
                net_profit = row['net_profit']
                if net_profit < criteria['min_net_profit']:
                    continue
                cf_ratio = row['net_operate_cash_flow'] / net_profit if net_profit > 0 else 0
                profit_growth = row.get('inc_net_profit_year_on_year', 0) / 100.0
                if profit_growth < 0.0001:
                    profit_growth = 0.0001
                peg = pe / (profit_growth * 100) if profit_growth > 0 else 999
                
                roe = row.get('roe', 0)
                if roe < criteria['min_roe']:
                    continue
                if cf_ratio < criteria['min_cash_flow_ratio']:
                    continue
                
                revenue_growth = row.get('inc_total_revenue_year_on_year', -100) / 100.0
                if revenue_growth < criteria['min_revenue_growth']:
                    continue
                
                if peg <= 0 or peg > criteria['max_peg']:
                    continue
                
                stock_info = {
                    'market_cap': row['market_cap'],
                    'pe_ratio': pe,
                    'roe': roe,
                    'net_profit': net_profit,
                    'cf_ratio': cf_ratio,
                    'net_profit_growth': profit_growth,
                    'peg': peg,
                    'confidence': 'high',
                }
                
                context.stock_fundamentals[row['code']] = stock_info
                high_confidence_stocks.append(row['code'])
            except:
                continue
        
        log.info(f"高置信度股票(已公告): {len(high_confidence_stocks)}只")
        
        if len(high_confidence_stocks) < 10:
            log.warning(f"【增强兜底】高置信度股票仅{len(high_confidence_stocks)}只 < 10只，放宽至近4个月数据")
            fallback_date = prev_date - timedelta(days=120)
            
            q_fallback = query(
                valuation.code,
                valuation.market_cap,
                valuation.pe_ratio,
                indicator.roe,
                indicator.inc_net_profit_year_on_year,
                indicator.inc_total_revenue_year_on_year,
                income.net_profit,
                cash_flow.net_operate_cash_flow,
            ).filter(
                valuation.code.in_(list(target_stocks)),
                valuation.market_cap >= CONFIG['min_market_cap'] * 0.5,
                valuation.market_cap <= CONFIG['max_market_cap'] * 1.5,
                valuation.pe_ratio <= CONFIG['max_pe_ratio'] * 1.5,
            )
            
            try:
                fundamentals_fallback = get_fundamentals(q_fallback, date=prev_date)
                
                for _, row in fundamentals_fallback.iterrows():
                    if row['code'] in high_confidence_stocks:
                        continue
                    
                    try:
                        pe = row['pe_ratio']
                        if pe <= 0 or pe > CONFIG['max_pe_ratio'] * 1.5:
                            continue
                        net_profit = row['net_profit']
                        if net_profit < criteria['min_net_profit'] * 0.3:
                            continue
                        cf_ratio = row.get('net_operate_cash_flow', 0) / net_profit if net_profit > 0 else 0
                        profit_growth = row.get('inc_net_profit_year_on_year', 0) / 100.0
                        if profit_growth < -0.5:
                            continue
                        if profit_growth < 0.0001:
                            profit_growth = 0.0001
                        peg = pe / (profit_growth * 100) if profit_growth > 0 else 999
                        
                        roe = row.get('roe', -10)
                        if roe < -10:
                            continue
                        
                        if peg <= 0 or peg > criteria['max_peg'] * 2:
                            continue
                        
                        stock_info = {
                            'market_cap': row['market_cap'],
                            'pe_ratio': pe,
                            'roe': roe,
                            'net_profit': net_profit,
                            'cf_ratio': cf_ratio,
                            'net_profit_growth': profit_growth,
                            'peg': peg,
                            'confidence': 'low',
                        }
                        
                        context.stock_fundamentals[row['code']] = stock_info
                        low_confidence_stocks.append(row['code'])
                    except:
                        continue
                
                log.info(f"【增强兜底】新增低置信度股票(近4个月): {len(low_confidence_stocks)}只")
            except Exception as e:
                log.error(f"【增强兜底】放宽查询失败: {e}")
        
        log.info(f"基本面过滤后(高置信{len(high_confidence_stocks)}只+低置信{len(low_confidence_stocks)}只): {len(context.stock_fundamentals)}只")
        if not context.stock_fundamentals:
            return
    except Exception as e:
        log.error(f"基本面过滤失败: {e}")
        return
    
    filtered_stocks = list(context.stock_fundamentals.keys())
    required_count = CONFIG['vol_window'] + CONFIG['momentum_window'] + 60
    candidates = []
    batch_size = 500
    
    log.info(f"开始价格数据获取和筛选...")
    for i in range(0, len(filtered_stocks), batch_size):
        batch = filtered_stocks[i:i+batch_size]
        try:
            df = get_price(batch, count=required_count, end_date=prev_date,
                          frequency='daily', fields=['close', 'high', 'low', 'volume'], panel=False)
            if df is None or df.empty:
                continue
            stock_groups = df.groupby('code')
            for stock, group in stock_groups:
                try:
                    info = get_security_info(stock)
                    if not info:
                        continue
                    if info.display_name and ('ST' in info.display_name or '退' in info.display_name):
                        continue
                    if (current_date - info.start_date).days < CONFIG['min_listing_days']:
                        continue
                    industry_name = context.stock_industry_map.get(stock, '')
                    match_score = calculate_match_score(info.display_name, industry_name)
                    if match_score == 0:
                        continue
                    
                    is_core_sector = industry_name in CORE_TECH_SECTORS
                    is_top_sector = industry_name in context.current_top_sectors
                    if not is_core_sector and not is_top_sector:
                        continue
                    
                    group = group.set_index('time')
                    if len(group) < 60:
                        continue
                    
                    if not check_trend_confirmation(group, regime):
                        continue
                    
                    atr = calculate_atr(group)
                    if atr is None:
                        continue
                    atr_ratio = atr / group['close'].iloc[-1]
                    
                    min_atr = CONFIG['min_atr_ratio']
                    max_atr = CONFIG['max_atr_ratio']
                    if regime == "SAFE":
                        min_atr = CONFIG['min_atr_ratio'] * 1.2
                        max_atr = CONFIG['max_atr_ratio'] * 0.8
                    if atr_ratio < min_atr or atr_ratio > max_atr:
                        continue
                    
                    momentum = (group['close'].iloc[-1] - group['close'].iloc[-CONFIG['momentum_window']]) / group['close'].iloc[-CONFIG['momentum_window']]
                    
                    min_momentum = CONFIG['min_momentum_return']
                    if regime == "SAFE":
                        min_momentum = CONFIG['min_momentum_return'] * 0.6
                    if momentum < min_momentum:
                        continue
                    
                    if not check_liquidity_filter(stock, context):
                        continue
                    
                    fund = context.stock_fundamentals[stock]
                    quality_score = calculate_quality_score(fund, criteria)
                    
                    stock_confidence = fund.get('confidence', 'high')
                    confidence_weight = 0.5 if stock_confidence == 'low' else 1.0
                    
                    vol_factor = min(3.0, 1.0 / (atr_ratio / min_atr)) * dynamic_weights['vol_weight'] * 100 * confidence_weight
                    momentum_factor = min(3.0, momentum / min_momentum) * dynamic_weights['momentum_weight'] * 100 * confidence_weight
                    quality_factor = (quality_score / 100) * dynamic_weights['quality_weight'] * 100 * confidence_weight
                    match_factor = (match_score / 100) * dynamic_weights['match_weight'] * 100 * confidence_weight
                    
                    sector_bonus = 20 if is_top_sector else 0
                    total_score = vol_factor + momentum_factor + quality_factor + match_factor + sector_bonus
                    
                    if not np.isnan(total_score) and not np.isinf(total_score):
                        candidates.append({
                            'code': stock,
                            'name': info.display_name,
                            'score': total_score,
                            'vol': atr_ratio,
                            'momentum': momentum,
                            'quality': quality_score,
                            'match': match_score,
                            'industry': industry_name,
                            'is_top_sector': is_top_sector,
                            'atr_value': atr,
                            'confidence': stock_confidence,
                        })
                except:
                    continue
        except:
            continue
    
    candidates.sort(key=lambda x: x['score'], reverse=True)
    context.stock_pool = candidates[:30]
    log.info(f"最终股票池: {len(context.stock_pool)}只")
    high_conf_count = sum(1 for s in context.stock_pool if s.get('confidence') == 'high')
    low_conf_count = len(context.stock_pool) - high_conf_count
    log.info(f"  - 高置信度(已公告): {high_conf_count}只")
    log.info(f"  - 低置信度(近4个月): {low_conf_count}只")
    for i, stock in enumerate(context.stock_pool[:5], 1):
        conf_tag = "✓" if stock.get('confidence') == 'high' else "⚠"
        log.info(f"  {i}. {stock['code']}({stock['name']}) 评分:{stock['score']:.2f} 行业:{stock['industry']} {conf_tag}")

def apply_industry_constraint(stock_list, context):
    if not stock_list:
        return []
    industry_count = {}
    filtered = []
    max_per_ind = max(1, int(len(stock_list) * CONFIG['max_industry_weight']))
    for stock in stock_list:
        ind = context.stock_industry_map.get(stock, '其他')
        if industry_count.get(ind, 0) < max_per_ind:
            filtered.append(stock)
            industry_count[ind] = industry_count.get(ind, 0) + 1
    return filtered

def emergency_buy(context):
    """防踏空机制（V1.3.5优化：使用科创50ETF）"""
    current_position = context.portfolio.positions_value / context.portfolio.total_value
    
    if current_position >= CONFIG['emergency_buy_threshold'] - 0.05:
        return
    
    log.warning(f"【防踏空机制】当前仓位{current_position:.1%} < {CONFIG['emergency_buy_threshold'] - 0.05:.0%}，触发科创50ETF买入")
    
    current_data = get_current_data()
    etf_codes = ['588000.XSHG', '588080.XSHG', '159915.XSHE']
    etf_code = None
    
    for code in etf_codes:
        if code in current_data and not current_data[code].paused:
            last_price = current_data[code].last_price
            if last_price not in [current_data[code].high_limit, current_data[code].low_limit]:
                etf_code = code
                break
    
    if etf_code is None:
        log.warning(f"所有ETF都不可用，回退到沪深300ETF")
        etf_code = '510300.XSHG'
        if etf_code not in current_data or current_data[etf_code].paused:
            return
    
    for stock in list(context.portfolio.positions.keys()):
        if not stock.startswith(('510300', '159915', '588000', '588080')):
            order_target(stock, 0)
    
    target_value = context.portfolio.total_value * CONFIG['emergency_buy_threshold']
    order_target_value(etf_code, target_value)
    log.info(f"【防踏空机制】买入{etf_code}至{CONFIG['emergency_buy_threshold']:.0%}仓位")

def check_emergency_buy(context):
    if not context.stock_pool or len(context.stock_pool) < CONFIG['emergency_buy_min_stocks']:
        emergency_buy(context)

def calculate_risk_parity_weights(stocks_info):
    atr_values = {si['code']: si.get('atr_value', 0.03) for si in stocks_info}
    inv_atr_sum = sum(1.0 / (atr + 1e-6) for atr in atr_values.values())
    
    weights = {}
    for si in stocks_info:
        atr = atr_values[si['code']]
        base_weight = 1.0 / (atr + 1e-6) / inv_atr_sum
        
        stock_confidence = si.get('confidence', 'high')
        max_weight = 0.05 if stock_confidence == 'low' else CONFIG['max_position_weight']
        
        weights[si['code']] = min(base_weight, max_weight)
    
    total_weight = sum(list(weights.values()))
    if total_weight > 0:
        weights = {k: v / total_weight for k, v in weights.items()}
    
    return weights

def rebalance_portfolio(context):
    if not context.stock_pool:
        log.warning("股票池为空")
        return
    
    current_date = context.current_dt.date()
    if context.current_dt.weekday() != 4:
        return
    week = (current_date.day - 1) // 7 + 1
    if week not in [2, 4]:
        return
    if context.last_rebalance and (current_date - context.last_rebalance).days < 10:
        return
    
    candidate_stocks = [s['code'] for s in context.stock_pool[:CONFIG['top_n_stocks']]]
    
    if len(candidate_stocks) < CONFIG['emergency_buy_min_stocks']:
        log.warning(f"【防踏空预警】候选股票仅{len(candidate_stocks)}只 < {CONFIG['emergency_buy_min_stocks']}只")
        if len(candidate_stocks) < 5:
            log.warning("股票不足，跳过正常调仓")
            return
    
    target_stocks_list = apply_industry_constraint(candidate_stocks, context)
    log.info(f"调仓日: {current_date}, 目标股票: {len(target_stocks_list)}只")
    
    base_position_ratio = get_market_position_ratio(context)
    risk_adj = context.risk_adjust_ratio
    final_position_ratio = base_position_ratio * risk_adj
    log.info(f"当前仓位因子: 牛熊={base_position_ratio:.0%}, 组合风控={risk_adj:.2f}, 最终={final_position_ratio:.0%}")
    
    top_stocks_info = [s for s in context.stock_pool[:CONFIG['top_n_stocks']] if s['code'] in target_stocks_list]
    
    weights = calculate_risk_parity_weights(top_stocks_info)
    
    low_conf_stocks = [code for code, weight in weights.items() 
                      if any(s.get('confidence') == 'low' for s in top_stocks_info if s['code'] == code)]
    if low_conf_stocks:
        log.warning(f"【置信度警告】低置信度股票: {len(low_conf_stocks)}只，权重上限5%")
    
    industry_weights = {}
    for stock, weight in list(weights.items()):
        industry = context.stock_industry_map.get(stock, '其他')
        industry_weights[industry] = industry_weights.get(industry, 0) + weight
        if industry_weights[industry] > CONFIG['max_industry_weight'] * final_position_ratio:
            excess = industry_weights[industry] - CONFIG['max_industry_weight'] * final_position_ratio
            weights[stock] -= excess * (weight / industry_weights[industry])
            industry_weights[industry] = CONFIG['max_industry_weight'] * final_position_ratio
    
    total_weight = sum(list(weights.values()))
    if total_weight > 0:
        weights = {k: v / total_weight * final_position_ratio for k, v in weights.items()}
    
    log.info(f"调仓详情:")
    for code, weight in sorted(weights.items(), key=lambda x: x[1], reverse=True)[:10]:
        conf_tag = "✓" if not any(s.get('confidence') == 'low' for s in top_stocks_info if s['code'] == code) else "⚠"
        log.info(f"  {code} 权重:{weight:.2%} {conf_tag}")
    
    execute_trades(context, weights)
    context.last_rebalance = current_date

def execute_trades(context, target_weights):
    current_data = get_current_data()
    current_date = context.current_dt.date()
    
    for stock in list(context.portfolio.positions.keys()):
        if stock.startswith(('510300', '159915', '588000', '588080')):
            continue
        if stock not in target_weights and not current_data[stock].paused:
            # 检查是否跌停，跌停则不清仓
            if current_data[stock].last_price == current_data[stock].low_limit:
                log.info(f"{stock} 跌停，暂不清仓")
                continue
            order_target(stock, 0)
            if stock in context.position_dates:
                del context.position_dates[stock]
    
    for stock, weight in target_weights.items():
        if current_data[stock].paused:
            continue
        if current_data[stock].last_price in [current_data[stock].high_limit, current_data[stock].low_limit]:
            continue
        
        order_value(stock, context.portfolio.total_value * weight)
        
        # 记录买入日期（用于持仓天数），不再记录成本（改用avg_cost）
        if stock not in context.position_dates:
            context.position_dates[stock] = current_date
        # 初始化最高价记录
        if stock not in context.highest_prices:
            context.highest_prices[stock] = current_data[stock].last_price
        else:
            context.highest_prices[stock] = max(context.highest_prices[stock], current_data[stock].last_price)

def calculate_atr_for_stock(stock, context):
    current_date = context.current_dt.date()
    df = get_price(stock, count=20, end_date=current_date - timedelta(days=1),
                  frequency='daily', fields=['high', 'low', 'close'], panel=False)
    
    if df is None or len(df) < 14:
        return 0.05
    
    df = df.copy()
    df['tr'] = np.max([
        df['high'] - df['low'],
        np.abs(df['high'] - df['close'].shift(1)),
        np.abs(df['low'] - df['close'].shift(1))
    ], axis=0)
    atr = df['tr'].rolling(14).mean().iloc[-1]
    
    return atr if not pd.isna(atr) and atr > 0 else 0.05

def check_stop_loss(context):
    if context.current_dt.hour < 14:
        return
    
    current_data = get_current_data()
    current_date = context.current_dt.date()
    
    for stock in list(context.portfolio.positions.keys()):
        if stock.startswith(('510300', '159915', '588000', '588080')):
            continue
        
        if stock not in current_data:
            continue
        
        position = context.portfolio.positions[stock]
        if position.total_amount == 0:
            continue
        
        stock_data = current_data[stock]
        current_price = stock_data.last_price
        
        # 使用真实持仓成本
        cost_price = position.avg_cost
        if cost_price <= 0:
            continue
        
        # 更新持仓期间最高价
        if stock not in context.highest_prices:
            context.highest_prices[stock] = current_price
        else:
            context.highest_prices[stock] = max(context.highest_prices[stock], current_price)
        
        highest_price = context.highest_prices[stock]
        return_rate = (current_price - cost_price) / cost_price
        
        # ---------- 简化止损逻辑 ----------
        # 1. ATR跟踪止损：成本价 - 2.5倍ATR
        atr = calculate_atr_for_stock(stock, context)
        atr_stop = cost_price - atr * CONFIG['stop_loss_atr_multiplier']
        
        # 2. 最高点回撤止盈：最高价回撤5%
        trailing_stop = highest_price * (1 - CONFIG['trailing_stop_pct'])
        
        # 取两者中较高者（更贴近市价）
        stop_price = max(atr_stop, trailing_stop)
        if stop_price <= 0:
            stop_price = cost_price * 0.95
        
        if current_price <= stop_price:
            # 跌停保护：如果跌停无法卖出，则跳过
            if current_price == stock_data.low_limit:
                log.info(f"【止损】{stock} 触发止损但跌停无法卖出")
                continue
            order_target(stock, 0)
            log.info(f"【止损】{stock} 当前价{current_price:.2f} <= 止损价{stop_price:.2f} (成本{cost_price:.2f}，ATR止损{atr_stop:.2f}，移动止盈{trailing_stop:.2f})")
            context.highest_prices[stock] = 0
            if stock in context.position_dates:
                del context.position_dates[stock]
            continue
        
        # 3. 单日大跌止损（-5%）
        try:
            df = get_price(stock, count=2, end_date=current_date - timedelta(days=1),
                          frequency='daily', fields=['close'], panel=False)
            if df is not None and len(df) >= 2:
                today_change = (current_price - df['close'].iloc[-1]) / df['close'].iloc[-1]
                if today_change <= CONFIG['stop_loss_single_day']:
                    if current_price == stock_data.low_limit:
                        log.info(f"【止损-单日】{stock} 单日跌{today_change:.2%}但跌停无法卖出")
                        continue
                    order_target(stock, 0)
                    log.info(f"【止损-单日】{stock} 单日跌{today_change:.2%}，清仓")
                    if stock in context.position_dates:
                        del context.position_dates[stock]
        except:
            pass

def record_data(context):
    record(
        total_value=context.portfolio.total_value,
        positions=len(context.portfolio.positions),
        cash=context.portfolio.cash,
    )