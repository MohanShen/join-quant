# study/program.md — 自动策略解剖团队（4 智能体，家族级）

本文件是解剖循环的**团队编排指令**（auto-enhance `enhance/program.md` 的姊妹篇）。
人类只编辑本文件与 `harness/harness.md`；团队据此**自主**提问、跑实验、记发现、**写回家族页**、反哺 KB。
权威规则见 `docs/study-schema.md`（冲突以它为准）与 `harness/harness.md`（评测台冻结，只读）。

> **目标不是优化指标，而是理解一个策略家族**：基类为什么有效、各变体的改动**为何**导致其结果变化、参数敏感性、regime 依赖、失效模式与机理。
> **家族级**：解剖对象是**一个策略家族**（`wiki/families/<family>.md`），不是单个策略。家族页 §2 已累积一组**变体**（来自 normalize 的原始变体 + 过往 study/enhance 实验）；本流程把每个变体当作「同一基类上的一处改动」，追问**这处改动为何产生这个结果**——正是过去对单策略做归因的做法，现在放到家族的变体维度上递归。
> **批量模式**：遍历 `study/manifest.json` 里**所有家族**，逐个做完整解剖、把结论写回家族页（§2 变体 + §6 研究问答），标 `done`，**不到全部完成（或用户说停）不退出**。外层循环（遍历家族）+ 内层循环（对一个家族的 4-agent 解剖）。

---

## 必读（每次开始前）

1. `docs/study-schema.md` —— 结构与规则（**权威**）。
2. `harness/harness.md` —— 冻结评测台（成本/滑点/真实性过滤；窗口 2022–2024，2025 OOS 硬阻断）。**只读**。
3. **目标家族页** `wiki/families/<family>.md`（§1 基类、§2 变体、§3 横评、§4 待研究、§5 沿革）+ 其 `base:`/成员策略的 `wiki/strategies/<...>.md` 页 + 相关 `wiki/concepts/*.md`。
4. `docs/wiki-schema.md` §2.1/§2.2 —— 受控因子/家族词表（描述组件与家族时用统一命名）。

---

## 团队与共享状态

**四个智能体**（角色定义见 `.claude/agents/autostudy-*.md`），以**临时 subagent** 方式运行：

> **临时 subagent 模型**：编排者（`/run-study` 主会话）在状态机的**每一步**用 `Agent` 工具**新生成**对应角色的一次性 subagent，给它当步任务 + 最小上下文；subagent 干完返回结果即终止，**不常驻、不互相寻址，全部路由经编排者居中**（星型）。`--resume` 后无 teammate 需重生成——编排者上下文已在，按需再新生成；transcript 与磁盘冲突**以磁盘为准**。不需要 `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`。

| # | Agent | 角色 | 读/写 |
|---|---|---|---|
| **1** | `questioner`（提问官） | 读家族页 + KB + 已有发现，产出**带假设+价值+测法**的解剖问题：基类「为什么有效」+ **每个变体「这处改动为何得到这个 Δ」**；接收实验结果 → 提追问 | 读家族页/wiki/findings；提问 |
| **2** | `prioritizer`（排序官） | 判问题**是否可证伪/可一实验回答**，按「洞察价值×可行×预算」排名入队；出队最有价值者交实验官 | 读写 `study/<family>/questions.json` |
| **3** | `experimenter`（实验官，**封闭环境**） | 造消融/改参变体或跑分区间/数据探针，跑回测调试到有效结果；返回**相对基类基线的 Δ** | 写 `study/<family>/variants/`；只经执行器 |
| **4** | `analyst`（分析官/报告员） | 把结果解读成**发现**、记 `findings.tsv`、**写回家族页 §2 变体表 + §6 研究问答**、反哺 KB，交回提问官 | 写 `findings.tsv`、`wiki/families/<family>.md` §2/§6、`wiki/concepts/**` |

