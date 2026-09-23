// Second batch of the epoch-6 round (idempotent by qId): u-3, u-4, u-5.
//   node -e "require('./study/PT多策略/record2.js')"
// Anchor: total 772.01 / annual 195.74 / sharpe 11.15 / maxDD 9.82 / obj 1.8592; 2022 +300.50 (9.82) / 2023 +121.38 (2.69).
const rq = require('../../utils/research-queue');
const F = 'PT多策略';
const have = new Set(rq.findings(F).map(f => f.qId));
const W = 'train 2022-01-01→2023-12-31（729d / 484 交易日）';
const rows = [
  {
    qId: 'u-3', type: 'ablation',
    component_or_param: 'edge test 均值回归 by mirror：同一薄 band、同一 |premium| 加权、同一 top-10，只把信号翻成买最高溢价（premium>0，降序），两行',
    metric_delta: 'vs 锚点：obj 1.8592→−1.6164（−3.4756）· annual 195.74→−70.42（−266pp）· sharpe 11.15→−5.24 · maxDD 9.82→91.22（+81.4pp）· total 772.01→−91.22 · 逐年 2022 +300.50→−79.25（maxDD 9.82→79.29 · 上涨日 164→37/241）、2023 +121.38→−57.48（2.69→57.48 · 159→30/242）；对数尺度 ln(8.72)=+2.17 vs ln(0.088)=−2.43，近似对称',
    window: W,
    finding: '镜像两年亏掉 91%：买开盘价高于净值最多的薄 ETF，两年只有 14% 的交易日是涨的（基类 68%）。对数尺度上基类 +2.17 与镜像 −2.43 近似对称——收益就是「开盘价对净值的偏离在当天/次日回归」这一件事：折价方向赚，溢价方向亏，量级相同。这是 均值回归（对 NAV）能给出的最强形态',
    confidence: 'high',
    flags: 'edge-test-ran · mirror-collapses · log-symmetric · both-years-same-sign · 14%-up-days',
    description: 'variants/u-3_mirror-premium.py（两行 diff：排序降序 + premium>0）；algorithmId 6a73a79e9a52258eea3b263451dd7cfb；SUMMARY train 2022-01-01 2023-12-31 729 -91.22 -70.42 -5.24 91.22 completed；3 JQ 分钟（101 → 104）；曲线 data/series/study_PT多策略_variants_u-3_mirror-premium__train__e6.json',
    implication: '均值回归 的镜像臂跑了且未证伪（等 u-4 的无信号控制组定 status）。关闭「薄 ETF universe 本身有回弹/beta」的读法：若是 universe，镜像不会塌到 −91%。同时打开 realizability 的机制问题——信号是 09:25 的集合竞价开盘价，回归发生在开盘之后；一本在开盘价上按成交量 5% 成交的书，实际买到的是集合竞价那一笔的价格，而薄 ETF 的集合竞价成交量远小于全天的 5%',
    spawned: 'none',
    edgeRef: '均值回归',
  },
  {
    qId: 'u-4', type: 'isolate',
    component_or_param: '无信号控制组：同一薄 band，premium 一行换成 −1e7/money（不含 NAV 信息，最薄在前、过滤全过）+ 等权（两处一个概念）——持最薄 10 只等权、每日按薄度换仓',
    metric_delta: 'vs 锚点：obj 1.8592→−0.6734（−2.5326）· annual 195.74→−24.04（−219.8pp）· sharpe 11.15→−1.71 · maxDD 9.82→43.30（+33.5pp）· total 772.01→−42.26 · 逐年 2022 +300.50→−22.41（maxDD 9.82→25.58 · 上涨日 101/241）、2023 +121.38→−24.61（2.69→31.35 · 105/242）',
    window: W,
    finding: '拿掉 NAV 信息、只持 band 里最薄的 10 只等权，两年亏 42%、回撤 43%，两年同号为负。薄 universe 本身不赚钱，它亏钱（最薄的 ETF 是在萎缩/清盘边缘的基金，加上每日换仓的往返）。分解：universe −42% / 折价信号 +772% / 镜像 −91%——收益全部来自信号，universe 是它的载体而非来源',
    confidence: 'high',
    flags: 'edge-test-ran · control-negative · both-years-same-sign · universe-is-carrier-not-source',
    description: 'variants/u-4_universe-control.py（两处 diff）；algorithmId 62cdb724204763391937f715e8991294；SUMMARY train 2022-01-01 2023-12-31 729 -42.26 -24.04 -1.71 43.30 completed；3 JQ 分钟（104 → 107）；曲线 data/series/study_PT多策略_variants_u-4_universe-control__train__e6.json',
    implication: '均值回归 升 measured（u-3 镜像 −91%、u-4 无信号 −42%、基类 +772%，三臂两年同号）：这条血统的 edge 是「薄 ETF 的集合竞价开盘价对净值的偏离会回归」，信号承重、universe 不承重。与 流动性溢价 合读：薄不是为了持有薄基金，而是因为只有薄基金的开盘价才会偏离净值那么远——两条 edge 是同一件事的两面（偏离的幅度由薄度供给，方向由 NAV 供给）。关闭一切「换 universe 保信号」的 improve（u-1 已量：流动基金上偏离太小）',
    spawned: 'none',
    edgeRef: '均值回归',
  },
  {
    qId: 'u-5', type: 'ablation',
    component_or_param: '权重：|premium| 加权 → 等权，一行（band / 过滤 / top-10 不动）',
    metric_delta: 'vs 锚点：obj 1.8592→1.7020（−0.1572）· annual 195.74→178.93（−16.8pp）· sharpe 11.15→10.37 · maxDD 9.82→8.73（−1.1pp）· total 772.01→675.82 · 逐年 2022 +300.50→+251.38（maxDD 9.82→8.72）、2023 +121.38→+124.50（2.69→2.73）',
    window: W,
    finding: '等权少赚 17pp 年化、回撤只浅 1.1pp：折价深度有边际信息——最深折价的名字回归得更多，把资金压向它们是对的。差额几乎全在 2022（+300 vs +251），2023 持平（+121 vs +125）：深折价在熊市里更深、回归也更大。不是惰性（|Δobj| 0.16 > 0.05 的阈）',
    confidence: 'high',
    flags: 'depth-weighting-informative · 2022-concentrated-gain · gate-pass-both-arms',
    description: 'variants/u-5_equal-weight.py（一行 diff）；algorithmId f6c514a66fdaa2202efd3851976c32a0；SUMMARY train 2022-01-01 2023-12-31 729 675.82 178.93 10.37 8.73 completed；3 JQ 分钟（107 → 110）；曲线 data/series/study_PT多策略_variants_u-5_equal-weight__train__e6.json',
    implication: '关闭「等权作为降回撤的 improve」：换来的 −1.1pp 回撤买不回 −17pp 年化。打开的是 pt-imp-2 的反向读法：既然深度有信息，集中到 top-5 应至少不降——若 top-5 反而降，那是 5% 参与上限在薄名字上填不满，作者放宽到 10 是对的',
    spawned: 'pt-imp-2',
    edgeRef: '均值回归',
  },
];
let n = 0;
for (const r of rows) if (!have.has(r.qId)) { rq.recordFinding(F, r); n++; }
console.log(`record2: wrote ${n}, findings now ${rq.findings(F).length}`);
