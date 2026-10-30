// Step-0 exit record for the 2026-10-30 re-invocation (reason: new-members, 1 since 2026-10-27).
//   node -e "require('./study/打板短线/archive-logged6.js')"
require('../../utils/consumption').record({
  key: '打板短线', kind: 'family', stage: 'research', runId: 'run-family-2026-10-30', outcome: 'logged-only',
  note: 'step-0 exit, 0 backtests: e1053979 连板策略 V5.8 (b518f737 连板 body + emotion gate + auction volume-ratio filter) is DQ on 2024 (obj -0.0844 / sharpe 0.56 / maxDD 40.6) with the inverse half-year shape of the base (H1 -39 / H2 +117) — a nuance for the regime wording (first-half fat tail belongs to the 首板 legs, not to the limit-up event), no new question. '
    + 'Family still R=1 (exit gate rejects before VAL); valReopened: 9 left unspent, prior basis binds. Edges unchanged; queue 0 open',
});
console.log('recorded logged-only research event for 打板短线 (2026-10-30)');
