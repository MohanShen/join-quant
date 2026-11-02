// One-shot recorder for i-1-gxlonly (family-recorder, 2026-11-01). Idempotent guard: refuses a second write.
const rq = require('../../utils/research-queue');
const FAM = '蓝筹分红持续性';
if (rq.findings(FAM).some(f => f.qId === 'i-1-gxlonly')) { console.log('already recorded'); process.exit(0); }

rq.recordFinding(FAM, {
  qId: 'i-1-gxlonly',
  type: 'improve',
  component_or_param: 'cascade collapsed: on the reference book dxpit, L102-103 (gxl2 head(40) / gxl3 head(20) passes) deleted, so qualifiers are ranked by gxl only (gxl head(10) -> bten, head(5) -> bfive); L86 persistence gate, universe, month cadence, 5-name equal weight, empty-month rule and order logic untouched; one asserted edit (build-gxlonly.js)',
  metric_delta: 'vs dxpit: obj 0.2630->0.0146 (Δ-0.2484); sharpe 2.02->0.89 (Δ-1.13); maxDD 14.61->23.17 (Δ+8.56pp, 2024-05-29 -> 09-11 vs ref 05-29 -> 09-13); total 40.91->24.63 (HS300 2024 +14.68); daily corr 0.8413 recorder recompute / 0.8419 executor (242 pts, final cum 24.63, maxDD 23.17 — match)',
  window: 'TRAIN 2024 e9',
  finding: 'REFUTE of the hypothesis ("gxl2/gxl3 add nothing") by the declared rule (Δobj -0.2484 <= -0.03). Binding verified from the log: n_qual identical to dxpit all 12 months (52/51/47/50/55/55/58/57/68/51/54/54 — gate untouched), bfive differs 12/12 months, ref_overlap 1,1,1,2,2,1,2,2,3,4,4,4 (drifting back toward the reference from Sep). Name-months entering bfive (recorder count vs ref_bfive): 600039 四川路桥 8, 601699 潞安环能 8, 601225 陕西煤业 4, 000001 平安银行 4, 600188 3, 002555 三七互娱 3, 601088 2; leaving: 601229 上海银行 7, 601006 大秦铁路 4, 601166 3, 000895 双汇 3, then 600015 / 600585 / 601169 / 601328 / 601818 / 000651 2 each. So the gxl-only rank swaps the steadiest payers (banks, 大秦, 双汇) for coal/cyclical/one-off high-TTM payers — the same direction as dxpers, smaller. Note 601229 is the reference book\'s largest P&L name (29.8% price P&L) and is out of bfive 7 of 12 months here. Monthly (var vs ref, recorder-recomputed): wins Jan 12.56/9.80, Feb 6.35/2.91, Sep 20.30/15.90; loses the other 9 (Mar -4.34/-2.25, Apr 3.06/4.25, May 6.91/11.36, Jun -6.62/-2.31, Jul -6.58/-3.90, Aug -3.82/-2.51, Oct -8.30/-4.79, Nov 2.49/3.14, Dec 4.13/5.50). Drawdown sits in the SAME window as the reference (peak 05-29) but is 8.56pp deeper — unlike dxpers, whose drawdown started 2.5 months early. Still beats HS300 (24.63 vs 14.68). 0 ERROR lines: no failed orders, no STAR names entered.',
  confidence: 'medium',
  flags: 'regime-specific (2024 红利/中特估 year, one TRAIN year); n-small (5 names; 601229 alone — the reference\'s 29.8% P&L name — is out 7/12 months, so a large share of Δ may be one name); attribution vs dxpers is ARITHMETIC (Δ ratio), not a decomposition — the gate and cascade interact; ⚠零滑点高估 (minor, HS300 monthly)',
  description: 'build study/蓝筹分红持续性/build-gxlonly.js -> variants/gxlonly.py; algorithmId 2a932a684f23299d71332ef2536df600; curve study_蓝筹分红持续性_variants_gxlonly__train__e9 (242 pts, final cum 24.63, epoch 9, train); raw log variants/gxlonly.log.txt (12 DXMON, 0 ERROR). Recorder verified: n_qual / overlap from DXMON, entering/leaving counts from bfive vs ref_bfive, corr / maxDD window / monthly returns recomputed from both stored curves, HS300 benchCum 14.68.',
  implication: 'CLOSES "simplify the cascade to a single TTM-yield rank" as an improve direction on this bench — the gxl2/gxl3 passes are load-bearing, not removable knobs, so the simpler book is NOT preferred and no fewer-knob variant should drop them without a new reason. CORRECTS the attribution written at dxew ("GATE carries most"): with the gate kept and only the cascade removed the book already gives back -0.2484 of dxpers\'s -0.4612 (~54%, arithmetic, not a decomposition), so the persistence effect is split roughly evenly between the gate (which persistent payers QUALIFY) and the cascade (re-ranking qualifiers by 2- and 3-years-ago yield, i.e. persistence of the yield LEVEL, not merely clearing the gate). 分红持续性 is therefore STRENGTHENED in exactly its claimed two-part form (gate + cascade): append as supporting evidence; status stays measured (this did not run the edge\'s stated test). The plausible channel is the same dividend-trap shape as dxpers (gxl alone promotes one-off/cyclical high payers over steady ones); that mechanism argument survives a bench change, the -0.25 magnitude does not (one year, n-small, possibly one name — 601229). Consequences: (1) i-2-indcap and i-4-top10ew must keep the cascade verbatim — a variant that also touches it confounds with this result; (2) for integration, the "persistence" component is gate AND cascade together — a merge that keeps the 3-year gate but ranks by TTM yield (红利低频-style) should be expected to lose about half the effect; (3) the dxew basket (no cascade) is not contradicted: it drops the rank entirely, a different change from replacing it with gxl. VAL still not due: realizability unmeasured, i-2/i-4 open.',
  spawned: 'none',
  edgeRef: '分红持续性',
});

