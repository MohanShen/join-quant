---
postId: 75df4f9ec84338a71b8d00ba615f0379
title: 自用做t策略 自定义标的
sourceFile: strategies/2026-11-07_自用做t策略_自定义标的-75df4f9e.py
joinquantPost: https://www.joinquant.com/post/joinquant.com/post/73551
concepts: [日内做T]
factors:
  风控: [止损线, 止盈]
familyProposal: ~
familyProposalNote: below MIN_SCORE
ingestedAt: 2026-11-06
codeLines: 432
stats: { 绩效未公开: true }
normalized: { epoch: 9, window: "TRAIN 2024", annualReturn: 0.0061, sharpe: -1.10, maxDrawdown: 0.0236, objective: -0.0175, gate: fail }
autoStub: true
---

# 自用做t策略 自定义标的

**一句话**：⚙ 自动桩页（daily 归一化生成），概念为启发式推断，忠实翻译待 `/ingest-strategy` 补全。

## 绩效
📊 归一化（TRAIN 2024，零滑点）：年化 0.6% | 夏普 -1.10 | 最大回撤 2.4% | objective -0.0175（未过门槛 夏普<1）。自报绩效未公开。

## 涉及概念
- [[日内做T]]

## 备注
- ⚙ **自动桩页**（`autoStub: true`）：概念/因子为源码启发式推断，未做忠实翻译。运行 `/ingest-strategy strategies/2026-11-07_自用做t策略_自定义标的-75df4f9e.py` 可补全并去除该标记。
