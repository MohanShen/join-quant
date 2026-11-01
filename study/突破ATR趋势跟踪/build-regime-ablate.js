// q-e9-atr-regime-ablate: base e79e9884 built as the normalizer builds it (py2to3(src) + OVERRIDE),
// with ONE asserted edit: the first statement of get_index_regime()'s body (after the docstring)
// becomes `return 'offensive'`; the original body is left as dead code. Removes both the
// no-open rule and the defensive forced liquidation. Everything else verbatim.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const ROOT = path.join(__dirname, '..', '..');
const SRC = path.join(ROOT, 'strategies', '2026-10-27_基于上一版本进行了适当调整_增加其攻击性-e79e9884.py');
const raw = py2to3(fs.readFileSync(SRC, 'utf8'));
const a = raw.split('\n');
const defs = a.map((l, i) => (/^def get_index_regime\(\):\s*$/.test(l) ? i : -1)).filter(i => i >= 0);
if (defs.length !== 1) throw new Error('expected 1 def, got ' + defs.length);
let i = defs[0] + 1;
if (!/^\s+"""/.test(a[i])) throw new Error('expected docstring at ' + (i + 1));
i++;
while (!/"""\s*$/.test(a[i])) i++;
const first = i + 1;
if (!/^    hist = attribute_history\(/.test(a[first])) throw new Error('unexpected first statement: ' + a[first]);
const b = a.slice(0, first).concat(["    return 'offensive'"], a.slice(first));
const changed = b.filter((l, k) => (k < first ? l !== a[k] : k === first ? true : l !== a[k - 1])).length;
if (b.length !== a.length + 1 || changed !== 1) throw new Error('not a one-line insertion');
const out = path.join(__dirname, 'variants', 'q-e9-atr-regime-ablate.py');
fs.writeFileSync(out, b.join('\n') + OVERRIDE);
console.log('built', path.relative(ROOT, out), 'inserted at line', first + 1);
