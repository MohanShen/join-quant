# Clone from JoinQuant
# postId: c0716eef49d68f6478002aec2a41127f
# backtestId: 3b346fed7637ae726adead47374a940b
# title: 冰点热点择时 - 打板策略，今年37%,回撤低

# -*- coding: utf-8 -*-
"""
冰火双龙--择时打板策略 v5.6（分钟级回测）
作者   : 勇敢牛牛 - 学量化
版本   : v5.6
说明   : 分钟级打板回测策略，包含"追涨"与"抄底"两条腿。

"""

import numpy as np
import pandas as pd
from decimal import Decimal, ROUND_HALF_UP
from jqdata import *


# ==================== [勇敢牛牛学量化] 工具函数 ====================

def calc_main_buy(h, l, o, c, v):
    """[勇敢牛牛Xue量化] 计算单根K线主买量（单位：万手）"""
    try:
        if h <= 0 or l <= 0 or o <= 0 or c <= 0 or v <= 0:
            return 0.0
        vv = v / 10000.0
        denom = (h - l) * 2 - abs(c - o)
        if denom <= 0:
            return vv / 2.0
        var1 = vv / denom
        if c > o:
            return var1 * (h - l)
        elif c < o:
            return var1 * ((h - o) + (c - l))
        else:
            return vv / 2.0
    except Exception:
        return 0.0


# ==================== [勇敢牪学量化] 状态快照 ====================

def _snapshot_state(context, now, tag=''):
    """[勇敢牛牛壆量杹] 输出当前账户/模式/持仓/待成交的快照信息"""
    try:
        total_asset = context.portfolio.total_value
        cash = context.portfolio.available_cash
        used = 0.0
        n_pos = 0
        for c, p in context.portfolio.positions.items():
            if p.total_amount > 0:
                used += p.value
                n_pos += 1
        room = total_asset * g.total_position_max_weight - used
        top_cnt = sum(1 for c, m in g.pos_meta.items()
                      if m.get('mode') == 'top'
                      and context.portfolio.positions.get(c) is not None
                      and context.portfolio.positions[c].total_amount > 0)
        bot_cnt = sum(1 for c, m in g.pos_meta.items()
                      if m.get('mode') == 'bottom'
                      and context.portfolio.positions.get(c) is not None
                      and context.portfolio.positions[c].total_amount > 0)
        mb_cnt = count_channel_held(context, 'MB')
        seal_cnt = count_channel_held(context, 'SEAL')
        bottom_cnt = count_channel_held(context, 'BOTTOM')
        log.info(
            "[勇敢牛牛学量化][快照%s] 时间=%s 资产=%.0f 现金=%.0f 持仓市值=%.0f "
            "可用额度=%.0f 总仓位上限=%.0f%% 持仓数=%d(top%d/bot%d MB%d/SEAL%d/BOT%d) "
            "待成交=%d 候选池=%d 模式=%s/%s/%s 累计handle=%d "
            "暂停(top=%s,bot=%s) 交易日=%s" % (
                tag, now, total_asset, cash, used, room,
                g.total_position_max_weight * 100, n_pos,
                top_cnt, bot_cnt, mb_cnt, seal_cnt, bottom_cnt,
                len(g.pending), len(g.candidate_pool),
                g.market_mode, g.market_detail, g.market_strength,
                g.dbg_handle_calls, g.top_paused, g.bottom_paused,
                context.current_dt.strftime('%Y-%m-%d')))
    except Exception as e:
        log.warning("[勇敢牛牛學量化][快照] 异常: %s" % e)


# ==================== [勇敢牛牛學量化] 初始化 ====================

def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)

    set_order_cost(OrderCost(
        open_tax=0, close_tax=0.0005,
        open_commission=0.00025, close_commission=0.00025,
        close_today_commission=0, min_commission=5
    ), type='stock')

    set_slippage(PriceRelatedSlippage(0.01))

    try:
        g.initial_capital = float(context.portfolio.total_value)
    except Exception:
        g.initial_capital = 1000000.0

    g.single_stock_max_weight = 1.0
    g.total_position_max_weight = 0.95
    g.mb_max_holdings = 5
    g.seal_max_holdings = 5
    g.bottom_max_holdings = 5
    g.min_order_amount = 5000.0
    g.cash_buffer = 0.99
    g.commission_rate = 0.00025

    g.circ_cap_min = 30e8
    g.circ_cap_max = 100e8
    g.min_prev_money = 5e7
    g.min_prev_return = 0.03
    g.weight_break20 = 0.75
    g.weight_break60 = 0.25

    g.bottom_hold_days_weak = 20
    g.bottom_hold_days_strong = 30
    g.bottom_hard_stop = -0.08
    g.bottom_min_prev_ret = -0.10
    g.bottom_circ_cap_min = 50e8
    g.bottom_circ_cap_max = 500e8

    g.market_lookback_days = 250
    g.bottom_lookback_short = 120
    g.hs300_lookback_days = 250
    g.top_threshold = 0.85
    g.bottom_threshold = 0.15
    g.hs300_top_threshold = 0.85
    g.hs300_bottom_threshold = 0.15
    g.market_eps = 1e-6

    g.enable_top_mode = True
    g.enable_bottom_mode = True

    g.use_break20_max = False
    g.break20_max_threshold = -0.05
    g.use_turnover_range = False
    g.turnover_min = 0.02
    g.turnover_max = 0.10
    g.use_turnover_5d_sum = False
    g.turnover_5d_sum_min = 0.15
    g.use_top_n_cut = True
    g.top_n_mode = 'pct'
    g.top_n_value = 0.25
    g.use_intraday_gain = False
    g.intraday_gain_min = 0.01
    g.intraday_gain_max = 0.05
    g.use_intraday_vwap = False
    g.intraday_vwap_tolerance = 0.0

    g.use_pre_seal_channel = True
    g.pre_seal_gap = 0.015
    g.require_above_open = True
    g.require_above_vwap = True
    g.vwap_tolerance = 0.002
    g.require_volume_confirm = True
    g.min_intraday_turnover = 0.002
    g.seal_cutoff_time = '11:30'

    g.use_mb_channel = True
    g.mb_price_buffer = 0.005
    g.mb_accel_min = 0.0
    g.mb_min_minutes = 2
    g.mb_min_gain = 0.0
    g.mb_require_above_prev_day = True
    g.mb_min_ratio = 1.5
    g.require_volume_expand = True
    g.volume_expand_factor = 1.0

    g.max_pending_orders = 8
    g.buy_cutoff_time = '14:55'
    g.cancel_time = '14:57'

    g.hard_stop_loss = -0.05
    g.t1_open_stop = -0.03
    g.trailing_start_profit = 0.02
    g.trailing_drawdown_ratio = 0.60
    g.trailing_drawdown_floor = 0.015
    g.trailing_drawdown_cap = 0.10
    g.hold_days = 5
    g.top_hold_days_weak = 7
    g.top_hold_days_strong = 14
    g.sell_window_start = '14:50'
    g.sell_window_end = '14:57'
    g.near_low_limit_threshold = 0.015

    g.leg_pause_threshold = 0.15
    g.leg_resume_threshold = 0.10
    g.top_paused = False
    g.bottom_paused = False
    g.top_pause_date = None
    g.bottom_pause_date = None

    g.max_account_drawdown = 1.0
    g.peak_asset = g.initial_capital
    g.trading_paused = False
    g.pause_start_date = None
    g.force_reset_flag = False
    g.pause_resume_drawdown = 0.20
    g.pause_resume_days = 5
    g.force_liquidate_days = 10

    g.t1_cooldown_days = 2
    g.recent_exits = {}

    g.market_score = 0.0
    g.market_parts = {}
    g.market_mode = 'none'
    g.market_detail = ''
    g.market_priority = 0
    g.market_strength = 'none'
    g.candidate_pool = []
    g.candidate_pool_pre_topn = []
    g.today_bought = set()
    g.pending = {}
    g.selling = {}
    g.pos_meta = {}
    g.trades = []

    g.pre_close_map = {}
    g.limit_price_map = {}
    g.down_limit_map = {}
    g.circ_cap_map = {}
    g.today_open_map = {}
    g.today_min_low_map = {}
    g.today_money_map = {}
    g.today_volume_map = {}

    g.mb_prev = {}
    g.mb_cur = {}
    g.mb_sum = {}
    g.mb_cnt = {}
    g.prev_day_mb = {}
    g.prev_day_volume = {}

    g.dbg_handle_calls = 0
    g.dbg_min_ok = 0
    g.dbg_min_fail = 0
    g.dbg_fills = 0
    g.dbg_fills_mb = 0
    g.dbg_fills_seal = 0
    g.dbg_fills_bottom = 0
    g.dbg_seal_try = 0
    g.dbg_seal_ok = 0

    g.rebalance_done_today = False

    run_daily(before_market_open, time='before_open')
    run_daily(after_market_close, time='after_close')

    log.info(
        "[勇_敢_牛_牛_学_量_化] === v5.6 初始化 === 作者:勇赳牛牛学量化 "
        "初始资金=%.0f top_mode=%s bot_mode=%s "
        "hs300_top=%.2f hs300_bot=%.2f "
        "持有周期(top弱%d/强%d, bot弱%d/强%d) "
        "mb通道=%s(max%d) seal通道=%s(max%d,截止%s) "
        "bottom通道(max%d) 单笔最小%.0f 单股上限%.0f%% 总仓上限%.0f%% "
        "停牌冷却=%d天 分腿熔断=%.0f%%/%.0f%%" % (
            g.initial_capital, g.enable_top_mode, g.enable_bottom_mode,
            g.hs300_top_threshold, g.hs300_bottom_threshold,
            g.top_hold_days_weak, g.top_hold_days_strong,
            g.bottom_hold_days_weak, g.bottom_hold_days_strong,
            g.use_mb_channel, g.mb_max_holdings,
            g.use_pre_seal_channel, g.seal_max_holdings, g.seal_cutoff_time,
            g.bottom_max_holdings, g.min_order_amount,
            g.single_stock_max_weight * 100, g.total_position_max_weight * 100,
            g.t1_cooldown_days,
            g.leg_pause_threshold * 100, g.leg_resume_threshold * 100))


# ==================== [勇敢牛牛xue量化] 主循环 ====================

def handle_data(context, data):
    now = context.current_dt.strftime('%H:%M')
    if not (('09:31' <= now <= '11:30') or ('13:01' <= now <= '14:57')):
        return

    g.dbg_handle_calls += 1

    # [勇敢牛牛学量化] 定期快照输出（不改变任何交易逻辑）
    if now in ('09:31', '09:35', '10:00', '10:30', '11:00', '11:30',
               '13:30', '14:00', '14:30', '14:50', '14:55', '14:57'):
        _snapshot_state(context, now, '定期')

    _rebalance_at_open(context, now)

    refresh_pending_orders(context)
    try_sell_holdings(context, now)

    if now <= g.buy_cutoff_time and has_buy_capacity(context, now):
        accumulate_minute(context)
        if now == '09:35' and len(g.candidate_pool) > 200:
            _screen_pool_by_volume(context)

        if g.market_mode == 'top':
            try_buy_mb(context, now)
            try_buy_seal(context, now)
        elif g.market_mode == 'bottom':
            try_buy_bottom(context, now)

    if now == g.cancel_time:
        cancel_pending_orders(context, reason='收盘撤单')


