# Probe: is an UNDATED get_fundamentals(q) inside a backtest equivalent to one
# explicitly dated to the previous trading day, or does it leak later data?
#
# 130 undated calls appear across the held strategies/, and a screened community
# post claims undated get_fundamentals is a lookahead source. Answer is encoded in
# the result: ONE marker trade fires iff the two ever disagree.
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
    same = (len(undated) == len(dated)
            and list(undated['code']) == list(dated['code'])
            and [round(float(x), 6) for x in undated['market_cap']]
                == [round(float(x), 6) for x in dated['market_cap']])
    if not same:
        order_value('000001.XSHE', 10000)   # marker: undated != dated
        g.fired = True
