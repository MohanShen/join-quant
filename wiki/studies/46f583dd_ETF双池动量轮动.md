---
studyId: 46f583dd_ETF双池动量轮动
target: strategies/2026-05-23_近4个月狂揽62_六年11倍_ETF双池动量轮动-46f583dd.py
targetRefs: [[46f583dd_ETF双池动量轮动]], [[ETF轮动]], [[动量与趋势]]
harness: research/harness.md（冻结成本；窗口 2022–2024，2025 OOS 禁用）
startedAt: 2026-07-16
status: done
---

# 解剖报告：46f583dd_ETF双池动量轮动（DQ — 为什么不行）

## 一句话结论
ETF 双池动量轮动（动量打分安全区间 + 放量过滤 + 止损/放量卖出、双池）。normalize train 2022-2023 **Sharpe 仅 0.34 → DQ**（远不达门槛；概念页横评 14%/31% DD）。

## 为什么不过门槛（DQ 归因）
- 动量轮动 regime-dependent（[[ETF轮动]] 核心结论）；冻结 2022-23 非趋势窗动量 whipsaw，双池/放量过滤不减 regime 依赖 → 高回撤（~31%）、Sharpe 0.34。
- 头条「六年11倍/近4个月62%」是含牛市长窗 + 短窗爆发产物；截到冻结窗即塌。

## 机理与真实性
归因基于 normalize train Sharpe 0.34 + [[ETF轮动]] 家族机理；未独立重跑（清晰家族迁移，节省预算）。confidence=med。

## 待研究 / 反哺 auto-research
又一个 ETF 动量轮动 DQ 数据点（且是低 Sharpe/高 DD 一档）。
