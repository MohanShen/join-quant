// Recorder input for 价值红利多腿 q-e9-orphan-fix (epoch 9). Run from repo root.
const rq = require('../../utils/research-queue');
const FAM = '价值红利多腿';

rq.recordFinding(FAM, {
  qId: 'q-e9-orphan-fix',
  type: 'probe',
  component_or_param: 'virtual sub-ledger reconciliation after 送转: reconcile_sub_holdings(context) at the end of daily_init syncs g.sub_holdings to the real position (single holder = real; multi-holder pro rata), logging ORPHANSYNC/ORPHANREAL; on the reference q-e9-s4-pit',
  metric_delta: 'obj 0.1217→0.1369 (+0.0152) / sharpe 1.32→1.35 (+0.03) / annual 32.93→33.87 / maxDD 20.76→20.18 (−0.58); derived s3 16.69pp of book (49.3% of net), own ¥250k 66.76% / sharpe 1.94 / maxDD 20.90',
  window: 'TRAIN 2024 e9',
  finding: "BINDS, NOT MATERIAL under the pre-registered rule (|Δobj| 0.0152 < 0.03). On 2024-08-15 s3 sells 78,000 600368 (control sold 60,000 and left 18,000 held to 12-31). Exactly ONE ORPHANSYNC line: 2024-06-20 s3 600368 60000→78000; no ORPHANREAL and no other corporate action in any sleeve. Curve identical through 2024-08-14, diverges 08-15, max gap 3.04pp on 11-07; final 33.87 (stored curve verified). s1/s2/s4 trades byte-identical to control; s3 same names and dates, sizes ~30% larger from 08-15 (the 18,000 shares' proceeds reinvested). Order failures 39→19 (the December 511010 sub-lot fallback failures are gone). Derived s3 = fixed − q-e9-s1-only − q-e9-div-only is VALID (every ORPHANSYNC is s3-tagged; it matches the pre-fix s3-only curve within 0.05pp through 08-14): 16.69pp of ¥1M = 49.3% of 33.87 net; on own ¥250k 66.76% / sharpe 1.94 / maxDD 20.90 ⇒ 价值因子（破净） SUPPORTED by its pre-registered rule (≥25% of net AND own sharpe ≥1.0). ρ(daily) vs pbm-e9-2: fixed book 0.4650, derived s3 0.2986; derived s3 vs fixed book 0.6876.",
  confidence: 'high',
  flags: 'single-name-event (601677 ≈22% of book net); single-year SE≈1 (|Δsharpe| 0.03 is noise — binding is read from the log); 2024-inside-author-view (posted 2026-05-12); 零滑点 bench',
  description: 'variant study/价值红利多腿/variants/q-e9-orphan-fix.py built by build-orphan-fix.js (q-e9-s4-pit.py + helper + one call line, asserted). Control = q-e9-s4-pit row 0.1217 / 1.32 / 32.93 / 20.76. Log paged by dump-orphan-fix.js → log-q-e9-orphan-fix.txt; checks orphan-fix-check.js; derived s3 + ρ orphan-fix-curves.js. Curve data/series/study_价值红利多腿_variants_q-e9-orphan-fix__train__e9.json (242 pts, final cum 33.87).',
  implication: "CORRECTS q-e9-pb-only: its '~55% of s3 P&L is an orphan artefact; ex-orphan ~7.2pp of book' was WRONG and must not be cited. The 10送3 shares are compensation for the ex-date price adjustment, so the bug MISATTRIBUTED P&L (stranded 18,000 shares idle and unmanaged) rather than inflating it — fixing it RAISES s3 (15.74→16.69pp of book) instead of halving it. The old row is left as written; this finding supersedes its derived numbers (page §2/§4/edge evidence struck with a pointer here). ADOPTS per the declared rule: q-e9-orphan-fix.py is now the family REFERENCE base, control 0.1369 / sharpe 1.35 / annual 33.87 / maxDD 20.18 — q-e9-liq-1 (now active), q-e9-liq-2, q-e9-free-subsets (unblocked, zero-cost, recompute on this curve) and q-e9-s2-order must mutate/read this build, never q-e9-s4-pit. 价值因子（破净）'s test is run and SUPPORTED on the honest book, but status stays `proposed`: the name is not in wiki-schema §2.3's canonical table, so promotion to measured is blocked only on registering it (a schema edit, not more experiments). Integration reading strengthens: s3 is more orthogonal to what 全A ships once fixed (0.2986 vs pbm-e9-2, was 0.3574), so any integration candidate from this family is s3-led. Library-level: any other virtual-sub-ledger book (g.sub_holdings-style) is exposed to the same 送转 stranding, and its sleeve attribution is wrong until reconciled.",
  spawned: 'q-e9-liq-1 (unblocked → active); q-e9-free-subsets (unblocked); repoints q-e9-liq-2, q-e9-s2-order, dvl-imp-2 to the fixed reference',
  edgeRef: '价值因子（破净）',
});

const q = rq.load(FAM);
const set = (id, f) => { const e = q.find(x => x.id === id); if (!e) throw new Error('no ' + id); f(e); };
const REF = 'study/价值红利多腿/variants/q-e9-orphan-fix.py';
set('q-e9-orphan-fix', e => {
  e.status = 'done';
  e.result = "BINDS, NOT MATERIAL (|Δobj| 0.0152<0.03): 08-15 s3 sells 78,000 600368; one ORPHANSYNC (06-20 s3 60000→78000). 0.1369 / sh 1.35 / 33.87 / maxDD 20.18 vs 0.1217 / 1.32 / 32.93 / 20.76. Derived s3 49.3% of net, own sh 1.94 ⇒ 破净 SUPPORTED by rule (status proposed: name unregistered). CORRECTS q-e9-pb-only's '~7.2pp ex-orphan' (wrong: shares compensate the ex-date adjustment). ADOPTED AS REFERENCE BASE: " + REF;
});
const refNote = ` [2026-11-01 q-e9-orphan-fix] REFERENCE BASE is now ${REF} (control 0.1369 / sharpe 1.35 / annual 33.87 / maxDD 20.18); build on it, never q-e9-s4-pit.`;
set('q-e9-liq-1', e => { e.status = 'active'; e.note = 'UNBLOCKED (q-e9-orphan-fix done).' + refNote; });
set('q-e9-liq-2', e => { e.note = (e.note || '') + refNote + ' Still blocked on q-e9-liq-1 being inert/near-inert.'; });
set('q-e9-free-subsets', e => { e.status = 'queued'; e.note = 'UNBLOCKED (q-e9-orphan-fix done); NO BACKTEST.' + refNote + ' The pre-fix s1+s3 numbers (sharpe 1.28 / maxDD 9.82 / obj ≈0.132) are SUPERSEDED — recompute every subset by subtraction on the fixed curve (derived s3 = fixed − s1-only − div-only; valid because all ORPHANSYNC lines are s3-tagged). Information only, not a book choice.'; });
set('q-e9-s2-order', e => { e.note = (e.note || '') + refNote; });
set('dvl-imp-2', e => { e.note = (e.note || '') + refNote; });
rq.save(FAM, q);
console.log('ok');
