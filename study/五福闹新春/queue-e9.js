// gatekeeper, 2026-10-25 — epoch-9 round 2 queue for 五福闹新春.
// Run once: node -e "require('./study/五福闹新春/queue-e9.js')"
const rq = require('../../utils/research-queue');
const F = '五福闹新春';

const E = [];

// ── rank 1 — ACTIVE ─────────────────────────────────────────────────────────
E.push({
  id: 'q-e9-leg', kind: 'understand', rank: 1, status: 'active', edgeRef: '动量',
  title: '冠军 bf30eb36 的腿分解：ETF 腿单独跑（小市值腿权重归零但保留其资本）',
  hypothesis: 'bf30eb36 的 1.94/1.97 主要由 ETF（五福）腿供给。v5.2 单独 annual 187.39% ⇒ 半仓 ETF 腿 + 半仓闲置资本应约 90–95% annual。证伪（双向，预注册）：ETF-腿-only annual ≥ 150%（obj ≥ 1.35）⇒ ETF 腿是驱动，冠军正当地属于本族；annual ≤ 100%（obj ≤ 0.90）⇒ 小市值腿供给多数，冠军归因错误，本族的「产品」大半是别族的边。90–100%/1.35 之间读作「两腿各半」，须由 census 侧（下）定案而非 Δ。',
  why: '四件事同时压在这一个读数上：(a) 本族 bestVariant 是 三马105-五福35 组合书，而 小市值 自己的冠军 bba95a11 也是 小市值×五福 杂交 —— 两族可能在互相把对方的腿记成自己的产品；(b) **它可以把一条已记录的 epoch-9 结论从结构性降级为算术性**：q-e9-pit-r2 记下「有股票腿 ⇒ 池不敏感 (3/3)」，但一条少数权重的 ETF 袖子在算术上就不可能让总额动 33%，那么该结论就不是「小市值腿的边无池可选」而只是「ETF 腿占比小」——而 CLAUDE.md 已经在用那张 4 本书的表决定哪些书是 pool-clean 可推进的候选；(c) integrate guard 的 rule-2 腿归因；(d) 我们正要给谁打 realizability 分。一条被引用的错结论比一条缺失的结论贵。',
  design: '父本 **study/五福闹新春/q-e9-pit_bf30eb36.py**（obj 1.9658 / sharpe 7.51，已测、有存档曲线 study_五福闹新春_q-e9-pit_bf30eb36__train__e9），**不是** strategies 里的生书 —— 生书的 ETF 池含 17 只窗后上市名字（其中 7 只 2025 年上市），它们全在 ETF 袖子里，用生书做腿分解会系统性高报 ETF 腿，正好偏向本测要检验的那一侧。编辑：L87 `g.portfolio_value_proportion = [0.5,0,0.5,0]` → `[0,0,0.5,0]`，单行。刻意**不**用 `[0,0,1,0]`：子账户资本隔离，保留 0.5 权重使持仓规模 / order_volume_ratio 咬合 / min_money 与父本逐字相同，否则权重与成交规模混淆。对照 = 父本已测行，**不跑对照**。--window train。\n⚠⚠ **构建期必须断言的两件事，缺一则结果作废而非解读**：(1) generator B 测到 **L3555 存在对 g.portfolio_value_proportion 的重复赋值** —— 若它可达，变体会静默跑父本配置并报 Δ≈0，而 Δ≈0 在本测里恰好读成「ETF 腿独力产出冠军全部收益」，是最坏方向的假阳性；builder 须证明 L3555 不可达或同步编辑它，并打印两处赋值的最终生效值。(2) 日志普查：strategy-1（小市值袖子）成交笔数必须为 **0**；非 0 即构建失败。\n免费 rider（同一份日志）：ETF 腿的持仓天数 / 空仓天数、走弱分支触发日数。',
  from: ['q-e9-pit-r2', 'q-e9-pit-b50e4387', 'q-e9-pit-bba95a11', 'ledger:bf30eb36@e9 obj 1.9437', 'orchestrator-verified:q-e9-pit_bf30eb36 obj 1.9658/sharpe 7.51', 'ledger:17b3b439@e9 obj 1.7479 annual 187.39'],
  note: 'ACTIVE。本轮第 1 跑。不触碰任何已关闭方向（冠军是 epoch 9 才进榜的书，§4 的 15 条关闭无一覆盖腿分解）。效应预估 ~1.0 objective，是旧噪声地板 0.031 的 30× 与其按水平缩放后 ~0.14 的 7×，所以读数不依赖 q-e9-floor。',
});

