/**
 * record-2026-10-27-breadth-universe.js — recorder step for the 2026-10-27 second round.
 *
 * Two completed executions on the CHAMPION 0a7de9fa (not the base 7a1c225f):
 *   q-e9-champ-breadth   g.target_stock_count 2 -> 4
 *   q-e9-champ-universe  pool 399101 -> 000985, ranking rule verbatim
 *
 * Control for BOTH is the champion's own epoch-9 ledger row (2.6282 / 7.07 / 276.82 / 14.00,
 * 365d), never re-run. Run via:  node -e "require('./study/小市值/record-2026-10-27-breadth-universe.js')"
 */

const rq = require('../../utils/research-queue');

const WINDOW = 'train 2024-01-01→2024-12-31 (365d)';
const CTRL = 'champion 0a7de9fa 自身 epoch-9 台账行 2.6282 / sharpe 7.07 / annual 276.82 / maxDD 14.00（365d，曲线复算 2.6281；Jan–Nov 1.6888；十二月占全年对数增长 28.1%）';

rq.recordFinding('小市值', {
  qId: 'q-e9-champ-breadth',
  type: 'ablation',
  component_or_param:
    '**对照是 champion [[0a7de9fa_中小盘趋势策略（年化85%）]] 自身的 epoch-9 台账行 2.6282（sharpe 7.07 / annual 276.82 / maxDD 14.00，365 天），不是 base 7a1c225f** —— 本族 §2 其余各行的 Δ 都对 base，两者不可并列读。' +
    '唯一改动：L111 `g.target_stock_count = 2` → `4`；该变量在 L270 / L276 / L286 / L573 / L727 共 5 处被读、全部随之改变，这是预期行为而不是第二处编辑。' +
    'builder `study/小市值/build-breadth-0a7de9fa.js`，变体 `study/小市值/variants/0a7de9fa-breadth-4.py`。' +
    '对照从不重跑（orchestrator ruling：builder 走的是 normalizer 同一条 py2to3 + 冻结 OVERRIDE 路径，单处编辑的变体可直接与 2.6282 比）。',
  metric_delta:
    'objective 2.6282 → **1.8875**（曲线复算 1.8874，Δ **−0.7407 / −28.2%**）/ sharpe 7.07 → **5.79** / annual 276.82 → **212.52**（保留 **76.8%**）/ maxDD 14.00 → **23.77**（**+9.77pp，1.70×**）。' +
    '日收益相关 **0.8842**，首次分岔 2024-02-20。损失拆解：**87% 来自年化、13% 来自回撤**。已实现波动率反而**下降**（41.2% → 38.2%）而回撤近乎翻倍，且两段回撤窗口不同（control 03-21→06-03，变体 05-07→07-24）⇒ 风险在路径不在波动率。' +
    '持仓计数（设计要求 1，load-bearing）：41 次 rebalance，**40 次 × 4 名 + 1 次 × 0 名**（2024-02-06 目标表为空），调仓后 **37 次持 4 只**、均值 **3.76** ⇒ 预期的宽度**确实实现了**；但现金 ETF 在 242 个交易日中的 **19 天**吃掉一个名额，L727 的仓位数 break 触发 **55 次**，日均只有 **2.86 只股票名 / 3.13 个仓位**。' +
    '顶背离 overlay 在**同一日历**上只发火 1 次（2024-12-17），清 **4** 仓（control 清 2 仓）。' +
    'Jan–Nov 副读 1.6888 → **1.4152**（Δ −0.2736，**−16.2%**，相对幅度明显小于全年的 −28.2%）；十二月对数增长占比 28.1% → **21.4%**，十二月简单收益 +45.09% → **+27.64%**。',
  window: WINDOW,
  finding:
    '把持仓只数从作者的 2 翻到 4：objective 2.6282 → 1.8875（−28.2%），但年化保留 **76.8%**（212.52），回撤 14.00 → 23.77（**1.70×**），sharpe 仍 5.79。' +
    '⚠⚠ **结果落在预注册的一个空档里**：三分是 (a) <1.6 ⇒ 优势特指「只持 2 只」的集中度、(b) 2.1–2.68 ⇒ 平台、(c) ≥2.68 ⇒ 作者的 2 是被 2024 调出来的旋钮，而 **1.8875 落在未被任何一支覆盖的 1.6–2.1**；executor 正确地拒绝自行选支。' +
    '**本判定由 orchestrator 作出（记为 orchestrator 的判断，不是 executor 的）**：翻倍后 76.8% 的年化仍然活着 ⇒ 集中度**不是** 2.6282 量级的解释（那需要落 (a)）；但 −0.7407 的 objective 与 2.3× 的回撤使它是一个真实且不小的贡献项，并非 (b) 隐含的弱义「部分」。诚实判词是「**量级的实质但非解释性贡献项**（a material but non-explanatory contributor）」。' +
    '宽度确实实现（调仓后 37/41 次持 4 只、均值 3.76），但现金 ETF 在 19 天吃掉名额、L727 的仓位 break 触发 55 次，故日均仅 2.86 只股票名 —— 2→4 改变的不只是股票只数，这一点在 Δ 的归因里必须带上。',
  confidence: 'high',
  flags: '⚠零滑点高估, preregistration-gap-1.6-2.1, verdict-by-orchestrator, etf-slot-eats-a-name, december-attribution',
  description:
    '预注册三分自身的缺口是本行的第二个产物：(a) <1.6 / (b) 2.1–2.68 / (c) ≥2.68 不穷尽，1.6–2.1 无归属，' +
    '于是判词只能由 orchestrator 补；下一轮写 band 必须穷尽（相邻区间端点相接，不留洞）。' +
    '另：预注册 (b) 支里「4 只把可行性下限从 1e7 砍到 5e6 ⇒ capacity 白赚」这句被本行的数字否掉 —— 4 仓的容量要付 −0.7407 objective 与 +9.77pp 回撤，不是白赚。' +
    '邻点 3 / 6 **不 spawn**：本族 VAL 已在本台花尽且 FAIL（xsz-e9-champ 0.83），一个三点驼峰扫描正是本轮明确不收的纯分数旋钮；而量级问题已由排除法结清（见 implication）。',
  implication:
    '**结清「champion 的 TRAIN 量级」这条排除法，并据此停止寻找第三个机制**：规模 只给方向（上挪一档只保留 29.5%）、BBI 带已 REFUTED（去掉它年化反而 100.9%）、顶背离 overlay 是 2024-12-17 一次 session 值 0.2963 且 ΔmaxDD 0.00、集中度现在测得是实质但非解释性贡献项（翻倍仍留 76.8% 年化）⇒ §4 原先预测的「量级 = 一次十二月事件 + 2 仓的尾部运气」成为**最有支持的读法**，且**没有任何单一部件解释 2.6282**。' +
    '三项后续动作随之改变：(1) 邻点 3 / 6 **不入列**，本族在本台的旋钮搜索到此为止（VAL 已花尽，任何分数旋钮都产不出候选）；' +
    '(2) 容量路线回到 liq-2 (¥5e7) / liq-3 (¥1e8)，**不得**再用「改成 4 仓把下限砍半」当作免费的容量办法 —— 实测代价是 −0.7407 objective 与 +9.77pp 回撤；' +
    '(3) 下一轮的预注册 band 必须**穷尽**（本次 1.6–2.1 无归属，把判词推给了 orchestrator，这是流程缺陷而不是结果的性质）。',
  spawned: 'none',
  edgeRef: '规模',
});

