// Step-0 (new-members) finding for the 2026-09-27 re-invocation: two members assigned on
// 2026-09-26 (git b85e991), both gate-passing on epoch 6, read from their stored curves and sources
// at zero cost. Idempotent by qId.
//   node -e "require('./study/打板短线/record-nm.js')"
const rq = require('../../utils/research-queue');
const F = '打板短线';
const have = new Set(rq.findings(F).map(f => f.qId));
const row = {
  qId: 'nm-2026-09-27', type: 'probe',
  component_or_param: '两个新成员（2026-09-26 分配，git b85e991）：6ada2917 年化60%的龙头首板低开战法（obj 0.2970 / annual 45.82 / sharpe 1.77 / maxDD 16.12，过闸）与 b3751277 【手搓自用】涨停优选后再买入（obj 0.4873 / annual 63.89 / sharpe 2.69 / maxDD 15.16，过闸）——源码 + 归一化曲线，零回测',
  metric_delta: '6ada2917 曲线：2022 +73.0 / 2023 +22.8，半年 59 / 9 / 11 / 11 全正，2023 maxDD 3.1%，活跃日 92/483；b3751277 曲线：2022 +55.9 / 2023 +72.1，半年 55 / 0 / 41 / 22，活跃日 409/483（持续持仓）。基类同期：442 / −3，半年 206 / 77 / 18 / −18',
  window: 'train 2022-01-01→2023-12-31（归一化曲线切片，信息性）',
  finding: '两个成员是两条不同的东西。6ada2917 = 基类的**首板低开腿**单独成书（昨日首板、非连板、60 日相对位置 ≤0.5、开盘价/昨收 0.96–0.97）+ 无条件当日离场（11:28 浮盈卖 / 14:50 未封板全卖），无成交额 / 市值 / 左压过滤，只在空仓时买：四个半年全正、2023 回撤 3%，但一年只交易几十天、obj 0.30——它用另一套代码印证了 u-rzq-deconf 的读数（去掉弱转强腿后剩下的两腿四个半年全正，赚得少）。b3751277 = 每周调仓的 **5 只最小市值 × 月训 ML 排序** 书（1000 只最小市值池 → 三年涨停史筛选 → AI_score 前 5，四月空仓，止损线），409/483 日持仓，2023 +72% 是全家族最好的 2023——它的机制是 小市值 + 多因子ML，涨停只是「涨停基因」筛选；代码匹配器对它弃权（below MIN_SCORE），人工按同代码体的 c658ef98 / d5b83074（涨停基因轮动）归入本家族并注明「拆分时随它们一起走」',
  confidence: 'high',
  flags: 'zero-cost · step-0-exit · sublineage-涨停基因（c658ef98 / d5b83074 / b3751277）· edge-likely-规模因子-for-b3751277 · 6ada2917-confirms-u-rzq-deconf',
  description: '数据：data/series/*_tmp_jq-normalize_{6ada2917,b3751277}__train__e6.json 的 cum 切片；源码 strategies/2026-07-04_…-6ada2917.py（221 行）、strategies/2026-06-30_…-b3751277.py（950 行，get_stock_list 第 495–512 行：market_cap.asc() 前 1000 → get_highlimit_and_startpoint → rank_stocks → 前 5）',
  implication: '关闭「新成员需要开一轮」：6ada2917 没有提出未探索的问题（它就是 低开腿 + imp-2 式离场的组合，读数与 u-rzq-deconf / imp-4 一致：稳、少赚、四个半年全正），b3751277 提出的不是本家族 edge 的问题而是**分类**问题。打开（不花本家族预算）：涨停基因 子血统（c658ef98 / d5b83074 / b3751277）的 edge 大概率是 规模因子——若要证实，一条实验是去掉 b3751277 第 508 行的三年涨停史筛选看 objective 是否保持；它属于 小市值 / 多因子ML 的冗余组，type 层引用时不应把 b3751277 的 2023 +72% 记到 涨停动量延续 名下。建议人工把 涨停基因 拆成子家族（parent 待定），而不是在 打板短线 下研究它',
  spawned: 'none',
  edgeRef: '涨停动量延续',
};
if (!have.has(row.qId)) { rq.recordFinding(F, row); console.log('recorded', row.qId); } else console.log('already recorded');
