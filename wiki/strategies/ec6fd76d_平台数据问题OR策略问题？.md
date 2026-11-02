---
postId: ec6fd76ded67745d4ea9cc863c893dd0
title: 平台数据问题 OR 策略问题？
sourceFile: strategies/2026-11-02_平台数据问题_OR_策略问题-ec6fd76d.py
family: 其他
concepts: [未分类]
factors:
  选股: [未分类]
familyProposal: ~
familyProposalNote: below MIN_SCORE
ingestedAt: 2026-11-02
codeLines: 77
stats: { 绩效未公开: true }
normalized: { epoch: 9, window: "TRAIN 2024", annualReturn: -0.0920, sharpe: -0.62, maxDrawdown: 0.1940, objective: -0.286, gate: fail }
autoStub: true
---

# 平台数据问题 OR 策略问题？

**一句话**：⚙ 自动桩页（daily 归一化生成），概念为启发式推断，忠实翻译待 `/ingest-strategy` 补全。

## 绩效
📊 归一化（TRAIN 2024，零滑点）：年化 -9.2% | 夏普 -0.62 | 最大回撤 19.4% | objective -0.286（未过门槛 夏普<1）。自报绩效未公开。

## 涉及概念
- [[未分类]]

## 备注
- ⚙ **自动桩页**（`autoStub: true`）：概念/因子为源码启发式推断，未做忠实翻译。运行 `/ingest-strategy strategies/2026-11-02_平台数据问题_OR_策略问题-ec6fd76d.py` 可补全并去除该标记。
