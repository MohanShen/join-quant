// Builds study/突破ATR趋势跟踪/baseline.py: the family base exactly as the normalizer submits it —
// py2to3(src) + OVERRIDE, with NO edit — plus a header naming the source.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const ROOT = path.join(__dirname, '..', '..');
const REL = 'strategies/2026-10-27_基于上一版本进行了适当调整_增加其攻击性-e79e9884.py';
const body = py2to3(fs.readFileSync(path.join(ROOT, REL), 'utf8')) + OVERRIDE;
for (const pin of ['avoid_future_data', 'order_volume_ratio', 'set_order_cost']) {
  if (!body.includes(pin)) throw new Error(`missing pin: ${pin}`);
}
const header =
  `# study baseline — family: 突破ATR趋势跟踪\n` +
  `# source: ${REL}\n` +
  `# construction: py2to3(source) + utils/strategy-normalize OVERRIDE, no edit (identical to the normalizer's submission)\n` +
  `# built: ${new Date().toISOString().slice(0, 10)} by study/突破ATR趋势跟踪/build-baseline.js\n`;
const out = path.join(__dirname, 'baseline.py');
fs.writeFileSync(out, header + body);
console.log('built', path.relative(ROOT, out), 'bytes', (header + body).length);
