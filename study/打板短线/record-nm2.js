// Step-0 (new-members) finding for the 2026-10-07 re-invocation: e73c9d89 assigned 2026-10-06
// (git 58fbb68) as a fork of the base's 首板高开 leg. Zero cost: ledger row + curve + source.
//   node -e "require('./study/打板短线/record-nm2.js')"
const rq = require('../../utils/research-queue');
const F = '打板短线';
const have = new Set(rq.findings(F).map(f => f.qId));
const row = {
  qId: 'nm-2026-10-07', type: 'probe',
  component_or_param: '新成员 e73c9d89 无未来，26年回撤10%，收益100%+的打板策略（2026-10-06 分配，git 58fbb68：基类 439385b4 首板高开腿的分叉——均价涨幅 / 成交额 / 市值过滤、竞价量比 + 高开检查、左压 zyts、止盈卖出逐字相同，去掉 低开 与 弱转强 两腿，14:50 无条件离场）',
  metric_delta: 'epoch 6 归一化：obj −0.0733 / annual 20.26 / sharpe 0.48 / maxDD 27.59 / total 44.54，DQ；曲线 2022 +51.7 / 2023 −4.7，半年 73.5 / −12.6 / 17.6 / −19.0；活跃日 409/483（几乎每天有候选，T+1 离场）。对照：基类 0.9668（442 / −3）、imp-4 高开+低开重分仓 0.5600（182 / 18，四个半年全正）、6ada2917 低开腿单独 0.2970（73 / 23，四个半年全正）',
  window: 'train 2022-01-01→2023-12-31（归一化曲线切片，信息性）',
  finding: '首板高开腿单独成书（另一作者的代码，带无条件当日离场）是一本 regime 形状的书：2022-H1 +73% 之后两个下半年都亏、2023 为负、回撤 28%、过不了闸；而同样用别人代码单独成书的 低开腿（6ada2917）四个半年全正、2023 回撤 3%。两本外部书合起来把 u-rzq-deconf 留下的最后一个腿问题（高开 + 低开 两腿里谁是「四个半年全正」的那条）经验地答了：是 低开，高开腿自己也是「上半年肥尾、下半年退潮」的形状，只是幅度比弱转强小。⚠ 两本都不是干净的消融（过滤集与离场规则各有差异），所以只到「方向」为止，不给量级',
  confidence: 'med（方向：两本书形状差异明显）/ low（量级：非同台消融）',
  flags: 'zero-cost · step-0-exit · leg-attribution-by-outside-codes · 高开-leg-regime-shaped · 低开-leg-steady · DQ',
  description: '数据：harness/normalize-train.tsv 行 + data/series/*_tmp_jq-normalize_e73c9d89__train__e6.json 切片 + 源码第 320–337 行（11:28 浮盈卖 / 14:50 未封板全卖）',
  implication: '关闭「在基类上再跑一次 高开 vs 低开 的分腿消融」：两条外部代码已给出方向，而本家族的决策（基类是 epoch 6 的候选、improve 结构性封顶、VAL 已花）不依赖它的量级；若将来某轮需要量级，一行 diff（第 177 行只留 sbdk_stocks）即可，≈16 分钟。不开新一轮；成员记为 §2 raw 行。对 edge 块无改动：涨停动量延续 的 regime 结构（每年上半年肥尾）在 高开腿 上同样成立，这是对 u-2023 / val-base-e6 读数的第三个旁证',
  spawned: 'none',
  edgeRef: '涨停动量延续',
};
if (!have.has(row.qId)) { rq.recordFinding(F, row); console.log('recorded', row.qId); } else console.log('already recorded');
