# Clone from JoinQuant
# postId: 872b03e1b8a894104033d3e1f7e1731b
# backtestId: ca3f9a89cfd32967d2a8030de8f667f2
# title: 通过聚类+多因子评分，优化五福闹春策略，收益非常好

# 克隆自聚宽文章：https://www.joinquant.com/post/67485
# 标题：优化五福闹春3.0-动态池去重问题（聚类改进版V3）
# 作者：futures hh（聚类改进版V3）
# 
# 策略概述：
# 本策略通过动态构建ETF池（聚类+多因子评分）解决同类ETF重复问题，然后对池内ETF进行动量评分，
# 选出评分最高的1只（可调）进行投资。同时配备多重止损机制（固定/当日跌幅/ATR）和冷却期，
# 并在无合适标的时切换至防御性ETF，以控制回撤。
#
# 主要步骤：
# 1. 每日09:00更新动态ETF池（流动性筛选、趋势预过滤、K-Means聚类、综合评分、相关性过滤）
# 2. 每日13:10根据动量排名确定目标ETF，并卖出不在目标中的持仓
# 3. 每日13:11等金额买入目标ETF（若未在冷却期且无未卖出风险持仓）
# 4. 盘中分钟级检查止损条件，触发后清仓并买入避险ETF，进入冷却期
#
# 适用标的：全市场ETF（自动排除债券/货币类）
# 风险等级：中高风险，适合有一定波动承受能力的投资者

import numpy as np
import math
import pandas as pd
import datetime
from jqdata import *
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
import warnings
warnings.filterwarnings('ignore')

# ==================== 聚类参数配置 ====================
# 该字典控制动态ETF池构建时的聚类参数，直接影响池子的分散度和代表性
CLUSTER_PARAMS = {
    'n_clusters': 20,              # 基准聚类数（会根据ETF总数动态调整，参考范围：10~30）
    'min_clusters': 8,              # 最小聚类数（ETF数量较少时使用，参考范围：5~10）
    'max_clusters': 25,             # 最大聚类数（避免聚类过多导致代表不足，参考范围：20~30）
    'min_history_days': 250,        # 最小历史数据天数（用于聚类，参考范围：200~300）
    'history_days': 350,            # 聚类使用的历史数据天数（取最近N天收益率，参考范围：200~400）
    'liq_threshold': 50000000,      # 流动性阈值（成交额低于此值的ETF被剔除，单位：元，参考范围：3千万~1亿）
    'corr_threshold': 0.85,         # 相关性阈值（超过此值的ETF将被去重，参考范围：0.8~0.95）
    'trend_lookback': 60,            # 趋势强度回看天数（用于预筛选，参考范围：30~90）
    'short_ma': 10,                  # 短期均线（用于趋势强度，参考范围：5~20）
    'long_ma': 30,                    # 长期均线（用于趋势强度，参考范围：20~60）
    'trend_threshold': 3,           # 趋势强度阈值（短期均线>长期均线的天数占比需≥此值/100，即3%，参考范围：0~100）
    'representatives_per_cluster': 3, # 每个聚类选取的代表数量（参考范围：2~5）
    'exclude_bond': True,           # 是否排除债券ETF（根据名称关键词）
    'exclude_monetary': True,       # 是否排除货币ETF（根据名称关键词）
}

# 需要排除的ETF类型关键词（根据名称匹配，可根据需要增减）
EXCLUDE_KEYWORDS = [
    '国债', '国开', '地方债', '政策性金融债', '短融', '中短债', '城投债',
    '货币', '保证金', '理财', '添利', '日利', '收益',
]

