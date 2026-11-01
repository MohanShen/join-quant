// q-e9-ranker-isolate: base = strategies/2026-10-17_六因子选股版破净策略_附PT迁移版在各时期的回测截图-e7c95ca1.py
// built exactly as build-attrib-probe.js builds the probe (py2to3(src) + log-only ATTRIB handler + OVERRIDE),
// plus ONE asserted trading edit inside get_stock_list: the six-ranker `indicators` merge is replaced by
// "the 6 lowest valuation.pb_ratio names of stock_list (the PB + quality qualified list), weight 1/6 each".
// Quality chain, calendar, limit-up exits, cooldown, buy_stocks (bug included) all verbatim.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const ROOT = path.join(__dirname, '..', '..');
const SRC = path.join(ROOT, 'strategies', '2026-10-17_六因子选股版破净策略_附PT迁移版在各时期的回测截图-e7c95ca1.py');
const raw = py2to3(fs.readFileSync(SRC, 'utf8'));

const ANCHOR = "    run_daily(update_just_sold_stocks, time='15:01')\n";
if (raw.split(ANCHOR).length - 1 !== 1) throw new Error('expected exactly 1 anchor');
const SCHED = "    run_daily(log_positions, time='15:00')\n";
const FN = `

def log_positions(context):
    # q-e9-attrib-probe: LOG ONLY. Reads context.portfolio, places no order, writes no g.* state.
    d = context.current_dt.strftime('%Y-%m-%d')
    for code, p in context.portfolio.positions.items():
        log.info('ATTRIB POS %s %s %d %.2f %.4f %.4f' % (d, code, p.total_amount, p.value, p.avg_cost, p.price))
    log.info('ATTRIB CASH %s %.2f %.2f' % (d, context.portfolio.available_cash, context.portfolio.total_value))
`;
const probe = raw.replace(ANCHOR, ANCHOR + SCHED) + FN;
const probeFile = fs.readFileSync(path.join(__dirname, 'variants', 'q-e9-attrib-probe.py'), 'utf8');
if (probeFile !== probe + OVERRIDE) throw new Error('probe rebuild differs from stored probe variant');

// the ONE trading edit: the block from the 多维指标筛选 comment through `return targets`
const START = '    # 多维指标筛选\n';
const END = '    targets = targets.sort_values(ascending=False).to_dict()\n    return targets\n';
const i0 = probe.indexOf(START), i1 = probe.indexOf(END);
if (i0 < 0 || i1 < 0 || probe.indexOf(START, i0 + 1) >= 0 || probe.indexOf(END, i1 + 1) >= 0) throw new Error('block anchors not unique');
const OLD = probe.slice(i0, i1 + END.length);
if (!OLD.includes("get_f_score_top(context, stock_list, top_n=g.top_n)") || OLD.split('\n').length !== 16) throw new Error('unexpected ranker block');
const NEW = `    # q-e9-ranker-isolate: six rankers replaced by the 6 lowest-PB names of the qualified list
    q2 = query(valuation.code, valuation.pb_ratio).filter(valuation.code.in_(stock_list))
    df = get_fundamentals(q2, date=previous_date).sort_values('pb_ratio', ascending=True)
    picks = df.code.tolist()[:6]
    log.info('RANKISO %s qualified=%d picks=%s pb=%s' % (previous_date, len(stock_list), picks, [round(float(x), 3) for x in df.pb_ratio.tolist()[:6]]))
    targets = {s: 1.0 / 6 for s in picks}
    return targets
`;
const body = probe.slice(0, i0) + NEW + probe.slice(i1 + END.length);
// everything outside the block is byte-identical
if (body.slice(0, i0) !== probe.slice(0, i0) || body.slice(i0 + NEW.length) !== probe.slice(i1 + END.length)) throw new Error('edit leaked');

const out = path.join(__dirname, 'variants', 'q-e9-ranker-isolate.py');
fs.writeFileSync(out, body + OVERRIDE);
console.log('built', path.relative(ROOT, out));
