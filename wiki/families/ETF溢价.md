---
family: ETF溢价
aliases: [ETF折价, 折价率轮动]
concepts: [[ETF轮动]]
edge:
  - name: 均值回归
    kind: anomaly
    claim: "信号是 09:30 last_price（日频台 = 开盘价）对 T−1 单位净值的折价：买最深折价的 5 只、等价格向净值回归。若同一 universe 上翻成买最高溢价也赚到同量级，则折价的符号不承载信息"
    test: "u-3 镜像（premium>0、降序 top-5）；若镜像 objective ≥ 基类 −0.1，证伪。u-1（信号不动、成交挪到 14:50）判 realizability：偏离是否存活到日内可交易时段"
    status: measured
    evidence: "[[study-u-3]]（镜像买最高溢价：total −98.72%，annual −88.7 / sharpe −4.04 / maxDD 98.7，上涨日 20%，两年同号）+ [[study-u-1]]（同一信号、成交挪到 14:50：+321% → +10%，sharpe 0.07——偏离在开盘价到收盘价之间已回归完毕）+ [[study-ep-imp-3]]（收盘折价、收盘买入：−53%，次日不回归）+ [[study-u-2]]（去 LOF：obj +0.76——只有 ETF 的折价靠实物申赎当日套平，LOF 的折价是持续的）。⚠ 信号承重，但机制只存在于集合竞价的成交价上：开盘折价与收盘折价两头都不可实现"
  - name: 流动性溢价
    kind: risk-premium
    claim: "偏离的幅度由薄度供给：收益不成比例地活在昨日 share-volume 最低的 ETF/LOF 上；抬高下界到流动基金，折价信号应失去风险调整后的 edge（pre-wipe epoch-2 q-1：sharpe 8.44→3.16→1.10，1e8 DQ，无参与上限）"
    test: "u-4 下界 2e6→1e8（流动臂）；若 objective ≥ 基类 −0.1，证伪。ep-imp-1 下界 1e7 给中间档"
    status: measured
    evidence: "[[study-u-4]]（下界 1e8：obj 0.8607→0.0937，annual 33.7 / sharpe 1.04 / maxDD 24.3，DQ，两年仍为正，复现 epoch-2 的 sharpe 1.10）+ [[study-ep-imp-1]]（ETF-only 上下界 2e6→1e7：obj +0.054，收益不丢——收益活在 1e7–1e8 股这一档，最薄的 2e6–1e7 在 5% 参与上限下本就填不满）+ [[study-baseline-e6]]（参与上限单独把 epoch-2 的 178% 压到 105%：容量，不是信号）"
base: [[15c36e0c_ETF溢价改进版]]
bestVariant: [[15c36e0c_ETF溢价改进版]]
bestObjective: 1.5642
memberCount: 2
sources: { normalized: 2, study: 6, enhance: 4 }
realism: "⚠⚠ 头条不可实现，且已定量：收益 ≈100% 是「在集合竞价的开盘成交价上按全天成交量 5% 买到开盘价低于 T−1 净值的薄 ETF」这一件事。同一信号把成交挪到 14:50 → 两年 +321% 变 +10%、sharpe 0.07（u-1）；在收盘看折价、收盘买、等次日回归 → −53%、回撤 54%（ep-imp-3）。偏离幅度由薄度供给：下界 1e8 股的流动 universe 上只剩年化 34% / sharpe 1.04（DQ，u-4）。5% 参与上限已把 epoch-2 的 178% 压到 105%（baseline-e6），而薄 ETF 的集合竞价成交量远小于全天的 5%。零滑点台。TRAIN 174–182% / VAL 214% 都建立在同一不可成交假设上；与 [[PT多策略]] 是同一机制的两个实现（两条 edge 同名、同 status），整合层不得把本家族当作可拼接 sleeve，引用时按 u-4 的 34% / 1.04 估值。建议 status → DQ-realizability，由人裁决"
status: active
updatedAt: 2026-09-23
---

# ETF溢价 — strategy family

**一句话**：在全市场 LOF + ETF 里，09:20 取昨日 share-volume > 2e6 的名字和 T−1 单位净值，09:30 用 last_price（日频台 = 开盘价）算 premium = price/NAV − 1，留折价者、按折价最深取 5 只等权，离开 top-5 即卖，无止损、无择时，节前清仓。epoch-6 TRAIN 年化 105% / sharpe 5.93 / maxDD 19.3%（obj 0.8607）；去掉 LOF 后 174% / 8.06 / 12.5%（obj 1.6193）；VAL 2024–25 候选 214% / 7.60 / 13.0%——**而把成交从开盘价挪到 14:50，同一信号两年只剩 +10%**（u-1）：收益全部是集合竞价那口成交价，不可实现。与 [[PT多策略]] 是同一机制。