// ── rank 2 ──────────────────────────────────────────────────────────────────
E.push({
  id: 'q-e9-weak', kind: 'understand', rank: 2, status: 'queued', edgeRef: '趋势择时',
  title: 'edge test 趋势择时 在 epoch-9 台上重跑：走弱期永不触发（below_count 3→999）',
  hypothesis: '本族唯一 measured 的 edge 在 2024 单年窗上仍然主导。2022–23 上关掉它值 −0.4796（占当时水平 0.3755 的 −128%）。证伪（预注册）：Δobj > −0.50（即仍保留 ≥1.25，>71% 的水平）⇒ 在本台上不再主导，claim 必须重新界定范围或降为 proposed；Δobj ≥ 0 ⇒ 直接证伪，edge status 须改。',
  why: 'epoch 9 把 TRAIN 换成 2024 单年，measurementPreservedFromPrevious=false ⇒ 本族 23 条 findings 里 18 条与全部 13 条关闭都测于 2022–23，机制可能可迁移、幅度一定不可迁移。而 趋势择时 是本族**唯一**站得住的 edge（动量 已 refuted），它同时是 imp-e9-1 要移植进冠军的那个机制 —— 若它在 2024 上不成立，imp-e9-1 就不是 improve 而是无前提的移植，本族也成为 none-found 候选。2024 的两面性是真实的：2 月微盘股踩踏（闸门该帮忙）与 9/24–10/8 的 A 股暴涨（MA10 退出会迟 2–3 天错过 +25%）。',
  design: '父本 **生书 strategies/…17b3b439.py** 经 py2to3 + 现行 OVERRIDE 重建（build-e6.js 路径），对照 = 账本行 1.7479 / sharpe 5.97，**不跑对照**。编辑 = 复用既有 variants/q-2_no-weak-switch.py 的同一处单行（below_count 阈值 3→999），其余逐字不动。--window train。\n免费 rider（必须收割，这是本条真正便宜的部分）：(1) 2024 逐日 weak/normal 普查，含**最长连续走弱天数** —— 它免费重测 idea-imp-2 的 20 日上限前提（旧窗上该上限从不生效），而不重跑 imp-2；(2) 防御性 511880 兜底天数；(3) 走弱分支触发总日数，这是 q-e9-mechpool 与 imp-e9-1 的 census 配平基准（旧窗参照：点时广度均值 10.00、范围 7–13）。',
  from: ['q-e6-2', 'q-e6-4', 'q-e8-7', 'q-e8-3', 'harness:epoch9 measurementPreservedFromPrevious=false', 'ledger:17b3b439@e9 obj 1.7479'],
  note: '本轮第 2 跑。不是重开关闭方向：q-e6-2 是 answered 且 supported，本条是同一个 test: 在一张新测量台上的重测；它既不触 imp-2（退出上限）也不触 imp-3（进入阈值），两条都已关闭而本条是整机关断。§4 明确把「改池 / 结构侧」排除在 0.031 分钟地板约束之外，且预估效应是地板的 16×。',
});

