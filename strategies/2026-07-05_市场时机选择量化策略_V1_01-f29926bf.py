# Clone from JoinQuant
# postId: f29926bf64c02366205efcd849aceedc
# backtestId: ef2bd38df44e433865d718b85e904e06
# title: 市场时机选择量化策略 V1.01

# 市场时机选择量化策略 - 技术指标驱动版本
# 主要功能：
# 版本：1.01
# 最后更新：2025-11-19

import numpy as np
import statsmodels.api as sm

# 全局参数配置字典
global_params = {
    'regression_window': 18,           # 回归分析窗口期
    'normalization_period': 300,       # 标准化计算周期
    'entry_threshold': 0.7,            # 进场信号阈值
    'exit_threshold': -0.7,            # 离场信号阈值
    'target_security': '000300.XSHG',  # 目标交易标的
    'slope_history': [],               # 斜率历史数据存储
    'determination_coeffs': [],        # 决定系数存储
    'data_ready': False                # 数据准备状态标志
}

def initialize(context):
    """
    策略初始化函数
    在策略开始运行时执行一次，完成基础配置工作
    """
    # 设定业绩比较基准
    set_benchmark('000300.XSHG')
    
    # 启用真实价格模式
    set_option('use_real_price', True)
    
    # 配置交易成本参数
    set_order_cost(OrderCost(
        close_tax=0.001,          # 卖出印花税
        open_commission=0.0003,   # 买入佣金
        close_commission=0.0003,  # 卖出佣金
        min_commission=5          # 最低佣金
    ), type='stock')
    
    # 注册每日运行函数
    run_daily(market_open, time='open')
    run_daily(market_close, time='after_close')
    
    # 记录初始化完成信息
    log.info('量化策略初始化流程完成')

def market_open(context):
    """
    市场开盘执行函数
    每个交易日开盘时自动调用，包含主要交易逻辑
    """
    security = global_params['target_security']
    available_capital = context.portfolio.available_cash
    
    # 首次运行时的数据初始化
    if not global_params['data_ready']:
        prepare_historical_data(context)
        global_params['data_ready'] = True
        log.info("历史数据准备完成，累计{}个数据点".format(len(global_params['slope_history'])))
        return
    
    # 检查是否有足够的历史数据
    if len(global_params['slope_history']) < global_params['normalization_period']:
        log.warning("历史数据不足，需要积累更多数据，当前{}/{}".format(
            len(global_params['slope_history']), global_params['normalization_period']))
        # 继续计算当前指标但不交易
        calculate_current_indicator(context, security)
        return
    
    # 获取近期价格序列
    price_data = attribute_history(security, global_params['regression_window'], '1d', ['high', 'low'])
    if price_data is None or len(price_data) < global_params['regression_window']:
        log.warning("价格数据获取异常或数据量不足")
        return
        
    high_prices = price_data['high']
    low_prices = price_data['low']
    
    # 计算技术指标
    try:
        # 准备回归分析数据
        explanatory_var = sm.add_constant(low_prices)
        regression_model = sm.OLS(high_prices, explanatory_var)
        regression_results = regression_model.fit()
        
        # 提取回归系数
        current_slope = regression_results.params[1]
        current_r2 = regression_results.rsquared
        
        # 更新历史数据集
        global_params['slope_history'].append(current_slope)
        global_params['determination_coeffs'].append(current_r2)
        
        # 计算综合技术评分
        technical_score = compute_technical_score(current_slope, current_r2)
        
        # 输出技术指标信息
        log.info("技术指标分析 - 斜率系数: {:.4f}, 拟合优度: {:.4f}, 综合评分: {:.4f}".format(
            current_slope, current_r2, technical_score))
        
        # 执行交易决策
        make_trading_decision(context, security, available_capital, technical_score)
        
    except Exception as error:
        log.error("技术指标计算过程中发生错误: {}".format(error))

def calculate_current_indicator(context, security):
    """
    计算当前技术指标但不进行交易
    用于数据积累期间
    """
    # 获取近期价格序列
    price_data = attribute_history(security, global_params['regression_window'], '1d', ['high', 'low'])
    if price_data is None or len(price_data) < global_params['regression_window']:
        return
        
    high_prices = price_data['high']
    low_prices = price_data['low']
    
    try:
        # 准备回归分析数据
        explanatory_var = sm.add_constant(low_prices)
        regression_model = sm.OLS(high_prices, explanatory_var)
        regression_results = regression_model.fit()
        
        # 提取回归系数
        current_slope = regression_results.params[1]
        current_r2 = regression_results.rsquared
        
        # 更新历史数据集
        global_params['slope_history'].append(current_slope)
        global_params['determination_coeffs'].append(current_r2)
        
        log.info("数据积累中 - 当前斜率: {:.4f}, 累计数据: {}/{}".format(
            current_slope, len(global_params['slope_history']), global_params['normalization_period']))
        
    except Exception as error:
        log.error("计算技术指标时发生错误: {}".format(error))

