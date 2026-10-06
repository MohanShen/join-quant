// Records the 涨停基因 sub-lineage round's research consumption event (2026-10-04/05).
//   node -e "require('./study/打板短线/archive-jy.js')"
require('../../utils/consumption').record({
  key: '打板短线', kind: 'family', stage: 'research', runId: 'run-family-2026-10-05', outcome: 'done',
  note: '2 epoch-6 TRAIN backtests on the 涨停基因 sub-lineage base c9e0451d (anchor = normalizer row 2026-10-03: obj 0.5478 sharpe 2.94, both years positive); '
    + 'jy-u-1 no limit-up info: obj 0.3237 sharpe 2.00, same shape, four positive half-years (floor is size; the screen adds +0.22 / ~20pp per year); '
    + 'jy-u-2 same screen on the 1000 largest caps: obj -0.4136, 2023 -26%, win 43% (size necessary; executor slow-skipped at the 50-min cap, run completed server-side, result recovered from buildList/stats/result); '
    + 'edges: 涨停基因 refuted as an independent edge (size-conditional overlay, unregistered), 规模因子 measured for the sub-lineage (6th family fed by size) -> recommend moving the sub-lineage to 小市值; '
    + '涨停动量延续 unchanged (measured, base 439385b4); VAL already spent 2026-09-22; queue 0 open. 10-04 attempt was blocked by a phantom run (CONCURRENT-STOP), 0 backtests that day',
});
console.log('recorded research event for 打板短线 (2026-10-05)');
