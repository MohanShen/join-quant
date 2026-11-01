// i-e9-2 + i-e9-3 builders. Asserted exactly-once edits + live OVERRIDE (never hand-copied).
//   i-e9-2 (from BASE 4a8bcfd5, py2to3): get_vol_rank's statistic std -> downside semi-deviation
//          sqrt(mean(min(r,0)^2)) * sqrt(252) on the same 60 log returns. ONE changed line.
//          Feeds both the ranking and the 0.40 safe-leg median (same function). Everything else verbatim.
//   i-e9-3 (from variants/q-e9-3.py): run_daily target swapped to rebalance_top3 (appended);
//          rebalance_trade left defined but unscheduled. Selection/vol function/safe-leg rule reused.
// strategies/ never modified.
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const ROOT = path.join(__dirname, '../..');
const BASE = path.join(ROOT, 'strategies/2026-10-17_量化分享_ETF低波海龟法则与复利增强的验证-4a8bcfd5.py');
const Q3 = path.join(__dirname, 'variants', 'q-e9-3.py');
const sha = s => crypto.createHash('sha256').update(s).digest('hex').slice(0, 16);

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
function write(name, body) {
  const out = path.join(__dirname, 'variants', `${name}.py`);
  if (!body.endsWith(OVERRIDE)) throw new Error('OVERRIDE not the file tail');
  fs.writeFileSync(out, body);
  console.log('wrote', out, 'sha', sha(body));
}

// ---- i-e9-2
const base = py2to3(fs.readFileSync(BASE, 'utf8'));
console.log('base(py2to3) sha', sha(base));
const v2 = edit(base,
  '    vol = grp.std().mul(np.sqrt(252)).loc[valid].dropna().sort_values()\n',
  '    vol = grp.apply(lambda x: np.sqrt(np.mean(np.minimum(x.dropna().values, 0.0) ** 2))).mul(np.sqrt(252)).loc[valid].dropna().sort_values()  # i-e9-2: downside semi-deviation\n');
if (changedLines(base, v2) !== 1) throw new Error('i-e9-2 expected 1 changed line');
write('i-e9-2', '# i-e9-2: ETF低波海龟 base 4a8bcfd5, vol statistic = downside semi-deviation (ranking + 0.40 median). Built by study/ETF低波海龟/build-i-e9-2-3.js\n' + v2 + OVERRIDE);

// ---- i-e9-3
const q3 = fs.readFileSync(Q3, 'utf8');
console.log('q-e9-3 sha', sha(q3));
if (!q3.endsWith(OVERRIDE)) throw new Error('q-e9-3 tail is not the live OVERRIDE');
let b = q3.slice(0, q3.length - OVERRIDE.length);
const b0 = b;
b = edit(b, "    run_daily(rebalance_trade, '09:35')\n",
  "    g.i3_days = {}  # i-e9-3\n    run_daily(rebalance_top3, '09:35')  # i-e9-3: was rebalance_trade\n");
const x = b0.split('\n'), y = b.split('\n');
if (y.length !== x.length + 1) throw new Error('i-e9-3 initialize edit moved more than 1 line');
b += `

# i-e9-3: hold the K=3 lowest-vol names (same get_vol_rank, same safe-leg rule), weights ∝ 1/vol,
# re-weighted ONLY on a day the held SET changes. Per-name 20-day min hold; per-name 10% band:
# a held name outside the top-K is replaced by the lowest-vol non-held top-K name only if
# in_vol < out_vol * (1 - 0.10) and the outgoing name has been held >= 20 days.
# Forced (no min-hold, no band): a held name missing from the valid pool (incl. a bond once
# allow_safe turns False — the base's 换回 rule) is dropped and the slot refilled from the ranking.
# A held bond is exempt from the band while allow_safe is True (base: 继续持有避险资产).
I3_K = 3

def rebalance_top3(context):
    risk_vol = get_vol_rank(context, g.all_risk_etfs)
    risk_vol_median = risk_vol.median() if len(risk_vol) > 0 else 0
    allow_safe = risk_vol_median > g.risk_vol_median_threshold
    if allow_safe:
        candidates = {**g.all_risk_etfs, **g.safe_etfs}
    else:
        candidates = g.all_risk_etfs
    vol = get_vol_rank(context, candidates)
    if len(vol) == 0:
        log.warn("I3 无有效标的，今日不交易")
        return
    pos = context.portfolio.positions
    held = [c for c in pos if pos[c].total_amount > 0]
    for c in held:
        g.i3_days[c] = g.i3_days.get(c, 0) + 1
    for c in list(g.i3_days.keys()):
        if c not in held:
            del g.i3_days[c]
    topk = list(vol.index[:I3_K])
    new_set = list(held)
    why = []
    for c in list(new_set):
        if c not in vol.index:
            new_set.remove(c)
            why.append("drop-invalid %s" % c)
    for c in vol.index:
        if len(new_set) >= I3_K:
            break
        if c not in new_set:
            new_set.append(c)
            why.append("fill %s" % c)
    while True:
        incoming = [c for c in topk if c not in new_set]
        outgoing = [c for c in new_set if c not in topk
                    and g.i3_days.get(c, 0) >= g.min_hold_days
                    and not (allow_safe and c in g.safe_etfs)]
        if not incoming or not outgoing:
            break
        outgoing.sort(key=lambda c: -vol[c])
        i, o = incoming[0], outgoing[0]
        if vol[i] < vol[o] * (1 - g.switch_threshold):
            new_set.remove(o)
            new_set.append(i)
            why.append("swap %s(%.4f)->%s(%.4f)" % (o, vol[o], i, vol[i]))
        else:
            break
    changed = set(new_set) != set(held)
    log.info("I3 med=%.4f allow=%s top=%s held=%s" % (
        risk_vol_median, allow_safe, ",".join(topk), ",".join(sorted(held))))
    if not changed:
        return
    inv = {c: 1.0 / vol[c] for c in new_set}
    s = 0.0  # builtin sum is shadowed by 'from jqdata import *'
    for c in new_set:
        s += inv[c]
    w = {c: inv[c] / s for c in new_set}
    tv = context.portfolio.total_value
    for c in held:
        if c not in new_set:
            order_target_value(c, 0)
    cur = {c: (pos[c].total_amount * pos[c].price if c in pos else 0.0) for c in new_set}
    order = sorted(new_set, key=lambda c: tv * w[c] - cur[c])
    for c in order:
        tgt = tv * w[c]
        if tgt > cur[c]:
            tgt = min(tgt, cur[c] + context.portfolio.available_cash)
        order_target_value(c, tgt)
    for c in new_set:
        if c not in held:
            g.i3_days[c] = 0
    log.info("I3SET %s | %s | %s" % (
        " ".join("%s:%.3f" % (c, w[c]) for c in sorted(new_set)), "; ".join(why),
        " ".join("%s=%.4f" % (c, vol[c]) for c in sorted(new_set))))
`;
write('i-e9-3', '# i-e9-3: q-e9-3 (overlay off) -> 3 lowest-vol names, weights ∝ 1/vol, set-change rebalance, per-name min-hold + 10% band. Built by study/ETF低波海龟/build-i-e9-2-3.js\n' + b + OVERRIDE);
