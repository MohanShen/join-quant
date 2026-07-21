---
studyId: 2768beaa_终极优化ETF核心资产轮动
target: strategies/2026-05-17_终极优化-ETF核心资产轮动策略-2768beaa.py
targetRefs: [[2768beaa_终极优化ETF核心资产轮动]], [[ETF轮动]], [[动量与趋势]]
harness: research/harness.md（冻结成本；窗口 2022–2024，2025 OOS 禁用）
startedAt: 2026-07-16
status: done
---

# 解剖报告：2768beaa_终极优化ETF核心资产轮动（DQ — 为什么不行）

## 一句话结论
ETF 核心资产动量轮动「终极优化」版（多周期动量打分 + 周移动盈亏空仓信号 + 止损）。normalize train 2022-2023 **Sharpe 1.62 → DQ**。属 [[ETF轮动]] 动量轮动家族 regime-dependent DQ。

## 为什么不过门槛（DQ 归因）
动量轮动高度依赖趋势 regime；冻结 2022-23 非趋势窗 whipsaw，Sharpe 1.62 不达门槛（与 0aa4028d 1.67、1c96e06b 1.28 同档）。「终极优化」为参数/空仓/止损微调，不改动量核心的 regime 依赖。

## 机理与真实性
归因基于 normalize train Sharpe 1.62 + [[ETF轮动]] 家族机理；未独立重跑（清晰家族迁移，节省预算）。confidence=med。

## 待研究 / 反哺 auto-research
又一个 ETF 动量轮动 DQ 数据点；「终极优化/多周期/空仓信号」的叠加救不了非趋势窗的低 Sharpe。
