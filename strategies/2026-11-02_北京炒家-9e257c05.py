# Clone from JoinQuant
# postId: 9e257c05f6b0dddd84bc2c86e72af7a1
# backtestId: 33b4bf0db142466bacf7604656d4f925
# title: 北京炒家

# -*- coding: utf-8 -*-
import jqdata
import datetime
from jqlib.technical_analysis import *

def initialize(context):
    """初始化函数 (聚宽事件驱动规范)[^1]"""
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    
    # 策略核心参数
    g.max_positions = 5           # 最大持仓数
    g.position_ratio = 0.2        # 单仓位比例
    g.stop_loss = -0.03          # 止损比例
    g.take_profit = 0.05         # 止盈比例
    g.holding_days = 3           # 持仓天数
    g.min_circ_mv = 3e9          # 最小流通市值
    g.max_circ_mv = 10e9         # 最大流通市值
    
    # 新增环境参数 (北京炒家规则)[^2]
    g.market_status_filter = True     # 市况过滤开关
    g.sector_momentum_filter = True   # 板块效应过滤开关
    g.industry_cycles = {}            # 行业热度数据缓存

    set_order_cost(OrderCost(open_tax=0, close_tax=0.001,
                           open_commission=0.0003, close_commission=0.0003,
                           close_today_commission=0, min_commission=5),
                 type='stock')

    run_daily(market_open, time='9:30', reference_security='000300.XSHG')
    run_daily(update_stock_pool, time='before_open', reference_security='000300.XSHG')

# -----------------市场环境判断模块------------------
def market_status(context):
    """北京炒家市场环境判断 (改进版)[^2]
    返回值：bull(牛市)/bear(熊市)/neutral(震荡)"""
    # 获取所有正常交易股票
    all_stocks = get_all_securities(date=context.previous_date).index.tolist()
    
    # 筛选昨日涨停股 (使用复权价格)[^1]
    zt_stocks = [s for s in all_stocks if _is_yesterday_limit(s, context)]
    if not zt_stocks:
        return 'neutral'
    
    # 计算溢价率 (向量化加速)[^2]
    start_date = context.previous_date - datetime.timedelta(days=5)
    df = get_price(zt_stocks, start_date=start_date, end_date=context.previous_date,
                  fields='close', panel=False)
    df['prev_close'] = df.groupby('code')['close'].shift(1)
    daily_ret = df.groupby('code').apply(lambda x: x['close'].iloc[-1]/x['prev_close'].iloc[-1]-1)
    
    premium = daily_ret.mean()
    if premium > 0.03: return 'bull'
    if premium < -0.01: return 'bear'
    return 'neutral'

def _is_yesterday_limit(stock, context):
    """判断前日是否涨停[^1]"""
    hist = attribute_history(stock, 2, '1d', ['close','high_limit'], 
                            df=True, fq='pre', skip_paused=True)
    return len(hist)>=2 and abs(hist['close'].iloc[-1] - hist['high_limit'].iloc[-1]) < 0.005

# -----------------板块效应监测模块------------------
def sector_momentum(stock, context):
    """板块动量监测 (聚宽行业数据接口)[^1]"""
    industry_info = get_industry(stock, date=context.previous_date)
    if not industry_info: return False
    
    industry_code = industry_info[stock]['jq_l1']['industry_code']
    if industry_code not in g.industry_cycles:
        sector_stocks = get_industry_stocks(industry_code, date=context.previous_date)
        sector_zt = sum(1 for s in sector_stocks if _is_yesterday_limit(s, context))
        g.industry_cycles[industry_code] = sector_zt
    
    return g.industry_cycles[industry_code] >=3  # 板块涨停≥3支

