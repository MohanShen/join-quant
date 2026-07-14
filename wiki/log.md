# 知识库活动日志

追加式记录，每行一条：`## [YYYY-MM-DD] <op> | <说明>`
`op` ∈ { ingest, skip-dup, concept, query, lint, merge }。详见 `docs/wiki-schema.md` §5。

---

## [2026-06-27] init | 初始化 wiki/ 骨架与 Schema（Phase 1）
## [2026-06-27] concept | 新建 小市值因子（6 篇）
## [2026-06-27] concept | 新建 ETF轮动（6 篇）
## [2026-06-27] ingest | 国九小市值排除3bug版 (aaba7575) → concepts: 小市值因子, 择时-均线, 止损模块
## [2026-06-27] ingest | 小市值微调 (17c95d16) → concepts: 小市值因子, 择时-均线, 止损模块
## [2026-06-27] ingest | 小市值低开优化 (7a1c225f) → concepts: 小市值因子, 止损模块
## [2026-06-27] ingest | 小市值优选KNN (3141242e) → concepts: 小市值因子, 多因子模型, 止损模块
## [2026-06-27] ingest | 微盘三正动量止损 (7fc942bf) → concepts: 小市值因子, ETF轮动, 多因子模型, 止损模块
## [2026-06-27] ingest | 最小市值轮动不择时 (cad4cc5d) → concepts: 小市值因子
## [2026-06-27] ingest | 三部曲吃透ETF动量1 (d1cf57eb) → concepts: ETF轮动, 动量与趋势
## [2026-06-27] ingest | ETF动量轮动实盘反思 (71117205) → concepts: ETF轮动, 动量与趋势
## [2026-06-27] ingest | 七星高照ETF轮动V17 (a593a36d) → concepts: ETF轮动, 动量与趋势, 止损模块
## [2026-06-27] ingest | 核心资产轮动安全摸狗 (1c96e06b) → concepts: ETF轮动, 动量与趋势, 择时-均线
## [2026-06-27] ingest | 市场温度驱动极简ETF (dc9f9dad) → concepts: ETF轮动, 择时-均线, 止损模块
## [2026-06-27] ingest | ETF溢价回撤 (edd94ebc) → concepts: ETF轮动 ⚠绩效存疑已标注
## [2026-06-27] lint | pilot 完成：12 策略页 + 2 概念页；待补概念页 [[择时-均线]] [[止损模块]] [[多因子模型]] [[动量与趋势]]（被引用但尚无独立页）
## [2026-06-27] lint | 因子构成列改由 utils/wiki-factor-signature.js 从 factors frontmatter 生成；校验 12 单元格零漂移
## [2026-06-27] concept | 新建 止损模块（机制·12篇）、择时-均线（机制·6篇）
## [2026-06-27] ingest | 万得微盘股指数复制 (8bafb765) → concepts: 小市值因子
## [2026-06-27] ingest | 低开小市值年化105 (5e874b5b) → concepts: 小市值因子, 止损模块
## [2026-06-27] ingest | 年化180逻辑奇怪小市值 (8dbd994c) → concepts: 小市值因子, 止损模块
## [2026-06-27] ingest | 中小板微盘优化稳定 (76593fb6) → concepts: 小市值因子, 择时-均线, 止损模块
## [2026-06-27] ingest | 动态仓位小市值五年20倍 (2a4882de) → concepts: 小市值因子, 止损模块
## [2026-06-27] ingest | 大小外择时小市值 (1c80dd9a) → concepts: 小市值因子, 择时-均线, 止损模块
## [2026-06-27] batch | 小市值 backfill 第1批(6篇)；wiki 累计 18/141 策略
## [2026-06-27] ingest | ETF batch: 15c36e0c,0aa4028d,8781a24d,2768beaa,62c2664f,46f583dd,48187f0c,97355171,19ca0e69,fd5d388d → ETF轮动(+动量与趋势/止损模块/择时-均线)
## [2026-06-27] ingest | 行业ETF轮动研究代码 (24fd2813) → ETF轮动 ⚙工具代码无交易
## [2026-06-27] ingest | 连续涨停基因轮动 (c658ef98) → 打板与涨停, 多因子模型, 止损模块（股票，非ETF，文件名「轮动」易误归）
## [2026-06-27] lint | 48187f0c(4138%)、97355171(3501%) 短窗口绩效已标⚠；ETF轮动 累计17篇
## [2026-06-27] batch | ETF backfill 第2批(12篇)；wiki 累计 30/141 策略
## [2026-06-27] concept | 新建 打板与涨停(结构·12篇)、龙虎榜(结构·2篇)
## [2026-06-27] ingest | 打板batch: 439385b4,25898ae1,9106ccaf,b518f737,53aea437,51f7b3ab,4cce4058,69ca427f,452ee858,01d39031,0ff0ddba → 打板与涨停(+龙虎榜/止损模块/多因子模型)
## [2026-06-27] lint | 打板组绩效系统性高估(涨停成交假设+短窗口)，439385b4/53aea437/452ee858/01d39031等已标⚠
## [2026-06-27] batch | 打板 backfill 第3批(11篇)；wiki 累计 41/141 策略
## [2026-06-27] concept | 新建 多因子模型(结构·13篇)、均值回归(因子族·3篇)
## [2026-06-27] ingest | 多因子batch: 49efd264,f9ca1d2e,34e0e03f,23f07734,c18e0923,b0e7b728,c748b9d5,796c6f98,5a5ba567 → 多因子模型
## [2026-06-27] ingest | 均值回归: 3691829a,be2b5192,(23f07734交叉) → 均值回归
## [2026-06-27] lint | 5a5ba567 引用 [[择时-RSRS]]（forward-link，待建）；多因子模型/均值回归 因子构成已生成
## [2026-06-27] batch | 多因子 backfill 第4批(11篇)；wiki 累计 52/141 策略
## [2026-06-28] concept | 新建 动量与趋势(因子族·21篇,含13 ETF动量)、择时-RSRS(机制·2篇)
## [2026-06-28] ingest | 动量batch: 57abbac2,9befa9b8,a67b6f26,11406b82,91e4a8e4,995abb4d,897d12a4,b7269ff2 → 动量与趋势(+择时-均线/止损模块)
## [2026-06-28] ingest | RSRS: 9ca7f493 → 择时-RSRS（解决 5a5ba567 的 forward-link）
## [2026-06-28] batch | 动量+RSRS backfill 第5批(9篇)；wiki 累计 61/141 策略
## [2026-06-28] concept | 新建 期货与套利(结构·3篇)、网格交易(结构·1篇)、行业轮动(结构·2篇)
## [2026-06-28] ingest | 期货:1294c538,ec720559,10a3c43d | 网格:598050b9 | 行业:9cba5a29,537edfae
## [2026-06-28] lint | 537edfae 绩效彻底失真(夏普108085)已标⚠⚠作废；598050b9 stats空
## [2026-06-28] batch | 期货/网格/行业 backfill 第6批(6篇)；wiki 累计 67/141 策略
## [2026-06-28] concept | 新建 多策略组合(结构·7篇)、日内做T(结构·1篇)
## [2026-06-28] ingest | 组合batch: 962e727b,3a5ab0c1,b50e4387,87826299,9f6f8188,fa0d3bd9,dc84f028 → 多策略组合 | ecba365f → 日内做T | 872b03e1 → ETF轮动+多因子模型
## [2026-06-28] lint | fa0d3bd9(557%)、dc84f028(6617%) 框架类绩效已标⚠
## [2026-06-28] batch | 组合/做T backfill 第7批(9篇)；wiki 累计 76/141 策略
## [2026-06-28] ingest | 七星/五福/三马 ETF家族变体×12 (965618d9,5dfc830e,4d4705e1,cd86d926,be107ff9,a722ab8a,7a0e0f18,406a1e4d,3c462ece,bf30eb36,4fa17009,d93fc998) → ETF轮动
## [2026-06-28] lint | 965618d9(5810%/sh98)、cd86d926(815%)、5dfc830e(471%)、d93fc998(388%) 短窗口已标⚠；ETF轮动 累计30篇
## [2026-06-28] batch | 五福/七星家族 backfill 第8批(12篇)；wiki 累计 88/141 策略
## [2026-06-28] ingest | 打板/短线×8 (38ca196e,a7f60565,c18c86c5,d9810155,01d60c34,43fca771,4b3b39e1,4e2baa95) → 打板与涨停(20)
## [2026-06-28] ingest | 三进兵×4 (7d1012a5,e4eb8dca,7552f0ef,87ab0122) → 动量与趋势(三EMA均线,25)
## [2026-06-28] batch | 打板短线+三进兵 backfill 第9批(12篇)；wiki 累计 100/141 策略
## [2026-06-28] ingest | 小市值/指数增强×9: f3ca90a7,1ae37a5f,5a70adc1,2f5bc859,fa9c8c9e,052da9b4,8101e57b→小市值因子(19) | 914d5724→多因子模型(14·中证500增强) | bba95a11→多策略组合(8)
## [2026-06-28] batch | 小市值/指数增强 backfill 第10批(9篇)；wiki 累计 109/141 策略
## [2026-06-28] ingest | ETF家族×7 (0b192155,c4291a66,ee354cc0,0d5f2d8b,54e0fd89,4c494c9c,b23a4a10)→ETF轮动(37)
## [2026-06-28] ingest | 多因子/价值×10 (b8a7451f,aa9678cd,a30641fb,6ad90252,f8d8348c,26b52dca,775faa4e,77cabc3c,5a127075,5b915770)→多因子模型(24) | 3c269466布林→均值回归(4)
## [2026-06-28] batch | ETF家族+多因子尾部 backfill 第11批(18篇)；wiki 累计 127/141 策略
## [2026-06-28] ingest | 尾部×17: cf5cbac2→小市值;6be8cff8,22152780→ETF轮动(39);f1253042,ef10ee67,2596a8ab,d02cde29,77e78b06,d5b83074→多因子(30);390dc094,e3914be0→动量;9c577879→多策略组合(9);23b0cbdc→择时-均线(7)
## [2026-06-28] ingest | 工具页×4(无概念): 477c48dc,1b0b018d,74914475,d29d708e（爬虫/保存对象/同花顺对接/灵感Skill）
## [2026-06-28] lint | e3914be0(39706%)等已标⚠⚠；cron 期间 strategies 增至144
## [2026-06-28] DONE | backfill 完成：144/144 策略页，15 概念页，零漂移；0 未 ingest / 0 孤儿

