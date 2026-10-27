// LIQUIDITY-FLOOR test for ETF动量's point-in-time champion (q-e9-3_pit-champion), epoch 9.
//
// ## Why this book, and why now
//
// `realizability: 2` on the family page rests on `etf-m2 round 2 candidate.json` — a different
// book (an ETF MERGE candidate) measured on the OLD bench — and `realizabilityScope` is EMPTY,
// which by the documented rule means the score describes the BASE, not the candidate. So the
// candidate's tradeability is UNMEASURED, and a VAL on that evidence would repeat the mistake
// CLAUDE.md records for 大小盘轮动 (R=2 scored on the base while the product was always-small).
//
// The book being measured is q-e9-3: the champion 62c2664f's own 26 ETF codes intersected with
// `上市日期 < 2024-01-01`, i.e. listing-date hindsight removed and nothing else touched. It scores
// objective 1.3247 / sharpe 4.20 on TRAIN 2024 — four times the epoch-9 gate — so it is the only
// hindsight-free book this family has that is worth spending a floor measurement on.
//
// ## FLOOR DERIVATION — from this book's own position size
//
// ⚠ This book holds ONE name at a time, which makes its floor unusually demanding and is the
// whole reason the measurement is interesting:
//
//     g_portfolio_value_proportion = [1]        # single sleeve, 100% of capital
//     g_etf_rotation["stock_sum"] = 1           # one ETF held at a time
//
//   capital 1,000,000 x proportion 1.0 / 1 name = 1,000,000 CNY per full position
//   epoch 4 pins order_volume_ratio = 0.05, so filling that position inside a SINGLE daily bar
//   needs that bar's traded value >= 1,000,000 / 0.05 = 20,000,000/day.
//
// liq-1 = 2e7 is the FILL-FEASIBILITY MINIMUM at the book's own size, not a comfort level. That is
// 8x the floor 小市值's liq-1 used (2.5e6), purely because concentration replaces diversification
// here: one name carries what eight carried there.
//
// liq-2 / liq-3 (5x, 10x) are built for the capacity CURVE but NOT queued — a different question,
// worth minutes only once feasibility is settled. Declaring all three up front is what stops the
// curve being fitted to taste afterwards.
//
// ## Insertion site
//
// ONE line, in `get_cached_etf_targets(context)`:
//
//     targets = raw_targets[:g_etf_rotation["stock_sum"]]
//
// i.e. the fully-filtered ranking immediately before truncation to 1, so only names that already
// passed every other screen cost 20 bars of `money`. `context` is in scope there, which is what
// lets the floor read `context.previous_date` and never consult the bar being traded.
//
// ⚠ The SOURCE is the VARIANT, not `strategies/`: it already has py2to3 applied and the frozen
// OVERRIDE appended. Re-applying either would rebind `__jq_orig_initialize` to the wrapper and
// raise RecursionError at import — the exact trap study/五福闹新春/build-e9-pit.js hit. Asserted
// below rather than trusted.
//
//   node study/ETF动量/build-liq-q-e9-3.js --dry
//   node study/ETF动量/build-liq-q-e9-3.js

const fs = require('fs');
const path = require('path');
const harness = require('../../utils/harness-config');

const DRY = process.argv.includes('--dry');
const OUT = __dirname + '/variants';
const SRC = path.join(__dirname, 'variants/q-e9-3_pit-champion.py');

const CAP = harness.config().costs.capital;
const RATIO = harness.config().costs.orderVolumeRatio;
const PROPORTION = 1.0;   // g_portfolio_value_proportion = [1], the only line
const NAMES = 1;          // g_etf_rotation["stock_sum"], read off the source
const BASE_FLOOR = (CAP * PROPORTION / NAMES) / RATIO;   // 2e7
const FLOORS = { 'liq-1': BASE_FLOOR, 'liq-2': BASE_FLOOR * 5, 'liq-3': BASE_FLOOR * 10 };

const SITE = '    targets = raw_targets[:g_etf_rotation["stock_sum"]]';
const INSERTED = '    targets = filter_liquidity_floor(context, raw_targets)[:g_etf_rotation["stock_sum"]]  # liq: ONLY change vs q-e9-3';

