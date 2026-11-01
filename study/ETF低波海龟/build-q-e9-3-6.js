// q-e9-3 + q-e9-6 builders. py2to3(base 4a8bcfd5) + asserted exactly-once edits + live OVERRIDE.
//   q-e9-3 (turtle overlay ablation): open_position buys 100% of total_value (was 3 Units = 75%);
//          the stop-loss, take-profit and add-on CALL SITES are disabled with `False and ...`.
//          Selection, 20d min hold, 10% switch band, safe leg verbatim. 4 changed lines, line count fixed.
//   q-e9-6 (pool equal-weight B&H): run_daily target swapped to bh_buy_once, which buys the 14
//          g.all_risk_etfs at 1/14 of available cash each at the first 09:35 and never trades again.
//          initialize (costs/timing/benchmark) verbatim; rebalance_trade left defined but unscheduled.
// strategies/ never modified.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const ROOT = path.join(__dirname, '../..');
const SRC = path.join(ROOT, 'strategies/2026-10-17_量化分享_ETF低波海龟法则与复利增强的验证-4a8bcfd5.py');
const src = py2to3(fs.readFileSync(SRC, 'utf8'));

function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${from}`);
  return s.replace(from, to);
}
function changedLines(a, b) {
  const x = a.split('\n'), y = b.split('\n');
  if (x.length !== y.length) throw new Error('line count moved');
  return x.filter((l, i) => l !== y[i]).length;
}
function write(name, hdr, body) {
  const out = path.join(__dirname, 'variants', `${name}.py`);
  fs.writeFileSync(out, hdr + body + OVERRIDE);
  console.log('wrote', out);
}

// ---- q-e9-3
let b = src;
b = edit(b, '    target_value = total_value * g.unit_value_ratio * g.initial_units\n',
  '    target_value = total_value  # q-e9-3: 100% on entry (was 3 Units)\n');
b = edit(b, '    if check_stop_loss(context, cur):\n',
  '    if False and check_stop_loss(context, cur):  # q-e9-3: no 4N stop\n');
b = edit(b, '    if check_take_profit(context, cur):\n',
  '    if False and check_take_profit(context, cur):  # q-e9-3: no take-profit\n');
b = edit(b, '        if check_add_position(context, cur):\n',
  '        if False and check_add_position(context, cur):  # q-e9-3: no add-ons\n');
const n3 = changedLines(src, b);
if (n3 !== 4) throw new Error(`q-e9-3 expected 4 changed lines, got ${n3}`);
write('q-e9-3', '# q-e9-3: ETF低波海龟 base 4a8bcfd5, turtle overlay removed (100% entry, no add/stop/TP). Built by study/ETF低波海龟/build-q-e9-3-6.js\n', b);

// ---- q-e9-6
let c = src;
c = edit(c, "    run_daily(rebalance_trade, '09:35')\n",
  "    g.bh_done = False  # q-e9-6\n    run_daily(bh_buy_once, '09:35')  # q-e9-6: was rebalance_trade\n");
c += `

# q-e9-6: equal-weight buy-and-hold of the 14 risk ETFs, bought once, never rebalanced.
def bh_buy_once(context):
    if g.bh_done:
        return
    codes = list(g.all_risk_etfs.keys())
    cd = get_current_data()
    each = context.portfolio.available_cash * 0.998 / len(codes)
    for code in codes:
        if cd[code].paused:
            log.warn("BH paused %s" % code)
            continue
        order_value(code, each)
    g.bh_done = True
    held = [k for k in context.portfolio.positions if context.portfolio.positions[k].total_amount > 0]
    log.info("BH bought %d of %d, cash left %.0f" % (len(held), len(codes), context.portfolio.available_cash))
`;
write('q-e9-6', '# q-e9-6: ETF低波海龟 pool reference — 14 risk ETFs equal-weight B&H from first 09:35. Built by study/ETF低波海龟/build-q-e9-3-6.js\n', c);
