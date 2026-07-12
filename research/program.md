# research/program.md — 自主策略研究团队（4 智能体）

本文件是研究循环的 **团队编排指令**（类比 Karpathy `autoresearch` 的 `program.md`，但本项目是**四智能体团队**，不是单 agent 循环）。
人类只编辑本文件与 `research/harness.md`；团队据此**自主**生成想法、变异策略、跑回测、记账、回填知识库。
权威规则见 `docs/research-schema.md`（冲突以它为准）与 `research/harness.md`（评测台冻结，只读）。

> **为什么是团队**：把「想法生成 / 想法筛选 / 脚本+回测 / 记账」拆成四个各司其职的角色，
> 用**严格窗口协议**（`harness.md` §1）防过拟合：迭代只在 TRAIN，定稿才碰 VAL，2025+ OOS 永不触碰。

---

## 必读（每次开始前）

1. `docs/research-schema.md` —— 结构与规则（**权威**）。
2. `research/harness.md` —— 冻结评测台（窗口协议、objective、门槛、OOS 硬阻断）。**只读**。
3. `docs/wiki-schema.md` §2 / §2.1 —— 受控概念与因子词表（变异空间边界）。
4. `wiki/index.md` 及相关 `wiki/concepts/*.md` —— 想法来源（尤其各概念页「归一化横评」与「待研究」）。

---

## 团队与共享状态

**四个智能体**（角色定义见 `.claude/agents/autoresearch-*.md`）：

| # | Agent | 角色 | 只读/可写 |
|---|---|---|---|
| **1** | `ideator`（点子官） | 通读 KB + 实验日志，产出**带推理**的新策略/改进想法；接收 TRAIN 结果，决定「继续迭代 / 定稿 / 放弃」 | 读 wiki+results；写 ideas-queue（提议） |
| **2** | `critic`（筛选官） | 判断想法是否**成立**，成立则入**排名队列**；出队最有希望的想法交给 Agent 3 | 读 wiki；读写 `research/ideas-queue.json` |
| **3** | `engineer`（工程师，**封闭环境**） | 生成策略 `.py`、跑回测、调试到有效结果；**严格服从 harness**；按想法类型路由结果 | 写 `research/candidates/`；只能用回测执行器 |
| **4** | `recorder`（记账官） | 仅当拿到 **VAL 结果**时触发：写实验日志/结果、**归档策略到 `validated_strategies/`**、更新 KB，然后交回 Agent 1 开下一轮 | 写 `research/results.tsv`、`validated_strategies/`、`wiki/**` |

**共享状态（磁盘为真相源，非仅靠消息 → 可断点续跑）**：
- `research/loop-state.json` —— **断点检查点**：每次 agent 交接后由编排者**原子写入**，记录「上次停在哪」。见下「断点续跑」。
- `research/ideas-queue.json` —— Agent 2 维护的**排名想法队列**。每项：
  `{ id, title, hypothesis, reasoning, sourceRefs:[...], baseExpId|null, rank, status: queued|active|done|dropped }`。
- `research/candidates/<expId>.py` —— Agent 3 的策略脚本（`expId = <tag>-<NNN>` 递增）。
- `research/results.tsv` —— Agent 4 记账（**git 不跟踪**）。列见 §记账。
- `wiki/experiments/<expId>.md`、`wiki/log.md`、`wiki/concepts/*.md` —— Agent 4 回填。

### 断点续跑（resume after interruption）

编排者在**每次 agent 交接后**把当前进度原子写入 `research/loop-state.json`（git 不跟踪），字段：

```json
{
  "epoch": 2,
  "branch": "research/<tag>",
  "phase": "ideating | filtering | engineering-train | deciding | engineering-val | recording",
  "activeAgent": "ideator | critic | engineer | recorder",
  "activeIdeaId": "idea-12 | null",
  "activeExpId": "<tag>-007 | null",
  "iterationStep": 3,
  "iteratingBest": { "expId": "<tag>-006", "trainObjective": 1.47 },
  "lastAction": "engineer 报 <tag>-007 TRAIN objective=1.47 gate=pass",
  "nextAction": "ideator 判 继续迭代 vs 定稿",
  "updatedAt": "<ISO 时间>"
}
```

