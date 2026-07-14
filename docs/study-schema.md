# join-quant 自动研究·策略解剖（auto-study）Schema

本文件定义 `study/` **自动策略解剖循环**的结构与规则，是 `docs/research-schema.md`（自动寻优）的**姊妹篇**。
两者共用同一冻结评测台（`research/harness.md` 的成本/滑点/真实性过滤）与同一执行器，但**目标不同**：

- **auto-research（`research-schema.md`）**：最大化 `objective`，找更好的策略；有选择压力、护 VAL/OOS。
- **auto-study（本文件）**：**理解一个既定策略**——各组件贡献归因、参数敏感性、区间/regime 依赖、失效模式；**没有选择压力**，每个实验都产出「发现」，最终产出一份**解剖报告**。

---

## 1. 与 auto-research 的对应关系

| auto-research | auto-study | 说明 |
|---|---|---|
| 目标：最大化 objective | 目标：**理解一个策略** | 不优化指标，产出洞察 |
| 单位：一次「变异」 | 单位：一个**问题** + 回答它的实验 | |
| 变异类型（参数/因子/模块/拼装） | **实验类型**（消融/敏感性扫描/分区间/组件隔离/数据探针，§5） | |
| keep/discard 靠 objective | **无 keep/discard**——每个实验都记为「发现」 | |
| 冻结三窗、OOS 禁用 | **2022–2024 内任意子窗**（做 regime 分析）、2025 OOS 仍硬阻断 | |
| 产物：`validated_strategies/` + 实验页 | 产物：**解剖报告** `wiki/studies/<id>.md` | |
| 4 智能体（点子/筛选/工程/记账） | 4 智能体（**提问/排序/实验/分析**，§ program.md） | 同框架 |

---

## 2. 目录结构

```
join-quant/
├── study/
│   ├── program.md                     # 团队编排指令（人类编辑；见姊妹文件）
│   └── <strategyId>/                   # 一次解剖 = 一个目标策略
│       ├── target.py                   #   被解剖策略的源码快照（+ 冻结成本 override）
│       ├── questions.json              #   排名问题队列（git 不跟踪）
│       ├── findings.tsv                #   发现账本（git 不跟踪，§7）
│       └── variants/<qId>.py           #   每个实验的消融/改参变体（raw，不可变）
├── research/harness.md                 # 共用冻结评测台（成本/滑点/真实性过滤；只读）
└── wiki/
    └── studies/<strategyId>.md         # 解剖报告（§8；人类决定何时 commit）
```

- `<strategyId>` = 被解剖策略的标识（如 `jul12-005`、`aaba7575`）。
- `study/<id>/variants/` 与 `research/candidates/` 一样属 **raw 层**：跑过即不可变（git 记录演进）。
- 正文中文，与 `wiki-schema.md` / `research-schema.md` 一致；agent 定义为英文。

---

## 3. 冻结评测台（复用，权威见 `research/harness.md`）

- **成本/滑点/真实性过滤**：与 auto-research **完全相同**（`harness.md` §2–§3）——解剖时给 `target.py` 与所有 variant 追加同一**冻结成本 override**（零滑点/PerTrade，见 `utils/strategy-normalize.js` 的 `OVERRIDE`），使基线与变体**可比**。
- **窗口**：解剖是「刻画」不是「选择」，故可在 **2022-01-01 → 2024-12-31** 内跑**任意子窗**（`--window train|val` 或 `--start/--end`）做 regime 分析。
- **2025+ OOS 仍禁用**：`strategy-post-backtest.js` 对任何 `>= 2025-01-01` 的窗口 `OOS-BLOCKED`（除用户私测 `JQ_ALLOW_OOS=1`）。解剖 agent **绝不设** `JQ_ALLOW_OOS`。
- **指标**：与 §research-schema §3.3 同的 `objective / gate / sharpe / annualReturn / maxDrawdown`；解剖更关心**相对基线的 Δ**（归因）而非绝对值。

---

## 4. 「理解一个策略」= 回答四类问题

对一个表现好（或坏）的策略，值得问：

1. **归因**：哪个组件在起作用？把某组件去掉，objective/回撤/换手怎么变？
2. **敏感性**：objective 对某参数有多敏感？是平台（稳健）还是悬崖（脆弱/过拟合）？最优点在哪、边际多薄？
3. **regime 依赖**：它在什么区间/市场状态下有效/失效？（2022 熊 / 2023 震荡 / 2024 / 2024-02 微盘踩踏等）
4. **机理**：持仓/换手/成交时点的实际数据长什么样，是否印证叙事？成交假设是否真实（零滑点高估？）

每个问题必须**可证伪、可用一次实验回答**，落入 `questions.json`（§6）。

---

## 5. 实验类型（study 的「招式」）

执行器唯一 = `utils/strategy-post-backtest.js`（同 auto-research，封闭环境）。

