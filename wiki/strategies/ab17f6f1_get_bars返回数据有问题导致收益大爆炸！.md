---
postId: ab17f6f13ff914d74c671cea6c326d7f
title: get_bars返回数据有问题导致收益大爆炸！
sourceFile: strategies/2026-11-01_get_bars返回数据有问题导致收益大爆炸-ab17f6f1.py
familyDeclined: true
familyDeclinedBasis: "JQ worked example iterating g.securitys with order_value(security, 24000). Post reports get_bars returning bad data and inflating returns — a data bug report."
concepts: [未分类]
factors:
  选股: [未分类]
familyProposal: ~
familyProposalNote: below MIN_SCORE
ingestedAt: 2026-10-31
codeLines: 60
stats: { 绩效未公开: true }
normalized: { epoch: 9, window: "TRAIN 2024", annualReturn: 0.0945, sharpe: 0.26, maxDrawdown: 0.1459, objective: -0.0514, gate: fail }
autoStub: true
---

# get_bars返回数据有问题导致收益大爆炸！

**一句话**：⚙ 自动桩页（daily 归一化生成），概念为启发式推断，忠实翻译待 `/ingest-strategy` 补全。

## 绩效
📊 归一化（TRAIN 2024，零滑点）：年化 9.4% | 夏普 0.26 | 最大回撤 14.6% | objective -0.0514（未过门槛 夏普<1）。自报绩效未公开。

## 涉及概念
- [[未分类]]

## 备注
- ⚙ **自动桩页**（`autoStub: true`）：概念/因子为源码启发式推断，未做忠实翻译。运行 `/ingest-strategy strategies/2026-11-01_get_bars返回数据有问题导致收益大爆炸-ab17f6f1.py` 可补全并去除该标记。
