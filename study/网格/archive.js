// Records the round's research consumption event. No validated_strategies/ archive: nothing in
// this round cleared the 1.5 sharpe stage gate (base 1.19 is the family's ceiling on epoch 6),
// so the family's epoch-6 VAL was NOT spent.
//   node -e "require('./study/网格/archive.js')"
require('../../utils/consumption').record({
  key: '网格', kind: 'family', stage: 'research', runId: 'run-family-2026-09-22', outcome: 'done',
  note: '11 epoch-6 TRAIN backtests (~7 JQ min: used 140 -> 147), 0 VAL (no candidate passes sharpe 1.5; budget kept); '
    + 'base 598050b9 (= 32021d45, q-dup) anchor reproduces epoch 2 digit for digit (obj 0.1411 / annual 33.79 / sharpe 1.19 / maxDD 19.68; pins are no-ops); '
    + 'edges: 均值回归 measured (hold-the-basket control obj -0.27, mirror ladder -0.30, ladder 0.14, both years same sign), '
    + '趋势择时 measured (index 2-day -3% stop off: obj -0.09, maxDD +9.3; 2022-only insurance, costs 10pp in 2023); '
    + 'selection = lowest price-level variance 5 (documented intent "highest" collapses to -0.35; pure low price -0.14, pure low vol 0.00, neither alone) -> unnamed component, name-specific risk; '
    + 'sector swap to C27+C39: still positive both years but annual 11.9 -> ~2/3 of 33.8 is the I64/I65 2023-H1 AI rally; '
    + 'imp-1 diversify rejected (-0.22, dilution), imp-2 tighter buy rung inert (-0.02), imp-3 tighter sell rung rejected (-0.04, maxDD invariant). Improve queue exhausted',
});
console.log('recorded research event for 网格');
