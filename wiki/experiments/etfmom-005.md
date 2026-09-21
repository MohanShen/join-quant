---
expId: etfmom-005
family: ETF动量
branch: main
commit: untracked                       # ⚠ enhance/candidates/etfmom-005.py 本轮未提交（人工审阅工作树后再定）
ideaId: idea-1                          # + enable_dynamic_position 后继步（队列内未单独开条目）
baseExpId: etfmom-004
harness_epoch: 6
hypothesis: 在 epoch 6（首次钉死股票侧 set_order_cost）的台子上，把家族 base 22152780 的小市值腿满仓（[1,0,0,0]）并打开作者自己关掉的两处回撤控制开关（avoid_trade_april、enable_dynamic_position），objective(TRAIN) 高于本纪元家族基线 etfmom-003 的 0.2944 且 gate(sharpe>=1.5) PASS。
reasoning: >
  证据链全部来自本家族自己的 study 台账，**不是**一个新机理假设：
  [[study-q-2]] 小市值腿满仓单跑自己就过闸（家族名指向的 ETF 腿满仓反而 DQ，[[study-q-1]]）；
  [[study-q-8]] 叠加 1/4 月日历规则 annual +7.56pp / maxDD −1.89pp，删掉的 10 笔全是亏损单、盈利单 90→90 不动、turnover 持平 ⇒ 成分变化而非降杠杆；
  [[study-q-9]] 动态仓位的 annual 成本实测 0.00pp、maxDD −1.89pp（「免费」的回撤削减器，但 n≈1 episode-risk）；
  [[study-q-10]] 两处开关在族内彼此独立（annual/sharpe/vol 三轴交互项近零）。
  ⚠ 因此本实验的**新颖度为零**：它与 study q-10 配置等价。它之所以仍值得跑，只因为
  harness.measurementValid(5) = false ⇒ **当前 epoch 6 台上不存在该配置的任何有效测量**，
  且本家族此前从未有任何一条臂跑过 VAL。
sourceRefs:
  - "[[ETF动量]] §1 第 6/8/9/10 条, §2 study-q-2 / q-3 / q-8 / q-9 / q-10 行, §4"
  - "[[study-q-2]]"
  - "[[study-q-8]]"
  - "[[study-q-9]]"
  - "[[study-q-10]]"
  - "[[harness/harness.md]] §2（epoch 4 钉死项 / epoch 6 股票成本钉死）"
mutation: >
  相对家族 base 文件（strategies/2026-06-21_无未来函数_模拟运行了俩月_小有成效-22152780.py）三行：
  L138 g.portfolio_value_proportion [0.5,0,0.5,0] -> [1,0,0,0]（小市值腿满仓、ETF 腿权重归零）；
  L169 g.avoid_trade_april False -> True；L186 g.enable_dynamic_position False -> True。
  另加冻结的 epoch-6 成本 OVERRIDE。无新因子、无结构改动，纯配置。
factors:
  选股: { 规模价值: [小市值] }
  择时: [日历-1/4月轮出(511880货币ETF)]
  风控: [止损冷却(base 自带, 未改), ATR止损(base 自带, 未改)]
  仓位: [满仓单腿, 波动率缩放目标名义(HS300 20日vol)]
iterations:
  - { step: 1, expId: etfmom-003, change: "家族 bestVariant（成员 23584678，纯 ETF 书）在 epoch 6 上重测 = 本纪元基线", train_objective: 0.2944, note: "annual 42.87 / sharpe 1.66 / maxDD 13.43 / total 103.92；⚠ 与后续各臂是跨成员比较" }
  - { step: 2, expId: etfmom-004, change: "改用家族 base 文件 + [1,0,0,0] + avoid_trade_april=True", train_objective: 0.6459, note: "annual 77.64 / sharpe 3.10 / maxDD 13.05 / total 215.05" }
  - { step: 3, expId: etfmom-005, change: "在 004 上再开 enable_dynamic_position（一行 diff）", train_objective: 0.6516, note: "annual 76.47 / sharpe 3.20 / maxDD 11.31 / total 210.94 ⇒ 收益 −1.17pp 换 maxDD −1.74pp，迭代最优，定稿" }
  - { step: 4, expId: etfmom-006, change: "另一支：在 004 上把 no_buy_after_day 2->3（不叠在 005 上）", train_objective: 0.5334, note: "annual 63.98 / sharpe 2.78 / maxDD 10.64 / total 168.52 ⇒ 劣化，丢弃；该旋钮就此关闭" }
results:
  train: { total: 2.1094, annualReturn: 0.7647, sharpe: 3.20, maxDrawdown: 0.1131, objective: 0.6516, gate: pass }
  val:   { total: 5.4414, annualReturn: 1.5380, sharpe: 5.27, maxDrawdown: 0.1407, objective: 1.3973, gate: pass }