# ==================== 全局变量（使用字典）====================
# 该字典控制策略的交易逻辑、过滤条件、止损等核心参数
g = {
    # ---------- 基础参数 ----------
    'dynamic_etf_pool': [],          # 动态ETF池，每日更新
    'holdings_num': 1,               # 同时持有的ETF数量（参考范围：1~5，过多会导致资金分散）
    'defensive_etf': '511880.XSHG',  # 防御性ETF（无目标时持有，通常为货币/短债ETF）
    'safe_haven_etf': '511660.XSHG', # 避险ETF（止损后持有，通常为货币/短债ETF）
    'min_money': 5000,               # 最小交易金额（低于此值不交易，参考范围：3000~10000）

    # ---------- 动量得分参数 ----------
    'lookback_days': 25,              # 动量计算回看天数（加权线性回归，参考范围：15~60）
    'min_score_threshold': 0,         # 动量得分下限（低于此值剔除，设为0表示不限制负值，参考范围：-10~10）
    'max_score_threshold': 5,         # 动量得分上限（高于此值剔除，设为5可过滤极端高值，参考范围：5~20）

    # ---------- 短期动量过滤（可选） ----------
    'use_short_momentum_filter': False,   # 是否启用短期动量过滤
    'short_lookback_days': 10,            # 短期动量回看天数（参考范围：5~20）
    'short_momentum_threshold': 0.0,      # 短期动量阈值（年化收益率需≥此值，参考范围：-0.2~0.2）

    # ---------- R²过滤 ----------
    'enable_r2_filter': True,         # 是否启用R²过滤
    'r2_threshold': 0.4,              # R²阈值（拟合优度需大于此值，参考范围：0.3~0.7）

    # ---------- 年化收益率过滤（可选） ----------
    'enable_annualized_return_filter': False,  # 是否启用年化收益率过滤
    'min_annualized_return': 1.0,              # 最小年化收益率（1.0表示100%，参考范围：0.1~2.0）

    # ---------- 均线过滤（可选） ----------
    'enable_ma_filter': False,         # 是否启用均线过滤
    'ma_filter_days': 20,               # 均线周期（价格需高于此均线，参考范围：10~60）

    # ---------- 成交量过滤 ----------
    'enable_volume_check': True,        # 是否启用成交量检查（缩量过滤）
    'volume_lookback': 5,                # 成交量回看天数（参考范围：3~10）
    'volume_threshold': 1.0,             # 成交量比率阈值（当日累计成交量/过去N日均量需小于此值，参考范围：0.8~1.5）

    # ---------- 短期风控（连续下跌过滤） ----------
    'enable_loss_filter': True,          # 是否启用短期风控
    'loss': 0.97,                        # 单日最大允许跌幅（0.97表示不能跌超3%，参考范围：0.95~0.99）

    # ---------- RSI过滤（可选） ----------
    'use_rsi_filter': False,             # 是否启用RSI过滤
    'rsi_period': 6,                      # RSI计算周期（参考范围：6~14）
    'rsi_lookback_days': 1,               # RSI回看天数（检查过去N日RSI是否超阈值，参考范围：1~3）
    'rsi_threshold': 98,                  # RSI阈值（超过此值且价格低于5日均线则剔除，参考范围：90~99）

    # ---------- 止损参数 ----------
    # 固定止损（按成本价）
    'use_fixed_stop_loss': True,          # 是否启用固定止损
    'fixedStopLossThreshold': 0.95,       # 固定止损比例（成本价*此比例触发，参考范围：0.92~0.98）

    # 当日跌幅止损（按开盘价）
    'use_pct_stop_loss': False,           # 是否启用当日跌幅止损
    'pct_stop_loss_threshold': 0.95,      # 当日跌幅阈值（开盘价*此比例触发，参考范围：0.92~0.97）

    # ATR止损
    'use_atr_stop_loss': False,           # 是否启用ATR止损
    'atr_period': 14,                      # ATR计算周期（参考范围：10~20）
    'atr_multiplier': 2,                   # ATR倍数（止损价 = 成本价/最高价 - 倍数*ATR，参考范围：1.5~3）
    'atr_trailing_stop': True,             # 是否启用跟踪止损（True：基于最高价，False：基于成本价）
    'atr_exclude_defensive': True,         # 是否对防御性ETF禁用ATR止损

    # ---------- 冷却期参数 ----------
    'sell_cooldown_enabled': False,        # 是否启用冷却期（止损触发后暂停交易N天）
    'sell_cooldown_days': 3,               # 冷却期天数（参考范围：1~5）
    'cooldown_end_date': None,             # 冷却期结束日期（内部记录，勿手动修改）

    # ---------- 持仓状态记录（内部使用） ----------
    'positions': {},                       # 记录持仓数量（用于辅助，勿手动修改）
    'position_highs': {},                  # 记录持仓期间最高价（用于ATR跟踪止损）
    'position_stop_prices': {},            # 记录ATR止损价
    'target_etfs_list': [],                 # 当日目标ETF列表（内部使用）
}

# 以下为函数定义，已添加详细注释，说明功能及关键参数含义

# ==================== 辅助函数（需在initialize前定义）====================
def get_security_name(security):
    """获取证券名称，异常时返回代码"""
    try:
        current_data = get_current_data()
        return current_data[security].name
    except:
        return security

def calculate_rsi(prices, period=6):
    """
    计算RSI指标
    :param prices: 价格序列（list或array）
    :param period: RSI周期（参考范围：6~14）
    :return: RSI值列表（长度与输入相同，前period个元素为50）
    """
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

def calculate_atr(security, period=14):
    """
    计算ATR指标
    :param security: 证券代码
    :param period: ATR周期（参考范围：10~20）
    :return: (当前ATR, ATR序列, 成功标志, 消息)
    """
    try:
        needed_days = period + 20
        hist_data = attribute_history(security, needed_days, '1d', ['high', 'low', 'close'])
        if len(hist_data) < period + 1:
            return 0, [], False, "数据不足"
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
        valid_atr = atr_values[period:] if len(atr_values) > period else atr_values
        return current_atr, valid_atr, True, "成功"
    except Exception as e:
        return 0, [], False, str(e)

def is_in_cooldown(context):
    """检查是否处于冷却期"""
    if not g['sell_cooldown_enabled'] or g['cooldown_end_date'] is None:
        return False
    return context.current_dt.date() <= g['cooldown_end_date']

def set_cooldown(context):
    """设置冷却期结束日期"""
    if g['sell_cooldown_enabled']:
        g['cooldown_end_date'] = context.current_dt.date() + datetime.timedelta(days=g['sell_cooldown_days'])
        log.info(f"🔒 进入冷却期，结束: {g['cooldown_end_date']}")

def get_volume_ratio(context, security, lookback_days=None, threshold=None):
    """
    计算当日成交量与过去N日均量的比值
    :param context: 聚宽context
    :param security: 证券代码
    :param lookback_days: 均量回看天数，默认使用g['volume_lookback']
    :param threshold: 阈值（未使用，仅保留参数）
    :return: 成交量比率，若计算失败返回None
    """
    if lookback_days is None:
        lookback_days = g['volume_lookback']
    try:
        hist_data = attribute_history(security, lookback_days, '1d', ['volume'])
        if hist_data.empty or len(hist_data) < lookback_days:
            return None
        past_n_days_vol = hist_data['volume']
        if past_n_days_vol.isnull().any() or past_n_days_vol.eq(0).any():
            return None
        avg_volume = past_n_days_vol.mean()
        if avg_volume == 0:
            return None
        today = context.current_dt.date()
        df_vol = get_price(security,
                           start_date=today,
                           end_date=context.current_dt,
                           frequency='1m',
                           fields=['volume'],
                           skip_paused=False,
                           fq='pre',
                           fill_paused=False,
                           panel=False)
        current_volume = df_vol['volume'].sum()
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
        return volume_ratio
    except Exception as e:
        return None

