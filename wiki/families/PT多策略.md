---
family: PT多策略
aliases: []
concepts: [[ETF轮动]], [[多策略组合]]
base: [[fa0d3bd9_PT多策略并行]]
bestVariant: [[fa0d3bd9_PT多策略并行]]
bestObjective: 3.5952
memberCount: 2
sources: { normalized: 1, study: 0, enhance: 0 }
realism: "⚠⚠ 本批最被高估的家族——头条 obj 3.5955/sharpe 18 是纯薄基金 illiquidity 溢价，由构造把 universe 限死在成交额 5M–20M CNY/日的微流动 ETF、每日折价全换承载，零滑点成交在这些标的上不可实现，头条完全不可规模化；band 移到真流动基金(50M-100M)即 edge 崩塌到 DQ(sharpe 1.09)——唯一可真实成交的点恰是 edge 消失的点。溯源 study-q-1。"
status: done
updatedAt: 2026-07-26
---

# PT多策略 — strategy family

**一句话**：营销为「四大策略并行 / 自有账本」，但回测代码实为**单一 ETF 折价均值回归 sleeve**，刻意把 universe 锁在**成交额 5M–20M CNY/日的微流动 ETF**上做每日折价全换——头条 obj 3.5955/sharpe 18 是薄基金 illiquidity 溢价的极端形态（溯源 study-q-1）。

## 1. 基类 (base archetype)   ← study 溯源
- **REFRAME（关键）**：尽管标题「PT多策略并行 / 自有账本」宣称多策略组合，**被回测的具体代码是单一折价反转 sleeve**——「多策略/账本」框架不是 edge 来源。与 [[ETF溢价]] 家族本质同一信号（premium<0 折价均值回归），唯一差异是 PT 额外加了 <2e7 成交额上界把 universe 压到最薄尾部。
- **Universe 选股池**：全市场 ETF；09:20 预筛 = 昨日成交额（money）落在 **5e6–2e7（500万–2000万 CNY/日）** 的 ETF，**刻意排除流动基金**。
- **交易频率**：daily；每日重算、离场即换。
- **交易机制**：
  - *入场 / 择时*：09:25 计算 `premium=(day_open/NAV−1)×100`，保留 premium<0（折价），取最深折价 **top-10**，按 **|premium| 加权**；09:30 执行。
  - *调仓*：卖出跌出 top-10 的持仓，买入新入选者。
  - *止损 / 风控*：**无**独立风控。
- **基线绩效**（frozen harness, TRAIN 2022–2023, 变体 [[fa0d3bd9_PT多策略并行]]）：
  | objective | sharpe | annual% | maxDD% | window |
  |---|---|---|---|---|
  | 3.5955 | 18.17 | 369.10 | 9.55 | train |

  （复现值，与归一化账本 3.5952 一致 ✓）
- **为什么有效**（essential driver, 溯源 study-q-1）：**决定性的薄基金 illiquidity 溢价**。折价反转信号本身在流动基金上几乎无风险调整 edge——把 band 移到真流动基金(50M-100M)时头条不是软化而是**崩塌到 DQ**(sharpe 1.09/obj 0.05)；仅去上限纳入流动基金即稀释(obj→2.89/sharpe→13.37)。alpha 专属于最不流动尾部，band 越贴薄基金头条越高。PT 的 sharpe 18 >> [[ETF溢价]] 的 8.87 正因它把同一 edge 推到了 band 的薄极端。
- **⚠ 现实性 / 容量**：**本批最被高估的家族**。edge 由构造集中在成交额 5M–20M CNY/日的微流动 ETF 上、每日折价全换 = 在最不可成交的名字上高换手；obj 3.5955 **不可实现、不可规模化**。唯一可真实成交的点（流动 band）恰是 edge 消失的点。⚠⚠零滑点高估、capacity-capped。

