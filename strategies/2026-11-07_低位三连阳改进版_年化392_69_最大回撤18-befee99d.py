# Clone from JoinQuant
# postId: befee99dd015a7b5f019fdac8d0745a3
# backtestId: b84bd2e872a7ee854f5cf4a66e7891d7
# title: 低位三连阳改进版，年化392.69%，最大回撤18%

# -*- coding: utf-8 -*-


from jqdata import *
from datetime import timedelta, time

STRATEGY_NAME = '低位3连阳_升级版'


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
    log.info('低位3连阳=开（首板高开已移除）  最多持仓=%d' % g.max_hold_count)
    log.info('基础池=主板 流通市值%.0f~%.0f亿  上市满%d天'
             % (g.cap_min_yi, g.cap_max_yi, g.list_days_min))
    log.info('日内止损=%s' % (
        '关闭' if not g.enable_intraday_stop
        else '开盘价为基准 %.1f%%' % (g.intraday_stop_loss * 100)))
    log.info('跟踪止盈=%s' % (
        '关闭' if not g.enable_trail_tp
        else '浮盈%.0f%%激活 / 峰值回撤%.1f%%卖 / %.0f%%放飞' % (
            g.trail_tp_activate * 100, g.trail_tp_drawdown * 100, g.trail_tp_release * 100)))
    log.info('回测请用 1 分钟K；买入 09:27；定点卖出 11:25 / 13:30 / 14:55')
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
    g.pick_cache_date = ''
    g.minute_sell_cache = {}
    g.close_sell_cache = {}
    g.today_high = {}
    g.trail_peak = {}
    g.trail_active = set()
    g.trail_released = set()


def _init_params():
    g.max_hold_count = 10
    # 单票上限。删掉 sbgk 后每天最多 0.2~0.3 个候选，10 个仓位几乎永远填不满，
    # 于是 max_position_pct=1.0 会变成「单票吃满可用现金」，实际仓位中位数约 49%。
    # 本地分钟级实测（2024-01~2026-09，low3 单跑）：
    #   1.00 → 118 笔 / +473% / 回撤 -37.5% / Calmar 2.38
    #   0.50 → 159 笔 / +458% / 回撤 -21.8% / Calmar 4.00   ← 收益几乎不变、回撤减半
    #   0.35 → 169 笔 / +261% / 回撤 -17.3% / Calmar 3.46
    # 想让资金分散一点就改成 0.5。
    g.max_position_pct = 1.0

    # 低位基础池
    g.cap_min_yi = 30.0
    g.cap_max_yi = 300.0
    g.list_days_min = 60

    # 日内止损（以当日开盘价为基准）
    g.enable_intraday_stop = True
    g.intraday_stop_loss = -0.07       # 现价/开盘价 - 1 <= -7% 即清仓

    # B1：小浮盈跟踪止盈（实测失败，默认关闭）
    # 2021-2026 全周期对比（800 笔，混合策略口径）：
    #   关闭：年化 254.05% / 回撤 29.80% / Calmar 8.526
    #   开启：年化 247.31% / 回撤 31.68% / Calmar 7.807
    #   胜率 61.4%→66.0%、盈亏比 1.21→2.081 均改善，但收益 -26%、回撤反而变大
    # 原因：砍掉了「小回撤 0~-2% 后拉起」那 22.9% 的盈利单（平均赚 11.46%）
    g.enable_trail_tp = False
    g.trail_tp_activate = 0.02         # 浮盈达到 2% 才激活保护
    g.trail_tp_drawdown = 0.015        # 从峰值回撤 1.5% 即清仓
    g.trail_tp_release = 0.08          # 浮盈超过 8% 永久退出保护（不打扰连板票）


def _schedule():
    run_weekly(prepare_base_stocks, 1, '09:10')
    run_daily(before_open, time='09:11')
    run_daily(precompute_sell_cache, time='09:11')
    run_daily(get_buy, time='09:27')
    run_daily(get_close_sell, time='11:25')
    run_daily(get_close_sell, time='13:30')
    run_daily(get_close_sell, time='14:55')
    run_daily(get_minute_sell, time='every_bar')


