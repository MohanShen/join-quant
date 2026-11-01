// Step-0 exit record for the 2026-11-01 re-invocation (reason: new-members, 1 since 2026-10-31).
//   node -e "require('./study/打板短线/archive-logged8.js')"
require('../../utils/consumption').record({
  key: '打板短线', kind: 'family', stage: 'research', runId: 'run-family-2026-11-01', outcome: 'logged-only',
  note: 'step-0 exit, 0 backtests: bd771016 (fork of 439385b4\'s 首板低开 leg, 09:28 auction-window entry, split sells) passes on 2024 (obj 2.2204 / sharpe 4.25 / maxDD 28.4) with H1 +325 / H2 -17.5 — the base lineage shape; no new question. '
    + 'Family still R=1 (exit gate rejects before VAL); valReopened: 9 left unspent, prior basis binds. Edges unchanged; queue 0 open',
});
console.log('recorded logged-only research event for 打板短线 (2026-11-01)');
