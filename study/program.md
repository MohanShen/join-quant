# study/program.md — 自动策略解剖团队（4 智能体）

本文件是解剖循环的**团队编排指令**（auto-research `research/program.md` 的姊妹篇）。
人类只编辑本文件与 `research/harness.md`；团队据此**自主**提问、跑实验、记发现、写报告、反哺 KB。
权威规则见 `docs/study-schema.md`（冲突以它为准）与 `research/harness.md`（评测台冻结，只读）。

> **目标不是优化指标，而是理解策略**：各组件贡献、参数敏感性、regime 依赖、失效模式与机理。
> **批量模式**：遍历 `study/manifest.json` 里**所有归一化策略**，逐个做完整解剖、产出 `wiki/studies/<id>.md` 报告、标 `done`，**不到全部完成（或用户说停）不退出**。有外层循环（遍历策略）+ 内层循环（对一个策略的 4-agent 解剖）。

---

## 必读（每次开始前）

1. `docs/study-schema.md` —— 结构与规则（**权威**）。
2. `research/harness.md` —— 冻结评测台（成本/滑点/真实性过滤；窗口 2022–2024，2025 OOS 硬阻断）。**只读**。
3. 目标策略的源码 + 其 `wiki/strategies/<...>.md` 页 + 相关 `wiki/concepts/*.md`。
4. `docs/wiki-schema.md` §2.1 —— 受控因子词表（描述组件时用统一命名）。

---

## 团队与共享状态

**四个智能体**（角色定义见 `.claude/agents/autostudy-*.md`），以**临时 subagent** 方式运行（同 auto-research 的选择）：

> **临时 subagent 模型**：编排者（`/run-study` 主会话）在状态机的**每一步**用 `Agent` 工具**新生成**对应角色的一次性 subagent，给它当步任务 + 最小上下文；subagent 干完返回结果即终止，**不常驻、不互相寻址，全部路由经编排者居中**（星型）。`--resume` 后无 teammate 需重生成——编排者上下文已在，按需再新生成；transcript 与磁盘冲突**以磁盘为准**。不需要 `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`。

| # | Agent | 角色 | 读/写 |
|---|---|---|---|
| **1** | `questioner`（提问官） | 读 target + KB + 已有发现，产出**带假设+价值+测法**的解剖问题；接收实验结果 → 提追问 | 读 target/wiki/findings；提问 |
| **2** | `prioritizer`（排序官） | 判问题**是否可证伪/可一实验回答**，按「洞察价值×可行×预算」排名入队；出队最有价值者交实验官 | 读写 `study/<id>/questions.json` |
| **3** | `experimenter`（实验官，**封闭环境**） | 造消融/改参变体或跑分区间/数据探针，跑回测调试到有效结果；返回**相对基线的 Δ** | 写 `study/<id>/variants/`；只经执行器 |
| **4** | `analyst`（分析官/报告员） | 把结果解读成**发现**、记 `findings.tsv`、维护 `wiki/studies/<id>.md` 报告、反哺 KB，交回提问官 | 写 `findings.tsv`、`wiki/studies/`、`wiki/**` |

**共享状态**：
- `study/manifest.json` —— **批量清单**：所有归一化策略 + 每个的 `status`（pending|in-progress|done），按 objective 强→弱排序（git 不跟踪）。外层循环的进度真相源。
- `study/<id>/questions.json` —— 排序问题队列（git 不跟踪，§schema 6）。
- `study/<id>/target.py` —— 被解剖策略源码快照 + 冻结成本 override（**不可变**）。
- `study/<id>/variants/<qId>.py` —— 各实验变体（raw）。
- `study/<id>/findings.tsv` —— 发现账本（git 不跟踪，§schema 7）。
- `wiki/studies/<id>.md` —— 解剖报告（§schema 8）。

### 断点续跑
同 auto-research：推荐用交互式会话跑（可复用 `scripts/autoresearch-interactive.sh` 的会话-钉住/`--resume` 机制，或直接 `/run-study`）。续跑靠**会话恢复**——编排者上下文在，按需再新生成 subagent；`questions.json`/`findings.tsv`/git 为磁盘真相源。

---

## Setup（开批量解剖）

与人类确认后：

1. **建 manifest**：`study/manifest.json` 已由脚本从所有归一化 wiki 策略页生成（`id / sourceFile / objective / gate / status`，按 objective 强→弱）。不存在则重建（读 `wiki/strategies/*.md` 的 `normalized:` 块）。建分支 `study/all`（从当前 HEAD）。
2. **确认评测台 + 登录 + 预算**：`research/harness.md` 只读；`curl -s localhost:9225/json/version` 通 + `node utils/jq-budget.js` 出 `used/free`；定 `--usage-limit`。
3. **确认即开跑**（进入外层循环）。

---

## 外层循环（遍历所有归一化策略）——**不到全部 `done` 或用户说停不退出**

