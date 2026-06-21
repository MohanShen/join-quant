# Clone from JoinQuant
# postId: d29d708e57d6a60ef0f46c86c20ea3b6
# backtestId: 52c418086c39ed28a43068b211bc3033
# title: 分享我的聚宽灵感挖掘Skill

# 情绪门控_v182 — v181 + 退潮冲击阈值收紧到-4.8%
#
# 发现v227尾盘清(14:50)胜率仅18%，68笔均亏-1.77%，主要亏损源
# 13:00若仍亏≤-2%立刻清，不等午后继续跌
from collections import deque as _dq
WIN_WINDOW = 60

from jqdata import *
import numpy as np
import pandas as pd
from collections import deque

FB_WINDOW = 60
FB_MIN_HIST = 10


def calc_chip_stats(close_arr, high_arr, low_arr, volume_arr,
                    circulating_shares, decay_factor=1.0, bins=50):
    n = len(close_arr)
    if n < 20 or circulating_shares <= 0:
        return 0.0, 0.0
    highs  = np.asarray(high_arr,  dtype=float)
    lows   = np.asarray(low_arr,   dtype=float)
    closes = np.asarray(close_arr, dtype=float)
    vols   = np.asarray(volume_arr,dtype=float)
    price_min = lows.min()  * 0.95
    price_max = highs.max() * 1.05
    if price_max <= price_min:
        return 0.0, 0.0
    prices = np.linspace(price_min, price_max, bins)
    span  = highs - lows
    avg_p = (highs + lows + closes) / 3.0
    valid = (vols > 0) & (span > 0)
    safe_span = np.where(valid, span, 1.0)
    mask  = (prices[None, :] >= lows[:, None]) & (prices[None, :] <= highs[:, None])
    raw_w = np.maximum(1.0 - np.abs(prices[None, :] - avg_p[:, None]) / safe_span[:, None], 0.0)
    raw_w = np.where(mask, raw_w, 0.0)
    ws    = raw_w.sum(axis=1, keepdims=True)
    new_dist = np.where(ws > 0, raw_w / np.where(ws > 0, ws, 1.0), 0.0)
    t    = np.where(valid, np.minimum(vols / circulating_shares * decay_factor, 1.0), 0.0)
    keep = 1.0 - t
    suffix_keep = np.empty(n)
    suffix_keep[-1] = 1.0
    if n > 1:
        suffix_keep[:-1] = np.cumprod(keep[:0:-1])[::-1]
    weights = t * suffix_keep
    chips0 = np.ones(bins) / bins
    chips  = chips0 * keep.prod() + (new_dist * weights[:, None]).sum(axis=0)
    total = chips.sum()
    if total <= 0:
        return 0.0, 0.0
    chips /= total
    winner_rate = float(chips[prices <= closes[-1]].sum())
    return 0.0, winner_rate


def initialize(context):
    set_option('avoid_future_data', True)
    set_option('use_real_price', True)
    set_benchmark('000300.XSHG')
    set_slippage(FixedSlippage(0.01))
    set_order_cost(OrderCost(
        close_tax=0.001, open_commission=0.0003,
        close_commission=0.0003, min_commission=5
    ), type='stock')

    # v227 参数
    g.ipo_days = 250
    g.idx_code = '000852.XSHG'
    g.v227_stop = -0.05
    g.rzq_stop = -0.03    # v6: -3%（v5是-5%，收紧止损）

    # v227 状态
    g.yjj_candidates = []
    g.bear_candidates = []
    g.yjj_yclose = {}
    g.market_mode = 'bear'
    g.bull_sticky = 0  # v29: bull惯性计数器
    g.prev_first_boards = []
    g.first_board_perf = 0.0
    g.board_heights = []
    g.stoploss_cooldown = 0
    g.leader_holds = {}
    g.leader_candidates_for_tag = []

    # rzq 状态
    g.rzq_candidates = []
    g.rzq_yclose = {}
    g.dieting = []
    g.rzq_cooldown = 0     # v5: rzq硬止损后冷却
    g.rzq_highs = {}       # v30: 盈利保护

    # v104(B): zb（昨日炸板）并列第三腿状态
    g.zb_candidates = []
    g.zb_yclose = {}
    g.enable_zb = False
    g.zb_slots = 0

    # 路由状态
    g.enable_v227 = True
    g.enable_rzq = True
    g.v227_slots = 2
    g.rzq_slots = 2
    g.total_slots = 4
    g.owner = {}
    g.buy_mode = {}  # v88: 记录每只持仓买入时的 market_mode

    # v91: bull 连亏冷却 + 非bull赢也消解
    g.bull_consec_loss = 0
    g.bull_cooldown = 0  # 剩余冷却天数，>0 时禁 bull 新仓
    g.non_bull_consec_wins = 0  # v91: 非bull模式连赢计数（用于消解bull连亏）

    # v97(E): bull 连亏触发即强清存量 flag
    g.bull_force_clear = False

    # v178: 只在策略状态健康时启用 v169 的低价软排序弹性
    g.low_price_factor_enabled = True
    g.low_price_ref = 20.0
    g.low_price_weight = 0.15
    g.low_price_min_win_rate = 0.45

    # v181: 退潮态单日大亏后，只短暂停掉 v227一进二；不影响天蝎座/rzq/zb
    g.v227_shock_cooldown_enabled = True
    g.v227_shock_loss_threshold = -0.048
    g.v227_shock_cooldown_days = 1
    g.v227_shock_cooldown = 0
    g.prev_portfolio_value = None

    # 胜率追踪
    g.recent_trades = deque(maxlen=WIN_WINDOW)  # 1=win, 0=loss

    # FB_pct
    g.fb_pct = 0.5
    g.fb_perf_history = deque(maxlen=FB_WINDOW)

    run_daily(prepare_all, '9:05')
    run_daily(buy_v227_一进二, '9:26')
    run_daily(buy_rzq, '9:27')
    run_daily(buy_zb, '9:28')
    run_daily(buy_v227_天蝎座, '9:30')
    run_daily(sell_v227_morning, '11:25')
    run_daily(sell_rzq_slots, '11:28')
    run_daily(sell_zb_slots, '11:30')
    run_daily(check_stop_all, 'every_bar')
    run_daily(sell_v227_midday, '13:01')
    run_daily(sell_rzq_slots, '14:47')
    run_daily(sell_zb_slots, '14:48')
    run_daily(sell_v227_afternoon, '14:50')
    run_daily(sell_rzq_slots, '14:50')
    run_daily(sell_zb_slots, '14:52')
    run_daily(tag_leaders, '14:55')


# ======================================================================
#  准备阶段：扫描 + 模式判断 + 路由决策
# ======================================================================