## 1. 基类 (base archetype)   ← [[study-baseline-e6]] 起溯源；pre-wipe epoch-2 的 q-1 / q-2（git a6195c6）在 §5 引用，数字不横比
- **基类**：[[15c36e0c_ETF溢价改进版]]（78 行）。成员 [[edd94ebc_ETF溢价回撤]] 是同一 sleeve 的 ETF-only 版加三个入场过滤（昨日 high−low<0.1、成交额>8e5、收盘>MA5）与 top-2；**它在本台没有任何行**（q-ledger：ledger 回退时丢失，页面无 `normalized:` 块可重建，也不在 pending-normalize 里）。epoch-6 快照 `study/ETF溢价/baseline-e6.py`（`build-e6.js` 生成；所有变体 = py2to3(源码) + 断言过的一处改动 + live OVERRIDE）。源码自设基金费率 0.00025 / min 0、无滑点、不设 order_volume_ratio——epoch 4 的 5% 参与上限是唯一咬到它的 pin，annual 178 → 105。
- **Universe 选股池**：`get_all_securities(['lof','etf'], previous_date)` 全部 LOF + ETF；09:20 取昨日 `volume`（**股数**，非成交额）> 2e6 的名字，再取 `get_extras('unit_net_value', end_date=previous_date)` 的 T−1 净值。⚠ 库里唯一含 LOF 的折价书；u-2 证明 LOF 腿是 −69pp 年化的拖累。
- **交易频率**：日频，两个 run_daily：09:20 备数据 / 09:30 算信号并执行。
- **交易机制**：
  - *入场 / 信号*：09:30 `premium = (last_price / unit_net_value − 1) × 100`；升序，留 premium < 0，取 **top-5**。
  - *调仓*：先 `order_target_value(fund, 0)` 卖出不在 top-5 的持仓，再把可用现金按剩余仓位数**等权**买入新进者（`available_cash / now_position`）。
  - *止损 / 风控*：**无**。只有一张写死到 2021 年的 `g.holiday` 节前清仓表（TRAIN/VAL 窗内不命中，惰性）。
- **基线绩效**（frozen harness epoch 6）：
  | | objective | sharpe | annual% | maxDD% | 2022 total% | 2023 total% |
  |---|---|---|---|---|---|---|
  | **baseline-e6（锚点）** | **0.8607** | 5.93 | 105.37 | 19.30 | +83.14 | +133.78 |
  | ledger epoch-2 行（无参与上限） | 1.5642 | 8.87 | 177.88 | 21.46 | — | — |
  | u-1 同信号、14:50 成交 | −0.1676 | 0.07 | 4.95 | 21.71 | +6.16 | +3.72 |
  | u-2 去 LOF（= ep-imp-0） | 1.6193 | 8.06 | 174.40 | 12.47 | +237.92 | +123.45 |
  | u-3 镜像：买最高溢价 | −1.8746 | −4.04 | −88.72 | 98.74 | −89.39 | −88.05 |
  | u-4 下界 1e8 | 0.0937 | 1.04 | 33.66 | 24.29 | +45.55 | +23.46 |
  | ep-imp-1 ETF-only + 下界 1e7（adopted，边际） | 1.6733 | 7.26 | 182.21 | 14.88 | +241.66 | +133.75 |
  | ep-imp-2 ETF-only + top-2（rejected） | 1.0440 | 5.68 | 116.68 | 12.28 | +170.29 | +75.39 |
  | ep-imp-3 ETF-only + 收盘信号、收盘成交（rejected） | −0.8592 | −1.33 | −31.43 | 54.49 | −42.35 | −18.42 |
  | **VAL 2024–25 ep-imp-1**（本 epoch 唯一一次） | 2.0115 | 7.60 | 214.16 | 13.01 | 2024 +303.48 | 2025 +146.01 |
- **为什么有效**（[[study-u-3]] / [[study-u-1]] / [[study-u-2]] / [[study-u-4]] / [[study-ep-imp-1]] / [[study-ep-imp-3]]）：两条 measured edge，与 [[PT多策略]] 同名、同一件事的两面：
  - *均值回归*（对 NAV）：信号承重。镜像买最高溢价两年 −99%（上涨日 20%），基类 +321%，同信号在收盘价成交只剩 +10%——偏离在开盘价到收盘价之间已回归完毕。只有 ETF 的折价会回归（一级市场实物申赎 T+0 套平）；LOF 的折价是持续的（现金申赎 T+2、有费用），所以去掉 LOF 反而 +69pp（u-2）。
  - *流动性溢价*：偏离的幅度由薄度供给。下界 1e8 股的流动 universe 上同一规则只剩年化 34% / sharpe 1.04（DQ）；下界 1e7 不丢收益——收益活在 1e7–1e8 股这一档，最薄的 2e6–1e7 在 5% 参与上限下本就填不满（epoch-2 的「1e7 甜点、回撤减半」是无上限时的容量幻觉）。
  - **但机制只存在于集合竞价的成交价上**：开盘折价到收盘已回归（u-1），收盘时仍折价最深的是当天没人去套的名字、次日继续亏（ep-imp-3，−53%）。两头都测了，本家族没有可实现形态。
