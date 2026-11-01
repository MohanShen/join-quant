// Recorder helper for u-4 (动量 inversion in 摸狗: get_rank ascending=False -> True). One-shot;
// guarded so a re-run cannot double-append. Also queues u-8 (the edge's declared 摸狗 -> cash test).
const rq = require('../../utils/research-queue');
const F = '小盘ETF双轨切换';
if (rq.findings(F).some(r => r.qId === 'u-4')) { console.log('u-4 already recorded'); process.exit(0); }

if (!rq.load(F).some(e => e.id === 'u-8')) {
  rq.add(F, {
    id: 'u-8',
    kind: 'understand',
    title: '摸狗 -> cash: the 摸狗 branch skips the ETF buy (keeps the sell of non-target holdings)',
    hypothesis: 'The 摸狗 leg contributes positive return beyond being out of micro-caps; holding cash on 摸狗 days loses a material part of the base objective.',
    why: 'The 动量 edge\'s own declared test (摸狗 -> cash), which u-4 did NOT run: u-4 inverted the ranking within the 4-ETF pool, and the inverted leg stayed positive (+2.92 over the strict 摸狗 split), so part of 摸狗 is pool beta and inversion cannot separate ranking from beta. SUPPORTS 动量 as a contributor if the base beats u-8 by >= 0.1 objective; < 0.05 = 摸狗 is mere risk-off (动量 refuted as a return source). Between = inconclusive. 偷鸡 decision days are unchanged (DDDD reads 399101 independently), so the read is not exposed to the ~0.6 lock-phase noise. Report 摸狗-day return on the strict interior split AND the 5-boundary-day split, as u-4 did. Cost ~3-6 backtest-min.',
    design: 'Base 0d1bbe83, epoch-9 pins. In the 摸狗 branch, keep the sell of every holding that is not the target (so stocks and ETFs are still liquidated on 偷鸡 exit) but skip the ETF order_target_value buy. 偷鸡 logic, DDDD, 30-day lock and 14:00 check_limit_up verbatim. Log daily mode so the 摸狗/偷鸡 split is reproducible.',
    from: ['u-4 (momentum inversion: 摸狗 +15.77 -> +2.92 strict / 53% kept on boundary-inclusive split; inverted leg still positive)', 'edge 动量 .test (摸狗 -> cash)'],
    edgeRef: '动量',
    rank: 1,
    status: 'queued',
    note: 'recorder 2026-11-01 (after u-4): spawned as the declared 动量 test; inversion was ambiguous as the gatekeeper anticipated.',
  });
}

rq.recordFinding(F, {
  qId: 'u-4',
  type: 'understand',
  component_or_param: '摸狗 get_rank：ascending=False → True（持 4 只 ETF 中最弱的一只；唯一改动，偷鸡决策日与持股不变）',
  metric_delta: 'Δobjective −0.1676 (0.7266→0.5590); sharpe 2.85→2.11; total 89.75→74.06%; maxDD 17.09→18.16',
  window: 'TRAIN 2024 (epoch 9)',
  finding: 'Momentum inversion (variant u-4-mom-inverted, builder build-u4.js, algorithmId ce3c071f9111f4339de0b161361def48, curve study_小盘ETF双轨切换_variants_u-4-mom-inverted__train__e9, final cum 74.06 / maxDD 18.16 verified) scores total 74.06% / sharpe 2.11 / maxDD 18.16 / objective 0.5590. 偷鸡 decision days and names unchanged. 摸狗 days (151, strict interior split): +15.77 → +2.92 (18.5% kept; queue thresholds restated on this split: <50% supports, ≥75% refutes). 偷鸡 periods +63.90 → +69.12 — the whole gap sits on 5 boundary days where the held ETF differs (the entry-day ETF sale and the last-day ETF purchase). Moving those 5 boundary days into 摸狗: base +21.27 vs u-4 +11.20 = 52.7% kept, between the thresholds. The inverted book held 159915 创业板 90 days, 513100 纳指 20, 510180 上证180 18, 518880 黄金 12; 10 switches.',
  confidence: 'medium',
  flags: '⚠零滑点高估; regime-specific (one-year TRAIN); split-sensitive (18.5% strict vs 52.7% boundary-inclusive); 4-ETF pool (inversion ≠ cash control)',
  description: 'Gatekeeper-ranked weaker 动量 test (inversion, after ETF动量 q-e9-2). Not the edge\'s declared test (摸狗 → cash).',
  implication: '动量 is SUPPORTED but not measured: ranking within the 4-ETF pool carries information in 2024 on the strict split (18.5% kept) but only borderline on the robust one (53%), and the inverted 摸狗 leg is still positive, so part of 摸狗\'s return is pool beta (all 4 ETFs rose in parts of 2024) that inversion cannot separate from ranking. Sizes the leg: 摸狗 ranking is worth ~0.17 of the base\'s 0.73 objective — the minor leg; the book is mostly 规模因子 × Feb-2024 timing. Opens u-8 = the edge\'s declared test (摸狗 branch holds cash, sells kept): base beating u-8 by ≥0.1 objective supports 动量 as a contributor, <0.05 makes 摸狗 mere risk-off. 动量 stays proposed until u-8 runs; further ranking-direction variants inside the 4-ETF pool are closed (inversion has been run and cannot resolve beta vs rank).',
  spawned: 'u-8',
  edgeRef: '动量',
});
console.log('ok', rq.load(F).find(x => x.id === 'u-4').status, rq.load(F).find(x => x.id === 'u-8').status);
