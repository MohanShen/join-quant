// Builds the epoch-9 VAL copy of the family CHAMPION, 9befa9b8 (十日均线策略).
// ⚠ The champion is NOT the base: the page base 33b1b1e3 (CSI300 RPS rotation + MA20 gate) reads
// today's close at 08:00 and returns no-trades under avoid_future_data, so it has no epoch-9 row
// at all; the epoch-9 ledger's best member of this catch-all bucket is 9befa9b8 — a single-stock
// (600030 中信证券) MA10 timer, objective 0.1912 / sharpe 1.03 on TRAIN 2024. A VAL on
// study/趋势技术/baseline*.py would validate the wrong book; this builds the champion itself.
// Construction is byte-identical to strategy-normalize.js's temp copy (py2to3(src) + OVERRIDE),
// i.e. the exact form the epoch-9 ledger row measured — no edit, so no TRAIN re-run is needed.
//   node -e "require('./study/趋势技术/build-e9.js')"
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');

const ROOT = path.join(__dirname, '../..');
const SRC = path.join(ROOT, 'strategies/2026-06-08_十日均线策略-9befa9b8.py');
const out = path.join(__dirname, 'champion-e9.py');
fs.writeFileSync(out, py2to3(fs.readFileSync(SRC, 'utf8')) + OVERRIDE);
console.log('built', path.relative(ROOT, out));
