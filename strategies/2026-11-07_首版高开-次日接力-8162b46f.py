# Clone from JoinQuant
# postId: 8162b46f56f8d0794aa4100fa5e8250a
# backtestId: 77f1e5d6e16b5671285f202c27a8c997
# title: 首版高开-次日接力

# -*- coding: utf-8 -*-
# 标题：「龙头战法+首板接力」优先 low3，sbgk 替补（一刀切版）
# 作者：李
#
# v4.6 一刀切版：
#   - low3 优先，sbgk 替补，满仓
#   - 只要 LOW3 出现合格候选，开盘直接市价清仓所有可卖出的 SBGK 持仓，腾资金给 LOW3
#   - SBGK 沿用 v4.5-扩2 高级逻辑：放宽选股、14:55 硬止盈、收益>35%分批、移动止盈等
#   - [本次改动1] 回测禁用 call_auction 兜底，取不到竞价数据直接剔除
#   - [本次改动4] get_minute_sell 延长到 14:55，下午继续跑移动止盈
#   - [本次改动6] 增加账户级总回撤风控，单日回撤超阈值暂停开新仓
#   - [本次修复] _detect_backtest 只识别 backtest，模拟盘/实盘默认 False
#   - [本次修复] 撤单时间从 14:57 改到 14:56（14:57 起交易所不接受撤单）
#   - [本次新增] 卖出检查点增加 09:58
#   - [本次新增] LOW3 也加入移动止盈（盈利>10%且从最高点回撤>4%）
#   - [本次修改] LOW3 单票最大仓位上限调整为 80%
#
# 回测请用 1 分钟频率。

from jqdata import *
import pandas as pd
import os
import pickle
from datetime import datetime, timedelta, date, time

STRATEGY_NAME = '优先low3_sbgk替补_v4.6一刀切'
STATE_FILE = os.path.expanduser('~/.jq_strategy/strategy_state_v4_cut.pkl')

AUCTION_MIN_VOLUME = 5000
_AUCTION_CACHE = {}
_IS_BACKTEST = True


# =====================================================================
# 状态持久化
# =====================================================================
def save_my_state():
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        data = {'information': dict(g.information or {})}
        with open(STATE_FILE, 'wb') as f:
            pickle.dump(data, f)
    except Exception as e:
        log.info('[状态保存失败] %s' % e)


def load_my_state():
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'rb') as f:
                data = pickle.load(f)
            if isinstance(data, dict):
                return data.get('information', {}) or {}
    except Exception as e:
        log.info('[状态加载失败] %s' % e)
    return {}


# =====================================================================
# 初始化
# =====================================================================
def initialize(context):
    log.set_level('order', 'error')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_slippage(FixedSlippage(0.01))
    set_order_cost(OrderCost(
        close_tax=0.0005, open_commission=0.0002,
        close_commission=0.0002, min_commission=5
    ), type='stock')
    set_benchmark('399303.XSHE')

    global _IS_BACKTEST
    _IS_BACKTEST = _detect_backtest(context)

    _init_g()
    _schedule(context)

    log.info('=' * 60)
    log.info('>>> %s 初始化完成 <<<' % STRATEGY_NAME)
    log.info('>>> 竞价取 09:25 撮合价（对齐实盘） <<<')
    log.info('>>> 回测模式：%s <<<' % _IS_BACKTEST)
    log.info('>>> 回测请用「1分钟」频率 <<<')
    log.info('=' * 60)


def process_initialize(context):
    global _IS_BACKTEST
    _IS_BACKTEST = _detect_backtest(context)
    log.info('========== process_initialize 触发，恢复状态 ==========')
    _init_g()
    _schedule(context)


def after_code_changed(context):
    global _IS_BACKTEST
    _IS_BACKTEST = _detect_backtest(context)
    unschedule_all()
    _init_params()
    if not hasattr(g, 'n_days_limit_up_list'):
        g.n_days_limit_up_list = []
    if not hasattr(g, '_sbgk_first_board_date'):
        g._sbgk_first_board_date = None
    if not hasattr(g, '_sbgk_first_board_cache'):
        g._sbgk_first_board_cache = []
    _schedule(context)


def _init_g():
    _init_params()
    loaded = load_my_state()
    if loaded:
        g.information = loaded
        log.info('[状态恢复] 已恢复 %d 条记录' % len(loaded))
    else:
        g.information = {}
    g.base_stocks = []
    g.today_pick_low3 = []
    g.today_pick_sbgk = []
    g.pick_cache_date = ''
    g.minute_sell_cache = {}
    g.close_sell_cache = {}
    g.today_high = {}
    g.n_days_limit_up_list = []
    g._sbgk_first_board_date = None
    g._sbgk_first_board_cache = []
    # [本次改动6] 账户级回撤风控状态
    g.account_drawdown_date = ''
    g.account_open_value = 0.0
    g.account_drawdown_triggered = False


