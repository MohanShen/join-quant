// Step-0 exit record for the 2026-11-02 re-invocation (reason: new-members, 1 since 2026-11-01).
//   node -e "require('./study/打板短线/archive-logged9.js')"
require('../../utils/consumption').record({
  key: '打板短线', kind: 'family', stage: 'research', runId: 'run-family-2026-11-02', outcome: 'logged-only',
  note: 'step-0 exit, 0 backtests: 6e532250 (439385b4 three-leg fork + stricter 首板 definition + 10:00 high-position heavy-volume exit) is the new family and bench top, obj 11.3000 / sharpe 16.81 / maxDD 33.3 (curve = ledger, implied vol ~69%, not a scrape artefact); 2024 H1 +857 / H2 +32 vs base +933 / -13. '
    + 'Attribution of the H2 gain is an exit-detail ablation with nowhere to go (R=1). Family still R=1 (exit gate rejects before VAL); valReopened: 9 left unspent, prior basis binds. Edges unchanged; queue 0 open',
});
console.log('recorded logged-only research event for 打板短线 (2026-11-02)');
