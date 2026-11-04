# Clone from JoinQuant
# postId: 724cf7e414044e4ca05e10c5075763d4
# backtestId: 82fc0626b45c290da26fd0e9b12f770a
# title: Q MT限制后可继续使用方案,聚宽信号如何同步

# 低位3连阳 + 首板高开 合并策略 - 聚宽
#
# 两套选股独立运行，09:27 合并买入；持仓打来源标签，卖出按原策略各自执行。
# 重叠标的 source=both：分钟止盈走低位，定点卖出两套条件任一触发即卖。
#
# 口径对齐：
# - 低位3连阳首板接力.py（股池周更+市值、竞价取 09:26 末笔、09:27 买入）
# - 聚宽一进二.py 仅首板高开（日频股池、竞价取 09:15 首笔、高开 0%~6% 不含端点）
# - 低位3连阳_首板高开_QMT.py（合并架构）
#
# 回测请用 1 分钟频率（分钟止盈依赖 every_bar）。

from jqdata import *
import pandas as pd
from datetime import datetime, timedelta, date, time

STRATEGY_NAME = '低位3连阳_首板高开'


def initialize(context):
    log.set_level('order', 'error')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_slippage(FixedSlippage(0.005))
    set_order_cost(OrderCost(
        close_tax=0.0005, open_commission=0.0002,
        close_commission=0.0002, min_commission=5
    ), type='stock')
    set_benchmark('399303.XSHE')

    _init_g()
    _schedule()
    log.info('=' * 60)
    log.info('%s 初始化' % STRATEGY_NAME)
    log.info('低位3连阳=%s  首板高开=%s  最多持仓=%d' % (
        '开' if g.enable_low3 else '关',
        '开' if g.enable_sbgk else '关',
        g.max_hold_count))
    log.info('回测请用 1 分钟K；买入 09:27')
    log.info('=' * 60)


def after_code_changed(context):
    unschedule_all()
    _init_params()
    _schedule()


def _init_g():
    _init_params()
    g.information = {}
    g.base_stocks = []
    g.today_pick_low3 = []
    g.today_pick_sbgk = []
    g.pick_cache_date = ''
    g.minute_sell_cache = {}
    g.close_sell_cache = {}
    g.today_high = {}
    g.n_days_limit_up_list = []


def _init_params():
    g.enable_low3 = True
    g.enable_sbgk = True
    g.max_hold_count = 10
    g.max_position_pct = 1.0

    g.cap_min_yi = 30.0
    g.cap_max_yi = 300.0
    g.list_days_min = 60

    g.sbgk_list_days = 50
    g.sbgk_avg_price_ratio_min = 0.07
    g.sbgk_money_min = 5.5e8
    g.sbgk_money_max = 20e8
    g.sbgk_market_cap_min = 70.0
    g.sbgk_circulating_cap_max = 520.0
    # 对齐聚宽一进二：current_ratio<=1 或 >=1.06 剔除，即 1.0 < x < 1.06
    g.sbgk_open_ratio_min = 1.0
    g.sbgk_open_ratio_max = 1.06
    g.sbgk_volume_ratio_min = 0.03


def _schedule():
    run_weekly(prepare_base_stocks, 1, '09:10')
    run_daily(before_open, time='09:11')
    run_daily(precompute_sell_cache, time='09:11')
    run_daily(get_buy, time='09:27')
    run_daily(get_close_sell, time='11:25')
    run_daily(get_close_sell, time='13:30')
    run_daily(get_close_sell, time='14:50')
    run_daily(get_close_sell, time='14:55')
    run_daily(get_minute_sell, time='every_bar')


# ---------- 板块 / 工具 ----------

def _is_sbgk_board(stock):
    """对齐聚宽一进二 filter_kcbj：剔除科创/北交，保留主板+创业板。"""
    s = str(stock)
    if s[0] in ('4', '8') or s[:2] == '68':
        return False
    return True


