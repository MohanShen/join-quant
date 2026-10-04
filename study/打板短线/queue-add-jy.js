// Queues the 涨停基因 sub-lineage questions for the 2026-10-04 re-invocation. Idempotent by id.
//   node -e "require('./study/打板短线/queue-add-jy.js')"
const rq = require('../../utils/research-queue');
const F = '打板短线';
const have = new Set(rq.load(F).map(e => e.id));
const ideas = [
  {
    id: 'jy-u-1', kind: 'understand', rank: 1, from: ['nm-2026-09-27'], edgeRef: '涨停基因',
    title: '涨停基因 子血统基类 c9e0451d：去掉全部涨停信息（三年涨停次数前 10% 的筛选 + 启动点距离排序都改成恒等）——剩下的是同一周频脚手架上的纯小市值书',
    hypothesis: '若 obj ≥ 0.5478 − 0.05（且逐年同号），涨停史在这本书里是惰性的，子血统的 edge 是 规模因子（与 小市值 冗余）；若 obj 掉 ≥ 0.15 或 2023 变负，历史涨停频率是承重的预测特征，涨停基因 升 measured 并需在 wiki-schema §2.3 登记',
    why: '人工把子血统基类归入本家族时明确写「edge 大概率 规模因子」而未测；这决定 b3751277 / c658ef98 / d5b83074 / c9e0451d 四本书是本家族的第二条 edge 还是 小市值 的冗余组——整合层按哪个算，差别很大',
    design: 'variants/jy-u-1_no-limit-info.py（build-jy.js：get_stock_list 两行改 pass，一个概念）；--window train；锚点 = 归一化行 0.5478 / 67.73 / 2.94 / 12.95（2026-10-03，同一 OVERRIDE）',
  },
  {
    id: 'jy-u-2', kind: 'understand', rank: 2, from: ['nm-2026-09-27'], edgeRef: '涨停基因',
    title: '镜像：保留涨停基因筛选与启动点排序，把 1000 只最小市值换成 1000 只最大市值',
    hypothesis: '若 obj 塌到 < 0.1 或任一年为负，size 是子血统收益的必要条件（涨停史最多是 小市值 内部的二次筛选）；若 obj ≥ 0.5478 − 0.15 且两年同号，涨停史在大票上也赚，是独立于 size 的来源',
    why: 'jy-u-1 只能说「涨停信息有没有用」，说不清「离开小市值它还在不在」；两条合起来才能给子血统的 edge 定名',
    design: 'variants/jy-u-2_largest-caps.py（build-jy.js：valuation.market_cap.asc() → desc()，一行）；--window train',
  },
];
let n = 0;
for (const i of ideas) if (!have.has(i.id)) { rq.add(F, i); n++; }
console.log(`queue-add-jy: added ${n}, total ${rq.load(F).length}`);
