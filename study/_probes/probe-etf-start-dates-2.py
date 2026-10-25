"""probe-etf-start-dates-2 — follow-up to probe-etf-start-dates.py. Under the bench's forced
avoid_future_data=True, get_security_info returns None for a code not yet listed on the query date,
so run 1 (2024-01-02) could only say 159550/159378/159529 were NOT listed by then. This run
re-queries them every trading day of TRAIN 2024 and logs FIRSTSEEN <code> <day> <start_date> the
first day JQ returns them. A code never seen by 2024-12-31 ⇒ listed 2025 or later.
CONTROL: 159529 has a corpus date of 2024-02-02 and must appear on/after it.
Trades nothing: SUMMARY no-trades is EXPECTED.
"""

PENDING = ['159550.XSHE', '159378.XSHE', '159529.XSHE']


def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    g.pending = list(PENDING)
    log.info('PROBE-BEGIN pending=%s' % ','.join(g.pending))
    run_daily(check, '09:31')


def check(context):
    # Membership via get_all_securities: unlike get_security_info it emits no per-code 未上市
    # WARNING, which flooded the first version's 100-line log window and truncated its end marker.
    d = context.current_dt.date()
    listed = set(get_all_securities(['etf', 'lof'], date=d).index)
    left = []
    for c in g.pending:
        if c in listed:
            info = get_security_info(c)
            log.info('FIRSTSEEN\t%s\t%s\t%s\t%s' % (c, d, info.start_date, info.display_name))
        else:
            left.append(c)
    g.pending = left
    if d.day <= 3 or str(d) >= '2024-12-30':
        log.info('HEARTBEAT\t%s\tpending=%s' % (d, ','.join(g.pending) or '-'))


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
