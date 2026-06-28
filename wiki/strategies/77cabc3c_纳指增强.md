---
postId: 77cabc3c180e77700dc170c7fec07907
backtestId: fc1782f0a5a3a5e1182ec36721253377
title: 挑战纳指增强（更新）
sourceFile: strategies/2026-06-02_挑战纳指增强_更新-77cabc3c.py
concepts: [多因子模型, ETF轮动, 止损模块]
factors:
  选股:
    动量: [纳指ETF增强信号]
  风控: [止损50%]
  仓位: [纳指ETF100基准]
ingestedAt: 2026-06-28
codeLines: 118
stats: { annualReturn: 0.27196898150394, sharpe: 1.1293613433845, maxDrawdown: 0.23003166482713, periodLabel: "2024-12" }
---

# 挑战纳指增强（更新）

**一句话**：纳指 ETF（513100）增强策略（基准纳指100，带止损）。

## 忠实翻译
**选股池/逻辑**：见 frontmatter `factors`；纳指 ETF（513100）增强策略（基准纳指100，带止损）。
**风控**：见 `factors.风控`（如有）。回测区间 2024-12 起，代码 118 行。

## 绩效
📊 年化27% | 夏普1.13 | 最大回撤23% | 回测区间 2024-12 起

## 涉及概念
- [[多因子模型]]、[[ETF轮动]]、[[止损模块]]
