# Clone from JoinQuant
# postId: 2c1626052bf4bcb3e292c51d6334725d
# backtestId: 1137db25dfa38dfce713e880a6becf16
# title: 拆解低回撤策略：不追热点凭什么16年565%，回撤9%？

# 克隆自聚宽文章：https://www.joinquant.com/post/72568
# 标题：又找到组织了，有没有低频ETF稳健策略？
# 作者：大磨投

# 全天候低波动策略（升级版 - 已剔除月中仓位漂移微调）
# 增强功能：支持启动后首个交易日立刻全配置，随后切换为月度调仓

import jqdata
import numpy as np
import pandas as pd
import datetime
from jqdata import *


def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_option('order_volume_ratio', 1)
    set_order_cost(
        OrderCost(close_tax=0, open_commission=0.00013,
                  close_commission=0.00013, min_commission=5),
        type='fund'
    )

    # ========== 4只核心标的（月度逆波动率加权） ==========
    g.all_symbols = [
        '518880.XSHG',  # 黄金ETF
        '159985.XSHE',  # 豆粕ETF
        '513100.XSHG',  # 纳指100
        '159915.XSHE',  # 创业板ETF（受日度信号控制）
    ]

    # ========== 闲置资金替代标的 ==========
    g.bond_substitute = '512890.XSHG'  # 红利ETF 

    # 波动率计算周期
    g.vol_lookback = 60

    # ========== stra2：创业板日度动量信号 ==========
    g.stra2_asset              = '159915.XSHE'
    g.roc_period               = 20
    g.stra2_roc_buy_threshold  = 0.08
    g.stra2_roc_sell_threshold = 0.0
    g.stra2_signal             = 0   # 0=空仓（持城投债） 1=持仓（持创业板）

    # ========== 调仓状态控制相关 ==========
    g.monthly_weights       = {}   # 每月算出的全资产理论权重
    g.signal_date           = None
    g.execute_tomorrow      = False
    g.ready_to_trade        = False
    g.ready_to_trade_stra2  = False
    
    # 【新增控制锁】标记是否为启动后的第一次运行
    g.is_first_run          = True  

    # ========== 定时任务：级差时序流 ==========
    # 1. 每月第一个交易日收盘：计算下月纯粹的理论权重
    run_monthly(generate_monthly_weights, 1, time='close', reference_security='000300.XSHG')

    # 2. 每日开盘：确认今天是不是调仓执行日（引入首日立即触发逻辑）
    run_daily(check_execute, time='open', reference_security='000300.XSHG')
    
    # 3. 每日 10:30：更新动量择时信号
    run_daily(stra2_update_signal, time='10:30', reference_security='000300.XSHG')
    
    # 4. 每日 10:31：月度调仓卖出（大调仓日运行）
    run_daily(monthly_sell, time='10:31', reference_security='000300.XSHG')
    
    # 5. 每日 10:32：月度调仓买入（大调仓日运行）
    run_daily(monthly_buy, time='10:32', reference_security='000300.XSHG')
    
    # 6. 每日 10:33：日度择时执行（精准处理互换，规避月中漂移）
    run_daily(stra2_execute, time='10:33', reference_security='000300.XSHG')

    log.info("【系统初始化】策略初始化完毕。首个交易日即刻建仓机制已激活。")


# ======================================================================
# 月度逆波动率加权
# ======================================================================

