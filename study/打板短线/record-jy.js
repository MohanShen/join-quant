// Findings of the 涨停基因 sub-lineage round (2026-10-05). Idempotent by qId.
//   node -e "require('./study/打板短线/record-jy.js')"
// Anchor = normalizer row of c9e0451d (2026-10-03, same OVERRIDE): obj 0.5478 / annual 67.73 /
// sharpe 2.94 / maxDD 12.95 / total 180.94; 2022 +56.04 / 2023 +80.04; half-years 47.7 / 5.7 /
// 24.5 / 44.6; stats 149 trades (100/49), win 67.1%, pl 2.65, avgpos 30.6d, turnover 0.050, vol 22.6%.
const rq = require('../../utils/research-queue');
const F = '打板短线';
const have = new Set(rq.findings(F).map(f => f.qId));
const W = 'train 2022-01-01→2023-12-31（729d / 484 交易日）';
const rows = [
  {
    qId: 'jy-u-1', type: 'isolate',
    component_or_param: '涨停基因 子血统基类 c9e0451d：get_stock_list 里「三年涨停次数前 10%」筛选与「离上一次涨停启动点的距离」排序两行改为 pass（一个概念：去掉全部涨停信息），列表保持市值升序，其余（1000 最小市值池、每行业 1 只、周频 6 只、止损、1/4 月空仓）一字不动',
    metric_delta: 'vs 锚点：obj 0.5478 → 0.3237（−0.2241）· annual 67.73 → 47.49 · sharpe 2.94 → 2.00（仍过 1.5）· maxDD 12.95 → 15.12 · total 180.94 → 117.30 · 逐年 2022 +56.0 → +36.8 / 2023 +80.0 → +58.9 · 逐半年 47.7 / 5.7 / 24.5 / 44.6 → 32.1 / 3.5 / 7.6 / 47.6（四个半年仍全正）· 笔数 149 → 73、avgpos 30.6 → 76.2 天、turnover 0.050 → 0.026、win 67.1% → 71.2%、pl 2.65 → 4.31、vol 22.6% → 22.7%',
    window: W,
    finding: '去掉全部涨停信息后，同一周频脚手架上的纯小市值书仍过闸（obj 0.32 / sharpe 2.00），两年同号、四个半年全正，形状与锚点相同，只是每年少赚约 20pp；换手减半（名字在最小市值表里停留更久，是涨停排序在让它轮动）。预注册阈值（掉 ≥ 0.15）触发：涨停史是承重的，但它承重的方式是在一个本身就过闸的 规模因子 底座上加一层稳定的增量，而不是收益的来源本身。单看本条无法区分「涨停史独立有效」与「涨停史只是小市值内部的二次筛选」',
    confidence: 'high',
    flags: 'edge-test-(a)-ran · not-inert（−0.22）· floor-is-size（底座独立过闸）· same-shape-both-arms · gate-pass-both-arms',
    description: 'variants/jy-u-1_no-limit-info.py（build-jy.js，两行 → pass）；algorithmId 13733c7177438ae6a1204421c1e83762 / backtestId 30348f5f9c4fe040fc5e480c47d145a5；SUMMARY train 2022-01-01 2023-12-31 729 117.30 47.49 2.00 15.12 completed；usage 119→≈128/135；曲线 data/series/study_打板短线_variants_jy-u-1_no-limit-info__train__e6.json；stats 52/21、pl 4.306、avgpos 76.19、turnover 0.0257',
    implication: '关闭「涨停基因 筛选是惰性的、子血统 = 换了名字的 小市值」这一读法：它值 0.22 objective、每年约 20pp、两年都在。同时关闭「子血统的 edge 只有 涨停基因」：底座（1000 最小市值 × 每行业 1 只 × 周频）独立过闸，规模因子 是这本书的地板，整合层对本子血统的冗余判断必须按 规模因子 算、再加一层增量。打开的只剩 jy-u-2：同样的涨停史筛选搬到 1000 只最大市值上还剩多少——决定 涨停基因 是 size 内部的二次筛选（proposed 保留、不升）还是独立来源（升 measured 并登记）',
    spawned: 'jy-u-2',
    edgeRef: '涨停基因',
  },
  {
    qId: 'jy-u-2', type: 'isolate',
    component_or_param: '镜像：涨停基因 筛选与启动点排序原样保留，valuation.market_cap.asc() → desc()（一行）——同一台机器搬到 1000 只最大市值上',
    metric_delta: 'vs 锚点：obj 0.5478 → −0.4136（−0.9614）· annual 67.73 → −2.10 · sharpe 2.94 → −0.27 · maxDD 12.95 → 39.26 · total 180.94 → −4.16 · 逐年 2022 +56.0 → +30.1 / 2023 +80.0 → **−26.3** · 逐半年 47.7 / 5.7 / 24.5 / 44.6 → 31.0 / −0.7 / −15.6 / −12.7 · 笔数 149 → 179、avgpos 30.6 → 33.1 天、turnover 0.050 → 0.063（节奏相同）、win 67.1% → 43.0%、pl 2.65 → 0.99、vol 22.6% → 22.8%；基准同窗 −26.8%',
    window: W,
    finding: '同样的涨停史筛选、同样的启动点排序、同样的周频节奏，搬到最大市值的 1000 只上就不赚钱：胜率掉到 43%、盈亏比 0.99，2023 亏 26%、回撤 39%（仍略好于基准的 −27%，但那是 beta 不是 alpha）。预注册条件（obj < 0.1 或任一年为负）两条都触发：size 是子血统收益的必要条件。与 jy-u-1 合读：底座（小市值）独立过闸 0.32；涨停史在小市值内部值 +0.22；涨停史离开小市值值 −0.41 ⇒ 涨停基因 是 size 条件下的二次筛选（overlay），不是独立的收益来源。⚠ 执行器在 50 分钟上限处 slow-skip 并五次取消失败（「在此状态不能取消」），但该跑在服务端 2 分钟后完成；结果从算法的 buildList → stats / result 零成本回收并存为曲线',
    confidence: 'high',
    flags: 'edge-test-(b)-ran · size-necessary · overlay-not-source · both-years-flip（2023 负）· recovered-after-slow-skip（结果来自 buildList，非 SUMMARY 契约）· beta-vs-benchmark-only',
    description: 'variants/jy-u-2_largest-caps.py（build-jy.js，一行）；algorithmId 8fc8ab0761febf09ecb0127551fa28aa / backtestId 6d3c56d88c03d03537c9c1f78dd19f97（buildList 另给一个再铸 id 98a8dda6…，stats 相同）；执行器 SUMMARY train slow-skipped（51 分钟 wall，usage 126→135 封顶）；曲线 data/series/study_打板短线_variants_jy-u-2_largest-caps__train__e6.json（fetchViaHttp 回收，484 点 2022-01-04..2023-12-29）；stats 77/102、pl 0.990、avgpos 33.14、turnover 0.0629、vol 0.2279',
    implication: '涨停基因 作为独立 edge 判 refuted（test (b) 触发）；它在小市值内部的 +0.22 增量记在 §1 作为 规模因子 之上的 overlay，不单独成 edge、不登记名字。规模因子 对 涨停基因 子血统升 measured——jy-u-2 正是 §2.3 登记的 test（「只在最大档内跑同一规则；若 edge 成立，超额应基本消失」），jy-u-1 给出底座独立过闸。关闭在本家族内继续研究这条子血统：它的 edge 与 小市值 家族相同（库里第 6 个靠 规模因子 供血的家族），整合层按 规模因子 冗余组计，人工拆分时应并入 小市值（或作其子血统），而不是留在 打板短线 下。关闭「涨停次数更高的筛选阈值 / 更长的窗口」一类 improve：overlay 的来源仍是 size。队列清空；VAL 本 epoch 已花，不再有候选',
    spawned: 'none',
    edgeRef: '涨停基因',
  },
];
let n = 0;
for (const r of rows) if (!have.has(r.qId)) { rq.recordFinding(F, r); n++; }
console.log(`record-jy: wrote ${n}, findings now ${rq.findings(F).length}`);
