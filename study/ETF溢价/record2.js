// Records the second half of the epoch-6 round (idempotent by qId).
//   node -e "require('./study/ETF溢价/record2.js')"
// Anchor (baseline-e6): obj 0.8607 / annual 105.37 / sharpe 5.93 / maxDD 19.30 / total 320.95.
// u-2 (ETF-only): obj 1.6193 / annual 174.40 / sharpe 8.06 / maxDD 12.47 / total 650.87 — the improve
// candidates are built on it, so their Δ is against u-2 (and against the anchor in brackets).
const rq = require('../../utils/research-queue');
const F = 'ETF溢价';
const have = new Set(rq.findings(F).map(f => f.qId));
const W = 'train 2022-01-01→2023-12-31（729d / 484 交易日）';
const rows = [
  {
    qId: 'u-4', type: 'sweep',
    component_or_param: 'edge test 流动性溢价，流动臂：昨日 share-volume 下界 2e6 → 1e8（universe lof+etf、top-5 等权不动），一行',
    metric_delta: 'vs 锚点：obj 0.8607→0.0937（−0.7670）· annual 105.37→33.66（−71.7pp）· sharpe 5.93→1.04 · maxDD 19.30→24.29（+5.0pp）· total 320.95→78.52 · 逐年 2022 +83.14→+45.55（maxDD 17.92→23.79 · sharpe~ 3.05→1.24）、2023 +133.78→+23.46（4.73→14.68 · 5.48→0.79）；pre-wipe epoch-2 同臂 sharpe 1.10 / Δobj −1.45',
    window: W,
    finding: '只留昨日成交量 ≥ 1e8 股的流动基金，同一折价规则只剩年化 34% / sharpe 1.04 / 回撤 24%——过不了 1.5 闸门，obj 归零。两年仍为正（+46 / +23）。与 epoch-2 的同臂读数（sharpe 1.10）一致：参与上限没有改变这条结论，因为流动基金上 5% 本来就不绑。折价信号在流动 ETF 上是一个弱的、DQ 的信号；做成 sharpe 6–8 的，是薄 universe',
    confidence: 'high',
    flags: 'edge-test-ran · liquid-arm-DQ · both-years-still-positive · reproduces-epoch-2-reading · DQ',
    description: 'variants/u-4_floor-1e8.py（一行 diff）；algorithmId 193558f69502fe51dde5f73bc6811ee2；SUMMARY train 2022-01-01 2023-12-31 729 78.52 33.66 1.04 24.29 completed；3 JQ 分钟（134 → 136）；曲线 data/series/study_ETF溢价_variants_u-4_floor-1e8__train__e6.json',
    implication: '流动性溢价 升 measured，但带 ep-imp-1 的细化：下界 2e6→1e7 不丢收益（+7.8pp），2e6→1e8 丢掉全部——收益活在 1e7–1e8 股这一档，而不是最薄的 2e6–1e7（那一档在 5% 参与上限下本就填不满，还是 LOF 扎堆的地方）。关闭「把 sleeve 移植到流动基金」作为 improve：那是 obj 0.09 的书。整合层若要一个「可真实成交」的读数，是 34% / sharpe 1.04，不是 105% / 174%',
    spawned: 'none',
    edgeRef: '流动性溢价',
  },
  {
    qId: 'ep-imp-0', type: 'improve',
    component_or_param: '采纳 u-2 的 ETF-only universe 作为候选（同一次测量，不重跑）',
    metric_delta: '= u-2：vs 锚点 obj +0.7586 · annual +69.0pp · sharpe +2.13 · maxDD −6.8pp',
    window: W,
    finding: 'ETF-only 是本家族在 epoch 6 上第一个过闸且优于基类的候选（obj 1.6193 / sharpe 8.06 / maxDD 12.47），高于基类的 epoch-2 ledger 行 1.5642。改动是减法：去掉 LOF',
    confidence: 'high',
    flags: 'adopted-on-TRAIN · shares-measurement-with-u-2 · zero-extra-cost',
    description: '无新回测；候选文件 = study/ETF溢价/variants/u-2_etf-only.py（algorithmId 12a97f62874d36580a6ac4479e0e4ac5）',
    implication: '后续 improve 全部以 ETF-only 为起点（ep-imp-1/2/3 已按此重建，Δ 对 u-2 量）。它不是 VAL 候选的终点——ep-imp-1 若更高则由它去 VAL',
    spawned: 'ep-imp-1, ep-imp-2, ep-imp-3',
    edgeRef: '均值回归',
  },
  {
    qId: 'ep-imp-1', type: 'improve',
    component_or_param: 'ETF-only + share-volume 下界 2e6 → 1e7（epoch-2 q-1 甜点），对 u-2 一行',
    metric_delta: 'vs u-2：obj 1.6193→1.6733（+0.0540）· annual 174.40→182.21（+7.8pp）· sharpe 8.06→7.26（−0.80）· maxDD 12.47→14.88（+2.4pp）· total 650.87→694.16 ‖ vs 锚点 +0.8126 · 逐年 2022 +241.66（maxDD 14.88 · sharpe~ 4.38 · 上涨日 145/241）/ 2023 +133.75（8.76 · 3.93 · 141/242）',
    window: W,
    finding: '收紧下界到 1e7 股：年化 +7.8pp、回撤 +2.4pp、sharpe −0.8，obj +0.054——刚过惰性阈（0.05），方向是可实现性变好的方向，但 epoch-2 的甜点（+0.47、回撤减半）没有了：那时最薄一档的收益是无参与上限的容量幻觉，现在 5% 上限已把它削掉，收紧下界只是不再买那些填不满的名字。2022 +242 / 2023 +134，两年都略高于 u-2',
    confidence: 'med',
    flags: 'adopted-marginal · Δobj-at-inert-threshold · sharpe-down-maxDD-up · realizability-direction · gate-pass（sharpe 7.26）',
    description: 'enhance/candidates/ep-imp-1.py（对 u-2 一行 diff）；algorithmId 6d3c23cd0910a65ee99e25411d23563c；SUMMARY train 2022-01-01 2023-12-31 729 694.16 182.21 7.26 14.88 completed；1–2 JQ 分钟（136 → 137）；曲线 data/series/enhance_candidates_ep-imp-1__train__e6.json',
    implication: '关闭下界作为旋钮：1e7 与 2e6 在 obj 上几乎无差（+0.05），1e8 塌掉（u-4）——收益活在 1e7–1e8 股，下界在这个区间内怎么放都差不多。按 objective 规则 ep-imp-1 是 TRAIN 最优候选，本家族的一次 VAL 花在它上（而不是 u-2）；⚠ 采纳是 TRAIN 内的相对判断，realizability 否决（u-1）不变',
    spawned: 'val-imp-1-e6',
    edgeRef: '流动性溢价',
  },
  {
    qId: 'ep-imp-2', type: 'improve',
    component_or_param: 'ETF-only + top-5 → top-2（epoch-2 q-2 的单峰顶点），对 u-2 一行',
    metric_delta: 'vs u-2：obj 1.6193→1.0440（−0.5753）· annual 174.40→116.68（−57.7pp）· sharpe 8.06→5.68（−2.38）· maxDD 12.47→12.28（−0.2pp）· total 650.87→368.52 ‖ vs 锚点 +0.1833 · 逐年 2022 +170.29（maxDD 12.28 · 上涨日 153/241）/ 2023 +75.39（4.53 · 150/242）',
    window: W,
    finding: '集中到最深折价的 2 只：年化 −58pp、回撤不变。epoch-2 的「N=2 单峰、+0.35」在本台上翻成 −0.58：5% 参与上限下最深的 2 只吃不下 100 万资金，第 3–5 名是填单宽度而不是分散（与 PT多策略 imp-2 的 top-10→top-5 −0.14 同一机制，本家族更陡因为从 5 到 2）。两年都低于 u-2（2022 +170 vs +238，2023 +75 vs +123）',
    confidence: 'high',
    flags: 'rejected · fill-width-not-diversification · epoch-2-peak-gone · both-years-lower · gate-pass（sharpe 5.68）',
    description: 'enhance/candidates/ep-imp-2.py（对 u-2 一行 diff）；algorithmId de74d314cff720fb0d16a68e8688cb4b；SUMMARY train 2022-01-01 2023-12-31 729 368.52 116.68 5.68 12.28 completed；2 JQ 分钟（137 → 139）；曲线 data/series/enhance_candidates_ep-imp-2__train__e6.json',
    implication: '关闭集中度作为 improve（向下：填单宽度；向上 top-N>5 = 更浅的折价，u-4 已示范流动/浅折价名字只加回撤不加收益）。pre-wipe §4 的「edd94ebc 的 top-2 + 三个过滤器解释 ~2.0 gap」这条归因作废：top-2 在本台是负贡献，edd94ebc 的 epoch-2 头条（3.5961）应是无参与上限下 top-2 吃满薄基金成交量的容量幻觉，它有锚点之前不再对它归因',
    spawned: 'none',
    edgeRef: '均值回归',
  },
  {
    qId: 'ep-imp-3', type: 'improve',
    component_or_param: "可实现形态：ETF-only + 信号与成交都在 14:50（last_price 换成 get_price(frequency='1m', count=1) 的 14:49 分钟收盘 vs T−1 净值，收盘价买入），对 u-2 两处一个概念",
    metric_delta: 'vs u-2：obj 1.6193→−0.8592（−2.4785）· annual 174.40→−31.43（−205.8pp）· sharpe 8.06→−1.33 · maxDD 12.47→54.49（+42.0pp）· total 650.87→−52.93 ‖ vs 锚点 −1.7199 · 逐年 2022 −42.35（maxDD 53.04 · 上涨日 101/241）/ 2023 −18.42（39.36 · 106/242）',
    window: W,
    finding: '在收盘看到的折价、在收盘买、等次日回归：两年 −53%、回撤 54%，两年同号为负。收盘时仍然折价最深的 ETF 不是「新的一次偏离」，而是当天没被套平的——薄到实物申赎也不去套的名字，持有它们拿到的是薄 ETF 的负漂移（与 PT多策略 u-4 无信号最薄 10 只 −42% 同量级）。日频台上 14:50 读当日 1m 数据被 avoid_future_data 放行（run completed、有成交），这是一个可复用的读法',
    confidence: 'high',
    flags: 'rejected · realizable-form-negative · both-years-negative · DQ · 1m-read-at-1450-works-on-daily-bench',
    description: 'enhance/candidates/ep-imp-3.py（对 u-2：run_daily 时点 + last_price 三行）；algorithmId a1e2a11510752be4f73c3d81abc922a2；SUMMARY train 2022-01-01 2023-12-31 729 -52.93 -31.43 -1.33 54.49 completed；3–4 JQ 分钟（139 → 143）；曲线 data/series/enhance_candidates_ep-imp-3__train__e6.json',
    implication: '关闭「可实现形态」这条线：开盘折价（u-1：到收盘已回归）与收盘折价（本条：次日不回归、还亏）两头都测了，机制只存在于集合竞价的成交价上，本家族没有任何可实现候选。improve 队列清空：universe（ep-imp-0 采纳）、下界（ep-imp-1 边际）、集中度（ep-imp-2 否决）、执行时点（ep-imp-3 否决）。家族 status 建议 DQ-realizability，与 PT多策略 同一裁决，由人定',
    spawned: 'none',
    edgeRef: '均值回归',
  },
  {
    qId: 'val-imp-1-e6', type: 'validate',
    component_or_param: '候选 ep-imp-1（ETF-only + 下界 1e7）在 VAL 2024-01-01→2025-12-31 上跑一次——本家族 epoch 6 的唯一一次验证，花在 TRAIN 最优候选上',
    metric_delta: 'VAL：total 886.96 · annual 214.16 · sharpe 7.60 · maxDD 13.01 · obj 2.0115 ‖ 对照 TRAIN ep-imp-1：annual 182.21 · sharpe 7.26 · maxDD 14.88 · obj 1.6733 ⇒ VAL 高 +0.34 obj；逐年见 description',
    window: 'val 2024-01-01→2025-12-31（730d / 485 交易日）',
    finding: 'VAL 不衰减、反而高于 TRAIN：年化 214% / sharpe 7.6 / 回撤 13%，过闸。四个年度（2022–2025）在「开盘价按成交量 5% 可成交」这个假设下都成立——与 PT多策略 的 VAL（242%，同样高于 TRAIN）同一形态。这不是对机制的新信息：u-1 已证明每一个数字都是集合竞价成交价上的伪影，VAL 只说明伪影在 2024–25 仍在',
    confidence: 'high',
    flags: 'VAL-spent · val-above-train · four-years-same-sign · gate-pass（sharpe 7.60）· ⚠零滑点 · ⚠开盘价成交假设（realizability 见 u-1 / ep-imp-3）',
    description: 'enhance/candidates/ep-imp-1.py --window val --family ETF溢价；algorithmId fdb2d73bd66c25f674bebc6c07f0a5ca；SUMMARY val 2024-01-01 2025-12-31 730 886.96 214.16 7.60 13.01 completed；~3 JQ 分钟（143 → ~146）；曲线 data/series/enhance_candidates_ep-imp-1__val__e6.json',
    implication: '关闭本 epoch 的 VAL（已花，不可再花；JQ_ALLOW_REVAL 是人的开关）。关闭「VAL 会把它筛掉」：不会。剩下的唯一一道门是人裁决 status：两条 edge measured、VAL 过、但 u-1 + ep-imp-3 证明开盘折价与收盘折价两头都不可实现。整合层引用本家族时按 u-4 的 34% / sharpe 1.04（流动 universe）估值，不按 214%',
    spawned: 'none',
    edgeRef: '均值回归',
  },
];
let n = 0;
for (const r of rows) if (!have.has(r.qId)) { rq.recordFinding(F, r); n++; }
console.log(`record2: wrote ${n}, findings now ${rq.findings(F).length}`);
