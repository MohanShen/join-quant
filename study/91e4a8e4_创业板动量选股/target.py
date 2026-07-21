# Clone from JoinQuant
# postId: 91e4a8e4bba018ef85991f9125014ad8
# backtestId: a91baf0fddcbce9e7f07493b993945b9
# title: 创业板指长中短动量选股

# 克隆自聚宽文章：https://www.joinquant.com/post/71381
# 标题：左手芯片右手光-2026年5月必胜
# 作者：超级幸运星

# ============================================================
# 策略名称：科技股池纯动量轮动（自建打分版）
# 说明：每日对预设的科技股池进行动量打分，选择得分最高的N只等权重买入
# 无有效信号时：保持现有持仓不变，不做任何交易
# ============================================================

import numpy as np
import math
from jqdata import *
from sklearn.svm import SVR  
from jqdata import *
from jqfactor import *
import datetime

def initialize(context):
    """
    初始化函数
    """
    
    set_benchmark('399006.XSHE')
    
    # ==================== 实盘交易设置 ====================
    set_option("avoid_future_data", True)
    set_option("use_real_price", True)
    set_slippage(PriceRelatedSlippage(0.0001), type="stock")
    
    # 交易成本设置（股票默认）
    set_order_cost(OrderCost(
        open_tax=0,
        close_tax=0.001,          # 印花税
        open_commission=0.00025,  # 佣金万2.5
        close_commission=0.00025,
        close_today_commission=0,
        min_commission=5
    ), type='stock')
    
    log.set_level('order', 'error')
    log.set_level('strategy', 'info')
    

    # ==================== 策略参数 ====================
    g.lookback_days = [3, 20, 200]      # 动量计算周期（天）
    g.holdings_num = 5        # 持仓数量（Top N）
    g.min_money = 5000        # 最小交易金额
    
    # 风控参数
    g.stop_loss = 0.95        # 固定止损线（亏损5%卖出）
    
    # ==================== 交易时间安排 ====================
    #run_daily(rebalance, time='14:50')   # 每日调仓
    run_weekly(rebalance, -1, time='9:32')
    #run_daily(check_positions, time='09:35') 
    
    #log.info(f"策略初始化完成，股票池数量: {len(g.stock_pool)}，持仓数: {g.holdings_num}")

# ==================== 动量打分函数 ====================
def calculate_momentum_score(security, lookback):
    """
    计算单只标的的动量得分（年化收益率 * 趋势稳定性R²）
    返回：得分（float），若数据不足返回0
    """
    try:
        prices = attribute_history(security, lookback+10, '1d', ['close'], skip_paused=True, df=False)
        if len(prices['close']) < lookback:
            print("attribute_history {security}无足够数据")
            return 0
        
        price_series = prices['close'][-lookback-1:]
        if len(price_series) < lookback+1:
            print("attribute_history2 {security}无足够数据")
            return 0
        
        current_data = get_current_data()
        current_price = current_data[security].last_price
        if current_price is None or current_price <= 0:
            print("current_price {security} is None")
            return 0
        
        price_series = np.append(price_series, current_price)
        y = np.log(price_series)
        x = np.arange(len(y))
        weights = np.linspace(1, 2, len(y))
        
        slope, intercept = np.polyfit(x, y, 1, w=weights)
        annualized_return = math.exp(slope * 250) - 1
        
        ss_res = np.sum(weights * (y - (slope * x + intercept))**2)
        ss_tot = np.sum(weights * (y - np.mean(y))**2)
        r_squared = 1 - ss_res/ss_tot if ss_tot != 0 else 0
        
        score = annualized_return * r_squared
        #score = annualized_return
        
        if len(price_series) >= 4:
            returns = price_series[-4:]/price_series[-5:-1] - 1
            if min(returns) < -0.03:
                score = score * 0.5
        
        return score if score > 0 else 0
        
    except Exception as e:
        log.warning(f"计算{security}得分出错: {e}")
        return 0
        
