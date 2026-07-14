---
epoch: 2
tag: jul12
branch: research/jul12
kind: epoch-summary（综述/capstone）
window: TRAIN 2022-01-01..2023-12-31 / VAL 2024-01-01..2024-12-31（OOS 2025+ 禁用）
harness: research/harness.md（epoch 2 冻结：零滑点 + PerTrade 万3/万13/5；objective=annual−maxdd；gate sharpe≥2.5）
arcsExplored: 5
finalizedRows: 2   # jul12-005 recorded, jul12-023 val-dq（见 research/results.tsv）
bothWindowSurvivors: 1   # 仅 jul12-005，且不可实现/不可部署
deployableProducts: 0
status: converged（ideator 宣告：KB 正 EV 家族在本 harness+窗口下耗尽）
ranAt: 2026-07-14
---

# Epoch 2 (jul12) 综述：严格窗口协议下的收敛结果

## VERDICT（裁定）
在**冻结 harness**（零滑点 + PerTrade 万3/万13/5；objective = 年化 − 最大回撤；硬门槛夏普≥2.5）与 **2022-23 TRAIN 窗口**下，KB 的**正 EV 家族已耗尽**——ideator 宣告收敛，无剩余正 EV 线索。

- **恰好一个双窗口幸存者**：Arc-1（[[jul12-005]]），TRAIN 1.3898 / VAL 1.3231。
- **但它不是净可实现 / 可部署的产品**（详见文末「Arc-1 可实现性裁定」）。
- **未找到任何在两个窗口都过关的诚实可实现策略**。5 条弧探索完毕：1 个双窗口过关（不可部署）+ 4 个 DQ/负结果。

## 弧清单（做了什么 / 为什么如此）

| 弧 | 载体 | TRAIN | VAL | 结局 | 页 |
|----|------|-------|-----|------|----|
| Arc-1 | 低开剥头皮 微盘日内 scalp | **1.3898** PASS | **1.3231** PASS | **唯一双窗口过关**（但不可部署） | [[jul12-005]] / [[7a1c225f_小市值低开优化]] |
| Arc-2 | 裸微盘周度轮动 | 0.2366 DQ | — | 回撤=不可约减系统性 beta | [[arc2-microcap-rotation]] |
| Arc-3 | 跨资产 ETF 动量/反转 | −0.1917 DQ | — | 趋势缺失窗口两向皆无 edge | [[arc3-etf-rotation]] |
| Arc-4 | 市场中性 微盘−IC 对冲 | 0.3202 PASS | −0.5260 DQ | basis 崩盘、VAL 灾难反转 | [[jul12-023]] |
| Arc-5 | Arc-1 引擎移植中证1000 | −0.5823 DQ/反号 | — | 日内反转是微盘微观结构专属 | [[arc5-liquid-transplant]] |

- **Arc-1（[[jul12-005]]）低开剥头皮微盘日内 scalp**：TRAIN 1.3898 / VAL 1.3231——**唯一双窗口过关**（regime-agnostic、日内 flat、无隔夜 beta）。内部旋钮已**完整映射到确证的局部最优**（target_count=6；破开盘价清仓 load-bearing；止盈对称峰值 +5%；振幅≤10 / 跳空 chg<−1）。**三重受限 → 规模化不可交易**：⚠ 零滑点高估 + 微盘容量上限（~¥100万）+ universe-locked（Arc-5 证同引擎流动化即反号）。
- **Arc-2（[[arc2-microcap-rotation]]）裸微盘周度轮动**：DQ——回撤是**不可约减的系统性微盘 beta**（~22-25%）；MA20/60 择时、−15% 止损、低波倾斜**每一个削掉的 edge ≈ 它削掉的风险**。
- **Arc-3（[[arc3-etf-rotation]]）跨资产 ETF 动量/反转**：DQ、**两向都净负**——趋势缺失窗口无 edge；跨资产 haven 给出最低基线回撤（16%）但零回报配对。
- **Arc-4（[[jul12-023]]）市场中性 微盘 − IC 对冲**：TRAIN 过门槛 obj 0.3202（**首个非 Arc-1 过门槛**；经验上确证 Arc-2 的「回撤即 beta」——IC 空头把 maxdd 25.4→12.3 腰斩）/ VAL-DQ obj −0.5260（basis 崩盘，2024-02 微盘专属崩里 maxdd 12.3→41.6）。这个「中性」实为 **basis-directional**。⚠ 期货腿未计成本。
- **Arc-5（[[arc5-liquid-transplant]]）Arc-1 引擎移植流动中证1000**：DQ / **反号** obj 1.3898→−0.5823（引擎 bit-identical，仅换 universe）——日内低开反转是**微盘散户微观结构**现象；流动名上同信号是 momentum/continuation（买 falling knife）。

