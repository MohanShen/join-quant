// q-e9-pit: POINT-IN-TIME POOL test for the two high-scoring ETF books under epoch 9.
//
// ## Why
//
// Epoch 9 (TRAIN 2024) produced the library's two strongest rows, both ETF-momentum books from
// the family whose pool CLAUDE.md records as 「写于 2026」:
//
//     73b13d92  五福_ETF_轮动五年迭代        sharpe 5.22  objective 1.4926
//     1cc495be  给五福多ETF动量增加卖出冷却   sharpe 4.59  objective 0.9954
//
// The family's measured edge was established to be the POOL, not the ranking (ETF动量's own
// 11-ETF pool scored −0.27 when swapped for a broad A-share pool; 七星高照's is
// 「事后选择且不可替换」). Epoch 9 does not fix that and plausibly sharpens it: a pool assembled
// in 2026 was chosen knowing what worked through 2024, and the window now sits ~2 years from the
// authoring date instead of 4.
//
// ## The rule — fixed before the run, zero free parameters
//
//   pool = the book's OWN active names (g.global_etf_pool + g.china_etf_pool)
//          ∩ { 上市日期 < 2024-01-01 }
//
// Both inputs are pre-run facts taken from the book itself: the names are its source, and the
// listing dates are the AUTHOR'S OWN inline comments on the same lines. A listing date is a
// security attribute, not performance data, so the rule cites no 2024 price, return, volume or
// ranking. Same rule as q-e8-7, with the cutoff moved to the active TRAIN start.
//
// ## What the audit found (and why this is not only a TRAIN question)
//
// These books carry ~114 active names, not 17, and **17 of them list after 2024-01-01**:
//
//   10 list DURING train 2024  — tradeable only from their listing day, chosen knowing 2024
//    7 list in 2025            — NOT tradeable in TRAIN at all ... but tradeable in VAL 2025
//
// ⚠⚠ The second group is the serious one. Epoch 9's VAL is 2025, so a pool authored in 2026
// containing seven names that listed during 2025 has selection-on-VAL built into the source. VAL
// is ONE shot per (family, bench) and epoch 9 just granted this family a fresh one — so a VAL on
// the unrestricted book would spend the family's only validation on a pool picked knowing 2025.
// A VAL on these books needs AT LEAST a pre-2025 cutoff; this file only settles TRAIN.
//
// ## Method
//
// The excluded lines are COMMENTED OUT in place — the smallest possible edit, auditable line by
// line, and it leaves the author's own listing-date comment visible next to each exclusion.
// Nothing else is touched: no ranking change, no threshold change, no liquidity change.
//
//   node study/五福闹新春/build-e9-pit.js --dry
//   node study/五福闹新春/build-e9-pit.js

const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const harness = require('../../utils/harness-config');

const ROOT = path.join(__dirname, '../..');
const OUT = __dirname;
const DRY = process.argv.includes('--dry');

// The cutoff is the ACTIVE train start, read from the harness — never written down, so this
// builder stays correct if the window moves again.
const CUT = harness.window('train').start;

const BOOKS = [
  { tag: 'q-e9-pit_73b13d92', match: /73b13d92/, label: '五福_ETF_轮动五年迭代' },
  { tag: 'q-e9-pit_1cc495be', match: /1cc495be/, label: '给五福多ETF动量增加卖出冷却' },
];

const header = (label, cut, dropped) => [
  '# ============================================================================',
  `# q-e9-pit 变体：${label} —— 「点时」池（POINT-IN-TIME POOL）`,
  '#',
  '# 【成员资格规则 —— 跑前固定，零自由度】',
  '#   池 = 本书自己的 g.global_etf_pool + g.china_etf_pool 中所有未被作者注释掉的名字',
  `#        ∩ { 上市日期 < ${cut} }`,
  '#   两个输入都是跑前可查的事实：名单来自本书源码；上市日来自同几行作者自己的行内注释',
  '#   （上市日是证券属性，不是业绩数据）。本规则不引用任何 2024 年的价格、收益、成交额或排名。',
  '#',
  `# 【被排除的 ${dropped.length} 只 —— 一只都不得放回】`,
  ...dropped.map(d => `#   ${d.code}  上市 ${d.date}${d.date >= '2025-01-01' ? '   ← 2025 才上市：TRAIN 完全不可交易，但 VAL(2025) 可交易' : '   ← TRAIN 窗口内上市'}`),
  '#',
  '# 【刻意不碰】排名、动量窗口、择时、阈值、流动性过滤、成本块，全部逐字不动。',
  '#   唯一的改动是把上述名字在池中注释掉。',
  '# ============================================================================',
  '',
].join('\n');

const built = [];
for (const b of BOOKS) {
  const src = fs.readdirSync(path.join(ROOT, 'strategies')).find(f => b.match.test(f));
  if (!src) throw new Error(`no source for ${b.tag}`);
  const raw = py2to3(fs.readFileSync(path.join(ROOT, 'strategies', src), 'utf8'));

  const dropped = [];
  const out = raw.split('\n').map((l) => {
    const m = l.match(/^(\s*)'([0-9]{6}\.(?:XSHG|XSHE))',\s*#(.*)$/);
    if (!m) return l;
    if (/^\s*#/.test(l)) return l;                      // already inactive in the author's source
    const date = (m[3].match(/上市日期：(\d{4}-\d{2}-\d{2})/) || [])[1];
    if (!date || date < CUT) return l;                  // no date, or genuinely pre-window
    dropped.push({ code: m[2], date });
    return `${m[1]}#${l.trim()}   # q-e9-pit: 上市 ${date} >= ${CUT}`;
  }).join('\n');

  // ⚠ Assert the edit did exactly what the rule says, and nothing else: the only differences
  // between raw and out must be the commented lines.
  const diff = raw.split('\n').filter((l, i) => l !== out.split('\n')[i]).length;
  if (diff !== dropped.length) {
    throw new Error(`${b.tag}: ${diff} line(s) changed but ${dropped.length} excluded — refusing`);
  }
  if (!dropped.length) throw new Error(`${b.tag}: nothing to exclude — the test would be inert`);

  const file = path.join(OUT, `${b.tag}.py`);
  const text = header(b.label, CUT, dropped) + out + OVERRIDE;
  if (!DRY) fs.writeFileSync(file, text);
  built.push({ tag: b.tag, src, dropped: dropped.length,
               in2025: dropped.filter(d => d.date >= '2025-01-01').length });
  console.log(`[pit] ${b.tag}: excluded ${dropped.length} name(s) listed >= ${CUT} ` +
              `(${dropped.filter(d => d.date >= '2025-01-01').length} of them only from 2025)`);
}

console.log(`[pit] cutoff ${CUT} (active TRAIN start, read from the harness)`);
if (DRY) console.log('[pit] --dry: nothing written');
else {
  console.log('[pit] run each against its own epoch-9 row:');
  console.log('      73b13d92 objective 1.4926 / sharpe 5.22');
  console.log('      1cc495be objective 0.9954 / sharpe 4.59');
}
