// One-shot recorder for u-e9-dxew (family-recorder, 2026-11-01). Idempotent guard: refuses a second write.
const rq = require('../../utils/research-queue');
const FAM = '蓝筹分红持续性';
if (rq.findings(FAM).some(f => f.qId === 'u-e9-dxew')) { console.log('already recorded'); process.exit(0); }

rq.recordFinding(FAM, {
  qId: 'u-e9-dxew',
  type: 'understand',
  component_or_param: 'style-basket test (edge[0] basket-vs-rank decomposition): on the reference book dxpit, orderStock target = ALL qualifiers (persistence gate L86 unchanged), each total_value/len(target), sell anything not in target, re-weighted every month; L95 empty-month rule verbatim; cascade/bfive/bten no longer used for orders; DXEW log per month (build-dxew.js)',
  metric_delta: 'vs dxpit: obj 0.2630->0.1952 (Δ-0.0678, ratio 0.742); sharpe 2.02->1.65 (Δ-0.37); maxDD 14.61->12.30 (Δ-2.31pp, 2024-05-22 -> 09-13 vs ref 05-29 -> 09-13); total 40.91->31.82 (HS300 2024 +14.68, basket +17.1pp over it); daily corr vs ref 0.8614, vs HS300 0.8328 (ref vs HS300 0.6340) — recorder recompute from both stored curves, 242 pts, final cum 31.82, all match the executor',
  window: 'TRAIN 2024 e9',
  finding: 'PARTIAL by the declared rule (0.5 <= ratio 0.742 < 0.8). Basket held 47-68 names/month (n_target 52/51/47/50/55/55/58/57/68/51/54/54 = dxpit n_qual exactly; n_held 47-66), empty=0 all months. Monthly (basket vs ref, recorder-recomputed): the whole gap is Jan 4.54/9.80 (-5.26) and May 2.93/11.36 (-8.43) — the same two months dxinv lost, i.e. the months the top-5 coal+bank names ran; outside them the basket is NET AHEAD (~+6pp summed): better Feb 5.86/2.91, Mar -1.31/-2.25, Jul -0.85/-3.90, Aug -2.15/-2.51, Sep 18.17/15.90, Oct -3.34/-4.79; worse Apr 3.14/4.25, Jun -2.56/-2.31, Nov 1.37/3.14, Dec 3.86/5.50 (executor listed only Feb/Jul/Sep as wins). Log: 248 ERROR lines = 243 订单委托失败 (236 sub-lot resize no-ops of the monthly re-weight, 4 STAR market orders: 688303 Jul/Aug/Sep, 688036 Sep — 科创板市价单需保护价), 3 下单数量为0, 2 suspended (002736 Sep, 601211 Oct); Oct-08 carried 109.7k cash (7.8%) after failed buys, in a down month. CONFOUND (not separable from this run): sizing also changed — the basket is re-weighted to equal every month, while the reference never resizes and drifts (sell-outside-top5 / buy-if-not-held) — so Δ mixes selection (top-5 vs all qualifiers) with sizing (drift vs monthly EW).',
  confidence: 'medium',
  flags: 'regime-specific (2024 红利/中特估 year, one TRAIN year — style basket vs 2024 rally not separable); SIZING-CONFOUND (monthly re-weight vs never-resize drift); n-small on the reference side (ref P&L ~96% in 4 names, gap in 2 months); EXECUTION-QUIRK (STAR market orders rejected 4x Jul-Sep, Oct 7.8% cash); ⚠零滑点高估 (larger for the basket: ~55 names re-weighted monthly vs 5)',
  description: 'build study/蓝筹分红持续性/build-dxew.js -> variants/dxew.py; algorithmId fbb76c2ed75a6dca112fffbdfee917e3; curve study_蓝筹分红持续性_variants_dxew__train__e9 (242 pts, final cum 31.82, epoch 9, train, benchCum 14.68); raw log variants/dxew.log.txt (287 lines, 12 DXEW). Recorder verified: final cum, maxDD 12.30 and its dates, corr 0.8614/0.8328/0.6340, monthly returns from both stored curves; error breakdown from the log.',
  implication: 'Answers the open half of 股息率\'s claim: the persistence-gated qualifier pool, held as an equal-weight ~55-name basket, beats HS300 by ~17pp with LOWER drawdown, so the family\'s return is NOT HS300 beta — but most of it (~74% of obj) is the "persistent high-dividend payer" style basket itself, which on one 2024 year cannot be told apart from the 红利/中特估 style premium. The top-5 rank adds ~0.07 obj on top, earned in Jan/May only (sector months, same as dxinv). Read with dxinv and dxpers, the attribution is now: GATE carries most (dxpers -0.46 when removed), the basket of gate-passers carries ~0.20 of the 0.26 level, the RANK is a smaller increment concentrated in two months. Consequences: (1) i-4-top10ew becomes eligible by its own subsumption rule (dxew partial) -> QUEUED; but dxew is a full-breadth point at Δobj -0.068 and ΔmaxDD -2.31, so i-4\'s adopt rule (ΔmaxDD <= -2pp AND Δobj >= -0.01) needs top-10 to keep almost all of top-5\'s return while buying most of the basket\'s drawdown cut — expect REFUTE unless the Jan/May names sit in ranks 1-5 only; i-4 must keep the reference\'s never-resize order logic so its Δ is breadth, not sizing. (2) The sizing confound is unresolved: a monthly-EW top-5 control would split selection from sizing; not queued (it changes the reference book, and the Jan/May attribution already points at selection). (3) Candidate selection: the dxew book is a fewer-knob alternative (no cascade, no top-N) at sharpe 1.65 >= 1.0 gate and maxDD 12.30 — lower fit-surface than dxpit and likely better capacity (~55 names), so it is a legitimate VAL candidate to weigh against dxpit once realizability is measured; it needs protective-price orders for STAR names. (4) Integration: the basket corr with HS300 is 0.83 vs dxpit 0.63 — the rank is what makes this family less index-like; a merge using the basket form diversifies less. VAL still not due: realizability unmeasured, i-1/i-2 open.',
  spawned: 'none new (unblocked existing: i-4-top10ew blocked -> queued)',
  edgeRef: '股息率',
});

