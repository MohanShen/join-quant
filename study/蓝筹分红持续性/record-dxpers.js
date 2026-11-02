// One-shot recorder for u-e9-dxpers (family-recorder, 2026-11-01). Idempotent guard: refuses a second write.
const rq = require('../../utils/research-queue');
const FAM = '蓝筹分红持续性';
if (rq.findings(FAM).some(f => f.qId === 'u-e9-dxpers')) { console.log('already recorded'); process.exit(0); }

rq.recordFinding(FAM, {
  qId: 'u-e9-dxpers',
  type: 'understand',
  component_or_param: 'edge.test 分红持续性: on the reference book dxpit, L86 gate reduced to one_year > comp_value (2% of market cap; the two_year/three_year persistence clauses and the 3y-sum >=10% clause removed) and the gxl2/gxl3 cascade passes deleted (cascade = gxl head(80) -> <20 cut verbatim -> gxl head(10) -> bten/bfive); universe, month cadence, 5-name equal weight, empty-month rule, order logic untouched; DXMON log with empty flag + ref_overlap (build-dxpers.js)',
  metric_delta: 'vs dxpit: obj 0.2630->-0.1982 (Δ-0.4612); sharpe 2.02->0.21 (Δ-1.81); maxDD 14.61->28.80 (Δ+14.19pp, 2024-03-06 -> 09-13 vs ref 05-29 -> 09-13); total 40.91->8.98 (HS300 2024 +14.68); daily corr 0.7496 (recorder recompute from both stored curves, 242 pts, final cum 8.98, maxDD 28.80 — all match the executor)',
  window: 'TRAIN 2024 e9',
  finding: 'Edge CONFIRMED by the declared ordered rule — both clauses fire (Δsharpe -1.81 <= -0.3 AND ΔmaxDD +14.19pp >= +2pp). Binding verified from the log: bfive differs 12/12 months, ref_overlap 0,0,0,0,2,1,1,2,2,3,4,3. n_qual 120..162 (executor said 127..162; Mar is 120) vs dxpit 47..68, ~2.5x wider; empty=0 in all 12 months on both books and the <20 truncation cannot fire (n_qual >= 120), so the declared empty-month confound is EMPTY. Who changed: entering names are one-off / cyclical-peak payers — 601919 中远海控 (Jan-Apr top), 601699 潞安环能 (in bfive 12/12), 688303 大全能源, 600438 通威, 601225 陕西煤业, 600039, 002555, 000408, 002271, plus 000001; leaving names are the banks / steady payers (601088, 601169, 600015, 601166, 600585, 601328, 601006, 601818). Persisting: 000983, 600188, 600016, 601229 (overlap grows to 3-4 from Oct as the variant drifts back toward banks). Monthly (var vs ref, recorder-recomputed): loses Jan 4.93/9.80, Mar -9.53/-2.25, Apr -2.92/4.25, May 6.59/11.36, Jun -6.47/-2.31, Dec 1.45/5.50; wins Feb 10.45/2.91 and Sep 21.04/15.90 (Sep-24 rally). The drawdown starts at the 03-06 peak, 2.5 months before the reference one, i.e. it is the cyclical/solar names rolling over, not the common Sep low. The variant UNDERPERFORMS HS300 (8.98 vs 14.68). EXECUTION CAVEAT: 688303 (STAR) market buy failed on 2024-01-02, 02-01 and 03-01 (订单委托失败: 科创板市价单需要保护价), so Jan-Mar the slot fell to bten fallback names and the variant book was not exactly its intended bfive; the effect is unquantified (it cannot plausibly produce a -1.81 sharpe gap — 688303 was 1 of 5 slots for 3 months, and Apr-Dec without it still lose 4 of 9 months — but it is not measured).',
  confidence: 'medium',
  flags: 'regime-specific (2024 红利/中特估 year, one TRAIN year); n-small (5 names, ref P&L ~96% in 4 names); EXECUTION-QUIRK (688303 STAR market order rejected Jan-Mar, bten fallback filled the slot, unquantified); gate and cascade removed TOGETHER (attribution between them is i-1); ⚠零滑点高估 (minor, HS300 monthly)',
  description: 'build study/蓝筹分红持续性/build-dxpers.js -> variants/dxpers.py; algorithmId 0ecbfc2c9bf9055c14d63f3d5eb76b36; curve study_蓝筹分红持续性_variants_dxpers__train__e9 (242 pts, final cum 8.98, epoch 9, train); raw log variants/dxpers.log.txt (12 DXMON, empty=0 every month; 3 ERROR lines = the 688303 rejections). Recorder verified: overlap sequence and n_qual from DXMON vs dxpit DXMON, corr 0.7496 / maxDD 28.80 2024-03-06..09-13 / monthly returns recomputed from both stored curves, HS300 benchCum 14.68.',
  implication: '分红持续性 -> REGISTERED in wiki-schema §2.3 and MEASURED, scoped to gate+cascade together on 2024: one-year yield alone (>=2%, rank by gxl) admits one-off and cyclical-peak payers — the classic dividend-trap shape — and doubles the drawdown, so the book\'s value is "persistent payers, high end", not "high trailing yield". Together with dxinv this makes the family\'s edge two-part (persistence filter + yield rank within it), and it DISTINGUISHES this family from a plain TTM-yield screen: relevant to 红利低频 (全A, 股息率 top-25% + profitability, no 3-year persistence clause) — 股息率 is shared and will flag redundancy, 分红持续性 is so far only measured here, and an integration merge that swaps this gate for a TTM-yield screen should be expected to lose. OPENS i-1-gxlonly (keep the gate, drop only the cascade): all three preconditions are now met, so it is QUEUED, and it is the attribution test — if i-1 lands within ±0.03 of dxpit, the gate is the whole selector and the cascade is a removable knob; if it loses materially, the cascade carries part of this result. Reading the entering names (all gate-excluded one-off payers) suggests the gate, but that is identity, not measurement. CLOSES "loosen the persistence gate" as an improve direction on this bench (Δobj -0.46 is far outside any noise band; do not re-propose a weaker 3-year clause without a different reason). Also exposes a realism gap: any variant admitting STAR names must use a protective-price order or the slot silently falls to the fallback. VAL still not due: realizability unmeasured, dxew and i-1 open.',
  spawned: 'none new (unblocked existing: i-1-gxlonly blocked -> queued)',
  edgeRef: '分红持续性',
});

