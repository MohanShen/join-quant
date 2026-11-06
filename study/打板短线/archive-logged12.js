// Step-0 exit record for the 2026-11-06 second re-invocation (reason: new-members, 1).
//   node -e "require('./study/打板短线/archive-logged12.js')"
require('../../utils/consumption').record({
  key: '打板短线', kind: 'family', stage: 'research', runId: 'run-family-2026-11-06b', outcome: 'logged-only',
  note: 'step-0 exit, 0 backtests: 16d201f2 = 低位三连阳 stock leg + 五福 v5.1 ETF idle-cash parking (held only while the stock leg is empty). Passes at obj 0.3029 / sharpe 1.35, H1 +32 / H2 +28, while the stock leg alone is 5 of 5 DQ on 2024 - the pass most likely comes from the 五福 leg (unablated; 五福闹新春\'s mechanism, noted for that family). '
    + 'Family still R=1; valReopened: 9 left unspent. Edges unchanged; queue 0 open',
});
console.log('recorded logged-only research event for 打板短线 (2026-11-06b)');
