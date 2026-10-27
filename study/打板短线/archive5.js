// Research consumption event for the 2026-10-27 round (epoch 9): step-0 found a live question in a
// stale closure and spent ONE backtest on it; VAL (reopened by the human on 2026-10-26) deliberately
// not spent — the reopen commit itself calls it inert for this family (R=1 binds before VAL).
//   node -e "require('./study/打板短线/archive5.js')"
require('../../utils/consumption').record({
  key: '打板短线', kind: 'family', stage: 'research', runId: 'run-family-2026-10-27', outcome: 'done',
  note: '1 epoch-9 TRAIN backtest (~7 JQ min): u-e9-rzq = u-rzq-deconf re-run on 2024 — skipping the 弱转强 leg takes H1 +933 -> +415 and H2 -13 -> +40 (Q4 -12 -> +47), obj 7.5458 -> 6.0066, maxDD halved (partly idle cash); the epoch-6 closure holds on the new bench (2 of 2 years), the standalone 弱转强 book 29048a4f\'s opposite shape is not evidence about the base\'s leg. '
    + 'Step 0 on 3 new members (004aca1c lineage framework, 29048a4f 弱转强 leg, b0c225d4 涨停基因+五福 combination), logged; free 2024 half-year split: base lineage first-half fat tail 5 of 5 years. '
    + 'VAL reopened by the human (valReopened: 9) but NOT spent: exit gate rejects on measured R=1 before VAL (owner none) and the prior basis (2025 in-sample for 2026 authors) still binds; route is a re-scored realizability. Edges unchanged; queue 0 open',
});
console.log('recorded research event for 打板短线 (2026-10-27)');