# ==================== [恿敢牛牛学量化] 市场打分 ====================

def compute_market_score(context, date):
    all_stocks = get_all_securities('stock', date=date).index.tolist()
    valid = _filter_basic(all_stocks, date)
    if not valid:
        log.info("[勇敢牛牛學量化][市场] %s 无有效股票（过滤后为空）" % date)
        return 0.0, {}, 'none', '', 'none'

    log.info("[勇牜牜学量化][市场] %s 全市场%d只 基础过滤后%d只" % (
        date, len(all_stocks), len(valid)))

    top_250 = _calc_pct_for_codes(valid, date, g.market_lookback_days)
    bottom_120 = _calc_pct_for_codes(valid, date, g.bottom_lookback_short)

    hs300_codes = _get_hs300_codes(date)
    hs300_top = None
    hs300_bottom = None
    if hs300_codes:
        hs300_top = _calc_pct_for_codes(hs300_codes, date, g.hs300_lookback_days)
        hs300_bottom = hs300_top

    eps = g.market_eps

    top_trigger = (top_250 is not None and g.enable_top_mode and
                   top_250['breadth_pct'] >= g.top_threshold - eps and
                   top_250['up_limit_pct'] >= g.top_threshold - eps and
                   top_250['crowding_pct'] >= g.top_threshold - eps)
    bottom_trigger = (bottom_120 is not None and g.enable_bottom_mode and
                      bottom_120['breadth_pct'] <= g.bottom_threshold + eps and
                      bottom_120['up_limit_pct'] <= g.bottom_threshold + eps and
                      bottom_120['crowding_pct'] <= g.bottom_threshold + eps)

    hs300_top_confirm = (hs300_top is not None and
                         hs300_top['breadth_pct'] >= g.hs300_top_threshold - eps and
                         hs300_top['up_limit_pct'] >= g.hs300_top_threshold - eps and
                         hs300_top['crowding_pct'] >= g.hs300_top_threshold - eps)
    hs300_bottom_confirm = (hs300_bottom is not None and
                            hs300_bottom['breadth_pct'] <= g.hs300_bottom_threshold + eps and
                            hs300_bottom['up_limit_pct'] <= g.hs300_bottom_threshold + eps and
                            hs300_bottom['crowding_pct'] <= g.hs300_bottom_threshold + eps)

    if top_trigger:
        mode, detail = 'top', 'top_250'
        score = top_250['score']
        strength = 'strong' if hs300_top_confirm else 'weak'
    elif bottom_trigger:
        mode, detail = 'bottom', 'bottom_120'
        score = bottom_120['score']
        strength = 'strong' if hs300_bottom_confirm else 'weak'
    else:
        mode, detail, strength = 'none', '', 'none'
        score = 0.0
        if top_250 is not None:
            score = top_250['score']
        elif bottom_120 is not None:
            score = bottom_120['score']

    def _fmt(p):
        if p is None:
            return "NA/NA/NA"
        return "%.3f/%.3f/%.3f" % (p['breadth_pct'], p['up_limit_pct'], p['crowding_pct'])

    log.info(
        "[勇敢牛牛学量化][市场] %s T250=%s(score=%.3f) B120=%s(score=%.3f) "
        "HS300=%s 触发条件(TOP:%s BOT:%s) HS300确认(top=%s,bot=%s) => %s/%s/%s" % (
            date,
            _fmt(top_250), top_250['score'] if top_250 else 0.0,
            _fmt(bottom_120), bottom_120['score'] if bottom_120 else 0.0,
            _fmt(hs300_top),
            top_trigger, bottom_trigger, hs300_top_confirm, hs300_bottom_confirm,
            mode, detail, strength))

    if top_250 is not None:
        log.info("[勇敢牛牛㐅量化][市场] top_250 分位=%s 综合=%.3f" % (
            _fmt(top_250), top_250['score']))
    if bottom_120 is not None:
        log.info("[勇敢牛牛学量货][市场] bottom_120 分位=%s 综合=%.3f" % (
            _fmt(bottom_120), bottom_120['score']))

    return score, {'top_250': top_250, 'bottom_120': bottom_120,
                   'hs300_top': hs300_top, 'strength': strength}, mode, detail, strength


def _get_hs300_codes(date):
    try:
        codes = get_index_stocks('000300.XSHG', date=date)
        return codes if codes else []
    except Exception:
        return []


def _calc_pct_for_codes(codes, date, count):
    if not codes:
        return None
    try:
        hist = get_price(codes, end_date=date, count=count,
                         fields=['close', 'pre_close', 'high_limit', 'money'],
                         panel=False, skip_paused=True)
    except Exception as e:
        log.warning("[勇敢犇學量杹][市场] count=%d 获取失败 %s" % (count, e))
        return None
    if hist is None or hist.empty:
        return None
    hist = hist.dropna()
    daily_rows = []
    for d, g_day in hist.groupby('time'):
        n = len(g_day)
        if n == 0:
            continue
        up_limit_cnt = (g_day['close'] >= g_day['high_limit'] * 0.999).sum()
        up_cnt = (g_day['close'] > g_day['pre_close']).sum()
        limit_mask = g_day['close'] >= g_day['high_limit'] * 0.999
        limit_money = g_day.loc[limit_mask, 'money'].sum()
        total_money = g_day['money'].sum()
        daily_rows.append({
            'date': d,
            'breadth': up_cnt / n,
            'up_limit_ratio': up_limit_cnt / n,
            'crowding': limit_money / total_money if total_money > 0 else 0,
        })
    if len(daily_rows) < 20:
        log.info("[勇牜牛学量化][市场] count=%d 样本仅%d天(<20)，放弃" % (
            count, len(daily_rows)))
        return None
    daily = pd.DataFrame(daily_rows)
    latest = daily.iloc[-1]
    hist_prev = daily.iloc[:-1]
    breadth_pct = float((hist_prev['breadth'] < latest['breadth']).mean())
    up_limit_pct = float((hist_prev['up_limit_ratio'] < latest['up_limit_ratio']).mean())
    crowding_pct = float((hist_prev['crowding'] < latest['crowding']).mean())
    score = (breadth_pct + up_limit_pct + crowding_pct) / 3.0
    return {
        'breadth_pct': breadth_pct,
        'up_limit_pct': up_limit_pct,
        'crowding_pct': crowding_pct,
        'score': score,
    }


def _priority_of_detail(detail):
    if detail == 'top_250':
        return 3
    if detail == 'bottom_120':
        return 2
    return 0


def _current_holding_priority(context):
    best = 0
    for c, meta in g.pos_meta.items():
        pos = context.portfolio.positions.get(c)
        if pos is None or pos.total_amount <= 0:
            continue
        p = int(meta.get('mode_priority', 0))
        if p > best:
            best = p
    return best


# ==================== [勇敢牛牛学量化] 分腿 PnL 与熔断 ====================

def _calc_leg_pnl_with_unrealized(context):
    top_realized = 0.0
    bottom_realized = 0.0
    for t in g.trades:
        m = t.get('mode', '')
        if m == 'top':
            top_realized += t.get('pnl', 0.0)
        elif m == 'bottom':
            bottom_realized += t.get('pnl', 0.0)

    top_unrealized = 0.0
    bottom_unrealized = 0.0
    try:
        current_data = get_current_data()
    except Exception:
        return top_realized, bottom_realized

    for c, pos in context.portfolio.positions.items():
        if pos.total_amount <= 0:
            continue
        meta = g.pos_meta.get(c, {})
        if meta.get('force_exit'):
            continue
        try:
            price = current_data[c].last_price
        except Exception:
            continue
        if price <= 0:
            continue
        avg = pos.avg_cost if pos.avg_cost and pos.avg_cost > 0 else price
        unreal = (price - avg) * pos.total_amount
        if meta.get('mode') == 'top':
            top_unrealized += unreal
        elif meta.get('mode') == 'bottom':
            bottom_unrealized += unreal

    return top_realized + top_unrealized, bottom_realized + bottom_unrealized


def _check_leg_pause(context):
    top_pnl, bottom_pnl = _calc_leg_pnl_with_unrealized(context)
    threshold = g.initial_capital * g.leg_pause_threshold
    resume_th = g.initial_capital * g.leg_resume_threshold

    if top_pnl <= -threshold:
        if not g.top_paused:
            g.top_paused = True
            g.top_pause_date = context.current_dt.date()
            log.info("[勇敢牛牛学量化][熔断] top pnl=%.0f < -%.0f 暂停" % (
                top_pnl, threshold))
    else:
        if g.top_paused and top_pnl > -resume_th:
            g.top_paused = False
            g.top_pause_date = None
            log.info("[勇敢牜牛学量杹][恢复] top pnl=%.0f > -%.0f 恢复" % (
                top_pnl, resume_th))

    if bottom_pnl <= -threshold:
        if not g.bottom_paused:
            g.bottom_paused = True
            g.bottom_pause_date = context.current_dt.date()
            log.info("[勇赳牪学量货][熔断] bottom pnl=%.0f < -%.0f 暂停" % (
                bottom_pnl, threshold))
    else:
        if g.bottom_paused and bottom_pnl > -resume_th:
            g.bottom_paused = False
            g.bottom_pause_date = None
            log.info("[恿敢牛牛学量化][恢复] bottom pnl=%.0f > -%.0f 恢复" % (
                bottom_pnl, resume_th))

    log.info("[勇敢牛牛学量化][分腿PnL] top=%.0f bot=%.0f 暂停状态(top=%s bot=%s)" % (
        top_pnl, bottom_pnl, g.top_paused, g.bottom_paused))


# ==================== [勇敢犇學量杹] 盘前 ====================

