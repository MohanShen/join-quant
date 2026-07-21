# Clone from JoinQuant
# postId: a7872a22dd1913f38b0352ab86742f88
# backtestId: 3d2d53c565172005cd42ec0fc602f311
# title: 头狼涨停战法

'''
头狼涨停战法 - 聚宽量化策略 v5.0
========================================

'''

import numpy as np
import pandas as pd
from datetime import time, timedelta

# ==================== 初始化 ====================
def initialize(context):
    """初始化"""
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    
    # 持仓
    g.max_stocks = 3
    g.max_stock_ratio = 0.33
    
    # 时间
    g.buy_start = time(9, 30)
    g.buy_end = time(10, 30)
    g.sell_deadline = time(10, 15)
    
    # 形态参数
    g.min_change = 0.005      # 最小涨幅 0.5%
    g.max_change = 0.11       # 最大涨幅 11%
    g.min_vol_ratio = 1.2     # 最小量比
    
    # 选股
    g.max_cap = 100e9           # 最大流通市值（亿元）
    g.min_cap = 10e7             # 最小流通市值（亿元）
    g.max_turnover = 30       # 最大换手率（%）
    
    # 风控
    g.stop_loss = -0.03
    g.take_profit = 0.10
    g.buy_score = 50          # 买入评分阈值
    
    # 状态
    g.stock_pool = []
    g.bought_today = []
    
    # 定时任务
    run_daily(before_open, '8:45')
    run_daily(check_open, '9:30')
    
    # 9:31-10:30 每分钟
    minutes = list(range(31, 60)) + list(range(0, 31))
    hours = ['9'] * 29 + ['10'] * 31
    for h, m in zip(hours, minutes):
        run_daily(check_minute, f'{h}:{m:02d}')
    
    # 9:31-10:15 卖出窗口
    for m in range(31, 46):
        run_daily(check_sell, f'9:{m}')
    
    run_daily(after_close, '15:10')

# ==================== 盘前 ====================
def before_open(context):
    """盘前选股"""
    log.info('=' * 50)
    log.info(f'【盘前】{context.current_dt.strftime("%Y-%m-%d")}')
    
    # 全市场
    all_stocks = get_all_securities(['stock']).index.tolist()
    log.info(f'全市场: {len(all_stocks)} 只')
    
    # 过滤1：ST、停牌
    current_data = get_current_data()
    valid = []
    for s in all_stocks:
        if current_data[s].is_st:
            continue
        if current_data[s].paused:
            continue
        # 排除已涨停
        if current_data[s].high_limit and current_data[s].last_price:
            if current_data[s].last_price >= current_data[s].high_limit * 0.999:
                continue
        valid.append(s)
    
    log.info(f'基础过滤后: {len(valid)} 只')
    
    # 过滤2：财务数据
    try:
        df = get_fundamentals(
            query(
                valuation.code,
                valuation.circulating_market_cap,
                valuation.turnover_ratio
            ).filter(
                valuation.code.in_(valid)
            )
        )
        
        if df is not None and not df.empty:
            # 单位：circulating_market_cap=亿元, turnover_ratio=%
            df = df[
                (df.circulating_market_cap >= g.min_cap) &
                (df.circulating_market_cap <= g.max_cap) &
                (df.turnover_ratio <= g.max_turnover)
            ]
            g.stock_pool = df.code.tolist()
            log.info(f'财务过滤后: {len(g.stock_pool)} 只')
        else:
            g.stock_pool = valid
            log.info(f'财务数据为空，使用基础过滤: {len(g.stock_pool)} 只')
    except Exception as e:
        log.warn(f'财务过滤失败: {e}')
        g.stock_pool = valid
    
    # 兜底：如果过滤后为0，使用基础列表
    if len(g.stock_pool) == 0:
        g.stock_pool = valid
        log.warn('警告：股票池为空，使用基础列表')
    
    g.bought_today = []
    log.info(f'【股票池】共 {len(g.stock_pool)} 只')

