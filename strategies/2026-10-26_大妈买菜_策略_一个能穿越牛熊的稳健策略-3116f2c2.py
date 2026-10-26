# Clone from JoinQuant
# postId: 3116f2c23868336f8e641d1a56a20a0b
# backtestId: 986579c825e86a1f3d0d2f0a30ce4bc2
# title: “大妈买菜”策略—一个能穿越牛熊的稳健策略

from jqdata import *
import pandas as pd
from datetime import datetime, timedelta, time

def initialize(context):
    context.max_hold = 10
    context.max_price = 9.0
    context.peg_low = -3.0
    context.peg_high = 3.0
    context.divident_quantile = 0.25
    
    context.current_month = 0
    context.month_pool = []
    context.month_rebalanced = False
    context.checked_date = None
    
    log.info('=== 策略初始化 === 手动计算股息率+PEG | 月度调仓+盘中轮动')

def handle_data(context, data):
    now = context.current_dt
    current_time = now.time()
    
    # 每月选股（新月第一个交易日 9:31）
    if now.month != context.current_month:
        if time(9, 30) <= current_time <= time(9, 32):
            select_month_pool(context)
            context.current_month = now.month
            context.month_rebalanced = False
            log.info('【选股】%d月股票池(%d只): %s' % (now.month, len(context.month_pool), str(context.month_pool)))
    
    # 每日14:00 轮动检查
    if time(14, 0) <= current_time < time(14, 1):
        if context.checked_date != now.date():
            context.checked_date = now.date()
            daily_check_and_rotate(context)
    
    # 每月25号以后14:30 月度调仓
    if now.day >= 25 and not context.month_rebalanced:
        if time(14, 30) <= current_time < time(14, 31):
            monthly_rebalance(context)
            context.month_rebalanced = True
            log.info('【月度调仓】完成')

# ==================== 选股逻辑（全部手动计算） ====================
def select_month_pool(context):
    all_stocks = get_all_securities('stock', context.current_dt).index.tolist()
    current_data = get_current_data()
    
    # 步骤1：剔除科创板、北交所、ST/*ST/退市/停牌/涨跌停
    filtered = []
    for s in all_stocks:
        if s.startswith('688') or s.startswith('8') or s.startswith('4'):
            continue
        d = current_data[s]
        if d.paused:
            continue
        if d.is_st or 'ST' in d.name or '*ST' in d.name or '退' in d.name:
            continue
        if d.last_price >= d.high_limit * 0.999 or d.last_price <= d.low_limit * 1.001:
            continue
        filtered.append(s)
    
    if len(filtered) == 0:
        context.month_pool = []
        return
    
    log.info('【选股调试】步骤1 基础过滤后: %d 只' % len(filtered))
    
    # ========== 步骤2：手动计算近12个月股息率 ==========
    start_dt = context.current_dt - timedelta(days=365)
    
    # 分批查询分红数据（finance.run_query单次最多4000行）
    chunk_size = 500
    div_records = []
    for i in range(0, len(filtered), chunk_size):
        chunk = filtered[i:i+chunk_size]
        q = query(
            finance.STK_XR_XD.code,
            finance.STK_XR_XD.bonus_amount_rmb  # 每股派息金额（元）
        ).filter(
            finance.STK_XR_XD.a_registration_date >= start_dt,
            finance.STK_XR_XD.a_registration_date <= context.current_dt,
            finance.STK_XR_XD.code.in_(chunk)
        )
        df = finance.run_query(q)
        if not df.empty:
            div_records.append(df)
    
    if len(div_records) == 0:
        log.info('【选股调试】无分红记录')
        context.month_pool = []
        return
    
    div_df = pd.concat(div_records)
    # 汇总每只股票近12个月累计每股分红
    div_sum = div_df.groupby('code')['bonus_amount_rmb'].sum().reset_index()
    div_sum.columns = ['code', 'dividend_ttm']
    
    # 获取当前收盘价计算股息率
    price_df = get_price(filtered, end_date=context.current_dt, frequency='daily',
                         fields=['close'], count=1, panel=False)
    price_dict = dict(zip(price_df['code'], price_df['close']))
    
    div_sum['price'] = div_sum['code'].map(price_dict)
    div_sum = div_sum[div_sum['price'] > 0]
    # 股息率 = 近12个月每股累计分红 / 当前股价
    div_sum['dividend_ratio'] = div_sum['dividend_ttm'] / div_sum['price']
    
    log.info('【选股调试】步骤2 有分红+有价格: %d 只' % len(div_sum))
    
    if len(div_sum) == 0:
        context.month_pool = []
        return
    
    threshold = div_sum['dividend_ratio'].quantile(1 - context.divident_quantile)
    high_div = div_sum[div_sum['dividend_ratio'] >= threshold]['code'].tolist()
    
    log.info('【选股调试】步骤2 高股息率(前25%%): %d 只' % len(high_div))
    
    if len(high_div) == 0:
        context.month_pool = []
        return
    
    # ========== 步骤3：手动计算PEG（PE / 净利润增长率） ==========
    # 获取PE和净利润同比增长率
    q = query(
        valuation.code,
        valuation.pe_ratio,                    # 市盈率
        indicator.inc_net_profit_year_on_year  # 净利润同比增长率(%)
    ).filter(
        valuation.code.in_(high_div)
    )
    df = get_fundamentals(q, date=context.current_dt)
    df = df.dropna(subset=['pe_ratio', 'inc_net_profit_year_on_year'])
    
    # 计算PEG = PE / (净利润增长率 * 100)
    # 注意：增长率为负时PEG无意义，这里按用户要求保留-3~3范围
    df['peg'] = df['pe_ratio'] / (df['inc_net_profit_year_on_year'] * 100)
    df = df[(df['peg'] >= context.peg_low) & (df['peg'] <= context.peg_high)]
    df = df.dropna(subset=['peg'])
    peg_stocks = df['code'].tolist()
    
    log.info('【选股调试】步骤3 PEG合格(-3~3): %d 只' % len(peg_stocks))
    
    if len(peg_stocks) == 0:
        context.month_pool = []
        return
    
    # 步骤4：股价低于9元
    cheap = [s for s in peg_stocks if current_data[s].last_price < context.max_price]
    
    log.info('【选股调试】步骤4 低价(<9元): %d 只' % len(cheap))
    
    if len(cheap) == 0:
        context.month_pool = []
        return
    
    # 步骤5：总市值从小到大，取前10
    q3 = query(
        valuation.code,
        valuation.market_cap
    ).filter(
        valuation.code.in_(cheap)
    ).order_by(valuation.market_cap.asc())
    
    df3 = get_fundamentals(q3, date=context.current_dt)
    context.month_pool = df3['code'].head(context.max_hold).tolist()
    
    log.info('【选股调试】步骤5 最终股票池: %d 只' % len(context.month_pool))