- **⚠ 现实性 / 容量**：见 frontmatter `realism`。

## 2. 变体 (variants)   ← epoch 6；Δ 对 baseline-e6（obj 0.8607）；improve 候选建立在 u-2 上，括号内为对 u-2 的 Δ；**失败的变体也记**（判定: rejected）
| 变体 | 类型 | 相对基类的改动 | 来源 | Δobjective | Δsharpe | ΔmaxDD | 判定 | 结论 |
|---|---|---|---|---|---|---|---|---|
| [[15c36e0c_ETF溢价改进版]] | raw | 无 | normalized-raw | 0 | 0 | 0 | — | 基类；epoch-6 锚点 obj 0.8607，§3 里的 1.5642 是 epoch-2 无参与上限的行 |
| [[edd94ebc_ETF溢价回撤]] | raw | ETF-only + 三个入场过滤 + top-2 | normalized-raw | — | — | — | — | q-ledger：本台无行（ledger 回退时丢失，非 DQ）；pre-wipe epoch-2 记 3.5961；top-2 在本台是负贡献（ep-imp-2），其头条应为容量幻觉，待 normalize 给它锚点 |
| u-1 同信号、14:50 成交 | understand | run_daily 14:50 + market_exec | [[study-u-1]] | −1.0283 | −5.86 | +2.41 | informative | **realizability 判决**：+321% → +10%，偏离只在集合竞价成交价上存在 |
| u-2 去 LOF | understand | universe 一行 | [[study-u-2]] | +0.7586 | +2.13 | −6.83 | informative | LOF 腿是拖累（差额全在 2022）；关闭 LOF 净值滞后=收益来源 |
| u-3 镜像买最高溢价 | understand | 排序降序 + premium>0 | [[study-u-3]] | −2.7353 | −9.97 | +79.44 | informative | 均值回归 measured：镜像 −99%，上涨日 20%；比 PT 更不对称（LOF/QDII 高溢价名字的塌陷） |
| u-4 下界 2e6→1e8 | understand | 一行 | [[study-u-4]] | −0.7670 | −4.89 | +4.99 | informative | 流动性溢价 measured：流动 universe 上 DQ（sharpe 1.04），复现 epoch-2 |
| ep-imp-0 ETF-only | improve | = u-2（同一次测量） | [[study-ep-imp-0]] | +0.7586 | +2.13 | −6.83 | adopted | 减法改进；后续候选的起点 |
| ep-imp-1 ETF-only + 下界 1e7 | improve | 对 u-2 一行 | [[study-ep-imp-1]] | +0.8126（+0.0540） | +1.33（−0.80） | −4.42（+2.41） | adopted | 边际（刚过 0.05 惰性阈），sharpe 降、回撤升，方向是可实现性变好；TRAIN 最优候选 → VAL |
| ep-imp-2 ETF-only + top-2 | improve | 对 u-2 一行 | [[study-ep-imp-2]] | +0.1833（−0.5753） | −0.25（−2.38） | −7.02（−0.19） | rejected | 5% 上限下 2 只吃不下资金：第 3–5 名是填单宽度不是分散；epoch-2 的 N=2 单峰消失 |
| ep-imp-3 ETF-only + 收盘信号、收盘成交 | improve | 对 u-2：run_daily 时点 + 1m 收盘读 | [[study-ep-imp-3]] | −1.7199（−2.4785） | −7.26 | +35.19 | rejected | 可实现形态为负（−53%，两年同号）：收盘仍折价的名字次日不回归 |
| VAL ep-imp-1 2024–25 | improve | 无（候选定稿） | [[study-val-imp-1-e6]] | VAL obj 2.0115 | VAL 7.60 | VAL 13.01 | adopted | 本 epoch 唯一一次 VAL；高于 TRAIN（1.6733），四年同号；⚠ 与 TRAIN 建立在同一不可成交假设上（u-1） |

## 3. 家族内绩效横评 (auto)

| 排名 | 变体 | obj | sharpe | annual% | maxDD% | gate |
|---|---|---|---|---|---|---|
| **1** | **[[15c36e0c_ETF溢价改进版]]** | 1.5642 | 8.87 | 177.88 | 21.46 | ✅ |
| 2 | [[edd94ebc_ETF溢价回撤]] | DQ/— | — | — | — | — |

*1 gate-pass / 2 members. 快照 2026-09-23（TRAIN 2022–2023, 冻结零滑点 ⚠）。由 `wiki-family-build.js` 生成，勿手改。*

