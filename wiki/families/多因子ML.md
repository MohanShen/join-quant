---
family: 多因子ML
aliases: []
concepts: []
edge:
  - name: 规模因子
    kind: risk-premium
    claim: "⚠ 家族名与机制不符：base d02cde29 不是多因子/ML，而是 etf .40 / small_cap .35 / white_horse .25 三分仓恒定混合；small_cap 微盘腿是收益的最大单一来源（35% 权重供给 39% 年化），但不是唯一来源"
    test: "在 epoch-6 台上把 small_cap 权重置 0（其余不动）；若 Δannual 小于总年化的 1/3，claim 证伪"
    status: measured
    evidence: [[study-q-e6-1]]（epoch 6：annual 52.58→32.05，Δ 占 39%；预注册的更强预测「失去过半且破闸」未成立，claim 已据此收窄）
  - name: 动量
    kind: anomaly
    claim: "etf 腿的跨资产动量轮动供给剩余收益的一部分"
    test: "epoch-6 台上 etf 权重置 0，只跑 2023 单年；若 etf 腿有非事后的动量 edge，2023 贡献应为正"
    status: refuted
    evidence: [[study-q-e6-2]]（epoch 6，2023：去 etf 后 total 26.94→35.37、sharpe 1.56→2.49、maxDD 8.25→4.99；c_etf(2023) = −8.43pp，贡献全在 2022 事后池）
base: [[d02cde29_高质量稳定上涨]]
bestVariant: [[d02cde29_高质量稳定上涨]]
bestObjective: 0.4737
memberCount: 20
sources: { normalized: 20, study: 0, enhance: 0 }
realism: "epoch-6 头条 52.58% 年化 / 8.55% 回撤不可当作可实现水平：(a) 台仍零滑点，而最大单一收益来源是 6 只微盘周度轮换（q-e6-1）；(b) etf 腿收益全在 2022 且池为事后组装，2023 净拖累 −8.43pp（q-e6-2, q-audit）；(c) 日线台把盘中止损坍缩成收盘检查、隐藏盘中回撤（q-audit）；(d) 约 3.8pp 回撤保护挂在 n=4 的 1/4 月日历规则上（q-3, epoch 2）。源码审计未发现确证的未来函数——是不可实现，不是造假"
status: active
updatedAt: 2026-09-23
---

# 多因子ML — strategy family

**一句话**：⚠ 家族名与 base 机制不符——唯一稳定过闸的 base [[d02cde29_高质量稳定上涨]] 不是多因子/ML，而是 etf 0.40 / small_cap 0.35 / white_horse 0.25 的三分仓恒定混合；收益的最大单一来源是微盘腿（规模因子，measured），etf 腿的收益全在 2022 且来自事后组装的池（动量 edge refuted）。

## 1. 基类 (base archetype)   ← [[study-q-e6-0]]~[[study-q-e6-2]]（epoch 6）+ q-1~q-audit（epoch 2，仅作方向先验）
- **Universe 选股池**：三分仓恒定混合（源码 `STRATEGY_ALLOCATION`）——`etf` 0.40：14 只硬编码跨资产 ETF 动量轮动，单标的持有；`small_cap` 0.35：6 只微盘股；`white_horse` 0.25：大盘白马。
- **交易频率**：etf 每日轮动检查；small_cap 周度调仓 + 三档止损；white_horse 月度大/小盘 regime 信号。⚠ 评测台为日线，盘中各时点的 run_daily 全落同一根 bar（q-audit）。
- **交易机制**：三仓都按 `total_value × 权重` 定仓（跨仓再平衡耦合，三仓次可加，q-5）。small_cap 在 1 月与 4 月整仓切到 600036 招商银行（日历轮换，n=4 事件，q-3：关掉 maxDD +3.78pp，epoch 2）。
- **基线绩效**（epoch 6, TRAIN 2022-01-01→2023-12-31）：total **132.55%** / annual **52.58%** / sharpe **3.01** / maxDD **8.55%** / objective **0.4403**（[[study-q-e6-0]]；epoch-2 账本行 0.4737 已失效，归一化器尚未写回 epoch-6 行）。2023 单年：total 26.94 / sharpe 1.56 / maxDD 8.25。
- **为什么有效**：微盘腿以 35% 权重供给 39% 年化（[[study-q-e6-1]]），是最大单一来源但非唯一；去掉后仍年化 32.05% / sharpe 1.99。剩余部分中 etf 腿在 2023 是净拖累（[[study-q-e6-2]]），其贡献只在 2022。
- **⚠ 现实性 / 容量**：见 frontmatter `realism`。

