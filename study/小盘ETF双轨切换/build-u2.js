// u-2 calendar substitute: base 0d1bbe83 + py2to3 + OVERRIDE (frozen pins, as the normalizer applies them)
// + ONE asserted edit: the DDDD breadth condition in consistent() replaced by `month not in (1, 4)`.
// The DDDD(context) call line is kept (it still runs, result ignored). 30-day lock verbatim.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const ROOT = path.join(__dirname, '../..');
const SRC = 'strategies/2026-10-12_年化51_的晴雨双轨_小盘游击_ETF防御-0d1bbe83.py';
function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${JSON.stringify(from)}`);
  return s.replace(from, to);
}
const raw = py2to3(fs.readFileSync(path.join(ROOT, SRC), 'utf8'));
const v = edit(raw,
  '            if variance < g.regime_variance_threshold and mean > 0:\n',
  '            if context.current_dt.month not in (1, 4):  # u-2: calendar substitute (was: variance < g.regime_variance_threshold and mean > 0)\n');
if (v === raw) throw new Error('edit changed nothing');
const diff = raw.split('\n').filter((l, i) => l !== v.split('\n')[i]);
if (diff.length !== 1) throw new Error('expected exactly one changed line, got ' + diff.length);
const out = path.join(__dirname, 'variants/u-2-calendar.py');
fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, v + OVERRIDE);
console.log('built', path.relative(ROOT, out), '| changed line:', diff[0].trim());
