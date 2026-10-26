// liq-1 LIQUIDITY-FLOOR test for 5a70adc1 (关于小市值的不同筛选条件的差异研究).
//
// ## Why this book
//
// It is the top CREDIBLE book on the epoch-9 bench: objective 1.9882 / sharpe 5.25, zero
// realizability-lint flags, and a weekly rebalance at 10:00 in continuous trading — so none of the
// mechanisms that make the bench's higher scores untradeable apply to it. The five books above it
// are either `call-auction-entry` (竞价擒龙 7.8535, 首板高开 7.5458, 一进二 5.2937, 短线情绪 2.5718)
// or come from families measured at realizability 1 whose defect is CAPACITY and therefore
// invisible to any static pattern (PT多策略 3.6758, etf基金溢价 2.2695).
//
// Capacity is the one axis that cannot be inferred from source — 大小盘轮动's liq-1 took 31 JQ
// minutes and returned the counter-intuitive answer (the floor removed ZERO names on 31/31
// rebalances), while ETF溢价's took sharpe 8.44 -> 1.10. A static rule would have guessed wrong on
// at least one. So this is the measurement, not a prediction.
//
// ## FLOOR DERIVATION — from this book's own position size
//
// ⚠ The capital is NOT the harness capital. This is a multi-strategy framework: each sleeve gets
// `portfolio.total_value * g.portfolio_value_proportion[self.index]`, and the ACTIVE line is
//
//     g.portfolio_value_proportion = [1, 0, 0, 0, 0]   # 测试小市值策略
//     # g.portfolio_value_proportion = [0.7, 0, 0, 0.3, 0]  # 实盘   <- commented out
//
// so the measured book runs 搅屎棍策略 (JSG, index 0) at 100% of capital. Reading the harness
// capital without checking the proportion would have been right here by luck and wrong on the
// author's live config, where the same sleeve gets 70%.
//
//   capital 1,000,000 x proportion 1.0 = 1,000,000 for JSG
//   JSG self.stock_sum = 8  =>  full position 125,000
//   epoch 4 pins order_volume_ratio = 0.05, so filling one full position inside a SINGLE daily bar
//   needs that bar's traded value >= 125,000 / 0.05 = 2,500,000/day.
//
// liq-1 = 2.5e6 is the FILL-FEASIBILITY MINIMUM at the book's own size, not a comfort level.
// liq-2 / liq-3 (5x, 10x) are built for the capacity CURVE but NOT queued — that is a different
// question and only worth minutes once feasibility is settled. Declaring all three up front is
// what stops the curve being fitted to taste later.
//
// ## Insertion site
//
// ONE line, in `JSG.adjust()`:
//
//     stocks = self.filter()[: self.stock_sum]
//
// i.e. the smallest fully-filtered set, immediately before truncation to 8 — so only names that
// already passed every other screen cost 20 bars of `money`.

const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const harness = require('../../utils/harness-config');

const ROOT = path.join(__dirname, '../..');
const OUT = __dirname;

const CAP = harness.config().costs.capital;
const RATIO = harness.config().costs.orderVolumeRatio;
const PROPORTION = 1.0;                           // g.portfolio_value_proportion[0], active line
const NAMES = 8;                                  // JSG.stock_sum, read off the source
const BASE_FLOOR = (CAP * PROPORTION / NAMES) / RATIO;   // 2.5e6
const FLOORS = { 'liq-1': BASE_FLOOR, 'liq-2': BASE_FLOOR * 5, 'liq-3': BASE_FLOOR * 10 };

const SITE = '            stocks = self.filter()[: self.stock_sum]';
const INSERTED = '            stocks = filter_liquidity_floor(self.context, self.filter())[: self.stock_sum]  # liq: ONLY change vs the raw book';

const helper = floor => `

# ---------------- liquidity floor (realizability measurement, epoch ${harness.config().epoch}) ----------------
# Derivation: capital ${CAP} x proportion ${PROPORTION} (g.portfolio_value_proportion[0], the ACTIVE
# line — the author's commented-out 实盘 line gives this sleeve 0.7) / JSG.stock_sum (=${NAMES})
# = ${CAP * PROPORTION / NAMES} CNY per full position. Epoch 4 pins order_volume_ratio = ${RATIO}, so
# filling one full position inside a SINGLE daily bar requires that bar's traded value
# >= ${CAP * PROPORTION / NAMES} / ${RATIO} = ${BASE_FLOOR}.
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
        # trustworthy, since that is what 大小盘轮动's liq-1 actually found.
        log.error('LIQFLOOR ERROR floor=%.0f in=%d exc=%s' % (LIQ_FLOOR, n_in, str(e)))
        return stock_list
    log.error('LIQFLOOR floor=%.0f date=%s in=%d out=%d removedFrac=%.4f slots=%d' % (
        LIQ_FLOOR, str(context.previous_date), n_in, len(keep),
        1.0 - float(len(keep)) / float(n_in), min(${NAMES}, len(keep))))
    return keep
`;

const src = fs.readdirSync(path.join(ROOT, 'strategies')).find(f => /5a70adc1/.test(f));
if (!src) throw new Error('5a70adc1 not found');
const raw = py2to3(fs.readFileSync(path.join(ROOT, 'strategies', src), 'utf8'));

if (raw.split(SITE).length - 1 !== 1) {
  throw new Error(`expected exactly 1 insertion site, got ${raw.split(SITE).length - 1}`);
}

const built = [];
for (const [tag, floor] of Object.entries(FLOORS)) {
  const body = raw.replace(SITE, INSERTED);
  const out = body + helper(floor) + OVERRIDE;
  if (!out.includes('filter_liquidity_floor(self.context, self.filter())')) {
    throw new Error(`${tag}: the call site is missing`);
  }
  // ⚠ The ONLY difference from the raw book must be the swapped call. The exact check is to UNDO
  // that edit on `body` and require BYTE equality with the original.
  //
  // ⚠⚠ Assert on `body`, NOT on a slice of `out`. Reconstructing by cutting `out` at the helper's
  // marker is ambiguous against the file's own trailing newlines — the helper opens with "\n\n#"
  // and the body already ends in a newline, so `indexOf` can land one character early and the
  // check then fails at the LAST line of an otherwise perfect build. It did exactly that here
  // (reported "first difference at line 840" on an 839-line file). The assertion refusing was
  // right; the assertion was wrong, which is the better way round — same lesson as b3751277's
  // positional-compare version.
  const undone = body.split('\n').map(l => (l === INSERTED ? SITE : l)).join('\n');
  if (undone !== raw) {
    const a = undone.split('\n'), b = raw.split('\n');
    const first = a.findIndex((l, i) => l !== b[i]);
    throw new Error(`${tag}: undoing the edit does not reproduce the original ` +
                    `(first difference at line ${first + 1} of ${b.length}) — refusing`);
  }
  fs.writeFileSync(path.join(OUT, `5a70adc1-${tag}.py`), out);
  built.push(`5a70adc1-${tag} (floor ${floor})`);
}

console.log('[liq] built:', built.join(', '));
console.log(`[liq] derivation: ${CAP} x ${PROPORTION} / ${NAMES} names / ${RATIO} = ${BASE_FLOOR} CNY/day`);
console.log('[liq] QUEUE liq-1 ONLY — it answers feasibility. liq-2/liq-3 are the capacity curve.');
console.log("[liq] compare against 5a70adc1's own epoch-9 row: objective 1.9882 / sharpe 5.25");
