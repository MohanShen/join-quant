---
postId: 5a5ba567903e1b326697d71ecb7bbc6e
backtestId: 9324c4788c0c2fbec3c0ae50aa99e84e
title: 价值选股与RSRS择时
sourceFile: strategies/2026-05-13_价值选股与RSRS择时-5a5ba567.py
concepts: [多因子模型, 择时-RSRS]
factors:
  选股:
    规模价值: [价值因子选股]
  择时: [RSRS阻力支撑相对强度择时]
  仓位: [等权10只]
ingestedAt: 2026-06-27
codeLines: 173
stats: { annualReturn: 0.345, sharpe: 1.70, maxDrawdown: 0.119, periodLabel: 2018-10 }
---

# 价值选股与RSRS择时

**一句话**：价值因子选股 + RSRS（阻力支撑相对强度）大盘择时——低回撤（11.9%）的「选股 × 择时」组合。

## 忠实翻译
**选股池**：按价值因子选股，持股数 10。
**仓位分配**：等权 10 只。
**择时**：RSRS 指标（参数 N、M）判断大盘多空——信号转弱则减仓/空仓，转强则建仓。
**风控**：基准沪深 300。回测区间 2018-10 起，代码 173 行。

## 绩效
📊 年化34.5% | 夏普1.70 | 最大回撤11.9% | 回测区间 2018-10 起

## 涉及概念
- [[多因子模型]]（价值选股）、[[择时-RSRS]]（RSRS 大盘择时，本库首个 RSRS 成员）。
