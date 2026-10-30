// Independent re-verification of variants/02fdafaa-benchsem.py: strip the OVERRIDE tail, delete the
// 35 lines the builder says it added, and require the remainder to equal py2to3(raw) exactly.
// Separate from the builder on purpose — the builder asserting on its own intermediate `body` is a
// weaker check than reading the file back off disk.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');

const ROOT = path.join(__dirname, '../..');
const src = fs.readdirSync(path.join(ROOT, 'strategies')).find(f => /02fdafaa/.test(f));
const raw = py2to3(fs.readFileSync(path.join(ROOT, 'strategies', src), 'utf8'));

const full = fs.readFileSync(path.join(__dirname, 'variants/02fdafaa-benchsem.py'), 'utf8');
if (!full.endsWith(OVERRIDE)) throw new Error('OVERRIDE tail is not the live one');
const bodyTxt = full.slice(0, full.length - OVERRIDE.length);

const a = raw.split('\n');
const b = bodyTxt.split('\n');

// Walk both, allowing b to contain extra lines; every extra must be probe text.
let i = 0, extras = [];
for (let j = 0; j < b.length; j++) {
  if (i < a.length && b[j] === a[i]) { i++; continue; }
  extras.push([j + 1, b[j]]);
}
if (i !== a.length) throw new Error(`only consumed ${i} of ${a.length} original lines — the probe changed or dropped one`);

const PROBE_RE = /_benchsem|BENCHSEM|q-e9-bench-lastprice|^#|^$|^ +(try|except|return|d =|codes =|s =|cd =|last =|hl =|dop =|pc =|dc =|if len\(codes\)|log\.error|\s*% \(tag)/;
for (const [n, l] of extras) {
  if (!PROBE_RE.test(l)) throw new Error(`extra line ${n} is not probe text: ${l}`);
}
console.log(`[verify] ${a.length} original lines all present, in order, unmodified`);
console.log(`[verify] ${extras.length} extra lines, every one probe text`);
console.log(`[verify] extra lines at: ${extras.map(e => e[0]).join(',')}`);
console.log('[verify] OVERRIDE tail is the live frozen block (byte-compared, not hand-copied)');