def _src_of(stock):
    rec = g.information.get(stock) or {}
    return str(rec.get('source', '') or '')


def _holdings(context):
    return [s for s, p in context.portfolio.positions.items() if p.total_amount > 0]


def _held_not_bought_today(context):
    """对齐低位原版：非今日买入的持仓。合并后仅处理本策略有标签的票。"""
    t_day = context.current_dt.strftime('%Y%m%d')
    out = []
    for s, p in context.portfolio.positions.items():
        if p.total_amount <= 0:
            continue
        rec = g.information.get(s) or {}
        if not rec:
            continue
        if str(rec.get('buy_date', '') or '') == t_day:
            continue
        out.append(s)
    return out


# ---------- 低位基础股票池（对齐原版：周更 + 市值 30~300） ----------

def prepare_base_stocks(context):
    by_date = context.previous_date - timedelta(days=g.list_days_min)
    stock_list = list(get_all_securities(['stock'], date=by_date).index)
    current_data = get_current_data()
    stock_list = [code for code in stock_list if not (
        code.startswith(('3', '68', '4', '8', '9'))
        or current_data[code].is_st
        or current_data[code].paused
        or '退' in current_data[code].name
    )]
    df = get_fundamentals(
        query(valuation.code).filter(
            valuation.code.in_(stock_list),
            valuation.circulating_market_cap.between(g.cap_min_yi, g.cap_max_yi)
        )
    )
    g.base_stocks = df['code'].tolist() if df is not None and not df.empty else []
    log.info('[基础股票池-低位] %d只（主板 流通市值%.0f~%.0f亿）' % (
        len(g.base_stocks), g.cap_min_yi, g.cap_max_yi))


# ---------- 首板高开股池 / 首板（对齐聚宽一进二） ----------

def get_hl_stock(stock_list, date1, days=1):
    if not stock_list:
        return []
    df = get_price(
        stock_list, end_date=date1, frequency='daily',
        fields=['close', 'high_limit', 'paused'],
        count=days, panel=False, fill_paused=False, skip_paused=False
    )
    if df is None or df.empty:
        return []
    h_s = df.query('close==high_limit and paused==0').groupby('code').size()
    return h_s.index.tolist()


def prepare_sbgk_first_board(context):
    """昨日涨停且前日未涨停。股池、新股、涨停判定对齐聚宽一进二。"""
    today = context.current_dt.date()
    yesterday = context.previous_date
    initial_list = get_all_securities('stock', yesterday).index.tolist()
    initial_list = [s for s in initial_list if _is_sbgk_board(s)]
    current_data = get_current_data()
    initial_list = [s for s in initial_list if not (
        current_data[s].is_st or current_data[s].paused or '退' in current_data[s].name
    )]
    cutoff = today - timedelta(days=g.sbgk_list_days)
    initial_list = [
        s for s in initial_list
        if get_security_info(s).start_date < cutoff
    ]

    if not g.n_days_limit_up_list:
        days = get_trade_days(end_date=yesterday, count=3)[:-1]
        for day in days:
            g.n_days_limit_up_list.append(get_hl_stock(initial_list, day, 1))

    hl_list = get_hl_stock(initial_list, yesterday, 1)
    g.n_days_limit_up_list.append(hl_list)
    hl1_list = set(g.n_days_limit_up_list[-2])
    first = [s for s in hl_list if s not in hl1_list]
    g.n_days_limit_up_list.pop(0)
    return first


# ---------- 盘前选股 ----------