def _init_params():
    g.enable_low3 = True
    g.enable_sbgk = True
    g.max_hold_count = 10
    g.max_position_pct = 1.0

    # [本次修改] LOW3 单票最大仓位上限
    g.low3_max_position_pct = 0.8

    # low3 基础池参数
    g.cap_min_yi = 30.0
    g.cap_max_yi = 300.0
    g.list_days_min = 60

    # SBGK 放宽后的选股参数
    g.sbgk_list_days = 50
    g.sbgk_avg_price_ratio_min = 0.07
    g.sbgk_money_min = 5.0e8
    g.sbgk_money_max = 25e8
    g.sbgk_market_cap_min = 60.0
    g.sbgk_circulating_cap_max = 650.0
    g.sbgk_open_ratio_min = 1.0
    g.sbgk_open_ratio_max = 1.06
    g.sbgk_volume_ratio_min = 0.03

    g.buy_slip = 0.02
    g.hard_stop_loss = -0.10
    g.hard_take_profit = 0.49
    g.auction_min_volume = AUCTION_MIN_VOLUME

    # 动态跌幅与移动止盈参数
    g.drop_threshold_default = -0.03
    g.drop_threshold_weak = -0.02
    g.market_weak_line = -0.015
    g.trailing_profit_trigger = 0.10
    g.trailing_drawdown = 0.04
    g.partial_sell_ratio = 0.5
    g.partial_sell_min_shares = 200

    # [本次改动6] 账户级总回撤风控参数
    g.enable_account_drawdown = True
    g.account_drawdown_threshold = -0.03   # 单日账户回撤超过 -3%，暂停开新仓


def _detect_backtest(context):
    # [本次修复] 只识别 backtest，模拟盘/实盘一律按实盘处理
    try:
        rp = getattr(context, 'run_params', None)
        if rp is not None:
            t = str(getattr(rp, 'type', '') or '').lower()
            if 'backtest' in t:
                return True
            if 'sim' in t or 'live' in t or 'trade' in t:
                return False
    except Exception:
        pass
    return False


def _is_backtest():
    return bool(_IS_BACKTEST)


def _schedule(context=None):
    unschedule_all()

    run_weekly(prepare_base_stocks, 1, '09:10')
    run_daily(before_open, time='09:11')
    run_daily(precompute_sell_cache, time='09:11')

    if _is_backtest():
        run_daily(get_buy, time='09:31')
    else:
        run_daily(get_buy, time='09:27')

    # [本次新增] 卖出检查点增加 09:58
    run_daily(get_close_sell, time='09:58')
    run_daily(get_close_sell, time='11:25')
    run_daily(get_close_sell, time='13:30')
    run_daily(get_close_sell, time='14:55')
    run_daily(get_minute_sell, time='every_bar')
    run_daily(update_high_every_bar, time='every_bar')
    run_daily(check_hard_stop, time='14:56')
    # [本次修复] 撤单从 14:57 改到 14:56
    run_daily(cancel_pending_orders, time='14:56')
    run_daily(after_trading_end, time='15:05')


# =====================================================================
# 工具
# =====================================================================
def _is_sbgk_board(stock):
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
    t_day = context.current_dt.strftime('%Y%m%d')
    out = []
    for s, p in context.portfolio.positions.items():
        if p.total_amount <= 0:
            continue
        rec = g.information.get(s)
        if not rec:
            g.information[s] = {
                'buy_date': '00000000',
                'buy_price': float(p.avg_cost or 0),
                'source': 'unknown',
                'orphan': True,
            }
            rec = g.information[s]
        if str(rec.get('buy_date', '') or '') == t_day:
            continue
        out.append(s)
    return out


# =====================================================================
# [本次改动6] 账户级总回撤风控
# =====================================================================
def _check_account_drawdown(context):
    """检查账户是否触发单日回撤风控"""
    if not getattr(g, 'enable_account_drawdown', False):
        return False

    today = context.current_dt.strftime('%Y%m%d')

    # 新的一天，重置状态，记录当日开盘总资产
    if g.account_drawdown_date != today:
        g.account_drawdown_date = today
        g.account_open_value = float(context.portfolio.total_value or 0)
        g.account_drawdown_triggered = False
        log.info('>>> [账户风控] 新交易日，记录开盘总资产 %.0f' % g.account_open_value)

    # 已经触发过，直接返回
    if g.account_drawdown_triggered:
        return True

    # 计算当前回撤
    if g.account_open_value > 0:
        cur_total = float(context.portfolio.total_value or 0)
        drawdown = (cur_total - g.account_open_value) / g.account_open_value
        if drawdown <= g.account_drawdown_threshold:
            log.info('🚨 [账户风控] 当日回撤%.2f%%（阈值%.2f%%），暂停开新仓' % (
                drawdown * 100, g.account_drawdown_threshold * 100))
            g.account_drawdown_triggered = True
            return True
    return False


