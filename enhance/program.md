# enhance/program.md — 自主策略增强团队（4 智能体，家族级）

本文件是**增强循环**的 **团队编排指令**（auto-study `study/program.md` 的姊妹篇；四智能体团队，不是单 agent 循环）。
人类只编辑本文件与 `harness/harness.md`；团队据此**自主**在一个策略家族上生成改进想法、变异策略、跑回测、记账、把结果**写回家族页**。
权威规则见 `docs/enhance-schema.md`（冲突以它为准）与 `harness/harness.md`（评测台冻结，只读）。

> **家族级增强**：目标是**提升一个策略家族**（`wiki/families/<family>.md`）。点子官有**三种取法**：
> 1. **族内改进**——从家族 §4 待研究 + §2 变体 + §3 横评 找可优化点，在血统内小步变异；
> 2. **跨族借鉴**——扫其他家族页，把在别处奏效的元素（如某家族的降回撤机器 / 择时闸 / 滤波器）移植进来；
> 3. **组合新族**——把 ≥2 个家族的要素拼成一个**新家族**（记账时登记 §2.2 词表 + 建家族页）。
> 用**严格窗口协议**（`harness.md` §1）防过拟合：迭代只在 TRAIN，定稿才碰 VAL，2025+ OOS 永不触碰。

---

## 必读（每次开始前）

1. `docs/enhance-schema.md` —— 结构与规则（**权威**）。
2. `harness/harness.md` —— 冻结评测台（窗口协议、objective、门槛、OOS 硬阻断）。**只读**。
3. `docs/wiki-schema.md` §2 / §2.1 —— 受控概念与因子词表（变异空间边界）。
4. **目标家族页** `wiki/families/<family>.md`（§2 变体 / §3 横评 / §4 待研究）+ **其他家族页**（跨族借鉴来源）+ 相关 `wiki/concepts/*.md`（因子/机制词表与横评）。

---

## 团队与共享状态

**四个智能体**（角色定义见 `.claude/agents/autoenhance-*.md`），以**临时 subagent** 方式运行：

> **临时 subagent 模型**（本项目的选择）：编排者（`/run-enhance` 主会话）在状态机的**每一步**用 `Agent` 工具**新生成**对应角色的一次性 subagent（不带 `name`、不常驻），给它**当步的具体任务 + 所需最小上下文**；subagent 干完这一件事、**把结果返回给编排者**即终止。subagent **互不寻址、不常驻**——所有路由**经编排者居中**（星型）：`ideator →(想法) critic →(出队想法) engineer →(TRAIN 结果) ideator →(定稿) engineer →(VAL 结果) recorder →(交回) ideator …`。
> - **续跑干净**：subagent 本就一次性，`--resume` 恢复的是**编排者会话**（§断点续跑）；**没有 teammate 需要重生成、不会「找不到 teammate」**。上下文靠编排者会话 + 磁盘账本（git / `results.tsv` / `ideas-queue.json`）；transcript 与磁盘冲突时**以磁盘为准**。
> - 代价：每次生成的 subagent 会重读它需要的最小上下文（如点子官读相关概念页）——换来续跑干净、路由可靠、无实验性 teams 依赖。
> - **不需要** `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`；不使用 `SendMessage`/常驻 teammate。

| # | Agent | 角色 | 只读/可写 |
|---|---|---|---|
| **1** | `ideator`（点子官） | 读目标家族页 + KB，产出**带推理**的改进想法：**族内改进 / 跨族借鉴 / 组合新族**；接收 TRAIN 结果，决定「继续迭代 / 定稿 / 放弃」 | 读 wiki+results；写 ideas-queue（提议） |
| **2** | `critic`（筛选官） | 判断想法是否**成立**（受控词表内、非族内重复、跨族借鉴有据、新族非已有家族的重复）；成立入**排名队列**；出队最优交 Agent 3 | 读 wiki；读写 `enhance/ideas-queue.json` |
| **3** | `engineer`（工程师，**封闭环境**） | 生成策略 `.py`、跑回测、调试到有效结果；**严格服从 harness**；按想法类型路由结果 | 写 `enhance/candidates/`；只能用回测执行器 |
| **4** | `recorder`（记账官） | 仅当拿到 **VAL 结果**时触发：把结果写成目标家族页 **§2 新变体**（来源 `enhance-<expId>`）、记 `results.tsv`、**归档到 `validated_strategies/`**；**组合新族**则登记 §2.2 + 建家族页；交回 Agent 1 | 写家族页 §2、`enhance/results.tsv`、`validated_strategies/`、`wiki/**` |