def before_open(context):
    t_day = context.current_dt.strftime('%Y%m%d')
    y_day = context.previous_date.strftime('%Y-%m-%d')
    g.today_pick_low3 = []
    g.today_pick_sbgk = []

    if g.enable_low3:
        if not g.base_stocks:
            prepare_base_stocks(context)
        low3_u = filter_first_board(g.base_stocks, y_day)
        log.info('[盘前-低位] 首板: %d只' % len(low3_u))
        low3_u = filter_volume_price(low3_u, y_day)
        log.info('[盘前-低位] 量价过滤: %d只' % len(low3_u))
        low3_u = filter_high_volatility(low3_u, y_day)
        log.info('[盘前-低位] 过滤高波动: %d只 %s' % (len(low3_u), low3_u))
        g.today_pick_low3 = low3_u
    else:
        log.info('[盘前-低位] 已关闭')

    if g.enable_sbgk:
        first = prepare_sbgk_first_board(context)
        log.info('[盘前-首板高开] 首板: %d只' % len(first))
        sbgk_u = filter_sbgk_hist(first, context.previous_date)
        log.info('[盘前-首板高开] 历史条件: %d只 %s' % (len(sbgk_u), sbgk_u))
        g.today_pick_sbgk = sbgk_u
    else:
        log.info('[盘前-首板高开] 已关闭')

    g.pick_cache_date = t_day


def filter_first_board(stock_list, y_day):
    """低位原版：昨日涨停、前日未涨停。停牌 close 为 NaN，不会判为涨停。"""
    if not stock_list:
        return []
    df = get_price(stock_list, end_date=y_day, frequency='daily',
                   fields=['close', 'high_limit'], count=2,
                   panel=False, fill_paused=False, skip_paused=False)
    if df is None or df.empty or len(df['time'].unique()) < 2:
        return []
    df = df.copy()
    df['is_limit'] = df['close'] == df['high_limit']
    groups = df[df['is_limit']].groupby('time')['code'].apply(set)
    if len(groups) >= 2:
        return list(groups.iloc[-1] - groups.iloc[-2])
    if len(groups) == 1:
        return list(groups.iloc[-1])
    return []


def filter_volume_price(stock_list, y_day):
    if not stock_list:
        return []
    df = get_price(stock_list, end_date=y_day, frequency='1d',
                   fields=['close', 'open', 'high', 'volume', 'money'],
                   count=35, skip_paused=True, fq='pre', panel=False)
    if df is None or df.empty:
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
        if d_b2.volume <= 0 or d_b1.volume > d_b2.volume * 2:
            continue
        if len(group) >= 30:
            prev_vols = group.volume.iloc[-6:-1].values
            if len(prev_vols) == 5 and prev_vols.min() > 0:
                avg_vol, min_vol = prev_vols.mean(), prev_vols.min()
                if (last.volume > avg_vol * 8 or last.volume > min_vol * 12) and last.close > group.high.iloc[-30:-1].max():
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


def filter_high_volatility(stock_list, y_day):
    if not stock_list:
        return []
    df = get_price(stock_list, end_date=y_day, frequency='1d',
                   fields=['high', 'low'], count=5, panel=False,
                   skip_paused=True, fill_paused=False)
    if df is None or df.empty:
        return stock_list
    grp = df.groupby('code')
    chg = (grp['high'].max() - grp['low'].min()) / grp['low'].min()
    return chg[chg <= 0.2].index.tolist()


def filter_sbgk_hist(stock_list, y_day):
    """对齐聚宽一进二：获利比例、成交额、市值；左压单独做。"""
    if not stock_list:
        return []
    df = get_price(stock_list, end_date=y_day, frequency='1d',
                   fields=['close', 'volume', 'money'], count=1,
                   skip_paused=True, panel=False, fill_paused=False)
    if df is None or df.empty:
        return []
    mid = []
    for code, group in df.groupby('code'):
        row = group.iloc[-1]
        prev_close = float(row['close'] or 0)
        prev_volume = float(row['volume'] or 0)
        prev_amount = float(row['money'] or 0)
        if prev_close <= 0 or prev_volume <= 0:
            continue
        if prev_amount < g.sbgk_money_min or prev_amount > g.sbgk_money_max:
            continue
        avg_price_ratio = prev_amount / prev_volume / prev_close * 1.1 - 1.0
        if avg_price_ratio < g.sbgk_avg_price_ratio_min:
            continue
        mid.append(code)
    if not mid:
        return []

    cap_ok = []
    batch = 200
    for i in range(0, len(mid), batch):
        part = mid[i:i + batch]
        val = get_valuation(
            part, start_date=y_day, end_date=y_day,
            fields=['market_cap', 'circulating_market_cap']
        )
        if val is None or val.empty:
            continue
        val = val.copy()
        if 'code' not in val.columns:
            val = val.reset_index()
        for _, row in val.iterrows():
            code = row['code'] if 'code' in row.index else None
            if not code:
                continue
            mc = float(row['market_cap'] if 'market_cap' in row.index else 0) or 0
            cc = float(row['circulating_market_cap'] if 'circulating_market_cap' in row.index else 0) or 0
            if mc < g.sbgk_market_cap_min or cc > g.sbgk_circulating_cap_max:
                continue
            cap_ok.append(code)
    return filter_left_pressure(cap_ok, y_day)


