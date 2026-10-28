// Records the epoch-9 round's findings into study/趋势技术/findings.tsv (idempotent by qId).
//   node -e "require('./study/趋势技术/record-e9.js')"
const rq = require('../../utils/research-queue');
const F = '趋势技术';
const have = new Set(rq.findings(F).map(f => f.qId));
const rows = [
  {
    qId: 'q-e9-val', type: 'validate',
    component_or_param: '家族 epoch-9 冠军 9befa9b8（600030 中信证券 单股 MA10 择时：价格 > MA10 全仓、< MA10 空仓；非页面基类 33b1b1e3，后者 08:00 读当日收盘，在 avoid_future_data 下无 epoch-9 行）在 VAL 2025 上的唯一一次验证',
    metric_delta: 'TRAIN 2024 obj 0.1912 / sharpe 1.03 / total 34.13 / maxDD 15.01 → VAL 2025 obj −0.1143 / sharpe −0.31 / total −0.72 / maxDD 10.71；gate_val fail（−0.31 < 1.0）',
    window: 'val 2025-01-01→2025-12-31（364d / 243 交易日）',
    finding: '冠军在 2025 上归零：全年 −0.72%、回撤 10.7%、sharpe −0.31，过不了 1.0 闸门。2024 的 34% 是一只券商股在 2024-09 V 型反转里的 beta（MA10 让它在场），择时器本身没有带到 2025 的东西；TRAIN 过闸只有 0.03 的边际，本就是桶里最薄的一次通过',
    confidence: 'high',
    flags: 'VAL-spent（epoch 9，本家族唯一一次）· gate_val-fail · single-stock · thin-train-margin(+0.03) · 零滑点台（中信证券流动性极深，折价可忽略）',
    description: 'study/趋势技术/champion-e9.py（build-e9.js：py2to3(源码)+OVERRIDE，与 normalizer 构造逐字节一致，TRAIN 曲线 …__train__e9 复现 ledger 行 34.13/15.01）；algorithmId 63c6c78d15c536ae8ce9a30c44f13f93；SUMMARY val 2025-01-01 2025-12-31 364 -0.72 -0.72 -0.31 10.71 completed；曲线 data/series/2026-06-08_十日均线策略-9befa9b8__val__e9.json（final cum −0.72，maxDD 10.71）；归档 validated_strategies/qsjs-e9-9befa9b8.py（gate_val: fail）；约 1 JQ 分钟',
    implication: '本家族 epoch 9 的 VAL 已花在一本失败的书上，出口闸门在本 bench 上到此为止（owner none/human，不再是 research 待办）——除非新成员改变冠军。关闭：单标的均线择时作为本桶的候选方向（五个同胞 + 冠军，TRAIN 全部 ≤1.03，VAL 归零）。打开（只在 TRAIN，不花验证）：桶内真正的血统 RPS 基类 33b1b1e3 在 epoch 9 上还没有清洁数——它的 e6 清洁书（e6-1，previous_date 改动）应在 TRAIN 2024 上复测一次，这是 8 条 stale closure 能否沿用的前提；§4 的「桶应拆」仍是结构性修复',
    spawned: 'q-e9-rps-clean',
    edgeRef: '',
  },
];
let n = 0;
for (const r of rows) if (!have.has(r.qId)) { rq.recordFinding(F, r); n++; }
console.log(`record-e9: wrote ${n}, findings now ${rq.findings(F).length}`);
