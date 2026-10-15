# Clone from JoinQuant
# postId: 223a137ed5b63daedcb57320c10c1207
# backtestId: ed24fcb6085e668ac6e5c2bf20a86a3a
# title: 回测里的坑：你选的ETF那时候还没上市呢

# 极简版ETF动量轮动策略（仅保留R²和加权回归作为可选过滤，其他高过拟合项全部去除）
import numpy as np
import pandas as pd
import math
from collections import defaultdict

# ==================== 策略配置 ====================
STRATEGY_CONFIG = {
    # 核心参数
    "momentum_days": 25,                 # 动量计算天数
    "stock_sum": 3,                      # 持仓数量
    "defensive_etf": "511880.XSHG",      # 防御ETF
    "weighting": "equal",                # 权重分配：'equal' 或 'momentum'
    
    # 可选过滤（默认关闭，可开启测试）
    "enable_r2_filter": True,           # R²过滤开关
    "r2_threshold": 0.2,                 # R²阈值（当enable_r2_filter=True时生效）
    "weighted_regression": False,        # 是否使用加权回归（True=近期权重大，False=等权）
    
    # 动态池参数
    "dynamic_pool_min_money": 2000000,   # 200万（降低门槛确保早期有ETF）
    "dynamic_pool_size": 100,
    "use_fixed_pool": True,              # 启用固定池保底
    "fixed_etf_pool": ["510300.XSHG", "518880.XSHG", "513100.XSHG", "159915.XSHE"],
}

# ==================== 常量 ====================
EXCLUDE_KEYWORDS = ['债券', '货币', '国债', '可转债', '短融']  # 只排除纯债/货币类ETF

# ==================== 全局变量 ====================
g_dynamic_pool = []
g_merged_etf_pool = []
g_etf_names = {}
g_buy_prices = {}

def initialize(context):
    set_option('avoid_future_data', True)
    set_option('use_real_price', True)
    set_slippage(FixedSlippage(0.005), type="fund")
    set_order_cost(OrderCost(open_tax=0, close_tax=0,
                            open_commission=0.0001, close_commission=0.0001,
                            close_today_commission=0.0001, min_commission=5), type="fund")
    
    run_daily(morning_routine, time='09:00')
    run_daily(afternoon_routine, time='13:10')
    
    context._targets_cache = {'date': None, 'targets': [], 'weights': {}}
    log.info("ETF动量轮动策略启动（仅保留R²和加权回归作为可选过滤）")
    log.info(f"R²过滤: {STRATEGY_CONFIG['enable_r2_filter']} (阈值{STRATEGY_CONFIG['r2_threshold']})")
    log.info(f"加权回归: {STRATEGY_CONFIG['weighted_regression']}")

def get_security_name(security):
    return g_etf_names.get(security, security)

def update_etf_names(context):
    global g_etf_names
    try:
        df = get_all_securities(['etf'])
        g_etf_names = df['display_name'].to_dict()
    except:
        g_etf_names = {}

# ==================== 动态池构建 ====================
def update_sector_pool(context):
    global g_dynamic_pool
    all_etf = list(get_all_securities(['etf']).index)
    today = context.current_dt.date()
    valid = []
    for code in all_etf:
        if code == STRATEGY_CONFIG["defensive_etf"]:
            continue
        name = g_etf_names.get(code, code)
        if any(kw in name for kw in EXCLUDE_KEYWORDS):
            continue
        info = get_security_info(code)
        if info.start_date > today:
            continue
        valid.append(code)
    
    if not valid:
        g_dynamic_pool = []
        return
    
    threshold = STRATEGY_CONFIG["dynamic_pool_min_money"]
    end_date = context.previous_date
    try:
        price_data = get_price(valid, end_date=end_date, count=3, frequency='daily', fields=['money'], panel=False)
        if price_data is None or price_data.empty:
            g_dynamic_pool = []
            return
        total_money = price_data.groupby('code')['money'].sum()
        avg_money = total_money / 3
        qualified = avg_money[avg_money > threshold].sort_values(ascending=False)
        g_dynamic_pool = qualified.head(STRATEGY_CONFIG["dynamic_pool_size"]).index.tolist()
        log.info(f"动态池数量: {len(g_dynamic_pool)}")
    except Exception as e:
        log.warning(f"动态池更新异常: {e}")
        g_dynamic_pool = []

def merge_etf_pools(context):
    global g_merged_etf_pool
    today = context.current_dt.date()
    merged = []
    if STRATEGY_CONFIG["use_fixed_pool"]:
        for code in STRATEGY_CONFIG["fixed_etf_pool"]:
            info = get_security_info(code)
            if info.start_date <= today:
                merged.append(code)
    merged.extend(g_dynamic_pool)
    g_merged_etf_pool = list(set(merged))
    if not g_merged_etf_pool:
        g_merged_etf_pool = ["510300.XSHG", "518880.XSHG", "159915.XSHE"]
        log.warning("合并池为空，强制加入保底ETF")
    log.info(f"合并池: {len(g_merged_etf_pool)}只")

