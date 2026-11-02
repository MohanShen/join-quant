// One-shot recorder for i-2-indcap (family-recorder, 2026-11-01). Idempotent guard: refuses a second write.
const rq = require('../../utils/research-queue');
const FAM = '蓝筹分红持续性';
if (rq.findings(FAM).some(f => f.qId === 'i-2-indcap')) { console.log('already recorded'); process.exit(0); }

rq.recordFinding(FAM, {
  qId: 'i-2-indcap',
  type: 'improve',
  component_or_param: 'industry cap <= 2 per industry_id: on the reference book dxpit, the author\'s dead cc_industry (source L185-211, inside a \'\'\' docstring, never called) un-quoted (row-append translated to index collection, same rows/order) and called ONCE on the cascade df right after the gxl3 head(20) pass, before the final gxl sort / head(10); cascade gxl -> <20 cut -> gxl2 -> gxl3 -> gxl verbatim; industry = finance.STK_COMPANY_INFO.industry_id (CSRC 2-digit, CURRENT classification); cap 2 (author\'s); dxpit obs layer replaced by DXMON/DXIND/DXINDREF/DXINDBTEN/DXDROP (build-indcap.js)',
  metric_delta: 'vs dxpit: obj 0.2630->0.0988 (Δ-0.1642); sharpe 2.02->1.12 (Δ-0.90 = 82% of dxinv\'s -1.10 gap, arithmetic); maxDD 14.61->13.72 (Δ-0.89pp, 2024-05-29 -> 09-11 vs ref 05-29 -> 09-13); total 40.91->23.61 (HS300 2024 +14.68); daily corr 0.9454 (recorder recompute from both stored curves, 242 pts, final cum 23.61, maxDD 13.72 — match the executor)',
  window: 'TRAIN 2024 e9',
  finding: 'REFUTE by the declared rule (Δsharpe -0.90 <= -0.25; adopt clause fails on both legs: ΔmaxDD -0.89pp > -2pp and Δsharpe < 0). The cap BINDS every month: the gxl3 head(20) pool shrinks 20 -> 12-15 (n_post 13/13/13/13/12/14/15/15/14/13/14/14), 77 name-months dropped of which 58 are J66 (banks); n_qual identical to dxpit (52..68); bfive differs 12/12 months (ref_overlap 3,3,3,4,3,3,3,4,4,3,3,3). industry_id is CSRC 2-digit (J66 货币金融服务 = banks only, insurers/brokers are not J66; B06 coal; G53 rail). bfive name-months by industry (variant vs ref, recorder tally of DXIND/DXINDREF): J66 18 vs 29, B06 17 vs 18, G53 11 vs 4, C13 5 vs 3, C30 3 vs 2, K70 2 vs 0, G55 2/2, C38 2/2 — i.e. effectively the 3rd/4th bank swapped for 601006 大秦铁路 (and some 000895/000002), coal nearly untouched. Mechanism: the cap keeps the FIRST 2 per industry in gxl3 order, and the final selection is by gxl after it, so which bank survives is decided by the 3-years-ago yield rank, not by current yield — and the one it drops most is 601229 上海银行, the reference\'s largest P&L name (29.8% price P&L): in variant bfive only Jan-Mar (3 months) vs 10 in the reference, out 7 months (Apr-Aug, Oct-Dec). Monthly (var vs ref, recorder-recomputed): the gap is SPREAD, not in dxinv\'s months — Jan 7.59/9.80, Mar -5.13/-2.25, Apr 2.55/4.25, Oct -6.89/-4.79, Nov 1.36/3.14, Dec 1.85/5.50 carry it; Feb/May/Sep within 0.6pp; only Jul wins (-1.58/-3.90); Jun/Aug flat. Contrast: dxinv\'s gap sat in Jan/May/Nov and it WON Sep. Still beats HS300 (23.61 vs 14.68). 0 ERROR lines (no failed orders, no STAR names).',
  confidence: 'medium',
  flags: 'regime-specific (2024 红利/中特估 year, one TRAIN year); n-small + ONE-NAME (601229 out 7/12 months — the second variant in a row, after i-1-gxlonly, whose Δ may be largely this one name); CONFOUNDED as a yield-vs-sector test (cut made in gxl3 order: Δ mixes losing a 3rd bank, WHICH bank survives, and 601229 alone); mild hindsight (STK_COMPANY_INFO current classification, tolerable for HS300 blue chips); the 82% ratio to dxinv is ARITHMETIC, not an attribution; ⚠零滑点高估 (minor, HS300 monthly)',
  description: 'build study/蓝筹分红持续性/build-indcap.js -> variants/indcap.py; algorithmId 1a43a0f2bfd0031c5a8ea5f166ed5537; curve study_蓝筹分红持续性_variants_indcap__train__e9 (242 pts, final cum 23.61, epoch 9, train; orchestrator- and recorder-verified); raw log variants/indcap.log.txt (101 lines: 12 DXMON, 12 DXIND, 12 DXINDREF, 12 DXINDBTEN, 12 DXDROP, 0 ERROR). Recorder verified: final cum, maxDD and its dates, corr 0.9454, monthly returns from both stored curves; n_post / dropped-industry / bfive industry composition / 601229 months tallied from the log.',
  implication: 'CLOSES "industry cap <= 2 as an improvement" on this bench: it costs 0.90 sharpe to buy 0.89pp of drawdown, so concentration control by industry count is not a route to a better dxpit — do not re-propose an industry cap at this call site or a looser cap number without a new reason. Does NOT answer yield-vs-sector, and that question stays OPEN: the cut is made in gxl3 (3-years-ago yield) order and removes the single best P&L name, so the Δ cannot be split between (a) losing a 3rd bank, (b) which bank survives, (c) 601229 alone; the gap is also spread across months rather than sitting in dxinv\'s Jan/May/Nov, a further sign it is not the same effect as the inversion gap. So 股息率\'s evidence must NOT be re-scoped to "sector" on this result, and must not be read as "yield, not sector" either — append the caveat, status stays measured (this was not its edge.test). A clean sector test would have to hold the bank set fixed and vary yield (e.g. a within-industry yield rank, or the cap applied AFTER the final gxl sort so it removes the lowest-current-yield bank) — not queued. STRENGTHENS the §4 one-name gap: 601229 is now the dominant explanatory candidate for two consecutive improve Δs (i-1 out 7 months, i-2 out 7 months), so a dxpit-minus-601229 control has become the cheapest single run that would tell whether the cascade / rank findings are mechanism or one bank; it should precede any further rank/selection improve. i-4-top10ew is unaffected (it keeps 601229 in ranks 1-5). VAL still not due: realizability unmeasured, i-4 open.',
  spawned: 'none',
  edgeRef: '股息率',
});