# =====================================================================
# 撤单（14:56 撤销所有未成交买单）
# =====================================================================
def cancel_pending_orders(context):
    try:
        open_orders = get_open_orders()
        if open_orders:
            for oid, o in open_orders.items():
                if o.is_buy:
                    cancel_order(oid)
                    log.info('>>> [撤单] 撤销未成交买单: %s' % o.security)
                    if o.security in g.information:
                        rec = g.information.get(o.security, {})
                        if rec.get('pending', False):
                            g.information.pop(o.security, None)
                            g.today_high.pop(o.security, None)
                            log.info('>>> [撤单-清理] 移除未成交记录: %s' % o.security)
    except Exception as e:
        log.info('>>> [撤单错误] %s' % e)
    save_my_state()


# =====================================================================
# 股票池
# =====================================================================
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
    log.info('[基础股票池-低位] %d只' % len(g.base_stocks))


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
    today = context.current_dt.date()
    yesterday = context.previous_date

    if getattr(g, '_sbgk_first_board_date', None) == today:
        return list(getattr(g, '_sbgk_first_board_cache', []) or [])
    g._sbgk_first_board_date = today

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

    if not getattr(g, 'n_days_limit_up_list', None):
        g.n_days_limit_up_list = []
        days = get_trade_days(end_date=yesterday, count=3)[:-1]
        for day in days:
            g.n_days_limit_up_list.append(get_hl_stock(initial_list, day, 1))

    hl_list = get_hl_stock(initial_list, yesterday, 1)
    g.n_days_limit_up_list.append(hl_list)
    hl1_list = set(g.n_days_limit_up_list[-2])
    first = [s for s in hl_list if s not in hl1_list]
    g.n_days_limit_up_list.pop(0)

    g._sbgk_first_board_cache = list(first)
    return first


# =====================================================================
# 盘前选股
# =====================================================================
def before_open(context):
    t_day = context.current_dt.strftime('%Y%m%d')
    y_day = context.previous_date.strftime('%Y-%m-%d')
    g.today_pick_low3 = []
    g.today_pick_sbgk = []

    if g.enable_low3:
        if not g.base_stocks:
            prepare_base_stocks(context)
        low3_u = filter_first_board(g.base_stocks, y_day)
        low3_u = filter_volume_price(low3_u, y_day)
        low3_u = filter_high_volatility(low3_u, y_day)
        g.today_pick_low3 = low3_u
        log.info('[盘前-低位] 最终候选: %s' % low3_u)
    else:
        log.info('[盘前-低位] 已关闭')

    if g.enable_sbgk:
        first = prepare_sbgk_first_board(context)
        sbgk_u = filter_sbgk_hist(first, context.previous_date)
        g.today_pick_sbgk = sbgk_u
        log.info('[盘前-首板高开] 最终候选: %s' % sbgk_u)
    else:
        log.info('[盘前-首板高开] 已关闭')

    g.pick_cache_date = t_day


def filter_first_board(stock_list, y_day):
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
        try:
            val = get_valuation(
                part, start_date=y_day, end_date=y_day,
                fields=['market_cap', 'circulating_market_cap']
            )
        except Exception:
            continue
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


# =====================================================================
# 集合竞价
# =====================================================================
def _auction_df(stock, t_day_str):
    start = '%s 09:15:00' % t_day_str
    end = '%s 09:26:00' % t_day_str
    try:
        auction = get_call_auction(stock, start_date=start, end_date=end,
                                   fields=['time', 'volume', 'current'])
    except Exception:
        return None
    if auction is None or auction.empty:
        return None
    return auction


def _get_auction_px(stock, t_day_str):
    key = (stock, t_day_str)
    if key in _AUCTION_CACHE:
        return _AUCTION_CACHE[key]

    px, vol = None, None
    auction = _auction_df(stock, t_day_str)
    if auction is not None and not auction.empty:
        last = auction.iloc[-1]
        try:
            px = float(last['current'] or 0)
            vol = float(last['volume'] or 0)
        except Exception:
            px, vol = None, None
        if px is None or px <= 0:
            px, vol = None, None

    # [本次改动1] 删除了原回测兜底逻辑：
    # 之前当 call_auction 取不到时，会用 09:30 第一根 1 分钟 K 线 open 冒充竞价价，
    # 会导致回测虚高（实盘 09:25 竞价价和 09:30 开盘价经常偏离）。
    # 现在直接返回 (None, None)，由调用方剔除该标的。

    _AUCTION_CACHE[key] = (px, vol)
    return px, vol


