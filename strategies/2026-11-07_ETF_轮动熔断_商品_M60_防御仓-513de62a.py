# Clone from JoinQuant
# postId: 513de62a711ee1c10812cc02994fb12e
# backtestId: f22603791b30bad5c2dadf95303ae8eb
# title: ETF 轮动熔断 + 商品 M60 防御仓

# -*- coding: utf-8 -*-
"""ETF 轮动防御 · 聚宽分钟级 · 对照 G（熔断 10% + 商品 M60 防御仓）

池约 120 只场内 ETF/LOF，用 25 日加权对数线性回归的年化斜率乘 R² 打分，
取分数不低于首选分 85% 的前十名，剔除 60 日相关性高于 0.9 的重复标的，最多持 3 只。
弱势期（4 个宽基指数有 3 个跌破 10 日均线）放开均线、量比、三日暴跌三项过滤；
弱势且首选分低于 1.0 时目标置空，清仓持现金。
13:10 算目标、13:20 卖出非目标持仓，13:25–14:55 每 5 分钟重挂未卖完的持仓，
14:45/14:50/14:53/14:55 按 30%/60%/80%/100% 累计仓位分四批买入，每根分钟 K 线检查止损。
总资产自回测内最高点回撤 10% 触发熔断：清仓并锁仓至少 10 个交易日，
且在熔断期内按 60 日动量在六只商品 ETF 中取最强一只投满防御仓，
解除需锁满 10 个交易日且连续 2 日至少 3 个指数站上 MA10；熔断期止损放宽到 -8%。

回测需选分钟频率，基准 000300.XSHG。
"""

from jqdata import *
import pandas as pd
import numpy as np

LOOKBACK = 25
R2_MIN = 0.4
VOL_MAX = 1.8
CRASH_MIN = 0.97
SCORE_MAX = 5.0
TOP_N = 10
KEEP = 0.85
N_HOLD = 3
COOL_DAYS = 5
CORR_WIN = 60
CORR_MAX = 0.9
CORR_BLOCK = 0.9
LIQ_MIN = 24320000.0
STOP = 0.95
MIN_GAP = 0.01

DD_BREAK = 0.10
DD_MIN_LOCK = 10
DD_CONFIRM = 2
DD_STRONG_MAX = 1

SCORE_MIN_WEAK = 1.0

DEF_ON = True
DEF_FRAC = 1.0
DEF_MOM_N = 60
DEF_MOM_MIN = 0.0
DEF_POOL = ('518880.XSHG', '161226.XSHE', '159985.XSHE', '501018.XSHG',
            '159981.XSHE', '159980.XSHE')
DEF_COMMODITY = ('518880.XSHG', '161226.XSHE', '159985.XSHE', '501018.XSHG',
                 '159981.XSHE', '159980.XSHE')
DEF_INCOME = ()
DEF_HALF = DEF_FRAC
DEF_ENTER_MOM = 0.005
DEF_EXIT_MOM = -0.005
DEF_SWITCH_MOM = 0.010
DEF_STOP = 0.92

BUY_MODE = 'close'

RESELL_ON = True
RESELL_STEP = 5
RESELL_START = '13:25'
RESELL_END = '14:55'

BATCH_PLAN = (('14:45', 0.30), ('14:50', 0.60), ('14:53', 0.80), ('14:55', 1.00))

MIN_HOLD_DAYS = 1

BENCHMARK = '000300.XSHG'
DEFENSIVE = '511880.XSHG'
IDX = ('000300.XSHG', '399101.XSHE', '399006.XSHE', '000510.XSHG')

GLOBAL = ('518880.XSHG', '501018.XSHG', '161226.XSHE', '159985.XSHE', '159980.XSHE',
          '513310.XSHG', '159509.XSHE', '513520.XSHG', '513290.XSHG', '159529.XSHE')
