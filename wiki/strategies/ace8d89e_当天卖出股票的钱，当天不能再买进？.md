---
postId: ace8d89ecd7fc2a3fe08b274c6f50f1d
title: 当天卖出股票的钱，当天不能再买进？
sourceFile: strategies/2026-11-03_当天卖出股票的钱_当天不能再买进-ace8d89e.py
familyDeclined: true
familyDeclinedBasis: "23 lines: order_target then order_value on hardcoded 000001.XSHE to demonstrate that T+0 sale proceeds are not reusable same-day. A platform-semantics question."
concepts: [未分类]
factors:
  选股: [未分类]
familyProposal: ~
familyProposalNote: below MIN_SCORE
ingestedAt: 2026-11-02
codeLines: 23
stats: { 绩效未公开: true }
normalized: { epoch: 9, window: "TRAIN 2024", annualReturn: 0.0593, sharpe: 0.09, maxDrawdown: 0.2014, objective: -0.1421, gate: fail }
autoStub: true
---

# 当天卖出股票的钱，当天不能再买进？

**一句话**：⚙ 自动桩页（daily 归一化生成），概念为启发式推断，忠实翻译待 `/ingest-strategy` 补全。

## 绩效
📊 归一化（TRAIN 2024，零滑点）：年化 5.9% | 夏普 0.09 | 最大回撤 20.1% | objective -0.1421（未过门槛 夏普<1）。自报绩效未公开。

## 涉及概念
- [[未分类]]

## 备注
- ⚙ **自动桩页**（`autoStub: true`）：概念/因子为源码启发式推断，未做忠实翻译。运行 `/ingest-strategy strategies/2026-11-03_当天卖出股票的钱_当天不能再买进-ace8d89e.py` 可补全并去除该标记。
