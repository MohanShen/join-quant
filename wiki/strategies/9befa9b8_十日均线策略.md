---
postId: 9befa9b8dee359408631307f021fed6c
backtestId: 048448df645ff8c2737c7214d3bd4e5c
title: 十日均线策略
sourceFile: strategies/2026-06-08_十日均线策略-9befa9b8.py
concepts: [动量与趋势, 择时-均线]
factors:
  选股:
    动量: [MA10单均线择时]
  仓位: [单标的择时, 满仓/空仓]
ingestedAt: 2026-06-27
codeLines: 47
stats: { annualReturn: 0.209, sharpe: 0.46, maxDrawdown: 0.647, periodLabel: 2015-12 }
normalized: { epoch: 1, window: "TRAIN 2022-2023", annualReturn: -0.0946, sharpe: -0.72, maxDrawdown: 0.2308, objective: DQ, gate: fail, ranAt: 2026-07-11 }
---

# 十日均线策略

**一句话**：中信证券经典「单均线 10 日」择时——价格在 MA10 之上持有、之下空仓。

## 忠实翻译
**选股池**：单一标的（基准上证综指）。
**仓位分配**：上一时点价格低于 10 日均价则空仓卖出，高于则持有。
**风控**：均线即止损；但回撤高达 65%（单标的择时在大熊市仍受重创）。回测区间 2015-12 起，代码 47 行。

## 绩效
📊 年化20.9% | 夏普0.46 | 最大回撤64.7% | 回测区间 2015-12 起

## 涉及概念
- [[动量与趋势]]、[[择时-均线]] —— 单均线择时的回撤短板样本（65%）。
