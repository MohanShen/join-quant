---
postId: a9fd736af7fa3013aade2cc14ff9b71f
title: MACD单因子多头策略
sourceFile: strategies/2026-11-05_MACD单因子多头策略-a9fd736a.py
family: 其他
concepts: [小市值因子]
factors:
  选股: [规模价值·小市值]
  风控: [止损线]
familyProposal: 向导式低波价值
familyProposalScore: 0.901
ingestedAt: 2026-11-04
codeLines: 449
stats: { 绩效未公开: true }
normalized: { epoch: 9, window: "TRAIN 2024", annualReturn: -0.0015, sharpe: -0.11, maxDrawdown: 0.2514, objective: -0.2529, gate: fail }
autoStub: true
---

# MACD单因子多头策略

**一句话**：⚙ 自动桩页（daily 归一化生成），概念为启发式推断，忠实翻译待 `/ingest-strategy` 补全。

## 绩效
📊 归一化（TRAIN 2024，零滑点）：年化 -0.1% | 夏普 -0.11 | 最大回撤 25.1% | objective -0.2529（未过门槛 夏普<1）。自报绩效未公开。

## 涉及概念
- [[小市值因子]]

## 备注
- ⚙ **自动桩页**（`autoStub: true`）：概念/因子为源码启发式推断，未做忠实翻译。运行 `/ingest-strategy strategies/2026-11-05_MACD单因子多头策略-a9fd736a.py` 可补全并去除该标记。