def prepare_all(context):
    g.yjj_candidates = []
    g.bear_candidates = []
    g.yjj_yclose = {}
    g.rzq_candidates = []
    g.rzq_yclose = {}
    g.zb_candidates = []
    g.zb_yclose = {}
    g.leader_candidates_for_tag = []

    # 清理已卖出的 owner / leader
    for s in list(g.owner.keys()):
        if s not in context.portfolio.positions or context.portfolio.positions[s].total_amount <= 0:
            del g.owner[s]
    for s in list(g.leader_holds.keys()):
        if s not in context.portfolio.positions or context.portfolio.positions[s].total_amount <= 0:
            del g.leader_holds[s]
    for s in context.portfolio.positions:
        if context.portfolio.positions[s].total_amount > 0 and s not in g.owner:
            g.owner[s] = 'v227'

    if g.stoploss_cooldown > 0:
        g.stoploss_cooldown -= 1
    if g.rzq_cooldown > 0:
        g.rzq_cooldown -= 1
    if g.bull_cooldown > 0:
        g.bull_cooldown -= 1

    g.first_board_perf = calc_fb_perf(context)
    g.fb_perf_history.append(g.first_board_perf)
    g.fb_pct = calc_fb_pct()

    # v227 模式判断 + 扫描（始终运行，FB_pct 依赖 prev_first_boards）
    _v227_mode_and_scan(context)
    _update_v227_shock_cooldown(context)

    # rzq 扫描
    if not _is_pass_month(context):
        _rzq_prepare(context)

    # v104(B): zb 扫描（只在 bull 模式下扫，受 _is_pass_month 限制）
    if not _is_pass_month(context) and g.market_mode == 'bull':
        _zb_prepare(context)

    # === 路由决策：互斥切换，每天只有一个策略开新仓，全部资金给它 ===
    # 卖出逻辑始终双跑（清理各自持仓），只有买入受路由控制
    rzq_month_pass = _is_pass_month(context)
    if g.market_mode == 'bear':
        g.active = 'v227'       # 天蝎座专属
    elif g.market_mode == 'cautious':
        g.active = 'v227'       # rzq cautious均亏-2793
    elif g.fb_pct >= 0.8:
        g.active = 'v227'       # XH档 rzq均亏-1230
    elif not rzq_month_pass:
        g.active = 'rzq+zb'     # v104: bull 默认 rzq 和 zb 并列
    else:
        g.active = 'v227'       # rzq 1/4/12月空仓，回退v227

    g.enable_v227 = (g.active == 'v227')
    g.enable_rzq = (g.active == 'rzq+zb')
    g.enable_zb = (g.active == 'rzq+zb')

    # 仓位：活跃策略独占全部资金；rzq+zb 情况下各分 3 slot
    if g.enable_v227:
        g.v227_slots, g.rzq_slots, g.zb_slots = 2, 0, 0
    else:
        g.v227_slots, g.rzq_slots, g.zb_slots = 0, 3, 3

    # 详细状态日志
    status_parts = [
        '模式=%s' % g.market_mode,
        'FB%+.1f%%' % (g.first_board_perf * 100),
        'pct=%.2f' % g.fb_pct,
        '活跃=%s' % g.active,
        '仓%d+%d+%d' % (g.v227_slots, g.rzq_slots, g.zb_slots),
        'v227候选%d' % len(g.yjj_candidates),
        'rzq候选%d' % len(g.rzq_candidates),
        'zb候选%d' % len(g.zb_candidates),
        'bear候选%d' % len(g.bear_candidates)
    ]
    if g.bull_cooldown > 0:
        status_parts.append('【bull冷却%d天】' % g.bull_cooldown)
    if g.stoploss_cooldown > 0:
        status_parts.append('v227冷却%d天' % g.stoploss_cooldown)
    if g.rzq_cooldown > 0:
        status_parts.append('rzq冷却%d天' % g.rzq_cooldown)
    if _v227_shock_cooldown_active():
        status_parts.append('v227冲击冷却%d天' % g.v227_shock_cooldown)
    if _low_price_tilt_active():
        status_parts.append('健康低价tilt')
    wr = _win_rate()
    if len(g.recent_trades) >= WIN_WINDOW:
        status_parts.append('胜率%.0f%%' % (wr * 100))

    log.info(' | '.join(status_parts))


def calc_fb_perf(context):
    if not g.prev_first_boards:
        return 0.0
    closes = history(2, field='close', security_list=g.prev_first_boards, df=False, fq=None)
    rets = []
    for s in g.prev_first_boards:
        c = closes.get(s)
        if c is not None and len(c) == 2 and c[0] > 0:
            rets.append(c[1] / c[0] - 1)
    return float(np.mean(rets)) if rets else 0.0


def calc_fb_pct():
    buf = list(g.fb_perf_history)
    if len(buf) < FB_MIN_HIST:
        return 0.5
    rank = sum(1 for v in buf if v < g.first_board_perf)
    return rank / len(buf)


def _low_price_health_ok():
    if getattr(g, 'stoploss_cooldown', 0) > 0:
        return False
    if getattr(g, 'bull_cooldown', 0) > 0:
        return False
    if getattr(g, 'bull_force_clear', False):
        return False
    return _win_rate() >= getattr(g, 'low_price_min_win_rate', 0.45)


def _retreat_phase_for_low_price():
    if getattr(g, 'market_mode', 'bear') == 'cautious' and getattr(g, 'fb_pct', 0.5) < 0.4:
        return True
    if getattr(g, 'first_board_perf', 0.0) < 0 and getattr(g, 'fb_pct', 0.5) < 0.5:
        return True
    heights = list(getattr(g, 'board_heights', []))
    if len(heights) >= 10:
        recent = float(np.mean(heights[-3:]))
        prior = float(np.mean(heights[-10:]))
        if recent < prior and recent <= 3:
            return True
    return False


def _v227_shock_retreat_active():
    return _retreat_phase_for_low_price()


def _update_v227_shock_cooldown(context):
    current_value = getattr(getattr(context, 'portfolio', None), 'total_value', None)
    if current_value is None or current_value <= 0:
        return

    prev_value = getattr(g, 'prev_portfolio_value', None)
    if prev_value is None or prev_value <= 0:
        g.prev_portfolio_value = current_value
        return

    daily_ret = current_value / prev_value - 1.0
    if (
        getattr(g, 'v227_shock_cooldown_enabled', False)
        and daily_ret <= getattr(g, 'v227_shock_loss_threshold', -0.04)
        and _v227_shock_retreat_active()
    ):
        g.v227_shock_cooldown = getattr(g, 'v227_shock_cooldown_days', 1)
        _log_info('[v227冲击冷却] 退潮态组合收益%.2f%%，禁v227一进二%d天' % (
            daily_ret * 100,
            g.v227_shock_cooldown,
        ))
    elif getattr(g, 'v227_shock_cooldown', 0) > 0:
        g.v227_shock_cooldown -= 1
    g.prev_portfolio_value = current_value


def _v227_shock_cooldown_active():
    return (
        getattr(g, 'v227_shock_cooldown_enabled', False)
        and getattr(g, 'v227_shock_cooldown', 0) > 0
    )


def _v227_shock_new_buy_blocked(label):
    if not _v227_shock_cooldown_active():
        return False
    _log_info('[%s] 退潮冲击冷却%d天跳过新仓' % (label, g.v227_shock_cooldown))
    return True


def _log_info(msg):
    logger = globals().get('log')
    if logger is not None:
        logger.info(msg)


def _low_price_tilt_active():
    if not getattr(g, 'low_price_factor_enabled', False):
        return False
    if getattr(g, 'market_mode', 'bear') not in ('bear', 'cautious'):
        return False
    if getattr(g, 'fb_pct', 0.5) >= 0.6:
        return False
    if _retreat_phase_for_low_price():
        return False
    return _low_price_health_ok()


def _low_price_multiplier(price):
    if not _low_price_tilt_active() or price <= 0:
        return 1.0
    bonus = max(0.0, min(1.0, getattr(g, 'low_price_ref', 20.0) / float(price) - 1.0))
    return 1.0 + getattr(g, 'low_price_weight', 0.15) * bonus


def _apply_low_price_tilt(candidates, price_map):
    if not candidates or not _low_price_tilt_active():
        return candidates
    ranked = []
    for idx, item in enumerate(candidates):
        stock = item[0] if isinstance(item, tuple) else item
        price = price_map.get(stock, 0)
        base_score = 1.0
        if isinstance(item, tuple) and len(item) > 1:
            try:
                base_score = float(item[1])
            except Exception:
                base_score = 1.0
        ranked.append((item, base_score * _low_price_multiplier(price), idx))
    ranked.sort(key=lambda x: (-x[1], x[2]))
    return [item for item, _, _ in ranked]


