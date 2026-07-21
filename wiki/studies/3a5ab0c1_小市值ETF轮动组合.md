---
studyId: 3a5ab0c1_小市值ETF轮动组合
target: strategies/2026-06-01_策略组合_优质小市值周换手与ETF轮动策略组合-3a5ab0c1.py
targetRefs: [[3a5ab0c1_小市值ETF轮动组合]], [[小市值因子]], [[ETF轮动]]
harness: research/harness.md（冻结成本；窗口 2022–2024，2025 OOS 禁用）
startedAt: 2026-07-16
status: done
---

# 解剖报告：3a5ab0c1_小市值ETF轮动组合

## 一句话结论
一个 50/50 的「优质小市值周轮动（PB-同比增长为正、带 defensive months）＋ ETF收益率稳定性轮动（stability-focused + 技术滤波）」双 sleeve 组合（隔离子账户、策略1 blackout 时动态再分配），train 2022-2023 冻结零滑点下 MARGINAL 过门槛（total 114.82%/年化 46.64%/Sharpe 2.57/maxDD 9.75%/obj 0.3689）。**与本批的 blend-drag 模式相反，其 ETF sleeve 是一个 GENUINE DIVERSIFIER**：去掉它（纯小市值 [1,0]）虽把 raw 年化抬 +7pt（→53.54%），却**降 Sharpe（2.57→2.34，跌破 2.5 门槛而 DQ）并抬 maxDD（9.75→12.49%，+2.7pt）**——ETF sleeve 兑现真实回撤压制、提 Sharpe，且是让这个边际策略保住过门槛的组件。annual−maxDD objective 上纯小市值仅微高 +0.04（噪声内、且 DQ），是**真实的风险/收益 tradeoff（cf. [[1c80dd9a_大小外择时小市值]]）而非严格拖累（cf. [[3c462ece_三马七星1.7.2大池]] / [[9f6f8188_大小盘多策略]]）**；⚠ 零滑点高估两支绝对数、regime-conditional。

## 组件贡献归因（按贡献排序）
| 组件 | 去掉后 Δobjective | Δmaxdd | Δ换手 | 结论 |
|---|---|---|---|---|
| 50% ETF收益率稳定性轮动 sleeve（[0.5,0.5]→[1,0]，dynamic_proportion=False） | +0.0416（0.3689→0.4105，噪声内） | **+2.74pt（9.75→12.49%，去掉后回撤上升）** | ↓（去掉高换手 ETF sleeve） | **GENUINE DIVERSIFIER，非拖累**：去掉后 Sharpe 2.57→2.34（DQ）、maxDD +2.7pt、raw 年化仅 +7pt——兑现真实回撤压制+提 Sharpe、且是保住过门槛的组件；objective +0.04 是噪声且 DQ，不可部署 |

变体对照（train 2022-2023，冻结零滑点，⚠零滑点高估）：

| variant | total% | annual% | Sharpe | maxDD% | objective | gate | Δobj |
|---|---|---|---|---|---|---|---|
| baseline (50% 小市值 + 50% ETF稳定性轮动) | 114.82 | 46.64 | 2.57 | 9.75 | 0.3689 | PASS | — |
| q-1 puresmall [1,0] | 135.47 | 53.54 | 2.34 | 12.49 | 0.4105 | **FAIL (2.34<2.5)** | +0.0416 |

## 参数敏感性
未做系统 sweep（适度批深）。归因层面的 tradeoff：ETF sleeve 权重从 0.5→0 换来 raw 年化 +7pt 但 Sharpe −0.23、maxDD +2.7pt 且跌破门槛。关键差异化解释：**ETF 子策略的构造质量**——这里是 stability-focused（收益率稳定性 + 技术滤波）的 ETF 轮动，genuinely 多样化；而 [[3c462ece_三马七星1.7.2大池]] 的 七星 momentum sleeve 只是 minor DD reducer/major drag（严格被 dominated）。sleeve 价值取决于 diversifier 的构造，不止于「小盘 vs 非小盘」。

## regime 依赖
train 2022-2023 偏好小盘 raw return，故纯小市值 raw 年化更高。ETF diversifier 的价值在此窗表现为「以 ~7pt 收益换低 DD+高 Sharpe+过门槛」；在小盘崩盘 regime（如 2024-02 微盘踩踏，本窗未含）其保护价值可能更大——未测。confidence：测得 train-window Δ high，regime 普适 med。

## 机理与真实性
⚠ 零滑点高估：小市值周轮动 + ETF 轮动均高换手，两支绝对数被抬高，Δ 方向稳健、量级虚高。可实现性判断：这是一个 MARGINAL gate-pass 策略，且其**过门槛资格依赖 ETF sleeve**（纯小市值 Sharpe 2.34 直接 DQ）——真实滑点下 Sharpe 与门槛裕度会进一步收窄。weight-0/dynamic=False sleeve 干净不注资、无崩溃。

## 待研究 / 反哺 auto-research
- **IMPORTANT COUNTEREXAMPLE to「blend dilutes small-cap core」pattern**：一个 stability-focused 的 ETF-rotation diversifier genuinely 降低小市值 book 的回撤并让边际策略保住过门槛（对照 [[3c462ece_三马七星1.7.2大池]] 的 七星 momentum sleeve 严格拖累）。sleeve VALUE 取决于 diversifier 的**构造/质量**，不止「小盘 vs 非小盘」——勿默认 overlay sleeve 一律是拖累。
- **objective 盲区**：annual−maxDD objective under-credits 一个真实的 Sharpe/DD 改进（不抬 annual−maxDD）——一个让策略保住过门槛的 diversifier 有该 objective 遗漏的可部署价值。auto-research 选择时应把 gate-survival / Sharpe 纳入，而非只看 annual−maxDD。
- 未做：ETF sleeve 内部技术滤波逐一消融、动态再分配（blackout reallocation）机制隔离、out-of-regime（小盘崩盘）保护验证、参数 sweep。
