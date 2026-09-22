// One-off: seed the merged-loop queue for the 小市值 epoch-6 round.
const rq = require('../../utils/research-queue');
const F = '小市值';
if (rq.load(F).length) { console.log('queue already seeded'); process.exit(0); }
const V = 'study/小市值/variants/';
[
  {
    id: 'q-e6-0', kind: 'understand', rank: 1, edgeRef: '规模',
    title: 'base 7a1c225f（小市值低开优化）在 epoch-6 台上的真实水平',
    hypothesis: '微盘高换手书在 pin（5% 成交量上限、印花税 0.1%、零滑点）下收益明显缩水；证伪：objective < 0.3 或 sharpe < 2.0（家族头名不再是一个强基线）',
    why: '§3 的 7a1c225f 行（1.3738）是 epoch 2；epoch 4 的 order_volume_ratio=0.05 对微盘逐笔成交可能咬合，没有 epoch-6 基线任何 Δ 都不可比。旧 study（q-1..q-3）也测于 epoch 2',
    design: 'py2to3(7a1c225f)+当前 OVERRIDE → study/小市值/baseline-e6.py（build-e6.js），--window train；年度拆分 yearsplit.js',
    from: ['ledger:7a1c225f@epoch2 obj 1.3738', 'git:51334e3^ study-q-1..q-3'],
  },
  {
    id: 'q-e6-1', kind: 'understand', rank: 2, edgeRef: '规模',
    title: 'edge test 规模：选股池换成市值升序第 1001–2000 名',
    hypothesis: '若规模是收益主体，换池后年化损失过半；证伪：年化 ≥ base-e6 的 75%',
    why: 'edge 草稿的 test:。旧 study 断言「低回撤来自日内机器而非 size」，但从未测过 size 本身——换池是唯一直接的测量',
    design: `${V}q-1_next-1000.py：get_stocks 取 limit(2000) 后 [1000:]，其余不动（排序仍按市值升序、候选仍按买一额/市值排）`,
    from: ['q-e6-0', 'git:51334e3^ §4 size 因子本身 vs 日内机器'],
  },
  {
    id: 'q-e6-2', kind: 'understand', rank: 3, edgeRef: '低开反转',
    title: 'edge test 低开反转：去掉低开入场条件',
    hypothesis: '若低开闸门是选择性来源，去掉后年化损失过半；证伪：年化 ≥ base-e6 的 75%',
    why: 'edge 草稿第二条的 test:。epoch 2 旧 q-2b 测得去掉后年化 148.5→32.7——在 epoch 6 复核，因为 5% 成交量上限可能恰好改变低开日的成交',
    design: `${V}q-2_no-gap.py：is_eligible_for_buy 的条件 4 删除，单处 diff`,
    from: ['q-e6-0', 'git:51334e3^ study-q-2b'],
  },
  {
    id: 'q-e6-3', kind: 'understand', rank: 4, edgeRef: '低开反转',
    title: '部件：关掉 11:30「现价 < 今日开盘价即清仓」（只作用于前日及更早的持仓，T+1）',
    hypothesis: '该退出是收益的存在性部件：关掉后 objective 转负；证伪：Δobj > −0.3',
    why: '旧 q-2a（epoch 2）称其为「日内止损 / EV 转换器」，但代码是 T+1——它是次日起每日的弱势退出，不是日内止损。机理描述错了，量级需在 epoch 6 重测',
    design: `${V}q-3_no-below-open-exit.py：initialize 里的 run_daily(sell, 11:30) 删除`,
    from: ['q-e6-0', 'git:51334e3^ study-q-2a'],
  },
  {
    id: 'q-e6-4', kind: 'understand', rank: 5, edgeRef: '规模',
    title: '部件：1/4 月日历空仓（avoid_months [1,4] → []）',
    hypothesis: '1/4 月财报季微盘回撤真实存在：关掉后 maxDD +3pp 以上；证伪：|ΔmaxDD| < 1pp',
    why: '在本 base 上从未测过；七星旧 q-3 在 406a1e4d 的小市值腿上测得 +4.30pp maxDD，那是另一套机器',
    design: `${V}q-4_no-avoid-months.py：g.avoid_months = []`,
    from: ['q-e6-0', '七星高照:q-3'],
  },
].forEach(e => rq.add(F, e));
console.log('seeded', rq.load(F).length);