# ==================== 每日14:00 轮动检查 ====================
def daily_check_and_rotate(context):
    if len(context.month_pool) == 0:
        return
    
    current_data = get_current_data()
    positions = context.portfolio.positions
    sold_cash = 0
    
    for stock in list(positions.keys()):
        try:
            hist = attribute_history(stock, 1, '1d', ['close', 'high_limit'])
            if len(hist) == 0:
                continue
            y_close = hist['close'][0]
            y_limit = hist['high_limit'][0]
            
            if abs(y_close - y_limit) < 0.01:
                if current_data[stock].last_price < current_data[stock].high_limit * 0.999:
                    v = positions[stock].value
                    order_target(stock, 0)
                    sold_cash += v
                    log.info('【轮动卖出】%s 昨日涨停今日未连板，释放资金 %.0f' % (stock, v))
        except:
            continue
    
    if sold_cash > 0:
        held = set(positions.keys())
        candidates = []
        for s in context.month_pool:
            if s in held:
                continue
            if current_data[s].paused:
                continue
            if current_data[s].last_price >= current_data[s].high_limit * 0.999:
                continue
            candidates.append(s)
        
        if candidates:
            stock_to_buy = candidates[0]
            order_value(stock_to_buy, sold_cash)
            log.info('【轮动买入】%s，金额 %.0f' % (stock_to_buy, sold_cash))

# ==================== 月末月度调仓 ====================
def monthly_rebalance(context):
    if len(context.month_pool) == 0:
        return
    
    current_data = get_current_data()
    
    for stock in list(context.portfolio.positions.keys()):
        if stock not in context.month_pool:
            order_target(stock, 0)
            log.info('【月度清仓】%s 不在新池中' % stock)
    
    target_value = context.portfolio.total_value * 0.1
    
    for stock in context.month_pool:
        if current_data[stock].paused:
            log.info('【月度买入跳过】%s 停牌' % stock)
            continue
        if current_data[stock].last_price >= current_data[stock].high_limit * 0.999:
            log.info('【月度买入跳过】%s 涨停无法买入' % stock)
            continue
        
        order_target_value(stock, target_value)
        log.info('【月度买入】%s 目标市值 %.0f' % (stock, target_value))