## 4. 待研究 / 空白 (research gaps)
- **人类裁决：status → DQ-realizability？** 两条 edge 都 measured、VAL 也过（sharpe 7.60），但 u-1 + ep-imp-3 证明开盘折价与收盘折价两头都不可实现。与 [[PT多策略]] 同一裁决；本轮不改 status。整合层在裁决前不得引用本家族的任何 objective；`edge-redundancy.js` 会把两家族标为 INTEGRATION-REDUNDANT（两条 edge 同名同 status）。
- **edd94ebc 没有本台锚点**（q-ledger）：normalize 应把它重新排进 `data/pending-normalize.json`；它的 MA5 逐只 get_price 循环可能落入 slow-skip，先按 deferred 的更高上限跑。三个入场过滤器（high−low<0.1 / 成交额>8e5 / 收盘>MA5）的归因只在它有锚点之后做；本轮已证 top-2 是负贡献（ep-imp-2）。
- **登记观察、不登记收益**：component 登记若做，只登记「薄 ETF 集合竞价开盘价偏离 T−1 净值、当日回归」这个观察本身（evidence u-1 / u-3），不登记任何收益数。
- **集合竞价可成交量**：日频台按全天成交量的 5% 在开盘价成交；真实可成交的是集合竞价那一笔的量。分钟级数据里的 09:25 成交量在日频台上不可测，属 harness 之外——两个折价家族共用这一空白。
- **§3 显示 epoch-2 的 1.5642**：`wiki-family-build.js` 按「每个源文件 objective 最高的行」取数、不看 epoch，且本轮的 epoch-6 锚点不写 ledger（研究变体不是归一化行）。builder 的通用问题，不在本家族改。
- **improve 已穷尽**：universe（ep-imp-0 采纳）、下界（ep-imp-1 边际、u-4 上限）、集中度（ep-imp-2）、执行时点（u-1 / ep-imp-3）都量过；ETF-only + 下界 1e7 是这条血统在 epoch 6 上的最优点，而最优点不可实现。

## 5. 沿革 (provenance)
- **[[15c36e0c_ETF溢价改进版]]**（postId 15c36e0ce892a62b264d518d2aa5df31，2026-06-01 抓取）：标题「etf基金溢价-改进版-高收益低回撤-速度已最优」，自报 2021-06 起年化 59% / 夏普 2.32 / 回撤 17.6%。最简纯折价反转实现，本页基类。
- **[[edd94ebc_ETF溢价回撤]]**（postId edd94ebc3a42fe6ad845ce0555314b31，2026-06-19 抓取）：「ETF溢价回撤13.12%年化1599%，实盘效果好」——基类的 ETF-only 版 + 三个入场过滤 + top-2，自报 2025-08 起年化 1599% / 夏普 51（短窗）。本台无行。
- **兄弟家族 [[PT多策略]]**：同一机制（成交额 band 5e6–2e7、day_open 信号、top-10 |premium| 加权），2026-09-22 在 epoch 6 上得到同一判决（u-7：+772% → −29%）。
- **研究史**：2026-07-27 epoch-2 auto-study（git e009f67 / a6195c6：q-1 下界 sweep 2e6→1e7/3e7/1e8 = obj +0.47/−0.84/−1.45、q-2 top-N 5→1/2/3 = −0.06/+0.35/+0.15，均无参与上限；页面于 2026-09-21 被 51334e3 刻意清空以测试 /run-family 能否从零建页）→ 2026-09-23 epoch-6 run-family（本页：8 次 TRAIN 回测 + 1 次 VAL，约 23 JQ 分钟，used 123 → ~146；两条 edge measured；VAL 已花在 ep-imp-1 上）。epoch-2 的 q-1 结论「流动 universe 塌掉」在本台复现（u-4），其「1e7 甜点」与 q-2 的「N=2 单峰」在本台消失（ep-imp-1 / ep-imp-2）——两者都是无参与上限下的容量幻觉。

## 6. 研究问答 (study-log)
- **[Q q-ledger]** 成员 edd94ebc 的 ledger 行（§3 显示 DQ/—），零回测（type: probe）
  **→** harness/normalize-train.tsv、四个 .bak、normalize-train.rebuild.json、data/deferred.json、data/series-scan.json 里都没有 edd94ebc；data/pending-normalize.json 也没有排它。它的策略页没有 normalized: 块（15c36e0c 的有），所以 ledger 回退后 normalize-ledger-rebuild.js 无从重建它——§3 的「DQ/—」不是 DQ，是行丢失。它的代码是基类 + 三个入场过滤（昨日 high−low<0.1、成交额>8e5、收盘>MA5）+ top-2 + ETF-only，其中 MA5 用逐只 get_price 循环（每日 ~数百次调用），本台上可能落入 slow-skip
  **⇒** 关闭「edd94ebc 是 DQ」的读法：它从未在本台被量过。打开两件事：(1) normalize 应把它重新排进 pending-normalize（本轮不代做——归一化是 normalize 阶段的账，且它的 MA5 循环可能吃掉 20 分钟）；(2) 本轮 u-2（ETF-only）给它的 universe 一个可比读数，q-2 的 top-2 由 ep-imp-2 在本台重量，剩下的三个过滤器归因留给它有锚点之后
  （Δ Δ 不适用（零回测）。pre-wipe 页面（git a6195c6）记 edd94ebc epoch-2 obj 3.5961 / annual 374.38 / sharpe 14.77 / maxDD 14.77；confidence high；⚠ ledger-row-lost · not-in-pending · zero-cost-probe · per-security-loop） 溯源 [[study-q-ledger]]
