// Records the epoch-6 round's findings into study/PT多策略/findings.tsv (idempotent by qId).
//   node -e "require('./study/PT多策略/record.js')"
// Base anchor (baseline-e6): total 772.01 / annual 195.74 / sharpe 11.15 / maxDD 9.82 / obj 1.8592;
// per-year 2022 +300.50 (maxDD 9.82, vol 0.2253) / 2023 +121.38 (maxDD 2.69, vol 0.1181).
// Every Δ below is against it.
const rq = require('../../utils/research-queue');
const F = 'PT多策略';
const have = new Set(rq.findings(F).map(f => f.qId));
const W = 'train 2022-01-01→2023-12-31（729d / 484 交易日）';
const rows = [
  {
    qId: 'q-struct', type: 'probe',
    component_or_param: '家族成员计数：c70281d3 的 4358 行「分仓隔离插件」是否真的运行（零回测，逐行读源码）',
    metric_delta: 'Δ 不适用（零回测）。ledger 对照：c70281d3 epoch-6 行 annual 192.66 / sharpe 11.20 / maxDD 8.18 / obj 1.8448 vs fa0d3bd9 锚点 195.74 / 11.15 / 9.82 / 1.8592 ⇒ Δobj −0.014、annual −3.1pp、maxDD −1.6pp',
    window: '—',
    finding: 'c70281d3 第 143 行与第 4355 行是一对模块级 \'\'\'：其间 4,200 行（第二个 initialize、subPortfolio/subPosition/subOrder 类、「小市值策略A」、PTrade 兼容层）全部在字符串字面量里，从不执行。真正跑的是 1–142 行：与 fa0d3bd9 同一 ETF 折价 sleeve（band 5e6–2e7、premium<0、top-10、|premium| 加权），差异只有三处——09:30 的 last_price 取代 09:25 的 day_open 作信号、多一个 09:30/14:59 的 −5% 止损 / +10% 止盈、order_target_value 直下不走交易计划。ledger 上两者 obj 只差 0.014，三处差异合起来近乎惰性。家族 = 一份代码体；「四大策略并行 / 自有账本 / 分仓隔离」是标题，不是被回测的东西',
    confidence: 'high',
    flags: 'member-count-inflated · dead-code · zero-cost-probe · stub-concepts-wrong（c70281d3 桩页标了 小市值因子/打板与涨停，描述的是死代码）',
    description: 'grep 模块级三引号（143 / 1497 / 1520 / 4355 行）与 def initialize（10 / 159 行）；两份源码 1–142 行 diff 逐行核对。本行无 algorithmId',
    implication: '关闭「c70281d3 是多策略、要拆它的子策略」（pre-wipe §4 第一条）：没有子策略可拆。家族的独立证据量 = 1 份代码体、2 次归档；一切 Δ 只需对 fa0d3bd9 的锚点量。同时关闭「借 c70281d3 的止损止盈到基类」作为 improve——ledger 已经量了，−0.014',
    spawned: 'baseline-e6',
    edgeRef: '',
  },
  {
    qId: 'baseline-e6', type: 'baseline',
    component_or_param: '基类 fa0d3bd9 在 epoch 6 上的锚点（源码 + live OVERRIDE；ledger 只有 epoch 2 / 4 行）',
    metric_delta: 'vs ledger epoch-4 行：total 772.01 = 772.01 · annual 195.74 = 195.74 · sharpe 11.15 = 11.15 · maxDD 9.82 = 9.82 · obj 1.8592，逐位复现；vs epoch-2 行：annual 369.07 → 195.74（−173pp）· sharpe 18.16 → 11.15 · maxDD 9.55 → 9.82；逐年 2022 +300.50（maxDD 9.82 · vol 0.2253 · sharpe~ 6.34 · 上涨日 164/241）/ 2023 +121.38（maxDD 2.69 · vol 0.1181 · sharpe~ 6.68 · 159/242）',
    window: W,
    finding: 'epoch-6 锚点逐位复现 epoch-4 行（纯 ETF 书，epoch 6 的股票费率 pin 是 no-op）。腰斩发生在 epoch 4：对这本书 epoch 4 只咬两处——order_volume_ratio=0.05 与基金费率 0.00025→0.0003；费率差每边 0.00005、每日近乎全换，两年合计约 5%，解释不了 annual −173pp ⇒ epoch-2 的 369% 里约一半是「一笔单吃掉薄基金一天成交量 5% 以上」的成交，是容量，不是信号。两年都强正：2022（熊）+300%、2023 +121%，回撤全在 2022（9.82 vs 2.69），2023 的 vol 只有 2022 的一半',
    confidence: 'high',
    flags: 'anchor · reproduces-epoch-4 · participation-cap-halves-return · capacity-not-signal · both-years-positive · gate-pass（sharpe 11.15）',
    description: 'study/PT多策略/baseline-e6.py（build-e6.js 生成）；algorithmId f541f7a6ca2d15f8682c03ebcd0cd423；SUMMARY train 2022-01-01 2023-12-31 729 772.01 195.74 11.15 9.82 completed；6 JQ 分钟（used 88 → 94）；曲线 data/series/study_PT多策略_baseline-e6__train__e6.json，yearsplit.js 逐年',
    implication: '关闭「引用 pre-wipe epoch-2 q-1 的数字」：参与上限改变的正是 band 这件事本身，band sweep 必须在本台重跑（u-1 / u-2 已排）。打开 realizability 的定量读法：仅仅把成交限在成交量 5% 就少一半，任何 VAL 预期与整合层估值都应从 196% 而不是 369% 起算，而且 5% 对开盘集合竞价上的薄 ETF 仍然偏宽',
    spawned: 'u-1, u-2, u-6',
    edgeRef: '流动性溢价',
  },
  {
    qId: 'u-1', type: 'sweep',
    component_or_param: 'edge test 流动性溢价 (a)：同一规则、同一权重、同一 top-10，成交额 band 5e6–2e7 → 5e7–1e8（流动基金），一行',
    metric_delta: 'vs 锚点：obj 1.8592→0.0076（−1.8516）· annual 195.74→22.74（−173.0pp）· sharpe 11.15→0.94 · maxDD 9.82→21.98（+12.2pp）· total 772.01→50.56 · 逐年 2022 +300.50→+14.53（maxDD 9.82→21.98 · sharpe~ 6.34→0.55）、2023 +121.38→+30.57（2.69→10.77 · 6.68→1.43）；pre-wipe epoch-2 同臂 obj 0.0535 / sharpe 1.09',
    window: W,
    finding: '搬到流动 band 后同一折价规则只剩年化 22.7%、sharpe 0.94、回撤 22%——过不了 1.5 闸门，obj 归零。但没有变负：两年各 +14.5% / +30.6%，仍是正的。与 epoch-2 的同臂读数（0.05 / 1.09）一致，参与上限没有改变这条结论。折价信号在流动 ETF 上是一个弱的、DQ 的信号；把它做成 sharpe 11 的，是薄 band',
    confidence: 'high',
    flags: 'edge-test-ran · liquid-band-DQ · both-years-still-positive · reproduces-epoch-2-reading · DQ',
    description: 'variants/u-1_band-liquid.py（一行 diff）；algorithmId 4341c478ed9f2231766cd2e6db95340c；SUMMARY train 2022-01-01 2023-12-31 729 50.56 22.74 0.94 21.98 completed；4 JQ 分钟（94 → 98）；曲线 data/series/study_PT多策略_variants_u-1_band-liquid__train__e6.json',
    implication: '流动性溢价 的 (a) 臂跑了、未证伪；等 (b) 臂 u-2 再定 status。关闭「把 sleeve 移植到流动基金」作为 improve：那是 obj 0.008 的书。同时把 realizability 判决写成数字：唯一能真实成交的 band 上，这条血统是年化 23% / 回撤 22% 的东西，任何整合层引用都应按这个数而不是 196%',
    spawned: 'none',
    edgeRef: '流动性溢价',
  },
  {
    qId: 'u-2', type: 'sweep',
    component_or_param: 'edge test 流动性溢价 (b)：去掉 2e7 上界、保留 5e6 下界（流动基金可以挤进 top-10），一行',
    metric_delta: 'vs 锚点：obj 1.8592→1.8055（−0.0537）· annual 195.74→194.54（−1.2pp）· sharpe 11.15→9.30 · maxDD 9.82→13.99（+4.2pp）· total 772.01→764.97 · 逐年 2022 +300.50→+278.27（maxDD 9.82→13.99）、2023 +121.38→+129.77（2.69→5.39）；pre-wipe epoch-2 同臂 obj 2.8897（−0.71 vs 3.5955）',
    window: W,
    finding: '放开上界后收益几乎不动（annual −1.2pp），回撤 +4.2pp、sharpe −1.85。在 epoch 2（无参与上限）同一臂丢了 0.71 obj，现在只丢 0.05：有了 5% 上限之后，上界对「选谁」几乎不起作用——最深折价本来就在薄基金里，top-10 by 折价深度基本还是那些名字；偶尔挤进来的流动基金带来的是回撤（2022 13.99 vs 9.82），不是收益。上界是一道回撤过滤器，不是收益来源',
    confidence: 'high',
    flags: 'edge-test-ran · ceiling-is-drawdown-filter · return-invariant · gate-pass（sharpe 9.30）',
    description: 'variants/u-2_band-nocap.py（一行 diff）；algorithmId 1298b726231f20fb71c30b429187e578；SUMMARY train 2022-01-01 2023-12-31 729 764.97 194.54 9.30 13.99 completed；3 JQ 分钟（98 → 101）；曲线 data/series/study_PT多策略_variants_u-2_band-nocap__train__e6.json',
    implication: '流动性溢价 升 measured：(a) 只留流动基金 → 塌到 DQ（u-1）；(b) 放流动基金进来 → 收益不变、只加回撤（u-2）。收益活在 band 的下端（薄），不在上界的「排除」里；关闭「2e7 上界是诀窍」的读法。打开 pt-imp-1：从下端反过来问——丢掉 band 最薄的一半（下界 5e6 → 1e7），收益跟着薄尾走还是回撤跟着走',
    spawned: 'pt-imp-1',
    edgeRef: '流动性溢价',
  },
  {
    qId: 'u-6', type: 'regime',
    component_or_param: '基类曲线逐年拆（2022 熊 / 2023 震荡），零回测，读 baseline-e6 的曲线',
    metric_delta: '2022：total +300.50 · maxDD 9.82 · vol 0.2253 · sharpe~ 6.34 · 上涨日 164/241（68%）‖ 2023：total +121.38 · maxDD 2.69 · vol 0.1181 · sharpe~ 6.68 · 159/242（66%）；复利校验 4.0050 × 2.2138 = 8.867 ≈ 1 + 7.7201 ✓',
    window: W,
    finding: '两年同号强正，没有「2022 专属」：熊市年赚得更多（+300 vs +121）也承担全部回撤（9.82 vs 2.69）；2023 的 vol 只有 2022 的一半，风险调整后两年几乎一样（sharpe~ 6.3 / 6.7）。上涨日占比两年都在 2/3——这是一个每天赚一点、极少大亏的分布，与 多因子ML / 打板短线 / 大小盘轮动 那条「收益集中在 2022」的模式不同，也与 网格 的「99% 在一个半年」不同',
    confidence: 'high',
    flags: 'both-years-positive · not-regime-carried · vol-halves-in-2023 · zero-cost',
    description: 'yearsplit.js 读 data/series/study_PT多策略_baseline-e6__train__e6.json（cum 链式换算，不差分）。本行无新 algorithmId（同 baseline-e6）',
    implication: '关闭「TRAIN 内部 regime 承载」：两年各自都过闸，本轮不需要再花子窗回测。打开的唯一 regime 检验是 VAL 2024–25（2024-02 微盘踩踏对薄 ETF 的开盘折价是未知的一课）——本家族的一次 VAL 应留给基类或 on-mechanism 候选，不留给任何改 band 的变体',
    spawned: 'none',
    edgeRef: '',
  },
];
let n = 0;
for (const r of rows) if (!have.has(r.qId)) { rq.recordFinding(F, r); n++; }
console.log(`record: wrote ${n}, findings now ${rq.findings(F).length}`);
