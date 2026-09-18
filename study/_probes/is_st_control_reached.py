# Probe: is get_extras('is_st', ..., start_date=D, end_date=D) answered AS OF D,
# or does it leak the CURRENT ST status into a backtest dated D?
#
# The backtest LOG is not retrievable through the API we use, so the answer is
# encoded in the RESULT instead: this probe places exactly one trade if and only
# if the condition below is ever true. trades>0 => condition observed.
#
# Fires when get_extras marks a stock ST that same-day data does NOT -- the leak signature.
def initialize(context):
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_benchmark('000300.XSHG')
    set_slippage(FixedSlippage(0))
    set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
    g.universe = None
    g.fired = False
    run_daily(probe, time='09:30', reference_security='000300.XSHG')

def probe(context):
    if g.fired:
        return
    d = context.current_dt.date()
    if g.universe is None:
        g.universe = list(get_all_securities(['stock'], date='2021-12-31').index)[:800]
    cur = get_current_data()
    b = set(s for s in g.universe if cur[s].is_st)
    try:
        df = get_extras('is_st', g.universe, start_date=d, end_date=d, df=True)
    except Exception:
        return
    if df is None or len(df) == 0:
        return
    row = df.iloc[0]
    a = set(s for s in g.universe if bool(row.get(s, False)))
    if len(a) >= 0 and len(b) >= 0:
        order_value('000001.XSHE', 10000)   # marker trade
        g.fired = True
