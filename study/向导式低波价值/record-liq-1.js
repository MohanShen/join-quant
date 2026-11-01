// recorder helper for liq-1 (one-shot). Writes the finding and marks liq-1 done.
const rq = require('../../utils/research-queue');
const FAM = '向导式低波价值';

rq.recordFinding(FAM, {
  qId: 'liq-1',
  type: 'understand',
  component_or_param: 'realizability (run dxlv-liq-1, study/向导式低波价值/variants/liq-1.py): base 8b9cb8e2 + filter_liquidity_floor (verbatim from study/大小盘轮动/build-liq.js) applied to buy_lists in trade() after the ATR entry filter, LIQ_FLOOR = 4e7 CNY/day on the trailing-20-bar MEDIAN money to previous_date = 10x the book\'s own feasibility floor (capital 1e6 / 5 slots / order_volume_ratio 0.05 = 4e6) + LIQMIN log of every held name each day',
  metric_delta: 'liq-1 29.38 / 1.19 / 10.80 / 0.1858 vs base 29.38 / 1.19 / 10.80 / 0.1858 => Δ 0 on every metric. Recorder recomputed from curves study_向导式低波价值_variants_liq-1__train__e9 vs 2026-10-29_向导式_ATR指标择时测试_0_0_1-8b9cb8e2__train__e9: 242/242 dates identical, max|Δcum| = 0 (bit-identical), final cum 29.38 both',
  window: 'TRAIN 2024',
  finding: 'INERT at 10x (decision rule R=3 met on both legs). Log re-paged by the recorder (backtest 08046ef1, 270 LIQ lines, saved as log-liq-1.txt): 25 LIQFLOOR lines (one per check date, so the floor RAN), out == in on 25/25, 0 ERROR lines; one line has in=0 out=0 (2024-10-21, the known empty refill day from u-2), the rest removedFrac 0.0000. Held-name minimum of the 20-bar median money over 2024 (LIQMIN): 600018 上港集团 8.81e7 (thinnest; 2.2x the 4e7 floor, ~22x the 1x need of 4e6), 601319 1.89e8, 601117 2.04e8, 601669 2.28e8, 601006 3.44e8, 601288 1.94e9. Execution corroboration from u-1: all 7 transactions of the base were 09:30 market orders filled in full, on HS300 large caps; no 688/STAR name can enter (the yuan ATR<0.15 gate prices them out, u-2/u-4/u-5), so the u-3 STAR protective-limit refusal does not apply to this book.',
  confidence: 'high (curve bit-identical, every LIQFLOOR line accounted for, LIQMIN minima recomputed from the full paged log)',
  flags: 'regime-specific',
  description: 'Build study/向导式低波价值/build-liq.js; variant variants/liq-1.py; log log-liq-1.txt (LIQ lines only, paged with study/小市值/pagelog.js). Scope = the BASE book 8b9cb8e2 at its own sizing (5 slots, 1e6). The floor is a decline-to-buy model, not a partial-fill model. LIQMIN covers held names only; never-held candidates are covered by out == in on all 25 LIQFLOOR lines. 2024 only: large-cap SOE turnover in 2024 is not guaranteed in other years, but at 22x headroom on the thinnest name this is not a knife-edge.',
  implication: 'CLOSES realizability for the base book: R=3 by the queue\'s pre-declared rule, written to the family page as realizability: 3 with realizabilityScope = base 8b9cb8e2. The exit gate no longer blocks on realizability; its remaining block is VAL, and §4 still orders VAL after the edge question, so the next step is u-8 (the only live edge test, 低波动), not VAL. Do not queue further liq floors (2x/20x) on this book: unimpaired capacity is roughly ¥10M+ (thinnest name 22x the 1x need), so capacity is not where this family can fail. Conditional reopen: any variant that widens the pool (drops or relaxes the yuan ATR gate, e.g. u-3/u-5/u-8 harnesses, or admits 688 names) is a different book and must re-run liq before its number is citable, and a 688-admitting book also needs protected limit orders.',
  spawned: 'none (u-8 already queued as the next step; no further liq floor needed)',
  edgeRef: '',
});

const e = rq.load(FAM);
const h = e.find(x => x.id === 'liq-1');
h.status = 'done';
h.result = 'INERT at 10x: bit-identical (max|Δcum|=0, 242 days), 25 LIQFLOOR out==in, thinnest held name 600018 min median money 8.81e7 (2.2x floor). R=3, scope base 8b9cb8e2.';
rq.save(FAM, e);
console.log(h.id, h.status);
console.log(rq.load(FAM).map(x => x.id + ':' + x.status).join(' '));