// ── rank 3 ──────────────────────────────────────────────────────────────────
E.push({
  id: 'imp-e9-1', kind: 'improve', rank: 3, status: 'queued', edgeRef: '趋势择时',
  title: '把 A 股 breadth 走弱期切池移植进冠军的 ETF 袖子（冠军本身没有这个机制）',
  hypothesis: '冠军的 五福 袖子**没有** A 股 breadth 输入、没有走弱期切池 —— 它是一张 114 只合并池按动量排序、震荡期只换滤波（Laplace→Gaussian）的书，即它依赖 q-e6-1 已 refuted 的排序，而不依赖本族唯一 measured 的 edge。补上该机制应提升。幅度估计照实写：有切池的 v5.2 1.7479 vs v3.5/v3.1 血统的 1.4002/1.3832/1.3578 ⇒ 独立水平差 ~0.35 × 50% 权重 ⇒ 朴素 **+0.17**。证伪（预注册，三条）：Δobj ≤ 0 ⇒ 移植无效；走弱日普查显示闸门在 2024 的 ~242 日里活跃 **<20 日** ⇒ 判「惰性」而非「被证伪」（两者结论不同，不可合并）；若 0 < Δ < 0.16 ⇒ **定案必须来自结构侧**（走弱日数 × 两分支各自的持仓与收益归属），不得用 Δ 的数值。',
  why: '本族 improve 轴在 epoch 8 上被加总上界关死（0.4621 < 0.4848），epoch 9 把整张表作废后这是唯一一条站在真实结构缺口上的 improve：家族唯一的边不在家族自己的冠军里。generator B 另免费核实了移植不发明任何名字 —— base 的 17 只 g.global_etf_pool 全部已在冠军池内（17/17）。',
  design: '父本 **study/五福闹新春/q-e9-pit_bf30eb36.py**（1.9658），对照 = 该已测行，**不跑对照**。编辑点与本族已用过四次的那一处相同：13 只池字面量（base 的 17 只减去点时规则排除的 4 只）+ `check_a_share_weak_period` 逐字复制 + `morning_routine` 内 09:00 一次调用（刻意放在 13:1x 快照**之外**，q-e8-2 已定位噪声在该快照）+ 走弱分支的池取 `[x for x in g.filtered_fixed_pool if x in g.global_etf_pool]`，以保留冠军自己的流动性过滤、避免重新引入 q-e8-7 的 bypass 混淆。--window train。\n⚠ 与 q-e9-leg 共享的构建风险：L3555 的重复赋值（见 q-e9-leg），以及**池内名额数配平** —— §4 的设计约束要求改池实验保持每日通过滤波的广度不变，配平参照取 q-e9-weak 跑出的 2024 census，不得沿用 2022–23 的均值 10.00。',
  from: ['q-e9-pit-r2', 'q-e6-2', 'q-e8-7', 'q-e8-2', 'orchestrator-verified:q-e9-pit_bf30eb36 obj 1.9658', 'ledger:17b3b439@e9 1.7479', 'ledger:4d4705e1@e9 / 5ac906ea@e9 v3.x standalones 1.40/1.38/1.36'],
  note: '本轮第 3 跑，**条件性**：必须在 q-e9-weak 之后 —— 它移植的是 趋势择时，若该 edge 在 2024 被证伪就没有机制可移植，本条须改为 dropped 而非照跑。亦须在 q-e9-leg 之后：若 ETF 腿只占少数，+0.17 的朴素估计要再对半折，读法随之改变。朴素 Δ 落在按水平缩放后的 ~0.16 噪声估计附近，所以预注册的 census 定案条款是本条可资助的理由（q-e8-2 的设计规则：要么远超地板，要么结构性定案）。',
});

// ── rank 4 ──────────────────────────────────────────────────────────────────
E.push({
  id: 'q-e9-liq', kind: 'understand', rank: 4, status: 'queued', edgeRef: '趋势择时',
  title: '冠军 bf30eb36 的 realizability 取证：两腿各自的可成交下限地板 + 逐日 LIQFLOOR 普查',
  hypothesis: '冠军在自身 ¥1M 规模下不是 floor-broken。按 harness 自推的逐腿地板：ETF 腿 ¥1e6×0.5÷1÷0.05 = **¥1e7/日**，股票腿 ¥1e6×0.5÷5÷0.05 = **¥2e6/日**。证伪（预注册）：加地板后 obj < 1.00 **或** sharpe < 1.0 ⇒ R=1；Δ ≥ −0.20 **且**地板在普查中可证非惰性 ⇒ R=2。**R=3 明确不可主张**（容量是能吸收多少本金，不是到闸的余量 —— CLAUDE.md 对大小盘轮动产品的自我更正）。',
  why: '`realizability:` 未设 ⇒ integrate 闸门对本族 BLOCKED，而未知 realizability 是阻断而非放行。本族此前只测过 pit9 这本非候选书（q-e8-3：¥2e7 上 0.3962→0.3463，sharpe 1.85 仍过闸，地板非惰性），冠军是两腿书、从未测过。免费顺便定一件事：股票腿**不是** R=1 的 小市值 形态 —— market_cap 10–100 亿、5 只、周频 09:40/09:45、无集合竞价入场、无 tick-depth ×100、`high_limit` 用作 REJECT；它唯一一条实测严重度的 lint flag 是 L2769 的 uncapped-position-size。',
  design: '父本 **study/五福闹新春/q-e9-pit_bf30eb36.py**，对照 = 1.9658 已测行，**不跑对照**。逐腿施加各自地板，逐腿逐日打印 LIQFLOOR in/out 与 money=，--window train。\n⚠ q-e8-3 已经关掉「再加一个地板点看剔除多少只」这类测项（剔除侧存活曲线由 money= 日志免费给全阈值），所以本条**不得**把剔除侧普查当作新结果出售；它可资助的理由只在**绩效侧**（新书、两腿、从未测过）。\n⚠ 必须在 q-e9-leg 之后：若股票腿供给多数收益，R 的数值须 **scope 到那条腿**并与 小市值 实测的 R=1 并读，且 `realizabilityScope:` 必须点名所描述的那本书（CLAUDE.md：realizability 是一本书的属性，而页面只放一个数）。',
  from: ['q-e8-3', 'q-e9-leg', 'integrate-eligible:realizability unset ⇒ blocked', 'orchestrator-verified:q-e9-pit_bf30eb36 obj 1.9658', 'realizability-lint:bf30eb36 uncapped-position-size L2769'],
  note: '本轮第 4 跑。R 的数字由 orchestrator 落到 frontmatter，不由本条自行写入页面。',
});