# ==================== 获取目标持仓权重 ====================
def get_target_weights(context):
    """
    对股池内所有标的打分，选出得分最高的g.holdings_num只，等权重分配
    返回：{security: weight} 字典
    """
    current_date = context.previous_date


    stock_pool = list(set(get_index_stocks('399006.XSHE', current_date) ) ) # + + get_index_stocks('000688.XSHG', current_date) 
    scores = []
    for stock in stock_pool:
        score1 = calculate_momentum_score(stock, g.lookback_days[1]) # 20天动量
        score2 = calculate_momentum_score(stock, g.lookback_days[2]) # 200天动量
        if score1 <= 0 or score2 <= 0:
            continue
        score = score1 * score2* calculate_momentum_score(stock, g.lookback_days[0]) # 3天动量
        if score > 0:
            scores.append((stock, score))
    
    if  len(scores) <= 0:
        #log.warning("无任何标的得分>0，清仓")
        return {}
    
    scores.sort(key=lambda x: x[1], reverse=True)
    top_stocks = [s[0] for s in scores[:g.holdings_num]]
    weight = 1.0 / len(top_stocks)
    target = {stock: weight for stock in top_stocks}
    
    log.info(f"今日得分前{g.holdings_num}名: {[s[0] for s in scores[:g.holdings_num]]}")
    return target

# ==================== 智能下单函数 ====================
def smart_order_target_value(context, security, target_value):
    """
    下单到目标市值（处理停牌、涨停跌停、最小交易单位）
    返回：是否成功下单
    """
    current_data = get_current_data()
    if security not in current_data:
        return False
    if current_data[security].paused:
        log.info(f"{security} 停牌，跳过")
        return False
    
    price = current_data[security].last_price
    if price <= 0:
        return False
    
    pos = context.portfolio.positions.get(security, None)
    current_amount = pos.total_amount if pos else 0
    
    target_amount = int(target_value / price)
    target_amount = (target_amount // 100) * 100
    if target_amount <= 0 and target_value > 0:
        target_amount = 100
    
    diff_amount = target_amount - current_amount
    if diff_amount == 0:
        return True
    
    if abs(diff_amount) * price < g.min_money:
        log.info(f"{security} 交易金额小于{g.min_money}，跳过")
        return False
    
    if diff_amount < 0:
        closeable = pos.closeable_amount if pos else 0
        if closeable <= 0:
            log.info(f"{security} 无可卖股份（T+1限制）")
            return False
        diff_amount = -min(abs(diff_amount), closeable)
    
    # 👇 这里加科创板保护限价
    if security.startswith('688'):
        style = MarketOrderStyle(limit_price=price * 1.02)  # 买入设+2%，卖出-2%
    else:
        style = MarketOrderStyle()
    order_result = order(security, diff_amount, style = style)
    
    if order_result:
        action = "买入" if diff_amount > 0 else "卖出"
        log.info(f"{action} {security} {abs(diff_amount)}股 @ {price:.3f}")
        return True
    else:
        log.warning(f"下单失败: {security} 数量{diff_amount}")
        return False

# ==================== 调仓主函数 ====================
def rebalance(context):
    log.info("=== 开始调仓 ===")
    
    target_weights = get_target_weights(context)
    
    # 无有效信号 -> 保持现有持仓不变，不做任何交易
    #if not target_weights:
    #    log.info("无有效信号，保持现有持仓不变（不做任何交易）")
    #    return
    
    total_value = context.portfolio.total_value
    
    # 卖出不在目标中的持仓
    current_holdings = list(context.portfolio.positions.keys())
    for sec in current_holdings:
        if len(target_weights) ==0 or sec not in target_weights:
            order_target_value(sec, 0)
            #smart_order_target_value(context, sec, 0)
            
    if len(target_weights) ==0:
        return
    # 买入/调整目标持仓
    for sec, weight in target_weights.items():
        target_value = total_value * weight
        smart_order_target_value(context, sec, target_value)
    
    # 固定止损检查
    for sec in list(context.portfolio.positions.keys()):
        pos = context.portfolio.positions[sec]
        if pos.total_amount > 0:
            current_price = pos.price
            avg_cost = pos.avg_cost
            if current_price <= avg_cost * g.stop_loss:
                log.info(f"触发止损: {sec} 成本{avg_cost:.3f} 现价{current_price:.3f}")
                smart_order_target_value(context, sec, 0)
    
    log.info("=== 调仓完成 ===")

def check_positions(context):
    """记录当日持仓"""
    for sec, pos in context.portfolio.positions.items():
        if pos.total_amount > 0:
            log.info(f"持仓 {sec} 数量{pos.total_amount} 成本{pos.avg_cost:.3f} 现价{pos.price:.3f}")