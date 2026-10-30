// Appends the §2 row for q-e9-champ-liq-02fdafaa and the §4 / §6 entries, and rewrites the three
// frontmatter fields the EXIT GATE reads (realizability / realizabilityScope / realizabilityBasis).
// APPEND-ONLY for §2/§4/§6 — the frontmatter fields are the only rewrite, and the prior 0a7de9fa
// evidence is CARRIED, never discarded: the two are different books and both measurements are real.

const fs = require('fs');
const path = require('path');

const P = path.join(__dirname, '../../wiki/families/小市值.md');
let t = fs.readFileSync(P, 'utf8');
const before = t;

/* ------------------------------------------------------------------ §2 row */

const row2 = [
  '',
  '| **02fdafaa liq-1 流动性可行性地板 ¥3.33e6/日** | understand | ' +
    '**⚠⚠ 对照是本族新 champion [[02fdafaa_今天多个策略告警，这是什么意思，怎么解决？]] 自身的 epoch-9 台账行 3.0172 / sharpe 8.22 / annual 320.35 / maxDD 18.63（365d，曲线在盘）**，既不是 base 7a1c225f 的 1.3861，也不是前 champion [[0a7de9fa_中小盘趋势策略（年化85%）]] 的 2.6282 —— 三种对照互不可比，**不得并列读**。' +
    '**本行不是一条排名出来的研究想法，而是 EXIT GATE 自身的要求**：`integrate-eligible` 需要 `realizability >= 2` 而 UNKNOWN 一律 BLOCK，realizability 又是「一本书」的属性，换 champion 之后页上那个在 0a7de9fa 上取证的分数已不覆盖当前 candidate。' +
    '唯一改动：py2to3 后 **L137** `    return final_list` → `    return filter_liquidity_floor(context, final_list)`（`get_stock_list` 末行，615 行里仅此 1 行不同，recorder 独立复核，三枚 pin 齐备）。' +
    '**地板全部由本书自身仓位推出、无一处猜测**：源码无 `g.portfolio_value_proportion` ⇒ SINGLE SLEEVE；`buy_security`(L500-521) 以 `cash / target_num` 定仓、`target_num = g.stock_num = 6`（L50，被读 6 处、赋值仅 1 处）；capital 1,000,000 / 6 = 166,666.67 每仓，epoch 4 钉死 `order_volume_ratio = 0.05` ⇒ 单根日 bar 填满一仓需成交额 **≥ ¥3,333,333.33/日**。' +
    'helper 取 **20 根日 bar 的 median** `money`（单日放量不得送进常态不流动的名字），在 `context.previous_date` 求值（今天要交易的那根 bar 永不被查询）⇒ 非 lookahead；两个调用点（`weekly_adjustment` L149 10:30、`check_remain_amount` L216 的 14:25/14:55）都被这一处编辑覆盖。' +
    'builder `study/小市值/build-liq-02fdafaa.js`（断言撤销后与 `py2to3(raw)` 逐字节相同，并断言 `adjust_stock_num` 虽有定义但从未被调用），变体 `study/小市值/variants/02fdafaa-liq-1.py` | ' +
    '[[study-q-e9-champ-liq-02fdafaa]] | ' +
    '**+0.0020**（3.0172→**3.0192**） | −0.02（8.22→8.20） | **0.00**（18.63→18.63，**窗口也不动**：2024-05-07→2024-06-24 两边逐位相同） | informative | ' +
    '**按预注册三分落 (b)：名字确实被剔除、但代价为零甚至微正 ⇒ 02fdafaa 的 realizability = 2**（远过 epoch-9 的 1.0 闸门）。' +
    '⚠ **明确不是 (a)**：`max|Δcum| = 4.17pp`（2024-09-23），曲线并非逐位相同，所以正确判词是「**剔除了但不重要**」（removed but immaterial），**不是「地板是惰性的」** —— 这与 大小盘轮动 / b3751277 的 liq-1「曲线逐位相同」是两种不同结果。' +
    '证据细目：LIQFLOOR **91 行、0 ERROR 行**，`in > out` **仅 3 次**（均 in=10 out=9，previous_date 2024-09-18 / 09-19 / 09-23，**一个连续的九月中旬窗口**），cumIn=910 / cumOut=907 ⇒ 剔掉 **3 / 910 次候选评估 = 0.33%**；' +
    '**91/91 次 slots=6、minSlots=6、cumShort=0** ⇒ 一次都没有饿死、第 7 名顶替全部成功，且 `in=10` 恒定（6 槽常备 4 个备选）⇒ **Δ 纯为「名字质量」、不混入持仓稀释**（这是本行可读的前提，不是装饰）。' +
    '调用点分布 42 次 10:30（剔 2）· 43 次 14:25（剔 1）· 6 次 14:55（剔 0）。' +
    '机制很窄且可复述：地板在九月中旬的一个周度窗口换掉一个名字，第 7 名顶上并且略好，把 **0.23pp 从九月搬到十月**（09 月 27.1224→26.8924、10 月 19.6574→19.9321），**其余十个月月度 Δ 恰为 0.0000**（11 月 +0.0036 / 12 月 −0.0042 是 board-lot 舍入，11-01 后 `max|Δdaily| = 0.0056pp`）；首个相异日 **2024-09-19**，正是第一次剔除的次日；日收益相关 **0.998631**，年化波动 41.13%→41.29%。' +
    '本书自身的筛选链（399101 → 市值升序前 200 → 前 100 → 行业）本已排掉吃不下 ¥166.7k（5% 参与上限下）的名字，所以地板几乎无事可做。' +
    '两个 FREE 可观测量**都逐位保留**：**2024-01 月度收益 0.00% 两边相同**（`today_is_between` / `g.pass_april=True` 空仓）、**maxDD 窗口 2024-05-07→2024-06-24 两边相同** ⇒ 地板没有悄悄重塑这本书。' +
    'Jan–Nov 副读 3.0001→**3.0024**（Δ +0.0023，与全年同号同量级）⇒ **不是十二月产物**，与 [[study-q-e9-champ-emptymonth]] 测到的「本书不是十二月书」一致。' +
    '同口径横向对照（预注册约定相同，故可比）：前 champion 0a7de9fa（**2 仓**、¥1e7 地板）剔 **1.96%**（61/3116）、41 次中 15 次有剔除、Δ **−0.1823**；本书（**6 仓**、¥3.33e6 地板）剔 **0.33%**、91 次中 3 次、Δ **+0.0020** ⇒ 先验「6 仓的地板约小 3 倍 ⇒ 咬得更少」**被证实**。' +
    '⚠⚠ **四条载重保留**：(1) **容量上限未测** ⇒ 只支持 **R ≥ 2、不支持 3**（liq-2 ¥1.67e7 / liq-3 ¥3.33e7 已在 builder 的 `FLOORS` 表声明，**未建未跑**）；' +
    '(2) **地板按 BASE CAPITAL 推出** —— `buy_security` 按 `context.portfolio.total_value` 定仓而本书全年复利约 **4.2×**，故其**有效**下限随权益上行、到十二月约 **¥1.4e7**，而本次全程固定在 ¥3.33e6 ⇒ 测得的是**窗口起点的下限**（本仓每一条 liq-1 共有的诚实边界，0a7de9fa 同一条写作「1e7 只约束年初」）；' +
    '(3) `slots = min(6, n_out)` 测的是**候选可得性**、不是已确认成交 —— 它排除「被筛选饿死」，不排除每一种成交失败；' +
    '(4) ⚠ `adjust_stock_num` 有定义但**从未被调用**，一旦某个未来变体调用它、除数变为动态 3..6，地板必须重新推导、本分数作废。' +
    '⚠⚠ **本行不得被读成「本书可以送出 exit gate」**：本族在本台的 VAL 已**花尽且 FAIL**（`xsz-e9-champ`，前 champion 的零逻辑改动快照，VAL 2025 sharpe **0.83** < 1.0，已归档 `validated_strategies/xsz-e9-champ.py` 带 `gate_val: fail`）⇒ realizability 只是闸门两半里**可清**的那一半，另一半 owner 已是 **human**。' +
    '⚠ 本行**不运行任何 edge 的 test:**（它是可成交性测量，不是横截面方向），故 规模 与 低开反转 两条 claim 的 `status` 与 `evidence` 一律不动，`edgeRef` 刻意留空 |',
  '',
].join('\n');