## 2. 变体 (variants)   ← **失败的变体也记**（判定: rejected）
| 变体 | 类型 | 相对基类的改动 | 来源 | Δobjective | Δsharpe | ΔmaxDD | 判定 | 结论 |
|---|---|---|---|---|---|---|---|---|
| baseline-e6 | understand | 台 epoch 2→6，策略主体不变 | [[study-q-e6-0]] | −0.0334 | −0.20 | −1.06 | informative | base 在 epoch 6 存活，epoch-2 头条仅小幅高估 |
| q-e6-1 small_cap=0 | understand | small_cap 0.35→0 | [[study-q-e6-1]] | −0.1952 | −1.02 | −1.01 | informative | 微盘腿是最大单一来源（39% 年化），非唯一；规模因子 → measured |
| q-e6-2 etf=0（2023） | understand | etf 0.40→0，仅 2023 | [[study-q-e6-2]] | 2023 子窗，不与全窗比 | +0.93（2023） | −3.26（2023） | informative | etf 腿 2023 净拖累 −8.43pp；动量 edge → refuted |
| idea-imp-1 加大微盘权重 | improve | small_cap 0.35→0.50 | queue（未回测） | — | — | — | rejected | 未回测即否决：增量全在零滑点最失真的腿，并把本家族推成 [[小市值]] 的副本 |
| q-1…q-audit | understand | 三腿消融 / 年度 / 日历 / 审计 | §6（epoch 2） | — | — | — | informative | epoch 2 测得，数字不可再引用，方向由 q-e6-0 背书 |

## 3. 家族内绩效横评 (auto)

| 排名 | 变体 | obj | sharpe | annual% | maxDD% | gate |
|---|---|---|---|---|---|---|
| **1** | **[[d02cde29_高质量稳定上涨]]** | 0.4737 | 3.21 | 56.98 | 9.61 | ✅ |
| 2 | [[ef10ee67_保守版低回撤因子]] | 0.2139 | 1.76 | 30.10 | 8.71 | ✅ |
| 3 | [[f1253042_10万本金低频风控]] | 0.0449 | 0.65 | 9.56 | 5.07 | ❌ |
| 4 | [[6ad90252_巴菲特价值量化]] | 0.0000 | 0.00 | 0.00 | 0.00 | ❌ |
| 5 | [[775faa4e_信息熵策略]] | -0.0011 | 0.47 | 12.16 | 12.27 | ❌ |
| 6 | [[f9ca1d2e_机器学习多因子]] | -0.0723 | 0.46 | 12.09 | 19.32 | ❌ |
| 7 | [[f8d8348c_投资学作业多因子]] | -0.4353 | -0.82 | -12.84 | 30.69 | ❌ |
| 8 | [[49efd264_量化课堂多因子入门]] | -0.7465 | -1.47 | -26.02 | 48.63 | ❌ |
| 9 | [[5b915770_多因子入门副本]] | -0.7465 | -1.47 | -26.02 | 48.63 | ❌ |
| 10 | [[91e4a8e4_创业板动量选股]] | -1.0217 | -1.22 | -38.40 | 63.77 | ❌ |
| 11 | [[26b52dca_季报预告信号研究]] | DQ/— | — | — | — | — |
| 12 | [[5a127075_行为金融学预测]] | DQ/— | — | — | — | — |
| 13 | [[5a5ba567_价值选股与RSRS择时]] | DQ/— | — | — | — | — |
| 14 | [[77e78b06_多任务学习框架]] | DQ/— | — | — | — | — |
| 15 | [[796c6f98_市盈率股息率选股]] | DQ/— | — | — | — | — |
| 16 | [[914d5724_中证500增强]] | DQ/— | — | — | — | — |
| 17 | [[b0e7b728_特质波动率因子研究]] | DQ/— | — | — | — | — |
| 18 | [[b8a7451f_实战模型量化转化]] | DQ/— | — | — | — | — |
| 19 | [[c18e0923_BP单因子测试]] | DQ/— | — | — | — | — |
| 20 | [[c748b9d5_价值投资低估选股]] | DQ/— | — | — | — | — |

