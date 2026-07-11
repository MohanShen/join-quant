---
postId: f9ca1d2e1a810511ee9915bcb85dfbe9
backtestId: 2eea050c7cdd7fcb39f3bbf36bf4332b
title: 【量化课堂】机器学习多因子策略
sourceFile: strategies/2026-05-14_量化课堂_机器学习多因子策略-f9ca1d2e.py
concepts: [多因子模型]
factors:
  选股:
    质量基本面: [SVR回归市值的残差因子(被低估)]
  仓位: [等权10只]
ingestedAt: 2026-06-27
codeLines: 97
stats: { annualReturn: 0.588, sharpe: 2.13, maxDrawdown: 0.248, periodLabel: 2017-12 }
normalized: { epoch: 1, window: "TRAIN 2022-2023", annualReturn: 0.1227, sharpe: 0.47, maxDrawdown: 0.1932, objective: DQ, gate: fail, ranAt: 2026-07-11 }
---

# 【量化课堂】机器学习多因子策略

**一句话**：用 SVR（支持向量回归）以财务因子拟合 log 市值，取「实际市值远低于预测」的残差最小 10 只（被低估）持有。

## 忠实翻译
**选股池**：查询市值与多项财务因子（总资产-总负债等），用 SVR 回归 log 市值得到拟合值，计算残差因子 = 实际 - 预测，按残差升序取前 10（被市场低估的标的）。
**仓位分配**：等权买入 10 只，定期 `trade` 调仓。
**风控**：无显式止损。基准上证综指。回测区间 2017-12 起，代码 97 行。

## 绩效
📊 年化58.8% | 夏普2.13 | 最大回撤24.8% | 回测区间 2017-12 起

## 涉及概念
- [[多因子模型]] —— 用 ML 回归构造「估值残差」因子的教学范例。
