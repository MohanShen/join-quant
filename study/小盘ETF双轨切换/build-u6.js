// u-6 placebo +5: base 0d1bbe83 + py2to3 + OVERRIDE (frozen pins, as the normalizer applies them)
// + ONE asserted edit: the DDDD entry condition replaced by the base's own 3 偷鸡 DECISION days
// shifted +5 trading days. Decision days 2024-02-20 / 09-30 / 11-21 (consistent() logs
// 当前模式 before deciding, so the first 偷鸡 print is the day AFTER) -> 02-27 / 10-14 / 11-28,
// verified against the base e9 curve's date list (10-01..10-07 National Day closure).
// The DDDD call itself, the 30-day lock, exit-to-摸狗 and everything else verbatim.
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
  "            if context.current_dt.strftime('%Y-%m-%d') in ('2024-02-27', '2024-10-14', '2024-11-28'):  # u-6 placebo +5 (was: variance < g.regime_variance_threshold and mean > 0)\n");
if (v === raw) throw new Error('edit changed nothing');
const diff = raw.split('\n').filter((l, i) => l !== v.split('\n')[i]);
if (diff.length !== 1) throw new Error('expected exactly one changed line, got ' + diff.length);
const out = path.join(__dirname, 'variants/u-6-shift-plus5.py');
fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, v + OVERRIDE);
console.log('built', path.relative(ROOT, out), '| changed line:', diff[0].trim());
