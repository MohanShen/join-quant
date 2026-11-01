// One-off recorder write for q-e9-persist (family-recorder, 2026-11-01).
// Run: node -e "require('./study/红利质量/record-q-e9-persist.js')"
const rq = require('../../utils/research-queue');
rq.recordFinding('红利质量', {
  qId: 'q-e9-persist',
  type: 'understand',
  component_or_param: 'dividend-persistence gate removed: SCHD_MIN_DIVIDEND_YEARS 10 -> 1 and SCHD_DIVIDEND_GROWTH_MIN -> -1 (5y growth gate off), yield 1-15% band and everything else verbatim; study/红利质量/variants/q-e9-persist.py (build-q-e9-persist.js), log study/红利质量/persist-run.log, curve data/series/study_红利质量_variants_q-e9-persist__train__e9.json; ¥1M, on-bench',
  metric_delta: 'variant − base: annual 16.82 vs 25.94 (−9.12pp), sharpe 0.59 vs 1.09 (Δ −0.50), maxDD 19.59 vs 13.73 (+5.86pp), objective −0.0277 vs 0.1221 (Δ −0.1498); daily corr 0.980; post-gate pool N 301–611 vs 78–174 (2.5–3.5×), Top100 binds 12/12 months; mean 1-lot price ¥10.7–14.5 vs ¥9.6–13.4; new buys 471 vs 391',
  window: 'TRAIN 2024-01-01..2024-12-31 e9',
  finding: 'Removing the 10-year continuous-dividend gate and the 5y growth>=0 gate scores annual 16.82 / sharpe 0.59 / maxDD 19.59 / objective −0.0277 against base 25.94 / 1.09 / 13.73 / 0.1221: Δsharpe −0.50, Δobjective −0.1498, below the 1.0 gate. The post-gate pool is 2.5–3.5× larger (N 301–611 vs 78–174) so Top100 binds in all 12 months; the price cap stays on but holdings sit about ¥1 higher per share (¥10.7–14.5 vs ¥9.6–13.4). The shortfall is spread across months (largest Jun–Aug and Jan), not one event; no fill problems; turnover higher (471 vs 391 new buys). Daily corr 0.980. Pre-registered Δsh <= −0.3 => SUPPORTED.',
  confidence: 'medium',
  flags: 'regime-specific (single TRAIN year 2024); author-in-sample (author scanned 3/5/10 years and the growth gate on 2020-01..2026-08 incl. 2024, which biases toward SUPPORT, so supported is the WEAK direction); two-knobs (years + growth changed together, as the edge defines them; attribution between them not separated); confounded-ranking (wider pool lets the composite select from more names; weak, since q-e9-rankinv measured that ranking inert); confounded-price (~¥1 higher holdings price leaks 低价股效应 into Δ; cap20at10x/cap10x dose-response puts ¥10->¥24 at ~0.23–0.36 sharpe, so ¥1 is minor); ⚠零滑点高估 (~100 names monthly, more turnover in variant)',
  description: 'Edge test of 分红持续性筛选: SCHD_MIN_DIVIDEND_YEARS 10->1 + growth gate off, all else unchanged; one TRAIN run at ¥1M, epoch 9.',
  implication: 'Edge 分红持续性筛选 -> MEASURED in this same write (it ran the stated test). With the four-factor ranking refuted (q-e9-rankinv) and the price cap measured (q-e9-minlots/cap20at10x), the book is now fully decomposed: a persistent-dividend POOL (10y continuous payout + non-negative 5y growth) × a low share-price cap; the composite score adds nothing. So the honest minimal book is pool gates + fixed ¥20 cap + yield weighting, with no composite score — the candidate form for integration and realizability scoring (recorded in §4, not queued). The family is NOT merely a low-price tilt: dividend persistence is a second measured component, so the 全A integration reading changes from "another 低价股效应 implementation" to "persistence pool × low price". i-1 (送转-adjusted growth) is unblocked because it touches a supported gate, but stays low priority: support is the weak direction under author-in-sample tuning, and separating years vs growth would come before refining growth inputs. The remaining blocker on the exit gate is q-e9-liq (liquidity at ¥1M on the base), now the next run.',
  spawned: 'none (i-1 unblocked blocked->queued; q-e9-liq already queued and now next; minimal-book candidate recorded in §4, not queued)',
  edgeRef: '分红持续性筛选',
});
const e = rq.load('红利质量');
const i1 = e.find(x => x.id === 'i-1');
i1.status = 'queued';
i1.note += ' ‖ recorder 2026-11-01（q-e9-persist）：门槛被 SUPPORTED（Δsh −0.50），解锁 blocked→queued；但低优先：作者样本内调过此门，支持是弱方向；且年数 vs 增速尚未拆分，先拆再修增速输入。';
const liq = e.find(x => x.id === 'q-e9-liq');
liq.note += ' ‖ recorder 2026-11-01（q-e9-persist）：持续性门 measured、排序 refuted、价格上限 measured ⇒ 机制已分解完，本条是 exit gate 剩下的唯一输入，下一跑。';
rq.save('红利质量', e);
console.log(e.filter(x => ['q-e9-persist', 'i-1', 'q-e9-liq'].includes(x.id)).map(x => x.id + ' ' + x.status).join('\n'));
