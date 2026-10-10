// One-off: seed the merged-loop queue for the ETF动量 epoch-6 rebuild round.
const rq = require('../../utils/research-queue');
const F = 'ETF动量';
if (rq.load(F).length) { console.log('queue already seeded'); process.exit(0); }
const V = 'study/ETF动量/variants/';
[
  {
    id: 'q-e6-0', kind: 'understand', rank: 1, edgeRef: '动量',
    title: 'base 0aa4028d（追电，11 只跨资产 ETF，斜率×R² 持第一）在 epoch-6 台上的真实水平',
    hypothesis: '单持仓日频 ETF 轮动受 pin 影响有限；证伪：objective < 0.05 或 sharpe < 1.0（家族没有可研究的正基线）',
    why: '页面是 09-21 wipe 留下的空脚手架，且是唯一未在 epoch 6 重建的家族；旧 study（baseline..q-12）跑在 22152780 的 50/50 小市值+ETF 混合上，收益由小市值腿承载，不描述本家族的动量机制。base 只有 epoch-2 行（0.2965）',
    design: 'py2to3(0aa4028d)+当前 OVERRIDE → study/ETF动量/baseline-e6.py（build-e6.js），--window train',
    from: ['ledger:0aa4028d@epoch2 obj 0.2965', 'baseline', 'q-1'],
  },
  {
    id: 'q-e6-1', kind: 'understand', rank: 2, edgeRef: '动量',
    title: 'edge test 动量：排序方向反转（持 0<score≤4.8 合格者中得分最低者）',
    hypothesis: '若截面动量有预测力，反排年化损失过半；证伪：反排年化 ≥ base-e6 的 75%',
    why: 'edge 草稿的 test:。子族 [[五福闹新春]] 同一打分反排保留 78%（refuted），[[七星高照]] 7 只池反排保留 22%/42%（measured）——本族 11 只池介于两者之间，是第三个复制点',
    design: `${V}q-1_invert-rank.py：sort_values ascending False→True，单行 diff`,
    from: ['q-e6-0', '五福闹新春:q-e6-1', '七星高照:q-e6-1'],
  },
  {
    id: 'q-e6-2', kind: 'understand', rank: 3, edgeRef: '趋势择时',
    title: 'edge test 趋势择时：去掉 score>0 绝对动量闸门（总持得分第一者）',
    hypothesis: '若闸门是独立来源，Δobj ≤ −0.15；证伪：Δobj > −0.05',
    why: 'edge 草稿第二条的 test:。新成员 0717871e 用同一打分但无闸门、只用 A 股池，TRAIN 年化 −22%、maxDD 41%——它的失败是池子造成的还是缺闸门造成的，须由 q-e6-2 与 q-e6-3 拆开',
    design: `${V}q-2_no-abs-gate.py：df[(score>0)&(score<=4.8)] → df[score<=4.8]，单行 diff`,
    from: ['q-e6-0', 'ledger:0717871e@epoch6 obj -0.6365', '七星高照:q-e6-2'],
  },
  {
    id: 'q-e6-3', kind: 'understand', rank: 4, edgeRef: '动量',
    title: '池子归因：同一打分+闸门+止损，换成 0717871e 的 A 股 4 只池（300/500/创业板/创业板50）',
    hypothesis: '若收益来自打分+闸门这套机制，换到 A 股池仍应显著好于 0717871e 的 −22%（闸门在 2022 熊市躲开）；证伪（=收益属于跨资产池）：objective < 0',
    why: '新成员 0717871e 提出的、本族从未问过的问题：机制 vs 池子。旧 study 全部在混合书上，没有一条测过池子',
    design: `${V}q-3_ashare-pool.py：g.etf_pool 换为 4 只 A 股宽基，其余不动`,
    from: ['ledger:0717871e@epoch6 obj -0.6365', 'q-e6-0'],
  },
  {
    id: 'q-e6-4', kind: 'understand', rank: 5, edgeRef: '趋势择时',
    title: '部件：去掉 −10% 固定止损',
    hypothesis: '日频轮动下 −10% 止损很少先于排名换仓触发；证伪（=止损有作用）：|ΔmaxDD| ≥ 1pp 或 |Δannual| ≥ 2pp',
    why: '唯一的显式风控部件，归属待定',
    design: `${V}q-4_no-stop.py：stop_loss −0.10→−9，单行 diff`,
    from: ['q-e6-0'],
  },
  {
    id: 'q-e6-5', kind: 'understand', rank: 6, edgeRef: '动量',
    title: '部件：去掉 score≤4.8 的「不极端」上限',
    hypothesis: '上限 4.8（年化 380%×R²）在 TRAIN 几乎不咬合；证伪（=上限有作用）：|Δobj| ≥ 0.02',
    why: '作者的「正动量但不极端」滤波，可能是对某次暴涨（如白银）的事后修补',
    design: `${V}q-5_no-cap.py：去掉 score<=4.8，单行 diff`,
    from: ['q-e6-0'],
  },
].forEach(e => rq.add(F, e));
console.log('seeded', rq.load(F).length);
