// Gatekeeper write for the epoch-8 understand round on 五福闹新春.
// One-shot: `node study/五福闹新春/gate-e8.js`. Idempotent-by-id is NOT provided by add(),
// so run once; re-running would duplicate ids.
const rq = require('../../utils/research-queue');
const FAM = '五福闹新春';

const existing = new Set(rq.load(FAM).map(e => e.id));
const entries = [

// ───────────────────────────── QUEUED ─────────────────────────────
{
  id: 'q-e8-1', kind: 'understand', rank: 1, status: 'active',
  title: '走弱期避风港退化检验：17 只手选海外/商品池 → 只留黄金 518880',
  hypothesis: 'q-e6-4 归给手选池的 +0.2415 不是「选池」而是「任何 2021 年作者都能点出的一只避风港」；成立：objective ≥ 0.30 且 sharpe ≥ 1.5（则该腿可按「持一只规范避险资产」主张，池的事后嫌疑基本解除）。预注册证伪：objective ≤ 0.20（贴近 q-e6-4 的现金 0.1340）⇒ 该腿确实需要那 17 只事后名字，趋势择时 edge 收窄固定在 0.1340/sharpe 1.18，家族没有可主张的过闸 edge。落在 0.20–0.30 之间按 partial 记，不得向任一侧读。',
  why: '这是 §4 第一条「[最高优先，需数据] 点时海外池」的可负担替代：点时 QDII/商品名单需要逐日数据（本轮没有），而「退化成单一规范避险」用同一个编辑点就能把「池选择」这一自由度压到零——池里 18 只有 5 只上市于 TRAIN 末或之后（159518 2023-11、159502/513400 2024-01/02、520830 2024-07、159529 2024-02），所以这张池子确实是 2025 年份的产物。518880 的选择规则在跑之前就固定且可核验：全池上市最早（2013-07-29）、2025 日均成交最高（51.35 亿）——59.37 亿的 513310 更高但上市于 2022-12-22，正是事后嫌疑名字本身，故按「上市早于 TRAIN」先排除。效应尺度（现金 0.1340 ↔ base 0.3755，跨度 0.24）比本族任何噪声地板大一个量级，所以读数不依赖 q-e8-2 的结果。⚠ 读数纪律：黄金 2022–23 在人民币口径下本身走强，所以「高」只能读成「单一规范避险即可复制该腿」，不能读成「避险资产无关」——那需要第二只（如 511880 已测 / 原油 501018）才能分开。',
  design: 'baseline-e6.py afternoon_routine 走弱分支（第 277–281 行，与 q-e6-4 完全相同的编辑点）：把 g.merged_etf_pool 的两条赋值改为固定 g.merged_etf_pool = [\'518880.XSHG\']，其余（择时触发、R²/MA 滤波、候选系数 1.0、20 日上限）逐字不动 → study/五福闹新春/variants/q-e8-1_weak-gold-only.py，--window train。顺带（不改任何决策）在走弱分支加一行 log.info(f"WEAKHOLD {date} {security}")，用 utils/backtest-log.js 收割走弱持仓天数分布——这是 q-e8-6 被否决后的零边际成本替代。报告 2022/2023 年度拆分（yearsplit.js），与 q-e6-4 的 2022 40.24 / 2023 13.56、base 的 64.11 / 38.50 对齐：手选池的贡献集中在 2023，所以年度拆分是本测的主要证据而不是附注。',
  from: ['q-e6-4', 'q-e6-2', 'q-e6-3', '§4 gap 1 点时海外池', 'source:g.global_etf_pool 18 只，5 只上市于 2023-11 之后'],
  edgeRef: '趋势择时',
  note: 'gatekeeper rank 1：本族 14 条 finding 后唯一还活着的机制问题，两侧门槛都带强 implication（高 ⇒ 趋势择时可升为「择时+规范避险」并重新具备过闸的主张；低 ⇒ edge 永久收窄到 0.1340，家族在本台没有可主张的过闸来源）。效应尺度 0.24 远超噪声地板，故不被 q-e8-2 的结果左右；且 q-e8-3 的优先级取决于本测落在哪一侧。',
},
{
  id: 'q-e8-2', kind: 'understand', rank: 2, status: 'queued',
  title: '执行分钟噪声地板：13:10 → 13:12（afternoon/sell/buy 三条 run_daily 同时移动）',
  hypothesis: '把成交时点挪 2 分钟不改变任何机制，objective 变动应落在复跑漂移量级，|Δobj| ≤ 0.015。预注册证伪：|Δobj| > 0.048 ⇒ 执行分钟噪声地板 ≥ 本族史上最大效应（imp-6 的 +0.0480），§2 全部 14 条 Δ 都无法与「它被测在哪一分钟」分开，家族的 §2 表须整体标注该地板。',
  why: '本族所有 Δ 目前都用「~0.15pp 复跑漂移」当地板，而那只量了同一文件重跑同一分钟的抖动，量不到「这本书对成交时点有多敏感」。有两条独立的外部证据指向后者很大：成员 fork aaee3035（13:10 算动量但 14:10 卖/14:20 买）objective 0.2533、5ac906ea（13:12 成交）0.2552，都比 base 0.3755 低约 0.12——但两者与 base 的代码 Jaccard 只有 0.432 / 0.745，所以那 0.12 不可归因于时点。本测是把时点从那些混淆里拆出来的最小改动，而 13:12 正是 5ac906ea 的时点，所以若本测也落到 ~0.25，同一次回测既判定了噪声地板又解释了那个成员的差距。⚠ 预注册方向纪律（沿用 generator A 的自我约束）：13:12 若更好，那是脆弱性发现，不是改进，不得采纳、不得带去 VAL。',
  design: 'baseline-e6.py 第 201–203 行（initialize 里连续三条 run_daily：afternoon_routine / sell_routine / buy_routine）time=\'13:10\' → \'13:12\'，三条必须同时移动——它们是一个有序块（算分→卖→买），单独移一条会制造 base 不存在的跨时点状态。其余逐字不动（09:00 morning / 09:40 走弱判断 / 15:10 reset / every_bar 止损都不动）→ variants/q-e8-2_exec-1312.py，--window train。报告 objective/sharpe/maxdd + 2022/2023 拆分，并用 backtest-series.correlate(baseline-e6, q-e8-2) 给日收益相关度：相关度接近 1 而 Δ 很小才是真正的「地板低」，相关度塌掉而 Δ 恰好很小则是两条不同的书凑巧同分，必须分开报。',
  from: ['q-e6-7', 'q-e6-6', 'member:aaee3035 obj 0.2533 (14:10/14:20)', 'member:5ac906ea obj 0.2552 (13:12)', 'q-e6-0 ~0.15pp 复跑漂移'],
  edgeRef: '趋势择时',
  note: 'gatekeeper rank 2：唯一一个结果会改写其它 14 条 finding 读法的测项，且是全队列最小的 diff。放在 q-e8-1 之后只因为 q-e8-1 的效应尺度（0.24）不依赖地板，而 q-e8-3 的 ±0.02 判据依赖它。',
},
{
  id: 'q-e8-3', kind: 'understand', rank: 3, status: 'queued',
  title: '走弱池流动性地板：在本书自己的可成交下限 ¥2e7/日 上重测（为 realizability 取证）',
  hypothesis: '走弱池剔除不掉任何名字或剔除后 Δobj ≥ −0.02 ⇒ ¥1M 本金下该腿的成交可行性由测量确认，realizability = 2（scope：base 本书）。预注册证伪：Δobj ≤ −0.10 ⇒ 承载 +0.2415 的避风港腿由一个 ¥1M 书填不满的名单供给，realizability = 1，家族在整合层被永久拒绝而不只是 blocked。',
  why: '本族 realizability 当前是**未设**，按 CLAUDE.md 的规则未知即 BLOCK——而这个数字按仓库自己的判例不可从源码猜：大小盘轮动的 liq-1 跑了三个地板才发现地板 31/31 次换仓剔除 0 只、曲线逐点相同，静态规则会猜反。地板值不是我们挑的：harness 本金 ¥1,000,000、order_volume_ratio=0.05、g.holdings_num=1 ⇒ 单名可行性下限 = 1e6/0.05 = ¥2e7/日，而 base 自己的走弱池控制是相对量（全市场 ETF 日均成交额/20000 ≈ ¥1e7），约为该下限的一半。预期大概率接近惰性（2e7 = 0.2 亿，而池里最薄的 159529 按 2025 快照也有 0.50 亿），而**惰性正是能挣到 R=2 的结果**——前提是用日志证明它惰性，这是 liq-1 的教训。⚠ 本测的 scope 必须写清：它只测「日成交量够不够让 ¥1M 的单子成交」，**不测** QDII 的溢价/折价与申赎额度，而 §1 的现实性块点名走弱池里有日均 < 1 亿的 QDII（德国 0.95 亿、纳指生物 0.78 亿，且都是 2025 快照，2022–23 更薄）。所以 R=2 只能按「¥1M 规模的成交可行性」落笔，不得读成「容量没问题」。',
  design: 'initialize 加 g.weak_liquidity_floor = 2e7；在 filter_global_pool_by_volume（第 ~396–430 行）把门槛改为 threshold = max(dynamic_threshold, g.weak_liquidity_floor)，并每次过滤后打印 `LIQFLOOR in=<len(g.global_etf_pool)> out=<len(new_global_pool)> removed=<names>`，使「剔除 0 只」可被日志证明而不是从 Δ=0 推断。正常期的合并池与其流动性除数一律不动（q-e6-3 已关闭该方向）→ variants/q-e8-3_weak-liqfloor-2e7.py，--window train。若曲线与 baseline-e6 逐点相同（backtest-series 比较），按 liq-1 的格式报「bit-identical，N 次换仓 in==out」。',
  from: ['q-e6-4 海外池腿 +0.2415', 'CLAUDE.md 大小盘轮动 liq-1（地板可能完全惰性，静态规则会猜反）', 'harness: 本金 1e6 × order_volume_ratio 0.05 ÷ holdings_num 1 = 2e7', 'wiki 五福闹新春 frontmatter: realizability 未设 ⇒ 整合闸 BLOCK', '§1 现实性块：走弱池含日均 < 1 亿 QDII'],
  edgeRef: '趋势择时',
  note: 'gatekeeper rank 3，并裁定它**不是** q-e6-3 的重开：q-e6-3 关闭的是「正常期池构成 + 改流动性除数」这类选池/调参 improve，本测动的是**走弱池**，加的是一个由 harness 本金与 order_volume_ratio 推出的**绝对可成交下限**，产出是一个 frontmatter 事实（realizability + realizabilityBasis + realizabilityScope: base），不是一个候选。两者的对象、量纲与产物都不同。⚠ 它的 ±0.02 判据依赖 q-e8-2 给出的噪声地板，所以排在其后；若 q-e8-2 判出地板 > 0.048，本测只能靠 LIQFLOOR 日志的 in==out 来挣 R=2，Δ 一侧作废——这一点要在派发时讲清。',
},
{
  id: 'q-e8-5', kind: 'understand', rank: 4, status: 'queued',
  title: '全时点对照：13:10 → 14:50（三条 run_daily 同时移动），只在 q-e8-2 判出低地板后才跑',
  hypothesis: '若 13:10 不是一个被挑出来的时点，整天的成交时点应近似等价，|Δobj| ≤ 0.05。预注册证伪：|Δobj| ≥ 0.10 **且** q-e8-2 已显示局部稳定（|Δobj| ≤ 0.015）⇒ objective 是成交分钟的平滑函数、13:10 承载约四分之一的分数，base 的 0.3755 是一个「13:10 专属」的数字，家族标题须带时点限定；并且成员 fork aaee3035（14:10/14:20，0.2533）的差距由时点而非代码差异解释。',
  why: 'base 的文件名就写着「别再被1310狙」，即作者自己认为这个分钟是被人盯的——那恰恰意味着它可能是被挑的。q-e8-2 只能判「局部平坦」，判不了「整条曲线平坦还是有坡度」：局部平坦 + 全局大坡度是最危险的组合（每个 §2 的 Δ 都可比，但家族的绝对水平挂在一个分钟上），而这两种形状只有把两点都拿到手才能分开。⚠ 本测跨五个通道同时变（成交价、current_price 进入动量/R²/MA/止损判定、以及放量外推乘子 240/130=1.846 → 240/230=1.043），所以大 Δ 不可归因到单一通道——它的价值是判形状，不是判机制；派发时必须带着这句话，否则会被读成「时点有机制」。（更正 generator A 的算术：14:50 的 elapsed 是 230 分钟、乘子 1.043，不是它写的 200/1.20；14:50 仍在函数自己的 240 上限内且离收盘集合竞价有距离，选点结论不变。）',
  design: 'baseline-e6.py 第 201–203 行三条 run_daily 一起 \'13:10\' → \'14:50\'（与 q-e8-2 同一编辑点、同一「三条必须同动」约束）→ variants/q-e8-5_exec-1450.py，--window train。报告 objective/sharpe/maxdd、2022/2023 拆分、与 baseline-e6 的日收益相关度，并与 q-e8-2 的 13:12 读数并排给出三点（13:10 / 13:12 / 14:50）。',
  from: ['q-e8-2', 'member:aaee3035 obj 0.2533 (14:10/14:20)', 'source:baseline-e6 第 201–203 行 + 第 780–783 行 elapsed_minutes', 'base 标题「别再被1310狙」'],
  edgeRef: '趋势择时',
  note: 'gatekeeper rank 4，**条件派发**：只在 q-e8-2 判出 |Δobj| ≤ 0.015（局部稳定）时才值一次回测，因为那时「局部平坦 vs 全局平坦」才是一个未决问题；若 q-e8-2 已判出 |Δobj| > 0.048，脆弱性结论已经成立，本测只是加一个同向的点，改不了任何决定 ⇒ 届时转 dropped 并记下原因。',
},

// ───────────────────────────── DROPPED ─────────────────────────────
{
  id: 'q-e8-4', kind: 'understand', rank: 99, status: 'dropped',
  title: '取消成交量外推：projected_today_vol = today_vol * (240/elapsed) → today_vol',
  hypothesis: '—（未测，gatekeeper 否决）',
  why: '登记否决理由，避免再次提出。',
  design: '原提案：第 783 行去掉 240/elapsed 外推，g.volume_threshold 保持 1.8。',
  from: ['q-e6-1', 'idea-imp-6'],
  edgeRef: '动量',
  note: 'gatekeeper 否决，不回测。**先裁定 generator A 争议点：它确实不在 q-e6-1 的关闭方向内**——q-e6-1 关的是「把第一名选得更准」的排序旋钮（lookback/斜率加权/R² 乘子/score_threshold_ratio），而它的 implication 明确把「滤波门槛（只准正趋势/放量/无急跌者入选）」列为仍要去找收益的地方，且 imp-6（走弱期入场门槛）正是在这条上拿到本族唯一一个正结果。所以**入选资格门槛是开放领域，generator A 的论证成立**。否决的是**设计**：在 13:10，elapsed_minutes = (13−9)×60+10−30−90 = 130，外推乘子 240/130 = 1.846；去掉它而把阈值留在 1.8，等于把算出来的放量比整体缩小 1.85 倍，而这个门槛是**排除**条件（放量比 < 1.8 才准入选），所以这一改近乎把放量滤波整体关掉。于是两个预注册分支都不可归因：|Δ| 大读不出是「时点进入信号」还是「放量滤波本身值这么多」；而 1.85 倍的等效门槛变动远大于 q-e6-6/7 里 ±0.1（25%）就吃掉 75–91% 优势的那次扰动，所以单点读数在本族已被证明不可解释。**两个干净的替代形式**（留给下一轮 generator，本轮不排）：(a) 精确消融放量门槛本身（g.volume_threshold → 1e9 使其恒真），这是对一个入选资格门槛的原子 ablation、落在 q-e6-1 指明的开放领域里；(b) 真正的时点通道隔离——把 elapsed_minutes 冻结为常数 130 使乘子与调用时刻无关，它在 13:10 逐点等同 base（故只有与 q-e8-5 配对相减才有信息），须作为 q-e8-5 的后继提出。',
},
{
  id: 'q-e8-6', kind: 'understand', rank: 99, status: 'dropped',
  title: '观测型探针：走弱分支每日打印 WEAKHOLD <date> <security>，统计走弱持仓集中度',
  hypothesis: '—（未测；观测内容已折叠进 q-e8-1，不单独占回测）',
  why: '登记否决理由，避免再次提出。',
  design: '原提案：不改任何决策，只加日志，用 utils/backtest-log.js 收割；generator A 已核实 base 没有可免费读日志的既有 backtestId，故它要花一整次回测。',
  from: ['q-e8-1', 'q-e6-4'],
  edgeRef: '趋势择时',
  note: 'gatekeeper 否决为**独立条目**，但观测本身不丢：一个不改任何决策的日志行必须搭车在反正要跑的回测上，所以这一行已写进 q-e8-1 的 design（走弱分支 log.info WEAKHOLD），边际成本为零——大小盘轮动 liq-1 的 LIQFLOOR 就是这个办法。另外它作为独立测项的信息量本来也弱：(1) 在 q-e8-1 落高的分支里它被完全包含——若单只黄金就能复制该腿，「该腿是否集中」已由测量回答；(2) 在落低的分支里它只能确认 q-e6-4 flags 已经点名的嫌疑（贡献集中在 2023，疑点落在 513310 2022-12 上市、159509 2023-08 上市这些名字上），确认一个已知怀疑既不开也不关方向，达不到 implication 的门槛。',
},
];

for (const e of entries) {
  if (existing.has(e.id)) { console.log(`skip ${e.id} (already present)`); continue; }
  rq.add(FAM, e);
  console.log(`added ${e.id}  rank=${e.rank}  status=${e.status}`);
}
