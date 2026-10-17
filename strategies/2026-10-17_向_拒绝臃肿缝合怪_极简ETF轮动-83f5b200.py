# Clone from JoinQuant
# postId: 83f5b2005791326d669c6f0a5bef03ba
# backtestId: f5c5aab2db9be65a00c34834250bd702
# title: ******向】拒绝臃肿缝合怪！极简ETF轮动

# 极简纯净版：七星 ETF 动量轮动策略 (专为 2万元 实盘定制)
# 彻底切除小市值模块，0股票持仓，消除5元最低佣金损耗
# 运行节拍：11:00盈利保护巡检，14:45卖出，14:50买入

import pandas as pd
import numpy as np
import math
import datetime
from jqdata import *

def initialize(context):
    set_backtest()
    set_params(context)
    set_strategy_params(context)
    schedule_tasks(context)

def set_backtest():
    set_option("avoid_future_data", True)
    set_benchmark("159919.XSHE") # 以沪深300ETF为基准
    set_option("use_real_price", True)

    # 设定真实滑点
    set_slippage(PriceRelatedSlippage(0.002), type="fund")
    
    # 设定真实手续费：ETF免印花税，买卖均万三，单笔最低5元
    set_order_cost(
        OrderCost(
            open_tax=0, close_tax=0, 
            open_commission=0.0003, close_commission=0.0003, 
            min_commission=5
        ), 
        type="fund"
    )

def set_params(context):
    g.starting_cash = context.portfolio.total_value
    g.strategy_holdings = [] # 记录当前持仓的ETF
    g.position_highs = {}    # 记录持仓以来的最高价
    g.rankings_cache = {'date': None, 'data': None} # 每日排名缓存

def set_strategy_params(context):
    # 核心大类资产 ETF 弹药库 (涵盖全球指数、科技、红利、商品)
    g.etf_pool = [
        "518880.XSHG", "159980.XSHE", "159985.XSHE", "501018.XSHG",
        "161226.XSHE", "159981.XSHE", "513100.XSHG", "159509.XSHE",
        "513290.XSHG", "513500.XSHG", "159529.XSHE", "513400.XSHG",
        "513520.XSHG", "513030.XSHG", "513080.XSHG", "513310.XSHG",
        "513730.XSHG", "159792.XSHE", "513130.XSHG", "513050.XSHG",
        "159920.XSHE", "513690.XSHG", "510300.XSHG", "510500.XSHG",
        "510050.XSHG", "510210.XSHG", "159915.XSHE", "588080.XSHG",
        "512100.XSHG", "563360.XSHG", "563300.XSHG", "512890.XSHG",
        "159967.XSHE", "512040.XSHG", "159201.XSHE", "511380.XSHG",
        "511010.XSHG", "511220.XSHG",
    ]    
    
    # 动量评分核心参数
    g.lookback_days = 25       # 动量回溯周期
    g.holdings_num = 1         # 满仓持有排名第 1 的ETF（资金极度集中）
    g.defensive_etf = "511880.XSHG" # 银华日利货币ETF（全市场大跌时的避风港）
    
    # 分数与止损阈值
    g.min_score_threshold = 0  # 动量得分必须大于0才能买入
    g.max_score_threshold = 100.0
    g.loss = 0.97              # 近期连续下跌止损判定
    
    # 过滤参数
    g.enable_volume_check = True
    g.volume_lookback = 5
    g.volume_threshold = 2
    g.volume_return_limit = 1
    
    g.use_short_momentum_filter = True
    g.short_lookback_days = 10
    g.short_momentum_threshold = 0.0
    
    # 盈利动态保护参数（防过山车）
    g.enable_profit_protection = True
    g.profit_protection_lookback = 1
    g.profit_protection_threshold = 0.05 # 最高点回撤5%强制锁利
    
    # 溢价率过滤（防止买入被游资爆炒的跨境ETF）
    g.enable_premium_filter = True      
    g.premium_threshold = 0.05           # 溢价率超过5%坚决不买

def schedule_tasks(context):
    unschedule_all()
    # 每天 11:00 巡检一次，如果盘中从最高点回撤超过5%，立刻锁利出局
    run_daily(profit_protection_check, time='11:00')
    
    # 【核心调仓节拍：尾盘执行，躲避洗盘】
    run_daily(strategy_sell, time='14:45') # 卖出弱势/破位品种
    run_daily(strategy_buy, time='14:50')  # 满仓买入全市场最强品种

# ======================== 核心交易逻辑 ========================

def profit_protection_check(context):
    if not g.enable_profit_protection: return
    for sec in g.strategy_holdings[:]:
        if sec not in context.portfolio.positions: continue
        pos = context.portfolio.positions[sec]
        if pos.total_amount > 0 and check_profit_protection(sec, context):
            log.info(f"🛡️【盈利保护】{sec} 触发最高点回撤锁定防线，落闸锁利！")
            smart_order_target_value(sec, 0, context)

def check_profit_protection(security, context):
    hist = attribute_history(security, g.profit_protection_lookback, '1d', ['high'])
    if hist.empty or len(hist) < g.profit_protection_lookback: return False
    max_high = hist['high'].max()
    current_price = get_current_data()[security].last_price
    return current_price <= max_high * (1 - g.profit_protection_threshold)

