// Recorder helper for q-e9-liq (run once via node -e "require('./study/红利质量/record-q-e9-liq.js')").
const rq = require('../../utils/research-queue');
rq.recordFinding('红利质量', {
  qId: 'q-e9-liq', type: 'understand',
  component_or_param: 'liquidity floor (20d mean turnover >= F) added after _liquidity_filter, LIQFLOOR in->out logged per rebalance; two sequential TRAIN runs at ¥1M on the base d0a149b1: study/红利质量/variants/q-e9-liq-1.py (F=2e5, the book own feasibility floor: ¥1M/100 names/order_volume_ratio 0.05) and q-e9-liq-3.py (F=2e6, 10x), built by build-q-e9-liq.js; logs study/红利质量/liq-1-run.log and liq-3-run.log; curves data/series/study_红利质量_variants_q-e9-liq-1__train__e9.json and study_红利质量_variants_q-e9-liq-3__train__e9.json; on-bench',
  metric_delta: 'both floors vs base: Δobjective 0.0000, max|Δcum| = 0 over 242/242 days (bit-identical curves); LIQFLOOR in == out at 12/12 rebalances at both 2e5 and 2e6; min monthly P5 turnover threshold ¥13.9M/day (Aug) ≈ 70x the 2e5 floor, ≈ 7x the 2e6 floor',
  window: 'TRAIN 2024-01-01..2024-12-31 e9',
  finding: 'Both liquidity floors are fully inert: at F=2e5 (the book own feasibility floor) and F=2e6 (10x) the curve is bit-identical to the base on 242/242 days (max|Δcum| = 0, Δobjective 0.0000) and LIQFLOOR reports in == out at all 12 rebalances. The reason is structural: the book own P5 turnover filter (5-day mean, bottom 5% cut) never let its threshold fall below ¥13.9M/day (August low), ~70x the 2e5 floor and ~7x the 2e6 floor, so nothing the floor could remove is ever in the pool.',
  confidence: 'high',
  flags: 'regime-specific (single TRAIN year 2024; the P5 threshold level is a market-turnover fact of 2024); ⚠零滑点高估 (inert floor says names are fillable at order_volume_ratio 0.05, not that impact is zero on ~100 names monthly); structural-not-incidental (unlike 大小盘轮动 liq-1, inertness follows from the P5 rule itself)',
  description: 'realizability measurement for the exit gate; read jointly with q-e9-cap10x and q-e9-cap20at10x',
  implication: 'Liquidity is CLOSED as a capacity question for the base as written: with q-e9-cap20at10x (fixed ¥20 cap at ¥10M: 0 fill warnings, order_volume_ratio never bound) the only capacity limit left is the author equity/500 price-cap rule, which q-e9-cap10x showed takes the as-written book below the 1.0 gate at ¥10M (sharpe 0.86). So realizability is scored 2 on the base d0a149b1 in this same write (3 would need the as-written book to hold the gate at scale, and it does not); the family exit gate no longer blocks on realizability and the next step is the VAL decision (orchestrator-owned). Conditional reopening: any variant loosening SCHD_LIQ_PCT (the P5 cut) removes the structural guarantee and must re-run liq before its number is citable; no liq-2 (5x) run is needed on the base since 10x is already inert.',
  spawned: 'none (realizability scored in frontmatter; next step is VAL, which the orchestrator owns and is not a queue idea; SCHD_LIQ_PCT conditional gap recorded in §4)',
  edgeRef: 'none (realizability, no edge claim; all edge statuses unchanged)',
});
const e = rq.load('红利质量').find(x => x.id === 'q-e9-liq');
console.log('q-e9-liq status:', e.status);
