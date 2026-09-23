// Third batch of the epoch-6 round (idempotent by qId): the two improve candidates.
//   node -e "require('./study/PT多策略/record3.js')"
// Anchor: total 772.01 / annual 195.74 / sharpe 11.15 / maxDD 9.82 / obj 1.8592; 2022 +300.50 (9.82) / 2023 +121.38 (2.69).
const rq = require('../../utils/research-queue');
const F = 'PT多策略';
const have = new Set(rq.findings(F).map(f => f.qId));
const W = 'train 2022-01-01→2023-12-31（729d / 484 交易日）';
const rows = [
  {
    qId: 'pt-imp-1', type: 'improve',
    component_or_param: '下界 5e6 → 1e7、保留 2e7 上界（丢掉 band 最薄的一半），一行——on-mechanism 于 流动性溢价，方向是可实现性变好的方向',
    metric_delta: 'vs 锚点：obj 1.8592→1.2859（−0.5733）· annual 195.74→137.68（−58.1pp）· sharpe 11.15→7.29 · maxDD 9.82→9.09（−0.7pp）· total 772.01→463.60 · 逐年 2022 +300.50→+181.24（maxDD 9.82→9.09）、2023 +121.38→+102.50（2.69→4.33）',
    window: W,
    finding: '丢掉最薄一半，年化少 58pp、回撤只浅 0.7pp：收益跟着薄尾走，回撤不跟。三档 band 单调：5e6–2e7 年化 196 / 1e7–2e7 138 / 5e7–1e8 23——越可成交越少赚，没有 ETF溢价 q-1 那种「下界过松、收紧反而更好」的甜点。ETF溢价 的 2e6 是股数下界、本家族的 5e6 是成交额下界，两者不是同一个量，甜点不迁移',
    confidence: 'high',
    flags: 'rejected · monotone-in-thinness · no-sweet-spot · gate-pass（sharpe 7.29）· realizability-veto-stands',
    description: 'enhance/candidates/pt-imp-1.py（一行 diff）；algorithmId 9f8423adaf9ba0348e9e55888bc037c4；SUMMARY train 2022-01-01 2023-12-31 729 463.60 137.68 7.29 9.09 completed；2 JQ 分钟（110 → 112）；曲线 data/series/enhance_candidates_pt-imp-1__train__e6.json',
    implication: '关闭 band 下界作为 improve（收紧单调变差；放松 = 走向 5% 参与上限也填不满的更薄名字，是容量幻觉）。流动性溢价 的 evidence 补上第三臂：band 三档单调。整合层引用本家族时，「可实现的版本」应按 1e7–2e7 的 138%/7.29 或 u-1 的 23%/0.94 估，取决于愿意假设多薄的名字能在开盘价成交',
    spawned: 'none',
    edgeRef: '流动性溢价',
  },
  {
    qId: 'pt-imp-2', type: 'improve',
    component_or_param: 'top-10 → top-5（作者从 5 放宽到 10「以求尽可能多地成交」），一行——on-mechanism 于 均值回归（集中到最深折价）',
    metric_delta: 'vs 锚点：obj 1.8592→1.7191（−0.1401）· annual 195.74→181.58（−14.2pp）· sharpe 11.15→10.49 · maxDD 9.82→9.67（−0.2pp）· total 772.01→690.61 · 逐年 2022 +300.50→+317.80（maxDD 9.82→9.67）、2023 +121.38→+92.35（2.69→2.74）',
    window: W,
    finding: '集中到 top-5 少赚 14pp、回撤不变；2022 反而多赚 17pp，2023 少赚 29pp。与 u-5 合读：深度有信息（加权 > 等权）但集中到 5 只不如 10 只——第 6–10 名在 2023 贡献正收益，因为 5% 参与上限下最深的 5 只吃不下全部资金（2023 vol 从 0.118 降到 0.098 = 资金留在现金里）。作者的放宽是填单宽度，不是分散',
    confidence: 'high',
    flags: 'rejected · fill-width-not-diversification · 2023-cash-drag · gate-pass（sharpe 10.49）',
    description: 'enhance/candidates/pt-imp-2.py（一行 diff）；algorithmId 065bd38bc8fc55338fd7ef5b48dc0e52；SUMMARY train 2022-01-01 2023-12-31 729 690.61 181.58 10.49 9.67 completed；3 JQ 分钟（112 → 115）；曲线 data/series/enhance_candidates_pt-imp-2__train__e6.json',
    implication: '关闭集中度作为 improve（top-5 变差；top-N > 10 = 更浅的折价，u-2 已示范流动名字只加回撤）。improve 队列清空：band 上界（u-2）、下界（imp-1）、权重（u-5）、集中度（imp-2）四个 on-mechanism 旋钮都不优于原值，基类 fa0d3bd9 是这条血统在 epoch 6 上的最优点。本家族的一次 VAL 花在基类上',
    spawned: 'val-base-e6',
    edgeRef: '均值回归',
  },
];
let n = 0;
for (const r of rows) if (!have.has(r.qId)) { rq.recordFinding(F, r); n++; }
console.log(`record3: wrote ${n}, findings now ${rq.findings(F).length}`);
