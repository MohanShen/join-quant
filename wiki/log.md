# 知识库活动日志

追加式记录，每行一条：`## [YYYY-MM-DD] <op> | <说明>`
`op` ∈ { ingest, skip-dup, concept, query, lint, merge }。详见 `docs/wiki-schema.md` §5。

---

## [2026-07-20] study | 9cba5a29_行业资金流入小市值 (q-1+FINALIZE：微盘周度小市值(深证综指/国证2000→smallest-200→smallest-100·周二调仓·6持仓·联合线+大盘趋势止损 stoploss_strategy=3·4月空仓·空仓月持3 ETF)+招牌「行业热点资金流入」hot-sector 硬过滤(smallest-100 后只保留申万二级属 g.top_sectors 前10资金流入行业)·家族 [[小市值因子]]；MARGINAL 过门槛(Sharpe 2.53/obj 0.4094 家族垫底)；消融 绕过 hot-sector 硬过滤(final_list=industry_filtered_stocks→纯最小市值,同 g.top_sectors 计算保留)确证=STRICT LARGE NET DRAG——同时改善每一根轴：total 154.81→335.76%/年化 59.73→108.96%(+49pt)/Sharpe 2.53→4.71(+2.18)/maxDD 18.79→9.99%(近腰斩)/obj 0.4094→0.9897(+0.5803)；机制=过滤缩小可选池→过度集中抬回撤 AND 追逐热点行业切收益,与真 edge 微盘 size 因子对着干；家族对照=非惰性(8dbd994c)非损坏(2a4882de)而是主动摧毁价值,本批「头条 overlay 稀释/伤害小市值核心」模式最强一档(8dbd994c 惰性/2a4882de 损坏/9f6f8188·1c80dd9a·2f5bc859 拖累/本=严格大拖累);偏弱头条 objective 完全是过滤器锅,纯最小市值 sleeve 独立 obj 0.99(与 [[17c95d16_小市值微调]] 同档);drag 非 risk/return tradeoff(return AND drawdown 双改善,in-window likely regime-robust,另 regime 可能翻正=未测);⚠零滑点高估(纯最小市值高换手,方向稳健幅度虚高)+基础止损/空仓未在本 target 独立消融(迁移自 17c95d16/76593fb6);反哺=hot-sector/资金流入 HARD FILTER 叠加微盘账本可能 STRICTLY value-destroying、诊断弱 objective 微盘策略先消融招牌 overlay 再断定 size 因子弱;status=done) → 回填 [[小市值因子]]
## [2026-07-20] study | 2f5bc859_四择时大小盘风格轮动 (q-1+FINALIZE：3 择时 大小盘 style-vote 切换器(择时一大小盘涨幅博弈/择时二沪深300-vs-国证2000比值/择时三小市值一致性→白马大市值/高息低价小盘/国债ETF避险+MACD顶背离风控)·家族 [[小市值因子]]；MARGINAL 过门槛(Sharpe 2.67/obj 0.4564 垫底带)；消融 force final_signal='small'(关 style vote=纯高息低价小盘,保留 MACD 风控 ON 隔离 STYLE 投票)确证=NET DRAG——total 153→228%/年化 59.16→81.26%(+22pt)/Sharpe 2.67→3.52/maxDD 13.52→14.70%(仅+1.18pt)/obj 0.4564→0.6656(+0.2092)；style vote 是次要 DD 削减器(带它低~1.2pt)但主要收益拖累,annual−maxDD objective 上 dominated；偏弱头条 objective 是 STYLE-VOTE artifact NOT 组件损坏(纯小盘 sleeve 独立 obj 0.67)；家族对照更接近 [[9f6f8188_大小盘多策略]] 严格稀释而非 [[1c80dd9a_大小外择时小市值]] 真实但昂贵保护(DD 保护太薄不值收益代价)；⚠零滑点高估(小盘高换手)+regime-conditional(2022-23 偏好小盘→切离付收益;小盘崩盘 regime 可能翻正);反哺=多择时 style-vote 在小盘主导 regime 倾向净拖累(三次复现)、加风格切换/避险 sleeve 须 out-of-regime 保护测试证成;个别择时子信号+MACD 风控腿+市场温度白马过滤 un-ablated;status=done) → 回填 [[小市值因子]]
## [2026-07-16] study | 1c80dd9a_大小外择时小市值 (q-1+FINALIZE：大/小/外月度 style-timing 小市值切换器·家族 [[小市值因子]]；MARGINAL 过门槛(Sharpe 2.52/obj 0.4659 垫底带)；消融 force g.singal='small'(关择时=纯小盘)确证=真实 risk/return tradeoff——total 151→358%/年化 58.53→114.23%(近翻倍)/Sharpe 2.52→3.95/maxDD 11.94→29.95%(+18pt)/obj 0.4659→0.8428(+0.3769)；大小外切换是真实回撤保护器(腰斩微盘 DD 30%→12%,头条低回撤由择时交付 NOT size)但过付收益(冻结窗偏好小盘→切离付掉近半年化)故 objective 净拖累；关键对照 [[9f6f8188_大小盘多策略]] 严格拖累(去掉每轴皆改善) vs 本 target 真实但昂贵保护(去掉 obj 升 AND 回撤翻倍);纯小盘 29.95% 揭示未对冲微盘真实回撤;⚠零滑点高估+regime-conditional(小盘崩盘 regime 择时可能翻正);反哺=harness annual−maxDD objective 低估风险削减、区分 objective-drag vs 真实风险价值;regime 子窗 un-run;status=done) → 回填 [[小市值因子]]
## [2026-07-16] study | 4fa17009_五福v5差异化滤波 (q-1+FINALIZE：五福v5 单-ETF 动量轮动·家族 [[ETF轮动]]；标志性差异=差异化滤波(Laplace, g.enable_laplace_filter)——消融确证非惰性但小：obj 0.6053→0.5744(−0.031)、年化80.15→77.06(−3.09pp)、Sharpe 2.61→2.5055(−0.10)、maxDD 不变(19.62%)故价值走收益/入场质量非回撤控制；核心脆弱性=razor's-edge gate-pass，滤波恰供给越 2.5 硬门薄垫(去掉仅+0.0055 越门，一噪声tick即DQ)；⚠零滑点&短窗口高估、真实成本极可能 sub-gate；标题「11年538倍」是长窗口/自报成本数字非冻结窗现实(obj 0.6053)；与小市值族大margin对照=ETF动量族远更脆弱/边际(横评32成员仅5过门)；其余滤波器(R²/MA/放量/溢价/弱势择时)未逐个消融=预算；status=done) → 回填 [[ETF轮动]]
## [2026-07-16] study | 76593fb6_中小板微盘优化稳定 (q-1+FINALIZE：微盘周度·同源姊妹 [[17c95d16_小市值微调]]；标志性差异=联合线+大盘趋势止损(strategy=3, limit=0.09)；消融确证联合止损承重(NOT 惰性)——g.run_stoploss=False 后 obj 0.8385→0.6737(−0.1648)、maxDD 11.52→19.07%(+7.55pt)、Sharpe−0.53、年化−8.93pt；REFINES 家族「止损惰性」先验(那只对 17c95d16 纯止损线成立)——干活的是大盘趋势腿(10:00 指数下跌比≥5%→全平)、2022 熊 binding；⚠零滑点高估其可实现保护(下跌微盘日内 order_target_value(0)、出场泊进 银华日利ETF)；家族季节空仓=DD主引擎/MA-sizing objective-负/国九条净正/regime 稳健结论迁移自姊妹未复测；stop TYPE matters；limit=0.09 敏感性 + strategy=1/2/3 三态隔离 un-run；status=done) → 回填 [[小市值因子]]
## [2026-07-16] study | aaba7575_国九小市值排除3bug版 (q-1+FINALIZE：微盘周度·同源姊妹 [[17c95d16_小市值微调]]；国九条质量过滤(net_profit>0 & revenue>1e8)消融确证=温和净正 RETURN-ADDITIVE 筛——移除 obj 0.8809→0.8015(−0.0794)、年化 −8.8pt、Sharpe−0.22，maxDD 反略降(11.10→10.28)故价值走收益非可见DD；⚠干净回测低估其 live junk-tail/退市护栏；归因下界(保留 np_parent>0)；与 [[5a70adc1_小市值筛选条件研究]](过滤全关)对照成组=启用质量过滤是净正；家族日历空仓/止损/MA-sizing 结论迁移自姊妹未复测；⚠零滑点高估；status=done) → 回填 [[小市值因子]]
## [2026-07-16] study | 5a70adc1_小市值筛选条件研究 (q-1+FINALIZE：微盘周度·姊妹 [[17c95d16_小市值微调]]；纯最小市值(质量过滤全注释关闭=标题的筛选条件研究)；独特点=Jan/Apr 空仓月轮入防御ETF(债券/黄金/银行)而非坐现金——消融确证优于现金 objective+0.039、maxDD−0.81pt，家族级温和改进；家族季节空仓=DD主引擎/止损惰性等结论迁移自姊妹未独立复测；⚠零滑点高估+纯最小市值抬高junk-tail暴露；status=done) → 回填 [[小市值因子]]
## [2026-07-16] study | 5e874b5b_低开小市值年化105 (q-1+FINALIZE：低开剥头皮族第三名，引擎迁移自 [[7a1c225f_小市值低开优化]]；标志性 9:40 day-open 止损时点扫描——objective+Sharpe 峰在 11:30，本成员 9:40 偏早/次优、移到 siblings 时点抬 obj+0.20；时点=收益旋钮非单调风险旋钮，单调性被否；标题20%maxDD 本 harness 实为10.30%；status=done) → 回填 [[小市值因子]]
## [2026-07-15] study | 8dbd994c_年化180逻辑奇怪小市值 (q-1+FINALIZE：近似克隆 [[7a1c225f_小市值低开优化]]；标题的「逻辑奇怪」a1卖一档买一金额/市值降序排名消融确证 INERT 且轻度反效果——移除 obj 1.281→1.3953、maxDD 不变，怪逻辑「有效因为约等于没做」；核心机器与三层归因迁移自姊妹；status=done) → 回填 [[小市值因子]]
## [2026-07-15] study | 15c36e0c_ETF溢价改进版 (q-2+FINALIZE 分区间：21.46% maxDD 为 2022 熊市专属(2022 精确复现)、2023/2024 仅5-9%，edge regime-robust；每窗回撤 ~2.3× 深于姊妹 fa0d3bd9=集中度非regime；踩踏尾部不可测；status=done) → 回填 [[ETF轮动]]
## [2026-07-15] study | 15c36e0c_ETF溢价改进版 (q-1 流动性分层扫描：illiquidity-premium 指纹在折价族内复现且更陡，edge 活在≤2e7 CNY/日、5e7-1e8 即 DQ；t0单独复现基线) → 回填 [[ETF轮动]]
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