**恢复时**（会话被打断/额度重置/Chrome 重连后）：编排者先读 `loop-state.json` + `ideas-queue.json`（队列与已测/待测想法）+ `results.tsv`（已定稿）+ git（当前 candidate），据 `phase`/`nextAction` **从上次断点继续**，不重跑已完成的回测、不重复已测想法。若 `loop-state.json` 不存在 = 全新纪元，从 Setup 开始。
- 写 `loop-state.json` 用「先写临时文件再 rename」原子替换，避免半写。
- `ideas-queue.json` 里 `status` 已区分：`queued`=待测、`active`=在测、`done`=已定稿、`dropped`=已放弃——与 `loop-state.json` 互补（一个记队列、一个记当前阶段）。

---

## Setup（开一个新研究纪元）

与人类确认后：

1. **定 run tag**、建分支 `research/<tag>`（从 master，必须不存在=全新纪元）。
2. **确认评测台 + 登录 + 预算**：
   - `harness.md` epoch 2 协议已冻结（TRAIN 选择 / VAL 定稿 / OOS 禁用）；只读。
   - CDP Chrome 在跑；**登录/预算用 statistics API 查**：`curl -s localhost:9225/json/version` 通 + `node utils/jq-budget.js` 返回 `used/free`。
   - **预算**：JQ 每日免费 60 分钟、超出烧积分。定 `JQ_USAGE_LIMIT`（默认 55）。
3. **初始化**：`research/ideas-queue.json`=`[]`；`research/results.tsv` 写表头（§记账）；`research/loop-state.json` 写初始检查点（`phase: ideating`）。（若续跑：这些已存在，读 `loop-state.json` 从断点继续，跳过本步。）
4. **选 baseline**：从 `wiki/concepts/*.md` 「归一化横评」挑一个 **gate ✅** 的强基线做 `<tag>-000`
   （源码 + `utils/strategy-normalize.js` 的冻结成本 `OVERRIDE`），Agent 3 在 **TRAIN** 上跑一次确立基准线。
5. **确认即开跑**。

---

## 主循环（状态机）——**只在用户明确说「停」时才停**

```
         ┌─────────────────────────────────────────────────────────────────────┐
         │                                                                       │
   ┌───► Agent 1 ideator ──(新想法+推理)──► Agent 2 critic                       │
   │      ▲   ▲                               │ 成立 → 入排名队列                 │
   │      │   │                               │ 出队最优想法                      │
   │(放弃:无TRAIN改进)                         │ (队列空 → 退回 Agent 1 重新产想法) │
   │      │   │                               ▼                                  │
   │      │   └──── TRAIN 结果 ◀──── Agent 3 engineer（封闭环境）                 │
   │      │            (Type-1 迭代 → --window train)                            │
   │  Agent 1 判定：继续调参(→A3 TRAIN) / 定稿 / 放弃                            │
   │      │                                                                      │
   │      └── 定稿 ──► Agent 3（Type-2 → --window val）──► Agent 4 recorder ──────┘
   │                                                         (记账+更新KB, 找A1要日志细节)
   └─────────────────────────────── 下一轮 ◀────────────────────────────────────
                          2025+ OOS：任何 agent 永不触碰（代码硬阻断）
```

**逐步说明**：

1. **Agent 1 产想法**：读最新 KB + `results.tsv`/实验页，产出一个**带推理**的想法（新策略或对现有的改进），推理须有据（逻辑或既往回测事实）。交 Agent 2。
2. **Agent 2 筛选/排队**：
   - 想法**成立** → 按预期收益/新颖度**排名入队** `ideas-queue.json`。
   - 无论成立与否，只要**队列非空** → 出队 `rank` 最高者，标 `active`，交 Agent 3（Type-1 迭代）。
   - 想法**不成立且队列空** → 退回 Agent 1，说明「不成立」，Agent 1 重新产想法。
3. **Agent 3 实现+回测（封闭环境）**：把 `active` 想法写成 `research/candidates/<expId>.py`（从 `baseExpId` 或 baseline 小步变异，只用受控词表内因子），跑回测、调试到有效 `SUMMARY`：
   - **Type-1（迭代中，未定稿）** → `--window train` → 把 TRAIN `objective/sharpe/gate` 报回 **Agent 1**。
   - **Type-2（Agent 1 已定稿）** → `--window val` → 把 VAL 结果报给 **Agent 4**。
   - **绝不** `--window holdout` 或任何 2025+ 区间（执行器会 `OOS-BLOCKED` 抛错）。
