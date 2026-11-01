// pbn-imp-1: base = strategies/2026-10-17_六因子选股版破净策略_附PT迁移版在各时期的回测截图-e7c95ca1.py
// built exactly as build-attrib-probe.js builds the probe (py2to3(src) + log-only ATTRIB handler + OVERRIDE),
// plus ONE asserted trading edit: g.top_n = 1 -> 2.
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
const probe = raw.replace(ANCHOR, ANCHOR + SCHED) + FN;
const fnCode = FN.split('\n').map(l => l.replace(/#.*$/, '')).join('\n');
if (/order\w*\(|(^|[^\w.])g\./m.test(fnCode)) throw new Error('helper touches trading');

// the ONE trading edit
const TN = '    g.top_n = 1  # 每个维度筛选的股数';
if (probe.split(TN).length - 1 !== 1) throw new Error('expected exactly 1 top_n line');
const body = probe.replace(TN, '    g.top_n = 2  # 每个维度筛选的股数');
const x = probe.split('\n'), y = body.split('\n');
if (x.length !== y.length || x.filter((l, k) => l !== y[k]).length !== 1) throw new Error('top_n edit not a single line');

// must equal the probe artifact except that one line
const probeFile = fs.readFileSync(path.join(__dirname, 'variants', 'q-e9-attrib-probe.py'), 'utf8');
if (probeFile !== probe + OVERRIDE) throw new Error('probe rebuild differs from stored probe variant');

const out = path.join(ROOT, 'enhance', 'candidates', 'pbn-imp-1.py');
fs.writeFileSync(out, body + OVERRIDE);
console.log('built', path.relative(ROOT, out));