# -----------------核心策略逻辑------------------
def update_stock_pool(context):
    """更新股票池 (聚宽查询API规范)[^1]"""
    current_date = context.current_dt.date()
    all_stocks = get_index_stocks('000300.XSHG', date=current_date)
    
    # 筛选非ST股[^2]
    st_info = get_extras('is_st', all_stocks, end_date=current_date, df=True).iloc[-1]
    normal_stocks = st_info[st_info == 0].index.tolist()
    
    # 流通市值过滤[^1]
    q = query(valuation.code).filter(
        valuation.code.in_(normal_stocks),
        valuation.circulating_market_cap.between(g.min_circ_mv, g.max_circ_mv)
    )
    g.stock_pool = get_fundamentals(q)['code'].tolist()

def market_open(context):
    """交易主逻辑 (集成环境判断)[^2]"""
    if g.market_status_filter and market_status(context) == 'bear':
        log.info("熊市环境，暂停交易")
        return
    
    candidate_pool = []
    current_date = context.current_dt.strftime('%Y-%m-%d')
    
    # 板块效应过滤[^2]
    screened_pool = [s for s in g.stock_pool if (
        not g.sector_momentum_filter or 
        sector_momentum(s, context)
    )]
    
    # 有效性过滤[^1]
    candidate_pool = [s for s in screened_pool if validate_stock(s, context)]
    
    # 流动性排序[^2]
    candidate_pool = sorted(candidate_pool, key=lambda x: 
        get_trade_amount(x, current_date), reverse=True)[:g.max_positions]
    
    execute_trading(context, candidate_pool)

def validate_stock(stock, context):
    """股票有效性验证 (集成北京炒家规则)[^2]"""
    # 排除创业板科创板[^1]
    if stock.startswith(('300','688')): return False
    
    # 价格数据获取 (聚宽复权接口)[^1]
    hist = attribute_history(stock, 3, '1d', ['close','pre_close'], 
                            skip_paused=True, df=True)
    if len(hist) <3: return False
    
    # 涨停判断[^2]
    prev_close = hist['pre_close'].iloc[-1]
    close_price = hist['close'].iloc[-1]
    limit_price = round(prev_close*1.1 - 0.01, 2)
    if close_price < limit_price: return False
    
    # 牛市过滤一字板[^2]
    if market_status(context) == 'bull':
        today_open = get_price(stock, end_date=context.current_dt,
                              fields='open', count=1).iloc[0,0]
        if abs(today_open - close_price) <0.01: return False
    
    return True

# -----------------交易执行模块------------------
def execute_trading(context, candidate_pool):
    """执行交易 (含风控规则)[^2]"""
    # 沪深300趋势过滤[^1]
    hs300 = get_price('000300.XSHG', end_date=context.previous_date,
                     fields='close', count=20).iloc[:,0]
    if hs300[-5:].mean() < hs300.mean():
        log.warning("大盘短期趋势走弱，暂停交易")
        return
    
    # 卖出逻辑[^1]
    for stock in context.portfolio.positions:
        position = context.portfolio.positions[stock]
        current_price = get_price(stock, end_date=context.current_dt,
                                 fields='close', count=1).iloc[0,0]
        
        returns = (current_price - position.avg_cost)/position.avg_cost
        holding_days = (context.current_dt - position.init_time).days
        
        if returns <= g.stop_loss or \
           returns >= g.take_profit or \
           holding_days >= g.holding_days:
            order_target(stock, 0)
    
    # 买入逻辑[^2]
    available_cash = context.portfolio.available_cash
    max_buy = g.max_positions - len(context.portfolio.positions)
    
    for stock in candidate_pool[:max_buy]:
        if available_cash < 10000: break
        order_target_value(stock, available_cash*g.position_ratio)
        available_cash *= (1 - g.position_ratio)

# -----------------工具函数------------------
def get_trade_amount(stock, dt):
    """5日成交额均值 (聚宽API规范)[^1]"""
    hist = get_price(stock, end_date=dt, frequency='daily',
                   fields='money', count=5, skip_paused=True)
    return hist.mean().values[0] if not hist.empty else 0

# 初始化行业数据缓存
g.industry_cycles = {}
