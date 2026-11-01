// One-shot recorder for u-e9-inv-h (family-recorder, 2026-11-01). Idempotent guard: refuses a second write.
// Touches ONLY the u-e9-inv-h queue entry (an executor is concurrently running u-e9-nobb-h).
const rq = require('../../utils/research-queue');
const FAM = '银行股轮动';
if (rq.findings(FAM).some(f => f.qId === 'u-e9-inv-h')) { console.log('already recorded'); process.exit(0); }
rq.recordFinding(FAM, {
  qId: 'u-e9-inv-h',
  type: 'understand',
  component_or_param: 'score sort inverted on the HONEST-dividend book: base = variants/u-e9-dypit.py; reverse=True -> reverse=False at L147 (top-3 candidate cut) and the eligible sort; INV date/n_eligible/order logged (observation only); all else verbatim',
  metric_delta: 'vs dypit 46.76/2.38/13.13/0.3363: total 32.52 / sharpe 1.65 / maxDD 10.44 / obj 0.2208 -> Δobj -0.1155, Δsharpe -0.73, ΔmaxDD -2.69pp; corr(daily, dypit)=0.9184; vs EW u-e9-ew 0.3185: -0.0977; leaky u-e9-inv was Δobj -0.0951 vs leaky base; binding n_eligible 1/2/3/4/5 in 8/3/3/4/10 weeks (>=3: 17, >3: 14; rule needs >=8)',
  window: 'TRAIN 2024 e9',
  finding: 'On honest TTM dividends, buying the LOWEST-scored eligible banks scores 32.52 / sharpe 1.65 / maxDD 10.44 / objective 0.2208 against the dypit baseline 46.76 / 2.38 / 13.13 / 0.3363: Δobj -0.1155, Δsharpe -0.73, ΔmaxDD -2.69pp, daily corr 0.9184. The score was binding: 28 of 51 rebalances reached the sort with n_eligible 1/2/3/4/5 in 8/3/3/4/10 weeks, so 17 weeks with >=3 eligible (order matters) and 14 with >3 (set changes), above the declared minimum of 8. Declared rule (Δobj <= -0.08 OR Δsharpe <= -0.55) -> CONFIRM, both conditions fire. The leaky u-e9-inv gave Δobj -0.0951, so the honest inversion is if anything larger.',
  confidence: 'medium',
  flags: 'regime-specific (one year, 5 co-moving banks, 2024 bank uptrend); hindsight-pool (2026-authored 5-bank list); n-small (17 binding weeks); ⚠零滑点高估 (minor at mega-cap weekly)',
  description: 'build study/银行股轮动/build-inv-h.js -> variants/u-e9-inv-h.py; algorithmId 67820476a422a51cfd4b8cde928b0cd5; curve study_银行股轮动_variants_u-e9-inv-h__train__e9 (final cum 32.52 verified by orchestrator). Decision rule declared in queue.json before the run, re-anchored to dypit.',
  implication: 'The score sign is real and is NOT a product of the dividend lookahead (honest −0.1155 vs leaky −0.0951), so the score half of 池内轮动 survives and the family is not beta-only — the "inv-h REFUTE ⇒ only bank-imp-pit remains" branch is closed. But the information is asymmetric: inverted sits 0.0977 BELOW equal-weight while the forward book sits only 0.0178 ABOVE it (dypit vs u-e9-ew), so ~85% of the score\'s value is in AVOIDING the bottom scorers, not in picking the top. Consequences: (1) the on-mechanism improve is exclusion, not concentration — drop the bottom 1–2 by score and equal-weight the rest (spawned bank-imp-drop2, not queued here); top-1/top-2 concentration is the wrong direction. (2) Split the 池内轮动 claim now: the score part is measured on this bench (new claim 池内 PB+股息+1M 打分), the timing part (Bollinger/MA250) stays proposed pending nobb-h and a window with ICBC < MA250. (3) The inverted book has LOWER drawdown (−2.69pp), so the score\'s top picks carry the extra risk — dypit\'s +1.30pp maxDD is plausibly the score, not drift; any exclusion variant must report maxDD against dypit. (4) No weight sweep: 17 binding weeks on one year cannot support it; the PB+dy vs 1M-momentum component split remains the prior question.',
  spawned: 'bank-imp-drop2 (exclusion rule: drop bottom 1–2 by score, equal-weight the rest; to be gated, not queued by the recorder)',
  edgeRef: '池内 PB+股息+1M 打分',
});
const q = rq.load(FAM);
const e = q.find(x => x.id === 'u-e9-inv-h');
e.status = 'done';
e.result = 'CONFIRM score sign on honest dividends: obj 0.2208 vs dypit 0.3363 (Δ-0.1155), sharpe 1.65 (Δ-0.73), maxDD 10.44 (Δ-2.69pp), corr 0.9184; binding 17/14 weeks; leaky inv was -0.0951 so not a leak artifact. Asymmetric: inverted is -0.0977 vs EW, forward +0.0178. curve study_银行股轮动_variants_u-e9-inv-h__train__e9, algorithmId 67820476a422a51cfd4b8cde928b0cd5';
rq.save(FAM, q);
const last = rq.findings(FAM).slice(-1)[0];
console.log('recorded', last.qId, 'epoch', last.measuredEpoch, 'queue status', e.status, 'nobb-h status', (q.find(x => x.id === 'u-e9-nobb-h') || {}).status);