| 类型 | 做法 | 产出 |
|---|---|---|
| **消融 ablation** | 复制 `target.py` → 关闭/移除**一个**组件（某因子/过滤/择时/止损）→ 跑同窗 | Δobjective / Δsharpe / Δmaxdd / **Δ换手** → 该组件贡献 |
| **参数敏感性 sweep** | 在网格上改**一个**参数（持仓数/止损线/均线周期/振幅阈值…）→ 跑一串 | 敏感性曲线：平台 vs 悬崖 vs 单峰；最优/稳健区 |
| **分区间 regime** | 同一策略跑多个子窗（2022/2023/2024/压力月）| 何时有效/失效 |
| **组件隔离 isolate** | 只留一个组件单独跑 | 该组件的独立边际价值 |
| **数据探针 probe** | 读回测持仓/换手/成交时点（结果表或日志）| 机理，非仅指标 |

- 一次实验只改/看**一处**（干净归因）。变体源码存 `study/<id>/variants/<qId>.py`。
- 成交假设不真实（打板/涨停/高换手零滑点）者，发现里**必标 ⚠**，Δ 仅作机理参考。

---

## 6. 问题队列 `study/<strategyId>/questions.json`

排名队列（git 不跟踪）。每项：

```json
{ "id": "q-3", "question": "把 MA10 择时空仓开关去掉，回撤会抬多少？",
  "type": "ablation | sweep | regime | isolate | probe",
  "hypothesis": "MA10 择时贡献了大部分回撤压制，去掉后 maxdd 从 11% 抬到 ~18%",
  "why": "定位低回撤的主因（组件归因）",
  "design": "复制 target.py，注释掉 market_ok() 的 MA10 分支，跑 --window train + 分 2022/2023/2024",
  "rank": 5, "status": "queued | active | answered | dropped" }
```

---

## 7. 发现账本 `study/<strategyId>/findings.tsv`

追加式、TAB 分隔、**git 不跟踪**。每个已回答问题一行，9 列：

```
qId	type	component_or_param	metric_delta	window	finding	confidence	flags	description
```

1. `qId`（如 `q-3`）2. `type`（§5）3. 被测组件/参数 4. 关键 Δ（如 `maxdd +0.07 / annual -0.03`）
5. `window`（train/val/2022/…）6. **一句发现**（这实验告诉我们什么）7. `confidence`（high/med/low）
8. `flags`（⚠零滑点高估 / overfit-cliff / regime-specific…）9. 简述（怎么测的）

---

## 8. 解剖报告 `wiki/studies/<strategyId>.md`

由分析 agent 维护、逐步充实（不是一次写完）。模板：

```markdown
---
studyId: <strategyId>
target: research/candidates/<id>.py 或 strategies/<file>.py
targetRefs: [[<strategy wiki 页>]], [[<相关概念>]]
harness: research/harness.md（冻结成本；窗口 2022–2024，2025 OOS 禁用）
startedAt: <YYYY-MM-DD>
status: in-progress | done
---

# 解剖报告：<strategyId>

## 一句话结论
<这个策略靠什么赚钱、最脆弱在哪>

## 组件贡献归因（按贡献排序）
| 组件 | 去掉后 Δobjective | Δmaxdd | Δ换手 | 结论 |
|---|---|---|---|---|
| … | … | … | … | 核心 alpha / 次要 / 冗余(可删) |

## 参数敏感性
<每个关键参数的曲线：平台/悬崖/最优；哪些是过拟合的窄峰>

## regime 依赖
<2022/2023/2024 分区间表现；何时失效；对 2024-02 微盘踩踏这类事件的暴露>

## 机理与真实性
<持仓/换手/成交时点数据；零滑点高估程度；可实现性判断>

## 待研究 / 反哺 auto-research
<本次解剖暴露的新问题；对 auto-research 想法生成的启示（§9 反哺）>
```

---

## 9. 知识反哺契约（write-back）

解剖产生的**跨策略洞察**要回填知识库（与 `wiki-schema.md` §9、`research-schema.md` §9 一致）：
- **可溯源**：概念页/策略页每条新结论带 `[[<studyId>]]` 指针。
- **只追加**：概念页只加不改；矛盾只标记留人裁决。
- 有价值的敏感性/归因规律 → 追加到相关 `wiki/concepts/*.md`「观察」，供 auto-research 的 ideator 复用。
- `wiki/log.md` 追加：`## [YYYY-MM-DD] study | <strategyId> (<摘要>) → 回填 [[<页>]]`。

---

## 10. 不可违反的原则

- **评测台冻结**：成本/滑点/真实性过滤只读；**2025+ OOS 绝不触碰**（代码硬阻断，绝不设 `JQ_ALLOW_OOS`）。
- **target 不可变**：被解剖策略源码快照 `target.py` 一经确定即冻结；实验只在 `variants/` 造变体。
- **一次一处**：一个实验只改/看一处，保证归因干净。
- **真实性红线**：零滑点高估 / 不真实成交必标 ⚠，Δ 不当作可实现结论。
- **无选择压力**：不 keep/discard、不挑「最优变体」当产物——产物是**理解**，不是新策略。（若解剖启发了值得优化的新策略，那是 auto-research 的活，另起。）
- **预算**：同 auto-research 的 JQ 计费现实（每日免费 60 分钟、`--usage-limit` 上限、并发 2）。
