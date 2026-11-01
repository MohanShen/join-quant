// gatekeeper 2026-11-01: seeds study/破净价值多因子/queue.json from generators A + B (round 1).
// Idempotence guard: refuses to run if the queue already holds entries.
const rq = require('../../utils/research-queue.js');
const F = '破净价值多因子';
if (rq.context(F).queue.length) { console.error('queue already populated — refusing'); process.exit(1); }
const BASE = 'strategies/2026-10-17_六因子选股版破净策略_附PT迁移版在各时期的回测截图-e7c95ca1.py';
const CTRL = 'control = base e7c95ca1 epoch-9 ledger row 0.3897 / sharpe 2.10 / annual 54.17 / maxDD 15.20';
const SE = 'Single TRAIN year ⇒ sharpe SE≈1: |Δsharpe|<1 is UNRESOLVED, not a null — report it as such.';
const G = 'gatekeeper 2026-11-01';
const entries = [
  {
    id: 'q-e9-pb-ablate', kind: 'understand', rank: 1, status: 'active',
    title: 'Edge ablation: delete valuation.pb_ratio.between(0, 1) — is 破净 the return source?',
    hypothesis: 'If 价值因子（破净） is the edge, removing the PB∈(0,1) screen (quality chain, six rankers, calendar, everything else verbatim) drops sharpe by ≥1.0 vs base 2.10. Refuted if Δsharpe ≥ 0 (the return comes from the quality chain/rankers). −1.0<Δ<0 = unresolved at SE≈1.',
    why: `${G}: ACCEPTED, rank 1, ACTIVE. It is the family's own edge.test and §4's named [第一步]; until it runs the edge may not be cited. Either outcome is information — a refute is as valuable as a support, and the result also decides whether q-e9-ranker-isolate runs. Not a duplicate (0 findings, 0 closures binding or stale, 0 §2 rejects). Cost ~3 backtest-min. ⚠ The base holds 2–5 names (free holdings fact), so this Δ is a Δ of a concentrated book — note it, do not correct for it here. ${SE}`,
    design: `Base ${BASE} + py2to3 + OVERRIDE, epoch-9 pins. ONE asserted edit: remove the line \`        valuation.pb_ratio.between(0, 1),\` (line ~97, exactly-one match). Everything else verbatim. Report objective/sharpe/annual/maxDD vs ${CTRL}, plus the per-rebalance target count (the qualified list will be larger; rankers still take top_n=1 each) and the monthly split vs the base curve data/series/…e7c95ca1__train__e9.json.`,
    from: ['wiki/families/破净价值多因子.md edge[0].test + §4 [第一步] 机制消融', 'generator A free measurement: 5/2/4 names bought Feb/May/Sep; Sep +21.5% and Dec +15.1% ≈78% of log-growth'],
    edgeRef: '价值因子（破净）',
  },
  {
    id: 'q-e9-calendar-ablate', kind: 'understand', rank: 2, status: 'queued',
    title: 'Edge ablation: g.if_check_calendar_effect=False — does January/April cash help?',
    hypothesis: 'If 日历空仓 is an edge, turning it off lowers sharpe vs base 2.10. Refuted on 2024 if sharpe ≥ base. Generator expects UP (the 红利低频 proxy made +10% Jan / +2.5% Apr 2024 while this book sat in cash) — a likely refute is a reason to run it, not to rank it down.',
    why: `${G}: ACCEPTED, rank 2. Second proposed edge; same ablation shape, ~3 min. ⚠ Window caveat from the edge.test: TRAIN 2024 January is the small-cap stampede month, so read the result as a MONTHLY split (Jan and Apr contribution) — a Δ concentrated entirely in 2024-01 is a window coincidence, not mechanism, and must be reported that way whichever sign it takes. ${SE}`,
    design: `Base ${BASE} + py2to3 + OVERRIDE. ONE asserted edit: \`g.if_check_calendar_effect = True\` → \`False\` (line ~42). Report vs ${CTRL} and the Jan/Apr/rest-of-year return split vs the base curve.`,
    from: ['wiki/families/破净价值多因子.md edge[1].test', 'generator A free measurement: 93379f98 proxy +10% Jan / +2.5% Apr 2024 while base was in cash; daily corr 0.62 with 93379f98'],
    edgeRef: '日历空仓（1月、4月）',
  },
  {
    id: 'pbn-imp-3', kind: 'improve', rank: 3, status: 'queued',
    title: 'Fix buy_stocks cash split: divide available_cash only over names not yet held',
    hypothesis: 'The measured book never holds its intended ≤6 names because target_value = available_cash/len(buy_list) counts already-held names (verified, source line 187). Fixing it deploys idle cash. Judged on SHARPE, not objective (deploying more cash mechanically raises annual). Support: sharpe ≥ base 2.10 with maxDD not worse by >5pp. Refute: sharpe ≤ 1.10 (Δ ≤ −1.0) ⇒ the measured 2.10 depends on bug-induced concentration, itself a finding about the edge.',
    why: `${G}: ACCEPTED, rank 3. Execution fidelity — the book being measured is not the book the author describes, so this is half improve, half understand (is the level a concentration artifact?). Bug confirmed in source (line 187: divisor includes held names). The 14:00/14:50 limit-up exits that park cash to month-end are a SEPARATE cause and stay out of scope — one experiment. Below the two edge ablations because §4 orders 消融 first; above imp-1 because imp-1 is confounded by this bug. Expected Δsharpe plausibly <1 ⇒ may be unresolvable at SE≈1; cost ~3 min. ${SE}`,
    design: `Base ${BASE} + py2to3 + OVERRIDE. ONE asserted edit in buy_stocks: replace \`target_value = context.portfolio.available_cash / len(buy_list)\` with \`to_buy = [s for s in buy_list if s not in context.portfolio.positions]\` / \`if not to_buy: return\` / \`target_value = context.portfolio.available_cash / len(to_buy)\`. Report vs ${CTRL} and names-held count per month (from the log).`,
    from: ['generator A free measurement: never 6 names; ~2–3 held Jun–Aug from the buy_stocks cash-splitting bug + limit-up exits parking cash', 'source line 187 (verified by gatekeeper)'],
    edgeRef: '价值因子（破净）',
  },
  {
    id: 'q-e9-attrib-probe', kind: 'understand', rank: 4, status: 'queued',
    title: 'Per-name P&L attribution: log positions daily at 15:00',
    hypothesis: '≤2 names supply >50% of TRAIN P&L. Refuted if the top-2 names supply ≤50%. Control must reproduce 0.3897/2.10/54.17/15.20 exactly, else the probe changed the book and is void.',
    why: `${G}: ACCEPTED, rank 4. Resolves whether the Sep/Dec spikes are one or two names (a concentration fact the other reads depend on). ⚠ Partly answered for free already (holdings counts; the two months supplying ~78%). BEFORE spending a run, try the free route: reconstruct per-name P&L from the base run's existing 买入/卖出 log lines + daily closes — if that answers it, record a zero-cost finding and mark this answered. Only if fills/sizes cannot be recovered, run the probe (~3 min). Logs page 100 lines/request — use study/小市值/pagelog.js.`,
    design: `Base ${BASE} + py2to3 + OVERRIDE + appended helper log_positions(context) scheduled run_daily(..., time='15:00'): one log.info line per position 'POS date code value avg_cost' plus 'CASH date available_cash total_value'. No trading change. Control check against the ledger row first; absence of POS lines = instrumentation failure, not 'no positions'.`,
    from: ['generator A free measurement: Sep 2024 +21.5%, Dec +15.1% ≈78% of log-growth; 5/2/4 names per rebalance'],
    edgeRef: null,
  },
  {
    id: 'pbn-imp-1', kind: 'improve', rank: 5, status: 'blocked',
    title: 'g.top_n 1→2 (each ranker contributes two names, ≤12 targets)',
    hypothesis: 'Broadening each ranker to 2 names diversifies a 2–5-name book and raises sharpe. Support: sharpe ≥ base+1.0; refute: sharpe ≤ base.',
    why: `${G}: ACCEPTED but BLOCKED on pbn-imp-3. On the buggy base a longer buy_list makes the cash-split bug WORSE (bigger divisor, less cash deployed), so the Δ would mix diversification with under-deployment — two effects in one experiment. Build on whichever base pbn-imp-3 settles. Expected gain modest and likely <1 sharpe ⇒ probably unresolvable at SE≈1. Only weakly on-mechanism: the edge claim says the rankers are NOT the return source, so ranker width is a sizing change, not an edge lever. Cost ~3 min.`,
    design: `Base = pbn-imp-3 variant if adopted, else ${BASE}; py2to3 + OVERRIDE; ONE asserted edit g.top_n = 1 → 2 (line ~36). Report vs the chosen base's row.`,
    from: ['generator A free measurement: never 6 names held'],
    edgeRef: '价值因子（破净）',
  },
  {
    id: 'q-e9-ranker-isolate', kind: 'understand', rank: 6, status: 'blocked',
    title: 'Ranker isolation: replace the six rankers with the 6 lowest-PB names of the qualified list (merges pbn-imp-2)',
    hypothesis: 'If the edge is 破净 and the rankers only pick within it (edge[0].claim), the 6 cheapest-PB qualifiers score sharpe within 1.0 of base. Refuted (rankers carry return) if sharpe ≤ base −1.0.',
    why: `${G}: ACCEPTED as ONE entry — generator B's pbn-imp-2 is the same experiment and is merged here (pbn-imp-2 recorded as dropped:duplicate). BLOCKED on q-e9-pb-ablate: runs only if that is not a clean refute (if removing PB does not hurt, a cheapest-PB ranker tests a non-edge). Kind stays understand (the question is where the return lives); if it beats base it is judged on improve terms then. Cost ~3 min.`,
    design: `Base ${BASE} + py2to3 + OVERRIDE. Replace the six-ranker union with: the qualified list (pb screen + quality chain unchanged) ordered by valuation.pb_ratio.asc(), take 6. Everything else verbatim (buy_stocks bug included, so the Δ isolates the ranker).`,
    from: ['q-e9-pb-ablate (gate)', 'generator B pbn-imp-2 (merged)', 'wiki/families/破净价值多因子.md edge[0].claim: 六个排序器只是在合格集合里挑'],
    edgeRef: '价值因子（破净）',
  },
  {
    id: 'pbn-imp-2', kind: 'improve', rank: 99, status: 'dropped',
    title: '6 cheapest-PB qualifiers instead of the ranker union',
    hypothesis: 'Same as q-e9-ranker-isolate.',
    why: `${G}: DROPPED as duplicate of q-e9-ranker-isolate (identical experiment). Recorded so it is not re-proposed.`,
    from: ['q-e9-ranker-isolate'],
    edgeRef: '价值因子（破净）',
  },
];
for (const e of entries) rq.add(F, e);
console.log(`added ${entries.length}`);