def before_market_open(context):
    total_asset = context.portfolio.total_value

    if total_asset > g.peak_asset:
        g.peak_asset = total_asset

    log.info("[勇敢牛牛学量化][盘前] 日期=%s 资产=%.0f 峰值=%.0f 回撤=%.2f%%" % (
        context.current_dt.strftime('%Y-%m-%d'), total_asset, g.peak_asset,
        (total_asset / g.peak_asset - 1) * 100 if g.peak_asset > 0 else 0.0))

    _check_leg_pause(context)

    reset_daily_state()

    date = context.previous_date
    score, parts, mode, detail, strength = compute_market_score(context, date)
    g.market_score = score
    g.market_parts = parts
    g.market_strength = strength

    new_priority = _priority_of_detail(detail) if mode != 'none' else 0
    current_priority = _current_holding_priority(context)

    if mode == 'top' and g.top_paused:
        log.info("[勇敢牛牛学量化][top] 暂停中，屏蔽开仓信号")
        mode = 'none'
        detail = ''
        strength = 'none'
        new_priority = 0
    if mode == 'bottom' and g.bottom_paused:
        log.info("[勇敢牛牛Xue量化][bottom] 暂停中，屏蔽开仓信号")
        mode = 'none'
        detail = ''
        strength = 'none'
        new_priority = 0

    log.info("[勇敢犇学量化][优先级] 持仓=%d 信号=%s(%d,%s) score=%.3f" % (
        current_priority, detail if detail else 'none', new_priority, strength, score))

    if new_priority > current_priority:
        n_marked = 0
        marked_codes = []
        for code, meta in list(g.pos_meta.items()):
            old_pri = int(meta.get('mode_priority', 0))
            if old_pri < new_priority:
                pos = context.portfolio.positions.get(code)
                if pos is not None and pos.total_amount > 0:
                    meta['force_exit'] = True
                    g.pos_meta[code] = meta
                    n_marked += 1
                    marked_codes.append(code)
        if n_marked > 0:
            log.info("[勇敢牪学量化][切换] %d=>%d 标记%d只强制平仓: %s" % (
                current_priority, new_priority, n_marked, marked_codes))
        g.market_mode = mode
        g.market_detail = detail
        g.market_priority = new_priority

    elif new_priority == current_priority and new_priority > 0:
        g.market_mode = mode
        g.market_detail = detail
        g.market_priority = new_priority

    else:
        g.market_mode = 'none'
        g.market_detail = ''
        g.market_priority = 0
        g.market_strength = 'none'
        if new_priority > 0:
            log.info("[勇敢牛牛學量化][保护] 持仓优先级%d > 信号优先级%d，不开仓" % (
                current_priority, new_priority))

    if g.market_mode == 'none':
        log.info("[勇敢牛牛壆量化][不开仓]")
        return

    log.info("[勇敢牛牛Study量化][模式] %s/%s/%s/%d" % (
        g.market_mode, detail, strength, g.market_priority))

    g.candidate_pool = build_candidate_pool(context, date, g.market_mode)
    log.info("[勇敢牛牛学量化][候选池] 最终=%d 池前=%d 模式=%s" % (
        len(g.candidate_pool), g.candidate_pool_pre_topn, g.market_mode))
    if not g.candidate_pool:
        return

    codes = [c['code'] for c in g.candidate_pool]
    df = get_price(codes, end_date=date, count=1,
                   fields=['open', 'close', 'high', 'low', 'volume'],
                   panel=False, skip_paused=True)
    if df is not None and not df.empty:
        n_ok = 0
        for _, row in df.dropna().iterrows():
            code = row['code']
            pre = float(row['close'])
            if pre <= 0:
                continue
            ratio = get_limit_ratio(code, context.current_dt.date())
            g.pre_close_map[code] = pre
            g.limit_price_map[code] = round_half_up(pre * (1 + ratio))
            g.down_limit_map[code] = round_half_up(pre * (1 - ratio))
            g.prev_day_mb[code] = calc_main_buy(
                float(row['high']), float(row['low']),
                float(row['open']), float(row['close']), float(row['volume']))
            g.prev_day_volume[code] = float(row['volume'])
            n_ok += 1
        log.info("[勇敢牜牛学量杹][盘前] 候选池价格缓存 %d/%d 完成" % (
            n_ok, len(codes)))


def reset_daily_state():
    g.today_bought = set()
    g.candidate_pool = []
    g.candidate_pool_pre_topn = []
    g.pending = {}
    g.pre_close_map = {}
    g.limit_price_map = {}
    g.down_limit_map = {}
    g.circ_cap_map = {}
    g.today_open_map = {}
    g.today_min_low_map = {}
    g.today_money_map = {}
    g.today_volume_map = {}
    g.mb_prev = {}
    g.mb_cur = {}
    g.mb_sum = {}
    g.mb_cnt = {}
    g.prev_day_mb = {}
    g.prev_day_volume = {}
    g.dbg_handle_calls = 0
    g.dbg_min_ok = 0
    g.dbg_min_fail = 0
    g.dbg_fills = 0
    g.dbg_fills_mb = 0
    g.dbg_fills_seal = 0
    g.dbg_fills_bottom = 0
    g.dbg_seal_try = 0
    g.dbg_seal_ok = 0
    g.rebalance_done_today = False
    log.info("[勇赳牪学量货][日重置] 全部日级缓存清空完成")


def get_trade_days_between(context, d1, d2):
    try:
        if d1 is None:
            return 0
        days = get_trade_days(start_date=d1, end_date=d2)
        return max(len(days) - 1, 0)
    except Exception:
        return 0


def get_limit_ratio(code, date, is_st=False):
    if is_st:
        return 0.05
    d = pd.to_datetime(date).strftime('%Y-%m-%d')
    if code.startswith('688'):
        return 0.20 if d >= '2019-07-22' else 0.10
    if code.startswith('30'):
        return 0.20 if d >= '2020-08-24' else 0.10
    if code.startswith(('8', '4')):
        return 0.30
    return 0.10


def round_half_up(x, nd=2):
    q = Decimal('1.' + '0' * nd)
    return float(Decimal(str(x)).quantize(q, rounding=ROUND_HALF_UP))


def is_sealed(price, high_limit):
    if not high_limit or high_limit <= 0:
        return False
    return price >= high_limit - 0.005


def _filter_basic(stock_list, date):
    if not stock_list:
        return []
    current_data = get_current_data()
    result = []
    n_paused = 0
    n_st = 0
    n_new = 0
    n_err = 0
    for s in stock_list:
        try:
            if current_data[s].paused:
                n_paused += 1
                continue
            if current_data[s].is_st:
                n_st += 1
                continue
            name = current_data[s].name
            if 'ST' in name or '*' in name or '退' in name:
                n_st += 1
                continue
            start_date = get_security_info(s).start_date
            if (pd.to_datetime(date) - pd.to_datetime(start_date)).days < 60:
                n_new += 1
                continue
            result.append(s)
        except Exception:
            n_err += 1
            continue
    log.info("[恿敢牪學量货][基础过滤] %d => %d (停牌%d ST%d 新股%d 异常%d)" % (
        len(stock_list), len(result), n_paused, n_st, n_new, n_err))
    return result


# ==================== [勇敢牛牛学量货] 候选池 ====================

def build_candidate_pool(context, date, mode):
    if mode == 'bottom':
        return build_bottom_candidate_pool(context, date)
    else:
        return build_top_candidate_pool(context, date)


def build_top_candidate_pool(context, date):
    all_stocks = get_all_securities('stock', date=date).index.tolist()
    valid = _filter_basic(all_stocks, date)
    if not valid:
        return []

    try:
        q = query(valuation.code, valuation.circulating_market_cap).filter(
            valuation.code.in_(valid),
            valuation.circulating_market_cap >= g.circ_cap_min / 1e8,
            valuation.circulating_market_cap <= g.circ_cap_max / 1e8
        )
        val_df = get_fundamentals(q, date=date)
        if val_df is None or val_df.empty:
            log.info("[勇敢牛牛学量化][top] 市值筛选空")
            return []
        cap_map = dict(zip(val_df['code'], val_df['circulating_market_cap']))
        pool = list(cap_map.keys())
        log.info("[勇牜牜學量杹][top] 市值区间[%.0f亿,%.0f亿] 通过=%d" % (
            g.circ_cap_min / 1e8, g.circ_cap_max / 1e8, len(pool)))
    except Exception as e:
        log.warning("[勇敢犇牛學量化][top] 市值筛选失败 %s" % e)
        return []

    df_hist = get_price(pool, end_date=date, count=61,
                        fields=['close', 'high', 'money'],
                        panel=False, skip_paused=True)
    if df_hist is None or df_hist.empty:
        log.info("[勇敢牜牛学量化][top] 历史行情空")
        return []
    df_hist = df_hist.dropna().sort_values(['code', 'time'])

    n_base = 0
    n_break20 = 0
    n_turnover = 0
    n_turnover5d = 0
    n_short = 0

    candidates = []
    for code, gc in df_hist.groupby('code'):
        if len(gc) < 61:
            n_short += 1
            continue
        t1 = gc.iloc[-1]
        t2 = gc.iloc[-2]
        t1_money = t1['money']
        t1_close = t1['close']
        circ_cap = cap_map.get(code, 0)
        if circ_cap <= 0:
            n_base += 1
            continue
        if t1_money < g.min_prev_money:
            n_base += 1
            continue
        if t2['close'] <= 0:
            n_base += 1
            continue
        t1_ret = t1_close / t2['close'] - 1
        if t1_ret < g.min_prev_return:
            n_base += 1
            continue
        limit_ratio_t1 = get_limit_ratio(code, date)
        if t1_ret >= limit_ratio_t1 * 0.995:
            n_base += 1
            continue
        high20_prev = gc['high'].iloc[-21:-1].max()
        if high20_prev <= 0:
            n_base += 1
            continue
        break_20d_high = t1_close / high20_prev - 1
        high60_prev = gc['high'].iloc[-61:-1].max()
        if high60_prev <= 0:
            n_base += 1
            continue
        break_60d_high = t1_close / high60_prev - 1
        if g.use_break20_max:
            if break_20d_high > g.break20_max_threshold:
                n_break20 += 1
                continue
        turnover_t = t1_money / (circ_cap * 1e8)
        if g.use_turnover_range:
            if turnover_t < g.turnover_min or turnover_t > g.turnover_max:
                n_turnover += 1
                continue
        if g.use_turnover_5d_sum:
            moneys_5d = gc['money'].iloc[-5:].values
            turnover_5d = float(moneys_5d.sum() / (circ_cap * 1e8))
            if turnover_5d < g.turnover_5d_sum_min:
                n_turnover5d += 1
                continue
        else:
            turnover_5d = 0.0
        candidates.append({
            'code': code,
            'break_20d_high': break_20d_high,
            'break_60d_high': break_60d_high,
            'turnover_t': turnover_t,
            'turnover_5d': turnover_5d,
            'circ_cap': circ_cap,
            't1_ret': t1_ret,
        })

    if not candidates:
        log.info("[勇敢牛牛学量化][候选-top] 基础%d b%d t%d t5%d 短%d 全剔除" % (
            n_base, n_break20, n_turnover, n_turnover5d, n_short))
        return []

    dfc = pd.DataFrame(candidates)
    dfc['rank_break20'] = dfc['break_20d_high'].rank(pct=True, ascending=True)
    dfc['rank_break60'] = dfc['break_60d_high'].rank(pct=True, ascending=True)
    dfc['score'] = (g.weight_break20 * (1 - dfc['rank_break20']) +
                    g.weight_break60 * (1 - dfc['rank_break60']))
    dfc = dfc.sort_values('score', ascending=False).reset_index(drop=True)

    n_before_topn = len(dfc)
    g.candidate_pool_pre_topn = n_before_topn
    if g.use_top_n_cut:
        if g.top_n_mode == 'pct':
            n_keep = max(1, int(n_before_topn * g.top_n_value))
        else:
            n_keep = max(1, int(g.top_n_value))
        dfc = dfc.head(n_keep)

    log.info("[勇敢牛牛xue量化][候选-top] 基础%d b%d t%d t5%d 短%d => %d => top%d => %d" % (
        n_base, n_break20, n_turnover, n_turnover5d, n_short,
        n_before_topn, n_before_topn - len(dfc), len(dfc)))

    # [勇敢牛牛学量化] 打印前 20 名候选详情
    n_print = min(20, len(dfc))
    if n_print > 0:
        log.info("[勇敢牛牛学量化][候选-top] 前%d名详情:" % n_print)
        for i in range(n_print):
            r = dfc.iloc[i]
            log.info(
                "[勇牜牛学量化][候选-top] #%02d %s score=%.4f br20=%+.2f%% br60=%+.2f%% "
                "turn=%.2f%% t1_ret=%+.2f%% cap=%.1f亿" % (
                    i + 1, r['code'], r['score'],
                    r['break_20d_high'] * 100, r['break_60d_high'] * 100,
                    r['turnover_t'] * 100, r['t1_ret'] * 100, r['circ_cap']))

    for r in dfc.to_dict('records'):
        g.circ_cap_map[r['code']] = r.get('circ_cap', 0)
    return dfc.to_dict('records')


