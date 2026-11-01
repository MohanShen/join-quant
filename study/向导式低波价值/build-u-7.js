// Builds study/向导式低波价值/variants/u-7.py — u-7, the pool-EW CONTROL.
// = baseline.py (py2to3 + live OVERRIDE) + the shared POOL-EW HARNESS (H1/H2/H3 + logging),
// and NOTHING else: the yuan ATR<0.15 entry and the PE 6-11 band stay. u-3/u-4/u-5 build from
// applyHarness() too and add exactly one asserted edit each.
const fs = require('fs');
const path = require('path');
const { loadBase, applyHarness, edit } = require('./pool-ew-harness');
const ROOT = path.join(__dirname, '..', '..');

let src = applyHarness(loadBase());
src = edit(src, src.split('\n')[0] + '\n',
  '# study variant u-7 — family: 向导式低波价值 — pool-EW CONTROL (exit off, max_hold 1000, equal cash split); no screen changed\n' +
  '# built from study/向导式低波价值/baseline.py by study/向导式低波价值/build-u-7.js via pool-ew-harness.js; every edit is marked # HARNESS\n');
for (const keep of ['ATR_judge_xiaoyu(security, 0.15, 14)', 'valuation.pe_ratio, (6,11)', "set_option('avoid_future_data', True)"]) {
  if (!src.includes(keep)) throw new Error('lost: ' + keep);
}
const out = path.join(__dirname, 'variants', 'u-7.py');
fs.writeFileSync(out, src);
console.log('built', path.relative(ROOT, out), 'harness-lines', src.split('\n').filter(l => l.includes('# HARNESS')).length);
