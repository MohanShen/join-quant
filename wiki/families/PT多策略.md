---
family: PT多策略
aliases: [PT多策略并行, PT分仓隔离]
concepts: [[ETF轮动]]
edge:
  - name: 流动性溢价
    kind: risk-premium
    claim: "收益来自把 universe 锁在昨日成交额 5e6–2e7 的最薄 ETF 上：折价在薄基金里最深、也最能回归；同一规则搬到流动基金（5e7–1e8）上应失去风险调整后的 edge"
    test: "同一规则、同一权重、同一 top-10，只把成交额 band 换成 5e7–1e8（u-1）与去掉 2e7 上界（u-2）；若流动 band 的 objective ≥ 基类 −0.1，证伪"
    status: measured
    evidence: "[[study-u-1]]（流动 band 5e7–1e8：obj 1.8592→0.0076，annual 22.7 / sharpe 0.94 / maxDD 22.0，DQ，两年仍为正）+ [[study-u-2]]（去上界：annual −1.2pp、maxDD +4.2pp——上界是回撤过滤器，收益在 band 下端）+ [[study-pt-imp-1]]（下界 5e6→1e7：annual −58pp，回撤不变——收益在最薄一半）。⚠ 偏离的幅度由薄度供给：band 越薄头条越高、越不可成交；参与上限 5% 已把 epoch-2 的 369% 腰斩到 196%（[[study-baseline-e6]]）"
  - name: 均值回归
    kind: anomaly
    claim: "在薄 band 内，信号是 09:25 day_open/NAV 的折价：买最深折价、等价格向净值回归。若同一 band 的信号翻成买最高溢价、或换成不含 NAV 信息的「最薄 10 只等权」也赚到同量级，则折价信号本身不承载信息"
    test: "u-3 镜像（premium>0，取最大 10 只）与 u-4 无信号控制组；若镜像或控制组的 objective ≥ 基类 −0.1，证伪"
    status: measured
    evidence: "[[study-u-3]]（镜像买最高溢价：total −91.22%，annual −70.4 / sharpe −5.24 / maxDD 91.2，上涨日 14%；对数尺度与基类 +2.17 / −2.43 近似对称）+ [[study-u-4]]（无 NAV 信息、最薄 10 只等权：total −42.26%，annual −24.0 / maxDD 43.3，两年同号为负）+ [[study-u-5]]（折价深度加权比等权多 17pp 年化——深度有边际信息）。信号承重、universe 不承重；两条 edge 是同一件事的两面：偏离的方向由 NAV 供给、幅度由薄度供给"
base: [[fa0d3bd9_PT多策略并行]]
bestVariant: [[fa0d3bd9_PT多策略并行]]
bestObjective: 3.5952
memberCount: 2
sources: { normalized: 2, study: 6, enhance: 2 }
realism: "⚠⚠ 头条不可实现，且已定量：收益 100% 是「在集合竞价的开盘成交价上买到开盘价低于 T−1 净值的薄 ETF（昨日成交额 5e6–2e7）」这一件事。同一信号把成交挪到 14:50 → 两年 −29%、回撤 40%（u-7），与无信号的最薄 10 只等权（u-4，−42%）同量级；偏离到收盘不但已回归、还越过了。偏离幅度由薄度供给：band 三档单调（5e6–2e7 年化 196 / 1e7–2e7 138 / 5e7–1e8 23，后者 sharpe 0.94 DQ），5% 参与上限已把 epoch-2 的 369% 腰斩到 196%（baseline-e6），而薄 ETF 的集合竞价成交量远小于全天的 5%。零滑点台。TRAIN 196% / VAL 242% 都建立在同一不可成交假设上，整合层不得把本家族当作可拼接 sleeve；可登记的只有「薄 ETF 集合竞价开盘价偏离净值」这个观察。建议 status → DQ-realizability，由人裁决"
status: active
updatedAt: 2026-09-23
---

# PT多策略 — strategy family

**一句话**：标题说「四大策略并行 / 自有账本」，被回测的代码是**单一 ETF 折价回归 sleeve**：09:20 取昨日成交额落在 5e6–2e7 的最薄 ETF，09:25 用集合竞价开盘价算 premium = open/NAV(T−1) − 1，留折价者、取最深 10 只按 |premium| 加权，09:30 市价成交，离开 top-10 即卖。epoch-6 TRAIN 年化 195.7% / sharpe 11.15 / maxDD 9.82%，VAL 2024–25 年化 241.7% / sharpe 12.82 / maxDD 5.92%——**而把成交从开盘价挪到 14:50，同一信号两年 −29%**（u-7）：收益全部是集合竞价那口成交价，不可实现。

