// q-e6-6: sensitivity of the weak-period R² gate that imp-6 just found (+0.0480).
// Adds a SEPARATE weak-period threshold so the normal period is untouched, and sets it to 0.5.
// One mechanism, one level change; plateau vs cliff is the whole question.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');

const ROOT = path.join(__dirname, '../..');
const BASE = path.join(ROOT, 'strategies/2026-07-08_五福闹新春_v5_2-已解密_别再被13_10狙击了_快跑-17b3b439.py');

function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${from}`);
  return s.replace(from, to);
}

let s = py2to3(fs.readFileSync(BASE, 'utf8'));
// imp-6's H78a, plus its own weak-period threshold
s = edit(s, '    g.enable_r2_filter = True\n',
  '    g.enable_r2_filter = True\n    g.enable_weak_r2_filter = True  # imp-6 (H78a)\n' +
  '    g.weak_r2_threshold = 0.5  # q-e6-6: weak-period gate at 0.5 (imp-6 used 0.4)\n');
s = edit(s, "            'passed_r2': passed_r2,\n",
  "            'passed_r2': passed_r2,\n" +
  "            'passed_r2_weak': r_squared > getattr(g, 'weak_r2_threshold', g.r2_threshold),  # q-e6-6\n");
s = edit(s,
  "        ('R²', lambda m: m['passed_r2'], g.enable_r2_filter and not g.is_a_share_weak),\n",
  "        ('R²', lambda m: m['passed_r2'], g.enable_r2_filter and not g.is_a_share_weak),\n" +
  "        ('R²走弱', lambda m: m['passed_r2_weak'],\n" +
  "         getattr(g, 'enable_weak_r2_filter', False) and g.is_a_share_weak),  # q-e6-6\n");
fs.writeFileSync(path.join(__dirname, 'variants', 'q-6_weak-r2-050.py'), s + OVERRIDE);
console.log('built q-6_weak-r2-050');
