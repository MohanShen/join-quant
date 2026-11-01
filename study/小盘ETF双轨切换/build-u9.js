// u-9 always-摸狗: base 0d1bbe83 + py2to3 + OVERRIDE (frozen pins, as the normalizer applies them)
// + ONE asserted edit: the DDDD breadth trigger in consistent() forced FALSE, so 偷鸡 is never entered.
// 摸狗 ranking, 4-ETF pool, 30-day lock code and 14:00 check_limit_up verbatim (the latter inert: no stocks).
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
  '            if False:  # u-9: DDDD trigger forced false (was: variance < g.regime_variance_threshold and mean > 0)\n');
if (v === raw) throw new Error('edit changed nothing');
const diff = raw.split('\n').filter((l, i) => l !== v.split('\n')[i]);
if (diff.length !== 1) throw new Error('expected exactly one changed line, got ' + diff.length);
const out = path.join(__dirname, 'variants/u-9-always-mogou.py');
fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, v + OVERRIDE);
console.log('built', path.relative(ROOT, out), '| changed line:', diff[0].trim());