// ── rank 5 — funded only as a contingency ───────────────────────────────────
E.push({
  id: 'q-e9-rank', kind: 'understand', rank: 5, status: 'queued', edgeRef: '动量',
  title: 'edge test 动量 在 epoch-9 台上重跑：池内排序方向反转（持最弱的正趋势 ETF）',
  hypothesis: '2022–23 的证伪可迁移。证伪（预注册）：反排 annual ≥ 187.39% 的 75%（≥140.5%）⇒ 证伪仍成立，q-e6-1 的整条关闭保持关闭；≤50% ⇒ 该关闭重开，动量 status 须从 refuted 改回 proposed/measured。rider：反排与 base 的日收益相关（旧窗 0.33）。',
  why: '冠军的 ETF 袖子正是靠动量排序选名（generator B 的结构核实），而本族记下的是「测得的 edge 是池子不是排序」。若 2024 上排序仍无用、而 q-e9-pit-r2 又记下杂交书的池加成为 0%，那冠军的 ETF 袖子既不靠排序也不靠池子 —— 这是一个真实的张力，值得一个读数。',
  design: '父本 生书 17b3b439 经 py2to3 + OVERRIDE，对照 = 账本行 1.7479，**不跑对照**。编辑 = 既有 variants/q-1_invert-rank.py 的同一处单行 `reverse=True`→`False`。--window train。',
  from: ['q-e6-1', 'q-e9-pit-r2', 'q-e9-pit-b50e4387', 'ledger:17b3b439@e9 1.7479'],
  note: '**不是重开 q-e6-1 的关闭**：那条关闭的文本明确只关 improve（「调 lookback、斜率加权、R² 乘子、score_threshold_ratio 这类把第一名选得更准的 improve 想法」），且 imp-1 的 implication 已修正读法为「关闭的是挑最强，不是按动量离场」；本条跑的是 edge 自己的 test: 在新台上的重测。**先验强烈指向「会确认」**，这不降它的分（understand 按是否解决不确定性判，不按是否改善目标判）—— 但它排在腿分解之后，因为若 ETF 腿只是少数袖子，这个张力自行消失。**本轮的替补**：若 q-e9-weak 证伪了 趋势择时，imp-e9-1 失去前提，本条顶上第 3 跑。',
});

