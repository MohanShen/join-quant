# Clone from JoinQuant
# postId: b5dd66ebfd94579ec47e89b2bd132b82
# backtestId: 34a31b65048394ab2a59a82d309f66db
# title: 【十年十倍】纳指+黄金全天候：动态杠杆网格系统

import pandas as pd
import numpy as np

# ==================== 1. 初始化 ====================
def initialize(context):
    set_benchmark('513100.XSHG')
    set_option('use_real_price', True) # 融资融券必须使用真实价格
    set_option("avoid_future_data", True)
    log.set_level('system', 'error')

    # 信用账户挂载
    set_subportfolios([SubPortfolioConfig(cash=context.portfolio.cash, type='stock_margin')])
    set_option('margincash_interest_rate', 0.06)
    set_option('margincash_margin_rate', 0.4) 

    set_slippage(FixedSlippage(0.001))
    set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.0002, close_commission=0.0002, close_today_commission=0, min_commission=5), type='fund')

    g.target_etf = '513100.XSHG' # 纳指ETF
    g.shield_etf = '518880.XSHG' # 黄金ETF
    
    g.base_spear_weight = 0.70  # 70% 纳指底仓
    g.base_shield_weight = 0.30 # 30% 黄金防弹衣
    
    # 🔒 棘轮最高杠杆状态记录
    g.max_leverage_locked = 1.0    
    
    run_daily(ratchet_core_satellite_engine, '14:45')

def get_name(code):
    try: return get_security_info(code).display_name
    except: return code

# ==================== 2. 真实复权杠杆引擎 ====================
def ratchet_core_satellite_engine(context):
    p = context.portfolio.subportfolios[0]
    nav = p.net_value 
    if nav <= 0: return

    # 🚨 终极修复：历史数据只能取到【昨天】（context.previous_date）
    df = get_price(g.target_etf, count=750, end_date=context.previous_date, fields=['high'], fq='pre')
    if len(df) == 0: return
    
    # 实时数据：获取【今天此时此刻(14:45)】的最新价
    current_data = get_current_data()
    p_now = current_data[g.target_etf].last_price
    
    # 真实的前高 = 过去750天的最高点，和今天当下的价格比大小（防止今天刚好创出历史新高）
    historical_high = max(df['high'].max(), p_now)
    
    # 🎯 计算无污染的真实回撤
    if p_now >= historical_high:
        drawdown = 0.0
        if g.max_leverage_locked > 1.0:
            log.info(f"🎉 纳指破历史新高({p_now:.3f})！真实回撤归零，全额卸除信用杠杆。")
            g.max_leverage_locked = 1.0
    else:
        drawdown = (p_now / historical_high) - 1

    # 根据真实回撤线性映射杠杆
    temp_leverage = 1.0
    if drawdown <= -0.30: temp_leverage = 2.0
    elif drawdown <= -0.20: temp_leverage = 1.6
    elif drawdown <= -0.10: temp_leverage = 1.3

    # 🎯 棘轮机制：锁死最高档位，不创新高绝不下车
    if temp_leverage > g.max_leverage_locked:
        g.max_leverage_locked = temp_leverage
        log.info(f"🔥 纳指发生真实回撤 {drawdown*100:.2f}%，棘轮锁定！偏置杠杆升至 {g.max_leverage_locked}x")

    # ---------------- 3. 动态计算双资产目标市值 ----------------
    ideal_shield_value = nav * g.base_shield_weight  
    ideal_spear_value = nav * g.base_spear_weight * g.max_leverage_locked 

    current_shield_value = p.positions[g.shield_etf].value if g.shield_etf in p.positions else 0
    current_spear_value = p.positions[g.target_etf].value if g.target_etf in p.positions else 0

    # ---------------- 4. 精准执行（先卖后买） ----------------
    if current_shield_value > ideal_shield_value * 1.05:
        sell_amount = int((current_shield_value - ideal_shield_value) / current_data[g.shield_etf].last_price / 100) * 100
        if sell_amount > 0: order(g.shield_etf, -sell_amount, pindex=0)
            
    if current_spear_value > ideal_spear_value * 1.05:
        sell_amount = int((current_spear_value - ideal_spear_value) / p_now / 100) * 100
        if sell_amount > 0: order(g.target_etf, -sell_amount, pindex=0)

    if current_shield_value < ideal_shield_value * 0.95:
        buy_value = ideal_shield_value - current_shield_value
        buy_amount = int(buy_value / current_data[g.shield_etf].last_price / 100) * 100
        if buy_amount > 0: execute_buy(context, g.shield_etf, buy_amount, current_data[g.shield_etf].last_price)

    if current_spear_value < ideal_spear_value * 0.95:
        buy_value = ideal_spear_value - current_spear_value
        buy_amount = int(buy_value / p_now / 100) * 100
        if buy_amount > 0: execute_buy(context, g.target_etf, buy_amount, p_now)

    # 自动归还利息
    repay_debt(context)

# ----------------- 辅助模块 -----------------
def execute_buy(context, etf, buy_amount, price):
    p = context.portfolio.subportfolios[0]
    available_cash = p.available_cash
    cash_buy_amount = min(buy_amount, int(available_cash / price / 100) * 100)
    margin_buy_amount = buy_amount - cash_buy_amount
    
    if cash_buy_amount > 0:
        order(etf, cash_buy_amount, pindex=0)
    if margin_buy_amount > 0:
        margincash_open(etf, margin_buy_amount, pindex=0)

def repay_debt(context):
    p = context.portfolio.subportfolios[0]
    cash = p.available_cash
    liability = p.cash_liability
    if cash > 100 and liability > 0:
        repay_amount = min(cash, liability)
        margincash_direct_refund(repay_amount, pindex=0)