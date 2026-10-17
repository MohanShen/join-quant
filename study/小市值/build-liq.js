// LIQUIDITY-FLOOR SENSITIVITY for the two UNITS-CORRECTED 低开剥头皮 siblings.
//
// Method copied from study/大小盘轮动/build-liq.js: one floor, inserted as the LAST filter, keeping
// names whose TRAILING-20-BAR MEDIAN daily `money` clears it, evaluated on context.previous_date.
//
// ## Why run it on the CORRECTED books and not the originals
//
// The originals' depth gate was inert (q-e6-14: switching it off moved objective +0.0107,
// correlation 0.9986, 2022 bit-identical), so a floor test on them would have measured a book that
// already admitted anything. After q-e8-1/2 the gate means what it says — names need ¥50k resting
// on the ask — so the question becomes a real one and a different one: ON TOP of a per-tick depth
// gate, does a DAILY-TURNOVER floor still bite? Those are not the same constraint. A name can show
// ¥50k at the touch and trade very little all day.
//
// ## FLOOR DERIVATION — from these books' own position size, not 大小盘轮动's
//
//   harness capital ¥1,000,000 (harness/config/epoch-8.json), g.target_count = 5 names
//     => full position ¥200,000
//   epoch 4 pins order_volume_ratio = 0.05, so filling one full position inside a SINGLE daily bar
//   needs that bar's traded value >= 200,000 / 0.05 = ¥4,000,000/day.
//
// That is 2x 大小盘轮动's 2e6 minimum, purely because these hold 5 names where it holds 10 — the
// derivation must come from each book, which is why this is a separate builder.
//
// Three declared points, all reported whatever they say. A SENSITIVITY CURVE, not a search for the
// floor that looks best; no fourth point is added to improve the shape.
//   liq-1  4e6   can the book be filled at its own position size?
//   liq-2  2e7   5x headroom — and it happens to equal the floor the ETF溢价 experiment used, so
//                this point is cross-family comparable for free
//   liq-3  4e7   10x headroom
//
// ⚠ The LIQFLOOR lines are now READABLE. The old rule that a probe must smuggle its answer out as
// a marker trade rested on a claim CLAUDE.md records as wrong: `utils/backtest-log.js` fetches the
// 日志 tab. So `in=/out=/slots=` can be counted directly rather than inferred from the curve.

const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');

const ROOT = path.join(__dirname, '../..');
const VARIANTS = path.join(__dirname, 'variants');

function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${JSON.stringify(from)}`);
  return s.replace(from, to);
}

const helper = floorExpr => `

# ---------------- liquidity floor (understand experiment, 2026-10-17) ----------------
# Derivation: harness capital 1,000,000 CNY / g.target_count (=5) = 200,000 CNY per full position.
# Epoch 4 pins order_volume_ratio = 0.05, so filling one full position inside a SINGLE daily bar
# requires that bar's traded value >= 200,000 / 0.05 = 4,000,000 CNY. 4e6 is the FILL-FEASIBILITY
# MINIMUM for THIS book (5 names), not a comfort level; 2e7 is 5x headroom and matches the ETF溢价
# floor; 4e7 is 10x.
#
# This sits AFTER the book's own per-tick depth gate (money > 5e4 on the corrected units), so it
# answers a different question: a name can show 50k at the touch and still trade very little all day.
LIQ_FLOOR = ${floorExpr}

def filter_liquidity_floor(context, pairs):
    """Keep (stock, money) pairs whose TRAILING-20-BAR MEDIAN daily \`money\` is >= LIQ_FLOOR.

    Median, not mean: one spike day must not admit a normally-illiquid name.
    Evaluated on context.previous_date, so the bar being traded today is never consulted.
    Accepts tuples or lists — element [0] is the code in both books.
    Emits one LIQFLOOR line per call via log.error, so it survives the strategy's log.set_level.
    """
    n_in = len(pairs)
    if n_in == 0:
        log.error('LIQFLOOR floor=%.0f in=0 out=0 removedFrac=NA slots=0' % LIQ_FLOOR)
        return []
    codes = [p[0] for p in pairs]
    try:
        df = get_price(codes, count=20, end_date=context.previous_date,
                       fields=['money'], frequency='1d', panel=False)
        med = df.groupby('code')['money'].median()
        keep = [p for p in pairs if (p[0] in med.index) and (med[p[0]] >= LIQ_FLOOR)]
    except Exception as e:
        # Loud, never silent: a swallowed failure would reproduce the corrected baseline exactly
        # and be indistinguishable from "the floor did nothing" — the one answer we must be able
        # to trust, since that is what 大小盘轮动's liq-1 actually found.
        log.error('LIQFLOOR ERROR floor=%.0f in=%d exc=%s' % (LIQ_FLOOR, n_in, str(e)))
        return pairs
    log.error('LIQFLOOR floor=%.0f date=%s in=%d out=%d removedFrac=%.4f slots=%d' % (
        LIQ_FLOOR, str(context.previous_date), n_in, len(keep),
        1.0 - float(len(keep)) / float(n_in), min(g.target_count, len(keep))))
    return keep
`;

// ONE insertion point per book: immediately after its own depth gate has produced `valid_stocks`
// and the empty check, i.e. the smallest surviving set — so only names that already passed
// market-cap preselect, hygiene filters and the ¥50k touch gate cost 20 bars of `money`.
const BOOKS = {
  'q-e8-1_8dbd994c': {
    base: 'q-e8-1_8dbd994c-fix.py',
    apply: s => edit(s,
      '    if not valid_stocks:\n        return\n',
      '    if not valid_stocks:\n        return\n' +
      '    valid_stocks = filter_liquidity_floor(context, valid_stocks)  # liq: ONLY change vs -fix\n' +
      '    if not valid_stocks:\n        return\n'),
  },
  'q-e8-2_5e874b5b': {
    base: 'q-e8-2_5e874b5b-fix.py',
    apply: s => edit(s,
      '        if not valid_stocks:\n            return False\n',
      '        if not valid_stocks:\n            return False\n' +
      '        valid_stocks = filter_liquidity_floor(context, valid_stocks)  # liq: ONLY change vs -fix\n' +
      '        if not valid_stocks:\n            return False\n'),
  },
};

const FLOORS = { 'liq-1': '4e6', 'liq-2': '2e7', 'liq-3': '4e7' };

const built = [];
for (const [book, spec] of Object.entries(BOOKS)) {
  // Start from the -fix artifact, which already carries OVERRIDE; strip it so the helper lands
  // before the pins rather than after (the OVERRIDE must stay last — it rebinds the cost calls).
  const withPins = fs.readFileSync(path.join(VARIANTS, spec.base), 'utf8');
  const i = withPins.indexOf(OVERRIDE);
  if (i < 0) throw new Error(`${book}: OVERRIDE not found in ${spec.base} — cannot place the helper`);
  const body = withPins.slice(0, i);
  for (const [tag, floor] of Object.entries(FLOORS)) {
    const out = spec.apply(body) + helper(floor) + OVERRIDE;
    if (!out.includes('filter_liquidity_floor(context, valid_stocks)')) {
      throw new Error(`${book} ${tag}: the call site is missing`);
    }
    fs.writeFileSync(path.join(VARIANTS, `${book}-${tag}.py`), out);
    built.push(`${book}-${tag}`);
  }
}
console.log('built', built.length, 'variants:');
built.forEach(b => console.log('  ', b));
console.log('\nfloors: 4e6 = fill-feasibility minimum (1M/5 names ÷ 0.05), 2e7 = 5x, 4e7 = 10x');
