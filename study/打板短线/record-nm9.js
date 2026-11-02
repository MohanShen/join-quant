// Step-0 (new-members) finding for the 2026-11-02 re-invocation. Zero cost. Idempotent by qId.
//   node -e "require('./study/打板短线/record-nm9.js')"
const rq = require('../../utils/research-queue');
const F = '打板短线';
const have = new Set(rq.findings(F).map(f => f.qId));
const row = {
  qId: 'nm-2026-11-02', type: 'probe',
  component_or_param: '新成员 6e532250 一进二策略左压函数咨询（git 197e004：基类 439385b4 首板高开 / 低开 / 弱转强 三腿的分叉，同 09:26 买、11:25 / 14:50 卖、MA5 止损、day_open 市价单）。差异：首板定义更严（昨日涨停且 D-1、D-2 都未曾触板）；左压检查重构为 rise_low_volume()（同一规则，函数化）；新增 10:00 sell_heavy_turnover（持仓昨日最高价处于 60 日相对位置 ≥0.85、昨日量比 ≥0.5、昨日收盘位置 ≤0.65 且现价低于昨收 ⇒ 卖）。epoch 9：obj **11.3000** / annual 1163.33 / sharpe 16.81 / maxDD 33.33，过闸——家族与全台新头名（前头名 竞价擒龙 7.8535）；call-auction-entry',
  metric_delta: '曲线自洽（零成本）：曲线末值 1163.33 = 账本 total、曲线回撤 33.33 = 账本 maxDD，隐含波动 ≈69%（<150%，非抓取伪影）。2024 逐半年 H1 +857.2 / H2 +32.0；逐季 +199.2 / +219.9 / +58.2 / −16.6。对照同窗：基类 +933 / −13（obj 7.5458）',
  window: 'TRAIN 2024-01-01→2024-12-31（epoch 9 归一化行与曲线切片）',
  finding: '基类三腿书加一条 10:00 高位放量离场与更严的首板定义，2024 objective 7.55 → 11.30：上半年与基类相当（+857 vs +933），差别几乎全在下半年（+32 vs −13，Q3 +58）。形状仍是基类血统的上半年肥尾。新增部件全部读 previous_date 的日线与 10:00 的 last_price，无未来数据；入场仍是 09:26 竞价后 day_open 市价，可实现性问题与基类相同。头名的数字真实（曲线与账本逐位一致），但它是 R=1 家族里的头名',
  confidence: 'high（数字与形状直接）/ low（把下半年改善归因到 sell_heavy_turnover 还是首板定义：未做消融）',
  flags: 'zero-cost · step-0-exit · 439385b4-three-leg-fork · new-family-and-bench-top（11.30）· curve-ledger-agree · first-half-fat-tail · call-auction-entry · R1-family',
  description: '数据：harness/normalize-train.tsv e9 行；data/series/<slug>__train__e9.json（末值、回撤、切片）；diff -b 对基类 439385b4；源码阅读 rise_low_volume / sell_heavy_turnover / sell；data/family-assignments.tsv（git 197e004）',
  implication: '不打开实验：下半年 +45pp 的归因（10:00 高位放量离场 vs 更严首板定义）是同一 edge 的离场 / 执行细节，单次消融约 8 分钟可答，但家族 R=1 在 exit gate 之前终局拒绝，任何结果都无处可去，且不改变 涨停动量延续 的 status。若将来出现可成交的入场（R≥2 的 fill 模型重新打分），这是第一条该做的消融（sell_heavy_turnover 关掉，单点 diff）。头名换人不改变 VAL 决定：valReopened: 9 下先前 basis 仍绑定（R=1；VAL 2025 对 2026 作者在样本内），不花。对全台读者：当前 epoch 9 头名是 R=1 的打板书，与 CLAUDE.md「台面顶部都是涨停追逐」一致，应按 VAL / OOS 而非 TRAIN 排名阅读',
  spawned: 'none',
  edgeRef: '涨停动量延续',
};
if (!have.has(row.qId)) { rq.recordFinding(F, row); console.log('recorded', row.qId); } else console.log('already recorded');
