// Record the epoch-9 point-in-time pool result as a finding on 五福闹新春.
//
// Run once; `recordFinding` appends and also closes the matching queue entry.
const rq = require('../../utils/research-queue');
const h = require('../../utils/harness-config');

const w = h.window('train');
const obj = (annual, maxdd, sharpe) => h.objective(annual, maxdd, sharpe);

// Measured 2026-10-18/19 on the epoch-9 bench. The unrestricted figures are the books' own
// ledger rows from the re-measurement; the restricted ones are q-e9-pit.
const PIT = obj(115.74, 15.49, 3.66);     // 1.0025
const PIT2 = obj(90.29, 9.61, 3.77);      // 0.8068

rq.recordFinding('五福闹新春', {
  qId: 'q-e9-pit',
  type: 'isolate',
  component_or_param:
    'ETF 池成员资格：两本高分书各自的 g.global_etf_pool + g.china_etf_pool ∩ { 上市日期 < ' +
    `${w.start} }（study/五福闹新春/build-e9-pit.js；规则跑前固定、零自由度：名单来自书自身源码，` +
    '上市日来自同几行作者自己的行内注释，上市日是证券属性而非业绩数据）。排除的名字就地注释掉，' +
    'builder 断言「被改动的行恰好等于被排除的行」，排名/动量窗口/择时/阈值/流动性/成本块逐字不动。',
  metric_delta:
    `73b13d92: objective 1.4926 → ${PIT.toFixed(4)} (−0.4901, −33%)，sharpe 5.22 → 3.66，` +
    'total 115.74% / maxdd 15.49（排除 17 只，池内仍有 97 只） ‖ ' +
    `1cc495be: objective 0.9954 → ${PIT2.toFixed(4)} (−0.1886, −19%)，sharpe 4.59 → 3.77，` +
    'total 90.29% / maxdd 9.61（排除 16 只，仍有 99 只）。两本都远过 epoch-9 的 1.0 闸门。',
  window: `train ${w.start}→${w.end}, 2 runs, ~11 JQ min`,
  finding:
    '把池限制为「窗口开始前已上市」后，两本书各损失 33% 与 19% 的 objective，但都保持 sharpe 3.66 / 3.77、' +
    'objective 1.0025 / 0.8068，稳稳过闸。池子确实在美化结果，但没有解释结果。',
  confidence: 'high',
  flags:
    '⚠ 不是 ETF动量 的模式：那边换成宽基 A 股池后掉到 −0.27，这里只掉三分之一 / 五分之一 / ' +
    'val-contamination-UNADDRESSED: 本测只管 TRAIN。池中有 7 只在 2025 年才上市（159323、159206、' +
    '588170、159218、159227、588790、159256），而 epoch 9 的 VAL 正是 2025 —— 一个 2026 年写下的池子' +
    '含有「验证年内才上市」的名字，等于把选择偏差写进了源码。VAL 必须至少用 pre-2025 截断。 / ' +
    'selection-hindsight-residual: 上市日规则消掉的是「上市日期」的事后性，不是「资产类别」的事后性；' +
    '剩下 97/99 只仍是 2026 年作者的类别选择 / single-window',
  description:
    'epoch 9 把 TRAIN 移到 2024，两本 ETF 动量书成了全库最强（1.4926 / 0.9954）。本族既有结论是' +
    '「测得的 edge 是池子而不是排序」（ETF动量 换宽基池 → −0.27；七星高照 池「事后选择且不可替换」），' +
    '而 epoch 9 并不缓解这个问题、反而让它更尖锐：可得性那一半改善了（2026 年的池子到 2024 多半已存在，' +
    '而旧 TRAIN 下 17 只里有 8 只晚于 2022-01-01），但选择那一半更糟（窗口离写池子的时点只剩约两年，' +
    '旧窗口是四年）。所以这一测是在问：这个 2024 的强度里有多少是事后选池子选出来的。答案是三分之一以下。',
  implication:
    '把「2024 的 ETF 动量强度主要是事后选池」这条怀疑关掉：限制为点时池后两本都仍过闸，所以后续可以把' +
    '这两本当作真实候选继续做，而不必先推翻池子。相应地开出两条新约束：(1) 本族任何 VAL 都必须先做' +
    'pre-2025 截断，否则验证窗口自带选择偏差——这是比 TRAIN 更严重的一半，且本测没有触及；(2) 引用这两本' +
    '的分数时必须成对引用（未限制 / 点时），因为未限制值高出 19–33%，单独引用会系统性高报。' +
    '同时把同一测试开给新的全库第一 bba95a11（objective 1.7881，池结构相同：115 只中 18 只晚于 2024-01-01）。',
  spawned: 'q-e9-pit-bba95a11',
  edgeRef: '动量',
});

console.log('[record] q-e9-pit written to study/五福闹新春/findings.tsv');
