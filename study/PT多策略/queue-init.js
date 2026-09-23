// Seeds study/PT多策略/queue.json for the epoch-6 round (idempotent by id).
//   node -e "require('./study/PT多策略/queue-init.js')"
// Priors: the pre-wipe epoch-2 study (git e009f67, wiki/families/PT多策略.md §6 q-1) measured the
// band sweep WITHOUT a participation cap: liquid band 5e7–1e8 obj 0.0535 / sharpe 1.09 (DQ),
// no-ceiling obj 2.8897 / sharpe 13.37, base 3.5955 / 18.17. Epoch 4/6 pins order_volume_ratio=0.05
// and fund costs; the ledger already shows the same file at annual 195.74 (epoch 4) vs 369.07 (epoch 2).
const rq = require('../../utils/research-queue');
const F = 'PT多策略';
const have = new Set(rq.load(F).map(e => e.id));
const ideas = [
  {
    id: 'q-struct', kind: 'understand', rank: 0,
    title: '家族成员计数：c70281d3 的 4358 行「分仓隔离插件」是否真的运行（零回测）',
    hypothesis: '文件第 143 行与第 4355 行是一对模块级 \'\'\'，其间的第二个 initialize / subPortfolio 类 / 小市值子策略全部在字符串字面量里，从不执行；真正跑的是 1–142 行的单一 ETF 折价 sleeve（与 fa0d3bd9 同源，差异：09:30 last_price 取代 09:25 day_open、多一个 −5%/+10% 止损止盈）。证伪：任一 run_daily 注册来自 143 行之后',
    why: '标题与 wiki 桩页都把它记成「小市值 + ETF 动量 + 打板」多策略；若它是同一 sleeve，家族独立证据量 = 1 份代码体，而且「多策略/账本」框架不是 edge 来源',
    design: '逐行读源码（grep 模块级三引号与 def initialize），零回测',
    from: [], edgeRef: null,
  },
  {
    id: 'baseline-e6', kind: 'understand', rank: 1,
    title: '基类 fa0d3bd9 在 epoch 6 上的锚点（ledger 只有 epoch 2/4 行）',
    hypothesis: '源码自设基金费率 0.00025 与 0.1% 滑点、不设 order_volume_ratio；epoch 6 的股票费率 pin 对纯 ETF 书是 no-op，故预期逐位复现 epoch-4 行 annual 195.74 / sharpe 11.15 / maxDD 9.82 / obj 1.8592。证伪：任一指标偏离 >0.3pp。同时读出 epoch-2 → 4 的腰斩（369 → 196）是 5% 参与上限还是费率造成的（费率差 0.00005/边 × 每日全换 ≈ 5% 两年，解释不了 −173pp）',
    why: '每个后续 Δ 都对它量；腰斩本身是 流动性溢价 claim 的第一条证据——若成交被限在成交量 5% 就少赚一半，收益就活在「能吃掉薄基金成交量」这件事上',
    design: 'study/PT多策略/baseline-e6.py = 源码 + live OVERRIDE（build-e6.js）；曲线 → yearsplit.js 逐年拆',
    from: ['q-struct'], edgeRef: '流动性溢价',
  },
  {
    id: 'u-1', kind: 'understand', rank: 2,
    title: 'edge test 流动性溢价 (a)：同一规则搬到流动基金 band 5e7–1e8',
    hypothesis: '若 edge 是薄基金 illiquidity 溢价，流动 band 上折价信号应失去风险调整后的收益（epoch-2 先例：obj 0.0535 / sharpe 1.09）。证伪：流动 band objective ≥ 基类 −0.1',
    why: '这是家族 edge 的直接检验，也是 realizability 的判决：唯一可真实成交的 band 恰是 edge 消失的 band 这一读数，需要在有 5% 参与上限的本 epoch 重新确立',
    design: 'variants/u-1_band-liquid.py：一行 band 5e6–2e7 → 5e7–1e8',
    from: ['baseline-e6'], edgeRef: '流动性溢价',
  },
  {
    id: 'u-2', kind: 'understand', rank: 3,
    title: 'edge test 流动性溢价 (b)：去掉 2e7 上界（流动基金可以挤进 top-10）',
    hypothesis: '若 alpha 专属薄尾部，让流动基金参与只会稀释（epoch-2 先例 obj 2.89 vs 3.60，−20%）；若在 5% 参与上限下薄基金本就填不满，放开上界反而可能变好。证伪方向双向，都是信息',
    why: '与 u-1 合起来给 band 的两端各一个读数；u-2 同时是 realizability 的可行版本（上界是作者刻意加的）',
    design: 'variants/u-2_band-nocap.py：一行 band → money > 5e6',
    from: ['baseline-e6'], edgeRef: '流动性溢价',
  },
  {
    id: 'u-3', kind: 'understand', rank: 4,
    title: 'edge test 均值回归 by mirror：同一薄 band，买最高溢价（premium>0，降序 top-10）',
    hypothesis: '若信息在折价的符号里，镜像应塌（两年同号为负或 obj ≤ 0）；若镜像也赚到同量级，则收益是薄 ETF 的 universe/回弹效应而非折价回归。证伪：镜像 objective ≥ 基类 −0.1',
    why: '流动性溢价 说的是 universe，均值回归 说的是信号；两条 claim 要分开测，否则「薄基金」和「折价」不可区分',
    design: 'variants/u-3_mirror-premium.py：两行（排序降序 + premium>0）',
    from: ['baseline-e6'], edgeRef: '均值回归',
  },
  {
    id: 'u-4', kind: 'understand', rank: 5,
    title: '无信号控制组：同一薄 band，不看 NAV，持最薄 10 只等权',
    hypothesis: '若 universe 本身（薄 ETF）就能给出基类量级的收益，则折价信号是装饰；若控制组 ≤ 0 而基类 >> 0，信号承重。证伪（对 均值回归）：控制组 objective ≥ 基类 −0.1',
    why: 'u-3 只翻符号；u-4 把 NAV 信息整个拿掉，两者合读才能把「薄 universe」与「折价信号」的贡献拆开',
    design: 'variants/u-4_universe-control.py：premium 一行换成 −1e7/money（最薄在前，过滤全过）+ 权重等权（两处一个概念）',
    from: ['baseline-e6'], edgeRef: '均值回归',
  },
  {
    id: 'u-5', kind: 'understand', rank: 6,
    title: '|premium| 加权 → 等权（其余不动）',
    hypothesis: '按折价深度加权把资金压向最深折价（通常也最薄）的名字；等权若 objective 不降（|Δ| < 0.05），加权是惰性；若降 ≥ 0.1，深折价的边际信息是真的。证伪：无——两个方向都是发现',
    why: 'pre-wipe §4 列为空白；也是 ETF溢价 q-2「集中度是回撤一等旋钮」的对照',
    design: 'variants/u-5_equal-weight.py：weights 一行',
    from: ['baseline-e6'], edgeRef: '均值回归',
  },
  {
    id: 'u-6', kind: 'understand', rank: 7,
    title: 'regime：基类曲线逐年拆（2022 熊 / 2023 震荡），零回测',
    hypothesis: '折价族的低回撤在跨族规律里多为 2022 熊市专属（ETF溢价 §4）；若 2023 单年 total ≤ 0 或 sharpe~ < 1，edge 是 regime 承载的。证伪：两年同号为正且各自 sharpe~ ≥ 2',
    why: 'VAL 2024–25 是另一个 regime；先知道 TRAIN 内部是否已经不稳',
    design: 'yearsplit.js 读 data/series/study_PT多策略_baseline-e6__train__e6.json',
    from: ['baseline-e6'], edgeRef: null,
  },
  {
    id: 'pt-imp-1', kind: 'improve', rank: 8,
    title: '下界 5e6 → 1e7（保留 2e7 上界）：丢掉 band 最薄的一半',
    hypothesis: 'ETF溢价 q-1：把过松的下界收紧一档反而 obj +0.47、maxDD 减半（超薄尾部贡献回撤多于收益）。若 obj > 基类，则更可实现的 band 也更好；若 obj 降，则收益确实活在最薄一半。证伪：obj ≤ 基类',
    why: 'on-mechanism（作用在 流动性溢价 的 band 上）且方向是可实现性变好的方向——本家族唯一不违反 realizability 否决的 improve',
    design: 'enhance/candidates/pt-imp-1.py：一行 band 1e7–2e7',
    from: ['baseline-e6', 'u-1', 'u-2'], edgeRef: '流动性溢价',
  },
  {
    id: 'pt-imp-2', kind: 'improve', rank: 9,
    title: 'top-10 → top-5（作者从 5 放宽到 10「以求尽可能多地成交」）',
    hypothesis: 'ETF溢价 q-2：obj 在 N=2 单峰，N=5 回撤最低；本家族 N=10 在 5% 参与上限下可能是必要的填单宽度。若 top-5 obj > 基类，集中度还有余量；若降，作者的放宽是对的（填单限制）。证伪：obj ≤ 基类',
    why: 'on-mechanism（集中到最深折价）；与 u-5 一起回答「深折价的边际信息」',
    design: 'enhance/candidates/pt-imp-2.py：一行 head(10) → head(5)',
    from: ['baseline-e6', 'u-5'], edgeRef: '均值回归',
  },
];
let n = 0;
for (const e of ideas) if (!have.has(e.id)) { rq.add(F, e); n++; }
console.log(`queue-init: added ${n}, queue now ${rq.load(F).length}`);