# ---------- 工具 ----------

def _holdings(context):
    return [s for s, p in context.portfolio.positions.items() if p.total_amount > 0]


def _held_not_bought_today(context):
    """对齐低位原版：非今日买入的持仓（T+1 且只处理本策略下过单的票）。"""
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


# ---------- 低位基础股票池（周更 + 流通市值 30~300 亿） ----------

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


# ---------- 盘前选股 ----------

def before_open(context):
    t_day = context.current_dt.strftime('%Y%m%d')
    y_day = context.previous_date.strftime('%Y-%m-%d')
    g.today_pick_low3 = []

    if not g.base_stocks:
        prepare_base_stocks(context)
    low3_u = filter_first_board(g.base_stocks, y_day)
    log.info('[盘前-低位] 首板: %d只' % len(low3_u))
    low3_u = filter_volume_price(low3_u, y_day)
    log.info('[盘前-低位] 量价过滤: %d只' % len(low3_u))
    low3_u = filter_high_volatility(low3_u, y_day)
    log.info('[盘前-低位] 过滤高波动: %d只 %s' % (len(low3_u), low3_u))
    g.today_pick_low3 = low3_u
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
            if last.volume / yv >= 0.024 and 1.0 < last.current / yc < 1.06:
                qualified.append(stock)
        except Exception:
            continue
    return qualified


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

    cand = [s for s in (g.today_pick_low3 or []) if s not in holdings]
    log.info('[低位排除持仓后] %s' % cand)
    to_buy = filter_auction_low3(cand, y_day, t_day_str)
    log.info('[低位竞价过滤后] %s' % to_buy)

    if not to_buy:
        log.info('[买入] 无标的')
        return

    slots = g.max_hold_count - len(holdings)
    to_buy = to_buy[:slots]
    total = context.portfolio.total_value
    cash = context.portfolio.available_cash
    max_per = total * float(g.max_position_pct)
    per = min(cash / float(len(to_buy)), max_per) if to_buy else 0
    log.info('[分配资金] 持仓%d 可买%d 每只%.0f 标的=%s' % (
        len(holdings), slots, per, to_buy))

    for s in to_buy:
        try:
            op = c_data[s].day_open
            if op is None or op <= 0:
                continue
            shares = int(per / op / 100) * 100
            if shares < 100:
                log.info('[买入跳过] %s 不足1手' % s)
                continue
            order_value(s, per, MarketOrderStyle(op))
            g.information[s] = {'buy_date': t_day, 'buy_price': op}
            log.info('[买入][低位] %s 开盘价%.2f 金额约%.0f 预计%d股' % (s, op, per, shares))
        except Exception as e:
            log.info('[买入错误] %s %s' % (s, e))


# ---------- 日内止损（优先级最高） ----------

def _intraday_stop_loss(context):
    """以当日开盘价为基准的日内止损。跌幅 <= 阈值即清仓。

    对所有可卖持仓生效，不受时间窗口限制。
    当日买入的票 closeable_amount=0（T+1），自动跳过。
    返回本次触发止损的代码集合，供后续卖出逻辑跳过。
    """
    if not g.enable_intraday_stop:
        return set()
    hit = set()
    try:
        c_data = get_current_data()
    except Exception:
        return hit
    for s, p in list(context.portfolio.positions.items()):
        if p.total_amount <= 0 or p.closeable_amount <= 0:
            continue
        try:
            cd = c_data[s]
            op = cd.day_open
            cp = cd.last_price
            if op is None or op <= 0 or cp is None or cp <= 0:
                continue
            dd = (cp - op) / op
            # 加 1e-9 容差：价格正好落在 -7% 时避免浮点误差漏判
            if dd <= g.intraday_stop_loss + 1e-9:
                order_target_value(s, 0)
                log.info('[日内止损] %s 开盘%.2f 现价%.2f 日内%.2f%% <= %.1f%% 清仓' % (
                    s, op, cp, dd * 100, g.intraday_stop_loss * 100))
                g.today_high.pop(s, None)
                hit.add(s)
        except Exception as e:
            log.info('[日内止损] %s 异常 %s' % (s, e))
    return hit


