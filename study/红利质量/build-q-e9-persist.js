// q-e9-persist — baseline.py with TWO asserted edits (the edge 分红持续性筛选 is both together):
// SCHD_MIN_DIVIDEND_YEARS 10 -> 1 and SCHD_DIVIDEND_GROWTH_MIN 0.0 -> -1.0 (the l.354 `>= 0` guard
// then skips the growth filter). Everything else verbatim, including the baseline's OVERRIDE.
const fs = require('fs');
const path = require('path');
const ROOT = path.join(__dirname, '../..');
const base = fs.readFileSync(path.join(__dirname, 'baseline.py'), 'utf8');
const r1 = /^SCHD_MIN_DIVIDEND_YEARS = 10(\s)/m, r2 = /^SCHD_DIVIDEND_GROWTH_MIN = 0\.0(\s)/m;
for (const [re, k] of [[r1, 'SCHD_MIN_DIVIDEND_YEARS'], [r2, 'SCHD_DIVIDEND_GROWTH_MIN']]) {
  const n = base.split('\n').filter(l => new RegExp('^' + k + '\\s*=').test(l)).length;
  if (n !== 1 || !re.test(base)) throw new Error('expected exactly one ' + k + ' line, got ' + n);
}
const header = '# q-e9-persist — 红利质量 understand: baseline.py with SCHD_MIN_DIVIDEND_YEARS 10->1, SCHD_DIVIDEND_GROWTH_MIN 0.0->-1.0 (persistence gate off). Built by study/红利质量/build-q-e9-persist.js.\n';
const out = header + base.replace(r1, 'SCHD_MIN_DIVIDEND_YEARS = 1$1').replace(r2, 'SCHD_DIVIDEND_GROWTH_MIN = -1.0$1');
const a = base.split('\n'), b = out.split('\n').slice(1);
const diff = a.map((l, i) => l !== b[i] ? i : -1).filter(i => i >= 0);
if (a.length !== b.length || diff.length !== 2 ||
    !/^SCHD_MIN_DIVIDEND_YEARS = 1\s/.test(b[diff[0]]) ||
    !/^SCHD_DIVIDEND_GROWTH_MIN = -1\.0\s/.test(b[diff[1]])) throw new Error('edit assertion failed: ' + diff);
const dst = path.join(__dirname, 'variants/q-e9-persist.py');
fs.writeFileSync(dst, out);
console.log('built', path.relative(ROOT, dst), 'changed lines', diff.map(i => i + 1).join(','),
  diff.map(i => JSON.stringify(b[i])).join(' '));
