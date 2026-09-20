# join-quant 自动研究·策略解剖（auto-study）Schema

本文件定义 `study/` **自动策略解剖循环**的结构与规则，是 `docs/enhance-schema.md`（自动寻优）的**姊妹篇**。
两者共用同一冻结评测台（`harness/harness.md` 的成本/滑点/真实性过滤）与同一执行器，但**目标不同**：

- **auto-enhance（`enhance-schema.md`）**：最大化 `objective`，找更好的策略；有选择压力、护 VAL/OOS。
- **auto-study（本文件）**：**理解一个既定策略**——各组件贡献归因、参数敏感性、区间/regime 依赖、失效模式；**没有选择压力**，每个实验都产出「发现」，最终产出一份**解剖报告**。

---

## 1. 与 auto-enhance 的对应关系

| auto-enhance | auto-study | 说明 |
|---|---|---|
| 目标：最大化 objective | 目标：**理解一个策略** | 不优化指标，产出洞察 |
| 单位：一次「变异」 | 单位：一个**问题** + 回答它的实验 | |
| 变异类型（参数/因子/模块/拼装） | **实验类型**（消融/敏感性扫描/分区间/组件隔离/数据探针，§5） | |
| keep/discard 靠 objective | **无 keep/discard**——每个实验都记为「发现」 | |
| 冻结三窗、OOS 禁用 | **2022–2024 内任意子窗**（做 regime 分析）、2025 OOS 仍硬阻断 | |
| 产物：`validated_strategies/` + 实验页 | 产物：**解剖报告** `wiki/families/<family>.md` | |
| 4 智能体（点子/筛选/工程/记账） | 4 智能体（**提问/排序/实验/分析**，§ program.md） | 同框架 |

---

## 2. 目录结构

**批量模式**：解剖**所有策略家族**（`wiki/families/*.md`，不含单例桶「其他」）。`study/manifest.json` 列全部家族 + 每个 `status`（pending|in-progress|done），按家族 `bestObjective` 强→弱排序；外层循环逐个做完，**不到全部 `done` 或用户说停不退出**（`program.md` 外层循环）。

```
join-quant/
├── study/
│   ├── program.md                     # 团队编排指令（人类编辑；见姊妹文件）
│   ├── manifest.json                   # 批量清单：所有家族 + status（git 不跟踪）
│   └── <family>/                       # 每个家族一目录
│       ├── baseline.py                 #   家族基类源码快照（+ 冻结成本 override）
│       ├── questions.json              #   排名问题队列（git 不跟踪）
│       ├── findings.tsv                #   发现账本（git 不跟踪，§7）
│       └── variants/<qId>.py           #   每个实验的消融/改参变体（raw，不可变）
├── harness/harness.md                 # 共用冻结评测台（成本/滑点/真实性过滤；只读）
└── wiki/
    └── families/<family>.md            # 写回目标（§8：§2 变体 + §6 研究问答）
```

- `<family>` = 家族规范名（如 `五福闹新春`、`小市值`）；既有 `wiki/studies/*.md` 为单策略归档。
- `study/<family>/variants/` 与 `enhance/candidates/` 一样属 **raw 层**：跑过即不可变（git 记录演进）。
- 正文中文，与 `wiki-schema.md` / `enhance-schema.md` 一致；agent 定义为英文。

---

## 3. 冻结评测台（复用，权威见 `harness/harness.md`）

- **成本/滑点/真实性过滤**：与 auto-enhance **完全相同**（`harness.md` §2–§3）——解剖时给 `baseline.py` 与所有 variant 追加同一**冻结成本 override**（零滑点/PerTrade，见 `utils/strategy-normalize.js` 的 `OVERRIDE`），使基线与变体**可比**。
- **窗口**：解剖是「刻画」不是「选择」，故可在 **2022-01-01 → 2025-12-31** 内跑**任意子窗**（`--window train|val` 或 `--start/--end`）做 regime 分析。
- **2026+ OOS 仍禁用**：`strategy-post-backtest.js` 对任何 `>= 2026-01-01` 的窗口 `OOS-BLOCKED`（除用户私测 `JQ_ALLOW_OOS=1`）。解剖 agent **绝不设** `JQ_ALLOW_OOS`。
- **指标**：与 §enhance-schema §3.3 同的 `objective / gate / sharpe / annualReturn / maxDrawdown`；解剖更关心**相对基线的 Δ**（归因）而非绝对值。

---

## 4. 「理解一个策略家族」= 回答的问题

对一个家族的**基类 + 其变体**，值得问：

0. **变体归因（家族级核心）**：§2 里某变体相对基类的**一处改动**，为何产生了它那个 Δ？用一次受控实验证实/证伪该因果链（如「取消 13:10 狙击窗为何 +0.08 obj」）。这是把过去对单策略做的组件归因，放到家族的变体维度上递归。
1. **组件归因**：基类哪个组件在起作用？把某组件去掉，objective/回撤/换手怎么变？
2. **敏感性**：objective 对某参数有多敏感？是平台（稳健）还是悬崖（脆弱/过拟合）？最优点在哪、边际多薄？
3. **regime 依赖**：它在什么区间/市场状态下有效/失效？（2022 熊 / 2023 震荡 / 2024 / 2024-02 微盘踩踏等）
4. **机理**：持仓/换手/成交时点的实际数据长什么样，是否印证叙事？成交假设是否真实（零滑点高估？）