*2 gate-pass / 20 members. 快照 2026-09-23（TRAIN 2022–2023, 冻结零滑点 ⚠）。由 `wiki-family-build.js` 生成，勿手改。*

## 4. 待研究 / 空白 (research gaps)
- **家族归属**：base 是组合书，与 [[小市值]]、[[ETF动量]] 部分重叠；是否应将 d02cde29 改归或将本家族改名，是人工 / `/ingest-strategy` 决定（`family:` 不自动改）。真正的多因子/ML 成员（49efd264 / f9ca1d2e / 775faa4e / f8d8348c）全部不过闸。
- **10 个成员没有有效测量**（8 个 compile-error、2 个 slow-skipped，均为 epoch 2）——属于归一化 / deferred 池，不属于本循环。
- **VAL 未花**：没有 improve 候选；base 的 VAL 2024–25 对作者而言很可能是样本内（帖子 2026-02、ETF 池为事后组装）。epoch 6 的一次 VAL 预算留给未来的候选。
- q-3 日历轮换未在 epoch 6 上复测（n=4，过拟合嫌疑，方向先验来自 epoch 2）。

## 5. 沿革 (provenance)   ← 待人工填写：首发 postId/作者、版本演进

## 6. 研究问答 (study-log)
- **[Q q-4]** 基类全仓年度形态（etf 0.40 / small_cap 0.35 / white_horse 0.25 三分仓恒定混合，零代码改动）（type: regime）
  **→** 假设被完全反转——2022 熊市才是收益年（+93.52%，sharpe 5.09），2023 震荡年是拖累年（+28.20%，sharpe 1.59），不均衡约 3.3×；且两年 maxDD 均低于全窗 9.61%（8.54 / 9.23），最深回撤跨 2022/2023 年界，因 2023 子窗 9.23% 仅差 0.38pp，该段最可能峰值立于 2022 年末、主体落在 2023，故回撤负担不是 2022 熊市事件
  **⇒** (no implication recorded — contract violation)
  （Δ 2022 total 93.52 / sharpe 5.09 / maxdd 8.54；2023 total 28.20 / sharpe 1.59 / maxdd 9.23；全窗 total 146.11 / sharpe 3.21 / maxdd 9.61；confidence high；⚠ ⚠零滑点高估 / regime-specific / hypothesis-inverted / falsifier-B-未触发(9.23 vs 9.61，差 0.38pp) / 子窗annual与全窗annual不同量纲 / 跨年回撤定位为med推断） 溯源 [[study-q-4]]
