// q-e9-cap20at10x — q-e9-cap10x.py (= baseline.py + header) with ONE asserted edit: the MIN_LOTS
// prefilter test `p * min_lots_cost < budget` (cap = equity/100/500, ~¥200 at ¥10M) becomes a FIXED
// `p < 20.0`, independent of equity. The log line's printed cap follows it (so the control can read
// "价<20.0元"); 预算 is still printed for reference. Everything else verbatim, incl. the OVERRIDE.
const fs = require('fs');
const path = require('path');
const ROOT = path.join(__dirname, '../..');
const src = fs.readFileSync(path.join(__dirname, 'variants/q-e9-cap10x.py'), 'utf8');
const a = src.split('\n');
if (!/^# q-e9-cap10x/.test(a[0])) throw new Error('unexpected header: ' + a[0]);
const T1 = '                    return p * min_lots_cost < budget';
const R1 = '                    return p < 20.0  # q-e9-cap20at10x: FIXED ¥20 price cap, independent of equity';
const T2 = '                    budget / (SCHD_MIN_LOTS * 100) if SCHD_MIN_LOTS else 0,';
const R2 = '                    20.0,  # q-e9-cap20at10x: printed cap = the fixed ¥20';
const count = t => a.filter(l => l === t).length;
if (count(T1) !== 1 || count(T2) !== 1) throw new Error(`expected one of each target, got ${count(T1)}/${count(T2)}`);
const b = a.map(l => l === T1 ? R1 : l === T2 ? R2 : l);
b[0] = '# q-e9-cap20at10x — 红利质量 understand: baseline.py with MIN_LOTS cap fixed at price<¥20 (was equity/500), run with --capital 10000000. Study-only, never a ledger row. Built by study/红利质量/build-q-e9-cap20at10x.js.';
const diff = a.map((l, i) => l !== b[i] ? i : -1).filter(i => i > 0);
if (a.length !== b.length || diff.length !== 2 || b[diff[0]] !== R1 || b[diff[1]] !== R2) throw new Error('edit assertion failed: ' + diff);
const dst = path.join(__dirname, 'variants/q-e9-cap20at10x.py');
fs.writeFileSync(dst, b.join('\n'));
console.log('built', path.relative(ROOT, dst), 'changed lines', diff.map(i => i + 1).join(','));