- **[Q baseline-e6]** 基类 15c36e0c 在 epoch 6 上的锚点（py2to3(源码) + live OVERRIDE；ledger 只有 epoch-2 行）（type: baseline）
  **→** epoch 6 上基类年化从 178% 掉到 105%，obj 1.56→0.86，仍过闸（sharpe 5.93）。纯基金书，epoch 6 的股票费率 pin 是 no-op；咬到它的是 epoch 4 的两处——order_volume_ratio=0.05 与基金费率 0.00025/min 0 → 0.0003/min 5。费率差每边 0.00005、日频全换两年约 5%，解释不了 −72pp ⇒ 缩水的主体是参与上限：2e6 股的下界比 PT多策略 的 5e6 成交额更薄，一笔单吃掉薄基金一天成交量 5% 以上的成交在 epoch 2 里占了年化的四成。与 PT多策略 的 369→196 同一模式。两年同号为正，回撤几乎全在 2022（17.92 vs 4.73），2023 反而是更强的一年（+134 vs +83）——与 PT多策略 相反（+300 / +121）
  **⇒** 关闭「引用 pre-wipe epoch-2 的 q-1 / q-2 数字」：参与上限改变的正是下界与集中度这两个旋钮本身，两个 sweep 都要在本台重跑（u-4 / ep-imp-1 / ep-imp-2 已排）。打开 realizability 的定量读法：任何 VAL 预期与整合层估值从 105% 起算而不是 178%，而且 5% 对开盘集合竞价上的薄 ETF/LOF 仍然偏宽（u-1 判决）
  （Δ vs ledger epoch-2 行：obj 1.5642→0.8607（−0.7035）· annual 177.88→105.37（−72.5pp）· sharpe 8.87→5.93 · maxDD 21.46→19.30（−2.2pp）；逐年 2022 +83.14（maxDD 17.92 · vol 0.1994 · sharpe~ 3.05 · 上涨日 131/241）/ 2023 +133.78（maxDD 4.73 · vol 0.1553 · sharpe~ 5.48 · 151/242）；复利 1.8314 × 2.3378 = 4.281 ≈ 1 + 3.2095 ✓；confidence high；⚠ anchor · participation-cap-bites · capacity-not-signal · both-years-positive · 2023-stronger · gate-pass（sharpe 5.93）） edge: 流动性溢价 溯源 [[study-baseline-e6]]
- **[Q u-1]** realizability：信号不动（09:30 = 日频台的开盘价），卖/买挪到 14:50（收盘价成交）；market_open 只存 g.order_fund，新增 market_exec（type: probe）
  **→** 同一信号、只把成交从开盘价挪到收盘价，两年从 +321% 变成 +10%（年化 5%、sharpe 0.07）。开盘时对净值的折价到收盘已经回归完毕——不是逐步回归、能在盘中分一杯羹，而是全部发生在开盘那口价与收盘之间。与 PT多策略 u-7（+772% → −29%）同一判决，本家族没有塌到负：等权 top-5 + 含 LOF 的 universe 在收盘价上是零收益而非负漂移（PT 的 |premium| 加权 top-10 最薄 band 是 −29%）。收益 ≈100% 是「在集合竞价的成交价上以全天成交量 5% 成交」这个撮合假设
  **⇒** 关闭一切以 TRAIN 头条为准的引用：105%（或 u-2 的 174%）是集合竞价成交价上的回测伪影，一个不能在开盘集合竞价里以那口价成交的账户拿到的是 ~0。整合层与 type 层不得把本家族当作可拼接的 sleeve；与 PT多策略 一起，「ETF 开盘价偏离净值」这个观察在两个家族上都成立、都不可实现。家族 status 建议 DQ-realizability，由人裁决。打开 ep-imp-3：既然开盘折价到收盘已回归，收盘时看到的折价是新的一次偏离——在收盘买、等次日开盘回归，是唯一可实现的形态，值得一跑
  （Δ vs 锚点：obj 0.8607→−0.1676（−1.0283）· annual 105.37→4.95（−100.4pp）· sharpe 5.93→0.07 · maxDD 19.30→21.71（+2.4pp）· total 320.95→10.14 · 逐年 2022 +83.14→+6.16（maxDD 17.92→21.71 · 上涨日 131→113/241）、2023 +133.78→+3.72（4.73→14.94 · 151→120/242）；confidence high；⚠ realizability-DECISIVE · auction-print-only · both-years-≈0 · DQ（sharpe 0.07）· matches-PT多策略-u-7） edge: 均值回归 溯源 [[study-u-1]]