const q = rq.load(FAM);
const by = id => q.find(x => x.id === id);
const STAMP = 'recorder 2026-11-01 (i-2-indcap): ';

const p = by('i-2-indcap');
p.status = 'done';
p.verdict = 'rejected';
p.result = 'REJECTED (REFUTE: Δsharpe -0.90 <= -0.25): dxpit 0.2630/2.02/14.61 -> 0.0988/1.12/13.72, total 23.61 (HS300 14.68); corr 0.9454. Cap binds: gxl3 pool 20 -> 12-15, 58 of 77 dropped name-months J66; bfive differs 12/12 (overlap 3-4). Composition J66 29->18, B06 18->17, G53 4->11 (banks swapped for 601006). 601229 out 7 months (cut in gxl3 order). Δsharpe = 82% of dxinv gap (arithmetic) but CONFOUNDED — yield-vs-sector remains OPEN. algorithmId 1a43a0f2bfd0031c5a8ea5f166ed5537, curve study_蓝筹分红持续性_variants_indcap__train__e9.';
p.note = STAMP + 'done/rejected; yield-vs-sector NOT answered (confounded by gxl3-order cut + 601229). ' + (p.note || '');

const i4 = by('i-4-top10ew');
if (i4 && i4.status === 'queued') i4.note = STAMP + 'unaffected; reference still dxpit. 601229 explains part of both i-1 and i-2 Δs — name the 601229 months when reading this Δ. ' + (i4.note || '');

rq.save(FAM, q);
const last = rq.findings(FAM).slice(-1)[0];
console.log('recorded', last.qId, 'epoch', last.measuredEpoch);
console.log(q.slice().sort((a, b) => a.rank - b.rank).map(e => `${e.id}\t${e.status}\trank ${e.rank}`).join('\n'));
