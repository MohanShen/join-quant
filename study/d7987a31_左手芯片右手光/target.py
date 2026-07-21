# Clone from JoinQuant
# postId: d7987a3132fc49b6bb02476fdf446770
# backtestId: 95f20fdf66f1d4a3673c6cff2639fd16
# title: 左手芯片右手光-2026年5月必胜

# ============================================================
# 策略名称：科技股池纯动量轮动（自建打分版）
# 说明：每日对预设的科技股池进行动量打分，选择得分最高的N只等权重买入
# 无有效信号时：保持现有持仓不变，不做任何交易
# ============================================================

import numpy as np
import math
from jqdata import *

def initialize(context):
    """
    初始化函数
    """
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
    
    # ==================== 科技股池（股票） ====================
    g.stock_pool = [
        # ===== 光模块/CPO =====
        "300308.XSHE",   # 中际旭创
        "300502.XSHE",   # 新易盛
        "300394.XSHE",   # 天孚通信
        "002281.XSHE",   # 光迅科技
        "300620.XSHE",   # 光库科技
        "688498.XSHG",   # 源杰科技
        "688313.XSHG",   # 仕佳光子
        "300548.XSHE",   # 博创科技
        "300570.XSHE",   # 太辰光
        "603083.XSHG",   # 剑桥科技
        # ===== 存储/芯片 =====
        "603986.XSHG",   # 兆易创新
        "688525.XSHG",   # 佰维存储
        "301308.XSHE",   # 江波龙
        "001309.XSHE",   # 德明利
        "688008.XSHG",   # 澜起科技
        "300475.XSHE",   # 香农芯创
        "688110.XSHG",   # 东芯股份
        # ===== 航天 =====
        "600118.XSHG",   # 中国卫星
        "600879.XSHG",   # 航天电子
        "002025.XSHE",   # 航天电器
        "688270.XSHG",   # 臻镭科技
        "001270.XSHE",   # 铖昌科技
        # ===== 其他科技 =====
        "002384.XSHE",   # 东山精密（CPO连接器）
        "002475.XSHE",   # 立讯精密
        "300454.XSHE",   # 深信服（存储/AI）
        # ===== 新增股票 =====
        "002407.XSHE",   # 多氟多
        "688981.XSHG",   # 中芯国际
        "301217.XSHE",   # 铜冠铜箔
        "688560.XSHG",   # 明冠新材
        "603601.XSHG",   # 再升科技
        "601869.XSHG",   # 长飞光纤
        "603220.XSHG",   # 中贝通信
    ]
    
    # ==================== 策略参数 ====================
    g.lookback_days = 20      # 动量计算周期（天）
    g.holdings_num = 5        # 持仓数量（Top N）
    g.min_money = 5000        # 最小交易金额
    
    # 风控参数
    g.stop_loss = 0.95        # 固定止损线（亏损5%卖出）
    
    # ==================== 交易时间安排 ====================
    run_daily(rebalance, time='14:50')   # 每日调仓
    run_daily(check_positions, time='09:35')
    
    log.info(f"策略初始化完成，股票池数量: {len(g.stock_pool)}，持仓数: {g.holdings_num}")

# ==================== 动量打分函数 ====================
def calculate_momentum_score(security, lookback):
    """
    计算单只标的的动量得分（年化收益率 * 趋势稳定性R²）
    返回：得分（float），若数据不足返回0
    """
    try:
        prices = attribute_history(security, lookback+10, '1d', ['close'], skip_paused=True, df=False)
        if len(prices['close']) < lookback:
            return 0
        
        price_series = prices['close'][-lookback-1:]
        if len(price_series) < lookback+1:
            return 0
        
        current_data = get_current_data()
        current_price = current_data[security].last_price
        if current_price is None or current_price <= 0:
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
    scores = []
    for stock in g.stock_pool:
        score = calculate_momentum_score(stock, g.lookback_days)
        if score > 0:
            scores.append((stock, score))
    
    if not scores:
        log.warning("无任何标的得分>0，将保持现有持仓不变")
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
    
    order_result = order(security, diff_amount)
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
    if not target_weights:
        log.info("无有效信号，保持现有持仓不变（不做任何交易）")
        return
    
    total_value = context.portfolio.total_value
    
    # 卖出不在目标中的持仓
    current_holdings = list(context.portfolio.positions.keys())
    for sec in current_holdings:
        if sec not in target_weights:
            smart_order_target_value(context, sec, 0)
    
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