# ==================== 动量得分计算 ====================
def calc_momentum_score(close_series):
    """计算动量得分，根据配置选择加权回归或等权回归，同时返回R²"""
    y = np.log(close_series)
    x = np.arange(len(y))
    if STRATEGY_CONFIG["weighted_regression"]:
        weights = np.linspace(1, 2, len(y))
        slope, intercept = np.polyfit(x, y, 1, w=weights)
        fitted = slope * x + intercept
        ss_res = np.sum(weights * (y - fitted)**2)
        ss_tot = np.sum(weights * (y - np.mean(y))**2)
        r2 = 1 - ss_res / ss_tot if ss_tot != 0 else 0
    else:
        slope, intercept = np.polyfit(x, y, 1)
        fitted = slope * x + intercept
        ss_res = np.sum((y - fitted)**2)
        ss_tot = np.sum((y - np.mean(y))**2)
        r2 = 1 - ss_res / ss_tot if ss_tot != 0 else 0
    ann_return = math.exp(slope * 250) - 1
    return ann_return * r2, r2  # 得分 = 年化收益 × R²

def get_ranked_etfs(context):
    cfg = STRATEGY_CONFIG
    etf_list = g_merged_etf_pool
    if not etf_list:
        return [], {}

    momentum_days = cfg["momentum_days"]
    lookback = momentum_days + 10
    try:
        hist = get_price(etf_list, end_date=context.previous_date, count=lookback,
                        frequency='daily', fields=['close'], panel=False)
        if hist is None or hist.empty:
            return [], {}
    except Exception as e:
        log.warning(f"获取历史数据异常: {e}")
        return [], {}
    
    current_data = get_current_data()
    all_metrics = []
    for etf in etf_list:
        if current_data[etf].paused:
            continue
        etf_hist = hist[hist['code'] == etf]
        if len(etf_hist) < momentum_days:
            continue
        closes = etf_hist['close'].values[-momentum_days:]
        score, r2 = calc_momentum_score(closes)
        if np.isnan(score):
            continue
        # R²过滤（如果启用）
        if cfg["enable_r2_filter"] and r2 < cfg["r2_threshold"]:
            continue
        all_metrics.append((etf, score))
    
    if not all_metrics:
        log.info("无ETF通过动量筛选")
        return [], {}
    
    all_metrics.sort(key=lambda x: x[1], reverse=True)
    selected = all_metrics[:cfg["stock_sum"]]
    
    # 权重分配
    if cfg["weighting"] == "momentum":
        total = sum(s for _, s in selected)
        if total > 0:
            weights = {etf: s/total for etf, s in selected}
        else:
            weights = {etf: 1.0/len(selected) for etf, _ in selected}
    else:
        weights = {etf: 1.0/len(selected) for etf, _ in selected}
    
    target_list = [etf for etf, _ in selected]
    log.info(f"最终目标({len(target_list)}只): {[(etf, round(s,4)) for etf,s in selected]}")
    return target_list, weights

def get_cached_targets(context):
    today = context.current_dt.date()
    if hasattr(context, '_targets_cache') and context._targets_cache.get('date') == today:
        return context._targets_cache['targets'], context._targets_cache['weights']
    targets, weights = get_ranked_etfs(context)
    context._targets_cache = {'date': today, 'targets': targets, 'weights': weights}
    return targets, weights

# ==================== 交易执行 ====================
def smart_order_target_value(security, target_value, context):
    current_data = get_current_data()
    if current_data[security].paused:
        return False
    if target_value == 0:
        order_target_value(security, 0)
        return True
    if target_value > context.portfolio.available_cash:
        return False
    order_target_value(security, target_value)
    return True

def afternoon_routine(context):
    log.info("午后调仓")
    targets, target_weights = get_cached_targets(context)
    # 卖出不在目标列表的持仓
    for sec in list(context.portfolio.positions.keys()):
        if sec not in targets:
            smart_order_target_value(sec, 0, context)
            if sec in g_buy_prices:
                del g_buy_prices[sec]
    total_value = context.portfolio.total_value
    if not targets:
        defensive = STRATEGY_CONFIG["defensive_etf"]
        cd = get_current_data().get(defensive)
        if cd and not cd.paused and cd.last_price < cd.high_limit:
            smart_order_target_value(defensive, total_value, context)
            log.info(f"防御模式买入 {defensive}")
        else:
            log.info("空仓")
        return
    for sec, weight in target_weights.items():
        target_val = total_value * weight
        pos = context.portfolio.positions.get(sec)
        current_val = pos.value if pos else 0
        if abs(current_val - target_val) > 1000:
            smart_order_target_value(sec, target_val, context)
            if sec not in g_buy_prices:
                g_buy_prices[sec] = get_current_data()[sec].last_price
            log.info(f"调仓 {sec} 目标{target_val:.0f} ({weight*100:.1f}%)")

def morning_routine(context):
    log.info("晨间流水线")
    update_etf_names(context)
    update_sector_pool(context)
    merge_etf_pools(context)
    # 重置缓存
    context._targets_cache = {'date': None, 'targets': [], 'weights': {}}