def generate_monthly_weights(context):
    log.info(f"[计算权重] 开始计算逆波动率理论权重: {context.current_dt.strftime('%Y-%m-%d')}")
    valid_assets = []
    asset_vols   = {}

    for asset in g.all_symbols:
        prices_df = get_price(
            asset, end_date=context.previous_date,
            frequency='daily', fields=['close'], count=g.vol_lookback + 1
        )
        if prices_df is None or len(prices_df['close']) < g.vol_lookback + 1:
            continue

        returns = prices_df['close'].pct_change().dropna()
        if len(returns) < 2:
            continue

        vol = returns.std()
        if vol > 0:
            asset_vols[asset] = vol
            valid_assets.append(asset)

    if not valid_assets:
        g.monthly_weights  = {}
        g.signal_date      = context.current_dt.date()
        g.execute_tomorrow = True
        return

    total_inv_vol = sum(1.0 / asset_vols[a] for a in valid_assets)
    weights = {a: (1.0 / asset_vols[a]) / total_inv_vol for a in valid_assets}

    log.info(f"[计算权重] 全资产理论组合权重: " + ", ".join(f"{a}:{w:.2%}" for a, w in weights.items()))

    g.monthly_weights  = weights
    g.signal_date      = context.current_dt.date()
    g.execute_tomorrow = True
    g.ready_to_trade    = False


def check_execute(context):
    """
    每日开盘检查：融合了“首日强制调仓”与“常规月初调仓”双轨机制
    """
    # 【核心修改】如果检测到是启动后的第一个交易日，强行触发全套调仓权重计算与执行流
    if g.is_first_run:
        log.info(f"【首日激活】监测到策略首次运行，开启首日紧急盘中建仓机制...")
        generate_monthly_weights(context) # 现场立即计算出当前的理论仓位骨架
        g.ready_to_trade = True           # 允许 10:31 和 10:32 的买卖函数破例开闸执行
        g.is_first_run = False            # 永久关闭首日状态锁，回归常规月度逻辑
        return

    # 常规月度调仓执行检查
    if not g.execute_tomorrow:
        return
    if g.signal_date and context.current_dt.date() == g.signal_date:
        return
    g.ready_to_trade = True


def get_effective_weights(context):
    return g.monthly_weights


def monthly_sell(context):
    if not g.ready_to_trade:
        return

    effective    = get_effective_weights(context)
    total_value  = context.portfolio.total_value
    current_data = get_current_data()

    for security in list(context.portfolio.positions.keys()):
        if security == g.bond_substitute:
            continue

        pos = context.portfolio.positions[security]
        if pos.total_amount <= 0:
            continue

        current_price  = current_data[security].last_price
        current_value  = pos.total_amount * current_price
        current_weight = current_value / total_value

        if security not in effective:
            log.info(f"[调仓-卖] {security} 移出资产池，实施清仓")
            order_target_value(security, 0)
        else:
            target_weight = effective[security]
            if target_weight < current_weight - 0.01:
                log.info(f"[调仓-减仓] {security} {current_weight:.2%} -> {target_weight:.2%}")
                order_target_value(security, target_weight * total_value)


def monthly_buy(context):
    if not g.ready_to_trade:
        return

    effective    = get_effective_weights(context)
    total_value  = context.portfolio.total_value
    current_data = get_current_data()

    for security, target_weight in effective.items():
        if security == g.stra2_asset:
            continue

        pos = context.portfolio.positions.get(security)
        current_price = current_data[security].last_price
        current_value = pos.total_amount * current_price if pos else 0
        current_weight = current_value / total_value

        if target_weight > current_weight + 0.01:
            log.info(f"[调仓-加仓] {security} {current_weight:.2%} -> {target_weight:.2%}")
            safe_order(security, target_weight * total_value, context)

    # 无论是首日建仓还是常规月初调仓，都向 10:33 函数发出“开始处理创业板头寸”信号
    g.ready_to_trade_stra2 = True 

    g.ready_to_trade   = False
    g.execute_tomorrow = False
    g.signal_date      = None


# ======================================================================
# stra2：创业板日度动量信号与城投债精准互换
# ======================================================================

