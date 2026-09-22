// Seeds study/网格/queue.json for the epoch-6 round. Idempotent: skips ids already present.
//   node -e "require('./study/网格/queue-init.js')"
const rq = require('../../utils/research-queue');
const F = '网格';
const have = new Set(rq.load(F).map(e => e.id));
const ideas = [
  {
    id: 'baseline-e6', kind: 'understand', rank: 1, from: ['baseline', 'q-dup'], edgeRef: null,
    title: '基类在 epoch 6 上的锚点（ledger 无 epoch-6 行）',
    hypothesis: '源码不设任何成本/滑点/成交量上限，epoch-4/6 的 pin 全部落在它本来就跑的 JQ 默认值上，且 epoch-4 行已逐位复现 epoch-2；预期 annual 33.79 / sharpe 1.19 / maxDD 19.68 逐位复现。证伪：任一指标偏离 >0.2pp，或 no-trades',
    why: '每个后续 Δ 都对它量；若它复现，epoch-2 的 q-1 / q-2 / q-3 就是同一台上的读数，可以直接引用而不必再花分钟重跑',
    design: 'study/网格/baseline-e6.py = 源码 + live OVERRIDE（build-e6.js）',
  },
  {
    id: 'u-1', kind: 'understand', rank: 2, from: ['q-3', 'baseline'], edgeRef: '均值回归',
    title: '关掉分档：只买入场档（4 units）不加不减——分档相对「持有同一篮子」赚了什么（edge 均值回归 的 test）',
    hypothesis: '分档只在价格跌到锚点 −8% 以下才首次买入、−16/−24/−32% 加到 7/9/10 units，涨到 +15/+30/+45/+60% 减到 6/3/1/0——它赚的是价格围绕锚点的往返。若持有控制组（同池、同轮换、同止损，首见即买 4 units 并持有）objective ≥ 网格书，则分档没有在篮子之上加任何东西，均值回归 证伪',
    why: 'q-3 显示两年收益的 99% 来自 2023-H1 单个半年（TMT/AI 行情），家族标题主张的熊市网格叙事已被数字否定；剩下的问题是「分档」还是「篮子」在赚钱——这决定 edge 是 均值回归 还是 none-found',
    design: 'variants/u-1_hold-control.py：handle_data 里两处 setup_position 换成 hold_position（amount==0 时 order_target_value 4*(g.cash/40)，其余不动）',
  },
  {
    id: 'u-2', kind: 'understand', rank: 3, from: ['q-3'], edgeRef: '均值回归',
    title: '行业换成作者自己注释掉的 C27+C39——同一台机器离开 I64/I65 还剩什么',
    hypothesis: 'q-3 的 2023-H1 集中度（+78% 单半年）与宇宙 I64/I65（互联网/软件）正是 AI 行情的板块重合；若同一规则在 C27（医药）+C39（电子）上 objective ≤ 0，则家族收益是板块 beta 而非分档机制。证伪：换板块后 objective ≥ 基类 −0.05',
    why: '一个只在一个板块的一个半年里有效的机制不是 edge；作者注释里保留了替代板块，是最贴近原文意图的对照',
    design: 'variants/u-2_sector-swap.py：industry_list 一行 I64,I65 → C27,C39（仍是 2 个行业，g.cash/40 的梯形与每行业 5 只不变）',
  },
  {
    id: 'u-3', kind: 'understand', rank: 4, from: ['baseline'], edgeRef: null,
    title: '文档 vs 实现：注释说取波动率最高，代码 s1[s1<6] 取的是价格方差最低的 5 只——翻成文档意图',
    hypothesis: 'variance() 算的是 180 日收盘价水平的方差（随价格平方放大），rank 升序取 <6 即选出市值前 30 里价格最低/最稳的 5 只；翻成最高 5 只后，若 objective 下降 ≥0.10，则「低价格方差」这一实际选股是承重的（可能是 低价股效应 的变体）；证伪：翻转后 objective ≥ 基类',
    why: 'baseline 量到 77% 特质方差、5 只票；选股规则的实际内容从未被指认，而它和文档相反',
    design: 'variants/u-3_top-variance.py：一行 s1[s1 < 6] → s1[s1 > len(s1) - 5]',
  },
  {
    id: 'wg-imp-1', kind: 'improve', rank: 5, from: ['baseline', 'q-3'], edgeRef: '均值回归',
    title: '名字翻倍、单位减半：每行业 10 只、unit_value = g.cash/80',
    hypothesis: 'baseline 说 DQ 的成因是 77% 特质方差（5 只票），闸门需要 vol 从 26% 降到 ~20%；同样的梯形铺在两倍名字上应压 vol ≥4pp 而年化下降 <5pp。证伪：objective ≤ 基类',
    why: '唯一直接作用在 DQ 成因（集中度）上的杠杆；on-mechanism（不改分档、不改止损）。排在三个 understand 之后：若 u-1 证伪分档，本条无意义',
    design: 'enhance/candidates/wg-imp-1.py：s1[s1 < 11] + unit_value = g.cash/80（两处一个概念）',
  },
];
let n = 0;
for (const i of ideas) if (!have.has(i.id)) { rq.add(F, i); n++; }
console.log(`queue-init: added ${n}, total ${rq.load(F).length}`);