CHINA = ('513090.XSHG', '513120.XSHG', '513180.XSHG', '513330.XSHG', '159892.XSHE', '513190.XSHG',
         '159323.XSHE', '510900.XSHG', '513970.XSHG', '511380.XSHG', '512050.XSHG', '510500.XSHG',
         '510300.XSHG', '512100.XSHG', '159949.XSHE', '588080.XSHG', '159967.XSHE', '588220.XSHG',
         '563300.XSHG', '510760.XSHG', '515880.XSHG', '159981.XSHE', '512880.XSHG', '513350.XSHG',
         '159326.XSHE', '159516.XSHE', '512480.XSHG', '159870.XSHE', '159755.XSHE', '588170.XSHG',
         '159992.XSHE', '159995.XSHE', '159566.XSHE', '159869.XSHE', '512070.XSHG', '515120.XSHG',
         '512010.XSHG', '510880.XSHG', '515980.XSHG', '512660.XSHG', '560860.XSHG', '515030.XSHG',
         '159766.XSHE', '159218.XSHE', '516150.XSHG', '159227.XSHE', '159583.XSHE', '159851.XSHE',
         '561980.XSHG', '562590.XSHG', '512200.XSHG', '159667.XSHE', '516510.XSHG', '159840.XSHE',
         '515400.XSHG', '159256.XSHE', '561330.XSHG', '515170.XSHG', '159638.XSHE', '516520.XSHG',
         '513360.XSHG', '516190.XSHG', '588710.XSHG', '589800.XSHG', '588890.XSHG', '159939.XSHE',
         '159731.XSHE', '512220.XSHG', '588110.XSHG', '588990.XSHG', '515260.XSHG', '159790.XSHE',
         '561100.XSHG', '563320.XSHG', '588040.XSHG', '520500.XSHG', '513060.XSHG', '159735.XSHE',
         '516620.XSHG', '513820.XSHG', '159541.XSHE', '513660.XSHG', '588260.XSHG', '159822.XSHE',
         '159954.XSHE', '159691.XSHE', '512580.XSHG', '159335.XSHE',
         '159761.XSHE', '516670.XSHG', '513990.XSHG', '513050.XSHG', '159814.XSHE', '562030.XSHG',
         '515630.XSHG', '516780.XSHG', '159720.XSHE', '159991.XSHE', '159608.XSHE', '516590.XSHG',
         '159997.XSHE', '516380.XSHG', '516660.XSHG', '517090.XSHG', '516570.XSHG', '159804.XSHE',
         '512720.XSHG', '159546.XSHE', '512770.XSHG', '510410.XSHG')
POOL = GLOBAL + CHINA


def cd(code):
    return code.split('.')[0]


def _now(context):
    try:
        return context.current_dt.strftime('%H:%M')
    except Exception:
        return ''


def _minute_of(t):
    try:
        hh, mm = t.split(':')
        return int(hh) * 60 + int(mm)
    except Exception:
        return -1


def daily(context, codes, count):
    out = {}
    try:
        today = pd.Timestamp(context.current_dt.date())
    except Exception:
        today = None
    for code in codes:
        if not code:
            continue
        df = None
        for fields in (['close', 'volume', 'money'], ['close', 'volume'], ['close']):
            try:
                df = attribute_history(code, count, '1d', fields,
                                       skip_paused=False, fq='pre', df=True)
                break
            except Exception:
                df = None
        if df is None or len(df) == 0:
            continue
        if today is not None:
            try:
                df = df[df.index < today]
            except Exception:
                pass
        if len(df) == 0:
            continue
        try:
            close = np.asarray(df['close'], dtype=float)
        except Exception:
            continue
        if close.size == 0:
            continue
        rec = {'close': close, 'volume': None, 'money': None}
        for k in ('volume', 'money'):
            if k in df.columns:
                try:
                    rec[k] = np.asarray(df[k], dtype=float)
                except Exception:
                    rec[k] = None
        out[code] = rec
    return out


