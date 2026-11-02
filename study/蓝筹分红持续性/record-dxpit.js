// One-shot recorder for u-e9-dxpit (family-recorder, 2026-11-01). Idempotent guard: refuses a second write.
const rq = require('../../utils/research-queue');
const FAM = '蓝筹分红持续性';
if (rq.findings(FAM).some(f => f.qId === 'u-e9-dxpit')) { console.log('already recorded'); process.exit(0); }

rq.recordFinding(FAM, {
  qId: 'u-e9-dxpit',
  type: 'understand',
  component_or_param: 'honest dividend baseline: finance.STK_XR_XD filter at L60-63 gains board_plan_pub_date <= rebalance date (null -> min(shareholders_plan_pub_date, implementation_pub_date); fully-null rows kept, 0 such rows per dxla), filter applied in SQL BEFORE order_by + limit(12); DXMON log; one asserted edit (build-dxpit.js)',
  metric_delta: 'obj 0.2352->0.2630 (Δ+0.0278); sharpe 1.81->2.02 (Δ+0.21); maxDD 15.48->14.61 (Δ-0.87pp); annual 39.00->40.91; daily corr vs base 0.9923; curve identical through 2024-08-30, first divergence 2024-09-02 (242 pts, recorder-verified from the stored curve)',
  window: 'TRAIN 2024 e9',
  finding: 'Leak IMMATERIAL by the declared rule (|Δobj| <= 0.03; Δ+0.0278 sits only 0.0022 inside the band) and its sign is the opposite of the hypothesis: the honest book scores HIGHER (2.02 vs 1.81 sharpe, lower maxDD), so the lookahead hurt the base rather than flattering it — the unannounced interim plans pulled 601229/601818 into the Sep top-5 in place of 601006/600015. Replay cross-check PASSES: dxpit DXMON n_qual and bfive equal dxla bfive_honest in all 12 months (n_qual 52/51/47/50/55/55/58/57/68/51/54/54), so the probe replay was correct. Executor-reported mechanics (base behaviour, not introduced here): from Aug the book holds 6 names, positions are never resized, and sell-outside-top5 then buy-top10-if-cash creates drift and re-buys (601006 Oct). Executor P&L reconstruction (reconciles: 367,983 price + 41,076 dividend = 409,059 = the 40.91% gain on 1M): price P&L 601229 29.8% (~31.6% with heuristically attributed dividends), 601919 26.3%, 600015 22.2%, 601169 16.1%; top-4 ~96%; 10 winners +130% offset by 6 losers -30%. Industry re-check on dxpit holdings (DXIND classification from dxla, all codes mapped): >=3 of 5 bfive in J66 金融业 in 6 of 12 months (Jan-Mar, Oct-Dec); Sep drops out (J66 2 / B06 2).',
  confidence: 'high',
  flags: 'n-small (P&L ~96% in 4 names, top-2 ~56%); regime-specific (2024 high-dividend year, one TRAIN year); ⚠零滑点高估 (minor, HS300 monthly); DXP-ERR: in-strategy P&L logger crashed every day (jqdata sum shadowing builtin) — logging only, book unaffected, P&L numbers come from the executor offline reconstruction not the logger; plan-amount final-state question (§4) still open',
  description: 'build study/蓝筹分红持续性/build-dxpit.js -> variants/dxpit.py; algorithmId ec695c55324dc20ec48ed7facda19925; curve study_蓝筹分红持续性_variants_dxpit__train__e9 (242 pts, final cum 40.91, epoch 9, train); raw log variants/dxpit.log.txt (2069 lines, 12 DXMON). Recorder verified from log+curve: 12/12 DXMON match dxla honest replay, maxDD 14.61 recomputed from curve, first divergence 2024-09-02, corr 0.9923. The 30% one-name figure is borderline: 29.8% on exact price P&L, ~31.6% only with heuristic dividend attribution.',
  implication: 'Reference-baseline swap is DONE: every later Δ (dxinv, dxpers, dxew, i-1, i-2, i-4) is measured against dxpit 0.2630 / sharpe 2.02 / maxDD 14.61, never against 94888e61; the raw base stays disqualified as a VAL candidate even though its leak moved the level only within band. The leak is real but the level does not rest on it, so the edge question moves wholly onto the ablations — dxinv/dxpers/dxew are unblocked as queued and run next. Because ~96% of P&L sits in 4 names, every later Δ is an n-small reading: a ±0.03 move can be one name entering or leaving the top-5 in one month, so each later finding must name the months/names that differ before its Δ is interpreted. i-2 precondition RE-EVALUATED on dxpit holdings and still MET (J66 >=3/5 in 6 months) -> i-2 QUEUED. i-4 stays BLOCKED: its numeric precondition (>30% one name) is borderline (29.8% exact / ~31.6% heuristic), not cleanly met, so it is gated on dxew subsumption (run only if dxew lands partial) rather than run on a borderline pass. i-1 stays BLOCKED on the dxpers verdict. Edges untouched: this was neither edge.test.',
  spawned: 'none (reopened existing: i-2-indcap blocked -> queued)',
  edgeRef: '股息率',
});