def check_defensive_etf_available(context):
    """检查防御性ETF是否可交易（未停牌、未涨跌停）"""
    current_data = get_current_data()
    defensive_etf = g['defensive_etf']
    if current_data[defensive_etf].paused:
        return False
    if current_data[defensive_etf].last_price >= current_data[defensive_etf].high_limit:
        return False
    if current_data[defensive_etf].last_price <= current_data[defensive_etf].low_limit:
        return False
    return True

def smart_order_target_value(security, target_value, context):
    """
    智能调仓函数：调整证券至目标市值（考虑停牌、涨跌停、最小交易额、可卖数量等）
    :param security: 证券代码
    :param target_value: 目标市值
    :param context: 聚宽context
    :return: 是否成功下单
    """
    current_data = get_current_data()
    security_name = get_security_name(security)

    if current_data[security].paused:
        log.info(f"{security_name}: 停牌，跳过")
        return False
    if current_data[security].last_price >= current_data[security].high_limit:
        log.info(f"{security_name}: 涨停，跳过买入")
        return False
    if current_data[security].last_price <= current_data[security].low_limit:
        log.info(f"{security_name}: 跌停，跳过卖出")
        return False

    current_price = current_data[security].last_price
    if current_price == 0:
        return False

    target_amount = int(target_value / current_price)
    target_amount = (target_amount // 100) * 100
    if target_amount <= 0 and target_value > 0:
        target_amount = 100

    current_position = context.portfolio.positions.get(security, None)
    current_amount = current_position.total_amount if current_position else 0

    amount_diff = target_amount - current_amount
    trade_value = abs(amount_diff) * current_price

    if 0 < trade_value < g['min_money']:
        log.info(f"{security_name}: 交易额{trade_value:.2f} < {g['min_money']}，跳过")
        return False

    if amount_diff < 0:
        closeable_amount = current_position.closeable_amount if current_position else 0
        if closeable_amount == 0:
            log.info(f"{security_name}: 当日买入不可卖")
            return False
        amount_diff = -min(abs(amount_diff), closeable_amount)

    if amount_diff != 0:
        order_result = order(security, amount_diff)
        if order_result:
            g['positions'][security] = target_amount
            if amount_diff > 0 and security != g['defensive_etf'] and security != g['safe_haven_etf']:
                g['position_highs'][security] = current_price
            if g['use_atr_stop_loss'] and security != g['defensive_etf'] and security != g['safe_haven_etf']:
                current_atr, _, success, _ = calculate_atr(security, g['atr_period'])
                if success:
                    if g['atr_trailing_stop']:
                        g['position_stop_prices'][security] = current_price - g['atr_multiplier'] * current_atr
                    else:
                        g['position_stop_prices'][security] = current_price - g['atr_multiplier'] * current_atr

            if amount_diff > 0:
                log.info(f"📥 买入 {security_name}，数量: {amount_diff}，价格: {current_price:.3f}")
            else:
                log.info(f"📤 卖出 {security_name}，数量: {abs(amount_diff)}，价格: {current_price:.3f}")
            return True
        else:
            return False
    return False

def enter_safe_haven_and_set_cooldown(context, trigger_reason=""):
    """
    触发止损后：清仓风险持仓，买入避险ETF，进入冷却期
    :param trigger_reason: 触发原因（日志用）
    """
    if not g['sell_cooldown_enabled']:
        return

    log.info(f"触发止损({trigger_reason})，进入冷却期")

    # 卖出所有非避险持仓
    for security in list(context.portfolio.positions.keys()):
        if security == g['safe_haven_etf']:
            continue
        position = context.portfolio.positions[security]
        if position.total_amount > 0:
            security_name = get_security_name(security)
            smart_order_target_value(security, 0, context)
            g['position_highs'].pop(security, None)
            g['position_stop_prices'].pop(security, None)
            log.info(f"冷却期卖出: {security_name}")

    # 买入避险ETF
    total_value = context.portfolio.total_value
    if total_value > g['min_money']:
        smart_order_target_value(g['safe_haven_etf'], total_value * 0.99, context)
        safe_name = get_security_name(g['safe_haven_etf'])
        log.info(f"买入避险ETF: {safe_name}")
    else:
        log.info("资金不足，无法买入避险ETF")

    set_cooldown(context)

def exit_safe_haven_if_cooldown_ends(context):
    """冷却期结束后卖出避险ETF，恢复正常交易"""
    if not g['sell_cooldown_enabled'] or g['cooldown_end_date'] is None:
        return

    current_date = context.current_dt.date()
    if current_date > g['cooldown_end_date']:
        log.info(f"冷却期结束: {current_date}")

        if g['safe_haven_etf'] in context.portfolio.positions:
            position = context.portfolio.positions[g['safe_haven_etf']]
            if position.total_amount > 0:
                security_name = get_security_name(g['safe_haven_etf'])
                smart_order_target_value(g['safe_haven_etf'], 0, context)
                log.info(f"卖出避险ETF: {security_name}")
                g['position_highs'].pop(g['safe_haven_etf'], None)
                g['position_stop_prices'].pop(g['safe_haven_etf'], None)

        g['cooldown_end_date'] = None
        log.info("恢复正常运行")

def check_positions(context):
    """每日09:10打印持仓信息"""
    current_data = get_current_data()
    for security in context.portfolio.positions:
        position = context.portfolio.positions[security]
        if position.total_amount > 0:
            security_name = get_security_name(security)
            log.info(f"持仓: {security_name}, 数量: {position.total_amount}, 成本: {position.avg_cost:.3f}, 现价: {position.price:.3f}")
            if current_data[security].paused:
                log.info(f"⚠️ {security_name} 停牌")

def minute_level_stop_loss(context):
    """分钟级固定止损检查"""
    if not g['use_fixed_stop_loss']:
        return
    if is_in_cooldown(context):
        return

    for security in list(context.portfolio.positions.keys()):
        if security == g['defensive_etf'] or security == g['safe_haven_etf']:
            continue
        position = context.portfolio.positions[security]
        if position.total_amount <= 0:
            continue

        current_data = get_current_data()
        current_price = current_data[security].last_price
        cost_price = position.avg_cost

        if current_price <= cost_price * g['fixedStopLossThreshold']:
            security_name = get_security_name(security)
            loss_percent = (current_price / cost_price - 1) * 100
            log.info(f"🚨 固定止损: {security_name}，当前价: {current_price:.3f}, 成本: {cost_price:.3f}, 亏损: {loss_percent:.2f}%")

            success = smart_order_target_value(security, 0, context)
            if success:
                log.info(f"✅ 止损成功: {security_name}")
                g['position_highs'].pop(security, None)
                g['position_stop_prices'].pop(security, None)
                enter_safe_haven_and_set_cooldown(context, trigger_reason="固定止损")
            else:
                log.info(f"❌ 止损失败: {security_name}")

def minute_level_pct_stop_loss(context):
    """分钟级当日跌幅止损检查（基于开盘价）"""
    if not g['use_pct_stop_loss']:
        return
    if is_in_cooldown(context):
        return

    current_data = get_current_data()
    for security in list(context.portfolio.positions.keys()):
        if security == g['defensive_etf'] or security == g['safe_haven_etf']:
            continue
        position = context.portfolio.positions[security]
        if position.total_amount <= 0:
            continue

        today_open = current_data[security].day_open
        if not today_open or today_open <= 0:
            continue

        current_price = current_data[security].last_price
        stop_price = today_open * g['pct_stop_loss_threshold']

        if current_price <= stop_price:
            security_name = get_security_name(security)
            daily_loss = (current_price / today_open - 1) * 100
            log.info(f"🚨 当日跌幅止损: {security_name}，当前价: {current_price:.3f}, 开盘价: {today_open:.3f}, 当日跌幅: {daily_loss:.2f}%")

            success = smart_order_target_value(security, 0, context)
            if success:
                log.info(f"✅ 止损成功: {security_name}")
                g['position_highs'].pop(security, None)
                g['position_stop_prices'].pop(security, None)
                enter_safe_haven_and_set_cooldown(context, trigger_reason="当日跌幅止损")
            else:
                log.info(f"❌ 止损失败: {security_name}")

def minute_level_atr_stop_loss(context):
    """分钟级ATR止损检查（支持固定或跟踪止损）"""
    if not g['use_atr_stop_loss']:
        return
    if is_in_cooldown(context):
        return

    current_data = get_current_data()
    for security in list(context.portfolio.positions.keys()):
        if security == g['defensive_etf'] or security == g['safe_haven_etf']:
            continue
        position = context.portfolio.positions[security]
        if position.total_amount <= 0:
            continue
        if g['atr_exclude_defensive'] and security == g['defensive_etf']:
            continue

        try:
            security_name = get_security_name(security)
            current_price = current_data[security].last_price
            if current_price <= 0:
                continue

            cost_price = position.avg_cost

            current_atr, _, success, _ = calculate_atr(security, g['atr_period'])
            if not success or current_atr <= 0:
                continue

            if security not in g['position_highs']:
                g['position_highs'][security] = current_price
            else:
                g['position_highs'][security] = max(g['position_highs'][security], current_price)

            if g['atr_trailing_stop']:
                atr_stop_price = g['position_highs'][security] - g['atr_multiplier'] * current_atr
            else:
                atr_stop_price = cost_price - g['atr_multiplier'] * current_atr

            g['position_stop_prices'][security] = atr_stop_price

            if current_price <= atr_stop_price:
                loss_percent = (current_price / cost_price - 1) * 100
                atr_type = "跟踪" if g['atr_trailing_stop'] else "固定"
                log.info(f"🚨 ATR止损({atr_type}): {security_name}，当前价: {current_price:.3f}, 止损价: {atr_stop_price:.3f}, 亏损: {loss_percent:.2f}%")

                success = smart_order_target_value(security, 0, context)
                if success:
                    log.info(f"✅ ATR止损成功: {security_name}")
                    g['position_highs'].pop(security, None)
                    g['position_stop_prices'].pop(security, None)
                    enter_safe_haven_and_set_cooldown(context, trigger_reason="ATR止损")
                else:
                    log.info(f"❌ ATR止损失败: {security_name}")
        except Exception as e:
            continue

# ==================== 核心指标计算与过滤 ====================
def calculate_all_metrics_for_etf(context, etf):
    """
    计算单个ETF的所有动量指标和过滤条件
    :param context: 聚宽context
    :param etf: ETF代码
    :return: 字典包含各项指标及通过状态，若数据不足返回None
    """
    try:
        etf_name = get_security_name(etf)
        lookback = max(
            g['lookback_days'],
            g['short_lookback_days'],
            g['rsi_period'] + g['rsi_lookback_days'],
            g['ma_filter_days'],
            g['volume_lookback']
        ) + 20
        prices = attribute_history(etf, lookback, '1d', ['close', 'high', 'low'])
        current_data = get_current_data()
        if len(prices) < max(g['lookback_days'], g['ma_filter_days']):
            return None
        current_price = current_data[etf].last_price
        price_series = np.append(prices["close"].values, current_price)

        # 加权线性回归计算动量得分
        recent_price_series = price_series[-(g['lookback_days'] + 1):]
        y = np.log(recent_price_series)
        x = np.arange(len(y))
        weights = np.linspace(1, 2, len(y))  # 权重线性递增，越近权重越大
        slope, intercept = np.polyfit(x, y, 1, w=weights)
        annualized_returns = math.exp(slope * 250) - 1
        ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
        ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot else 0
        momentum_score = annualized_returns * r_squared

        # 短期动量（可选）
        if len(price_series) >= g['short_lookback_days'] + 1:
            short_return = price_series[-1] / price_series[-(g['short_lookback_days'] + 1)] - 1
            short_annualized = (1 + short_return) ** (250 / g['short_lookback_days']) - 1
        else:
            short_annualized = -np.inf

        # 均线过滤（可选）
        ma_price = np.mean(price_series[-g['ma_filter_days']:])
        current_above_ma = current_price >= ma_price

        # 成交量比率
        volume_ratio = get_volume_ratio(context, etf)

        # 短期风控：检查最近三日单日涨跌幅是否小于阈值
        day_ratios = []
        passed_loss_filter = True
        if len(price_series) >= 4:
            day1 = price_series[-1] / price_series[-2]
            day2 = price_series[-2] / price_series[-3]
            day3 = price_series[-3] / price_series[-4]
            day_ratios = [day1, day2, day3]
            if min(day_ratios) < g['loss']:
                passed_loss_filter = False

        # RSI过滤（可选）
        current_rsi = 0
        max_recent_rsi = 0
        passed_rsi_filter = True
        if g['use_rsi_filter'] and len(price_series) >= g['rsi_period'] + g['rsi_lookback_days']:
            rsi_values = calculate_rsi(price_series, g['rsi_period'])
            if len(rsi_values) >= g['rsi_lookback_days']:
                recent_rsi = rsi_values[-g['rsi_lookback_days']:]
                max_recent_rsi = np.max(recent_rsi)
                current_rsi = recent_rsi[-1]
                if np.any(recent_rsi > g['rsi_threshold']):
                    ma5 = np.mean(price_series[-5:]) if len(price_series) >= 5 else current_price
                    if current_price < ma5:
                        passed_rsi_filter = False

        return {
            'etf': etf,
            'etf_name': etf_name,
            'momentum_score': momentum_score,
            'annualized_returns': annualized_returns,
            'r_squared': r_squared,
            'short_annualized': short_annualized,
            'current_price': current_price,
            'ma_price': ma_price,
            'volume_ratio': volume_ratio,
            'day_ratios': day_ratios,
            'current_rsi': current_rsi,
            'max_recent_rsi': max_recent_rsi,
            'passed_momentum': g['min_score_threshold'] <= momentum_score <= g['max_score_threshold'],
            'passed_short_mom': short_annualized >= g['short_momentum_threshold'],
            'passed_r2': r_squared > g['r2_threshold'],
            'passed_annual_ret': annualized_returns >= g['min_annualized_return'],
            'passed_ma': current_above_ma,
            'passed_volume': volume_ratio is not None and volume_ratio < g['volume_threshold'],
            'passed_loss': passed_loss_filter,
            'passed_rsi': passed_rsi_filter,
        }
    except Exception as e:
        return None

def apply_filters(metrics_list):
    """
    按顺序应用所有启用的过滤器
    :param metrics_list: 指标列表
    :return: 过滤后的指标列表
    """
    steps = [
        ('动量得分', lambda m: m['passed_momentum'], True),
        ('短期动量', lambda m: m['passed_short_mom'], g['use_short_momentum_filter']),
        ('R²', lambda m: m['passed_r2'], g['enable_r2_filter']),
        ('年化收益率', lambda m: m['passed_annual_ret'], g['enable_annualized_return_filter']),
        ('均线', lambda m: m['passed_ma'], g['enable_ma_filter']),
        ('成交量', lambda m: m['passed_volume'], g['enable_volume_check']),
        ('短期风控', lambda m: m['passed_loss'], g['enable_loss_filter']),
        ('RSI', lambda m: m['passed_rsi'], g['use_rsi_filter']),
    ]
    filtered = metrics_list[:]
    for name, condition, is_enabled in steps:
        if is_enabled:
            filtered = [m for m in filtered if condition(m)]
    return filtered

def get_final_ranked_etfs(context):
    """
    对动态ETF池中的所有ETF计算指标、过滤、排序，返回前几名（用于卖出决策）
    :return: 过滤排序后的指标列表（已按动量得分降序）
    """
    all_metrics = []
    etf_set = set(g['dynamic_etf_pool'])
    
    log.info(f"【ETF池】共{len(etf_set)}只ETF")

    for etf in etf_set:
        current_data = get_current_data()
        if current_data[etf].paused:
            continue
        metrics = calculate_all_metrics_for_etf(context, etf)
        if metrics:
            all_metrics.append(metrics)

    for item in all_metrics:
        score = item.get('momentum_score')
        if pd.isna(score) or np.isnan(score):
            item['momentum_score'] = float('-inf')

    all_metrics.sort(key=lambda x: x.get('momentum_score', float('-inf')), reverse=True)

    final_list = apply_filters(all_metrics)
    for item in final_list:
        score = item.get('momentum_score')
        if pd.isna(score) or np.isnan(score):
            item['momentum_score'] = float('-inf')
    final_list.sort(key=lambda x: x.get('momentum_score', float('-inf')), reverse=True)
    
    top_3 = final_list[:3]
    if top_3:
        log.info(f"【动量排名】第1: {top_3[0]['etf_name']}({top_3[0]['momentum_score']:.3f})")
        if len(top_3) > 1:
            log.info(f"         第2: {top_3[1]['etf_name']}({top_3[1]['momentum_score']:.3f})")
        if len(top_3) > 2:
            log.info(f"         第3: {top_3[2]['etf_name']}({top_3[2]['momentum_score']:.3f})")

    return final_list

def etf_sell_trade(context):
    """
    卖出操作：根据最新排名确定目标ETF，卖出不在目标中的持仓
    """
    log.info("========== 卖出操作开始 ==========")

    if is_in_cooldown(context):
        log.info("🔒 当前处于冷却期，跳过卖出操作")
        log.info("========== 卖出操作完成 ==========")
        return

    ranked_etfs = get_final_ranked_etfs(context)
    target_etfs = []
    if ranked_etfs:
        for metrics in ranked_etfs[:g['holdings_num']]:
            target_etfs.append(metrics['etf'])
            log.info(f"目标: {metrics['etf_name']}，得分: {metrics['momentum_score']:.3f}")
    else:
        if check_defensive_etf_available(context):
            target_etfs = [g['defensive_etf']]
            etf_name = get_security_name(g['defensive_etf'])
            log.info(f"防御模式: {etf_name}")
        else:
            log.info("空仓模式")
            target_etfs = []

    g['target_etfs_list'] = target_etfs

    current_positions = list(context.portfolio.positions.keys())
    target_set = set(target_etfs)

    for security in current_positions:
        position = context.portfolio.positions[security]
        if position.total_amount > 0 and security not in target_set:
            security_name = get_security_name(security)
            log.info(f"卖出持仓: {security_name}")

            success = smart_order_target_value(security, 0, context)
            if success:
                log.info(f"✅ 卖出成功: {security_name}")
            else:
                log.info(f"❌ 卖出失败: {security_name}")

            g['position_highs'].pop(security, None)
            g['position_stop_prices'].pop(security, None)

    log.info("========== 卖出操作完成 ==========")

def etf_buy_trade(context):
    """
    买入操作：等金额买入目标ETF（需确保所有风险持仓已卖出）
    """
    log.info("========== 买入操作开始 ==========")

    exit_safe_haven_if_cooldown_ends(context)

    if is_in_cooldown(context):
        log.info("🔒 当前处于冷却期，跳过买入操作")
        log.info("========== 买入操作完成 ==========")
        return

    target_etfs = g['target_etfs_list']
    if not target_etfs:
        log.info("今日无目标ETF，保持空仓")
        log.info("========== 买入操作完成 ==========")
        return

    current_positions = list(context.portfolio.positions.keys())
    current_risk_positions = [pos for pos in current_positions if pos != g['defensive_etf'] and pos != g['safe_haven_etf']]
    positions_to_sell = [pos for pos in current_risk_positions if pos not in target_etfs]

    if positions_to_sell:
        log.info(f"尚有持仓需卖出: {[get_security_name(p) for p in positions_to_sell]}，等待卖出")
        log.info("========== 买入操作完成 ==========")
        return

    total_value = context.portfolio.total_value
    investable_value = total_value * 0.99

    target_value_per_etf = investable_value / len(target_etfs)

    log.info(f"总资产: {total_value:.2f}, 单只目标: {target_value_per_etf:.2f}")

    if target_value_per_etf < g['min_money']:
        log.info(f"目标金额 {target_value_per_etf:.2f} < {g['min_money']}，无法买入")
        log.info("========== 买入操作完成 ==========")
        return

    for etf in target_etfs:
        current_value = 0
        if etf in context.portfolio.positions:
            position = context.portfolio.positions[etf]
            if position.total_amount > 0:
                current_value = position.total_amount * position.price

        success = smart_order_target_value(etf, target_value_per_etf, context)
        if success:
            etf_name = get_security_name(etf)
            if current_value == 0:
                log.info(f"📦 买入: {etf_name}")
            elif current_value < target_value_per_etf:
                log.info(f"📦 增持: {etf_name}")
            else:
                log.info(f"📦 减持: {etf_name}")

    log.info("========== 买入操作完成 ==========")


# ==================== 动态ETF池更新函数（优化版V3）====================
def update_sector_pool(context):
    """
    动态ETF池更新（优化版V3）：
    1. 获取全市场ETF，排除债券/货币ETF，按流动性筛选
    2. 计算趋势强度，剔除趋势较弱的ETF
    3. 对剩余ETF进行K-Means聚类，动态确定聚类数
    4. 每个聚类中选取前3只综合得分最高的ETF（综合得分=成交额*0.4 + 波动率*0.3 + 动量*0.3）
    5. 相关性过滤，剔除高度相关的ETF
    6. 最终动态池（按成交额排序取前50）
    """
    try:
        # 获取所有ETF
        all_etfs = get_all_securities(['etf']).index.tolist()
        
        end_date = context.previous_date
        if end_date is None:
            end_date = context.current_dt.date()
        
        # 获取成交额数据
        try:
            h = get_price(all_etfs, count=1, end_date=end_date, frequency='daily', 
                          fields=['money'], panel=False, skip_paused=True)
            money_series = dict(zip(h['code'], h['money']))
        except Exception as e:
            log.error(f"获取成交额异常: {e}")
            g['dynamic_etf_pool'] = []
            return
        
        # 初步筛选：排除债券/货币ETF，并满足流动性要求
        candidate_etfs = []
        money_dict = {}
        
        for code in all_etfs:
            money = money_series.get(code, 0)
            if pd.isna(money) or money <= CLUSTER_PARAMS['liq_threshold']:
                continue
            
            # 获取ETF名称用于排除
            try:
                etf_name = get_security_info(code).display_name
            except:
                continue
            
            # 排除债券/货币ETF
            exclude = False
            if CLUSTER_PARAMS['exclude_bond'] or CLUSTER_PARAMS['exclude_monetary']:
                for kw in EXCLUDE_KEYWORDS:
                    if kw in etf_name:
                        exclude = True
                        break
            
            if exclude:
                continue
            
            candidate_etfs.append(code)
            money_dict[code] = money
        
        if len(candidate_etfs) < 10:
            log.warning(f"【警告】有效ETF不足10只({len(candidate_etfs)})，使用防御ETF")
            g['dynamic_etf_pool'] = []
            return
        
        # -------------------- 趋势强度预筛选 --------------------
        trend_scores = {}
        for code in candidate_etfs:
            try:
                # 获取足够的历史数据计算均线
                price = get_price(code, end_date=end_date, count=CLUSTER_PARAMS['trend_lookback']+CLUSTER_PARAMS['long_ma'],
                                  fields=['close'], skip_paused=True, panel=False)
                if len(price) < CLUSTER_PARAMS['trend_lookback'] + CLUSTER_PARAMS['long_ma']:
                    continue
                
                close = price['close'].values
                # 计算短期和长期均线
                short_ma = pd.Series(close).rolling(window=CLUSTER_PARAMS['short_ma']).mean().values
                long_ma = pd.Series(close).rolling(window=CLUSTER_PARAMS['long_ma']).mean().values
                
                # 取最近 trend_lookback 天
                short_ma = short_ma[-CLUSTER_PARAMS['trend_lookback']:]
                long_ma = long_ma[-CLUSTER_PARAMS['trend_lookback']:]
                
                # 计算短期均线大于长期均线的天数占比
                above_days = np.sum(short_ma > long_ma)
                trend_strength = above_days / CLUSTER_PARAMS['trend_lookback']
                trend_scores[code] = trend_strength
            except Exception as e:
                continue
        
        # 筛选出趋势强度达标的ETF
        trend_filtered = [code for code in candidate_etfs if code in trend_scores and trend_scores[code] >= CLUSTER_PARAMS['trend_threshold']]
        
        if len(trend_filtered) < 10:
            log.warning(f"趋势筛选后ETF不足10只({len(trend_filtered)})，回退到全部候选池")
            trend_filtered = candidate_etfs
        
        # -------------------- 获取收益率数据用于聚类和因子计算 --------------------
        hist_days = min(CLUSTER_PARAMS['history_days'], 200)
        returns_list = []
        codes_for_cluster = []
        
        for code in trend_filtered:
            try:
                price = get_price(code, end_date=end_date, count=hist_days,
                                  fields=['close'], skip_paused=True, panel=False)
                if len(price) >= hist_days * 0.8:
                    returns = price['close'].pct_change().dropna().values
                    if len(returns) >= 100:
                        # 取最后100个点
                        returns = returns[-100:]
                        returns_list.append(returns)
                        codes_for_cluster.append(code)
            except Exception as e:
                continue
        
        if len(codes_for_cluster) < 10:
            log.warning(f"【警告】可用于聚类的ETF不足10只({len(codes_for_cluster)})")
            g['dynamic_etf_pool'] = []
            return
        
        # -------------------- 动态确定聚类数 --------------------
        n_etfs = len(codes_for_cluster)
        n_clusters = min(CLUSTER_PARAMS['max_clusters'], max(CLUSTER_PARAMS['min_clusters'], n_etfs // 5))
        log.info(f"动态聚类数: {n_clusters} (总ETF数: {n_etfs})")
        
        # 构建特征矩阵
        n_days = len(returns_list[0])
        X = np.zeros((n_etfs, n_days))
        for i, ret in enumerate(returns_list):
            X[i, :] = ret
        
        # K-Means聚类
        try:
            cluster = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            labels = cluster.fit_predict(X)
        except Exception as e:
            log.error(f"聚类失败: {e}")
            g['dynamic_etf_pool'] = []
            return
        
        # 计算每只ETF的各项因子
        factor_data = []
        for code in codes_for_cluster:
            # 成交额
            money = money_dict[code]
            
            # 波动率（近60天）
            try:
                price_60 = get_price(code, end_date=end_date, count=60,
                                     fields=['close'], skip_paused=True, panel=False)
                if len(price_60) >= 20:
                    vol = price_60['close'].pct_change().std() * np.sqrt(250)
                else:
                    vol = 0
            except:
                vol = 0
            
            # 动量因子（过去20日收益率）
            try:
                price_20 = get_price(code, end_date=end_date, count=20,
                                     fields=['close'], skip_paused=True, panel=False)
                if len(price_20) >= 20:
                    ret_20 = (price_20['close'].iloc[-1] / price_20['close'].iloc[0] - 1)
                else:
                    ret_20 = 0
            except:
                ret_20 = 0
            
            factor_data.append({
                'code': code,
                'money': money,
                'volatility': vol,
                'momentum': ret_20
            })
        
        factor_df = pd.DataFrame(factor_data)
        
        # 归一化因子
        max_money = factor_df['money'].max()
        max_vol = factor_df['volatility'].max()
        max_mom = factor_df['momentum'].max()
        
        if max_money > 0:
            factor_df['money_norm'] = factor_df['money'] / max_money
        else:
            factor_df['money_norm'] = 0
        
        if max_vol > 0:
            factor_df['vol_norm'] = factor_df['volatility'] / max_vol
        else:
            factor_df['vol_norm'] = 0
        
        if max_mom > 0:
            factor_df['mom_norm'] = factor_df['momentum'] / max_mom
        else:
            factor_df['mom_norm'] = 0
        
        # 综合得分：成交额40%，波动率30%，动量30%
        factor_df['score'] = factor_df['money_norm'] * 0.4 + factor_df['vol_norm'] * 0.3 + factor_df['mom_norm'] * 0.3
        
        # 添加聚类标签
        factor_df['cluster'] = labels
        
        # 每个聚类选取前3只得分最高的ETF
        top_representatives = factor_df.sort_values('score', ascending=False).groupby('cluster').head(CLUSTER_PARAMS['representatives_per_cluster'])
        pool1 = top_representatives['code'].tolist()
        log.info(f"初步代表ETF数量: {len(pool1)} (来自{n_clusters}个聚类，每类最多{CLUSTER_PARAMS['representatives_per_cluster']}只)")
        
        # -------------------- 相关性过滤 --------------------
        try:
            # 获取收益率数据
            ret_data = {}
            for code in pool1:
                hist = attribute_history(code, 100, '1d', ['close'], skip_paused=True)
                if len(hist) >= 60:
                    ret = hist['close'].pct_change().dropna().values
                    if len(ret) > 50:
                        ret_data[code] = ret[-50:]
            
            if len(ret_data) >= 5:
                df_ret = pd.DataFrame(ret_data)
                corr = df_ret.corr().abs()
                
                remove_set = set()
                for i in range(len(pool1)):
                    for j in range(i+1, len(pool1)):
                        if pool1[i] in corr.columns and pool1[j] in corr.columns:
                            corr_val = corr.loc[pool1[i], pool1[j]]
                            if corr_val > CLUSTER_PARAMS['corr_threshold']:
                                # 保留得分较高的
                                score_i = factor_df[factor_df['code']==pool1[i]]['score'].iloc[0]
                                score_j = factor_df[factor_df['code']==pool1[j]]['score'].iloc[0]
                                if score_i < score_j:
                                    remove_set.add(pool1[i])
                                else:
                                    remove_set.add(pool1[j])
                
                pool2 = [c for c in pool1 if c not in remove_set]
                if len(remove_set) > 0:
                    log.info(f"相关性过滤: 移除{len(remove_set)}只高度相关ETF，剩余{len(pool2)}只")
            else:
                pool2 = pool1
        except Exception as e:
            log.warning(f"相关性过滤失败: {e}")
            pool2 = pool1
        
        # 更新动态池
        if not pool2:
            log.warning("聚类筛选后ETF池为空")
            g['dynamic_etf_pool'] = []
        else:
            # 按成交额排序后取前50只
            sorted_pool = sorted(pool2, key=lambda x: money_dict[x], reverse=True)
            g['dynamic_etf_pool'] = sorted_pool[:50]
        
        # 简化的日志输出
        etf_names = []
        for c in g['dynamic_etf_pool'][:10]:
            try:
                name = get_security_info(c).display_name
                etf_names.append(f"{name}")
            except:
                etf_names.append(c)
        
        log.info(f"【动态池更新】共{len(g['dynamic_etf_pool'])}只ETF，前10: {etf_names}")
        
    except Exception as e:
        log.error(f"更新动态池时发生错误: {e}")
        g['dynamic_etf_pool'] = []


# ==================== 初始化 ====================
def initialize(context):
    set_option("avoid_future_data", True)
    set_option("use_real_price", True)
    
    set_slippage(PriceRelatedSlippage(0.0001), type="fund")
    
    set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.0001, close_commission=0.0001,
                             close_today_commission=0.0001, min_commission=5), type="fund")
    
    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'info')
    
    log.info("增强版策略初始化完成（聚类改进版V3）！")
    
    set_benchmark("510300.XSHG")

    # 定时任务
    run_daily(check_positions, time='09:10')
    run_daily(etf_sell_trade, time='13:10')
    run_daily(etf_buy_trade, time='13:11')
    run_daily(update_sector_pool, time='09:00')  # 每日更新动态池

    for hour in range(9, 15):
        for minute in range(0, 60):
            current_time = "%02d:%02d" % (hour, minute)
            if ('09:27' < current_time < '11:30') or ('13:00' < current_time < '14:57'):
                run_daily(minute_level_stop_loss, time=current_time)
                run_daily(minute_level_pct_stop_loss, time=current_time)
                run_daily(minute_level_atr_stop_loss, time=current_time)

    # 简化的初始化日志
    log.info(f"策略参数: 持仓数={g['holdings_num']}, 动量周期={g['lookback_days']}, R²阈值={g['r2_threshold']}")
    log.info(f"聚类配置: 聚类数={CLUSTER_PARAMS['n_clusters']}, 流动性阈值={CLUSTER_PARAMS['liq_threshold']/1e8:.2f}亿")
    log.info(f"止损: 固定比例={g['use_fixed_stop_loss']}, 阈值={g['fixedStopLossThreshold']:.0%}")

# 空函数，满足run_daily要求
def trade(context):
    pass