def filter_left_pressure(stock_list, y_day):
    """对齐聚宽一进二 rise_low_volume：高点以来成交量须同步放大。"""
    if not stock_list:
        return []
    df = get_price(stock_list, end_date=y_day, frequency='1d',
                   fields=['high', 'volume'], count=101,
                   skip_paused=True, panel=False)
    if df is None or df.empty:
        return []
    keep = []
    for code, group in df.groupby('code'):
        group = group.sort_values('time').reset_index(drop=True)
        hs = group['high']
        vs = group['volume']
        if len(hs) < 10:
            continue
        prev_high = hs.iloc[-1]
        zyts_0 = next(
            (i - 1 for i, high in enumerate(hs.iloc[-3::-1], 2) if high >= prev_high),
            100
        )
        zyts = zyts_0 + 5
        volume_data = vs.iloc[-zyts:]
        if len(volume_data) < 2:
            continue
        if volume_data.iloc[-1] <= volume_data.iloc[:-1].max() * 0.9:
            continue
        keep.append(code)
    return keep


# ---------- 集合竞价 ----------

def _auction_df(stock, t_day_str):
    start = '%s 09:15:00' % t_day_str
    end = '%s 09:26:00' % t_day_str
    auction = get_call_auction(stock, start_date=start, end_date=end,
                               fields=['time', 'volume', 'current'])
    if auction is None or auction.empty:
        return None
    return auction


def filter_auction_low3(stock_list, y_day, t_day_str):
    """低位原版：取 09:26 最后一笔；量比>=3%，1.0 < 竞价/昨收 < 1.06。"""
    if not stock_list:
        return []
    hist_df = get_price(stock_list, end_date=y_day, frequency='1d',
                        fields=['close', 'volume'], count=1,
                        skip_paused=True, panel=False, fill_paused=False)
    if hist_df is None or hist_df.empty:
        return []
    qualified = []
    for stock in stock_list:
        try:
            auction = _auction_df(stock, t_day_str)
            if auction is None:
                continue
            last = auction.iloc[-1]
            hist = hist_df[hist_df['code'] == stock]
            if hist.empty:
                continue
            yv = hist.iloc[0]['volume']
            yc = hist.iloc[0]['close']
            if yv <= 0 or yc <= 0:
                continue
            if last.volume / yv >= 0.03 and 1.0 < last.current / yc < 1.06:
                qualified.append(stock)
        except Exception:
            continue
    return qualified