const q = rq.load(FAM);
const by = id => q.find(x => x.id === id);
const STAMP = 'recorder 2026-11-01 (i-1-gxlonly): ';

const p = by('i-1-gxlonly');
p.status = 'done';
p.verdict = 'rejected';
p.result = 'REJECTED (REFUTE: Δobj -0.2484 <= -0.03): dxpit 0.2630/2.02/14.61 -> 0.0146/0.89/23.17, total 24.63 (HS300 14.68); corr 0.8413. Gate untouched (n_qual identical), bfive differs 12/12 (overlap 1,1,1,2,2,1,2,2,3,4,4,4). In: 600039, 601699, 601225, 000001, 002555; out: 601229 (7/12), 601006, 601166, 000895. Wins Jan/Feb/Sep only. ~54% of dxpers\'s -0.4612 -> cascade carries about half of the persistence effect. 0 failed orders. algorithmId 2a932a684f23299d71332ef2536df600, curve study_蓝筹分红持续性_variants_gxlonly__train__e9.';
p.note = STAMP + 'done/rejected. ' + (p.note || '');

for (const id of ['i-2-indcap', 'i-4-top10ew']) {
  const e = by(id);
  if (e && e.status === 'queued') e.note = STAMP + 'keep the gxl->gxl2->gxl3->gxl cascade VERBATIM — i-1 measured it load-bearing (removing it alone: Δobj -0.2484), so any edit to it confounds this variant\'s Δ. ' + (e.note || '');
}

rq.save(FAM, q);
const last = rq.findings(FAM).slice(-1)[0];
console.log('recorded', last.qId, 'epoch', last.measuredEpoch);
console.log(q.slice().sort((a, b) => a.rank - b.rank).map(e => `${e.id}\t${e.status}\trank ${e.rank}`).join('\n'));