- **[Q u-2]** universe：get_all_securities(['lof','etf']) → ['etf']（去掉 LOF），一行（type: ablation）
  **→** 去掉 LOF 后年化 +69pp、回撤 −6.8pp、sharpe 5.93→8.06：LOF 腿是拖累，不是来源。差额几乎全在 2022（+83 → +238），2023 持平略降（+134 → +123）。机制读法：ETF 的折价靠一级市场实物申赎（T+0）当日套平，所以开盘折价到收盘回归（u-1）；LOF 的申赎是现金、T+2 确认、有费用，折价是持续的而不是回归的——按「最深折价」排序，LOF 在 2022 熊市里长期占住 top-5 的位置却不回归，还带来更深回撤。CLAUDE.md 记的「LOF/QDII 净值发布滞后造成假折价」这个方向，若成立应表现为 LOF 贡献正收益（假折价被当真折价买入、次日净值更新后价格跟上）；实测相反
  **⇒** 关闭「LOF 净值滞后是折价族收益来源」的公开问题（CLAUDE.md）：LOF 腿在本台上是 −69pp 年化的拖累，NAV 陈旧没有制造可赚的假折价。打开：(1) ETF-only 是本家族第一个 improve 候选（同一次测量，不重跑，登记为 ep-imp-0 adopted-on-TRAIN）；(2) 后续 improve 候选全部建立在 ETF-only 上（ep-imp-1/2/3 已重建）；(3) 兄弟家族 PT多策略 与成员 edd94ebc 本来就是 ETF-only，家族的 base 15c36e0c 是唯一含 LOF 的——家族最优点在 ETF 上。⚠ realizability 否决（u-1）不因此解除：+174% 仍是集合竞价成交价上的数
  （Δ vs 锚点：obj 0.8607→1.6193（+0.7586）· annual 105.37→174.40（+69.0pp）· sharpe 5.93→8.06 · maxDD 19.30→12.47（−6.8pp）· total 320.95→650.87 · 逐年 2022 +83.14→+237.92（maxDD 17.92→12.47 · 上涨日 131→161/241）、2023 +133.78→+123.45（4.73→9.81 · 151→160/242）；confidence high；⚠ LOF-leg-is-drag · 2022-concentrated · gate-pass（sharpe 8.06）· improve-by-subtraction · obj-above-epoch-2-row（1.6193 vs 1.5642）） edge: 均值回归 溯源 [[study-u-2]]
- **[Q u-3]** edge test 均值回归 by mirror：同一 universe（lof+etf）/ 2e6 下界 / top-5 等权，排序降序 + premium>0（买最高溢价）（type: ablation）
  **→** 镜像两年亏掉 98.7%：买开盘价高于净值最多的 5 只基金，两年只有 20% 的交易日是涨的（基类 58%）。折价方向赚、溢价方向亏，符号承载全部信息。与 PT多策略 u-3（−91%，对数近似对称）不同，本家族不对称——lof+etf 的 universe 里最高溢价的名字是 QDII-LOF / 持续高溢价的 LOF（净值陈旧或额度受限），溢价方向除了回归还叠加了这些名字的清算式塌陷；这与 u-2「LOF 腿是拖累」互相印证
  **⇒** 均值回归 升 measured（镜像 −99%、基类 +321%、两年同号；与 u-1 合读：偏离的方向由 NAV 供给，回归发生在开盘价到收盘价之间）。关闭「薄基金 universe 本身有回弹」的读法。不再需要 PT多策略 那样的无 NAV 控制组：u-1 已把「拿掉信号时点」的读数给了（+10%），u-3 把「翻转信号」给了（−99%），两者夹住基类
  （Δ vs 锚点：obj 0.8607→−1.8746（−2.7353）· annual 105.37→−88.72（−194pp）· sharpe 5.93→−4.04 · maxDD 19.30→98.74（+79.4pp）· total 320.95→−98.72 · 逐年 2022 +83.14→−89.39（上涨日 131→57/241）、2023 +133.78→−88.05（151→41/242）；对数尺度 ln(4.21)=+1.44 vs ln(0.013)=−4.36，不对称：镜像亏得远多于基类赚的；confidence high；⚠ edge-test-ran · mirror-collapses · both-years-same-sign · 20%-up-days · asymmetric-vs-PT） edge: 均值回归 溯源 [[study-u-3]]