## 1. 基类 (base archetype)   ← [[study-baseline-e6]] 起溯源；pre-wipe epoch-2 的 q-1（band sweep，git e009f67）在 §5 引用，数字不横比
- **基类**：[[fa0d3bd9_PT多策略并行]]（455 行）。[[c70281d3_PT多策略分仓隔离插件V1.3]] 是同一 sleeve（1–142 行）加 4,200 行落在模块级 `'''` 字符串里的死代码（q-struct）；两者 ledger 上 Δobj −0.014。家族实际只有 **一份代码体**。epoch-6 快照 `study/PT多策略/baseline-e6.py`（`build-e6.js` 生成；所有变体 = 源码 + 断言过的一处改动 + live OVERRIDE）。源码自设基金费率 0.00025 与 0.1% 滑点（OVERRIDE 钉死），不设 order_volume_ratio——epoch 4 的 5% 参与上限是唯一咬到它的 pin，annual 369 → 196。
- **Universe 选股池**：`get_all_securities(['etf'], previous_date)` 全部 ETF；09:20 取昨日 `money`（成交额）落在 **(5e6, 2e7)** 的名字，再取 `get_extras('unit_net_value', end_date=previous_date)` 的 **T−1 净值**。
- **交易频率**：日频，三个 run_daily：09:20 备数据 / 09:25 算信号 / 09:30 执行。
- **交易机制**：
  - *入场 / 信号*：09:25 `premium = (current_data.day_open / unit_net_value − 1) × 100`，剔停牌；留 premium < 0，升序取 **top-10**，权重 = |premium| / Σ|premium|，目标市值按（现金 + 预期卖出）分配。
  - *调仓*：09:30 先 `order(fund, −amount)` 卖出不在 top-10 的持仓，再按权重从可用现金买入新进者（源码把 `weights`（对应 order_fund）与 `buy_list` zip，持仓错位时买单权重错配——基类行为的一部分，未改）。
  - *止损 / 风控*：**无**。c70281d3 加的 −5% 止损 / +10% 止盈在 ledger 上近乎惰性。
- **基线绩效**（frozen harness epoch 6）：
  | | objective | sharpe | annual% | maxDD% | 2022 total% | 2023 total% |
  |---|---|---|---|---|---|---|
  | **baseline-e6（锚点，= ledger epoch-4 行）** | **1.8592** | 11.15 | 195.74 | 9.82 | +300.50 | +121.38 |
  | c70281d3（ledger epoch-6 行） | 1.8448 | 11.20 | 192.66 | 8.18 | — | — |
  | u-1 流动 band 5e7–1e8 | 0.0076 | 0.94 | 22.74 | 21.98 | +14.53 | +30.57 |
  | u-2 去 2e7 上界 | 1.8055 | 9.30 | 194.54 | 13.99 | +278.27 | +129.77 |
  | u-3 镜像：买最高溢价 | −1.6164 | −5.24 | −70.42 | 91.22 | −79.25 | −57.48 |
  | u-4 无信号：最薄 10 只等权 | −0.6734 | −1.71 | −24.04 | 43.30 | −22.41 | −24.61 |
  | u-5 等权 | 1.7020 | 10.37 | 178.93 | 8.73 | +251.38 | +124.50 |
  | u-7 同信号、14:50 成交 | −0.5601 | −1.09 | −16.05 | 39.96 | −31.39 | +2.75 |
  | pt-imp-1 下界 1e7（rejected） | 1.2859 | 7.29 | 137.68 | 9.09 | +181.24 | +102.50 |
  | pt-imp-2 top-5（rejected） | 1.7191 | 10.49 | 181.58 | 9.67 | +317.80 | +92.35 |
  | **VAL 2024–25 基类**（本 epoch 唯一一次） | 2.3581 | 12.82 | 241.73 | 5.92 | 2024 +373.60 | 2025 +147.40 |
- **为什么有效**（[[study-u-3]] / [[study-u-4]] / [[study-u-1]] / [[study-u-2]] / [[study-pt-imp-1]] / [[study-u-7]]）：两条 measured edge，是同一件事的两面：
  - *均值回归*（对 NAV）：信号承重、universe 不承重。镜像买最高溢价两年 −91%（对数尺度与基类 +2.17 / −2.43 近似对称），无 NAV 信息的最薄 10 只等权 −42%，基类 +772%。折价深度还有边际信息（等权少 17pp 年化，u-5）。
  - *流动性溢价*：偏离的幅度由薄度供给。流动 band 上同一规则只剩年化 23% / sharpe 0.94（DQ），去上界收益不变只加回撤，收紧下界到 1e7 少 58pp——band 越薄头条越高。
  - **但机制只存在于集合竞价的成交价上**（u-7）：把执行挪到 14:50，同一信号 −29%，与无信号 universe 同量级。偏离在开盘后不是「逐步回归」，而是到收盘已越过——这本书赚的是「用全天成交量的 5% 在开盘那一口价成交」这个回测撮合假设。
- **⚠ 现实性 / 容量**：见 frontmatter `realism`。

