---
studyId: 9befa9b8_十日均线策略
target: strategies/2026-06-08_十日均线策略-9befa9b8.py
targetRefs: [[9befa9b8_十日均线策略]], [[动量与趋势]]
harness: research/harness.md（冻结成本；窗口 2022–2024，2025 OOS 禁用）
startedAt: 2026-07-16
status: done
---

# 解剖报告：9befa9b8_十日均线策略（DQ — 为什么不行）

## 一句话结论
裸技术指标（单指标）策略。normalize train **Sharpe n/a → DQ 无 edge**。单一 TA 指标无真实 alpha。

## 为什么不过门槛（DQ 归因）
裸技术指标（均线/网格/布林/MACD/RSI 单指标）在 A 股冻结窗普遍无 alpha，产出近零风险调整收益 + market-like 回撤。经典「单一 TA 无 edge」DQ，与 [[3c269466_布林通道策略]] 同类。

## 机理与真实性
归因基于 normalize train 指标（Sharpe n/a）+ 家族已确立机理；未独立重跑（清晰家族迁移，节省预算）。confidence=med。

## 待研究 / 反哺 auto-research
裸单指标 TA（均线/网格/布林/MACD/RSI）冻结窗普遍无 alpha；勿当 edge。
