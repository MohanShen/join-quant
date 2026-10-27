// One-off recorder for q-e9-corr-resid / q-e9-month / q-e9-pool. DELETE after running.
const rq = require('/Users/mshen/join-quant/utils/research-queue');
const FAM = '多因子ML';

const before = rq.load(FAM).find(e => e.id === 'q-e9-pit');
console.log('q-e9-pit status BEFORE:', before && before.status);

// ── new ideas these findings produced (grounded: `from` names the result) ──
const ideas = [
  {
    id: 'q-e9-corr-resid2',
    kind: 'understand',
    title: '零回测：双残差 ρ——同时控制 benchmark 与一条 ETF 动量参照，看 小市值 侧的结构性重叠是否独立存活',
    hypothesis: 'q-e9-corr-resid 测得 base 在 benchmark 残差尺度上对 ETF 侧（0aa4028d 0.5952 / 对 ETF+白马半书 0.7092）与 小市值 侧（5a70adc1 0.6416 / 对合成微盘腿 0.6653）都有结构性连接。若把 0aa4028d 一并作为回归量，小市值 侧的残差 ρ 仍显著（> 人口 p75 0.4284），则 base 是真三腿混合、两侧重叠互不替代；若 小市值 侧塌到人口中位以下，则本族的「结构性重叠」其实只是一条共同的组合书因子。',
    why: '这是 §4「家族归属 / 改名」空白唯一还能用相关性回答的半边：q-e9-corr 的原始 ρ 带已作废，q-e9-corr-resid 换成了单残差尺度，但单残差不能区分「两侧各自独立重叠」与「两侧共享同一条非 benchmark 因子」。零回测、只读已存曲线。',
    design: '对 base / 5a70adc1 / 0aa4028d / q-e9-1 变体 / 合成腿 d(t) 的链式日收益做二元 OLS（regressor = benchCum 链式收益 + 0aa4028d 残差），取残差后重算两两 ρ；对称地反向控制（以 5a70adc1 为第二回归量看 ETF 侧）。全库 281 条 e9 曲线给同一尺度的人口分布。先注册证伪项：小市值 侧双残差 ρ < 0.4284（人口 p75）即判「共享因子」。⚠ 不写 data/series、不建变体、不碰 variants/（并行 PIT 执行器持有）。',
    from: ['q-e9-corr-resid'],
    edgeRef: '规模因子',
    rank: 35,
  },
  {
    id: 'q-e9-jan',
    kind: 'understand',
    title: 'log.info 探针：2024 年 1 月 small_cap 腿到底持有什么——日历规则（整仓 600036）还是空仓/被过滤',
    hypothesis: 'q-e9-month 测得 sleeve 的累计贡献整个 1 月只有 +0.03..+0.34pp，而纯 小市值 参照 5a70adc1 在 02-07 已累计 −9.81%；贡献在 02-06 突然跳 +1.69pp。先验候选解释是 q-3 记录的 1/4 月日历规则：small_cap 在 1 月与 4 月整仓切 600036 招商银行。若日志证实 1 月持仓是 600036（或空仓），则「这条腿在崩盘期做了择时」被证伪，1 月的平坦是一条 n=2 的日历规则。',
    why: 'q-e9-month 的唯一真例外就是 1 月，而曲线在原理上读不出「持了微盘但躲过了」与「根本没持微盘」的区别——这需要日志，不是曲线。它同时决定 q-e9-1 读数 (1)（「1 月的强势从来不是这条腿给的」）该怎么改写，以及 q-e9-3（pass_april）是否从回撤保护复测升级为这条日历规则的直接判据。',
    design: '在 base 的 small_cap 调仓点加 log.info（持仓代码 + 市值 + 当日权重），只跑 2024-01-01..2024-02-29 子窗，读 /algorithm/backtest/log。零策略逻辑改动、零自由参数。⚠ 变体文件不得写进 study/多因子ML/variants/（并行 PIT 执行器持有该目录），另起文件名或等其交还。',
    from: ['q-e9-month'],
    edgeRef: '规模因子',
    rank: 40,
  },
  {
    id: 'q-e9-pool-sel',
    kind: 'understand',
    title: 'etf 池的 selection 级事后性（listing 级已被 q-e9-pool 排除）——把手写 14 只池换成规则化池',
    hypothesis: 'q-e9-pool 测得池里只有 1 只（159525, 2024-05-20）在 TRAIN 开始后上市、0 只在 VAL 2025 上市，所以 listing-availability 这半边的事后性量级很小。但池本身是 2026 年手写的，selection 级事后性（知道 2024–25 哪些资产涨了才把它们写进池）完全未测。参照 [[ETF动量]]：换成宽基 A 股池后同族结果到 −0.27，而 [[小市值]] 的混合书换 point-in-time 池只动 +0.0015 —— 所以本书属于哪一类是未知的，不是可推的。',
    why: 'q-audit Finding A / q-e6-2 把「etf 池为 2026 年事后组装」列为 realism 四条腿之一，也是 valDeclinedPrior 的理由之一。q-e9-pool 只关掉了其中 listing 的半边；selection 半边仍是本族 realism 里最大的一块未测项，且它决定 VAL 候选的论证能不能站住。',
    design: '⚠ 替代池的构造规则必须由 generator 设计并预注册，不得由记录者指定——这是一个设计决定（候选方向：同类资产的宽基全集按同一动量排序；或按 2023-12-31 可得的规模/成交额门槛机械筛出 N 只）。规则一旦写定：排序逻辑、动量窗、择时、阈值、成本块逐字不动，只换池；预注册证伪项（例如 objective 掉到闸门 1.0 以下即判「池就是 edge」）。约 1 次 TRAIN 回测。',
    from: ['q-e9-pool'],
    edgeRef: '动量',
    rank: 45,
  },
];

