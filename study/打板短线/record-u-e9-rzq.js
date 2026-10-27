// u-e9-rzq — the epoch-6 closure u-rzq-deconf re-run on epoch 9's TRAIN 2024 window.
//   node -e "require('./study/打板短线/record-u-e9-rzq.js')"
// recordFinding stamps measuredEpoch (13th column) from the live harness config and marks the
// queue entry answered; idempotent via the qId check below.
const rq = require('../../utils/research-queue');
const F = '打板短线';
const have = new Set(rq.findings(F).map(f => f.qId));
const row = {
  qId: 'u-e9-rzq', type: 'isolate',
  component_or_param: 'u-rzq-deconf 在 epoch 9 重跑：variants/u-rzq-deconf.py = 基类 439385b4 + 弱转强腿保留在第 46 行的仓位计数里、只在下单循环里 continue（两行 diff，与 epoch-6 的变体同一文件）；--window train（2024-01-01→2024-12-31）；锚点 = 账本 e9 行 439385b4（obj 7.5458 / annual 798.96 / sharpe 11.46 / maxDD 44.38，曲线 H1 +933.1 / H2 −13.0，Q 220.8 / 222.0 / −1.3 / −11.8）',
  metric_delta: 'vs 锚点：obj 7.5458 → 6.0066（−1.5392，−20.4%）· annual 798.96 → 622.42（−176.5pp）· sharpe 11.46 → 11.25（−0.21）· maxDD 44.38 → 21.76（−22.6pp，减半；最深回撤由 08-30→10-22 移到 12-16→12-31）· vol 0.753 → 0.593 · 逐半年 H1 +933.1 → +414.9（−518pp，maxDD 12.5 两者相同）/ H2 −13.0 → **+40.3**（+53.3pp，maxDD 44.4 → 21.8）· 逐季 Q1 220.8 → 88.9 / Q2 222.0 → 172.5 / Q3 −1.3 → −4.8 / Q4 −11.8 → **+47.3**（+59pp）· 日收益相关 0.746（242 日，64 日逐位相同）· stats：笔数 122（81/41）→ 102（69/33）、win 0.664 → 0.676、盈亏比 1.72 → 2.44、均笔 +2.78% → +3.08%、1.50 → 1.51 天/轮、换手 0.271 → 0.225',
  window: 'TRAIN 2024-01-01→2024-12-31（epoch 9，365 日历日，242 交易日）',
  finding: '预注册证伪线（H2 变化 < 5pp）未触发（+53pp）；预测 A 成立：弱转强腿在 2024 同时是上半年肥尾（去腿后 H1 −518pp）和下半年亏损（H2 −13 → +40，全部在 Q4：−11.8 → +47.3）。epoch-6 闭合 u-rzq-deconf（「该腿 = 2022-H1 肥尾 + 2023-H2 全部亏损」）在 2024 窗上以同一消融复现，现为 2/2 年。obj −1.54（−20%）、sharpe −0.21、maxDD 减半、盈亏比 1.72 → 2.44。变体日志：逐季候选数 高开 9/15/13/44、低开 24/12/12/1、弱转强 6/8/11/10（跳过 35、下单 165）；19 天只有弱转强候选 ⇒ 变体持现金；12 个混合日按含弱转强的名额分仓。Q4 的构成本身换了（低开塌到 1 只、高开跳到 44）——2024-H2 是另一种构成的书，不只是少一条腿。⚠ 不是干净归因：腿仍在除数里，跳过它 = 现金闲置（曝险约 −20%）并改变后续成交，回撤减半有一部分是闲置现金而非更好的成交。可实现性不变（R=1）',
  confidence: 'high（同台同窗同文件的消融；方向与半年形状直接读自曲线）/ medium（量级：现金拖累未分离，去腿的 obj 损失含 −20% 曝险）',
  flags: 'stale-closure-reconfirmed-e9（u-rzq-deconf）· first-half-fat-tail-leg · not-clean-attribution（cash drag）· R1-family-understand-only · ⚠零滑点高估 · regime-specific（2024 单年）',
  description: 'algorithmId b3df4b4d6ebcd78c86d0dc3998771512 / backtestId 7081c0b2d9f64c219a0fddf1d5e2097d；SUMMARY train 2024-01-01 2024-12-31 365 622.42 622.42 11.25 21.76 completed；曲线 data/series/study_打板短线_variants_u-rzq-deconf__train__e9.json（242 点）；stats 自免费端点；≈7 JQ 分钟',
  implication: '关闭：stale 闭合 u-rzq-deconf 在现行台（epoch 9）重测后再次绑定——「弱转强腿是上半年肥尾也是下半年亏损」是机制级结论，不是 2022–23 窗口级的（u-rzq-deconf + u-e9-rzq，2/2 年）；§4 的「14 条 stale 闭合」里这一条已重测，不再是 REOPENABLE。关闭：把 29048a4f（弱转强单独成书，H1 −13 / H2 +138）读成基类弱转强腿的证据——那个反向形状属于那位作者的书（中小板宇宙、另一套过滤），不属于基类的腿。不打开候选：「去腿」把回撤减半靠的是持现金（19 个纯弱转强日空仓）而不是更好的成交，与 epoch-6 rejected 的 imp-4 同一形状，家族 exit gate 状态不变（R=1；valDeclinedPrior 9 的 reasoning 仍绑定，本条不碰 VAL）。打开（低优先、零成本优先）：若要把现金拖累从腿的 alpha 里分离，需在 19 个纯弱转强日把名额按另两腿重分（即 imp-4 在 2024 上的读数）——仅当 realizability 重评 ≥2 才值得 8 分钟',
  spawned: 'none',
  edgeRef: '涨停动量延续',
};
if (!have.has(row.qId)) { rq.recordFinding(F, row); console.log('recorded', row.qId); } else console.log('already recorded');
