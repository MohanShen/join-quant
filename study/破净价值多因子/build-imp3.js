// pbn-imp-3: base = strategies/2026-10-17_六因子选股版破净策略_附PT迁移版在各时期的回测截图-e7c95ca1.py
// built exactly as the normalizer builds it (py2to3(src) + OVERRIDE), with ONE asserted edit in buy_stocks:
// divide available_cash over the names NOT yet held, not over the whole buy_list. Calendar rule ON (base as written).
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const ROOT = path.join(__dirname, '..', '..');
const SRC = path.join(ROOT, 'strategies', '2026-10-17_六因子选股版破净策略_附PT迁移版在各时期的回测截图-e7c95ca1.py');
const raw = py2to3(fs.readFileSync(SRC, 'utf8'));

const FROM = '    target_value = context.portfolio.available_cash / len(buy_list)';
const TO = [
  '    new = [s for s in buy_list if s not in context.portfolio.positions]',
  '    if not new:',
  '        return',
  '    target_value = context.portfolio.available_cash / len(new)',
].join('\n');
const n = raw.split(FROM).length - 1;
if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}`);
const body = raw.replace(FROM, TO);
const a = raw.split('\n'), b = body.split('\n');
if (b.length !== a.length + 3) throw new Error('line count');
const i = a.indexOf(FROM);
if (a.slice(0, i).join('\n') !== b.slice(0, i).join('\n')) throw new Error('prefix changed');
if (a.slice(i + 1).join('\n') !== b.slice(i + 4).join('\n')) throw new Error('suffix changed');
if (b.slice(i, i + 4).join('\n') !== TO) throw new Error('edit mismatch');
if (!body.includes('g.if_check_calendar_effect = True')) throw new Error('calendar flag not ON');

const out = path.join(__dirname, 'variants', 'pbn-imp-3.py');
fs.writeFileSync(out, body + OVERRIDE);
console.log('built', path.relative(ROOT, out), 'edited line', i + 1);
