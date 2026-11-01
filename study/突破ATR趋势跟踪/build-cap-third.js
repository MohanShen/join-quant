// atr-imp-cap-third: base e79e9884 built as the normalizer builds it (py2to3(src) + OVERRIDE),
// with ONE asserted edit at the MAX_POSITION_PCT assignment: 0.50 -> 1.0/3. 2% risk sizing and
// the cash constraint are untouched (size = min(risk, cap, cash)), so risk still binds when smaller.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const ROOT = path.join(__dirname, '..', '..');
const SRC = path.join(ROOT, 'strategies', '2026-10-27_基于上一版本进行了适当调整_增加其攻击性-e79e9884.py');
const a = py2to3(fs.readFileSync(SRC, 'utf8')).split('\n');
const hits = a.map((l, i) => (/^MAX_POSITION_PCT\s*=\s*0\.50\b/.test(l) ? i : -1)).filter(i => i >= 0);
if (hits.length !== 1) throw new Error('expected 1 MAX_POSITION_PCT assignment, got ' + hits.length);
const b = a.slice();
b[hits[0]] = a[hits[0]].replace(/=\s*0\.50/, '= 1.0/3');
const changed = b.filter((l, k) => l !== a[k]).length;
if (changed !== 1 || b.length !== a.length) throw new Error('not a one-line edit');
const out = path.join(__dirname, 'variants', 'atr-imp-cap-third.py');
fs.writeFileSync(out, b.join('\n') + OVERRIDE);
console.log('built', path.relative(ROOT, out), 'line', hits[0] + 1, ':', b[hits[0]]);
