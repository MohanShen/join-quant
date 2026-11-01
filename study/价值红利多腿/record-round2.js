// Recorder input for 价值红利多腿: q-e9-free-subsets, q-e9-s2-order, dvl-imp-2 (epoch 9). Run from repo root.
const rq = require('../../utils/research-queue');
const FAM = '价值红利多腿';
const REF = 'study/价值红利多腿/variants/q-e9-orphan-fix.py';

rq.recordFinding(FAM, {
  qId: 'q-e9-free-subsets',
  type: 'ablation',
  component_or_param: 'sleeve-subset table on the reference q-e9-orphan-fix by exact curve subtraction (book on ¥1M); s2/s4 split from q-e9-div-only tabs; zero backtest',
  metric_delta: 'full 33.87/1.35/20.17/obj 0.1370/ρpbm 0.4650; s1+s3 23.98/1.33/9.13/0.1485/0.4594; s3 16.69/1.37/5.57/0.1112/0.3286; minus-s4 (s1+s2+s3) 31.43/1.52/11.12/0.2031/0.4835; minus-s2 26.42/1.19/19.01/0.0741/0.4535; s2 7.45/0.55/4.79/0.0266/0.3893; s4 2.44/−0.15/13.10/−0.1066/0.2105 (total% / sharpe / maxDD / obj / ρ vs pbm-e9-2)',
  window: 'TRAIN 2024 e9',
  finding: 'VALID: the formula reproduces JQ on the full book (33.87 / sharpe 1.354 / maxDD 20.17), and the s2/s4 split rebuilt from q-e9-div-only tabs reproduces their own-capital sharpes 1.15 / 0.16 exactly (residual ≤0.005pp). Pre-registered reading: s1+s3 vs full Δsharpe −0.02 against the +1.0 bar ⇒ dividend legs NOT shown harmful on sharpe, but they DOUBLE maxDD (9.13→20.17). s4 is the drawdown source: minus-s4 Δsharpe +0.17 (inside SE≈1), maxDD 20.17→11.12, obj 0.1370→0.2031; s4 alone book-level sharpe −0.15. Dropping s2 instead lowers sharpe (1.35→1.19). s3 alone is the only subset with sharpe ≥1.0 (1.37) AND ρ<0.35 vs pbm-e9-2 (0.3286).',
  confidence: 'high',
  flags: 'single-year SE≈1; sleeve selection on TRAIN = cheapest overfit available; 2024-inside-author-view (posted 2026-05-12); ρ(s3) 0.3286 here vs 0.2986 in q-e9-orphan-fix for the same derived leg — unreconciled, both <0.35; 零滑点 bench',
  description: 'study/价值红利多腿/free-subsets.js over data/series/study_价值红利多腿_variants_{q-e9-orphan-fix,q-e9-s1-only,q-e9-div-only}__train__e9.json + div-only tabs; enhance_candidates_pbm-e9-2__train__e9 for ρ. No backtest.',
  implication: "CLOSES sleeve-subset selection as a candidate route on this bench: minus-s4 (obj 0.2031, sharpe 1.52) and s1+s3 are information only — choosing legs on one TRAIN year inside a 2026-05-12 author's view is selection, and every Δsharpe here is inside SE≈1, so no subset book is to be built, archived or VAL'd from this table. The page's 股息率 edge.test is now read EXACTLY on the honest reference (s2=s4=0 ⇒ Δsharpe −0.02 vs support bar ≤ −1.0) and fails ⇒ 股息率 flipped to refuted in this write. Integration: the family's only leg clearing sharpe ≥1.0 with ρ<0.35 vs pbm-e9-2 is s3 (破净), and 破净 is already what 破净价值多因子 ships inside pbm-e9-2 — so this family adds no NEW mechanism to 全A; an s3-led integration candidate would be a second implementation of a shipped edge and is not queued. Supersedes §4's pre-fix subset numbers (s1+s3 sh 1.28 / maxDD 9.82).",
  spawned: 'none',
  edgeRef: '股息率',
});

