// q-e9-champ-liq — liq-1 LIQUIDITY-FEASIBILITY FLOOR for the 小市值 family's epoch-9 champion
// `strategies/2026-10-26_中小盘趋势策略_年化_85-0a7de9fa.py` (objective 2.6282 / sharpe 7.07).
//
// ## Why this book, and why this is the family's binding measurement
//
// 小市值's frontmatter carries `realizability: 1`, but that score was evidenced on the 低开反转
// scalping branch (min-500 market cap, 9:26 auction entry, ~100% daily turnover) — a book that is
// no longer the family's candidate. The binding closure q-e9-liq-5a70adc1 says realizability must
// be re-bounded PER BRANCH, and capacity is the one axis that cannot be read off source:
// 大小盘轮动's liq-1 removed ZERO names on 31/31 rebalances (curve bit-identical), while ETF溢价's
// took sharpe 8.44 -> 1.10. So this is a measurement, not a prediction.
//
// ## FLOOR DERIVATION — from this book's own position size, nothing guessed
//
// This is a SINGLE-SLEEVE book: no `g.portfolio_value_proportion`, and `buy_security()` (L699-731)
// splits `context.portfolio.cash` evenly across the names it still needs, bounded by
// `g.target_stock_count` (L111 = 2). So a full position is the whole capital over 2 names:
//
//   capital 1,000,000 / g.target_stock_count 2        = 500,000 per position
//   epoch 4 pins order_volume_ratio = 0.05, so filling one full position inside a SINGLE daily bar
//   needs that bar's traded value >= 500,000 / 0.05  = 10,000,000 CNY/day.
//
// liq-1 = 1e7 is the FILL-FEASIBILITY MINIMUM at the book's own size, not a comfort level.
// liq-2 (5x) / liq-3 (10x) are DECLARED here so the capacity curve cannot be fitted to taste
// later, but only liq-1 is BUILT and only liq-1 is queued — feasibility first.
//
// ## Insertion site — ONE line
//
//   L248  `    return bbi_pass`  ->  `    return filter_liquidity_floor(context, bbi_pass)`
//
// That is the last line of `get_stock_list(context)` (L159-248), i.e. the smallest fully-screened
// set, after 市值 / 价格 / ST / BBI. Only genuine candidates pay for 20 bars of `money`, and the
// floor cannot interact with any other screen's ordering.
//
// ⚠ The book already filters `market_cap.between(10, 80)` (¥1.0bn-¥8.0bn) and `g.up_price = 80`,
// so the a-priori expectation is that the floor is INERT. Pre-registered three-way verdict is in
// the queue entry; it was locked before this file existed.

const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const harness = require('../../utils/harness-config');

const ROOT = path.join(__dirname, '../..');
const OUT = __dirname;

const CAP = harness.config().costs.capital;
const RATIO = harness.config().costs.orderVolumeRatio;
const NAMES = 2;                                  // g.target_stock_count, L111, read off the source
const PER_POSITION = CAP / NAMES;
const BASE_FLOOR = PER_POSITION / RATIO;          // 1e7

// Declared up front; only liq-1 is built. liq-2/liq-3 are the capacity CURVE, a different question.
const FLOORS = { 'liq-1': BASE_FLOOR, 'liq-2': BASE_FLOOR * 5, 'liq-3': BASE_FLOOR * 10 };
const BUILD = ['liq-1'];

const SITE = '    return bbi_pass';
const INSERTED = '    return filter_liquidity_floor(context, bbi_pass)  # liq: ONLY change vs the raw book';

