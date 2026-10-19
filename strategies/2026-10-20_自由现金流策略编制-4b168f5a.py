# Clone from JoinQuant
# postId: 4b168f5aa530c847a8d5a04f69f5f1af
# backtestId: 5ebe91487a5ab72cedf170cc4e08a950
# title: 自由现金流策略编制

from jqdata import *
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import statsmodels.api as sm
from sklearn.linear_model import LinearRegression

# 初始化函数
def initialize(context):
    # 设置基准
    set_benchmark('000300.XSHG')
    
    # 设置滑点
    set_slippage(FixedSlippage(0.001))
    
    # 设置佣金
    set_order_cost(OrderCost(
        open_tax=0,
        close_tax=0.001,
        open_commission=0.0003,
        close_commission=0.0003,
        close_today_commission=0,
        min_commission=5
    ), type='stock')
    
    # 设置交易参数 - 简化版本
    g.stock_num = 50
    g.exclude_st = True
    g.industry_classification = 'sw1'
    g.winsorize_nstd = 3
    g.min_listing_days = 365
    
    # 优化参数
    g.exclude_finance_real_estate = False
    g.rebalance_frequency = 'monthly'
    g.weight_method = 'equal_weight'
    
    # 因子设置 - 只使用FCF/EV因子
    g.only_fcf_ev = True
    g.min_stocks_for_trading = 20  # 最小交易股票数
    
    # 设置调仓频率
    if g.rebalance_frequency == 'monthly':
        run_monthly(rebalance, 1, time='9:30')
    else:
        run_weekly(rebalance, weekday=1, time='9:30')
    
    # 月度报告
    run_monthly(log_portfolio_info, 1, time='9:00')
    
    # 初始化性能跟踪
    g.peak_value = 0
    g.max_drawdown = 0
    g.daily_returns = []

# 主调仓函数 - 单因子FCF/EV版本
def rebalance(context):
    log.info(f"\n{'='*60}")
    log.info(f"开始调仓: {context.current_dt}")
    
    # 1. 获取基础股票池
    stock_list = get_initial_stock_pool(context)
    log.info(f"初始股票池数量: {len(stock_list)}")
    
    if len(stock_list) < 100:
        log.warning(f"候选股票数量不足: {len(stock_list)}")
        return
    
    # 2. 获取财务数据
    factor_data = get_factors_data_simple(stock_list, context.current_dt)
    log.info(f"获取到财务数据数量: {len(factor_data)}")
    
    if factor_data.empty or len(factor_data) < 30:
        log.warning(f"有效财务数据不足: {len(factor_data)}")
        return
    
    # 3. 计算FCF/EV因子
    fcf_ev_raw = calculate_fcf_ev_factor_simple(factor_data)
    log.info(f"FCF/EV因子有效值: {len(fcf_ev_raw.dropna())}")
    
    if len(fcf_ev_raw.dropna()) < g.min_stocks_for_trading:
        log.warning(f"有效因子数据不足")
        return
    
    # 4. 异常值处理
    fcf_ev_clean = winsorize_factor(fcf_ev_raw, g.winsorize_nstd)
    
    # 5. 因子标准化
    fcf_ev_std = standardize_cross_sectional(fcf_ev_clean)
    
    if fcf_ev_std.empty or len(fcf_ev_std) < g.min_stocks_for_trading:
        log.warning(f"标准化后有效因子不足: {len(fcf_ev_std)}")
        return
    
    # 6. 排序选股
    ranked_stocks = fcf_ev_std.sort_values(ascending=False).index.tolist()
    target_stocks = ranked_stocks[:g.stock_num]
    
    log.info(f"选出的目标股票数量: {len(target_stocks)}")
    
    if len(target_stocks) > 0:
        log.info(f"前10只股票及其FCF/EV因子值:")
        for i, stock in enumerate(ranked_stocks[:10]):
            try:
                stock_name = get_security_info(stock).display_name
            except:
                stock_name = stock
            factor_value = fcf_ev_std[stock]
            log.info(f"  {i+1}. {stock_name}({stock}): {factor_value:.4f}")
    
    # 7. 风险管理检查
    if not risk_management_check(context, target_stocks, fcf_ev_std):
        log.warning("风险控制检查未通过，跳过本次调仓")
        return
    
    # 8. 调仓
    adjust_portfolio_equal_weight(context, target_stocks)
    
    # 9. 记录信息
    log_optimization_info_simple(context, target_stocks, fcf_ev_std)
    
    # 10. 记录性能
    monitor_performance(context)

