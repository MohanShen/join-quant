// q-e8-1 (epoch 8 round) for 五福闹新春: degrade the weak-period haven pool from the
// 17 hand-picked overseas/commodity names to ONE canonical haven (gold 518880).
// Same edit site as q-e6-4 (afternoon_routine's weak branch, baseline-e6.py L277-281).
// Plus ONE decision-free log line (WEAKHOLD) so the weak-period holdings census is free.
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');

const ROOT = path.join(__dirname, '../..');
const SRC = path.join(ROOT, 'strategies/2026-07-08_五福闹新春_v5_2-已解密_别再被13_10狙击了_快跑-17b3b439.py');

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

const TO = [
  "        g.merged_etf_pool = ['518880.XSHG']  # q-e8-1: weak period -> ONE canonical haven (gold)",
  '        log.info(f"WEAKHOLD {context.current_dt.date()} {sorted(context.portfolio.positions.keys())}")',
  '',
].join('\n');

const variant = edit(src, FROM, TO) + OVERRIDE;

const outDir = path.join(__dirname, 'variants');
fs.mkdirSync(outDir, { recursive: true });
const outFile = path.join(outDir, 'q-e8-1_weak-gold-only.py');
fs.writeFileSync(outFile, variant);

// ---- visible diff against the baseline ----
const tmp = path.join(require('os').tmpdir(), 'wufu-e8-1-base.py');
fs.writeFileSync(tmp, baseline);
let diff = '';
try {
  execFileSync('diff', ['-u', tmp, outFile], { encoding: 'utf8' });
} catch (e) { diff = e.stdout; }
console.log('\n===== diff baseline-e6.py -> variants/q-e8-1_weak-gold-only.py =====');
console.log(diff);

// ---- assertions: nothing else moved ----
const bl = baseline.split('\n'), vl = variant.split('\n');
const changedBase = bl.filter(l => !vl.includes(l));
console.log('lines present in baseline and absent from variant:', changedBase.length);
changedBase.forEach(l => console.log('  -', l));
const added = vl.filter(l => !bl.includes(l));
console.log('lines added:', added.length);
added.forEach(l => console.log('  +', l));

// the log line must touch no g.* value, no filter, no ordering
const logLine = added.find(l => l.includes('WEAKHOLD'));
if (!logLine) throw new Error('WEAKHOLD log line missing');
if (/\bg\.\w+\s*=/.test(logLine) || /\.sort\(|\.append\(|\.pop\(|del /.test(logLine)) {
  throw new Error('WEAKHOLD line mutates state: ' + logLine);
}
if (!/^\s*log\.info\(f"WEAKHOLD /.test(logLine)) throw new Error('WEAKHOLD line is not a bare log.info');
console.log('WEAKHOLD line is a bare read-only log.info (no assignment, no sort/append/pop/del)');

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