def current_px(context, codes):
    out = {}
    try:
        cdata = get_current_data()
    except Exception:
        cdata = None
    miss = []
    for code in codes:
        unit = None
        if cdata is not None:
            try:
                unit = cdata[code]
            except Exception:
                unit = None
        if unit is None or getattr(unit, 'paused', False):
            continue
        p = 0.0
        try:
            p = float(unit.last_price)
        except Exception:
            p = 0.0
        if np.isfinite(p) and p > 0:
            out[code] = p
        else:
            miss.append(code)
    for code in miss:
        try:
            df = get_price(code, end_date=context.current_dt, count=1,
                           frequency='1m', fields=['close'],
                           skip_paused=False, fq=None)
        except Exception:
            continue
        if df is None or len(df) == 0:
            continue
        p = float(df['close'].iloc[-1])
        if np.isfinite(p) and p > 0:
            out[code] = p
    g.last_px.update(out)
    return out


def momentum(y, w):
    if len(y) < 3 or np.isnan(y).any() or (y <= 0).any():
        return None, None, None
    x = np.arange(len(y), dtype=float)
    try:
        slope, inter = np.polyfit(x, np.log(y), 1, w=np.sqrt(w))
    except Exception:
        return None, None, None
    pred = slope * x + inter
    ly = np.log(y)
    ss_res = np.sum(w * (ly - pred) ** 2)
    ss_tot = np.sum(w * (ly - ly.mean()) ** 2)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return float((np.exp(slope * 250.0) - 1.0) * r2), float(r2), float(slope)


def corr60(a, b):
    if a is None or b is None or len(a) < CORR_WIN + 1 or len(b) < CORR_WIN + 1:
        return None
    a = np.asarray(a[-CORR_WIN - 1:], float)
    b = np.asarray(b[-CORR_WIN - 1:], float)
    if np.isnan(a).any() or np.isnan(b).any():
        return None
    ra = a[1:] / a[:-1] - 1.0
    rb = b[1:] / b[:-1] - 1.0
    if ra.std() == 0 or rb.std() == 0:
        return None
    return float(np.corrcoef(ra, rb)[0, 1])