## 5 条持久 META 发现

1. **本窗口（2022 熊 + 2023 震荡）× 硬门槛夏普≥2.5 系统性惩罚净多头方向 / beta / basis 暴露**。只有 regime-agnostic 的 edge 能过：日内 flat 的那个（Arc-1）被微盘锁死，市场中性的那个（Arc-4）带 basis 风险。
2. **junk-tail = alpha（微盘）成立，但该 alpha 与其系统性 beta（Arc-2）不可分**，一旦对冲又暴露 basis 风险（Arc-4）→ 在此评测台**无法变现为稳健的双窗口产品**。
3. **日内均值回归是微观结构锁死的**：在流动名上**反号**（而非仅淡出，Arc-5）。反转有效性取决于散户 vs 机构微观结构，而非策略逻辑。
4. **跨资产 ETF 动量与反转在趋势缺失/均值回归窗口两向都无 edge**（Arc-3）。
5. **冻结 harness 的零滑点 + 期货腿未计成本，使高换手/微盘与对冲类策略系统性偏乐观**——「− 最大回撤」项与 ⚠ 真实性标记是两道护栏，且它们**正确抓住了两个 would-be winner**（Arc-1 被高估、Arc-4 VAL 崩盘）。

## Arc-1 可实现性裁定（realizability verdict）
Arc-1（[[jul12-005]]）是**本纪元冻结 harness 下最佳研究 artifact**，但**不是可部署产品**：
- objective 1.39(TRAIN) / 1.32(VAL) **非净可实现**——微盘 scalp 的成交在零滑点假设下才存在，真实换手成本会大幅侵蚀；
- **容量受限于极小 AUM**（~¥100万级微盘容量），不可规模化；
- **edge universe-locked**（Arc-5 证：同引擎移到流动 universe 即反号亏损）。
→ 记为「**best-in-epoch，带 standing ⚠ 真实性保留**」，**非可交易**。

## 收敛后建议（供人类 / 下一纪元）
- 若要找**诚实可实现**的双窗口赢家：需换 harness（如引入 `PriceRelatedSlippage` 对换手计费）或换 TRAIN 窗口（含牛市）——二者皆为**新纪元**（harness.md §6）。
- 已登记的负结果地图（Arc-2/3/4/5）标出了本窗口下的**死路**：方向性 beta、basis-mismatch 对冲、趋势缺失窗口的 ETF 动量/反转、流动化的日内反转——下一纪元不必重推。

## 溯源
- 账本：`research/results.tsv`（2 行定稿：jul12-005 recorded / jul12-023 val-dq；DQ baseline 不占行）。
- 归档：`validated_strategies/jul12-005.py`（gate pass）、`validated_strategies/jul12-023.py`（gate fail，仍收——完成 VAL 流程）。
- 弧页：[[jul12-005]] / [[arc2-microcap-rotation]] / [[arc3-etf-rotation]] / [[jul12-023]] / [[arc5-liquid-transplant]]。
- 概念回填：[[小市值因子]] · [[止损模块]] · [[仓位管理]] · [[择时-均线]] · [[动量与趋势]] · [[均值回归]] · [[ETF轮动]] · [[期货与套利]]。