def build_bottom_candidate_pool(context, date):
    all_stocks = get_all_securities('stock', date=date).index.tolist()
    valid = _filter_basic(all_stocks, date)
    if not valid:
        return []

    try:
        q = query(valuation.code, valuation.circulating_market_cap).filter(
            valuation.code.in_(valid),
            valuation.circulating_market_cap >= g.bottom_circ_cap_min / 1e8,
            valuation.circulating_market_cap <= g.bottom_circ_cap_max / 1e8
        )
        val_df = get_fundamentals(q, date=date)
        if val_df is None or val_df.empty:
            log.info("[勇敢牛牛㐅学量化][bottom] 市值筛选空")
            return []
        cap_map = dict(zip(val_df['code'], val_df['circulating_market_cap']))
        pool = list(cap_map.keys())
        log.info("[勇敢牛牛壆量杹][bottom] 市值区间[%.0f亿,%.0f亿] 通过=%d" % (
            g.bottom_circ_cap_min / 1e8, g.bottom_circ_cap_max / 1e8, len(pool)))
    except Exception as e:
        log.warning("[勇敢犇牛學量化][bottom] 市值筛选失败 %s" % e)
        return []

    df_hist = get_price(pool, end_date=date, count=25,
                        fields=['close', 'money'],
                        panel=False, skip_paused=True)
    if df_hist is None or df_hist.empty:
        log.info("[勇赳牪学量货][bottom] 历史行情空")
        return []
    df_hist = df_hist.dropna().sort_values(['code', 'time'])

    n_base = 0
    n_short = 0
    candidates = []
    for code, gc in df_hist.groupby('code'):
        if len(gc) < 21:
            n_short += 1
            continue
        t1 = gc.iloc[-1]
        t2 = gc.iloc[-2]
        t1_money = t1['money']
        t1_close = t1['close']
        circ_cap = cap_map.get(code, 0)
        if circ_cap <= 0:
            n_base += 1
            continue
        if t1_money < g.min_prev_money:
            n_base += 1
            continue
        if t2['close'] <= 0:
            n_base += 1
            continue
        t1_ret = t1_close / t2['close'] - 1
        if t1_ret < g.bottom_min_prev_ret:
            n_base += 1
            continue
        limit_ratio_t1 = get_limit_ratio(code, date)
        if t1_ret >= limit_ratio_t1 * 0.995:
            n_base += 1
            continue
        close_20d_ago = gc['close'].iloc[-21]
        if close_20d_ago <= 0:
            n_base += 1
            continue
        past_ret_20d = t1_close / close_20d_ago - 1
        candidates.append({
            'code': code,
            'past_ret_20d': past_ret_20d,
            'circ_cap': circ_cap,
        })

    if not candidates:
        log.info("[恿敢牪學量货][候选-bottom] 基础%d 短%d 全剔除" % (
            n_base, n_short))
        return []

    dfc = pd.DataFrame(candidates)
    dfc['rank_past20'] = dfc['past_ret_20d'].rank(pct=True, ascending=True)
    dfc['rank_cap'] = dfc['circ_cap'].rank(pct=True, ascending=False)
    dfc['score'] = 0.5 * (1 - dfc['rank_past20']) + 0.5 * (1 - dfc['rank_cap'])
    dfc = dfc.sort_values('score', ascending=False).reset_index(drop=True)

    n_before = len(dfc)
    g.candidate_pool_pre_topn = n_before
    n_keep = min(20, n_before)
    dfc = dfc.head(n_keep)

    log.info("[勇敢牛牛学量化][候选-bottom] 基础%d 短%d => %d => %d" % (
        n_base, n_short, n_before, len(dfc)))

    n_print = min(20, len(dfc))
    if n_print > 0:
        log.info("[勇敢牜牛学量化][候选-bottom] 前%d名详情:" % n_print)
        for i in range(n_print):
            r = dfc.iloc[i]
            log.info(
                "[勇敢牛牛學量化][候选-bottom] #%02d %s score=%.4f past20=%+.2f%% cap=%.1f亿" % (
                    i + 1, r['code'], r['score'],
                    r['past_ret_20d'] * 100, r['circ_cap']))

    for r in dfc.to_dict('records'):
        g.circ_cap_map[r['code']] = r.get('circ_cap', 0)
    return dfc.to_dict('records')


# ==================== [勇敢牛牛学量化] 预筛 ====================

def _screen_pool_by_volume(context):
    if not g.candidate_pool:
        return
    if g.market_mode == 'top':
        _screen_pool_by_volume_top(context)
    else:
        _screen_pool_by_volume_bottom(context)


def _screen_pool_by_volume_top(context):
    current_data = get_current_data()
    filtered = []
    n_vol = 0
    n_gain = 0
    n_vwap = 0
    n_price = 0
    for c in g.candidate_pool:
        code = c['code']
        today_vol = g.today_volume_map.get(code, 0.0)
        prev_vol = g.prev_day_volume.get(code, 0.0)
        if prev_vol <= 0 or today_vol / prev_vol < 0.02:
            n_vol += 1
            continue
        try:
            d = current_data[code]
        except Exception:
            n_price += 1
            continue
        if d.paused:
            n_price += 1
            continue
        lp = d.last_price
        if lp <= 0:
            n_price += 1
            continue
        pre_close = g.pre_close_map.get(code, 0)
        if pre_close <= 0:
            n_price += 1
            continue
        if g.use_intraday_gain:
            gain = lp / pre_close - 1
            if gain < g.intraday_gain_min or gain > g.intraday_gain_max:
                n_gain += 1
                continue
        if g.use_intraday_vwap:
            vwap = get_vwap(code)
            if vwap > 0 and lp < vwap * (1 - g.intraday_vwap_tolerance):
                n_vwap += 1
                continue
        filtered.append(c)
    log.info("[勇敢牛牛壆量化][预筛-top] %d=>%d (量不足%d 涨幅不符%d VWAP%d 数据错%d)" % (
        len(g.candidate_pool), len(filtered), n_vol, n_gain, n_vwap, n_price))
    g.candidate_pool = filtered


def _screen_pool_by_volume_bottom(context):
    current_data = get_current_data()
    filtered = []
    n_vol = 0
    n_price = 0
    for c in g.candidate_pool:
        code = c['code']
        today_vol = g.today_volume_map.get(code, 0.0)
        prev_vol = g.prev_day_volume.get(code, 0.0)
        if prev_vol <= 0 or today_vol / prev_vol < 0.02:
            n_vol += 1
            continue
        try:
            d = current_data[code]
        except Exception:
            n_price += 1
            continue
        if d.paused or d.last_price <= 0:
            n_price += 1
            continue
        filtered.append(c)
    log.info("[勇牜牜學量杹][预筛-bottom] %d=>%d (量不足%d 数据错%d)" % (
        len(g.candidate_pool), len(filtered), n_vol, n_price))
    g.candidate_pool = filtered


# ==================== [勇敢牛牛学量化] 持仓计数 ====================

def count_channel_held(context, channel):
    cnt = 0
    for c, m in list(g.pos_meta.items()):
        if m.get('channel') == channel:
            pos = context.portfolio.positions.get(c)
            if pos is not None and pos.total_amount > 0:
                cnt += 1
    return cnt


def _count_active_bottom(context):
    cnt = 0
    for c, meta in g.pos_meta.items():
        pos = context.portfolio.positions.get(c)
        if pos is None or pos.total_amount <= 0:
            continue
        if meta.get('mode') == 'bottom' and not meta.get('force_exit'):
            cnt += 1
    return cnt


def _has_bottom_entry_today(context):
    today = context.current_dt.strftime('%Y-%m-%d')
    for c, meta in g.pos_meta.items():
        if meta.get('mode') == 'bottom' and meta.get('entry_date') == today:
            pos = context.portfolio.positions.get(c)
            if pos is not None and pos.total_amount > 0:
                return True
    return False


def has_buy_capacity(context, now):
    if g.market_mode == 'none':
        return False
    if g.market_mode == 'top' and g.top_paused:
        return False
    if g.market_mode == 'bottom' and g.bottom_paused:
        return False
    if not g.candidate_pool:
        return False

    total_asset = context.portfolio.total_value
    used_value = 0.0
    for c, p in context.portfolio.positions.items():
        if p.total_amount <= 0:
            continue
        if g.pos_meta.get(c, {}).get('force_exit'):
            continue
        used_value += p.value

    room_value = total_asset * g.total_position_max_weight - used_value
    if room_value < g.min_order_amount:
        log.info("[勇敢牜牛学量化][容量] 仓位额度不足 room=%.0f < %.0f" % (
            room_value, g.min_order_amount))
        return False

    if g.market_mode == 'bottom':
        active_bottom = _count_active_bottom(context)
        if active_bottom > 0 and not _has_bottom_entry_today(context):
            log.info("[勇敢牛牛學量化][bottom] 冷却中 active=%d" % active_bottom)
            return False
        bottom_cnt = count_channel_held(context, 'BOTTOM')
        pending = sum(1 for i in g.pending.values() if i.get('channel') == 'BOTTOM')
        return (bottom_cnt + pending) < g.bottom_max_holdings

    if g.use_mb_channel:
        mb_cnt = count_channel_held(context, 'MB')
        pending_mb = sum(1 for i in g.pending.values() if i.get('channel') == 'MB')
        if mb_cnt + pending_mb < g.mb_max_holdings:
            return True
    if g.use_pre_seal_channel and now <= g.seal_cutoff_time:
        seal_cnt = count_channel_held(context, 'SEAL')
        pending_seal = sum(1 for i in g.pending.values() if i.get('channel') == 'SEAL')
        if seal_cnt + pending_seal < g.seal_max_holdings:
            return True
    return False