def initialize(context):
    g.day_no = 0
    g.targets = []
    g.scores = {}
    g.codes = list(POOL) + [DEFENSIVE]
    g.cost = {}
    g.held = set()
    g.cooldown = {}
    g.last_px = {}
    g.sold_today = 0.0
    g.sellq = []
    g.buy_day = {}
    g.eq_peak = 0.0
    g.breaker = False
    g.def_w = {}
    g.def_leg = {}
    g.def_sig = None
    g.okrun = 0
    g.brk_days = 0
    g.sig_ok = False

    set_benchmark(BENCHMARK)
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_order_cost(OrderCost(open_commission=0.0001,
                             close_commission=0.0001,
                             close_today_commission=0.0,
                             min_commission=5.0), type='fund')
    set_slippage(PriceRelatedSlippage(0.001))

    run_daily(check_stop, time='every_bar')
    if BUY_MODE == 'next':
        run_daily(next_exec, time='09:31')
        run_daily(next_buy, time='09:32')
    else:
        run_daily(on_signal, time='13:10')
        run_daily(on_execute, time='13:20')
    if BUY_MODE == 'open':
        run_daily(open_buy, time='13:21')
        for tt in ('13:40', '14:10', '14:40'):
            run_daily(on_check, time=tt)
        run_daily(on_force, time='14:55')
    elif BUY_MODE == 'close':
        for m in range(_minute_of(RESELL_START), _minute_of(RESELL_END) + 1, RESELL_STEP):
            run_daily(on_resell, time='%02d:%02d' % (m // 60, m % 60))
        for tt, _frac in BATCH_PLAN:
            run_daily(stage_buy, time=tt)
    log.info('初始化完成：池 %d 只，持仓上限 %d，买入模式 %s，防御池 %d 只'
             % (len(POOL), N_HOLD, BUY_MODE, len(DEF_POOL)))


def before_trading_start(context):
    g.day_no += 1
    g.targets = []
    g.scores = {}
    g.sold_today = 0.0
    g.sellq = []
    g.sig_ok = False


def after_trading_end(context):
    g.targets = []
    g.scores = {}


def _def_targets(hist):
    mom = {}
    for c in DEF_POOL:
        cl = (hist.get(c) or {}).get('close')
        if cl is None or len(cl) < DEF_MOM_N + 1:
            continue
        p0 = float(cl[-DEF_MOM_N - 1])
        p1 = float(cl[-1])
        if p0 <= 0 or p1 <= 0:
            continue
        mom[c] = p1 / p0 - 1.0

    det = []
    legs = {}
    for key, grp in (('commodity', DEF_COMMODITY), ('income', DEF_INCOME)):
        cand = [(mom[c], c) for c in grp
                if c in mom and not (c in g.cooldown and g.day_no <= g.cooldown[c])]
        best = max(cand, default=None)
        cur = g.def_leg.get(key)
        cur_ok = (cur in mom and mom[cur] > DEF_EXIT_MOM
                  and not (cur in g.cooldown and g.day_no <= g.cooldown[cur]))
        pick = None
        if key == 'income':
            if cur_ok:
                if best and best[1] != cur and best[0] >= mom[cur] + DEF_SWITCH_MOM:
                    pick = best
                else:
                    pick = (mom[cur], cur)
            elif best and best[0] > DEF_ENTER_MOM:
                pick = best
        else:
            if best and best[0] > DEF_MOM_MIN:
                pick = best
        legs[key] = pick[1] if pick else None
        if pick:
            det.append((pick[1], DEF_HALF, pick[0]))
    g.def_leg = legs
    return [(c, w) for c, w, _ in det], det


def on_signal(context):
    tag = _now(context)
    px = current_px(context, g.codes + list(IDX))
    if not px:
        log.warning('%s 未取到现价，跳过信号' % tag)
        return False

    hist = daily(context, g.codes, LOOKBACK + CORR_WIN + 5)
    if len(hist) < len(g.codes) * 0.5:
        log.warning('%s 历史数据不足（%d/%d），跳过信号'
                    % (tag, len(hist), len(g.codes)))
        return False

    idx_h = daily(context, list(IDX), 15)
    if len(idx_h) < 3:
        log.warning('%s 指数日线仅取到 %d/4，本轮按强势期处理' % (tag, len(idx_h)))
    below = 0
    for code in IDX:
        h = idx_h.get(code)
        if not h or h['close'] is None or len(h['close']) < 10:
            continue
        c = np.asarray(h['close'], float)
        p = px.get(code, c[-1])
        if not np.isfinite(p):
            continue
        if p < np.append(c[-9:], p).mean():
            below += 1
    weak = below >= 3
    strong = below <= DD_STRONG_MAX

    w = np.linspace(1.0, 2.0, LOOKBACK + 1) ** 2
    scored = []
    for code in POOL:
        if code in g.cooldown and g.day_no <= g.cooldown[code]:
            continue
        h = hist.get(code)
        p = px.get(code)
        if not h or p is None or h['close'] is None or len(h['close']) < LOOKBACK + 1:
            continue
        c = np.asarray(h['close'], float)[-LOOKBACK:]
        y = np.append(c, p)

        score, r2, slope = momentum(y, w)
        if score is None or not np.isfinite(score):
            continue
        if score < 0 or score > SCORE_MAX or r2 <= R2_MIN:
            continue
        if slope is None or slope <= 0:
            continue

        if not weak:
            if p <= np.append(c[-9:], p).mean():
                continue
            v = h.get('volume')
            if v is not None and len(v) >= 6:
                base = np.nanmean(np.asarray(v, float)[-6:-1])
                if np.isfinite(base) and base > 0 \
                        and np.asarray(v, float)[-1] / base >= VOL_MAX:
                    continue
            r = np.append(c[-2:], p)
            if min(r[1] / r[0], r[2] / r[1]) < CRASH_MIN:
                continue
        m = h.get('money')
        if m is not None and len(m) >= 3:
            mm = np.nanmean(np.asarray(m, float)[-3:])
            if np.isfinite(mm) and mm <= LIQ_MIN:
                continue
        scored.append((score, code))

    scored.sort(reverse=True)
    top = scored[:TOP_N]
    ref = top[0][0] if top else 0.0
    cpool = [(s, c) for s, c in top if s >= ref * KEEP]

    targets = []
    for s, code in cpool:
        if len(targets) >= N_HOLD:
            break
        ok = True
        for t in targets:
            co = corr60((hist.get(t) or {}).get('close'),
                        (hist.get(code) or {}).get('close'))
            if co is not None and co > CORR_MAX:
                ok = False
                break
        if ok:
            targets.append(code)

    pool_codes = [c for _, c in cpool]
    new_codes = [c for c in targets if c not in g.held]
    for old in sorted(g.held):
        if old in targets or old not in pool_codes:
            continue
        for i, t in enumerate(targets):
            if t not in new_codes:
                continue
            co = corr60((hist.get(old) or {}).get('close'),
                        (hist.get(t) or {}).get('close'))
            if co is not None and co > CORR_BLOCK:
                log.info('%s 相关性阻挡 旧仓=%s 新目标=%s 相关=%.3f'
                         % (tag, cd(old), cd(t), co))
                targets[i] = old
                new_codes.remove(t)
                break

    if weak and ref < SCORE_MIN_WEAK and targets:
        log.info('%s 弱势低分不建仓 首选分=%.2f 剔除=%s'
                 % (tag, ref, ','.join(cd(c) for c in targets)))
        targets = []

    total = _total(context)
    if total > g.eq_peak:
        g.eq_peak = total
    dd = (total / g.eq_peak - 1.0) if g.eq_peak > 0 else 0.0
    if g.breaker:
        g.brk_days += 1
        if strong:
            g.okrun += 1
        else:
            g.okrun = 0
        if g.brk_days >= DD_MIN_LOCK and g.okrun >= DD_CONFIRM:
            g.breaker = False
            g.def_w = {}
            g.def_leg = {}
            g.def_sig = None
            g.eq_peak = total
            g.okrun = 0
            log.info('%s 回撤熔断 解除 总资产=%.0f 锁定=%d日 连续强势=%d日 跌破MA10=%d'
                     % (tag, total, g.brk_days, DD_CONFIRM, below))
            g.brk_days = 0
    elif dd <= -DD_BREAK:
        g.breaker = True
        g.okrun = 0
        g.brk_days = 1
        log.info('%s 回撤熔断 触发 总资产=%.0f 高点=%.0f 回撤=%.2f%%'
                 % (tag, total, g.eq_peak, dd * 100))

    if g.breaker:
        if DEF_ON:
            dw, det = _def_targets(hist)
            targets = [c for c, _ in dw]
            g.def_w = {c: wt for c, wt in dw}
            sig = tuple(targets)
            if sig != g.def_sig:
                log.info('%s 熔断防御仓 目标=%s'
                         % (tag, ','.join('%s %.0f%%(动量%.1f%%)'
                                          % (cd(c), wt * 100, mv * 100)
                                          for c, wt, mv in det) or '空仓'))
                g.def_sig = sig
        else:
            targets = []
            g.def_w = {}

    g.targets = targets
    g.scores = {c: s for s, c in top}
    g.sig_ok = True
    log.info('%s 弱势=%s 候选=%d 目标=%s 熔断=%s 首选分=%.2f 总资产=%.0f'
             % (tag, weak, len(scored),
                ','.join(cd(c) for c in targets) or '空仓',
                'Y' if g.breaker else 'N', ref, total))
    return True


def _positions(context):
    out = {}
    try:
        items = context.portfolio.positions.items()
    except Exception:
        items = []
    for code, pos in items:
        try:
            amt = float(pos.total_amount or 0)
        except Exception:
            amt = 0.0
        if amt > 0:
            out[code] = amt
    g.held = set(out)
    return out


def _amount(context, code):
    try:
        return float(context.portfolio.positions[code].total_amount or 0)
    except Exception:
        return 0.0


def _total(context):
    try:
        return float(context.portfolio.portfolio_value)
    except Exception:
        return 0.0


def _cash(context):
    try:
        return max(float(context.portfolio.available_cash), 0.0)
    except Exception:
        return 0.0


def _sell_all(context, code, px_value=0.0, quiet=False):
    amt = 0.0
    closeable = 0.0
    try:
        pos = context.portfolio.positions[code]
        amt = float(pos.total_amount or 0)
        closeable = float(getattr(pos, 'closeable_amount', amt) or 0)
    except Exception:
        return True
    if amt <= 0:
        return True
    if closeable <= 0:
        return False
    try:
        order_target_value(code, 0)
    except Exception as e:
        log.warning('卖出 %s 失败：%s' % (cd(code), e))
        return False
    left = 0.0
    try:
        left = float(context.portfolio.positions[code].total_amount or 0)
    except Exception:
        left = 0.0
    g.sold_today += max(amt - left, 0.0) * (px_value or 0.0)
    if not quiet:
        log.info('卖出 %s 委托前=%.0f 卖后=%.0f 成交=%.0f 价=%.3f 当日已卖=%.0f'
                 % (cd(code), amt, left, amt - left, px_value, g.sold_today))
    return True


def on_execute(context):
    tag = _now(context)
    if not g.sig_ok:
        log.warning('%s 当日信号未成功，跳过卖出以免误清仓' % tag)
        return False
    held = _positions(context)
    for c in list(g.buy_day.keys()):
        if c not in held:
            g.buy_day.pop(c, None)
    queued = []
    locked = 0
    for c in held:
        if c in g.targets:
            continue
        d0 = g.buy_day.get(c)
        if d0 is not None and g.day_no - d0 < MIN_HOLD_DAYS:
            locked += 1
            continue
        queued.append(c)
    g.sellq = list(queued)
    px = current_px(context, queued)
    for c in queued:
        _sell_all(context, c, px_value=px.get(c, 0.0))
    g.sellq = [c for c in queued if _amount(context, c) > 0]
    if g.sold_today > 0 or g.sellq:
        log.info('%s 卖出完成 现金=%.0f 当日已卖=%.0f 待卖=%d 最小持有锁定=%d'
                 % (tag, _cash(context), g.sold_today, len(g.sellq), locked))
    return True


def on_resell(context):
    if not RESELL_ON or not g.sellq:
        return
    left = [c for c in g.sellq if _amount(context, c) > 0]
    g.sellq = left
    if not left:
        return
    px = current_px(context, left)
    for code in left:
        _sell_all(context, code, px_value=px.get(code, 0.0), quiet=True)


def on_buy(context, frac=1.0, tag=''):
    if not g.targets:
        return True
    px = current_px(context, list(g.targets) + list(g.held))
    if not px:
        return False
    total = _total(context)
    if total <= 0:
        return True
    held = _positions(context)
    cash = _cash(context)
    need = [c for c in g.targets if c not in held and c in px]
    budget = total / min(len(g.targets) + 1, N_HOLD) * frac
    bmap = {}
    if g.breaker:
        bmap = {c: total * g.def_w.get(c, 0.0) for c in g.targets}
        budget = total * DEF_FRAC
    elif need:
        budget = min(budget, cash / len(need))
    done = 0
    for code in g.targets:
        p = px.get(code)
        if not p:
            continue
        b = bmap.get(code, budget) if g.breaker else budget
        cur = held.get(code, 0) * p
        gap = min(b - cur, cash)
        lot = 100.0 * p
        if gap < max(lot, total * 0.01):
            continue
        try:
            order_value(code, gap)
        except Exception as e:
            log.warning('买入 %s 失败：%s' % (cd(code), e))
            continue
        g.held.add(code)
        g.cost[code] = p
        if code not in g.buy_day:
            g.buy_day[code] = g.day_no
        cash -= gap
        done += 1
    if frac >= 1.0:
        log.info('%s 成交完成 目标=%s 总资产=%.0f 预计剩余可用=%.0f 预算=%.0f 下单=%d'
                 % (tag, ','.join(cd(c) for c in g.targets), total, cash, budget, done))
    return True


def stage_buy(context):
    t = _now(context)
    frac = 1.0
    for tt, fr in BATCH_PLAN:
        if t == tt:
            frac = fr
            break
    on_buy(context, frac=frac, tag=t)


def open_buy(context):
    on_buy(context, frac=1.0, tag=_now(context))


def next_exec(context):
    if on_signal(context):
        on_execute(context)


def next_buy(context):
    on_buy(context, frac=1.0, tag=_now(context))


def on_check(context):
    on_resell(context)
    if not g.targets or g.breaker:
        return
    px = current_px(context, list(g.targets) + list(g.held))
    if not px:
        return
    total = _total(context)
    if total <= 0:
        return
    budget = total / min(len(g.targets) + 1, N_HOLD)
    held = _positions(context)
    hist = daily(context, [c for c in g.targets if c != DEFENSIVE], 11)
    for code in g.targets:
        if code == DEFENSIVE:
            continue
        p = px.get(code)
        h = hist.get(code)
        if not p or not h or h['close'] is None or len(h['close']) < 10:
            continue
        if p <= np.append(np.asarray(h['close'], float)[-9:], p).mean():
            continue
        gap = budget - held.get(code, 0) * p
        gap = min(gap, _cash(context))
        if gap > max(total * MIN_GAP, 2000.0):
            try:
                order_value(code, gap)
            except Exception as e:
                log.warning('补仓 %s 失败：%s' % (cd(code), e))
                continue
            g.held.add(code)


def on_force(context):
    if not g.targets:
        return
    on_resell(context)
    px = current_px(context, list(g.targets) + list(g.held))
    if not px:
        return
    total = _total(context)
    if total <= 0:
        return
    budget = total / min(len(g.targets) + 1, N_HOLD)
    held = _positions(context)
    for code in g.targets:
        p = px.get(code)
        if not p:
            continue
        gap = budget - held.get(code, 0) * p
        gap = min(gap, _cash(context))
        if gap > max(total * 0.005, 1000.0):
            try:
                order_value(code, gap)
            except Exception as e:
                log.warning('强制补仓 %s 失败：%s' % (cd(code), e))
                continue
            g.held.add(code)


def check_stop(context):
    held = _positions(context)
    if not held:
        return
    px = current_px(context, list(held))
    for code in list(held):
        p = px.get(code)
        if not p:
            continue
        cp = 0.0
        try:
            cp = float(context.portfolio.positions[code].avg_cost or 0)
        except Exception:
            cp = 0.0
        if not cp:
            cp = g.cost.get(code, 0.0)
        if not cp:
            continue
        stop_px = DEF_STOP if (g.breaker and DEF_ON) else STOP
        if p <= cp * stop_px:
            if _sell_all(context, code, px_value=p):
                g.buy_day.pop(code, None)
                g.cooldown[code] = g.day_no + COOL_DAYS
                if code in g.targets:
                    g.targets.remove(code)
                g.sellq = [c for c in g.sellq if c != code]
                log.info('止损卖出 %s 现价%.4f 成本%.4f 阈值%.0f%% 冷却至第%d日'
                         % (cd(code), p, cp, (1 - stop_px) * 100,
                            g.day_no + COOL_DAYS))
