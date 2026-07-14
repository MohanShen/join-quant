---
expId: arc3-etf-rotation (jul12-018..021)
branch: research/jul12
ideaId: Arc-3（诚实流动跨资产 ETF 载体探索）
baseExpId: jul12-018（13-ETF 跨资产 20日动量轮动 baseline）
hypothesis: 一个诚实流动的 13-ETF 跨资产动量轮动基线，能在 2022-23 TRAIN 上靠跨资产分散（国债/黄金/海外避险）把回撤压到低位、并用动量/反转提取正收益过夏普门槛
reasoning: Arc-1（日内剥头皮）过门槛但极端换手/零滑点高估，Arc-2（裸微盘）回撤=不可约减系统性 beta；转向诚实流动、跨资产分散的 ETF 载体，期望换手温和、真实可实现，且跨资产 haven 提供低回撤
sourceRefs: [[[ETF轮动]], [[动量与趋势]], [[均值回归]]]
mutation: 在 13-ETF 跨资产动量轮动基线上分别改动量回看周期(20→60d) / 加国债切换 / 反向为反转(买最弱)
iterations:
  - { step: 1, exp: jul12-018, change: "baseline 13-ETF 跨资产 20日动量轮动", train_objective: -0.1917, gate: fail, note: "ann-3.05/dd16.12/sharpe-0.45 净亏 BEST(仍DQ)" }
  - { step: 2, exp: jul12-019, change: "+20日国债切换", train_objective: -0.2027, gate: fail, note: "ann-3.57/dd16.70/sharpe-0.47" }
  - { step: 3, exp: jul12-020, change: "动量回看 20→60日", train_objective: -0.3710, gate: fail, note: "ann-11.70/dd25.40/sharpe-1.22 放慢反而更差" }
  - { step: 4, exp: jul12-021, change: "反向为反转(买20日最弱)", train_objective: -0.3705, gate: fail, note: "ann-6.74/dd30.31/sharpe-0.56 回撤最差" }
results:
  train:   { annualReturn: -0.0305, sharpe: -0.45, maxDrawdown: 0.1612, objective: -0.1917, note: "最佳 artifact jul12-018，净负、仍 DQ" }
  val:     { note: "未跑——从未过 TRAIN 门槛，不定稿、不碰 VAL" }
status: negative（KB-only，无 results.tsv 行、无 validated_strategies 归档）
confirmed: false
flags: [DQ-all, net-negative, never-finalized, honestly-liquid(换手温和、非零滑点高估重灾区)]
ranAt: 2026-07-14
---

# Arc-3 负结果：跨资产 ETF 动量/反转在 2022-23 无 edge

**论点（thesis）**：一个**诚实流动**的 13-ETF 跨资产动量轮动基线，在 2022 熊 + 2023 震荡的 TRAIN 窗口是**净负**的（年化 −3.05%、DQ）。跨资产分散（国债/黄金/海外 haven）**确实交付了本纪元最低的基线回撤 16.12%**——**风险轴 work**——但该 universe 在整个 TRAIN 处于**净 drawdown**，**动量与反转都提取不出正收益**。从未过门槛、从未定稿、从未碰 VAL。最佳 artifact 为 jul12-018（objective −0.1917，仍 DQ）。

> 记账定位：**KB-only 负结果**（Arc-3 无任何过门槛/定稿版本），**不占 `research/results.tsv` 行、不归档 `validated_strategies/`**。此页固化「此方向在本窗口不成立」的知识。⚠ 注意与 Arc-1/2 不同：本族**诚实流动、换手温和**，**不是零滑点高估的重灾区**——它的 DQ 是**真·无 edge**，而非成本假设失真。

## 排行榜（全 DQ · 净负 · TRAIN 2022-01-01…2023-12-31 · objective=年化−回撤 · gate 夏普≥2.5）

| 变体 | objective | 年化 | 最大回撤 | 夏普 | gate |
|------|-----------|------|----------|------|------|
| [[jul12-018]] 20日动量 baseline **BEST** | **−0.1917** | −3.05% | 16.12% | −0.45 | ❌ DQ |
| [[jul12-019]] +20日国债切换 | −0.2027 | −3.57% | 16.70% | −0.47 | ❌ DQ |
| [[jul12-021]] 反转(买20日最弱) | −0.3705 | −6.74% | 30.31% | −0.56 | ❌ DQ |
| [[jul12-020]] 60日动量 | −0.3710 | −11.70% | 25.40% | −1.22 | ❌ DQ |

## 结论：动量与反转两向皆无 edge

- **动量与反转都失败**：universe 整段 TRAIN 净 drawdown，方向暴露无处藏身。
- **动量排序 faint-but-slightly-positive**：20日（[[jul12-018]]）是最不差的一档，winners > losers（买强于买弱）——排序里还残留一丝正向信号，但绝对收益仍负，不足以过门槛。
- **放慢回看使每轴更差**：动量回看 20→60日（[[jul12-020]]）年化从 −3.05% 恶化到 −11.70%——**放慢反而更糟**，说明该窗口的 regime 是**动量反转/均值回归**性质（慢趋势被证伪），而非单纯 whipsaw 噪声。
- **买 losers 更差且炸回撤**：简单反转（买 20日最弱，[[jul12-021]]）不但收益更负（−6.74%），还把回撤从 16% 吹到 **30.3%**——反转在此窗口既不赚钱又放大尾部。
- **风险轴 work、收益轴不 work**：跨资产分散真实压住了回撤（16.12%，本纪元最低基线回撤），但**没有正回报与之配对**——低回撤 × 净负收益 = objective 仍深 DQ。

## 回填指针（§9）
- [[ETF轮动]]（待研究）：统一 TRAIN 2022-23 下诚实流动 13-ETF 跨资产动量轮动净亏（年化 −3.05% DQ），edge 高度 regime 依赖（[[jul12-018]]）。
- [[动量与趋势]]（观察）：跨资产 ETF 动量在 2022熊/2023震荡 ANTI-predictive，放慢回看每轴更差（[[jul12-020]]）。
- [[均值回归]]（观察）：简单反转也失败且回撤最差 30.3%，两向皆无 edge（[[jul12-021]]）。
