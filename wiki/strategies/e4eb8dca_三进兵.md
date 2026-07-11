---
postId: e4eb8dcafd7cb1b5964cf26fbcac8f59
backtestId: 3bb88ef38387f723e4b780586cbbdb99
title: 【策略研发】三进兵策略
sourceFile: strategies/2026-06-06_策略研发_三进兵策略-e4eb8dca.py
concepts: [动量与趋势, 择时-均线, 止损模块]
factors:
  选股:
    动量: [三EMA均线组合(三进兵)]
  风控: [收盘跌破中均线止损]
  仓位: [趋势持有]
ingestedAt: 2026-06-28
codeLines: 177
stats: { annualReturn: 0.21, sharpe: 1.1, maxDrawdown: 0.09, periodLabel: 2019-01 }
normalized: { epoch: 1, window: "TRAIN 2022-2023", annualReturn: 0.0000, sharpe: -0.49, maxDrawdown: 0.0900, objective: DQ, gate: fail, ranAt: 2026-07-11 }
---

# 【策略研发】三进兵策略

**一句话**：三 EMA 均线组合（三进兵）基础版。

## 忠实翻译
**选股池/逻辑**：见 frontmatter `factors`；三 EMA 均线组合（三进兵）基础版。
**风控**：见 `factors.风控`。
**风控说明**：回测区间 2019-01 起，代码 177 行。

## 绩效
📊 年化21.0% | 夏普1.1 | 最大回撤9% | 回测区间 2019-01 起

## 涉及概念
- [[动量与趋势]]、[[择时-均线]]、[[止损模块]]
