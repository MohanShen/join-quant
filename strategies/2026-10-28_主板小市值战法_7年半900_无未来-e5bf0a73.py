# Clone from JoinQuant
# postId: e5bf0a736e0469ded0691114f8f49102
# backtestId: 56a6232eb774a3dd6c7aa130d990a303
# title: 主板小市值战法 7年半900+%无未来

# -*- coding: utf-8 -*-
from jqdata import *
import pandas as pd
import datetime

def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option("avoid_future_data", True)
    log.set_level('order', 'info')
    log.set_level('system', 'info')
    # 每周一开盘调仓 9:30执行
    run_weekly(select_and_rebalance, weekday=1, time='open')
    # 每日收盘风控
    # run_daily(check_drawdown_and_cool_down, time='close')
    # 每日收盘个股止盈判断
    run_daily(check_sell_rule, time='close')

    g.in_cool_down = False
    g.cool_down_end_date = None
    g.max_asset = context.portfolio.total_value


def get_filtered_stocks(context):
    today_dt = context.current_dt
    prev_date = context.previous_date

    if g.in_cool_down and today_dt <= g.cool_down_end_date:
        return []

    # 获取全部A股
    all_stocks = get_all_securities(['stock'], date=prev_date)
    stock_candidates = [
        code for code in all_stocks.index
        if not code.startswith('300')
        and not code.startswith('8')
        and not code.startswith('688')
    ]

    # 过滤ST、停牌
    current_data = get_current_data()
    stock_pool_pre = []
    for code in stock_candidates:
        cd = current_data[code]
        if cd.is_st or cd.paused:
            continue
        stock_pool_pre.append(code)
    if len(stock_pool_pre) == 0:
        return []

    # 读取估值表
    q_val_pool = query(valuation.code, valuation.market_cap, valuation.pe_ratio)\
        .filter(valuation.code.in_(stock_pool_pre))
    df_val_pool = get_fundamentals(q_val_pool, date=prev_date).dropna()
    if len(df_val_pool) ==0:
        return []
    cap_cutoff = df_val_pool['market_cap'].quantile(0.2)
    df_cap_filtered = df_val_pool[df_val_pool['market_cap'] <= cap_cutoff]
    stock_pool = list(df_cap_filtered['code'])
    if len(stock_pool) ==0:
        return []

    # 读取财务指标
    q_ind = query(indicator.code, indicator.adjusted_profit).filter(indicator.code.in_(stock_pool))
    df_ind = get_fundamentals(q_ind, date=prev_date).dropna()
    df_ind = df_ind.set_index("code")

    df_val = df_cap_filtered.set_index("code")
    stock_result = []

    for code in stock_pool:
        if code not in df_ind.index:
            continue
        try:
            adjusted_profit = df_ind.loc[code, "adjusted_profit"]
            pe = df_val.loc[code, "pe_ratio"]
            market_cap = df_val.loc[code, "market_cap"]
        except Exception:
            continue
        if pd.isna(adjusted_profit) or pd.isna(pe):
            continue
        if adjusted_profit <= 0:
            continue
        growth = 0.2
        peg = pe / growth

        # 成交量：用prev_date历史数据
        df_price = get_price(code, count=11, end_date=prev_date, fields=['volume'])
        if len(df_price) <11:
            continue
        vol_prev = df_price['volume'].iloc[-2]
        vol_10_mean = df_price['volume'].iloc[:-2].mean()
        if vol_10_mean <= 1e-6:
            continue
        vol_factor = vol_prev / vol_10_mean

        stock_result.append({
            'code': code,
            'peg': peg,
            'market_cap': market_cap,
            'vol_factor': vol_factor
        })

    if len(stock_result) <2:
        return [x['code'] for x in stock_result]

    df_score = pd.DataFrame(stock_result)
    df_score['peg_norm'] = (df_score['peg'] - df_score['peg'].min())/(df_score['peg'].max()-df_score['peg'].min()) *10
    df_score['cap_norm'] = (1 - (df_score['market_cap'] - df_score['market_cap'].min())/(df_score['market_cap'].max()-df_score['market_cap'].min())) *10
    df_score['total_score'] = df_score['peg_norm'] + df_score['cap_norm']
    df_score = df_score.sort_values('total_score', ascending=False)
    top2 = list(df_score.head(2)['code'])
    return top2


