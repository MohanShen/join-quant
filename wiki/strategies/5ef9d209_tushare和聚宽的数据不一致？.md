---
postId: 5ef9d209382bdd8f2523dd29ab37704b
title: tushare和聚宽的数据不一致？
sourceFile: strategies/2026-11-04_tushare和聚宽的数据不一致-5ef9d209.py
concepts: [ETF轮动]
factors:
  选股: [ETF动量]
familyProposal: ~
familyProposalNote: below MIN_SCORE
ingestedAt: 2026-11-03
codeLines: 19
stats: { 绩效未公开: true }
normalized: { epoch: 9, window: "TRAIN 2024", annualReturn: 0.0350, sharpe: -0.09, maxDrawdown: 0.0277, objective: 0.0073, gate: fail }
autoStub: true
---

# tushare和聚宽的数据不一致？

**一句话**：⚙ 自动桩页（daily 归一化生成），概念为启发式推断，忠实翻译待 `/ingest-strategy` 补全。

## 绩效
📊 归一化（TRAIN 2024，零滑点）：年化 3.5% | 夏普 -0.09 | 最大回撤 2.8% | objective 0.0073（未过门槛 夏普<1）。自报绩效未公开。

## 涉及概念
- [[ETF轮动]]

## 备注
- ⚙ **自动桩页**（`autoStub: true`）：概念/因子为源码启发式推断，未做忠实翻译。运行 `/ingest-strategy strategies/2026-11-04_tushare和聚宽的数据不一致-5ef9d209.py` 可补全并去除该标记。
