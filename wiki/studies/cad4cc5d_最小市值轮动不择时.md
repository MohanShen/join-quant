---
studyId: cad4cc5d_最小市值轮动不择时
target: strategies/2026-06-17_最小市值轮动_不择时-cad4cc5d.py
targetRefs: [[cad4cc5d_最小市值轮动不择时]], [[小市值因子]]
harness: research/harness.md（冻结成本；窗口 2022–2024，2025 OOS 禁用）
startedAt: 2026-07-16
status: done
---

# 解剖报告：cad4cc5d_最小市值轮动不择时（DQ — 为什么不行）

## 一句话结论
long-only 无（或弱）风控组合。normalize train **Sharpe 0.68 → DQ**：回撤大/Sharpe 不足。无择时/止损 → market-like 回撤 → 风险调整收益不达门槛。

## 为什么不过门槛（DQ 归因）
无风控 → 熊市 regime 吃满回撤：无空仓/止损/择时的 long-only 组合在 2022 熊市随大盘下行，raw 收益可能正但回撤 market-like、Sharpe 掉出门槛。印证 [[1d995d0b_小市值多体系融合]]/[[17c95d16_小市值微调]]：家族低回撤/高 Sharpe 是风控机器造的，非 raw 因子自带。

## 机理与真实性
归因基于 normalize train 指标（Sharpe 0.68）+ 家族已确立机理；未独立重跑（清晰家族迁移，节省预算）。confidence=med。

## 待研究 / 反哺 auto-research
低换手/低频/基本面/裸因子 long-only 无风控 → 熊市 regime 高回撤 DQ；下行保护是 gate-pass 的必要条件。