for (const i of ideas) {
  const existing = rq.load(FAM).find(e => e.id === i.id);
  if (existing) { console.log('idea already present, skipped:', i.id); continue; }
  rq.add(FAM, i);
  console.log('idea added:', i.id);
}

// ── A ──────────────────────────────────────────────────────────────────────
rq.recordFinding(FAM, {
  qId: 'q-e9-corr-resid',
  type: 'probe',
  component_or_param: '零回测、0 回测分钟：以 base 自己记录里的 benchmark 累计曲线（000300.XSHG，链式后作回归量）对双边日收益做 OLS 取残差，再重算 ρ；同一回归量施于全库 281 条已存 __train__e9 曲线以给出人口分布；并用 q-e9-1 的消融变体（ETF+white_horse-only）与合成微盘腿 d(t)=r_base−r_var 做三方残差分解。helper study/多因子ML/resid-e9.js / resid-sub-e9.js / resid-ablate-e9.js / resid-sweep-e9.js 只读，不写 data/series、不写账本、不建变体、不碰 variants/',
  metric_delta: 'betaBase 0.8889 / R2 0.4101（base 日方差的 41% 是 CSI300）。三元组（原始 ρ / 残差 ρ / peer beta）：d5040aa0 0.9014/0.8441/0.8726；8d6831d4(小市值) 0.7524/0.6465/0.8264；9f6f8188(小市值) 0.7512/0.6187/0.6468；1c80dd9a(小市值) 0.7423/0.6414/0.7592；7301c5c4(七星高照) 0.7340/0.5902/0.6434；5a70adc1(小市值) 0.7092/0.6416/0.8302；0aa4028d(ETF动量) 0.7060/0.5952/0.8448；bba95a11(小市值) 0.6244/0.5105/0.5514。人口（同一回归量，281 条）：残差 ρ med 0.3115 / p75 0.4284 / p95 0.5902（原始 med 0.5019 / p95 0.7092）。控制：aa9678cd（红利低频，原始 ρ 0.5019 ＝ 人口中位）残差化后 −0.0117。n=241 时 ρ 0.5105 的 t=9.16。衰减比一致为 0.80–0.94。腿分解（残差 ρ 对 base / 对变体 / 对合成腿）：0aa4028d 0.5952/0.7092/0.1228；5a70adc1 0.6416/0.3878/0.6653；9f6f8188 0.6187/0.4406/0.5492；d5040aa0 0.8441/0.6520/0.6752；bba95a11 0.5105/0.4080/0.3883；8d6831d4 0.6465/0.5444/0.4528；1c80dd9a 0.6414/0.5248/0.4703。去 9+10 月（残差尺度）：5a70adc1 0.6414→0.6928（升）、0aa4028d 0.5961→0.5167、其对变体 0.7092→0.6052（仍高于人口 p75 0.4284）、d5040aa0 0.8441→0.8169。合成腿对 CSI300 的 beta 仅 0.2504，日波动 0.830% vs base 1.869%。回测次数 0',
  window: 'TRAIN 2024-01-01→2024-12-31（epoch 9）；base 曲线 242 点 2024-01-02..2024-12-31，残差 ρ 用 n=241 日收益，所有配对重叠均为全长；另有去 2024 年 9+10 月的子样本',
  finding: 'q-e9-corr 的「ETF 侧是共享 9/10 月 beta、小市值 侧才是结构性的」被证伪。把双边都对 base 自己的 benchmark（000300.XSHG，betaBase 0.8889 / R2 0.4101）残差化之后，八个最高 peer 的残差 ρ 全部仍在 0.51 以上，预注册证伪项（全部塌到 0.2 以下）未触发：d5040aa0 0.8441、8d6831d4 0.6465、1c80dd9a 0.6414、5a70adc1 0.6416、9f6f8188 0.6187、0aa4028d 0.5952、7301c5c4 0.5902、bba95a11 0.5105。衰减比一致为 0.80–0.94，排名只在中段换位（5a70adc1 6→3、9f6f8188 3→5、7301c5c4 5→7），即重排来自各 peer 不同的 beta，而不是某一个特殊 peer。残差尺度本身由人口与一个控制读数定标：281 条 e9 曲线的残差 ρ med 0.3115 / p75 0.4284 / p95 0.5902，而原始 ρ 恰为人口中位（0.5019）的 aa9678cd 残差化后是 −0.0117 —— 一个中位的原始 ρ 完全是 benchmark beta，所以旧的 0.5–0.8 原始带确实大部分是 beta，而上面八条全部越过人口 p95 附近。腿分解是主结果：对消融变体（ETF+white_horse-only）与合成微盘腿 d(t)=r_base−r_var 分别算残差 ρ，0aa4028d（ETF动量）对变体 0.7092 / 对合成腿仅 0.1228，5a70adc1（纯 小市值）对合成腿 0.6653 / 对变体 0.3878 —— 两条腿各自对上各自家族，交叉项低，所以 base 是一本真三腿混合书、两侧都有结构性重叠。再去掉 2024 年 9+10 月：小市值 侧持平到反升（5a70adc1 0.6414→0.6928），ETF 侧只从 0.5961 降到 0.5167、对半书 0.7092→0.6052，仍高于人口 p75 —— 即 ETF 侧的重叠在无 benchmark、无 9/10 月的尺度上依然是全库最强的连接。合成腿对 CSI300 的 beta 只有 0.2504（日波动 0.830% vs base 1.869%），所以微盘腿本身几乎不是市场暴露。附：bba95a11 声明的 benchmark 是 510300.XSHG 而非别处的 000300.XSHG，两条已存 bench 曲线相关 0.9858，且双边统一用 base 的曲线残差化，处理一致',
  confidence: 'high（残差 ρ 读数、241 天全重叠、人口分布与 aa9678cd 控制、以及「证伪项未触发」这一判定）/ med（「结构性 vs beta」的归因与单年单窗；合成腿 d(t) 是两条曲线相减得到的综合量，不是一次独立回测）',
  flags: 'probe-零回测 / ⚠零滑点高估 / regime-specific（单年 TRAIN 2024）/ supersedes-q-e9-corr（撤回其「归属 ETF动量」的关闭理由）/ benchmark-yardstick-void（0.6388 这把尺子在残差尺度上不存在：benchmark 对自己的残差恒为 0）/ raw-rho-is-mostly-beta（人口中位原始 ρ 0.5019 残差化为 −0.0117）/ correlation-is-not-attribution（残差 ρ 仍只证共动，不证收益来自哪条腿）/ synthetic-sleeve-derived（合成腿由相减得到，含两书的一切共同实现细节）/ hypothesis-survived（预注册证伪项未触发，八条全 >0.51）/ method-validated（链式日收益；benchCum 同样先链式后回归）',
  description: '口径纪律：回归量取 base 记录自带的 benchCum 并按 (1+c_t/100)/(1+c_{t-1}/100)−1 链式，与双边日收益同一构造；残差 ρ 一律在 n=241 上算，不做任何子集挑选（去 9/10 月的子样本单独报，不替代全样本）。人口分布与控制读数用同一回归量，否则残差 ρ 没有可比尺度。bba95a11 的 benchmark 声明不同（510300.XSHG，与 base 的 000300.XSHG 相关 0.9858），双边统一用 base 的曲线，故处理一致、不是逐书各自残差化',
  implication: '(1) 撤回 q-e9-corr implication 第 (2) 条：「归属 ETF动量」这条方向按它记录的理由 VOID。残差化且去 9/10 月之后 ETF peer 对 base 仍 0.5167、对 ETF+白马半书 0.6052（人口 p75 为 0.4284），是本台上找到的最强的无 benchmark 连接 —— 所以「ETF 侧只是共享的 9/10 月 beta」不成立。该方向若要继续关闭必须换成新理由（base 是真三腿混合，两侧都有结构性重叠，加任一侧权重都是在做别族的副本），§4 那条 bullet 必须就地改并标注本 qId；任何人不得再引用「ETF 侧与 benchmark 同步塌」这句话。(2) 解除 q-e9-corr 对 ρ 的禁令，并换掉尺子：§4「家族归属 / 改名」此后可以用残差 ρ 作证据，判据是人口残差分布（med 0.3115 / p75 0.4284 / p95 0.5902），而 0.6388 这把 benchmark 尺子从此作废（benchmark 对自己残差恒为 0，该数在残差尺度上不存在）；控制读数 aa9678cd −0.0117 是必须一并引用的那半句，否则读者会以为旧的 0.5–0.8 带还有意义。(3) d5040aa0 残差化后仍 0.8441（去 9/10 月 0.8169，两条腿都 ≥0.65），所以 q-e9-corr 第 (3) 条「若 assign 把它归入本族，它不建任何变体就直接以 1.5967 取代 base 1.4731」不仅存活而且加强；仍然只是记录，是 assign/人工的决定，本循环不得据此改写 improve 方向。(4) 新开 q-e9-corr-resid2（零回测双残差：同时控制 benchmark 与一条 ETF 动量参照），因为单残差分不出「两侧各自独立重叠」与「两侧共享同一条组合书因子」；在它出结果之前 §4 归属空白只许写「两侧都结构性重叠」，不许写哪一侧更该拿走这本书。(5) 明确不开的：残差 ρ 仍然不是 attribution，0.6653 这种数不得用来替代消融 —— 本族 2024 的 1.4731 里各腿占多少，判据仍只有 q-e9-2 / q-e9-4，它们的排序不变（仍在任何 improve 之前）。(6) 两条 edge 的 status 都不动：本测没跑 规模因子 或 动量 任一条声明的 test:',
  spawned: 'q-e9-corr-resid2',
  edgeRef: '规模因子',
});
console.log('recorded q-e9-corr-resid');

