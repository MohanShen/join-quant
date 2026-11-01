// q-e9-minlots — baseline.py with ONE asserted edit: SCHD_MIN_LOTS 5 -> 0 (removes the l.296
// MIN_LOTS price-cap prefilter; SCHD_MIN_PRICE=0.0 so nothing else in that block changes).
// Everything else verbatim, including the OVERRIDE the baseline already carries (built from
// utils/strategy-normalize by build-baseline.js — not hand-copied).
const fs = require('fs');
const path = require('path');
const ROOT = path.join(__dirname, '../..');
const base = fs.readFileSync(path.join(__dirname, 'baseline.py'), 'utf8');
const re = /^SCHD_MIN_LOTS = 5(\s)/m;
const hits = base.split('\n').filter(l => /^SCHD_MIN_LOTS\s*=/.test(l));
if (hits.length !== 1 || !re.test(base)) throw new Error('expected exactly one `SCHD_MIN_LOTS = 5` line, got ' + hits.length);
const header = '# q-e9-minlots — 红利质量 understand: baseline.py with SCHD_MIN_LOTS 5->0 (price cap off). Built by study/红利质量/build-q-e9-minlots.js.\n';
const out = header + base.replace(re, 'SCHD_MIN_LOTS = 0$1');
const a = base.split('\n'), b = out.split('\n').slice(1);
const diff = a.map((l, i) => l !== b[i] ? i : -1).filter(i => i >= 0);
if (a.length !== b.length || diff.length !== 1 || !/^SCHD_MIN_LOTS = 0/.test(b[diff[0]])) throw new Error('edit assertion failed: ' + diff);
const dst = path.join(__dirname, 'variants/q-e9-minlots.py');
fs.writeFileSync(dst, out);
console.log('built', path.relative(ROOT, dst), 'changed line', diff[0] + 1, JSON.stringify(b[diff[0]]));
