"""probe-pitpool-members — do the two families' OWN pool members clear the
point-in-time eligibility rule, and if not, which ones fail and why?

Separates two explanations for the pit-pool collapse:
  (a) the 2026 list is hindsight (the names were fine, the CHOICE was not), vs
  (b) some of those names cannot absorb this strategy's own position size at all.

CONTROL: it re-runs the IDENTICAL pool builder used by both pit-pool variants and logs
POOLSIZE. If those 24 lines do not reproduce the two measured runs exactly
(154/163/170/193/196/200/228/233/232/236/252/265/248/255/267/278/302/299/293/289/301/280/276/274)
the code path did not run and no MEMBER line may be read. No trades by design -> SUMMARY
status `no-trades` is the EXPECTED outcome, not a failure.
"""

import numpy as np
import pandas as pd

MEMBERS = [
    "513100.XSHG",  # 纳指ETF        (both families)
    "518880.XSHG",  # 黄金ETF        (both)
    "161226.XSHE",  # 白银LOF        (both)
    "159985.XSHE",  # 豆粕ETF        (both)
    "159915.XSHE",  # 创业板         (both)
    "513520.XSHG",  # 日经ETF        (ETF动量)
    "513030.XSHG",  # 德国ETF        (ETF动量)
    "511090.XSHG",  # 30年国债ETF    (ETF动量)
    "159525.XSHE",  # 红利低波       (ETF动量)
    "513130.XSHG",  # 恒生科技       (ETF动量)
    "159628.XSHE",  # 国证2000       (ETF动量)
    "501018.XSHG",  # 南方原油       (七星高照)
    "511220.XSHG",  # 城投债ETF      (七星高照)
    "511880.XSHG",  # 银华日利(防御) (七星高照 defensive)
]


def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    log.set_level('system', 'error')
    log.set_level('strategy', 'error')
    g.etf_pool = []
    g.pool_month = None
    g.probe_month = None
    run_daily(rebuild_pool, 'before_open')
    run_daily(probe_members, 'before_open')


def probe_members(context):
    key = (context.current_dt.year, context.current_dt.month)
    if g.probe_month == key:
        return
    g.probe_month = key
    d = context.previous_date
    allsec = get_all_securities(types=POOL_TYPES, date=d)
    sd = pd.to_datetime(allsec['start_date'])
    med = _pool_median_money(MEMBERS, d)
    for c in MEMBERS:
        if c in allsec.index:
            listed = (pd.Timestamp(d) - pd.Timestamp(sd.loc[c])).days
        else:
            listed = -1
        m = med.get(c, float('nan'))
        verdict = 'PASS' if (listed >= POOL_MIN_LISTED and m >= POOL_MIN_MONEY) else (
            'NOTLISTED' if listed < 0 else ('TOONEW' if listed < POOL_MIN_LISTED else 'THIN'))
        log.error('MEMBER %s %s listed_days=%d med_money=%.0f in_pool=%s %s'
                  % (str(d), c, listed, (0.0 if m != m else m), c in g.etf_pool, verdict))


# ===== POINT-IN-TIME POOL (declared construction; identical text in both families) =====
# Replaces a hard-coded 2026 ETF list with a pool GENERATED on the decision date from
#   (a) listing date  and  (b) same-day-available liquidity.
# Nothing is hand-picked and no post-2023 information is used: every input is read as of
# context.previous_date (the last completed trading day).
#
#  - 次新 exclusion: harness/harness.md §3 — listed < 250 calendar days is never eligible.
#  - LIQUIDITY FLOOR, derived from the strategy's OWN position size: base capital is
#    1,000,000 and the strategy holds ONE fund, so a full position is 1,000,000. Epoch 4
#    pins order_volume_ratio=0.05, i.e. one order may take at most 5% of a bar's volume,
#    so filling that position inside a single daily bar needs same-day turnover of at least
#    1,000,000 / 0.05 = 20,000,000 CNY. Floor = trailing-20-bar MEDIAN `money` (median, not
#    mean, so one spike day cannot admit a normally-illiquid fund).
#  - types = ['etf','lof'] because BOTH families' own pools contain LOFs (161226 白银LOF,
#    501018 南方原油); restricting to 'etf' would drop their own members by type and
#    confound the pool question with a type restriction.
#  - Rebuilt on the first trading day of each month. Eligibility is a slow-moving universe
#    property and a monthly rebuild can only ever LAG a new listing, never anticipate one.
#  - Current holdings are unioned in, because the strategies gate their own position
#    management on `sec in g.etf_pool`; without the union a fund that later drops out of
#    eligibility could never be sold.
POOL_MIN_MONEY   = 2.0e7     # CNY/day, see derivation above
POOL_MIN_LISTED  = 250       # calendar days
POOL_LIQ_WINDOW  = 20        # trailing trading bars
POOL_TYPES       = ['etf', 'lof']


def _pool_not_paused(cur, c):
    try:
        return not cur[c].paused
    except Exception:
        return False