- **[Q u-4]** edge test 流动性溢价，流动臂：昨日 share-volume 下界 2e6 → 1e8（universe lof+etf、top-5 等权不动），一行（type: sweep）
  **→** 只留昨日成交量 ≥ 1e8 股的流动基金，同一折价规则只剩年化 34% / sharpe 1.04 / 回撤 24%——过不了 1.5 闸门，obj 归零。两年仍为正（+46 / +23）。与 epoch-2 的同臂读数（sharpe 1.10）一致：参与上限没有改变这条结论，因为流动基金上 5% 本来就不绑。折价信号在流动 ETF 上是一个弱的、DQ 的信号；做成 sharpe 6–8 的，是薄 universe
  **⇒** 流动性溢价 升 measured，但带 ep-imp-1 的细化：下界 2e6→1e7 不丢收益（+7.8pp），2e6→1e8 丢掉全部——收益活在 1e7–1e8 股这一档，而不是最薄的 2e6–1e7（那一档在 5% 参与上限下本就填不满，还是 LOF 扎堆的地方）。关闭「把 sleeve 移植到流动基金」作为 improve：那是 obj 0.09 的书。整合层若要一个「可真实成交」的读数，是 34% / sharpe 1.04，不是 105% / 174%
  （Δ vs 锚点：obj 0.8607→0.0937（−0.7670）· annual 105.37→33.66（−71.7pp）· sharpe 5.93→1.04 · maxDD 19.30→24.29（+5.0pp）· total 320.95→78.52 · 逐年 2022 +83.14→+45.55（maxDD 17.92→23.79 · sharpe~ 3.05→1.24）、2023 +133.78→+23.46（4.73→14.68 · 5.48→0.79）；pre-wipe epoch-2 同臂 sharpe 1.10 / Δobj −1.45；confidence high；⚠ edge-test-ran · liquid-arm-DQ · both-years-still-positive · reproduces-epoch-2-reading · DQ） edge: 流动性溢价 溯源 [[study-u-4]]
- **[Q ep-imp-0]** 采纳 u-2 的 ETF-only universe 作为候选（同一次测量，不重跑）（type: improve）
  **→** ETF-only 是本家族在 epoch 6 上第一个过闸且优于基类的候选（obj 1.6193 / sharpe 8.06 / maxDD 12.47），高于基类的 epoch-2 ledger 行 1.5642。改动是减法：去掉 LOF
  **⇒** 后续 improve 全部以 ETF-only 为起点（ep-imp-1/2/3 已按此重建，Δ 对 u-2 量）。它不是 VAL 候选的终点——ep-imp-1 若更高则由它去 VAL
  （Δ = u-2：vs 锚点 obj +0.7586 · annual +69.0pp · sharpe +2.13 · maxDD −6.8pp；confidence high；⚠ adopted-on-TRAIN · shares-measurement-with-u-2 · zero-extra-cost） edge: 均值回归 溯源 [[study-ep-imp-0]]
- **[Q ep-imp-1]** ETF-only + share-volume 下界 2e6 → 1e7（epoch-2 q-1 甜点），对 u-2 一行（type: improve）
  **→** 收紧下界到 1e7 股：年化 +7.8pp、回撤 +2.4pp、sharpe −0.8，obj +0.054——刚过惰性阈（0.05），方向是可实现性变好的方向，但 epoch-2 的甜点（+0.47、回撤减半）没有了：那时最薄一档的收益是无参与上限的容量幻觉，现在 5% 上限已把它削掉，收紧下界只是不再买那些填不满的名字。2022 +242 / 2023 +134，两年都略高于 u-2
  **⇒** 关闭下界作为旋钮：1e7 与 2e6 在 obj 上几乎无差（+0.05），1e8 塌掉（u-4）——收益活在 1e7–1e8 股，下界在这个区间内怎么放都差不多。按 objective 规则 ep-imp-1 是 TRAIN 最优候选，本家族的一次 VAL 花在它上（而不是 u-2）；⚠ 采纳是 TRAIN 内的相对判断，realizability 否决（u-1）不变
  （Δ vs u-2：obj 1.6193→1.6733（+0.0540）· annual 174.40→182.21（+7.8pp）· sharpe 8.06→7.26（−0.80）· maxDD 12.47→14.88（+2.4pp）· total 650.87→694.16 ‖ vs 锚点 +0.8126 · 逐年 2022 +241.66（maxDD 14.88 · sharpe~ 4.38 · 上涨日 145/241）/ 2023 +133.75（8.76 · 3.93 · 141/242）；confidence med；⚠ adopted-marginal · Δobj-at-inert-threshold · sharpe-down-maxDD-up · realizability-direction · gate-pass（sharpe 7.26）） edge: 流动性溢价 溯源 [[study-ep-imp-1]]
