// Fifth batch (idempotent by qId): u-7, the realizability probe.
//   node -e "require('./study/PT多策略/record5.js')"
// Anchor: total 772.01 / annual 195.74 / sharpe 11.15 / maxDD 9.82 / obj 1.8592; 2022 +300.50 (9.82) / 2023 +121.38 (2.69).
const rq = require('../../utils/research-queue');
const F = 'PT多策略';
const have = new Set(rq.findings(F).map(f => f.qId));
const W = 'train 2022-01-01→2023-12-31（729d / 484 交易日）';
const rows = [
  {
    qId: 'u-7', type: 'probe',
    component_or_param: '执行时点：run_daily(market_open) 09:30 → 14:50，一行；信号仍是 09:25 的集合竞价开盘价 vs T−1 净值（日频回测里 09:30 单以开盘价成交、14:50 单以收盘价成交）',
    metric_delta: 'vs 锚点：obj 1.8592→−0.5601（−2.4193）· annual 195.74→−16.05（−211.8pp）· sharpe 11.15→−1.09 · maxDD 9.82→39.96（+30.1pp）· total 772.01→−29.49 · 逐年 2022 / 2023 见 description；对照 u-4 无信号 universe：annual −24.04 / maxDD 43.30',
    window: W,
    finding: '同一信号、只把成交从开盘价挪到收盘价，两年从 +772% 变成 −29%，回撤 40%——落到与「无信号最薄 10 只」（u-4，−42%）同一量级。开盘价对净值的偏离到收盘不但已经回归，还越过了：在收盘价买那些开盘折价最深的薄 ETF，拿到的是薄 ETF universe 的负漂移。收益 100% 是「在集合竞价的成交价上买到」这一件事，没有任何部分持续到日内可交易的时段',
    confidence: 'high',
    flags: 'realizability-DECISIVE · auction-print-only · matches-universe-control · both-years-negative · DQ',
    description: 'variants/u-7_exec-1450.py（一行 diff）；algorithmId 732c02c78a93da689f2d56a51d5e0a64；SUMMARY train 2022-01-01 2023-12-31 729 -29.49 -16.05 -1.09 39.96 completed；~3 JQ 分钟（120 → ~123）；曲线 data/series/study_PT多策略_variants_u-7_exec-1450__train__e6.json',
    implication: '关闭一切以 TRAIN/VAL 头条为准的引用：196% / 242% 是「按全天成交量 5% 在集合竞价成交价上成交」的回测伪影，一个不能在开盘集合竞价里以那口价成交的账户拿到的是负数。整合层与 type 层不得把本家族当作可拼接的 sleeve；component 登记（若有）只能登记「薄 ETF 集合竞价开盘价偏离净值」这个观察本身，不登记收益。关闭 improve 的全部方向（band/权重/集中度已量、执行时点已量）。家族 status 建议 DQ-realizability，由人裁决；本轮不改 status',
    spawned: 'none',
    edgeRef: '均值回归',
  },
];
let n = 0;
for (const r of rows) if (!have.has(r.qId)) { rq.recordFinding(F, r); n++; }
console.log(`record5: wrote ${n}, findings now ${rq.findings(F).length}`);
