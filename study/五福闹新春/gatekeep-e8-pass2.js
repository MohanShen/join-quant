// gatekeeper pass 2 (epoch-8 round) for 五福闹新春.
// Ranks the four live entries, marks ONE active, and fixes q-e8-7's membership rule so the
// executor has no free parameter to tune. Idempotent: re-running rewrites the same fields.
const rq = require('../../utils/research-queue');
const FAM = '五福闹新春';
const q = rq.load(FAM);
const byId = id => { const e = q.find(x => x.id === id); if (!e) throw new Error('no ' + id); return e; };

// ─────────────────── q-e8-7 : rank 1, ACTIVE, design FIXED ───────────────────
const e7 = byId('q-e8-7');
e7.rank = 1;
e7.status = 'active';
e7.title = '广度配平的点时避险池：走弱期池 → base 自己那 17 只里上市早于 2022-01-01 的 9 只（N=9，跑前枚举）';

e7.hypothesis = [
  '本测一次给出两个对照，判据分开预注册，不得混读。',
  '',
  '(A) 广度对照 —— 对 q-e8-1（0.1021 / sharpe 1.04，单名池）。同一编辑点、同一编辑形状、同样绕过流动性过滤，',
  '唯一变化是池内名额数 1 → 9。若 objective ≥ 0.30，则 q-e8-1 的低读数主要由「单名池被走弱期趋势滤波滤空」解释，',
  '而不是由「那 17 个名字是事后挑的」解释。',
  '',
  '(B) 点时对照 —— 对 baseline-e6（0.3755 / sharpe 1.99 / 2022 64.11% / 2023 38.50%）。本池只含 2022-01-01 前已上市者，',
  '即一个 2021 年的作者真能写下的名单。预注册证伪：objective ≤ 0.20 ⇒ 在 9 倍广度、且用的还是 base 自己的名字的条件下，',
  '那半边（q-e6-4 的 +0.2415）仍拿不回来 ⇒ 它由窗口内/窗口后才上市的 4 只 + 2025 年的具体组合承载 ⇒',
  '§4 第一条以「事后选池」定案，不再需要逐日点时名单；趋势择时 claim 永久收窄到择时+现金的 0.1340 / sharpe 1.18（不过闸）。',
  '',
  '0.20–0.30 记 partial，不得向任一侧读；该带宽 0.10 远大于 q-e8-2 预注册的噪声地板上限 0.048，故本判据不依赖 q-e8-2，',
  '但若读数落在 0.272–0.308 或 0.172–0.208（任一阈值 ±0.048）内，须等 q-e8-2 的地板再定稿。',
  '',
  '(C) 结构判据，与 objective 无关、也与噪声地板无关：294 个走弱日里持 511880（防御货币 ETF，即当日池内零只通过滤波）的天数。',
  'q-e8-1 是 178/294（60.5%）。预注册：若 ≤ 60/294，广度确已配平，(A)(B) 两个读数均成立；',
  '若 > 150/294，广度**未**配平（9 只也几乎天天被滤空），则无论 objective 多少，(A) 判 inconclusive，',
  '且该结果本身改写 §4——瓶颈是走弱期趋势滤波而不是池子，须另开一条。',
].join('\n');

