// Follow-ups spawned by u-1 / u-3 (and the epoch-6 re-run of q-2). Idempotent.
//   node -e "require('./study/网格/queue-add-2.js')"
const rq = require('../../utils/research-queue');
const F = '网格';
const have = new Set(rq.load(F).map(e => e.id));
const ideas = [
  {
    id: 'u-4', kind: 'understand', rank: 6, from: ['u-1'], edgeRef: '均值回归',
    title: '镜像分档：涨到锚点 +8/16/24/32% 才买、跌到 −15/30/45/60% 才卖——方向是不是信息所在',
    hypothesis: 'u-1 说分档相对持有值 +18pp（2022）/ +45pp（2023）；若任何「按偏离锚点缩放暴露」的梯子都能赚，镜像书 objective ≥ 基类 −0.05，均值回归 证伪；若镜像书塌掉（objective < 0），信息在方向（跌买涨卖）本身',
    why: 'u-1 的控制组暴露路径与分档不同（首见即满 4 units vs 等 −8%），「分档赢过持有」仍可能是暴露择时而非均值回归；镜像保留了同样的暴露缩放几何，只翻方向',
    design: 'variants/u-4_mirror-ladder.py：setup_position 内 8 个比较符翻转 + 两处调用的 bench 变号（build-e6.js 断言恰好 8 处）',
  },
  {
    id: 'u-5', kind: 'understand', rank: 7, from: ['q-2', 'baseline-e6'], edgeRef: '趋势择时',
    title: '在 epoch-6 锚点上关掉沪指 2 日 −3% 整卷清仓（q-2 的同台复跑，去掉跨 epoch 注脚）',
    hypothesis: 'baseline-e6 逐位复现 epoch-2，故预期 q-2 的读数复现：annual −13.4pp、maxDD +9.3pp、回撤窗端点不变。证伪：objective 不降',
    why: '1 JQ 分钟换 趋势择时 的 evidence 完全落在 epoch 6 上',
    design: 'variants/u-5_no-index-stop.py：handle_data 首行 if conduct_nday_stoploss(...) → if False',
  },
  {
    id: 'u-6', kind: 'understand', rank: 8, from: ['u-3'], edgeRef: null,
    title: 'u-3 拆分 (a)：按最新收盘价升序取 5 只（纯低价）——「最低价格方差」是不是 低价股效应',
    hypothesis: 'variance() 是 180 日收盘价水平的方差 ∝ 价格² × 收益方差；若纯低价书 objective 在基类 ±0.05 内，则实际选股 = 低价股效应；证伪：纯低价书 objective < 基类 −0.15',
    why: 'u-3 证明这条选股承重 −0.49；它到底选的是「便宜的票」还是「不动的票」决定 edge 的名字',
    design: 'variants/u-6_low-price.py：variance_list.append 一行换成最新收盘价',
  },
  {
    id: 'u-7', kind: 'understand', rank: 9, from: ['u-3'], edgeRef: null,
    title: 'u-3 拆分 (b)：按 180 日对数收益 std 升序取 5 只（纯低波动）',
    hypothesis: '若纯低波动书 objective 在基类 ±0.05 内而 u-6 不在，则选股是低波动而非低价；两者都在 ±0.05 内则两者共线（低价大票本来就低波）；两者都不在则价格水平方差里的组合本身才是那 5 只',
    why: '与 u-6 互为对照，一条线各答一半',
    design: 'variants/u-7_low-vol.py：variance_list.append 一行换成 180 日对数收益 std',
  },
];
let n = 0;
for (const i of ideas) if (!have.has(i.id)) { rq.add(F, i); n++; }
console.log(`queue-add-2: added ${n}, total ${rq.load(F).length}`);
