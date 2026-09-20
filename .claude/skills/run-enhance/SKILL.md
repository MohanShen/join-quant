---
name: run-enhance
description: Run the join-quant autoenhance TEAM — a 4-agent loop (ideator → critic → engineer → recorder) that improves a strategy FAMILY: generates ideas (within-family / cross-family borrow / new-family combination), iterates mutations on the frozen TRAIN window, validates finalized strategies once on VAL, and writes results back to the family page as new variants. Never touches the reserved OOS window (epoch 5: 2026+). Use when asked to run/continue autoenhance, enhance a strategy family, or propose/improve a strategy.
---

# Run the autoenhance team

驱动 `enhance/` 的**四智能体**自主策略研究团队。你是**编排者（orchestrator）**：按 `enhance/program.md` 的状态机，调度四个角色 agent，用磁盘共享状态（`enhance/ideas-queue.json`、`candidates/`、`results.tsv`、`wiki/**`）协调，**循环直到用户明确说「停」**。
**权威规则见 `enhance/program.md` 与 `docs/enhance-schema.md`（冲突以它们为准）、`harness/harness.md`（评测台冻结，只读）**——本技能是入口，不复述全部细节。

## 必读（每次开始前）
1. `enhance/program.md` —— **团队编排主流程 + 状态机**。
2. `harness/harness.md` —— 冻结评测台：**TRAIN 选择 / VAL 定稿 / OOS 硬阻断**（边界随纪元变动，当前 epoch 5 为 2026-01-01；以 `node utils/harness-config.js` 为准）。只读。
3. `docs/enhance-schema.md` —— 结构/账本/记账格式（权威）。
4. `docs/wiki-schema.md` §2.1 —— 受控因子词表（变异空间边界）。
5. `wiki/index.md` + 相关 `wiki/concepts/*.md` —— 想法来源。⚠ index 不完整（187 篇里只链 79 篇），
   别把它当全集；概念页 `strategyCount` 已漂移，不可引用。
6. **`screen/verdicts.json` —— 目前最富的想法来源（2026-09-19 新增）**。857 篇社区帖已按冻结
   评测规则打分，`band=fetch-now/fetch` 的条目带 `mechanism`/`why`/`flags`，其中 **93 个
   `NEW:<机制>`** 是 14 个家族都没有的机制轴（全天候/风险平价、宏观择时、北上资金、异常财务因子、
   隔夜跳空、商品截面、国债）。**跨族借鉴与组合新族的想法优先从这里取**，并在想法里引用其 `key`。
   注意：高 `priority` ≠ 好回测对象——`S=0` 的条目是**读物**（写作/期货/缺数据），不可送去跑回测。

## 团队（**临时 subagent**，角色定义见 `.claude/agents/autoenhance-*.md`）
每步用 `Agent` 工具**新生成**对应角色的一次性 subagent，干完一件事返回即终止；不常驻、不互相寻址，**全部路由经编排者居中**（详见 `program.md`「团队与共享状态」）。
- **Agent 1 `autoenhance-ideator`** —— 读目标家族页 + KB 产出带推理的想法（**族内改进 / 跨族借鉴 / 组合新族**）；收 TRAIN 结果判「继续/定稿/放弃」。
- **Agent 2 `autoenhance-critic`** —— 判想法成立（受控因子+家族词表、非族内重复、借鉴有据、新族非重复）、排名入 `ideas-queue.json`、出队交工程师。
- **Agent 3 `autoenhance-engineer`** —— 封闭环境：写 `.py`、跑回测、调试；Type-1→train，Type-2→val。
- **Agent 4 `autoenhance-recorder`** —— 仅 VAL 结果触发：**把结果写成目标家族页 §2 新变体**（`enhance-<expId>`）+ 记 `results.tsv` + 归档 `validated_strategies/` + 组合新族则登记 §2.2 建页 + 回填 KB，交回 Agent 1。

## 前置检查
- CDP Chrome 在跑；**登录/预算**：`curl -s localhost:9225/json/version` 通 + `node utils/jq-budget.js` 返回 `used/free`。
- **预算**：`used < JQ_USAGE_LIMIT`（默认 55=仅免费 60 分钟内）。`used ≥ limit` → 干净暂停，等次日重置。
  ⚠ **这 60 分钟是全仓库共用的**：`utils/normalize-backfill.js` 写的归一化队列
  （`data/pending-normalize.json`，当前 54 条）与本团队抢同一份额度。开跑前先确认人类要把今天的
  额度给谁；2026-09-18 的一次回填里 **59 分钟有 50 分钟耗在 5 次 slow-skip 超时上**，颗粒无收。
- 在实验分支 `enhance/<tag>` 上。**断点续跑靠会话恢复**（`program.md`「断点续跑」）：本会话若是被 `--resume` 续起的，上下文已在，直接接着上次断点跑，不重跑已完成回测、不重复已测想法。若是**冷启动新会话**才需从 `enhance/ideas-queue.json`(status) + `enhance/results.tsv` + git 当前 candidate 重建上下文；都没有 → 按 `program.md` Setup 初始化（全新纪元）。

