// Recorder for q-e9-champ-liq-02fdafaa — the liquidity-feasibility floor on the family's NEW
// epoch-9 champion 02fdafaa. Dispatched to clear the EXIT GATE's realizability half, not as a
// ranked research idea.
//
// Every number below was RECOMPUTED by the recorder from the two stored 242-point curves
// (control 2026-10-30_..-02fdafaa__train__e9.json, variant
// study_小市值_variants_02fdafaa-liq-1__train__e9.json) and agrees with the executor's report.
// The one-line diff, the `g.stock_num = 6` read and the never-called `adjust_stock_num` were
// re-verified against the raw source independently of the builder's own assertions.

const rq = require('../../utils/research-queue');

const component_or_param = [
  '流动性可行性地板（builder study/小市值/build-liq-02fdafaa.js → 变体 study/小市值/variants/02fdafaa-liq-1.py）。',
  '**CONTROL = NEW champion 02fdafaa 自身的 epoch-9 台账行** strategies/2026-10-30_今天多个策略告警_这是什么意思_怎么解决-02fdafaa.py',
  '（399101 中小板综指周度支、6 仓），objective 3.0172 / sharpe 8.22 / annual 320.35 / maxDD 18.63（365d，曲线在盘）——',
  '**不是 base 7a1c225f，也不是前 champion 0a7de9fa**，三者不可并列读。',
  '唯一改动：py2to3 后 L137 `    return final_list` → `    return filter_liquidity_floor(context, final_list)`',
  '（get_stock_list 末行；recorder 独立复核：base 615 行里只有这 1 行不在变体内，三枚 pin 齐备）。',
  '地板全部由本书自身仓位推出，无一处猜测：源码无 g.portfolio_value_proportion ⇒ SINGLE SLEEVE；',
  'buy_security(L500-521) 以 cash / target_num 定仓、target_num = g.stock_num = 6（L50；recorder 复核：该变量被读 6 处、赋值仅 1 处）；',
  'capital 1,000,000 / 6 = 166,666.67 每仓，epoch 4 钉死 order_volume_ratio=0.05 ⇒ 单根日 bar 填满一仓需成交额 ≥ **¥3,333,333.33/日**（变体里 LIQ_FLOOR = 1 * (1000000.0 / 6 / 0.05)，已复核）。',
  'helper 取 20 根日 bar 的 **median** `money`（单日放量不得送进常态不流动的名字），在 context.previous_date 求值（今天要交易的那根 bar 永不被查询）⇒ 非 lookahead。',
  '两个调用点（weekly_adjustment L149 10:30、check_remain_amount L216 的 14:25/14:55）都被这一改动覆盖，本书要买的名字没有一个绕过地板。',
  '⚠ **adjust_stock_num(L576) 在源码里存在但从未被调用**（recorder 独立复核：全文仅 1 次出现，即其 def 行）——',
  '若将来有变体调用它，除数变成动态 3..6，本地板必须重新推导、本分数随之作废。',
  'FLOORS 表已把 liq-2(5× = ¥1.67e7) / liq-3(10× = ¥3.33e7) 写进 builder 以免日后按口味补点，但**两者只声明、未构建、未运行**。',
].join('');

