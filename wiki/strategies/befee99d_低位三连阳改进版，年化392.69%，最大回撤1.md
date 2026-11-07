---
postId: befee99dd015a7b5f019fdac8d0745a3
title: 低位三连阳改进版，年化392.69%，最大回撤18%
sourceFile: strategies/2026-11-07_低位三连阳改进版_年化392_69_最大回撤18-befee99d.py
family: 打板短线
concepts: [小市值因子, 打板与涨停]
factors:
  选股: [规模价值·小市值]
  风控: [止损线, 止盈]
familyProposal: ~
familyProposalNote: below MIN_SCORE
ingestedAt: 2026-11-06
codeLines: 611
stats: { 绩效未公开: true }
normalized: { epoch: 9, window: "TRAIN 2024", annualReturn: -0.3260, sharpe: -0.83, maxDrawdown: 0.5022, objective: -0.8282, gate: fail }
realizabilityFlags: [call-auction-entry]   # static, FREE, never a veto — node utils/realizability-lint.js strategies/2026-11-07_低位三连阳改进版_年化392_69_最大回撤18-befee99d.py
autoStub: true
---

# 低位三连阳改进版，年化392.69%，最大回撤18%

**一句话**：⚙ 自动桩页（daily 归一化生成），概念为启发式推断，忠实翻译待 `/ingest-strategy` 补全。

## 绩效
📊 归一化（TRAIN 2024，零滑点）：年化 -32.6% | 夏普 -0.83 | 最大回撤 50.2% | objective -0.8282（未过门槛 夏普<1）。自报绩效未公开。

## 涉及概念
- [[小市值因子]]
- [[打板与涨停]]

## 备注
- ⚙ **自动桩页**（`autoStub: true`）：概念/因子为源码启发式推断，未做忠实翻译。运行 `/ingest-strategy strategies/2026-11-07_低位三连阳改进版_年化392_69_最大回撤18-befee99d.py` 可补全并去除该标记。
