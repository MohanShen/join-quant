# Clone from JoinQuant
# postId: af3ca524d3b1fbd094066ebc1287c8f8
# backtestId: 993f953d3fd72b98dd8c93b7fe5a2cf5
# title: 模拟交易买卖交易未执行

from jqdata import *
import pandas as pd
import numpy as np
import statsmodels.api as sm
from datetime import timedelta
import math

def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option("avoid_future_data", True)
    set_slippage(FixedSlippage(0.000))
    # 开启系统日志
    log.set_level('order', 'info')
    
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.00012, close_commission=0.00012, min_commission=5), type='stock')

    # 30只精选高股息/价值蓝筹股票池
    context.stocks = [
        '601899.XSHG', #紫金矿业
        '601600.XSHG', #中国铝业
        '600531.XSHG', #豫光金铅
        '000426.XSHE', #兴业银锡
        '002466.XSHE', #天齐锂业
        '600489.XSHG', #中金黄金
        
        '601857.XSHG', #中石油
        '600938.XSHG', #中海油
        
        '601985.XSHG', #中国核电
        '003816.XSHE', #中广核
        '601868.XSHG', #中国能建
        '601669.XSHG', #中国电建
        
        '601390.XSHG', #中国中铁
        '601006.XSHG', #大秦铁路
        
        '600150.XSHG', #中国船舶
        '600482.XSHG', #中国动力
        '601872.XSHG', #招商轮船
        
        '000725.XSHE', #京东方
        '002278.XSHE', #神开股份
        '600690.XSHG', #海尔智家
        '000333.XSHE', #美的集团
        
        # '600887.XSHG', #伊利股份
        '601339.XSHG', #百隆东方
        '600066.XSHG', #宇通客车
        '002352.XSHE', #顺丰控股
        
        '601901.XSHG', #方正证券
        # '000166.XSHE', #申万宏源
        # '601377.XSHG', #兴业证券
        '600919.XSHG', #江苏银行
        # '601169.XSHG', #北京银行
        # '600015.XSHG', #华夏银行
        
        '600096.XSHG', #云天化
        '002648.XSHE', #卫星化学
        
        '601118.XSHG', #海南橡胶
        '600737.XSHG', #中粮糖业
    ]
    
    # --- 策略参数配置 ---
    g.target_num = 5               # 目标持仓数量
    g.risk_target_num = 3          # RISK状态持仓数
    g.hold_rank_limit = 10         # 容忍排名下限(跌出前10则卖出)
    g.m_days = 25                  # 动量回溯期
    g.v_lookback = 60              # 估值回溯期
    
    # 大盘 RSRS 参数
    g.rsrs_N = 18
    g.rsrs_M = 300
    g.market_rsrs_threshold = -0.685 # 大盘RSRS低于此值则判定为极度弱市，停止买入
    
    # ATR 动态吊灯止盈止损参数
    g.atr_period = 14
    g.atr_multiplier = 2.5         # 动态止损乘数(2~3之间较合理)
    g.highest_prices = {}          # 记录持仓以来的最高价: {stock: highest_price}
    
    # 因子权重
    g.weights = {'dy': 0.1, 'mom': 0.3, 'v_deg': 0.3, 'v_dur': 0.3}

    # 状态变量
    g.buy_list = []
    g.sell_list = []
    g.market_status = 'NORMAL'

    run_daily(before_market_open, time='07:30') 
    run_daily(market_trade, time='09:35') 

# --- 数据与因子计算函数 ---

def get_valuation_indicators(context, stock_list, lookback):
    q = query(valuation.code, valuation.pb_ratio).filter(valuation.code.in_(stock_list))
    df_pb = get_fundamentals_continuously(q, end_date=context.previous_date, count=lookback, panel=False)
    
    if df_pb.empty:
        return pd.Series(0.0, index=stock_list), pd.Series(0.0, index=stock_list)

    pb_table = df_pb.pivot(index='day', columns='code', values='pb_ratio')
    degree_scores, duration_scores = {}, {}

    for stock in stock_list:
        if stock not in pb_table.columns:
            degree_scores[stock], duration_scores[stock] = 0, 0
            continue
            
        pb_series = pb_table[stock].dropna()
        if pb_series.empty:
            degree_scores[stock], duration_scores[stock] = 0, 0
            continue
            
        curr_pb = pb_series.iloc[-1]
        min_pb = pb_series.min()
        max_pb = pb_series.max()
        
        # 低估程度
        if max_pb != min_pb:
            deg = (max_pb - curr_pb) / (max_pb - min_pb + 1e-6)
        else:
            deg = 0.5
            
        # 低估时间
        median_pb = pb_series.median()
        dur = (pb_series < median_pb).sum() / float(len(pb_series))
        
        degree_scores[stock] = deg
        duration_scores[stock] = dur
        
    return pd.Series(degree_scores), pd.Series(duration_scores)
    
