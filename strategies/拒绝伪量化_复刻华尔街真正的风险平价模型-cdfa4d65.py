# Clone from JoinQuant
# postId: cdfa4d65c1ec714b8c0721928e055b30
# backtestId: f03b227e7ea71b4b6b1d97b8645e2aa9
# title: 拒绝伪量化！复刻华尔街真正的风险平价模型

import pandas as pd
import numpy as np
from scipy.optimize import minimize

def initialize(context):
    '''
    【全球视野风险平价 (Global Risk Parity)】
    删除了所有画蛇添足的均线过滤。
    通过引入全球低相关性资产（美股/A股/黄金/国债），
    让底层的协方差矩阵自然发力，实现高夏普比率的稳健爬坡。
    '''
    
    # 标的池：
    # 510300: 沪深300 (A股大盘)
    # 159915: 创业板 (A股高弹性)
    # 513100: 纳斯达克100 (美股科技引擎)
    # 518880: 黄金ETF (抗通胀/乱世避险)
    # 511260: 十年期国债 (绝对防御压舱石)
    g.assets = [
        '510300.XSHG', 
        '159915.XSHE', 
        '513100.XSHG', 
        '518880.XSHG', 
        '511260.XSHG'
    ]
    
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_order_cost(OrderCost(close_tax=0, open_commission=0.0001, close_commission=0.0001, min_commission=5), type='fund')
    
    # 恢复月度调仓，减少摩擦成本
    run_monthly(handle_global_risk_parity, monthday=1, time='09:30')

def get_risk_contribution(weights, cov_matrix):
    """纯 NumPy 矩阵计算风险贡献"""
    w = np.array(weights)
    cov = np.array(cov_matrix)
    
    portfolio_var = np.dot(np.dot(w, cov), w)
    portfolio_vol = np.sqrt(portfolio_var)
    
    mrc = np.dot(cov, w) / portfolio_vol
    rc = w * mrc
    return rc

def risk_budget_objective(weights, cov_matrix):
    """目标函数：风险等权配置"""
    num_assets = len(weights)
    target_risk = np.array([1.0 / num_assets] * num_assets)
    
    rc = get_risk_contribution(weights, cov_matrix)
    rc_perc = rc / np.sum(rc)
    
    error = np.sum(np.square(rc_perc - target_risk))
    return error

def handle_global_risk_parity(context):
    log.info("=== 🌐 启动全球大类资产风险平价引擎 ===")
    
    # 获取过去 120 天数据计算波动率与相关性
    prices = history(120, '1d', 'close', g.assets)
    if prices.empty: return
    
    returns = prices.pct_change().dropna()
    if returns.empty: return
    
    # 计算年化协方差矩阵
    cov_matrix = returns.cov().values * 252 
    
    num_assets = len(g.assets)
    init_weights = np.array([1.0 / num_assets] * num_assets)
    bounds = [(0.0, 1.0) for _ in range(num_assets)] 
    constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1.0}) 
    
    res = minimize(risk_budget_objective, init_weights, args=(cov_matrix,),
                   method='SLSQP', constraints=constraints, bounds=bounds)
    
    if res.success:
        target_weights = res.x
        
        # 打印分配结果，你会发现系统会自动压制纳指和创业板的权重，重仓国债
        log.info("🎯 资产权重分配：")
        for i, asset in enumerate(g.assets):
            log.info(f"{asset}: {target_weights[i]:.2%}")
        
        # 精确目标市值调仓
        for i, stock in enumerate(g.assets):
            target_value = context.portfolio.total_value * target_weights[i]
            order_target_value(stock, target_value)
    else:
        log.error("优化求解失败，本月维持原仓位。")