# ---------- B1 小浮盈跟踪止盈 ----------

def _trailing_take_profit(context):
    """浮盈达到激活线后，从峰值回撤即清仓；超过放飞线后不再干预。

    设计意图：锁住 2%~8% 这段「小浮盈」——实盘中它贡献了 52% 的亏损额。
    浮盈超过 8% 的票自动退出保护，避免打断连板行情。
    返回本次触发的代码集合。
    """
    if not g.enable_trail_tp:
        return set()
    hit = set()
    try:
        c_data = get_current_data()
    except Exception:
        return hit
    for s, p in list(context.portfolio.positions.items()):
        if p.total_amount <= 0 or p.closeable_amount <= 0:
            continue
        if s in g.trail_released:
            continue
        try:
            cd = c_data[s]
            cp = cd.last_price
            cost = float(p.avg_cost or 0)
            if cp is None or cp <= 0 or cost <= 0:
                continue
            profit = (cp - cost) / cost
            # 放飞：涨幅足够大，交给原规则（保护连板）
            if profit >= g.trail_tp_release:
                g.trail_released.add(s)
                log.info('[跟踪止盈] %s 浮盈%.2f%% 超过放飞线%.0f%%，退出保护'
                         % (s, profit * 100, g.trail_tp_release * 100))
                continue
            # 激活
            if s not in g.trail_active:
                if profit >= g.trail_tp_activate:
                    g.trail_active.add(s)
                    g.trail_peak[s] = cp
                    log.info('[跟踪止盈] %s 浮盈%.2f%% 激活保护 峰值%.2f'
                             % (s, profit * 100, cp))
                continue
            # 更新峰值
            if cp > g.trail_peak.get(s, 0):
                g.trail_peak[s] = cp
            peak = g.trail_peak.get(s, 0)
            # 回撤触发
            if peak > 0 and cp <= peak * (1 - g.trail_tp_drawdown):
                order_target_value(s, 0)
                log.info('[跟踪止盈] %s 峰值%.2f 现价%.2f 回撤%.2f%% 清仓（浮盈%.2f%%）'
                         % (s, peak, cp, (1 - cp / peak) * 100, profit * 100))
                g.today_high.pop(s, None)
                g.trail_active.discard(s)
                g.trail_peak.pop(s, None)
                hit.add(s)
        except Exception as e:
            log.info('[跟踪止盈] %s 异常 %s' % (s, e))
    return hit


# ---------- 定点卖出（低位：11:25 / 13:30 / 14:55） ----------

def get_close_sell(context):
    _intraday_stop_loss(context)
    _trailing_take_profit(context)
    hm = context.current_dt.strftime('%H%M')
    if hm not in ('1125', '1330', '1455'):
        return
    hold = _held_not_bought_today(context)
    if not hold:
        return
    metrics = g.close_sell_cache or {}
    c_data = get_current_data()

    for s in hold:
        cd = c_data[s]
        cp = cd.last_price
        if cp <= 0:
            continue
        pos = context.portfolio.positions.get(s)
        if pos is None or pos.total_amount <= 0:
            continue
        cost = float(pos.avg_cost or 0)
        if s not in metrics:
            log.info('[低位持仓] %s 无卖出缓存，跳过' % s)
            continue
        _try_sell_low3_close(context, s, cd, cp, metrics[s], cost)


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


# ---------- 分钟止盈（09:30~11:25） ----------

def get_minute_sell(context):
    # 日内止损 + 跟踪止盈最先执行，不受分钟止盈时间窗口限制
    stopped = _intraday_stop_loss(context)
    tp = _trailing_take_profit(context)

    t_day_time = context.current_dt.time()
    if t_day_time < time(9, 30) or t_day_time > time(11, 25):
        return
    y_day = context.previous_date
    hold = [x for x in _held_not_bought_today(context) if x not in stopped and x not in tp]
    if not hold:
        return
    c_data = get_current_data()
    for s in hold:
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
    g.trail_active.clear()
    g.trail_peak.clear()
    g.trail_released.clear()