const q = rq.load(FAM);
const by = id => q.find(x => x.id === id);
const STAMP = 'recorder 2026-11-01 (u-e9-dxpit): ';
const REF = 'dxpit 0.2630 / sharpe 2.02 / maxDD 14.61 / annual 40.91';

const pit = by('u-e9-dxpit');
pit.status = 'done';
pit.result = 'IMMATERIAL leak, honest book HIGHER: 0.2352 -> 0.2630 (Δ+0.0278, inside ±0.03), sharpe 1.81 -> 2.02, maxDD 15.48 -> 14.61; corr 0.9923, diverges 2024-09-02. DXMON 12/12 equal to dxla honest replay. Now the family REFERENCE baseline. P&L ~96% in 4 names (601229 29.8% price / ~31.6% w/ dividends). algorithmId ec695c55324dc20ec48ed7facda19925, curve study_蓝筹分红持续性_variants_dxpit__train__e9.';
pit.note = STAMP + 'done. ' + (pit.note || '');

for (const id of ['u-e9-dxinv', 'u-e9-dxpers', 'u-e9-dxew']) {
  const e = by(id);
  e.status = 'queued';
  e.note = STAMP + `reference measured: ${REF}. Read every Δ against it, and name the months/names that differ (P&L ~96% in 4 names, so Δ is n-small). ` + (e.note || '');
}

const i1 = by('i-1-gxlonly');
i1.note = STAMP + `precondition (1) reference MET (${REF}). Still BLOCKED on (3) the dxpers verdict. ` + (i1.note || '');

const i2 = by('i-2-indcap');
i2.status = 'queued';
i2.note = STAMP + `QUEUED — both preconditions met: reference exists (${REF}); industry re-check on dxpit holdings shows >=3 of 5 bfive in J66 in 6 of 12 months (Jan-Mar, Oct-Dec; Sep now J66 2 / B06 2). ` + (i2.note || '');

const i4 = by('i-4-top10ew');
i4.note = STAMP + 'precondition now MEASURED but BORDERLINE: top name 601229 = 29.8% of exact price P&L, ~31.6% only with heuristic dividend attribution; top-2 ~56%, top-4 ~96%. The >30% rule is not cleanly met, so do NOT run on it — stays BLOCKED on the dxew subsumption rule (run only if dxew lands partial; if dxew >= 0.8 x ref, drop). ' + (i4.note || '');

rq.save(FAM, q);
const last = rq.findings(FAM).slice(-1)[0];
console.log('recorded', last.qId, 'epoch', last.measuredEpoch);
console.log(q.slice().sort((a, b) => a.rank - b.rank).map(e => `${e.id}\t${e.status}\trank ${e.rank}`).join('\n'));
