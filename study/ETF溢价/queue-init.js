// Seeds study/ETF溢价/queue.json for the epoch-6 round (idempotent by id).
//   node -e "require('./study/ETF溢价/queue-init.js')"
// Priors: the pre-wipe epoch-2 study (git e009f67 / a6195c6, wiki/families/ETF溢价.md §6 q-1 / q-2)
// measured, WITHOUT a participation cap: share-volume floor 2e6 -> 1e7 obj +0.47 (maxDD halved),
// 3e7 -0.84, 1e8 -1.45 DQ (sharpe 8.44 -> 3.16 -> 1.10); top-N 5 -> 2 obj +0.35 (peak), N=1 collapse.
// Epoch 4/6 pins order_volume_ratio=0.05 and fund costs; the only ledger row is epoch 2 (1.5642).
// Sibling family PT多策略 (same mechanism, money band 5e6–2e7, top-10) measured on epoch 6 on
// 2026-09-22: the 5% cap halved its annual, mirror -91%, no-signal thinnest-10 -42%, and the
// whole return vanished when the fill moved from the open to 14:50 (u-7).
const rq = require('../../utils/research-queue');
const F = 'ETF溢价';
const have = new Set(rq.load(F).map(e => e.id));
const ideas = [
  {
    id: 'q-ledger', kind: 'understand', rank: 0,
    title: '成员 edd94ebc 为什么没有 ledger 行（§3 显示 DQ/—），零回测',
    hypothesis: 'pre-wipe 页面记它 epoch-2 obj 3.5961 / annual 374.38 / sharpe 14.77；现在 harness/normalize-train.tsv、所有 .bak、deferred.json、series-scan.json 里都没有它，pending-normalize 也没有排它。它的策略页没有 normalized: 块，所以 ledger 回退后 normalize-ledger-rebuild.js 无从重建。证伪：任一处找到它的行',
    why: '家族只有 2 个成员；一个没有任何本台数字，§3 的「DQ/—」不是 DQ，是丢失。决定本轮要不要花分钟给它一个锚点',
    design: 'grep 全部 ledger 与备份；读 wiki/strategies/edd94ebc 页',
    from: [], edgeRef: null,
  },
  {
    id: 'baseline-e6', kind: 'understand', rank: 1,
    title: '基类 15c36e0c 在 epoch 6 上的锚点（ledger 只有 epoch-2 行 1.5642）',
    hypothesis: '源码自设基金费率 0.00025 min 0、无滑点、不设 order_volume_ratio；epoch 6 的股票费率 pin 对纯基金书是 no-op，咬到的是 5% 参与上限（share-volume 下界只有 2e6 股，比 PT多策略 的 5e6 成交额更薄）与 min_commission 5。预期 annual 明显低于 177.88，方向与 PT多策略 的 369 -> 196 一致；证伪：obj 落在 1.5642 ± 0.05',
    why: '每个后续 Δ 都对它量；参与上限造成的缩水本身是 流动性溢价 的第一条证据',
    design: 'study/ETF溢价/baseline-e6.py = py2to3(源码) + live OVERRIDE（build-e6.js）；曲线 -> yearsplit.js 逐年',
    from: ['q-ledger'], edgeRef: '流动性溢价',
  },
  {
    id: 'u-1', kind: 'understand', rank: 2,
    title: 'realizability：信号不动（09:30 = 开盘价），成交挪到 14:50（收盘价）',
    hypothesis: '若收益是「在集合竞价那口价上成交」这件事（PT多策略 u-7：+772% -> −29%），把成交挪到收盘应塌到负；若折价在开盘后逐步回归，14:50 成交仍应保留一部分。证伪（对 DQ-realizability 读法）：14:50 成交的 objective ≥ 基类 −0.3 且两年同号为正',
    why: '兄弟家族的判决性实验；本家族信号用 last_price 而非 day_open、等权 top-5、含 LOF，机制是否相同要在本家族量一次。这是决定整合层能否引用本家族 objective 的一条',
    design: 'variants/u-1_exec-1450.py：market_open 只算 g.order_fund，新增 market_exec 在 14:50 执行卖/买（两处一个概念）',
    from: ['baseline-e6'], edgeRef: '均值回归',
  },
  {
    id: 'u-2', kind: 'understand', rank: 3,
    title: 'universe：去掉 LOF、只留 ETF（edd94ebc 的 universe）',
    hypothesis: 'LOF / QDII 的 T−1 净值发布有滞后（CLAUDE.md 记为折价族的公开问题）：若「折价」多半是净值陈旧造成的假折价，收益应集中在 LOF 上，去掉 LOF 后 objective 大幅下降；若 ETF 上同量级，NAV 滞后不是主要来源。证伪：|Δobj| < 0.1',
    why: '本家族是库里唯一 universe 含 LOF 的折价书，只有它能回答这个公开问题；同时给 edd94ebc 的 universe 一个可比读数',
    design: "variants/u-2_etf-only.py：一行 ['lof','etf'] -> ['etf']",
    from: ['baseline-e6'], edgeRef: '均值回归',
  },
  {
    id: 'u-3', kind: 'understand', rank: 4,
    title: 'edge test 均值回归 by mirror：同一 universe / 下界 / top-5 等权，买最高溢价（premium>0，降序）',
    hypothesis: '若信息在折价的符号里，镜像应塌（两年同号为负或 obj ≤ 0）；若镜像也赚到同量级，则收益是薄基金 universe 的效应而非折价回归。证伪：镜像 objective ≥ 基类 −0.1',
    why: '流动性溢价 说的是 universe，均值回归 说的是信号；两条 claim 要分开测。PT多策略 的镜像 −91%，本家族含 LOF、等权，要自己量',
    design: 'variants/u-3_mirror.py：排序降序 + premium>0（两个 sort 分支一起翻）',
    from: ['baseline-e6'], edgeRef: '均值回归',
  },
  {
    id: 'u-4', kind: 'understand', rank: 5,
    title: 'edge test 流动性溢价，流动臂：share-volume 下界 2e6 -> 1e8',
    hypothesis: 'epoch-2 q-1 在无参与上限下量到 1e8 臂 sharpe 1.10 / obj −1.45（DQ）。若 edge 是薄基金的 illiquidity 溢价，本台上流动臂仍应 DQ；若参与上限已经把薄尾部的收益削掉，流动臂与基类的差距应缩小。证伪：流动臂 objective ≥ 基类 −0.1',
    why: '家族 edge 的直接检验，也是 realizability 的定量读数：唯一能真实成交的 universe 上这条血统值多少',
    design: 'variants/u-4_floor-1e8.py：一行 2e6 -> 1e8',
    from: ['baseline-e6'], edgeRef: '流动性溢价',
  },
  {
    id: 'ep-imp-1', kind: 'improve', rank: 6,
    title: 'share-volume 下界 2e6 -> 1e7（epoch-2 甜点：obj +0.47、maxDD 减半）',
    hypothesis: 'epoch-2 q-1 说基类的 2e6 下界过松、纳入超薄高回撤尾部。有了 5% 参与上限后，那段尾部本就填不满，甜点可能消失（PT多策略 imp-1：下界收紧一档 −0.57，band 单调）。若 obj > 基类，更可实现的 universe 也更好；若降，收益活在最薄一档。证伪：obj ≤ 基类',
    why: 'on-mechanism（作用在 流动性溢价 的下界上）且方向是可实现性变好的方向',
    design: 'enhance/candidates/ep-imp-1.py：一行 2e6 -> 1e7',
    from: ['baseline-e6', 'u-4'], edgeRef: '流动性溢价',
  },
  {
    id: 'ep-imp-2', kind: 'improve', rank: 7,
    title: 'top-5 -> top-2（epoch-2 q-2 的单峰顶点：obj +0.35，maxDD +2.9）',
    hypothesis: 'epoch-2 说集中度在 N=2 单峰、N=1 崩塌。5% 参与上限下最深的 2 只可能吃不下资金（PT多策略 imp-2：top-10 -> top-5 反而 −0.14，现金拖累）。若 obj > 基类，深折价的边际信息还在；若降，填单宽度压过集中度。证伪：obj ≤ 基类',
    why: 'on-mechanism（集中到最深折价）；与 u-3 一起回答折价深度的边际信息',
    design: 'enhance/candidates/ep-imp-2.py：一行 df[:5] -> df[:2]',
    from: ['baseline-e6', 'u-3'], edgeRef: '均值回归',
  },
  {
    id: 'ep-imp-3', kind: 'improve', rank: 8,
    title: '可实现形态：信号与成交都在 14:50（14:49 分钟收盘价 vs T−1 净值，收盘价买入）',
    hypothesis: '若开盘折价到收盘已回归（u-1 预期），那么在收盘看到的折价是新的一次偏离，次日开盘可能回归；这才是一个不抢集合竞价的账户能拿到的版本。若 obj > 0 且过闸，家族有一个可实现候选；否则机制只存在于集合竞价。证伪：obj ≤ 0 或 sharpe < 1.5',
    why: '本家族唯一不违反 realizability 否决的 improve 方向；u-1 的结果决定它是否值得跑',
    design: "enhance/candidates/ep-imp-3.py：run_daily 时点 09:30 -> 14:50，last_price 换成 get_price(frequency='1m', count=1) 的分钟收盘。⚠ 日频台上 14:50 读当日分钟数据是否被 avoid_future_data 放行未验证；跑失败即记 blocked",
    from: ['u-1'], edgeRef: '均值回归',
  },
];
let n = 0;
for (const e of ideas) if (!have.has(e.id)) { rq.add(F, e); n++; }
console.log(`queue-init: added ${n}, queue now ${rq.load(F).length}`);