// ── rank 6 — queued, NOT funded: design defect ──────────────────────────────
E.push({
  id: 'q-e9-mechpool', kind: 'understand', rank: 6, status: 'queued', edgeRef: '趋势择时',
  title: '机械点时走弱池：移植成员 9473ea7a 的 build_etf_pool(end_date) 替换手写的 17 只避险池',
  hypothesis: '走弱期那半边收益不依赖作者的**资产类别**选择。证伪：obj < 1.20（≤1.7479 的 69%）⇒ 该腿依赖作者选的类别集合，§4 第一条残余成立。',
  why: '§4 唯一**完全未结**的残余：q-e8-7 的上市日规则只消掉上市日期事后性，那 9 类（黄金/美股/德国/日经/白银/原油/豆粕/有色）仍是 2026 年作者选出的类别集合，而 §4 和 q-e8-7 的 implication 都写明「彻底 settle 仍只有逐日点时池一条路」。新成员 9473ea7a 自带这台机器（get_all_securities(["fund"], date=end_date) + 货币/债券排除 + MIN_LIST_DAYS + 规模 + 流动性 + 机械 yy_asset_class 分类，月度重建），所以第一次有一个可负担的实现。',
  design: '取 {商品 ∪ 跨境}，月度重建，父本 生书 17b3b439 + OVERRIDE，对照 1.7479。--window train。\n⚠⚠ **本轮不资助，三条必须先收紧，否则跑了也答不了它自己的问题**：(1) `yy_fetch_traced_index_table()` 的分类表缓存在**真实的今天**，所以这台「机械点时」机器自己带属性级 lookahead —— 用一个含窗后知识的分类去消除资产类别事后性是循环的；须换成跑前冻结的类别映射，或一条只引用上市日期 + 静态命名规则的判据。(2) 多函数逐字移植是七条里构建风险最高的一条，而本仓的判例要求移植必须有**单一可断言的编辑点**（q-e8-7 断言改动行恰为排除项；q-e9-pit 的 builder 在池无日期时直接 REFUSE）。(3) 广度配平的参照必须取 q-e9-weak 跑出的 **2024** census，不能沿用 2022–23 的均值 10.00（范围 7–13），否则「改池」与「每天是否有东西通过滤波」再次混淆 —— 而且若 2024 的走弱日很少，本测量的是一条近乎惰性的分支，读数不成立。',
  from: ['q-e8-7', 'q-e8-1', 'q-e8-3', 'family-page:§4 资产类别事后性 唯一完全未结项', 'member:9473ea7a build_etf_pool'],
  note: '方向正确且是 §4 最后一条完全未结项，但本轮**不资助**：设计缺陷（分类表的 lookahead）使它当前跑不出它声称要答的东西，且其可读性依赖 q-e9-weak 的 2024 census。按上列三条收紧后下一轮优先。',
});

// ── rank 7 — queued, NOT funded ─────────────────────────────────────────────
E.push({
  id: 'q-e9-dipbuy', kind: 'understand', rank: 7, status: 'queued', edgeRef: null,
  title: '原位敲除：关掉成员 9473ea7a 自己的 暴跌抄底 模块（register_strategy(SID_S1, …, enabled=False)）',
  hypothesis: '暴跌抄底 是一条独立的第三条边，而非装饰。证伪：|Δ| < 0.15 ⇒ 装饰，不提新 edge；Δ ≤ −0.40 ⇒ 挣得 `edge: 暴跌反转 (proposed)`。',
  why: '本族只有一条站得住的边（动量 已 refuted），epoch 8 的 improve 加总上界已随 epoch 9 作废，所以家族需要新机制材料。该模块在**暴跌时买入**，而 趋势择时 在暴跌时**离场** —— 它是分散化材料而不是同一件事的第二种实现，这是它比任何旋钮都值钱的地方。原位敲除用成员自带的 enabled 开关，对照 = 其账本行 1.3357 / sharpe 5.23 / maxDD 12.93，不跑对照。',
  design: '父本成员 9473ea7a（py2to3 + OVERRIDE），单处 `enabled=False`，--window train。rider：S1 触发日数、S1 持满全书的天数。\n⚠ 先执行 obs-7c2e9238 立下的 close-fork 纪律（免费）：与 base 的 Jaccard + 旋钮逐字比对 + `^def` 差集。若 9473ea7a 的调参面与某个既有成员逐字相同，这个 Δ 可能已经由别人付费测过，则登记而非回购。\n⚠ |Δ| < 0.15 的「装饰」带落在按水平缩放后的 ~0.11–0.14 噪声估计之内，所以**空读数不可由 Δ 定案**，必须由 rider 的触发日普查承担。',
  from: ['obs-7c2e9238', 'ledger:9473ea7a@e9 obj 1.3357 sharpe 5.23', 'q-e8-2', 'family-page:edge 动量 refuted'],
  note: '本轮不资助（第 5 顺位）。**非重开**：obs-7c2e9238 的「不开新方向」是建立在 epoch-8 的加总上界 0.4621<0.4848 之上，该算术已随 epoch 9 全表作废；§4 的 15 条关闭无一覆盖 暴跌抄底。edgeRef 为 null 是正确的 —— 它提出一条新边而不是改进一条旧边。下一轮最强的**新机制**候选。',
});