**共享状态**：
- `study/manifest.json` —— **批量清单**：所有家族 + 每个的 `status`（pending|in-progress|done），按家族 `bestObjective` 强→弱排序（git 不跟踪）。外层循环的进度真相源。
- `study/<family>/questions.json` —— 排序问题队列（git 不跟踪，§schema 6）。
- `study/<family>/baseline.py` —— 家族**基类**（家族页 `base:`）源码快照 + 冻结成本 override（**不可变**，作 Δ 参照）。
- `study/<family>/variants/<qId>.py` —— 各实验变体（raw）。
- `study/<family>/findings.tsv` —— 发现账本（git 不跟踪，§schema 7）。
- **`wiki/families/<family>.md`** —— 解剖产物落地处：变体结果进 **§2**，问题→结论进 **§6 研究问答**（§schema 8）。§3 横评由 `wiki-family-build.js` 自动生成，勿手写。

### 断点续跑
推荐用交互式会话跑（`scripts/autostudy-interactive.sh` 的会话-钉住/`--resume`，或直接 `/run-study`）。续跑靠**会话恢复**——编排者上下文在，按需再新生成 subagent；`manifest.json`/`questions.json`/`findings.tsv`/家族页 git 为磁盘真相源。

---

## Setup（开批量解剖）

与人类确认后：

1. **建 manifest**：`study/manifest.json` 从 `wiki/families/*.md` 生成（`family / bestObjective / memberCount / status`，按 bestObjective 强→弱；不含单例桶「其他」）。建分支 `study/all`（从当前 HEAD）。
2. **确认评测台 + 登录 + 预算**：`harness/harness.md` 只读；`curl -s localhost:9225/json/version` 通 + `node utils/jq-budget.js` 出 `used/free`；定 `--usage-limit`。
3. **确认即开跑**（进入外层循环）。

---

## 外层循环（遍历所有家族）——**不到全部 `done` 或用户说停不退出**

1. 读 `study/manifest.json`，选**第一个 `status != done`** 的家族（强→弱序）；无则**全部完成**，收尾简报。
2. 标其 `status: in-progress`。
3. **该家族 Setup**：读 `wiki/families/<family>.md`；快照 `study/<family>/baseline.py` = 家族 `base:` 的 `sourceFile` 源码 + 冻结成本 `OVERRIDE`；跑一次基类基线（`--window train`）作 Δ 参照；建 `study/<family>/questions.json`=`[]`、`findings.tsv` 表头。§2 现有变体（来自 normalize）作为**待解释的对象**读入。
4. 跑**内层解剖循环**（下节）直到该家族问题穷尽 → analyst **收口写回家族页**。
5. 标其 `status: done`，回到 1 取下一个家族。
6. **预算/额度到顶**：停在干净状态（进度留磁盘），cron 续跑时从 manifest 的 `in-progress`/下一个 `pending` 接着做。

> **每家族适度深度**：覆盖「基类为何有效 + 每个 gate-pass 变体的改动归因 + 关键参数敏感性 + regime + 机理真实性」即可收口，**别在单个家族上钻牛角尖**——批量要推进。强家族（多个 gate-pass 变体）值得更深，全 DQ 家族重点答「为什么这条血统不行」。

---

## 内层循环（对一个家族的解剖，状态机）——问题穷尽即收口该家族

```
   ┌──► questioner ──(问题+假设+测法)──► prioritizer
   │      ▲                                │ 可证伪且有价值 → 入排名队列
   │      │                                │ 出队最有价值问题
   │  (追问: 据发现提下一个问题)             ▼
   │      │                          experimenter（封闭环境）
   │      │                            造变体/分区间/探针 → 跑回测 → 相对基类 Δ
   │      └────── 结果 ◀───────────────────┘
   │                          │
   │                          ▼
   └────── 下一轮 ◀──── analyst：解读成发现 → 记 findings.tsv → 写回家族页 §2/§6 → 反哺概念页
                        2025+ OOS：任何 agent 永不触碰（代码硬阻断）
```

