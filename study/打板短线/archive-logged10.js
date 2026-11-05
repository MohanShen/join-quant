// Step-0 exit record for the 2026-11-05 re-invocation (reason: new-members, 6 since 2026-11-02).
//   node -e "require('./study/打板短线/archive-logged10.js')"
require('../../utils/consumption').record({
  key: '打板短线', kind: 'family', stage: 'research', runId: 'run-family-2026-11-05', outcome: 'logged-only',
  note: 'step-0 exit, 0 backtests: six members. 低位三连阳 lineage 353f0f75 / b5218789 (same metrics) / 215cfc4a all DQ on 2024 (4 of 4 with 51f7b3ab); 724cf7e4 passes only by carrying the base 首板高开 leg (H1 +200 / H2 -38). 连板 b4089243 DQ, H1 -28.5 / H2 +78.8 - second independent book for the H2-leg reading. '
    + '涨停基因 sub-lineage 94c64f06 is its new best (obj 1.6092, both halves positive, no auction entry) - strengthens the standing split-to-小市值 suggestion (human decision). Family still R=1; valReopened: 9 left unspent. Edges unchanged; queue 0 open',
});
console.log('recorded logged-only research event for 打板短线 (2026-11-05)');
