// q-e9-7 builder: variants/q-e9-3.py with 518880.XSHG (黄金ETF) removed from g.all_risk_etfs.
// Exactly one parent line deleted (asserted); one header comment line prepended. Nothing else moves.
// Usage: node study/ETF低波海龟/build-q-e9-7.js
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { OVERRIDE } = require('../../utils/strategy-normalize');
const PARENT = path.join(__dirname, 'variants', 'q-e9-3.py');
const OUT = path.join(__dirname, 'variants', 'q-e9-7.py');
const src = fs.readFileSync(PARENT, 'utf8');
console.log('parent sha256', crypto.createHash('sha256').update(src).digest('hex'));

const LINE = '        "518880.XSHG": "黄金ETF",\n';
const n = src.split(LINE).length - 1;
if (n !== 1) throw new Error(`expected exactly 1 match of the gold line, got ${n}`);
if ((src.match(/518880/g) || []).length !== 1) throw new Error('518880 appears elsewhere in parent');
const body = src.replace(LINE, '');
const HDR = '# q-e9-7: q-e9-3 with 518880.XSHG (黄金ETF) removed from g.all_risk_etfs (14 -> 13). Built by study/ETF低波海龟/build-q-e9-7.js\n';
const out = HDR + body;

// assertions: line diff is exactly the removed line (+ the header), OVERRIDE tail intact
const a = src.split('\n'), b = body.split('\n');
if (b.length !== a.length - 1) throw new Error('line count did not drop by exactly 1');
const idx = a.indexOf(LINE.replace(/\n$/, ''));
const recon = b.slice(0, idx).concat([a[idx]], b.slice(idx));
if (recon.join('\n') !== src) throw new Error('re-inserting the removed line does not restore the parent');
if (!out.endsWith(OVERRIDE)) throw new Error('frozen OVERRIDE is not the file tail');
if (body.includes('518880')) throw new Error('518880 still present');
fs.writeFileSync(OUT, out);
console.log('wrote', OUT, 'sha256', crypto.createHash('sha256').update(out).digest('hex'));
