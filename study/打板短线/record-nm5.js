// Step-0 (new-members) finding for the 2026-10-27 re-invocation — three members, read at zero cost,
// plus a free half-year split of the 2024 curves that turns one stale closure into a live question.
//   node -e "require('./study/打板短线/record-nm5.js')"
const rq = require('../../utils/research-queue');
const F = '打板短线';
const have = new Set(rq.findings(F).map(f => f.qId));
const row = {
  qId: 'nm-2026-10-27', type: 'probe',
  component_or_param: '三个新成员（人工分配）：004aca1c 重研可SHI盘的打板策略（5070 行打板框架，首板 高开/低开/反转 三池与 38ca196e / 96fb1ca0 / e73c9d89 共享，09:27:27 竞价买、call-auction-entry）；29048a4f 中小板弱转强修复版（弱转强腿单独成书：09:26 筛 09:27 买、13:00 / 14:55 卖，call-auction-entry）；b0c225d4 叠加涨停基因小市值·1/4月五福（涨停基因 链 + 1/4 月切换五福 ETF，涨停次数过滤是死代码）。epoch 9：1.0693 / 3.29 / dd 23.2；0.7897 / 2.38 / dd 27.5；1.0492 / 3.12 / dd 26.4，三本都过闸',
  metric_delta: '2024 曲线逐半年（零成本，data/series e9）：基类 439385b4 H1 +933.1 / H2 −13.0（Q 221 / 222 / −1 / −12）；96fb1ca0 +875.6 / −5.3；低开腿 6ada2917 +135.9 / +0.5；高开腿 e73c9d89 +17.9 / +47.8；**弱转强单独 29048a4f −13.3 / +138.1（Q4 +82.5）**；004aca1c +58.3 / +45.4；涨停基因 c9e0451d +37.6 / +76.1；b0c225d4 +60.9 / +43.8',
  window: 'TRAIN 2024-01-01→2024-12-31（epoch 9 归一化行与曲线切片）',
  finding: '基类血统在 2024 再次是「上半年肥尾、下半年退潮」（基类 +933 / −13，竞价擒龙 +876 / −5），连同 val-base-e6 的 2022–25 读数已是 5/5 年。但弱转强腿单独成书（29048a4f，中小板宇宙、另一作者的过滤）在 2024 是反过来的：H1 −13、H2 +138、Q4 +82——而 epoch-6 的 u-rzq-deconf 把弱转强腿定为「2022-H1 肥尾 + 2023-H2 全部亏损」。两者不矛盾（不同代码、不同年份），但它把那条 stale 闭合变成一个在现行台上可证伪的分歧：2024 的基类 H2 亏损到底是不是这条腿。三本新书本身没有提出其它新问题：004aca1c 是同血统的大框架，b0c225d4 是子血统的组合书（随 涨停基因 一起并入 小市值）',
  confidence: 'high（形状读数直接来自曲线）/ low（29048a4f 对基类腿的推断：非同一代码）',
  flags: 'zero-cost · first-half-fat-tail-5-of-5 · stale-closure-made-live（u-rzq-deconf）· 弱转强-standalone-opposite-shape-2024 · R1-family（understand only，无候选）',
  description: '数据：harness/normalize-train.tsv e9 行；data/series/<slug>__train__e9.json 切片；源码 grep（29048a4f run_daily 行、004aca1c run_daily / get_call_auction 行）；git log data/family-assignments.tsv',
  implication: '打开 u-e9-rzq（一次、单年窗 ≈ 8 分钟）：在 2024 上重跑 u-rzq-deconf。预测 A：去腿后 H1 大降、H2 由负转正 ⇒ 闭合跨窗成立；预测 B：去腿后 H2 更差 ⇒ 弱转强腿的 regime 贡献逐年翻转，u-rzq-deconf 的 implication 改写。关闭对 004aca1c / b0c225d4 的单独研究（同血统框架 / 子血统组合）。家族 exit gate 的 R=1 拒绝与 valDeclined: 9 不受本条影响——这是机制理解，不是候选',
  spawned: 'u-e9-rzq',
  edgeRef: '涨停动量延续',
};
if (!have.has(row.qId)) { rq.recordFinding(F, row); console.log('recorded', row.qId); } else console.log('already recorded');