## [2026-07-14] study | fa0d3bd9_PT多策略并行 (代码实为单信号ETF折价均值回归≠wiki四策略叙事;滑点0→0.003扫描每翻倍总回报约减半、门槛稳健但369%年化零滑点高估) → 回填 [[ETF轮动]]（折价族头条=零滑点×低流动universe产物、成交额过滤下界×滑点弹性作真实性护栏）；⚠wiki/代码不符flag待人工核对(勿覆盖策略页)

## [2026-07-15] study | fa0d3bd9_PT多策略并行 q-2 流动性分层扫描：折价 alpha 随成交额 band 上移单调衰减（Sharpe 18.16→4.74→1.09→0.89，maxDD 反而 9.55→21.15% 恶化），门槛在 5000万–1亿即失守——教科书 illiquidity-premium 指纹，全部 edge 集中在最不流动 5–20M CNY/日 band。与 q-1 同源：制造 edge 的成交额下界=让零滑点不真实的过滤器 → 真实但 capacity-capped 不可规模化。→ 回填 [[ETF轮动]]（折价 alpha=单调 illiquidity 溢价、成交额下界作开关）

## [2026-07-15] study | fa0d3bd9_PT多策略并行 FINALIZE (status=done, 四轴齐) q-3 分区间：头条 9.55% maxDD 是 2022 熊市专属（2022 独占复现 9.55%、2023 仅 3.24%/2024 仅 4.48%），edge regime-ROBUST（各年 Sharpe 18–26、2024 最佳）；2024-02 踩踏窗 maxDD 反最低 2.39%——raw 数字证伪 illiquidity 尾部爆仓，但零滑点+跌停不卖掩盖挤兑成本故不可测。一句话结论：单信号不流动 ETF 折价均值回归/illiquidity 溢价，真实但 capacity-capped × 零滑点高估、低 maxDD 熊市专属、尾风险本 harness 不可裁定。→ 回填 [[ETF轮动]]（折价族低回撤 regime-specific、liquidity-crunch 尾在零滑点台不可测）