- **[Q q-1]** small_cap 分仓权重 0.35 → 0.0（variants/q-1.py 第 29 行，单行 diff 已核）（type: ablation）
  **→** small_cap 仓在这个恒定混合权重下同时是组合的收益发动机与闸门守门员：去掉它总回报少 64.62pp、年化 −22.21pp，且 sharpe 3.21→2.16 直接 gate FAIL（提问官未预见的闸损）；每单位混合权重贡献 184.6 total%/unit，是 etf（91.3）的两倍多。同时最大回撤不升反降 1.42pp，说明它是回撤的来源之一而非被其它仓保护的对象
  **⇒** (no implication recorded — contract violation)
  （Δ total 146.11→81.49（−64.62pp）/ annual 56.98→34.77（−22.21pp）/ sharpe 3.21→2.16（−1.05，跌破 2.5 闸）/ maxdd 9.61→8.19（−1.42pp，反而改善）/ 原始分 annual−maxdd 0.4737→0.2658（−0.2079），但正式 objective = DQ（harness §4 sharpe 闸）；confidence high；⚠ ⚠零滑点高估 / idle-cash-confound(35% 权重归零后闲置吃 0 收益，不再分配) / bundled-machinery(权重归零使 schedule_tasks 整块跳过该仓的 1/4 月日历轮换与三档止损，Δ 是「仓+其风控机器」) / gate-loss-DQ / hypothesis-survived(证伪项 Δannual > −8pp 未触发，实测 34.77% 落在预测 22–35% 带最上沿)） 溯源 [[study-q-1]]
- **[Q q-2]** etf 分仓权重 0.4 → 0.0（variants/q-2.py 第 28 行，单行 diff 已核）（type: ablation）
  **→** 假设被证伪且方向反转——etf 仓不是回撤压制器：maxDD 没有抬到预测的 14–20%，反而降了 1.85pp。它权重最大（0.40）却贡献最少（36.52 total%，91.3 total%/unit-weight），且去掉后 sharpe 仍 3.10 稳过闸，是这个组合在当前 objective 下最「割得起」的一条腿。与 q-1 合看：去掉任一仓 maxDD 都下降（−1.42 / −1.85pp），按闲置现金归一化后分别为 −0.0406 / −0.0463 pp per idle-weight-pp，两者接近且都可由纯现金稀释解释，任一仓都没有留下可归因的对冲残差 → 全窗 9.61% 的回撤更像三仓叠加的涌现属性（各仓回撤时段重叠相加），而非某条腿失职；「跨资产 ETF 仓是减震器」的叙事就此终结
  **⇒** (no implication recorded — contract violation)
  （Δ total 146.11→109.59（−36.52pp）/ annual 56.98→44.85（−12.13pp）/ sharpe 3.21→3.10（−0.11）/ maxdd 9.61→7.76（−1.85pp，反而改善）/ objective 0.4737→0.3709（−0.1028，gate PASS→PASS）；confidence high；⚠ ⚠零滑点高估（q-2 变体的剩余 60 权重点中 35 点是微盘，成交假设比基线更不真实，109.59% 同样不可实现）/ idle-cash-confound(40% 闲置，且 sharpe 会被现金稀释人为抬高，故 sharpe 未跌破 2.5 不构成对减震器假设的辩护) / hypothesis-falsified-and-reversed / emergent-drawdown 为当前最佳读法而非已证明） 溯源 [[study-q-2]]