# 获取初始股票池
def get_initial_stock_pool(context):
    """获取初始股票池"""
    all_stocks = get_all_securities(['stock'], date=context.current_dt).index.tolist()
    
    # 排除ST股票
    if g.exclude_st:
        current_data = get_current_data()
        all_stocks = [s for s in all_stocks if not current_data[s].is_st]
    
    # 排除上市时间不足
    valid_stocks = []
    for s in all_stocks:
        try:
            stock_info = get_security_info(s)
            if stock_info and stock_info.start_date:
                current_date = context.current_dt.date() if hasattr(context.current_dt, 'date') else context.current_dt
                start_date = stock_info.start_date
                days_listed = (current_date - start_date).days
                
                if days_listed > g.min_listing_days:
                    valid_stocks.append(s)
        except:
            continue
    
    # 排除停牌股票
    current_data = get_current_data()
    valid_stocks = [s for s in valid_stocks if not current_data[s].paused]
    
    return valid_stocks

# 简化的财务数据获取
def get_factors_data_simple(stock_list, current_date):
    """简化的财务数据获取，避免API问题"""
    if not stock_list:
        return pd.DataFrame()
    
    # 限制数量，避免查询过多
    if len(stock_list) > 500:
        stock_list = stock_list[:500]
    
    # 使用简单的查询，避免复杂的字段
    try:
        q = query(
            valuation.code,
            valuation.market_cap,
            balance.total_liability,
            balance.cash_equivalents,
            income.total_profit,
            income.financial_expense,
            cash_flow.net_operate_cash_flow,
            cash_flow.net_invest_cash_flow
        ).filter(valuation.code.in_(stock_list))
        
        # 使用当前日期
        df = get_fundamentals(q, date=current_date)
        
        if df is None or df.empty:
            log.warning("get_fundamentals返回空数据")
            return pd.DataFrame()
        
        return df
    
    except Exception as e:
        log.error(f"获取财务数据失败: {e}")
        return pd.DataFrame()

# 简化的FCF/EV计算
def calculate_fcf_ev_factor_simple(factor_df):
    """简化的FCF/EV因子计算"""
    if factor_df.empty:
        return pd.Series()
    
    df = factor_df.copy()
    
    # 计算自由现金流
    if 'net_invest_cash_flow' in df.columns:
        df['fcf'] = df['net_operate_cash_flow'] - abs(df['net_invest_cash_flow'])
    else:
        df['fcf'] = df['net_operate_cash_flow']
    
    # 计算企业价值
    df['ev'] = df['market_cap'] + df['total_liability'] - df['cash_equivalents']
    
    # 计算FCF/EV比率
    df['fcf_ev_ratio'] = df.apply(
        lambda row: row['fcf'] / row['ev'] if row['ev'] > 1e-6 else np.nan,
        axis=1
    )
    
    # 移除无效值
    valid_df = df.dropna(subset=['fcf_ev_ratio'])
    
    if len(valid_df) == 0:
        return pd.Series()
    
    return pd.Series(valid_df['fcf_ev_ratio'].values, index=valid_df['code'])

# 异常值处理
def winsorize_factor(factor_series, n_std=3):
    """使用n倍标准差进行截尾处理"""
    if factor_series.empty or len(factor_series) < 3:
        return factor_series
    
    clean_series = factor_series.dropna()
    
    if len(clean_series) < 3:
        return factor_series
    
    mean_val = clean_series.mean()
    std_val = clean_series.std()
    
    if std_val < 1e-8:
        return factor_series
    
    lower_bound = mean_val - n_std * std_val
    upper_bound = mean_val + n_std * std_val
    
    winsorized_series = clean_series.clip(lower_bound, upper_bound)
    
    return winsorized_series

# 横截面Z-score标准化
def standardize_cross_sectional(factor_series):
    """横截面Z-score标准化"""
    if factor_series.empty or len(factor_series) < 2:
        return factor_series
    
    clean_series = factor_series.dropna()
    
    if len(clean_series) < 2:
        return factor_series
    
    mean_val = clean_series.mean()
    std_val = clean_series.std()
    
    if std_val < 1e-8:
        standardized = clean_series - mean_val
    else:
        standardized = (clean_series - mean_val) / std_val
    
    return standardized

# 等权重调仓
def adjust_portfolio_equal_weight(context, target_stocks):
    """等权重调仓"""
    if not target_stocks:
        log.info("目标股票列表为空，清空所有持仓")
        for stock in list(context.portfolio.positions.keys()):
            order_target_value(stock, 0)
        return
    
    current_positions = context.portfolio.positions
    
    log.info(f"当前持仓数量: {len(current_positions)}")
    log.info(f"目标持仓数量: {len(target_stocks)}")
    
    # 卖出不在目标列表中的股票
    sell_count = 0
    for stock in list(current_positions.keys()):
        if stock not in target_stocks:
            order_target_value(stock, 0)
            sell_count += 1
    
    log.info(f"卖出股票数量: {sell_count}")
    
    # 等权重分配资金
    weight = 1.0 / len(target_stocks)
    
    buy_count = 0
    for stock in target_stocks:
        target_value = context.portfolio.total_value * weight
        
        if stock in current_positions:
            position = current_positions[stock]
            current_value = position.total_amount * position.price
        else:
            current_value = 0.0
        
        if abs(target_value - current_value) > target_value * 0.05:
            order_target_value(stock, target_value)
            if target_value > current_value:
                buy_count += 1
    
    log.info(f"买入/调整股票数量: {buy_count}")

