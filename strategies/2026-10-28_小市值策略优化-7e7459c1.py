# Clone from JoinQuant
# postId: 7e7459c1b8c9e61330c6d551abc72f2f
# backtestId: 27b63d034a4d1bc6643de09f4dcf0acb
# title: 小市值策略优化

import pandas as pd 
import numpy as np
from jqdata import *
from datetime import datetime, timedelta

def initialize(context):
    # 全局设置
    log.info('策略开始运行')
    log.set_level('order', 'error')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_benchmark('000300.XSHG')
    
    # 优化交易成本设置
    set_order_cost(OrderCost(
        close_tax=0.001, 
        open_commission=0.00025, 
        close_commission=0.00025, 
        min_commission=5
    ), type='stock')
    
    # 优化滑点设置
    set_slippage(PriceRelatedSlippage(0.004))
    
    # 全局变量 - 优化参数
    g.stock_num = 6  # 增加持仓数量以分散风险
    g.max_position_ratio = 0.15  # 单只股票最大仓位
    g.buy_list = []
    g.just_sold = []
    g.high_limit_list = []
    g.previous_total_value = 0  # 记录前一日总资产
    
    # 风险控制参数
    g.stop_loss_rate = 0.08  # 止损比例
    g.take_profit_rate = 0.25  # 止盈比例
    
    # 技术指标参数
    g.ma_short = 20
    g.ma_long = 60
    g.rsi_period = 14
    
    # 优化运行频率
    run_daily(get_stock_list, time='9:15', reference_security='000300.XSHG')
    run_daily(check_risk_control, time='14:30')  # 风险控制检查
    run_daily(check_limit_up, time='14:45') 
    run_monthly(month_filter_stock, 3, time='10:30')  # 调整为每月第3个交易日
    run_monthly(month_trader, 3, time='14:50')
    run_daily(after_trading_end, time='15:10')  # 收盘后更新前一日资产

def month_filter_stock(context):
    """优化的多因子选股策略"""
    dt_last = context.previous_date
    
    # 获取基础股票池
    stocks = get_all_securities('stock', dt_last).index.tolist()
    
    # 多层次过滤
    stocks = filter_kcbj_stock(stocks)
    stocks = filter_st_stock(stocks)
    stocks = filter_paused_stock(stocks)
    stocks = filter_recently_listed(stocks, dt_last)  # 过滤新股
    
    if len(stocks) == 0:
        log.warn("没有符合条件的股票")
        g.buy_list = []
        return
    
    # 多因子综合选股
    fundamental_list = get_fundamental_factors(context, stocks)
    technical_list = get_technical_factors(context, stocks)
    momentum_list = get_momentum_factors(context, stocks)
    
    # 综合评分
    scored_stocks = score_stocks(fundamental_list, technical_list, momentum_list)
    
    # 最终过滤
    final_list = filter_final_stocks(context, scored_stocks)
    g.buy_list = final_list[:g.stock_num * 2]  # 保留备选池
    
    # 记录选股结果
    if len(g.buy_list) > 0:
        stock_names = [get_security_info(stock).display_name for stock in g.buy_list[:min(5, len(g.buy_list))]]
        log.info("本月选股列表前5只: {}".format(stock_names))

def get_fundamental_factors(context, stocks):
    """基本面因子选股 - 修复字段名称"""
    # 使用正确的聚宽财务指标字段名称
    q = query(
        valuation.code,
        valuation.market_cap,
        valuation.pe_ratio,
        valuation.pb_ratio,
        valuation.ps_ratio,
        indicator.roe,
        indicator.net_profit_margin,
        indicator.inc_net_profit_year_on_year,
        indicator.inc_revenue_year_on_year,  # 修正：营业收入同比增长率
        indicator.eps
    ).filter(
        valuation.code.in_(stocks),
        valuation.pe_ratio > 0,
        valuation.pe_ratio < 50,
        valuation.pb_ratio > 0.5,
        valuation.pb_ratio < 8,
        indicator.roe > 5,
        indicator.inc_net_profit_year_on_year > -100  # 允许小幅负增长但排除大幅亏损
    )
    
    df = get_fundamentals(q, date=context.previous_date)
    if df is None or len(df) == 0:
        return []
    
    # 因子计算和标准化
    factors = {}
    for stock in df.code:
        stock_data = df[df.code == stock].iloc[0]
        
        # 估值因子 (越低越好)
        pe_score = 1 / max(stock_data.pe_ratio, 1)
        pb_score = 1 / max(stock_data.pb_ratio, 0.1)
        
        # 盈利因子 (越高越好)
        roe_score = stock_data.roe / 100
        profit_margin_score = stock_data.net_profit_margin / 100
        
        # 成长因子
        profit_growth_score = min(max(stock_data.inc_net_profit_year_on_year / 100, -1), 2)  # 限制在-100%到200%之间
        revenue_growth_score = min(max(stock_data.inc_revenue_year_on_year / 100, -1), 2)  # 修正字段
        
        # 质量因子
        eps_score = stock_data.eps / max(abs(stock_data.eps), 0.1)
        
        # 综合基本面得分
        fundamental_score = (
            pe_score * 0.2 + pb_score * 0.15 + roe_score * 0.2 + 
            profit_margin_score * 0.15 + profit_growth_score * 0.15 + 
            revenue_growth_score * 0.1 + eps_score * 0.05
        )
        
        factors[stock] = fundamental_score
    
    # 按得分排序
    sorted_stocks = sorted(factors.items(), key=lambda x: x[1], reverse=True)
    return [stock for stock, score in sorted_stocks[:100]]