- **[Q q-3]** SMALL_CAP_CONFIG['pass_april'] True → False（variants/q-3.py 第 62 行，单行 diff 已核）＝取消「1 月与 4 月把 small_cap 仓整体换成 600036.XSHG 招商银行」的日历轮换（type: ablation）
  **→** 本家族第一个被正面测到的回撤压制组件，而且它是一条纯日历规则：关掉后 maxDD 从 9.61% 抬到 13.39%（+3.78pp），同时总回报少 19.34pp——即该规则既买回撤保护也卖收益，两侧都要付账。预注册证伪项要求同时满足「maxDD 抬升 < 1.5pp」且「Δannual < 3pp」，两个子句都不成立，故证伪项未触发、规则不是装饰件。它是全套问题里唯一无闲置资金混淆的干净消融（开关两侧 small_cap 仓都按 total_value×0.35 满额建仓，只改持有什么），所以这 +3.78pp 是干净的因果量。⚠ 但其样本内支撑只有 n=4 次事件（2022-01/2022-04/2023-01/2023-04），基类 9.61% 低回撤里约 3.8pp 与约 19pp 总回报挂在一张硬编码月份表上，「低回撤稳健」的任何主张都必须带这条
  **⇒** (no implication recorded — contract violation)
  （Δ total 146.11→126.77（−19.34pp）/ annual 56.98→50.67（−6.31pp）/ sharpe 3.21→2.73（−0.48，距 2.5 闸只剩 0.23）/ maxdd 9.61→13.39（+3.78pp）/ objective 0.4737→0.3728（−0.1009，gate PASS→PASS）；confidence high；⚠ ⚠零滑点高估 / overfit-risk（硬编码月份表，样本内 n=4 事件，是全策略最可疑的过拟合部件）/ no-idle-cash-confound（唯一无闲置资金的干净消融，两侧仓位占用相同）/ hypothesis-survived（证伪项两个子句均未满足）/ maxDD 13.39% 落在预测 13–19% 带的最下沿、Δobjective −0.1009 比预测的 −0.15~−0.30 温和（因规则同时也在卖收益）/ narrative-corrected（是「微盘→大盘银行」标的轮换，不是空仓降仓；源码注释误称 600036 为 ETF）/ sharpe 2.73 距闸仅 0.23） 溯源 [[study-q-3]]
- **[Q q-5]** white_horse 分仓权重 0.25 → 0.0（variants/q-5.py 第 30 行，单行 diff 已核）；附带纯纸面可加性检验（复用 q-1/q-2/q-5 三行，0 次额外回测）（type: ablation）
  **→** 两个结论。(a) white_horse 确是最弱的一条腿：Δobjective 仅 −0.0701，预注册证伪项「|Δobjective| > 0.20」未触发，假设存活；贡献 26.39 total%（105.6 total%/unit-weight），补齐三仓分解后排序为 small_cap（64.62，184.6/unit）> etf（36.52，91.3/unit）> white_horse（26.39，105.6/unit）——注意 etf 权重最大却贡献最少。(b) 可加性假设被证伪、方向与预设相反：R=146.11、ΣA_i=310.80、2R=292.22 → 残差 +18.58pp（等价地 Σc_i=127.53 < R=146.11），即三仓的去一仓边际贡献之和 SMALLER than 整体，是 SUB-additive（次可加）；预注册期望是残差≈0（可加）或显著为负（正向复利耦合），观测到的是正号。乘法零假设同向（∏(G/G_i)=1.784 vs G=2.461），故符号不是线性账本的记账假象。实务含义：三仓不可分离，c_i 只能读作「该仓在此组合语境下的贡献」，绝不能读作「该仓独立运行能赚多少」
  **⇒** (no implication recorded — contract violation)
  （Δ total 146.11→119.72（−26.39pp）/ annual 56.98→48.31（−8.67pp）/ sharpe 3.21→3.12（−0.09）/ maxdd 9.61→7.95（−1.66pp，反而改善）/ objective 0.4737→0.4036（−0.0701，gate PASS→PASS）；confidence high（Δ 与最弱腿判定）/ med（次可加的方向；量级不可信）；⚠ ⚠零滑点高估 / idle-cash-confound（25% 权重归零后闲置吃 0 收益、不再分配）/ bundled-machinery（schedule_tasks 第 184 行守卫整块跳过该仓的月度大小盘 regime 信号、周度反弹清仓、每日调整与三次盘中止损）/ hypothesis-survived-A（|Δobjective|>0.20 未触发）/ hypothesis-falsified-B（可加性残差显著为正 → 次可加，与预设的「≈0 或负」相反）/ additivity-contaminated（每个 A_i 都被闲置现金压低，修正后残差只会更正，故方向稳健、量级不稳健，只作耦合强弱的定性指标）/ ΔmaxDD 归一化 −1.66/25 = −0.0664 pp per idle-weight-pp，高于 q-1/q-2 的 −0.0406/−0.0463，但三点无误差带，不足以支持「white_horse 增加风险」的说法） 溯源 [[study-q-5]]
