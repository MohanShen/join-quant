// gatekeeper 2026-11-01: 价值红利多腿 queue update (orphan-fix, liq-1/2, free-subsets, decisions).
// One-shot; refuses to re-apply.
const fs = require('fs');
const path = require('path');
const ROOT = path.join(__dirname, '..', '..');
const P = path.join(__dirname, 'queue.json');
const q = JSON.parse(fs.readFileSync(P, 'utf8'));
const by = id => { const e = q.find(x => x.id === id); if (!e) throw new Error('missing ' + id); return e; };
if (q.some(e => e.id === 'q-e9-orphan-fix')) throw new Error('already applied');
const REF = 'reference book after q-e9-orphan-fix (its variant if adopted per its rule; otherwise study/价值红利多腿/variants/q-e9-s4-pit.py)';

q.push({
  id: 'q-e9-orphan-fix', kind: 'understand',
  title: 'Correctness: reconcile the virtual sub-ledger with the real position after a 送转 (600368 10送3 orphan shares)',
  hypothesis: "The sub-ledger g.sub_holdings never sees 送转, so 600368's 2024-06-20 10送3 left 18,000 real shares that s3 never sells (¥85,860 at year end, ~55% of s3 P&L). BINDS if, in the fixed run, s3 sells 78,000 shares of 600368 on 2024-08-15 (real position 0 after that day) instead of 60,000. MATERIAL if |Δobjective| > 0.03 vs the reference row 0.1217. REFUTED-as-inert only if the curve is bit-identical (not expected: ~¥80k of cash re-enters s3 on 08-15). Sign is not presumed. ADOPTION RULE (declared now, same as q-e9-s4-pit): if it binds, the fixed book becomes the family REFERENCE whatever the sign — an honest book is the reference, not the better one. EDGE RE-READ (declared now): the s3 sleeve curve is then derived by subtraction (fixed − q-e9-s1-only − q-e9-div-only curves), valid ONLY if every ORPHANSYNC line is s3-tagged (otherwise other sleeve curves moved and the subtraction is void — say so; do not spend more runs). On that derived s3 curve, 价值因子（破净） is SUPPORTED if s3 ≥ 25% of the fixed book's net P&L AND s3 own-capital sharpe ≥ 1.0; REFUTED if ≤ 10%; between = unresolved. The likely answer — s3 falls toward ~7pp of book and the edge stays unresolved — is information, not a reason to skip.",
  why: "gatekeeper 2026-11-01: ACCEPTED, rank 1, ACTIVE. Spawned by q-e9-pb-only (its implication names this entry). Ranked above everything that reads s3, the book level, the liq floor or a VAL decision: half of the strongest leg is a bookkeeping artefact, so promoting 破净, scoring liq, re-reading integration ρ or deciding VAL on the current reference would all be done on a book the strategy does not intend to hold. Not a duplicate: closedDirections 0, staleClosures 0, rejected §2 0 for this family, and nothing covers sub-ledger corporate actions. Falsifiable by the 08-15 sell amount in the log. Cost ~4 backtest-min (full four-sleeve book, 242 days); budget 10/180 used. ⚠ Single TRAIN year ⇒ sharpe SE≈1; the binding question is answered by the log, not by Δsharpe. ⚠ Base posted 2026-05-12: 2024 is inside the author's view — irrelevant to a correctness fix, which is adopted on the rule, not the number.",
  design: "Base = study/价值红利多腿/variants/q-e9-s4-pit.py (current reference; already py2to3 + OVERRIDE). ONE asserted insertion: a helper reconcile_sub_holdings(context) called at the end of daily_init (run_daily 9:00, every day, before any sleeve trades). For each code in context.portfolio.positions: virt = sum over sleeves of g.sub_holdings[sid].get(code, 0); real = positions[code].total_amount. If virt > 0 and real != virt: if exactly ONE sleeve holds it, set that sleeve's amount = real; if ≥ 2 sleeves hold it, scale each pro rata (int floor, remainder to the largest holder). Log `ORPHANSYNC date sid code virt real` for every adjustment and `ORPHANREAL date code real` for a real position with virt == 0 (should be none on a fresh run). Nothing else moves; the builder asserts the diff vs q-e9-s4-pit.py is exactly the helper + one call line. Expected first ORPHANSYNC: s3 600368 60000→78000 on the ex-date (~2024-06-20); report every other one (any other 送转, any sleeve). Report: objective/sharpe/annual/maxDD vs 0.1217 / 1.32 / 32.93 / 20.76; the 08-15 [s3][卖出] 600368 amt; first curve divergence vs data/series/study_价值红利多腿_variants_q-e9-s4-pit__train__e9.json; the derived s3 curve (share of net, own-capital sharpe by the page's formula) and its ρ vs enhance_candidates_pbm-e9-2__train__e9. Page the log in steps of 100 (study/小市值/pagelog.js).",
  from: [
    'study/价值红利多腿/findings.tsv q-e9-pb-only (implication + spawned: q-e9-orphan-fix)',
    'study/价值红利多腿/findings.tsv q-e9-sleeve-attrib (orphan 600368 18,000 shares, ¥85,860)',
    'wiki/families/价值红利多腿.md §4 [正确性缺口] + [腿隔离破口]',
    'q-e9-s4-pit (adoption-rule precedent)',
  ],
  edgeRef: '价值因子（破净）', rank: 1, status: 'active', result: null,
});

