---
name: run-experiment
description: Run the join-quant autoresearch TEAM — a 4-agent loop (ideator → critic → engineer → recorder) that generates strategy ideas from the wiki KB, iterates mutations on the frozen TRAIN window, validates finalized strategies once on VAL, and writes learnings back to the wiki. Never touches the 2025+ OOS window. Use when asked to run/continue autoresearch, start the research loop, or propose/improve a strategy.
---

# Run the autoresearch team

驱动 `research/` 的**四智能体**自主策略研究团队。你是**编排者（orchestrator）**：按 `research/program.md` 的状态机，调度四个角色 agent，用磁盘共享状态（`research/ideas-queue.json`、`candidates/`、`results.tsv`、`wiki/**`）协调，**循环直到用户明确说「停」**。
**权威规则见 `research/program.md` 与 `docs/research-schema.md`（冲突以它们为准）、`research/harness.md`（评测台冻结，只读）**——本技能是入口，不复述全部细节。

## 必读（每次开始前）
1. `research/program.md` —— **团队编排主流程 + 状态机**。
2. `research/harness.md` —— 冻结评测台：**TRAIN 选择 / VAL 定稿 / 2025+ OOS 硬阻断**。只读。
3. `docs/research-schema.md` —— 结构/账本/记账格式（权威）。
4. `docs/wiki-schema.md` §2.1 —— 受控因子词表（变异空间边界）。
5. `wiki/index.md` + 相关 `wiki/concepts/*.md` —— 想法来源。

## 团队（**持久 teammate**，角色定义见 `.claude/agents/autoresearch-*.md`）
以 Claude Code agent teams 方式运行：一次性生成四个**具名常驻** teammate，用 `SendMessage` 反复调度，全程保留上下文，直到用户说停（详见 `program.md`「团队与共享状态」）。
- **Agent 1 `autoresearch-ideator`** —— 通读 KB+日志产出带推理的想法；收 TRAIN 结果判「继续/定稿/放弃」。
- **Agent 2 `autoresearch-critic`** —— 判想法是否成立、排名入 `ideas-queue.json`、出队交工程师。
- **Agent 3 `autoresearch-engineer`** —— 封闭环境：写 `.py`、跑回测、调试；Type-1→train，Type-2→val。
- **Agent 4 `autoresearch-recorder`** —— 仅 VAL 结果触发：记 `results.tsv`+实验页+归档 `validated_strategies/`+回填 KB，交回 Agent 1。

## 前置检查
- CDP Chrome 在跑；**登录/预算**：`curl -s localhost:9225/json/version` 通 + `node utils/jq-budget.js` 返回 `used/free`。
- **预算**：`used < JQ_USAGE_LIMIT`（默认 55=仅免费 60 分钟内）。`used ≥ limit` → 干净暂停，等次日重置。
- 在实验分支 `research/<tag>` 上。**断点续跑靠会话恢复**（`program.md`「断点续跑」）：本会话若是被 `--resume` 续起的，上下文已在，直接接着上次断点跑，不重跑已完成回测、不重复已测想法。若是**冷启动新会话**才需从 `research/ideas-queue.json`(status) + `research/results.tsv` + git 当前 candidate 重建上下文；都没有 → 按 `program.md` Setup 初始化（全新纪元）。

## 运行方式（交互式前台 + cron 续跑同一会话）
- **推荐**：人类用 `scripts/autoresearch-interactive.sh` 起一个**钉住会话 id** 的交互式会话来跑本技能，可观察、可打断。额度停了别管——每小时的 launchd cron（`scripts/autoresearch-loop.sh`）会 `claude -p --resume` **同一会话**续跑；回来再跑一次该脚本即重开同一会话看进展。
- 作为编排者：**开局一次性**用 `Agent`（带 `name`、`run_in_background: true`）生成四个具名常驻 teammate（`ideator`/`critic`/`engineer`/`recorder`）；此后**只用 `SendMessage({to: name})` 反复调度同一批**（它们保留上下文，不重生成/重读），按 `program.md` 状态机居中路由：
  `ideator →(想法) critic →(出队) engineer →(train) ideator →(定稿) engineer →(val) recorder → ideator …`。
- **续跑（`--resume`）后**：teammate 已随上个会话消失 → **先重新生成同一批具名 teammate**，再据会话上下文 + 磁盘账本从断点继续。
- **只有用户说停才结束**（预算到顶=干净暂停，非停止）。

## 回测命令（唯一执行器 = Pipeline 2，封闭环境）
```bash
JQ_USAGE_LIMIT=55 node utils/strategy-post-backtest.js research/candidates/<expId>.py "<expId>" --window <train|val>
```
- 迭代（Type-1）用 `--window train` 算 `objective(TRAIN)`；定稿（Type-2）用 `--window val` 算 `objective(VAL)`。
- **`holdout` / 任何 2025+ 区间被 `OOS-BLOCKED` 拒跑**（除非用户私测 `JQ_ALLOW_OOS=1`——agent 绝不设）。
- 读末尾 10 列 `SUMMARY`（`harness.md` §5）；`annual%` 已年化，直接算 objective。

## 完成后简报
本纪元处理了多少想法、定稿几个、当前最优 `objective(TRAIN)` 及其 `objective(VAL)`、发现的规律与回填落点、多少放弃/crash、队列剩余。不 `git commit` wiki 或 `results.tsv`，除非人类明确要求。

## 红线
严格窗口（迭代 TRAIN / 定稿 VAL / 2025+ 永不碰）、评测台冻结、封闭环境（Agent 3 只能经执行器）、HOLDOUT 禁用、真实性红线（零滑点高估必标 ⚠）、raw 不可变、受控命名、概念页只追加不覆盖。