def filter_auction_sbgk(stock_list, y_day, t_day_str):
    """对齐聚宽一进二：取竞价第一笔 [0]；量比>=3%，1.0 < 竞价/昨收 < 1.06。"""
    if not stock_list:
        return []
    hist_df = get_price(stock_list, end_date=y_day, frequency='1d',
                        fields=['close', 'volume'], count=1,
                        skip_paused=True, panel=False, fill_paused=False)
    if hist_df is None or hist_df.empty:
        return []
    qualified = []
    for stock in stock_list:
        try:
            auction = _auction_df(stock, t_day_str)
            if auction is None:
                continue
            first = auction.iloc[0]
            hist = hist_df[hist_df['code'] == stock]
            if hist.empty:
                continue
            yv = float(hist.iloc[0]['volume'] or 0)
            yc = float(hist.iloc[0]['close'] or 0)
            if yv <= 0 or yc <= 0:
                continue
            vol = float(first['volume'] or 0)
            px = float(first['current'] or 0)
            if px <= 0 or vol <= 0:
                continue
            if vol / yv < g.sbgk_volume_ratio_min:
                continue
            ratio = px / yc
            if ratio <= g.sbgk_open_ratio_min or ratio >= g.sbgk_open_ratio_max:
                continue
            qualified.append(stock)
        except Exception:
            continue
    return qualified


def _merge_buy_list(low3_ok, sbgk_ok):
    """重叠优先，其余按低位、首板高开排列。返回 [(code, source), ...]。"""
    s3 = set(low3_ok or [])
    sg = set(sbgk_ok or [])
    both = [s for s in (low3_ok or []) if s in sg]
    only_l = [s for s in (low3_ok or []) if s not in sg]
    only_s = [s for s in (sbgk_ok or []) if s not in s3]
    tagged = [(s, 'both') for s in both]
    tagged += [(s, 'low3') for s in only_l]
    tagged += [(s, 'sbgk') for s in only_s]
    return tagged


# ---------- 买入 ----------

def get_buy(context):
    t_day = context.current_dt.strftime('%Y%m%d')
    t_day_str = context.current_dt.strftime('%Y-%m-%d')
    y_day = context.previous_date.strftime('%Y-%m-%d')
    c_data = get_current_data()

    holdings = _holdings(context)
    if len(holdings) >= g.max_hold_count:
        log.info('[持仓已达上限] %d只' % g.max_hold_count)
        return

    if g.pick_cache_date != t_day:
        before_open(context)

    low3_ok, sbgk_ok = [], []
    if g.enable_low3:
        cand = [s for s in (g.today_pick_low3 or []) if s not in holdings]
        log.info('[低位排除持仓后] %s' % cand)
        low3_ok = filter_auction_low3(cand, y_day, t_day_str)
        log.info('[低位竞价过滤后] %s' % low3_ok)
    if g.enable_sbgk:
        cand = [s for s in (g.today_pick_sbgk or []) if s not in holdings]
        log.info('[首板高开排除持仓后] %s' % cand)
        sbgk_ok = filter_auction_sbgk(cand, y_day, t_day_str)
        log.info('[首板高开竞价过滤后] %s' % sbgk_ok)

    tagged = _merge_buy_list(low3_ok, sbgk_ok)
    if not tagged:
        log.info('[买入] 两套均无标的')
        return

    slots = g.max_hold_count - len(holdings)
    to_buy = tagged[:slots]
    total = context.portfolio.total_value
    cash = context.portfolio.available_cash
    max_per = total * float(g.max_position_pct)
    per = min(cash / float(len(to_buy)), max_per) if to_buy else 0
    log.info('[分配资金] 持仓%d 可买%d 每只%.0f 标的=%s' % (
        len(holdings), slots, per, [(x[0], x[1]) for x in to_buy]))

    for s, src in to_buy:
        try:
            op = c_data[s].day_open
            if op is None or op <= 0:
                continue
            shares = int(per / op / 100) * 100
            if shares < 100:
                log.info('[买入跳过] %s 不足1手' % s)
                continue
            order_value(s, per, MarketOrderStyle(op))
            g.information[s] = {'buy_date': t_day, 'buy_price': op, 'source': src}
            log.info('[买入][%s] %s 开盘价%.2f 金额约%.0f 预计%d股' % (src, s, op, per, shares))
        except Exception as e:
            log.info('[买入错误] %s %s' % (s, e))


# ---------- 定点卖出 ----------

