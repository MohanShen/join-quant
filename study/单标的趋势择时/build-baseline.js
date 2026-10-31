// Builds study/单标的趋势择时/baseline.py = py2to3(base c4f480e3) + OVERRIDE, the same transform
// strategy-normalize.js applied to the temp copy behind the epoch-9 ledger row.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');

const ROOT = path.join(__dirname, '../..');
const SRC = path.join(ROOT, 'strategies/2026-10-12_7_8_极限回撤_用架构解耦重构多策略动态路由-c4f480e3.py');
const base = py2to3(fs.readFileSync(SRC, 'utf8')) + OVERRIDE;
fs.writeFileSync(path.join(__dirname, 'baseline.py'), base);
console.log('built study/单标的趋势择时/baseline.py');
