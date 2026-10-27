---
postId: 004aca1c2b4beba715adaf31885c4c16
title: 重研可SHI盘的打板策略
sourceFile: strategies/2026-10-26_重研可SHI盘的打板策略-004aca1c.py
family: 打板短线
concepts: [小市值因子, 打板与涨停, 择时-均线]
factors:
  选股: [规模价值·小市值]
  择时: [趋势均线]
  风控: [止损线, 止盈]
familyProposal: ~
familyProposalNote: below MIN_SCORE
ingestedAt: 2026-10-26
codeLines: 5070
stats: { 绩效未公开: true }
normalized: { epoch: 9, window: "TRAIN 2024", annualReturn: 1.3009, sharpe: 3.29, maxDrawdown: 0.2316, objective: 1.0693, gate: pass }
realizabilityFlags: [call-auction-entry]   # static, FREE, never a veto — node utils/realizability-lint.js strategies/2026-10-26_重研可SHI盘的打板策略-004aca1c.py
autoStub: true
---

# 重研可SHI盘的打板策略

**一句话**：⚙ 自动桩页（daily 归一化生成），概念为启发式推断，忠实翻译待 `/ingest-strategy` 补全。

## 绩效
📊 归一化（TRAIN 2024，零滑点）：年化 130.1% | 夏普 3.29 | 最大回撤 23.2% | objective 1.0693（过门槛）。自报绩效未公开。

## 涉及概念
- [[小市值因子]]
- [[打板与涨停]]
- [[择时-均线]]

## 备注
- ⚙ **自动桩页**（`autoStub: true`）：概念/因子为源码启发式推断，未做忠实翻译。运行 `/ingest-strategy strategies/2026-10-26_重研可SHI盘的打板策略-004aca1c.py` 可补全并去除该标记。