const MARK3 = '\n## 3. 家族内绩效横评 (auto)';
if (t.indexOf(MARK3) === -1) throw new Error('section 3 marker not found');
t = t.replace(MARK3, row2 + MARK3);

/* --------------------------------------------------------------- §4 append */

const MARK5 = '\n## 5. 沿革 (provenance)';
if (t.indexOf(MARK5) === -1) throw new Error('section 5 marker not found');

const gap4 = [
  '',
  '- ✅ **CLOSED（本轮）：新 champion 02fdafaa 的流动性可行性下限**（§4 上一项「换 champion 之后那个分数已不覆盖当前 candidate」的直接答复）。',
  '  [[study-q-e9-champ-liq-02fdafaa]] 在本书自身推出的 **¥3.33e6/日** 地板上实测：剔 **3/910 = 0.33%** 候选评估（3 次调用，2024-09-18/09-19/09-23）、',
  '  **objective 3.0172 → 3.0192（Δ +0.0020）**、**maxDD 与其窗口完全不动**、**slots=6 全程**（cumShort=0）⇒ **R = 2**，frontmatter 的 `realizabilityScope` 已改挂到 02fdafaa。',
  '  ⚠ 这不是「地板惰性」：`max|Δcum| = 4.17pp`，它换了持仓名字、只是换得不重要（**removed but immaterial**，与 大小盘轮动 / b3751277 的「曲线逐位相同」不同类）。',
  '- ⚠⚠ **OPEN：02fdafaa 的容量上限（ceiling），现在是本支唯一剩下的可成交性问题。**',
  '  liq-1 测的是「吃不吃得下自己的仓位」（答案：吃得下，且几乎不付代价）；**容量是「能吃下多少」，不是「闸门上还剩多少余量」**（判据同 大小盘轮动 产品的 R=2 裁决）。',
  '  builder 的 `FLOORS` 表已把 **liq-2 = ¥1.67e7（5×）** 与 **liq-3 = ¥3.33e7（10×）** 预先声明（以免日后按口味补点），但**两者未构建、未运行**。',
  '  **不预先入列**：本族 VAL 已花尽，一条容量曲线产不出可过闸的候选，故它排在任何 improve 之后，只有在人授予新 VAL、本族重新有候选可送时才值得花回测分钟。',
  '  ⚠ 并且 liq-1 的地板是在 **base capital** 上推出的，而本书全年复利约 **4.2×** ⇒ 其**有效**下限到十二月已约 **¥1.4e7**，已经逼近 liq-2 的点位；',
  '  换言之「窗口起点可行」与「全年可行」是两个问题，后者未测。',
  '- ⚠⚠⚠ **本族 exit gate 仍然 BLOCK，而剩下的那一半 owner 是 `human`，不是 `research` —— 不得把 `realizability: 2` 读成「eligible」。**',
  '  闸门有两半：realizability（本轮**已清**，R=2 有了当前 candidate 自身的证据）与 **一次 PASS 的 VAL**（**已花尽且 FAIL**：`xsz-e9-champ`，前 champion 0a7de9fa 的零逻辑改动 pinned 快照，VAL 2025 sharpe **0.83** < epoch-9 的 1.0 闸门，已归档 `validated_strategies/xsz-e9-champ.py` 带 `gate_val: fail`）。',
  '  一次新的 VAL 需要人去设 **`JQ_ALLOW_REVAL`**，agent / recorder 均不得设 ⇒ 若 `family-queue` 仍把本族当 `integrate-blocked` 每天重派，**正确动作是撤掉那个环境变量或由人作判断，而不是再跑一轮 research**（与 [[study-q-e9-champ-val]] 的 implication (a) 同一条，本轮把它从「唯一的 block」收窄成「唯一剩下的 block」）。',
  '- ⚠⚠ **记给下一轮的事实（不是再花一次 VAL 的理由）：champion 在那次 VAL 之后已经改变。**',
  '  被验证的书是 **0a7de9fa**（彼时的 champion，objective 2.6282），而 2026-10-30 的 normalize 把 champion 换成了 **02fdafaa**（3.0172）⇒ **已花掉的那次验证验的不是本族当前最佳成员**。',
  '  这**不构成**重验的理由：「上次 VAL 让人失望，所以换一本候选再验一次」正是 `harness.md` 点名的**对 VAL 的逐次选择**，会把留出窗口悄悄变成第二个训练集。',
  '  ⚠ 而且 02fdafaa 的 **postedAt 是 2025-06-06**（文件名前缀 2026-10-30 是**抓取日**），作者看得见**整个 TRAIN 2024 与 VAL 2025 的前五个月** ⇒ 即便授予新 VAL，VAL 2025 对这本书的作者也大半是样本内。',
  '- **本支（399101 周度轮动）的评分状态已经分化，引用时须分清**：**02fdafaa 已评 R=2**（本轮，自身证据）；',
  '  同支的 39880585 / 7d57c262 / a40bc39b / 0d022129 / 5a70adc1 以外各本**仍未评分**，`realizabilityScope` 不代为给分 ⇒ 它们即便过闸也不得被当作本族 candidate 送出 exit gate。',
  '  **低开剥头皮支**（base 7a1c225f / 8dbd994c / 5e874b5b / a30641fb）按其自身实测证据**仍为 R=1**（买一/卖一额 100× 单位错误 ⇒ 头条约 7/8 不可成交），不得借本轮的分数过闸。',
  '- **一条引用纪律（由本轮收紧）**：今后本族任何 liq-1 的引用都必须同时给出 **「仓位数、推出的地板、slots 是否满、窗口内复利倍数」** 四项。',
  '  缺了就会把 R=2 读成 R=3 —— 本轮的 +0.0020 看起来像「地板不存在」，而它实际只说明「窗口起点的 ¥3.33e6 不是约束」。',
].join('\n');

