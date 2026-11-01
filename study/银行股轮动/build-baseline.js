// baseline.py: base 2a323522 + py2to3 + OVERRIDE (frozen pins, as the normalizer applies them). NO edits.
// base == bestVariant (sole member), so a VAL on this file validates the family champion.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const ROOT = path.join(__dirname, '../..');
const SRC = 'strategies/2026-10-26_自己搭建的一个10年230_收益率的银行股策略-2a323522.py';
const raw = py2to3(fs.readFileSync(path.join(ROOT, SRC), 'utf8'));
const out = path.join(__dirname, 'baseline.py');
fs.writeFileSync(out, raw + OVERRIDE);
console.log('built', path.relative(ROOT, out));