# ==================== 开盘 ====================
def check_open(context):
    """9:30 开盘检查"""
    log.info('【开盘9:30】开始扫描...')
    scan_buy(context)

# ==================== 分钟检查 ====================
def check_minute(context):
    """每分钟检查"""
    now = context.current_dt.time()
    
    # 在买入窗口内
    if g.buy_start <= now <= g.buy_end:
        if len(context.portfolio.positions) < g.max_stocks:
            scan_buy(context)
    
    # 止损检查
    check_stop(context)

def check_sell(context):
    """卖出窗口"""
    now = context.current_dt.time()
    
    for stock in list(context.portfolio.positions.keys()):
        pos = context.portfolio.positions[stock]
        price = get_current_data()[stock].last_price
        
        if not price:
            continue
        
        ret = (price - pos.avg_cost) / pos.avg_cost
        
        # 止损
        if ret <= g.stop_loss:
            order_target(stock, 0)
            log.info(f'【止损】{stock} {ret*100:.2f}%')
            continue
        
        # 止盈
        if ret >= g.take_profit:
            order_target(stock, 0)
            log.info(f'【止盈】{stock} {ret*100:.2f}%')
            continue
        
        # 早盘弱势卖出
        if now <= g.sell_deadline:
            if is_weak_today(stock, context):
                order_target(stock, 0)
                log.info(f'【弱势卖出】{stock} {ret*100:.2f}%')

# ==================== 扫描买入 ====================
def scan_buy(context):
    """扫描并买入"""
    positions = list(context.portfolio.positions.keys())
    slots = g.max_stocks - len(positions)
    
    if slots <= 0:
        return
    
    cash = context.portfolio.available_cash / max(slots, 1) * 0.98
    
    # 扫描前50只
    signals = []
    for stock in g.stock_pool[:50]:
        if stock in positions or stock in g.bought_today:
            continue
        
        signal = analyze(stock, context)
        if signal and signal['score'] >= g.buy_score:
            signals.append((stock, signal))
    
    # 按评分排序
    signals.sort(key=lambda x: x[1]['score'], reverse=True)
    
    for stock, signal in signals[:slots]:
        amount = min(cash, context.portfolio.total_value * g.max_stock_ratio)
        if amount >= 100:
            order_value(stock, amount)
            log.info(f'【买入】{stock} 价格:{signal["price"]:.2f} '
                    f'涨幅:{signal["change"]*100:.1f}% '
                    f'量比:{signal["vol_ratio"]:.1f} '
                    f'评分:{signal["score"]}')
            g.bought_today.append(stock)
            
            slots -= 1
            if slots <= 0:
                break

def check_stop(context):
    """止损检查"""
    for stock in list(context.portfolio.positions.keys()):
        pos = context.portfolio.positions[stock]
        price = get_current_data()[stock].last_price
        
        if not price:
            continue
        
        ret = (price - pos.avg_cost) / pos.avg_cost
        if ret <= g.stop_loss:
            order_target(stock, 0)
            log.warn(f'【止损】{stock} {ret*100:.2f}%')

# ==================== 分析 ====================
def analyze(stock, context):
    """分析股票"""
    try:
        today = context.current_dt.strftime('%Y-%m-%d')
        
        # 获取分钟数据
        data = get_price(
            stock,
            start_date=today + ' 09:25:00',
            end_date=today + ' 11:35:00',
            frequency='1m',
            fields=['open', 'close', 'volume']
        )
        
        if data is None or len(data) < 10:
            return None
        
        close = data['close'].values
        vol = data['volume'].values
        
        # 涨幅过滤
        change = (close[-1] - close[0]) / close[0] if close[0] > 0 else 0
        if change < g.min_change or change > g.max_change:
            return None
        
        score = 0
        detail = {'price': close[-1], 'change': change}
        
        # 1. 波浪 (0-50分)
        s1 = wave_score(close)
        score += s1
        
        # 2. 量能 (0-30分)
        s2, vr = vol_score(vol, stock, context)
        score += s2
        detail['vol_ratio'] = vr
        
        # 3. 均线 (0-20分)
        s3 = line_score(close)
        score += s3
        
        detail['score'] = score
        return detail
        
    except Exception as e:
        return None

