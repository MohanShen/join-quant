# Probe: does get_extras('is_st', ..., start_date=D, end_date=D) answer AS OF D,
# or does it leak the CURRENT (end-of-data) ST status into a backtest dated D?
#
# Claim under test (community post, screened 2026-09-18, screen/verdicts.json):
#   "get_extras('is_st') returns a stock's ST status as of today, not as of the
#    backtest date — 241 ST names leaked into a 2019 stock pool."
#
# 15 held strategies in strategies/ use the get_extras form; 98 use the safe
# get_current_data()[s].is_st form. If the claim holds, those 15 are contaminated.
#
# Design (falsifiable, no strategy logic):
#   On each trading day D we count ST names in a fixed universe two ways:
#     A = get_extras('is_st', universe, start_date=D, end_date=D)   <- under test
#     B = get_current_data()[s].is_st                               <- as-of-D truth
#   Run over two widely separated windows inside TRAIN.
#   - If A == B on every day, get_extras is correctly date-indexed: NO leak.
#   - If A is constant across both windows while B moves, A is answering with
#     one fixed snapshot: LEAK.
# We also print the symmetric difference so a disagreement can be inspected.

def initialize(context):
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_benchmark('000300.XSHG')
    set_slippage(FixedSlippage(0))
    set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
    # Fixed universe, chosen once and never re-queried, so the only thing that can
    # move between runs is the ST answer itself.
    g.universe = None
    run_daily(probe, time='09:30', reference_security='000300.XSHG')


def probe(context):
    d = context.current_dt.date()
    if g.universe is None:
        # All A-shares listed before the window opens. Fixed for the whole run.
        g.universe = list(get_all_securities(['stock'], date='2021-12-31').index)[:800]

    cur = get_current_data()
    b = {s for s in g.universe if cur[s].is_st}

    a = set()
    try:
        df = get_extras('is_st', g.universe, start_date=d, end_date=d, df=True)
        if df is not None and len(df) > 0:
            row = df.iloc[0]
            a = {s for s in g.universe if bool(row.get(s, False))}
    except Exception as e:
        log.info('PROBE_ERROR %s %s' % (d, e))
        return

    only_a = sorted(a - b)[:5]
    only_b = sorted(b - a)[:5]
    log.info('PROBE %s universe=%d get_extras_st=%d current_data_st=%d '
             'only_extras=%d %s only_current=%d %s'
             % (d, len(g.universe), len(a), len(b),
                len(a - b), only_a, len(b - a), only_b))