def _v227_mode_and_scan(context):
    idx = attribute_history(g.idx_code, 65, '1d', ['close'])['close']

    # 20日回撤保护
    if len(idx) >= 20:
        high_20 = np.max(idx.iloc[-20:])
        now_price = idx.iloc[-1]
        if (now_price - high_20) / high_20 <= -0.12:
            g.market_mode = 'bear'
            _scan_boards_for_prev(context)
            _update_board_heights()
            return

    # 三档模式
    if len(idx) >= 60:
        ma20 = np.mean(idx.iloc[-20:])
        ma60 = np.mean(idx.iloc[-60:])
        price = idx.iloc[-1]
        recent_30 = idx.iloc[-30:] if len(idx) >= 30 else idx.iloc[-10:]
        days_above = sum(1 for p in recent_30 if p > ma60)

        if price <= ma60 and ma20 <= ma60:
            new_mode = 'bear'
        elif price <= ma60 and ma20 > ma60:
            new_mode = 'cautious' if g.first_board_perf > 0 else 'bear'
        elif days_above >= len(recent_30) * 0.66:
            new_mode = 'bull'
        else:
            new_mode = 'cautious' if g.first_board_perf > -0.02 else 'bear'
    else:
        new_mode = 'bear'

    # v29: bull惯性——昨天bull今天掉到cautious，保留bull共2天
    if new_mode == 'bull':
        g.bull_sticky = 2
        g.market_mode = 'bull'
    elif g.bull_sticky > 0 and new_mode == 'cautious':
        g.bull_sticky -= 1
        g.market_mode = 'bull'
    else:
        g.bull_sticky = 0
        g.market_mode = new_mode

    if g.market_mode == 'bear':
        _scan_boards_for_prev(context)
    else:
        _scan_all(context)
    _update_board_heights()


def _update_board_heights():
    h = g._today_max_boards if hasattr(g, '_today_max_boards') else 0
    g.board_heights.append(h)
    if len(g.board_heights) > 20:
        g.board_heights = g.board_heights[-20:]


def _scan_boards_for_prev(context):
    all_stocks = list(get_all_securities(['stock'], date=context.previous_date).index)
    all_stocks = [s for s in all_stocks if not s.startswith('688') and not s.startswith('8')]
    high_limits = history(3, field='high_limit', security_list=all_stocks, df=False, fq=None)
    closes_raw = history(3, field='close', security_list=all_stocks, df=False, fq=None)
    secs = get_all_securities(['stock'], date=context.previous_date)
    fb = []
    bear_pool = []
    max_b = 0
    for s in all_stocks:
        hl = high_limits.get(s)
        cr = closes_raw.get(s)
        if hl is None or cr is None or len(hl) < 3 or len(cr) < 3:
            continue
        if hl[-1] > 0 and abs(cr[-1] - hl[-1]) <= 0.01:
            boards = 1
            if hl[-2] > 0 and abs(cr[-2] - hl[-2]) <= 0.01:
                boards = 2
                if hl[-3] > 0 and abs(cr[-3] - hl[-3]) <= 0.01:
                    boards = 3
            if boards > max_b:
                max_b = boards
            if boards >= 3:
                g.leader_candidates_for_tag.append((s, boards))
            if boards == 1:
                fb.append(s)
                if s.startswith('30'):
                    continue
                if s in secs.index:
                    name = secs.loc[s, 'display_name']
                    if 'ST' in name or 'st' in name:
                        continue
                    if (context.current_dt.date() - secs.loc[s, 'start_date']).days < g.ipo_days:
                        continue
                g.yjj_yclose[s] = cr[-1]
                bear_pool.append(s)
    g.prev_first_boards = fb
    g._today_max_boards = max_b

    if bear_pool and g.market_mode == 'bear':
        closes_60 = history(60, field='close', security_list=bear_pool, df=False, fq='pre')
        for s in bear_pool:
            c60 = closes_60.get(s)
            if c60 is None or len(c60) < 20:
                continue
            h60, l60 = max(c60), min(c60)
            if h60 <= l60:
                continue
            if (c60[-1] - l60) / (h60 - l60) <= 0.5:
                g.bear_candidates.append(s)
        if g.bear_candidates:
            g.bear_candidates = _apply_low_price_tilt(g.bear_candidates, g.yjj_yclose)