const q = rq.load(FAM);
const by = id => q.find(x => x.id === id);
const STAMP = 'recorder 2026-11-01 (u-e9-dxpers): ';

const p = by('u-e9-dxpers');
p.status = 'done';
p.result = 'CONFIRM (both clauses: Δsharpe -1.81 <= -0.3, ΔmaxDD +14.19pp >= +2pp): dxpit 0.2630/2.02/14.61 -> -0.1982/0.21/28.80, total 8.98 < HS300 14.68; corr 0.7496. bfive differs 12/12 (overlap 0,0,0,0,2,1,1,2,2,3,4,3); n_qual 120..162 vs 47..68; empty=0 both books -> confound empty. Entering = one-off/cyclical payers (601919, 601699, 688303, 600438, 601225, ...); leaving = banks/steady payers. Caveat: 688303 STAR market buy rejected Jan-Mar (bten fallback filled, unquantified). algorithmId 0ecbfc2c9bf9055c14d63f3d5eb76b36, curve study_蓝筹分红持续性_variants_dxpers__train__e9.';
p.note = STAMP + 'done. ' + (p.note || '');

const i1 = by('i-1-gxlonly');
i1.status = 'queued';
i1.note = STAMP + 'precondition (3) MET — dxpers CONFIRMED (gate+cascade removed together: 0.2630 -> -0.1982, maxDD 14.61 -> 28.80). All three preconditions now met -> QUEUED. Reading set by dxpers: i-1 is the gate-vs-cascade ATTRIBUTION. Report its Δ beside the dxpers gap (Δobj -0.4612): within ±0.03 of dxpit => the gate is the whole selector and the cascade is removable (prefer the simpler book only with an explicit note, per the rule); a material loss => the cascade carries part of the persistence result. Watch for STAR names (688xxx) in bfive: dxpers had market buys rejected for 688303 — name any rejected order in the finding. ' + (i1.note || '');

rq.save(FAM, q);
const last = rq.findings(FAM).slice(-1)[0];
console.log('recorded', last.qId, 'epoch', last.measuredEpoch);
console.log(q.slice().sort((a, b) => a.rank - b.rank).map(e => `${e.id}\t${e.status}\trank ${e.rank}`).join('\n'));
