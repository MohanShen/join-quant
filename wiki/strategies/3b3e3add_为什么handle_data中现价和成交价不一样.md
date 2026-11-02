---
postId: 3b3e3adde9277defbd0863253d413c31
title: 为什么handle_data中现价和成交价不一样
sourceFile: strategies/2026-11-03_为什么handle_data中现价和成交价不一样-3b3e3add.py
joinquantPost: https://www.joinquant.com/post/joinquant.com/post/9311
concepts: [网格交易]
factors:
  仓位: [网格分档]
familyProposal: ~
familyProposalNote: below MIN_SCORE
ingestedAt: 2026-11-02
codeLines: 54
stats: { 绩效未公开: true }
normalized: { epoch: 9, window: "TRAIN 2024", annualReturn: 0.0963, sharpe: 0.30, maxDrawdown: 0.1129, objective: -0.0166, gate: fail }
autoStub: true
---

# 为什么handle_data中现价和成交价不一样

**一句话**：⚙ 自动桩页（daily 归一化生成），概念为启发式推断，忠实翻译待 `/ingest-strategy` 补全。

## 绩效
📊 归一化（TRAIN 2024，零滑点）：年化 9.6% | 夏普 0.30 | 最大回撤 11.3% | objective -0.0166（未过门槛 夏普<1）。自报绩效未公开。

## 涉及概念
- [[网格交易]]

## 备注
- ⚙ **自动桩页**（`autoStub: true`）：概念/因子为源码启发式推断，未做忠实翻译。运行 `/ingest-strategy strategies/2026-11-03_为什么handle_data中现价和成交价不一样-3b3e3add.py` 可补全并去除该标记。
