// Step-0 exit record for the 2026-10-07 re-invocation (reason: new-members, 1 since 2026-10-05).
//   node -e "require('./study/打板短线/archive-logged2.js')"
require('../../utils/consumption').record({
  key: '打板短线', kind: 'family', stage: 'research', runId: 'run-family-2026-10-07', outcome: 'logged-only',
  note: 'step-0 exit, 0 backtests: e73c9d89 (fork of the base\'s 首板高开 leg with a forced 14:50 exit; obj -0.0733 sharpe 0.48, 2022 +52 / 2023 -5, both second halves negative) '
    + 'read against 6ada2917 (低开 leg alone, four positive half-years) settles the last leg question by direction — 低开 is the steady leg, 高开 is regime-shaped — no run warranted. '
    + 'Edges unchanged (涨停动量延续 measured, 规模因子 measured for the 涨停基因 sub-lineage, 涨停基因 refuted). VAL spent 2026-09-22. Queue 0 open',
});
console.log('recorded logged-only research event for 打板短线 (2026-10-07)');
