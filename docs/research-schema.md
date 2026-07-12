# join-quant 自主研究（autoresearch）Schema

本文件定义 `research/` 自主策略研究循环的结构与规则，是 `docs/wiki-schema.md`（知识库 Schema）的姊妹篇。
灵感来自 Andrej Karpathy 的 [`autoresearch`](https://github.com/karpathy/autoresearch)：
**「人类只编辑 `program.md`/`harness.md`，AI 在冻结的评测台上自主迭代策略；迭代/选择全凭 `objective(TRAIN)`，定稿才验 VAL。」**
本项目把「AI」实现为一个**四智能体团队**（点子/筛选/工程/记账，见 `research/program.md`）。

本项目在其基础上加了 autoresearch 没有的东西：一个**持久知识库**（`wiki/`）。
因此研究循环是闭环的：

```
wiki「待研究/空白/归一化横评」 → 想法+推理 → 变异 candidate.py
        ↑                                          │
        │                                          ▼
   回填 wiki + 归档 validated_strategies/  ←  TRAIN 迭代→定稿→VAL 确认  ←  冻结评测台回测
```

分工同 `wiki-schema.md`：**人类**提方向、审阅、裁决冲突、维护冻结常量、说「停」；**四智能体团队**负责产想法、筛选排队、生成/回测、记账回填。

---

## 1. 与 autoresearch 的对应关系

| autoresearch | 本项目 | 说明 |
|---|---|---|
| `train.py`（被编辑的产物） | `research/candidates/<expId>.py`（策略源码） | 唯一被变异的对象 |
| `prepare.py`（只读评测台） | **冻结评测台**（§3）：回测窗口 + 标的池 + 费率滑点 + 目标函数 | **绝不可被 agent 修改** |
| `val_bpb`（单标量） | `objective`（§3.3），迭代在 **TRAIN** 上度量、定稿在 **VAL** 确认 | 越大越好 |
| 固定 5 分钟预算 | 固定回测窗口（train/val，§3.1；2025+ OOS 禁用） | 保证实验可比 |
| `results.tsv` | `research/results.tsv`（§7） | 追加式账本，git 不跟踪 |
| `program.md` | `research/program.md`（**四智能体团队**编排） | 研究团队的 agent 指令 |
| keep=advance / discard=git reset | 迭代在 TRAIN 推进/回退；**定稿**才跑一次 VAL（§8） | |
| （无持久知识） | `wiki/experiments/`（§6）+ 回填契约（§9） | **本项目独有** |

---

## 2. 目录结构

```
join-quant/
├── research/
│   ├── program.md              # 四智能体团队编排指令（人类编辑，见姊妹文件）
│   ├── harness.md              # 冻结评测台常量的权威定义（§3，人类维护，改动即新纪元）
│   ├── strategy_template.py    # 策略脚手架（§5）：受控因子槽位
│   ├── candidates/<expId>.py   # 每个实验的策略源码（变异产物，raw）
│   ├── ideas-queue.json        # Agent 2 排名想法队列（git 不跟踪）
│   ├── loop-state.json         # 断点检查点（git 不跟踪）
│   └── results.tsv             # 追加式账本（§7，git 不跟踪）
├── validated_strategies/       # 定稿并跑过 VAL 的策略归档（Agent 4 写，git 跟踪 = 产物货架）
│   └── <expId>.py              #   candidate 拷贝 + 指标头注（train/val objective, gate）
└── wiki/
    └── experiments/<expId>.md  # 每个实验一页（§6）：假设·变异·迭代轨迹·TRAIN/VAL结果·结论·回填指针
```

- `research/candidates/` 与 `strategies/` 一样属于 **raw 层**：一旦回测过即不可变（git 记录演进）。
- `wiki/experiments/` 是 wiki 的**第四类页面**（前三类：strategies / concepts / authors）。
- 所有正文为**中文**，与 `wiki-schema.md`、`push-format.md` 一致。

---

## 3. 冻结评测台（frozen harness）

这是本 Schema 的核心。类比 `prepare.py`：**一经设定即冻结，agent 只读不可改**。
**权威常量定义在 `research/harness.md`**（本节仅摘要，冲突以 harness.md 为准）。
任何改动都视为「新纪元」，需人类在 `research/harness.md` 显式变更并记 `log.md`，此前所有实验结果就此封版、不再与新纪元横比。

### 3.1 三个回测窗口（period split）

用 JoinQuant Pipeline 2（`utils/strategy-post-backtest.js`）的回测区间参数实现。当前 epoch 2（权威见 `research/harness.md` §1）——**严格窗口协议**：

| 窗口 | 区间 | 用途 | 谁能跑 / 何时 |
|---|---|---|---|
| **TRAIN** | 2022-01-01 → 2023-12-31 | **迭代与选择**：变异搜索在此，选择指标 = `objective(TRAIN)` | Agent 3，迭代中（Type-1）可无限次 |
| **VAL** | 2024-01-01 → 2024-12-31 | **定稿确认**：仅对已定稿策略跑一次做泛化检验 | Agent 3，仅 Type-2（定稿）时 |
| ~~OOS~~ | 2025-01-01 → 今 | **保留样本外**——用户私有最终检验 | **任何 agent 禁用**（代码硬阻断 `OOS-BLOCKED`） |

> **迭代只看 TRAIN，定稿才碰 VAL，2025+ 永不触碰**。`strategy-post-backtest.js` 对任何 `>= 2025-01-01`
> 的窗口抛 `OOS-BLOCKED` 拒跑（除用户私测 `JQ_ALLOW_OOS=1`）——代码级保证，不是口头约定。
> ⚠ 区间特性：TRAIN 无明显牛市、VAL 仅一年、夏普噪声大——故 VAL 只作定稿泛化参考，不作逐轮选择（`harness.md` §1）。

### 3.2 标的池与成本假设（冻结，权威见 `harness.md` §2–§3）

- **手续费**：`PerTrade(buy_cost=0.0003, sell_cost=0.0013, min_cost=5)`（买万3 / 卖万3+印花税千1 / 最低5元）。
- **滑点**：**零滑点** `FixedSlippage(0)`——刻意与社区/wiki 绩效保持可比。**代价：换手成本被忽略**，高换手/微盘/打板类 `objective` 被系统性高估；此类 keep 必标「零滑点高估」（详见 `harness.md` §2 警示）。
- **基准**：`000300.XSHG`，仅显示用，不影响 `objective`（夏普对基准无关）；固定它只为跨实验一致。
- **基础资金**：￥1,000,000；**真实性过滤**（剔除 ST/停牌/次新、涨停不买/跌停不卖）强制内置于 `strategy_template.py`，不得移除（`harness.md` §3）。
- **真实性红线**：继承 wiki 的 ⚠ 约定——打板/涨停/龙虎榜等**成交假设不真实**的范式，其回测收益不得当作可实现收益；此类实验必标 ⚠，`objective` 仅作参考、不得据以宣称「有效」。

### 3.3 目标函数（objective）——本项目的 `evaluate_bpb`

单标量，越大越好。在指定窗口 `w` 上：

```
gate(w)   = ( sharpe(w) >= 2.5 )                       # 硬门槛：夏普 < 2.5 直接淘汰
score(w)  = annualReturn(w) - maxDrawdown(w)           # 均为小数（0.35 = 35%）
objective(w) = score(w)        若 gate(w) 为真
             = DQ (disqualified，记为 -inf)   否则
```

- **选择指标** = `objective(TRAIN)`：Agent 1 迭代中的 keep/继续/定稿全看它（§8）。`objective(VAL)` 仅在**定稿后**算一次做泛化确认，由 Agent 4 记账，**不参与迭代选择**（否则 VAL 泄漏）。2025/OOS 永不计算。
- `gate` 未过（夏普 < 2.5）即 `DQ`，等价于淘汰该变异，无论收益多高。
- `score` 用「年化 − 最大回撤」而非夏普/卡玛：奖励高收益、惩罚深回撤，夏普退化为门槛而非连续目标。
- 门槛值 2.5、公式形式均属**冻结常量**，改动即新纪元。

---

## 4. 假设来源（hypothesis）

实验不能凭空起。每个实验的假设必须可溯源到 wiki 的某处「缺口」或「观察」：

1. **概念页「待研究/空白」小节**——首选来源。这是 KB 明确登记的知识缺口。
2. **概念页「变体与差异」表**——横向对比暴露的规律（如「加了大盘趋势止损的小市值回撤更低」）可作为可检验假设。
3. **`/query-wiki` 回填的「观察」**——过往问答沉淀的规律。
4. **跨概念组合**——把两个概念页的因子拼装（如 [[小市值因子]] × [[择时-均线]]），检验 1+1 是否 >2。

每个假设写成一句可证伪的话，落入实验页 frontmatter 的 `hypothesis` 字段（§6）。

---

## 5. 策略脚手架与变异空间（mutation space）

策略不是随意改代码，而是从 KB 的**受控因子词表**（`wiki-schema.md` §2.1）组合而来。
`research/strategy_template.py` 提供带槽位的骨架，槽位对应四类因子角色：

```
选股因子  →  规模价值 / 质量基本面 / 动量 / 技术量价 / 流动性 / 情绪事件
择时因子  →  趋势均线 / 位置估值 / 日历 / 防御信号
风控因子  →  §3.1 止损类型枚举
仓位因子  →  等权 / 动态持仓数 / 满仓单标的 / 流动性配权 / 预留资金
```

一次「变异」= 下列之一：
- **参数调整**：在既有因子上调参（均线周期、持仓数、止损线）。
- **因子增删**：加/减一个受控因子（如给纯小市值加「大盘趋势」风控）。
- **模块替换**：换择时或风控模块（如 MA10偏离 → RSRS）。
- **跨概念拼装**：组合两个概念族的信号。

新因子子类/概念**必须先登记** `wiki-schema.md` 的受控词表，再使用——杜绝同义分叉，与 ingest 规则一致。

---

## 6. 实验页格式 `wiki/experiments/<expId>.md`

`expId` = `<tag>-<NNN>`（如 `jul3-007`），与分支 `research/<tag>`、账本行、`candidates/<expId>.py` 一一对应。

```markdown
---
expId: jul3-007
branch: research/jul3
commit: <7位短哈希>                      # candidates/<expId>.py 的提交
ideaId: idea-12                         # 来自 ideas-queue.json 的想法 id
baseExpId: jul3-006                     # 本实验（定稿版）从哪个 candidate 变异而来（首个填 baseline）
hypothesis: 给最小市值轮动叠加深证综指MA10择时能把回撤压到15%以内而不牺牲年化   # 一句可证伪的话
reasoning: <为什么可能成立：逻辑或既往回测事实，引用 [[expId]]/概念页>
sourceRefs: [[[小市值因子]], [[择时-均线]]]   # 假设溯源到的 wiki 页
mutation: 在 baseline 上增加 择时·趋势均线(深证综指MA10偏离) 空仓开关
factors:                                # 同 wiki-schema §2.1，四角色受控
  选股: { 规模价值: [小市值], 质量基本面: [国九条] }
  择时: [深证综指MA10偏离]
  风控: [止损线-9%]
  仓位: [等权, 动态持仓数]
iterations:                             # Agent 1 在 TRAIN 上的迭代轨迹（每步改了什么 + objective(TRAIN)）
  - { step: 1, change: "初版", train_objective: <数或DQ> }
  - { step: 2, change: "持仓数5→10", train_objective: <数或DQ> }
results:                                # 迭代终版的 TRAIN + 定稿 VAL（无 holdout——OOS 禁用）
  train:   { annualReturn: <小数>, sharpe: <数>, maxDrawdown: <小数>, objective: <数或DQ> }
  val:     { annualReturn: <小数>, sharpe: <数>, maxDrawdown: <小数>, objective: <数或DQ> }
status: recorded | val-dq | crash       # 与账本一致（recorded=定稿记账；val-dq=定稿但VAL未过门槛）
confirmed: true | false                 # VAL 是否过门槛且与 TRAIN 同向
flags: [overfit?, ⚠零滑点高估]           # 可选：VAL 明显劣于 TRAIN 记 overfit
ranAt: <YYYY-MM-DD>
---

# 实验 jul3-007：小市值 + MA10择时

**假设**：<复述 frontmatter 的可证伪命题>

## 变异
<相对 baseExpId 具体改了什么：加了哪个因子/调了哪个参数，引用 [[概念]]>

## 结果
| 窗口 | 年化 | 夏普 | 最大回撤 | objective |
|------|------|------|----------|-----------|
| TRAIN（迭代终版） | … | … | … | … |
| VAL（定稿确认） | … | … | … | … |
（无 HOLDOUT——2025+ OOS 禁用）

## 迭代轨迹
<Agent 1 在 TRAIN 上试了哪几步、各步 objective(TRAIN)、为何这样收敛、何时判定定稿>

## 结论
<假设成立与否？TRAIN 上相对 baseExpId 是提升还是劣化？定稿 VAL 是否过门槛且与 TRAIN 同向（confirmed）？>

## 回填指针（§9）
- 已回填至 [[择时-均线]]「观察」小节：<一句结论>
- 或：无跨策略价值，未回填。
```

---

## 7. 结果账本 `research/results.tsv`

追加式，制表符分隔（**非逗号**，描述里会有逗号）。**git 不跟踪**（同 autoresearch，`.gitignore` 加 `research/results.tsv`）。
账本是快速 `grep` 的一手记录；`wiki/experiments/` 是其结构化、带溯源的对应物。

**每个定稿策略一行**（迭代中的 TRAIN 步不单独占行，浓缩进实验页 `iterations`）。10 列：

```
expId	commit	ideaId	baseExpId	train_objective	val_objective	sharpe_val	gate_val	status	description
```

1. `expId`（如 `jul3-007`）
2. `commit`（7 位短哈希）
3. `ideaId`（来自 `ideas-queue.json`）
4. `baseExpId`（从哪个 candidate 变异；首个填 `baseline`）
5. `train_objective`（迭代终版 TRAIN 目标值；DQ 记 `DQ`）
6. `val_objective`（定稿 VAL 目标值；DQ 记 `DQ`）
7. `sharpe_val`（定稿 VAL 夏普）
8. `gate_val`（`pass`/`fail`，VAL 是否过 2.5 门槛）
9. `status`：`recorded` / `val-dq` / `crash`
10. 简短描述（想法 + 迭代收敛到什么）

示例：

```
expId	commit	ideaId	baseExpId	train_objective	val_objective	sharpe_val	gate_val	status	description
jul3-000	a1b2c3d	baseline	baseline	1.35	1.23	5.42	pass	recorded	baseline 低开小市值
jul3-001	b2c3d4e	idea-3	jul3-000	1.47	1.41	6.42	pass	recorded	持仓数5→10，TRAIN 收敛后定稿
jul3-002	c3d4e5f	idea-7	jul3-001	1.52	0.88	1.9	fail	val-dq	国九过滤：TRAIN 升但 VAL 跌破门槛，标注
```

---

## 8. 迭代 / 定稿 / branch 规则（四智能体，权威流程见 `research/program.md`）

团队跑在专用分支 `research/<tag>`。状态机与角色见 `research/program.md`；此处定义 keep/finalize 的判据：

**迭代（Type-1，只在 TRAIN）**——由 Agent 3 跑、Agent 1 判：
1. Agent 1 从当前迭代最优提一个**小步变异**（或队列新想法的初版），Agent 3 写 `candidates/<expId>.py` 并 `git commit`。
2. 回测 **TRAIN**，读 `objective(TRAIN)`：
   - **`gate(TRAIN)` 且 `objective(TRAIN) > 当前迭代最优`** → 正向改进：推进为新迭代最优。Agent 1 再判**是否定稿**（已迭代充分、想不出更多有价值变异）。
   - **DQ 或 ≤ 当前最优** → 本次变异丢弃（`git reset` 回上一步）。同一想法**多次无改进** → Agent 1 **放弃该想法**，转 Agent 2 取队列下一个。
3. 未定稿 → 回到 1 继续迭代（TRAIN）。

**定稿（Type-2，跑一次 VAL）**——Agent 1 定稿后：
4. Agent 3 用 **`--window val`** 跑一次定稿版，得 `objective(VAL)`、`gate(VAL)`。
5. Agent 4 记账：`status: recorded`（VAL 过门槛）或 `val-dq`（VAL 未过门槛，仍记账并标注）；`confirmed = gate(VAL) 且 VAL 与 TRAIN 同向`。写账本（§7）+ 实验页（§6）+ 回填（§9）+ `wiki/log.md`，**并把定稿策略归档到 `validated_strategies/<expId>.py`**（拷贝 candidate + 指标头注；每个拿到 VAL 结果的定稿策略都归档，`gate_val` 标 pass/fail；此目录 git 跟踪，是流水线产物货架）。交回 Agent 1 开下一轮。

- **首个** `<tag>-000` = **baseline**：某个已归一化的过门槛策略 + 冻结成本 override，在 TRAIN 上确立基准线（§11.5）。
- **VAL 绝不驱动迭代选择**——只对定稿版跑一次确认。任何用 VAL 逐轮调参 = 泄漏。
- **2025+ OOS 绝不触碰**——代码 `OOS-BLOCKED` 硬阻断。
- **崩溃**：回测跑不动/CDP 掉线/策略报错，判断是否手误可修；否则记 `crash`，跳过。
- **超时/限流**：JoinQuant Pipeline 2 是唯一执行器，受 CDP 会话与 VIP 限额约束；throughput 远低于 autoresearch 的 100/夜。可按批次人机协作推进，但**单批次内**遵循上述自主循环。

---

## 9. 知识回填契约（write-back）

实验产生两类知识：

1. **单实验结果** → `wiki/experiments/<expId>.md`（§6）+ 账本（§7）。
2. **跨策略规律** → 回填到相关**概念页**。复用 `/query-wiki` 的回填机制：**只追加**到概念页的「观察」或「待研究/空白」小节，**不覆盖**既有结论。

回填规则（与 `wiki-schema.md` §9 一致）：
- **可溯源**：概念页每条新结论必须带 `[[<expId>]]` 指针，回溯到实验页 → commit → `candidates/<expId>.py`。
- **追加优先**：概念页只加不改；矛盾只标记、留人裁决。
- **闭环登记**：假设若来自某概念页的「待研究」，实验有结论后应把该条从「待研究」移动/更新为「观察」，并注明 `[[expId]]`。
- **`log.md` 新增 op** `experiment`：
  ```
  ## [YYYY-MM-DD] experiment | jul3-007 (小市值+MA10择时) train=0.31 val=0.28 recorded → 回填 [[择时-均线]]
  ```
  op 全集扩展为：`ingest` / `skip-dup` / `concept` / `query` / `lint` / `merge` / **`experiment`**。

---

## 10. 不可违反的原则

- **评测台冻结**：`objective`、门槛 2.5、窗口区间、费率滑点一经设定即不可改；改动即新纪元，旧结果封版。
- **严格窗口**：迭代只 TRAIN、定稿才 VAL、**2025+ OOS 绝不触碰**（代码 `OOS-BLOCKED` 硬阻断，agent 绝不设 `JQ_ALLOW_OOS`）。任何用 VAL 逐轮调参或触碰 OOS 都使纪元作废。
- **raw 不可变**：`strategies/` 与已回测的 `research/candidates/` 均不改。
- **真实性红线**：继承 wiki 的 ⚠ 约定；不真实成交的范式不得宣称「有效」。
- **可溯源**：账本、实验页、概念页结论均可回溯到 commit 与源码。
- **受控命名**：因子/概念一律走 `wiki-schema.md` §2 词表，先登记后使用。
- **追加与人裁**：概念页只追加；冲突只标记、不自行裁决。

---

## 11. 归一化（normalize）——把 raw 策略重测到统一基线

`strategies/` 里的 144+ 策略是**不同年代、不同费率/滑点、不同回测区间**下自报绩效的 raw 层，彼此不可横比。
归一化 = 用**冻结评测台**把每个 raw 策略在**同一 TRAIN 区间、同一成本、同一 objective** 下重测一遍，
得到 apples-to-apples 的「谁在统一区间真能打」——这是 autoresearch 的**先验基线**：
已知有效的策略/因子 = 归一化后过门槛者，据此挑选变异起点、避免重复造轮子。

### 11.1 强制成本归一（raw 不可变）
- 每个 raw 策略源码**尾部追加**一段 override（不改 `strategies/` 原文，写临时副本喂 Pipeline 2）：
  重定义 `set_slippage`/`set_commission` 为**恒定冻结值**（零滑点 + `PerTrade(万3/万13/5)`），
  这样即便策略在 `before_trading_start`/`handle_data` 里**逐 bar 重设**成本，也一律被拉回冻结值；
  并包裹 `initialize` 补 `use_real_price=True`。见 `utils/strategy-normalize.js` 的 `OVERRIDE`。
- 区间/基础资金（¥100万）由 Pipeline 2 平台参数强制（`--window train`）。

### 11.2 批量执行器与账本
- `node utils/strategy-normalize.js --window train [--filter <substr>] [--limit N]`：枚举 → 兼容性预检 → 追加 override → 跑 Pipeline 2 → 解析 SUMMARY → 写账本。
- **可续跑**账本 `research/normalize-<window>.tsv`（git 不跟踪），已有终态的策略跳过。列：
  `sourceFile  postId  title  status  start  end  days  total_pct  annual_pct  sharpe  maxdd_pct  objective  gate`
- `status`：`normalized`（完成，可入 KB）/ `incompatible-futures`（期货，stock 回测跑不了）/ `incompatible-notrunnable`（无 `initialize` 的工具/研究页）/ `crash`（回测报错）/ `window-mismatch`。
- `objective` / `gate` 同 §3.3（`annual−maxdd`，门槛 `sharpe≥2.5`；不过门槛记 `DQ`/`fail`）。

### 11.3 KB 更新契约
账本产出后，按下列方式更新 wiki（可分批，像 ingest 一样）：
- **策略页 frontmatter** 增 `normalized` 块（可溯源到本次 epoch 与账本）：
  ```yaml
  normalized:
    epoch: 1
    window: TRAIN 2022-01-01..2023-12-31
    annualReturn: <小数>   sharpe: <数>   maxDrawdown: <小数>
    objective: <数或DQ>    gate: pass|fail
    ranAt: <YYYY-MM-DD>
  ```
  与页内既有「自报绩效」并存、不覆盖；若归一化结果与自报差距大，在「备注/矛盾」注明（区间/成本差异）。
- **概念页** 增「## 归一化绩效横评（TRAIN 2022–2023）」小节：按 `objective` 排序的表，
  标 `gate pass/fail`，一眼看出该概念下**统一区间真能打的成员**；旧「绩效横评」保留（自报、区间不一）。
- **`log.md` 新增 op** `normalize`：`## [YYYY-MM-DD] normalize | <n> 策略 @TRAIN | pass <a> / fail <b> / incompat <c>`。
  op 全集：`ingest` / `skip-dup` / `concept` / `query` / `lint` / `merge` / `experiment` / **`normalize`**。

### 11.4 运行时预算与安全（JoinQuant 计费现实）

JoinQuant 对回测**计时收费**，直接约束归一化的节奏：
- **每日免费 60 分钟**回测运行时长（每日重置）；超出部分**每 30 分钟扣 2 积分**，**积分为负时才无法新建回测**（超免费但积分为正仍可跑，只是花积分）。
- 用量直接查 API：`GET /algorithm/index/statistics` → `{data:{duration:{used,free}, running:[{id,name,usedSec}]}}`。
- **并发上限 2**（`编译失败:当前并行编译或回测数量最多2个`）。
- ⚠ **回测一经开启即运行至结束（最长 3 天），即使前端离开也在服务器端继续跑、并在结束时计入 `used`**。

**成本控制 = 事前用量闸门（不是取消）**。取消一个运行中的回测既脆弱又易失败，且失败会让慢回测跑到底、全额计费——这正是早期烧积分的根因。故新策略：
- **事前闸门**：每个回测开跑前查 `used`；`used ≥ USAGE_LIMIT`（`--usage-limit`，默认 55）就**不再新建**回测（子进程打印 `USAGE-STOP`，`strategy-normalize.js` 据此停批）。因批次**串行**，`used` 在每次检查时都是最新，无滞后。
- **运行中不早停**：让回测跑到 `完成/失败`，其时长计费（已接受）。最坏超支 = 最后一个刚好卡在闸门下启动的回测的时长。
- **仅保留安全网**：`MAX_POLL_MS`（默认 45 分钟）——只有**真卡死**的回测才在此调**取消 API** 兜底，防止阻塞整批；正常慢回测远早于此结束。
- **取消 API（关键）**：`#cancel-daily-backtest-button` 只弹「确实要取消?」确认框，点它**不会取消**（早期孤儿的根因）。真正的取消是 `Cy.ajax("/algorithm/index/cancel",{data:"backtestId="+backtestId})`——即带 `X-Requested-With: XMLHttpRequest` 头请求 `/algorithm/index/cancel`，`backtestId` 取编辑页隐藏输入 `#backtestId`。`cancelBacktest()` 已直接调此 API。
- **并发上限检测**：`编译运行` 后读编辑页 `编译失败…并行…最多` toast → `rate-limited`，退避 45s 后重试（不烧该策略）。**熔断**：连续 6 次失败即停（`process.exit(2)`），可续跑。

**按日预算跑法**（用量闸门自动控成本，可花积分换吞吐）：
```bash
# 例：小市值概念，日用量上限 240 分钟（免费60 + ~180 积分时长）
node utils/strategy-normalize.js --window train --concept 小市值因子 --usage-limit 240
```
`--concept <名>` 按 wiki 概念挑成员；`--usage-limit N` 设日用量上限（默认 55，仅免费额度内）；`--limit N` 限批量条数；账本可续跑。

### 11.5 与 autoresearch 的关系（起点契约）
- 归一化基线回答「**起点**在哪」：过门槛（gate ✅）的策略/因子组合是 autoresearch 变异的高价值起点；
  全员 DQ 的概念则提示该方向在此区间不成立。
- **autoresearch 的 `<tag>-000` baseline 必须是一个已归一化的过门槛策略**（从各概念页「归一化绩效横评」挑 gate ✅ 者），
  而**不是**裸 `strategy_template.py`（裸最小市值月度轮动在归一化 TRAIN 上即 DQ，不宜作起点）。做法：
  取该策略 `strategies/<file>.py` 源码 + `strategy-normalize.js` 的冻结成本 `OVERRIDE`（零滑点/PerTrade），
  存为 `research/candidates/<tag>-000.py`；其 TRAIN objective 应≈ 该策略页 `normalized:` 值。此后小步变异，朝赢家配方靠拢。
- 归一化用 **TRAIN**（与迭代区间一致），故它是**先验/特征**：迭代在 TRAIN 上进行本就用它，
  不构成对 VAL 的泄漏——VAL 仍只对定稿版跑一次（§8），2025+ OOS 永不触碰。
- **预算一致**：autoresearch 与归一化共用同一 JQ 计费现实（§11.4）——循环受 `--usage-limit` 约束，
  `used ≥ limit` 即停、等次日重置，不为「跑满循环」烧积分。