def filter_auction_low3(stock_list, y_day, t_day_str):
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
            px, vol = _get_auction_px(stock, t_day_str)
            if px is None:
                continue
            if vol is None or vol < g.auction_min_volume:
                continue
            hist = hist_df[hist_df['code'] == stock]
            if hist.empty:
                continue
            yv = float(hist.iloc[0]['volume'] or 0)
            yc = float(hist.iloc[0]['close'] or 0)
            if yv <= 0 or yc <= 0:
                continue
            if vol / yv >= 0.03 and 1.0 < px / yc < 1.06:
                qualified.append(stock)
        except Exception:
            continue
    return qualified


def filter_auction_sbgk(stock_list, y_day, t_day_str):
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
            px, vol = _get_auction_px(stock, t_day_str)
            log.info('[sbgk竞价数据] %s px=%s vol=%s' % (stock, px, vol))
            if px is None:
                continue
            if vol is None or vol < g.auction_min_volume:
                continue
            hist = hist_df[hist_df['code'] == stock]
            if hist.empty:
                continue
            yv = float(hist.iloc[0]['volume'] or 0)
            yc = float(hist.iloc[0]['close'] or 0)
            if yv <= 0 or yc <= 0:
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


# =====================================================================
# 买入（一刀切版本 + LOW3 单票 80% 上限）
# =====================================================================
def get_buy(context):
    _AUCTION_CACHE.clear()
    t_day = context.current_dt.strftime('%Y%m%d')
    t_day_str = context.current_dt.strftime('%Y-%m-%d')
    y_day = context.previous_date.strftime('%Y-%m-%d')

    c_data = get_current_data()
    holdings = _holdings(context)
    log.info('=' * 50)
    log.info('>>> get_buy 触发 %s <<<' % context.current_dt)
    log.info('>>> 当前持仓: %s' % holdings)

    # [本次改动6] 账户级总回撤风控
    if _check_account_drawdown(context):
        log.info('>>> [账户风控] 已触发当日回撤风控，暂停开新仓')
        return

    if len(holdings) >= g.max_hold_count:
        log.info('>>> 持仓已满，跳过')
        return

    if g.pick_cache_date != t_day:
        before_open(context)

    # ---- 第一优先级：low3 ----
    low3_ok = []
    if g.enable_low3:
        cand = [s for s in (g.today_pick_low3 or []) if s not in holdings]
        low3_ok = filter_auction_low3(cand, y_day, t_day_str)

    # ================= 一刀切：有 LOW3 机会，直接清仓 SBGK 腾资金 =================
    if low3_ok:
        log.info('>>> [一刀切资金置换] 发现 LOW3 机会，强制清仓所有可卖出的 SBGK 持仓')
        for s in list(context.portfolio.positions.keys()):
            pos = context.portfolio.positions[s]
            if pos.total_amount <= 0 or pos.closeable_amount <= 0:
                continue
            if _src_of(s) == 'sbgk':
                log.info('>>> [一刀切-卖出] 清仓 SBGK: %s' % s)
                try:
                    order_target_value(s, 0, MarketOrderStyle())
                    g.information.pop(s, None)
                    g.today_high.pop(s, None)
                except Exception as e:
                    log.info('>>> [一刀切-卖出错误] %s %s' % (s, e))
        holdings = _holdings(context)
    # ==========================================================================

    if low3_ok:
        tagged = [(s, 'low3') for s in low3_ok]
        log.info('>>> [优先级] low3 命中 %d 只，sbgk 不启用' % len(low3_ok))
    else:
        # ---- 第二优先级：sbgk 替补 ----
        sbgk_ok = []
        if g.enable_sbgk:
            cand = [s for s in (g.today_pick_sbgk or []) if s not in holdings]
            sbgk_ok = filter_auction_sbgk(cand, y_day, t_day_str)
        tagged = [(s, 'sbgk') for s in sbgk_ok]
        log.info('>>> [优先级] low3 空，启用 sbgk %d 只' % len(sbgk_ok))

    log.info('>>> 合并买入清单: %s' % tagged)

    if not tagged:
        log.info('>>> 今日无买入标的')
        return

    slots = g.max_hold_count - len(holdings)
    to_buy = tagged[:slots]

    total = context.portfolio.total_value
    cash = context.portfolio.available_cash

    # [本次修改] 根据买入来源选择不同的单票仓位上限
    if tagged and tagged[0][1] == 'low3':
        max_per = total * float(g.low3_max_position_pct)
        log.info('>>> [仓位上限] LOW3 模式，单票上限 %.0f%% = %.0f 元' % (
            g.low3_max_position_pct * 100, max_per))
    else:
        max_per = total * float(g.max_position_pct)
        log.info('>>> [仓位上限] SBGK 模式，单票上限 %.0f%% = %.0f 元' % (
            g.max_position_pct * 100, max_per))

    per = min(cash / float(len(to_buy)), max_per) if to_buy else 0
    log.info('>>> 分配: 每只 %.0f 元 (可买%d只, 现金%.0f, 总资产%.0f)' % (
        per, len(to_buy), cash, total))

    feasible = []
    for s, src in to_buy:
        try:
            cd = c_data[s]
            last_px = float(cd.last_price or 0)
            if last_px <= 0:
                continue
            one_hand_cost = last_px * 100
            if one_hand_cost > per:
                log.info('>>> [跳过] %s 一手成本 %.0f > 分配额度 %.0f' % (
                    s, one_hand_cost, per))
                continue
            feasible.append((s, src))
        except Exception as e:
            log.info('>>> [跳过] %s 异常 %s' % (s, e))
    to_buy = feasible

    if not to_buy:
        log.info('>>> 无可行买入标的')
        return

    per = min(cash / float(len(to_buy)), max_per)
    log.info('>>> 最终分配: 每只 %.0f 元 (%d只)' % (per, len(to_buy)))

    buy_slip = float(getattr(g, 'buy_slip', 0.02))

    for s, src in to_buy:
        try:
            cd = c_data[s]
            if cd.paused:
                log.info('>>> [跳过-停牌] %s' % s)
                continue
            if cd.last_price >= cd.high_limit * 0.999:
                log.info('>>> [跳过-涨停] %s' % s)
                continue

            auction_px, auction_vol = _get_auction_px(s, t_day_str)
            if auction_px is None:
                log.info('>>> [跳过] %s 无有效竞价数据' % s)
                continue

            limit_px = auction_px * (1 + buy_slip)
            if limit_px >= cd.high_limit:
                log.info('>>> [跳过-封板] %s 竞价%.2f+2%%=%.2f≥涨停%.2f' % (
                    s, auction_px, limit_px, cd.high_limit))
                continue

            shares = int(per / limit_px / 100) * 100
            if shares < 100:
                log.info('>>> [跳过] %s 不足1手' % s)
                continue

            order_obj = order(s, shares, LimitOrderStyle(limit_px))

            if order_obj is not None:
                if s not in g.information:
                    g.information[s] = {
                        'buy_date': t_day,
                        'buy_price': limit_px,
                        'auction_price': auction_px,
                        'limit_price': limit_px,
                        'source': src,
                        'pending': getattr(order_obj, 'filled', 0) == 0,
                    }
                    filled = getattr(order_obj, 'filled', 0)
                    if filled > 0:
                        log.info('>>> [买入成功][%s] %s 竞价%.2f 限价%.2f 成交%.2f 数量%d' % (
                            src, s, auction_px, limit_px,
                            getattr(order_obj, 'price', limit_px), filled))
                    else:
                        log.info('>>> [买入挂单][%s] %s 竞价%.2f 限价%.2f 未成交，已登记' % (
                            src, s, auction_px, limit_px))
            else:
                log.info('>>> [买入失败][%s] %s 订单返回空' % (src, s))

        except Exception as e:
            log.info('>>> [买入错误] %s %s' % (s, e))

    save_my_state()
    log.info('=' * 50)


