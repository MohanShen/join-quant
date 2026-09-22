// Records the round's research consumption event. The VAL row (validate / dbdx-VAL-base-e6) was
// written by the executor itself; validated_strategies/dbdx-base-e6.py is the archive copy.
//   node -e "require('./study/打板短线/archive.js')"
require('../../utils/consumption').record({
  key: '打板短线', kind: 'family', stage: 'research', runId: 'run-family-2026-09-22', outcome: 'done',
  note: '6 epoch-6 TRAIN/sub-window backtests (~75 JQ min; the JQ day counter rolled over mid-round) + 1 VAL (~16 min); '
    + '3 zero-cost findings + 7 measured + VAL; 6 epoch-2 findings synced to §6 and promoted to same-bench (baseline-e6 reproduces epoch 2 digit for digit: obj 0.9668 / annual 129.24 / sharpe 2.58 / maxDD 32.56, pins no-op); '
    + 'INSTRUMENT BUG: 3 epoch-6 ledger rows (4cce4058 3.9626, 51f7b3ab 3.2999, a7f60565 2.7094) were the authors\' header-comment numbers scraped from the Ace editor text; repaired from the stats endpoint to -0.1472 / -0.0314 / -0.1472, wiki blocks repaired, executor now hides the editor before reading; '
    + 'e6-dup: 4cce4058 = a7f60565 = 69ca427f = 5175b18b (one curve), the family holds 2 code behaviours in that lineage; '
    + 'edge: 涨停动量延续 measured (near-miss control -10% vs +442% in 2022, same turnover, win 70->49%, payoff 2.28->1.02); '
    + 'u-2023 (zero-cost): 2023 machine still turns (94 trades, 61% win) but the fat tail vanished; u-rzq-deconf: the 弱转强 leg is ~1/3 of terminal wealth, the 2022-H1 fat tail AND the whole 2023-H2 loss, resizing inert; '
    + 'u-barprice: MarketOrderStyle(0.01) identical to the anchor -> price argument discarded on the daily bench (repo-level); '
    + 'improve: imp-1 dropped by arithmetic, imp-2 dropped (u-2023), imp-3 breadth gate rejected (-0.12; four positive half-years, 2022 -44%), imp-4 no-leg rejected (-0.41); '
    + 'VAL spent on the base: obj 4.2002 / annual 464.40 / sharpe 7.48 / maxDD 44.38, pass; every year first-half fat tail / second-half fade (4/4); VAL overlaps the author\'s design window (post published 2026), zero-slippage limit-up fills, 5% volume pin binds late. '
    + 'Ledger still has no row for base 439385b4 (pending-normalize) — normalize should measure it first',
});
console.log('recorded research event for 打板短线');
