// Seeds study/三进兵/queue.json for the epoch-6 round. Idempotent: skips ids already present.
//   node -e "require('./study/三进兵/queue-init.js')"
const rq = require('../../utils/research-queue');
const F = '三进兵';
const have = new Set(rq.load(F).map(e => e.id));
const ideas = [
  {
    id: 'baseline-e6', kind: 'understand', rank: 1, from: ['baseline', 'q-dup'], edgeRef: null,
    title: '基类 7d1012a5 在 epoch 6 上的锚点（ledger 只有 epoch-2 行）',
    hypothesis: '源码自设的 stock 成本表与 bench 逐项相同（epoch-6 pin 是 no-op）；滑点 PriceRelated 0.00246 → FixedSlippage(0) 在 epoch 2 已生效；order_volume_ratio 0.25 → 0.05 对 5 只创业板大票、11–26% 的仓位不应卡单。预期 annual 0.07 / sharpe −0.49 / maxDD 9.00 / 27 笔逐位复现。证伪：任一指标偏离 >0.2pp、笔数 ≠ 27、或 no-trades',
    why: '每个后续 Δ 都对它量；若复现，epoch-2 的 q-1 / q-2 / q-3 / q-4 就是同一台上的读数，可直接引用而不必重跑',
    design: 'study/三进兵/baseline-e6.py = py2to3(源码) + live OVERRIDE（build-e6.js）',
  },
  {
    id: 'u-1', kind: 'understand', rank: 2, from: ['q-1', 'q-3'], edgeRef: '趋势择时',
    title: '同一 overlay 换到规则选出的池：2021-12-31 创业板指市值前 5（数据止于 TRAIN 之前）——择时信息是形态的，还是这 5 个名字的',
    hypothesis: '作者自述「发现本策略并不是适合所有的股票的」并手挑 5 只；q-1 量到那个篮子在 TRAIN 上是后见之明的输家（B&H −48%）而 overlay 仍比等暴露随机在场高约 +7pp/年。若择时信息属于形态，换到规则池后 overlay 相对该池自己的 B&H（u-1c）应仍有同号的 Δsharpe（≥ +0.3）；若 Δsharpe ≤ 0，则 q-1 的 +0.56 是名字挑出来的，趋势择时 证伪',
    why: '这是 edge 块 test: 的 (a) 半——家族唯一可能的收益来源就是这条 overlay，而它此前只在作者挑过的 5 只上量过',
    design: 'variants/u-1_pool-transfer.py：g.stokcs_pool 一行换成 get_index_stocks(399006, date=2021-12-31) 按 market_cap 降序前 5（initialize 内，只读 TRAIN 之前的数据）；hold_count 5、三条规则、分仓不动',
  },
  {
    id: 'u-1c', kind: 'understand', rank: 3, from: ['q-1'], edgeRef: '趋势择时',
    title: 'u-1 的读数基准：同一规则池、首日等权买入持有（q-1 持有控制组的原形）',
    hypothesis: '2022–23 创业板指 −29% / −19%，规则池 B&H 预期为负（annual −15 ~ −30%、maxDD ≥ 40%）；它本身不是发现，只是 u-1 的 Δ 所对的那本账。证伪项无——这是控制臂',
    why: 'q-1 的教训：overlay 相对「哪本 B&H」才是那个 Δ；没有它 u-1 的 sharpe 读不出「择时信息」还是「池子本身更好」',
    design: 'variants/u-1c_hold-on-pool.py：u-1 的池 + trade_func 换成 q-1 的持有体（首日 order_target_value 等权，g.bought 后不再交易）',
  },
  {
    id: 'u-3', kind: 'understand', rank: 4, from: ['q-1', 'q-4'], edgeRef: '趋势择时',
    title: '第三条规则单独拆：收盘跌破 EMA20（且 EMA20 < EMA60）止损关掉',
    hypothesis: 'q-1 一次合并了三条出入场规则，+0.56 sharpe 无法拆到止损与均线交叉之间；q-4 已证倒置的 is_sell 是一条有效的意外止盈。若关掉止损后 sharpe 下降 ≥ 0.2，止损承重（overlay 的信息有一半在退出）；若上升，止损在 2023 的磨人行情里只是在割反弹底部的仓位',
    why: '把 q-1 的合成消融拆成部件，是 q-1 自己留下的未完成项；也决定 improve 能不能碰止损',
    design: 'variants/u-3_no-stop.py：re_loss = False 一行；is_sell 与入场不动',
  },
  {
    id: 'u-2', kind: 'understand', rank: 5, from: ['q-3'], edgeRef: '趋势择时',
    title: '去掉入场的「底部」子句（EMA20 < EMA60）：入场变成任何阶段的 EMA5/EMA60 金叉——2023 的 1W/12L 是不是底部过滤造成的',
    hypothesis: 'q-3 把入场读成只在熊市 V 反弹里触发的底部反转形态（2022 P/L 2.64、2023 P/L 0.18）。若去掉底部子句后 2023 单年不再是 1W/12L（P/L ≥ 0.8）而 2022 保持为正，则「只在底部买」是 2023 的成本；若两年同时变差，底部子句承重、q-3 的机理读法成立',
    why: 'q-3 的机理读法是这个家族目前唯一的「为什么」，但它没有被单独检验过',
    design: 'variants/u-2_no-bottom-filter.py：is_buy 里删去 and (y_ma_med_value < y_ma_max_value)，一行；逐年读数从曲线切',
  },
  {
    id: 'sjb-imp-1', kind: 'improve', rank: 6, from: ['q-2', 'u-1'], edgeRef: '趋势择时',
    title: '同一规则、池子放宽到 2021-12-31 创业板指市值前 20（hold_count 仍 5）——用更多名字治「信号稀缺」',
    hypothesis: 'q-2：仓位 scale-invariant、常年只有 11–26% 在场，DQ 的成因是信号稀缺而非风控；加仓走不出 sharpe=(annual−rf)/vol 的陷阱，唯一 on-mechanism 的杠杆是更多名字产生更多信号。若 u-1 显示 overlay 可迁移，则 20 只池应把在场率抬到 ≥ 40% 且 sharpe ≥ u-1；证伪：sharpe ≤ u-1 或仍 < 0',
    why: '仅在 u-1 迁移成立时有意义（否则是在更多名字上摊一个没有信息的 overlay）；故排在 u-1 之后、由 u-1 的结果决定是否派发',
    design: 'enhance/candidates/sjb-imp-1.py：u-1 的池规则 limit(5) → limit(20)，其余逐字节相同',
  },
];
let n = 0;
for (const i of ideas) if (!have.has(i.id)) { rq.add(F, i); n++; }
console.log(`queue-init: added ${n}, total ${rq.load(F).length}`);
