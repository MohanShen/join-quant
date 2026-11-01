// recorder helper for u-5 (one-shot). Writes the finding, marks u-5 done, spawns u-8.
const rq = require('../../utils/research-queue');
const FAM = '向导式低波价值';

rq.recordFinding(FAM, {
  qId: 'u-5',
  type: 'understand',
  component_or_param: 'REDESIGNED relative-ATR gate (run dxlv-u-5): u-7 pool-EW harness + L196 yuan ATR_judge_xiaoyu(0.15,14) replaced by talib ATR(14) on 15 daily bars to previous_date / previous close < k = 0.01646 (rel15 basis, the basis the queue derived k on). PE 6-11, HS300, industry, ST/paused/high-limit filters unchanged. Control = u-7. This is edge 低价股效应 test:',
  metric_delta: 'u-5 total/annual 28.09, sharpe 1.23, maxDD 13.75, obj 0.1434 vs u-7 29.50/1.08/12.20/0.1730 => Δsharpe +0.15, Δobj -0.0296, maxDD +1.55pp; daily corr 0.8791 (242/242 days, same start 2024-01-02). Recomputed from curve study_向导式低波价值_variants_u-5__train__e9: final cum 28.09, maxDD 13.75, obj (28.09-13.75)/100 = 0.1434, corr 0.8791; curve-sharpe estimator 1.158 vs u-7 1.045 (Δ +0.11, same sign, inside the ±0.2 band on both)',
  window: 'TRAIN 2024',
  finding: 'VALID (decision rule met): U5GATE day 1 n_pre=26 n_in=6, POOL0 = exactly the pre-registered {600018 600104 600332 600362 601006 601319}; day-1 EWDEPLOY cash_after 2861.95 / total 999700.95 = 0.29% (<=5%); no 688 name admitted, so the STAR refusal did not bite. Result: Δsharpe +0.15 vs u-7, inside the pre-declared REFUTE band (|Δ| <= 0.2) and far from the CONFIRM line (<= -0.5). Return level landed where the pre-run preview put it (price-only day-1 EW +24.07% vs u-7 +25.95%; realised 28.09 vs 29.50 incl. dividends). Shared names 601006/600018/601319; added 600332 -0.7, 600362 +15.4, 600104 +53.1 (day-1 close ¥28.60/17.86/13.53); dropped 601117 +29.7, 601669 +11.7, 601800 +37.7 (¥6.36/4.89/7.60). Day-1 median price u-5 ≈ ¥10.4 vs u-7 ≈ ¥5.6, so the swap really did move nominal price up ~2x at equal breadth. After day 1 the relative gate admits a median of 1 name per check date (0 on 10 of 25) vs u-7 median 5, so both runs are in effect day-1 6-name EW buy-and-holds; year-end dividend dust 7 names ≈3.3% of the book (u-7 2.9%), within the shared noise floor.',
  confidence: 'high (validity + measurement: POOL0 exact, curve reproduces total/maxDD/obj/corr, JQ and curve sharpe agree in sign and band); medium (scope: one day-1 cross-section, 3 swapped names decide it)',
  flags: 'regime-specific',
  description: 'Log study/向导式低波价值/log-u-5.txt (9 pages, 794 lines: U5REL per PE survivor per date, U5GATE, POOL0, EWFILL, EWDEPLOY, EWFINAL); build build-u-5.js. ⚠ k is on the rel15 basis (15 bars). Under 60-bar Wilder values (the basis u-2 found the wizard uses for yuan) the same k admits only 4 names on day 1, which would have voided the run by its validity clause, so the basis choice is load-bearing and is the queue\'s, not a post-hoc pick. k remains knife-edge (601319 0.01638 in, 601318 0.01654 out).',
  implication: 'REFUTES 低价股效应 for this family (status proposed -> refuted in the same write, evidence [[study-u-5]]), scoped exactly: on the 2024-01-02 cross-section, a low-volatility (ATR/close) gate of equal breadth matches the yuan gate, so NOMINAL PRICE adds nothing over low volatility here. Does NOT touch the canonical 低价股效应 registered from 大小盘轮动 u-7 (small-cap universe, different mechanism). Does NOT establish low volatility as an edge: the only gate-vs-no-gate evidence is u-3 (-0.70, n=1 date, gap mostly 5 solar/lithium/property names), so what u-3 measured is "some ATR gate beats none on 2024", consistent with low vol, sector avoidance, or both. Do not queue further price-variants (price caps, price-rank, yuan-threshold sweeps): that direction is closed on this book. A proposed edge 低波动 is registered with a test that needs MANY cross-sections, which a day-1 buy-and-hold cannot give, so spawned u-8 (rebalanced rank-based low-vol basket vs rebalanced PE-pool EW, ~25 check dates) for the gatekeeper; it ranks behind u-4 and liq-1, which block the exit gate. The family name 低波 is now the only live reading of the gate, still proposed.',
  spawned: 'u-8',
  edgeRef: '低价股效应',
});