def _scan_all(context):
    all_stocks = list(get_all_securities(['stock'], date=context.previous_date).index)
    all_stocks = [s for s in all_stocks if not s.startswith('688') and not s.startswith('8')]
    high_limits = history(3, field='high_limit', security_list=all_stocks, df=False, fq=None)
    closes_raw = history(3, field='close', security_list=all_stocks, df=False, fq=None)
    opens_raw = history(3, field='open', security_list=all_stocks, df=False, fq=None)
    moneys = history(1, field='money', security_list=all_stocks, df=False)
    volumes = history(1, field='volume', security_list=all_stocks, df=False)  # v134: 为 avg_chg 准备
    secs = get_all_securities(['stock'], date=context.previous_date)

    q = query(valuation.code, valuation.circulating_market_cap).filter(
        valuation.circulating_market_cap > 30, valuation.circulating_market_cap < 500)
    val_df = get_fundamentals(q, date=context.previous_date)
    valid_caps = set(val_df['code'].tolist()) if not val_df.empty else set()

    first_boards = []
    max_b = 0
    for s in all_stocks:
        hl = high_limits.get(s)
        cr = closes_raw.get(s)
        if hl is None or cr is None or len(hl) < 3 or len(cr) < 3:
            continue
        if hl[-1] <= 0 or abs(cr[-1] - hl[-1]) > 0.02:
            continue
        boards = 1
        if hl[-2] > 0 and abs(cr[-2] - hl[-2]) <= 0.02:
            boards = 2
            if hl[-3] > 0 and abs(cr[-3] - hl[-3]) <= 0.02:
                boards = 3
        if boards > max_b:
            max_b = boards
        if boards >= 3:
            g.leader_candidates_for_tag.append((s, boards))
        is_first = boards == 1
        if is_first:
            first_boards.append(s)

        if s in secs.index:
            name = secs.loc[s, 'display_name']
            if 'ST' in name or 'st' in name:
                continue
            if (context.current_dt.date() - secs.loc[s, 'start_date']).days < g.ipo_days:
                continue
        if s not in valid_caps:
            continue
        m = moneys.get(s)
        if m is None or len(m) == 0 or m[-1] < 6e8:
            continue
        if g.market_mode == 'bull' and m[-1] > 20e8:
            continue
        # v134: 均价涨幅过滤（摘自 INS002 趋势高点首板接力）
        # 昨日首板: close = prev_close × 1.1 → prev_close = close / 1.1
        # avg_chg = (money/volume) / (close/1.1) − 1 = money/volume/close × 1.1 − 1
        # >7% 表示全天均价涨幅>7%，排除"尾盘拉涨停"的假强势
        if is_first:
            v_arr = volumes.get(s)
            if v_arr is not None and len(v_arr) > 0 and v_arr[-1] > 0 and cr[-1] > 0:
                avg_chg = m[-1] / v_arr[-1] / cr[-1] * 1.1 - 1
                if avg_chg < 0.07:
                    continue
        g.yjj_yclose[s] = cr[-1]
        if is_first:
            g.yjj_candidates.append(s)

    g.prev_first_boards = first_boards
    g._today_max_boards = max_b

    # v122: 爆量防追高过滤（摘自"低位接力"策略）
    # 昨日量 > 5 日均量×8 或 > 5 日最低量×12，且 创 31 日新高 → 排除
    if g.yjj_candidates:
        v31 = history(31, '1d', 'volume', security_list=g.yjj_candidates, df=False, fq='pre')
        h31 = history(31, '1d', 'high', security_list=g.yjj_candidates, df=False, fq='pre')
        c31 = history(31, '1d', 'close', security_list=g.yjj_candidates, df=False, fq='pre')
        kept = []
        removed = 0
        for s in g.yjj_candidates:
            v = v31.get(s)
            h = h31.get(s)
            c = c31.get(s)
            if v is None or h is None or c is None or len(v) < 31:
                kept.append(s)
                continue
            prev_vols = v[-6:-1]
            if len(prev_vols) == 5 and prev_vols.min() > 0:
                avg_vol = float(np.mean(prev_vols))
                min_vol = float(np.min(prev_vols))
                is_blast = (v[-1] > avg_vol * 8) or (v[-1] > min_vol * 12)
                is_new_high = c[-1] > float(np.max(h[-31:-1]))
                if is_blast and is_new_high:
                    removed += 1
                    continue
            kept.append(s)
        if removed > 0:
            log.info('[v122爆量过滤] 排除 %d 只，保留 %d 只' % (removed, len(kept)))
        g.yjj_candidates = kept

    # v130: 封板时点分桶（Researcher + Analyst 双独立提出）
    # T-1 首次触及涨停的时间：<10:00 早封 / 10:00-14:00 午封 / >=14:00 尾封
    # 尾封 = 弱势，次日溢价率显著低 → 硬禁
    if g.yjj_candidates:
        yday = context.previous_date
        start_dt = '%s 09:30:00' % yday.strftime('%Y-%m-%d')
        end_dt = '%s 15:00:00' % yday.strftime('%Y-%m-%d')
        kept_t = []
        removed_tail = 0
        removed_err = 0
        for s in g.yjj_candidates:
            try:
                df_m = get_price(s, start_date=start_dt, end_date=end_dt,
                                 frequency='1m', fields=['close', 'high_limit'],
                                 skip_paused=True, panel=False)
                if df_m is None or len(df_m) == 0:
                    kept_t.append(s)
                    continue
                if 'time' in df_m.columns:
                    df_m = df_m.set_index('time')
                # 首次触板（close 接近 high_limit，允许 0.001 容差）
                hit_mask = df_m['close'] >= (df_m['high_limit'] - 0.001)
                if not hit_mask.any():
                    # 理论上作为首板票应该有触板，无则数据异常保留
                    kept_t.append(s)
                    continue
                first_hit_ts = df_m.index[hit_mask][0]
                t_hit = pd.to_datetime(first_hit_ts).time()
                # 尾封（14:00 之后首次封板）→ 硬禁
                if t_hit.hour >= 14:
                    removed_tail += 1
                    continue
                kept_t.append(s)
            except Exception:
                kept_t.append(s)
                removed_err += 1
        if removed_tail > 0 or removed_err > 0:
            log.info('[v130封板时点] 尾封排除 %d 只，异常保留 %d 只，剩 %d 只' %
                     (removed_tail, removed_err, len(kept_t)))
        g.yjj_candidates = kept_t

    if g.yjj_candidates and g.market_mode == 'bull':
        g.yjj_candidates = _score_with_left_pressure(context, g.yjj_candidates, closes_raw)
    elif g.yjj_candidates:
        g.yjj_candidates = _apply_low_price_tilt(g.yjj_candidates, g.yjj_yclose)


def _score_with_left_pressure(context, candidates, closes_raw):
    closes_100 = history(100, field='close', security_list=candidates, df=False, fq='pre')
    volumes_100 = history(100, field='volume', security_list=candidates, df=False, fq='pre')
    highs_60 = history(60, field='high', security_list=candidates, df=False, fq='pre')
    lows_60 = history(60, field='low', security_list=candidates, df=False, fq='pre')
    q2 = query(valuation.code, valuation.circulating_market_cap).filter(
        valuation.code.in_(candidates))
    cap_df = get_fundamentals(q2, date=context.previous_date)
    circ_caps = dict(zip(cap_df['code'], cap_df['circulating_market_cap'])) if not cap_df.empty else {}
    scored = []
    for s in candidates:
        c = closes_100.get(s)
        v = volumes_100.get(s)
        if c is None or v is None or len(c) < 60:
            continue
        prev_highs = c[:-1]
        prev_vols = v[:-1]
        max_idx = np.argmax(prev_highs)
        is_break = c[-1] >= prev_highs[max_idx] * 0.99
        vol_ok = v[-1] >= prev_vols[max_idx] * 0.9 if prev_vols[max_idx] > 0 else False
        lp_score = 1.0 if (is_break and vol_ok) else 0.5 if is_break else 0.0
        circ_cap = circ_caps.get(s, 0)
        wr = 0.0
        if circ_cap > 0 and c[-1] > 0:
            cs = circ_cap * 1e8 / c[-1]
            n = min(len(c), 60)
            h_arr = highs_60.get(s)
            l_arr = lows_60.get(s)
            if h_arr is not None and l_arr is not None:
                _, wr = calc_chip_stats(c[-n:], h_arr[-n:], l_arr[-n:], v[-n:], cs, bins=30)
        score = lp_score * 0.5 + wr * 0.5
        scored.append((s, score))
    scored.sort(key=lambda x: -x[1])
    return scored


# ======================================================================
#  rzq 准备：龙虎榜 → 主板白名单 → MA10+放量 → 炸板
# ======================================================================

def _rzq_prepare(context):
    try:
        bb = get_billboard_list(stock_list=None, end_date=context.previous_date, count=1)
    except Exception as e:
        log.warning('[rzq] 龙虎榜获取失败 %s' % e)
        return
    if bb is None or bb.empty:
        return
    pool = bb['code'].unique().tolist()

    secs = get_all_securities(['stock'], date=context.previous_date)
    pool2 = []
    for s in pool:
        if not isinstance(s, str) or '.' not in s:
            continue
        if not (s.startswith('60') or s.startswith('00')):
            continue
        if s.startswith('688') or s.startswith('8') or s.startswith('30'):
            continue
        if s in secs.index:
            name = secs.loc[s, 'display_name']
            if 'ST' in name or 'st' in name or '*' in name or '退' in name:
                continue
            if (context.current_dt.date() - secs.loc[s, 'start_date']).days < 375:
                continue
        pool2.append(s)
    if not pool2:
        return

    df_hl = get_price(pool2, end_date=context.previous_date, frequency='daily',
                     fields=['close', 'high', 'high_limit'], count=1,
                     panel=False, fill_paused=False)
    if df_hl is None or df_hl.empty:
        return
    df_hl = df_hl.dropna()
    df_hl = df_hl[(df_hl['high'] == df_hl['high_limit']) & (df_hl['close'] != df_hl['high_limit'])]
    if df_hl.empty:
        return
    pool3 = df_hl['code'].tolist()

    df_t = get_price(pool3, end_date=context.previous_date, frequency='1d',
                    fields=['close', 'low', 'volume'], count=11, panel=False)
    if df_t is None or df_t.empty:
        return
    if 'time' not in df_t.columns:
        df_t = df_t.reset_index()
    grouped = df_t.groupby('code')
    ma10 = grouped['close'].transform(lambda x: x.rolling(10).mean())
    prev_low = grouped['low'].shift(1)
    prev_vol = grouped['volume'].shift(1)
    cond = ((df_t['close'] > prev_low) &
            (df_t['close'] > ma10) &
            (df_t['volume'] > prev_vol) &
            (df_t['volume'] < 10 * prev_vol) &
            (df_t['close'] > 1))
    yday = pd.Timestamp(context.previous_date)
    latest = df_t[df_t['time'] == yday]
    valid_codes = latest[cond.loc[latest.index]]['code'].unique().tolist()
    if not valid_codes:
        return

    g.rzq_yclose = df_hl[df_hl['code'].isin(valid_codes)].set_index('code')['close'].to_dict()
    g.rzq_candidates = valid_codes


