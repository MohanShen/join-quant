// Builds the epoch-9 VAL copy of the family CHAMPION, 9498d93f (多ETF网格交易策略-年化10.61%).
// ⚠ The champion is NOT the base: at epoch 9 the base 598050b9 scores 0.26 sharpe on TRAIN 2024,
// while 9498d93f (a separate code body — 10-ETF percentage grid, 80% initial position, 2.5% log
// rungs trading 5% of each ETF's 10% sleeve) scores objective 0.1293 / sharpe 1.10. So a VAL on
// study/网格/baseline*.py would validate the wrong book; this builds the champion itself.
// Construction is byte-identical to strategy-normalize.js's temp copy (py2to3(src) + OVERRIDE),
// i.e. the exact form the epoch-9 ledger row measured — no edit, so no TRAIN re-run is needed.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');

const ROOT = path.join(__dirname, '../..');
const SRC = path.join(ROOT, 'strategies/2026-07-01_多ETF网格交易策略-年化10_61-9498d93f.py');
const out = path.join(__dirname, 'champion-e9.py');
fs.writeFileSync(out, py2to3(fs.readFileSync(SRC, 'utf8')) + OVERRIDE);
console.log('built', path.relative(ROOT, out));