const helper = floor => `

# ---------------- liquidity floor (realizability measurement, epoch ${harness.config().epoch}) ----------------
# Derivation: capital ${CAP} x proportion ${PROPORTION} / stock_sum (=${NAMES}) = ${CAP * PROPORTION / NAMES}
# CNY per full position. Epoch 4 pins order_volume_ratio = ${RATIO}, so filling that position inside
# a SINGLE daily bar requires that bar's traded value >= ${CAP * PROPORTION / NAMES} / ${RATIO} = ${BASE_FLOOR}.
# ${floor === BASE_FLOOR ? 'This is the FILL-FEASIBILITY MINIMUM for this book, not a comfort level.'
                        : `This is ${Math.round(floor / BASE_FLOOR)}x that minimum (capacity headroom).`}
LIQ_FLOOR = ${floor}

def filter_liquidity_floor(context, stock_list):
    """Keep names whose TRAILING-20-BAR MEDIAN daily \`money\` is >= LIQ_FLOOR.

    Median, not mean: one spike day must not admit a normally-illiquid name.
    Evaluated on context.previous_date, so the bar being traded today is never consulted.
    Emits one LIQFLOOR line per call via log.error, so it survives the strategy's log.set_level.
    """
    stock_list = list(stock_list)
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
        # Loud, never silent: a swallowed failure reproduces the baseline exactly and is
        # indistinguishable from "the floor did nothing" — which is the one answer that must be
        # trustworthy, since that is what 大小盘轮动's and b3751277's liq-1 actually found.
        log.error('LIQFLOOR ERROR floor=%.0f in=%d exc=%s' % (LIQ_FLOOR, n_in, str(e)))
        return stock_list
    log.error('LIQFLOOR floor=%.0f date=%s in=%d out=%d removedFrac=%.4f slots=%d' % (
        LIQ_FLOOR, str(context.previous_date), n_in, len(keep),
        1.0 - float(len(keep)) / float(n_in), min(${NAMES}, len(keep))))
    return keep
`;

const raw = fs.readFileSync(SRC, 'utf8');

// The source must ALREADY carry the pins, and must not be re-wrapped.
for (const marker of ['avoid_future_data', 'order_volume_ratio', 'set_order_cost']) {
  if (!raw.includes(marker)) throw new Error(`source is missing the pinned marker ${marker}`);
}
if (!/__jq_orig_initialize/.test(raw)) {
  throw new Error('source has no OVERRIDE — this builder expects the already-normalized variant');
}
if (raw.split(SITE).length - 1 !== 1) {
  throw new Error(`expected exactly 1 insertion site, got ${raw.split(SITE).length - 1}`);
}

const built = [];
for (const [tag, floor] of Object.entries(FLOORS)) {
  const body = raw.replace(SITE, INSERTED);
  const out = body + helper(floor);

  // The ONLY difference from q-e9-3 must be the one call site plus the appended helper.
  if (!out.includes('filter_liquidity_floor(context, raw_targets)')) {
    throw new Error(`${tag}: the call site is missing`);
  }
  const changed = body.split('\n').filter((l, i) => l !== raw.split('\n')[i]);
  if (changed.length !== 1 || !changed[0].includes('filter_liquidity_floor')) {
    throw new Error(`${tag}: expected exactly 1 changed line, got ${changed.length}`);
  }
  // Re-wrapping would raise RecursionError at import.
  if ((out.match(/__jq_orig_initialize/g) || []).length !== (raw.match(/__jq_orig_initialize/g) || []).length) {
    throw new Error(`${tag}: OVERRIDE count changed — the book would recurse at import`);
  }

  const dest = path.join(OUT, `q-e9-3_${tag}.py`);
  if (!DRY) fs.writeFileSync(dest, out);
  built.push(`${tag}  floor=${floor.toExponential(2)}  ${path.relative(path.join(__dirname, '../..'), dest)}`);
}

console.log((DRY ? '[dry] ' : '[write] ') + `base floor ${BASE_FLOOR.toExponential(2)} ` +
            `(capital ${CAP} / ${NAMES} name / ratio ${RATIO})`);
for (const b of built) console.log('  ' + b);
console.log(DRY ? '  (nothing written)' : '  liq-1 is the one to RUN; liq-2/3 are the capacity curve, unqueued');