def wave_score(close):
    """波浪评分"""
    if len(close) < 10:
        return 0
    
    score = 0
    
    # 早期涨幅
    early_gain = (close[min(9, len(close)-1)] - close[0]) / close[0] if close[0] > 0 else 0
    
    if early_gain >= 0.005:
        score += 10
    if early_gain >= 0.015:
        score += 10
    if early_gain >= 0.025:
        score += 10
    
    # 回调
    if len(close) > 10:
        early_high = max(close[:10])
        mid_low = min(close[10:min(20, len(close))])
        callback = (early_high - mid_low) / early_high if early_high > 0 else 0
        
        if 0.05 <= callback <= 0.40:
            score += 20
    
    # 近期上涨
    if len(close) >= 5:
        if close[-1] > close[-5]:
            score += 10
    
    return min(score, 50)

def vol_score(vol, stock, context):
    """量能评分"""
    if len(vol) < 5:
        return 0, 1.0
    
    today_avg = vol[5:].mean() if len(vol) > 5 else vol.mean()
    
    # 历史均量
    try:
        hist = get_price(
            stock,
            count=300,
            end_date=context.current_dt - timedelta(days=1),
            frequency='1m',
            fields=['volume']
        )
        hist_avg = hist['volume'].mean() if hist is not None and len(hist) > 0 else today_avg
    except:
        hist_avg = today_avg
    
    ratio = today_avg / hist_avg if hist_avg > 0 else 1.0
    
    score = 0
    if ratio >= 1.5:
        score = 30
    elif ratio >= 1.2:
        score = 20
    elif ratio >= 1.0:
        score = 10
    
    return min(score, 30), ratio

def line_score(close):
    """均线评分"""
    if len(close) < 5:
        return 0
    
    # 累计均价
    avg = np.cumsum(close) / np.arange(1, len(close) + 1)
    
    # 最近5分钟
    recent_p = close[-5:]
    recent_a = avg[-5:]
    
    above = sum(recent_p[i] >= recent_a[i] * 0.998 for i in range(5))
    
    return int(above / 5 * 20)

def is_weak_today(stock, context):
    """判断是否弱势"""
    try:
        today = context.current_dt.strftime('%Y-%m-%d')
        
        data = get_price(
            stock,
            start_date=today + ' 09:30:00',
            frequency='1m',
            fields=['close', 'volume']
        )
        
        if data is None or len(data) < 10:
            return False
        
        close = data['close'].values
        vol = data['volume'].values
        
        # 均价
        avg = np.cumsum(close) / np.arange(1, len(close) + 1)
        
        # 在均线下方
        below = sum(close[-10:] < avg[-10:]) / 10
        if below > 0.6:
            return True
        
        # 量能萎缩
        if len(vol) >= 10:
            early = vol[:len(vol)//3].mean()
            recent = vol[-len(vol)//3:].mean()
            if early > 0 and recent < early * 0.5:
                return True
        
        return False
        
    except:
        return False

# ==================== 收盘 ====================
def after_close(context):
    """收盘复盘"""
    log.info('=' * 50)
    log.info(f'【收盘】{context.current_dt.strftime("%Y-%m-%d")}')
    log.info(f'总资产: {context.portfolio.total_value:.2f}')
    log.info(f'持仓: {len(context.portfolio.positions)} 只')
    
    for stock, pos in context.portfolio.positions.items():
        ret = (pos.price - pos.avg_cost) / pos.avg_cost * 100
        log.info(f'  {stock}: 成本{pos.avg_cost:.2f} 现价{pos.price:.2f} {ret:.2f}%')
    
    log.info('=' * 50)