def stra2_update_signal(context):
    asset    = g.stra2_asset
    end_date = context.previous_date

    prices = get_price(
        asset, end_date=end_date, frequency='daily', fields=['close'], count=g.roc_period + 1
    )['close']

    if len(prices) < g.roc_period + 1:
        return

    roc        = prices.iloc[-1] / prices.iloc[0] - 1
    old_signal = g.stra2_signal

    if roc > g.stra2_roc_buy_threshold:
        g.stra2_signal = 1
    elif roc < g.stra2_roc_sell_threshold:
        g.stra2_signal = 0

    if old_signal != g.stra2_signal:
        f = "[日度信号变动]"
        msg = f"{f} 创业板ROC({g.roc_period}d)={roc:.4f}, 信号: {old_signal} -> {g.stra2_signal}"
        act = '配置创业板' if g.stra2_signal == 1 else '切换城投债防守'
        log.info(f"{msg} ({act})")


def stra2_execute(context):
    """
    状态激活制互换：
    仅在首日建仓、大调仓日或日度动量信号突变当天出单，月中拒绝微调。
    """
    asset = g.stra2_asset
    bond  = g.bond_substitute
    current_data = get_current_data()

    if current_data[asset].paused or current_data[bond].paused:
        return

    total_value = context.portfolio.total_value
    theory_weight = g.monthly_weights.get(asset, 0)
    if theory_weight == 0:
        return  

    pos_asset = context.portfolio.positions.get(asset)
    pos_bond  = context.portfolio.positions.get(bond)

    val_asset = pos_asset.total_amount * current_data[asset].last_price if pos_asset else 0
    val_bond  = pos_bond.total_amount * current_data[bond].last_price if pos_bond else 0

    init_needed = getattr(g, 'ready_to_trade_stra2', False)

    if g.stra2_signal == 1:
        # === 场景 A：应该持有创业板 ===
        if val_bond > 0 or val_asset == 0 or init_needed:
            if val_bond > 0:
                log.info(f"[日度撤退] 切换回权益资产，清仓城投债 {bond}")
                order_target_value(bond, 0)
            
            log.info(f"[日度进攻] 创业板足额补齐配置，理论比例: {theory_weight:.2%}")
            safe_order(asset, theory_weight * total_value, context)
            g.ready_to_trade_stra2 = False 

    elif g.stra2_signal == 0:
        # === 场景 B：应该持有城投债防守 ===
        if val_asset > 0 or val_bond == 0 or init_needed:
            if val_asset > 0:
                log.info(f"[日度避险] 切换回防守资产，清仓 {asset}")
                order_target_value(asset, 0)
            
            log.info(f"[日度防守] 闲置份额全额转入城投债 {bond}，理论比例: {theory_weight:.2%}")
            safe_order(bond, theory_weight * total_value, context)
            g.ready_to_trade_stra2 = False 


# ======================================================================
# 安全下单函数
# ======================================================================

def safe_order(security, target_value, context):
    if target_value <= 0:
        order_target_value(security, 0)
        return

    current_data = get_current_data()
    if current_data[security].paused or \
       current_data[security].last_price >= current_data[security].high_limit or \
       current_data[security].last_price <= current_data[security].low_limit:
        return

    price = current_data[security].last_price
    if price <= 0: return

    available_cash = context.portfolio.available_cash
    pos             = context.portfolio.positions.get(security)
    current_shares  = pos.total_amount if pos else 0
    current_value   = current_shares * price

    target_shares = (int(target_value / price) // 100) * 100
    if target_shares < 100:
        if available_cash + current_value >= 100 * price:
            target_shares = 100
        else:
            return

    actual_value    = target_shares * price
    net_cash_needed = actual_value - current_value

    if net_cash_needed > available_cash:
        max_shares = ((int((available_cash + current_value) / price)) // 100) * 100
        if max_shares >= 100:
            target_shares = max_shares
            actual_value  = target_shares * price
        else:
            return

    if abs(target_shares - current_shares) < 100:
        return

    try:
        order_target_value(security, actual_value)
    except Exception as e:
        log.error(f"[safe_order] {security} 下单失败: {e}")

def handle_data(context, data):
    pass