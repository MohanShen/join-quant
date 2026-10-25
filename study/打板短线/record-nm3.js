// Step-0 (new-members) finding for the 2026-10-25 re-invocation — the first under epoch 9
// (TRAIN 2024 only, VAL 2025, gate 1.0; every pre-9 row re-measured). Zero cost. Idempotent by qId.
//   node -e "require('./study/打板短线/record-nm3.js')"
const rq = require('../../utils/research-queue');
const F = '打板短线';
const have = new Set(rq.findings(F).map(f => f.qId));
const row = {
  qId: 'nm-2026-10-25', type: 'probe',
  component_or_param: '三个新成员（git b15627c）在 epoch 9 上：96fb1ca0 竞价擒龙，年化245.83%（obj 7.8535 / sharpe 11.95 / annual 824 / maxDD 38.9，epoch-9 全库第一，realizabilityFlags call-auction-entry）；a170cc02 带涨停基因的小市值 Q1战报（1.2056 / 3.88）；d29621b6 模拟近一年的打板策略（1.2260 / 2.99）。零成本：账本行 + git diff --no-index + 源码头部',
  metric_delta: 'a170cc02 vs c9e0451d：4/4 行差（clone 头），epoch-9 行逐位相同（142.34 / 3.88 / 21.78）⇒ 同一代码体；d29621b6 vs 6ada2917：5/3 行差，epoch-9 行逐位相同（137.14 / 2.99 / 14.54）⇒ 同一代码体；96fb1ca0 vs 基类 439385b4：387/185 行差，vs a7f60565 418/485——是同一血统（子匀工具箱：09:26 竞价 get_call_auction 入场、MarketOrderStyle(day_open)、market_cap<70 过滤、11:25 / 14:50 两次 sell，一进二）的另一本书，不是副本；epoch 9 上基类 439385b4 自己 7.5458 / 11.46，两者相差 0.31。家族 epoch-9 前三名全是本血统（7.85 / 7.55 / 5.29，sharpe 11+），隐含波动 47–70%，不是抓取伪影',
  window: 'TRAIN 2024-01-01→2024-12-31（epoch 9 归一化行；本家族 20 条既有 finding 全部量在 epoch 6 的 2022–23 窗上）',
  finding: '三个新成员里两个是已读成员的 clone 副本，一个是基类血统在 2024 窗上的新头名——没有提出本家族未探索过的问题。epoch 9 把窗口换成 2024 单年，本血统的 TRAIN 读数从 0.97 跳到 7.5–7.9：这与 epoch-6 VAL 已经量过的 2024（基类 +799%，val-base-e6）一致，是同一个「上半年肥尾」regime 事件被换成了 TRAIN，不是新的机制信息。家族的 edge（涨停动量延续 measured、规模因子 对子血统 measured、涨停基因 refuted）全部是机制级结论，不随窗口改变；而决定家族去向的是 realizability = 1（measured：买昨日涨停次日开盘，一字板买不到），exit gate 在任何重测或 VAL 之前就 REJECT（owner none）',
  confidence: 'high',
  flags: 'zero-cost · step-0-exit · two-clone-duplicates · epoch-9-leader-is-this-lineage · findings-are-epoch-6 · exit-gate-rejected-R1 · val-declined-9',
  description: '数据：harness/normalize-train.tsv epoch-9 行；git diff --no-index 三对；strategies/2026-07-06_…-96fb1ca0.py 头 30 行；node utils/integrate-eligible.js 打板短线（REJECTED realizability 1 < 2）；node utils/val-budget.js（epoch 9 ALLOWED first-of-epoch，本轮不花）',
  implication: '关闭「新成员 ⇒ 新一轮」与「epoch 9 的头名需要重新研究」：机制结论已在 epoch 6 量完，2024 的数字是已知 regime 的另一面。关闭 epoch 9 的 VAL（写入 valDeclined: 9）：家族被 exit gate 以 realizability 1 终局拒绝，VAL 改变不了它能否进入 shipping set；且本血统的作者都在 2026 年发帖、VAL 2025 对他们是样本内，与 val-base-e6 的告诫相同。重开条件只有一个：harness 加入可成交性建模（成交量 / 封板过滤）并把 realizability 重新量到 ≥2——那是人类的 epoch 决定，不是本家族的 improve。整合层 / type 层引用本家族请继续按 R=1 与 realism 三重折扣读 7.85',
  spawned: 'none',
  edgeRef: '涨停动量延续',
};
if (!have.has(row.qId)) { rq.recordFinding(F, row); console.log('recorded', row.qId); } else console.log('already recorded');