t = t.replace(MARK5, gap4 + '\n' + MARK5);

/* --------------------------------------------------------------- §6 append */

const q6 = [
  '',
  '### Q（本轮，exit-gate 要求而非排名想法）：本族新 champion `02fdafaa` 吃得下自己的仓位吗？—— 它的 realizability 从未被测过',
  '',
  '**背景**：2026-10-30 的 normalize 把 champion 从 [[0a7de9fa_中小盘趋势策略（年化85%）]]（2.6282）换成 [[02fdafaa_今天多个策略告警，这是什么意思，怎么解决？]]（**3.0172** / sharpe 8.22 / annual 320.35 / maxDD 18.63，epoch 9，365 天）。',
  '页上的 `realizability: 2` 其 `realizabilityScope` 指名的是 **0a7de9fa** —— 另一本书、另一支（BBI 两仓 vs 399101 周度 6 仓）。realizability 是**一本书**的属性，而 `integrate-eligible` 对 UNKNOWN 一律 **BLOCK**，所以必须实测当前 candidate 自己的地板。',
  '容量也是唯一读不出源码的轴：大小盘轮动 的 liq-1 在 31/31 次 rebalance 剔 0 个（曲线逐位相同），而 ETF溢价 的把 sharpe **8.44 → 1.10**。',
  '',
  '**A（落预注册 (b)：剔除了，但不重要 ⇒ R = 2）**',
  '',
  '按本书自身仓位推出地板，无一处猜测：单 sleeve（无 `g.portfolio_value_proportion`）、`buy_security` 以 `cash / target_num` 定仓、`target_num = g.stock_num = 6`（L50）⇒ 每仓 ¥166,666.67，epoch 4 钉死 `order_volume_ratio = 0.05` ⇒ 单根日 bar 填满一仓需 **≥ ¥3,333,333.33/日**。',
  '一处编辑（L137 `get_stock_list` 末行）把 20 日 median `money` 地板插在**两个**买入调用点之前，在 `context.previous_date` 求值（非 lookahead）。',
  '',
  '| | objective | sharpe | annual% | maxDD% | maxDD 窗口 |',
  '|---|---|---|---|---|---|',
  '| control（台账行） | 3.0172 | 8.22 | 320.35 | 18.63 | 2024-05-07 → 2024-06-24 |',
  '| liq-1 @ ¥3.33e6/日 | **3.0192** | 8.20 | 320.55 | 18.63 | **2024-05-07 → 2024-06-24（不动）** |',
  '| Δ | **+0.0020** | −0.02 | +0.20 | **0.00** | — |',
  '',
  '- LIQFLOOR **91 行、0 ERROR**；`in > out` **仅 3 次**（in=10 out=9，previous_date **2024-09-18 / 09-19 / 09-23**，一个连续的九月中旬窗口）；cumIn=910 / cumOut=907 ⇒ 剔 **3/910 = 0.33%**。',
  '- **91/91 次 slots=6，minSlots=6，cumShort=0** ⇒ 从未饿死、第 7 名顶替全部成功；`in=10` 恒定（6 槽常备 4 备选）⇒ **Δ 纯为名字质量**。',
  '- **不是 (a) INERT**：`max|Δcum| = 4.17pp`；首个相异日 **2024-09-19**（第一次剔除的次日）；日收益相关 **0.998631**；波动 41.13% → 41.29%。',
  '- 月度表只有两格动：09 月 **−0.2300pp** / 10 月 **+0.2747pp**，其余十个月 Δ **恰为 0.0000** ⇒ 地板把 0.23pp **从九月搬到十月**，没有改变这本书其他任何部分。',
  '- 两个 FREE 可观测量**都逐位保留**：**2024-01 = 0.00% 两边相同**、**maxDD 窗口两边相同** ⇒ 地板没有悄悄重塑这本书。',
  '- Jan–Nov 副读 3.0001 → **3.0024**（Δ +0.0023）⇒ 与全年同号同量级，**不是十二月产物**。',
  '',
  '**为什么它几乎无事可做（机制，不是运气）**：本书的筛选链 399101 → 市值升序前 200 → 前 100 → 行业，本已排掉吃不下 ¥166.7k（5% 参与上限）的名字。',
  '同口径对照也支持这一读法：0a7de9fa **2 仓**、地板 ¥1e7（3× 大）⇒ 剔 **1.96%**、Δ **−0.1823**；本书 **6 仓**、地板 ¥3.33e6 ⇒ 剔 **0.33%**、Δ **+0.0020**。',
  '看数前写下的先验「6 仓的地板约小 3 倍 ⇒ 咬得更少」**兑现了**。',
  '',
  '**所以本轮改变了什么**：`realizabilityScope` 从 0a7de9fa 改挂到 **02fdafaa**，`realizabilityBasis` 记上本次测量 —— exit gate 的 **realizability 这一半从 UNKNOWN-BLOCK 变成 PASS**。',
  '',
  '**⚠⚠ 以及它没有改变什么（必须与上一句同时读）**：**闸门仍然 BLOCK**。另一半是「一次 PASS 的 VAL」，而本族在本台的 VAL **已花尽且 FAIL** —— `xsz-e9-champ`（前 champion 的零逻辑改动快照）VAL 2025 sharpe **0.83** < 1.0，归档于 `validated_strategies/xsz-e9-champ.py` 带 `gate_val: fail`。',
  '那一半的 owner 现在是 **`human`**（需要人设 `JQ_ALLOW_REVAL`，agent 与 recorder 均不得设），**不是 `research`** ⇒ 再派一轮 research 到本族只会重新导出同一个答案。',
  '**不要把 `realizability: 2` 读成「eligible」。**',
  '',
  '⚠ 并且：那次 VAL 花在 **0a7de9fa** 上，champion 此后已换成 **02fdafaa** ⇒ 已花掉的验证**验的不是本族当前最佳成员**。这是记给下一轮的事实，**不是**重验的理由（逐次换候选重验 = 对 VAL 的选择）。',
  '⚠ 02fdafaa 的 **postedAt = 2025-06-06**（文件名前缀 2026-10-30 是**抓取日**），作者看得见整个 TRAIN 2024 与 VAL 2025 的前五个月。',
  '',
  '**往下只剩一个可成交性问题，而且不预先入列**：**容量上限** liq-2（¥1.67e7，5×）/ liq-3（¥3.33e7，10×），已在 builder 的 `FLOORS` 表声明、未建未跑。',
  '地板是按 **base capital** 推出的，而本书全年复利约 **4.2×** ⇒ 其有效下限到十二月已约 **¥1.4e7**，已逼近 liq-2 ⇒ 「窗口起点可行」与「全年可行」是两个问题。',
  '⚠ 本轮**不运行任何 edge 的 test:**（可成交性测量，不是横截面方向）⇒ 规模 与 低开反转 两条 claim 的 `status` / `evidence` 一律不动。',
  '',
].join('\n');

