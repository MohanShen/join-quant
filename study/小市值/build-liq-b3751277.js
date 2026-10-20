// liq-1 LIQUIDITY-FLOOR test for b3751277 (手搓自用_涨停优选后再买入), epoch-9 objective 1.3443.
//
// ## Why this book
//
// It is the 4th-highest objective on the epoch-9 bench, and I initially flagged it as a 涨停-entry
// book — the mechanism behind 打板短线's realizability 1, where a sealed 一字板 cannot be bought at
// any price. **That was wrong**, and reading the code is what showed it:
//
//   - the entry is `run_weekly(weekly_buy, 2, '10:30')` — a weekly rebalance, NOT a buy at the
//     next-day open of yesterday's limit-up, which is the specific unfillable thing;
//   - 涨停 is a HISTORICAL screen (`g.limit_days_window = 3 * 250`, equality tests over a
//     three-year lookback), i.e. a 涨停基因 filter, not a trigger;
//   - it explicitly AVOIDS sealed boards: both the sell path and the limit-up handling gate on
//     `last_price < high_limit` / `close < high_limit`;
//   - `utils/realizability-lint.js` flags none of its four grounded patterns.
//
// The title misled me: 「涨停优选后再买入」 is "screen by limit-up, THEN buy later" — the 再 is
// load-bearing. This is exactly the error that got the `limit-up-entry` lint pattern DELETED from
// the repo ("'buys them' and 'screens them out' both read high_limit with an equality, and the
// difference lives in control flow a line regex cannot see"). I made the regex's mistake by eye.
//
// So the R=1 mechanism does not apply and there is no evidence-based ground to reject it. What is
// still unknown is CAPACITY, and realizability cannot be scored from source — it needs
// measurement. That is this test.
//
// ## FLOOR DERIVATION — from this book's own position size
//
//   harness capital ¥1,000,000 (harness/config/epoch-9.json), g.stock_num = 5
//     => full position ¥200,000
//   epoch 4 pins order_volume_ratio = 0.05, so filling one full position inside a SINGLE daily bar
//   needs that bar's traded value >= 200,000 / 0.05 = ¥4,000,000/day.
//
// liq-1 = 4e6 is the FILL-FEASIBILITY MINIMUM at the book's own size, not a comfort level. It is
// the decisive point: if the floor is inert, the book is fillable as written (R >= 2); if it guts
// the result the way ETF溢价 (8.44 -> 1.10) or 小市值 (7/8 不可成交) did, that is R = 1 measured.
//
// liq-2 / liq-3 (5x and 10x headroom) are built but NOT queued — they are the capacity CURVE, a
// different question, worth spending on only once liq-1 has answered the feasibility one. Three
// points were declared up front so the curve cannot later be fitted to taste.
//
// ⚠ On the known design flaw: `filter_liquidity_floor` calls `get_price(count=20)` per rebalance,
// which CLAUDE.md records as the thing to fix before the next liq run (it cost 75 minutes on a
// DAILY book whose candidate set grew when the floor bit). It is acceptable here and deliberately
// left alone: this book rebalances **weekly** (~52 calls over TRAIN, against ~250), and the
// candidate set is the already-filtered list, not a growing one. Precomputing a median series
// instead would add a lookahead surface for no gain at this cadence.

const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const harness = require('../../utils/harness-config');

const ROOT = path.join(__dirname, '../..');
const OUT = __dirname;

const CAP = harness.config().costs.capital;
const RATIO = harness.config().costs.orderVolumeRatio;
const NAMES = 5;                                  // g.stock_num, read off the source
const BASE_FLOOR = (CAP / NAMES) / RATIO;         // 4e6
const FLOORS = { 'liq-1': BASE_FLOOR, 'liq-2': BASE_FLOOR * 5, 'liq-3': BASE_FLOOR * 10 };

function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${JSON.stringify(from)}`);
  return s.replace(from, to);
}

const helper = floor => `

# ---------------- liquidity floor (realizability measurement, epoch 9) ----------------
# Derivation: harness capital ${CAP} / g.stock_num (=${NAMES}) = ${CAP / NAMES} CNY per full
# position. Epoch 4 pins order_volume_ratio = ${RATIO}, so filling one full position inside a
# SINGLE daily bar requires that bar's traded value >= ${CAP / NAMES} / ${RATIO} = ${BASE_FLOOR}.
# ${floor === BASE_FLOOR ? 'This is the FILL-FEASIBILITY MINIMUM for this book, not a comfort level.'
                         : `This is ${Math.round(floor / BASE_FLOOR)}x that minimum (capacity headroom).`}
