# Clone from JoinQuant
# postId: 66180d0346502e15ee8742998e36cca3
# backtestId: 875eef686d2cd3cec0522a350237e178
# title: 最新升级的强势股策略，下载满50个删除

# 克隆自聚宽文章：https://www.joinquant.com/post/77676
# 标题：低位启动强势股主升段
# 作者：qaz1912
from jqdata import *
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, date, time

def initialize(context):
    log.set_level('order', 'error')
    set_option('use_real_price', True)
    set_option("avoid_future_data", True)
    set_slippage(FixedSlippage(0.005))
    set_order_cost(OrderCost(close_tax=0.0005, open_commission=0.0002, close_commission=0.0002, min_commission=5), type='stock')
    set_benchmark('399303.XSHE')

    g.information = {}
    g.sold_stocks = set()
    g.base_stocks = []
    g.today_pick = []
    g.pick_cache_date = ''
    g.minute_sell_cache = {}
    g.close_sell_cache = {}
    g.today_high = {}
    g.buy_list = []

    g.max_position_pct = 1
    g.max_hold_count = 10

    run_weekly(prepare_base_stocks, 1, '09:10')
    run_daily(before_open, time='09:11')
    run_daily(precompute_minute_sell_cache, time='09:11')
    run_daily(prepare_buy_list, time='09:27')
    run_daily(get_buy, time='09:31')
    run_daily(get_close_sell, time='11:25')
    run_daily(get_close_sell, time='13:30')
    run_daily(get_close_sell, time='14:55')
    run_daily(get_minute_sell, time='every_bar')

def before_open(context):
    t_day = context.current_dt.strftime('%Y%m%d')
    y_day = context.previous_date.strftime('%Y-%m-%d')
    if not g.base_stocks:
        prepare_base_stocks(context)
    g.target_list = filter_first_board(g.base_stocks, y_day)
    log.info(f"[盘前] 首板筛选: {len(g.target_list)}只")
    g.target_list = filter_volume_price(g.target_list, y_day)
    log.info(f"[盘前] 量价过滤: {len(g.target_list)}只")
    g.target_list = filter_high_volatility(g.target_list, y_day)
    log.info(f"[盘前] 过滤高波动股票: {len(g.target_list)}只")
    g.today_pick = g.target_list.copy()
    g.pick_cache_date = t_day

def filter_high_volatility(stock_list, y_day):
    if not stock_list:
        return []
    df = get_price(stock_list, end_date=y_day, frequency='1d',
                   fields=['high', 'low'], count=5, panel=False,
                   skip_paused=True, fill_paused=False)
    if df.empty:
        return stock_list
    grp = df.groupby('code')
    chg = (grp['high'].max() - grp['low'].min()) / grp['low'].min()
    return chg[chg <= 0.3].index.tolist()

def filter_volume_price(stock_list, y_day):
    if not stock_list:
        return []
    df = get_price(stock_list, end_date=y_day, frequency='1d',
                   fields=['close', 'open', 'high', 'volume', 'money'],
                   count=35, skip_paused=True, fq='pre', panel=False)
    if df.empty:
        return []
    candidates = []
    for code, group in df.groupby('code'):
        if len(group) < 6:
            continue
        group = group.sort_values('time').reset_index(drop=True)
        last = group.iloc[-1]
        d_b1 = group.iloc[-2]
        d_b2 = group.iloc[-3]
        d_b3 = group.iloc[-4]
        if last.money < 5e8 or last.money > 30e8:
            continue
        if d_b1.volume <= 0 or last.volume < d_b1.volume * 2:
            continue
        if len(group) >= 30:
            prev_vols = group.volume.iloc[-6:-1].values
            if len(prev_vols) == 5 and prev_vols.min() > 0:
                avg_vol, min_vol = prev_vols.mean(), prev_vols.min()
                if (last.volume > avg_vol * 8 or last.volume > min_vol * 12) and last.close > group.high.iloc[-40:-1].max():
                    continue
        if not (d_b1.close > d_b1.open and d_b2.close > d_b2.open):
            continue
        if d_b2.close == 0 or d_b3.close == 0:
            continue
        g1 = (d_b1.close - d_b2.close) / d_b2.close
        g2 = (d_b2.close - d_b3.close) / d_b3.close
        if g1 >= 0.05 or g2 >= 0.05:
            continue
        candidates.append(code)
    return candidates

def filter_auction(stock_list, y_day, t_day_str):
    if not stock_list:
        return []
    hist_df = get_price(stock_list, end_date=y_day, frequency='1d',
                        fields=['close', 'volume'], count=1,
                        skip_paused=True, panel=False, fill_paused=False)
    if hist_df.empty:
        return []
    start = f'{t_day_str} 09:15:00'
    end = f'{t_day_str} 09:26:00'
    qualified = []
    for stock in stock_list:
        try:
            auction = get_call_auction(stock, start_date=start, end_date=end, fields=['time', 'volume', 'current'])
            if auction.empty:
                continue
            last = auction.iloc[-1]
            hist = hist_df[hist_df['code'] == stock].iloc[0]
            if (last.volume / hist['volume'] >= 0.03 and 1.0 < last.current / hist['close'] < 1.06):
                qualified.append(stock)
        except:
            continue
    return qualified

