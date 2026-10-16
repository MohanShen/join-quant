// Builds the LIQUIDITY-FLOOR SENSITIVITY variants for 大小盘轮动 (understand experiment).
//
// Base = study/大小盘轮动/baseline-e6.py's source, i.e. py2to3(2f5bc859) + the live OVERRIDE —
// the family champion (obj 0.4567 / sharpe 2.68 / annual 59.19 / maxDD 13.52, per-year 2.38 / 2.82).
// ONE change per variant, in ONE place: a liquidity floor added to the SMALL-CAP SLEEVE ONLY
// (daily_my_trader_1). The 白马 sleeve, the three timing votes, the dapan divergence overlay and
// the bond leg are untouched.
//
// WHY: realizability was scored 2 on 2026-10-16 on the reasoning that the family has NO liquidity
// or volume gate anywhere — selection ends in "ascending market_cap, take 10" over the thinnest
// end of A-shares, so only the harness's order_volume_ratio=0.05 caps participation. The same test
// moved ETF溢价 from sharpe 8.44 to 1.10 and found 小市值 7/8 不可成交. The axis is untested here.
//
// FLOOR DERIVATION (also stated in the injected Python):
//   base capital 1,000,000 CNY, sleeve holds g.stock_num = 10 names -> full position = 100,000 CNY.
//   epoch 4 pins order_volume_ratio = 0.05, so filling 100,000 inside ONE daily bar needs same-day
//   traded value >= 100,000 / 0.05 = 2,000,000 CNY/day. That is the FILL-FEASIBILITY MINIMUM.
//   Liquidity = TRAILING-20-BAR MEDIAN of daily `money` (median, not mean: one spike day must not
//   admit a normally-illiquid name), evaluated on context.previous_date (no lookahead).
//
// Three declared points, run in this order. This is a SENSITIVITY CURVE, like the family's own
// ¥9/¥12/¥5 price-cap curve (u-7 / u-8 / dxp-imp-3) — NOT a search for the best floor. All three
// are reported whatever they say; no fourth point is added to improve the shape.
//   liq-1  2e6   can the book even be filled at its own position size?
//   liq-2  1e7   5x headroom — a realistic retail / small-fund comfort level
//   liq-3  2e7   the floor the ETF溢价 experiment used, for cross-family comparability
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');

const ROOT = path.join(__dirname, '../..');
const SRC = path.join(ROOT, 'strategies/2026-05-20_四择时高息低价小市值和白马大市值轮动-2f5bc859.py');
const src = py2to3(fs.readFileSync(SRC, 'utf8'));

function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${JSON.stringify(from)}`);
  return s.replace(from, to);
}

// The ONE insertion point: the last filter of the small-cap sleeve's chain, immediately before the
// ascending-market_cap sort + take-10. Placing the floor LAST in the chain is also the cheapest
// place to put it — only the names that already survived dividend/profitability/hygiene/price get
// 20 bars of `money` fetched, which matters on a strategy that has slow-skipped twice.
const CHAIN = '    stocks = filter_highprice_stock(context, stocks)\n';

const helper = floorExpr => `

# ----------------- liquidity floor (understand experiment, ${new Date().toISOString().slice(0, 10)}) -----------------
# Floor derivation: base capital 1,000,000 CNY / g.stock_num (=10) = 100,000 CNY per full position.
# Epoch 4 pins order_volume_ratio = 0.05, so filling one full position inside a SINGLE daily bar
# requires that bar's traded value to be >= 100,000 / 0.05 = 2,000,000 CNY. 2e6 is therefore the
# FILL-FEASIBILITY MINIMUM, not a comfort level; 1e7 is 5x headroom; 2e7 matches the floor the
# ETF溢价 liquidity experiment used, for cross-family comparability.
LIQ_FLOOR = ${floorExpr}

def filter_liquidity_floor(context, stock_list):
    """Keep names whose TRAILING-20-BAR MEDIAN daily \`money\` is >= LIQ_FLOOR.

    Median, not mean: a single spike day must not admit a name that is normally illiquid.
    Evaluated on context.previous_date, so the bar being traded today is never consulted.
    Emits one LIQFLOOR line per call (log.error so it survives the strategy's log.set_level calls)
    recording how many names entered, how many survived, and how many of the 10 slots the sleeve
    could therefore fill at all.
    """
    n_in = len(stock_list)
    if n_in == 0:
        log.error('LIQFLOOR floor=%.0f in=0 out=0 removedFrac=NA slots=0' % LIQ_FLOOR)
        return []
    try:
        df = get_price(stock_list, count=20, end_date=context.previous_date,
                       fields=['money'], frequency='1d', panel=False)
        med = df.groupby('code')['money'].median()
        keep = [s for s in stock_list if (s in med.index) and (med[s] >= LIQ_FLOOR)]
    except Exception as e:
        # Loud, never silent: a swallowed failure here would reproduce the baseline and be
        # indistinguishable from "the floor did nothing".
        log.error('LIQFLOOR ERROR floor=%.0f in=%d exc=%s' % (LIQ_FLOOR, n_in, str(e)))
        return stock_list
    log.error('LIQFLOOR floor=%.0f date=%s in=%d out=%d removedFrac=%.4f slots=%d' % (
        LIQ_FLOOR, str(context.previous_date), n_in, len(keep),
        1.0 - float(len(keep)) / float(n_in), min(g.stock_num, len(keep))))
    return keep
`;

const V = {
  // 1. fill-feasibility minimum at the sleeve's own position size
  'liq-1_floor-2e6': { floor: '2e6' },
  // 2. 5x headroom — realistic retail / small-fund comfort
  'liq-2_floor-1e7': { floor: '1e7' },
  // 3. the ETF溢价 floor, for cross-family comparability
  'liq-3_floor-2e7': { floor: '2e7' },
};

const dir = path.join(__dirname, 'variants');
fs.mkdirSync(dir, { recursive: true });
for (const [id, { floor }] of Object.entries(V)) {
  const body = edit(src, CHAIN, CHAIN +
    `    stocks = filter_liquidity_floor(context, stocks)  # ${id}: ONLY change vs baseline-e6\n`) +
    helper(floor);
  fs.writeFileSync(path.join(dir, `${id}.py`), body + OVERRIDE);
}
console.log('built', Object.keys(V).join(', '));
