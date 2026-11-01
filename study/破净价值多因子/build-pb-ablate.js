// q-e9-pb-ablate: base = strategies/2026-10-17_六因子选股版破净策略_附PT迁移版在各时期的回测截图-e7c95ca1.py
// built exactly as the normalizer builds it (py2to3(src) + OVERRIDE), with ONE asserted edit:
// delete the line `        valuation.pb_ratio.between(0, 1),`. Everything else verbatim.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const ROOT = path.join(__dirname, '..', '..');
const SRC = path.join(ROOT, 'strategies', '2026-10-17_六因子选股版破净策略_附PT迁移版在各时期的回测截图-e7c95ca1.py');
const raw = py2to3(fs.readFileSync(SRC, 'utf8'));

const LINE = '        valuation.pb_ratio.between(0, 1),\n';
const n = raw.split(LINE).length - 1;
if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}`);
const body = raw.replace(LINE, '');
if (body.length !== raw.length - LINE.length) throw new Error('edit size mismatch');
if (body.includes('pb_ratio.between')) throw new Error('pb screen still present');
// the diff is exactly that one line
const a = raw.split('\n'), b = body.split('\n');
if (a.length !== b.length + 1) throw new Error('line count');
const i = a.indexOf(LINE.replace(/\n$/, ''));
if (a.slice(0, i).concat(a.slice(i + 1)).join('\n') !== body) throw new Error('not a one-line deletion');

const out = path.join(__dirname, 'variants', 'q-e9-pb-ablate.py');
fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, body + OVERRIDE);
console.log('built', path.relative(ROOT, out), 'deleted line', i + 1);