t = t.replace(/\s*$/, '\n') + q6.replace(/^\n/, '');

/* ------------------------------------------------- frontmatter: the gate's fields */

const SCOPE = '"**本分数描述当前 candidate，即 bestVariant/champion [[02fdafaa_今天多个策略告警，这是什么意思，怎么解决？]]**（399101 中小板综指 + 周度轮动支、6 仓、周二 10:30；**不是** base 的低开剥头皮支，**也不是**前 champion 0a7de9fa 的 BBI 两仓支），依据是它在**自身推出的可行性下限 ¥3.33e6/日**上的实测（q-e9-champ-liq-02fdafaa：剔 3/910 = 0.33% 候选评估、objective 3.0172→3.0192（Δ +0.0020）、maxDD 18.63 不变且窗口 2024-05-07→2024-06-24 逐位相同、slots=6 全程）。给 **2 而非 3**：¥3.33e6 只是**窗口起点**的下限（buy_security 按 total_value 定仓、本书全年复利约 4.2× ⇒ 十二月的有效下限约 ¥1.4e7），容量上限未测（liq-2 ¥1.67e7 / liq-3 ¥3.33e7 已声明、未建、未跑），见 §4。⚠ 不是「地板惰性」：max|Δcum| = 4.17pp ⇒ 剔除了但不重要（removed but immaterial），与 大小盘轮动 / b3751277 的「曲线逐位相同」不同类。⚠ `adjust_stock_num` 有定义但从未被调用；若未来变体调用它，除数变为动态 3..6，地板须重推、本分数作废。⚠⚠ **三处 carve-out，本分数不覆盖**：(1) **低开剥头皮支** —— base [[7a1c225f_小市值低开优化]]、[[8dbd994c_年化180逻辑奇怪小市值]]、[[5e874b5b_低开小市值年化105]] 与 [[a30641fb_学习策略5年70倍]] 按其自身实测证据**仍为 R=1**（买一/卖一额 100× 单位错误 ⇒ 头条约 7/8 不可成交，q-e6-13/15/18/19），该支不得借本分数送出 exit gate；(2) **前 champion [[0a7de9fa_中小盘趋势策略（年化85%）]] 自身仍是 R=2，证据独立且仍然有效**（q-e9-champ-liq，¥1e7 地板、剔 1.96%、Δ −0.1823）—— 两本是不同的书、两次测量都是真的，不因换 scope 而作废；(3) **399101 周度轮动支的其余各本**（39880585 / 7d57c262 / a40bc39b / 0d022129 / aaba7575 / 76593fb6 / 2a4882de / 3a0d2c5e 等）**仍未评分**，见 §4 —— 不代为给分。⚠⚠ **本分数清掉的只是 exit gate 的一半**：另一半（一次 PASS 的 VAL）已花尽且 FAIL（xsz-e9-champ sharpe 0.83 < 1.0，gate_val: fail），owner = human ⇒ `realizability: 2` **不等于 eligible**"';