每个问题必须**可证伪、可用一次实验回答**，落入 `questions.json`（§6）。

---

## 5. 实验类型（study 的「招式」）

执行器唯一 = `utils/strategy-post-backtest.js`（同 auto-enhance，封闭环境）。

| 类型 | 做法 | 产出 |
|---|---|---|
| **消融 ablation** | 复制 `baseline.py` → 关闭/移除**一个**组件（某因子/过滤/择时/止损）→ 跑同窗 | Δobjective / Δsharpe / Δmaxdd / **Δ换手** → 该组件贡献 |
| **参数敏感性 sweep** | 在网格上改**一个**参数（持仓数/止损线/均线周期/振幅阈值…）→ 跑一串 | 敏感性曲线：平台 vs 悬崖 vs 单峰；最优/稳健区 |
| **分区间 regime** | 同一策略跑多个子窗（2022/2023/2024/压力月）| 何时有效/失效 |
| **组件隔离 isolate** | 只留一个组件单独跑 | 该组件的独立边际价值 |
| **数据探针 probe** | 读回测持仓/换手/成交时点（结果表或日志）| 机理，非仅指标 |

- 一次实验只改/看**一处**（干净归因）。变体源码存 `study/<family>/variants/<qId>.py`。
- 成交假设不真实（打板/涨停/高换手零滑点）者，发现里**必标 ⚠**，Δ 仅作机理参考。

---

## 6. 问题队列 `study/<family>/questions.json`

排名队列（git 不跟踪）。每项：

```json
{ "id": "q-3", "question": "把 MA10 择时空仓开关去掉，回撤会抬多少？",
  "type": "ablation | sweep | regime | isolate | probe",
  "hypothesis": "MA10 择时贡献了大部分回撤压制，去掉后 maxdd 从 11% 抬到 ~18%",
  "why": "定位低回撤的主因（组件归因）",
  "design": "复制 baseline.py，注释掉 market_ok() 的 MA10 分支，跑 --window train + 分 2022/2023/2024",
  "rank": 5, "status": "queued | active | answered | dropped" }
```

---

## 7. 发现账本 `study/<family>/findings.tsv`

追加式、TAB 分隔、**git 不跟踪**。每个已回答问题一行，9 列：

```
qId	type	component_or_param	metric_delta	window	finding	confidence	flags	description
```

1. `qId`（如 `q-3`）2. `type`（§5）3. 被测组件/参数 4. 关键 Δ（如 `maxdd +0.07 / annual -0.03`）
5. `window`（train/val/2022/…）6. **一句发现**（这实验告诉我们什么）7. `confidence`（high/med/low）
8. `flags`（⚠零滑点高估 / overfit-cliff / regime-specific…）9. 简述（怎么测的）

---

## 8. 写回家族页 `wiki/families/<family>.md`

study **不再产出独立报告页**，而是把理解**写回家族页**（结构见 `wiki-schema.md` §3.3），由分析 agent 逐步充实（不是一次写完）：

- **§1 基类「为什么有效」**：基类归因结论（核心 alpha / 控回撤机器 / 脆弱点），随实验刷新。
- **§2 变体表**：每个被解释的变体一行——`改动 / 来源 study-<qId> / Δobjective / Δsharpe / ΔmaxDD / 结论`。**追加不覆盖**。
- **§6 研究问答（study-log）**：问题 → 结论，逐条追加：
  ```
  - **[Q <qId>]** <问题>（type: ablation|sweep|regime|isolate|probe）
    **→** <一句结论>（Δ…；confidence high/med/low；⚠ flags）溯源 [[study-<qId>]]
  ```
- **§4 待研究**：本次暴露的新问题 / 对 auto-enhance 的启示（§9 反哺）。
- **§3 横评**：**勿手写**——跑 `node utils/wiki-family-build.js` 从 `family:` + 归一化账本重生成。

> 既有 82 篇 `wiki/studies/<id>.md` 为**单策略时代的归档**，保留只读，不再新增。

---

## 9. 知识反哺契约（write-back）

解剖产生的**跨策略洞察**要回填知识库（与 `wiki-schema.md` §9、`enhance-schema.md` §9 一致）：
- **可溯源**：概念页/策略页每条新结论带 `[[<family>]]` 指针。
- **只追加**：概念页只加不改；矛盾只标记留人裁决。
- 有价值的敏感性/归因规律 → 追加到相关 `wiki/concepts/*.md`「观察」，供 auto-enhance 的 ideator 复用。
- `wiki/log.md` 追加：`## [YYYY-MM-DD] study | <family> (<摘要>) → 回填 [[<页>]]`。

---

## 10. 不可违反的原则

- **评测台冻结**：成本/滑点/真实性过滤只读；**2025+ OOS 绝不触碰**（代码硬阻断，绝不设 `JQ_ALLOW_OOS`）。
- **target 不可变**：被解剖策略源码快照 `baseline.py` 一经确定即冻结；实验只在 `variants/` 造变体。
- **一次一处**：一个实验只改/看一处，保证归因干净。
- **真实性红线**：零滑点高估 / 不真实成交必标 ⚠，Δ 不当作可实现结论。
- **无选择压力**：不 keep/discard、不挑「最优变体」当产物——产物是**理解**，不是新策略。（若解剖启发了值得优化的新策略，那是 auto-enhance 的活，另起。）
- **预算**：同 auto-enhance 的 JQ 计费现实（每日免费 60 分钟、`--usage-limit` 上限、并发 2）。