## [2026-07-11] normalize | 82 策略 @TRAIN 2022-2023 (零滑点/¥100万) | 74 策略页写入 normalized 块，18 过门槛(夏普≥2.5)；8 概念页加「归一化绩效横评」表；小市值 13/19 pass 为最强族，ETF/多因子/打板多 DQ；16 terminal-fail(多缺自定义库/旧pandas API)，2 true-hang，5 incompat

## [2026-07-12] experiment | jul12-005 (低开小市值剥头皮 + target_count 5→6) train=1.3898 val=1.3231 recorded → 回填 [[止损模块]] [[小市值因子]] [[择时-均线]] [[仓位管理]](新建)

## [2026-07-13] experiment | Arc1 低开剥头皮收敛：jul12-006..012 穷尽单因子扫描确认 jul12-005 (obj 1.3898) 为联合局部最优 → 回填调参地图（无新VAL行）到 [[jul12-005]]（调参地图节）· [[止损模块]]（破开盘价承重/止盈+5%对称峰值/跨日止损死代码）· [[仓位管理]]（分散>过滤，count内点@6）· [[小市值因子]]（junk-tail=alpha二确认、振幅≤10/跌幅<−1入场阈最优、扩池撞300s执行器上限）；⚠零滑点高估贯穿整族

## [2026-07-13] experiment | Arc2 裸微盘周度轮动 = 负结果（全DQ，从未过门槛/定稿/碰VAL，无results.tsv行、无归档）：jul12-013..017 三个正交降回撤杠杆各自失败，回撤=系统性微盘beta不可约减，最佳 jul12-015 obj 0.2366 仍DQ → 新建 [[arc2-microcap-rotation]] 负结果页 + 回填 [[小市值因子]]（裸轮动夏普~1.65 vs 剥头皮2.5-5.8，低回撤来自日内机器非size；低波倾斜=alpha腰斩）· [[止损模块]]（−15%止损在多日弧LIVE但压不动beta，持有周期决定live/dead vs [[jul12-002]]）· [[择时-均线]]（指数MA全书闸两速度均失败）；⚠零滑点高估（周度轮动仍高换手）

