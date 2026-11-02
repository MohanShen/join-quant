// One-shot recorder for u-e9-dxinv (family-recorder, 2026-11-01). Idempotent guard: refuses a second write.
const rq = require('../../utils/research-queue');
const FAM = '蓝筹分红持续性';
if (rq.findings(FAM).some(f => f.qId === 'u-e9-dxinv')) { console.log('already recorded'); process.exit(0); }

rq.recordFinding(FAM, {
  qId: 'u-e9-dxinv',
  type: 'understand',
  component_or_param: 'edge.test 股息率: all four sort directions flipped (L99 / L102 / L103 / L104 ascending=False -> True) on the reference book dxpit; gate, universe, month cadence, 5-name equal weight, L100-101 <20 cut, order logic untouched; DXMON log with ref_overlap (build-dxinv.js)',
  metric_delta: 'vs dxpit: obj 0.2630->0.1093 (Δ-0.1537); sharpe 2.02->0.92 (Δ-1.10); maxDD 14.61->14.34 (Δ-0.27pp); total 40.91->25.27 (HS300 2024 +14.68); daily corr 0.6954 executor / 0.6983 recorder recompute (242 pts, final cum 25.27, maxDD 14.35 from curve)',
  window: 'TRAIN 2024 e9',
  finding: 'Rank half of 股息率 CONFIRMED by the declared rule (Δsharpe -1.10 <= -0.5). Binding verified from the log: bfive differs 12/12 months with 0/5 overlap every month, bten also fully disjoint (0/10 every month), n_qual identical to dxpit all 12 months, the L100-101 <20 truncation never fires (n_qual min 47). Holdings differ by sector, not only by yield: reference = coal + banks (601229 上海银行 10 months, 600188 兖矿 9, 000983 山西焦煤 8, 601166 兴业 6, 601006 / 600016 4); inverted = insurers / brokers / industrials (601336 新华保险, 600176 中国巨石, 000157 中联重科, 601601 中国太保, 601211 国泰君安). Monthly (inv vs ref, recorder-recomputed from curves): the gap is made in Jan +0.43 vs +9.80, May -0.17 vs +11.36, Nov -1.99 vs +3.14 (~-26pp together); the inversion WINS Sep +22.88 vs +15.90 (the Sep-24 rally, financials beta) and is flat Jul/Aug (+0.84 / -0.07) while ref fell (-3.90 / -2.51). Drawdown is NOT what the rank buys: maxDD is equal (14.34 vs 14.61). The low-yield end still beat HS300 by ~10.6pp (25.27 vs 14.68).',
  confidence: 'medium',
  flags: 'regime-specific (2024 红利/中特估 year, one TRAIN year); SECTOR-CONFOUNDED (high-yield end = coal+banks, low end = financials-beta / cyclicals — the rank and the sector are the same split here); n-small (5 names, gap concentrated in 3 months); ⚠零滑点高估 (minor, HS300 monthly)',
  description: 'build study/蓝筹分红持续性/build-dxinv.js -> variants/dxinv.py; algorithmId 9468ba3c7c3a302da48610cceea1ee6b; curve study_蓝筹分红持续性_variants_dxinv__train__e9 (242 pts, final cum 25.27, epoch 9, train); raw log variants/dxinv.log.txt (12 DXMON, ref_overlap=0 every month). Recorder verified: 12/12 bfive and bten disjoint from dxpit DXMON, n_qual equal 12/12, maxDD 14.35 and monthly returns recomputed from both stored curves, HS300 benchCum 14.68.',
  implication: '股息率 edge -> MEASURED, scoped to the rank half: within qualifiers the high-yield end beat the low-yield end in 2024, so the top-5 selection is doing work and a rank-free design (pure style basket) cannot be assumed equivalent. It does NOT separate yield from sector — the two ends of the rank are coal+banks vs insurers/brokers/cyclicals — so the next two runs carry the attribution: i-2-indcap (<=2 per industry) is now the yield-vs-sector test as well as a concentration tweak — if capping banks/coal costs sharpe >= the dxinv gap, the edge is substantially SECTOR, and the evidence line must be re-scoped (not left reading as a pure yield claim); u-e9-dxew answers the remaining half of the claim (basket vs index: the inverted book still beat HS300 by ~10.6pp, so the qualifier pool itself carries return the rank does not explain). Drawdown is closed as a rank benefit on this bench (ΔmaxDD -0.27pp), so any risk argument for the rank must come from i-2 or dxew, not from re-running this. Integration consequence: 股息率 is now measured in both this family and 红利低频, so edge-redundancy will flag the pair regardless of correlation (different universes: 宽基大盘 vs 全A). VAL still not due: realizability unmeasured and dxpers/dxew open.',
  spawned: 'none (re-scoped existing: i-2-indcap now also carries the yield-vs-sector attribution; u-e9-dxew carries the vs-index half)',
  edgeRef: '股息率',
});

const q = rq.load(FAM);
const by = id => q.find(x => x.id === id);
const STAMP = 'recorder 2026-11-01 (u-e9-dxinv): ';

const inv = by('u-e9-dxinv');
inv.status = 'done';
inv.result = 'CONFIRM rank (Δsharpe -1.10 <= -0.5): dxpit 0.2630/2.02/14.61 -> 0.1093/0.92/14.34; bfive 0/5 and bten 0/10 overlap all 12 months, n_qual identical, <20 cut never fires. SECTOR-CONFOUNDED: ref = coal+banks, inverted = insurers/brokers/cyclicals. Gap in Jan/May/Nov; inversion won Sep. maxDD unchanged. Inverted still beat HS300 (25.27 vs 14.68). algorithmId 9468ba3c7c3a302da48610cceea1ee6b, curve study_蓝筹分红持续性_variants_dxinv__train__e9.';
inv.note = STAMP + 'done. ' + (inv.note || '');

const ew = by('u-e9-dxew');
ew.note = STAMP + 'dxinv CONFIRMED the rank half (0.1093 vs ref 0.2630). dxew now carries the remaining half of edge[0] (basket vs HS300 beta): report HS300 2024 = +14.68 beside it; note the inverted low-yield book already beat HS300 by ~10.6pp, so a high dxew is expected and does NOT by itself contradict the rank result. ' + (ew.note || '');

const i2 = by('i-2-indcap');
i2.note = STAMP + 'now ALSO the yield-vs-sector attribution for 股息率: dxinv\'s rank split coincides with a sector split (coal+banks vs insurers/brokers/cyclicals). In the finding, report Δsharpe against the dxinv gap (-1.10): a cap that costs most of that gap says the edge is substantially sector, and the 股息率 evidence line must be re-scoped. Decision rule unchanged. ' + (i2.note || '');

rq.save(FAM, q);
const last = rq.findings(FAM).slice(-1)[0];
console.log('recorded', last.qId, 'epoch', last.measuredEpoch);
console.log(q.slice().sort((a, b) => a.rank - b.rank).map(e => `${e.id}\t${e.status}\trank ${e.rank}`).join('\n'));
