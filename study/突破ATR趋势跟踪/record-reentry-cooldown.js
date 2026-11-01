// Recorder helper for q-e9-atr-reentry-cooldown (2026-11-01). Run once:
//   node -e "require('./study/突破ATR趋势跟踪/record-reentry-cooldown.js')"
const path = require('path');
const ROOT = path.resolve(__dirname, '..', '..');
const rq = require(path.join(ROOT, 'utils/research-queue'));
const FAM = '突破ATR趋势跟踪';

if (rq.findings(FAM).some(f => f.qId === 'q-e9-atr-reentry-cooldown')) { console.log('already recorded'); return; }

rq.recordFinding(FAM, {
  qId: 'q-e9-atr-reentry-cooldown',
  type: 'understand',
  component_or_param: 'from variants/q-e9-atr-bb-ablate.py (cond4-only entry): ONE asserted insertion - record exit date per symbol in the sell path, skip re-entry on the exit day D or D+1; exits/sizing/regime/pool verbatim',
  metric_delta: 'obj 0.2361 (base 0.2007, ablate 0.1523); sharpe 1.62 (base 1.54 Δ+0.08 inside SE≈1; ablate 1.21 Δ+0.41); annual 30.98; maxDD 7.37 (base 8.38, ablate 10.20); opens 27 (base 13, ablate 34)',
  window: 'TRAIN 2024-01-01..2024-12-31 e9',
  finding: "cond4-only entry plus a no-re-entry rule on D and D+1 after an exit scores objective 0.2361, sharpe 1.62, annual 30.98, maxDD 7.37 - Δsharpe +0.08 vs base (inside SE≈1) and +0.41 vs the bb-ablate. Opens 27 vs base 13 vs ablate 34. September is 23.20 in all three books (identical 9/25 entries). Oct-Dec compounded: base -1.37, ablate -5.24, cooldown -0.87. The ablate had 10 re-entries within 1 day in Oct-Dec (8 closed, summed -28,926; e.g. 510300 re-entered 10-09, stopped 10-16 at -31,875); the cooldown had 0 (9 COOLDOWN skips in Oct-Dec, 14 in the year). Caveat: freed slots went to other ETFs (512880 10-09 -34,807, 518880 +32,276, 510500 11-08 -30,051), and realized P&L on post-9/25 entries is about equal (-46.1k cooldown vs -47.0k ablate), so part of the curve gap is year-end open positions. Pre-declared rule: first branch (sharpe >= 1.44) holds => the Bollinger conditions' measured role is anti-churn, not entry timing.",
  confidence: 'medium',
  flags: '⚠零滑点高估 (27 opens vs base 13 - zero slippage flatters the higher-turnover book, so the true +0.08 is smaller or negative); regime-specific (single TRAIN year; Sep 23.20 identical in all three books); author-in-sample (posted 2026-09-12); part of Oct-Dec gap is year-end open positions, realized P&L on post-9/25 entries ≈ equal',
  description: "study/突破ATR趋势跟踪/build-reentry-cooldown.js -> variants/q-e9-atr-reentry-cooldown.py; curve study_突破ATR趋势跟踪_variants_q-e9-atr-reentry-cooldown__train__e9 (242 points, ends 30.98). Controls: base e79e9884 epoch-9 ledger row (0.2007/1.54/28.45/8.38) and q-e9-atr-bb-ablate (0.1523/1.21/25.43/10.20).",
  implication: "Together with q-e9-atr-bb-ablate this settles edge[0]: removing the Bollinger breakout costs nothing once same-day churn is blocked, so the claim as written (the breakout event creates trend-continuation return) is REFUTED on TRAIN 2024 and flipped to refuted in this write; the breakout's only measured job is an anti-churn filter that any re-entry cooldown replaces. Consequences: (1) every improve idea that tunes BB(20,2) parameters is closed - it would tune a churn filter, not a signal; (2) the cooldown variant is NOT adopted (Δsharpe +0.08 inside SE, ~2x turnover, zero-slippage flattered) and N=5 cooldown is not worth a run, since N=1 already resolved the question; (3) the book's level is now attributed to HS300 regime turning offensive + full-size broad-ETF entries on 9/25 (one event, 84.6% of net), so the only open mechanism claim is edge[2] (择时 = 现金储备/集中开关) and its own test is the next and last understand experiment before any VAL decision. With edge[0] refuted, edge[1] refuted and edge[2] proposed, a VAL here would confirm a one-event level, not a mechanism.",
  spawned: 'none',
  edgeRef: '布林上轨突破（时序动量）',
});
console.log('cooldown status:', rq.load(FAM).find(e => e.id === 'q-e9-atr-reentry-cooldown').status);
