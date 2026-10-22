// q-e9-pit ROUND 2: four more books through the same point-in-time pool rule.
//
// Round 1 (q-e9-pit, q-e9-pit-bba95a11) measured four books and read the result as
// 「hybrids lose nothing, pure ETF momentum loses 19–33%」 at n=2 per group. Round 2 adds four
// and the reading survives on the STOCK-SLEEVE side but acquires a counterexample on the pure
// side, which is why this is recorded as one finding rather than four rows.
const rq = require('../../utils/research-queue');
const h = require('../../utils/harness-config');

const w = h.window('train');
const o = (a, d, s) => h.objective(a, d, s);

// Measured 2026-10-22, 4 runs, 8 JQ min total, each against its own epoch-9 row.
const R = {
  bf30eb36: { base: 1.9437, pit: o(209.36, 12.78, 7.51), shB: 7.44, shP: 7.51, stock: 73 },
  fd5d388d: { base: 1.7890, pit: o(154.12, 17.18, 4.63), shB: 5.96, shP: 4.63, stock: 2 },
  '4d4705e1': { base: 1.7405, pit: o(149.44, 17.18, 4.59), shB: 5.93, shP: 4.59, stock: 2 },
  a722ab8a: { base: 1.5278, pit: o(164.69, 13.57, 5.11), shB: 5.08, shP: 5.11, stock: 4 },
};
const pct = k => ((R[k].pit - R[k].base) / R[k].base * 100).toFixed(1);
const line = k => `${k}: ${R[k].base.toFixed(4)} → ${R[k].pit.toFixed(4)} (${pct(k)}%), ` +
                  `sharpe ${R[k].shB} → ${R[k].shP}`;

rq.recordFinding('五福闹新春', {
  qId: 'q-e9-pit-r2',
  type: 'isolate',
  component_or_param:
    'ETF 池成员资格，同 q-e9-pit 的规则与同一个 builder（study/五福闹新春/build-e9-pit.js，' +
    `新增 BOOKS 条目而非另写一份）：各书自己的池 ∩ { 上市日期 < ${w.start} }。` +
    '四本各排除 17–18 只（其中 7 只 2025 年才上市），排名/动量窗口/择时/阈值/流动性/成本块逐字不动。' +
    '⚠ builder 原先只认单引号，而部分书的池是双引号，所以它把 3c462ece 判为「什么都没改」并' +
    '正确拒绝（而不是产出一个空测试）——四处正则现已同时接受两种引号。',
  metric_delta: [line('bf30eb36'), line('fd5d388d'), line('4d4705e1'), line('a722ab8a')].join(' ‖ '),
  window: `train ${w.start}→${w.end}, 4 runs, 8 JQ min`,
  finding:
    '带「股票腿」的书对池事后性不敏感（3/3：bf30eb36 +1.1%、bba95a11 +0.1%、b50e4387 +1.1%，' +
    '股票相关信号 48–73 处）；纯 ETF 书 4 本中 3 本损失 19–33%，但 a722ab8a 只掉 1.1% —— ' +
    '所以「纯 ETF 必然受损」不成立。',
  confidence: 'high',
  flags:
    '⚠ a722ab8a 是反例：股票信号仅 4 处却几乎不受影响（−1.1%），唯一的结构差异是「三状态」择时层。' +
    '择时可能让它在新 ETF 起作用的时段空仓——这是候选解释，未经检验，不得当成结论 / ' +
    '⚠ fd5d388d(v5.1) 与 4d4705e1(v5.0) 是同一本书的相邻版本，不是独立证据：受限后两者收敛到' +
    '同一个风险画像（maxdd 均 17.18，sharpe 4.63/4.59），即「版本差异」比「池里多了哪些 2024 后上市的名字」' +
    '更不重要——与小市值双胞胎修正后收敛到 0.286 同形 / ' +
    'val-contamination-STILL-UNADDRESSED: 四本池中同样有 7 只 2025 上市名字，而 epoch 9 的 VAL 就是 2025，' +
    'pre-2025 截断的前置条件不变 / single-window',
  description:
    'epoch-9 重测把五本带池的书推进可信区间（objective 1.53–1.94），而本族既有结论是「测得的 edge 是池子」。' +
    'round 1 在 n=2 per group 下读作「hybrid 不损失 / 纯 ETF 损失 19–33%」，样本太小，' +
    '且新上榜的 bf30eb36 是 三马×五福 组合（不是小市值×ETF），属于不同的配对方式，必须单独测。',
  implication:
    '把 round 1 的读法分成两半：**有股票腿 ⇒ 不敏感** 现在是 3/3，且跨两种配对方式（小市值×ETF、三马×五福），' +
    '可以当作结构性结论用于挑选后续候选；**纯 ETF ⇒ 受损** 只是 3/4，必须退回为「通常如此」。' +
    '操作上：fd5d388d 与 4d4705e1 的分数今后必须成对引用（未限制/点时），bf30eb36 与 a722ab8a 可按原值引用。' +
    '下一步若要把 a722ab8a 的反例讲清楚，测的是「三状态」择时层而不是池子。',
  spawned: 'none',
  edgeRef: '动量',
});

console.log('[record] q-e9-pit-r2 written to study/五福闹新春/findings.tsv');
