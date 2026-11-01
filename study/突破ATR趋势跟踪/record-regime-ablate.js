// Recorder helper for q-e9-atr-regime-ablate (2026-11-01). Run once:
//   node -e "require('./study/突破ATR趋势跟踪/record-regime-ablate.js')"
const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '..', '..');
const rq = require(path.join(ROOT, 'utils/research-queue'));
const FAM = '突破ATR趋势跟踪';

const already = rq.findings(FAM).some(f => f.qId === 'q-e9-atr-regime-ablate');
if (already) { console.log('already recorded'); return; }

rq.recordFinding(FAM, {
  qId: 'q-e9-atr-regime-ablate',
  type: 'understand',
  component_or_param: "get_index_regime(): one inserted `return 'offensive'` as first statement (removes L219 defensive liquidation + L302 no-open rule); entries/exits/sizing/pool verbatim",
  metric_delta: 'obj 0.2007->0.1190 (Δ-0.0817); sharpe 1.54->1.25 (Δ-0.29, <SE≈1); annual 28.45->16.94 (Δ-11.51); maxDD 8.38->5.04 (-3.34pp, LOWER); vol 16.56->10.79; flat days 132->57; daily corr 0.785; trades 13->16, win 61.5%->50%',
  window: 'TRAIN 2024-01-01..2024-12-31 e9',
  finding: "Always-offensive regime lowers sharpe 1.54->1.25, objective 0.2007->0.1190, annual 28.45->16.94 AND lowers maxDD 8.38->5.04 (vol 16.56->10.79, flat days 132->57, corr 0.785). Monthly base/variant: Jan 0/-0.21, Feb 1.34/2.78, Mar 3.93/2.47, Apr 2.13/-1.08, May -1.72/-1.72, Jun 0/1.42, Jul 0/0.75, Aug 0/-2.43, Sep 23.20/11.39, Oct 1.45/3.80, Nov -4.43/-3.71, Dec 1.72/3.12; Jun-Aug sum ≈ -0.30, so the cash months cost nothing to sit out and gained nothing either. Opens variant(base): 510300 4(4), 518880 4(2), 513100 3(2), 512880 3(2), 510500 2(2), 159915 0(1); exits trail 9(7), MA20 5(5), stop 2(1). No regime forced-liquidation line in EITHER log - the L219 defensive exit never fired in base. Both books enter equity ETFs on 9/25, but in the variant capital was already committed under the 50% cap: 510500 got 1,000 shares vs 96,700 (+1,020 vs +98,634) and 159915 never opened; March likewise (518880 23,700 vs 106,000 shares because 513100 held capital). Pre-declared rule: support (maxDD +>=3 & sharpe ->=0.3) no - maxDD moved the opposite sign; refute (sharpe >=1.54) no; risk-only no. Lands on no branch.",
  confidence: 'medium',
  flags: 'regime-specific (single TRAIN year; Sep = 23.20 of 28.45% in base); author-in-sample (posted 2026-09-12); pre-declared rule did not anticipate the opposite-sign maxDD',
  description: "study/突破ATR趋势跟踪/build-regime-ablate.js -> variants/q-e9-atr-regime-ablate.py (one inserted `return 'offensive'`). Control = base e79e9884 epoch-9 ledger row; variant curve study_突破ATR趋势跟踪_variants_q-e9-atr-regime-ablate__train__e9 (242 points, ends 16.94).",
  implication: "edge[1] (大盘择时 is the source of the low maxDD) is REFUTED as written - removing the timing layer LOWERS maxDD and its defensive liquidation never fired - so it must not be cited as drawdown protection. Its measured role is capital allocation: by keeping the book in cash through regime-off months it leaves the 50%-capped slots free so the 9/25 broad-ETF entries get full size. Together with q-e9-atr-bb-ablate (Sep identical without Bollinger), the 2024 level is index-regime-turns-offensive + broad ETFs at full size on one event ≈ concentrated beta, not a breakout or timing mechanism. Consequence for the queue: atr-imp-regime-ashare (frees gold/Nasdaq from the regime) is now EXPECTED TO HURT September by the same cash-tie-up (this run's 513100/518880 positions are what starved 510500/159915), so the gatekeeper should reframe or rank it down before spending minutes; atr-imp-cap-third bears directly on the concentration reading and becomes the more informative improve test. A new proposed claim (择时 = 现金储备/集中开关) replaces the refuted one as the family's prior.",
  spawned: 'none',
  edgeRef: '大盘 MA20/MA60 择时',
});

const qf = path.join(ROOT, 'study', FAM, 'queue.json');
const q = JSON.parse(fs.readFileSync(qf, 'utf8'));
const r = q.find(e => e.id === 'atr-imp-regime-ashare');
if (r) {
  r.note = "recorder 2026-11-01 (q-e9-atr-regime-ablate): ungating gold/Nasdaq is now expected to HURT 2024-09 - in the always-offensive run 513100/518880 held capital under the 50% cap and starved the 9/25 broad-ETF entries (510500 1,000 vs 96,700 shares; 159915 never opened). Gatekeeper: reframe or rank down before running.";
  fs.writeFileSync(qf, JSON.stringify(q, null, 2) + '\n');
}
console.log('status:', q.find(e => e.id === 'q-e9-atr-regime-ablate').status);