# ======================================================================
#  zb 准备：v104(B) 全市场 → 昨日炸板 → 国九条 → MA3放量 → 流通10-2000亿
# ======================================================================

def _zb_prepare(context):
    secs = get_all_securities(['stock'], date=context.previous_date)
    all_codes = []
    for s in secs.index:
        if not (s.startswith('60') or s.startswith('00')):
            continue
        if s.startswith('688') or s.startswith('8') or s.startswith('30'):
            continue
        name = secs.loc[s, 'display_name']
        if 'ST' in name or 'st' in name or '*' in name or '退' in name:
            continue
        if (context.current_dt.date() - secs.loc[s, 'start_date']).days < 375:
            continue
        all_codes.append(s)
    if not all_codes:
        return

    df_hl = get_price(all_codes, end_date=context.previous_date, frequency='daily',
                     fields=['close', 'high', 'high_limit'], count=1,
                     panel=False, fill_paused=False)
    if df_hl is None or df_hl.empty:
        return
    df_hl = df_hl.dropna()
    # 昨日炸板：盘中触板但收盘未封住
    df_hl = df_hl[(df_hl['high'] == df_hl['high_limit']) & (df_hl['close'] < df_hl['high_limit'])]
    if df_hl.empty:
        return
    bomb_codes = df_hl['code'].tolist()

    try:
        q = query(valuation.code).filter(
            valuation.code.in_(bomb_codes),
            income.operating_revenue > 1e8,
        )
        df_gjt = get_fundamentals(q, date=context.previous_date)
        gjt_codes = list(df_gjt['code']) if not df_gjt.empty else []
    except Exception:
        gjt_codes = bomb_codes
    if not gjt_codes:
        return

    df_t = get_price(gjt_codes, end_date=context.previous_date, frequency='1d',
                    fields=['close', 'low', 'volume'], count=3, panel=False)
    if df_t is None or df_t.empty:
        return
    if 'time' not in df_t.columns:
        df_t = df_t.reset_index()
    grouped = df_t.groupby('code')
    ma3 = grouped['close'].transform(lambda x: x.rolling(3).mean())
    prev_low = grouped['low'].shift(1)
    prev_vol = grouped['volume'].shift(1)
    cond = ((df_t['close'] > prev_low) &
            (df_t['close'] > ma3) &
            (df_t['volume'] > prev_vol) &
            (df_t['volume'] < 15 * prev_vol) &
            (df_t['close'] > 1))
    yday = pd.Timestamp(context.previous_date)
    latest = df_t[df_t['time'] == yday]
    valid_codes = latest[cond.loc[latest.index]]['code'].unique().tolist()
    if not valid_codes:
        return

    try:
        q_mv = query(valuation.code, valuation.circulating_market_cap).filter(
            valuation.code.in_(valid_codes),
            valuation.circulating_market_cap > 10,
            valuation.circulating_market_cap < 2000,
        )
        df_mv = get_fundamentals(q_mv, date=context.previous_date)
        valid_codes = list(df_mv['code']) if not df_mv.empty else []
    except Exception:
        pass
    if not valid_codes:
        return

    g.zb_yclose = df_hl[df_hl['code'].isin(valid_codes)].set_index('code')['close'].to_dict()
    g.zb_candidates = valid_codes


# ======================================================================
#  买入
# ======================================================================

def buy_v227_一进二(context):
    if not g.enable_v227:
        log.info('[v227一进二] 未启用(活跃=%s)' % g.active)
        return
    if _v227_shock_new_buy_blocked('v227一进二'):
        return
    # v86: cautious + fb_pct 中段 [0.4, 0.6) 禁开新仓
    if g.market_mode == 'cautious' and 0.4 <= g.fb_pct < 0.6:
        log.info('[v227一进二] cautious+pct毒区跳过')
        return
    # v111(O3): bull + fb_pct < 0.2 禁 v227（29笔 Σpct -99% 毒区）
    if g.market_mode == 'bull' and g.fb_pct < 0.2:
        log.info('[v227一进二] bull+pct<0.2跳过')
        return
    # v89: bull 冷却期禁开新仓（连亏≥3 触发，5 天后自动解除）
    if g.market_mode == 'bull' and g.bull_cooldown > 0:
        log.info('[v227一进二] bull冷却期跳过')
        return
    if g.market_mode == 'bear':
        log.info('[v227一进二] bear模式跳过')
        return
    if g.stoploss_cooldown > 0 and g.market_mode != 'bull':
        log.info('[v227一进二] v227冷却期跳过')
        return
    if not g.yjj_candidates:
        log.info('[v227一进二] 无候选')
        return

    held = _held_count_by('v227', context)
    slots = g.v227_slots - held
    if slots <= 0:
        return

    if g.market_mode == 'bull':
        open_hi = 0.095
    else:
        open_hi = 0.07 if g.first_board_perf > 0 else 0.03

    pos_pct = 1.00 if g.market_mode == 'bull' else 0.75  # v22: bear/cautious 0.65→0.75
    scale = _win_scale()
    if scale == 0.0:
        return
    pos_pct *= scale
    cd = get_current_data()
    bought = 0
    for item in g.yjj_candidates:
        if bought >= slots:
            break
        stock = item[0] if isinstance(item, tuple) else item
        d = cd[stock]
        if d.paused:
            continue
        yc = g.yjj_yclose.get(stock, 0)
        if yc <= 0:
            continue
        if d.day_open >= d.high_limit * 0.999:
            continue
        open_pct = d.day_open / yc - 1
        if open_pct < 0 or open_pct > open_hi:
            continue
        if stock in context.portfolio.positions and context.portfolio.positions[stock].total_amount > 0:
            continue
        cash = context.portfolio.available_cash * pos_pct / max(slots - bought, 1)
        if cash > 5000:
            o = order_value(stock, cash, MarketOrderStyle(d.day_open))
            if not o:
                continue
            g.owner[stock] = 'v227'
            g.buy_mode[stock] = g.market_mode
            log.info('[v227买] %s 开%.1f%% [%s]' % (stock, open_pct * 100, g.market_mode))
            bought += 1


def buy_v227_天蝎座(context):
    if not g.enable_v227:
        return
    if g.market_mode != 'bear' or not g.bear_candidates:
        return
    scale = _win_scale()
    if scale == 0.0:
        return
    held = _held_count_by('v227', context)
    slots = g.v227_slots - held
    if slots <= 0:
        return

    cd = get_current_data()
    bought = 0
    for stock in g.bear_candidates:
        if bought >= slots:
            break
        d = cd[stock]
        if d.paused:
            continue
        yc = g.yjj_yclose.get(stock, 0)
        if yc <= 0:
            continue
        if d.day_open >= d.high_limit * 0.999:
            continue
        open_pct = d.day_open / yc - 1
        if open_pct < -0.04 or open_pct > -0.03:
            continue
        if stock in context.portfolio.positions and context.portfolio.positions[stock].total_amount > 0:
            continue
        cash = context.portfolio.available_cash / max(slots - bought, 1)
        if cash > 5000:
            o = order_value(stock, cash * scale)
            if not o:
                continue
            g.owner[stock] = 'v227'
            g.buy_mode[stock] = g.market_mode
            log.info('[天蝎座] %s 低开%.1f%%' % (stock, open_pct * 100))
            bought += 1


