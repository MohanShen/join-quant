// q-e9-atr-bb-ablate: base e79e9884 built as the normalizer builds it (py2to3(src) + OVERRIDE),
// with ONE asserted edit: `if not (cond1 and cond2 and cond3 and cond4):` -> `if not cond4:`.
// Exits / sizing / regime / pool / schedule verbatim.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const ROOT = path.join(__dirname, '..', '..');
const SRC = path.join(ROOT, 'strategies', '2026-10-27_基于上一版本进行了适当调整_增加其攻击性-e79e9884.py');
const raw = py2to3(fs.readFileSync(SRC, 'utf8'));
const FROM = 'if not (cond1 and cond2 and cond3 and cond4):';
const TO = 'if not cond4:';
const n = raw.split(FROM).length - 1;
if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}`);
const body = raw.replace(FROM, TO);
const a = raw.split('\n'), b = body.split('\n');
if (a.length !== b.length) throw new Error('line count changed');
const diff = a.map((l, i) => (l !== b[i] ? i : -1)).filter(i => i >= 0);
if (diff.length !== 1 || b[diff[0]].trim() !== TO) throw new Error('not a one-line edit: ' + diff);
const out = path.join(__dirname, 'variants', 'q-e9-atr-bb-ablate.py');
fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, body + OVERRIDE);
console.log('built', path.relative(ROOT, out), 'edited line', diff[0] + 1);