def check_drawdown_and_cool_down(context):
    today_dt = context.current_dt
    if g.in_cool_down and today_dt > g.cool_down_end_date:
        g.in_cool_down = False
        g.cool_down_end_date = None
        g.max_asset = context.portfolio.total_value
        log.info(f"冷却期结束，重置总资产基准：{g.max_asset:.2f}")
        return
    if g.in_cool_down:
        return

    current_asset = context.portfolio.total_value
    if current_asset > g.max_asset:
        g.max_asset = current_asset
        log.info(f"新高，更新最大资产基准：{g.max_asset:.2f}")
    asset_drawdown = (current_asset - g.max_asset) / g.max_asset
    trigger = False
    cool_days = 30
    if asset_drawdown <= -0.10:
        log.info(f"总资产回撤{asset_drawdown:.2%}，触发60天空仓冷却")
        trigger = True
        cool_days = 60
    else:
        index_rules = {'000688.XSHG': -0.15, '000300.XSHG': -0.10}
        for idx_code, threshold in index_rules.items():
            df = get_price(idx_code, count=20, end_date=today_dt, fields=['high','close'])
            if len(df)<20:
                continue
            peak_price = df['high'].max()
            current_price = df['close'].iloc[-1]
            drawdown = (current_price - peak_price)/peak_price
            if drawdown <= threshold:
                log.info(f"{idx_code}回撤{drawdown:.2%}，触发30天空仓冷却")
                trigger = True
                cool_days =30
                break
    if trigger:
        g.in_cool_down = True
        g.cool_down_end_date = today_dt + datetime.timedelta(days=cool_days)
        current_data = get_current_data()
        for stock_code, pos_info in context.portfolio.positions.items():
            if pos_info.sellable_amount <=0:
                continue
            if current_data[stock_code].paused:
                continue
            order_target(stock_code, 0)


def select_and_rebalance(context):
    today_dt = context.current_dt
    month = today_dt.month
    current_data = get_current_data()
    if month in [1,4,12]:
        log.info(f"{month}月强制空仓")
        for stock_code, pos_info in context.portfolio.positions.items():
            if pos_info.sellable_amount <=0:
                continue
            if current_data[stock_code].paused:
                continue
            order_target(stock_code,0)
        return

    target_stocks = get_filtered_stocks(context)
    # 平仓不在目标列表的股票
    for stock_code, pos_info in context.portfolio.positions.items():
        if stock_code not in target_stocks:
            if pos_info.sellable_amount <=0:
                continue
            if current_data[stock_code].paused:
                continue
            order_target(stock_code,0)
    if len(target_stocks)==0:
        log.info("无选股标的，全部清仓")
        return
    cash = context.portfolio.available_cash
    per_stock_cash = cash / len(target_stocks)
    for s in target_stocks:
        if current_data[s].paused:
            log.info(f"{s}停牌，跳过买入")
            continue
        # ✅ 开盘直接取当日盘中最新价格，9:30执行时就是当日开盘价，不触发FutureDataError
        price = current_data[s].last_price
        if price <=0:
            continue
        max_shares = int(per_stock_cash / price)
        buy_shares = max_shares //100 *100
        if buy_shares >=100:
            order(s, buy_shares)
    log.info("本周选中标的：%s" % target_stocks)


def check_sell_rule(context):
    """每日收盘个股止盈，收盘任务，允许读取当日日线"""
    today_dt = context.current_dt
    month = today_dt.month
    if month in [1,4,12]:
        return
    current_data = get_current_data()
    pos_dict = context.portfolio.positions
    for stock_code, pos_info in pos_dict.items():
        if pos_info.sellable_amount <=0:
            continue
        avg_cost = pos_info.avg_cost
        if avg_cost <=0:
            continue
        if current_data[stock_code].paused:
            continue
        current_price = pos_info.price
        profit_rate = (current_price - avg_cost)/avg_cost
        df_price = get_price(stock_code, count=20, end_date=today_dt, fields=['close'])
        if len(df_price) <20:
            continue
        ma20 = df_price['close'].rolling(20).mean().iloc[-1]
        if profit_rate >=0.30 or current_price > ma20 * 1.2:
            order_target(stock_code, 0)
            log.info(f"止盈卖出 {stock_code},收益率:{profit_rate:.2%}")