1. 读 `study/manifest.json`，选**第一个 `status != done`** 的策略（强→弱序）；无则**全部完成**，收尾简报。
2. 标其 `status: in-progress`。
3. **该策略 Setup**：快照 `study/<id>/target.py` = 其 `sourceFile` 源码 + 冻结成本 `OVERRIDE`（`strategy-normalize.js`；research/candidates 的已带则直接拷）；跑一次基线（`--window train`，必要时 `--window val`）作 Δ 参照；建 `study/<id>/questions.json`=`[]`、`findings.tsv` 表头、`wiki/studies/<id>.md` 空报告。
4. 跑**内层解剖循环**（下节）直到该策略问题穷尽 → analyst **定稿 `wiki/studies/<id>.md`**。
5. 标其 `status: done`，回到 1 取下一个。
6. **预算/额度到顶**：停在干净状态（当前策略进度留在磁盘），cron 续跑时从 manifest 的 `in-progress`/下一个 `pending` 接着做。

> **每策略适度深度**：覆盖四轴（主组件归因 + 关键参数敏感性 + regime + 机理真实性）即可定稿，**别在单个策略上钻牛角尖**——批量要推进。强策略（gate pass）值得更深，DQ 策略重点答「为什么不行」即可。

---

## 内层循环（对一个策略的解剖，状态机）——问题穷尽即定稿该策略

```
   ┌──► questioner ──(问题+假设+测法)──► prioritizer
   │      ▲                                │ 可证伪且有价值 → 入排名队列
   │      │                                │ 出队最有价值问题
   │  (追问: 据发现提下一个问题)             ▼
   │      │                          experimenter（封闭环境）
   │      │                            造变体/分区间/探针 → 跑回测 → 相对基线 Δ
   │      └────── 结果 ◀───────────────────┘
   │                          │
   │                          ▼
   └────── 下一轮 ◀──── analyst：解读成发现 → 记 findings.tsv → 更新报告 → 反哺 KB
                        2025+ OOS：任何 agent 永不触碰（代码硬阻断）
```

**逐步**：
1. **questioner 提问**：读 target + KB + 已有 findings，产出一个**可一实验回答**的问题（消融/敏感性/regime/隔离/探针之一），带假设、为何值得问、怎么测。交 prioritizer。
2. **prioritizer 排序/出队**：判问题是否成立（可证伪、可行、非重复），成立入队；出队 `rank` 最高者交 experimenter；队列空则退回 questioner 再提。
3. **experimenter 跑实验（封闭）**：造 `variants/<qId>.py`（只改一处）或跑分区间/探针，回测调试到有效 SUMMARY，算**相对基线的 Δ**，把结果交 analyst。
4. **analyst 记账+报告**：把 Δ 解读成一句**发现**（含 confidence、⚠ flags），追加 `findings.tsv`，更新 `wiki/studies/<id>.md` 对应小节（归因表/敏感性/regime/机理），有跨策略价值则反哺概念页（§schema 9）。把发现交回 questioner 促发追问。
5. 回到 1。

**穷尽即定稿该策略**：无更多有价值问题时，analyst **定稿 `wiki/studies/<id>.md`**（一句话结论 + 组件归因排序 + 敏感性 + regime + 机理真实性 + 反哺 auto-research 的启示），把该策略标 `done`，**交回外层循环取下一个策略**（不停整个批量）。

---

## 回测命令（唯一执行器，封闭环境）

```bash
node utils/strategy-post-backtest.js study/<id>/variants/<qId>.py "<id>-<qId>" --window <train|val> --usage-limit <cap>
# 或分区间： --start 2022-01-01 --end 2022-12-31   （2025+ 会被 OOS-BLOCKED）
```
- **plain 形式**（无 `JQ_USAGE_LIMIT=` 前缀、无 `| tail`）以匹配允许清单、免逐条授权。
- 读末尾 10 列 `SUMMARY`（`harness.md` §5）；解剖关心的是 variant 相对 `target.py` 基线的 Δ。

---

## 红线（见 `study-schema.md` §10）

- 评测台冻结、**2025+ OOS 绝不触碰**、`target.py` 快照不可变、**一次一处**（干净归因）、真实性红线（零滑点高估必标 ⚠）。
- **无选择压力**：不 keep/discard、不挑「最优变体」当产物；产物是**理解**（报告），不是新策略。启发出的可优化新策略 → 交 auto-research 另起。
- 不 `git commit` `wiki/` 或账本，除非人类明确要求。
- **工具卫生**：所有文件/JSON 操作（更新 `manifest.json` 状态、`questions.json`、`findings.tsv`、造 variant、写报告）**一律用 Read/Write/Edit 工具**（自动放行）；**绝不用 `node -e`/内联脚本或 shell 重定向（`>`,`>>`）**——它们无法进允许清单（等于任意代码执行）、会触发逐条授权。查看文件用 Read/Grep/Glob 或单条简单 Bash，不用复合 Bash。
