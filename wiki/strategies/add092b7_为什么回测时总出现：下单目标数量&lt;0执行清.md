---
postId: add092b7c12cc5a4b39b2e33d2bf9130
title: 为什么回测时总出现：下单目标数量 &lt; 0: 执行清仓处理
sourceFile: strategies/2026-11-03_为什么回测时总出现_下单目标数量_lt_0_执行清仓处理-add092b7.py
family: 其他
joinquantPost: https://www.joinquant.com/post/joinquant.com/post/9311
concepts: [网格交易]
factors:
  仓位: [网格分档]
familyProposal: ~
familyProposalNote: below MIN_SCORE
ingestedAt: 2026-11-02
codeLines: 58
stats: { 绩效未公开: true }
normalized: { epoch: 9, window: "TRAIN 2024", annualReturn: -0.0198, sharpe: -5.24, maxDrawdown: 0.0206, objective: -0.0404, gate: fail }
autoStub: true
---

# 为什么回测时总出现：下单目标数量 &lt; 0: 执行清仓处理

**一句话**：⚙ 自动桩页（daily 归一化生成），概念为启发式推断，忠实翻译待 `/ingest-strategy` 补全。

## 绩效
📊 归一化（TRAIN 2024，零滑点）：年化 -2% | 夏普 -5.24 | 最大回撤 2.1% | objective -0.0404（未过门槛 夏普<1）。自报绩效未公开。

## 涉及概念
- [[网格交易]]

## 备注
- ⚙ **自动桩页**（`autoStub: true`）：概念/因子为源码启发式推断，未做忠实翻译。运行 `/ingest-strategy strategies/2026-11-03_为什么回测时总出现_下单目标数量_lt_0_执行清仓处理-add092b7.py` 可补全并去除该标记。
