---
postId: d5040aa00b1168d9c0926f68ba673b8d
title: 多策略组合系统：ETF轮动 + 小市值增强
sourceFile: strategies/2026-10-26_多策略组合系统_ETF轮动_小市值增强-d5040aa0.py
concepts: [小市值因子, ETF轮动, 动量与趋势, 多策略组合]
factors:
  选股: [规模价值·小市值, ETF动量, 动量]
  风控: [止损线]
familyProposal: 多因子ML
familyProposalScore: 0.4575
ingestedAt: 2026-10-26
codeLines: 747
stats: { 绩效未公开: true }
normalized: { epoch: 9, window: "TRAIN 2024", annualReturn: 1.6932, sharpe: 5.56, maxDrawdown: 0.0965, objective: 1.5967, gate: pass }
autoStub: true
---

# 多策略组合系统：ETF轮动 + 小市值增强

**一句话**：⚙ 自动桩页（daily 归一化生成），概念为启发式推断，忠实翻译待 `/ingest-strategy` 补全。

## 绩效
📊 归一化（TRAIN 2024，零滑点）：年化 169.3% | 夏普 5.56 | 最大回撤 9.7% | objective 1.5967（过门槛）。自报绩效未公开。

## 涉及概念
- [[小市值因子]]
- [[ETF轮动]]
- [[动量与趋势]]
- [[多策略组合]]

## 备注
- ⚙ **自动桩页**（`autoStub: true`）：概念/因子为源码启发式推断，未做忠实翻译。运行 `/ingest-strategy strategies/2026-10-26_多策略组合系统_ETF轮动_小市值增强-d5040aa0.py` 可补全并去除该标记。
