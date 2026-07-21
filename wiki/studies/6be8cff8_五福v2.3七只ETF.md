---
studyId: 6be8cff8_五福v2.3七只ETF
target: strategies/2026-06-15_这个策略今年很强_点赞回复必回赞_克隆_没积分_模拟盘快到期-6be8cff8.py
targetRefs: [[6be8cff8_五福v2.3七只ETF]], [[ETF轮动]], [[动量与趋势]]
harness: research/harness.md（冻结成本；窗口 2022–2024，2025 OOS 禁用）
startedAt: 2026-07-16
status: done
---

# 解剖报告：6be8cff8_五福v2.3七只ETF（DQ — 为什么不行）

## 一句话结论
ETF/七星-五福-三马 动量轮动家族成员。normalize train **Sharpe 0.4 → DQ**（不达 2.5 门槛）。属 [[ETF轮动]] 动量轮动家族典型 regime-dependent DQ。

## 为什么不过门槛（DQ 归因）
动量轮动高度依赖趋势 regime（[[ETF轮动]] 核心结论）；冻结 2022-23 非趋势窗动量 whipsaw，Sharpe 结构性不足。参数/池/滤波/实盘链路类变体不改动量核心的 regime 依赖，故与家族同 DQ。头条长窗高倍数是含牛市产物。

## 机理与真实性
归因基于 normalize train 指标（Sharpe 0.4）+ 家族已确立机理；未独立重跑（清晰家族迁移，节省预算）。confidence=med。

## 待研究 / 反哺 auto-research
又一个 ETF/动量轮动 家族 DQ 数据点（family 归一化横评：动量族多数 DQ、regime 依赖）。
