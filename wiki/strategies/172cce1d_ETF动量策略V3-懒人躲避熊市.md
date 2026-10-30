---
postId: 172cce1d195f92113d0ea7da087d92af
title: ETF动量策略V3-懒人躲避熊市
sourceFile: strategies/2026-10-30_ETF动量策略V3-懒人躲避熊市-172cce1d.py
family: 其他
concepts: [ETF轮动, 动量与趋势]
factors:
  选股: [ETF动量, 动量]
  风控: [止损线]
familyProposal: ~
familyProposalNote: below MIN_SCORE
ingestedAt: 2026-10-30
codeLines: 509
stats: { 绩效未公开: true }
normalized: { epoch: 9, window: "TRAIN 2024", annualReturn: -0.1366, sharpe: -0.73, maxDrawdown: 0.2425, objective: -0.3791, gate: fail }
autoStub: true
---

# ETF动量策略V3-懒人躲避熊市

**一句话**：⚙ 自动桩页（daily 归一化生成），概念为启发式推断，忠实翻译待 `/ingest-strategy` 补全。

## 绩效
📊 归一化（TRAIN 2024，零滑点）：年化 -13.7% | 夏普 -0.73 | 最大回撤 24.3% | objective -0.3791（未过门槛 夏普<1）。自报绩效未公开。

## 涉及概念
- [[ETF轮动]]
- [[动量与趋势]]

## 备注
- ⚙ **自动桩页**（`autoStub: true`）：概念/因子为源码启发式推断，未做忠实翻译。运行 `/ingest-strategy strategies/2026-10-30_ETF动量策略V3-懒人躲避熊市-172cce1d.py` 可补全并去除该标记。
