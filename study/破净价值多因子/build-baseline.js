// Builds study/破净价值多因子/baseline.py: the family base exactly as the normalizer submits it —
// py2to3(src) + OVERRIDE (utils/strategy-normalize.js line ~347), with NO edit — plus a header
// comment naming the source. This is the artifact the orchestrator runs VAL on.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const ROOT = path.join(__dirname, '..', '..');
const REL = 'strategies/2026-10-17_六因子选股版破净策略_附PT迁移版在各时期的回测截图-e7c95ca1.py';
const body = py2to3(fs.readFileSync(path.join(ROOT, REL), 'utf8')) + OVERRIDE;

for (const pin of ['avoid_future_data', 'order_volume_ratio', 'set_order_cost']) {
  if (!body.includes(pin)) throw new Error(`missing pin: ${pin}`);
}
const header =
  `# study baseline — family: 破净价值多因子\n` +
  `# source: ${REL}\n` +
  `# construction: py2to3(source) + utils/strategy-normalize OVERRIDE, no edit (identical to the normalizer's submission)\n` +
  `# built: ${new Date().toISOString().slice(0, 10)} by study/破净价值多因子/build-baseline.js\n`;
const out = path.join(__dirname, 'baseline.py');
fs.writeFileSync(out, header + body);
console.log('built', path.relative(ROOT, out), 'bytes', (header + body).length);