## [2026-07-14] experiment | Arc3 跨资产ETF动量/反转 = 负结果（全DQ净负，从未过门槛/定稿/碰VAL，无results.tsv行、无归档）：jul12-018..021 诚实流动13-ETF基线年化−3.05%，动量与反转两向皆无edge，universe整段净drawdown；跨资产分散给出本纪元最低基线回撤16%但无正回报配对，最佳 jul12-018 obj −0.1917 仍DQ → 新建 [[arc3-etf-rotation]] 负结果页 + 回填 [[ETF轮动]]（regime依赖、纯熊/震荡无效）· [[动量与趋势]]（ETF动量ANTI-predictive，放慢更差 [[jul12-020]]）· [[均值回归]]（简单反转也败、回撤最差30% [[jul12-021]]）；本族诚实流动、DQ为真·无edge非零滑点高估

## [2026-07-14] META | 两连负弧同窗口（Arc-2微盘/Arc-3 ETF 均全DQ）：本纪元唯一过门槛者仍是 Arc-1 日内剥头皮（[[jul12-005]]），因其 regime-agnostic（日内进出、无隔夜beta暴露）。TRAIN 2022熊/2023震荡窗口系统性惩罚**净多头方向暴露**对硬夏普门槛（2.5）——凡承接方向性beta的载体（微盘size beta / 跨资产ETF动量）在此窗口都过不了门槛。→ Arc-4 转向 market-neutral / low-beta / regime-agnostic 方向。

