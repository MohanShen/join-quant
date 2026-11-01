// recorder helper for q-e9-atr-attrib (2026-11-01). Run once; recordFinding appends.
const rq = require('../../utils/research-queue');
const FAM = '突破ATR趋势跟踪';
rq.recordFinding(FAM, {
  qId: 'q-e9-atr-attrib',
  type: 'understand',
  component_or_param: 'per-ETF P&L attribution from the base run 5e3c1028 own 开仓/卖出 log lines (no edit, no run)',
  metric_delta: 'net logged P&L 285,736 (gross wins 352,988); top-1 37.8%, top-2 70.7%; 9/25 entries 84.6% of net; 0 backtest-min',
  window: 'TRAIN 2024-01-01..2024-12-31 e9',
  finding: 'Re-paged log of the ledger run 5e3c1028 (log end equity 1,284,494.51 = 28.45%, so the control holds by construction; logged P&L exceeds ledger by 1,241 = fees + open-vs-fill, immaterial). Per-ETF net P&L of 285,736: 510300 +108,060 (37.8%, 4 trades), 510500 +94,012 (32.9%), 518880 gold +67,449 (23.6%), 513100 Nasdaq +26,160 (9.2%), 159915 +22,568 (7.9%, 1 trade), 512880 证券 -32,513 (-11.4%, 2 losing trades opened 4/29 and 11/06, NOT held in Sep). Pre-declared rule: REFUTE branch (3 names >=15%: 510300/510500/518880); no single name >50%. The three 2024-09-25 entries (510300 151,400 sh ≈528k; 510500 96,700 sh ≈469k; 159915 36,400 sh ≈59k) made +241,716 = 84.6% of net, all exited 10/09-10/10 on the ATR trailing stop; the first two consumed ~99.7% of capital, so 159915 (+38% move) got ~6% of the book. Gold + Nasdaq = 32.8% of net, all earned outside Sep.',
  confidence: 'high',
  flags: 'regime-specific (single TRAIN year; one event = 84.6% of net); author-in-sample (posted 2026-09-12)',
  description: 'study/突破ATR趋势跟踪/attrib.js over study/突破ATR趋势跟踪/atr-log-base.txt (full re-paged log of the existing epoch-9 normalize run). Free route, no control run needed.',
  implication: 'Concentration is in TIME (one 9/25 event), not in one NAME, so the single-name-hindsight reading is closed for 2024. (1) 证券 is not the hidden driver: it LOST money and was not held in Sep, so atr-imp-512100 stays dropped and its re-propose condition is settled NO (removing 证券 would only be TRAIN pool-tuning, not a hindsight test). (2) q-e9-atr-pool-broad must be read as "does the book survive losing gold+Nasdaq, the only non-Sep earners (32.8% of net)": expect Sep roughly unchanged (510300/510500 stay) and the rest of the year worse, so the monthly split decides it, not the pooled sharpe. (3) Pool-order cash starvation is now measured on the base itself (the third 9/25 signal got ~6% of capital vs ~33% under equal 1/3 slots), which raises atr-imp-cap-third from low-information to the most informative improve test, and is direct evidence for edge[2] (择时 = 现金储备/集中开关) although it did not run that claim\'s test.',
  spawned: 'none',
  edgeRef: '布林上轨突破（时序动量）',
});
const q = rq.load(FAM);
const add = (id, txt) => { const e = q.find(x => x.id === id); e.note = (e.note ? e.note + ' ‖ ' : '') + txt; };
add('q-e9-atr-pool-broad', 'recorder 2026-11-01 (q-e9-atr-attrib): 证券 lost -32,513 in 2024 and was not held in Sep, so this run is NOT a 证券-hindsight test. What it removes that matters is gold+Nasdaq = 32.8% of net, the only earners outside Sep; 510300/510500 (70.7% of net, the 9/25 legs) stay. Expect Sep ≈ unchanged and the rest of the year worse; read by the monthly split and pre-declare the non-Sep comparison.');
add('atr-imp-cap-third', 'recorder 2026-11-01 (q-e9-atr-attrib): cash starvation measured on the base: on 9/25 510300+510500 took ~99.7% of capital and 159915 (+38% move) got ~6% (36,400 sh ≈59k); equal 1/3 slots would have given it ~33%. Now the most informative improve test; gatekeeper may rank it up. Report 9/25 share counts per ETF.');
add('atr-imp-512100', 'recorder 2026-11-01 (q-e9-atr-attrib): re-propose condition settled NO. 证券 is not the Sep driver (not held in Sep) and lost -32,513 in 2024, so dropping it is TRAIN pool-tuning, not a hindsight test. Stays dropped.');
rq.save(FAM, q);
console.log(q.find(e => e.id === 'q-e9-atr-attrib').status);
