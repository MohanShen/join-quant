---
postId: 15c36e0ce892a62b264d518d2aa5df31
backtestId: 12ef917dcc3f9cd5a610d0efb64f1068
title: etf基金溢价-改进版-高收益低回撤-速度已最优
sourceFile: strategies/2026-06-01_etf基金溢价-改进版-高收益低回撤-速度已最优-15c36e0c.py
concepts: [ETF轮动]
factors:
  选股:
    规模价值: [折价率(取折价<0)]
  风控: [无]
  仓位: [折价ETF轮动]
ingestedAt: 2026-06-27
codeLines: 78
stats: { annualReturn: 0.593, sharpe: 2.32, maxDrawdown: 0.176, periodLabel: 2021-06 }
normalized: { epoch: 1, window: "TRAIN 2022-2023", annualReturn: 1.7788, sharpe: 8.87, maxDrawdown: 0.2146, objective: 1.5642, gate: pass, ranAt: 2026-07-11 }
---

# etf基金溢价-改进版-高收益低回撤-速度已最优

**一句话**：[[edd94ebc_ETF溢价回撤]] 的同族精简版——按折价率排序买入折价 ETF。

## 忠实翻译
**选股池**：全市场 ETF，盘前计算溢价=（最新价/单位净值-1）。
**仓位分配**：9:20 盘前/9:30 开盘，按溢价升序取折价<0 的若干只轮动，卖出脱离目标池者。
**止损**：无。
**风控**：手续费佣金万 2.5、min 0（fund）；基准沪深 300。回测区间 2021-06 起，代码 78 行。

## 绩效
📊 年化59.3% | 夏普2.32 | 最大回撤17.6% | 回测区间 2021-06 起

## 涉及概念
- [[ETF轮动]] —— 折价率轮动，与 [[edd94ebc_ETF溢价回撤]] 同族（区间更长，绩效正常）。