const helper = floor => `

# ---------------- liquidity floor (realizability measurement, epoch ${harness.config().epoch}) ----------------
# Derivation, entirely from this book's own position size:
#   capital ${CAP} / g.target_stock_count (=${NAMES}, L111) = ${PER_POSITION} CNY per full position
#   epoch 4 pins order_volume_ratio = ${RATIO}, so filling one full position inside a SINGLE daily
#   bar requires that bar's traded value >= ${PER_POSITION} / ${RATIO} = ${BASE_FLOOR} CNY/day.
# ${floor === BASE_FLOOR ? 'This is the FILL-FEASIBILITY MINIMUM for this book, not a comfort level.'
                         : `This is ${Math.round(floor / BASE_FLOOR)}x that minimum (capacity headroom).`}
LIQ_FLOOR = ${floor}

# Cumulative counters, so the LAST LIQFLOOR line is self-sufficient even if the log tab is
# truncated by the reader's limit. The per-call line is still emitted — the count of calls where
# in > out is the whole point of this measurement and must not be inferred from a total.
LIQ_STATS = {'calls': 0, 'cut': 0, 'n_in': 0, 'n_out': 0, 'err': 0}

def filter_liquidity_floor(context, stock_list):
    """Keep names whose TRAILING-20-BAR MEDIAN daily \`money\` is >= LIQ_FLOOR.

    Median, not mean: one spike day must not admit a normally-illiquid name.
    Evaluated at context.previous_date, so the bar being traded today is NEVER consulted — the
    floor is a point-in-time feasibility screen, not a lookahead.
    Emits one LIQFLOOR line per call via log.error, so it survives log.set_level.
    """
    stock_list = list(stock_list)
    n_in = len(stock_list)
    LIQ_STATS['calls'] += 1
    LIQ_STATS['n_in'] += n_in
    if n_in == 0:
        log.error('LIQFLOOR floor=%.0f date=%s in=0 out=0 removedFrac=NA slots=0 cumCalls=%d cumCut=%d'
                  % (LIQ_FLOOR, str(context.previous_date), LIQ_STATS['calls'], LIQ_STATS['cut']))
        return []
    try:
        df = get_price(stock_list, count=20, end_date=context.previous_date,
                       fields=['money'], frequency='1d', panel=False)
        med = df.groupby('code')['money'].median()
        keep = [s for s in stock_list if (s in med.index) and (med[s] >= LIQ_FLOOR)]
    except Exception as e:
        # Loud, never silent: a swallowed failure reproduces the baseline exactly and is
        # indistinguishable from "the floor did nothing" — which is the one answer that must be
        # trustworthy, since that is what 大小盘轮动's liq-1 actually found.
        LIQ_STATS['err'] += 1
        log.error('LIQFLOOR ERROR floor=%.0f in=%d exc=%s cumErr=%d'
                  % (LIQ_FLOOR, n_in, str(e), LIQ_STATS['err']))
        return stock_list
    n_out = len(keep)
    LIQ_STATS['n_out'] += n_out
    if n_out < n_in:
        LIQ_STATS['cut'] += 1
    log.error('LIQFLOOR floor=%.0f date=%s in=%d out=%d removedFrac=%.4f slots=%d cumCalls=%d cumCut=%d cumIn=%d cumOut=%d cumErr=%d'
              % (LIQ_FLOOR, str(context.previous_date), n_in, n_out,
                 1.0 - float(n_out) / float(n_in), min(${NAMES}, n_out),
                 LIQ_STATS['calls'], LIQ_STATS['cut'], LIQ_STATS['n_in'], LIQ_STATS['n_out'],
                 LIQ_STATS['err']))
    return keep
`;

const src = fs.readdirSync(path.join(ROOT, 'strategies')).find(f => /0a7de9fa/.test(f));
if (!src) throw new Error('0a7de9fa not found in strategies/');

// ⚠ The comparison baseline is py2to3(raw), NOT the on-disk file: the variant is built on the
// py2to3 output, which is also what the normalizer measured the control on.
const raw = py2to3(fs.readFileSync(path.join(ROOT, 'strategies', src), 'utf8'));

const hits = raw.split('\n').filter(l => l === SITE).length;
if (hits !== 1) throw new Error(`expected exactly 1 insertion site, got ${hits}`);

const built = [];
for (const tag of BUILD) {
  const floor = FLOORS[tag];
  // Line-exact replacement: `    return bbi_pass` must not match a longer line by substring.
  const body = raw.split('\n').map(l => (l === SITE ? INSERTED : l)).join('\n');
  const out = body + helper(floor) + OVERRIDE;
  if (!out.includes('return filter_liquidity_floor(context, bbi_pass)')) {
    throw new Error(`${tag}: the call site is missing`);
  }
  // ⚠⚠ The ONLY difference from py2to3(raw) must be the swapped line. Assert on `body` — the
  // PRE-OVERRIDE text — never on a slice of `out`: cutting `out` at the helper's marker is
  // ambiguous against the file's own trailing newlines (the helper opens "\n\n#" and the body
  // already ends in a newline), and that is exactly what made build-liq-5a70adc1 report a false
  // "first difference at line 840" of an 839-line file.
  const undone = body.split('\n').map(l => (l === INSERTED ? SITE : l)).join('\n');
  if (undone !== raw) {
    const a = undone.split('\n'), b = raw.split('\n');
    const first = a.findIndex((l, i) => l !== b[i]);
    throw new Error(`${tag}: undoing the edit does not reproduce py2to3(raw) byte-for-byte ` +
                    `(first difference at line ${first + 1} of ${b.length}) — refusing`);
  }
  fs.writeFileSync(path.join(OUT, `variants/0a7de9fa-${tag}.py`), out);
  built.push(`variants/0a7de9fa-${tag}.py (floor ${floor})`);
}

console.log('[liq] built:', built.join(', '));
console.log(`[liq] derivation: capital ${CAP} / ${NAMES} names = ${PER_POSITION} per position; ` +
            `/ order_volume_ratio ${RATIO} = ${BASE_FLOOR} CNY/day`);
console.log(`[liq] FLOORS declared: ${Object.entries(FLOORS).map(([k, v]) => `${k}=${v}`).join(' ')}`);
console.log('[liq] QUEUE liq-1 ONLY — it answers feasibility. liq-2/liq-3 are the capacity curve.');
console.log("[liq] control = the champion's own epoch-9 row: objective 2.6282 / sharpe 7.07 / " +
            'annual 276.82 / maxDD 14.00');