## [2026-07-15] study | 7a1c225f_小市值低开优化 q-1 滑点弹性扫描（恢复作者自带 PriceRelatedSlippage r 0→0.003，train 2022-2023）：objective 近似线性侵蚀 1.3738→1.10→0.94，无悬崖无平台，滑点=拖累非尾部（maxDD 仅 +0.4–0.7pt）；在作者声明的 0.2% 下仍舒适过门槛（Sharpe 4.74、obj 1.10，~25% 折价），DQ 只在 ~3× 声明滑点。CONTRAST：明显比 ETF 折价 illiquidity 族（[[fa0d3bd9_PT多策略并行]] 轻微摩擦即 DQ）更耐滑点——真实且门槛稳健、头条轻度高估非虚构。→ 回填 [[小市值因子]]（低开剥头皮族滑点稳健 vs 折价族容量受限对照）

## [2026-07-15] study | 7a1c225f_小市值低开优化 FINALIZE (status=done, 两轴：真实性+归因) q-2 组件消融：11:30 破开盘价日内止损是 EXISTENTIAL 单一主导——去掉 total +516→−29%/maxDD 11.1→39.7%/Sharpe 5.81→−0.72（EV 转换器非回撤削减器）；低开入场闸门=alpha/选择性（去掉 annual 148.5→32.7、Sharpe 1.40 DQ）；+5% 止盈=收益点缀（缺仍过门槛）。归因排序 日内止损≫低开入场>止盈。强确证 Arc-2 先验「低回撤=日内风控机器非 size」。⚠ 该 DD 机器依赖无摩擦微盘盘中退出，~11% 低回撤部分是回测假象、现实更差。一句话结论：选择性低开均值回归入场靠存在性 11:30 破价止损转成正 EV；低回撤是风控机器产物+部分无摩擦成交假象；另 q-1 滑点独立稳健。参数敏感性/regime 未覆盖（批量适度深度）。→ 回填 [[小市值因子]]（低开剥头皮族低回撤=日内止损制造非 size、消融确证、无摩擦成交 caveat）

