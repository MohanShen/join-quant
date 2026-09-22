// Improve ideas spawned once 均值回归 measured (u-1, u-4). Idempotent.
//   node -e "require('./study/网格/queue-add-3.js')"
const rq = require('../../utils/research-queue');
const F = '网格';
const have = new Set(rq.load(F).map(e => e.id));
const ideas = [
  {
    id: 'wg-imp-2', kind: 'improve', rank: 10, from: ['u-1', 'u-4'], edgeRef: '均值回归',
    title: '买入档距收紧：−8/16/24/32% → −5/10/15/20%（只动买档）',
    hypothesis: 'u-1/u-4 说信息在「跌买涨卖」的方向上；更密的买档在同一往返里更早、更多次地接住回撤，若均值回归成立应抬 annual ≥5pp 且 maxDD 不升；证伪：objective ≤ 基类',
    why: 'on-mechanism：直接作用在 measured 的 均值回归 上；imp-1 已证明动选股会稀释，所以只动档距',
    design: 'enhance/candidates/wg-imp-2.py：handle_data 里 long 调用的 bench −0.08 → −0.05（一处）',
  },
  {
    id: 'wg-imp-3', kind: 'improve', rank: 11, from: ['u-1', 'u-4'], edgeRef: '均值回归',
    title: '卖出档距收紧：+15/30/45/60% → +10/20/30/40%（只动卖档）',
    hypothesis: '基类卖档比买档宽近一倍（15 vs 8），2023-H1 的 +78% 里大部分是在 +60% 才清空；更早减仓应压 maxDD 但也削弱 2023；若 objective 上升则往返更对称更好，证伪：objective ≤ 基类',
    why: '与 imp-2 互为一半：买/卖档各自的贡献分开量',
    design: 'enhance/candidates/wg-imp-3.py：handle_data 里 short 调用的 bench 0.15 → 0.10（一处）',
  },
];
let n = 0;
for (const i of ideas) if (!have.has(i.id)) { rq.add(F, i); n++; }
console.log(`queue-add-3: added ${n}, total ${rq.load(F).length}`);