const metric_delta = [
  'objective 3.0172 → **3.0192**（Δ **+0.0020**）/ sharpe 8.22 → **8.20**（−0.02）/ annual 320.35 → **320.55**（+0.20pp）/ ',
  'maxDD **18.63 → 18.63（Δ 0.00，窗口也不动：2024-05-07 → 2024-06-24 两边逐位相同）**。',
  'LIQFLOOR 共 **91 行、0 ERROR 行**；**in > out 仅 3 次**，均为 in=10 out=9（removedFrac 0.1000），previous_date 为 2024-09-18 / 09-19 / 09-23 ——',
  '**一个连续的九月中旬窗口**，不是全年散布。cumIn=910 / cumOut=907 ⇒ 剔掉 **3 / 910 次候选评估 = 0.33%**。',
  '**91/91 次 slots=6，minSlots=6，cumShort=0** ⇒ 一次都没有饿死，第 7 名顶替全部成功；且 **in=10 恒定**（6 槽常备 4 个备选）⇒ Δ 纯为「名字质量」，不混入持仓稀释。',
  '调用点分布：42 次 weekly_adjustment 10:30（剔 2）· 43 次 check_remain_amount 14:25（剔 1）· 6 次 14:55（剔 0）。',
  'RECORDER 从两条 242 点曲线独立复算全部数字，与抓取逐位一致：total 320.35 / 320.55，maxDD 18.629 / 18.629（峰 2024-05-07、谷 2024-06-24 两边同），objective 3.0172 / 3.0192。',
  '**max|Δcum| = 4.17pp（2024-09-23）⇒ 不是 (a) INERT**；首个相异日 **2024-09-19**，正是第一次剔除的次日。',
  '月度表只有两个月真分歧：09 月 27.1224 → 26.8924（**−0.2300pp**）、10 月 19.6574 → 19.9321（**+0.2747pp**）；',
  '其余十个月 Δ **恰为 0.0000**，11 月 +0.0036 / 12 月 −0.0042 是 board-lot 舍入残差（11-01 之后 max|Δdaily| = 0.0056pp）。',
  '日收益相关 **0.998631**；年化波动 41.13% → **41.29%**（与 JQ 口径 sharpe 8.20 蕴含的约 38.6% 相容 ⇒ 非 scrape artefact）；',
  '125 涨/80 跌/37 平 → 124/81/37，最差日 −9.93%、最好日 +9.49% → +9.48%。',
  'Jan–Nov 副读 3.0001 → **3.0024**（Δ +0.0023，与全年同号同量级）⇒ 本行**不是十二月产物**，与「02fdafaa 不是十二月书」一致（q-e9-champ-emptymonth 已测）。',
  '⚠ 算术口径 sharpe（mean/sd×√252）为 3.85 / 3.84，与 JQ 口径 8.22 / 8.20 **不可并列引用**。',
].join('');

const finding = [
  '按预注册三分落 **(b)**：名字**确实被剔除**，但代价为零甚至微正 —— objective 3.0172 → 3.0192（Δ **+0.0020**）、sharpe 8.20、**maxDD 与其窗口完全不动**，远过 epoch-9 的 1.0 闸门 ⇒ **02fdafaa 的 realizability = 2**。',
  '⚠ **明确不是 (a)**：max|Δcum| 4.17pp，曲线并非逐位相同，所以正确判词是「**剔除了但不重要**」（removed but immaterial），不是「地板是惰性的」——',
  '这与 大小盘轮动 / b3751277 的 liq-1「曲线逐位相同」是两种不同结果，不得混为一谈。',
  '机制很窄且可复述：地板在九月中旬的一个周度窗口上换掉了一个名字（3 次候选评估、3/910 = 0.33%），第 7 名顶上并且略好，把 **0.23pp 从九月搬到十月**；全年其余十个月的月度收益 Δ 恰为 0。',
  '本书自身的筛选链（399101 → 市值升序前 200 → 前 100 → 行业）本已排掉吃不下 ¥166.7k（5% 参与上限下）的名字，所以地板几乎无事可做。',
  '**slots=6 全程、cumShort=0** 是本行可读的前提而非装饰：它排除了「饿死」这一混淆项，使 +0.0020 可以被当作纯名字质量读。',
  '两个 FREE 可观测量**都逐位保留**：2024-01 月度收益 **0.00% 两边相同**（today_is_between / g.pass_april=True 空仓），maxDD 窗口 **2024-05-07 → 2024-06-24 两边相同** ⇒ 地板没有悄悄重塑这本书。',
  '同口径横向对照（预注册约定相同，故可比）：前 champion 0a7de9fa（2 仓、¥1e7 地板）剔 61/3116 = **1.96%**、41 次 rebalance 中 15 次有剔除、Δobjective **−0.1823**；',
  '本书（6 仓、¥3.33e6 地板）剔 **0.33%**、91 次中 3 次、Δ **+0.0020**。先验「6 仓的地板约小 3 倍 ⇒ 咬得更少」**被证实**，这是本轮唯一一条在看数前写下并兑现的定量预期。',
].join('');

