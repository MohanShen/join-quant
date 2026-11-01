// q-e9-calendar-ablate: base = strategies/2026-10-17_六因子选股版破净策略_附PT迁移版在各时期的回测截图-e7c95ca1.py
// built exactly as the normalizer builds it (py2to3(src) + OVERRIDE), with ONE asserted edit:
// `g.if_check_calendar_effect = True` -> `False`. Everything else verbatim.
// With the flag off, g.calendar_signal stays at its init value False, so trade_func trades every rebalance.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const ROOT = path.join(__dirname, '..', '..');
const SRC = path.join(ROOT, 'strategies', '2026-10-17_六因子选股版破净策略_附PT迁移版在各时期的回测截图-e7c95ca1.py');
const raw = py2to3(fs.readFileSync(SRC, 'utf8'));

const FROM = '    g.if_check_calendar_effect = True  # 是否检查日历效应';
const TO = '    g.if_check_calendar_effect = False  # 是否检查日历效应';
const n = raw.split(FROM).length - 1;
if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}`);
const body = raw.replace(FROM, TO);
const a = raw.split('\n'), b = body.split('\n');
if (a.length !== b.length) throw new Error('line count');
const diff = a.map((l, i) => (l !== b[i] ? i : -1)).filter(i => i >= 0);
if (diff.length !== 1 || b[diff[0]] !== TO) throw new Error(`not a one-line edit: ${diff}`);
if (body.includes('if_check_calendar_effect = True')) throw new Error('flag still True');

const out = path.join(__dirname, 'variants', 'q-e9-calendar-ablate.py');
fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, body + OVERRIDE);
console.log('built', path.relative(ROOT, out), 'edited line', diff[0] + 1);
