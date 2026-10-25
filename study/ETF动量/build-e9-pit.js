// q-e9-3: POINT-IN-TIME POOL test for the ETF动量 champion 62c2664f under epoch 9.
//
// Rule (fixed before any run, same as study/五福闹新春/build-e9-pit.js):
//   pool = the book's own active etf_pool codes ∩ { 上市日期 < harness.window('train').start }
//
// 62c2664f's pool is 26 BARE codes, several per line, with no inline dates, so every date comes
// from the corpus-wide fallback (another author's `"code", # ... 上市日期：YYYY-MM-DD` comment in
// strategies/). ⚠ A code with NO date anywhere in the corpus makes the builder REFUSE: treating an
// undated code as "pre-cutoff" is a guess, and it is exactly the guess that would bias the test
// toward "no hindsight".
//
//   node study/ETF动量/build-e9-pit.js --dry
//   node study/ETF动量/build-e9-pit.js

const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const harness = require('../../utils/harness-config');

const ROOT = path.join(__dirname, '../..');
const DRY = process.argv.includes('--dry');
const CUT = harness.window('train').start;
const TAG = 'q-e9-3_pit-champion';
const MATCH = /62c2664f/;
const CODE = /["']([0-9]{6}\.(?:XSHG|XSHE))["']/g;

function corpusListingDates() {
  const map = new Map();
  const dir = path.join(ROOT, 'strategies');
  for (const f of fs.readdirSync(dir).filter(x => x.endsWith('.py')).sort()) {
    const t = fs.readFileSync(path.join(dir, f), 'utf8');
    for (const m of t.matchAll(/["']([0-9]{6}\.(?:XSHG|XSHE))["'],\s*#[^\n]*上市日期：(\d{4}-\d{2}-\d{2})/g)) {
      if (!map.has(m[1])) map.set(m[1], { date: m[2], src: f });
    }
  }
  return map;
}

// JQ's own listing dates (preferred over the corpus; both are stamped). Read from two probes on
// the bench, which forces avoid_future_data=True, so get_security_info hides a code that has not
// yet listed on the query date:
//   P1 = study/_probes/probe-etf-start-dates.py,   algorithmId 1727285513adbb79e6f555bbb3398b41,
//        window 2024-01-02..01-05, get_security_info(code).start_date for all 26 codes (23 returned).
//   P3 = study/_probes/probe-etf-start-dates-2.py, algorithmId 9d60e3059ab91919637a0c1cdb387d4b,
//        window TRAIN 2024, daily get_all_securities membership for the 3 hidden codes.
//        Control: 159529 FIRSTSEEN on 2024-02-02, its exact start_date.
// `notBy` = still not listed on that date (P3), so the listing is AFTER it; the exact date cannot
// be observed without a run inside VAL 2025, which this test does not make.
const P1 = 'JQ get_security_info start_date, probe 1727285513adbb79e6f555bbb3398b41';
const P3 = 'JQ get_all_securities membership, probe 9d60e3059ab91919637a0c1cdb387d4b';
const JQ = {
  '513100.XSHG': '2013-05-15', '159509.XSHE': '2023-08-08', '513520.XSHG': '2019-06-25',
  '513030.XSHG': '2014-09-05', '518880.XSHG': '2013-07-29', '159985.XSHE': '2019-12-05',
  '159981.XSHE': '2020-01-17', '501018.XSHG': '2016-06-28', '511260.XSHG': '2017-08-24',
  '513130.XSHG': '2021-06-01', '513690.XSHG': '2021-05-20', '510180.XSHG': '2006-05-18',
  '159915.XSHE': '2011-12-09', '510410.XSHG': '2012-05-11', '515650.XSHG': '2019-11-11',
  '588120.XSHG': '2023-09-15', '159851.XSHE': '2021-03-19', '159637.XSHE': '2022-09-01',
  '516160.XSHG': '2021-02-04', '515250.XSHG': '2021-01-08', '516510.XSHG': '2021-04-07',
  '515050.XSHG': '2019-10-16', '515000.XSHG': '2019-08-16',
};
const JQ_P3 = {
  '159529.XSHE': { date: '2024-02-02' },             // first seen 2024-02-02 = start_date
  '159550.XSHE': { notBy: '2024-12-31' },            // unlisted through all of TRAIN 2024
  '159378.XSHE': { notBy: '2024-12-31' },
};
const CORPUS = corpusListingDates();
const DATES = new Map();
for (const [c, d] of Object.entries(JQ)) DATES.set(c, { date: d, src: P1 });
for (const [c, v] of Object.entries(JQ_P3)) {
  DATES.set(c, v.date ? { date: v.date, src: P3 }
    : { date: '2025-01-01', notBy: v.notBy, src: `${P3} (not listed by ${v.notBy} ⇒ lists 2025+)` });
}
// Cross-check JQ against the corpus wherever both exist; JQ wins, both are stamped.
const disagree = [];
for (const [c, v] of DATES) {
  const k = CORPUS.get(c);
  if (k) { v.corpus = `${k.date} [${k.src}]`; if (k.date !== v.date) disagree.push(`${c} JQ ${v.date} vs corpus ${k.date}`); }
}
for (const [c, k] of CORPUS) if (!DATES.has(c)) DATES.set(c, { date: k.date, src: `corpus ${k.src}` });
console.log(`[pit] JQ-vs-corpus cross-check: ${[...DATES.values()].filter(v => v.corpus).length} overlap, ` +
  `${disagree.length} disagree${disagree.length ? ': ' + disagree.join('; ') : ''}`);
const src = fs.readdirSync(path.join(ROOT, 'strategies')).find(f => MATCH.test(f));
if (!src) throw new Error('no source for 62c2664f');
const raw = py2to3(fs.readFileSync(path.join(ROOT, 'strategies', src), 'utf8'));
const lines = raw.split('\n');

// The pool is the `etf_pool = [ ... ]` literal; read only that block.
const start = lines.findIndex(l => /^etf_pool\s*=\s*\[/.test(l));
const end = lines.findIndex((l, i) => i > start && /^\]/.test(l));
if (start < 0 || end < 0) throw new Error('etf_pool block not found');

const pool = [];
for (let i = start; i <= end; i++) {
  if (/^\s*#/.test(lines[i])) continue;
  for (const m of lines[i].matchAll(CODE)) pool.push({ code: m[1], line: i });
}

const rows = pool.map(p => {
  const d = DATES.get(p.code);
  return { ...p, date: d ? d.date : null, notBy: d && d.notBy, via: d ? d.src : null, corpus: d && d.corpus };
});
const shown = r => r.notBy ? `>${r.notBy}` : r.date;
for (const r of rows) {
  const status = !r.date ? 'NO-DATE' : r.date < CUT ? 'keep' :
    r.date >= '2025-01-01' ? 'EXCLUDE (lists 2025+: VAL-contaminating)' : 'EXCLUDE (listed during TRAIN 2024)';
  console.log(`[pit] ${r.code}  ${shown(r) || '----------'}  ${status}  [${r.via || '-'}]${r.corpus ? '  corpus ' + r.corpus : ''}`);
}
const undated = rows.filter(r => !r.date);
const dropped = rows.filter(r => r.date && r.date >= CUT);
console.log(`[pit] pool ${rows.length}, dated ${rows.length - undated.length}, undated ${undated.length}, ` +
  `excluded ${dropped.length} (2024: ${dropped.filter(d => d.date < '2025-01-01').length}, ` +
  `2025: ${dropped.filter(d => d.date >= '2025-01-01').length}); cutoff ${CUT}`);

if (undated.length) {
  console.error(`[pit] REFUSING: ${undated.length} code(s) have no listing date anywhere in strategies/: ` +
    undated.map(u => u.code).join(' '));
  process.exitCode = 2;
  return;
}
if (!dropped.length) {
  console.log('[pit] nothing excluded — the test would be inert; no variant written');
  return;
}

const kill = new Set(dropped.map(d => d.code));
const out = lines.map((l, i) => {
  if (i < start || i > end || /^\s*#/.test(l)) return l;
  const here = [...l.matchAll(CODE)].map(m => m[1]).filter(c => kill.has(c));
  if (!here.length) return l;
  let o = l;
  for (const c of here) o = o.replace(new RegExp(`["']${c.replace('.', '\\.')}["'],?\\s*`), '');
  return `${o}   # q-e9-3: 移除 ${here.join(' ')}（上市 >= ${CUT}）`;
});

const changed = lines.map((l, i) => [i, l, out[i]]).filter(([, a, b]) => a !== b);
for (const [i, , b] of changed) if (!/q-e9-3:/.test(b)) throw new Error(`line ${i + 1} changed without marker`);
const removed = changed.reduce((n, [, a, b]) => n + ([...a.matchAll(CODE)].length - [...b.split('#')[0].matchAll(CODE)].length), 0);
if (removed !== dropped.length) throw new Error(`removed ${removed} codes but rule excludes ${dropped.length} — refusing`);

const header = [
  '# ============================================================================',
  '# q-e9-3 变体：ETF动量 冠军 62c2664f —— 「点时」池（POINT-IN-TIME POOL）',
  `#   池 = 本书 etf_pool 中的代码 ∩ { 上市日期 < ${CUT} }（截止日读自 harness）`,
  '#   本书池无行内日期；日期以 JQ 自身 start_date 为准（两次探针，见 build-e9-pit.js），',
  '#   语料库内其他作者的行内注释作交叉核对（14 只重叠，全部一致）。',
  ...rows.map(r => `#   ${r.code}  上市 ${shown(r)}  [来源: ${r.via}]` +
    (r.corpus ? `  [语料: ${r.corpus}]` : '') +
    (kill.has(r.code) ? (r.date >= '2025-01-01' ? '  ← 排除（2025+ 上市：TRAIN 不可交易，VAL 可交易）' : '  ← 排除（TRAIN 窗口内上市）') : '')),
  '# 【刻意不碰】排名、动量窗口、择时、阈值、成本块，逐字不动。',
  '# ============================================================================',
  '',
].join('\n');

const file = path.join(__dirname, 'variants', `${TAG}.py`);
if (!DRY) fs.writeFileSync(file, header + out.join('\n') + OVERRIDE);
console.log(DRY ? '[pit] --dry: nothing written' : `[pit] wrote ${path.relative(ROOT, file)}`);