- **[Q ep-imp-2]** ETF-only + top-5 → top-2（epoch-2 q-2 的单峰顶点），对 u-2 一行（type: improve）
  **→** 集中到最深折价的 2 只：年化 −58pp、回撤不变。epoch-2 的「N=2 单峰、+0.35」在本台上翻成 −0.58：5% 参与上限下最深的 2 只吃不下 100 万资金，第 3–5 名是填单宽度而不是分散（与 PT多策略 imp-2 的 top-10→top-5 −0.14 同一机制，本家族更陡因为从 5 到 2）。两年都低于 u-2（2022 +170 vs +238，2023 +75 vs +123）
  **⇒** 关闭集中度作为 improve（向下：填单宽度；向上 top-N>5 = 更浅的折价，u-4 已示范流动/浅折价名字只加回撤不加收益）。pre-wipe §4 的「edd94ebc 的 top-2 + 三个过滤器解释 ~2.0 gap」这条归因作废：top-2 在本台是负贡献，edd94ebc 的 epoch-2 头条（3.5961）应是无参与上限下 top-2 吃满薄基金成交量的容量幻觉，它有锚点之前不再对它归因
  （Δ vs u-2：obj 1.6193→1.0440（−0.5753）· annual 174.40→116.68（−57.7pp）· sharpe 8.06→5.68（−2.38）· maxDD 12.47→12.28（−0.2pp）· total 650.87→368.52 ‖ vs 锚点 +0.1833 · 逐年 2022 +170.29（maxDD 12.28 · 上涨日 153/241）/ 2023 +75.39（4.53 · 150/242）；confidence high；⚠ rejected · fill-width-not-diversification · epoch-2-peak-gone · both-years-lower · gate-pass（sharpe 5.68）） edge: 均值回归 溯源 [[study-ep-imp-2]]
- **[Q ep-imp-3]** 可实现形态：ETF-only + 信号与成交都在 14:50（last_price 换成 get_price(frequency='1m', count=1) 的 14:49 分钟收盘 vs T−1 净值，收盘价买入），对 u-2 两处一个概念（type: improve）
  **→** 在收盘看到的折价、在收盘买、等次日回归：两年 −53%、回撤 54%，两年同号为负。收盘时仍然折价最深的 ETF 不是「新的一次偏离」，而是当天没被套平的——薄到实物申赎也不去套的名字，持有它们拿到的是薄 ETF 的负漂移（与 PT多策略 u-4 无信号最薄 10 只 −42% 同量级）。日频台上 14:50 读当日 1m 数据被 avoid_future_data 放行（run completed、有成交），这是一个可复用的读法
  **⇒** 关闭「可实现形态」这条线：开盘折价（u-1：到收盘已回归）与收盘折价（本条：次日不回归、还亏）两头都测了，机制只存在于集合竞价的成交价上，本家族没有任何可实现候选。improve 队列清空：universe（ep-imp-0 采纳）、下界（ep-imp-1 边际）、集中度（ep-imp-2 否决）、执行时点（ep-imp-3 否决）。家族 status 建议 DQ-realizability，与 PT多策略 同一裁决，由人定
  （Δ vs u-2：obj 1.6193→−0.8592（−2.4785）· annual 174.40→−31.43（−205.8pp）· sharpe 8.06→−1.33 · maxDD 12.47→54.49（+42.0pp）· total 650.87→−52.93 ‖ vs 锚点 −1.7199 · 逐年 2022 −42.35（maxDD 53.04 · 上涨日 101/241）/ 2023 −18.42（39.36 · 106/242）；confidence high；⚠ rejected · realizable-form-negative · both-years-negative · DQ · 1m-read-at-1450-works-on-daily-bench） edge: 均值回归 溯源 [[study-ep-imp-3]]
- **[Q val-imp-1-e6]** 候选 ep-imp-1（ETF-only + 下界 1e7）在 VAL 2024-01-01→2025-12-31 上跑一次——本家族 epoch 6 的唯一一次验证，花在 TRAIN 最优候选上（type: validate）
  **→** VAL 不衰减、反而高于 TRAIN：年化 214% / sharpe 7.6 / 回撤 13%，过闸。四个年度（2022–2025）在「开盘价按成交量 5% 可成交」这个假设下都成立——与 PT多策略 的 VAL（242%，同样高于 TRAIN）同一形态。这不是对机制的新信息：u-1 已证明每一个数字都是集合竞价成交价上的伪影，VAL 只说明伪影在 2024–25 仍在
  **⇒** 关闭本 epoch 的 VAL（已花，不可再花；JQ_ALLOW_REVAL 是人的开关）。关闭「VAL 会把它筛掉」：不会。剩下的唯一一道门是人裁决 status：两条 edge measured、VAL 过、但 u-1 + ep-imp-3 证明开盘折价与收盘折价两头都不可实现。整合层引用本家族时按 u-4 的 34% / sharpe 1.04（流动 universe）估值，不按 214%
  （Δ VAL：total 886.96 · annual 214.16 · sharpe 7.60 · maxDD 13.01 · obj 2.0115 ‖ 对照 TRAIN ep-imp-1：annual 182.21 · sharpe 7.26 · maxDD 14.88 · obj 1.6733 ⇒ VAL 高 +0.34 obj；逐年见 description；confidence high；⚠ VAL-spent · val-above-train · four-years-same-sign · gate-pass（sharpe 7.60）· ⚠零滑点 · ⚠开盘价成交假设（realizability 见 u-1 / ep-imp-3）） edge: 均值回归 溯源 [[study-val-imp-1-e6]]