**逐步**：
1. **questioner 提问**：读家族页 + KB + 已有 findings，产出一个**可一实验回答**的问题。两类核心问题：
   - **基类机理**：家族基类的哪个组件在贡献 alpha/控回撤（消融/隔离）。
   - **变体归因**（家族级新增核心）：§2 里某变体相对基类的改动（如「取消 13:10 狙击窗」「关闭 Laplace 滤波」「融合三马多池」）**为何**产生了它那个 Δ——用一个受控实验证实/证伪该因果链。
   带假设、为何值得问、怎么测。交 prioritizer。
2. **prioritizer 排序/出队**：判问题是否成立（可证伪、可行、非重复），成立入队；出队 `rank` 最高者交 experimenter；队列空则退回 questioner 再提。
3. **experimenter 跑实验（封闭）**：造 `study/<family>/variants/<qId>.py`（只改一处）或跑分区间/探针，回测调试到有效 SUMMARY，算**相对基类基线的 Δ**，把结果交 analyst。
4. **analyst 记账+写回**：把 Δ 解读成一句**发现**（含 confidence、⚠ flags），追加 `findings.tsv`；**写回家族页**——变体结果进 **§2 变体表**（改动/来源 study-`<qId>`/Δ/结论），问题→结论进 **§6 研究问答**；有跨策略价值则反哺概念页（§schema 9）。把发现交回 questioner 促发追问。
5. 回到 1。

**穷尽即收口该家族**：无更多有价值问题时，analyst 把家族页 §1「为什么有效」、§2 变体归因、§4 待研究刷新到位（§3 横评跑 `wiki-family-build.js` 重生成），把该家族标 `done`，**交回外层循环取下一个家族**（不停整个批量）。

---

## 回测命令（唯一执行器，封闭环境）

```bash
node utils/strategy-post-backtest.js study/<family>/variants/<qId>.py "<family>-<qId>" --window <train|val> --usage-limit <cap>
# 或分区间： --start 2022-01-01 --end 2022-12-31   （2025+ 会被 OOS-BLOCKED）
```
- **plain 形式**（无 `JQ_USAGE_LIMIT=` 前缀、无 `| tail`）以匹配允许清单、免逐条授权。
- **前台阻塞跑**：发一条命令、等它返回再读 `SUMMARY`；**绝不**后台跑（`run_in_background`）+ 等完成通知——headless `claude -p` 无人值守跑中该通知不会重新唤起会话，循环会卡在半路。
- 读末尾 10 列 `SUMMARY`（`harness.md` §5）；解剖关心的是 variant 相对家族基类基线的 Δ。

---

## 红线（见 `study-schema.md` §10）

- 评测台冻结、**2025+ OOS 绝不触碰**、`baseline.py` 快照不可变、**一次一处**（干净归因）、真实性红线（零滑点高估必标 ⚠）。
- **无选择压力**：不 keep/discard、不挑「最优变体」当产物；产物是**理解**（家族页 §1/§2/§6），不是新策略。启发出的可优化新策略 → 交 auto-enhance 另起。
- **家族页写回规则**：§2 变体表与 §6 研究问答**追加优先、不覆盖既有行**；§3 横评只由 `wiki-family-build.js` 生成勿手写；矛盾只标不裁决；受控命名（§2.2）。
- 不 `git commit` `wiki/` 或账本，除非人类明确要求。
- **工具卫生**：所有文件/JSON 操作**一律用 Read/Write/Edit 工具**（自动放行）；**绝不用 `node -e`/内联脚本或 shell 重定向（`>`,`>>`）**——无法进允许清单、触发逐条授权。查看用 Read/Grep/Glob 或单条简单 Bash，不用复合 Bash。
- **git 用分开的单条命令**：`git add <路径>` → `git commit -m "一行说明"` → `git push origin <分支>`，各自单独一条。**不要** `&&` 串联、**不要**用 `$(...)`/heredoc 写多行提交信息。
