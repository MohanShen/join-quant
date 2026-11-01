// Step-0 (new-members) finding for the 2026-11-01 re-invocation. Zero cost. Idempotent by qId.
//   node -e "require('./study/打板短线/record-nm8.js')"
const rq = require('../../utils/research-queue');
const F = '打板短线';
const have = new Set(rq.findings(F).map(f => f.qId));
const row = {
  qId: 'nm-2026-11-01', type: 'probe',
  component_or_param: '新成员 bd771016 模拟交易信号微信推送延迟问题（git fab32d6：基类 439385b4 首板低开腿的分叉——同 prepare_stock_list、60 日相对位置 ≤0.5、低开带 0.96–0.97、均价涨幅 + 成交额 7e8–19e8 + 市值 70–520 亿过滤；09:28 买（基类 09:26），MarketOrderStyle(day_open)；卖出拆成 10:15 / 11:00 / 14:00，去掉 MA5 止损与 1e8 成交额下限）。epoch 9：obj 2.2204 / annual 250.48 / sharpe 4.25 / maxDD 28.44，过闸；call-auction-entry',
  metric_delta: '2024 曲线逐半年（零成本）：H1 +324.8 / H2 −17.5；逐季 +79.7 / +136.3 / −8.9 / −9.4。对照同窗：基类 +933 / −13、低开腿另一套代码 6ada2917 +136 / +0.5、弱转强单腿 12ec85b6 +172 / +20',
  window: 'TRAIN 2024-01-01→2024-12-31（epoch 9 归一化行与曲线切片）',
  finding: '基类的首板低开腿单独成书（基类过滤逐字、09:28 入场、拆分卖出）在 2024 是典型的基类血统形状：上半年 +325、下半年 −17.5（Q3 / Q4 都负）。比 6ada2917（另一套低开腿代码，H2 +0.5）的下半年更差，比基类整书的上半年弱——即整书的 H1 肥尾不只来自低开腿。不提出新问题：低开腿的归属、半年形状与「形状跟着过滤走」都已由 u-rzq-deconf / u-e9-rzq / nm-2026-10-31 回答；入场仍在 9:26–9:29 竞价窗口 + day_open 市价，R=1 理由不变',
  confidence: 'med（形状读数直接；跨书比较非同一代码的消融）',
  flags: 'zero-cost · step-0-exit · 439385b4-低开腿-fork · first-half-fat-tail · call-auction-entry · R1-family',
  description: '数据：harness/normalize-train.tsv e9 行；data/series/<slug>__train__e9.json 切片；源码 grep（run_daily / MarketOrderStyle）；data/family-assignments.tsv（git fab32d6）',
  implication: '关闭对 bd771016 的单独研究：基类单腿分叉，家族 R=1 终局拒绝（09:28 竞价后 day_open 市价入场，同一可实现性问题），valReopened: 9 但先前 basis 仍绑定，不花 VAL。不打开实验：09:26→09:28 的入场时点差与卖出拆分都只是同腿的执行细节，测出来也无处可去（无候选能过 exit gate）',
  spawned: 'none',
  edgeRef: '涨停动量延续',
};
if (!have.has(row.qId)) { rq.recordFinding(F, row); console.log('recorded', row.qId); } else console.log('already recorded');
