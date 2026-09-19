---
name: run-study
description: Run the join-quant auto-STUDY loop — a 4-agent team (questioner → prioritizer → experimenter → analyst) that dissects ONE strategy FAMILY to understand it: the base's mechanics, why each variant's change moved the result, parameter sensitivity, regime dependence — then writes results back to the family page (§2 variants + §6 study-log). Reuses the frozen harness; never touches 2025 OOS. Use when asked to study/dissect/understand a strategy family, do sensitivity/ablation analysis, or figure out what makes a family work.
---

# Run the auto-study team (family-level)

驱动 `study/` 的**四智能体**解剖团队：理解**一个策略家族**（不优化指标）。你是**编排者**：按 `study/program.md` 状态机，用**临时 subagent** 逐步调度四个角色，磁盘共享状态协调，**循环到问题穷尽或用户说停**，把结论**写回家族页 `wiki/families/<family>.md`**（§2 变体 + §6 研究问答）。
**权威见 `study/program.md` 与 `docs/study-schema.md`（冲突以它们为准）、`harness/harness.md`（评测台冻结，只读）**——本技能是入口，不复述全部细节。

## 必读
1. `study/program.md` —— 团队编排主流程 + 状态机（家族级）。
2. `docs/study-schema.md` —— 结构/实验类型/发现账本/家族页写回格式（权威）。
3. `harness/harness.md` —— 冻结成本/滑点；窗口 **2022–2024 任意子窗**，**2025 OOS 硬阻断**。只读。
4. **目标家族页** `wiki/families/<family>.md`（§1 基类、§2 变体、§4 待研究）+ 其 `base:`/成员策略页 + 相关 `wiki/concepts/*.md`。

## 团队（**临时 subagent**，角色定义见 `.claude/agents/autostudy-*.md`）
每步用 `Agent` 工具**新生成**对应角色的一次性 subagent，干完返回即终止；不常驻、不互相寻址，**全部路由经编排者居中**。
- **Agent 1 `autostudy-questioner`** —— 提可证伪、可一实验回答的问题：基类机理 + **每个变体的改动为何得到该 Δ**。
- **Agent 2 `autostudy-prioritizer`** —— 判问题成立、排名入 `questions.json`、出队交实验官。
- **Agent 3 `autostudy-experimenter`** —— 封闭环境：造消融/改参变体或跑分区间/探针，返回相对**基类基线** Δ。
- **Agent 4 `autostudy-analyst`** —— 把结果解读成发现、记 `findings.tsv`、**写回家族页 §2/§6**、反哺 KB。

## ⚠ 批量模式已跑完（2026-09-19 实测）
`study/manifest.json` 的 **14 个家族全部 `status: done`**——外层循环没有 pending 了。所以：
- 用户指定单个家族 → 照常跑（可就既有家族提新问题）。
- 想要**新目标** → 目标来自 `screen/verdicts.json`：筛选官已提出 **93 个 `NEW:<机制>` 家族**
  （全天候/风险平价、宏观择时、北上资金、异常财务因子、隔夜跳空、商品截面、国债…），
  **但一个都还没注册成 `wiki/families/*.md`**。必须先建家族页（受控命名，见 `docs/wiki-schema.md` §9）
  并把成员策略归位，本技能才有东西可解剖。**不要**把 `NEW:` 字符串当家族页用。
- §3 横评：`node utils/wiki-family-build.js` 目前对 **7 个家族仍是 BLOCKED**（账本缺 20 个策略的行）。
  收口时 §3 跑不动是**预期**的，**绝不 `--force`**——那会抹掉页上的历史指标。

## 前置检查
- **目标家族** `<family>`（用户指定，如 `五福闹新春`；或批量遍历 `study/manifest.json`）。**在当前分支上跑**（不再要求 `study/all`；分支由人类自行选定，续跑时会话钉住的分支需与当前一致）。
- CDP Chrome 在跑：`node utils/jq-budget.js` 出 `used/free`（remote 模式下它会自动拉起 SSH 隧道）；`used < --usage-limit`。隧道状态可用 `./scripts/cdp-tunnel.sh status` 查。
- Setup（首次）：快照 `study/<family>/baseline.py` = 家族 `base:` 源码（+ 冻结成本 override）、跑基类基线、初始化 `questions.json`/`findings.tsv`；读入 §2 现有变体作为待解释对象。续跑：读磁盘状态从断点继续。

## 运行方式
作为编排者按 `study/program.md` 状态机逐步调度：`questioner →(问题) prioritizer →(出队) experimenter →(Δ结果) analyst →(写回家族页) questioner …`。每一步新生成临时 subagent、拿结果、再决定下一步。**只在问题穷尽或用户说停时结束**；穷尽时 analyst 收口家族页（§1 为什么有效 / §2 变体归因 / §4 待研究；§3 横评跑 `wiki-family-build.js` 重生成）。

## 回测命令（唯一执行器，封闭环境）
```bash
node utils/strategy-post-backtest.js study/<family>/variants/<qId>.py "<family>-<qId>" --window <train|val> --usage-limit <cap>
# 分区间： --start 2022-01-01 --end 2022-12-31   （2025+ 被 OOS-BLOCKED）
```
plain 形式（无 `JQ_USAGE_LIMIT=` 前缀、无 `| tail`）以免逐条授权。**前台阻塞跑**——发一条等它返回再读 `SUMMARY`，**绝不**后台跑+等通知（headless `claude -p` 无人值守跑中通知不会重新唤起会话，会卡住）。关心 variant 相对家族**基类基线**的 Δ。

## 红线
评测台冻结、**2025+ OOS 永不碰**、`baseline.py` 不可变、**一次一处**（干净归因）、**无选择压力**（产物是理解不是新策略；优化/借鉴想法交 auto-enhance）、零滑点高估必标 ⚠。家族页 §2/§6 只追加不覆盖、§3 横评勿手写（`wiki-family-build.js` 生成）、概念页只追加不覆盖。不 `git commit` wiki/账本除非人类要求。

## 工具卫生（编排者也适用）
所有文件/JSON 操作（读家族页/`manifest.json`/`questions.json`、更新 `findings.tsv`、写回家族页）**一律用 Read/Write/Edit 工具或单条 `jq`**（自动放行）；**绝不用 `node -e`/内联脚本或 shell 重定向（`>`,`>>`）**——无法进允许清单、触发逐条授权。查看用 Read/Grep/Glob 或单条简单 Bash，不用复合 Bash（`for`、`cd &&`、`$var`）。此规则不止约束四个 subagent，**编排者主循环同样遵守**。
