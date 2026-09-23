// Records the round's research consumption event. No validated_strategies/ archive: nothing in
// this round cleared the 1.5 sharpe stage gate (every arm is negative), so the family's epoch-6
// VAL was NOT spent.
//   node -e "require('./study/三进兵/archive.js')"
require('../../utils/consumption').record({
  key: '三进兵', kind: 'family', stage: 'research', runId: 'run-family-2026-09-22', outcome: 'done',
  note: '14 epoch-6 TRAIN backtests (~8 JQ min: used 145 -> 153), 0 VAL (no candidate passes sharpe 1.5; budget kept); '
    + 'base 7d1012a5 (= e4eb8dca, q-dup; 87ab0122/7552f0ef are wall-clock grid searches, unmeasurable) anchor reproduces epoch 2 digit for digit (annual 0.07 / sharpe -0.49 / maxDD 9.00); '
    + 'reading = overlay minus exposure x hold: author basket +12.6pp/2y (all 2022); four disjoint rule pools (创业板指 top 1-5/6-10/11-15/16-20 by cap on 2021-12-31) -1.8/+16.2/+7.5/+18.2pp, 3 of 4 positive both years, absolute return -12/+6/-6/+4, sharpe < 0 on every pool; '
    + 'stop off (u-3): information +12.6 -> -3.0pp, the EMA20 exit carries all of it; bottom clause off (u-2): near inert; '
    + '20-name pool (sjb-imp-1) rejected: exposure 0.27 -> 0.67, information unchanged, book -15.6%. '
    + 'Edge 趋势择时 measured as bear-market insurance (~+5pp/yr x 30% exposure), not alpha; improve queue exhausted',
});
console.log('recorded research event for 三进兵');
