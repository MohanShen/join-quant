---
postId: 2768beaa9eaa6abe494378db218202b1
backtestId: 3a8ca7dc979cf3f0b91ea68e05d26c9c
title: 终极优化-ETF核心资产轮动策略
sourceFile: strategies/2026-05-17_终极优化-ETF核心资产轮动策略-2768beaa.py
concepts: [ETF轮动, 动量与趋势, 止损模块]
factors:
  选股:
    动量: [多周期动量打分(均值3/5/10·diff3/26)]
  择时: [周移动盈亏空仓信号]
  风控: [止损]
  仓位: [满仓单ETF, 每日轮动, 空仓5天冷却]
ingestedAt: 2026-06-27
codeLines: 223
stats: { annualReturn: 0.435, sharpe: 1.57, maxDrawdown: 0.306, periodLabel: 2025-07 }
normalized: { epoch: 1, window: "TRAIN 2022-2023", annualReturn: 0.2850, sharpe: 1.62, maxDrawdown: 0.1136, objective: DQ, gate: fail, ranAt: 2026-07-11 }
---

# 终极优化-ETF核心资产轮动策略

**一句话**：核心资产 ETF 的多周期动量轮动，叠加周盈亏空仓信号与止损。

## 忠实翻译
**选股池**：核心资产 ETF 池（黄金/创业板等），用多周期（均值 3/5/10、差分 3/26）综合动量打分。
**仓位分配**：每日 9:30，取动量第 1 名满仓；触发周移动盈亏信号后空仓 5 天冷却。
**止损**：`stop_loss` 检查触发清仓；分数<0 空仓。
**风控**：滑点 0；手续费佣金万 2、min 5（fund）；基准沪深 300。回测区间 2025-07 起，代码 223 行。

## 绩效
📊 年化43.5% | 夏普1.57 | 最大回撤30.6% | 回测区间 2025-07 起

## 涉及概念
- [[ETF轮动]]、[[动量与趋势]]（多周期动量）、[[止损模块]]（止损 + 空仓冷却）。
