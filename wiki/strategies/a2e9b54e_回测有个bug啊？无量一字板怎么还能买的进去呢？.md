---
postId: a2e9b54e9bd8f526fe28934330cb5077
title: 回测有个bug啊？无量一字板怎么还能买的进去呢？
sourceFile: strategies/2026-11-01_回测有个bug啊_无量一字板怎么还能买的进去呢-a2e9b54e.py
familyDeclined: true
familyDeclinedBasis: "38 lines: order_value(security, cash) on one symbol, with the sell commented out. Post asks how a sealed 一字板 could be filled — a fill-semantics bug report."
concepts: [未分类]
factors:
  选股: [未分类]
familyProposal: ~
familyProposalNote: below MIN_SCORE
ingestedAt: 2026-10-31
codeLines: 38
stats: { 绩效未公开: true }
normalized: { epoch: 9, window: "TRAIN 2024", annualReturn: -0.3499, sharpe: -0.41, maxDrawdown: 0.7744, objective: -1.1243, gate: fail }
autoStub: true
---

# 回测有个bug啊？无量一字板怎么还能买的进去呢？

**一句话**：⚙ 自动桩页（daily 归一化生成），概念为启发式推断，忠实翻译待 `/ingest-strategy` 补全。

## 绩效
📊 归一化（TRAIN 2024，零滑点）：年化 -35% | 夏普 -0.41 | 最大回撤 77.4% | objective -1.1243（未过门槛 夏普<1）。自报绩效未公开。

## 涉及概念
- [[未分类]]

## 备注
- ⚙ **自动桩页**（`autoStub: true`）：概念/因子为源码启发式推断，未做忠实翻译。运行 `/ingest-strategy strategies/2026-11-01_回测有个bug啊_无量一字板怎么还能买的进去呢-a2e9b54e.py` 可补全并去除该标记。