e7.design = [
  '【成员资格规则 —— 跑前固定，零自由度，执行者不得增删替换任何一只】',
  '',
  '池 = base 自己的 g.global_etf_pool（那 17 只）∩ { 上市日 < 2022-01-01 }。',
  '两个输入都是跑前可查的事实：17 只名单来自 base 源码第 25–46 行，上市日来自同几行作者自己的行内注释',
  '（上市日是证券属性，不是业绩数据）。规则不引用任何 2022–2023 的价格、收益、成交额或排名。',
  '',
  'N = 9。完整枚举（执行者按此顺序逐字写入，不排序、不去重、不补充）：',
  "  '518880.XSHG',  # 黄金ETF        上市 2013-07-29",
  "  '513100.XSHG',  # 纳指ETF        上市 2013-05-15",
  "  '513500.XSHG',  # 标普500        上市 2014-01-15",
  "  '513030.XSHG',  # 德国ETF        上市 2014-09-05",
  "  '161226.XSHE',  # 国投白银LOF    上市 2015-08-17",
  "  '501018.XSHG',  # 南方原油LOF    上市 2016-06-28",
  "  '513520.XSHG',  # 日经ETF        上市 2019-06-25",
  "  '159985.XSHE',  # 豆粕ETF华夏    上市 2019-12-05",
  "  '159980.XSHE',  # 有色ETF大成    上市 2019-12-24",
  '',
  '被排除的 8 只（上市 ≥ 2022-01-01），一只都不得放回：',
  '  513290 (2022-08-29)、513310 (2022-12-22)、159509 (2023-08-08)、159518 (2023-11-15)  ← 这 4 只在 TRAIN 窗口内上市',
  '  159502 (2024-01-10)、513400 (2024-02-02)、159529 (2024-02-02)、520830 (2024-07-16)  ← 这 4 只在 TRAIN 之后上市',
  '',
  '【为什么 N=9 而不是配平到 base 的 17 —— 这是本设计的要点，不是省事】',
  '1. 17 不是 base 在 TRAIN 上的广度。17 只里有 8 只在 2022-01-01 之后才上市：4 只整个 TRAIN 都不存在，',
  '   另 4 只在窗口中途上市。所以 base 自己的走弱池在 2022-01-04 是 9 只，到 2023-12-29 最多 13 只，',
  '   **没有任何一个 TRAIN 交易日是 17 只**。「配平到 17」是配平到一个 2025 年文件的产物。',
  '2. 补到 17 需要我在 2026 年另找 8 只 2022 年前上市的海外/商品 ETF——而我已经知道 2022–23 哪些资产涨了。',
  '   那正是本测要排除的事后选择，且是一个执行者可以调的自由度。N=9 的集合由 base 源码 + 上市日唯一确定，',
  '   没有可调之处。诚实的配平是「配平到点时真能有的广度」，不是配平到一个标称的格位数。',
  '3. 9 对 1 已经是 9 倍广度，正是 q-e8-1 留下的那个自由度；(C) 的 511880 天数会直接证明它够不够。',
  '',
  '【编辑点 —— 与 q-e6-4 / q-e8-1 同一处，同一形状】',
  'baseline-e6.py 第 277–281 行（afternoon_routine 的 if g.is_a_share_weak 分支），把',
  "  if hasattr(g,'filtered_global_pool') and g.filtered_global_pool: g.merged_etf_pool = list(set(...)) / else / .sort()",
  '这 5 行整块替换为一条字面量赋值（上面那 9 只）+ 一条 q-e8-1 原样的 WEAKHOLD 日志行。',
  '⚠ 必须和 q-e8-1 一样**绕过** g.filtered_global_pool（即不保留流动性过滤）：只有这样 q-e8-7 与 q-e8-1 才',
  '只差「名额数」一个维度，否则 (A) 的广度读数又被流动性过滤混淆——那正是 q-e8-1 的 implication 禁止的事。',
  '流动性是 q-e8-3 的题，本测刻意不碰。',
  '',
  '【不变量 —— 复用 build-e8-1.js 的断言，逐条必须通过】',
  '先由 py2to3(strategies/…17b3b439.py) + OVERRIDE 重算 baseline-e6.py 并断言字节相同；edit() 断言 FROM 只匹配 1 次；',
  'WEAKHOLD 行必须是裸 log.info（无赋值、无 sort/append/pop/del）；marker 计数不变：',
  'g.enable_r2_filter = True / weak_condition_met = (below_count >= 3) / g.max_weak_days = 20 /',
  'g.score_threshold_ratio = 0.9 / g.defensive_etf = "511880.XSHG" / _ORIG_SET_ORDER_COST。',
  '择时触发、R²/MA 滤波、走弱期候选系数 1.0、20 日上限、13:10 三条 run_daily、止损——逐字不动。',
  '清单与上面的成员资格规则须一并写进 variants/ 文件头（先写后跑）。',
  '',
  '产物 variants/q-e8-7_weak-pit9.py，build-e8-7.js 生成，--window train。',
  '',
  '【汇报 —— 缺一项即判 inconclusive】',
  'a) objective / sharpe / annual / maxDD；b) 2022 与 2023 年度 total%，并与 base(64.11/38.50)、',
  '现金 q-e6-4、黄金 q-e8-1 三本并列——2023 是诊断年（base 的那一大块在 2023，且 4 只窗口内上市者里 3 只在 2023 已活）；',
  'c) (C) 的 511880 天数 N/294，以及零通过的原因拆分（动量分 / MA10 / 两者 / 量比）；',
  'd) backtest-series 日收益相关：对 baseline-e6、对 q-e6-4 现金版、对 q-e8-1 黄金版，三个都给。',
].join('\n');