- **[Q q-6]** etf 分仓权重 0.4 → 0.0（复用 variants/q-2.py，无新变体文件），只把窗口换成 2022 单年子窗（type: regime）
  **→** etf 腿的贡献在时间上极度集中，全窗读数被推翻：c_etf(2022) = +39.72pp > 全窗 c_etf = +36.52pp → 集中比 1.088（约 109%），即该腿把两年的全部贡献都在 2022 一年内交付。乘法口径同向：2022 腿效应 ×1.258（+25.8%），倒推 2023 腿效应 ×0.933（−6.7%，是拖累）。故 etf 不是「最不出活的一条腿」这么简单，而是 2022 单年赢家 + 2023 净拖累，在 0.40 固定权重下不构成稳定分散器，也不是减震器（同窗 maxDD 仍反降 0.78pp）。第二个结论同等重要：预注册 Case A（2022 掉到 50% 以下）未成立，Case B 成立——去掉 ETF 腿仍有 +53.80% / maxDD 7.76% / sharpe 3.66，即 2022 异常收益里约 58% 与 ETF 腿无关，落回 small_cap 微盘腿 + 零滑点微盘成交，而这恰是成本偏差最大的部分
  **⇒** (no implication recorded — contract violation)
  （Δ 2022 子窗：total 93.52→53.80（−39.72pp）/ annual 93.87→53.98 / sharpe 5.09→3.66（−1.43）/ maxdd 8.54→7.76（−0.78pp，反降）；对照全窗 c_etf = +36.52pp；confidence high（集中方向与 Case B 判定）/ med（1.088 比值的精确量级，受闲置现金与子窗重建影响）；⚠ ⚠零滑点高估（残余 58% 的 2022 异常正好落在换手最高的微盘腿，绝对水平不可实现）/ regime-specific（结论限 2022）/ idle-cash-confound 40%（闲置不再分配，措辞须为「该腿在其固定 0.40 混合权重下的贡献」）/ full-window-reading-reversed（全窗把它读成「最弱但中性」的腿是错的，实为单年赢家+次年拖累）/ 子窗 annual% 为 364 天再年化，绝不与两年 56.98% 同量纲） 溯源 [[study-q-6]]
