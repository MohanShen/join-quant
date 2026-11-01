// Recorder input for 价值红利多腿 round-1 sleeve-only runs (epoch 9). Run from repo root.
const rq = require('../../utils/research-queue');
const FAM = '价值红利多腿';

rq.recordFinding(FAM, {
  qId: 'q-e9-pb-only',
  type: 'ablation',
  component_or_param: "s3-only book (g.strategy_weights 0/0/0.25/0) on the reference q-e9-s4-pit: does the PB<1 sleeve carry return?",
  metric_delta: 'raw book 0.1018 / sharpe 1.32 / total 15.74 / maxDD 5.56 vs reference 0.1217 / 1.32 / 32.93 / 20.76; sleeve on own ¥250k 62.96% / sharpe 1.87 / maxDD 20.90; implied s3=0 ablation (reference minus this curve) sharpe 1.32→0.73, obj 0.1217→≈−0.036, maxDD 20.76→20.74',
  window: 'TRAIN 2024 e9',
  finding: "SUPPORTED-BY-RULE (pre-registered: share ≥25% AND sleeve sharpe ≥1.0): s3 alone = 47.8% of the reference's net (¥157.4k), sleeve sharpe 1.87 on its own capital. 11 names / 13 buys; 600368 chosen on every rebalance 05-06..07-15. ⚠ ~55% of the sleeve's P&L (¥85.9k of ¥157.4k) is the 18,000 orphan 600368 bonus shares (10送3 2024-06-20) that the virtual sub-ledger never tracked and so never sold — they sat in the real account to 12-31. Ex-orphan the sleeve earns ~7.2pp of book (~28.6% on own capital), i.e. the level is about half a bookkeeping artifact. ρ(daily) vs 全A promoted pbm-e9-2 0.3574 (ORTHOGONAL band <0.4), vs reference 0.7142. Additivity across the three sleeve-only runs holds exactly (daily residual ≤ ¥100 on all 242 days), and the orphan shares appear in this curve and no other, so the attribution's ~8.6pp orphan line is reproduced, not a residual.",
  confidence: 'medium',
  flags: 'orphan-bonus-share artifact (~55% of sleeve P&L); single-name-event (600368, 601677); single-year SE≈1; 2024-inside-author-view (posted 2026-05-12)',
  description: 'build-pb-only.js; one asserted edit to g.strategy_weights; curve data/series/study_价值红利多腿_variants_q-e9-pb-only__train__e9.json (final 15.74 verified)',
  implication: "价值因子（破净） stays `proposed` despite meeting its rule: half the level is shares the strategy's own ledger did not know it owned, so promoting on this number would certify a bookkeeping bug as an edge. OPENS a correctness entry ahead of everything else that reads s3: q-e9-orphan-fix — after any 送转, sync g.sub_holdings to the real position so the sleeve sells what it actually holds — and its row (not this one) is what decides promotion; until then quote s3's level as a PAIR (with orphan 15.74pp / ex-orphan ~7.2pp of book). ALSO OPENS the integration reading: s3 is the one leg orthogonal to what 全A ships (ρ 0.36 vs pbm-e9-2), so if this family ever builds an integration candidate it is s3-led — re-check ρ on the orphan-fixed curve first, since the orphan shares are 6.5% of book held passively to year end.",
  spawned: 'q-e9-orphan-fix',
  edgeRef: '价值因子（破净）',
});