## 2. 变体 (variants)   ← epoch 6；Δ 对 baseline-e6（obj 1.8592）；**失败的变体也记**（判定: rejected）
| 变体 | 类型 | 相对基类的改动 | 来源 | Δobjective | Δsharpe | ΔmaxDD | 判定 | 结论 |
|---|---|---|---|---|---|---|---|---|
| [[fa0d3bd9_PT多策略并行]] | raw | 无 | normalized-raw | 0 | 0 | 0 | — | 基类；epoch-6 锚点逐位复现 epoch-4 行；§3 里的 3.5952 是 epoch-2 无参与上限的数 |
| [[c70281d3_PT多策略分仓隔离插件V1.3]] | raw | 09:30 last_price 作信号 + −5%/+10% 止损止盈 + 4,200 行死代码 | normalized-raw | −0.0144 | +0.05 | −1.64 | — | q-struct：同一 sleeve，差异近乎惰性；「分仓隔离插件」从不执行 |
| u-1 流动 band 5e7–1e8 | understand | band 一行 | [[study-u-1]] | −1.8516 | −10.21 | +12.16 | informative | 流动性溢价 (a)：流动基金上 DQ（sharpe 0.94），两年仍为正 |
| u-2 去 2e7 上界 | understand | band 一行 | [[study-u-2]] | −0.0537 | −1.85 | +4.17 | informative | 流动性溢价 (b)：上界是回撤过滤器，收益不变、回撤 +4.2pp |
| u-3 镜像买最高溢价 | understand | 排序降序 + premium>0 | [[study-u-3]] | −3.4756 | −16.39 | +81.40 | informative | 均值回归 measured：镜像 −91%，对数对称，上涨日 14% |
| u-4 无信号最薄 10 只等权 | understand | premium → −1e7/money + 等权 | [[study-u-4]] | −2.5326 | −12.86 | +33.48 | informative | universe 本身 −42%：信号承重、universe 是载体 |
| u-5 等权 | understand | weights 一行 | [[study-u-5]] | −0.1572 | −0.78 | −1.09 | informative | 折价深度有边际信息（−17pp 年化，差额在 2022） |
| u-7 同信号、14:50 成交 | understand | run_daily 时点一行 | [[study-u-7]] | −2.4193 | −12.24 | +30.14 | informative | **realizability 判决**：偏离只在集合竞价成交价上存在，收盘价买入 −29% |
| pt-imp-1 下界 5e6→1e7 | improve | band 一行 | [[study-pt-imp-1]] | −0.5733 | −3.86 | −0.73 | rejected | 收益跟着薄尾走（−58pp 年化），回撤不跟；band 三档单调，无甜点 |
| pt-imp-2 top-10→top-5 | improve | head 一行 | [[study-pt-imp-2]] | −0.1401 | −0.66 | −0.15 | rejected | 填单宽度不是分散：5% 上限下 top-5 吃不下资金，2023 现金拖累 |
| VAL 基类 2024–25 | improve | 无（基类定稿） | [[study-val-base-e6]] | VAL obj 2.3581 | VAL 12.82 | VAL 5.92 | adopted | 本 epoch 唯一一次 VAL；高于 TRAIN，四年同号；⚠ 与 TRAIN 建立在同一不可成交假设上（u-7） |

## 3. 家族内绩效横评 (auto)

| 排名 | 变体 | obj | sharpe | annual% | maxDD% | gate |
|---|---|---|---|---|---|---|
| **1** | **[[fa0d3bd9_PT多策略并行]]** | 3.5952 | 18.16 | 369.07 | 9.55 | ✅ |
| 2 | [[c70281d3_PT多策略分仓隔离插件V1.3]] | 3.5423 | 18.12 | 362.33 | 8.10 | ✅ |

*2 gate-pass / 2 members. 快照 2026-09-23（TRAIN 2022–2023, 冻结零滑点 ⚠）。由 `wiki-family-build.js` 生成，勿手改。*

## 4. 待研究 / 空白 (research gaps)
- **人类裁决：status → DQ-realizability？** 两条 edge 都 measured、VAL 也过（sharpe 12.82），但 u-7 证明收益只存在于集合竞价的成交价上。按 wiki-schema 家族 `status` 只有 active / deprecated / DQ；本轮不改，留给人裁决。整合层在裁决前不得引用本家族的任何 objective。
- **集合竞价可成交量**：回测按全天成交量的 5% 在开盘价成交；真实可成交的是集合竞价那一笔的量（薄 ETF 上常常只有几手）。若要给「可实现版本」定尺寸，需要分钟级数据里的 09:25 成交量——日频台上不可测，属 harness 之外。
- **NAV 是 T−1 的**：premium 里混着隔夜指数变动。u-1 把这一分量的上界定在流动 band 的年化 23% / sharpe 0.94——若「隔夜跌后反弹」是机制，流动 ETF 上也该看到，没有。可以不再花预算。
- **LOF / QDII 的净值发布滞后**（CLAUDE.md 对折价族的公开问题）：本家族 universe 是 `['etf']`，不含 LOF；QDII-ETF 的 T−1 NAV 滞后一天可能制造「假折价」——那部分若被 u-7 的 14:50 成交拿到，应为正，实测为负，说明它不是主要来源。未单独测。
- **§3 显示 epoch-2 的 3.5952**：`wiki-family-build.js` 按「每个源文件 objective 最高的行」取数、不看 epoch，所以家族头条与 `bestObjective` 仍是无参与上限的旧数（epoch-6 应为 1.8592 / 1.8448）。是 builder 的通用问题，不在本家族改。
- **c70281d3 桩页的概念是死代码的概念**（小市值因子 / 打板与涨停）：已在其 备注 挂旗，frontmatter 等 `/ingest-strategy` 重写；[[fa0d3bd9_PT多策略并行]] 的「忠实翻译」同样按标题写、与代码不符，已挂旗。
- **improve 已穷尽**：band 上界（u-2）、下界（imp-1）、权重（u-5）、集中度（imp-2）、执行时点（u-7）都不优于原值；基类是这条血统在 epoch 6 上的最优点，而最优点不可实现。