const e = rq.load(FAM);
const h = e.find(x => x.id === 'u-5');
h.status = 'done';
rq.save(FAM, e);

rq.add(FAM, {
  id: 'u-8',
  kind: 'understand',
  title: 'REBALANCED low-vol test: every check date hold EW the 6 lowest ATR/close among HS300 ∩ PE 6-11, vs the same rebalance on the whole PE pool EW (edge 低波动 test)',
  hypothesis: 'The ATR gate earns because it selects LOW VOLATILITY, not because of 2024 sector avoidance on one date: across ~25 re-formed cross-sections, a lowest-ATR/close basket beats the full PE-pool basket on sharpe.',
  why: 'type: edge test for the PROPOSED edge 低波动 (unregistered; proposed only). Spawned by the u-5 recorder: u-5 refuted the price reading, and u-3 (gate removed, -0.70) cannot separate low vol from sector avoidance because it is one day-1 cross-section with the gap carried by ~5 solar/lithium/property names. Every pool-EW run so far (u-7/u-3/u-5) is a day-1 buy-and-hold, so it can never give a second cross-section; a rebalancing harness is the only way this book yields a multi-date test inside TRAIN. PROPOSED DECISION RULE (gatekeeper to fix before dispatch): CONFIRM 低波动 at Δsharpe >= +0.5 vs the rebalanced PE-pool EW control AND the low-vol leg beats the control on >= 60% of the 10-day holding periods; REFUTE at |Δsharpe| <= 0.2; else partial. Report per-period sector mix of the low-vol leg so a result carried by avoiding one sector is visible. ⚠ Still one regime (2024) even with 25 dates; a CONFIRM here is 「低波 on 2024」, not a durable edge. ⚠ Rebalancing adds turnover and costs the buy-and-hold legs never paid; report both legs\' trade counts. Rank behind u-4 and liq-1 (those block the exit gate). Cost ~2 runs x 3-5 min.',
  design: 'Two runs on a new REBALANCE harness (not the pool-EW harness): on each existing 10-day check date, target = EW over the selected set, sell anything not in it, buy to target. Leg A: rank PE 6-11 survivors by rel15 (talib ATR 14 on 15 bars to previous_date / previous close) ascending, take 6 (rank, not threshold, so breadth is fixed every date). Leg B (control): EW the whole PE 6-11 pool. Same universe/industry/ST/paused/high-limit filters. 688 names need protected limit orders (u-3 refusal), else Leg B measures idle cash. Log REBAL date n_pool codes sectors turnover.',
  from: ['u-5 (price refuted, low-vol gate matches yuan gate on day 1)', 'u-3 (gate vs no gate -0.70, n=1 date, sector-concentrated)', 'u-7'],
  edgeRef: '低波动',
  rank: 4,
  status: 'queued',
  note: 'recorder 2026-11-01 after u-5: PROPOSED, not gated. The gatekeeper should judge whether a rebalancing harness is worth ~8 min given that a CONFIRM would still be a single-regime result, and may drop it.',
});

console.log(h.status, '|', String(h.result).slice(0, 80));
console.log(rq.load(FAM).map(x => x.id + ':' + x.status).join(' '));
