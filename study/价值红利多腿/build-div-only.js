// q-e9-div-only: base = study/价值红利多腿/variants/q-e9-s4-pit.py (the honest-s4 reference, already
// py2to3 + OVERRIDE), with ONE asserted edit: g.strategy_weights -> s1=0, s2=0.25, s3=0, s4=0.25.
// Zero-weight sleeves never trade (sub_buy returns at sub_cash <= 100); their 50% sits idle as cash.
// Same method as build-pb-only.js.
const fs = require('fs');
const path = require('path');
const { OVERRIDE } = require('../../utils/strategy-normalize');
const ROOT = path.join(__dirname, '..', '..');
const REL = 'study/价值红利多腿/variants/q-e9-s4-pit.py';
let raw = fs.readFileSync(path.join(ROOT, REL), 'utf8');
if (!raw.startsWith('# q-e9-s4-pit')) throw new Error('unexpected reference header');
const hdrEnd = raw.indexOf('\n', raw.indexOf('# built:')) + 1;
raw = raw.slice(hdrEnd);
if (!raw.includes(OVERRIDE)) throw new Error('reference does not carry the live OVERRIDE');
const A = "    g.strategy_weights = {\n        's1': 0.25,\n        's2': 0.25,\n        's3': 0.25,\n        's4': 0.25,\n    }\n";
const A2 = "    g.strategy_weights = {\n        's1': 0.0,\n        's2': 0.25,\n        's3': 0.0,\n        's4': 0.25,\n    }\n";
const n = raw.split(A).length - 1;
if (n !== 1) throw new Error('expected exactly 1 weights block, got ' + n);
const body = raw.replace(A, A2);
if (body.replace(A2, A) !== raw) throw new Error('diff is not exactly the weights edit');
for (const pin of ['avoid_future_data', 'order_volume_ratio', 'set_order_cost']) {
  if (!body.includes(pin)) throw new Error('missing pin ' + pin);
}
const header =
  `# q-e9-div-only — family: 价值红利多腿\n` +
  `# source: ${REL} (honest-s4 reference; itself py2to3(cf1ec5bd) + s4 PIT bound + OVERRIDE)\n` +
  `# construction: reference + ONE asserted edit: g.strategy_weights s1=0 s2=0.25 s3=0 s4=0.25\n` +
  `# built: ${new Date().toISOString().slice(0, 10)} by study/价值红利多腿/build-div-only.js\n`;
const out = path.join(__dirname, 'variants', 'q-e9-div-only.py');
fs.writeFileSync(out, header + body);
console.log('built', path.relative(ROOT, out), 'bytes', (header + body).length);
