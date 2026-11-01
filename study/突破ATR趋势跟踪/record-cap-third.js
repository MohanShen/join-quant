// Recorder helper for atr-imp-cap-third (2026-11-01). Run once:
//   node -e "require('./study/突破ATR趋势跟踪/record-cap-third.js')"
const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '..', '..');
const rq = require(path.join(ROOT, 'utils/research-queue'));
const FAM = '突破ATR趋势跟踪';

if (rq.findings(FAM).some(f => f.qId === 'atr-imp-cap-third')) { console.log('already recorded'); return; }

rq.recordFinding(FAM, {
  qId: 'atr-imp-cap-third',
  type: 'improve',
  component_or_param: 'L51 MAX_POSITION_PCT 0.50 -> 1.0/3 (one asserted edit); entries/exits/regime/pool verbatim',
  metric_delta: 'obj 0.2007->0.1926 (Δ-0.0081); sharpe 1.54->1.28 (Δ-0.26, <SE≈1); annual 28.45->31.06 (+2.61); maxDD 8.38->11.80 (+3.42pp); same 13 trades',
  window: 'TRAIN 2024-01-01..2024-12-31 e9',
  finding: "Capping each position at 1/3 instead of 50% lowers sharpe 1.54->1.28 and objective 0.2007->0.1926 while RAISING annual 28.45->31.06 and maxDD 8.38->11.80. The 13 trades are identical in dates, symbols and exit reasons - only sizes change; the 1/3 cap binds on almost every entry and the 2%-risk size binds once. On 2024-09-25 capital is 510300 528k->344k, 510500 469k->344k, 159915 59k->341k; Sep P&L 241,716->281,252 (159915 22,568->130,448), Sep return 23.20->27.38 (+4.18). Other months move little: Mar -1.05, Apr -0.98, Nov +1.03. Per ETF, 159915 rises from 7.9% to 42.3% of net and the Sep share of net from 84.6% to 91.3%. Log end equity 1,310,571.49 = 31.06%, so the curve and log agree. Pre-declared rule: refute (Δsharpe <= 0) holds.",
  confidence: 'medium',
  flags: 'regime-specific (single TRAIN year; Sep = 91.3% of net in the variant); author-in-sample (posted 2026-09-12); |Δsharpe| 0.26 inside SE≈1, decided by the pre-declared sign rule plus the 9/25 share counts',
  description: "study/突破ATR趋势跟踪/build-cap-third.js -> variants/atr-imp-cap-third.py; log atr-log-cap-third.txt; curve study_突破ATR趋势跟踪_variants_atr-imp-cap-third__train__e9. Control = base e79e9884 epoch-9 ledger row (0.2007/1.54/28.45/8.38). Queue entry named edgeRef 布林上轨突破; the result bears on edge[2], recorded there.",
  implication: "Position-cap sizing is CLOSED as an improve lever on this bench: removing the cash starvation works as described (equal slots give the starved third signal a third of the book), but that only puts MORE of the book into the single 9/24 event and raises maxDD, so it trades sharpe for concentration. No cap value between 1/3 and 1/2 is worth a run. Re-propose conditions that depended on this cap now fail: the gatekeeper allowed atr-imp-regime-ashare back ONLY combined with a winning cap-third, and there is none, so it stays dropped. For edge[2] (择时 = 现金储备/集中开关) this is supporting evidence that sizing decides how much of the September event is captured, but it did not run that claim's test, so the claim stays proposed and its own test (always-offensive + liquidate when the regime turns back) is still the next step. Any improve idea that adds return by sizing up the 9/25 entries should be expected to fail the same way.",
  spawned: 'none',
  edgeRef: '大盘择时 = 现金储备/集中开关',
});

const qf = path.join(ROOT, 'study', FAM, 'queue.json');
const q = JSON.parse(fs.readFileSync(qf, 'utf8'));
const r = q.find(e => e.id === 'atr-imp-regime-ashare');
if (r) {
  r.note = (r.note ? r.note + ' ‖ ' : '') + "recorder 2026-11-01 (atr-imp-cap-third): the re-propose condition (combine with a WINNING cap-third) is settled NO - cap-third was rejected (sharpe 1.54->1.28). Stays dropped.";
}
fs.writeFileSync(qf, JSON.stringify(q, null, 2) + '\n');
console.log('cap-third status:', q.find(e => e.id === 'atr-imp-cap-third').status);
