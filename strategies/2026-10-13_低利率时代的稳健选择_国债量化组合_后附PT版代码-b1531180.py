# Clone from JoinQuant
# postId: b1531180d2a053730269362207ece435
# backtestId: a7146bf77abdab6540399cc02d4eea3b
# title: 低利率时代的稳健选择：国债量化组合（后附PT版代码）

# 国债核心策略 - 聚宽版本（已修复本地环境兼容性问题）

def initialize(context):
    # 策略参数
    g.rebalance_day = 1           # 每月调仓日（1号）
    g.last_rebalance_month = -1
    
    # 资产配置比例（四类ETF）
    g.target_weights = {
        "511260.XSHG": 0.40,      # 国债ETF
        "510880.XSHG": 0.20,      # 红利ETF
        "513100.XSHG": 0.20,      # 纳指ETF
        "518880.XSHG": 0.20,      # 黄金ETF
    }
    
    # 设置基准
    set_benchmark("000300.XSHG")
    
    # 设置ETF手续费：佣金万分之一，最低5元
    set_order_cost(OrderCost(open_commission=0.0001, close_commission=0.0001, min_commission=5), type='etf')
    
    # 启用真实价格模式
    set_option('use_real_price', True)
    
    # 定时任务
    run_daily(rebalance_portfolio, time='09:35')
    
    log.info("策略初始化完成")

def rebalance_portfolio(context):
    """月度再平衡 - 先卖出后买入"""
    current_dt = context.current_dt
    today = current_dt.date()
    
    if today.day != g.rebalance_day:
        return
    if current_dt.month == g.last_rebalance_month:
        return
    g.last_rebalance_month = current_dt.month
    
    log.info(f"===== 执行月度再平衡: {today} =====")
    total_value = context.portfolio.portfolio_value
    
    orders = []
    for etf, weight in g.target_weights.items():
        target_value = total_value * weight
        current_position = context.portfolio.positions.get(etf)
        
        # ====== 这里是修改的关键 ======
        # 原代码: current_value = current_position.market_value if current_position else 0
        # 新代码: 手动计算市值，以兼容不同的聚宽环境版本
        current_value = current_position.amount * current_position.price if current_position else 0
        # ==========================
        
        diff = target_value - current_value
        orders.append((etf, diff, target_value))
        log.info(f"{etf} 当前:{current_value:.2f} 目标:{target_value:.2f} 差额:{diff:+.2f}")
    
    # 先卖
    for etf, diff, target in orders:
        if diff < 0:
            log.info(f"卖出 {etf} 金额: {-diff:.2f}")
            order_target_value(etf, target)
    
    # 后买
    for etf, diff, target in orders:
        if diff > 0:
            log.info(f"买入 {etf} 金额: {diff:.2f}")
            order_target_value(etf, target)
    
    log.info("月度再平衡完成")

def handle_data(context, data):
    pass

# ===============以下是PT代码==============
# -*- coding: utf-8 -*-
# 国债核心策略 - 优化版（先卖出后买入，解决资金不足问题）

# def initialize(context):
#     # 策略参数
#     g.rebalance_day = 1           # 每月调仓日（1号）
#     g.last_rebalance_month = -1
    
#     # 资产配置比例（四类ETF）
#     g.target_weights = {
#         "511260.XSHG": 0.40,      # 国债ETF
#         "510880.XSHG": 0.20,      # 红利ETF
#         "513100.XSHG": 0.20,      # 纳指ETF
#         "518880.XSHG": 0.20,      # 黄金ETF
#     }
    
#     # 设置基准和手续费
#     set_benchmark("000300.XSHG")
#     set_commission(commission_ratio=0.0001, min_commission=5, type="ETF")
    
#     # 定时任务：开盘后执行再平衡（避免盘中剧烈波动）
#     run_daily(context, rebalance_portfolio, time='09:35')
#     # 可选：收盘前自动国债逆回购
#     # run_daily(context, auto_reverse_repo, time='14:57')
    
#     log.info("策略初始化完成")

# def rebalance_portfolio(context):
#     """月度再平衡 - 先卖出后买入"""
#     current_dt = context.current_dt
#     today = current_dt.date()
    
#     # 只在每月指定日期执行
#     if today.day != g.rebalance_day:
#         return
#     # 避免同月重复执行
#     if current_dt.month == g.last_rebalance_month:
#         return
#     g.last_rebalance_month = current_dt.month
    
#     log.info(f"===== 执行月度再平衡: {today} =====")
#     total_value = context.portfolio.portfolio_value
    
#     # 计算每个标的的目标市值和差值
#     orders = []
#     for etf, weight in g.target_weights.items():
#         target_value = total_value * weight
#         current_position = context.portfolio.positions.get(etf)
#         current_value = current_position.market_value if current_position else 0
#         diff = target_value - current_value
#         orders.append((etf, diff, target_value))
#         log.info(f"{etf} 当前:{current_value:.2f} 目标:{target_value:.2f} 差额:{diff:+.2f}")
    
#     # 第一步：执行卖出 （差额为负，调减）
#     for etf, diff, target in orders:
#         if diff < 0:
#             # 卖出需要调减的部分（使用目标市值卖出）
#             log.info(f"卖出 {etf} 金额: {-diff:.2f}")
#             order_target_value(etf, target)
    
#     # 等待委托送达（可休眠0.1秒，但回测中无需）
#     # 实盘可适当加短暂等待，回测会自动按顺序模拟
    
#     # 第二步：执行买入 （差额为正，调增）
#     for etf, diff, target in orders:
#         if diff > 0:
#             log.info(f"买入 {etf} 金额: {diff:.2f}")
#             order_target_value(etf, target)
    
#     log.info("月度再平衡完成")

# def auto_reverse_repo(context):
#     """可选：收盘前自动1天期国债逆回购"""
#     # 保留一定现金以备次日交易
#     reserve_cash = 2000.0
#     available = context.portfolio.cash
#     repo_amount = available - reserve_cash
#     if repo_amount >= 1000:
#         # 卖出逆回购（方向为卖出）
#         order("204001.SS", -repo_amount)
#         log.info(f"执行逆回购: 金额{repo_amount:.2f}")
#     else:
#         log.debug("无需逆回购")

# def handle_data(context, data):
#     # 无需处理
#     pass