rq.recordFinding('小市值', {
  qId: 'q-e9-champ-universe',
  type: 'edge-test',
  component_or_param:
    '**对照同为 champion [[0a7de9fa_中小盘趋势策略（年化85%）]] 自身的 epoch-9 台账行 2.6282，不是 base 7a1c225f** —— 不可与本族 §2 其余 Δ 并列读。' +
    '唯一改动在 **L165 而不是 L28**：新增常量 `POOL_INDEX = \'000985.XSHG\'`（中证全指）并只换 L165 `get_index_stocks()` 的实参；**L28 `MARKET_INDEX` 保持 `\'399101.XSHE\'`**，故 L330（市场整体止损基准）与 L366（顶背离择时输入，已测值 0.2963）**逐字不动** —— 实测确认：overlay 与 control 同日 2024-12-17 只发火一次。filter_kcbj_stock（剔科创/创业/北交）与 filter_new_stock（剔上市不足 1 年，顺带给本条一层 point-in-time 保护）均不动。' +
    'builder `study/小市值/build-universe-0a7de9fa.js`，变体 `study/小市值/variants/0a7de9fa-universe-000985.py`。' +
    '本条是今日新成员 `ba87029c` 触发的 Step-0 想法：那本书把四个指数取值由**第三方作者**预先写在源码 L44–47，故取值不是我们看过结果后挑的。',
  metric_delta:
    'annual 276.82 → **131.90**（保留 **47.65%**）/ objective 2.6282 → **0.9959**（曲线复算 0.9959）/ sharpe 7.07 → **3.24**（仍过 1.0 闸门）/ maxDD 14.00 → **32.31**（**+18.31pp，2.31×**）。蕴含波动约 **39.5%**，内部自洽 ⇒ 非 scrape artefact。' +
    '有效性闸门先过：POOLDEPTH min **1648** / mean **1817.8** / max **2000**（约 control 580/642/705 的 **2.8×**），`市值筛选后数量` 41 次全 = **200**，**0 次 < 200**；入选候选 market_cap（n=3,215）min 10.01 / p25 12.12 / **median 13.33** / p75 15.28 / max 19.88 亿 —— 10 亿下沿在两本书上都咬住，故**市值阶梯几乎没动**，confound 实测很小。' +
    '⚠ control 自身的 `mc_at200` **从未测过**，所以「顶档收窄约 25%」只是 q-e9-champ-size 的**散文**、不是实测对照。' +
    '十二月对数增长占比 28.1% → **4.5%**（十二月简单收益 +45.09% → **+3.87%**）；**除十二月**则年化保留 **76.5%**（139.90 / 182.88）、objective 保留 63.7%。' +
    '市场整体止损全年发火 **0** 次（L330 活但从未触发），个股止损 16 次；maxDD 在**全年与 Jan–Nov 两个切片都是 32.31** ⇒ 2.3× 的回撤是 Jan–Nov 现象、收益损失是十二月现象，**两件事不在同一批月份**。' +
    '67 笔成功买入中 **1 笔满仓买入失败**（002620.XSHE，¥791,168，2024-08-06），另 3 笔失败全是残余现金的 ETF 单。可实现性按构造不变（2 仓、每仓约 ¥50 万、同一 ¥1e7/日 地板）。',
  window: WINDOW,
  finding:
    '把 champion 的选股池从 399101（中小板综指）换成 000985（中证全指）、排名规则逐字不动：年化只保留 **47.65%**（131.90），objective 0.9959、sharpe 3.24（仍过 1.0 闸门），回撤 **2.31×**（32.31）。' +
    '按预注册三分（(a) 年化 ≥193.8% ⇒ edge 是「取最小的」、可推广；(b) <110.7% ⇒ 中小板成员籍承重；(c) 110.7–193.8% ⇒ 不判定），**131.90 落 (c)：不判定，成员籍部分承重**。' +
    '有效性闸门先过且 confound 实测很小（池深 2.8×，但 10 亿下沿在两本书上都咬住，入选候选中位市值 13.33 亿），所以这不是一次 q-e6-1 式的换档实验。' +
    '⚠⚠ **本条无法分离「最小」与「中小板」，与预注册写法完全一致**：十二月对数增长占比从 28.1% 塌到 **4.5%**，而预注册说塌了就不可分离。' +
    '⚠⚠ **而且 (a) 与 (c) 的全部差别就是十二月**：除十二月后年化保留 **76.5%**，那是会落 (a) 的保留率。全年是按规定的采纳口径，故判定维持 (c)，但**这次的 band 归属是一个单月产物，必须如此记录**。',
  confidence: 'high',
  flags: '⚠零滑点高估, no-verdict-band-c, band-is-a-december-artifact, cannot-separate-最小-from-中小板, mc_at200-control-unmeasured',
  description:
    '有效性闸门与 confound 的数字是本行可读的前提，不是装饰：POOLDEPTH 从未取不满 200，入选候选市值中位 13.33 亿，' +
    '故「它是不是只是换到更小的一档」读者可以直接判断，不必再花一次回测；但 control 的 `mc_at200` 未测，' +
    '所以两书顶档的定量比较仍缺一个数。另：L330 全年 0 次发火说明「市场整体止损」在 2024 年对两本书都是死部件，' +
    '这顺带解释了为什么只换 L165 的编辑能把 Δ 保持可归因。',
  implication:
    '**规模 claim 的适用域仍未测定，所以这条 claim 不得被推广，也不得被改写**：`status: measured` 与 evidence 一律不动（本行返回 (c) 无判定，既不加跨池证据、也不触发「成员籍 = 未申报的 segment choice」那套改写）；' +
    '于是族页只能继续说「399101 里的最小」，**任何把 规模 当作市场级 risk premium 引用的说法仍无支持**。' +
    '对 integration 的后果同样是「不变」：redundancy 判定不重写，新成员 ba87029c 作为「本族各成员池子各不相同」的证据**暂时用不上**（它只在落 (b) 时才被引）。' +
    '两条新约束给下一轮：(1) 唯一 spawn 的点是 **399106 深证综指**（最接近 399101，用来分离「深市」与「中小板」），**不预先入列**；' +
    '(2) 任何后续的池/档位实验，**必须在写 band 之前就把十二月作为声明切片**（或直接把 band 定在除十二月口径上）—— 本行的 (a)/(c) 之差全部由一个月产生，照当前写法 band 归属等于在赌一个月。' +
    '另加一条读数纪律：引用 q-e9-champ-size 的「顶档收窄约 25%」前须先测 control 自身的 `mc_at200`，否则那是散文不是测量。',
  spawned: '399106 深证综指（spawned，未入列，无 queue id）',
  edgeRef: '规模',
});

console.log('[record] 小市值: q-e9-champ-breadth + q-e9-champ-universe written');
