// Records the epoch-6 round's findings into study/ETF溢价/findings.tsv (idempotent by qId).
//   node -e "require('./study/ETF溢价/record.js')"
// Base anchor (baseline-e6): total 320.95 / annual 105.37 / sharpe 5.93 / maxDD 19.30 / obj 0.8607;
// per-year 2022 +83.14 (maxDD 17.92, vol 0.1994, sharpe~ 3.05, up 131/241) / 2023 +133.78 (maxDD 4.73,
// vol 0.1553, sharpe~ 5.48, up 151/242). Every Δ below is against it unless stated.
const rq = require('../../utils/research-queue');
const F = 'ETF溢价';
const have = new Set(rq.findings(F).map(f => f.qId));
const W = 'train 2022-01-01→2023-12-31（729d / 484 交易日）';
const rows = [
  {
    qId: 'q-ledger', type: 'probe',
    component_or_param: '成员 edd94ebc 的 ledger 行（§3 显示 DQ/—），零回测',
    metric_delta: 'Δ 不适用（零回测）。pre-wipe 页面（git a6195c6）记 edd94ebc epoch-2 obj 3.5961 / annual 374.38 / sharpe 14.77 / maxDD 14.77',
    window: '—',
    finding: 'harness/normalize-train.tsv、四个 .bak、normalize-train.rebuild.json、data/deferred.json、data/series-scan.json 里都没有 edd94ebc；data/pending-normalize.json 也没有排它。它的策略页没有 normalized: 块（15c36e0c 的有），所以 ledger 回退后 normalize-ledger-rebuild.js 无从重建它——§3 的「DQ/—」不是 DQ，是行丢失。它的代码是基类 + 三个入场过滤（昨日 high−low<0.1、成交额>8e5、收盘>MA5）+ top-2 + ETF-only，其中 MA5 用逐只 get_price 循环（每日 ~数百次调用），本台上可能落入 slow-skip',
    confidence: 'high',
    flags: 'ledger-row-lost · not-in-pending · zero-cost-probe · per-security-loop',
    description: 'grep 全部 ledger/备份/队列；读 wiki/strategies/edd94ebc_ETF溢价回撤.md 与源码。本行无 algorithmId',
    implication: '关闭「edd94ebc 是 DQ」的读法：它从未在本台被量过。打开两件事：(1) normalize 应把它重新排进 pending-normalize（本轮不代做——归一化是 normalize 阶段的账，且它的 MA5 循环可能吃掉 20 分钟）；(2) 本轮 u-2（ETF-only）给它的 universe 一个可比读数，q-2 的 top-2 由 ep-imp-2 在本台重量，剩下的三个过滤器归因留给它有锚点之后',
    spawned: 'u-2, ep-imp-2',
    edgeRef: '',
  },
  {
    qId: 'baseline-e6', type: 'baseline',
    component_or_param: '基类 15c36e0c 在 epoch 6 上的锚点（py2to3(源码) + live OVERRIDE；ledger 只有 epoch-2 行）',
    metric_delta: 'vs ledger epoch-2 行：obj 1.5642→0.8607（−0.7035）· annual 177.88→105.37（−72.5pp）· sharpe 8.87→5.93 · maxDD 21.46→19.30（−2.2pp）；逐年 2022 +83.14（maxDD 17.92 · vol 0.1994 · sharpe~ 3.05 · 上涨日 131/241）/ 2023 +133.78（maxDD 4.73 · vol 0.1553 · sharpe~ 5.48 · 151/242）；复利 1.8314 × 2.3378 = 4.281 ≈ 1 + 3.2095 ✓',
    window: W,
    finding: 'epoch 6 上基类年化从 178% 掉到 105%，obj 1.56→0.86，仍过闸（sharpe 5.93）。纯基金书，epoch 6 的股票费率 pin 是 no-op；咬到它的是 epoch 4 的两处——order_volume_ratio=0.05 与基金费率 0.00025/min 0 → 0.0003/min 5。费率差每边 0.00005、日频全换两年约 5%，解释不了 −72pp ⇒ 缩水的主体是参与上限：2e6 股的下界比 PT多策略 的 5e6 成交额更薄，一笔单吃掉薄基金一天成交量 5% 以上的成交在 epoch 2 里占了年化的四成。与 PT多策略 的 369→196 同一模式。两年同号为正，回撤几乎全在 2022（17.92 vs 4.73），2023 反而是更强的一年（+134 vs +83）——与 PT多策略 相反（+300 / +121）',
    confidence: 'high',
    flags: 'anchor · participation-cap-bites · capacity-not-signal · both-years-positive · 2023-stronger · gate-pass（sharpe 5.93）',
    description: 'study/ETF溢价/baseline-e6.py（build-e6.js 生成）；algorithmId d738b8dc4694748e96bb12e146bda615；SUMMARY train 2022-01-01 2023-12-31 729 320.95 105.37 5.93 19.30 completed；3 JQ 分钟（used 123 → 126）；曲线 data/series/study_ETF溢价_baseline-e6__train__e6.json，yearsplit.js 逐年',
    implication: '关闭「引用 pre-wipe epoch-2 的 q-1 / q-2 数字」：参与上限改变的正是下界与集中度这两个旋钮本身，两个 sweep 都要在本台重跑（u-4 / ep-imp-1 / ep-imp-2 已排）。打开 realizability 的定量读法：任何 VAL 预期与整合层估值从 105% 起算而不是 178%，而且 5% 对开盘集合竞价上的薄 ETF/LOF 仍然偏宽（u-1 判决）',
    spawned: 'u-1, u-2, u-3, u-4',
    edgeRef: '流动性溢价',
  },
  {
    qId: 'u-1', type: 'probe',
    component_or_param: 'realizability：信号不动（09:30 = 日频台的开盘价），卖/买挪到 14:50（收盘价成交）；market_open 只存 g.order_fund，新增 market_exec',
    metric_delta: 'vs 锚点：obj 0.8607→−0.1676（−1.0283）· annual 105.37→4.95（−100.4pp）· sharpe 5.93→0.07 · maxDD 19.30→21.71（+2.4pp）· total 320.95→10.14 · 逐年 2022 +83.14→+6.16（maxDD 17.92→21.71 · 上涨日 131→113/241）、2023 +133.78→+3.72（4.73→14.94 · 151→120/242）',
    window: W,
    finding: '同一信号、只把成交从开盘价挪到收盘价，两年从 +321% 变成 +10%（年化 5%、sharpe 0.07）。开盘时对净值的折价到收盘已经回归完毕——不是逐步回归、能在盘中分一杯羹，而是全部发生在开盘那口价与收盘之间。与 PT多策略 u-7（+772% → −29%）同一判决，本家族没有塌到负：等权 top-5 + 含 LOF 的 universe 在收盘价上是零收益而非负漂移（PT 的 |premium| 加权 top-10 最薄 band 是 −29%）。收益 ≈100% 是「在集合竞价的成交价上以全天成交量 5% 成交」这个撮合假设',
    confidence: 'high',
    flags: 'realizability-DECISIVE · auction-print-only · both-years-≈0 · DQ（sharpe 0.07）· matches-PT多策略-u-7',
    description: 'variants/u-1_exec-1450.py（两处一个概念：run_daily 14:50 + market_exec）；algorithmId 16b838ae90a083329afec4d9ab2b9c87；SUMMARY train 2022-01-01 2023-12-31 729 10.14 4.95 0.07 21.71 completed；3 JQ 分钟（126 → 129）；曲线 data/series/study_ETF溢价_variants_u-1_exec-1450__train__e6.json',
    implication: '关闭一切以 TRAIN 头条为准的引用：105%（或 u-2 的 174%）是集合竞价成交价上的回测伪影，一个不能在开盘集合竞价里以那口价成交的账户拿到的是 ~0。整合层与 type 层不得把本家族当作可拼接的 sleeve；与 PT多策略 一起，「ETF 开盘价偏离净值」这个观察在两个家族上都成立、都不可实现。家族 status 建议 DQ-realizability，由人裁决。打开 ep-imp-3：既然开盘折价到收盘已回归，收盘时看到的折价是新的一次偏离——在收盘买、等次日开盘回归，是唯一可实现的形态，值得一跑',
    spawned: 'ep-imp-3',
    edgeRef: '均值回归',
  },
  {
    qId: 'u-2', type: 'ablation',
    component_or_param: "universe：get_all_securities(['lof','etf']) → ['etf']（去掉 LOF），一行",
    metric_delta: 'vs 锚点：obj 0.8607→1.6193（+0.7586）· annual 105.37→174.40（+69.0pp）· sharpe 5.93→8.06 · maxDD 19.30→12.47（−6.8pp）· total 320.95→650.87 · 逐年 2022 +83.14→+237.92（maxDD 17.92→12.47 · 上涨日 131→161/241）、2023 +133.78→+123.45（4.73→9.81 · 151→160/242）',
    window: W,
    finding: '去掉 LOF 后年化 +69pp、回撤 −6.8pp、sharpe 5.93→8.06：LOF 腿是拖累，不是来源。差额几乎全在 2022（+83 → +238），2023 持平略降（+134 → +123）。机制读法：ETF 的折价靠一级市场实物申赎（T+0）当日套平，所以开盘折价到收盘回归（u-1）；LOF 的申赎是现金、T+2 确认、有费用，折价是持续的而不是回归的——按「最深折价」排序，LOF 在 2022 熊市里长期占住 top-5 的位置却不回归，还带来更深回撤。CLAUDE.md 记的「LOF/QDII 净值发布滞后造成假折价」这个方向，若成立应表现为 LOF 贡献正收益（假折价被当真折价买入、次日净值更新后价格跟上）；实测相反',
    confidence: 'high',
    flags: 'LOF-leg-is-drag · 2022-concentrated · gate-pass（sharpe 8.06）· improve-by-subtraction · obj-above-epoch-2-row（1.6193 vs 1.5642）',
    description: 'variants/u-2_etf-only.py（一行 diff）；algorithmId 12a97f62874d36580a6ac4479e0e4ac5；SUMMARY train 2022-01-01 2023-12-31 729 650.87 174.40 8.06 12.47 completed；3 JQ 分钟（129 → 131）；曲线 data/series/study_ETF溢价_variants_u-2_etf-only__train__e6.json',
    implication: '关闭「LOF 净值滞后是折价族收益来源」的公开问题（CLAUDE.md）：LOF 腿在本台上是 −69pp 年化的拖累，NAV 陈旧没有制造可赚的假折价。打开：(1) ETF-only 是本家族第一个 improve 候选（同一次测量，不重跑，登记为 ep-imp-0 adopted-on-TRAIN）；(2) 后续 improve 候选全部建立在 ETF-only 上（ep-imp-1/2/3 已重建）；(3) 兄弟家族 PT多策略 与成员 edd94ebc 本来就是 ETF-only，家族的 base 15c36e0c 是唯一含 LOF 的——家族最优点在 ETF 上。⚠ realizability 否决（u-1）不因此解除：+174% 仍是集合竞价成交价上的数',
    spawned: 'ep-imp-0, ep-imp-1, ep-imp-2, ep-imp-3',
    edgeRef: '均值回归',
  },
  {
    qId: 'u-3', type: 'ablation',
    component_or_param: 'edge test 均值回归 by mirror：同一 universe（lof+etf）/ 2e6 下界 / top-5 等权，排序降序 + premium>0（买最高溢价）',
    metric_delta: 'vs 锚点：obj 0.8607→−1.8746（−2.7353）· annual 105.37→−88.72（−194pp）· sharpe 5.93→−4.04 · maxDD 19.30→98.74（+79.4pp）· total 320.95→−98.72 · 逐年 2022 +83.14→−89.39（上涨日 131→57/241）、2023 +133.78→−88.05（151→41/242）；对数尺度 ln(4.21)=+1.44 vs ln(0.013)=−4.36，不对称：镜像亏得远多于基类赚的',
    window: W,
    finding: '镜像两年亏掉 98.7%：买开盘价高于净值最多的 5 只基金，两年只有 20% 的交易日是涨的（基类 58%）。折价方向赚、溢价方向亏，符号承载全部信息。与 PT多策略 u-3（−91%，对数近似对称）不同，本家族不对称——lof+etf 的 universe 里最高溢价的名字是 QDII-LOF / 持续高溢价的 LOF（净值陈旧或额度受限），溢价方向除了回归还叠加了这些名字的清算式塌陷；这与 u-2「LOF 腿是拖累」互相印证',
    confidence: 'high',
    flags: 'edge-test-ran · mirror-collapses · both-years-same-sign · 20%-up-days · asymmetric-vs-PT',
    description: 'variants/u-3_mirror.py（排序两个分支 + 过滤，三行一个概念）；algorithmId f0f115755e237a44c1c6320b10754f6a；SUMMARY train 2022-01-01 2023-12-31 729 -98.72 -88.72 -4.04 98.74 completed；3 JQ 分钟（131 → 134）；曲线 data/series/study_ETF溢价_variants_u-3_mirror__train__e6.json',
    implication: '均值回归 升 measured（镜像 −99%、基类 +321%、两年同号；与 u-1 合读：偏离的方向由 NAV 供给，回归发生在开盘价到收盘价之间）。关闭「薄基金 universe 本身有回弹」的读法。不再需要 PT多策略 那样的无 NAV 控制组：u-1 已把「拿掉信号时点」的读数给了（+10%），u-3 把「翻转信号」给了（−99%），两者夹住基类',
    spawned: 'none',
    edgeRef: '均值回归',
  },
];
let n = 0;
for (const r of rows) if (!have.has(r.qId)) { rq.recordFinding(F, r); n++; }
console.log(`record: wrote ${n}, findings now ${rq.findings(F).length}`);
