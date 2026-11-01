// Recorder input for 价值红利多腿 q-e9-liq-1 + q-e9-liq-2 (epoch 9). Run from repo root.
const rq = require('../../utils/research-queue');
const FAM = '价值红利多腿';
const REF = 'study/价值红利多腿/variants/q-e9-orphan-fix.py';

rq.recordFinding(FAM, {
  qId: 'q-e9-liq-1',
  type: 'probe',
  component_or_param: 'liquidity feasibility floor LIQ_FLOOR = 1e6×0.25/0.05 = 5e6 CNY/day (20-bar median money ending previous_date), one filter_liquidity_floor call per sleeve on the CANDIDATE list before the top-N cut (511010 exempt, holdings not exempt); on the reference ' + REF,
  metric_delta: 'obj 0.1369→0.1369 / sharpe 1.35→1.35 / annual 33.87→33.87 / maxDD 20.18→20.18; max|Δcum| 0 over 242 days',
  window: 'TRAIN 2024 e9',
  finding: 'INERT, bit-identical to the reference: max|Δcum| = 0 on all 242 days (stored curve final 33.87 verified). 81 LIQFLOOR lines, every one in==out, 0 names removed: s1 24 calls (2–3 candidates), s2 24 calls (4–12), s3 24 calls (3), s4 9 calls (34–45). No exception-path hits; all 124 pick lines identical to the control; the same 19 511010 sub-lot order failures as the control (so they are not a liquidity artefact).',
  confidence: 'high',
  flags: '⚠零滑点高估; single-year SE≈1; 2024-inside-author-view (posted 2026-05-12); headroom of kept names above 5e6 not logged (only removals are)',
  description: 'variant study/价值红利多腿/variants/liq-1_floor-5e6.py built by build-liq.js (reference + helper + exactly 4 call lines, asserted). Control = q-e9-orphan-fix row 0.1369 / 1.35 / 33.87 / 20.18. Log study/价值红利多腿/log-q-e9-liq-1.txt. Curve data/series/study_价值红利多腿_variants_liq-1_floor-5e6__train__e9.json (242 pts, final 33.87).',
  implication: 'REFUTES R=1 for this book by measurement: at its own position size (¥1M, 25% per sleeve, order_volume_ratio 0.05) the feasibility floor removes nothing, so the level is not funded by untradeable names. That made the 5× point (q-e9-liq-2) the discriminating run per the gatekeeper condition — liq-1 alone cannot tell R=2 from R=3. Because headroom above 5e6 was not logged, liq-1 says nothing about how close any kept name sat to the floor; capacity is read from liq-2 only. Not an edge test — no edge status changes.',
  spawned: 'q-e9-liq-2 (condition met: liq-1 inert → active)',
  edgeRef: 'none',
});

rq.recordFinding(FAM, {
  qId: 'q-e9-liq-2',
  type: 'probe',
  component_or_param: 'same builder, LIQ_FLOOR = 1e6×0.25×5/0.05 = 2.5e7 CNY/day (≈ ¥5M capital at these weights); only the literal moves; on the reference ' + REF,
  metric_delta: 'obj 0.1369→0.1219 (−0.0150) / sharpe 1.35→1.31 (−0.04) / annual 33.87→32.97 / maxDD 20.18→20.78 (+0.60); max|Δcum| 0.92pp (2024-12-26)',
  window: 'TRAIN 2024 e9',
  finding: 'NEAR-INERT under the pre-registered rule (|Δobj| 0.0150 ≤ 0.03, sharpe 1.31 ≥ 1.0). Curve identical through 2024-08-30, diverges 2024-09-02, max|Δcum| 0.92pp on 12-26; final 32.97 (stored curve verified). Removed (name: 20-day median money): s2 8 — 603551 ×5 Jan–Apr (~1.96–2.42e7), 605099 ×2 Jun (~1.45–1.59e7), 002884 ×1 09-02 (1.75e7); s3 4 — 600731 09-02 (8.35e6), 603366 10-08 (1.91e7), 600356 ×2 12-02/12-16 (~2.0–2.2e7); s1 0, s4 0. Only ONE pick changed all year: s2 on 2024-09-02 (000333,002555,002884 → 000333,002555,601168); every s3 removal was below that sleeve\'s top-1, and the s2 removals before September were outside its first 3. No sleeve emptied (minimum left: s1 2, s2 4, s3 2, s4 34).',
  confidence: 'high',
  flags: '⚠零滑点高估; single-year SE≈1 (the whole Δ is one s2 swap — not a capacity slope); 2024-inside-author-view (posted 2026-05-12); the floor models declining an unfillable name, not partial fills',
  description: 'variant study/价值红利多腿/variants/liq-2_floor-2.5e7.py built by build-liq.js --floor "1e6 * 0.25 * 5 / 0.05". Control = q-e9-orphan-fix row. Log study/价值红利多腿/log-q-e9-liq-2.txt. Curve data/series/study_价值红利多腿_variants_liq-2_floor-2.5e7__train__e9.json (242 pts, final 32.97).',
  implication: 'SETS realizability = 2 (written to the family page in this write, realizabilityScope = ' + REF + '), clearing the exit gate\'s unknown-realizability block. R=3 is NOT earned: the 10× point (5e7/day) is unmeasured and not queued, and at 5× the floor already reaches s2/s3 mid-caps trading ¥15–25M/day — so capacity is ≥ ~¥5M at these weights and s2/s3 are where it binds; s1 (mega-cap) and s4 (CSI500, 34+ candidates) never bind. The −0.0150 must not be read as a capacity slope: it is one s2 name swap on 09-02. Any variant that re-weights toward s2/s3 or loosens their screens (dvl-imp-2, a s3-led integration candidate) moves capacity in the binding direction and should re-run liq-2 before its R is cited. With R=2 set, the remaining exit-gate step is the VAL decision — a judgement on the honest reference, not a queued experiment.',
  spawned: 'none (R=2 recorded in frontmatter; next gate step is the VAL decision, not an idea)',
  edgeRef: 'none',
});

const q = rq.load(FAM);
const set = (id, f) => { const e = q.find(x => x.id === id); if (!e) throw new Error('no ' + id); f(e); };
set('q-e9-liq-1', e => {
  e.status = 'done';
  e.result = 'INERT, bit-identical (max|Δcum| 0): 81 LIQFLOOR lines in==out, 0 removed, all 124 picks identical, same 19 511010 sub-lot failures ⇒ R=1 refuted. Run on ' + REF + '.';
});
set('q-e9-liq-2', e => {
  e.status = 'done';
  e.result = 'NEAR-INERT: 0.1219 / sh 1.31 / 32.97 / maxDD 20.78 vs 0.1369 / 1.35 / 33.87 / 20.18 (Δobj −0.0150). 12 removals (s2 8, s3 4), ONE pick changed (s2 09-02 002884→601168), no sleeve emptied ⇒ R=2; R=3 not earned (5e7 unmeasured). Capacity ≥ ~¥5M; binds on s2/s3 mid-caps at ¥15–25M/day.';
});
rq.save(FAM, q);
console.log('ok');
