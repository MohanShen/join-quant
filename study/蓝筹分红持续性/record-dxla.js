// One-shot recorder for u-e9-dxla (family-recorder, 2026-11-01). Idempotent guard: refuses a second write.
const rq = require('../../utils/research-queue');
const FAM = '蓝筹分红持续性';
if (rq.findings(FAM).some(f => f.qId === 'u-e9-dxla')) { console.log('already recorded'); process.exit(0); }

rq.recordFinding(FAM, {
  qId: 'u-e9-dxla',
  type: 'understand',
  component_or_param: 'log-only lookahead probe: second finance.run_query(STK_XR_XD) beside L60-63 (same code filter, report_date <= statDate, limit 16) selecting board/shareholders/implementation pub dates + a_bonus_date + plan_progress; honest replay filters board_plan_pub_date <= rebalance date BEFORE the 12-row cut; logs DXLA/DXFLIP/DXMON/DXCNT + DXG5/DXIND/DXPOS; no logic edit',
  metric_delta: 'obj 0.2352->0.2352 (Δ0); 39.00 / 1.81 / 15.48; curve bit-identical to base (242 pts, max|Δcum|=0, orchestrator-verified); 0 DXREP (replica == g.bfive/g.bten every month)',
  window: 'TRAIN 2024 e9',
  finding: 'LEAK CONFIRM (rule a). 1064 DXLA rows (= sum of DXCNT dxla_rows over 12 rebalances; 1048 with non-zero bonus) counted by the book carry some date > current_dt. Strict subset: 47 rows (46 non-zero) whose board_plan_pub_date ITSELF is after the rebalance — 2024-05-06 1, 09-02 13, 10-08 7, 11-01 15, 12-02 11 — i.e. 2024 interim / Q3 plans counted as soon as the interim/Q3 statDate exists (report_date <= statDate bounds the PERIOD, not the announcement). The other 1017 rows had a public board plan with only shareholders / implementation / payment stages in the future (581 share+impl+pay, 362 impl+pay, 59 pay, 15 share). BINDS (rule b): DXFLIP = 4 (600926 Sep+Oct, sums 530343->308375; 000568 Nov+Dec, 994873->794873; all book=1 honest=0); bfive differs in Sep (book 601229,601818 out; 601006,600015 in) and Oct (601818 -> 601328); bten differs in the same two months; Jan-Aug and Nov-Dec bfive/bten identical. 601229 and 601818 ranked top-5 in Sep only via 2024 interim plans not yet announced (601229 interim 397787 board 2024-09-30; 601818 interim 614490 board 2024-10-31, still future on 10-08). Empty-month rule (n_qual <= 10) never fires: n_qual_book min 47 (Mar), max 69 (Sep), 0 empty months book and honest. Free precondition logs: DXG5 gxl-only top-5 differs from the cascade bfive in 12/12 months (overlap 1-4 of 5); DXIND over 60 name-months J66 金融业 30, B06 采矿业 18, >=3 of 5 in J66 in 7 months (Jan-Mar, Sep-Dec); DXPOS per-name P&L is NOT recoverable from the log (position values exclude cash dividends, Dec period unlogged, naive reconstruction recovers only 128k of the 317k gain to 2024-12-02).',
  confidence: 'high',
  flags: 'LOOKAHEAD (data-API, finance.STK_XR_XD report-period bound, not announcement bound); regime-specific (2024 interim-dividend wave); ⚠零滑点高估 (minor at HS300 monthly); plan amounts/progress may be final-state values (not testable from this table)',
  description: 'build study/蓝筹分红持续性/build-dxla.js -> variants/dxla.py; algorithmId 131f9d6384c2f0c5a1755d75e2dcc7c3; curve study_蓝筹分红持续性_variants_dxla__train__e9; raw log variants/dxla.log.txt (14 pages, 1291 lines, state=2). Control bit-identical, so logged values are the book own inputs. Executor reported 989 non-zero future rows; recount from the log gives 1048 non-zero of 1064 — the 1064 and the 47-row strict subset agree. Same class as 银行股轮动 u-e9-dyla, narrower (period-bounded, binds 2 of 12 months vs every week).',
  implication: 'OPENS u-e9-dxpit: it is now REQUIRED (precondition CONFIRM+BINDS met) and its book becomes the reference baseline for every later Δ (dxinv / dxpers / dxew / i-1 / i-2 / i-4); the raw base 94888e61 must never be the VAL candidate, because its Sep/Oct holdings were chosen with unannounced 2024 interim plans. Expect a small level move (2 of 12 months, path effects aside) — dxpit decides it by its declared ±0.03 rule; a near-zero Δ still does not relicense the base. CLOSES the empty-month question for this bench: with n_qual >= 47 in every 2024 month the L95 rule is inert on TRAIN, so u-e9-dxpers carries no empty-month confound on the reference side and i-3-relthr (precondition n_qual <= 15 or an empty month) is dropped — re-open only on a window where n_qual approaches 10 (check VAL 2025 logs first). Preconditions: i-1 MET (DXG5 differs 12/12), i-2 MET (J66 >=3/5 in 7 months; re-check Sep on dxpit, where honest bfive is J66 2 / B06 2), i-4 NOT MEASURABLE from this log — needs an end-of-period position log with dividends attributed, or defer to dxew per its subsumption rule. Edge status untouched: this was not either edge.test.',
  spawned: 'u-e9-dxpit (blocked -> queued, now head of queue); i-3-relthr dropped',
  edgeRef: '股息率,分红持续性',
});

