// Records the round's research consumption event (idempotent by key+stage+runId).
//   node -e "require('./study/ETF溢价/archive.js')"
require('../../utils/consumption').record({
  key: 'ETF溢价', kind: 'family', stage: 'research', runId: 'run-family-2026-09-23', outcome: 'done',
  note: '8 epoch-6 TRAIN backtests + 1 VAL (~23 JQ min: used 123 -> ~146); '
    + 'q-ledger (zero cost): member edd94ebc has NO ledger row anywhere (not in the tsv, any .bak, deferred, series-scan or pending-normalize) and its page has no normalized: block -> the §3 DQ/— is a lost row, not a DQ; normalize should re-queue it; '
    + 'baseline-e6: base 15c36e0c obj 1.5642 (epoch 2) -> 0.8607 (annual 177.88 -> 105.37 / sharpe 5.93 / maxDD 19.30): the 5% participation cap on a 2e6-share floor, capacity not signal; both years positive, 2023 stronger; '
    + 'u-1 REALIZABILITY DECISIVE: same 09:30 signal filled at 14:50 -> +321% becomes +10% (sharpe 0.07): the whole return is the auction-open print; '
    + 'u-2: dropping LOF raises obj 0.8607 -> 1.6193 (annual +69pp, maxDD -6.8): the LOF leg is a drag, closes the CLAUDE.md LOF-NAV-lag question (no fake-discount profit; LOF discounts persist, ETF discounts revert via in-kind creation); adopted as ep-imp-0; '
    + 'u-3 mirror (buy highest premium) -99% total, 20% up-days -> 均值回归 measured; '
    + 'u-4 liquid floor 1e8: annual 33.7 / sharpe 1.04 (DQ), reproduces the epoch-2 reading -> 流动性溢价 measured, refined by ep-imp-1 (floor 1e7 on ETF-only: obj +0.054, adopted-marginal; the return lives in 1e7-1e8 shares, the epoch-2 sweet spot was a no-cap capacity illusion); '
    + 'ep-imp-2 top-2 rejected (-0.58 vs ETF-only: fill width under the cap, the epoch-2 N=2 peak is gone); '
    + 'ep-imp-3 realizable form (close signal + close fill, 1m read at 14:50 works on the daily bench) rejected: -53% / maxDD 54, both years negative -> no realizable candidate exists; '
    + 'VAL spent on ep-imp-1: 2024-25 annual 214.16 / sharpe 7.60 / maxDD 13.01 (obj 2.0115, above TRAIN 1.6733); '
    + 'both edges shared with PT多策略 at status measured -> edge-redundancy will flag the pair; recommend status DQ-realizability (human call); integration must cite u-4 (34%/1.04), never the headline',
});
console.log('recorded research event for ETF溢价');
