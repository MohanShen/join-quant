// recorder helper for u-9 (one-shot). Writes the finding, marks u-9 done. Spawns nothing.
const rq = require('../../utils/research-queue');
const FAM = '向导式低波价值';

rq.recordFinding(FAM, {
  qId: 'u-9',
  type: 'understand',
  component_or_param: 'SECTOR-CONTROLLED low-vol test (runs dxlv-u-9a / dxlv-u-9b, build-u-8.js --u9): the u-8 rebalance harness verbatim + ONE asserted edit X1 per leg — after the PE 6-11 / ST / paused filters and before _rb_select, drop names whose SW L1 industry (get_industry at previous_date) is 电气设备I or 房地产I (RBEXCL log). Leg A = 6 lowest rel15 of the reduced pool; Leg B (control) = whole reduced pool EW. Decision rule FIXED by the u-8 recorder before the run. Test of edge 低波动',
  metric_delta: 'A 32.01 / sharpe 1.35 / maxDD 14.05 / obj 0.1796 vs B 28.45 / 1.16 / 14.25 / 0.1420 => Δsharpe +0.19 (JQ), Δobj +0.0376, maxDD -0.20pp; daily corr 0.9058 (242/242). Recorder recomputed from curves study_向导式低波价值_variants_u-9a/u-9b__train__e9: final cum 32.01 / 28.45, maxDD 14.05 / 14.26, curve-sharpe 1.250 vs 1.103 (Δ +0.147). vs u-8: Δsharpe +0.85 -> +0.19 (JQ) and +0.67 -> +0.147 (curve), i.e. ~78% of the gap removed on both estimators; A 1.40 -> 1.35, B 0.55 -> 1.16',
  window: 'TRAIN 2024',
  finding: "Verdict band SECTOR AVOIDANCE EXPLAINS u-8 (Δsharpe <= +0.2): JQ +0.19 (inside by 0.01), curve +0.147 (inside more clearly), so both estimators agree in band. VALID on every pre-declared clause: 25 rebalance dates identical across legs and equal to u-8; B day-1 pool 20 (min over dates 15, median 21, max 40); n_held == n_tgt on 25/25 dates; cash <= 2.3% on every rebalance date; A day-1 holds 6. RBEXCL ran on 25/25 dates (day 1 removed 000002/600048 房地产 + 002129/002459/688303/688599 电气设备, 26 -> 20). The exclusion moved B, not A: A held the same 6 names as u-8 on 22/25 dates (differs 05-08, 08-01, 08-15) and its sharpe barely moved (1.40 -> 1.35); B rose 0.55 -> 1.16. Per third (compounded): Jan-Apr A +14.26 vs B +13.04 (u-8 B was +1.54), A wins 3/8; May-Aug A -7.95 vs B -10.44, 7/9; Sep-Dec A +25.51 vs B +26.88, 4/8. Period wins 14/25 = 56%. The residual gap sits in May-Aug. Sector slot-share: A 银行 21% / 建筑 19% / 非银 19% / 交运 16%; B 建筑 19% / 非银 15% / 银行 12% / 交运 10% / 公用 8% / 有色 8%; 电气设备 B 14% -> 0. Turnover excl day 1 A 23.3 vs B 9.4 tv; orders A 163 filled / 0 refused, B 527 / 18 (sub-lot trims). Caveats: 002460 is SW 有色金属 not 电气设备, so it stayed in B (the rule was fixed; it was not widened after seeing it). Industry is as of previous_date. A's bank tilt (21% vs 12%) is uncontrolled.",
  confidence: 'high (measurement: curves reproduce total/maxDD, every validity clause met, JQ and curve sharpe both in the refute band); medium (verdict margin: JQ Δ sits 0.01 inside the +0.2 line, curve 0.05 inside; one year; A bank tilt uncontrolled)',
  flags: 'regime-specific',
  description: 'Logs study/向导式低波价值/log-u-9a.txt / log-u-9b.txt (RBEXCL / RBREL / RBSEL / RBORD / REBAL); builder study/向导式低波价值/build-u-8.js --u9; analysis = analyse-u-8.js logic re-pointed at the u-9 curves and logs (recorder, in memory). No VAL touched.',
  implication: "REFUTES 低波动 for this family (status proposed -> refuted in the same write, evidence [[study-u-9]]), by its own pre-fixed rule, scoped to TRAIN 2024, HS300 ∩ PE 6-11, rank-6 rebalance harness, with the 2-sector exclusion pre-declared from u-3. u-8's +0.85 was mostly the control holding 2024 solar/lithium/property losers. With 低估值 (u-4), 低价股效应 (u-5) and now 低波动 (u-9) all refuted, the edge block gains a kind: none-found entry: the base's 2024 level is the day-1 basket of large-cap low-price SOE names (u-7, corr 0.98), whose selection rules each fail their own ablation; the only measured effect is avoiding 2024's 电气设备/房地产 losers. CLOSES the understand side on this bench: no further ablation, low-vol, industry-neutral low-vol (the §4 follow-up was conditional on u-9 SUPPORTING), PE or price variant is to be queued on TRAIN 2024. It also leaves no premise for any improve idea that cites a rule-level edge here. Reopen only with a NEW cross-section (a different year's data, e.g. rolling day-1 cross-sections outside 2024) or a mechanism that is not one of these three. Does NOT change the VAL candidate (base 8b9cb8e2 as written) and does not decide VAL: whether to spend it on a none-found family is a separate decision for the orchestrator/human.",
  spawned: 'none',
  edgeRef: '低波动',
});

const q = rq.load(FAM);
const e = q.find(x => x.id === 'u-9');
e.status = 'done';
e.result = "SECTOR AVOIDANCE EXPLAINS u-8 (refute band Δsharpe <= +0.2): A 32.01 / 1.35 / 14.05 vs B 28.45 / 1.16 / 14.25, Δsharpe +0.19 JQ / +0.147 curve, corr 0.9058, A wins 14/25. Exclusion removed ~78% of u-8's gap, almost all via B (0.55 -> 1.16); A same 6 names on 22/25 dates. 低波动 refuted; family edge -> none-found entry added.";
e.note = (e.note || '') + ' ‖ recorder 2026-11-01: DONE. All validity clauses met (B min pool 15, cash <= 2.3%, 25/25 dates identical). Verdict in the refute band on both estimators (JQ by 0.01). 低波动 refuted in the same write; none-found entry added; understand side closed for this bench.';
rq.save(FAM, q);
console.log('ok', e.status);