def prepare_buy_list(context):
    t_day = context.current_dt.strftime('%Y%m%d')
    t_day_str = context.current_dt.strftime('%Y-%m-%d')
    y_day = context.previous_date.strftime('%Y-%m-%d')
    if g.pick_cache_date != t_day:
        g.today_pick = before_open(context)
        g.pick_cache_date = t_day
    holdings = [s for s, p in context.portfolio.positions.items() if p.total_amount > 0]
    candidates = [s for s in g.today_pick if s not in holdings]
    log.info(f"[选股] 候选标的(排除持仓后): {candidates}")
    if not candidates:
        g.buy_list = []
        return
    qualified = filter_auction(candidates, y_day, t_day_str)
    log.warning(f"[选股] 集合竞价过滤后: {qualified}")
    g.buy_list = qualified

def get_buy(context):
    t_day = context.current_dt.strftime('%Y%m%d')
    c_data = get_current_data()
    holdings = [s for s, p in context.portfolio.positions.items() if p.total_amount > 0]
    if len(holdings) >= g.max_hold_count:
        log.info(f"[买入] 持仓已达上限 {g.max_hold_count} 只")
        return
    qualified = g.buy_list
    if not qualified:
        return
    qualified = [s for s in qualified if s not in holdings]
    if not qualified:
        return
    slots = g.max_hold_count - len(holdings)
    to_buy = qualified[:slots]
    total = context.portfolio.total_value
    max_per = total * g.max_position_pct
    per_stock = min(context.portfolio.available_cash / len(to_buy), max_per) if to_buy else 0
    log.info(f"[买入] 当前持仓{len(holdings)}只，可再买{slots}只，每只分配{per_stock:.2f}")
    for s in to_buy:
        try:
            current_price = c_data[s].last_price
            if current_price <= 0:
                log.info(f"[买入跳过] {s}: 当前价格无效")
                continue
            shares = int(per_stock / current_price / 100) * 100
            if shares >= 100:
                order_value(s, per_stock)
                log.warning(f"[买入下单] {s}: 当前价{current_price:.2f}, 计划金额{per_stock:.2f}, 预计{shares}股")
                if not hasattr(g, 'information'):
                    g.information = {}
                g.information[s] = {'buy_date': t_day}
            else:
                log.info(f"[买入跳过] {s}: 资金不足1手")
        except Exception as e:
            log.info(f"[买入错误] {s}: {e}")

def get_close_sell(context):
    t_day = context.current_dt.strftime("%Y%m%d")
    hold = [s for s, p in context.portfolio.positions.items()
            if p.total_amount > 0 and g.information.get(s, {}).get('buy_date') != t_day]
    if not hold:
        return
    metrics = g.close_sell_cache
    c_data = get_current_data()
    for s in hold:
        if s not in metrics:
            continue
        pos = context.portfolio.positions[s]
        cd = c_data[s]
        cp = cd.last_price
        yc = metrics[s]['y_close']
        ma5 = metrics[s]['ma5']
        dg = (cp - yc) / yc
        pp = (cp - pos.avg_cost) / pos.avg_cost
        if cp >= cd.high_limit * 0.99:
            continue
        sell, reason = False, ""
        if pp > 0.5:
            sell, reason = True, "收益>50%"
        if dg < -0.02:
            sell, reason = True, f"当日跌幅<-2% ({dg*100:.2f}%)"
        elif cp < cd.day_open * 0.96:
            sell, reason = True, f"当前价<开盘价-4%"
        elif pp <= -0.07:
            sell, reason = True, f"收益<=-7%"
        elif cp < ma5 * 0.97:
            sell, reason = True, f"跌破5日均线-3%"
        if sell:
            order_target_value(s, 0)
            log.error(f"[卖出] {s}: {reason}，清仓")

