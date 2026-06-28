---
postId: 23b0cbdc6ab1f0fb90dfbaed43c09d5d
backtestId: b33a29307a1392db52c5cd52d41b3bec
title: 【经典策略系列】之周规则交易策略（使用分级移动止盈、移动止盈方法，以及新api--run_daily等的用法）
sourceFile: strategies/2026-05-28_经典策略系列_之周规则交易策略_使用分级移动止盈_移动止盈方法_以及新api--run_daily等的用法-23b0cbdc.py
concepts: [择时-均线, 止损模块]
factors:
  选股:
    动量: [周规则交易信号]
  风控: [分级移动止盈]
  仓位: [周规则]
ingestedAt: 2026-06-28
codeLines: 146
stats: { annualReturn: null, sharpe: 0.79945214036585, maxDrawdown: 0.45314249108084, periodLabel: "2015-12" }
---

# 【经典策略系列】之周规则交易策略（使用分级移动止盈、移动止盈方法，以及新api--run_daily等的用法）

**一句话**：经典「周规则交易」+ 分级移动止盈（新 run_daily API 示例）。

## 忠实翻译
**选股池/逻辑**：见 frontmatter `factors`；经典「周规则交易」+ 分级移动止盈（新 run_daily API 示例）。
**风控**：见 `factors.风控`（如有）。回测区间 2015-12 起，代码 146 行。

## 绩效
📊 年化— | 夏普0.80 | 最大回撤45% | 回测区间 2015-12 起

## 涉及概念
- [[择时-均线]]、[[止损模块]]