def _pool_median_money(cand, d):
    """{code: median turnover} over the POOL_LIQ_WINDOW bars ending at d. Shape-agnostic:
    JQ's get_price returns a long frame, a MultiIndex frame or a panel depending on runtime,
    so the result is validated against the candidate set and falls back to per-code calls."""
    candset = set(cand)
    out = {}
    try:
        try:
            px = get_price(cand, end_date=d, count=POOL_LIQ_WINDOW, frequency='daily',
                           fields=['money'], skip_paused=False, panel=False)
        except TypeError:
            px = get_price(cand, end_date=d, count=POOL_LIQ_WINDOW, frequency='daily',
                           fields=['money'], skip_paused=False)
        cols = list(getattr(px, 'columns', []))
        if 'code' in cols:                                  # long frame: time, code, money
            for c, grp in px.groupby('code'):
                out[c] = float(grp['money'].median())
        elif 'money' in cols and getattr(px.index, 'nlevels', 1) > 1:
            s = px['money']
            for lvl in (0, 1):
                g2 = s.groupby(level=lvl).median()
                if len(candset & set(g2.index)) > 0:
                    out = dict((k, float(v)) for k, v in g2.items())
                    break
        else:                                               # panel: px['money'] = days x codes
            m = px['money'].median()
            out = dict((k, float(v)) for k, v in m.items())
    except Exception as e:
        log.error('POOLWARN batched liquidity failed (%s)' % e)
        out = {}
    if len(candset & set(out.keys())) < len(candset) * 0.5:
        log.error('POOLWARN batched shape unusable (%d/%d) -> per-code fallback'
                  % (len(candset & set(out.keys())), len(candset)))
        out = {}
        for c in cand:
            try:
                p1 = get_price(c, end_date=d, count=POOL_LIQ_WINDOW, frequency='daily',
                               fields=['money'], skip_paused=False)
                out[c] = float(p1['money'].median())
            except Exception:
                continue
    return out


def rebuild_pool(context):
    import pandas as pd
    key = (context.current_dt.year, context.current_dt.month)
    if g.pool_month == key and g.etf_pool:
        return
    d = context.previous_date
    allsec = get_all_securities(types=POOL_TYPES, date=d)
    sd = pd.to_datetime(allsec['start_date'])
    cand = list(allsec.index[sd <= pd.Timestamp(d) - pd.Timedelta(days=POOL_MIN_LISTED)])
    med = _pool_median_money(cand, d) if cand else {}
    cur = get_current_data()
    pool = [c for c in cand
            if med.get(c, 0.0) >= POOL_MIN_MONEY and _pool_not_paused(cur, c)]
    held = [s for s in context.portfolio.positions
            if context.portfolio.positions[s].total_amount > 0]
    g.etf_pool = sorted(set(pool) | set(held))
    g.pool_month = key
    log.error('POOLSIZE %s listed=%d cand=%d pool=%d'
              % (str(d), len(allsec), len(cand), len(g.etf_pool)))
# ===== END POINT-IN-TIME POOL =====


# ===== AUTORESEARCH NORMALIZATION OVERRIDE (appended; strategies/ file untouched) =====
# harness/harness.md §2 — force the frozen execution settings regardless of what the
# raw strategy sets, even if it re-sets costs every bar. Values are pinned in
# harness/config/epoch-<n>.json; utils/harness-config.js --verify checks this block
# still matches, because Python running on JQ's servers cannot read that JSON.
__jq_set_slippage = set_slippage
def set_slippage(*a, **k):
    __jq_set_slippage(FixedSlippage(0))
__jq_set_commission = set_commission
def set_commission(*a, **k):
    __jq_set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
# epoch 4: set_commission does NOT govern funds, so 170 held strategies were running
# ETF trades on their own costs. Pin the fund table too, and neutralise re-sets.
# epoch 6: it does not govern STOCKS either. JQ deprecated set_commission in favour of
# set_order_cost, so a strategy's own type='stock' call won outright and 95 of 215 held
# strategies were being charged their AUTHOR's fees. Measured by probe: a 5%/side stock
# commission injected into int-001 moved total return +64.44% -> -11.33% (-75.77pp), i.e.
# the bench had no control over stock fees at all. Both tables are now pinned, and the
# fall-through forwards only the types we do not model (futures, mmf, ...).
# Guarded: unlike set_slippage/set_commission, set_order_cost is NOT bound at module
# scope in every JQ runtime — rebinding it unguarded raised NameError at import and
# the whole strategy came back compile-error.
try:
    __jq_set_order_cost = set_order_cost
    def __jq_cost_type(a, k):
        t = k.get('type')
        if t is None and len(a) > 1:
            t = a[1]
        return t
    def set_order_cost(*a, **k):
        __t = __jq_cost_type(a, k)
        if __t == 'fund':
            __jq_set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0, min_commission=5), type='fund')
        elif __t == 'stock':
            __jq_set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0.001, min_commission=5), type='stock')
        else:
            __jq_set_order_cost(*a, **k)
except NameError:
    pass
try:
    __jq_orig_initialize = initialize
    def initialize(context):
        __jq_orig_initialize(context)
        set_option('use_real_price', True)
        # epoch 4 pins, applied AFTER the strategy's own initialize so they win
        set_option('avoid_future_data', True)
        set_option('order_volume_ratio', 0.05)
        set_slippage(FixedSlippage(0))
        set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
        try:
            set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0, min_commission=5), type='fund')
        except Exception:
            pass
        # epoch 6: pin the stock table too, AFTER the strategy's own initialize so it wins
        # even when the strategy set its costs there rather than at module scope.
        try:
            set_order_cost(OrderCost(open_commission=0.0003, close_commission=0.0003, close_tax=0.001, min_commission=5), type='stock')
        except Exception:
            pass
except NameError:
    pass
# ===== END OVERRIDE =====