## 2. 变体 (variants)   ← 待人工/study/research 填写
| 变体 | 相对基类的改动 | 来源 | Δobjective | Δsharpe | ΔmaxDD | 结论 |
|---|---|---|---|---|---|---|
| （band 50M-100M） | universe 成交额 band 5M-20M→50M-100M（真流动基金） | study-q-1 | −3.5420 (→0.0535, DQ) | −17.08 (→1.09) | +11.60 (→21.15) | 移到流动基金 edge **崩塌到 DQ**——头条纯薄基金 illiquidity 溢价，折价信号在流动基金上无风险调整 edge。⚠零滑点高估 |
| （nocap >5M） | 去掉 20M 上界，保留 5M 下界（纳入流动基金） | study-q-1 | −0.7058 (→2.8897) | −4.80 (→13.37) | +4.39 (→13.94) | 仅纳入流动基金即稀释——它们偶尔挤掉 top-10 里的薄名字；alpha 专属最不流动尾部，band 越贴薄基金头条越高。⚠零滑点高估 |

## 3. 家族内绩效横评 (auto)

| 排名 | 变体 | obj | sharpe | annual% | maxDD% | gate |
|---|---|---|---|---|---|---|
| **1** | **[[fa0d3bd9_PT多策略并行]]** | 3.5952 | 18.16 | 369.07 | 9.55 | ✅ |
| 2 | [[c70281d3_PT多策略分仓隔离插件V1.3]] | 3.5423 | 18.12 | 362.33 | 8.10 | ✅ |

*2 gate-pass / 2 members. 快照 2026-07-26（TRAIN 2022–2023, 冻结零滑点 ⚠）。由 `wiki-family-build.js` 生成，勿手改。*

## 4. 待研究 / 空白 (research gaps)
- **「多策略」宣称对 c70281d3 未验证**：另一成员 [[c70281d3_PT多策略分仓隔离插件V1.3]]（4357 行「分仓隔离插件」框架）是否真的并行运行**多个不同子策略**，还是同样只是单一折价 sleeve 套了账本框架？（base fa0d3bd9 已证实是单 sleeve；c70281d3 待拆）。
- **换手/真实性量化探针**：读回测换手率量化 obj 3.5955 与可实现收益的现实差距（薄基金每日全换的冲击成本在零滑点台被完全掩盖）。
- **权重方案**：|premium| 加权 vs 等权对 obj/回撤的影响（对照 [[ETF溢价]] q-2 集中度是回撤一等旋钮）。
- **top-10 集中度扫描**：top-10 → top-5/3/2/1，折价 alpha 广度是否与 [[ETF溢价]] 家族一致（峰在 top-2/3、单名是分散度悬崖）。
- **regime 分区间**：低 maxDD 9.55% 是否 2022 熊市专属（对照 fa0d3bd9 前期 q-3 / [[ETF溢价]] 折价族回撤 2022 集中规律）。

## 5. 沿革 (provenance)
- 标题血统 = 「PT / 自有账本」交易框架（PT = 一套自建持仓账本/分仓框架），营销为「四大策略并行」。
- **base [[fa0d3bd9_PT多策略并行]]**：回测代码实为单一薄基金折价反转 sleeve（obj 3.5952）。
- **[[c70281d3_PT多策略分仓隔离插件V1.3]]**：4357 行「分仓隔离插件」框架精化版（obj 3.5423），框架侧重分仓隔离账本，核心信号疑同源（待 §4 拆解）。

## 6. 研究问答 (study log)
- **[Q q-1]** PT多策略头条 edge (obj 3.5955/sharpe 18.17) 是否纯薄基金 illiquidity artifact——把成交额 band 移离刻意的 5M-20M 窗到流动基金时是否崩塌？（type: sweep）
  **→** 决定性崩塌，确证头条 = 薄基金 illiquidity 溢价：band 50M-100M（流动）obj 3.5955→0.0535(DQ)/sharpe→1.09；nocap(去上限>5M) obj→2.8897/sharpe→13.37。折价反转信号在流动基金上无风险调整 edge，alpha 专属最不流动尾部，band 越贴薄基金头条越高、越不可实现——与 [[ETF溢价]] q-1 同一现象的薄-band 极端（PT sharpe 18 >> ETF溢价 8.87 即因此）。obj 3.5955 不可实现/不可规模化。（Δobj −3.54(液)/−0.71(nocap)；confidence high；⚠零滑点高估 capacity-capped）溯源 [[study-q-1]]
