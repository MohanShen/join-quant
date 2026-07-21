# Clone from JoinQuant
# postId: 6ad9025212970ab32023c589c3bb5329
# backtestId: 6e623bcb274de232a22805cf3839a6e0
# title: 巴菲特量化交易策略 V1.1

# 巴菲特量化交易策略 
# 版本：V1.2
# 作者：星
# 创建日期：2025-10-16
# 最后修改：2025-10-18
# 修改：修正财务数据获取错误

import pandas as pd
import numpy as np
from jqdata import *
from datetime import datetime, timedelta

class ValueInvestmentStrategy:
    """价值投资策略核心类"""
    
    def __init__(self):
        """初始化策略参数"""
        self.month_counter = 0
        self.trading_frequency = 12  # 交易频率（月）
        self.max_positions = 3       # 最大持仓数量
        self.financial_data_years = 10  # 财务数据回溯年限
        
        # 价值投资筛选标准
        self.quality_criteria = {
            'min_roe': 20,           # 最小ROE要求（%）
            'min_gross_margin': 40,  # 最小毛利率要求（%）
            'min_net_margin': 5,     # 最小净利率要求（%）
            'max_pe_ratio': 20,      # 最大市盈率要求
            'sell_pe_threshold': 40  # 卖出市盈率阈值
        }

def get_available_financial_date(context):
    """
    获取当前可用的最新财务报告日期
    修正：返回正确的statDate格式
    """
    current_date = context.current_dt.date()
    current_year = current_date.year
    current_month = current_date.month
    
    # 判断当前可用的最新财务报告期
    if current_month < 5:  # 1-4月，使用前年年度报告
        available_year = current_year - 2
        report_period = str(available_year)  # 年度报告使用年份字符串
        report_type = "annual"
    elif current_month < 9:  # 5-8月，使用上年年度报告
        available_year = current_year - 1
        report_period = str(available_year)  # 年度报告使用年份字符串
        report_type = "annual"
    elif current_month < 11:  # 9-10月，使用本年中期报告
        available_year = current_year
        report_period = f"{available_year}q2"  # 中期报告使用季度格式
        report_type = "interim"
    else:  # 11-12月，使用本年三季度报告
        available_year = current_year
        report_period = f"{available_year}q3"  # 三季度报告使用季度格式
        report_type = "interim"
    
    log_message(f'当前可用财务报告期: {report_period} ({report_type})')
    return report_period, report_type

def screen_high_quality_stocks(context):
    """
    筛选连续多年符合财务质量标准的股票
    修正：使用正确的statDate参数格式
    """
    strategy = context.strategy
    current_date = context.current_dt.date()
    quality_tracker = {}
    
    # 获取当前可用的最新财务报告期
    current_report_period, _ = get_available_financial_date(context)
    
    # 确定起始年份（如果是季度格式，提取年份）
    if 'q' in current_report_period:
        current_report_year = int(current_report_period.split('q')[0])
    else:
        current_report_year = int(current_report_period)
    
    # 回溯多年财务数据（使用实际可用的历史数据）
    for years_back in range(1, strategy.financial_data_years + 1):
        historical_year = current_report_year - years_back
        
        # 使用年度报告数据确保一致性（使用年份字符串）
        report_date = str(historical_year)
        
        try:
            # 查询符合质量标准的股票
            quality_query = query(
                valuation.code,
                indicator.roe,
                indicator.gross_profit_margin,
                indicator.net_profit_to_total_revenue
            ).filter(
                indicator.roe > strategy.quality_criteria['min_roe'],
                indicator.gross_profit_margin > strategy.quality_criteria['min_gross_margin'],
                indicator.net_profit_to_total_revenue > strategy.quality_criteria['min_net_margin']
            )
            
            # 使用具体的报告年份获取财务数据
            quality_stocks_data = get_fundamentals(quality_query, statDate=report_date)
            
            if not quality_stocks_data.empty:
                quality_stocks_list = list(quality_stocks_data['code'])
                
                # 统计连续达标年份
                for stock in quality_stocks_list:
                    quality_tracker[stock] = quality_tracker.get(stock, 0) + 1
                    
        except Exception as e:
            log_message(f"获取{historical_year}年财务数据时出错: {e}")
            continue
    
    # 筛选连续多年达标的优质股票（允许部分年份缺失）
    min_continuous_years = max(1, strategy.financial_data_years - 2)  # 至少需要1年，允许最多缺失2年
    consistently_quality_stocks = [
        stock for stock, years_count in quality_tracker.items()
        if years_count >= min_continuous_years
    ]
    
    log_message(f'连续{min_continuous_years}年以上财务达标股票数量: {len(consistently_quality_stocks)}')
    
    return consistently_quality_stocks