def get_close_sell(context):
    hm = context.current_dt.strftime('%H%M')
    hold = _held_not_bought_today(context)
    if not hold:
        return
    metrics = g.close_sell_cache or {}
    c_data = get_current_data()
    do_low3 = hm in ('1125', '1330', '1455')
    do_sbgk = hm in ('1125', '1450')

    for s in hold:
        src = _src_of(s)
        cd = c_data[s]
        cp = cd.last_price
        if cp <= 0:
            continue
        pos = context.portfolio.positions.get(s)
        if pos is None or pos.total_amount <= 0:
            continue
        cost = float(pos.avg_cost or 0)

        sold = False
        if do_low3 and src in ('low3', 'both'):
            if s not in metrics:
                log.info('[低位持仓] %s 无卖出缓存，跳过' % s)
            else:
                sold = _try_sell_low3_close(context, s, cd, cp, metrics[s], cost)
        if (not sold) and do_sbgk and src in ('sbgk', 'both'):
            pos = context.portfolio.positions.get(s)
            if pos is None or pos.closeable_amount == 0:
                continue
            _try_sell_sbgk(context, s, cd, cp, pos)


def _try_sell_low3_close(context, s, cd, cp, cache, cost):
    yc = cache['y_close']
    ma5 = cache['ma5']
    dg = (cp - yc) / yc if yc > 0 else 0
    pp = (cp - cost) / cost if cost > 0 else 0
    log.info('[低位持仓检查] %s 现%.2f 成本%.2f 收益%.2f%% 当日%.2f%% MA5=%.2f' % (
        s, cp, cost, pp * 100, dg * 100, ma5))
    if cp >= cd.high_limit * 0.985:
        log.info('[持有] %s 接近涨停' % s)
        return False
    sell, reason = False, ''
    if pp > 0.5:
        sell, reason = True, '收益>50%'
    if dg < -0.02:
        sell, reason = True, '当日涨幅<-2%% (%.2f%%)' % (dg * 100)
    elif cd.day_open > 0 and cp < cd.day_open * 0.96:
        sell, reason = True, '当前价<开盘-4%%'
    elif pp <= -0.07:
        sell, reason = True, '收益<=-7%%'
    elif ma5 > 0 and cp < ma5 * 0.97:
        sell, reason = True, '跌破5日均线-3%%'
    if sell:
        order_target_value(s, 0)
        log.info('[卖出] %s 低位-%s 清仓' % (s, reason))
        g.today_high.pop(s, None)
        return True
    log.info('[持有] %s 低位无卖出条件' % s)
    return False


def _try_sell_sbgk(context, s, cd, cp, position):
    """对齐聚宽一进二 sell：盈利且未涨停，或跌破实时 MA5。"""
    if position.closeable_amount == 0:
        return False
    cost = position.avg_cost
    if cost > 0 and cp > cost and cp < cd.high_limit:
        order_target_value(s, 0)
        log.info('[卖出] %s 首板高开-止盈未涨停 清仓' % s)
        g.today_high.pop(s, None)
        return True
    close_data = attribute_history(s, 4, '1d', ['close'])
    if close_data is None or len(close_data) < 1:
        return False
    m4 = close_data['close'].mean()
    ma5_live = (m4 * 4.0 + cp) / 5.0
    if cp < ma5_live:
        order_target_value(s, 0)
        log.info('[卖出] %s 首板高开-跌破MA5(%.2f) 清仓' % (s, ma5_live))
        g.today_high.pop(s, None)
        return True
    log.info('[持有] %s 首板高开无卖出条件 MA5=%.2f' % (s, ma5_live))
    return False


# ---------- 分钟止盈（仅低位 / both，对齐低位原版） ----------

