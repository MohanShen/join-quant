---
expId: arc2-microcap-rotation (jul12-013..017)
branch: research/jul12
ideaId: Arc-2（低换手载体探索）
baseExpId: jul12-013（裸最小市值周度轮动 baseline）
hypothesis: 裸最小市值周度等权轮动（宇宙400/持10）约46%年化，其~22-25%回撤可用某个正交风控杠杆压到夏普2.5门槛之上而不牺牲过多年化
reasoning: Arc-1 诊断出「junk-tail=alpha 又是缓冲」，据此另起低换手载体，避开日内剥头皮的极端换手；期望用跨日风控（止损/择时/低波倾斜）把系统性微盘 beta 的回撤驯服到门槛内
sourceRefs: [[[小市值因子]], [[止损模块]], [[择时-均线]], [[仓位管理]], [[jul12-005]]]
mutation: 在裸微盘周度轮动基线上分别叠加 三个正交降回撤杠杆（指数MA全书择时 / 个股-15%跨日止损 / 池内低波倾斜）
iterations:
  - { step: 1, exp: jul12-013, change: "baseline 裸最小市值周度等权轮动(宇宙400/持10)", train_objective: 0.2059, gate: fail, note: "annual46/maxdd25.4/sharpe1.65 DQ" }
  - { step: 2, exp: jul12-014, change: "+指数MA20全书防御闸", train_objective: -0.2377, gate: fail, note: "annual3/maxdd26.7/sharpe-0.07 崩" }
  - { step: 3, exp: jul12-015, change: "+个股-15%跨日止损", train_objective: 0.2366, gate: fail, note: "annual46/maxdd22.0/sharpe1.67 BEST(仍DQ)" }
  - { step: 4, exp: jul12-016, change: "+指数MA60全书防御闸", train_objective: -0.0881, gate: fail, note: "annual13/maxdd21.5/sharpe0.62" }
  - { step: 5, exp: jul12-017, change: "+池内低波动选股倾斜", train_objective: 0.0690, gate: fail, note: "annual25/maxdd18.0/sharpe1.05" }
results:
  train:   { annualReturn: 0.46, sharpe: 1.67, maxDrawdown: 0.220, objective: 0.2366, note: "最佳 artifact jul12-015，仍 DQ" }
  val:     { note: "未跑——从未过 TRAIN 门槛，不定稿、不碰 VAL" }
status: negative（KB-only，无 results.tsv 行、无 validated_strategies 归档）
confirmed: false
flags: [⚠零滑点高估, DQ-all, never-finalized, high-turnover(milder than daily scalp)]
ranAt: 2026-07-13
---

# Arc-2 负结果：裸微盘周度轮动不可风控至夏普门槛

**论点（thesis）**：裸最小市值周度等权轮动（宇宙 400 / 持仓 10）能捕获约 **46% 年化**，但其 **~22–25% 回撤是不可约减的系统性微盘 beta**——三个正交的降回撤杠杆**每一个削掉的 edge ≈ 它削掉的风险**，净效果 objective 不升反常降，夏普始终触不到 2.5 门槛。**从未过门槛（gate fail）、从未定稿、从未碰 VAL**。最佳 artifact 为 jul12-015（objective 0.2366，仍 DQ）。

> 记账定位：这是 **KB-only 负结果**（Arc-2 无任何过门槛/定稿版本），故**不占 `research/results.tsv` 行、不归档 `validated_strategies/`**。此页把「此方向不成立」的知识固化，避免被重推。⚠ **零滑点高估**：本轮动族仍高换手（周度全书轮动，虽比日内剥头皮温和），零滑点下 objective 偏高、换手成本被忽略。

## 排行榜（全 DQ · TRAIN 2022-01-01…2023-12-31 · objective=年化−回撤 · gate 夏普≥2.5）

| 变体 | objective | 年化 | 最大回撤 | 夏普 | gate |
|------|-----------|------|----------|------|------|
| [[jul12-015]] +个股−15%跨日止损 **BEST** | **0.2366** | 46% | 22.0% | 1.67 | ❌ DQ |
| [[jul12-013]] baseline 裸微盘周度轮动 | 0.2059 | 46% | 25.4% | 1.65 | ❌ DQ |
| [[jul12-017]] +池内低波倾斜 | 0.0690 | 25% | 18.0% | 1.05 | ❌ DQ |
| [[jul12-016]] +指数MA60防御闸 | −0.0881 | 13% | 21.5% | 0.62 | ❌ DQ |
| [[jul12-014]] +指数MA20防御闸 | −0.2377 | 3% | 26.7% | −0.07 | ❌ DQ |

## 结论：三个正交降回撤杠杆各自失败

1. **(i) 指数MA全书择时——两个速度都失败**：MA20（[[jul12-014]]）与 MA60（[[jul12-016]]）双双把 objective 打到负。系统性微盘 beta 涨跌**都比指数 MA 反应快**，二元 in/out 全书开关**两向都误时**——快闸（MA20）追涨杀跌把年化砍到 3%，慢闸（MA60）钝到 13% 年化仍不降回撤。
2. **(ii) 个股 −15% 跨日止损——只削 idiosyncratic 尾部**：把回撤从 25.4% 压到 22.0% 且**年化完整保留**（46%），故 objective 微升为族内最佳 0.2366；但夏普只从 1.65 挪到 1.67——止损只触及个股特异尾部，**碰不到系统性 beta**，离门槛（2.5）仍差一大截。
3. **(iii) 池内低波动倾斜——alpha 本身就是波动**：回撤降得最多（→18.0%），但**年化腰斩**（46%→25%）、夏普反降（1.67→1.05）。微盘 alpha 集中在高波动/彩票型名字，低波倾斜把溢价来源 deselect 掉了。

三条杠杆**正交却同命**：回撤与收益在裸微盘上是**同一枚硬币**（系统性 beta），任何压回撤的手段都等比压年化，objective 无法被抬过门槛。→ **裸微盘周度轮动这条低换手载体在本纪元 TRAIN 上不成立**；低回撤/高夏普不是 size 因子自带的，需要 Arc-1 那样的**日内风控机器**才能拿到（对照 [[jul12-005]]）。

## 回填指针（§9）
- [[小市值因子]]（归一化/备注）：裸最小市值周度轮动夏普仅 ~1.65 DQ；反证低开剥头皮族的低回撤/高夏普来自日内机器而非 size 本身（[[jul12-013]]）。
- [[止损模块]]：个股 −15% 跨日止损在**多日持有弧 LIVE**（保留年化、降回撤 25.4→22.0），与 scalp 弧的跨日止损死代码（[[jul12-002]]）对照——**持有周期决定其是否 live**（[[jul12-015]]）。
- [[择时-均线]]：指数 MA 全书防御闸在微盘多日弧**两个速度均失败**（[[jul12-014]]/[[jul12-016]]）；与 scalp 弧 MA 买入闸失败（[[jul12-001]]）机制相反、结论同为「MA 择时对该族有害」。
- [[仓位管理]] / [[小市值因子]] vol-tilt：微盘池内低波倾斜降回撤最多但年化腰斩、夏普跌（[[jul12-017]]）——微盘 alpha = 波动本身。