def find_value_investment_opportunities(context, quality_stocks):
    """
    从优质股票中寻找价值投资机会（低市盈率）
    """
    strategy = context.strategy
    
    if not quality_stocks:
        return []
    
    # 使用当前日期查询实时估值数据（无未来函数）
    value_query = query(
        valuation.code,
        valuation.pe_ratio,
        valuation.pb_ratio
    ).filter(
        valuation.pe_ratio > 0,
        valuation.pe_ratio < strategy.quality_criteria['max_pe_ratio'],
        valuation.code.in_(quality_stocks)
    ).order_by(valuation.pe_ratio.asc())
    
    value_stocks_data = get_fundamentals(value_query)
    
    if value_stocks_data.empty:
        return []
    
    # 返回按市盈率排序的股票列表
    return list(value_stocks_data['code'])

def get_current_financial_metrics(context, stock_code):
    """
    获取当前财务指标（使用可用的最新财务数据）
    """
    # 获取可用的财务报告期
    report_period, _ = get_available_financial_date(context)
    
    metrics_query = query(
        indicator.roe,
        indicator.gross_profit_margin,
        indicator.net_profit_to_total_revenue
    ).filter(valuation.code == stock_code)
    
    metrics_data = get_fundamentals(metrics_query, statDate=report_period)
    
    if not metrics_data.empty:
        return {
            'roe': metrics_data['roe'][0],
            'gross_margin': metrics_data['gross_profit_margin'][0],
            'net_margin': metrics_data['net_profit_to_total_revenue'][0],
            'report_date': report_period
        }
    
    return None

def initialize_strategy(context):
    """
    策略初始化配置
    设置交易环境、成本参数和运行周期
    """
    # 配置全局策略对象
    context.strategy = ValueInvestmentStrategy()
    
    # 设置基准指数为沪深300
    set_benchmark('000300.XSHG')
    
    # 配置交易环境
    configure_trading_environment(context)
    
    # 每月初执行主交易逻辑
    run_monthly(execute_trading_logic, 1, time='9:30')
    
    log_message('价值投资策略初始化完成')

def configure_trading_environment(context):
    """
    配置交易环境参数
    """
    # 设置固定滑点
    set_slippage(FixedSlippage(0.02))
    
    # 启用真实价格模式
    set_option('use_real_price', True)
    
    # 配置交易成本
    trading_costs = OrderCost(
        open_tax=0,
        close_tax=0.001,
        open_commission=2.5/10000,
        close_commission=2.5/10000,
        close_today_commission=0,
        min_commission=5
    )
    set_order_cost(trading_costs, type='stock')

def execute_trading_logic(context):
    """
    执行月度交易逻辑
    包含股票筛选、买卖决策和持仓管理
    """
    strategy = context.strategy
    
    # 筛选高质量股票池
    quality_stocks = screen_high_quality_stocks(context)
    
    # 从优质股票中寻找价值标的
    value_opportunities = find_value_investment_opportunities(context, quality_stocks)
    
    # 执行投资组合调整
    rebalance_portfolio(context, quality_stocks, value_opportunities)
    
    # 生成月度持仓报告
    generate_monthly_portfolio_report(context)
    
    # 更新月份计数器
    strategy.month_counter += 1

def rebalance_portfolio(context, quality_stocks, value_opportunities):
    """
    调整投资组合：卖出不符合标准的持仓，买入新的价值标的
    """
    strategy = context.strategy
    
    # 检查是否到达调仓周期
    if strategy.month_counter % strategy.trading_frequency != 0:
        return
    
    # 执行卖出逻辑
    execute_sell_decisions(context, quality_stocks)
    
    # 执行买入逻辑
    execute_buy_decisions(context, value_opportunities)
    
    # 重置月份计数器
    strategy.month_counter = 0

def execute_sell_decisions(context, quality_stocks):
    """
    执行卖出决策：卖出高市盈率或不再符合质量标准的股票
    """
    strategy = context.strategy
    current_positions = list(context.portfolio.positions.keys())
    
    for position_stock in current_positions:
        should_sell = False
        reason = ""
        
        # 检查市盈率是否过高
        current_pe = get_stock_valuation(position_stock, context.current_dt.date())
        if current_pe > strategy.quality_criteria['sell_pe_threshold']:
            should_sell = True
            reason = "市盈率过高"
        
        # 检查是否仍符合质量标准
        elif position_stock not in quality_stocks:
            should_sell = True
            reason = "不再符合质量标准"
        
        # 执行卖出操作
        if should_sell:
            order_target(position_stock, 0)
            log_message(f'卖出股票: {position_stock}, 原因: {reason}')

