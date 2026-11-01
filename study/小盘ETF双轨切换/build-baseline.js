// baseline.py: base 0d1bbe83 + py2to3 + OVERRIDE (frozen pins, as the normalizer applies them). NO edits.
// The VAL candidate: base == bestVariant, so a VAL on this file validates the family champion.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const ROOT = path.join(__dirname, '../..');
const SRC = 'strategies/2026-10-12_年化51_的晴雨双轨_小盘游击_ETF防御-0d1bbe83.py';
const raw = py2to3(fs.readFileSync(path.join(ROOT, SRC), 'utf8'));
const out = path.join(__dirname, 'baseline.py');
fs.writeFileSync(out, raw + OVERRIDE);
console.log('built', path.relative(ROOT, out));
