"""probe-etf-start-dates — JQ's own listing date for the 26 etf_pool codes of 62c2664f
(ETF动量 champion), for study/ETF动量/build-e9-pit.js (q-e9-3). Logs one STARTDATE line per code
from get_security_info(code).start_date + display_name. Trades nothing: SUMMARY no-trades is
EXPECTED. Control: a PROBE-BEGIN line and a PROBE-END line with the count; if they are absent the
code path did not run and no STARTDATE line may be read.
"""

CODES = ["513100.XSHG","159509.XSHE","513520.XSHG","513030.XSHG","518880.XSHG","159985.XSHE","159981.XSHE","501018.XSHG","511260.XSHG","513130.XSHG","513690.XSHG","510180.XSHG","159915.XSHE","510410.XSHG","515650.XSHG","588120.XSHG","159851.XSHE","159637.XSHE","516160.XSHG","159550.XSHE","515250.XSHG","159378.XSHE","516510.XSHG","515050.XSHG","515000.XSHG","159529.XSHE"]


def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    log.info('PROBE-BEGIN n=%d' % len(CODES))
    ok = 0
    for c in CODES:
        try:
            info = get_security_info(c)
            if info is None:
                log.info('STARTDATE\t%s\tNONE\t-\t-' % c)
                continue
            log.info('STARTDATE\t%s\t%s\t%s\t%s' % (c, info.start_date, info.display_name, info.type))
            ok += 1
        except Exception as e:
            log.info('STARTDATE\t%s\tERROR\t%s\t-' % (c, repr(e)))
    log.info('PROBE-END ok=%d' % ok)


def handle_data(context, data):
    pass


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
