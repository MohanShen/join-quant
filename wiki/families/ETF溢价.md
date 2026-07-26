---
family: ETF溢价
aliases: []
concepts: [[[ETF轮动]]]
base: [[15c36e0c_ETF溢价改进版]]
bestVariant: [[edd94ebc_ETF溢价回撤]]
bestObjective: 3.5961
memberCount: 2
sources: { normalized: 2, study: 0, enhance: 0 }
realism: "⚠ 零滑点高估：折价 alpha 集中在最薄/最小的 ETF-LOF，抬高成交量下界即流失（study-q-1：sharpe 8.44→3.16→1.10，1e8 DQ）；头条绩效建立在这些不可真实成交的标的上，capacity-capped、不可规模化。全家族 Δ（含 bestVariant edd94ebc 1599%⚠）须按此护栏折价看待。"
status: active
updatedAt: 2026-07-26
---

# ETF溢价 — strategy family

**一句话**：在全市场 ETF/LOF 中按「实时价/净值 − 1」的折价率升序选最深折价者、等权持有、离场即换的**折价均值回归**轮动族（非动量）——alpha 是一种 illiquidity 溢价，集中在薄流动性基金。

## 1. 基类 (base archetype)   ← study-q-1 溯源
基类 = 成员 `15c36e0c`（最简纯折价反转版）。
- **Universe 选股池**：全市场 ETF + LOF；09:20 预筛「昨日 share-volume > 2e6」后取净值 NAV。
- **交易频率**：每日。
- **交易机制**：入场/择时 09:30 计算 `premium=(last/NAV−1)×100`，升序排序，只留 `premium<0`（折价），买最深折价 top-5 等权；调仓 卖出任何离开该集合的持仓、买入新进者；止损/风控 **无**（无止损、无大盘择时、无回撤帽）。
- **基线绩效**（frozen harness, TRAIN 2022–2023, 零滑点 override）：obj 1.5642 / sharpe 8.87 / annual 177.87% / maxDD 21.46%。复现匹配归一化 1.5642 ✓。详见 §3。
- **为什么有效**：折价（premium<0）的 ETF/LOF 存在向净值均值回归的错误定价；每日买最深折价、回归后离场即赚这个 spread。**但 edge 是 illiquidity 溢价**——它不成比例地活在最薄/最小的基金里（study-q-1）。**edge 有广度、非单名**：obj 在持仓集中度上呈单峰，峰在 top-2（study-q-2），到 top-1 崩塌（分散度损失悬崖）；即折价反转信号同时命中若干深折价名字，靠 top-2/3 的组合而非任一只承载。风险/收益权衡清晰——base 的 **top-5 是最低回撤/最高 sharpe 点**，**N=2 是最高 obj 点**（集中度换回撤：maxDD 随集中度单调抬、sharpe 单调降）。
- **⚠ 现实性 / 容量**：见 frontmatter realism。折价 alpha 与「不可真实成交」是同一枚硬币——制造 edge 的成交量下界过滤器，也正是让零滑点成交不真实的过滤器。base 的 2e6 floor 甚至**过松**（study-q-1）。

## 2. 变体 (variants)   ← 待人工/study/research 填写
| 变体 | 相对基类的改动 | 来源 | Δobjective | Δsharpe | ΔmaxDD | 结论 |
|---|---|---|---|---|---|---|
| 成交量下界扫描 (line36 floor) | 把昨日 share-volume 下界从 2e6 抬到 1e7 / 3e7 / 1e8 | study-q-1 | +0.47(1e7) / −0.84(3e7) / −1.45(1e8 DQ) | −0.43 / −5.71 / −7.77 | −10.97(1e7) / −3.69(3e7) / +3.18(1e8) | 单峰后单调衰减（非平台）：edge 集中在薄基金，抬流动性即流失（1e8 DQ）；但 base 的 2e6 floor 过松，收紧到 1e7 反而 obj +0.47 且 maxDD 减半 → 1e7≈流动性甜点。⚠零滑点高估 |
| 持仓集中度扫描 (df[:5] 切片) | 把等权持仓数 top-5 收窄到 top-1 / 2 / 3（2e6 floor 不动） | study-q-2 | −0.06(N=1) / +0.35(N=2) / +0.15(N=3) | −2.11 / −0.44 / −0.07 | +9.31(N=1) / +2.87(N=2) / +3.99(N=3) | obj 单峰、峰在 **N=2**（obj 1.914，+0.35）；N=1 崩塌（obj 1.503 跌破 base、maxDD 30.77、sharpe 6.76、annual 反低于 N=2）=分散度损失悬崖 → edge 有广度（top-2/3）非单名。maxDD 随集中度单调抬、sharpe 单调降，base N=5 仍是最低回撤/最高 sharpe 点。集中度单独只占 base→edd94ebc ~2.0 gap 的 ~17%，bulk 来自 edd94ebc 的入场滤波器。⚠零滑点高估（换手未测，N=2 annual 尤其乐观） |