const description = [
  '⚠⚠ **本行不运行任何 edge 的 test:，所以 规模 与 低开反转 两条 claim 的 status 与 evidence 一律不动**。它测的是「这本书吃不吃得下自己的仓位」——一个可成交性（tradeability）测量，不是横截面方向。',
  'edgeRef 故意留空：挂到 规模 上会让一条容量读数混进那条 claim 的证据链，而该 claim 的 test: 是换池一档，本行完全没有碰池子。',
  '对照取自 data/series/2026-10-30_今天多个策略告警_这是什么意思_怎么解决-02fdafaa__train__e9.json（242 点，backtestId 4487c201…），变体取自 data/series/study_小市值_variants_02fdafaa-liq-1__train__e9.json（242 点）。',
  '⚠ **四条载重保留**（executor 标出，recorder 复核后原样带入族页 realizabilityScope / §4）：',
  '(1) **容量上限未测** ⇒ 本行只支持 **R ≥ 2，不支持 3**，与 0a7de9fa 的 liq-1、b3751277 的 liq-1 同级；liq-2(¥1.67e7) / liq-3(¥3.33e7) 已声明、未建、未跑。',
  '(2) **地板是在 BASE CAPITAL 上推出的**：buy_security 按 context.portfolio.total_value 定仓，而本书 2024 年复利约 4.2×，故其**有效**可行性下限随权益一路上行，到十二月已约 ¥1.4e7，而本次测试全程把地板固定在 ¥3.33e6。',
  '    所以测得的是**窗口起点的下限**——这是本仓每一条 liq-1 共有的诚实边界（0a7de9fa 的同一条写作「1e7 只约束年初」），不是本行独有的缺陷。',
  '(3) `slots = min(6, n_out)` 测的是**候选可得性**，不是已确认成交：它排除「被筛选饿死」，不排除每一种成交失败（部分成交、涨停板上买不到等本台不建模的情形）。',
  '(4) ⚠ `adjust_stock_num` 在源码里存在但从未被调用；一旦某个未来变体调用它，除数变为动态 3..6，地板必须重新推导、本分数作废。',
  '⚠⚠ **本行不得被读成「本书可以送出 exit gate」**：本族在本台的 VAL 已**花尽且 FAIL**（xsz-e9-champ = 前 champion 0a7de9fa 的零逻辑改动 pinned 快照，VAL 2025 sharpe **0.83** < 1.0，已归档 validated_strategies/xsz-e9-champ.py 带 `gate_val: fail`）。',
  'realizability 只是闸门两半里**可清**的那一半；另一半（VAL）现在 owner=**human**，需要人去设 JQ_ALLOW_REVAL，agent 与 recorder 均不得设。',
  '⚠ 并且那次 VAL 花在 0a7de9fa 上，而 champion 此后已**改为 02fdafaa**（2026-10-30 normalize）⇒ 已花掉的验证验的**不是**本族当前最佳成员。这是记给 §4 的事实，**不是**再花一次的理由——逐次换候选重验正是 harness.md 点名的「对 VAL 的选择」。',
  '⚠ 发帖日：02fdafaa 文件名前缀 2026-10-30 是**抓取日**；其真实 postedAt 为 **2025-06-06**，即作者看得见整个 TRAIN 2024 与 VAL 2025 的前五个月。本行不依赖这一点（容量不是绩效主张），但引用本书任何绩效水平时必须带上。',
].join('\n');