**共享状态**：
- `enhance/loop-state.json` —— **可选**的轻量进度快照（当前最优/活跃想法/下一步），供人类查看；**不是续跑的必需品**（续跑靠会话恢复，见下「断点续跑」），不强制每步写。
- `enhance/ideas-queue.json` —— Agent 2 维护的**排名想法队列**。每项：
  `{ id, title, hypothesis, reasoning, sourceRefs:[...], baseExpId|null, rank, status: queued|active|done|dropped }`。
- `enhance/candidates/<expId>.py` —— Agent 3 的策略脚本（`expId = <tag>-<NNN>` 递增）。
- `enhance/results.tsv` —— Agent 4 记账（**git 不跟踪**）。列见 §记账。
- `wiki/experiments/<expId>.md`、`wiki/log.md`、`wiki/concepts/*.md` —— Agent 4 回填。

### 断点续跑（resume after interruption）——**主要靠会话恢复**

推荐跑法：人类用 `scripts/autoenhance-interactive.sh` 在**交互式** claude 会话里跑本循环（脚本把会话 id 钉进 `data/autoenhance-session.txt`，可观察、可打断）。额度用尽会话停下后：

- 每小时的 launchd cron（`scripts/autoenhance-loop.sh`）用 **`claude -p --resume <该会话 id>`** 恢复**同一会话**——**编排者**的上下文都在，从上次断点直接续跑（临时 subagent 本就一次性，**没有 teammate 需要重生成**，编排者按需再新生成即可）；额度仍不足时 `--resume` 秒退，下次 fire 在额度重置后再续。
- cron 用 **pgrep 判断是否有活着的 `claude` 进程正持有该会话 id**（交互 TUI 或上一 fire）：有则跳过（无法恢复被占用的会话）；无则可恢复，与 transcript 新旧无关。**交接规则：要让 cron 接手，必须先关闭交互会话**（退出 TUI）——开着（哪怕空闲）就一直占用、cron 会正确让路。人类回来再跑 `autoenhance-interactive.sh` 即重开同一会话（自动续跑），看到 cron 期间的全部进展。

因此**续跑不依赖把每步写进 `loop-state.json`**——上下文就在会话里。`loop-state.json` / `ideas-queue.json` 仅作**人类可查的进度快照**（可选）；只有当你要**手动冷启动一个全新会话**、又想接着旧进度时，才需要它们（那时读 `ideas-queue.json` 的 `status`=queued/active/done/dropped + `results.tsv` 已定稿 + git 当前 candidate 来重建上下文）。

---

## Setup（开一个新研究纪元）

与人类确认后：

1. **选目标家族** `<family>`（用户指定，如 `五福闹新春`）+ 定 run tag。
   ⚠ **分支**：本条原文要求新建 `enhance/<tag>` 分支。现已改为**任意分支**（`auto*-loop.sh` 的分支门只要求
   `data/auto<stage>-session.txt` 的 pin 分支 == 当前 HEAD）。日常 cron 的 pin 在 `main` 上，另开分支会让
   每日流水线找不到会话而空转——**除非人类明确要求，否则留在当前分支**。
2. **确认评测台 + 登录 + 预算**：
   - `harness.md` 协议已冻结（TRAIN 选择 / VAL 定稿 / OOS 禁用）；只读。
     ⚠ **纪元号不要写死在文档里**——查 `node utils/harness-config.js`（本条原文写「epoch 2」，写下时是对的，
     此后已被取代四次）。结果永远归属于产生它的纪元；跨纪元的数字不可比。
   - CDP Chrome 在跑；**登录/预算用 statistics API 查**：`curl -s localhost:9225/json/version` 通 + `node utils/jq-budget.js` 返回 `used/free`。
   - **预算**：`node utils/jq-budget.js` 报当日 `used/free`——**以它为准，不要用文档里的数字**
     （本条原文写「每日免费 60 分钟」，账号开了 VIP 后是 180）。`--usage-limit` 由调用方传入。
