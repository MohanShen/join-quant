// Step-0 exit record for the 2026-10-25 re-invocation (reason: new-members, 3 since 2026-10-07;
// first invocation under epoch 9). No backtest.
//   node -e "require('./study/打板短线/archive-logged3.js')"
require('../../utils/consumption').record({
  key: '打板短线', kind: 'family', stage: 'research', runId: 'run-family-2026-10-25', outcome: 'logged-only',
  note: 'step-0 exit, 0 backtests, epoch 9: a170cc02 = c9e0451d and d29621b6 = 6ada2917 (clone headers, identical epoch-9 rows); 96fb1ca0 竞价擒龙 is the base lineage\'s 一进二 book and the epoch-9 bench leader (obj 7.8535 sharpe 11.95, call-auction-entry) — the same 2024 regime event val-base-e6 already measured (+799%), no new mechanism question. '
    + 'Exit gate REJECTS the family on measured realizability 1 (owner none) before any re-measure or VAL, so the fresh epoch-9 VAL is declined (valDeclined: 9). Edges unchanged; queue 0 open',
});
console.log('recorded logged-only research event for 打板短线 (2026-10-25)');
