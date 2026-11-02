# Clone from JoinQuant
# postId: 32fca4b938bacbb523477b8b98b38a69
# backtestId: 9dbad7db51255d21fb4bbd05f028882c
# title: 运行回测出现问题。

from jqdata import *
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def initialize(context):
    # 初始化参数
    set_params(context)
    set_backtest()
    init_learning()

def set_params(context):
    # 基础参数
    g.trade_limit = 3                # 每日最大买入数
    g.ma_short, g.ma_long = 5, 60    # 均线周期
    g.position_ratio = 0.1           # 单票仓位比例
    
    # 选股池配置
    g.stock_pool = get_index_stocks('399006.XSHE') + get_index_stocks('000688.XSHG')  # 创业板+科创板
    
    # 市场监控
    g.benchmark = '000300.XSHG'      # 沪深300指数
    g.market_ma_days = 20            # 市场趋势均线
    
    # 学习参数
    g.learn_window = 30              # 学习窗口(天)
    g.win_rate_threshold = 0.6       # 胜率阈值
    g.dynamic_params = {'position_ratio': 0.1, 'ma_short':5}

def set_backtest():
    set_option('use_real_price', True)
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, 
                           open_commission=0.0003, close_commission=0.0003,
                           min_commission=5), type='stock')
    set_benchmark(g.benchmark)

def init_learning():
    g.trade_log = pd.DataFrame(columns=['date','code','profit'])
    g.param_history = []

def handle_data(context, data):
    try:
        # 风控检查
        if not market_safe_check(context):
            return
            
        # 获取市场情绪
        sentiment = market_sentiment_analysis(context)
        
        # 执行交易逻辑
        execute_trading(context, data, sentiment)
        
        # 盘后学习(每周五)
        if context.current_dt.weekday() == 4:
            learning_model_update(context)
            
    except Exception as e:
        log.error(f"主逻辑异常:{str(e)}")

# 核心模块1：市场健康度检查
def market_safe_check(context):
    """三重市场风险过滤"""
    # 1. 指数趋势检查
    index_data = get_price(g.benchmark, count=g.market_ma_days+1, fields=['close'])
    if len(index_data) < g.market_ma_days:
        return False
    ma = index_data.close.rolling(g.market_ma_days).mean().iloc[-1]
    if index_data.close.iloc[-1] < ma * 0.98:
        return False
        
    # 2. 流动性检查
    if get_current_data().money.iloc[-1] < 5e10:  # 全市场成交额<50亿
        return False
        
    # 3. 波动率检查
    returns = index_data.close.pct_change().dropna()
    if returns.std() > 0.03:  # 波动率过高
        return False
        
    return True

# 核心模块2：市场情绪分析
def market_sentiment_analysis(context):
    """实时市场情绪量化"""
    stocks = get_index_stocks('000001.XSHG') + get_index_stocks('399001.XSHE')
    prices = get_price(stocks, count=2, fields=['close'], skip_paused=True)
    
    advance = (prices.xs('close', level=1).iloc[-1] > 
              prices.xs('close', level=1).iloc[-2]).sum()
    decline = (prices.xs('close', level=1).iloc[-1] < 
              prices.xs('close', level=1).iloc[-2]).sum()
    
    limit_up = len([s for s in stocks if get_current_data()[s].is_limit_up])
    
    return {
        'advance_ratio': advance / (advance + decline + 1e-5),
        'limit_up_count': limit_up
    }

# 核心模块3：选股引擎
def stock_selection(context, sentiment):
    """多因子选股系统"""
    selected = []
    for stock in g.stock_pool:
        try:
            if not is_tradable(stock):
                continue
                
            # 获取价格数据
            bars = get_bars(stock, count=g.ma_long+3, unit='1d', 
                          fields=['close','high','low','volume'])
            if len(bars) < g.ma_long+1:
                continue
                
            # 均线系统
            closes = [b.close for b in bars]
            ma5 = pd.Series(closes).rolling(g.dynamic_params['ma_short']).mean().values
            ma60 = pd.Series(closes).rolling(g.ma_long).mean().values
            
            # 买点条件
            cond1 = ma5[-2] < ma60[-2] and ma5[-1] > ma60[-1]  # 金叉
            cond2 = is_limit_up(bars[-1].close, bars[-2].close, stock)  # 当日涨停
            cond3 = is_limit_up(bars[-2].close, bars[-3].close, stock)  # 昨日涨停
            cond4 = bars[-1].volume > bars[-2].volume * 1.5  # 放量
            
            # 情绪调节
            if sentiment['advance_ratio'] < 0.4:
                cond4 = bars[-1].volume > bars[-2].volume * 2.0  # 弱势市场提高量能要求
                
            if all([cond1, cond2, cond3, cond4]):
                selected.append(stock)
                
        except:
            continue
            
    # 按20日波动率排序
    selected.sort(key=lambda x: get_price(x, count=20, fields='close').close.pct_change().std(),
                reverse=True)
    return selected[:g.trade_limit*2]

# 核心模块4：交易执行
def execute_trading(context, data, sentiment):
    # 卖出逻辑
    for stock in list(context.portfolio.positions):
        if need_sell(stock, data):
            order_target(stock, 0)
            log.info(f"卖出 {stock}")
    
    # 买入逻辑
    buy_list = stock_selection(context, sentiment)
    position_value = context.portfolio.total_value * g.dynamic_params['position_ratio']
    
    for stock in buy_list[:g.trade_limit]:
        if data[stock].close == data[stock].high_limit:
            order_target_value(stock, position_value)
            log.info(f"买入 {stock} 金额:{position_value:.2f}")

# 核心模块5：自适应学习
def learning_model_update(context):
    """参数动态优化系统"""
    if len(g.trade_log) < 30:
        return
        
    # 计算近期胜率
    recent = g.trade_log[g.trade_log.date > context.current_dt - timedelta(days=g.learn_window)]
    win_rate = (recent.profit > 0).mean()
    
    # 参数调整规则
    if win_rate > g.win_rate_threshold:
        new_ratio = min(0.2, g.dynamic_params['position_ratio'] * 1.1)
        new_ma = max(3, g.dynamic_params['ma_short'] -1)
    else:
        new_ratio = max(0.05, g.dynamic_params['position_ratio'] * 0.9)
        new_ma = min(8, g.dynamic_params['ma_short'] +1)
    
    # 更新参数
    g.dynamic_params.update({
        'position_ratio': round(new_ratio, 2),
        'ma_short': int(new_ma)
    })
    g.param_history.append({
        'date': context.current_dt,
        'params': dict(g.dynamic_params)
    })

# 工具函数集
def is_tradable(stock):
    """综合交易状态判断"""
    try:
        info = get_current_data()[stock]
        return all([
            not info.paused,
            not info.is_st,
            '退' not in info.name,
            info.low < info.high_limit  # 排除一字涨停
        ])
    except:
        return False

def is_limit_up(current, previous, stock):
    """精确涨停判断"""
    if previous == 0:
        return False
    # 科创板涨跌幅20%
    ratio = 1.2 if stock.startswith('688') else 1.1
    limit_price = round(previous * ratio + 1e-8, 2)
    return current >= limit_price

def need_sell(stock, data):
    """卖出信号检测"""
    try:
        # 使用昨日MA5判断，避免未来函数
        ma5 = get_price(stock, count=5, fields='close').close.mean()
        return data[stock].low < ma5 * 0.995  # 跌破0.5%容差
    except:
        return False