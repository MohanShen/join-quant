---
expId: arc5-liquid-transplant (jul12-025)
branch: research/jul12
ideaId: Arc-5（Arc-1 引擎流动化移植归因）
baseExpId: jul12-005（Arc-1 低开剥头皮定稿版；引擎 bit-identical 移植源）
hypothesis: 把 Arc-1 定稿的低开剥头皮日内引擎 bit-identical 搬到流动的中证1000 universe，能在更可交易/更大容量的名字上保留其 edge（若 edge 是通用的日内均值回归而非微盘专属）
reasoning: Arc-1（[[jul12-005]]）是本纪元唯一双窗口过关者，但被标为零滑点高估 + 高换手；若其日内反转 edge 是通用微观结构现象，移到流动 universe 应至少衰减而非反转——本实验做**受控归因**：只换 universe，其余全部 bit-identical，隔离「universe」这一单变量
sourceRefs: [[[均值回归]], [[小市值因子]], [[日内做T]], [[jul12-005]]]
mutation: 相对 jul12-005 唯一改动 = 选股 universe 从「全A 市值最小1000」换成「中证1000 成分（流动、机构化中盘）」；每一条日内规则均 bit-identical
factors:
  选股: { 规模价值: [中证1000成分], 技术量价: [低开破昨低+跌幅>1%, 近4日振幅≤10%, 昨收>MA5], 流动性: [买一档金额>5万] }
  择时: [1/4月空仓(avoid_months)]
  风控: [破开盘价11:30清仓, 固定止盈+5%]
  仓位: [等权, 动态持仓数(target_count=6), 预留资金50%]
iterations:
  - { step: 1, exp: jul12-025, change: "Arc-1 引擎 bit-identical + universe 微盘→中证1000", train_objective: -0.5823, gate: fail, note: "annual -12.84/maxdd 45.39/sharpe -0.67; edge 反转为亏损" }
results:
  train:   { annualReturn: -0.1284, sharpe: -0.67, maxDrawdown: 0.4539, objective: -0.5823, note: "gate FAIL；从未定稿、不碰 VAL" }
  val:     { note: "未跑——从未过 TRAIN 门槛" }
status: negative（KB-only 归因结果，无 results.tsv 行、无 validated_strategies 归档）
confirmed: false
flags: [edge-inversion(非衰减而是变号), universe-locked-alpha, ⚠零滑点高估(继承Arc-1), micro-cap-microstructure-specific]
ranAt: 2026-07-14
---

# Arc-5 归因结果：低开剥头皮 edge 是微盘微观结构专属，流动化即反转

> **一句话**：把 Arc-1 定稿的低开剥头皮日内引擎**逐字节相同（bit-identical）**地搬到流动的中证1000，唯一变量是 universe——edge **不是衰减到零，而是反号**：从 obj 1.3898 崩到 −0.5823，年化 +150.51% → −12.84%，夏普 5.96 → −0.67。→ 这条 edge 是**微盘微观结构专属**，不是可移植的通用日内均值回归配方。

## 受控归因：只换 universe，引擎 bit-identical

| 版本 | universe | 年化 | 最大回撤 | 夏普 | objective | gate |
|------|----------|------|----------|------|-----------|------|
| [[jul12-005]] Arc-1 定稿（微盘） | 全A 市值最小1000 | **+150.51%** | 11.53% | **5.96** | **1.3898** | ✅ PASS |
| [[jul12-025]] Arc-5（流动化） | 中证1000 成分 | **−12.84%** | 45.39% | **−0.67** | **−0.5823** | ❌ FAIL |

**唯一改动 = universe**。每一条日内规则均**逐字节相同**：低开破昨低 + 跌幅>1% 入场 / 近4日振幅≤10% / 昨收>MA5 / 破开盘价 11:30 清仓 / 止盈 +5% / target_count=6 / 1&4 月空仓 / 买一档金额>5万 流动性下限 / 冻结成本 OVERRIDE。因子、参数、退出机制、成本假设全部不变。故 obj 1.3898 → −0.5823 的整段落差**只能归因于 universe**。

## 机制：日内均值回归 → 动量/延续（买 falling knife）

低开跳空的**日内均值回归**是一个**微盘散户微观结构**现象：薄、散户主导的名字在开盘**超调**（overshoot）后**回抽**（snap back）——「今开低于昨低 + 低开」标记的是超卖反弹机会，引擎买入即接反弹。

搬到**流动、机构化交易**的中证1000 上，同一「开盘低于昨低 + 低开」信号变成 **momentum / continuation**：机构定价的名字低开后**继续下跌**，不回抽——引擎买的是 **falling knife（下落的刀）**，signal 从反转变号为延续 → 系统性亏损、回撤炸到 45.39%。

**关键**：edge 不随流动性**淡出到零**，而是**变号**——同一信号在两个 universe 的短期动力学**方向相反**（微盘 = 反转、流动 = 延续）。

## 结论
低开剥头皮的 edge **是微盘微观结构专属、universe-locked**，需要「薄 + 散户主导」的微观结构（开盘超调回抽）才成立。流动化移植即反转，不是可移植的通用日内反转配方。这对 Arc-1 headline 有**双重诚实性含义**：jul12-005 的 1.3898 **既**被零滑点高估（高换手成本被忽略），**又**是容量受限、不可移植的微盘专属 alpha——两道保留意见叠加。

## 回填指针（§9）
- [[均值回归]]「观察」：低开剥头皮日内反转是微盘专属，引擎 bit-identical 换 universe 到中证1000 即从 obj 1.3898 反转到 −0.5823，流动名上同信号变 momentum/continuation（[[jul12-025]]）。
- [[小市值因子]]「归一化/备注」：Arc-1 winner 1.3898 是微盘微观结构 alpha、universe-locked + 容量受限，不可移植到流动 universe（[[jul12-025]]）。
- [[日内做T]]：日内反转范式的有效性强依赖标的微观结构（散户 vs 机构），非策略逻辑通用（[[jul12-025]]）。
