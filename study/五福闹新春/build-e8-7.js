// q-e8-7 (epoch 8 round) for 五福闹新春: BREADTH-BALANCED point-in-time haven pool.
// Clone of build-e8-1.js. Same edit site (afternoon_routine's weak branch, baseline-e6.py
// L277-281 — the site q-e6-4 and q-e8-1 both used), same edit SHAPE, same bypass of
// g.filtered_global_pool. The ONLY difference vs q-e8-1 is the slot count: 1 -> 9.
// Plus q-e8-1's verbatim decision-free WEAKHOLD log line.
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');

const ROOT = path.join(__dirname, '../..');
const SRC = path.join(ROOT, 'strategies/2026-07-08_五福闹新春_v5_2-已解密_别再被13_10狙击了_快跑-17b3b439.py');

// ---- membership rule, fixed before the run; stamped into the variant's own header ----
const HEADER = [
  '# ============================================================================',
  '# q-e8-7 变体：走弱期避险池 = 广度配平的「点时」池（N=9）',
  '#',
  '# 【成员资格规则 —— 跑前固定，零自由度】',
  '#   池 = base 自己的 g.global_etf_pool（17 只，baseline-e6.py L25-46）',
  '#        ∩ { 上市日 < 2022-01-01 }',
  '#   两个输入都是跑前可查的事实：17 只名单来自 base 源码；上市日来自同几行作者自己的',
  '#   行内注释（上市日是证券属性，不是业绩数据）。本规则不引用任何 2022–2023 的价格、',
  '#   收益、成交额或排名。',
  '#',
  '# 【入选 9 只（逐字，不排序、不去重、不补充）】',
  "#   '518880.XSHG'  黄金ETF        上市 2013-07-29",
  "#   '513100.XSHG'  纳指ETF        上市 2013-05-15",
  "#   '513500.XSHG'  标普500        上市 2014-01-15",
  "#   '513030.XSHG'  德国ETF        上市 2014-09-05",
  "#   '161226.XSHE'  国投白银LOF    上市 2015-08-17",
  "#   '501018.XSHG'  南方原油LOF    上市 2016-06-28",
  "#   '513520.XSHG'  日经ETF        上市 2019-06-25",
  "#   '159985.XSHE'  豆粕ETF华夏    上市 2019-12-05",
  "#   '159980.XSHE'  有色ETF大成    上市 2019-12-24",
  '#',
  '# 【被排除的 8 只（上市 ≥ 2022-01-01），一只都不得放回】',
  '#   513290 (2022-08-29)、513310 (2022-12-22)、159509 (2023-08-08)、159518 (2023-11-15)',
  '#       ← 这 4 只在 TRAIN 窗口内上市',
  '#   159502 (2024-01-10)、513400 (2024-02-02)、159529 (2024-02-02)、520830 (2024-07-16)',
  '#       ← 这 4 只在 TRAIN 之后上市',
  '#',
  '# 【刻意不碰】g.filtered_global_pool 被绕过（与 q-e8-1 完全一致），即走弱期不做流动性',
  '#   过滤 —— 否则 q-e8-7 与 q-e8-1 就不只差「名额数」一个维度。流动性是 q-e8-3 的题。',
  '# 其余一切逐字不动：择时触发、R²/MA 滤波、候选系数 0.9、20 日上限、13:10 三条',
  '#   run_daily、止损、防御 ETF 511880、epoch-8 成本块。',
  '# ============================================================================',
  '',
].join('\n');

function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${JSON.stringify(from)}`);
  console.log(`edit matched exactly once (${from.trim().split('\n')[0].slice(0, 48)}...)`);
  return s.replace(from, to);
}

const src = py2to3(fs.readFileSync(SRC, 'utf8'));
const baseline = src + OVERRIDE;

// sanity: the generated baseline must equal the committed baseline-e6.py
const committed = fs.readFileSync(path.join(__dirname, 'baseline-e6.py'), 'utf8');
if (committed !== baseline) throw new Error('regenerated baseline != committed baseline-e6.py');
console.log('baseline-e6.py reproduced byte-identically from strategies/ + OVERRIDE');

const FROM = [
  "        if hasattr(g, 'filtered_global_pool') and g.filtered_global_pool:",
  '            g.merged_etf_pool = list(set(g.filtered_global_pool))',
  '        else:',
  '            g.merged_etf_pool = list(set(g.global_etf_pool))',
  '        g.merged_etf_pool.sort()',
  '',
].join('\n');

const POOL = [
  '518880.XSHG', '513100.XSHG', '513500.XSHG', '513030.XSHG', '161226.XSHE',
  '501018.XSHG', '513520.XSHG', '159985.XSHE', '159980.XSHE',
];
if (POOL.length !== 9) throw new Error('pool must hold exactly 9 names');
if (new Set(POOL).size !== 9) throw new Error('pool has duplicates');

const TO = [
  `        g.merged_etf_pool = [${POOL.map(s => `'${s}'`).join(',')}]  # q-e8-7: weak period -> 9 point-in-time havens (base's own 17 listed before 2022-01-01)`,
  '        log.info(f"WEAKHOLD {context.current_dt.date()} {sorted(context.portfolio.positions.keys())}")',
  '',
].join('\n');