- **[Q q-audit]** baseline.py 全文只读 look-ahead / 未来函数审计（0 次回测，无变体）（type: probe）
  **→** 未发现确证的未来函数——这是一条真结果，不是「没查出问题」。逐条核实为干净：两处 frequency='1m' 调用（约 713-718 行 @14:25/14:55、1041-1042 行 @14:00/14:30/14:50）都传 end_date=context.current_dt，JQ 分钟线以结束分钟标注，count=1 取到的是刚走完的那一分钟，非前视，且第 85 行 avoid_future_data=True 另有兜底；没有任何日频调用使用 end_date=context.current_dt；attribute_history（351/395/1006 行）结构上取不到当前 bar；208-214/222-228/653-659/814/823/1110-1112 行均用 context.previous_date；get_fundamentals（536/551/795/811/962/983/994 行）不传 date，JQ 默认 T-1 且按公告日对齐，无财报滞后泄漏；ETF 溢价（450-454 行）用 T-1 收盘价与 T-1 单位净值，是全文最规范的一处；white_horse_signal（777-825）与 assess_market_temp（1004-1010）均排除当日。三条可疑项改用机制解释而非泄漏：(A) 硬编码 14 只 etf_pool（34-49 行）含 159525/159628/159652/513130/511090 等 2021+/2022+ 上市代码，是以 ≥2023 视角组装的池，397 行长度守卫对未上市代码静默 continue，故 2022 段实际跑在一个「事后剪枝」过的池上，其 2022 可交易成员（159985 豆粕 / 501018 南方原油 / 161226 国投白银 / 518880 黄金）恰与该年赢家高度重合，q-6 已量化其体量为 +39.72pp、约 109% 集中在 2022 一年；foreign_etfs（76-81 行）同性质。(B) 冻结评测台频率为每天（harness.md §2，strategy-post-backtest.js:145 从不覆盖，JQ 结果行确认「每天」），日线一天只有一根 bar，故 9:31/10:00/14:25/14:50 的 run_daily 全部落在同一根 bar 上，get_current_data().last_price 与 position.price 都解析为当日收盘、市价单也按同一收盘成交 → 四档止损坍缩成一次收盘检查（永远不会被「盘中砸坑、收盘收回」洗出去），且 JQ 按日收盘净值算回撤 → 盘中回撤在结构上不可见。(C) 动量排名把当前价拼进序列（355/410 行 np.append(..., last_price)），本身不含成交后信息、非泄漏，但在日线台上意味着所谓「9:31 轮动」实为「按收盘排名、按同一收盘买入」。总判定：前视不足以解释 +93.52%/8.54% 的 2022 结果，该数字是不可实现而非造假，由 (a) 事后组装的 ETF 池、(b) 抹掉盘中洗盘并隐藏盘中回撤的日线台、(c) 微盘腿零滑点、(d) n=4 的 1/4 月日历规则四者合成
  **⇒** (no implication recorded — contract violation)
  （Δ 无 Δ（零回测成本）；confidence high（逐行核对的干净项与 A/B/C 的机制判定）/ med（依赖 JQ 平台语义的两处：get_fundamentals 默认 T-1 的公告日对齐、get_industry 不传 date 时的 SW 追溯重分类）；⚠ no-confirmed-leak（负面审计结论，须正面记录）/ hindsight-universe-selection（Finding A，最强可疑项）/ daily-bar-execution-fiction（Finding B，系统性乐观而非前视）/ intraday-drawdown-invisible / ⚠零滑点高估 / overfit-risk（n=4 日历规则，见 q-3）/ correction-a30641fb（本仓库先前笔记误述：wiki/families/小市值.md:106 记载姊妹策略 a30641fb 的审计结论是「未发现未来函数」，它是被改判家族并标注零滑点高估，并非审计失败；任何「a30641fb 审计不过」的说法都要纠正）/ probe-零回测） 溯源 [[study-q-audit]]
- **[Q q-e6-0]** 评测台 epoch 2 → epoch 6（策略主体逐字不变，仅换 OVERRIDE：股票成本 pin 3bp/3bp/千一印花/5元、基金成本 pin、order_volume_ratio 0.05、avoid_future_data）（type: probe）
  **→** base 在当前台上存活：pin 掉作者的 1bp 股票佣金与自定基金成本并加 5% 成交量上限后，年化只少 4.40pp、sharpe 仍 3.01，回撤反降 1.06pp；epoch-2 头条被高估约 0.03 objective，量级小。该成员此前 epoch-6 复测在 30min 上限 slow-skip，本次 324s 完成——那次 slow-skip 是平台排队而非策略本身慢
  **⇒** epoch-2 的 7 条发现（q-1…q-audit）的方向可以沿用为先验，但其绝对数字不得再引用；家族 bestObjective 应以 0.4403（epoch 6）替换 0.4737，待归一化器把该行正式写回账本。deferred 池里的 d02cde29 用 30min 以上上限一次即可完成，不需要更高档
  （Δ total 146.11→132.55（−13.56pp）/ annual 56.98→52.58（−4.40pp）/ sharpe 3.21→3.01（−0.20）/ maxdd 9.61→8.55（−1.06pp）/ objective 0.4737→0.4403（−0.0334，gate PASS→PASS，1.5 闸余量 1.51）；confidence high；⚠ ⚠零滑点高估（台本身仍零滑点）/ 未写账本（研究执行器不写 normalize-train.tsv；deferred 池仍持有该行）/ 序列已存 data/series/study_多因子ML_baseline-e6__train__e6.json） edge: 规模因子 溯源 [[study-q-e6-0]]