def buy_rzq(context):
    if not g.enable_rzq:
        log.info('[rzq] 未启用(活跃=%s)' % g.active)
        return
    # v86: cautious + fb_pct 中段 [0.4, 0.6) 禁开新仓
    if g.market_mode == 'cautious' and 0.4 <= g.fb_pct < 0.6:
        log.info('[rzq] cautious+pct毒区跳过')
        return
    # v111(O1): bull + fb_pct [0.4, 0.6) 禁 rzq（62笔 Σpct -8.9% 毒区，zb 这档+184%不动）
    if g.market_mode == 'bull' and 0.4 <= g.fb_pct < 0.6:
        log.info('[rzq] bull+pct毒区跳过')
        return
    # v89: bull 冷却期禁开新仓
    if g.market_mode == 'bull' and g.bull_cooldown > 0:
        log.info('[rzq] bull冷却期跳过')
        return
    if _is_pass_month(context):
        log.info('[rzq] 空仓月跳过')
        return
    if g.rzq_cooldown > 0:
        log.info('[rzq] rzq冷却期跳过')
        return
    if not g.rzq_candidates:
        log.info('[rzq] 无候选')
        return
    scale = _win_scale()
    if scale == 0.0:
        return

    cd = get_current_data()
    cands = []
    for s in g.rzq_candidates:
        d = cd[s]
        if d.paused:
            continue
        yc = g.rzq_yclose.get(s, 0)
        if yc <= 0:
            continue
        op = d.day_open
        if op <= 0:
            continue
        ratio = op / yc
        if not (0.96 < ratio < 1.01):
            continue
        if d.last_price >= d.high_limit * 0.999 or d.last_price <= d.low_limit * 1.001:
            continue
        if s in context.portfolio.positions and context.portfolio.positions[s].total_amount > 0:
            continue
        cands.append((s, op, yc))
    if not cands:
        return

    date_str = context.current_dt.strftime('%Y-%m-%d')
    filtered = []
    for s, op, yc in cands:
        try:
            au = get_call_auction(s, start_date=date_str, end_date=date_str)
            if au is None or au.empty:
                continue
            row = au.iloc[0]
            buy_m = sum(row.get('b%d_p' % i, 0) * row.get('b%d_v' % i, 0) for i in range(1, 6))
            sell_m = sum(row.get('a%d_p' % i, 0) * row.get('a%d_v' % i, 0) for i in range(1, 6))
            if sell_m <= 0 or (buy_m - sell_m) / sell_m <= 0:
                continue
        except Exception:
            continue
        filtered.append((s, op, yc, buy_m, sell_m))
    if not filtered:
        return

    codes = [s for s, _, _, _, _ in filtered]
    try:
        df_val = get_valuation(codes, start_date=context.previous_date,
                              end_date=context.previous_date,
                              fields=['turnover_ratio'])
    except Exception:
        df_val = pd.DataFrame()
    tr_map = dict(zip(df_val['code'], df_val['turnover_ratio'])) if not df_val.empty else {}
    # v99(F2): 排序乘 buymoney/sellmoney（集合竞价主买/主卖比）
    scored = [(s, (tr_map.get(s, 0) or 0) * (op / yc) * (buy_m / sell_m if sell_m > 0 else 1.0))
              for s, op, yc, buy_m, sell_m in filtered]
    scored.sort(key=lambda x: -x[1])

    held = _held_count_by('rzq', context)
    slots = max(0, g.rzq_slots - held)
    if slots == 0:
        return
    take = min(slots, len(scored))

    bought = 0
    for s, _ in scored:
        if bought >= take:
            break
        if s in context.portfolio.positions and context.portfolio.positions[s].total_amount > 0:
            continue
        d = cd[s]
        cash = context.portfolio.available_cash / max(take - bought, 1)
        if cash > 5000:
            o = order_value(s, cash * scale, MarketOrderStyle(d.day_open))
            if o:
                g.owner[s] = 'rzq'
                g.buy_mode[s] = g.market_mode
                log.info('[rzq买] %s op/yc=%.3f' % (s, d.day_open / g.rzq_yclose.get(s, 1)))
                bought += 1


def buy_zb(context):
    """v104(B): 炸板第三腿买入 —— 昨日炸板全市场，开盘 0.97-1.075，继承情绪门控"""
    if not g.enable_zb:
        log.info('[zb] 未启用(活跃=%s)' % g.active)
        return
    # 继承 rzq 的情绪门控
    if g.market_mode == 'cautious' and 0.4 <= g.fb_pct < 0.6:
        log.info('[zb] cautious+pct毒区跳过')
        return
    if g.market_mode == 'bull' and g.bull_cooldown > 0:
        log.info('[zb] bull冷却期跳过')
        return
    if _is_pass_month(context):
        log.info('[zb] 空仓月跳过')
        return
    if not g.zb_candidates:
        log.info('[zb] 无候选')
        return
    scale = _win_scale()
    if scale == 0.0:
        return

    cd = get_current_data()
    cands = []
    for s in g.zb_candidates:
        d = cd[s]
        if d.paused:
            continue
        yc = g.zb_yclose.get(s, 0)
        if yc <= 0:
            continue
        op = d.day_open
        if op <= 0:
            continue
        ratio = op / yc
        # 外部炸板策略的开盘区间：0.97-1.075
        if not (0.97 < ratio < 1.075):
            continue
        if d.last_price >= d.high_limit * 0.999 or d.last_price <= d.low_limit * 1.001:
            continue
        if s in context.portfolio.positions and context.portfolio.positions[s].total_amount > 0:
            continue
        cands.append((s, op, yc))
    if not cands:
        return

    date_str = context.current_dt.strftime('%Y-%m-%d')
    filtered = []
    for s, op, yc in cands:
        try:
            au = get_call_auction(s, start_date=date_str, end_date=date_str)
            if au is None or au.empty:
                continue
            row = au.iloc[0]
            buy_m = sum(row.get('b%d_p' % i, 0) * row.get('b%d_v' % i, 0) for i in range(1, 6))
            sell_m = sum(row.get('a%d_p' % i, 0) * row.get('a%d_v' % i, 0) for i in range(1, 6))
            if sell_m <= 0 or (buy_m - sell_m) / sell_m <= 0:
                continue
        except Exception:
            continue
        filtered.append((s, op, yc, buy_m, sell_m))
    if not filtered:
        return

    codes = [s for s, _, _, _, _ in filtered]
    try:
        df_val = get_valuation(codes, start_date=context.previous_date,
                              end_date=context.previous_date,
                              fields=['turnover_ratio'])
    except Exception:
        df_val = pd.DataFrame()
    tr_map = dict(zip(df_val['code'], df_val['turnover_ratio'])) if not df_val.empty else {}
    scored = [(s, (tr_map.get(s, 0) or 0) * (op / yc) * (buy_m / sell_m if sell_m > 0 else 1.0))
              for s, op, yc, buy_m, sell_m in filtered]
    scored.sort(key=lambda x: -x[1])

    held = _held_count_by('zb', context)
    slots = max(0, g.zb_slots - held)
    if slots == 0:
        return
    take = min(slots, len(scored))

    bought = 0
    for s, _ in scored:
        if bought >= take:
            break
        if s in context.portfolio.positions and context.portfolio.positions[s].total_amount > 0:
            continue
        d = cd[s]
        cash = context.portfolio.available_cash / max(take - bought, 1)
        if cash > 5000:
            o = order_value(s, cash * scale, MarketOrderStyle(d.day_open))
            if o:
                g.owner[s] = 'zb'
                g.buy_mode[s] = g.market_mode
                log.info('[zb买] %s op/yc=%.3f' % (s, d.day_open / g.zb_yclose.get(s, 1)))
                bought += 1


