// One-off: seed the merged-loop queue for the 七星高照 epoch-6 round.
const rq = require('../../utils/research-queue');
const F = '七星高照';
if (rq.load(F).length) { console.log('queue already seeded'); process.exit(0); }
const V = 'study/七星高照/variants/';
[
  {
    id: 'q-e6-0', kind: 'understand', rank: 1, edgeRef: '动量',
    title: 'base 19ca0e69（七星 V1.7，纯 7-ETF 轮动）在 epoch-6 台上的真实水平',
    hypothesis: '日频单持仓 ETF 轮动在 pin（基金佣金 2bp→3bp、滑点 1bp→0、5% 成交量上限）下收益明显缩水；证伪：objective < 0.05 或 sharpe < 1.0（家族连一个可研究的正基线都没有）',
    why: '家族 §3 全部是 epoch 2；旧 study（q-1..q-5）跑在 406a1e4d 的 50/50 小市值+七星混合上，其头条 0.4814 主要由小市值腿承载（旧 q-2），不描述本家族同名腿。没有 epoch-6 的纯七星基线，任何 Δ 都不可比',
    design: 'py2to3(19ca0e69)+当前 OVERRIDE → study/七星高照/baseline-e6.py（build-e6.js），--window train；年度拆分用 yearsplit.js',
    from: ['ledger:19ca0e69@epoch2 obj 0.1412', 'baseline', 'q-1', 'q-2'],
  },
  {
    id: 'q-e6-1', kind: 'understand', rank: 2, edgeRef: '动量',
    title: 'edge test 动量：排序方向反转（持通过全部滤波的得分最低者）',
    hypothesis: '若截面动量有预测力，反排年化损失过半；证伪：反排年化 ≥ base-e6 年化的 75%',
    why: 'edge 草稿的 test:。姊妹 [[五福闹新春]] 用同一套斜率×R² 打分，反排保留 78% 年化（动量 refuted）；七星池只有 7 只、且资产类别彼此差异大，截面排序在这里可能更有意义——这是一次跨家族复制，不是重复',
    design: `${V}q-1_invert-rank.py：get_ranked_etfs 的 sort reverse=True→False，单行 diff`,
    from: ['q-e6-0', '五福闹新春:q-e6-1'],
  },
  {
    id: 'q-e6-2', kind: 'understand', rank: 3, edgeRef: '趋势择时',
    title: 'edge test 趋势择时：关掉正趋势闸门（总持有池内得分第一者，除非被跌幅/盈利保护滤掉）',
    hypothesis: '若绝对动量闸门是独立来源，Δobj ≤ −0.15；证伪：Δobj > −0.05',
    why: 'edge 草稿第二条的 test:。无合格 ETF 时退 511880，是本族唯一的择时部件；[[五福闹新春]] 的 edge 正是择时躲避而非选强',
    design: `${V}q-2_no-trend-gate.py：min_score_threshold 0→−1e9 且 use_short_momentum_filter True→False（同一概念的两行）；3 日跌幅与盈利保护照旧`,
    from: ['q-e6-0', '五福闹新春:q-e6-2'],
  },
  {
    id: 'q-e6-3', kind: 'understand', rank: 4, edgeRef: '动量',
    title: '集中度：持全部通过滤波的 ETF 等权（holdings_num 1→7），而不是第一名',
    hypothesis: '若集中于第一名是来源，等权持全部合格者年化显著下降、回撤下降；证伪：年化 ≥ base 的 90%',
    why: '与 q-e6-1 配对：反排检验「第一名 vs 最后一名」，本题检验「第一名 vs 全部合格者的平均」，两者合起来才能说排序有没有信息',
    design: `${V}q-3_hold-all.py：holdings_num 1→7，单行 diff`,
    from: ['q-e6-0'],
  },
  {
    id: 'q-e6-4', kind: 'understand', rank: 5, edgeRef: '趋势择时',
    title: '部件：关掉盈利保护（持仓较昨日最高价回撤 5% 即卖、并从排名剔除）',
    hypothesis: '盈利保护是回撤压制器：关掉后 maxDD +2pp 以上；证伪：|ΔmaxDD| < 1pp 且 |Δannual| < 2pp（惰性）',
    why: 'V1.7 的版本卖点（独立拆分的盈利保护）；5% 单日回撤阈值对 ETF 很宽，可能几乎不触发',
    design: `${V}q-4_no-profit-protection.py：enable_profit_protection True→False，单行 diff`,
    from: ['q-e6-0'],
  },
  {
    id: 'q-e6-5', kind: 'understand', rank: 6, edgeRef: '趋势择时',
    title: '部件：关掉近 3 日单日跌幅 >3% 的排除（loss 0.97→0）',
    hypothesis: '该排除是回撤压制器：关掉后 maxDD 上升；证伪：|ΔmaxDD| < 1pp 且 |Δannual| < 2pp（惰性）',
    why: '白银/原油/纳指单日 >3% 跌幅常见，这条可能频繁把第一名踢出、改变持仓',
    design: `${V}q-5_no-loss-filter.py：loss 0.97→0.0，单行 diff`,
    from: ['q-e6-0'],
  },
].forEach(e => rq.add(F, e));
console.log('seeded', rq.load(F).length);
