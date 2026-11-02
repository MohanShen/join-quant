// baseline.py: base 94888e61 + py2to3 + OVERRIDE (frozen pins, as the normalizer applies them). NO edits.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const ROOT = path.join(__dirname, '../..');
const SRC = 'strategies/2026-10-20_蓝筹大盘分红策略_超稳健-94888e61.py';
const raw = py2to3(fs.readFileSync(path.join(ROOT, SRC), 'utf8'));
const out = path.join(__dirname, 'baseline.py');
fs.writeFileSync(out, raw + OVERRIDE);
console.log('built', path.relative(ROOT, out));
