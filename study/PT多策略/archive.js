// Records the round's research consumption event (idempotent by key+stage+runId).
//   node -e "require('./study/PT多策略/archive.js')"
require('../../utils/consumption').record({
  key: 'PT多策略', kind: 'family', stage: 'research', runId: 'run-family-2026-09-22', outcome: 'done',
  note: '10 epoch-6 TRAIN backtests + 1 VAL (~35 JQ min: used 88 -> 123); '
    + 'q-struct (zero cost): c70281d3\'s 4,200-line 分仓隔离插件 sits inside a module-level \'\'\' string and never runs -> family = ONE ETF-discount sleeve, two archives (ledger delta -0.014); '
    + 'base fa0d3bd9 anchor reproduces the epoch-4 row digit for digit (obj 1.8592 / annual 195.74 / sharpe 11.15 / maxDD 9.82; epoch-2 369.07 was halved by the 5% participation cap = capacity, not signal); '
    + 'edges: 均值回归 measured (mirror buy-highest-premium -91% total, no-NAV thinnest-10 control -42%, base +772%, log-symmetric; depth weighting +17pp over equal), '
    + '流动性溢价 measured (liquid band 5e7-1e8: annual 22.7 / sharpe 0.94 DQ; no ceiling: return flat, maxDD +4.2; floor 1e7: -58pp; band monotone in thinness); '
    + 'both years positive (2022 +300 / 2023 +121), not regime-carried; '
    + 'imp-1 floor 1e7 rejected (-0.57), imp-2 top-5 rejected (-0.14, fill width under the 5% cap); improve exhausted, base is the optimum; '
    + 'VAL spent on the base: 2024-25 annual 241.73 / sharpe 12.82 / maxDD 5.92 (obj 2.3581, above TRAIN, 2024-02 crash 4.5% maxDD); '
    + 'u-7 REALIZABILITY DECISIVE: same signal executed at 14:50 instead of the 09:30 open -> -29% total / maxDD 40, same magnitude as the no-signal universe: the whole return is the auction-open print of thin ETFs below NAV. '
    + 'Recommend status -> DQ-realizability (human call); integration must not cite this family\'s objective',
});
console.log('recorded research event for PT多策略');