# 简化的日志记录
def log_optimization_info_simple(context, target_stocks, factor_series):
    """简化的日志记录"""
    log.info(f"\n{'='*60}")
    log.info("FCF/EV单因子策略执行统计:")
    
    if len(target_stocks) > 0:
        log.info(f"选出股票数量: {len(target_stocks)}")
        
        # 计算平均因子值
        avg_factor = factor_series[target_stocks].mean()
        log.info(f"平均FCF/EV因子值: {avg_factor:.4f}")
        
        # 计算因子分布
        factor_values = factor_series[target_stocks]
        log.info(f"因子值范围: [{factor_values.min():.4f}, {factor_values.max():.4f}]")
        
        # 计算分位数
        quantiles = factor_series[target_stocks].quantile([0.25, 0.5, 0.75])
        log.info(f"25%分位数: {quantiles.iloc[0]:.4f}")
        log.info(f"中位数: {quantiles.iloc[1]:.4f}")
        log.info(f"75%分位数: {quantiles.iloc[2]:.4f}")

# 月度组合报告
def log_portfolio_info(context):
    """月度组合信息报告"""
    positions = context.portfolio.positions
    
    if len(positions) > 0:
        log.info(f"\n{'='*60}")
        log.info(f"月度组合报告 - {context.current_dt}")
        log.info(f"总资产: {context.portfolio.total_value:,.2f}元")
        log.info(f"现金: {context.portfolio.cash:,.2f}元")
        log.info(f"持仓股票数量: {len(positions)}")
        
        # 显示持仓前5只股票
        log.info("前5大持仓:")
        for i, (stock, position) in enumerate(list(positions.items())[:5]):
            try:
                stock_name = get_security_info(stock).display_name
            except:
                stock_name = stock
            value = position.total_amount * position.price
            weight = value / context.portfolio.total_value
            log.info(f"  {i+1}. {stock_name}: {value:,.2f}元 ({weight:.2%})")

# 风险管理检查
def risk_management_check(context, target_stocks, factor_series):
    """风险管理检查"""
    if len(target_stocks) < 10:
        log.warning("目标股票数少于10只，风险过高")
        return False
    
    # 检查因子值分布
    factor_values = factor_series[target_stocks]
    factor_std = factor_values.std()
    
    if factor_std < 0.1:  # 因子分散度不足
        log.warning(f"因子分散度不足: 标准差={factor_std:.4f}")
        return False
    
    # 检查当前持仓质量
    current_positions = context.portfolio.positions
    if current_positions:
        # 计算当前持仓的平均因子值
        current_factors = []
        for stock in current_positions.keys():
            if stock in factor_series.index:
                current_factors.append(factor_series[stock])
        
        if current_factors:
            avg_current_factor = np.mean(current_factors)
            avg_target_factor = factor_series[target_stocks].mean()
            
            # 如果新选股票因子值比当前持仓差很多，不调仓
            if avg_target_factor < avg_current_factor * 0.8:
                log.warning(f"新选股票质量不如当前持仓: 当前{avg_current_factor:.4f} vs 目标{avg_target_factor:.4f}")
                return False
    
    return True

# 性能监控
def monitor_performance(context):
    """性能监控"""
    portfolio = context.portfolio
    
    # 计算当日收益率
    if hasattr(g, 'prev_portfolio_value') and g.prev_portfolio_value > 0:
        daily_return = (portfolio.total_value - g.prev_portfolio_value) / g.prev_portfolio_value
        g.daily_returns.append(daily_return)
    
    g.prev_portfolio_value = portfolio.total_value
    
    # 最大回撤跟踪
    if g.peak_value == 0:
        g.peak_value = portfolio.total_value
    
    g.peak_value = max(g.peak_value, portfolio.total_value)
    current_drawdown = (g.peak_value - portfolio.total_value) / g.peak_value
    g.max_drawdown = max(g.max_drawdown, current_drawdown)
    
    # 月度报告时计算夏普比率
    if context.current_dt.day == 1 and len(g.daily_returns) >= 20:
        returns_array = np.array(g.daily_returns[-252:])  # 使用最近252个交易日
        annual_return = np.mean(returns_array) * 252
        annual_volatility = np.std(returns_array) * np.sqrt(252)
        sharpe_ratio = annual_return / annual_volatility if annual_volatility > 0 else 0
        
        log.info(f"年化夏普比率: {sharpe_ratio:.3f}")
        log.info(f"当前最大回撤: {g.max_drawdown:.2%}")

# 每日开盘前运行
def before_trading_start(context):
    pass

# 每日收盘后运行
def after_trading_end(context):
    pass