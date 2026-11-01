---
postId: bdd6aa9fa28f46952dbacb2448a6f3a2
title: 网格交易策略修改
sourceFile: strategies/2026-11-01_网格交易策略修改-bdd6aa9f.py
family: 网格
joinquantPost: https://www.joinquant.com/post/joinquant.com/post/539
concepts: [网格交易]
factors:
  风控: [止损线]
  仓位: [网格分档]
familyProposal: 网格
familyProposalScore: 0.8176
ingestedAt: 2026-11-01
codeLines: 198
stats: { 绩效未公开: true }
normalized: { epoch: 9, window: "TRAIN 2024", annualReturn: 0.1414, sharpe: 0.26, maxDrawdown: 0.4231, objective: -0.2817, gate: fail }
autoStub: true
---

# 网格交易策略修改

**一句话**：⚙ 自动桩页（daily 归一化生成），概念为启发式推断，忠实翻译待 `/ingest-strategy` 补全。

## 绩效
📊 归一化（TRAIN 2024，零滑点）：年化 14.1% | 夏普 0.26 | 最大回撤 42.3% | objective -0.2817（未过门槛 夏普<1）。自报绩效未公开。

## 涉及概念
- [[网格交易]]

## 备注
- ⚙ **自动桩页**（`autoStub: true`）：概念/因子为源码启发式推断，未做忠实翻译。运行 `/ingest-strategy strategies/2026-11-01_网格交易策略修改-bdd6aa9f.py` 可补全并去除该标记。