## [2026-07-16] study | 17c95d16_小市值微调 q-1 分区间（同源不改，冻结零滑点，⚠全行零滑点高估）：canonical 微盘股周度3持仓 maxDD 区间同质 9-14%（2022=9.32/2023=9.88设train基线/2024=13.60仅+3.7pp/2024-02踩踏窗=11.17）→实测证伪「2024微盘崩盘回撤爆仓>20%」假说，每整年窗过gate；2023震荡是drag年(total55%/Sharpe3.03/obj0.453)非崩盘；防护栈把踩踏窗压11%后吃反弹+34%但⚠crash-shielding是最不可实现部分(3持仓微盘踩踏出场依赖蒸发的流动性=零滑点回测属性非可实现声明)。status仍in-progress，下轮消融防护栈归因低回撤主因。→ 回填 [[小市值因子]]（微盘周度maxDD regime-同质、踩踏ON零滑点停11%、crash-shielding最不可实现）

## [2026-07-16] study | 17c95d16_小市值微调 FINALIZE (status=done, 四轴齐：regime+组件归因+参数敏感性+机理真实性) q-2 组件消融（冻结零滑点，⚠全行零滑点高估）：广告低~10%回撤主要由日历空仓(1/4/12月seasonal cash-out)交付 NOT size/止损/MA——去日历 maxDD 9.88→15.15%(+5.27唯一存在级DD削减器/年化-5.6pt=近乎纯风险削减)；日内止损 INERT/冗余(去掉maxDD仅+0.10,滑点后很可能净负);MA动态仓位 objective-负(只扩仓不清仓,去掉固定3仓 total 300→367%/年化+16pt/net Δobj+0.13=过付16pt年化削3pt DD)。回撤归因:日历空仓(主导+5.27)>MA sizing(+2.92但obj-负)≫止损(惰性+0.10)。一句话结论：微盘周度质量小盘，低回撤靠日历空仓非风控层，两防护组件冻结objective下次优，crash-shielding是零滑点假象。→ 回填 [[小市值因子]]（微盘周度低DD=seasonal-blackout artifact非风险模型、防护组件可能INERT/objective-负先消融、crash-shielding零滑点不可实现）