e7.from = [
  'q-e8-1 (0.1021 / sharpe 1.04；WEAKHOLD 178/294 走弱日被滤空)',
  'q-e8-1 implication: 池内名额数是未受控自由度，此后改池实验必须广度配平',
  'q-e6-4 (走弱持现金 0.1340 / sharpe 1.18，海外池腿值 +0.2415)',
  'q-e6-3 (正常期池构成已关闭，故本测只动走弱池)',
  '§4 gap 1 点时海外池（最高优先）',
  'source:baseline-e6.py L25-46 的 17 只名单 + 作者行内上市日注释（9 只 < 2022-01-01）',
];

e7.note = [
  'gatekeeper pass 2：rank 1，ACTIVE。',
  '它是四项里唯一能**定案**一条 §4 条目的测项，而且两个方向都定案：≥0.30 解除事后嫌疑，≤0.20 以事后选池结案。',
  '也是唯一挂在 edge 块上的测项——趋势择时 的 claim 目前带着「名字 vs 广度未分开（q-e8-7）」这个悬而未决的子句，',
  '一个带悬置子句的 measured claim 会被下一轮当作比它该有的更不确定的先验来引用。',
  '⚠ 它**不是** q-e8-1 的重跑：唯一变化是把名额数这个自由度配平，而那正是 q-e8-1 读不出的维度；',
  'q-e8-1 的 implication 本身就是开出本测的那句话。也**不是** q-e6-3 的重开（那条关闭的是正常期池构成）。',
  '⚠ 它仍不解决真正的点时问题（逐日按当日流动性生成名单），只把「事后选名字」压到「用跑前规则选的名字」+「点时可得」。',
].join('\n');

// ─────────────────── q-e8-2 : rank 2 ───────────────────
const e2 = byId('q-e8-2');
e2.rank = 2;
e2.note = [
  'gatekeeper pass 2：rank 2（从 pass 1 的 rank 2 保留，但理由改了）。',
  '保留在 q-e8-7 之后，不是因为它不重要——它是唯一一个结果会改写其它 14 条 finding 读法的测项——',
  '而是因为它的下游用户只有 q-e8-3（±0.02 判据，0.02 < 0.048，依赖很紧），不是 q-e8-7（判据带宽 0.10，远大于 0.048）。',
  '一旦它判出地板，§2 表须整体标注，且 q-e8-3 的 Δ 一侧才可读；若地板 > 0.048，q-e8-5 转 dropped（见其 note）。',
  '⚠ 预注册方向纪律：13:12 若更好，那是脆弱性发现，不是改进，不得采纳、不得带去 VAL。',
].join('\n');

// ─────────────────── q-e8-3 : rank 3 ───────────────────
const e3 = byId('q-e8-3');
e3.rank = 3;
const PASS2_E3 = 'gatekeeper pass 2：rank 3 保留，并下调紧迫性（不是价值）。';
if (!e3.note.includes(PASS2_E3)) {
  e3.note += '\n\n' + [
    PASS2_E3 + '核查了整合闸：本族读 BLOCKED / owner: none，',
    '因为 valDeclined: 8 —— 所以 realizability 这个数字**今天解不开任何闸**，它要等「不被成员 73b13d92（0.4848）支配的',
    '自建候选」出现才会被索取。它仍是一个该拿的耐久事实（闸迟早要它，且按 liq-1 判例不可从源码猜），',
    '但它排在 q-e8-2 之后的理由不变且是硬的：本测 ±0.02 的判据 < q-e8-2 预注册的地板上限 0.048。',
    '⚠ 派发时须讲清：若 q-e8-2 判出地板 > 0.048，本测的 Δ 一侧作废，R=2 只能靠 LIQFLOOR 日志的 in==out 来挣。',
  ].join('\n');
}

// ─────────────────── q-e8-5 : rank 4, conditional ───────────────────
byId('q-e8-5').rank = 4;

const bad = q.flatMap(e => rq.validate(e).map(b => `${e.id}: ${b}`));
if (bad.length) throw new Error('validate failed: ' + bad.join('; '));
const actives = q.filter(e => e.status === 'active');
if (actives.length !== 1) throw new Error('expected exactly 1 active, got ' + actives.length);
rq.save(FAM, q);
console.log('saved. active =', actives[0].id);
console.log(q.filter(e => ['queued', 'active'].includes(e.status))
  .sort((a, b) => a.rank - b.rank)
  .map(e => `  rank ${e.rank}  ${e.status.toUpperCase().padEnd(7)} ${e.id}  ${e.title}`).join('\n'));