def execute_buy_decisions(context, value_opportunities):
    """
    执行买入决策：买入最具价值的股票
    """
    strategy = context.strategy
    
    if not value_opportunities:
        log_message('未找到符合条件的价值投资标的')
        return
    
    # 选择最具价值的几只股票
    top_value_stocks = value_opportunities[:strategy.max_positions]
    
    # 计算每只股票的分配资金
    total_portfolio_value = context.portfolio.total_value
    cash_reserve_ratio = 0.05  # 保留5%现金
    investable_cash = total_portfolio_value * (1 - cash_reserve_ratio)
    cash_per_stock = investable_cash / len(top_value_stocks)
    
    # 执行买入操作
    for stock in top_value_stocks:
        current_price = get_previous_close_price(stock, context.current_dt.date())
        
        if current_price > 0:
            # 计算购买数量（按手为单位）
            shares_to_buy = cash_per_stock / current_price
            lots_to_buy = int(shares_to_buy // 100)  # 向下取整到整手
            
            if lots_to_buy > 0:
                order(stock, lots_to_buy * 100)
                log_message(f'买入股票: {stock}, 手数: {lots_to_buy}, 投资金额: {cash_per_stock:.2f}')
    
    log_message(f'最终投资组合: {top_value_stocks}')

def generate_monthly_portfolio_report(context):
    """
    生成月度持仓详细报告
    """
    print('=' * 80)
    print(f'价值投资组合月度报告 ({context.current_dt.strftime("%Y-%m-%d")})')
    print('=' * 80)
    
    # 获取持仓股票行业信息
    current_positions = context.portfolio.positions
    if current_positions:
        stock_codes = [pos.security for pos in current_positions.values()]
        industry_data = get_industry(security=stock_codes)
    
    # 遍历所有持仓生成详细报告
    portfolio_total_value = 0
    
    for position in current_positions.values():
        stock_code = position.security
        stock_info = get_security_info(stock_code)
        
        # 获取行业信息
        industry_name = "未知行业"
        if stock_code in industry_data:
            industry_name = industry_data[stock_code]['sw_l2']['industry_name']
        
        # 计算持仓收益
        cost_basis = position.avg_cost
        current_price = position.price
        shares_held = position.total_amount
        position_value = position.value
        profit_pct = 100 * (current_price / cost_basis - 1)
        
        portfolio_total_value += position_value
        
        # 获取当前财务指标
        current_pe = get_stock_valuation(stock_code, context.current_dt.date())
        financial_metrics = get_current_financial_metrics(context, stock_code)
        
        # 打印持仓详情
        print(f'股票代码: {stock_code}')
        print(f'股票名称: {stock_info.display_name}')
        print(f'所属行业: {industry_name}')
        print(f'持仓成本: {cost_basis:.2f} 元')
        print(f'当前价格: {current_price:.2f} 元')
        print(f'当前市盈率: {current_pe:.2f}')
        print(f'持仓数量: {shares_held:,} 股')
        print(f'持仓市值: {position_value:,.2f} 元')
        print(f'持仓收益: {profit_pct:+.2f}%')
        
        # 显示财务指标
        if financial_metrics:
            print(f'财务指标 - ROE: {financial_metrics["roe"]:.2f}%, '
                  f'毛利率: {financial_metrics["gross_margin"]:.2f}%, '
                  f'净利率: {financial_metrics["net_margin"]:.2f}%')
            print(f'财务报告期: {financial_metrics["report_date"]}')
        
        print('-' * 60)
    
    # 打印投资组合汇总信息
    print(f'投资组合总资产: {context.portfolio.total_value:,.2f} 元')
    print(f'持仓股票总市值: {portfolio_total_value:,.2f} 元')
    print(f'可用现金: {context.portfolio.cash:,.2f} 元')
    print(f'持仓股票数量: {len(current_positions)} 只')
    print(f'现金比例: {100 * context.portfolio.cash / context.portfolio.total_value:.1f}%')
    print('=' * 80)

def get_stock_valuation(stock_code, date):
    """
    获取指定股票的估值指标（市盈率）
    """
    valuation_query = query(valuation.pe_ratio).filter(valuation.code == stock_code)
    valuation_data = get_fundamentals(valuation_query, date=date)
    
    if not valuation_data.empty:
        return valuation_data['pe_ratio'][0]
    
    return 100  # 默认返回较高值表示估值数据缺失

def get_previous_close_price(stock_code, date):
    """
    获取指定日期前一个交易日的收盘价
    """
    price_data = get_price(
        stock_code, 
        end_date=date, 
        frequency='daily', 
        fields=['close'], 
        skip_paused=True, 
        count=1
    )
    
    if not price_data.empty:
        return price_data['close'][-1]
    
    return 0

def log_message(message):
    """
    统一日志记录函数
    """
    log.info(message)

# 主初始化函数（兼容平台要求）
def initialize(context):
    """
    策略初始化入口函数
    """
    initialize_strategy(context)

# 开盘前运行函数
def before_market_open(context):
    """
    每日开盘前执行
    """
    log_message(f'开盘前准备时间: {context.current_dt.time()}')

# 收盘后运行函数
def after_market_close(context):
    """
    每日收盘后执行
    """
    log_message(f'收盘后处理时间: {context.current_dt.time()}')
    
    # 记录当日成交
    daily_trades = get_trades()
    for trade in daily_trades.values():
        log_message(f'���交记录: {trade}')