// ── rank 8 — queued, NOT funded ─────────────────────────────────────────────
E.push({
  id: 'q-e9-floor', kind: 'understand', rank: 8, status: 'queued', edgeRef: null,
  title: '执行分钟噪声地板在 epoch-9 台上重测：13:10 → 13:12（三条 run_daily 同移）',
  hypothesis: '地板随水平按比例缩放。旧读数 0.0308 处于水平 0.3755 = **8.2% of level**；epoch-9 水平 1.7479 高 4.6× ⇒ 预期 ≈0.14。证伪（双向）：|Δ| < 0.05 ⇒ 不随水平缩放、地板是绝对量，旧的 0.031 可继续直接使用；|Δ| > 0.30 ⇒ 超比例放大，只有 0.3 以上的效应在本族可读，这会让本族大部分 Δ 式工作退休。0.05–0.30 之间与比例缩放一致。',
  why: '两位 generator 独立标出它。§4 把 0.031 的适用范围明确限定为「一个扰动幅度、一对分钟、一个窗口（TRAIN 2022–23）、一次测量、一张零滑点台」—— epoch 9 换掉了其中的「窗口」，所以这个误差棒现在无主，而本页的头条写法（≈0.375 ± 0.03）与「0.01–0.03 纯 Δ 不值得资助」的设计规则都挂在它上面。',
  design: '父本 生书 17b3b439 + OVERRIDE，对照 1.7479，编辑 = q-e8-2 的同一处（afternoon/sell/buy 三条 run_daily 由 13:10 同移 13:12），--window train。',
  from: ['q-e8-2', 'obs-7c2e9238', 'harness:epoch9 train 2024 only', 'ledger:17b3b439@e9 1.7479'],
  note: '⚠ **这条坐在一条已关闭的轴上，必须带着理由入队**：obs-7c2e9238 关闭了「成交时点 / 入场择时」**整条轴**，重开条件是给出一个与「延后只发生在下跌日」不同的机制论证。本条满足该条件但方式特殊 —— 它不是在该轴上求收益的提案，而是一次**误差棒标定**，预测的是**无方向性效应**（有方向才是意外），且 q-e8-2 自己的范围声明把窗口列为限制项。generator A 的逐方向表没有标出这条冲突。\n**本轮不资助**，理由是它交付不了最需要它的那个读数：本条测的是**生书 17b3b439 在 2024 的**分钟地板，而 imp-e9-1 的父本是**冠军**（两腿、不同成交笔数、水平 1.97）—— §4 明说这个数不是通用 σ，所以一个 base 上的 0.14 不授权解读冠军上的 0.17。imp-e9-1 因此无论如何都要靠它预注册的 census 定案，而另外三条资助项的预估效应是任何合理地板的 4–35×。先跑地板会花掉一次回测而仍留下同一个判据。',
});

