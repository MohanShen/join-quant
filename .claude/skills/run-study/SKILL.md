---
name: run-study
description: Run the join-quant auto-STUDY loop — a 4-agent team (questioner → prioritizer → experimenter → analyst) that dissects ONE target strategy to understand it: component attribution, parameter sensitivity, regime dependence, and mechanics, then writes a study report. Reuses the frozen harness; never touches 2025 OOS. Use when asked to study/dissect/understand a strategy, do sensitivity/ablation analysis, or figure out what makes a strategy work.
---

# Run the auto-study team

驱动 `study/` 的**四智能体**策略解剖团队：理解一个既定策略（不优化指标）。你是**编排者**：按 `study/program.md` 状态机，用**临时 subagent** 逐步调度四个角色，磁盘共享状态协调，**循环到问题穷尽或用户说停**，产出 `wiki/studies/<id>.md` 报告。
**权威见 `study/program.md` 与 `docs/study-schema.md`（冲突以它们为准）、`research/harness.md`（评测台冻结，只读）**——本技能是入口，不复述全部细节。

## 必读
1. `study/program.md` —— 团队编排主流程 + 状态机。
2. `docs/study-schema.md` —— 结构/实验类型/发现账本/报告格式（权威）。
3. `research/harness.md` —— 冻结成本/滑点；窗口 **2022–2024 任意子窗**，**2025 OOS 硬阻断**。只读。
4. 目标策略源码 + 其 `wiki/strategies/*.md` + 相关 `wiki/concepts/*.md`。

## 团队（**临时 subagent**，角色定义见 `.claude/agents/autostudy-*.md`）
每步用 `Agent` 工具**新生成**对应角色的一次性 subagent，干完返回即终止；不常驻、不互相寻址，**全部路由经编排者居中**。
- **Agent 1 `autostudy-questioner`** —— 提可证伪、可一实验回答的解剖问题（归因/敏感性/regime/机理）。
- **Agent 2 `autostudy-prioritizer`** —— 判问题成立、排名入 `questions.json`、出队交实验官。
- **Agent 3 `autostudy-experimenter`** —— 封闭环境：造消融/改参变体或跑分区间/探针，返回相对基线 Δ。
- **Agent 4 `autostudy-analyst`** —— 把结果解读成发现、记 `findings.tsv`、维护 `wiki/studies/<id>.md`、反哺 KB。

## 前置检查
- **目标策略** `<strategyId>`（用户指定，如 `jul12-005`）。在分支 `study/<strategyId>` 上。
- CDP Chrome 在跑；`node utils/jq-budget.js` 出 `used/free`；`used < --usage-limit`（默认 55）。
- Setup（首次）：快照 `study/<id>/target.py`（+ 冻结成本 override）、跑基线、初始化 `questions.json`/`findings.tsv`/空报告（`program.md` Setup）。续跑：读磁盘状态从断点继续。

## 运行方式
作为编排者按 `study/program.md` 状态机逐步调度：`questioner →(问题) prioritizer →(出队) experimenter →(Δ结果) analyst →(发现) questioner …`。每一步新生成临时 subagent、拿结果、再决定下一步。**只在问题穷尽或用户说停时结束**；穷尽时 analyst 定稿报告。

## 回测命令（唯一执行器，封闭环境）
```bash
node utils/strategy-post-backtest.js study/<id>/variants/<qId>.py "<id>-<qId>" --window <train|val> --usage-limit <cap>
# 分区间： --start 2022-01-01 --end 2022-12-31   （2025+ 被 OOS-BLOCKED）
```
plain 形式（无 `JQ_USAGE_LIMIT=` 前缀、无 `| tail`）以免逐条授权。关心 variant 相对 `target.py` 基线的 Δ。

## 红线
评测台冻结、**2025+ OOS 永不碰**、`target.py` 不可变、**一次一处**（干净归因）、**无选择压力**（产物是理解不是新策略）、零滑点高估必标 ⚠、概念页只追加不覆盖。不 `git commit` wiki/账本除非人类要求。

## 工具卫生（编排者也适用）
所有文件/JSON 操作（读 `manifest.json`/`questions.json`、批量查 `sourceFile`、更新 `findings.tsv`/报告）**一律用 Read/Write/Edit 工具或单条 `jq`**（自动放行）；**绝不用 `node -e`/内联脚本或 shell 重定向（`>`,`>>`）**——它们无法进允许清单（等于任意代码执行）、会触发逐条授权。查看用 Read/Grep/Glob 或单条简单 Bash，不用复合 Bash（`for`、`cd &&`、`$var`）。此规则不止约束四个 subagent，**编排者主循环同样遵守**。