q.push({
  id: 'q-e9-liq-1', kind: 'understand',
  title: "Realizability liq-1: liquidity feasibility floor 5e6 CNY/day at the book's own largest order",
  hypothesis: "At the book's own size the floor removes nothing. FLOOR: capital 1,000,000 × 25% per sleeve; s1/s3/s4 hold 1 name ⇒ largest single order ≈ ¥250k (s3 bought ¥268k in the log as its sleeve grew); s2 3 names ≈ ¥83k; order_volume_ratio 0.05 ⇒ 250,000 / 0.05 = 5e6 CNY/day, applied uniformly (the largest order sets the book's floor). R=1 REFUTED if the curve is bit-identical to the reference (max|Δcum| 0 over 242 days). R=1 SUPPORTED if any sleeve's pick changes AND (|Δobjective| > 0.03 or sharpe falls below the 1.0 gate). Picks change but |Δobj| ≤ 0.03 ⇒ R≥2 with the change stated as a capacity caveat.",
  why: "gatekeeper 2026-11-01: ACCEPTED, rank 2, BLOCKED on q-e9-orphan-fix — must run on whichever book is the reference after it (a floor on a book carrying unmanaged orphan shares scores the wrong book). Blocks the exit gate: realizability is unset and unknown BLOCKS. Inertness is a prior, not an assumption: s1 is mega-cap, but s3 is a 破净 sieve buying ~¥4 names such as 600368 五洲交通, and s4 is a single CSI500 name. 破净价值多因子's q-e9-liq was inert at 3.33e6 / 1e7 on overlapping names — a different book. Not a duplicate (no liq finding in this family). Cost ~4 backtest-min.",
  design: "Base = reference after q-e9-orphan-fix. Adapt study/破净价值多因子/build-liq.js into study/价值红利多腿/build-liq.js (a builder, not a hand edit): one helper filter_liquidity_floor(context, stock_list, sid) with LIQ_FLOOR = 1e6 * 0.25 / 0.05 (= 5e6), 20-bar median daily money ending context.previous_date, log `LIQFLOOR sid floor date in out removed=…`. ONE call per sleeve on its CANDIDATE list BEFORE the top-N cut, never after (an after-cut filter leaves empty slots and measures something else): s1 on the get_fundamentals result before `final_list = list(df['code'])[:g.s1_stock_num]`; s2 before `[:g.s2_stock_num]`; s3 on the check_out list before `[:g.s3_stock_num]`; s4 inside _s4_choice_stocks before the yield-rank cut. 511010 (s3 fallback ETF) exempt and logged as such. Existing holdings not exempt (precedent). Builder asserts variant = base + helper + exactly 4 call lines; CLI --floor / --out so liq-2 moves one literal. Report metrics vs the reference row, max|Δcum|, per-sleeve LIQFLOOR in/out counts, and every removed name that was ever a pick.",
  from: [
    'wiki/families/价值红利多腿.md §4 [阻塞 exit gate] realizability 未测',
    'study/破净价值多因子/build-liq.js + wiki/families/破净价值多因子.md q-e9-liq (precedent, R=2)',
    'CLAUDE.md liq-1 pattern (大小盘轮动 / b3751277 inert; ETF溢价 8.44→1.10 biting)',
  ],
  edgeRef: null, rank: 2, status: 'blocked', note: 'blocked on q-e9-orphan-fix (reference may move).', result: null,
});