# ======================================================================
#  卖出 — v227 和 rzq 各管各的持仓
# ======================================================================

def sell_v227_morning(context):
    """11:25 v227：盈利止盈，封板跳过，龙头保护"""
    cd = get_current_data()
    for s in list(context.portfolio.positions):
        if g.owner.get(s) != 'v227':
            continue
        pos = context.portfolio.positions[s]
        if pos.closeable_amount <= 0:
            continue
        d = cd[s]
        if d.last_price >= d.high_limit * 0.999:
            continue
        if s in g.leader_holds:
            continue
        if pos.avg_cost > 0 and d.last_price > pos.avg_cost:
            order_target(s, 0)
            _record_trade(pos.avg_cost, d.last_price, stock=s)
            g.owner.pop(s, None)
            log.info('[v227止盈] %s +%.1f%%' % (s, (d.last_price / pos.avg_cost - 1) * 100))


def sell_rzq_slots(context):
    """11:28/14:47/14:50 rzq：-3%止损 / +1%止盈 / 昨涨停卖"""
    holds = [s for s in context.portfolio.positions if g.owner.get(s) == 'rzq']
    if not holds:
        return
    cd = get_current_data()
    try:
        df_y = get_price(holds, end_date=context.previous_date, frequency='daily',
                       fields=['close', 'high_limit'], count=1, panel=False)
        df_y = df_y.set_index('code')
    except Exception:
        df_y = pd.DataFrame()

    for s in holds:
        pos = context.portfolio.positions[s]
        if pos.closeable_amount <= 0 or pos.avg_cost <= 0:
            continue
        d = cd[s]
        if d.last_price >= d.high_limit * 0.999:
            continue
        if d.last_price <= d.low_limit * 1.001:
            continue
        ret_pct = (d.last_price - pos.avg_cost) / pos.avg_cost * 100
        cond_loss = ret_pct < -3
        cond_gain = ret_pct > 1
        cond_yhl = False
        if s in df_y.index:
            try:
                cond_yhl = (df_y.loc[s, 'close'] == df_y.loc[s, 'high_limit'])
            except Exception:
                pass
        if cond_loss or cond_gain or cond_yhl:
            order_target(s, 0)
            _record_trade(pos.avg_cost, d.last_price, stock=s)
            if s in g.dieting:
                g.dieting.remove(s)
            g.owner.pop(s, None)
            log.info('[rzq卖] %s ret=%.1f%%' % (s, ret_pct))


def sell_zb_slots(context):
    """v104(B) zb 卖出：盈利>0 / 跌破MA5 / 昨涨停卖（外部炸板策略规则）"""
    holds = [s for s in context.portfolio.positions if g.owner.get(s) == 'zb']
    if not holds:
        return
    cd = get_current_data()
    yesterday = context.previous_date
    try:
        ma5 = history(5, unit='1d', field='close', security_list=holds).mean()
    except Exception:
        ma5 = {}
    try:
        df_y = get_price(holds, end_date=yesterday, frequency='daily',
                       fields=['close', 'high_limit'], count=1, panel=False)
        df_y = df_y.set_index('code')
    except Exception:
        df_y = pd.DataFrame()

    for s in holds:
        pos = context.portfolio.positions[s]
        if pos.closeable_amount <= 0 or pos.avg_cost <= 0:
            continue
        d = cd[s]
        if d.last_price >= d.high_limit * 0.999:
            continue  # 涨停不卖
        if d.last_price <= d.low_limit * 1.001:
            continue  # 跌停由 check_stop_all 处理
        ret = (d.last_price - pos.avg_cost) / pos.avg_cost
        ma_val = ma5.get(s, 0) if hasattr(ma5, 'get') else (ma5[s] if s in ma5.index else 0)
        cond_gain = ret > 0
        cond_ma = d.last_price < ma_val if ma_val > 0 else False
        cond_yhl = False
        if s in df_y.index:
            try:
                cond_yhl = (df_y.loc[s, 'close'] == df_y.loc[s, 'high_limit'])
            except Exception:
                pass
        if cond_gain or cond_ma or cond_yhl:
            order_target(s, 0)
            _record_trade(pos.avg_cost, d.last_price, stock=s)
            if s in g.dieting:
                g.dieting.remove(s)
            g.owner.pop(s, None)
            log.info('[zb卖] %s ret=%.1f%%' % (s, ret * 100))


def check_stop_all(context):
    """every_bar: v227 -5%止损 + 跌停等待打开清"""
    cd = get_current_data()

    # v97(E): bull 连亏首次触发 → 清所有 bull 买入的存量（非封板、非龙头）
    if g.bull_force_clear:
        cleared = []
        for s in list(context.portfolio.positions):
            if g.buy_mode.get(s) != 'bull':
                continue
            pos = context.portfolio.positions[s]
            if pos.closeable_amount <= 0 or pos.avg_cost <= 0:
                continue
            d = cd[s]
            if d.last_price >= d.high_limit * 0.999:
                continue  # 封板留
            if s in g.leader_holds:
                continue  # 龙头留
            ret = (d.last_price - pos.avg_cost) / pos.avg_cost
            order_target(s, 0)
            _record_trade(pos.avg_cost, d.last_price, stock=s)
            g.owner.pop(s, None)
            if s in g.dieting:
                g.dieting.remove(s)
            g.rzq_highs.pop(s, None)
            cleared.append('%s %.1f%%' % (s, ret * 100))
        if cleared:
            log.info('[bull强清] %d笔: %s' % (len(cleared), ', '.join(cleared)))
        g.bull_force_clear = False

    for s in list(context.portfolio.positions):
        pos = context.portfolio.positions[s]
        if pos.closeable_amount <= 0 or pos.avg_cost <= 0:
            continue
        d = cd[s]
        owner = g.owner.get(s, 'v227')

        if owner == 'v227':
            ret = (d.last_price - pos.avg_cost) / pos.avg_cost
            if s in g.dieting:
                if d.last_price <= d.low_limit * 1.001:
                    continue
                order_target(s, 0)
                _record_trade(pos.avg_cost, d.last_price, stock=s)
                _clear_v227_sell_state(s)
                _log_v227_loss_exit('v227跌停打开清', s, ret)
                continue
            if d.last_price <= d.low_limit * 1.001:
                g.dieting.append(s)
                log.info('[v227跌停等待] %s %.1f%%' % (s, ret * 100))
                continue
            if ret <= g.v227_stop:
                order_target(s, 0)
                _record_trade(pos.avg_cost, d.last_price, stock=s)
                _clear_v227_sell_state(s)
                _log_v227_loss_exit('v227止损', s, ret)

        elif owner == 'rzq':
            ret = (d.last_price - pos.avg_cost) / pos.avg_cost
            prev_high = g.rzq_highs.get(s, 0.0)
            if ret > prev_high:
                g.rzq_highs[s] = ret
                prev_high = ret
            if prev_high >= 0.05 and ret <= 0.01:
                order_target(s, 0)
                _record_trade(pos.avg_cost, d.last_price, stock=s)
                if s in g.dieting:
                    g.dieting.remove(s)
                g.owner.pop(s, None)
                g.rzq_highs.pop(s, None)
                log.info('[rzq盈利回落] %s high=%.1f%% now=%.1f%%' % (s, prev_high * 100, ret * 100))
                continue
            if ret <= g.rzq_stop:
                order_target(s, 0)
                _record_trade(pos.avg_cost, d.last_price, stock=s)
                if s in g.dieting:
                    g.dieting.remove(s)
                g.owner.pop(s, None)
                g.rzq_highs.pop(s, None)
                g.rzq_cooldown = 1
                log.info('[rzq止损] %s %.1f%% 冷却1天' % (s, ret * 100))
                continue
            # 跌停打开清
            if s not in g.dieting:
                if d.last_price <= d.low_limit * 1.001:
                    g.dieting.append(s)
            else:
                if d.last_price > d.low_limit * 1.001:
                    order_target(s, 0)
                    _record_trade(pos.avg_cost, d.last_price, stock=s)
                    g.dieting.remove(s)
                    g.owner.pop(s, None)
                    g.rzq_highs.pop(s, None)
                    log.info('[rzq跌停打开清] %s' % s)

        elif owner == 'zb':
            # v104(B) zb: 跌停打开清（同 rzq 规则，无独立止损——由 sell_zb_slots 的 MA5 处理）
            if s not in g.dieting:
                if d.last_price <= d.low_limit * 1.001:
                    g.dieting.append(s)
            else:
                if d.last_price > d.low_limit * 1.001:
                    order_target(s, 0)
                    _record_trade(pos.avg_cost, d.last_price, stock=s)
                    g.dieting.remove(s)
                    g.owner.pop(s, None)
                    log.info('[zb跌停打开清] %s' % s)