## 3. 家族内绩效横评 (auto)

| 排名 | 变体 | obj | sharpe | annual% | maxDD% | gate |
|---|---|---|---|---|---|---|
| **1** | **[[edd94ebc_ETF溢价回撤]]** | 3.5961 | 14.77 | 374.38 | 14.77 | ✅ |
| 2 | [[15c36e0c_ETF溢价改进版]] | 1.5642 | 8.87 | 177.88 | 21.46 | ✅ |

*2 gate-pass / 2 members. 快照 2026-07-26（TRAIN 2022–2023, 冻结零滑点 ⚠）。由 `wiki-family-build.js` 生成，勿手改。*

## 4. 待研究 / 空白 (research gaps)   ← 待人工填写：本家族未试方向
- ✅ **持仓集中度扫描**（study-q-2 已答）：单峰、峰在 N=2，N=1 是分散度损失悬崖；集中度单独只占 base→edd94ebc gap 的 ~17%。
- **【顶级开放归因】edd94ebc 滤波归因**：q-2 已证集中度只解释 ~17% 的 ~2.0 obj gap，**bulk（~83%）来自 edd94ebc 的 MA5 站上 / 成交额>80万 / 价格波动<0.1 三个入场滤波器**——这是本家族第一大未解归因。逐个拆解其边际贡献，定位 obj 残差究竟来自哪一处，及是否只是把 universe 推向更薄尾部的零滑点假象（edd94ebc 自身短窗 sharpe 51⚠ 已使残差 gap 真实性可疑）。
- **换手/成交真实性探针**：q-1/q-2 均未测换手；集中度越高换手越大，故 N=2 的 annual 尤其乐观。量化每日折价轮动换手率 + 薄标的实际可成交量，把「零滑点高估」从定性变定量（滑点弹性扫描）。
- **regime 分区间**：2022 熊 vs 2023 震荡——跨族规律显示折价族低 maxDD 多为 2022 熊市专属（[[ETF轮动]]），验证 15c36e0c 的回撤与 edge 是否同样 regime 承载。

## 5. 沿革 (provenance)   ← 待人工填写：首发 postId/作者、版本演进
折价率均值回归 ETF 轮动血统（与 [[ETF轮动]] 主流的「动量追强」正交）。base `15c36e0c`（ETF溢价改进版）是最简纯折价反转实现（仅折价率选股 + 等权 top-5 + 无风控，长区间版）；`edd94ebc`（ETF溢价回撤）是加过滤的变体（折价 + 站上 MA5 + 成交额>80万 + 价格波动<0.1，持 2 只），头条 1599%/夏普 51 极端存疑（短窗口外推，⚠ 已在其策略页与 [[ETF轮动]] 概念页标注）。

## 6. 研究问答 (study-log)
- **[Q q-1]** 把 universe 限制到更流动的 ETF 后折价 edge 还在吗，还是活在被零滑点抬高的低流动深折价基金里？（type: sweep）
  **→** 非平台，而是**单峰后单调衰减**：edge 不成比例地活在薄/小 ETF-LOF，抬高成交量下界即流失（sharpe 8.44→3.16→1.10，1e8 DQ）——确证零滑点高估失效模式；NUANCE：base 的 2e6 floor 过松、纳入超薄高回撤尾部，收紧到 1e7 反而 obj +0.47、maxDD 减半（21.46→10.49）、sharpe 持平，1e7≈流动性甜点。此结果 validity-gate 全家族（含 edd94ebc ⚠）。（Δobj +0.47/−0.84/−1.45；confidence med-high；⚠零滑点高估）溯源 [[study-q-1]]
- **[Q q-2]** 集中到最深折价名字（top-N，N=1/2/3）能否驱动收益，单调还是单峰，maxDD 怎么变？（type: sweep）
  **→** 单峰、峰在 **N=2**（obj 1.914，+0.35 vs base N=5）：集中度帮到 N=2 后到 N=1 崩塌（obj 1.503 跌破 base、maxDD 30.77 +9.3pp、annual 反低于 N=2）——N=1 是分散度损失悬崖，故折价 alpha 有广度（top-2/3）而非单名。maxDD 随集中度单调抬、sharpe 单调降，base N=5 仍是最低回撤/最高 sharpe 点。关键归因：edd94ebc 把 5→2 集中度与 MA5/成交额/价格稳定滤波捆绑，集中度单独只解释 obj +0.35 ≈ **~17%** 的 ~2.0 gap，bulk 的 edge 来自额外入场滤波器而非集中度（且滤波器 + edd94ebc 短窗 sharpe 51⚠ 使残差 gap 真实性存疑）。（Δobj −0.06/+0.35/+0.15；confidence med；⚠零滑点高估，换手未测）溯源 [[study-q-2]]
