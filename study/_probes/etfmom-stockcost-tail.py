
# ===== STOCKCOST PROBE TAIL =====
# Appended AFTER the frozen epoch-6 OVERRIDE. Control = enhance/candidates/etfmom-004.py,
# which is this exact file without this block (measured: total 215.05 / annual 77.64 /
# sharpe 3.10 / maxDD 13.05).
#
# Question: does a post-initialize set_order_cost(..., type='stock') actually BIND in this
# runtime for this strategy? Epoch 6 pins stock costs both at module scope and after
# initialize, yet this 100%-stock book returned bit-identical numbers on epoch 5 and
# epoch 6 — impossible if the pin took effect, because the file declares its own cheaper
# stock costs (close_tax 0.0005, commission 0.85/10000) versus the bench's 0.001 / 0.0003,
# roughly 9bp per round trip at turnover ~0.078/day.
#
# This block injects a deliberately ABSURD 5%/side stock commission by the same mechanism.
# Reading the result:
#   - result collapses      -> the mechanism binds; epoch 6 is genuinely applied and the
#                              real ~9bp delta simply rounds away (implausible, but then
#                              the bench is sound).
#   - result unchanged      -> the stock pin is INERT for this strategy, and every epoch-6
#                              stock number in this repo is still the AUTHOR's cost schedule.
# The backtest log is not retrievable (CLAUDE.md), so the answer has to be the return itself.
try:
    __probe_orig_initialize = initialize
    def initialize(context):
        __probe_orig_initialize(context)
        set_order_cost(
            OrderCost(open_commission=0.05, close_commission=0.05,
                      close_tax=0.001, min_commission=5),
            type='stock',
        )
except NameError:
    pass
# ===== END STOCKCOST PROBE TAIL =====
