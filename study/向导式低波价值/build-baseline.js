// Builds study/向导式低波价值/baseline.py: the family base exactly as the normalizer submits it —
// py2to3(src) + OVERRIDE, with NO edit — plus a header naming the source.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const ROOT = path.join(__dirname, '..', '..');
const REL = 'strategies/2026-10-29_向导式_ATR指标择时测试_0_0_1-8b9cb8e2.py';
const body = py2to3(fs.readFileSync(path.join(ROOT, REL), 'utf8')) + OVERRIDE;
for (const pin of ['avoid_future_data', 'order_volume_ratio', 'set_order_cost']) {
  if (!body.includes(pin)) throw new Error(`missing pin: ${pin}`);
}
const header =
  `# study baseline — family: 向导式低波价值\n` +
  `# source: ${REL}\n` +
  `# construction: py2to3(source) + utils/strategy-normalize OVERRIDE, no edit (identical to the normalizer's submission)\n` +
  `# built: ${new Date().toISOString().slice(0, 10)} by study/向导式低波价值/build-baseline.js\n`;
const out = path.join(__dirname, 'baseline.py');
fs.writeFileSync(out, header + body);
console.log('built', path.relative(ROOT, out), 'bytes', (header + body).length);
if (require.main === module) {}