def get_minute_sell(context):
    t_day_time = context.current_dt.time()
    if t_day_time < time(9, 30) or t_day_time > time(11, 25):
        return
    y_day = context.previous_date
    t_day = context.current_dt.strftime("%Y%m%d")
    hold = [s for s, p in context.portfolio.positions.items()
            if p.total_amount > 0 and g.information.get(s, {}).get('buy_date') != t_day]
    if not hold:
        return
    c_data = get_current_data()
    for s in hold:
        cache = g.minute_sell_cache.get(s)
        if not cache or cache['date'] != y_day:
            continue
        cd = c_data[s]
        cp = cd.last_price
        if cp >= cd.high_limit * 0.99:
            continue

        # 一字板放量检测：昨日一字板，今日量比>=8倍且未涨停
        y_hl = cache.get('y_high_limit', 0)
        y_op = cache.get('y_open', 0)
        if y_hl > 0 and y_op >= y_hl * 0.99 and cache['y_close'] >= y_hl * 0.99:
            t_now_str = context.current_dt.strftime('%Y-%m-%d')
            df_today = get_price(s, start_date=t_now_str, end_date=context.current_dt,
                                 frequency='1m', fields=['volume'], skip_paused=False)
            today_vol = df_today['volume'].sum() if not df_today.empty else 0
            y_vol = cache.get('y_volume', 0)
            if y_vol > 0 and today_vol >= y_vol * 8 and cp < cd.high_limit * 0.99:
                order_target_value(s, 0)
                log.error(f"[一字板放量] {s}: 昨一字板, 今量比{today_vol/y_vol:.1f}倍, 未涨停, 清仓")
                g.today_high.pop(s, None)
                continue

        if cache['y_day_gain'] >= 0:
            continue
        th = g.today_high.get(s, 0)
        if cp > th:
            g.today_high[s] = cp
            th = cp
        chr_val = (th - cache['y_close']) / cache['y_close'] if cache['y_close'] > 0 else 0
        if chr_val > 0.03:
            lt = max(0.005, 0.02 - (chr_val - 0.01) * 0.5)
            if cp < th * (1 - lt):
                order_target_value(s, 0)
                log.error(f"[线性止盈] {s}: 昨日跌幅{cache['y_day_gain']*100:.2f}%, 冲高{chr_val*100:.2f}%，清仓")
                g.today_high.pop(s, None)

def filter_first_board(stock_list, y_day):
    if not stock_list:
        return []
    df = get_price(stock_list, end_date=y_day, frequency='daily',
                   fields=['close', 'high_limit'], count=2,
                   panel=False, fill_paused=False, skip_paused=False)
    if df.empty or len(df['time'].unique()) < 2:
        return []
    df['is_limit'] = df['close'] == df['high_limit']
    groups = df[df['is_limit']].groupby('time')['code'].apply(set)
    if len(groups) >= 2:
        return list(groups.iloc[-1] - groups.iloc[-2])
    elif len(groups) == 1:
        return list(groups.iloc[-1])
    return []

def precompute_minute_sell_cache(context):
    y_day = context.previous_date
    pos = list(context.portfolio.positions.keys())
    if not pos:
        g.minute_sell_cache = {}
        g.close_sell_cache = {}
        return
    # 加一字板放量所需字段：open, high_limit, volume
    df2 = get_price(pos, end_date=y_day, frequency='1d',
                    fields=['close', 'open', 'high', 'high_limit', 'volume'], count=2, panel=False,
                    skip_paused=False, fill_paused=True)
    for s, sub in df2.groupby('code'):
        if len(sub) >= 2:
            yc, pc = sub['close'].iloc[-1], sub['close'].iloc[-2]
            g.minute_sell_cache[s] = {
                'y_close': yc,
                'y_high': sub['high'].iloc[-1],
                'y_open': sub['open'].iloc[-1],
                'y_high_limit': sub['high_limit'].iloc[-1],
                'y_volume': sub['volume'].iloc[-1],
                'prev_close': pc,
                'y_day_gain': (yc - pc) / pc if pc > 0 else 0,
                'date': y_day
            }
    df5 = get_price(pos, end_date=y_day, frequency='1d',
                    fields=['close'], count=5, panel=False,
                    skip_paused=False, fill_paused=True)
    g.close_sell_cache = {}
    for s, sub in df5.groupby('code')['close']:
        if len(sub) >= 2:
            g.close_sell_cache[s] = {'y_close': sub.iloc[-1], 'ma5': sub.mean()}
    g.today_high.clear()

def prepare_base_stocks(context):
    by_date = context.previous_date - timedelta(days=60)
    stock_list = list(get_all_securities(['stock'], date=by_date).index)
    stock_list = [code for code in stock_list if not (
        code.startswith(('3', '68', '4', '8', '9'))
    )]
    g.base_stocks = get_fundamentals(
        query(valuation.code).filter(
            valuation.code.in_(stock_list),
            valuation.circulating_market_cap.between(30, 300)
        ),
        date=by_date
    )['code'].tolist()
    log.info(f"[基础股票池]：{len(g.base_stocks)}只 (日期:{by_date})")

def after_trading_end(context):
    g.sold_stocks.clear()
    cur = set(context.portfolio.positions.keys())
    g.information = {k: v for k, v in g.information.items() if k in cur}
    g.minute_sell_cache = {k: v for k, v in g.minute_sell_cache.items() if k in cur}
    g.close_sell_cache = {k: v for k, v in g.close_sell_cache.items() if k in cur}
    g.today_high.clear()