const implication = [
  '**关闭「地板」这条容量问题，并把 02fdafaa 的下一个可成交性问题改写成「上限」而不是「下限」**：¥3.33e6/日 在 base capital 上**不是一条起约束作用的限制**（剔 0.33%、Δ +0.0020、maxDD 与窗口均不动），',
  '所以任何「新 champion 可能填不满自己的仓位」的担忧到此结清，不得再以此为由另开一轮；往下**唯一**未测的容量面是 builder 里已声明的 liq-2(¥1.67e7) / liq-3(¥3.33e7)，',
  '即「这本书能吃下多少」，而不是「地板上还剩多少余量」（判据同 大小盘轮动 产品的 R=2 裁决：容量是能吸收多少，不是闸门上还剩多少）。',
  '**直接后果一（本轮的全部目的）**：族页 realizability 的 scope 从 0a7de9fa 改挂到 **02fdafaa**，分数 2 有了本书自身的证据，exit gate 的 realizability 这一半**从 UNKNOWN-BLOCK 变成 PASS**。',
  '**直接后果二，必须与后果一同时说出**：闸门**仍然 block**，因为 VAL 这一半是一条实测失败（xsz-e9-champ sharpe 0.83 < 1.0，gate_val: fail），owner 从此是 **human** 而不是 research。',
  '所以若 family-queue 还把本族当 integrate-blocked 重派，**正确动作是撤掉环境里的 JQ_ALLOW_REVAL 或由人作判断，而不是再跑一轮 research**——与 q-e9-champ-val 的 implication (a) 同一条，本行把它从「唯一的 block」收窄成「唯一剩下的 block」。',
  '**直接后果三**：liq-2/liq-3 **不预先入列**。本族 VAL 已花尽，一条容量曲线产不出可过闸的候选，故它排在任何 improve 之后；只有在人授予新 VAL、本族重新有候选可送时，容量上限才值得花回测分钟。',
  '**最后一条是对读数纪律的收紧**：本行的 +0.0020 **不得**被引用成「地板是惰性的」（max|Δcum| 4.17pp ⇒ 它改变了持仓名字，只是改变得不重要）；',
  '而由于地板按 base capital 推出、本书全年复利 4.2×，到十二月其真实下限已约 ¥1.4e7（约为本次所用地板的 4.2 倍）⇒ **本分数只对窗口起点的规模成立**。',
  '今后本族任何 liq-1 的引用都必须同时给出「仓位数、推出的地板、slots 是否满、窗口内复利倍数」四项，否则 R=2 读起来像 R=3。',
].join('');

rq.recordFinding('小市值', {
  qId: 'q-e9-champ-liq-02fdafaa',
  type: 'isolate',
  component_or_param,
  metric_delta,
  window: 'train 2024-01-01→2024-12-31 (365d)',
  finding,
  confidence: 'high',
  flags: [
    '⚠零滑点高估',
    'removed-but-immaterial（不是 INERT：max|Δcum| 4.17pp）',
    'ceiling-unmeasured ⇒ 只支持 R ≥ 2 而非 3',
    'floor-derived-at-base-capital（全年复利 4.2×，十二月的有效下限约 ¥1.4e7）',
    'slots-measures-candidate-availability-not-confirmed-fills',
    'adjust_stock_num-defined-never-called（被调用则地板须重推）',
    'val-spent-and-failed: 本族 exit gate 仍 block，owner=human',
    'champion-changed-after-the-spent-VAL（0a7de9fa → 02fdafaa）',
    'posted-date: 02fdafaa 实际发帖 2025-06-06，文件名前缀 2026-10-30 是抓取日',
  ].join(', '),
  description,
  implication,
  spawned: '容量上限 liq-2 (¥1.67e7) / liq-3 (¥3.33e7)：builder 已声明、未构建、未运行（spawned，**不预先入列**——本族 VAL 已花尽，容量曲线产不出可过闸候选，须等人授予新 VAL）。两个方向都不开 improve。',
  edgeRef: '',
});

console.log('recorded q-e9-champ-liq-02fdafaa');
