// Builds the LIQUIDITY-FLOOR realizability variants for 小盘ETF双轨切换 (understand experiment).
//
// Base 0d1bbe83 + py2to3 + OVERRIDE (frozen pins, as the normalizer applies them) — same builder
// shape as build-u3.js: ONE asserted insertion + an appended helper. The helper is copied verbatim
// from study/大小盘轮动/build-liq.js, with ONE appended log field `heldRemoved=<k>`: how many of the
// PRE-floor stock_list[:g.stock_num] (the 10 names the base would buy) the floor drops. Here the
// decisive quantity is held names, not pool fraction.
//
// FLOOR DERIVATION: harness capital 1,000,000 / g.stock_num 10 = 100,000 per full position;
// order_volume_ratio 0.05 => 100,000 / 0.05 = 2e6 CNY/day = the FILL-FEASIBILITY MINIMUM.
//
// Insertion point: choose_stocks, after get_peg(...) (which returns the FULL list sorted
// market_cap.asc()) and before `return stocks[:g.stock_num]`. An order-preserving filter before the
// slice selects exactly the set that filtering before the sort would. choose_stocks runs only at
// 偷鸡 entry (g.Days == 0), so exactly 3 LIQFLOOR lines are expected on TRAIN 2024.
//
// Parameterised by floor so liq-2 (1e7) reuses it:
//   node study/小盘ETF双轨切换/build-liq.js liq-1     -> variants/liq-1-floor2e6.py
//   node study/小盘ETF双轨切换/build-liq.js liq-2     -> variants/liq-2-floor1e7.py
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');

const ROOT = path.join(__dirname, '../..');
const SRC = 'strategies/2026-10-12_年化51_的晴雨双轨_小盘游击_ETF防御-0d1bbe83.py';

const V = {
  'liq-1': { floor: '2e6', file: 'liq-1-floor2e6' },
  'liq-2': { floor: '1e7', file: 'liq-2-floor1e7' },
};

function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${JSON.stringify(from)}`);
  return s.replace(from, to);
}

const ANCHOR = '    stocks = get_peg(stocks, context.previous_date)\n';
const NEXT = '    # 截取不超过最大持仓数的股票量\n    return stocks[:g.stock_num]\n';

const helper = floorExpr => `

# ----------------- liquidity floor (understand experiment, ${new Date().toISOString().slice(0, 10)}) -----------------
# Floor derivation: base capital 1,000,000 CNY / g.stock_num (=10) = 100,000 CNY per full position.
# Epoch 4 pins order_volume_ratio = 0.05, so filling one full position inside a SINGLE daily bar
# requires that bar's traded value to be >= 100,000 / 0.05 = 2,000,000 CNY. 2e6 is therefore the
# FILL-FEASIBILITY MINIMUM, not a comfort level; 1e7 is 5x headroom.
LIQ_FLOOR = ${floorExpr}

def filter_liquidity_floor(context, stock_list):
    """Keep names whose TRAILING-20-BAR MEDIAN daily \`money\` is >= LIQ_FLOOR.

    Median, not mean: a single spike day must not admit a name that is normally illiquid.
    Evaluated on context.previous_date, so the bar being traded today is never consulted.
    Emits one LIQFLOOR line per call (log.error so it survives the strategy's log.set_level calls)
    recording how many names entered, how many survived, how many of the 10 slots the sleeve
    could therefore fill at all, and heldRemoved = how many of the pre-floor top g.stock_num
    (the names the base would buy) the floor drops.
    """
    n_in = len(stock_list)
    if n_in == 0:
        log.error('LIQFLOOR floor=%.0f in=0 out=0 removedFrac=NA slots=0 heldRemoved=0' % LIQ_FLOOR)
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
    keep_set = set(keep)
    held_removed = len([s for s in stock_list[:g.stock_num] if s not in keep_set])
    log.error('LIQFLOOR floor=%.0f date=%s in=%d out=%d removedFrac=%.4f slots=%d heldRemoved=%d' % (
        LIQ_FLOOR, str(context.previous_date), n_in, len(keep),
        1.0 - float(len(keep)) / float(n_in), min(g.stock_num, len(keep)), held_removed))
    return keep
`;

const id = process.argv[2];
if (!V[id]) throw new Error(`usage: build-liq.js <${Object.keys(V).join('|')}>`);
const { floor, file } = V[id];
const raw = py2to3(fs.readFileSync(path.join(ROOT, SRC), 'utf8'));
edit(raw, ANCHOR + NEXT, ANCHOR + NEXT); // assert the anchor is immediately followed by the slice
const body = edit(raw, ANCHOR, ANCHOR +
  `    stocks = filter_liquidity_floor(context, stocks)  # ${id}: ONLY change vs base\n`);
const added = body.split('\n').length - raw.split('\n').length;
if (added !== 1) throw new Error('expected exactly one inserted line, got ' + added);
const out = path.join(__dirname, 'variants', `${file}.py`);
fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, body + helper(floor) + OVERRIDE);
console.log('built', path.relative(ROOT, out), '| floor', floor);