# =====================================================================
# 硬止损（14:56）
# =====================================================================
def check_hard_stop(context):
    c_data = get_current_data()
    for stock in list(context.portfolio.positions.keys()):
        pos = context.portfolio.positions[stock]
        if pos.total_amount <= 0 or pos.closeable_amount <= 0:
            continue
        cost = float(pos.avg_cost or 0)
        if cost <= 0:
            continue
        cur = float(c_data[stock].last_price or 0)
        if cur <= 0:
            continue
        ret = (cur - cost) / cost
        if ret <= g.hard_stop_loss:
            log.info('🚨 [硬止损] %s 亏损%.2f%%' % (stock, ret * 100))
            order_target_value(stock, 0)
            g.information.pop(stock, None)
            g.today_high.pop(stock, None)


# =====================================================================
# 大盘环境与动态阈值工具
# =====================================================================
def _get_market_change(context):
    try:
        bench = '399303.XSHE'
        df = get_price(bench, end_date=context.previous_date, frequency='1d',
                       fields=['close'], count=2, skip_paused=True, panel=False, fill_paused=False)
        if df is None or df.empty or len(df) < 2:
            return 0.0
        prev_close = float(df.iloc[0]['close'] or 0)
        y_close = float(df.iloc[1]['close'] or 0)
        if prev_close > 0:
            return (y_close - prev_close) / prev_close
    except Exception:
        pass
    return 0.0


