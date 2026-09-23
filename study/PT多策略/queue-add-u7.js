// Adds u-7 (spawned by u-3 and val-base-e6): realizability of the auction-open fill.
//   node -e "require('./study/PT多策略/queue-add-u7.js')"
const rq = require('../../utils/research-queue');
const F = 'PT多策略';
if (!rq.load(F).some(e => e.id === 'u-7')) {
  rq.add(F, {
    id: 'u-7', kind: 'understand', rank: 10,
    title: '执行从 09:30（开盘价成交）挪到 14:50（收盘价成交），信号不动——偏离在集合竞价之后还剩多少',
    hypothesis: '若收益是「集合竞价开盘价对净值的偏离在开盘后即回归」，把成交挪到 14:50 应把它抹掉大半（obj 降 ≥ 1.0，甚至转负）；若 14:50 成交仍保留基类一半以上的年化，则偏离是持续到收盘的、日频账户可以拿到。证伪：obj ≥ 基类 −0.3',
    why: 'TRAIN/VAL 每个数字都建立在「薄 ETF 的开盘价能按全天成交量 5% 成交」上；这是唯一能把 realizability 从定性变成数字的一次实验，也是 u-3 镜像 −91% 提出的机制问题',
    design: 'variants/u-7_exec-1450.py：一行 run_daily(market_open, \'09:30\') → \'14:50\'（买卖都在 14:50，信号仍是 09:25 的 day_open）',
    from: ['u-3', 'val-base-e6', 'baseline-e6'], edgeRef: '均值回归',
  });
  console.log('added u-7');
} else console.log('u-7 already queued');