## [2026-07-14] experiment | jul12-023 (Arc-4 市场中性 微盘多头−IC空头@1.2×) train=0.3202(gate PASS,sharpe2.64) val=-0.5260(gate FAIL,sharpe-0.39,maxdd 12.3→41.6) val-dq confirmed=NO → 归档 validated_strategies/jul12-023.py(gate fail仍收) + 新建 [[jul12-023]] 实验页 + 回填 [[期货与套利]](IC对微盘basis不足、对冲工具须匹配alpha规模)· [[小市值因子]](微盘beta可对冲但regime-conditional)；⚠BASIS风险主导(非成本)/期货腿未计成本/TRAIN门槛边际薄0.14窗口外反转

## [2026-07-14] META | Arc-4 加入 Arc-2/Arc-3 成为 OOS/VAL 负结果序列：市场中性结构在 TRAIN 确证 beta 诊断(IC空头 maxdd 25.4→12.3)且过门槛，但 VAL 因 basis 风险灾难反转——VAL 抓住了 TRAIN 永远看不到的反转，**验证严格窗口协议**。本纪元至今**唯一同时过 TRAIN+VAL 者仍是 Arc-1 日内剥头皮 [[jul12-005]]**（regime-agnostic）；Arc-2/3/4 皆负。方向性 beta 与 basis-mismatch 对冲在此评测台都不稳健。

## [2026-07-14] experiment | Arc5 流动化移植归因（jul12-025 = Arc-1 引擎 bit-identical + universe 微盘→中证1000）= 负结果（DQ baseline，无results.tsv行、无归档）：edge 不衰减而**反号**，obj 1.3898→−0.5823（annual +150→−13，sharpe 5.96→−0.67，maxdd 11.5→45.4）→ 新建 [[arc5-liquid-transplant]] 归因页 + 回填 [[均值回归]]（日内反转是微盘微观结构专属、流动名上变momentum买falling knife）· [[小市值因子]]（⚠Arc-1 winner 双重打折：零滑点高估 + universe-locked容量受限微盘alpha）；[[jul12-025]]

## [2026-07-14] META | Arc-5 锐化「Arc-1 为何特殊」：其 edge 是**微盘微观结构专属**（散户超调回抽），**非可移植的日内反转配方**——bit-identical 引擎换到流动 universe 即反号亏损。5 弧至今：**仅 Arc-1（[[jul12-005]]）双窗口过关，且仅在一个规模化不可交易的微盘 universe 里**（高换手零滑点高估 + 容量受限 + universe-locked）。整个 epoch 的「赢家」都带三重保留意见。

## [2026-07-14] experiment | epoch2(jul12) 收敛综述 → 新建 capstone [[epoch2-jul12-summary]]：ideator 宣告 KB 正 EV 家族在冻结 harness + 2022-23 TRAIN 下耗尽。5 弧探索完毕，恰 1 个双窗口幸存者（Arc-1 [[jul12-005]]，但三重受限=不可部署），0 个可实现产品。账本 2 行定稿（jul12-005 recorded / jul12-023 val-dq），DQ baseline(Arc-2/3/5)不占行。5 条持久 META：窗口惩罚方向性beta/basis；junk-tail alpha 与 beta/basis 不可分不可变现；日内反转微观结构锁死(流动化反号)；趋势缺失窗口 ETF 动量/反转两向无 edge；零滑点+期货未计成本使高换手/对冲类系统性偏乐观，护栏正确抓住两个 would-be winner。下一纪元若求诚实可实现赢家须换 harness(计换手成本)或换含牛市窗口。