LIQ_FLOOR = ${floor}

def filter_liquidity_floor(context, stock_list):
    """Keep names whose TRAILING-20-BAR MEDIAN daily \`money\` is >= LIQ_FLOOR.

    Median, not mean: one spike day must not admit a normally-illiquid name.
    Evaluated on context.previous_date, so the bar being traded today is never consulted.
    Emits one LIQFLOOR line per call via log.error, so it survives the strategy's log.set_level.
    """
    n_in = len(stock_list)
    if n_in == 0:
        log.error('LIQFLOOR floor=%.0f in=0 out=0 removedFrac=NA slots=0' % LIQ_FLOOR)
        return []
    try:
        df = get_price(list(stock_list), count=20, end_date=context.previous_date,
                       fields=['money'], frequency='1d', panel=False)
        med = df.groupby('code')['money'].median()
        keep = [s for s in stock_list if (s in med.index) and (med[s] >= LIQ_FLOOR)]
    except Exception as e:
        # Loud, never silent: a swallowed failure reproduces the baseline exactly and is
        # indistinguishable from "the floor did nothing" — the one answer we must be able to
        # trust, since that is what 大小盘轮动's liq-1 actually found.
        log.error('LIQFLOOR ERROR floor=%.0f in=%d exc=%s' % (LIQ_FLOOR, n_in, str(e)))
        return stock_list
    log.error('LIQFLOOR floor=%.0f date=%s in=%d out=%d removedFrac=%.4f slots=%d' % (
        LIQ_FLOOR, str(context.previous_date), n_in, len(keep),
        1.0 - float(len(keep)) / float(n_in), min(g.stock_num, len(keep))))
    return keep
`;

const src = fs.readdirSync(path.join(ROOT, 'strategies')).find(f => /b3751277/.test(f));
if (!src) throw new Error('b3751277 not found');
const raw = py2to3(fs.readFileSync(path.join(ROOT, 'strategies', src), 'utf8'));

// ONE insertion point: immediately before the final truncation to g.stock_num, i.e. the smallest
// fully-filtered set — so only names that already passed every other screen cost 20 bars of money.
const SITE = '    final_list = stock_list[:g.stock_num]';
const built = [];
for (const [tag, floor] of Object.entries(FLOORS)) {
  const body = edit(raw, SITE,
    '    stock_list = filter_liquidity_floor(context, stock_list)  # liq: ONLY change vs the raw book\n' + SITE);
  const out = body + helper(floor) + OVERRIDE;
  if (!out.includes('filter_liquidity_floor(context, stock_list)')) {
    throw new Error(`${tag}: the call site is missing`);
  }
  // ⚠ The ONLY difference from the raw book must be the inserted call plus the appended helper.
  // A positional line-by-line comparison is the WRONG check for an insertion — it shifts every
  // subsequent line and reported 416 changes on the first run. The exact check is to UNDO the two
  // edits and require byte equality: strip the appended helper, delete the inserted call line,
  // and what remains must be the original. (The assertion refusing was correct behaviour; it was
  // the assertion that was wrong, which is the better way round.)
  const INSERTED = '    stock_list = filter_liquidity_floor(context, stock_list)  # liq: ONLY change vs the raw book';
  const undone = out.slice(0, out.indexOf('\n\n# ---------------- liquidity floor'))
    .split('\n').filter(l => l !== INSERTED).join('\n');
  if (undone !== raw.replace(/\n+$/, '')) {
    const a = undone.split('\n'), b2 = raw.replace(/\n+$/, '').split('\n');
    const first = a.findIndex((l, i) => l !== b2[i]);
    throw new Error(`${tag}: undoing the edits does not reproduce the original ` +
                    `(first difference at line ${first + 1}) — refusing`);
  }
  fs.writeFileSync(path.join(OUT, `b3751277-${tag}.py`), out);
  built.push(`b3751277-${tag} (floor ${floor})`);
}

console.log('[liq] built:', built.join(', '));
console.log(`[liq] derivation: ${CAP} / ${NAMES} names / ${RATIO} = ${BASE_FLOOR} CNY/day`);
console.log('[liq] QUEUE liq-1 ONLY — it answers feasibility. liq-2/liq-3 are the capacity curve.');
console.log('[liq] compare against b3751277\'s own epoch-9 row: objective 1.3443 / sharpe 4.29');
