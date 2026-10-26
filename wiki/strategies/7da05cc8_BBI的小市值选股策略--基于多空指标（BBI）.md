---
postId: 7da05cc892ce9a80eb2bb079f00b34a5
title: BBI 的小市值选股策略--基于多空指标（BBI）过滤
sourceFile: strategies/2026-10-21_BBI_的小市值选股策略--基于多空指标_BBI_过滤-7da05cc8.py
family: 小市值
joinquantPost: https://www.joinquant.com/post/joinquant.com/post/60630
concepts: [小市值因子]
factors:
  选股: [规模价值·小市值]
  风控: [止损线, 止盈]
familyProposal: ~
familyProposalNote: below MIN_SCORE
ingestedAt: 2026-10-25
codeLines: 420
stats: { 绩效未公开: true }
normalized: { epoch: 9, window: "TRAIN 2024", annualReturn: 1.0400, sharpe: 2.76, maxDrawdown: 0.1388, objective: 0.9012, gate: pass }
autoStub: true
---

# BBI 的小市值选股策略--基于多空指标（BBI）过滤

**一句话**：⚙ 自动桩页（daily 归一化生成），概念为启发式推断，忠实翻译待 `/ingest-strategy` 补全。

## 绩效
📊 归一化（TRAIN 2024，零滑点）：年化 104% | 夏普 2.76 | 最大回撤 13.9% | objective 0.9012（过门槛）。自报绩效未公开。

## 涉及概念
- [[小市值因子]]

## 备注
- ⚙ **自动桩页**（`autoStub: true`）：概念/因子为源码启发式推断，未做忠实翻译。运行 `/ingest-strategy strategies/2026-10-21_BBI_的小市值选股策略--基于多空指标_BBI_过滤-7da05cc8.py` 可补全并去除该标记。