def _get_dynamic_drop_threshold(context):
    mkt = _get_market_change(context)
    if mkt < g.market_weak_line:
        return g.drop_threshold_weak
    else:
        return g.drop_threshold_default


def _update_today_high(context):
    c_data = get_current_data()
    for s in list(context.portfolio.positions.keys()):
        pos = context.portfolio.positions[s]
        if pos.total_amount <= 0:
            continue
        cur = float(c_data[s].last_price or 0)
        if cur <= 0:
            continue
        prev_high = g.today_high.get(s, 0)
        if cur > prev_high:
            g.today_high[s] = cur


def update_high_every_bar(context):
    t = context.current_dt.time()
    if t < time(9, 30) or t > time(14, 57):
        return
    _update_today_high(context)


# =====================================================================
# 定点卖出（[本次新增] 增加 09:58；LOW3 也加入移动止盈）
# =====================================================================
def get_close_sell(context):
    hm = context.current_dt.strftime('%H%M')
    hold = _held_not_bought_today(context)
    if not hold:
        return
    metrics = g.close_sell_cache or {}
    c_data = get_current_data()
    # [本次新增] 检查点：09:58 / 11:25 / 13:30 / 14:55
    do_sell = hm in ('0958', '1125', '1330', '1455')

    if not do_sell:
        return

    for s in hold:
        src = _src_of(s)
        cd = c_data[s]
        cp = cd.last_price
        if cp <= 0:
            continue
        pos = context.portfolio.positions.get(s)
        if pos is None or pos.total_amount <= 0:
            continue
        if pos.closeable_amount <= 0:
            continue
        cost = float(pos.avg_cost or 0)

        # SBGK 高级逻辑 14:55 硬止盈（仅 14:55 触发）
        if src in ('sbgk', 'both', 'unknown') and hm == '1455' and cost > 0:
            pp = (cp - cost) / cost
            if pp >= g.hard_take_profit:
                log.info('🎯 [SBGK硬止盈-14:55] %s 盈利%.2f%%' % (s, pp * 100))
                order_target_value(s, 0)
                g.information.pop(s, None)
                g.today_high.pop(s, None)
                continue

        if s in metrics:
            if src in ('sbgk', 'both', 'unknown'):
                _try_sell_sbgk_advanced(context, s, cd, cp, metrics[s], cost)
            else:
                _try_sell_low3_close(context, s, cd, cp, metrics[s], cost)


def _try_sell_sbgk_advanced(context, s, cd, cp, cache, cost):
    yc = cache['y_close']
    ma5 = cache['ma5']
    dg = (cp - yc) / yc if yc > 0 else 0
    pp = (cp - cost) / cost if cost > 0 else 0

    if cp >= cd.high_limit * 0.985:
        return False

    pos = context.portfolio.positions.get(s)
    if pos is None or pos.closeable_amount <= 0:
        return False

    rec = g.information.get(s, {})
    is_partial_sold = rec.get('partial_sold', False)

    today_high = g.today_high.get(s, 0)
    if pp > g.trailing_profit_trigger and today_high > 0:
        drawdown = (today_high - cp) / today_high
        if drawdown > g.trailing_drawdown:
            if is_partial_sold:
                order_target_value(s, 0)
                log.info('[SBGK移动止盈-清仓剩余] %s 盈利%.2f%% 回撤%.2f%%' % (s, pp * 100, drawdown * 100))
                g.information.pop(s, None)
                g.today_high.pop(s, None)
                return True
            if pos.closeable_amount >= g.partial_sell_min_shares:
                sell_shares = int(pos.closeable_amount * g.partial_sell_ratio / 100) * 100
                if sell_shares >= 100:
                    order(s, -sell_shares)
                    log.info('[SBGK移动止盈-分批] %s 盈利%.2f%% 回撤%.2f%% 卖出一半(%d股)' % (s, pp * 100, drawdown * 100, sell_shares))
                    g.information[s]['partial_sold'] = True
                    return True
            order_target_value(s, 0)
            log.info('[SBGK移动止盈] %s 盈利%.2f%% 回撤%.2f%% 清仓' % (s, pp * 100, drawdown * 100))
            g.information.pop(s, None)
            g.today_high.pop(s, None)
            return True

    drop_th = _get_dynamic_drop_threshold(context)
    sell, reason = False, ''
    if pp > 0.35 and not is_partial_sold:
        sell, reason = True, '收益>35%'
    elif dg < drop_th:
        sell, reason = True, '当日<%.0f%%' % (drop_th * 100)
    elif cd.day_open > 0 and cp < cd.day_open * 0.96:
        sell, reason = True, '当前<开盘-4%'
    elif pp <= -0.07:
        sell, reason = True, '收益<=-7%'
    elif ma5 > 0 and cp < ma5 * 0.97:
        sell, reason = True, '跌破MA5-3%'

    if sell:
        if reason == '收益>35%' and not is_partial_sold and pos.closeable_amount >= g.partial_sell_min_shares:
            sell_shares = int(pos.closeable_amount * g.partial_sell_ratio / 100) * 100
            if sell_shares >= 100:
                order(s, -sell_shares)
                log.info('[SBGK卖出-分批] %s 低位-%s 卖出一半(%d股)' % (s, reason, sell_shares))
                g.information[s]['partial_sold'] = True
                return True
        order_target_value(s, 0)
        log.info('[SBGK卖出] %s 低位-%s' % (s, reason))
        g.information.pop(s, None)
        g.today_high.pop(s, None)
        return True
    return False