def get_dividend_ratio(context, stock_list):
    time1 = context.previous_date 
    time0 = time1 - timedelta(days=365)
    
    q = query(finance.STK_XR_XD.code, finance.STK_XR_XD.bonus_amount_rmb)\
        .filter(finance.STK_XR_XD.code.in_(stock_list),
                finance.STK_XR_XD.a_registration_date >= time0,
                finance.STK_XR_XD.a_registration_date <= time1)
    df_bonus = finance.run_query(q)
    
    dividend_sum = df_bonus.groupby('code')['bonus_amount_rmb'].sum() if not df_bonus.empty else pd.Series(0.0, index=stock_list)
        
    q_cap = query(valuation.code, valuation.market_cap).filter(valuation.code.in_(stock_list))
    df_cap = get_fundamentals(q_cap, date=time1).set_index('code')
    
    res = pd.concat([dividend_sum, df_cap], axis=1, sort=False).fillna(0)
    res.columns = ['bonus_amount', 'market_cap']
    res['dividend_ratio'] = (res['bonus_amount'] / 10000.0) / (res['market_cap'] + 1e-6)
    return res['dividend_ratio']

def MOM(stock):
    df = attribute_history(stock, g.m_days, '1d', ['close'])
    if len(df) < g.m_days: return 0
    y = np.log(df['close'].values)
    n = len(y)  
    x = np.arange(n)
    weights = np.linspace(1, 2, n)  
    slope, intercept = np.polyfit(x, y, 1, w=weights)
    annualized_returns = math.pow(math.exp(slope), 250) - 1
    residuals = y - (slope * x + intercept)
    weighted_residuals = weights * residuals**2
    r_squared = 1 - (np.sum(weighted_residuals) / (np.sum(weights * (y - np.mean(y))**2) + 1e-8))
    return annualized_returns * r_squared

def get_market_rsrs(context):
    """获取大盘(沪深300)的RSRS宏观风控指标"""
    h = attribute_history('000300.XSHG', g.rsrs_N + g.rsrs_M, '1d', ['high', 'low'])
    if len(h) < g.rsrs_N + 30: 
        return 0
    
    slopes = []
    available_len = len(h)
    for i in range(available_len - g.rsrs_N + 1):
        df = h.iloc[i : i + g.rsrs_N]
        X = sm.add_constant(df['high'])
        y = df['low']
        model = sm.OLS(y, X).fit()
        slopes.append(model.params['high'])
    
    current_slope = slopes[-1]
    history_slopes = slopes[:-1]
    
    if len(history_slopes) < 2: return 0
    return (current_slope - np.mean(history_slopes)) / (np.std(history_slopes) + 1e-6)

def get_atr(stock, period):
    """计算单个股票的真实波幅 ATR"""
    h = attribute_history(stock, period + 1, '1d', ['high', 'low', 'close'])
    if len(h) < period + 1:
        return 0
    tr_list = []
    for i in range(1, len(h)):
        high = h['high'].iloc[i]
        low = h['low'].iloc[i]
        prev_close = h['close'].iloc[i-1]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_list.append(tr)
    return np.mean(tr_list)

# --- 盘前与综合打分 ---

