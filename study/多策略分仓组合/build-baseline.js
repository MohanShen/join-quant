// Builds study/多策略分仓组合/baseline.py = py2to3(base 35ce65d2) + OVERRIDE, byte-identical to the
// temp copy strategy-normalize.js measured for the epoch-9 ledger row (0.8792 / sharpe 4.96), so the
// stored curve 2026-07-18_多策略-题材概念-35ce65d2__train__e9 is this file's control and no
// reproduction run is needed. Variants are built from this file with asserted edits.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');

const ROOT = path.join(__dirname, '../..');
const SRC = path.join(ROOT, 'strategies/2026-07-18_多策略-题材概念-35ce65d2.py');
fs.writeFileSync(path.join(__dirname, 'baseline.py'), py2to3(fs.readFileSync(SRC, 'utf8')) + OVERRIDE);
console.log('built study/多策略分仓组合/baseline.py');