const variant = HEADER + edit(src, FROM, TO) + OVERRIDE;

const outDir = path.join(__dirname, 'variants');
fs.mkdirSync(outDir, { recursive: true });
const outFile = path.join(outDir, 'q-e8-7_weak-pit9.py');
fs.writeFileSync(outFile, variant);

// ---- visible diff against the baseline ----
const tmp = path.join(require('os').tmpdir(), 'wufu-e8-7-base.py');
fs.writeFileSync(tmp, baseline);
let diff = '';
try {
  execFileSync('diff', ['-u', tmp, outFile], { encoding: 'utf8' });
} catch (e) { diff = e.stdout; }
console.log('\n===== diff baseline-e6.py -> variants/q-e8-7_weak-pit9.py =====');
console.log(diff);

// ---- assertions: nothing else moved ----
const bl = baseline.split('\n'), vl = variant.split('\n');
const changedBase = bl.filter(l => !vl.includes(l));
console.log('lines present in baseline and absent from variant:', changedBase.length);
changedBase.forEach(l => console.log('  -', l));
const added = vl.filter(l => !bl.includes(l));
const codeAdded = added.filter(l => !/^#/.test(l) && l.trim() !== '');
console.log('code lines added (header comments excluded):', codeAdded.length);
codeAdded.forEach(l => console.log('  +', l));

// the log line must touch no g.* value, no filter, no ordering
const logLines = codeAdded.filter(l => /^\s*log\.info\(f"WEAKHOLD /.test(l));
if (logLines.length !== 1) throw new Error(`expected exactly 1 WEAKHOLD log line, got ${logLines.length}`);
const logLine = logLines[0];
if (/\bg\.\w+\s*=/.test(logLine) || /\.sort\(|\.append\(|\.pop\(|del /.test(logLine)) {
  throw new Error('WEAKHOLD line mutates state: ' + logLine);
}
console.log('WEAKHOLD line is a bare read-only log.info (no assignment, no sort/append/pop/del)');

// the pool assignment must be a literal list: no filtered_global_pool, no set(), no sort
const poolLine = codeAdded.find(l => l.includes('g.merged_etf_pool ='));
if (!poolLine) throw new Error('pool assignment line missing');
if (/filtered_global_pool|set\(|\.sort\(|global_etf_pool/.test(poolLine.split('#')[0])) {
  throw new Error('pool line is not a bare literal: ' + poolLine);
}
for (const s of POOL) if (!poolLine.includes(`'${s}'`)) throw new Error('pool line missing ' + s);
const EXCLUDED = ['513290', '513310', '159509', '159518', '159502', '513400', '159529', '520830'];
for (const s of EXCLUDED) if (poolLine.includes(s)) throw new Error('excluded name restored: ' + s);
console.log(`pool line is a 9-name literal, bypasses filtered_global_pool, restores none of the 8 excluded`);

// everything else must be byte-identical: cost block, state machine, MA filter, stop, retention
for (const marker of [
  'g.enable_r2_filter = True',
  'weak_condition_met = (below_count >= 3)',
  'g.max_weak_days = 20',
  'g.score_threshold_ratio = 0.9',
  'g.defensive_etf = "511880.XSHG"',
  '_ORIG_SET_ORDER_COST',
]) {
  const a = baseline.split(marker).length - 1, b = variant.split(marker).length - 1;
  if (a !== b) throw new Error(`marker count changed for ${marker}: ${a} -> ${b}`);
}
console.log('untouched markers verified (breadth gate, 20d cap, 0.9 coefficient, defensive ETF, OVERRIDE)');
console.log('\nwrote', path.relative(ROOT, outFile));