- **[Q q-e6-1]** small_cap 分仓权重 0.35→0.0（variants/q-e6-1.py 第 29 行，单行 diff，基于 baseline-e6）（type: ablation）
  **→** 微盘腿以 35% 权重供给 39% 的年化（166.6 total%/unit-weight，其余两腿合计 114.2），是最大单一来源，但不是唯一来源：去掉它组合仍年化 32.05%、sharpe 1.99 过 1.5 闸。预注册证伪项（Δannual < 年化 1/3）未触发；更强的预测（失去过半、跌破闸）也未成立。epoch 2 的同一消融（q-1）读成「跌破闸」只因当时闸是 2.5
  **⇒** 规模因子 edge 升为 measured，但 claim 收窄为「最大单一来源」，不再写「唯一供给」；因此本家族与 [[小市值]] 的冗余是部分冗余而非完全冗余，剩余 ~32% 年化来自 etf+white_horse，其中 etf 部分已知集中于 2022 且池为事后组装（q-6/q-audit），故剩余收益的可信度低于微盘腿。改进方向上：加大微盘权重只会把本家族变成更差的小市值副本（且放大零滑点最失真的那条腿），该方向关闭
  （Δ total 132.55→74.25（−58.30pp）/ annual 52.58→32.05（−20.53pp，占年化 39%）/ sharpe 3.01→1.99（−1.02）/ maxdd 8.55→7.54（−1.01pp）/ objective 0.4403→0.2451（−0.1952，gate PASS→PASS）；confidence high；⚠ ⚠零滑点高估 / idle-cash-confound（35% 闲置不再分配，剩余两腿的真实单位产出被低估，故「非唯一来源」的判定方向稳健）/ hypothesis-partially-survived（证伪项未触发；强预测未成立）/ epoch-6 台） edge: 规模因子 溯源 [[study-q-e6-1]]
- **[Q q-e6-2]** etf 分仓权重 0.40→0.0（variants/q-e6-2.py 第 28 行，单行 diff，基于 baseline-e6），只跑 2023 单年，对照同窗 baseline-e6（type: regime）
  **→** 在事后池偏差最小的 2023 年，etf 腿是净拖累：去掉它（且 40% 资金闲置吃零）收益 +8.43pp、sharpe +0.93、回撤 −3.26pp，三个指标同向变好。与 epoch-2 q-6 的倒推（2023 ×0.933）在 epoch 6 上直接测得一致
  **⇒** 动量 edge claim 证伪（status → refuted）：etf 腿在 TRAIN 内的全部贡献来自 2022 一年，且该年池为事后组装，不构成可引用的动量 edge；家族页 realism 必须写明 TRAIN objective 0.4403 里有一段是 2022 事后池收益。不开「删 etf 腿」的 improve：epoch-2 q-2 显示全窗删 etf 会降 TRAIN objective，而按 2023 子窗挑选即是反向后视偏差，也不能拿 VAL 来做这个选择。edge 层面本家族剩下的唯一 measured edge 是规模因子
  （Δ 2023：total 26.94→35.37（+8.43pp）/ sharpe 1.56→2.49（+0.93）/ maxdd 8.25→4.99（−3.26pp）；c_etf(2023) = −8.43pp；confidence high；⚠ ⚠零滑点高估 / idle-cash-confound（40% 闲置却仍变好，故方向稳健、量级偏保守）/ regime-specific（仅 2023）/ hypothesis-falsified / 一年期 sharpe 噪声大，仅作方向） edge: 动量 溯源 [[study-q-e6-2]]
