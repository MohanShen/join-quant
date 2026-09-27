// Step-0 exit record for the 2026-09-27 re-invocation (reason: new-members, 2 since the
// 2026-09-22 round). No backtest was run; the two members were logged as §2 raw rows.
//   node -e "require('./study/打板短线/archive-logged.js')"
require('../../utils/consumption').record({
  key: '打板短线', kind: 'family', stage: 'research', runId: 'run-family-2026-09-27', outcome: 'logged-only',
  note: 'step-0 exit, 0 backtests: 6ada2917 (龙头首板低开, obj 0.2970 sharpe 1.77) is the base\'s 首板低开 leg standalone with a same-day exit, four positive half-years, confirms u-rzq-deconf; '
    + 'b3751277 (涨停优选后再买入, obj 0.4873 sharpe 2.69) is a weekly 5-smallest-cap ML book with a 3-year limit-up-history screen (涨停基因 sub-lineage with c658ef98/d5b83074), edge likely 规模因子 — a classification question, not a research idea for this family. '
    + 'VAL already spent (dbdx-VAL-base-e6). Queue has 0 open ideas',
});
console.log('recorded logged-only research event for 打板短线');