rq.recordFinding(FAM, {
  qId: 'q-e9-div-only',
  type: 'ablation',
  component_or_param: "s2+s4-only book (g.strategy_weights 0/0.25/0/0.25) on the reference q-e9-s4-pit: do the dividend sleeves carry the book?",
  metric_delta: 'raw book −0.0526 / sharpe 0.44 / total 9.89 / maxDD 15.15 vs reference 0.1217 / 1.32 / 32.93 / 20.76; pair on own ¥500k 19.78% / sharpe 0.61 / maxDD 27.15; implied s2=s4=0 ablation (reference minus this curve) sharpe 1.32→1.28 (−0.04), obj 0.1217→≈0.132, maxDD 20.76→9.82',
  window: 'TRAIN 2024 e9',
  finding: "UNRESOLVED under the pre-registered rule: share of reference net 30% (between the 25% refute and 50% support bars), pair sharpe 0.61 < 1.0. The two legs are not alike: s2 alone 29.79% / sharpe 1.15 / maxDD 16.14 on its ¥250k (15 names, top name 000683 = 22.5% of this book's net, five losers); s4 alone 9.77% / sharpe 0.16 / maxDD 42.47 (603156 +¥45.9k, 600398 −¥35.9k after four June rotations 600066↔600398). ρ s2–s4 0.51. ρ vs pbm-e9-2 0.3247, vs 93379f98 0.6292 (REDUNDANT band vs the 红利低频 parent), vs pb-only 0.4114. The dividend sleeves carried −10.79 of the reference's −13.52pp July and −8.64 of −9.74pp October. The page's own edge.test (s2=s4=0), implied by exact additivity, gives Δsharpe −0.04 against a declared support bar of ≤ −1.0, and removing the pair HALVES maxDD (20.76→9.82).",
  confidence: 'medium',
  flags: 'single-year SE≈1; s4 one-name (603156/600398); edge.test read by subtraction, not by its own run; 2024-inside-author-view (posted 2026-05-12)',
  description: 'build-div-only.js; one asserted edit to g.strategy_weights; curve data/series/study_价值红利多腿_variants_q-e9-div-only__train__e9.json (final 9.89 verified)',
  implication: "CLOSES q-e9-div-passive by its own condition: it was to run only if the pair's sharpe ≥ 1.0, and at 0.61 the passive-510880 control has nothing to discriminate, so it is dropped (not-triggered), not run. 股息率 stays `proposed` — but the evidence now leans against it, not toward it: the page's edge.test does not meet its support bar (Δsharpe −0.04) and the pair contributes most of the book's drawdown, so no later round may cite 股息率 as this book's source of return. Re-scopes the remaining dividend work to s2: s2 is the substantive leg (sharpe 1.15), s4 is a drag carried by one name, so q-e9-s2-order stays live (s2 carries P&L) while dvl-imp-3a (s4 1→3) and dvl-imp-4 (s4 persistence gate) are now improving a leg that is net harmful at the book level — their bar is the s4=0 book, not the reference. Integration: the pair is 0.63 vs 93379f98 and only 0.32 vs pbm-e9-2, so the dividend legs add nothing 全A's parent did not already have.",
  spawned: 'none',
  edgeRef: '股息率',
});

rq.recordFinding(FAM, {
  qId: 'q-e9-s1-only',
  type: 'ablation',
  component_or_param: "s1-only book (g.strategy_weights 0.25/0/0/0) + log-only U3 probes (roa>0.15 binding? size of retained_profit top-3) on the reference q-e9-s4-pit; plus the 3-run additivity check",
  metric_delta: 'raw book ≈−0.0343 / sharpe 0.33 / total 7.29 / maxDD 10.72 vs reference 0.1217 / 1.32 / 32.93 / 20.76; sleeve on own ¥250k 29.16% / sharpe 0.75 / maxDD 30.40; implied s1=0 ablation sharpe 1.32→1.20, obj 0.1217→≈0.102, maxDD 20.76→15.43',
  window: 'TRAIN 2024 e9',
  finding: "Trades byte-identical to the reference's s1 lines, so the log probes are valid instrumentation. Share of net 22.1% (between 10% refute and 25% support), sleeve sharpe 0.75 < 1.0. U3 probes: removing roa>0.15 grows s1's pool by ≤3.4% (median 1.0%) on 24 dates and roa>15 leaves 0–1 names, so the screen is near-inert and the % unit reading is confirmed; on s3 roa>0.15 cuts ≤16.7% (median 11.7%) — under the 20% bar, binds more than in s1. Size: all 24 picks in the top ~1% of 全A by market cap (median rank/N 0.0016); picks 600938 ×18, 601919 ×4, 000858 ×2; 600941 中国移动 is in the top-3 on 20/24 dates and never chosen. ρ vs pbm-e9-2 0.4231 — the highest of the three sleeve runs. ADDITIVITY: s1 72.9k + s3 157.4k + s2+s4 98.9k = 329.2k vs reference 329.3k, daily residual within ±¥100 (stored-curve rounding) on all 242 days: the sleeves add exactly and do not interact.",
  confidence: 'high',
  flags: 'single-name-event (600938 ×18/24); single-year SE≈1; 2024-inside-author-view (posted 2026-05-12)',
  description: 'build-s1-only.js; edit 1 g.strategy_weights, edit 2 log-only S1CNT/S1TOP3; curve data/series/study_价值红利多腿_variants_q-e9-s1-only__train__e9.json (final 7.29 verified)',
  implication: "REFUTES 盈利质量（ROA/ROIC） under U3's pre-registered rule (near-inert screen AND size pick both hold): s1 is a retained-profit-ranked mega-cap pick dominated by one energy name, and the quality filter does not choose anything — edge status flipped to refuted in this write. CLOSES dvl-imp-3b (s1 1→3): the gatekeeper made it conditional on this run, and widening a sleeve whose screen does not bind just adds more mega-caps by retained profit; dropped without running. CLOSES the 'roa>15 unit' test on s1 (0–1 names left; nothing to compare). REFUTES the prior that s1 is this book's diversifying leg (0.42 vs pbm-e9-2, above s3's 0.36). Because additivity is exact, every base-minus-a-sleeve question on this book is now answered by subtracting curves, at zero backtest cost — no future entry should spend minutes on an s_k=0 ablation of the reference.",
  spawned: 'none',
  edgeRef: '盈利质量（ROA/ROIC）',
});
console.log('ok');