4. **Agent 1 判 TRAIN 结果**（Type-1 回来后）：
   - **正向改进**（`gate(TRAIN)` 且 `objective(TRAIN) > 当前定稿中最优`）→ 推进为新的迭代最优，且**判断是否已「定稿」**：*已迭代充分、TRAIN 上取得正向改进、想不出更多有价值变异* → **定稿**，把该版本交 Agent 3 跑 Type-2（VAL）。否则**继续调参**：产下一个小步变异（回 Agent 3 Type-1）。
   - **无改进**（DQ 或不高于当前）→ 记一次失败迭代；若这个想法**多次变异仍无正向改进** → **放弃该想法**，报 Agent 2 取队列下一个（队列空则回 Agent 1 产新想法）。
5. **Agent 4 记账**（仅 VAL 结果触发）：写 `results.tsv` 行 + `wiki/experiments/<expId>.md` + `wiki/log.md`，回填相关 `wiki/concepts/*.md`（向 Agent 1 要假设/推理/迭代轨迹细节），并**把定稿策略归档到 `validated_strategies/<expId>.py`**（拷贝 candidate + 带指标头注；见 §记账）。完成后交回 Agent 1 开下一轮。

---

## 红线与约束（`research-schema.md` §10 / `harness.md`）

- **严格窗口**：迭代只 TRAIN、定稿才 VAL、**2025+ 永不碰**（代码硬阻断，agent 绝不设 `JQ_ALLOW_OOS`）。
- **评测台冻结**：objective、门槛 2.5、窗口区间、费率滑点、执行器窗口参数——全部只读，改动即新纪元。
- **封闭环境**：Agent 3 只能通过 `node utils/strategy-post-backtest.js ... --window <train|val>` 回测，不得改 harness、不得引入受控词表外的新因子/概念。
- **预算例外**（现实约束）：JQ 每日免费 60 分钟、超出烧积分、并发上限 2、CDP 会话可能失效。当 `used ≥ JQ_USAGE_LIMIT`、积分不足、或会话失效时——**停在干净 git 状态**，简报当前状态 + 队列剩余，告知人类「等次日重置/续额度/续 session」。这是**暂停按天分批**，不是「停止」——恢复后从队列与当前定稿中最优继续。
- **停止条件**：**只有用户明确说「停」**，团队才结束。否则持续跑：没想法了就想得更深（重读概念页「待研究」/「归一化横评」强弱对照、跨概念拼装）。
- **真实性红线**：零滑点高估必标 ⚠；raw 不可变；受控命名；概念页只追加不覆盖、冲突只标记。

---

## 记账（Agent 4，每个**定稿**策略一行）

`research/results.tsv` 列（TAB 分隔，git 不跟踪）：

```
expId  commit  ideaId  baseExpId  train_objective  val_objective  sharpe_val  gate_val  status  description
```

- 迭代中的 Type-1 TRAIN 结果**不单独占行**，浓缩进定稿行的 `train_objective` 与实验页的「迭代轨迹」。
- `status`：`recorded`（定稿并记账）/ `val-dq`（定稿但 VAL 未过门槛，仍记账并标注）/ `crash`。
- 实验页 `wiki/experiments/<expId>.md` 按 `research-schema.md` §6 模板，含：假设、推理、迭代轨迹（各 TRAIN 步）、TRAIN 与 VAL 结果、`confirmed`、`flags`、回填指针。
- **归档策略**：把 `research/candidates/<expId>.py` 拷贝到 `validated_strategies/<expId>.py`（目录不存在则建），文件头加注释：`expId / ideaId / baseExpId / train_objective / val_objective / sharpe_val / gate_val(pass|fail) / ranAt`。**每个拿到 VAL 结果的定稿策略都归档**（`gate_val` 标 pass/fail——这里收「过了验证流程」的成品，不只是过门槛者）。此目录**git 跟踪**（是流水线的产物货架，区别于 transient 的 `results.tsv`/`ideas-queue.json`/`loop-state.json`）。

---

## 完成/交接后

- 简报：本纪元处理了多少想法、定稿几个、当前最优 `objective(TRAIN)` 与其 `objective(VAL)`、发现的规律与回填落点、多少放弃/crash、队列剩余。
- 不 `git commit` wiki 改动或 `results.tsv`，除非人类明确要求。