// ── rank 9 — queued, NOT funded, hand-off flagged ───────────────────────────
E.push({
  id: 'imp-e9-2', kind: 'improve', rank: 9, status: 'queued', edgeRef: null,
  title: '恢复作者自己的短窗配置：portfolio_value_proportion [0.5,0,0.5,0] → [0.4,0.2,0.4,0]',
  hypothesis: '被归零的 ETF反弹 袖子在 epoch-9 的 TRAIN 上可用并加分。L87 是 `[0.5,0,0.5,0] #(用于长回测)`，L86 是作者预写的 `[0.4,0.2,0.4,0] #(实盘/短回测)`；该袖子被归零只因它需要 2023-09 才上市的 中证2000ETF 而作者的回测跨 11 年 —— epoch 9 的 TRAIN 完全晚于该上市日，产生 1.9437 的那条约束不再适用。证伪：Δobj ≤ 0。',
  why: '这是作者本人写下的两套配置之一，不是我们发明的旋钮点；而使它失效的那个理由（上市日）已被 epoch 9 的窗口移动消掉。',
  design: '父本 q-e9-pit_bf30eb36.py，单行，--window train。⚠ builder 必须断言 **L3555** 的重复赋值不可达或同步编辑，否则变体静默跑父本配置并报假性 Δ≈0。',
  from: ['member:bf30eb36 L86/L87 作者双配置', 'harness:epoch9 train 2024 晚于 中证2000ETF 2023-09 上市', 'orchestrator-verified:q-e9-pit_bf30eb36 obj 1.9658'],
  note: '**本轮不资助，且按现状它不是一个条目而是两个。** 三条理由：(1) **off-mechanism**，generator B 自己声明 edgeRef 无 —— 本族已有 measured edge，无 edgeRef 的 improve 默认离机制。(2) **它正是 generator B 自己拒掉的那个权重扫描上的一个点**（「第 15 个旋钮、在一年窗上搜索要持多少别族的边」）；作者把这行写下来并不使三个权重同时变动变得可归因。(3) 违反 one-experiment：[0.4,0.2,0.4,0] 同时改三个权重，正号无法在「ETF反弹 袖子有贡献」与「降低 小市值/五福 权重有利」之间归因；要可读须配一次 `[0.4,0,0.4,0]`（0.2 资本闲置，即 q-e9-leg 的资本隔离手法）作对照 —— 即两次回测，须拆成两条。\n⚠ **交接标记（generator B 已自陈，我同意）**：若它取胜，产物是一本 40% 五福 的 三马 血统书、其增益来自一条 中证2000 反弹袖子 —— 本族不应主张它。拆分重提时应连同归属一起由 orchestrator 决定它属于 三马 / 一条新的组合血统还是本族。',
});

// ── dropped, with the reason recorded so they are not re-proposed ───────────
E.push({
  id: 'q-e9-hold3', kind: 'understand', rank: 99, status: 'dropped', edgeRef: '动量',
  title: '正常期持仓数 1→3 在 epoch-9 台上重测',
  hypothesis: '（未提供预注册证伪项）',
  why: 'generator A 列出但未排名。',
  design: '（未指定）',
  from: ['idea-imp-5', 'generator-A unranked'],
  note: '**DROPPED，两条独立理由。** (1) 重开 idea-imp-5 的关闭，而那条关闭是**机制论证**不是幅度论证：「本族的收益形态是少数标的的大幅上涨，等权摊薄直接削掉它，且回撤换不回来」—— 要重提必须先给出一个不同的机制论证（照 obs-7c2e9238 为成交时点轴立下的同一标准），仅凭「窗口换了所以幅度要重测」不够。(2) 未提供证伪项 —— 无 test 不入队。\n⚠ 连带采纳 generator A 对我方 briefing 的更正：新成员 **091e1822 不能**回答持仓数问题（对 base 的 Jaccard 0.196、v4.1 血统、holdings_num=2，另带 ATR 止损与秒级成交），它的 0.3375 是 bundled 且不可归因 —— 所以「有成员已经免费答了」这条路也不存在。',
});

E.push({
  id: 'q-e9-3state', kind: 'understand', rank: 99, status: 'dropped', edgeRef: null,
  title: '折叠成员 a722ab8a 的三状态分支层',
  hypothesis: '（未提供预注册证伪项）',
  why: 'generator A 列出但未排名；a722ab8a 是点时检验里**没有**损失的那本纯 ETF 书（−1.1%），所以它的三状态层是一个未归因的差异。',
  design: '（未指定）',
  from: ['generator-A unranked', 'q-e9-pit-r2'],
  note: '**DROPPED 为缺少证伪项**（无 test 不入队），非方向否决 —— 该方向未被 §4 的任何一条关闭。重提时须带：预注册的 Δ 判据、一个远超按水平缩放后 ~0.14 的效应预估**或**一条结构性/普查式定案路径（q-e8-2 的设计规则），以及先做 obs-7c2e9238 的 close-fork 免费 diff（旋钮比对 + 函数集差集 + Jaccard）—— 若 a722ab8a 的调参面与 base 逐字相同，这个 Δ 可能已经在账本里。',
});

for (const e of E) { const r = rq.add(F, e); console.log(`${r.status.toUpperCase().padEnd(8)} rank ${String(r.rank).padEnd(3)} ${r.kind.padEnd(10)} ${r.id}`); }
