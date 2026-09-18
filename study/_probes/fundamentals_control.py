# Control for fundamentals_undated.py: fires unconditionally once both frames are
# fetched, proving the comparison path is reached and both calls return data.
def initialize(context):
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_benchmark('000300.XSHG')
    set_slippage(FixedSlippage(0))
    set_commission(PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5))
    g.fired = False
    run_daily(probe, time='09:30', reference_security='000300.XSHG')

def probe(context):
    if g.fired:
        return
    q = query(valuation.code, valuation.market_cap, valuation.pe_ratio
              ).order_by(valuation.market_cap.asc()).limit(300)
    try:
        undated = get_fundamentals(q)
        dated = get_fundamentals(q, date=context.previous_date)
    except Exception:
        return
    if undated is None or dated is None or len(undated) == 0 or len(dated) == 0:
        return
    order_value('000001.XSHE', 10000)
    g.fired = True