const q = rq.load(FAM);
const by = id => q.find(x => x.id === id);
const STAMP = 'recorder 2026-11-01 (u-e9-dxew): ';

const p = by('u-e9-dxew');
p.status = 'done';
p.result = 'PARTIAL (ratio 0.742): dxpit 0.2630/2.02/14.61 -> 0.1952/1.65/12.30, total 31.82 vs HS300 14.68 (+17.1pp); corr ref 0.8614, HS300 0.8328 (ref-HS300 0.6340). Gap entirely Jan (4.54 vs 9.80) + May (2.93 vs 11.36); basket net ahead elsewhere. 47-68 names/month. Confound: monthly EW re-weight vs reference never-resize drift. STAR market orders rejected 4x (688303 Jul-Sep, 688036 Sep). algorithmId fbb76c2ed75a6dca112fffbdfee917e3, curve study_蓝筹分红持续性_variants_dxew__train__e9.';
p.note = STAMP + 'done. ' + (p.note || '');

const i4 = by('i-4-top10ew');
i4.status = 'queued';
i4.note = STAMP + 'subsumption rule MET — dxew landed PARTIAL (0.742 x ref), so per this entry\'s own rule i-4 runs (the borderline >30% one-name precondition is superseded by the dxew gate, as recorded at dxpit). -> QUEUED. Reading set by dxew: full breadth gave Δobj -0.0678 / ΔmaxDD -2.31pp, with the whole gap in Jan/May (top-5 coal+bank months). The adopt rule (ΔmaxDD <= -2pp AND Δobj >= -0.01) therefore needs top-10 to keep nearly all of top-5\'s Jan/May return while getting most of the basket\'s drawdown cut — report which months/names differ. ⚠ Keep the reference\'s never-resize order logic (sell outside bten, buy missing at total_value/10, no monthly re-weight) so the Δ is breadth only — dxew confounded breadth with monthly re-weighting. Use protective-price orders if a 688 name enters bten. ' + (i4.note || '');

rq.save(FAM, q);
const last = rq.findings(FAM).slice(-1)[0];
console.log('recorded', last.qId, 'epoch', last.measuredEpoch);
console.log(q.slice().sort((a, b) => a.rank - b.rank).map(e => `${e.id}\t${e.status}\trank ${e.rank}`).join('\n'));
