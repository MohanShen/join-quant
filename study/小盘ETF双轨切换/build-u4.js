// u-4 momentum inversion: base 0d1bbe83 + py2to3 + OVERRIDE (frozen pins, as the normalizer applies them)
// + ONE asserted edit: get_rank's 摸狗 sort ascending=False -> True (pick the WORST-momentum ETF).
// DDDD and the 偷鸡 leg verbatim.
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
  "    df = df.sort_values(by='score', ascending=False)\n",
  "    df = df.sort_values(by='score', ascending=True)  # u-4 momentum inversion (was: ascending=False)\n");
if (v === raw) throw new Error('edit changed nothing');
const diff = raw.split('\n').filter((l, i) => l !== v.split('\n')[i]);
if (diff.length !== 1) throw new Error('expected exactly one changed line, got ' + diff.length);
const out = path.join(__dirname, 'variants/u-4-mom-inverted.py');
fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, v + OVERRIDE);
console.log('built', path.relative(ROOT, out), '| changed line:', diff[0].trim());