## 5. 沿革 (provenance)
- **[[fa0d3bd9_PT多策略并行]]**（postId fa0d3bd991f6791c82aac0fbbc559a00，2026-06-23 抓取）：标题「P-T多策略并行实战：用"自有账本"实现四大策略各安其位」；文件头残留「克隆自 post/595 鳄鱼法则 / 陈小米」，与代码无关。自报 2024-12 起年化 557% / 夏普 21。代码 = 本页 §1 的单一 sleeve。
- **[[c70281d3_PT多策略分仓隔离插件V1.3]]**（postId c70281d3cb9f773e1888220777f8956c，2026-07-18 抓取）：「PT」= PTrade 券商端；「分仓隔离插件」是把 PTrade 的子账户框架搬到聚宽的兼容层——整段被作者用 `'''` 注释掉（143–4355 行），实际运行的 1–142 行是 fa0d3bd9 的简化改写（last_price 信号、加止损止盈）。
- **研究史**：2026-07-27 epoch-2 auto-study（git e009f67：q-1 band sweep——流动 band obj 0.0535 / 去上界 2.8897 vs 基类 3.5955；页面于 2026-09-22 被 51334e3 刻意清空以测试 /run-family 能否从零建页）→ 2026-09-22/23 epoch-6 run-family（本页：10 次 TRAIN 回测 + 1 次 VAL，约 35 JQ 分钟，used 88 → 123；两条 edge measured；VAL 已花在基类上）。epoch-2 的 q-1 结论（流动 band 崩塌）在本台复现（u-1），数字不横比。