def before_market_open(context):
    stocks = context.stocks
    today = context.current_dt.date()
    
    # 1. 大盘风控判断
    market_rsrs = get_market_rsrs(context)
    if market_rsrs < g.market_rsrs_threshold:
        g.market_status = 'RISK'
    else:
        g.market_status = 'NORMAL'
        
    log.info(f"=========== {today} 盘前准备 ===========")
    log.info(f"大盘沪深300 RSRS: {market_rsrs:.2f} | 市场状态: {g.market_status}")
    
    # 2. 计算所有因子原始得分
    dy_series = get_dividend_ratio(context, stocks) 
    mom_series = pd.Series({s: MOM(s) for s in stocks})                   
    v_deg_series, v_dur_series = get_valuation_indicators(context, stocks, g.v_lookback)
        
    # 3. 核心修改：使用百分位排名(Rank)替代Z-Score，解决小样本失真
    def rank_score(s):
        # 排除空值干扰，采用最小排名法，并映射到 0~1 之间
        return (s.rank(ascending=True, method='min') - 1) / (len(s.dropna()) - 1 + 1e-6)

    s_dy = rank_score(dy_series)
    s_mom = rank_score(mom_series)
    s_deg = rank_score(v_deg_series)
    s_dur = rank_score(v_dur_series)
    
    # 4. 综合打分
    final_scores = (s_dy * g.weights['dy'] + s_mom * g.weights['mom'] + 
                    s_deg * g.weights['v_deg'] + s_dur * g.weights['v_dur']).sort_values(ascending=False)
    
    # 打印 Top 10 榜单及各项原始因子明细
    log.info("-" * 15 + f" {today} 盘前 Top 10 榜单及原始因子诊断 " + "-" * 15)
    
    # 取前10名，如果股票池不足10只则取全部
    top_n = min(10, len(final_scores)) 
    
    for i, s in enumerate(final_scores.index[:top_n]):
        name = get_security_info(s).display_name
        
        # 提取该股票的原始因子真实数值（非排名分）
        raw_dy = dy_series.get(s, 0)
        raw_mom = mom_series.get(s, 0)
        raw_deg = v_deg_series.get(s, 0)
        raw_dur = v_dur_series.get(s, 0)
        
        # 格式化输出：股息率转为百分比，动量与估值保留1位小数
        log.info(
            f"Top{i+1:02d} | {s} ({name}) | 综合得分: {final_scores[s]:.3f} "
            f"=> [股息率: {raw_dy:.1%} | 动量值: {raw_mom:.1f} | "
            f"低估程度: {raw_deg:.1f} | 低估时间占比: {raw_dur:.1f}]"
        )
    log.info("-" * 65)

    # 5. 生成今日交易名单与维护持仓最高价
    g.buy_list = list(final_scores.index[:g.target_num])
    g.sell_list = []
    
    current_positions = list(context.portfolio.positions.keys())
    
    # 清理已不在持仓列表中的最高价记录
    keys_to_remove = [k for k in g.highest_prices.keys() if k not in current_positions]
    for k in keys_to_remove:
        del g.highest_prices[k]
        
    for stock in current_positions:
        current_price = context.portfolio.positions[stock].price
        # 更新持仓以来的最高价
        if stock not in g.highest_prices:
            g.highest_prices[stock] = current_price
        else:
            g.highest_prices[stock] = max(g.highest_prices[stock], current_price)
            
        # 检查逻辑1：因子衰退（跌出Top10）
        rank_index = list(final_scores.index).index(stock) if stock in final_scores.index else 999
        if rank_index >= g.hold_rank_limit:
            log.info(f"【因子衰退】{stock} 当前排名第 {rank_index+1}，跌出安全区，列入卖出计划。")
            g.sell_list.append(stock)
            continue
            
        # 检查逻辑2：ATR 吊灯止盈/止损
        atr = get_atr(stock, g.atr_period)
        trailing_stop_price = g.highest_prices[stock] - g.atr_multiplier * atr
        
        if current_price < trailing_stop_price:
            log.info(f"【触及止损/止盈】{stock} 现价({current_price})低于退出线({trailing_stop_price:.2f}) [最高价:{g.highest_prices[stock]:.2f}, ATR:{atr:.2f}]，列入卖出计划。")
            g.sell_list.append(stock)

def market_trade(context):
    # 1. 执行卖出逻辑
    for stock in g.sell_list:
        if stock in context.portfolio.positions:
            order_target(stock, 0)
            log.info(f"执行卖出: 清仓 {stock}")
            
    # 2. 执行买入逻辑
    # 如果系统性风险高，则停止新开仓，仅持有防守
    if g.market_status == 'RISK':
        log.info("大盘风控生效：暂停一切新开仓动作。")
        return
        
    # 计算当前需要买入的标的（除去已有持仓且不需要卖出的标的）
    current_positions = [s for s in context.portfolio.positions.keys() if s not in g.sell_list]
    targets_to_buy = [s for s in g.buy_list if s not in current_positions]
    
    if not targets_to_buy:
        return
        
    # 资金等权重分配
    target_weight = 1.0 / g.target_num
    total_value = context.portfolio.total_value
    cash_per_stock = total_value * target_weight
    
    for stock in targets_to_buy:
        if len(context.portfolio.positions) >= g.target_num:
            break # 达到最大持股数限制
            
        available_cash = context.portfolio.available_cash
        # 若单份可用资金足够，则买入
        buy_cash = min(cash_per_stock, available_cash)
        if buy_cash > 5000: # 剔除极小额碎股买单
            order_value(stock, buy_cash)
            log.info(f"执行买入: 建仓 {stock}，分配金额: {buy_cash:.2f}")
            # 初始化最高价记录
            pos = context.portfolio.positions.get(stock)
            if pos:
                g.highest_prices[stock] = pos.price