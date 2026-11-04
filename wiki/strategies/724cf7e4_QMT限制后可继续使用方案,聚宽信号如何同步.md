---
postId: 724cf7e414044e4ca05e10c5075763d4
title: Q MT限制后可继续使用方案,聚宽信号如何同步
sourceFile: strategies/2026-11-05_Q_MT限制后可继续使用方案_聚宽信号如何同步-724cf7e4.py
concepts: [小市值因子, 打板与涨停]
factors:
  选股: [规模价值·小市值]
  风控: [止盈]
familyProposal: ~
familyProposalNote: below MIN_SCORE
ingestedAt: 2026-11-04
codeLines: 746
stats: { 绩效未公开: true }
normalized: { epoch: 9, window: "TRAIN 2024", annualReturn: 0.8688, sharpe: 1.53, maxDrawdown: 0.5394, objective: 0.3294, gate: pass }
realizabilityFlags: [call-auction-entry]   # static, FREE, never a veto — node utils/realizability-lint.js strategies/2026-11-05_Q_MT限制后可继续使用方案_聚宽信号如何同步-724cf7e4.py
autoStub: true
---

# Q MT限制后可继续使用方案,聚宽信号如何同步

**一句话**：⚙ 自动桩页（daily 归一化生成），概念为启发式推断，忠实翻译待 `/ingest-strategy` 补全。

## 绩效
📊 归一化（TRAIN 2024，零滑点）：年化 86.9% | 夏普 1.53 | 最大回撤 53.9% | objective 0.3294（过门槛）。自报绩效未公开。

## 涉及概念
- [[小市值因子]]
- [[打板与涨停]]

## 备注
- ⚙ **自动桩页**（`autoStub: true`）：概念/因子为源码启发式推断，未做忠实翻译。运行 `/ingest-strategy strategies/2026-11-05_Q_MT限制后可继续使用方案_聚宽信号如何同步-724cf7e4.py` 可补全并去除该标记。