## [2026-07-16] study | 2a4882de_动态仓位小市值五年20倍 FINALIZE (status=done, 家族迁移+一条标志性实验) q-1 消融：同名头条「动态仓位」多因子调仓引擎出厂 g.adjust_num=False 关停(死代码)且已损坏——打开(唯一改这一 bool)直接 CRASH(两跑 failed，-22 索引取 ~14 行回看帧→确定性 IndexError)；策略实为固定3仓微盘周度，[[17c95d16_小市值微调]] 近乎同源姊妹，基线 obj 0.746 唯一可运行；真正引擎(seasonal-blackout 低回撤主导/国九条质量过滤净正/价格止损线惰性)迁移自家族。比 17c95d16「MA sizing objective-负」更强：这里 MA 调仓不是负而是 un-runnable。头条过度标榜不运行的特性，⚠ 家族零滑点高估适用。→ 回填 [[小市值因子]]（头条特性可能=死代码/损坏须先验证执行；index/MA 动态仓位在微盘家族双证未增益）

## [2026-07-16] study | bf30eb36_三马105五福35修复 FINALIZE (status=done, LIGHTER treatment：baseline+结构+家族迁移+runtime-limitation，消融不可行) q-0 结构探针 + q-1 消融尝试（冻结零滑点，⚠零滑点高估 + runtime-infeasible）：191KB/4460 行三马v10.5+五福v3.5 多策略 merge，跑 isolated 虚拟子账户 [0.5,0,0.5,0]=50% 小市值+50% 五福ETF-momentum blend，基线 total 145%/年化 56.62%/Sharpe 2.57/maxDD 9.92%/obj 0.467=MARGINAL gate-pass（Sharpe 刚过 2.5），低 DD 迁移自小市值家族 blackout。计划 sleeve-attribution 消融（50% 五福→[1,0,0,0]）UNMEASURED——变体 20min/30min 两 poll 上限均 slow-skip >1800s，191KB merge 每 bar 重跑 250 日 ETF 预载+全池 RSRS（0 权重 sleeve 也触发 run_daily）→ harness 下无法 ablate。由平行 [[9f6f8188_大小盘多策略]]+[[4fa17009_五福v5差异化滤波]] 推断五福 momentum sleeve LIKELY 稀释强小市值 sleeve（边际 Sharpe 2.57 vs 纯小市值~4-6），但为 inference 非实测。反哺：(i) 重量级多 sleeve merge 可能不可实用地 backtest/ablate/validate=maintainability 红旗；(ii) 强小市值+脆弱 momentum 边际-Sharpe blend 很可能稀释，优先纯强 sleeve。→ 回填 [[小市值因子]]（重量级 merge 太慢无法消融=maintainability 红旗、边际 blend 五福 momentum 稀释强小市值为 inference-未实测）

## [2026-07-16] study | 9f6f8188_大小盘多策略 FINALIZE (status=done, 多 sleeve 拼装：一条决定性归因 + 小盘家族迁移，弱/边际策略适度批深) q-1 消融（冻结零滑点，⚠零滑点高估 + regime-specific）：30% 大盘价值(large-cap-value) sleeve 在冻结 2022-2023 窗口是净拖累——把其权重回填给两小盘 sleeve（proportion [0.35,0.3,0,0.35]→[0.5,0,0,0.5]）每根轴同时改善：年化 57.26→81.53%(+24.3pp)、maxDD 反降 9.55→8.40%(−1.15)、Sharpe 3.26→3.96、objective 0.4771→0.7313(+0.2542,+53%rel)。真正多样化用收益换低 DD；这里去掉它收益升 AND 回撤降=没兑现回撤保护、纯稀释更强的小/微盘 sleeve。策略偏弱头条 obj 是 BLEND-WEIGHT 产物非组件损坏（底层小盘引擎 obj 0.73 与家族齐平）。weight-0 sleeve sizing=0 干净空持无崩溃。⚠ 吸收权重是高换手微盘零滑点高估收益增幅；drag 判定 window-specific（大盘价值在小盘崩盘 regime 如 2024-02 踩踏可能真保护，本窗未含）。一句话结论：大小盘多策略拼装的大盘价值 sleeve 冻结窗内净拖累、多市值多样化适得其反且是弱 objective 之因；小盘 sleeve 机理迁移自 [[17c95d16_小市值微调]] 家族。参数敏感性/regime 未系统覆盖（适度批深；注 drag 结论 window-specific 跨 regime 未测）。→ 回填 [[小市值因子]]（naive 大盘+小盘拼装可能纯收益稀释非多样化、大盘价值 sleeve 小盘主导 regime 净拖累、多样化须 out-of-regime 保护测试证成、弱拼装先查 blend 权重）