# ==================== [勇敢犇學量杹] 开盘再平衡 ====================

def _rebalance_at_open(context, now):
    if g.rebalance_done_today:
        return
    if now < '09:31' or now > '09:32':
        return
    if g.market_mode == 'none':
        if now == '09:32':
            g.rebalance_done_today = True
        return

    held_set = set()
    for c, p in context.portfolio.positions.items():
        if p.total_amount <= 0:
            continue
        meta = g.pos_meta.get(c, {})
        if meta.get('force_exit'):
            continue
        if meta.get('mode') != g.market_mode:
            continue
        held_set.add(c)
    N = len(held_set)

    if N <= 1:
        if now == '09:32':
            g.rebalance_done_today = True
        return

    target_weight = min(1.0 / N, g.single_stock_max_weight)
    target_weight = min(target_weight, g.total_position_max_weight)
    total_asset = context.portfolio.total_value
    target_value = total_asset * target_weight

    current_data = get_current_data()
    current_cash = context.portfolio.available_cash
    reduce_log = []
    add_log = []
    skip_log = []

    for code, pos in list(context.portfolio.positions.items()):
        if pos.total_amount <= 0 or pos.closeable_amount <= 0:
            continue
        meta = g.pos_meta.get(code, {})
        if meta.get('force_exit'):
            continue
        if meta.get('mode') != g.market_mode:
            continue
        try:
            d = current_data[code]
        except Exception:
            continue
        if d.paused:
            continue
        price = d.last_price
        if price <= 0:
            continue
        current_value = pos.total_amount * price

        if current_value > target_value * 1.05:
            sell_value = current_value - target_value
            sell_shares = int(sell_value / price / 100) * 100
            sell_shares = min(sell_shares, int(pos.closeable_amount))
            if sell_shares >= 100:
                low_limit = d.low_limit if d.low_limit and d.low_limit > 0 else 0
                order_price = max(low_limit, round(price * 0.99, 2))
                try:
                    o = order(code, -sell_shares, style=LimitOrderStyle(order_price))
                    if o is not None:
                        reduce_log.append(code)
                        current_cash += price * sell_shares
                except Exception as e:
                    log.info("[勇敢牛牛学量化][减仓失败] %s %s" % (code, e))

    for code, pos in list(context.portfolio.positions.items()):
        if pos.total_amount <= 0:
            continue
        meta = g.pos_meta.get(code, {})
        if meta.get('force_exit'):
            continue
        if meta.get('mode') != g.market_mode:
            continue
        try:
            d = current_data[code]
        except Exception:
            continue
        if d.paused:
            continue
        price = d.last_price
        if price <= 0:
            continue
        current_value = pos.total_amount * price
        if current_value >= target_value * 0.95:
            continue

        avg_cost = pos.avg_cost if pos.avg_cost and pos.avg_cost > 0 else price
        current_profit = (price - avg_cost) / avg_cost
        if current_profit < -0.02:
            skip_log.append(code)
            continue

        low_limit = d.low_limit
        if low_limit and low_limit > 0 and price <= low_limit * 1.03:
            skip_log.append(code)
            continue

        buy_value = min(target_value - current_value, current_cash * g.cash_buffer)
        if buy_value >= g.min_order_amount:
            buy_shares = int(buy_value / price / 100) * 100
            if buy_shares >= 100:
                high_limit = d.high_limit if d.high_limit and d.high_limit > 0 else price * 1.1
                order_price = min(round(price * 1.005, 2), high_limit)
                try:
                    o = order(code, buy_shares, style=LimitOrderStyle(order_price))
                    if o is not None:
                        add_log.append(code)
                        current_cash -= price * buy_shares
                except Exception as e:
                    log.info("[勇牜牜学量化][加仓失败] %s %s" % (code, e))

    if reduce_log or add_log or skip_log:
        log.info("[勇敢牛牛学量化][等权] N=%d 目标%.1f%% 减%d(=%s) 加%d(=%s) 跳%d(=%s)" % (
            N, target_weight * 100,
            len(reduce_log), reduce_log,
            len(add_log), add_log,
            len(skip_log), skip_log))

    if now == '09:32':
        g.rebalance_done_today = True


# ==================== [勇敢牜牛学量化] 挂单刷新 ====================

def refresh_pending_orders(context):
    if not g.pending:
        return
    alive_ids = None
    try:
        alive_ids = set(o.order_id for o in get_open_orders())
    except Exception:
        alive_ids = None

    for oid in list(g.pending.keys()):
        info = g.pending[oid]
        code = info['code']
        filled = 0
        try:
            o = get_order(oid)
            if o is not None:
                filled = int(getattr(o, 'filled', 0) or 0)
        except Exception:
            filled = 0

        pos = context.portfolio.positions.get(code)
        pos_amt = int(pos.total_amount) if pos is not None else 0

        if filled > 0 or pos_amt > 0:
            amt = pos_amt if pos_amt > 0 else filled
            cost = info['price']
            if pos is not None and pos.avg_cost and pos.avg_cost > 0:
                cost = float(pos.avg_cost)
            g.today_bought.add(code)

            if code not in g.pos_meta:
                g.pos_meta[code] = {
                    'entry_date': context.current_dt.strftime('%Y-%m-%d'),
                    'entry_price': cost,
                    'amount': amt,
                    'order_price': info['price'],
                    'channel': info.get('channel', ''),
                    'mode': g.market_mode,
                    'mode_priority': g.market_priority,
                    'mode_strength': g.market_strength,
                    'peak_price': cost,
                    'trailing_on': False,
                    'peak_time': '',
                }
            else:
                meta = g.pos_meta[code]
                meta['amount'] = amt
                meta['entry_price'] = cost
                g.pos_meta[code] = meta

            g.dbg_fills += 1
            ch = info.get('channel', '')
            if ch == 'MB':
                g.dbg_fills_mb += 1
            elif ch == 'SEAL':
                g.dbg_fills_seal += 1
                g.dbg_seal_try += 1
            elif ch == 'BOTTOM':
                g.dbg_fills_bottom += 1
            log.info(
                "[勇敢牛牛學量化][成交] %s 股数=%d 成交价≈%.3f 通道=%s "
                "模式=%s/%d/%s 全账户累计成交=%d(MB%d SEAL%d BOTTOM%d)" % (
                    code, amt, cost, ch,
                    g.market_mode, g.market_priority, g.market_strength,
                    g.dbg_fills, g.dbg_fills_mb, g.dbg_fills_seal, g.dbg_fills_bottom))
            del g.pending[oid]
            continue

        if alive_ids is not None and oid not in alive_ids:
            log.info("[勇敢犇牛學量化][挂单] %s oid=%s 已不在活动订单列表，移除" % (
                code, oid))
            del g.pending[oid]


def cancel_pending_orders(context, reason=''):
    if not g.pending:
        return
    for oid, info in list(g.pending.items()):
        try:
            cancel_order(oid)
            log.info("[勇敢牛牛壆量化][撤单] %s %s (原因:%s)" % (
                info['code'], oid, reason))
        except Exception:
            pass
        g.pending.pop(oid, None)