3. **初始化**：`enhance/ideas-queue.json` 置为本轮想法队列。
   ⚠ `enhance/results.tsv` **不再重写表头**：它已是 tracked 的跨家族账本，清空会抹掉前几轮的定稿记录
   （本条原文写于该文件还是 gitignore 的临时件时）。只追加。续跑不靠这些文件而靠**会话恢复**（见「断点续跑」）。
4. **定 baseline**：目标家族页的 `bestVariant`（族内改进时）或拟组合的各家族最优（组合新族时）做 `<tag>-000`
   （源码 + `utils/strategy-normalize.js` 的冻结成本 `OVERRIDE`），Agent 3 在 **TRAIN** 上跑一次确立基准线——**增强要超过它**。
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

1. **Agent 1 产想法**：读目标家族页 + KB + `results.tsv`，产出一个**带推理**的想法——**三取法之一**：**族内改进**（§4 待研究 / §2 变体的可优化点）、**跨族借鉴**（把其他家族页里奏效的元素移植进来，引用来源家族+study 溯源）、**组合新族**（≥2 家族拼装）。推理须有据（逻辑或既往回测/study 事实）。交 Agent 2。
2. **Agent 2 筛选/排队**：
   - 想法**成立** → 按预期收益/新颖度**排名入队** `ideas-queue.json`。
   - 无论成立与否，只要**队列非空** → 出队 `rank` 最高者，标 `active`，交 Agent 3（Type-1 迭代）。
   - 想法**不成立且队列空** → 退回 Agent 1，说明「不成立」，Agent 1 重新产想法。
3. **Agent 3 实现+回测（封闭环境）**：把 `active` 想法写成 `enhance/candidates/<expId>.py`（从 `baseExpId` 或 baseline 小步变异，只用受控词表内因子），跑回测、调试到有效 `SUMMARY`：
   - **Type-1（迭代中，未定稿）** → `--window train` → 把 TRAIN `objective/sharpe/gate` 报回 **Agent 1**。
   - **Type-2（Agent 1 已定稿）** → `--window val` → 把 VAL 结果报给 **Agent 4**。
   - **绝不** `--window holdout` 或任何 2025+ 区间（执行器会 `OOS-BLOCKED` 抛错）。
   - **前台阻塞跑回测**：发一条命令等它返回再读 `SUMMARY`，**绝不**后台跑（`run_in_background`）+ 等完成通知——headless `claude -p` 无人值守跑中该通知不会重新唤起会话，循环会卡住。
4. **Agent 1 判 TRAIN 结果**（Type-1 回来后）：
   - **正向改进**（`gate(TRAIN)` 且 `objective(TRAIN) > 当前定稿中最优`）→ 推进为新的迭代最优，且**判断是否已「定稿」**：*已迭代充分、TRAIN 上取得正向改进、想不出更多有价值变异* → **定稿**，把该版本交 Agent 3 跑 Type-2（VAL）。否则**继续调参**：产下一个小步变异（回 Agent 3 Type-1）。
   - **无改进**（DQ 或不高于当前）→ 记一次失败迭代；若这个想法**多次变异仍无正向改进** → **放弃该想法**，报 Agent 2 取队列下一个（队列空则回 Agent 1 产新想法）。
5. **Agent 4 记账**（仅 VAL 结果触发）：**把定稿策略写成目标家族页 §2 的新变体行**（改动 / 来源 `enhance-<expId>` / Δ vs 基线 / 结论）；写 `results.tsv` + `wiki/log.md`；回填相关 `wiki/concepts/*.md`（向 Agent 1 要假设/推理/迭代轨迹）；**归档到 `validated_strategies/<expId>.py`**（拷贝 candidate + 带指标头注）。**若这是「组合新族」**：先在 `wiki-schema.md` §2.2 登记新家族名，建 `wiki/families/<new>.md`（§1 由人/后续 study 补），该定稿即其首个变体，并给 candidate 策略页写 `family: <new>`。完成后交回 Agent 1。

