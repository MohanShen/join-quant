// recorder helper for u-4 (one-shot). Writes the finding, marks u-4 done, annotates the
// dependants whose premise moved (dxlv-imp-screenexit cites 低估值; u-8 is now the only live edge test).
const rq = require('../../utils/research-queue');
const FAM = '向导式低波价值';

rq.recordFinding(FAM, {
  qId: 'u-4',
  type: 'understand',
  component_or_param: 'REDESIGNED PE-band ablation (run dxlv-u-4): u-7 pool-EW harness + L232 financial_data_filter_qujian(pe_ratio,(6,11)) made a pass-through; yuan ATR_judge_xiaoyu(0.15,14) entry, HS300, industry, ST/paused/high-limit filters unchanged. Control = u-7 (pool level), NOT the 5-name base the page test originally named. This is the redesigned test of edge 低估值',
  metric_delta: 'u-4 total/annual 26.78, sharpe 1.22, maxDD 10.33, obj 0.1645 vs u-7 29.50/1.08/12.20/0.1730 => Δsharpe +0.14, Δobj -0.0085, maxDD -1.87pp; daily corr 0.9477 (242/242 days, same dates). Recomputed by the recorder from curve study_向导式低波价值_variants_u-4__train__e9 (the executor could not): final cum 26.78, maxDD 10.33 (u-7 12.21 => -1.88pp), obj (26.78-10.33)/100 = 0.1645, corr 0.9477, ann. vol 0.195 vs u-7 0.247; curve-sharpe estimator 1.17 vs 1.03 (Δ +0.14, same sign and size as JQ, inside the ±0.2 band on both)',
  window: 'TRAIN 2024',
  finding: 'BINDING (the non-binding branch did not fire): day-1 gated pool 59 names vs u-7 6, EWDEPLOY cash_after 14535.60 / total 999703.60 = 1.45% (<=5%), no 688 name (the yuan gate still prices them out), no fill problems; gate admissions per check date median 39 (min 9, max 59, 25 dates) vs u-7 median 5. Δsharpe +0.14 vs u-7, inside the pre-declared REFUTE band (|Δ| <= 0.2), far from the CONFIRM line (<= -0.5). Per-name day-1 -> 12-31 price return (dividends excluded), recomputed from log-u-4.txt: in-band PE 6-11 (n=6, exactly u-7\'s names) mean +25.95; PE 0-6 (n=21: 16 banks 600000/601229/601288/600919/601398/601009/600015/601988/601169/601939/601328/601818/601998/601658/600016/601916 + 5 construction/transport 601668/601186/601390/601618/600039) mean +31.39; PE >11 (n=27) +19.79; PE <0 (n=5) +1.76; all 59 +23.02. So the band\'s 6 sit +2.9pp above the gated-pool mean and -5.4pp below the bucket its LOWER cut excludes. Late-entry dust 9 names = 4.30% of the book at year end (u-7 2.9%). The sharpe gain is diversification (59 vs 6 names, vol 0.195 vs 0.247), the return gap (-2.7pp total) is small; both legs remain day-1 EW buy-and-holds.',
  confidence: 'high (measurement: binding shown directly, curve reproduces total/maxDD/obj/corr, JQ and curve sharpe agree); medium (scope: one day-1 cross-section in one year, 2024)',
  flags: 'regime-specific',
  description: 'Log study/向导式低波价值/log-u-4.txt (1190 lines: U4CNT per check date, U4PE per day-1 name with pe/close/inband, EWFILL, EWDEPLOY, EWFINAL); build build-u-4.js; analysis analyse-u-4.js. Breadth is NOT matched (59 vs 6), so the sharpe Δ mixes selection with diversification; the per-bucket returns are the breadth-free reading and point the same way (band ≈ pool mean, below PE<6). Dust 4.3% vs 2.9% is within the shared noise floor and too small to move a ±0.2 verdict.',
  implication: 'REFUTES 低估值 as stated (「超额来自 PE 6–11 那一端」), status proposed -> refuted in the same write, evidence [[study-u-4]], scoped exactly: within the yuan-ATR-gated HS300 pool on the 2024-01-02 cross-section, the 6-11 band adds nothing over the whole gated pool on sharpe (slightly lower obj, lower DD). Does NOT say value fails: the names BELOW the band (PE<6, mostly banks) returned the most, so a monotone low-PE tilt is untested and if anything suggested. But both band cuts are arbitrary and the excluded bucket is the 2024 bank rally that failed VAL 2025 in 银行股轮动 (0.69) and 蓝筹分红持续性 (0.09), so NO PE<6 / PE-rank improve idea is spawned here: one would need a window other than 2024 to say anything, and on TRAIN it would only re-buy that rally. Closes PE-band tuning on this book (bounds sweeps, PE sort; pesort was already dropped). With 低价股效应 (u-5) and 低估值 (u-4) both refuted, the only live claim is 低波动 (proposed, u-8): if u-8 refutes too, the family goes to kind: none-found for its specific rules, its level read as a broad 2024 HS300 low-price/low-vol large-cap SOE basket. dxlv-imp-screenexit cites a now-refuted edge and its PE half has no premise; flagged for the gatekeeper. liq-1 is now the head of the queue and still blocks the exit gate.',
  spawned: 'none (u-8 already queued as the last live edge test; no PE<6 idea by design, see implication)',
  edgeRef: '低估值',
});

const e = rq.load(FAM);
const h = e.find(x => x.id === 'u-4');
h.status = 'done';
const se = e.find(x => x.id === 'dxlv-imp-screenexit');
if (se) se.note = (se.note || '') + ' ‖ recorder 2026-11-01 after u-4: its edgeRef 低估值 is now REFUTED (u-4: removing PE 6-11 under the gate, Δsharpe +0.14). Its run condition (u-3 or u-4 selects at Δsharpe <= -0.5) is met ONLY through u-3 (price/ATR gate, -0.70), never through PE. An exit on 「leaves PE 6-11」 therefore has no premise; if the gatekeeper keeps it, it should key on leaving the ATR gate alone and re-cite 低波动 (proposed), otherwise drop.';
const u8 = e.find(x => x.id === 'u-8');
if (u8) u8.note = (u8.note || '') + ' ‖ recorder 2026-11-01 after u-4: u-8 is now the ONLY live edge test (低价股效应 refuted by u-5, 低估值 by u-4). A refute here sends the family to kind: none-found for its specific rules. ⚠ u-4 showed the band binds hard without PE (59 day-1 names, median 39 per date), so u-8 Leg B on the PE pool (21-43) is the right control; do not widen it to the gated pool.';
rq.save(FAM, e);

console.log(h.status, '|', String(h.result).slice(0, 80));
console.log(rq.load(FAM).map(x => x.id + ':' + x.status).join(' '));