const BASIS = '"**低开剥头皮支 R=1**（原依据，仍有效）：xp-merge-1 candidate.json —— 头条的约 7/8 不可成交；the advertised 买一额>5万 gate is a 100x unit error（q-e6-13 / q-e6-15 / q-e6-18 / q-e6-19）。**前 champion 0a7de9fa R=2**（上一轮，证据保留、仍然有效，只是不再是当前 candidate）：q-e9-champ-liq —— 按其自身仓位推出的下限（1,000,000 / g.target_stock_count 2 / order_volume_ratio 0.05 = ¥1e7/日）下，41 次 rebalance 中 15 次有剔除、累计剔 61/3116 = 1.96%，objective 2.6282→2.4459（Δ −0.1823）、sharpe 7.07→6.59、maxDD 14.00 不变。**当前 candidate 02fdafaa R=2**（本轮新增，`realizabilityScope` 指名的就是它）：q-e9-champ-liq-02fdafaa —— 地板由本书自身仓位推出（capital 1,000,000 / g.stock_num **6**（L50，单 sleeve，无 portfolio_value_proportion）/ order_volume_ratio 0.05 = **¥3,333,333.33/日**），helper 取 20 根日 bar 的 median `money` 并在 context.previous_date 求值（非 lookahead），一处编辑（L137 get_stock_list 末行）覆盖两个买入调用点；实测 **91 次调用中仅 3 次有剔除**（2024-09-18 / 09-19 / 09-23，每次 in=10 out=9），累计剔 **3/910 次候选评估 = 0.33%**，**objective 3.0172→3.0192（Δ +0.0020）**、sharpe 8.22→8.20、**maxDD 18.63 不变且回撤窗口 2024-05-07→2024-06-24 逐位相同**，**91/91 次 slots=6（minSlots=6、cumShort=0）** ⇒ 从未饿死、Δ 纯为名字质量；2024-01 的 0.00% 空仓月也逐位保留。先验兑现：6 仓的地板比 0a7de9fa 的 2 仓小约 3 倍，咬得更少（0.33% vs 1.96%）。判 2 不判 3 的依据同 大小盘轮动 产品：容量是「能吃下多少」而不是「闸门上还剩多少余量」—— ¥3.33e6 只约束窗口起点，权益复利 4.2× 后十二月的有效下限约 ¥1.4e7，而 liq-2 (¥1.67e7) / liq-3 (¥3.33e7) 已声明未跑。⚠ slots = min(6, n_out) 测的是**候选可得性**、不是已确认成交：它排除「被筛选饿死」，不排除每一种成交失败。"';

function replaceFmBlock(text, key, value) {
  // Matches `key: ` plus its (possibly multi-line, quoted) value, up to the next top-level key.
  const re = new RegExp('(^|\\n)' + key + ': [\\s\\S]*?(?=\\n[a-zA-Z_]+: )');
  if (!re.test(text)) throw new Error(`frontmatter key not found: ${key}`);
  return text.replace(re, (m, p1) => `${p1}${key}: ${value}`);
}

t = replaceFmBlock(t, 'realizabilityScope', SCOPE);
t = replaceFmBlock(t, 'realizabilityBasis', BASIS);
// realizability itself stays 2 — asserted rather than rewritten, so a drift is loud.
if (!/\nrealizability: 2\n/.test(t)) throw new Error('realizability is not 2 — refusing to proceed');

t = t.replace(/\nupdatedAt: .*\n/, '\nupdatedAt: 2026-10-30\n');

if (t === before) throw new Error('nothing changed');
fs.writeFileSync(P, t);
console.log('page updated: §2 row + §4 gaps + §6 Q/A + realizabilityScope/Basis re-scoped to 02fdafaa');