def sell_v227_midday(context):
    """13:01 v227：若仍亏≤-2%立刻清，避免午后继续跌到尾盘"""
    cd = get_current_data()
    for s in list(context.portfolio.positions):
        if g.owner.get(s) != 'v227':
            continue
        pos = context.portfolio.positions[s]
        if pos.closeable_amount <= 0 or pos.avg_cost <= 0:
            continue
        d = cd[s]
        if d.last_price >= d.high_limit * 0.999:
            continue
        if d.last_price <= d.low_limit * 1.001:
            if s not in g.dieting:
                g.dieting.append(s)
            continue
        if s in g.leader_holds:
            continue
        ret = (d.last_price - pos.avg_cost) / pos.avg_cost
        if ret <= -0.02:
            order_target(s, 0)
            _record_trade(pos.avg_cost, d.last_price, stock=s)
            g.owner.pop(s, None)
            log.info('[v227午撤] %s %.1f%%' % (s, ret * 100))


def sell_v227_afternoon(context):
    """14:50 v227：非封板全清"""
    cd = get_current_data()
    for s in list(context.portfolio.positions):
        if g.owner.get(s) != 'v227':
            continue
        pos = context.portfolio.positions[s]
        if pos.closeable_amount <= 0:
            continue
        d = cd[s]
        if d.last_price >= d.high_limit * 0.999:
            continue
        if d.last_price <= d.low_limit * 1.001:
            if s not in g.dieting:
                g.dieting.append(s)
            continue
        if s in g.leader_holds:
            log.info('[龙头出局] %s 未封板 (%d板)' % (s, g.leader_holds[s]))
            del g.leader_holds[s]
        order_target(s, 0)
        _record_trade(pos.avg_cost, d.last_price, stock=s)
        _clear_v227_sell_state(s)
        if pos.avg_cost > 0:
            log.info('[v227尾盘清] %s %.1f%%' % (s, (d.last_price / pos.avg_cost - 1) * 100))


def tag_leaders(context):
    """14:55 标记封板的≥3板龙头"""
    if not g.leader_candidates_for_tag:
        return
    cd = get_current_data()
    board_map = {}
    for s, boards in g.leader_candidates_for_tag:
        if s not in board_map or boards > board_map[s]:
            board_map[s] = boards
    for stock in list(context.portfolio.positions):
        pos = context.portfolio.positions[stock]
        if pos.total_amount <= 0:
            continue
        if g.owner.get(stock) != 'v227':
            continue
        if stock in board_map:
            d = cd[stock]
            if d.last_price >= d.high_limit * 0.999:
                g.leader_holds[stock] = board_map[stock]
                log.info('[龙头标记] %s %d板' % (stock, board_map[stock]))


# ======================================================================
#  辅助
# ======================================================================

def _held_count_by(tag, context):
    cnt = 0
    for s, o in g.owner.items():
        if o != tag:
            continue
        pos = context.portfolio.positions.get(s)
        if pos is not None and pos.total_amount > 0:
            cnt += 1
    return cnt


def _clear_v227_sell_state(stock):
    g.owner.pop(stock, None)
    if stock in g.leader_holds:
        del g.leader_holds[stock]
    if stock in g.dieting:
        g.dieting.remove(stock)


def _log_v227_loss_exit(label, stock, ret):
    if ret <= -0.10:
        g.stoploss_cooldown = 3
        log.info('[%s] %s %.1f%% 冷却3天' % (label, stock, ret * 100))
    elif ret <= -0.06:
        g.stoploss_cooldown = 2
        log.info('[%s] %s %.1f%% 冷却' % (label, stock, ret * 100))
    else:
        log.info('[%s] %s %.1f%%' % (label, stock, ret * 100))


def _is_pass_month(context):
    # v99(A, F1+F3): 1/4/12 月 15 号后才空仓（前半月允许开仓）+ 春节前 15 天空仓
    date = context.current_dt.date()
    month, day = date.month, date.day
    # F1: 1/4/12 月的 15 号后
    if month in (1, 4, 12) and day >= 15:
        return True
    # F3: 春节前 15 天
    spring_festival_dates = {
        2015: "2015-02-19", 2016: "2016-02-08", 2017: "2017-01-28",
        2018: "2018-02-16", 2019: "2019-02-05", 2020: "2020-01-25",
        2021: "2021-02-12", 2022: "2022-02-01", 2023: "2023-01-22",
        2024: "2024-02-10", 2025: "2025-01-29", 2026: "2026-02-17",
        2027: "2027-02-06", 2028: "2028-01-26", 2029: "2029-02-13",
        2030: "2030-02-03",
    }
    y = date.year
    if y in spring_festival_dates:
        sf = pd.to_datetime(spring_festival_dates[y]).date()
        if (sf - pd.Timedelta(days=15)) <= date < sf:
            return True
    return False


def _win_rate():
    if len(g.recent_trades) < WIN_WINDOW:
        return 0.5
    return sum(g.recent_trades) / len(g.recent_trades)


def _win_scale():
    """胜率<30%暂停(返回0), 30-40%半仓, >40%全仓"""
    wr = _win_rate()
    if len(g.recent_trades) < WIN_WINDOW:
        return 1.0
    if wr < 0.30:
        return 0.0
    if wr < 0.40:
        return 0.5
    return 1.0


def _record_trade(cost, last_price, stock=None):
    if cost > 0:
        g.recent_trades.append(1 if last_price > cost else 0)
    # v89: bull 连亏追踪 + 冷却触发
    if stock and g.buy_mode.get(stock) == 'bull' and cost > 0:
        if last_price > cost:
            g.bull_consec_loss = 0
            g.bull_cooldown = 0
        else:
            prev = g.bull_consec_loss
            g.bull_consec_loss += 1
            if g.bull_consec_loss >= 3:
                g.bull_cooldown = 5
                if prev < 3:  # v97(E): 首次触发 → 强清 bull 存量
                    g.bull_force_clear = True
    # v91: 非bull交易赢了消解bull连亏 (v95/B2: 阈值=1)
    if stock and g.buy_mode.get(stock) in ('cautious', 'bear') and cost > 0:
        if last_price > cost:
            g.non_bull_consec_wins += 1
            if g.non_bull_consec_wins >= 1 and g.bull_consec_loss > 0:
                g.bull_consec_loss = max(0, g.bull_consec_loss - 1)
                g.non_bull_consec_wins = 0
                if g.bull_consec_loss < 3:
                    g.bull_cooldown = 0
        else:
            g.non_bull_consec_wins = 0
    if stock:
        g.buy_mode.pop(stock, None)