## 运行方式（交互式前台 + cron 续跑同一会话）
- **推荐**：人类用 `scripts/autoenhance-interactive.sh` 起一个**钉住会话 id** 的交互式会话来跑本技能，可观察、可打断。额度停了别管——每小时的 launchd cron（`scripts/autoenhance-loop.sh`）会 `claude -p --resume` **同一会话**续跑；回来再跑一次该脚本即重开同一会话看进展。
- 作为编排者：按 `program.md` 状态机，**每一步都用 `Agent` 工具新生成**对应角色的临时 subagent（不带 `name`、不常驻），把当步任务 + 最小上下文作为 prompt 传入，拿到它返回的结果后再决定下一步、再生成下一个角色。全部路由经你居中：
  `ideator →(想法) critic →(出队) engineer →(train) ideator →(定稿) engineer →(val) recorder → ideator …`。
- **续跑（`--resume`）后**：没有 teammate 需要重生成——你的编排上下文已在，直接按需继续新生成 subagent；transcript 与磁盘冲突以磁盘为准。
- **只有用户说停才结束**（预算到顶=干净暂停，非停止）。

## 回测命令（唯一执行器 = Pipeline 2，封闭环境）
```bash
node utils/strategy-post-backtest.js enhance/candidates/<expId>.py "<expId>" --window <train|val> --usage-limit <cap>
```
- **plain 形式**（不加 `JQ_USAGE_LIMIT=` 前缀、不接 `| tail`）以匹配 `.claude/settings.json` 允许清单、免逐条授权；`SUMMARY` 本就是最后一行。
- **前台阻塞跑**——发一条命令等它返回再读 `SUMMARY`；**绝不**后台跑（`run_in_background`）+ 等完成通知：headless `claude -p` 无人值守跑中该通知不会重新唤起会话，循环会卡在半路。
- `<cap>` = 每日 JQ 回测分钟上限（默认 **55**=免费额度；cron 续跑用 **240**）。
- 迭代（Type-1）用 `--window train` 算 `objective(TRAIN)`；定稿（Type-2）用 `--window val` 算 `objective(VAL)`。
- **`holdout` / 任何落入保留 OOS 的区间被 `OOS-BLOCKED` 拒跑**（epoch 5 为 2026-01-01 起；边界随纪元变动，查 `node utils/harness-config.js`）（除非用户私测 `JQ_ALLOW_OOS=1`——agent 绝不设）。
- 读末尾 10 列 `SUMMARY`（`harness.md` §5）；`annual%` 已年化，直接算 objective。

## 既有战绩（冷启动时先读，别重走弯路）
`validated_strategies/` 只有 **2 个**跑完 VAL 的策略，两个都值得当先例引用：
- `jul12-005`（小市值低开剥头皮，仓位 5→6）：TRAIN 1.3898 → **VAL 1.3231，过闸**。但 TRAIN 相对
  基线只赢 0.016——**薄边际也能过 VAL**。
- `jul12-023`（微盘多头 − IC 空头 1.2× 对冲）：TRAIN 0.3202 过闸 → **VAL −0.5260，maxDD 41.6%，惨败**。
  归因是 **basis risk 而非成本**：IC（中证500 中盘）对中证微盘是不充分对冲，2024-02 微盘专属崩盘时
  空头腿没保护。TRAIN 过闸只是 2022–23 两者同跌的 regime 产物。
  ⇒ **教训**：对冲腿与多头腿标的不匹配时，TRAIN 的「市场中性」可能是假象；薄闸门边际（当时 2.64 vs 当时的闸门 2.5——**epoch 2 的旧值**，epoch 5 已降为 1.5；教训在「边际薄」本身，不在这两个数）
  在窗口外最先反转。

## 完成后简报
本纪元处理了多少想法、定稿几个、当前最优 `objective(TRAIN)` 及其 `objective(VAL)`、发现的规律与回填落点、多少放弃/crash、队列剩余。不 `git commit` wiki 或 `results.tsv`，除非人类明确要求。

## 未过闸 ≠ 无价值：登记可用部件

epoch 5 起**未过闸仍保留分数**，`gate` 只是标签。一个整体过不了闸的变异，里面的**某个部件**
仍可能是 type 级整合的好配料——尤其是与本 type 头名**相关性低**的那种（按标准分挑配料，
恰好会丢掉最能分散风险的腿）。

所以：某次迭代若测到「这一处改动确实有用，但整体仍不过闸」，别只把它记成失败——登记为部件：

```
node utils/components.js --add --source <candidates/或 strategies/ 路径> --aspect "<部件>" \
  --kind factor|filter|universe|entry|exit|sizing|timing|risk|data --type <type> \
  --claim "<做到了什么>" --evidence "<expId + Δobjective/Δsharpe>" --by run-enhance
```

`--evidence` 必填。这些部件由 `/run-integrate` 在 type 级消费；`node utils/component-scan.js`
会按「对本 type 头名的增量」排序，并打印相关性——**它的混合是零成本日频再平衡的上界，不是结果**。

## 红线
严格窗口（迭代 TRAIN / 定稿 VAL / 保留 OOS 永不碰）、评测台冻结、封闭环境（Agent 3 只能经执行器）、HOLDOUT 禁用、真实性红线（零滑点高估必标 ⚠）、raw 不可变、受控命名、概念页只追加不覆盖。
