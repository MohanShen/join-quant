# Clone from JoinQuant
# postId: b162637c9c452789d9fe39de4260e30a
# backtestId: d81a14766cdc1dacd64eac2ef658846b
# title: 七星高照去除过拟合优化版模拟盘记录

# 克隆自聚宽文章：https://www.joinquant.com/post/70768
# 标题：ETF 轮动策略2026年04月24日优化
# 作者：实事求是

import numpy as np
import math
import datetime
import pandas as pd
from jqdata import *

# ==================== 初始化模块 ====================
def initialize(context):
    set_option("avoid_future_data", True)
    set_option("use_real_price", True)
    set_slippage(PriceRelatedSlippage(0.0002), type="fund")
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0,
            open_commission=0.0001,
            close_commission=0.0001,
            close_today_commission=0,
            min_commission=1,
        ),
        type="fund",
    )
    set_benchmark("161226.XSHE")

    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.info("========== 优化版ETF轮动策略 ==========")

    # ---------- ETF池（精简！保留高流动性、低相关性核心品种） ----------
    g.etf_pool = [
        "518880.XSHG",  # 黄金
        "159985.XSHE",  # 豆粕
        "501018.XSHG",  # 原油
        "161226.XSHE",  # 白银
        "513100.XSHG",  # 纳指
        "159915.XSHE",  # 创业板
        "510300.XSHG",  # 沪深300
        "510500.XSHG",  # 中证500
        "588080.XSHG",  # 科创50
        "511220.XSHG",  # 城投债
    ]

    # ---------- 核心参数（极简、稳健） ----------
    g.lookback_days = 20          # 动量周期（最优实测20日）
    g.holdings_num = 1            # 持仓数量
    g.defensive_etf = "511880.XSHG"  # 货币基金防御
    g.min_money = 1000            # 最小交易金额

    # ---------- 精简风控 ----------
    g.enable_stop_loss = True     # 统一止损：8%
    g.stop_loss_ratio = 0.92
    g.enable_premium_filter = True
    g.premium_threshold = 0.15    # 溢价15%以内更安全

    g.rankings_cache = {'date': None, 'data': None}

    # ---------- 调度 ----------
    run_daily(trade, time='14:00')  # 统一14点调仓，避免多时间点冲突
    log.info(f"ETF池:{len(g.etf_pool)}只 动量周期:{g.lookback_days}天 持仓:{g.holdings_num}只")

# ==================== 统一交易函数 ====================
def trade(context):
    sell_all_unqualified(context)
    buy_top_momentum(context)

# ==================== 卖出 ====================
def sell_all_unqualified(context):
    # 1. 止损卖出
    for sec in list(context.portfolio.positions.keys()):
        if sec not in g.etf_pool and sec != g.defensive_etf:
            continue
        pos = context.portfolio.positions[sec]
        price = get_current_data()[sec].last_price
        
        # 统一8%止损
        if g.enable_stop_loss and price < pos.avg_cost * g.stop_loss_ratio:
            smart_order_target_value(sec, 0, context)
            log.info(f"【止损卖出】{sec} {get_name(sec)}")

    # 2. 卖出不在目标列表的持仓
    ranked = get_cached_rankings(context)
    target_etfs = [m['etf'] for m in ranked[:g.holdings_num]]
    if not target_etfs:
        target_etfs = [g.defensive_etf]

    for sec in list(context.portfolio.positions.keys()):
        if sec not in target_etfs:
            smart_order_target_value(sec, 0, context)

# ==================== 买入 ====================
def buy_top_momentum(context):
    ranked = get_cached_rankings(context)
    if not ranked:
        smart_order_target_value(g.defensive_etf, context.portfolio.total_value, context)
        return

    target = ranked[0]['etf']
    target_value = context.portfolio.total_value
    smart_order_target_value(target, target_value, context)

# ==================== 核心动量计算（最稳版本） ====================
def get_cached_rankings(context):
    today = context.current_dt.date()
    if g.rankings_cache['date'] == today:
        return g.rankings_cache['data']
    
    etf_list = []
    for etf in g.etf_pool:
        if get_current_data()[etf].paused:
            continue
        
        # 动量 = 20日收益率
        hist = attribute_history(etf, g.lookback_days+1, '1d', 'close')
        if len(hist) < g.lookback_days+1:
            continue
        momentum = hist['close'].iloc[-1] / hist['close'].iloc[0] - 1

        # 溢价过滤（修复版调用）
        premium = None
        if g.enable_premium_filter:
            prev_date = get_trade_days(end_date=today, count=2)[0]
            premium = get_premium_rate(etf, prev_date)
        if premium is not None and premium > g.premium_threshold:
            continue

        etf_list.append({'etf': etf, 'score': momentum})

    etf_list.sort(key=lambda x: x['score'], reverse=True)
    g.rankings_cache = {'date': today, 'data': etf_list}
    return etf_list

# ==================== 工具函数 ====================
def get_premium_rate(code, date):
    try:
        price = get_price(code, start_date=date, end_date=date, frequency='daily', fields=['close'])['close'].iloc[0]
        net_value_df = get_extras('unit_net_value', code, start_date=date, end_date=date, df=True)
        net = net_value_df[code].iloc[0]
        return (price - net) / net
    except:
        return None

def get_name(security):
    try:
        return get_current_data()[security].name
    except:
        return "未知"

def smart_order_target_value(security, target_value, context):
    data = get_current_data()
    if data[security].paused:
        return False
    price = data[security].last_price
    if price <= 0:
        return False

    current_amount = context.portfolio.positions[security].total_amount if security in context.portfolio.positions else 0
    target_amount = int(target_value / price)
    target_amount = (target_amount // 100) * 100
    diff = target_amount - current_amount

    if diff == 0:
        return True
    if abs(diff * price) < 500:
        return False

    order(security, diff)
    return True