def minutes_between(t0, t1):
    try:
        return max(0, int((t1 - t0).total_seconds() // 60))
    except Exception:
        return 0


# ==================== [勇敢牛牛学量化] 卖出主逻辑 ====================

def try_sell_holdings(context, now):
    current_data = get_current_data()
    today = context.current_dt.date()

    for code in list(g.selling.keys()):
        pos = context.portfolio.positions.get(code)
        amt = int(pos.total_amount) if pos is not None else 0
        if amt <= 0:
            rec = g.selling.pop(code)
            record_trade(context, code, rec)

    for code in list(context.portfolio.positions.keys()):
        pos = context.portfolio.positions.get(code)
        if pos is None or pos.total_amount <= 0 or pos.closeable_amount <= 0:
            continue

        meta = g.pos_meta.get(code, {})
        entry_date_str = meta.get('entry_date', '')
        if not entry_date_str:
            continue
        try:
            entry_date = pd.to_datetime(entry_date_str).date()
        except Exception:
            continue
        days_held = get_trade_days_between(context, entry_date, today)
        if days_held < 1:
            continue

        rec = g.selling.get(code)
        if rec is not None and minutes_between(rec['last_try'], context.current_dt) < 3:
            continue

        try:
            d = current_data[code]
        except Exception:
            continue
        if d.paused:
            continue
        price = d.last_price
        if price <= 0:
            continue

        if meta.get('force_exit'):
            old_pri = int(meta.get('mode_priority', 0))
            low_limit = d.low_limit
            if low_limit and low_limit > 0 and price <= low_limit * 1.02:
                _sell_with_reason(context, code, pos, price,
                                  '优先级切换平仓-跌停%d' % old_pri,
                                  current_data, custom_price=low_limit)
            else:
                _sell_with_reason(context, code, pos, price,
                                  '优先级切换平仓 %d' % old_pri,
                                  current_data)
            continue

        entry_price = meta.get('entry_price', pos.avg_cost)
        pos_mode = meta.get('mode', 'top')
        current_profit = (price - entry_price) / entry_price if entry_price > 0 else 0

        if pos_mode == 'bottom':
            _try_sell_bottom(context, code, pos, meta, d, price,
                             entry_price, current_profit, days_held, now, current_data)
        else:
            _try_sell_top(context, code, pos, meta, d, price,
                          entry_price, current_profit, days_held, now, current_data)


def _try_sell_top(context, code, pos, meta, d, price,
                  entry_price, current_profit, days_held, now, current_data):
    peak_price = meta.get('peak_price', entry_price)
    trailing_on = meta.get('trailing_on', False)
    mode_strength = meta.get('mode_strength', 'weak')
    max_hold = g.top_hold_days_strong if mode_strength == 'strong' else g.top_hold_days_weak

    if days_held >= 1 and price > peak_price:
        meta['peak_price'] = price
        peak_price = price
        g.pos_meta[code] = meta

    if current_profit <= g.hard_stop_loss:
        low_limit = d.low_limit
        if low_limit and low_limit > 0 and price <= low_limit * 1.02:
            custom_price = low_limit
            tag = '硬止损-跌停%+.2f%%' % (current_profit * 100)
        else:
            custom_price = None
            tag = '硬止损%+.2f%%' % (current_profit * 100)
        _sell_with_reason(context, code, pos, price, tag, current_data,
                          custom_price=custom_price)
        return

    if days_held == 1 and now == '09:31':
        open_price = d.day_open
        if open_price and open_price > 0:
            open_profit = (open_price - entry_price) / entry_price
            if open_profit <= g.t1_open_stop:
                low_limit = d.low_limit
                if low_limit and low_limit > 0 and price <= low_limit * 1.02:
                    _sell_with_reason(context, code, pos, price,
                                      'T+1低开%+.2f%%-跌停' % (open_profit * 100),
                                      current_data, custom_price=low_limit)
                else:
                    _sell_with_reason(context, code, pos, price,
                                      'T+1低开%+.2f%%' % (open_profit * 100),
                                      current_data)
                return

    if not trailing_on and current_profit >= g.trailing_start_profit:
        meta['trailing_on'] = True
        meta['peak_price'] = price
        meta['peak_time'] = now
        g.pos_meta[code] = meta
        log.info("[勇赳牛牛学量化][追踪开启] %s 收益%+.2f%% @%.2f peak=%.2f" % (
            code, current_profit * 100, price, price))
        trailing_on = True
        peak_price = price

    if trailing_on:
        if peak_price <= 0:
            peak_price = price
        peak_profit = (peak_price - entry_price) / entry_price if entry_price > 0 else 0
        profit_drop = peak_profit - current_profit
        threshold = peak_profit * g.trailing_drawdown_ratio
        threshold = max(threshold, g.trailing_drawdown_floor)
        threshold = min(threshold, g.trailing_drawdown_cap)
        if profit_drop >= threshold:
            _sell_with_reason(
                context, code, pos, price,
                '追踪止盈 峰%+.2f%% 吐%.2f%% 现%+.2f%%' % (
                    peak_profit * 100, profit_drop * 100, current_profit * 100),
                current_data)
            return
        else:
            # [勇牜牜學量杹] 周期性追踪状态日志（节流）
            if now in ('10:00', '13:30', '14:50'):
                log.info(
                    "[勇敢犇學量杹][追踪状态] %s 现%+.2f%% 峰%+.2f%% 吐%.2f%%(阈%.2f%%) 峰@%s" % (
                        code, current_profit * 100, peak_profit * 100,
                        profit_drop * 100, threshold * 100, meta.get('peak_time', '')))

    if not trailing_on and days_held >= g.hold_days:
        if now >= g.sell_window_start:
            _sell_with_reason(context, code, pos, price,
                              '兜底%d天%+.2f%%' % (days_held, current_profit * 100),
                              current_data)
            return
    if trailing_on and days_held >= max_hold:
        if now >= g.sell_window_start:
            _sell_with_reason(context, code, pos, price,
                              '追踪超时%d天%s%+.2f%%' % (
                                  days_held, mode_strength, current_profit * 100),
                              current_data)
            return

    low_limit = d.low_limit
    if low_limit and low_limit > 0:
        dist_to_low = (price - low_limit) / price if price > 0 else 0
        if dist_to_low <= 1e-6:
            if not meta.get('_blocked_logged'):
                log.info("[勇敢牜牛学量杹][卖出受阻] %s 跌停无法卖出" % code)
                meta['_blocked_logged'] = True
                g.pos_meta[code] = meta
            return
        elif dist_to_low <= g.near_low_limit_threshold:
            _sell_with_reason(context, code, pos, price,
                              '接近跌停%+.2f%%' % (current_profit * 100),
                              current_data, custom_price=low_limit)
            return


def _try_sell_bottom(context, code, pos, meta, d, price,
                     entry_price, current_profit, days_held, now, current_data):
    mode_strength = meta.get('mode_strength', 'weak')
    hold_days = g.bottom_hold_days_strong if mode_strength == 'strong' else g.bottom_hold_days_weak

    if current_profit <= g.bottom_hard_stop:
        low_limit = d.low_limit
        if low_limit and low_limit > 0 and price <= low_limit * 1.02:
            _sell_with_reason(context, code, pos, price,
                              '抄底硬止损-跌停%+.2f%%' % (current_profit * 100),
                              current_data, custom_price=low_limit)
        else:
            _sell_with_reason(context, code, pos, price,
                              '抄底硬止损%+.2f%%' % (current_profit * 100),
                              current_data)
        return

    if days_held >= hold_days:
        if now >= g.sell_window_start:
            _sell_with_reason(context, code, pos, price,
                              '抄底到期%d天%s%+.2f%%' % (
                                  days_held, mode_strength, current_profit * 100),
                              current_data)
            return
        return

    low_limit = d.low_limit
    if low_limit and low_limit > 0:
        dist_to_low = (price - low_limit) / price if price > 0 else 0
        if dist_to_low <= 1e-6:
            if not meta.get('_blocked_logged'):
                log.info("[恿敢牪學量货][卖出受阻] %s 跌停" % code)
                meta['_blocked_logged'] = True
                g.pos_meta[code] = meta
            return


def _sell_with_reason(context, code, pos, price, reason, current_data, custom_price=None):
    d = current_data[code]
    low_limit = d.low_limit

    if custom_price is not None and custom_price > 0:
        order_price = custom_price
    elif low_limit and low_limit > 0:
        order_price = max(low_limit, round(price * 0.99, 2))
    else:
        order_price = round(price * 0.99, 2)

    meta = g.pos_meta.get(code, {})
    entry_price = meta.get('entry_price', pos.avg_cost)

    amt = int(pos.total_amount)

    try:
        order_target_value(code, 0, style=LimitOrderStyle(order_price))
    except Exception as e:
        log.info("[勇敢犇牛學量化][卖出失败] %s %s" % (code, e))
        return

    g.selling[code] = {
        'last_try': context.current_dt,
        'exit_price': price,
        'entry_price': entry_price,
        'amount': amt,
        'entry_date': meta.get('entry_date', ''),
        'channel': meta.get('channel', ''),
        'mode': meta.get('mode', ''),
        'mode_priority': int(meta.get('mode_priority', 0)),
        'mode_strength': meta.get('mode_strength', 'weak'),
        'reason': reason,
    }
    log.info(
        "[勇敢牛牛壆量杹][卖出] %s 数量=%d 参考价=%.2f 成本=%.3f 委托=%.2f "
        "浮盈%+.2f%% 通道=%s 模式=%s/%d/%s 原因=%s" % (
            code, amt, price, entry_price, order_price,
            (price - entry_price) / entry_price * 100 if entry_price > 0 else 0,
            meta.get('channel', ''), meta.get('mode', ''),
            int(meta.get('mode_priority', 0)), meta.get('mode_strength', 'weak'),
            reason))


def record_trade(context, code, rec):
    entry_price = rec['entry_price']
    amount = rec['amount']
    actual_exit_price = rec['exit_price']
    try:
        all_trades = get_trades()
        code_sells = [t for t in all_trades
                      if t.security == code and t.amount < 0]
        if code_sells:
            total_sell_amt = sum(abs(t.amount) for t in code_sells)
            if total_sell_amt > 0:
                actual_exit_price = sum(
                    abs(t.amount) * t.price for t in code_sells) / total_sell_amt
    except Exception:
        pass

    profit = (actual_exit_price - entry_price) / entry_price if entry_price > 0 else 0
    pnl = (actual_exit_price - entry_price) * amount

    log.info(
        "[勇赳牪学量货][完成] %s %+.2f%% pnl=%.0f 数量=%d 本%.3f 卖%.3f "
        "通道=%s 模式=%s/%d/%s 原因=%s" % (
            code, profit * 100, pnl, amount, entry_price, actual_exit_price,
            rec.get('channel', ''), rec.get('mode', ''),
            int(rec.get('mode_priority', 0)), rec.get('mode_strength', 'weak'),
            rec.get('reason', '')))

    g.trades.append({
        'code': code,
        'entry_date': rec['entry_date'],
        'exit_date': context.current_dt.strftime('%Y-%m-%d'),
        'entry_price': entry_price,
        'exit_price': actual_exit_price,
        'profit_pct': profit,
        'pnl': pnl,
        'channel': rec.get('channel', ''),
        'mode': rec.get('mode', ''),
        'mode_priority': rec.get('mode_priority', 0),
        'mode_strength': rec.get('mode_strength', 'weak'),
        'reason': rec.get('reason', ''),
    })
    g.recent_exits[code] = context.current_dt.date()

    if code in g.pos_meta:
        del g.pos_meta[code]


# ==================== [勇敢牛牛学量化] 下单 ====================

def _calc_target_weight(context, code):
    held_set = set()
    for c, p in context.portfolio.positions.items():
        if p.total_amount <= 0:
            continue
        meta = g.pos_meta.get(c, {})
        if meta.get('force_exit'):
            continue
        if meta.get('mode') != g.market_mode:
            continue
        held_set.add(c)
    pending_codes = set(i['code'] for i in g.pending.values())
    current_held = len(held_set | pending_codes)
    is_new = (code not in context.portfolio.positions) and (code not in pending_codes)
    N = (current_held + 1) if is_new else max(current_held, 1)

    if g.market_mode == 'bottom':
        target = g.total_position_max_weight / g.bottom_max_holdings
    else:
        target = 1.0 / N
        target = min(target, g.single_stock_max_weight)
        target = min(target, g.total_position_max_weight)
    return target, N


def _place_order(context, code, order_price, trigger_price, hl, channel, now,
                 override_weight=None):
    total_asset = context.portfolio.total_value
    cash = context.portfolio.available_cash

    if override_weight is not None:
        target_weight = override_weight
        N = 1
    else:
        target_weight, N = _calc_target_weight(context, code)
    target_amount = total_asset * target_weight

    used_value = 0.0
    for c, p in context.portfolio.positions.items():
        if p.total_amount <= 0:
            continue
        if g.pos_meta.get(c, {}).get('force_exit'):
            continue
        used_value += p.value
    room_value = total_asset * g.total_position_max_weight - used_value

    buy_amount = min(target_amount, room_value, cash * g.cash_buffer)
    if buy_amount < g.min_order_amount:
        log.info(
            "[勇敢牛牛Xue量化][下单跳过] %s 目标权重%.2f%% 目标额%.0f 可用额度%.0f "
            "现金*缓冲%.0f 下单额%.0f < 最小%.0f" % (
                code, target_weight * 100, target_amount, room_value,
                cash * g.cash_buffer, buy_amount, g.min_order_amount))
        return False

    shares = int(buy_amount / order_price / 100) * 100
    affordable = int(max(cash * g.cash_buffer - 5, 0)
                     / (order_price * (1 + g.commission_rate)) / 100) * 100
    shares = min(shares, affordable)
    if shares <= 0:
        log.info("[勇敢牛牛NiuNiu学量化][下单跳过] %s 可买股数为0 (现金%.0f 价格%.2f)" % (
            code, cash, order_price))
        return False

    if order_price <= 0 or order_price > hl:
        order_price = hl
    if order_price < trigger_price:
        order_price = trigger_price

    try:
        o = order(code, shares, style=LimitOrderStyle(order_price))
    except Exception as e:
        log.info("[勇敢牛牛壆量杹][下单失败] %s @%.2f %s" % (code, order_price, e))
        return False
    if o is None:
        log.info("[恿敢牪學量货][下单被拒] %s @%.2f" % (code, order_price))
        return False

    g.pending[o.order_id] = {
        'code': code, 'price': order_price, 'amount': shares,
        'dt': context.current_dt, 'time': now, 'channel': channel,
    }
    log.info(
        "[勇赳牛牛学量化][下单] %s 通道=%s 权重=%.2f%%(N=%d) 股数=%d 委托价=%.2f "
        "触发价=%.2f 涨停=%.2f 目标额=%.0f 可用额度=%.0f 现金=%.0f 时间=%s oid=%s" % (
            code, channel, target_weight * 100, N, shares, order_price,
            trigger_price, hl, target_amount, room_value, cash, now, o.order_id))
    return True


# ==================== [勇敢牛牛学量化] 主买通道 ====================

def check_mb_channel(code):
    if not g.use_mb_channel:
        return None
    prev_mb = g.mb_prev.get(code)
    cur_mb = g.mb_cur.get(code)
    if prev_mb is None or cur_mb is None:
        return None
    if g.mb_cnt.get(code, 0) < g.mb_min_minutes:
        return None
    if cur_mb <= prev_mb:
        return None
    pred_next = cur_mb + (cur_mb - prev_mb)
    if pred_next <= cur_mb * (1 + g.mb_accel_min):
        return None
    prev_day_mb = g.prev_day_mb.get(code, 0.0)
    today_mb = g.mb_sum.get(code, 0.0)
    pred_next_sum = today_mb + pred_next
    if g.mb_require_above_prev_day:
        if prev_day_mb <= 0 or pred_next_sum < prev_day_mb * g.mb_min_ratio:
            return None
    prev_day_vol = g.prev_day_volume.get(code, 0.0)
    today_vol = g.today_volume_map.get(code, 0.0)
    if g.require_volume_expand:
        if prev_day_vol <= 0 or today_vol <= prev_day_vol * g.volume_expand_factor:
            return None
    return {
        'mb_prev': prev_mb, 'mb_cur': cur_mb, 'pred_next': pred_next,
        'mb_sum': today_mb, 'pred_next_sum': pred_next_sum,
        'prev_day_mb': prev_day_mb,
        'vol_sum': today_vol, 'prev_day_vol': prev_day_vol,
        'mb_ratio': pred_next_sum / prev_day_mb if prev_day_mb > 0 else 0.0,
        'vol_ratio': today_vol / prev_day_vol if prev_day_vol > 0 else 0.0,
    }


def try_buy_mb(context, now):
    if g.market_mode != 'top' or g.top_paused:
        return
    if not g.use_mb_channel:
        return
    if not g.candidate_pool:
        return

    total_asset = context.portfolio.total_value
    used_value = 0.0
    for c, p in context.portfolio.positions.items():
        if p.total_amount <= 0:
            continue
        if g.pos_meta.get(c, {}).get('force_exit'):
            continue
        used_value += p.value
    room_value = total_asset * g.total_position_max_weight - used_value
    if room_value < g.min_order_amount:
        return

    mb_held = count_channel_held(context, 'MB')
    pending_mb = sum(1 for i in g.pending.values() if i.get('channel') == 'MB')
    slots = g.mb_max_holdings - mb_held - pending_mb
    if slots <= 0:
        return
    global_slots = g.max_pending_orders - len(g.pending)
    slots = min(slots, global_slots)
    if slots <= 0:
        return

    current_data = get_current_data()
    all_held_set = set(c for c, p in context.portfolio.positions.items()
                       if p.total_amount > 0)
    pending_codes = set(i['code'] for i in g.pending.values())
    today_date = context.current_dt.date()
    cooldown_codes = set()
    for c, d in g.recent_exits.items():
        if (today_date - d).days <= g.t1_cooldown_days:
            cooldown_codes.add(c)
    skip_set = all_held_set | pending_codes | cooldown_codes

    hits = []
    n_cand = 0
    for c in g.candidate_pool:
        code = c['code']
        if code in skip_set:
            continue
        n_cand += 1
        if g.mb_cnt.get(code, 0) < g.mb_min_minutes:
            continue
        mb_info = check_mb_channel(code)
        if mb_info is None:
            continue
        pre_close = g.pre_close_map.get(code, 0)
        hl_manual = g.limit_price_map.get(code, 0)
        if pre_close <= 0 or hl_manual <= 0:
            continue
        try:
            d = current_data[code]
        except Exception:
            continue
        if d.paused:
            continue
        try:
            lp = d.last_price
            hl = d.high_limit
        except Exception:
            continue
        if not hl or hl <= 0:
            hl = hl_manual
        if lp <= 0 or is_sealed(lp, hl):
            continue
        gain = lp / pre_close - 1
        if gain < g.mb_min_gain:
            continue
        order_price = round(min(lp * (1 + g.mb_price_buffer), hl), 2)
        hits.append({
            'code': code, 'score': c['score'], 'channel': 'MB',
            'price': lp, 'hl': hl, 'order_price': order_price,
            'gap': (hl - lp) / pre_close, 'mb': mb_info,
        })

    log.info("[勇敢牜牛学量化][主买扫描] 有效候选=%d 命中=%d slots=%d 现金额度=%.0f" % (
        n_cand, len(hits), slots, room_value))

    if not hits:
        return
    hits.sort(key=lambda x: -x['score'])
    for h in hits:
        if slots <= 0:
            break
        ok = _place_order(context, h['code'], h['order_price'],
                          h['price'], h['hl'], 'MB', now)
        if not ok:
            continue
        slots -= 1
        mb = h['mb']
        log.info(
            "[勇敢犇牛學量化][主买] %s 现价%.2f 委托%.2f 涨速g=%.3f mb:cur=%.2f pred=%.2f "
            "sum=%.2f vs昨=%.2f ratio=%.2f vol_ratio=%.2f 时间=%s" % (
                h['code'], h['price'], h['order_price'], h['gap'],
                mb['mb_cur'], mb['pred_next'], mb['pred_next_sum'],
                mb['prev_day_mb'], mb['mb_ratio'], mb['vol_ratio'], now))


# ==================== [勇牜牜学量化] 抢板通道 ====================

def try_buy_seal(context, now):
    if g.market_mode != 'top' or g.top_paused:
        return
    if not g.use_pre_seal_channel or now > g.seal_cutoff_time:
        return
    if not g.candidate_pool:
        return

    total_asset = context.portfolio.total_value
    used_value = 0.0
    for c, p in context.portfolio.positions.items():
        if p.total_amount <= 0:
            continue
        if g.pos_meta.get(c, {}).get('force_exit'):
            continue
        used_value += p.value
    room_value = total_asset * g.total_position_max_weight - used_value
    if room_value < g.min_order_amount:
        return

    seal_held = count_channel_held(context, 'SEAL')
    pending_seal = sum(1 for i in g.pending.values() if i.get('channel') == 'SEAL')
    slots = g.seal_max_holdings - seal_held - pending_seal
    if slots <= 0:
        return
    global_slots = g.max_pending_orders - len(g.pending)
    slots = min(slots, global_slots)
    if slots <= 0:
        return

    current_data = get_current_data()
    all_held_set = set(c for c, p in context.portfolio.positions.items()
                       if p.total_amount > 0)
    pending_codes = set(i['code'] for i in g.pending.values())
    today_date = context.current_dt.date()
    cooldown_codes = set()
    for c, d in g.recent_exits.items():
        if (today_date - d).days <= g.t1_cooldown_days:
            cooldown_codes.add(c)
    skip_set = all_held_set | pending_codes | cooldown_codes

    hits = []
    n_cand = 0
    for c in g.candidate_pool:
        code = c['code']
        if code in skip_set:
            continue
        n_cand += 1
        pre_close = g.pre_close_map.get(code, 0)
        hl_manual = g.limit_price_map.get(code, 0)
        if pre_close <= 0 or hl_manual <= 0:
            continue
        try:
            d = current_data[code]
        except Exception:
            continue
        if d.paused:
            continue
        try:
            lp = d.last_price
            hl = d.high_limit
        except Exception:
            continue
        if not hl or hl <= 0:
            hl = hl_manual
        if lp <= 0 or is_sealed(lp, hl):
            continue
        gap = (hl - lp) / pre_close
        if gap > g.pre_seal_gap:
            continue
        day_open = g.today_open_map.get(code)
        if day_open is None or is_sealed(day_open, hl):
            continue
        if g.require_above_open and lp <= day_open:
            continue
        if g.require_above_vwap:
            vwap = get_vwap(code)
            if vwap > 0 and lp < vwap * (1 - g.vwap_tolerance):
                continue
        if g.require_volume_confirm:
            cap = g.circ_cap_map.get(code, 0)
            if cap > 0 and g.today_money_map.get(code, 0.0) / (cap * 1e8) < g.min_intraday_turnover:
                continue
        hits.append({
            'code': code, 'score': c['score'], 'channel': 'SEAL',
            'price': lp, 'hl': hl, 'order_price': hl, 'gap': gap,
        })

    log.info("[恿敢牪學量货][抢板扫描] 有效候选=%d 命中=%d slots=%d 时间=%s" % (
        n_cand, len(hits), slots, now))

    if not hits:
        return
    hits.sort(key=lambda x: -x['score'])
    for h in hits:
        if slots <= 0:
            break
        ok = _place_order(context, h['code'], h['order_price'],
                          h['price'], h['hl'], 'SEAL', now)
        if not ok:
            continue
        slots -= 1
        log.info(
            "[勇敢牛牛xue量化][抢板] %s 现价%.2f 涨停%.2f gap=%.2f%% score=%.3f 时间=%s" % (
                h['code'], h['price'], h['hl'], h['gap'] * 100, h['score'], now))


# ==================== [勇敢犇學量杹] 抄底通道 ====================

def try_buy_bottom(context, now):
    if g.market_mode != 'bottom' or g.bottom_paused:
        return
    if not g.candidate_pool:
        return
    if now > '09:35':
        return

    active_bottom = _count_active_bottom(context)
    if active_bottom > 0 and not _has_bottom_entry_today(context):
        return

    bottom_held = count_channel_held(context, 'BOTTOM')
    pending_bottom = sum(1 for i in g.pending.values() if i.get('channel') == 'BOTTOM')
    slots = min(g.bottom_max_holdings - bottom_held - pending_bottom,
                g.max_pending_orders - len(g.pending))
    if slots <= 0:
        return

    current_data = get_current_data()
    all_held_set = set(c for c, p in context.portfolio.positions.items()
                       if p.total_amount > 0)
    pending_codes = set(i['code'] for i in g.pending.values())
    skip_set = all_held_set | pending_codes

    hits = []
    n_cand = 0
    for c in g.candidate_pool:
        code = c['code']
        if code in skip_set:
            continue
        n_cand += 1
        try:
            d = current_data[code]
        except Exception:
            continue
        if d.paused:
            continue
        try:
            lp = d.last_price
            hl = d.high_limit
            ll = d.low_limit
        except Exception:
            continue
        if lp <= 0:
            continue
        if is_sealed(lp, hl):
            continue
        if ll and ll > 0 and lp <= ll * 1.001:
            continue
        hits.append({
            'code': code, 'score': c['score'],
            'price': lp, 'hl': hl,
            'order_price': min(lp * 1.005, hl),
        })

    log.info("[勇敢牛牛壆量化][抄底扫描] 有效候选=%d 命中=%d slots=%d 强度=%s 时间=%s" % (
        n_cand, len(hits), slots, g.market_strength, now))

    if not hits:
        return
    hits.sort(key=lambda x: -x['score'])

    n_candidates = min(len(hits), g.bottom_max_holdings)
    per_weight = g.total_position_max_weight / max(n_candidates, 1)
    log.info("[勇牜牛学量杹][抄底] hits=%d 计划=%d 单股权重=%.1f%% 强度=%s" % (
        len(hits), n_candidates, per_weight * 100, g.market_strength))

    for h in hits:
        if slots <= 0:
            break
        ok = _place_order(context, h['code'], h['order_price'],
                          h['price'], h['hl'], 'BOTTOM', now,
                          override_weight=per_weight)
        if ok:
            slots -= 1
            log.info("[勇敢牜牛学量化][抄底] %s 现价%.2f 委托%.2f score=%.3f 时间=%s" % (
                h['code'], h['price'], h['order_price'], h['score'], now))


# ==================== [勇敢牛牛學量化] 分钟数据累积 ====================

def accumulate_minute(context):
    if not g.candidate_pool:
        return
    codes = [c['code'] for c in g.candidate_pool]
    for i in range(0, len(codes), 800):
        batch = codes[i:i + 800]
        try:
            m = get_price(batch, end_date=context.current_dt, count=1,
                          frequency='minute',
                          fields=['open', 'close', 'high', 'low', 'money', 'volume'],
                          panel=False, skip_paused=True)
        except Exception:
            g.dbg_min_fail += 1
            continue
        if m is None or m.empty:
            g.dbg_min_fail += 1
            continue
        g.dbg_min_ok += 1
        if 'code' in m.columns:
            for _, row in m.iterrows():
                merge_minute_row(row['code'], row)
        else:
            merge_minute_row(batch[0], m.iloc[-1])


def merge_minute_row(code, row):
    try:
        op = float(row['open'])
        cl = float(row['close'])
        hi = float(row['high'])
        lo = float(row['low'])
        mo = float(row['money'])
        vo = float(row['volume'])
    except Exception:
        return
    if op > 0 and code not in g.today_open_map:
        g.today_open_map[code] = op
    if lo > 0 and lo < g.today_min_low_map.get(code, 1e9):
        g.today_min_low_map[code] = lo
    if mo > 0:
        g.today_money_map[code] = g.today_money_map.get(code, 0.0) + mo
    if vo > 0:
        g.today_volume_map[code] = g.today_volume_map.get(code, 0.0) + vo
    mb = calc_main_buy(hi, lo, op, cl, vo)
    if mb > 0:
        g.mb_prev[code] = g.mb_cur.get(code, 0.0)
        g.mb_cur[code] = mb
        g.mb_sum[code] = g.mb_sum.get(code, 0.0) + mb
        g.mb_cnt[code] = g.mb_cnt.get(code, 0) + 1


def get_vwap(code):
    v = g.today_volume_map.get(code, 0.0)
    m = g.today_money_map.get(code, 0.0)
    return m / v if v > 0 else 0.0


# ==================== [勇赳牛牛学量化] 盘后 ====================

def after_market_close(context):
    current_data = get_current_data()
    today = context.current_dt.strftime('%Y-%m-%d')

    today_bought_codes = [c for c, m in g.pos_meta.items()
                          if m.get('entry_date') == today]
    seal_ok = 0
    for code in today_bought_codes:
        try:
            d = current_data[code]
            if is_sealed(d.last_price, d.high_limit):
                seal_ok += 1
        except Exception:
            continue
    n_bought = len(today_bought_codes)
    seal_rate = (seal_ok / n_bought * 100) if n_bought > 0 else 0.0

    total_asset = context.portfolio.total_value
    held = [c for c, p in context.portfolio.positions.items()
            if p.total_amount > 0]

    top_held = sum(1 for c, m in g.pos_meta.items()
                   if m.get('mode') == 'top' and
                   context.portfolio.positions.get(c, None) and
                   context.portfolio.positions[c].total_amount > 0)
    bottom_held = sum(1 for c, m in g.pos_meta.items()
                      if m.get('mode') == 'bottom' and
                      context.portfolio.positions.get(c, None) and
                      context.portfolio.positions[c].total_amount > 0)

    force_exit_cnt = sum(1 for c, m in g.pos_meta.items()
                         if m.get('force_exit') and
                         context.portfolio.positions.get(c, None) and
                         context.portfolio.positions[c].total_amount > 0)

    mb_cnt = count_channel_held(context, 'MB')
    seal_cnt = count_channel_held(context, 'SEAL')
    bottom_cnt = count_channel_held(context, 'BOTTOM')
    trailing_cnt = sum(1 for m in g.pos_meta.values() if m.get('trailing_on', False))

    log.info(
        "[勇敢牛牛xue量化][日终] 资产=%.0f 持%d(top%d/bot%d MB%d/SEAL%d/BOT%d) "
        "trail%d force%d 模式=%s/%s/%s 候选=%d 分钟累积ok=%d fail=%d "
        "今日成交=%d(MB%d/SEAL%d/BOT%d)" % (
            total_asset, len(held), top_held, bottom_held,
            mb_cnt, seal_cnt, bottom_cnt, trailing_cnt, force_exit_cnt,
            g.market_mode, g.market_detail, g.market_strength,
            len(g.candidate_pool), g.dbg_min_ok, g.dbg_min_fail,
            g.dbg_fills, g.dbg_fills_mb, g.dbg_fills_seal, g.dbg_fills_bottom))
    log.info("[勇敢牜牛學量化][封板] 今日买入%d 收盘封板%d 封板率=%.1f%%" % (
        n_bought, seal_ok, seal_rate))

    # [勇敢犇學量杹] 逐只持仓明细
    for code in held:
        pos = context.portfolio.positions[code]
        meta = g.pos_meta.get(code, {})
        try:
            d = current_data[code]
            lp = d.last_price
        except Exception:
            lp = 0.0
        entry = meta.get('entry_price', pos.avg_cost)
        profit = (lp - entry) / entry if entry > 0 else 0.0
        log.info(
            "[勇敢牛牛學量化][日终持仓] %s 股数=%d 成本=%.3f 收盘=%.2f 浮盈%+.2f%% "
            "通道=%s 模式=%s/%d/%s 入场=%s 追踪=%s 峰=%.2f" % (
                code, int(pos.total_amount), entry, lp, profit * 100,
                meta.get('channel', ''), meta.get('mode', ''),
                int(meta.get('mode_priority', 0)), meta.get('mode_strength', 'weak'),
                meta.get('entry_date', ''), meta.get('trailing_on', False),
                meta.get('peak_price', 0.0)))

    if context.current_dt.weekday() == 4:
        print_statistics(context)


def print_statistics(context):
    if not g.trades:
        log.info("[勇敢牜牛学量杹][统计] 无完成交易")
        return

    n = len(g.trades)
    wins = [t for t in g.trades if t['profit_pct'] > 0]
    losses = [t for t in g.trades if t['profit_pct'] <= 0]
    avg_profit = np.mean([t['profit_pct'] for t in wins]) if wins else 0.0
    avg_loss = np.mean([t['profit_pct'] for t in losses]) if losses else 0.0

    current_asset = context.portfolio.total_value
    real_return = (current_asset - g.initial_capital) / g.initial_capital

    log.info(
        "[勇敢牛牛壆量杹][统计] 交易%d笔 胜率%.2f%% 平均%+.2f%% 平均盈利%+.2f%% "
        "平均亏损%+.2f%% 资产=%.0f 总收益%+.2f%%" % (
            n, len(wins) / n * 100,
            np.mean([t['profit_pct'] for t in g.trades]) * 100,
            avg_profit * 100, avg_loss * 100,
            current_asset, real_return * 100))
    if avg_loss != 0:
        log.info("[勇敢牛牛Xue量化][统计] 盈亏比%.2f" % abs(avg_profit / avg_loss))

    for m, label in [('top', '追涨'), ('bottom', '抄底')]:
        sub = [t for t in g.trades if t.get('mode') == m]
        if not sub:
            continue
        sw = [t for t in sub if t['profit_pct'] > 0]
        log.info("[勇敢牛牛Study量化][统计-%s] %d笔 胜率%.1f%% 均%+.2f%% pnl=%.0f" % (
            label, len(sub), len(sw) / len(sub) * 100,
            np.mean([t['profit_pct'] for t in sub]) * 100,
            sum(t['pnl'] for t in sub)))

    for s, label in [('strong', '强'), ('weak', '弱')]:
        sub = [t for t in g.trades if t.get('mode_strength') == s]
        if not sub:
            continue
        sw = [t for t in sub if t['profit_pct'] > 0]
        log.info("[勇敢牛牛xue量化][统计-%s] %d笔 胜率%.1f%% 均%+.2f%% pnl=%.0f" % (
            label, len(sub), len(sw) / len(sub) * 100,
            np.mean([t['profit_pct'] for t in sub]) * 100,
            sum(t['pnl'] for t in sub)))

    for ch, label in [('MB', '主买'), ('SEAL', '抢板'), ('BOTTOM', '抄底')]:
        sub = [t for t in g.trades if t.get('channel') == ch]
        if not sub:
            continue
        sw = [t for t in sub if t['profit_pct'] > 0]
        log.info("[勇赳牪学量货][统计-%s] %d笔 胜率%.1f%% 均%+.2f%%" % (
            label, len(sub), len(sw) / len(sub) * 100,
            np.mean([t['profit_pct'] for t in sub]) * 100))

    reason_stats = {}
    for t in g.trades:
        r = t.get('reason', '其他')
        for key in ['优先级切换平仓', '抄底硬止损', '硬止损', 'T+1低开',
                    '追踪止盈', '兜底', '追踪超时', '接近跌停', '抄底到期']:
            if key in r:
                r = key
                break
        reason_stats.setdefault(r, []).append(t['profit_pct'])

    for reason, pcts in sorted(reason_stats.items(), key=lambda x: -len(x[1])):
        arr = np.array(pcts)
        log.info("[勇敢犇牛學量化][统计-原因] %-12s %2d笔 胜率%.1f%% 均%+.2f%%" % (
            reason, len(arr), (arr > 0).mean() * 100, arr.mean() * 100))

    log.info("[勇 敢 牛 牛 学 量 化][统计] 总收益%+.2f%% (作者:勇敢犇學量杹)" % (real_return * 100))