status: recorded
confirmed: true                         # ⚠ 仅在下列 flags 的限定内成立（尤其 VAL-not-a-clean-twin）
flags:
  - ⚠⚠零滑点高估（满仓微盘 × 零滑点台；VAL 的 544.14% / annual 153.80% 绝不可读作可实现）
  - ⚠⚠VAL 非 TRAIN 干净孪生（apply_nine_point_audit 门控 > 2025-01-01，2025 半窗无 TRAIN 覆盖）
  - ⚠VAL 高夏普可能部分来自 avoid_trade_april 躲开 2024 年 1–2 月微盘踩踏（TRAIN 证据仅 n=4，overfit-suspect）
  - ⚠零新颖（= study q-10 配置在 epoch 6 上的重测，不是 enhance 发现）
  - ⚠vs etfmom-003 的 Δ 是跨成员比较、非消融
  - ⚠标签矛盾（小市值书挂 ETF动量 名；挂旗不裁）
ranAt: 2026-09-20
---

# 实验 etfmom-005：满仓小市值腿 + 1/4 月日历规则 + 波动率缩放仓位（epoch 6 首测 + 首次 VAL）

**假设**：在 epoch 6 台上，把家族 base 的小市值腿满仓并打开作者关掉的两处回撤控制开关，
`objective(TRAIN)` 高于本纪元家族基线 etfmom-003 的 0.2944 且 `gate(sharpe ≥ 1.5)` PASS。

## 变异

相对家族 `base`（[[22152780_七星ETF轮动V1.7.2]]，3255 行）**三行配置**，无结构改动：

| 行 | 原值 | 改为 | 作用 |
|---|---|---|---|
| 138 | `g.portfolio_value_proportion = [0.5,0,0.5,0]` | `[1,0,0,0]` | 小市值腿满仓；同名 ETF轮动腿权重归零 |
| 169 | `g.avoid_trade_april = False` | `True` | 1/4 月把小市值腿整体轮进 511880 货币 ETF（**不是转现金**） |
| 186 | `g.enable_dynamic_position = False` | `True` | 按 HS300 20 日收益率标准差把目标名义从 1.0 线性压到 0.5 |

外加冻结的 **epoch-6 成本 OVERRIDE**（本纪元首次把 **stock** 侧 `set_order_cost` 也钉死）。

## 结果

| 窗口 | total | 年化 | 夏普 | 最大回撤 | objective | gate |
|------|------|------|------|----------|-----------|------|
| TRAIN 2022-01-01..2023-12-31（定稿版） | 210.94% | 76.47% | 3.20 | 11.31% | **0.6516** | pass |
| VAL 2024-01-01..2025-12-31（定稿确认，跑一次） | 544.14% | 153.80% | 5.27 | 14.07% | **1.3973** | pass |

（无 HOLDOUT —— 保留 OOS 禁用，`OOS-BLOCKED`；本流水线不产出 2025/OOS 独立口径的数字。）

**⚠⚠ 上表的绝对水平不可读作可实现**：全是满仓微盘个股跑在零滑点台上，VAL 的
`544.14% / annual 153.80%` 是本家族（乃至本项目）产出过的最被夸大的一组数字。
**唯一可信的量是同腿、同纪元臂间的 Δ**（etfmom-004 → 005 是一行 diff、同一条腿）。

## 迭代轨迹

| 步 | expId | 改动 | objective(TRAIN) | Δ | 判定 |
|---|---|---|---|---|---|
| 1 | etfmom-003 | 家族 `bestVariant`（成员 23584678，**纯 ETF 书**，另一个源文件）在 epoch 6 上重测 | 0.2944 | — | 本纪元基线 |
| 2 | etfmom-004 | 换用家族 `base` 文件 + `[1,0,0,0]` + `avoid_trade_april=True` | 0.6459 | +0.3515 vs 003（**跨成员**） | 推进 |
| 3 | **etfmom-005** | 004 + `enable_dynamic_position=True`（一行 diff） | **0.6516** | **+0.0057 vs 004** | 推进 → **定稿** |
| 4 | etfmom-006 | 004 + `no_buy_after_day 2→3`（**不**叠在 005 上） | 0.5334 | −0.1125 vs 004 | 丢弃 |

**第 3 步的细账**：annual 77.64 → 76.47（**−1.17pp**）、maxDD 13.05 → 11.31（**−1.74pp**）、
sharpe 3.10 → 3.20（+0.10）。⇒ 在 epoch 6 上，动态仓位仍是一个**近乎免费的回撤削减器**，
形态与 epoch-2 的 [[study-q-9]]（annual 成本 0.00pp、maxDD −1.89pp）一致，
但**两个纪元的数字不可并列**，这里只作形态对照。

**第 4 步的结论（一个被关闭的旋钮）**：`no_buy_after_day` **自作者值 2 起向上单调变差** ——
2→3 在 epoch 6 上 0.6459 → 0.5334，2→5 在 epoch 5 上 0.6459 → 0.4892。
更长的冷却把**赢家的再入场**一起挡掉，与 [[study-q-11]]「被冷却挡住的 7 个回合全是亏损单」
**不是线性外推关系**。该旋钮向上方向就此关闭。