---

## 红线与约束（`enhance-schema.md` §10 / `harness.md`）

- **严格窗口**：迭代只 TRAIN、定稿才 VAL、**2025+ 永不碰**（代码硬阻断，agent 绝不设 `JQ_ALLOW_OOS`）。
- **评测台冻结**：objective、门槛、窗口区间、费率滑点、执行器窗口参数——全部只读，改动即新纪元。
  ⚠ **门槛查 `harness.stageGate(stage, sharpe)`，不要写死**（本条原文写「2.5」；epoch 5 起 normalize/study/
  enhance/validate 是 1.5，type 整合是 2.0）。
- **封闭环境**：Agent 3 只能通过 `node utils/strategy-post-backtest.js ... --window <train|val>` 回测，不得改 harness、不得引入受控词表外的新因子/概念。
- **预算例外**（现实约束）：每日额度见 `jq-budget.js`、超出烧积分、并发上限 2、CDP 会话可能失效。
  ⚠ **并发回测会让结果张冠李戴**：完成信号读的是账号级 running 计数，两个 engineer 同时跑曾对不同策略
  返回逐字节相同的指标。`strategy-post-backtest.js` 现在会直接拒跑（`CONCURRENT-STOP`）——**一次只跑一个**。当 `used ≥ JQ_USAGE_LIMIT`、积分不足、或会话失效时——**停在干净 git 状态**，简报当前状态 + 队列剩余，告知人类「等次日重置/续额度/续 session」。这是**暂停按天分批**，不是「停止」——恢复后从队列与当前定稿中最优继续。
- **停止条件**：**只有用户明确说「停」**，团队才结束。否则持续跑：没想法了就想得更深（重读概念页「待研究」/「归一化横评」强弱对照、跨概念拼装）。
- **真实性红线**：零滑点高估必标 ⚠；raw 不可变；受控命名；概念页只追加不覆盖、冲突只标记。

---

## 记账（Agent 4，每个**定稿**策略一行）

`enhance/results.tsv` 列（TAB 分隔，git 不跟踪）：

```
expId  commit  ideaId  baseExpId  train_objective  val_objective  sharpe_val  gate_val  status  description
```

- 迭代中的 Type-1 TRAIN 结果**不单独占行**，浓缩进定稿行的 `train_objective` 与实验页的「迭代轨迹」。
- `status`：`recorded`（定稿并记账）/ `val-dq`（定稿但 VAL 未过门槛，仍记账并标注）/ `crash`。
- **主记录 = 家族页 §2 变体行**（改动 / 来源 `enhance-<expId>` / Δ vs 基线 / 结论）。完整假设·推理·迭代轨迹·TRAIN+VAL·`flags` 进实验页 `wiki/experiments/<expId>.md`（`enhance-schema.md` §6）作详情附页；既有 `wiki/experiments/*.md` 为归档，不再是主记录。
- **归档策略**：把 `enhance/candidates/<expId>.py` 拷贝到 `validated_strategies/<expId>.py`（目录不存在则建），文件头加注释：`expId / ideaId / baseExpId / train_objective / val_objective / sharpe_val / gate_val(pass|fail) / ranAt`。**每个拿到 VAL 结果的定稿策略都归档**（`gate_val` 标 pass/fail——这里收「过了验证流程」的成品，不只是过门槛者）。此目录**git 跟踪**（是流水线的产物货架，区别于 transient 的 `results.tsv`/`ideas-queue.json`/`loop-state.json`）。

---

## 完成/交接后

- 简报：本纪元处理了多少想法、定稿几个、当前最优 `objective(TRAIN)` 与其 `objective(VAL)`、发现的规律与回填落点、多少放弃/crash、队列剩余。
- 不 `git commit` wiki 改动或 `results.tsv`，除非人类明确要求。