const q = rq.load(FAM);
const by = id => q.find(x => x.id === id);
const STAMP = 'recorder 2026-11-01 (u-e9-dxla): ';

const dxla = by('u-e9-dxla');
dxla.status = 'done';
dxla.result = 'LEAK CONFIRM + BINDS. 1064 counted rows with a future date (47 with board_plan_pub_date > rebalance: May 1, Sep 13, Oct 7, Nov 15, Dec 11). DXFLIP 4 (600926 Sep/Oct, 000568 Nov/Dec); bfive+bten differ Sep, Oct. Empty-month rule inert (n_qual min 47). Control bit-identical. algorithmId 131f9d6384c2f0c5a1755d75e2dcc7c3, curve study_蓝筹分红持续性_variants_dxla__train__e9.';

const pit = by('u-e9-dxpit');
pit.status = 'queued';
pit.rank = 1;
pit.from = pit.from.map(s => s === 'u-e9-dxla (pending)' ? 'u-e9-dxla (CONFIRM + BINDS)' : s);
pit.note = STAMP + 'precondition MET (CONFIRM: 47 rows with board_plan_pub_date after the rebalance; BINDS: DXFLIP 4, bfive/bten differ Sep+Oct). QUEUED, head of queue. Cross-check: dxpit DXMON bfive must equal dxla bfive_honest in Jan-Aug and Nov-Dec exactly; Sep/Oct may differ only through path (held names), not through the qualifier set — n_qual_honest should read 68 (Sep) / 51 (Oct) / 54 (Nov, Dec). ' + (pit.note || '');

for (const id of ['u-e9-dxinv', 'u-e9-dxew']) {
  const e = by(id);
  e.note = STAMP + 'reference book is RESOLVED: the u-e9-dxpit book (dxla CONFIRM+BINDS), never the raw base. Runs after dxpit. ' + (e.note || '');
}
const pers = by('u-e9-dxpers');
pers.note = STAMP + 'reference = u-e9-dxpit book. Empty-month confound: reference side has 0 empty months (dxla n_qual min 47, base and honest replay); this variant loosens the gate so n_qual only rises — the confound is empty unless the variant logs an empty month. ' + (pers.note || '');

const i1 = by('i-1-gxlonly');
i1.note = STAMP + 'precondition (2) MET: DXG5 gxl-only top-5 differs from the cascade bfive in 12/12 months (overlap 1-4 of 5). Still BLOCKED on (1) dxpit reference and (3) dxpers verdict. ' + (i1.note || '');

const i2 = by('i-2-indcap');
i2.note = STAMP + 'precondition MET on the base: >=3 of 5 bfive in J66 金融业 in 7 of 12 months (Jan-Mar, Sep-Dec); 60 name-months J66 30 / B06 18, so a cap of 2 binds. On the honest replay Sep reads J66 2 / B06 2 — re-check from dxpit DXMON. Still BLOCKED on the dxpit reference. STK_COMPANY_INFO is current classification (mild hindsight). ' + (i2.note || '');

const i3 = by('i-3-relthr');
i3.status = 'dropped';
i3.result = 'DROPPED by precondition: dxla n_qual_book min 47 (Mar) / max 69, 0 empty months on base and honest replay — the absolute gate never approaches the L95 line in 2024, so a relative gate tests nothing on this bench. Re-open only on a window where n_qual approaches 10.';
i3.note = STAMP + 'dropped (precondition unmet, see result). ' + (i3.note || '');

const i4 = by('i-4-top10ew');
i4.note = STAMP + 'precondition NOT MEASURABLE from dxla: DXPOS logs position value at main() entry only — cash dividends land in cash, the Dec period is unlogged, and a naive buy/sell/DXPOS reconstruction recovers only 128k of the 317k gain to 2024-12-02, so no >30% one-name claim can be made either way. Holdings are dominated by 601229 / 600188 / 000983 / 601166 by frequency, not by measured P&L. Stays BLOCKED; resolve via dxew subsumption (run only if dxew is partial) or add an end-of-period + dividend log to the dxpit run. ' + (i4.note || '');

rq.save(FAM, q);
const last = rq.findings(FAM).slice(-1)[0];
console.log('recorded', last.qId, 'epoch', last.measuredEpoch);
console.log(q.map(e => `${e.id}\t${e.status}\trank ${e.rank}`).join('\n'));
