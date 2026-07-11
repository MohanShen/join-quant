---
postId: fd5d388d9762e7d8c4ba65810366a7d1
backtestId: 40e97ee2f7bbcd2eebe0309fa700dd92
title: 【五福闹新春】v5.1-拟合ETF池最严厉的父亲
sourceFile: strategies/2026-05-22_五福闹新春_v5_1-拟合ETF池最严厉的父亲-fd5d388d.py
concepts: [ETF轮动, 动量与趋势, 止损模块]
factors:
  选股:
    动量: [动量打分, 安全区间0<score≤5, R²≥0.4]
    技术量价: [均线过滤, 放量过滤]
  风控: [固定止损线0.95, 回撤阈值3%]
  仓位: [全球+中国双池, 满仓单ETF]
ingestedAt: 2026-06-27
codeLines: 1420
stats: { annualReturn: 2.430, sharpe: 6.83, maxDrawdown: 0.171, periodLabel: 2026-04 }
normalized: { epoch: 1, window: "TRAIN 2022-2023", annualReturn: 0.4006, sharpe: 1.48, maxDrawdown: 0.1485, objective: DQ, gate: fail, ranAt: 2026-07-11 }
---

# 【五福闹新春】v5.1-拟合ETF池最严厉的父亲

**一句话**：五福系列 v5.1——全球池 + 中国池合并的 ETF 动量轮动，叠加 R²/均线/放量多重过滤与固定止损。

## 忠实翻译
**选股池**：固定池 = 全球 ETF 池 + 中国 ETF 池（另有动态池机制）；动量打分取 0<score≤5、R²≥0.4，叠加均线（`ma_threshold`）与放量（1.8×）过滤。
**仓位分配**：`holdings_num=1` 满仓动量第 1 名。
**止损**：固定止损（`fixedStopLossThreshold=0.95`，即 -5%）+ 回撤阈值 3%。
**风控**：fund 手续费；回测区间 2026-04 起，代码 1420 行。

## 绩效
📊 年化243.0% | 夏普6.83 | 最大回撤17.1% | 回测区间 2026-04 起

## 涉及概念
- [[ETF轮动]]、[[动量与趋势]]、[[止损模块]] —— 五福系列以「多重过滤 + 固定止损」收敛动量轮动的回撤。