rq.recordFinding(FAM, {
  qId: 'q-e9-s2-order',
  type: 'ablation',
  component_or_param: "s2's final cut [:3] → [-3:] of the unsorted get_fundamentals list (≈ code order) + log-only S2LEN; on the reference q-e9-orphan-fix; s1/s3/s4 trade lines byte-identical (141 lines)",
  metric_delta: 'book 0.1369→0.0719 (−0.0650) / sharpe 1.35→1.06 (−0.29) / total 33.87→28.26 / maxDD 20.18→21.07; s2 own ¥250k first-3 29.79% / sh 1.15 / maxDD 16.14 → last-3 7.35% / sh 0.12 / maxDD 23.41 (−75% return)',
  window: 'TRAIN 2024 e9',
  finding: "REFUTED-AS-ARBITRARY under the pre-registered rule (s2 P&L moves by more than half: −75%). Not vacuous: S2LEN on 24 rebalances is 4–12 (median ~7), ≤3 on 0/24; first-3 and last-3 share 8 of 72 slots. Curve diverges day 1, max gap 6.01pp; final 28.26 (stored curve verified). s1/s3/s4 trades byte-identical to the reference, so the whole Δ is s2. First-3 ≈ Shenzhen 000/002 codes, last-3 ≈ Shanghai 60x codes.",
  confidence: 'high',
  flags: 'single-year SE≈1 (sleeve read, not book Δsharpe); 3 names × 24 rebalances is a handful of events; exchange/code-prefix confound (first-3 ≈ SZ, last-3 ≈ SH); 2024-inside-author-view (posted 2026-05-12); 零滑点 bench',
  description: 'variant study/价值红利多腿/variants/q-e9-s2-order.py built by build-s2-order.js (reference + one asserted slice edit + S2LEN log line). Log dump-s2-order.js → log-q-e9-s2-order.txt; tx/pos json alongside. Curve data/series/study_价值红利多腿_variants_q-e9-s2-order__train__e9.json (final cum 28.26).',
  implication: "CLOSES 's2's level is selection skill': s2's sharpe 1.15 (the one dividend leg that looked substantive in q-e9-div-only) is a property of which 3 of a 4–12-name qualifying list the code-order cut happens to take — a different arbitrary 3 earns a quarter as much. No later round may cite s2's 1.15 as dividend-selection evidence; it counts against 股息率, not for it. Made dvl-imp-2 non-vacuous (list >3 on 24/24, cut moves P&L by >half), which is why it was run rather than dropped. Not followed with a code-prefix (SZ vs SH) test: one year of 3-name picks cannot separate an exchange effect from luck, and that question has no mechanism behind it here.",
  spawned: 'dvl-imp-2 (unblocked, run)',
  edgeRef: '股息率',
});

rq.recordFinding(FAM, {
  qId: 'dvl-imp-2',
  type: 'improve',
  component_or_param: "s2's final df sorted by dividend-yield rank (descending) before [:g.s2_stock_num]; 3-line asserted diff on the reference q-e9-orphan-fix; s1/s3/s4 byte-identical",
  metric_delta: 'book 0.1369→0.0837 (−0.0532) / sharpe 1.35→1.20 (−0.15) / total 33.87→31.33 / maxDD 20.18→22.96 (+2.78); s2 own ¥250k 19.63% / sh 0.60 / maxDD 25.28 vs reference s2 29.79% / 1.15 / 16.14',
  window: 'TRAIN 2024 e9',
  finding: 'REFUTED by its pre-registered rule (book sharpe 1.20 ≤ reference 1.35; re-scoped sleeve bar also fails, s2 0.60 < 1.15). Yield-top-3 overlaps the code-order first-3 on 33/72 slots and the last-3 on 36/72 — the yield sort lands between the two arbitrary cuts. One new sub-lot order failure (2024-10-08 002884, ¥1,895). Final 31.33 (stored curve verified).',
  confidence: 'high',
  flags: 'single-year SE≈1 (|Δsharpe| 0.15 is noise at book level; read at sleeve level); 3-name sleeve; 2024-inside-author-view (posted 2026-05-12); 零滑点 bench; not re-run through liq-2 (rejected, so its R is never cited)',
  description: 'variant study/价值红利多腿/variants/dvl-imp-2.py built by build-imp-2.js (3-line asserted diff). Log dump-imp-2.js → log-dvl-imp-2.txt; tx/pos json alongside. Curve data/series/study_价值红利多腿_variants_dvl-imp-2__train__e9.json (final cum 31.33).',
  implication: "CLOSES the yield-sort knob on s2: ranking the PEG/growth-qualified list by the dividend yield itself LOWERS the sleeve (sharpe 1.15→0.60), so within this pre-filtered top-10% yield pool the yield ORDER carries no measured information — the last route by which 股息率 could have been shown to select anything in this book. Rejected, not adopted; reference stays q-e9-orphan-fix.py. Together with q-e9-s2-order this leaves no open improve direction on s2 (any further re-ordering is a search over arbitrary cuts on one year).",
  spawned: 'none',
  edgeRef: '股息率',
});

const q = rq.load(FAM);
const set = (id, f) => { const e = q.find(x => x.id === id); if (!e) throw new Error('no ' + id); f(e); };
set('q-e9-free-subsets', e => { e.status = 'done'; e.result = 'VALID (formula reproduces JQ; s2/s4 split exact). s1+s3 Δsh −0.02 (dividend legs not shown harmful, but double maxDD 9.13→20.17); minus-s4 sh 1.52 / maxDD 11.12 (s4 = drawdown source); s3 only leg with sh ≥1.0 and ρ<0.35 vs pbm-e9-2. Information only, not a candidate. Exact edge.test ⇒ 股息率 refuted.'; });
set('q-e9-s2-order', e => { e.status = 'done'; e.result = 'REFUTED-AS-ARBITRARY: last-3 vs first-3 moves s2 −75% (29.79%/1.15 → 7.35%/0.12); S2LEN 4–12 on 24/24 (not vacuous), overlap 8/72. Book 0.0719 / 1.06 / 28.26 / 21.07. s2 level is code-order luck.'; });
set('dvl-imp-2', e => { e.status = 'done'; e.verdict = 'rejected'; e.result = 'REJECTED (pre-registered REFUTE): book 0.0837 / 1.20 / 31.33 / 22.96 (Δobj −0.0532, Δsh −0.15); s2 own sharpe 0.60 < 1.15. Yield order carries no information within the pool. Reference unchanged: ' + REF; });
rq.save(FAM, q);
console.log(q.map(e => `${e.id}\t${e.status}`).join('\n'));
