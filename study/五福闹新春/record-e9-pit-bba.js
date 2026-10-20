// Answer the idea q-e9-pit spawned: the same point-in-time pool rule on bba95a11, the library's
// top book under epoch 9.
//
// ⚠ The finding is recorded on 五福闹新春 because that is where the q-e9-pit CHAIN lives (this
// closes the entry q-e9-pit spawned, and the rule/builder are shared). The BOOK itself is assigned
// to 小市值 (`wiki/strategies/bba95a11_小市值+五福组合.md`), so its §2 row goes on that page —
// a combination book belongs to its lineage, the finding belongs to the question it answers.
const rq = require('../../utils/research-queue');
const h = require('../../utils/harness-config');

const w = h.window('train');
const PIT = h.objective(187.47, 8.51, 7.10);   // 1.7896

rq.recordFinding('五福闹新春', {
  qId: 'q-e9-pit-bba95a11',
  type: 'isolate',
  component_or_param:
    'ETF 池成员资格，同 q-e9-pit 的规则与同一个 builder（study/五福闹新春/build-e9-pit.js，' +
    `新增一个 BOOKS 条目而非另写一份，这样成员资格规则不会在书之间漂移）：bba95a11 自己的池 ∩ ` +
    `{ 上市日期 < ${w.start} }，排除 18 只（池内仍有 98 只），其中 7 只是 2025 年才上市。` +
    '排除的名字就地注释掉；排名/动量窗口/择时/阈值/流动性/成本块逐字不动。',
  metric_delta:
    `bba95a11: objective 1.7881 → ${PIT.toFixed(4)}（**+0.0015**），sharpe 6.99 → 7.10（+0.11），` +
    'total 187.47% / maxdd 8.51。对照同一测试的两本：73b13d92 −33%、1cc495be −19%。',
  window: `train ${w.start}→${w.end}, 1 run, ~6 JQ min`,
  finding:
    '全库第一的 bba95a11 在点时池下**完全不变**：objective 1.7881 → 1.7896，受限池反而略好一点点。' +
    '把 18 只窗口开始后才上市的名字全部拿掉，结果没有移动。',
  confidence: 'high',
  flags:
    '⚠ 比另两本干净得多：同一规则在 73b13d92 上拿掉 33%、在 1cc495be 上拿掉 19%，在这里是 +0.0015 / ' +
    'val-contamination-STILL-UNADDRESSED: 本书池中同样有 7 只 2025 年上市的名字，而 epoch 9 的 VAL ' +
    '就是 2025。TRAIN 干净不等于 VAL 干净，pre-2025 截断的前置条件对本书同样成立 / ' +
    'selection-hindsight-residual: 消掉的是上市日期的事后性，不是资产类别的事后性 / ' +
    'book-is-小市值: 本书 family: 小市值（小市值+五福组合），不是 五福闹新春 的成员；本条记在这里是因为' +
    '它回答的是 q-e9-pit 开出的问题 / single-window',
  description:
    'q-e9-pit 把「2024 的 ETF 动量强度主要是事后选池」这条怀疑关掉了一半：两本书各掉 33% / 19% 但都过闸。' +
    '随后 epoch-9 重测产出了新的全库第一 bba95a11（objective 1.7881 / sharpe 6.99），池结构相同' +
    '（115 只带行内上市日，18 只晚于 2024-01-01），所以同一测试必须施于它，否则全库最高分就是未经检验的。' +
    '结果比前两本更强：不是「损失可接受」，而是「没有损失」。',
  implication:
    '把全库最高分从「待检验」移到「池子上已检验」：bba95a11 的 2024 强度不含任何池事后性，所以它是' +
    '当前最可信的高分书，后续研究应优先于前两本（它们各有 19–33% 的池加成）。' +
    '相应地也改变怎么读 q-e9-pit 的结论：池加成的大小因书而异（0% / 19% / 33%），所以不能把' +
    '「ETF 池都带事后性」当成本族的统一属性 —— 必须逐本测。' +
    '⚠ 不改变 VAL 前置条件：本书同样含 7 只 2025 上市名字，任何 VAL 仍须先做 pre-2025 截断。',
  spawned: 'none',
  edgeRef: '动量',
});

console.log('[record] q-e9-pit-bba95a11 written to study/五福闹新春/findings.tsv');
