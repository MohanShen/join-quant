// q-e9-attrib-probe: base = strategies/2026-10-17_六因子选股版破净策略_附PT迁移版在各时期的回测截图-e7c95ca1.py
// built exactly as the normalizer builds it (py2to3(src) + OVERRIDE), with ONE asserted addition:
// a log-only run_daily(log_positions, time='15:00') handler. No trading line is touched.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const ROOT = path.join(__dirname, '..', '..');
const SRC = path.join(ROOT, 'strategies', '2026-10-17_六因子选股版破净策略_附PT迁移版在各时期的回测截图-e7c95ca1.py');
const raw = py2to3(fs.readFileSync(SRC, 'utf8'));

const ANCHOR = "    run_daily(update_just_sold_stocks, time='15:01')\n";
const n = raw.split(ANCHOR).length - 1;
if (n !== 1) throw new Error(`expected exactly 1 anchor, got ${n}`);
const SCHED = "    run_daily(log_positions, time='15:00')\n";
const FN = `

def log_positions(context):
    # q-e9-attrib-probe: LOG ONLY. Reads context.portfolio, places no order, writes no g.* state.
    d = context.current_dt.strftime('%Y-%m-%d')
    for code, p in context.portfolio.positions.items():
        log.info('ATTRIB POS %s %s %d %.2f %.4f %.4f' % (d, code, p.total_amount, p.value, p.avg_cost, p.price))
    log.info('ATTRIB CASH %s %.2f %.2f' % (d, context.portfolio.available_cash, context.portfolio.total_value))
`;
if (raw.includes('log_positions')) throw new Error('name collision');
const body = raw.replace(ANCHOR, ANCHOR + SCHED) + FN;
// the diff is exactly: one inserted schedule line + one appended function
const a = raw.split('\n'), b = (raw.replace(ANCHOR, ANCHOR + SCHED)).split('\n');
const i = a.indexOf(ANCHOR.replace(/\n$/, ''));
if (b.length !== a.length + 1 || b[i + 1] !== SCHED.replace(/\n$/, '')) throw new Error('not a one-line insertion');
if (b.slice(0, i + 1).concat(b.slice(i + 2)).join('\n') !== raw) throw new Error('insertion changed other lines');
if (!body.startsWith(raw.replace(ANCHOR, ANCHOR + SCHED))) throw new Error('append mismatch');
// code side only (strip comments), and `g.` as a whole identifier — `log.info` must not match
const fnCode = FN.split('\n').map(l => l.replace(/#.*$/, '')).join('\n');
if (/order\w*\(|(^|[^\w.])g\./m.test(fnCode)) throw new Error('helper touches trading');

const out = path.join(__dirname, 'variants', 'q-e9-attrib-probe.py');
fs.writeFileSync(out, body + OVERRIDE);
console.log('built', path.relative(ROOT, out), 'inserted after line', i + 1);
