// One-shot recorder for u-e9-dxno601229 (family-recorder, 2026-11-01). Idempotent guard: refuses a second write.
const rq = require('../../utils/research-queue');
const FAM = '蓝筹分红持续性';
if (rq.findings(FAM).some(f => f.qId === 'u-e9-dxno601229')) { console.log('already recorded'); process.exit(0); }

rq.recordFinding(FAM, {
  qId: 'u-e9-dxno601229',
  type: 'understand',
  component_or_param: 'one-name robustness diagnostic: on the reference book dxpit, 601229.XSHG (上海银行, dxpit\'s largest P&L name, 29.8% price P&L) dropped from the qualifier frame right after controlReport, before the cascade; cascade, empty-month rule, never-resize order logic verbatim; DXNO + DXMON logs; one asserted edit (build-dxno601229.js). HINDSIGHT BY CONSTRUCTION — the name was chosen because it was the top earner; diagnostic, never a candidate',
  metric_delta: 'vs dxpit: obj 0.2630->0.2554 (Δ-0.0076); sharpe 2.02->2.00 (Δ-0.02); maxDD 14.61->14.81 (Δ+0.20pp, 2024-05-29 -> 09-11 vs ref 05-29 -> 09-13); total 40.91->40.35; daily corr 0.9876 (recorder recompute from both stored curves, 242 pts, final cum 40.35 — match the executor)',
  window: 'TRAIN 2024 e9',
  finding: 'NOT-ONE-NAME by the declared ordered rule, clause (a): Δobj -0.0076 >= -0.05 AND sharpe 2.00 >= 1.0. Binding check PASSES: DXNO in_qual=1 in 12/12 months (601229 qualified every month and was removed every month); dxpit held 601229 in bfive 10/12 months and the variant bfive differs from dxpit in exactly those 10 months, each by ONE name (ref_overlap 4); Jun and Sep identical (overlap 5, the two months dxpit did not hold it). Replacements (recorder tally of DXMON in=): 601328 交通银行 Mar/Apr/Nov, 601169 北京银行 May/Dec, 601009 南京银行 Jan, 601166 兴业银行 Jul, 600015 华夏银行 Aug, 000895 双汇 Feb, 601006 大秦铁路 Oct — 8 of 10 slot-months filled by another bank, 2 by a steady non-bank payer. Monthly (var vs ref, recorder-recomputed): small and two-signed — wins Jan 10.83/9.80, Sep 17.77/15.90 (Sep identical holdings: path/drift effect), Feb/Apr +0.1; loses Dec 4.37/5.50, May 10.76/11.36, Nov 2.69/3.14, Oct/Jul/Mar ~-0.3; Aug equal. Secondary readings (reported, not voted): (i) RANK-MARGIN survives — 0.2554 > dxew basket 0.1952, margin +0.0602 vs dxpit\'s +0.0678 (~89% retained); (ii) this Δobj is 3.1% of i-1-gxlonly\'s -0.2484 and 4.6% of i-2-indcap\'s -0.1642 (arithmetic ratios, not a decomposition; those removed 601229 for 7 months, this for 12). 0 ERROR lines.',
  confidence: 'medium',
  flags: 'HINDSIGHT-DIAGNOSTIC (name selected ex post as the top earner — never a candidate, never a ledger/§3 number); regime-specific (2024 红利/中特估 year, one TRAIN year); n-small (removes one name only — 601919 / 600015 / 601169, the other ~68% of P&L, untested); replacement set is itself banks, so this does NOT separate yield from sector; ⚠零滑点高估 (minor, HS300 monthly)',
  description: 'build study/蓝筹分红持续性/build-dxno601229.js -> variants/dxno601229.py; algorithmId 04e7fb0c3aad4bd090664d1af20a694c; curve study_蓝筹分红持续性_variants_dxno601229__train__e9 (242 pts, final cum 40.35, epoch 9, train; orchestrator- and recorder-verified); raw log variants/dxno601229.log.txt (12 DXNO, 12 DXMON, 0 ERROR). Recorder verified: final cum, maxDD and its dates, corr 0.9876, monthly returns from both stored curves; in_qual / overlap / replacement names tallied from the log. Executor listed the replacements without 601006 (Oct) — minor correction, conclusion unchanged.',
  implication: 'CLOSES the §4 one-name gap ("how much of Δ is 601229 alone", 升级 item) on this bench: the family\'s level does not rest on one bank — with 601229 never eligible the cascade fills its slot with the next high-persistence bank and keeps 97% of obj, so do not re-propose a 601229 / single-name exclusion control without a new reason. CORRECTS the reading of i-1-gxlonly and i-2-indcap recorded earlier ("a large share of Δ may be one name"): losing 601229 costs ~0.008, i.e. 3-5% of their Δs, so their losses come from WHAT REPLACED it — i-1: one-off/cyclical high-TTM payers (600039, 601699, 601225, 002555); i-2: the gxl3-order bank choice plus 601006 — and therefore the two mechanism readings stand STRENGTHENED: persistence (gate + cascade) and selection among banks via rank matter, not one stock. The rank\'s margin over the dxew basket survives (~89%), so the top-5 rank is not a one-name artefact either. VAL consequence: a VAL on dxpit would test a RULE, not a stock — this removes the strongest objection to spending the family\'s one validation on it; it remains gated on liq-1 (realizability unmeasured, which BLOCKS). Does not touch yield-vs-sector (replacements are banks) and does not test the other three concentrated names (601919 / 600015 / 601169) — not queued; the 8-of-10 bank substitution makes a per-name sweep low value. Edge statuses untouched: neither edge.test was run.',
  spawned: 'none',
  edgeRef: '股息率',
});

const q = rq.load(FAM);
const by = id => q.find(x => x.id === id);
const STAMP = 'recorder 2026-11-01 (u-e9-dxno601229): ';

const p = by('u-e9-dxno601229');
p.status = 'done';
p.verdict = 'informative';
p.result = 'NOT-ONE-NAME (clause a): dxpit 0.2630/2.02/14.61 -> 0.2554/2.00/14.81 (Δobj -0.0076), total 40.35; corr 0.9876. 601229 qualified 12/12, removed 12/12; bfive differs only in the 10 months dxpit held it, one name each, 8/10 replaced by another bank. Rank margin over dxew basket +0.0602 (~89% of +0.0678). Δ = 3.1% of i-1 / 4.6% of i-2 Δobj. Diagnostic (hindsight-selected), never a candidate. algorithmId 04e7fb0c3aad4bd090664d1af20a694c, curve study_蓝筹分红持续性_variants_dxno601229__train__e9.';
p.note = STAMP + 'done. ' + (p.note || '');

const l1 = by('liq-1');
if (l1) l1.note = STAMP + 'one-name objection to a dxpit VAL removed (NOT-ONE-NAME); liq-1 is now the remaining precondition before VAL. ' + (l1.note || '');

rq.save(FAM, q);
const last = rq.findings(FAM).slice(-1)[0];
console.log('recorded', last.qId, 'epoch', last.measuredEpoch);
console.log(q.slice().sort((a, b) => a.rank - b.rank).map(e => `${e.id}\t${e.status}\trank ${e.rank}`).join('\n'));
