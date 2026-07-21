---
studyId: ecba365f_日内单票做T
target: strategies/2026-06-14_日内单票做T策略-ecba365f.py
targetRefs: [[ecba365f_日内单票做T]], [[动量与趋势]]
harness: research/harness.md（冻结成本；窗口 2022–2024，2025 OOS 禁用）
startedAt: 2026-07-16
status: done
---

# 解剖报告：ecba365f_日内单票做T（DQ — 为什么不行）

## 一句话结论
日内单票做 T+0 策略。train 2022-2023 年化 14.03%、但 maxDD **29.49%**、Sharpe **0.30** → DQ。

## 为什么不过门槛（DQ 归因）
单票日内做 T 波动大、无稳健 edge（Sharpe 0.30），且集中单票 → 高回撤 29%。⚠ 日内高频真实成交/冲击成本存疑，零滑点下也仅 Sharpe 0.30。

## 机理与真实性
baseline 直接观测（total 29.99% / annual 14.03% / sharpe 0.30 / maxdd 29.49%）。confidence=high。

## 待研究 / 反哺 auto-research
见「为什么不过门槛」——冻结 2022-23 窗对无防御/负 alpha/过度保守/不可评测策略系统性 DQ。
