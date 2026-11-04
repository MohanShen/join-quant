---
postId: db583cfecee607941b94f9fc268573de
title: 对MACD均线择时策略的改进
sourceFile: strategies/2026-11-05_对MACD均线择时策略的改进-db583cfe.py
concepts: [小市值因子, 择时-均线]
factors:
  选股: [规模价值·小市值]
  择时: [趋势均线]
familyProposal: ~
familyProposalNote: below MIN_SCORE
ingestedAt: 2026-11-04
codeLines: 130
stats: { 绩效未公开: true }
normalized: { epoch: 9, window: "TRAIN 2024", annualReturn: 0.0280, sharpe: -0.03, maxDrawdown: 0.3543, objective: -0.3263, gate: fail }
autoStub: true
---

# 对MACD均线择时策略的改进

**一句话**：⚙ 自动桩页（daily 归一化生成），概念为启发式推断，忠实翻译待 `/ingest-strategy` 补全。

## 绩效
📊 归一化（TRAIN 2024，零滑点）：年化 2.8% | 夏普 -0.03 | 最大回撤 35.4% | objective -0.3263（未过门槛 夏普<1）。自报绩效未公开。

## 涉及概念
- [[小市值因子]]
- [[择时-均线]]

## 备注
- ⚙ **自动桩页**（`autoStub: true`）：概念/因子为源码启发式推断，未做忠实翻译。运行 `/ingest-strategy strategies/2026-11-05_对MACD均线择时策略的改进-db583cfe.py` 可补全并去除该标记。
