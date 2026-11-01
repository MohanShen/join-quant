// Step-0 (new-members) finding for the 2026-10-31 re-invocation. Zero cost. Idempotent by qId.
//   node -e "require('./study/打板短线/record-nm7.js')"
const rq = require('../../utils/research-queue');
const F = '打板短线';
const have = new Set(rq.findings(F).map(f => f.qId));
const row = {
  qId: 'nm-2026-10-31', type: 'probe',
  component_or_param: '新成员 12ec85b6 关于策略运行时和回测不一致的问题（git 5fbad89：与 439385b4 共享辅助函数体；只做弱转强腿——前日曾涨停未封、前前日未涨停，均价/成交额 3e8–19e8/市值 70–520 亿/左压放量过滤，09:26:01 竞价量比 ≥3%、竞价价位 0.98–1.09 后 MarketOrderStyle(day_open) 买 1 只，11:28 / 14:50 卖）。epoch 9：obj 1.7901 / annual 224.98 / sharpe 3.56 / maxDD 45.97，过闸；call-auction-entry',
  metric_delta: '2024 曲线逐半年（零成本）：H1 +171.6 / H2 +19.6；逐季 +113.1 / +27.4 / −33.4 / +79.6。对照同窗：基类 +933 / −13、u-e9-rzq（基类去弱转强腿）+415 / +40、弱转强单独 29048a4f（另一作者的过滤）−13 / +138、e1053979 连板 −39 / +117',
  window: 'TRAIN 2024-01-01→2024-12-31（epoch 9 归一化行与曲线切片）',
  finding: '在基类血统的过滤（成交额/市值/左压/竞价位）下单独成书的弱转强腿，2024 仍是上半年肥尾（H1 +172 / H2 +20），与 u-e9-rzq 对基类自身弱转强腿的读数同向，与 29048a4f（另一作者、中小板宇宙）的反向形状不同。所以 nm-2026-10-30 的措辞「哪条腿在哪半年赚由那本书的过滤与仓位决定」再得一例：同一血统过滤下，弱转强也是 H1 肥尾；反向形状跟着过滤走，不跟着腿名走。成员本身是同血统单腿书，过闸但 maxDD 46%，不改变家族任何结论',
  confidence: 'med（形状读数直接；跨书推断只到方向，非同一代码的消融）',
  flags: 'zero-cost · step-0-exit · 439385b4-helper-lineage · 弱转强-single-leg · first-half-fat-tail · call-auction-entry · R1-family',
  description: '数据：harness/normalize-train.tsv e9 行；data/series/<slug>__train__e9.json 切片；源码阅读（get_stock_list / buy 两段 / sell）；git show 5fbad89',
  implication: '关闭对 12ec85b6 的单独研究：同血统单腿书、家族 R=1 终局拒绝（09:26 竞价 + day_open 市价入场，与基类同一可实现性问题），valReopened: 9 但先前 basis 仍绑定，不花 VAL。§4 的 regime 措辞不再收窄：「上半年肥尾」在基类血统过滤下对首板两腿与弱转强腿都成立，反向形状只出现在其它作者的过滤下——不打开实验，要证明需在同一代码里换过滤，是新书不是消融，且产出无处可去',
  spawned: 'none',
  edgeRef: '涨停动量延续',
};
if (!have.has(row.qId)) { rq.recordFinding(F, row); console.log('recorded', row.qId); } else console.log('already recorded');