// ── B ──────────────────────────────────────────────────────────────────────
rq.recordFinding(FAM, {
  qId: 'q-e9-month',
  type: 'regime',
  component_or_param: '零回测、0 回测分钟：用两条已存曲线（base d02cde29 与 q-e9-1 的 small_cap=0 变体）按月分解 c_sleeve(m)=base(m)−variant(m)，2024 全 12 个月；并用纯 小市值 参照 5a70adc1 的月度收益做仲裁（同月 ρ、前月 ρ、符号一致性）。helper study/多因子ML/month-e9.js / month-context-e9.js 只读',
  metric_delta: 'c_sleeve(m)（pp，括号内为占 base 当月的比例）：1 月 +0.37（5%）、2 月 +10.05（89%）、3 月 +4.04（45%）、4 月 −0.20、5 月 −1.36、6 月 −4.46、7 月 +9.10（99%）、8 月 +1.70、9 月 +8.07（31%）、10 月 +16.30（65%）、11 月 +7.97（94%）、12 月 +1.89。加和 +53.48pp，Σ|c| 65.52pp，复利年度差 97.30pp（含首日 97.76pp ＝ q-e9-1 头条，可对账）。集中度：最大月 10 月占 Σ|c| 的 24.9%（第一项门槛 25% 差 0.1pp）、符号 9 正 3 负、HHI 0.1451（均匀为 0.0833）、top-3 占 54.1%、五个月各 ≥ +7.9pp（2 月 10.05 / 7 月 9.10 / 9 月 8.07 / 10 月 16.30 / 11 月 7.97）；2 月只占 15.3%。仲裁：ρ(c_sleeve, 同月 5a70adc1) 0.8422、符号一致 11/12 月；ρ 对前月参照 +0.3354；ρ 对同月 benchmark 0.3149。1 月细节：sleeve 累计差整个 1 月与 02-05 之前都在 +0.03..+0.34pp，02-06 单日跳 +1.69pp 后开始爬升，而 5a70adc1 在 02-07 已累计 −9.81%。方法核对：曲线算 base maxDD 9.40 ＝ 账本单元格、变体 7.14 vs 抓取 7.13、复利 156.71% / 58.95% 均对账、链式年化波动 0.2961（差分会给 0.5349）、重叠 242/242（去首日 241）、两种口径下 ρ 差 ≤0.001、月度差 ≤0.03pp。回测次数 0',
  window: 'TRAIN 2024-01-01→2024-12-31（epoch 9），逐月 12 个子区间；1 月例外段细看到 2024-02-07',
  finding: 'q-e9-1 的「崩盘后反弹收割者」读法在年度尺度上被证伪，而它附带的那条脆弱性主张被解体。预注册证伪项（最大月 < Σ|c| 的 25% 且符号大致均衡）只在第一个子句上差 0.1pp 未触发（10 月 24.9%），第二个子句明确不成立（9 正 3 负），但真正的读数在分布形状上：主导月是 10 月（+16.30pp）而不是 2 月，2 月只占 Σ|c| 的 15.3%，并且有五个月各贡献 ≥ +7.9pp（2 月 10.05 / 7 月 9.10 / 9 月 8.07 / 10 月 16.30 / 11 月 7.97），HHI 0.1451 对均匀的 0.0833、top-3 占 54.1% —— 集中但远不是单点。仲裁读数把机制直接定到 size：c_sleeve 与一本纯 小市值 参照（5a70adc1）的同月收益相关 0.8422、符号 11/12 月一致，而对「前一个月」的参照只有 +0.3354（反弹读法预测这一项应当大且为负）、对同月 benchmark 只有 0.3149 —— 所以这条腿赚的是当月的小盘 beta，不是上个月跌出来的反弹。唯一真例外是 1 月，而且只有 1 月：sleeve 的累计贡献在整个 1 月与 02-05 之前都只有 +0.03..+0.34pp，02-06 单日跳 +1.69pp 后才开始爬升，而参照小盘书在 02-07 已经累计 −9.81% —— 即这条腿在崩盘全程几乎没有小盘暴露，并在接近底部处才打开。曲线在原理上读不出这是一条择时过滤还是这条腿当月根本没被填仓，那需要 log.info，也就是一次回测。方法全部交叉核对通过：曲线算出的 base maxDD 9.40 与账本单元格完全一致、变体 7.14 对抓取 7.13、两边复利 156.71% / 58.95% 均对账、加和 +53.48pp 与复利年度差 97.30pp 的差距正是加和与复利的区别（含首日 97.76pp 即 q-e9-1 头条），链式年化波动 0.2961（若差分累计百分比会给 0.5349，1.8× 错）',
  confidence: 'high（逐月 c_sleeve、集中度统计、与 5a70adc1 的同月/前月仲裁、以及全部曲线对账）/ med（n=12 个月的单年单窗；1 月例外的机制归因 —— 择时过滤 vs 未填仓 —— 曲线读不出，待日志）',
  flags: 'probe-零回测 / ⚠零滑点高估 / regime-specific（单年 TRAIN 2024，n=1 次崩盘）/ supersedes-q-e9-1-mechanism（撤回「崩盘后反弹收割者」，回到 size/小盘 beta）/ fragility-claim-dissolved（「唯一 measured edge 挂在一次 2 月反弹上」被证伪：2 月 15.3%，五个月各 ≥7.9pp）/ falsifier-A-差-0.1pp（10 月 24.9% vs 门槛 25%）/ additive-vs-compounded（加和 53.48pp 与复利 97.30pp 不同量纲，不得混用）/ january-exception-unresolved（需 log.info，曲线读不出）/ synthetic-sleeve-derived（c_sleeve 由两条曲线相减，含 idle-cash 与 bundled-machinery 两个已记混淆）/ method-validated（maxDD / 复利 / 链式波动三项对账，口径差 ≤0.03pp）',
  description: '口径纪律：dailyReturns 先对整条 cum 链式、再按日期切月（先切后转会把之前所有年的累计涨幅折进切片首日，这是本仓库记过的错误）；加和口径（Σc 53.48pp）与复利口径（年度差 97.30pp）分开报，绝不互相替代；含/不含首个交易日两种口径都算过，ρ 差 ≤0.001、月度差 ≤0.03pp，故结论不依赖口径选择。c_sleeve 是合成量：它等于「在固定 0.35 权重下这条腿相对一本把 35% 闲置的两腿书」的差，仍带 q-e9-1 已记的 idle-cash 与 bundled-machinery 两个混淆，不是这条腿独立的赚钱能力',
  implication: '(1) 撤回 q-e9-1 的机制改写：规模因子 的读法从「崩盘后反弹收割者」退回「size / 小盘 beta」，frontmatter edge.claim 与 evidence 里 epoch-9 那半句的措辞必须相应改掉（同月 ρ 0.8422、符号 11/12，而前月 ρ 只有 0.3354 —— 反弹读法预测的那一项反而最弱）。本条只改措辞，不改 status：本测没跑 edge 声明的 test:，measured 维持。(2) 解除 q-e9-1 立下的那条前置条件：§4「本家族唯一的 measured edge 是否挂在一次 2 月反弹上」被证伪（2 月只占 Σ|c| 的 15.3%，10 月才是最大的 24.9%，五个月各 ≥7.9pp，HHI 0.1451），所以 realism 措辞与任何 VAL 候选的论证不必再等这条 —— 该 bullet 就地改并标注本 qId。(3) 新的集中度主张要按实际形状写，不要换一个单月再挂一遍：top-3 占 54.1% 是「集中但非单点」，而 9/10 月的可重复性判据仍然是 q-e9-2 / q-e9-4，本条不改它们的优先级（仍在任何 improve 之前）。(4) 开一条窄的新方向 q-e9-jan（log.info 探针，一次子窗回测）：1 月是唯一真例外，先验候选解释是 q-3 记录的 1/4 月日历规则（small_cap 在 1 月与 4 月整仓切 600036 招商银行）。若日志证实 1 月持的是 600036 或空仓，则 q-e9-1 读数 (1)「1 月的强势从来不是这条腿给的」要改写成「1 月这条腿根本不是微盘腿」，而 queued 的 q-e9-3（pass_april True→False）从「回撤保护复测」升级为这条日历规则的直接判据、排到 q-e9-idle 之前。⚠ q-e9-jan 的变体文件不得写进 study/多因子ML/variants/，该目录由并行 PIT 执行器持有。(5) 明确不开的：不得按月挑窗 —— 既不许用 10 月或 2 月的子窗挑变体、也不许用它撑 VAL（q-e6-2 的 implication 已就 2023 子窗立过同一条规矩）；也不得把 c_sleeve 的 0.8422 读成「这条腿可以换成任何一本小盘书」，那是冗余度的问题而不是本测的问题，归 q-e9-corr-resid2',
  spawned: 'q-e9-jan',
  edgeRef: '规模因子',
});
console.log('recorded q-e9-month');

