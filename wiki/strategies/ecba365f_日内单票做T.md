---
postId: ecba365f86232c7d8eebad8cab53ddac
backtestId: 7ea8c4eabf18fa9344cf1ee0f0143ed9
title: 日内单票做T策略
sourceFile: strategies/2026-06-14_日内单票做T策略-ecba365f.py
concepts: [日内做T]
factors:
  选股:
    技术量价: [单票日内高抛低吸]
  仓位: [底仓做T, 分钟级]
ingestedAt: 2026-06-28
codeLines: 291
stats: { annualReturn: 1.692, sharpe: 3.04, maxDrawdown: 0.219, periodLabel: 2026-03 }
---

# 日内单票做T策略

**一句话**：对单只持仓做日内 T+0——盘中分钟级高抛低吸，降低持仓成本（A股 T+1 下的「变相 T+0」）。

## 忠实翻译
**选股池**：单一标的（底仓）。
**仓位分配**：每分钟（`every_bar`）判断日内高低点，在底仓上分批高抛低吸做 T，赚日内波动、摊低成本。
**风控**：日内回转控制；基准沪深 300。回测区间 2026-03 起，代码 291 行。

## 绩效
📊 年化169.2% | 夏普3.04 | 最大回撤21.9% | 回测区间 2026-03 起

## 涉及概念
- [[日内做T]] —— 单票日内回转的代表；多策略组合（如 [[87826299_小市值做T全球ETF]]）常把做T作为子模块。