## 结论

**假设成立：`objective(TRAIN)` 0.6516 ≫ 基线 0.2944，`gate` PASS；定稿 VAL 1.3973 / sharpe 5.27
同样过闸且与 TRAIN 同向 ⇒ `confirmed: true`。但这句话必须带着下面六条限定读，否则就是错的。**

1. **⚠ 作为发现，新颖度为零。** 本配置与家族 §2 已有的 **study q-10**（满仓小市值 + both-ON）**等价**。
   它之所以被跑，只因为 `measurementValid(5) = false` ⇒ epoch 6 台上不存在该配置的有效测量；
   且本家族此前**从未有任何一条臂跑过 VAL**。⇒ 正确的记法是
   「**q-10 配置在 epoch 6 上的首个有效测量 + 本家族第一个 VAL-eligible 配置**」，
   **不是**一次 enhance 发现。功劳属于 study（q-2 / q-8 / q-9 / q-10）。
2. **⚠⚠ 零滑点高估。** 见上。**LEVEL 不可实现，只有 Δ 可信。**
   同轮的成本审计给了这条纪律一个量化下界：同一条臂在三档股票成本下 `total` 为
   **223.64%（作者自报成本）/ 215.05%（epoch-6 钉死）/ 71.47%（1%/侧）** ——
   **1%/侧就吃掉 152pp**，本血统对成本假设极其敏感。
3. **⚠⚠ VAL 不是 TRAIN 的干净孪生。** `apply_nine_point_audit` 由 `> 2025-01-01` 门控 ⇒
   **VAL 窗的 2025 那一半执行的是 TRAIN 零覆盖的代码路径**（家族 §4 常设 HOLDOUT 警告的正面兑现）。
   该 VAL 数字是一次**合法的单文件单台测量**，但**不是**对 TRAIN 所测机制的纯样本外重放。
   任何「该机制已通过样本外检验」的表述都是**过度声明**。
4. **⚠ VAL 的高夏普有一个尚未排除的廉价解释。** VAL 覆盖 **2024 年 1–2 月微盘踩踏**，而
   `avoid_trade_april` 每年 1 月 / 4 月把小市值腿整体轮进 511880 ⇒ VAL 窗内**新增 4 次触发**，
   而该规则的 TRAIN 证据只有 **n=4、已标 overfit-suspect**。
   高 VAL 夏普**可能部分就是这条规则躲开了 2024 的那一段**。⇒ **记作「待审查」，不得读作持久技能**；
   要分清须做窗口切分（如 2024-01→03 子窗），本轮不做。
5. **⚠ Δ 口径分裂。** vs **etfmom-003** 的 +0.3572 是**跨成员比较**（不同源文件：base 3255 行 vs
   成员 23584678 约 1683 行的纯 ETF 书），**不是 ablation**，且两臂**现实性等级不同**；
   vs **etfmom-004** 的 **+0.0057 / +0.10 / −1.74pp** 才是一行 diff 的干净读数。
6. **⚠ 标签矛盾（沿用家族裁定）。** 本臂实质是一本**小市值**书挂着 **ETF动量** 的家族名。
   家族页已记录该矛盾并裁定**挂旗不裁**（人工裁定，精度 `c374bf5`）⇒ 本轮**只挂旗**，
   不改 `family:`、不重新归档。
7. **⚠ 与家族页旧数字不可比。** `measurementValid(5) = false` ⇒ §3 横评与 §2 的 q-1…q-12 行
   （epoch 2/4/5）在本纪元**全部作废**；frontmatter 的 `bestObjective: 0.5267` 是**陈旧的 epoch-2 值**。

**附：一个值得记住的探针陷阱（同轮的副产品）。** 此前一次「epoch-6 股票成本钉死是惰性的」的误报，
根因是**探针自己调用 `set_order_cost` 时被 OVERRIDE 的同名影子函数拦截** —— 影子丢弃调用方的参数、
重新施加台子的值，于是探针实际上从未改变过成本。**在被 OVERRIDE 包住的代码里改成本，必须调用
被捕获的原函数 `__jq_set_order_cost`。** 该误报已撤回；epoch 6 的股票成本钉死**确实咬合**。

## 回填指针（§9）

- 家族页 [[ETF动量]] §2 新增变体行 `enhance-etfmom-005`（主记录）；§4 新增两条
  （`no_buy_after_day` 关闭；epoch-6 股票成本审计 + 探针陷阱）。
- [[仓位管理]]「观察」：波动率缩放仓位在 epoch 6 上的复现 + 首个 VAL 读数。
- [[止损模块]]「观察」：「止损后冷却」的**长度**旋钮自 2 起向上单调变差，ON/OFF 测量不能外推到剂量方向。
- [[小市值因子]]「观察」：VAL 窗含 2024 微盘踩踏 + 日历规则 ⇒ 高 VAL 夏普的归因陷阱。
- `study/_probes/README.md`：OVERRIDE 影子函数拦截探针的陷阱。
- `wiki/log.md`：`experiment` 条目。