def _try_sell_low3_close(context, s, cd, cp, cache, cost):
    yc = cache['y_close']
    ma5 = cache['ma5']
    dg = (cp - yc) / yc if yc > 0 else 0
    pp = (cp - cost) / cost if cost > 0 else 0
    if cp >= cd.high_limit * 0.985:
        return False

    pos = context.portfolio.positions.get(s)
    if pos is None or pos.closeable_amount <= 0:
        return False

    rec = g.information.get(s, {})
    is_partial_sold = rec.get('partial_sold', False)

    # [本次新增] LOW3 移动止盈：盈利 > 10% 且从最高点回撤 > 4%
    today_high = g.today_high.get(s, 0)
    if pp > g.trailing_profit_trigger and today_high > 0:
        drawdown = (today_high - cp) / today_high
        if drawdown > g.trailing_drawdown:
            if is_partial_sold:
                order_target_value(s, 0)
                log.info('[LOW3移动止盈-清仓剩余] %s 盈利%.2f%% 回撤%.2f%%' % (s, pp * 100, drawdown * 100))
                g.information.pop(s, None)
                g.today_high.pop(s, None)
                return True
            if pos.closeable_amount >= g.partial_sell_min_shares:
                sell_shares = int(pos.closeable_amount * g.partial_sell_ratio / 100) * 100
                if sell_shares >= 100:
                    order(s, -sell_shares)
                    log.info('[LOW3移动止盈-分批] %s 盈利%.2f%% 回撤%.2f%% 卖出一半(%d股)' % (s, pp * 100, drawdown * 100, sell_shares))
                    g.information[s]['partial_sold'] = True
                    return True
            order_target_value(s, 0)
            log.info('[LOW3移动止盈] %s 盈利%.2f%% 回撤%.2f%% 清仓' % (s, pp * 100, drawdown * 100))
            g.information.pop(s, None)
            g.today_high.pop(s, None)
            return True

    # ===== 原有 LOW3 固定规则 =====
    sell, reason = False, ''
    if pp > 0.5:
        sell, reason = True, '收益>50%'
    elif dg < -0.02:
        sell, reason = True, '当日<-2%'
    elif cd.day_open > 0 and cp < cd.day_open * 0.96:
        sell, reason = True, '当前<开盘-4%'
    elif pp <= -0.07:
        sell, reason = True, '收益<=-7%'
    elif ma5 > 0 and cp < ma5 * 0.97:
        sell, reason = True, '跌破MA5-3%'
    if sell:
        pos = context.portfolio.positions.get(s)
        if pos and pos.closeable_amount > 0:
            order_target_value(s, 0)
            log.info('[卖出] %s 低位-%s' % (s, reason))
            g.information.pop(s, None)
            g.today_high.pop(s, None)
            return True
    return False