q.push({
  id: 'q-e9-liq-2', kind: 'understand',
  title: 'Realizability liq-2: 5× floor 2.5e7 CNY/day (≈ ¥5M capital)',
  hypothesis: "Capacity at 5× the book's own floor (2.5e7/day ≈ ¥5M of capital at the same weights). Bit-identical ⇒ R=2 with capacity ≥ ¥5M (R=3 still not earned without a 10× point, per precedent). Biting with |Δobj| > 0.03 or sharpe < 1.0 ⇒ capacity < ¥5M, scored R=2 with that ceiling stated. s3's ~¥4 破净 names are where this floor most plausibly binds.",
  why: 'gatekeeper 2026-11-01: ACCEPTED, rank 3, BLOCKED on q-e9-liq-1 — run ONLY if liq-1 is inert or near-inert (if liq-1 already bites, the score is decided and the 5× point has nothing to discriminate). Separate entry because it is a second run. Cost ~4 backtest-min.',
  design: 'Same builder as q-e9-liq-1 with --floor "1e6 * 0.25 * 5 / 0.05" (2.5e7) --out liq-2_floor-2.5e7.py; only the LIQ_FLOOR literal and its gloss move. Same reporting.',
  from: ['q-e9-liq-1', 'study/破净价值多因子 q-e9-liq liq-2 (precedent: capacity above ~¥2M unmeasured ⇒ R=2 not 3)'],
  edgeRef: null, rank: 3, status: 'blocked', note: 'blocked on q-e9-liq-1 being inert/near-inert.', result: null,
});

q.push({
  id: 'q-e9-free-subsets', kind: 'understand',
  title: 'Free: sleeve-subset table on the post-orphan-fix reference by curve subtraction (s1+s3, s3 alone) — information, not candidates',
  hypothesis: "With exact additivity every subset of {s1, s3, s2+s4} is a sum of stored curves. Pre-registered reading: if s1+s3's sharpe exceeds the full reference by < 1.0 (SE≈1 on one year), the dividend legs are NOT shown harmful — they only add drawdown; ≥ 1.0 ⇒ shown harmful on TRAIN. Valid only if q-e9-orphan-fix's ORPHANSYNC lines are all s3-tagged (else the s1-only / div-only curves are stale and the table is void). s2 alone and s4 alone are NOT derivable from stored curves (they share one run): report them only if attrib.js can rebuild per-sleeve daily marks from the log; otherwise state 'not derivable' — do NOT spend a run on them.",
  why: "gatekeeper 2026-11-01: ACCEPTED, rank 4, ZERO backtest cost, BLOCKED on q-e9-orphan-fix (the pre-fix answer is already known: s1+s3 sharpe 1.28 / maxDD 9.82 / obj ≈0.132; only the post-fix version is new). This is where the orchestrator's 'drop s4' / 's1+s3 only' question lands, as information. ⚠ Must NOT be read as choosing a book: picking sleeves on TRAIN 2024 for a 2026-05-12 post is selection inside the author's view, and a subset search on one year is the cheapest overfit available — see dvl-imp-5 (dropped as a candidate). Follows q-e9-s1-only's implication (base-minus-sleeve is free by subtraction).",
  design: 'No backtest. Curves: fixed reference (q-e9-orphan-fix), study_价值红利多腿_variants_q-e9-s1-only__train__e9, study_价值红利多腿_variants_q-e9-div-only__train__e9; s3 = fixed − s1 − div. Chain cumulative % to daily values (never difference the percentages); sum CNY P&L per day; report subset total/annual/sharpe/maxDD/objective and ρ vs enhance_candidates_pbm-e9-2__train__e9; state the additivity residual.',
  from: [
    'study/价值红利多腿/findings.tsv q-e9-s1-only (implication: base-minus-sleeve free by subtraction)',
    'study/价值红利多腿/findings.tsv q-e9-div-only (implied s2=s4=0: sh 1.28 / maxDD 9.82)',
    'orchestrator 2026-11-01 (drop s4 / s1+s3 question)',
  ],
  edgeRef: null, rank: 4, status: 'blocked', note: 'blocked on q-e9-orphan-fix; NO BACKTEST.', result: null,
});