def get_technical_factors(context, stocks):
    """技术面因子选股"""
    technical_scores = {}
    end_date = context.previous_date
    
    for stock in stocks:
        try:
            # 获取价格数据
            prices = get_price(stock, end_date=end_date, count=g.ma_long + 20, 
                             fields=['close', 'volume'], skip_paused=True)
            if len(prices) < g.ma_long:
                continue
                
            close_prices = prices['close'].values
            volumes = prices['volume'].values
            
            # 移动平均线
            ma_short = np.mean(close_prices[-g.ma_short:])
            ma_long = np.mean(close_prices[-g.ma_long:])
            
            # 价格相对位置
            current_price = close_prices[-1]
            price_ratio = current_price / np.mean(close_prices[-20:])
            
            # 成交量分析
            volume_ma = np.mean(volumes[-20:])
            current_volume = volumes[-1]
            volume_ratio = current_volume / volume_ma if volume_ma > 0 else 1
            
            # 技术得分
            ma_score = 1 if ma_short > ma_long else 0
            price_score = min(price_ratio, 1.2) / 1.2
            volume_score = min(volume_ratio, 2) / 2
            
            technical_score = ma_score * 0.4 + price_score * 0.3 + volume_score * 0.3
            technical_scores[stock] = technical_score
            
        except Exception as e:
            continue
    
    sorted_stocks = sorted(technical_scores.items(), key=lambda x: x[1], reverse=True)
    return [stock for stock, score in sorted_stocks[:80]]

def get_momentum_factors(context, stocks):
    """动量因子选股"""
    momentum_scores = {}
    end_date = context.previous_date
    
    for stock in stocks:
        try:
            # 获取历史价格
            prices = get_price(stock, end_date=end_date, count=120, 
                             fields=['close'], skip_paused=True)
            if len(prices) < 60:
                continue
                
            close_prices = prices['close'].values
            
            # 动量指标
            momentum_1m = close_prices[-1] / close_prices[-20] - 1
            momentum_3m = close_prices[-1] / close_prices[-60] - 1
            
            # 波动率调整动量
            returns = np.diff(close_prices) / close_prices[:-1]
            volatility = np.std(returns[-60:]) if len(returns) >= 60 else 0.1
            
            # 动量得分 (考虑不同时间周期)
            momentum_score = (
                max(min(momentum_1m / max(volatility, 0.01), 2), -1) * 0.6 +
                max(min(momentum_3m / max(volatility, 0.01), 2), -1) * 0.4
            )
            
            momentum_scores[stock] = momentum_score
            
        except Exception as e:
            continue
    
    sorted_stocks = sorted(momentum_scores.items(), key=lambda x: x[1], reverse=True)
    return [stock for stock, score in sorted_stocks[:60]]

def score_stocks(fundamental_list, technical_list, momentum_list):
    """综合评分排序"""
    scores = {}
    
    # 为每个列表中的股票分配分数
    for i, stock in enumerate(fundamental_list):
        scores[stock] = scores.get(stock, 0) + (len(fundamental_list) - i) * 0.4
        
    for i, stock in enumerate(technical_list):
        scores[stock] = scores.get(stock, 0) + (len(technical_list) - i) * 0.35
        
    for i, stock in enumerate(momentum_list):
        scores[stock] = scores.get(stock, 0) + (len(momentum_list) - i) * 0.25
    
    # 按综合得分排序
    sorted_stocks = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [stock for stock, score in sorted_stocks]