# =====================================================================
# 分钟止盈（LOW3 也加入全天移动止盈）
# =====================================================================
def get_minute_sell(context):
    t_day_time = context.current_dt.time()
    if t_day_time < time(9, 30) or t_day_time > time(14, 55):
        return
    _update_today_high(context)

    hold = _held_not_bought_today(context)
    if not hold:
        return
    c_data = get_current_data()
    for s in hold:
        src = _src_of(s)
        cd = c_data[s]
        cp = cd.last_price
        if cp <= 0 or cp >= cd.high_limit * 0.985:
            continue
        pos = context.portfolio.positions.get(s)
        if pos is None or pos.total_amount <= 0 or pos.closeable_amount <= 0:
            continue
        cost = float(pos.avg_cost or 0)
        if cost <= 0:
            continue
        profit = (cp - cost) / cost

        # ===== 移动止盈（LOW3 和 SBGK 都生效，全天 09:30 - 14:55）=====
        if src in ('sbgk', 'both', 'unknown', 'low3'):
            rec = g.information.get(s, {})
            is_partial_sold = rec.get('partial_sold', False)
            today_high = g.today_high.get(s, 0)
            if profit > g.trailing_profit_trigger and today_high > 0:
                drawdown = (today_high - cp) / today_high
                if drawdown > g.trailing_drawdown:
                    tag = 'LOW3' if src == 'low3' else 'SBGK'
                    if is_partial_sold:
                        order_target_value(s, 0)
                        log.info('[分钟%s移动止盈-清仓剩余] %s 盈利%.2f%% 回撤%.2f%%' % (
                            tag, s, profit * 100, drawdown * 100))
                        g.information.pop(s, None)
                        g.today_high.pop(s, None)
                        continue
                    if pos.closeable_amount >= g.partial_sell_min_shares:
                        sell_shares = int(pos.closeable_amount * g.partial_sell_ratio / 100) * 100
                        if sell_shares >= 100:
                            order(s, -sell_shares)
                            log.info('[分钟%s移动止盈-分批] %s 盈利%.2f%% 回撤%.2f%%' % (
                                tag, s, profit * 100, drawdown * 100))
                            g.information[s]['partial_sold'] = True
                            continue
                    order_target_value(s, 0)
                    log.info('[分钟%s移动止盈] %s 盈利%.2f%% 回撤%.2f%% 清仓' % (
                        tag, s, profit * 100, drawdown * 100))
                    g.information.pop(s, None)
                    g.today_high.pop(s, None)
                    continue

        # ===== LOW3 早盘专属规则（限制在 11:25 前）=====
        if t_day_time <= time(11, 25) and src not in ('sbgk',):
            cache = g.minute_sell_cache.get(s)
            if cache and cache.get('date') == context.previous_date:
                y_close = float(cache.get('y_close', 0) or 0)
                if y_close > 0:
                    yesterday_loss = (y_close - cost) / cost
                    if yesterday_loss < -0.02 and profit > 0.02:
                        order_target_value(s, 0)
                        log.info('[分钟止盈] %s 昨亏今盈>2%%' % s)
                        g.information.pop(s, None)
                        continue

            today_open = cd.day_open
            if today_open > 0:
                open_loss = (today_open - cost) / cost
                if open_loss < -0.02 and profit > 0.02:
                    order_target_value(s, 0)
                    log.info('[分钟止盈] %s 开盘亏今盈>2%%' % s)
                    g.information.pop(s, None)
                    continue


# =====================================================================
# 盘前缓存
# =====================================================================
def precompute_sell_cache(context):
    y_day = context.previous_date
    pos = list(context.portfolio.positions.keys())
    g.minute_sell_cache = {}
    g.close_sell_cache = {}
    if not pos:
        g.today_high.clear()
        return
    try:
        df2 = get_price(pos, end_date=y_day, frequency='1d',
                        fields=['close'], count=2, panel=False,
                        skip_paused=False, fill_paused=False)
        if df2 is not None and not df2.empty:
            for s, sub in df2.groupby('code')['close']:
                sub = sub.dropna()
                if len(sub) >= 2:
                    yc, pc = sub.iloc[-1], sub.iloc[-2]
                    g.minute_sell_cache[s] = {
                        'y_close': yc,
                        'prev_close': pc,
                        'y_day_gain': (yc - pc) / pc if pc > 0 else 0,
                        'date': y_day
                    }
    except Exception:
        pass
    try:
        df5 = get_price(pos, end_date=y_day, frequency='1d',
                        fields=['close'], count=5, panel=False,
                        skip_paused=False, fill_paused=False)
        if df5 is not None and not df5.empty:
            for s, sub in df5.groupby('code')['close']:
                sub = sub.dropna()
                if len(sub) >= 2:
                    g.close_sell_cache[s] = {
                        'y_close': sub.iloc[-1],
                        'ma5': float(sub.mean())
                    }
    except Exception:
        pass
    g.today_high.clear()
    log.info('[缓存] 分钟止盈%d 定点卖出%d' % (
        len(g.minute_sell_cache), len(g.close_sell_cache)))


# =====================================================================
# 收盘收尾
# =====================================================================
def after_trading_end(context):
    cur = set(context.portfolio.positions.keys())
    g.information = {k: v for k, v in (g.information or {}).items() if k in cur}
    g.minute_sell_cache = {k: v for k, v in (g.minute_sell_cache or {}).items() if k in cur}
    g.close_sell_cache = {k: v for k, v in (g.close_sell_cache or {}).items() if k in cur}
    g.today_high.clear()
    save_my_state()