def get_premium_rate(code, date, max_back_days=5):
    """获取ETF溢价率"""
    price_data = get_price(code, start_date=date, end_date=date, frequency='daily', fields=['close'])
    if price_data.empty: return None
    price = price_data['close'].iloc[0]

    net_value = None
    start_date = date - datetime.timedelta(days=max_back_days * 2)
    trade_days = [pd.to_datetime(d).date() for d in get_trade_days(start_date=start_date, end_date=date)]
    
    for dt in reversed(trade_days):
        if dt > date: continue
        net_data = get_extras('unit_net_value', code, start_date=dt, end_date=dt, df=True)
        if not net_data.empty and not pd.isna(net_data[code].iloc[0]):
            net_value = net_data[code].iloc[0]
            break
        try:
            q = query(finance.FUND_NET_VALUE).filter(finance.FUND_NET_VALUE.code == code, finance.FUND_NET_VALUE.day == dt)
            net_df = finance.run_query(q)
            if not net_df.empty:
                net_value = net_df['net_value'].iloc[0]
                break
        except:
            continue

    if net_value is None or net_value == 0: return None
    return (price - net_value) / net_value

def calculate_momentum_metrics(context, etf):
    """计算单只ETF的动量与平滑度评分"""
    try:
        lookback = max(g.lookback_days, g.short_lookback_days) + 20
        prices = attribute_history(etf, lookback, '1d', ['close', 'high'])
        if len(prices) < g.lookback_days: return None

        current_price = get_current_data()[etf].last_price
        price_series = np.append(prices['close'].values, current_price)

        # 保护性过滤
        if check_profit_protection(etf, context): return None

        # 溢价率过滤
        if g.enable_premium_filter:
            prev_date = get_trade_days(end_date=context.current_dt.date(), count=2)[0]
            premium = get_premium_rate(etf, prev_date)
            if premium is not None and premium > g.premium_threshold: return None

        # 计算长期年化收益
        recent_y = np.log(price_series[-(g.lookback_days + 1):])
        x = np.arange(len(recent_y))
        weights = np.linspace(1, 2, len(recent_y))
        slope, intercept = np.polyfit(x, recent_y, 1, w=weights)
        ann_ret = math.exp(slope * 250) - 1
        
        # 计算R2平滑度
        ss_res = np.sum(weights * (recent_y - (slope * x + intercept)) ** 2)
        ss_tot = np.sum(weights * (recent_y - np.mean(recent_y)) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot != 0 else 0
        
        # 综合得分：涨得快(ann_ret) 且 涨得稳(r2)
        score = ann_ret * r2

        # 连跌剔除
        if len(price_series) >= 4:
            if min(price_series[-1]/price_series[-2], price_series[-2]/price_series[-3], price_series[-3]/price_series[-4]) < g.loss:
                return None

        return {'etf': etf, 'score': score}
    except:
        return None

def get_cached_rankings(context):
    """获取全市场ETF动量排名"""
    today = context.current_dt.date()
    if g.rankings_cache.get('date') != today:
        etf_metrics = []
        current_data = get_current_data()
        for etf in g.etf_pool:
            if current_data[etf].paused: continue
            metrics = calculate_momentum_metrics(context, etf)
            if metrics and (g.min_score_threshold < metrics['score'] < g.max_score_threshold):
                etf_metrics.append(metrics)
        etf_metrics.sort(key=lambda x: x['score'], reverse=True)
        g.rankings_cache = {'date': today, 'data': etf_metrics}
    return g.rankings_cache['data']

def check_defensive_etf_available(context):
    data = get_current_data()
    etf = g.defensive_etf
    if data[etf].paused: return False
    return True

def smart_order_target_value(security, target_value, context):
    data = get_current_data()
    if data[security].paused: return False
    price = data[security].last_price
    if price == 0: return False

    cur_pos = context.portfolio.positions.get(security, None)
    cur_amount = cur_pos.total_amount if cur_pos else 0
    
    target_amount = int(target_value / price)
    target_amount = (target_amount // 100) * 100 # 向下取整到手
    
    diff = target_amount - cur_amount
    if diff == 0: return False

    o = order(security, diff)
    if o:
        if target_value == 0 and security in g.strategy_holdings:
            g.strategy_holdings.remove(security)
            log.info(f"📉【卖出平仓】清空 {get_security_info(security).display_name} ({security})")
        elif target_value > 0 and security not in g.strategy_holdings:
            g.strategy_holdings.append(security)
            log.info(f"📈【全仓突击】买入全市场最强: {get_security_info(security).display_name} ({security})")
        return True
    return False

def strategy_sell(context):
    ranked = get_cached_rankings(context)
    target_etfs = []
    
    # 挑选前 N 名进入目标池
    for m in ranked[:g.holdings_num]:
        if m['score'] >= g.min_score_threshold:
            target_etfs.append(m['etf'])
            
    # 如果全市场都没有好机会，目标锁定为防御型货币ETF
    if not target_etfs and check_defensive_etf_available(context):
        target_etfs = [g.defensive_etf]
        
    target_set = set(target_etfs)

    # 卖出不在目标池里的原持仓
    for s in g.strategy_holdings[:]:
        if s not in context.portfolio.positions: continue
        if s not in target_set:
            smart_order_target_value(s, 0, context)

def strategy_buy(context):
    ranked = get_cached_rankings(context)
    target_etfs = []
    for m in ranked:
        if len(target_etfs) >= g.holdings_num: break
        target_etfs.append(m['etf'])

    if not target_etfs:
        if check_defensive_etf_available(context):
            target_etfs = [g.defensive_etf]
        else: return

    # 如果有该卖的还没卖完，暂停买入（防资金超限）
    to_sell = [s for s in g.strategy_holdings if s not in target_etfs]
    if to_sell: return

    # 满仓干！
    total_val = context.portfolio.total_value
    val_per = total_val / len(target_etfs)

    for etf in target_etfs:
        smart_order_target_value(etf, val_per, context)