def filter_final_stocks(context, stock_list):
    """最终过滤条件 - 修复volume属性错误"""
    filtered_list = []
    
    for stock in stock_list:
        try:
            current_data = get_current_data()
            
            # 价格过滤 - 使用前一日收盘价
            hist_price = get_price(stock, end_date=context.previous_date, count=1, fields=['close'])
            if len(hist_price) == 0:
                continue
                
            last_price = hist_price['close'][-1]
            if last_price >= 10:  # 过滤高价股
                continue
                
            # 流动性过滤 - 使用前一日成交额
            hist_data = get_price(stock, end_date=context.previous_date, count=1, fields=['close', 'volume'])
            if len(hist_data) == 0:
                continue
                
            last_volume = hist_data['volume'][-1]
            last_close = hist_data['close'][-1]
            turnover = last_close * last_volume
            
            if turnover < 10000000:  # 日成交额小于1000万
                continue
                
            # 排除近期大幅上涨的股票
            hist_20 = get_price(stock, end_date=context.previous_date, count=20, fields='close')
            if len(hist_20) >= 20:
                recent_return = hist_20['close'][-1] / hist_20['close'][0] - 1
                if recent_return > 0.3:  # 近期涨幅超过30%
                    continue
                    
            filtered_list.append(stock)
            
        except Exception as e:
            log.warn("过滤股票{}时出错: {}".format(stock, str(e)))
            continue
            
    return filtered_list[:g.stock_num]

def month_trader(context):
    """优化的交易执行"""
    g.just_sold = []
    cdata = get_current_data()
    buy_list = g.buy_list
    
    # 卖出逻辑优化
    for stock in list(context.portfolio.positions.keys()):
        position = context.portfolio.positions[stock]
        
        # 卖出条件：不在买入列表或触发风险控制
        should_sell = (
            stock not in buy_list or
            check_stop_loss(context, stock) or
            check_take_profit(context, stock)
        )
        
        if should_sell:
            log.info('卖出: {}, {}'.format(stock, cdata[stock].name))
            order_target(stock, 0)
            g.just_sold.append(stock)
    
    # 买入逻辑优化
    position_count = len(context.portfolio.positions)
    if position_count < g.stock_num and len(buy_list) > 0:
        available_cash = context.portfolio.available_cash
        max_cash_per_stock = available_cash * g.max_position_ratio
        
        for stock in buy_list:
            if stock not in context.portfolio.positions:
                # 检查买入条件
                if check_buy_condition(context, stock):
                    log.info('买入: {}, {}'.format(stock, cdata[stock].name))
                    order_value(stock, max_cash_per_stock)
                    
                    if len(context.portfolio.positions) >= g.stock_num:
                        break

def check_buy_condition(context, stock):
    """检查买入条件"""
    try:
        current_data = get_current_data()
        
        # 基础条件检查
        if (current_data[stock].paused or 
            current_data[stock].is_st or
            'ST' in current_data[stock].name):
            return False
            
        # 价格条件检查
        hist = get_price(stock, end_date=context.previous_date, count=2, fields=['close', 'high_limit'])
        if len(hist) < 2:
            return False
            
        # 排除涨停股
        if hist['close'][-1] >= hist['high_limit'][-1] * 0.998:
            return False
            
        return True
        
    except Exception as e:
        log.warn("检查买入条件时出错: {}".format(str(e)))
        return False

def check_stop_loss(context, stock):
    """止损检查"""
    try:
        position = context.portfolio.positions[stock]
        cost_price = position.avg_cost
        current_price = position.price
        
        # 计算亏损比例
        loss_ratio = (cost_price - current_price) / cost_price
        
        if loss_ratio >= g.stop_loss_rate:
            log.info("触发止损: {}, 亏损比例: {:.2%}".format(stock, loss_ratio))
            return True
            
    except Exception as e:
        log.warn("检查止损时出错: {}".format(str(e)))
        
    return False

def check_take_profit(context, stock):
    """止盈检查"""
    try:
        position = context.portfolio.positions[stock]
        cost_price = position.avg_cost
        current_price = position.price
        
        # 计算盈利比例
        profit_ratio = (current_price - cost_price) / cost_price
        
        if profit_ratio >= g.take_profit_rate:
            log.info("触发止盈: {}, 盈利比例: {:.2%}".format(stock, profit_ratio))
            return True
            
    except Exception as e:
        log.warn("检查止盈时出错: {}".format(str(e)))
        
    return False

