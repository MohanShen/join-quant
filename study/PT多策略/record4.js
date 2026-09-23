// Fourth batch (idempotent by qId): the family's single epoch-6 VAL, spent on the base.
//   node -e "require('./study/PT多策略/record4.js')"
const rq = require('../../utils/research-queue');
const F = 'PT多策略';
const have = new Set(rq.findings(F).map(f => f.qId));
const rows = [
  {
    qId: 'val-base-e6', type: 'validate',
    component_or_param: '基类 fa0d3bd9（= baseline-e6.py，源码 + live OVERRIDE）在 VAL 2024-01-01→2025-12-31 上跑一次——本家族 epoch 6 的唯一一次验证，花在基类上（两条 improve 均 rejected，基类是 TRAIN 最优点）',
    metric_delta: 'VAL：total 1067.81 · annual 241.73 · sharpe 12.82 · maxDD 5.92 · obj 2.3581 ‖ 对照 TRAIN 锚点：annual 195.74 · sharpe 11.15 · maxDD 9.82 · obj 1.8592 ⇒ VAL 更高 +0.50 obj；逐年 2024 +373.60（maxDD 4.46 · vol 0.2284 · sharpe~ 7.02 · 上涨日 170/241）/ 2025 +147.40（maxDD 5.92 · vol 0.1545 · sharpe~ 5.86 · 172/243）',
    window: 'val 2024-01-01→2025-12-31（730d / 485 交易日）',
    finding: 'VAL 不但没有衰减，还高于 TRAIN：年化 242% / sharpe 12.8 / 回撤 5.9%，两年同号强正、上涨日 70%。2024-02 微盘踩踏对这本书只值 4.46% 回撤（2024 全年 maxDD）——它持有的是薄 ETF 的开盘偏离，不是微盘股 beta。四个年度（2022–2025）年化全在 +92% 到 +374% 之间、单年 maxDD 全 ≤ 9.8%：在「开盘价按成交量 5% 可成交」这个假设下，机制在四个 regime 里都成立',
    confidence: 'high',
    flags: 'VAL-spent · val-above-train · four-years-same-sign · 2024-02-crash-4.5pct-maxDD · ⚠零滑点 · ⚠开盘价成交假设（realizability 见 u-7 / §4）· gate-pass（sharpe 12.82）',
    description: 'study/PT多策略/baseline-e6.py；algorithmId 09acf503e04721fdc7a05631b1168d23；SUMMARY val 2024-01-01 2025-12-31 730 1067.81 241.73 12.82 5.92 completed；3 JQ 分钟（115 → 118）；val-budget 已记（pt-val-base-e6，第二次 VAL 被 VAL-BLOCKED）；曲线 data/series/study_PT多策略_baseline-e6__val__e6.json',
    implication: '关闭「VAL 会把它筛掉」：不会，它在 VAL 上更强。这把问题推回唯一没关的门——可实现性：TRAIN 与 VAL 的每一个数字都建立在「薄 ETF 的集合竞价开盘价能按全天成交量 5% 成交」上。下一步不是再一次 VAL（已花、也不该），而是 u-7：把执行从 09:30 挪到 14:50，看偏离在开盘之后还剩多少——那才是一个不在集合竞价里抢单的账户能拿到的部分。整合层引用本家族时按 §4 的可实现档位估值，不按 242%',
    spawned: 'u-7',
    edgeRef: '均值回归',
  },
];
let n = 0;
for (const r of rows) if (!have.has(r.qId)) { rq.recordFinding(F, r); n++; }
console.log(`record4: wrote ${n}, findings now ${rq.findings(F).length}`);