def prepare_historical_data(context):
    """
    历史数据准备函数
    从历史数据中计算初始技术指标值
    """
    # 计算回测开始前足够长的历史数据期间
    # 使用回测开始日期前推足够天数来获取历史数据
    start_date = '2010-01-01'  # 使用更早的日期确保有足够数据
    
    # 获取历史价格数据
    historical_prices = get_price(global_params['target_security'], start_date, 
                                 context.current_dt, '1d', ['high', 'low'])
    
    if historical_prices is None or len(historical_prices) < global_params['regression_window']:
        log.error("历史数据获取失败，获取到的数据条数: {}".format(
            len(historical_prices) if historical_prices is not None else 0))
        return
    
    high_series = historical_prices['high']
    low_series = historical_prices['low']
    
    log.info("成功获取历史数据，总计{}条记录".format(len(high_series)))
    
    # 计算历史技术指标
    calculated_count = 0
    for i in range(global_params['regression_window'], len(high_series)):
        window_highs = high_series.iloc[i-global_params['regression_window']:i]
        window_lows = low_series.iloc[i-global_params['regression_window']:i]
        
        try:
            # 执行回归分析
            explanatory_data = sm.add_constant(window_lows)
            model = sm.OLS(window_highs, explanatory_data)
            results = model.fit()
            
            # 保存计算结果
            global_params['slope_history'].append(results.params[1])
            global_params['determination_coeffs'].append(results.rsquared)
            calculated_count += 1
        except Exception as e:
            log.warning("计算历史数据时出错: {}".format(e))
            continue
    
    log.info("历史技术指标计算完成，成功计算{}条记录".format(calculated_count))

def compute_technical_score(current_slope, current_r2):
    """
    技术评分计算函数
    基于历史数据计算当前技术的标准化评分
    """
    # 检查数据充足性
    if len(global_params['slope_history']) < global_params['normalization_period']:
        return 0.0
    
    # 提取近期数据序列
    recent_slopes = global_params['slope_history'][-global_params['normalization_period']:]
    
    # 计算统计特征
    mean_value = np.mean(recent_slopes)
    std_value = np.std(recent_slopes)
    
    # 处理标准差为零的特殊情况
    if std_value == 0:
        return 0.0
    
    # 计算标准化分数
    z_value = (current_slope - mean_value) / std_value
    
    # 计算综合技术评分
    composite_score = z_value * current_slope * current_r2
    
    return composite_score

def make_trading_decision(context, security, available_cash, technical_score):
    """
    交易决策执行函数
    根据技术评分决定交易操作
    """
    # 获取当前持仓情况
    current_holding = context.portfolio.positions[security].closeable_amount if security in context.portfolio.positions else 0
    
    # 输出决策相关信息
    log.info("交易决策分析 - 技术评分: {:.4f}, 当前持仓: {}, 可用资金: {:.2f}".format(
        technical_score, current_holding, available_cash))
    
    # 进场信号判断
    if technical_score > global_params['entry_threshold']:
        if available_cash > 0:
            log.info("=== 执行进场操作 ===")
            log.info("技术评分 {:.4f} 超过进场阈值 {}".format(technical_score, global_params['entry_threshold']))
            order_value(security, available_cash)
        else:
            log.info("检测到进场信号但可用资金不足")
    
    # 离场信号判断
    elif technical_score < global_params['exit_threshold']:
        if current_holding > 0:
            log.info("=== 执行离场操作 ===")
            log.info("技术评分 {:.4f} 低于离场阈值 {}".format(technical_score, global_params['exit_threshold']))
            order_target(security, 0)
        else:
            log.info("检测到离场信号但无对应持仓")
    
    else:
        log.info("技术评分处于阈值区间内，维持当前状态")

def market_close(context):
    """
    市场收盘执行函数
    每个交易日收盘后自动调用，完成当日总结
    """
    security = global_params['target_security']
    total_assets = context.portfolio.total_value
    available_cash = context.portfolio.available_cash
    current_holding = context.portfolio.positions[security].closeable_amount if security in context.portfolio.positions else 0
    
    # 输出当日资产概况
    log.info("当日交易总结 - 总资产价值: {:.2f}, 可用资金: {:.2f}, {}持仓数量: {}".format(
        total_assets, available_cash, security, current_holding))
    
    # 记录当日成交详情
    trade_records = get_trades()
    if trade_records:
        for trade in trade_records.values():
            log.info('成交详情记录: {}'.format(trade))