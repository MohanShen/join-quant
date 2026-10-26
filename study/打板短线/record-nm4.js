// Step-0 (new-members) finding for the 2026-10-26 re-invocation. Zero cost. Idempotent by qId.
//   node -e "require('./study/打板短线/record-nm4.js')"
const rq = require('../../utils/research-queue');
const F = '打板短线';
const have = new Set(rq.findings(F).map(f => f.qId));
const row = {
  qId: 'nm-2026-10-26', type: 'probe',
  component_or_param: '新成员 5d88889d 多因子共振策略（git bb3284e：小狮子 V2.2 涨停基因 代码体的分叉）：流通市值最小 200 只统一池 → 四路选股投票（涨停基因 get_history_highlimit + get_start_point、资金流、eps×市值复合、行业分散）→ 票数排序取前 N，周频；616 行，与 c9e0451d 541/552 行差。epoch 9：obj 0.3195 / annual 76.52 / sharpe 1.57 / maxDD 44.57，过闸（1.0）',
  metric_delta: 'vs 子血统基类 c9e0451d 同窗（epoch 9：obj 1.2056 / sharpe 3.88 / maxDD 21.78）：obj −0.89、sharpe −2.3、maxDD 翻倍；vs b3751277（1.3443 / 4.29）亦同向。四路投票的「共振」在 2024 上输给它自己的单一 涨停基因 筛选——方向明确，非同台消融，不给量级',
  window: 'TRAIN 2024-01-01→2024-12-31（epoch 9 归一化行）',
  finding: '这是 涨停基因 子血统的又一本书，而且是更差的一本：把 涨停基因 和另外三路筛选投票合成，2024 上比单一筛选的父本少 0.89 objective、回撤 44.6%（2024-02 微盘踩踏整段吃下）。它没有提出子血统未探索过的问题——jy-u-1 / jy-u-2 已把子血统定性为「规模因子 地板 + size 条件 overlay」，本书只是在同一地板上多叠了三层筛子并稀释了 overlay。对本家族的 edge（涨停动量延续）无关：没有竞价入场。14 条 stale 闭合（epoch 6 窗上做出的）原则上可重开，但本家族被 exit gate 以 measured realizability 1 终局拒绝、epoch 9 VAL 已声明不花，重开任何一条都买不到可发货的东西；清除条件与 valDeclinedBasis 相同',
  confidence: 'med（方向：父本与分叉同窗对比清楚）/ low（量级：非消融）',
  flags: 'zero-cost · step-0-exit · 涨停基因-sublineage-fork · worse-than-parent-on-2024 · no-auction-entry · stale-closures-not-reopened（R=1 terminal）',
  description: '数据：harness/normalize-train.tsv epoch-9 行；git diff --no-index --numstat vs c9e0451d / b3751277；源码第 103–279 行（get_unified_stock_pool / get_stock_list_limitgene / multi_strategy_get_stock_list）；git show bb3284e',
  implication: '关闭「多因子投票是子血统的改进方向」：同窗比父本差 0.89、回撤翻倍，而且是在 小市值 地板上的操作，属 小市值 家族的问题。维持 valDeclined: 9 与「子血统并入 小市值」的建议——本书与 c9e0451d / a170cc02 / b3751277 / c658ef98 / d5b83074 一起走。不重开 stale 闭合：exit gate 的 R=1 拒绝在任何重测或 VAL 之前生效，重开的产出无处可去；若 harness 加入可成交性建模并重评 realizability ≥2，再按 staleClosures 的 reasoning 逐条判断（机制级的仍成立，量级/窗口级的重测）',
  spawned: 'none',
  edgeRef: '规模因子',
};
if (!have.has(row.qId)) { rq.recordFinding(F, row); console.log('recorded', row.qId); } else console.log('already recorded');