## [2026-07-20] study | 3c462ece_三马七星1.7.2大池 FINALIZE (status=done, 一条决定性 sleeve 归因 + 家族迁移，弱/边际策略适度批深) q-1 消融（冻结零滑点，⚠零滑点高估 + regime-conditional）：与姊妹 [[bf30eb36_三马105五福35修复]] 同一 三驾马车 v10.5 框架、同 proportion [0.5,0,0.5,0]（50% 小市值 + 50% ETF轮动），ETF sleeve 为 七星高照 V1.7.2「大池」版。基线 MARGINAL 过门槛（Sharpe 2.52、obj 0.3837、家族垫底带）。bf30eb36 因 191KB merge 超时 slow-skip 只能 INFER 的 sleeve-attribution 消融，此处完整跑通：50% ETF sleeve 回填给小市值（[0.5,0,0.5,0]→[1,0,0,0]）→ objective 0.3837→0.5782(+0.1945)、年化 51.01→71.83%(+20.82pt)、Sharpe 2.52→2.63，仅 maxDD 12.71→14.01%(+1.30pt)。归因：七星 ETF-momentum sleeve = minor DD reducer(~1.3pt 弱保护)/ major return drag，annual−maxDD objective 上净拖累（21pt 收益牺牲 ≫ 1.3pt DD），形态同 [[2f5bc859_四择时大小盘风格轮动]] 非 [[9cba5a29_行业资金流入小市值]] 严格拖累。弱头条 obj 主要是 ETF sleeve 的锅，纯小市值 sleeve 独立 0.58。bf30eb36 稀释推断 CONFIRMED（inference→measured）。一句话结论：三马七星1.7.2大池是与 bf30eb36 同框架的 MARGINAL gate-pass，其 50% 七星ETF-momentum sleeve 净拖累，纯小市值 [1,0,0,0] 升 objective 0.38→0.58 仅 +1.3pt maxDD，实测并确证 bf30eb36 只能推断的 sleeve 稀释；⚠ 零滑点高估 + regime-conditional。→ 回填 [[小市值因子]]（三驾马车 50/50 小市值+ETF轮动 blend 的 ETF-momentum sleeve = MEASURED 净拖累、确证 bf30eb36 sleeve 稀释推断、minor DD reducer/major return drag）

## [2026-07-20] study | 3a5ab0c1_小市值ETF轮动组合 FINALIZE (status=done, 一条决定性 sleeve 归因 + 家族迁移，NUANCED CONTRAST 到本批 drag 模式) q-1 消融（冻结零滑点，⚠零滑点高估 + regime-conditional）：50/50 双 sleeve 组合（50% 优质小市值周轮动 ＋ 50% ETF收益率稳定性轮动 stability-focused+技术滤波，隔离子账户+动态再分配），基线 MARGINAL 过门槛（Sharpe 2.57、maxDD 9.75%、obj 0.3689）。与本批 [[3c462ece_三马七星1.7.2大池]]/[[9f6f8188_大小盘多策略]] 的 blend-drag 模式相反：去掉 ETF sleeve（[0.5,0.5]→[1,0] 且 enable_dynamic_proportion=False，唯此一改）raw 年化 46.64→53.54%(+6.9pt) 却 Sharpe 2.57→2.34（跌破 2.5 门槛 DQ）、maxDD 9.75→12.49%(+2.7pt)，obj 仅 +0.04（噪声内且 DQ）。归因：ETF sleeve = GENUINE DIVERSIFIER，兑现真实回撤压制+提 Sharpe，且是保住边际策略过门槛的组件；纯小市值 raw return 更高但风险调整后更差=真实 risk/return tradeoff（cf. [[1c80dd9a_大小外择时小市值]]）非严格拖累（cf. 3c462ece）。区别关键在 diversifier 构造质量（stability-focused 轮动多样化，七星 momentum 拖累）。→ 回填 [[小市值因子]]（COUNTEREXAMPLE：sleeve 价值取决于 diversifier 构造质量不止小盘 vs 非小盘、stability-focused ETF 轮动真实降 DD 并保住过门槛；annual−maxDD objective under-credits 不抬该指标的真实 Sharpe/DD 改进、遗漏保住过门槛的可部署价值）