// ── C ──────────────────────────────────────────────────────────────────────
rq.recordFinding(FAM, {
  qId: 'q-e9-pool',
  type: 'probe',
  component_or_param: '一次零下单探针 study/_probes/probe-e9-pool-listdates.py（不建变体、不改策略逻辑、不下单）：读 base 两个池（etf_pool 14 + foreign_etfs 4，去重 17 只）的上市日期，三条互证通道 —— initialize 里（在 OVERRIDE 的 pin 生效前）的 get_security_info、get_all_securities(date=2025-12-31 / 2026-10-20)、以及逐日 membership',
  metric_delta: 'SUMMARY train 2024-01-02 2024-01-05 3 / 0.00 0.00 0.00 0.00 / no-trades（1 次回测 21s，no-trades ＝ 不下单探针的预期终态；used 4→5 of 180）。17 只代码全部解析、0 只未解析，三条通道一致（get_all_securities 两个日期都 17/17）。控制：语料里 10 条作者自注日期全部逐字重现，0 处不一致。先前无日期的六只：159525 2024-05-20、159628 2022-07-18、159652 2023-02-08、511090 2023-06-13、159934 2013-12-16、515180 2019-12-20。其余：513100 2013-05-15、513130 2021-06-01、159915 2011-12-09、588120 2023-09-15、513520 2019-06-25、513030 2014-09-05、518880 2013-07-29、161226 2015-08-17、159985 2019-12-05、501018 2016-06-28、600036 2002-04-09。无退市（end_date 全为 2200-01-01）。答案：TRAIN 开始后上市的恰好 1 只（159525，2024-05-20，窗内约 4.5 个月，前约 92 个交易日不可交易）；VAL 2025 窗内上市 0 只，两池最晚上市日期是 2024-05-20',
  window: '探针自身跑 TRAIN 子窗 2024-01-02..2024-01-05（3 天，只为取得一个 JQ 会话读属性）；被回答的问题覆盖 TRAIN 2024 全年与 VAL 2025 全年（epoch 9）',
  finding: 'base 两个 ETF 池（etf_pool 14 + foreign_etfs 4，去重 17 只 + 600036）的上市日期全部测到，三条互证通道一致，且控制读数把语料里作者自注的 10 条日期逐字重现、0 处不一致。两个答案都是单一的：(1) TRAIN 开始后上市的恰好一只 —— 159525，2024-05-20，落在窗内约 4.5 个月处，前约 92 个交易日结构上不可交易，却被一位 2026 年写稿、已知 2024 结果的作者放进了池；逐日 membership 通道独立佐证（159525 在 2024-01-02..01-05 读作 OUT，另 16 只读作 IN）。(2) VAL 2025 窗内上市 0 只，两池最晚的上市日期就是 2024-05-20。先前语料里无日期的六只现在都有了：159525 2024-05-20、159628 2022-07-18、159652 2023-02-08、511090 2023-06-13、159934 2013-12-16、515180 2019-12-20；无一只退市。由此 q-e9-pit 不是一次空编辑，而是一次定义明确的单名编辑（etf_pool 14→13，foreign_etfs 逐字不动）。⚠ 159525 同时是 q-e9-liq-1 里被成交地板剔除次数最多的成员（63 次），也是 18 次 rank-1 替换里的 8 次 —— 事后上市与不可成交这两个缺陷指向同一只名字、同向叠加，而不是互相抵消。⚠ 本测只关掉 listing-availability 这半边的事后性；池子仍是 2026 年手写的，selection 级事后性（知道 2024–25 哪些资产涨了才写进池）完全未测、未被证伪。机制旁注值得留着：在被 pin 的 avoid_future_data=True 之下，get_security_info 对尚未上市的代码返回 None，所以日期必须在 initialize 里、OVERRIDE 的包装生效之前读',
  confidence: 'high（上市日期本身：三条通道一致、10 条语料日期零分歧、逐日 membership 独立佐证；以及「VAL 窗内 0 只」这个判定）/ med（159525 窗内上市对 q-e9-pit 的 Δ 会有多大 —— 未跑，且它与成交地板的剔除同向混在一起）',
  flags: 'probe-1 分钟配额（21s no-trades 探针，used 4→5 of 180）/ no-trades-是预期终态 / hindsight-listing-half-closed（TRAIN 内上市 1 只、VAL 内 0 只）/ hindsight-selection-UNTESTED（池仍为 2026 年手写，本测不触及）/ q-e9-pit-非空编辑（etf_pool 14→13，单名）/ defects-aligned-not-offsetting（159525 既是唯一事后上市名、又是地板剔除最多的名字 63 次）/ control-validated（10 条作者自注日期逐字重现）/ three-channel-agreement / mechanism-note（avoid_future_data=True 下 get_security_info 对未上市代码返回 None，须在 initialize 读）/ edge-status-untouched（未跑 规模因子 / 动量 任一条声明的 test:）',
  description: '口径纪律：上市日期是证券属性而不是窗内表现数据，所以读它不构成用窗内信息（与 [[五福闹新春]] build-e9-pit 同一条规矩）；三条通道（initialize 内 get_security_info、两个日期的 get_all_securities、逐日 membership）互为控制，任何一条单独都不足以下结论；作者自注的 10 条日期作为控制集先跑通再信其余六条。探针不下单，故 no-trades 是预期终态而不是失败 —— 它不占 VAL/OOS 任何预算，只花 1 分钟 TRAIN 配额。⚠ 本条不碰 study/多因子ML/variants/（并行 PIT 执行器持有），也不碰任何 valDeclined* / valReopened 字段',
  implication: '(1) q-e9-pit 从「可能是一次空编辑、不值得花回测」改判为一次定义明确的单名编辑（etf_pool 14→13，去 159525；foreign_etfs 逐字不动），所以它值得跑并且结果可解释；⚠ 本条不改它在 queue 里的 status（blocked），因为该方向正由并行执行器持有 —— 解除是执行器/orchestrator 的动作，不是记录者的。(2) 报 q-e9-pit 的 Δ 时必须声明混淆，否则会把它读成纯 hindsight 的量级：159525 同时是地板剔除次数最多的名字（63 次、18 次 rank-1 替换里的 8 次），所以去掉它的 Δ 同时包含「事后上市」与「不可成交」两部分。要分离需要一个「只对 159525 加地板、其余不动」的对照，记在 §4 作为条件性空白，暂不单独开 idea（避免与并行执行器撞同一目录）。(3) VAL 的池前置条件被测量部分解除：VAL 2025 窗内上市 0 只，所以 [[五福闹新春]] 那条「VAL 前必须做 pre-2025 池截断」的阻断条件在本族不适用，valDeclinedPrior 里「ETF 池为事后组装」的理由此后只剩 selection 半边、不再含 listing-availability 半边。⚠ 这是对理由的测量，不是一次许可：本条一个 valDeclined* / valReopened 字段都不碰，花不花 VAL 仍是 orchestrator 的决定。(4) selection 级事后性仍未测、也未被证伪 → 新开 q-e9-pool-sel（把手写 14 只池换成规则化池，替代池的构造规则必须由 generator 预注册，不得由记录者指定）；在它出结果之前，realism 第 (c) 条「etf 池是 2026 年事后组装的」与 动量 的 refuted 都原样保留 —— 本测没跑 动量 声明的 test:，两条 edge 的 status 均不动。(5) 方法可复用，记下来省掉下次的试错：在被 pin 的 avoid_future_data=True 之下 get_security_info 对未上市代码返回 None，所以上市日期必须在 initialize 里、OVERRIDE 包装生效之前读；一次 no-trades 探针（21s、1 分钟配额）就能换掉一整族「池子是否事后」的猜测',
  spawned: 'q-e9-pool-sel',
  edgeRef: '动量',
});
console.log('recorded q-e9-pool');

const after = rq.load(FAM).find(e => e.id === 'q-e9-pit');
console.log('q-e9-pit status AFTER:', after && after.status);