def check_risk_control(context):
    """风险控制检查 - 修复版本"""
    # 检查整体仓位风险
    total_value = context.portfolio.total_value
    if total_value == 0:
        return
    
    # 修复：使用正确的属性来计算当日盈亏
    current_total = context.portfolio.total_value
    if g.previous_total_value > 0:
        daily_return = (current_total - g.previous_total_value) / g.previous_total_value
        if daily_return < -0.03:  # 单日亏损超过3%
            log.warn("单日亏损过大: {:.2%}".format(daily_return))
            # 可以考虑减仓等风险控制措施

def get_stock_list(context):
    """获取股票列表"""
    g.high_limit_list = []
    hold_list = list(context.portfolio.positions.keys())
    
    if hold_list:
        # 修复：正确处理get_price返回的数据结构
        for stock in hold_list:
            try:
                hist = get_price(stock, end_date=context.previous_date, frequency='daily',
                               fields=['close', 'high_limit'], count=1, skip_paused=True)
                if hist is not None and len(hist) > 0:
                    close_price = hist['close'][-1] if hasattr(hist['close'], '__iter__') else hist['close']
                    high_limit = hist['high_limit'][-1] if hasattr(hist['high_limit'], '__iter__') else hist['high_limit']
                    
                    if close_price >= high_limit * 0.998:
                        g.high_limit_list.append(stock)
            except Exception as e:
                log.warn("获取{}价格数据时出错: {}".format(stock, str(e)))
                continue

def check_limit_up(context):
    """检查涨停板"""
    current_data = get_current_data()
    
    # 处理昨日涨停股票
    for stock in g.high_limit_list[:]:
        if stock in context.portfolio.positions:
            current_price = current_data[stock].last_price
            high_limit = current_data[stock].high_limit
            
            # 涨停打开且下跌一定幅度时卖出
            if current_price < high_limit * 0.99:
                log.info("涨停打开卖出: {}".format(stock))
                order_target(stock, 0)
                g.just_sold.append(stock)
                g.high_limit_list.remove(stock)
    
    # 补仓逻辑
    position_count = len(context.portfolio.positions)
    if position_count < g.stock_num and position_count > 0:
        month_filter_stock(context)
        available_cash = context.portfolio.available_cash
        max_cash_per_stock = available_cash * g.max_position_ratio / (g.stock_num - position_count)
        
        for stock in g.buy_list:
            if (stock not in context.portfolio.positions and 
                stock not in g.just_sold and
                check_buy_condition(context, stock)):
                
                log.info("补仓买入: {}".format(stock))
                order_value(stock, max_cash_per_stock)
                
                if len(context.portfolio.positions) >= g.stock_num:
                    break

def after_trading_end(context):
    """收盘后处理"""
    # 更新前一日总资产
    g.previous_total_value = context.portfolio.total_value
    log.info("当日总资产: {:.2f}".format(context.portfolio.total_value))

# 辅助过滤函数
def filter_kcbj_stock(stock_list):
    """过滤科创板和北交所股票"""
    return [stock for stock in stock_list 
            if not (stock.startswith('4') or stock.startswith('8') or stock.startswith('68'))]

def filter_st_stock(stock_list):
    """过滤ST股票"""
    current_data = get_current_data()
    filtered_stocks = []
    for stock in stock_list:
        try:
            if (not current_data[stock].is_st and
                'ST' not in current_data[stock].name and
                '*' not in current_data[stock].name and
                '退' not in current_data[stock].name):
                filtered_stocks.append(stock)
        except:
            continue
    return filtered_stocks

def filter_paused_stock(stock_list):
    """过滤停牌股票"""
    current_data = get_current_data()
    filtered_stocks = []
    for stock in stock_list:
        try:
            if not current_data[stock].paused:
                filtered_stocks.append(stock)
        except:
            continue
    return filtered_stocks

def filter_recently_listed(stock_list, date, days=60):
    """过滤新股"""
    result = []
    for stock in stock_list:
        try:
            security_info = get_security_info(stock)
            if security_info is None:
                continue
            start_date = security_info.start_date
            if start_date is None:
                continue
            days_listed = (date - start_date).days
            if days_listed >= days:
                result.append(stock)
        except Exception as e:
            continue
    return result