## 6. 研究问答 (study-log)
- **[Q q-struct]** 家族成员计数：c70281d3 的 4358 行「分仓隔离插件」是否真的运行（零回测，逐行读源码）（type: probe）
  **→** c70281d3 第 143 行与第 4355 行是一对模块级 '''：其间 4,200 行（第二个 initialize、subPortfolio/subPosition/subOrder 类、「小市值策略A」、PTrade 兼容层）全部在字符串字面量里，从不执行。真正跑的是 1–142 行：与 fa0d3bd9 同一 ETF 折价 sleeve（band 5e6–2e7、premium<0、top-10、|premium| 加权），差异只有三处——09:30 的 last_price 取代 09:25 的 day_open 作信号、多一个 09:30/14:59 的 −5% 止损 / +10% 止盈、order_target_value 直下不走交易计划。ledger 上两者 obj 只差 0.014，三处差异合起来近乎惰性。家族 = 一份代码体；「四大策略并行 / 自有账本 / 分仓隔离」是标题，不是被回测的东西
  **⇒** 关闭「c70281d3 是多策略、要拆它的子策略」（pre-wipe §4 第一条）：没有子策略可拆。家族的独立证据量 = 1 份代码体、2 次归档；一切 Δ 只需对 fa0d3bd9 的锚点量。同时关闭「借 c70281d3 的止损止盈到基类」作为 improve——ledger 已经量了，−0.014
  （Δ Δ 不适用（零回测）。ledger 对照：c70281d3 epoch-6 行 annual 192.66 / sharpe 11.20 / maxDD 8.18 / obj 1.8448 vs fa0d3bd9 锚点 195.74 / 11.15 / 9.82 / 1.8592 ⇒ Δobj −0.014、annual −3.1pp、maxDD −1.6pp；confidence high；⚠ member-count-inflated · dead-code · zero-cost-probe · stub-concepts-wrong（c70281d3 桩页标了 小市值因子/打板与涨停，描述的是死代码）） 溯源 [[study-q-struct]]
- **[Q baseline-e6]** 基类 fa0d3bd9 在 epoch 6 上的锚点（源码 + live OVERRIDE；ledger 只有 epoch 2 / 4 行）（type: baseline）
  **→** epoch-6 锚点逐位复现 epoch-4 行（纯 ETF 书，epoch 6 的股票费率 pin 是 no-op）。腰斩发生在 epoch 4：对这本书 epoch 4 只咬两处——order_volume_ratio=0.05 与基金费率 0.00025→0.0003；费率差每边 0.00005、每日近乎全换，两年合计约 5%，解释不了 annual −173pp ⇒ epoch-2 的 369% 里约一半是「一笔单吃掉薄基金一天成交量 5% 以上」的成交，是容量，不是信号。两年都强正：2022（熊）+300%、2023 +121%，回撤全在 2022（9.82 vs 2.69），2023 的 vol 只有 2022 的一半
  **⇒** 关闭「引用 pre-wipe epoch-2 q-1 的数字」：参与上限改变的正是 band 这件事本身，band sweep 必须在本台重跑（u-1 / u-2 已排）。打开 realizability 的定量读法：仅仅把成交限在成交量 5% 就少一半，任何 VAL 预期与整合层估值都应从 196% 而不是 369% 起算，而且 5% 对开盘集合竞价上的薄 ETF 仍然偏宽
  （Δ vs ledger epoch-4 行：total 772.01 = 772.01 · annual 195.74 = 195.74 · sharpe 11.15 = 11.15 · maxDD 9.82 = 9.82 · obj 1.8592，逐位复现；vs epoch-2 行：annual 369.07 → 195.74（−173pp）· sharpe 18.16 → 11.15 · maxDD 9.55 → 9.82；逐年 2022 +300.50（maxDD 9.82 · vol 0.2253 · sharpe~ 6.34 · 上涨日 164/241）/ 2023 +121.38（maxDD 2.69 · vol 0.1181 · sharpe~ 6.68 · 159/242）；confidence high；⚠ anchor · reproduces-epoch-4 · participation-cap-halves-return · capacity-not-signal · both-years-positive · gate-pass（sharpe 11.15）） edge: 流动性溢价 溯源 [[study-baseline-e6]]
- **[Q u-1]** edge test 流动性溢价 (a)：同一规则、同一权重、同一 top-10，成交额 band 5e6–2e7 → 5e7–1e8（流动基金），一行（type: sweep）
  **→** 搬到流动 band 后同一折价规则只剩年化 22.7%、sharpe 0.94、回撤 22%——过不了 1.5 闸门，obj 归零。但没有变负：两年各 +14.5% / +30.6%，仍是正的。与 epoch-2 的同臂读数（0.05 / 1.09）一致，参与上限没有改变这条结论。折价信号在流动 ETF 上是一个弱的、DQ 的信号；把它做成 sharpe 11 的，是薄 band
  **⇒** 流动性溢价 的 (a) 臂跑了、未证伪；等 (b) 臂 u-2 再定 status。关闭「把 sleeve 移植到流动基金」作为 improve：那是 obj 0.008 的书。同时把 realizability 判决写成数字：唯一能真实成交的 band 上，这条血统是年化 23% / 回撤 22% 的东西，任何整合层引用都应按这个数而不是 196%
  （Δ vs 锚点：obj 1.8592→0.0076（−1.8516）· annual 195.74→22.74（−173.0pp）· sharpe 11.15→0.94 · maxDD 9.82→21.98（+12.2pp）· total 772.01→50.56 · 逐年 2022 +300.50→+14.53（maxDD 9.82→21.98 · sharpe~ 6.34→0.55）、2023 +121.38→+30.57（2.69→10.77 · 6.68→1.43）；pre-wipe epoch-2 同臂 obj 0.0535 / sharpe 1.09；confidence high；⚠ edge-test-ran · liquid-band-DQ · both-years-still-positive · reproduces-epoch-2-reading · DQ） edge: 流动性溢价 溯源 [[study-u-1]]
- **[Q u-2]** edge test 流动性溢价 (b)：去掉 2e7 上界、保留 5e6 下界（流动基金可以挤进 top-10），一行（type: sweep）
  **→** 放开上界后收益几乎不动（annual −1.2pp），回撤 +4.2pp、sharpe −1.85。在 epoch 2（无参与上限）同一臂丢了 0.71 obj，现在只丢 0.05：有了 5% 上限之后，上界对「选谁」几乎不起作用——最深折价本来就在薄基金里，top-10 by 折价深度基本还是那些名字；偶尔挤进来的流动基金带来的是回撤（2022 13.99 vs 9.82），不是收益。上界是一道回撤过滤器，不是收益来源
  **⇒** 流动性溢价 升 measured：(a) 只留流动基金 → 塌到 DQ（u-1）；(b) 放流动基金进来 → 收益不变、只加回撤（u-2）。收益活在 band 的下端（薄），不在上界的「排除」里；关闭「2e7 上界是诀窍」的读法。打开 pt-imp-1：从下端反过来问——丢掉 band 最薄的一半（下界 5e6 → 1e7），收益跟着薄尾走还是回撤跟着走
  （Δ vs 锚点：obj 1.8592→1.8055（−0.0537）· annual 195.74→194.54（−1.2pp）· sharpe 11.15→9.30 · maxDD 9.82→13.99（+4.2pp）· total 772.01→764.97 · 逐年 2022 +300.50→+278.27（maxDD 9.82→13.99）、2023 +121.38→+129.77（2.69→5.39）；pre-wipe epoch-2 同臂 obj 2.8897（−0.71 vs 3.5955）；confidence high；⚠ edge-test-ran · ceiling-is-drawdown-filter · return-invariant · gate-pass（sharpe 9.30）） edge: 流动性溢价 溯源 [[study-u-2]]
- **[Q u-6]** 基类曲线逐年拆（2022 熊 / 2023 震荡），零回测，读 baseline-e6 的曲线（type: regime）
  **→** 两年同号强正，没有「2022 专属」：熊市年赚得更多（+300 vs +121）也承担全部回撤（9.82 vs 2.69）；2023 的 vol 只有 2022 的一半，风险调整后两年几乎一样（sharpe~ 6.3 / 6.7）。上涨日占比两年都在 2/3——这是一个每天赚一点、极少大亏的分布，与 多因子ML / 打板短线 / 大小盘轮动 那条「收益集中在 2022」的模式不同，也与 网格 的「99% 在一个半年」不同
  **⇒** 关闭「TRAIN 内部 regime 承载」：两年各自都过闸，本轮不需要再花子窗回测。打开的唯一 regime 检验是 VAL 2024–25（2024-02 微盘踩踏对薄 ETF 的开盘折价是未知的一课）——本家族的一次 VAL 应留给基类或 on-mechanism 候选，不留给任何改 band 的变体
  （Δ 2022：total +300.50 · maxDD 9.82 · vol 0.2253 · sharpe~ 6.34 · 上涨日 164/241（68%）‖ 2023：total +121.38 · maxDD 2.69 · vol 0.1181 · sharpe~ 6.68 · 159/242（66%）；复利校验 4.0050 × 2.2138 = 8.867 ≈ 1 + 7.7201 ✓；confidence high；⚠ both-years-positive · not-regime-carried · vol-halves-in-2023 · zero-cost） 溯源 [[study-u-6]]
- **[Q u-3]** edge test 均值回归 by mirror：同一薄 band、同一 |premium| 加权、同一 top-10，只把信号翻成买最高溢价（premium>0，降序），两行（type: ablation）
  **→** 镜像两年亏掉 91%：买开盘价高于净值最多的薄 ETF，两年只有 14% 的交易日是涨的（基类 68%）。对数尺度上基类 +2.17 与镜像 −2.43 近似对称——收益就是「开盘价对净值的偏离在当天/次日回归」这一件事：折价方向赚，溢价方向亏，量级相同。这是 均值回归（对 NAV）能给出的最强形态
  **⇒** 均值回归 的镜像臂跑了且未证伪（等 u-4 的无信号控制组定 status）。关闭「薄 ETF universe 本身有回弹/beta」的读法：若是 universe，镜像不会塌到 −91%。同时打开 realizability 的机制问题——信号是 09:25 的集合竞价开盘价，回归发生在开盘之后；一本在开盘价上按成交量 5% 成交的书，实际买到的是集合竞价那一笔的价格，而薄 ETF 的集合竞价成交量远小于全天的 5%
  （Δ vs 锚点：obj 1.8592→−1.6164（−3.4756）· annual 195.74→−70.42（−266pp）· sharpe 11.15→−5.24 · maxDD 9.82→91.22（+81.4pp）· total 772.01→−91.22 · 逐年 2022 +300.50→−79.25（maxDD 9.82→79.29 · 上涨日 164→37/241）、2023 +121.38→−57.48（2.69→57.48 · 159→30/242）；对数尺度 ln(8.72)=+2.17 vs ln(0.088)=−2.43，近似对称；confidence high；⚠ edge-test-ran · mirror-collapses · log-symmetric · both-years-same-sign · 14%-up-days） edge: 均值回归 溯源 [[study-u-3]]
- **[Q u-4]** 无信号控制组：同一薄 band，premium 一行换成 −1e7/money（不含 NAV 信息，最薄在前、过滤全过）+ 等权（两处一个概念）——持最薄 10 只等权、每日按薄度换仓（type: isolate）
  **→** 拿掉 NAV 信息、只持 band 里最薄的 10 只等权，两年亏 42%、回撤 43%，两年同号为负。薄 universe 本身不赚钱，它亏钱（最薄的 ETF 是在萎缩/清盘边缘的基金，加上每日换仓的往返）。分解：universe −42% / 折价信号 +772% / 镜像 −91%——收益全部来自信号，universe 是它的载体而非来源
  **⇒** 均值回归 升 measured（u-3 镜像 −91%、u-4 无信号 −42%、基类 +772%，三臂两年同号）：这条血统的 edge 是「薄 ETF 的集合竞价开盘价对净值的偏离会回归」，信号承重、universe 不承重。与 流动性溢价 合读：薄不是为了持有薄基金，而是因为只有薄基金的开盘价才会偏离净值那么远——两条 edge 是同一件事的两面（偏离的幅度由薄度供给，方向由 NAV 供给）。关闭一切「换 universe 保信号」的 improve（u-1 已量：流动基金上偏离太小）
  （Δ vs 锚点：obj 1.8592→−0.6734（−2.5326）· annual 195.74→−24.04（−219.8pp）· sharpe 11.15→−1.71 · maxDD 9.82→43.30（+33.5pp）· total 772.01→−42.26 · 逐年 2022 +300.50→−22.41（maxDD 9.82→25.58 · 上涨日 101/241）、2023 +121.38→−24.61（2.69→31.35 · 105/242）；confidence high；⚠ edge-test-ran · control-negative · both-years-same-sign · universe-is-carrier-not-source） edge: 均值回归 溯源 [[study-u-4]]
- **[Q u-5]** 权重：|premium| 加权 → 等权，一行（band / 过滤 / top-10 不动）（type: ablation）
  **→** 等权少赚 17pp 年化、回撤只浅 1.1pp：折价深度有边际信息——最深折价的名字回归得更多，把资金压向它们是对的。差额几乎全在 2022（+300 vs +251），2023 持平（+121 vs +125）：深折价在熊市里更深、回归也更大。不是惰性（|Δobj| 0.16 > 0.05 的阈）
  **⇒** 关闭「等权作为降回撤的 improve」：换来的 −1.1pp 回撤买不回 −17pp 年化。打开的是 pt-imp-2 的反向读法：既然深度有信息，集中到 top-5 应至少不降——若 top-5 反而降，那是 5% 参与上限在薄名字上填不满，作者放宽到 10 是对的
  （Δ vs 锚点：obj 1.8592→1.7020（−0.1572）· annual 195.74→178.93（−16.8pp）· sharpe 11.15→10.37 · maxDD 9.82→8.73（−1.1pp）· total 772.01→675.82 · 逐年 2022 +300.50→+251.38（maxDD 9.82→8.72）、2023 +121.38→+124.50（2.69→2.73）；confidence high；⚠ depth-weighting-informative · 2022-concentrated-gain · gate-pass-both-arms） edge: 均值回归 溯源 [[study-u-5]]
- **[Q pt-imp-1]** 下界 5e6 → 1e7、保留 2e7 上界（丢掉 band 最薄的一半），一行——on-mechanism 于 流动性溢价，方向是可实现性变好的方向（type: improve）
  **→** 丢掉最薄一半，年化少 58pp、回撤只浅 0.7pp：收益跟着薄尾走，回撤不跟。三档 band 单调：5e6–2e7 年化 196 / 1e7–2e7 138 / 5e7–1e8 23——越可成交越少赚，没有 ETF溢价 q-1 那种「下界过松、收紧反而更好」的甜点。ETF溢价 的 2e6 是股数下界、本家族的 5e6 是成交额下界，两者不是同一个量，甜点不迁移
  **⇒** 关闭 band 下界作为 improve（收紧单调变差；放松 = 走向 5% 参与上限也填不满的更薄名字，是容量幻觉）。流动性溢价 的 evidence 补上第三臂：band 三档单调。整合层引用本家族时，「可实现的版本」应按 1e7–2e7 的 138%/7.29 或 u-1 的 23%/0.94 估，取决于愿意假设多薄的名字能在开盘价成交
  （Δ vs 锚点：obj 1.8592→1.2859（−0.5733）· annual 195.74→137.68（−58.1pp）· sharpe 11.15→7.29 · maxDD 9.82→9.09（−0.7pp）· total 772.01→463.60 · 逐年 2022 +300.50→+181.24（maxDD 9.82→9.09）、2023 +121.38→+102.50（2.69→4.33）；confidence high；⚠ rejected · monotone-in-thinness · no-sweet-spot · gate-pass（sharpe 7.29）· realizability-veto-stands） edge: 流动性溢价 溯源 [[study-pt-imp-1]]
- **[Q pt-imp-2]** top-10 → top-5（作者从 5 放宽到 10「以求尽可能多地成交」），一行——on-mechanism 于 均值回归（集中到最深折价）（type: improve）
  **→** 集中到 top-5 少赚 14pp、回撤不变；2022 反而多赚 17pp，2023 少赚 29pp。与 u-5 合读：深度有信息（加权 > 等权）但集中到 5 只不如 10 只——第 6–10 名在 2023 贡献正收益，因为 5% 参与上限下最深的 5 只吃不下全部资金（2023 vol 从 0.118 降到 0.098 = 资金留在现金里）。作者的放宽是填单宽度，不是分散
  **⇒** 关闭集中度作为 improve（top-5 变差；top-N > 10 = 更浅的折价，u-2 已示范流动名字只加回撤）。improve 队列清空：band 上界（u-2）、下界（imp-1）、权重（u-5）、集中度（imp-2）四个 on-mechanism 旋钮都不优于原值，基类 fa0d3bd9 是这条血统在 epoch 6 上的最优点。本家族的一次 VAL 花在基类上
  （Δ vs 锚点：obj 1.8592→1.7191（−0.1401）· annual 195.74→181.58（−14.2pp）· sharpe 11.15→10.49 · maxDD 9.82→9.67（−0.2pp）· total 772.01→690.61 · 逐年 2022 +300.50→+317.80（maxDD 9.82→9.67）、2023 +121.38→+92.35（2.69→2.74）；confidence high；⚠ rejected · fill-width-not-diversification · 2023-cash-drag · gate-pass（sharpe 10.49）） edge: 均值回归 溯源 [[study-pt-imp-2]]
- **[Q val-base-e6]** 基类 fa0d3bd9（= baseline-e6.py，源码 + live OVERRIDE）在 VAL 2024-01-01→2025-12-31 上跑一次——本家族 epoch 6 的唯一一次验证，花在基类上（两条 improve 均 rejected，基类是 TRAIN 最优点）（type: validate）
  **→** VAL 不但没有衰减，还高于 TRAIN：年化 242% / sharpe 12.8 / 回撤 5.9%，两年同号强正、上涨日 70%。2024-02 微盘踩踏对这本书只值 4.46% 回撤（2024 全年 maxDD）——它持有的是薄 ETF 的开盘偏离，不是微盘股 beta。四个年度（2022–2025）年化全在 +92% 到 +374% 之间、单年 maxDD 全 ≤ 9.8%：在「开盘价按成交量 5% 可成交」这个假设下，机制在四个 regime 里都成立
  **⇒** 关闭「VAL 会把它筛掉」：不会，它在 VAL 上更强。这把问题推回唯一没关的门——可实现性：TRAIN 与 VAL 的每一个数字都建立在「薄 ETF 的集合竞价开盘价能按全天成交量 5% 成交」上。下一步不是再一次 VAL（已花、也不该），而是 u-7：把执行从 09:30 挪到 14:50，看偏离在开盘之后还剩多少——那才是一个不在集合竞价里抢单的账户能拿到的部分。整合层引用本家族时按 §4 的可实现档位估值，不按 242%
  （Δ VAL：total 1067.81 · annual 241.73 · sharpe 12.82 · maxDD 5.92 · obj 2.3581 ‖ 对照 TRAIN 锚点：annual 195.74 · sharpe 11.15 · maxDD 9.82 · obj 1.8592 ⇒ VAL 更高 +0.50 obj；逐年 2024 +373.60（maxDD 4.46 · vol 0.2284 · sharpe~ 7.02 · 上涨日 170/241）/ 2025 +147.40（maxDD 5.92 · vol 0.1545 · sharpe~ 5.86 · 172/243）；confidence high；⚠ VAL-spent · val-above-train · four-years-same-sign · 2024-02-crash-4.5pct-maxDD · ⚠零滑点 · ⚠开盘价成交假设（realizability 见 u-7 / §4）· gate-pass（sharpe 12.82）） edge: 均值回归 溯源 [[study-val-base-e6]]
- **[Q u-7]** 执行时点：run_daily(market_open) 09:30 → 14:50，一行；信号仍是 09:25 的集合竞价开盘价 vs T−1 净值（日频回测里 09:30 单以开盘价成交、14:50 单以收盘价成交）（type: probe）
  **→** 同一信号、只把成交从开盘价挪到收盘价，两年从 +772% 变成 −29%，回撤 40%——落到与「无信号最薄 10 只」（u-4，−42%）同一量级。开盘价对净值的偏离到收盘不但已经回归，还越过了：在收盘价买那些开盘折价最深的薄 ETF，拿到的是薄 ETF universe 的负漂移。收益 100% 是「在集合竞价的成交价上买到」这一件事，没有任何部分持续到日内可交易的时段
  **⇒** 关闭一切以 TRAIN/VAL 头条为准的引用：196% / 242% 是「按全天成交量 5% 在集合竞价成交价上成交」的回测伪影，一个不能在开盘集合竞价里以那口价成交的账户拿到的是负数。整合层与 type 层不得把本家族当作可拼接的 sleeve；component 登记（若有）只能登记「薄 ETF 集合竞价开盘价偏离净值」这个观察本身，不登记收益。关闭 improve 的全部方向（band/权重/集中度已量、执行时点已量）。家族 status 建议 DQ-realizability，由人裁决；本轮不改 status
  （Δ vs 锚点：obj 1.8592→−0.5601（−2.4193）· annual 195.74→−16.05（−211.8pp）· sharpe 11.15→−1.09 · maxDD 9.82→39.96（+30.1pp）· total 772.01→−29.49 · 逐年 2022 / 2023 见 description；对照 u-4 无信号 universe：annual −24.04 / maxDD 43.30；confidence high；⚠ realizability-DECISIVE · auction-print-only · matches-universe-control · both-years-negative · DQ） edge: 均值回归 溯源 [[study-u-7]]