def get_minute_sell(context):
    t_day_time = context.current_dt.time()
    if t_day_time < time(9, 30) or t_day_time > time(11, 25):
        return
    y_day = context.previous_date
    hold = _held_not_bought_today(context)
    if not hold:
        return
    c_data = get_current_data()
    for s in hold:
        if _src_of(s) == 'sbgk':
            continue
        cd = c_data[s]
        cp = cd.last_price
        if cp <= 0:
            continue
        if cp >= cd.high_limit * 0.985:
            continue
        pos = context.portfolio.positions.get(s)
        if pos is None or pos.total_amount <= 0:
            continue
        cost = float(pos.avg_cost or 0)
        if cost <= 0:
            continue
        profit = (cp - cost) / cost
        cache = g.minute_sell_cache.get(s)

        if cache and cache.get('date') == y_day:
            y_close = float(cache.get('y_close', 0) or 0)
            if y_close > 0:
                yesterday_loss = (y_close - cost) / cost
                if yesterday_loss < -0.02 and profit > 0.02:
                    order_target_value(s, 0)
                    log.info('[分钟止盈] %s 昨亏今盈>2%% 清仓' % s)
                    g.today_high.pop(s, None)
                    continue

        today_open = cd.day_open
        if today_open > 0:
            open_loss = (today_open - cost) / cost
            if open_loss < -0.02 and profit > 0.02:
                order_target_value(s, 0)
                log.info('[分钟止盈] %s 开盘亏今盈>2%% 清仓' % s)
                g.today_high.pop(s, None)
                continue

        if not cache or cache.get('date') != y_day:
            continue
        if float(cache.get('y_day_gain', 0) or 0) >= 0:
            continue
        th = g.today_high.get(s, 0)
        if cp > th:
            g.today_high[s] = cp
            th = cp
        y_close = float(cache.get('y_close', 0) or 0)
        if y_close <= 0 or th <= 0:
            continue
        chr_ = (th - y_close) / y_close
        if chr_ > 0.03:
            lt = max(0.005, 0.03 - (chr_ - 0.01) * 0.5)
            if cp < th * (1 - lt):
                order_target_value(s, 0)
                log.info('[线性止盈] %s 冲高%.2f%% 回撤超%.2f%% 清仓' % (s, chr_ * 100, lt * 100))
                g.today_high.pop(s, None)


# ---------- 盘前缓存 ----------

def precompute_sell_cache(context):
    y_day = context.previous_date
    pos = list(context.portfolio.positions.keys())
    g.minute_sell_cache = {}
    g.close_sell_cache = {}
    if not pos:
        g.today_high.clear()
        return

    df2 = get_price(pos, end_date=y_day, frequency='1d',
                    fields=['close'], count=2, panel=False,
                    skip_paused=False, fill_paused=True)
    if df2 is not None and not df2.empty:
        for s, sub in df2.groupby('code')['close']:
            if len(sub) >= 2:
                yc, pc = sub.iloc[-1], sub.iloc[-2]
                g.minute_sell_cache[s] = {
                    'y_close': yc,
                    'prev_close': pc,
                    'y_day_gain': (yc - pc) / pc if pc > 0 else 0,
                    'date': y_day
                }

    df5 = get_price(pos, end_date=y_day, frequency='1d',
                    fields=['close'], count=5, panel=False,
                    skip_paused=False, fill_paused=True)
    if df5 is not None and not df5.empty:
        for s, sub in df5.groupby('code')['close']:
            if len(sub) >= 2:
                g.close_sell_cache[s] = {
                    'y_close': sub.iloc[-1],
                    'ma5': float(sub.mean())
                }
    g.today_high.clear()
    log.info('[缓存] 分钟止盈%d 定点卖出%d' % (len(g.minute_sell_cache), len(g.close_sell_cache)))


def after_trading_end(context):
    cur = set(context.portfolio.positions.keys())
    g.information = {k: v for k, v in (g.information or {}).items() if k in cur}
    g.minute_sell_cache = {k: v for k, v in (g.minute_sell_cache or {}).items() if k in cur}
    g.close_sell_cache = {k: v for k, v in (g.close_sell_cache or {}).items() if k in cur}
    g.today_high.clear()