q.push({
  id: 'dvl-imp-5', kind: 'improve',
  title: 'Ship the s1+s3 book (drop the dividend legs, s2=s4=0) as the family candidate',
  hypothesis: 's1+s3 beats the reference by ≥ 1.0 sharpe on TRAIN. On pre-fix curves it does not (1.28 vs 1.32); it only halves maxDD (20.76→9.82).',
  why: "gatekeeper 2026-11-01: REJECTED as a candidate (recorded so it is not re-proposed). (1) Selection inside the author's view: a sleeve subset chosen on TRAIN 2024 for a book posted 2026-05-12. (2) No expected gain: pre-fix Δsharpe −0.04 at SE≈1 — a drawdown story, not a return one. (3) Its numbers are free and are reported as INFORMATION by q-e9-free-subsets, so no backtest is ever needed. (4) The strongest leg (s3) is half orphan shares until q-e9-orphan-fix lands. 'Drop s4 alone' is folded here: same objection, and not derivable from stored curves without a run that would itself be selection. Reopen only with a new member or a non-TRAIN reason.",
  design: 'None — not to be built.',
  from: ['study/价值红利多腿/findings.tsv q-e9-div-only', 'orchestrator 2026-11-01'],
  edgeRef: '价值因子（破净）', rank: 99, status: 'dropped', result: null,
});

let e = by('q-e9-s2-order');
e.status = 'queued'; e.rank = 5;
e.why += " [gatekeeper 2026-11-01 re-rank] UNBLOCKED (condition met: s2 sharpe 1.15, 29.8% on own capital), rank 5. The likely answer (s2's level is code-order luck over 15 names) is information, and it decides whether dvl-imp-2 is a principled fix or vacuous. Below orphan-fix/liq because it does not touch the exit gate. MUST be built on the post-orphan-fix reference. Read at SLEEVE level (s2 P&L from the log / by subtraction against div-only), not book Δsharpe — a 25% leg cannot move book sharpe by one SE.";
e.design = e.design.replace('Base = reference book', 'Base = ' + REF);
e.from.push('study/价值红利多腿/findings.tsv q-e9-div-only (s2 sharpe 1.15)');

e = by('dvl-imp-2');
e.status = 'blocked'; e.rank = 6;
e.why += " [gatekeeper 2026-11-01] BLOCKED on q-e9-s2-order: drop as vacuous if S2LEN ≤ 3 on most rebalances; drop if first-3 vs last-3 moves s2 P&L by < half (a sort has no room to help). ⚠ The book-level bar (+1.0 sharpe) is essentially unreachable from a 25% leg; re-scoped bar = s2 own-capital sharpe vs 1.15. Any gain is still selection inside the author's view (2024 vs post 2026-05-12) and is not a VAL argument.";

e = by('dvl-imp-3a');
e.status = 'dropped'; e.rank = 98;
e.why += " [gatekeeper 2026-11-01] DROPPED: s4 is net harmful at book level (sleeve sharpe 0.16, maxDD 42.47, one name each way), so its bar is the s4=0 book, which has no curve; breadth prior negative (破净价值多因子 pbn-imp-1 2.10→1.90); a 25% leg cannot reach the +1.0 book bar; tuning a leg on TRAIN 2024 for a 2026-05 post is selection in the author's view. Reopen only with a new member.";

e = by('dvl-imp-4');
e.status = 'dropped'; e.rank = 97;
e.why += " [gatekeeper 2026-11-01] DROPPED by its own condition ('conditional on s4 carrying return'): s4 = 7.4% of net at sleeve sharpe 0.16, carried by one name each way (603156 +45.9k vs 600398 −35.9k) — that is not carrying return. Novelty is real (persistence gate from 蓝筹分红持续性) but expected gain × information on this book is low for dvl-imp-3a's reasons. Reopen if a future member puts weight on a CSI500 yield leg.";

q.sort((a, b) => (a.rank == null ? 50 : a.rank) - (b.rank == null ? 50 : b.rank));
fs.writeFileSync(P, JSON.stringify(q, null, 2) + '\n');

// findings.tsv: q-e9-s1-only spawned cell (lint `unfollowed`)
const rq = require(path.join(ROOT, 'utils/research-queue'));
const F = path.join(__dirname, 'findings.tsv');
const si = rq.FINDING_COLUMNS.indexOf('spawned');
let n = 0;
const out = fs.readFileSync(F, 'utf8').split('\n').map(l => {
  const c = l.split('\t');
  if (c[0] !== 'q-e9-s1-only') return l;
  if (c[si] !== 'none') throw new Error('unexpected spawned: ' + c[si]);
  c[si] = 'q-e9-free-subsets (free subset table by subtraction; gatekeeper 2026-11-01); closed dvl-imp-3b (dropped)';
  n++; return c.join('\t');
});
if (n !== 1) throw new Error('rows=' + n);
fs.writeFileSync(F, out.join('\n'));
console.log('ok', q.length);
