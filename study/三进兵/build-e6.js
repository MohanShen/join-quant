// Builds the epoch-6 baseline and one-change variants for the 三进兵 round.
// Base = 7d1012a5 (【策略研发】三进兵策略与研究报告). e4eb8dca is the same file modulo log
// strings and blank lines (epoch-2 q-dup); 87ab0122 / 7552f0ef are the author's v2: a wall-clock
// grid search (calculate() reads get_trade_days(end_date=datetime.datetime.now(), count=250), i.e.
// the 250 trading days before the REAL today, not the backtest's) — unmeasurable on the bench and
// not a variant of the base's mechanism, so they are not built here.
// The source already declares the bench's stock cost table (0.0003/0.0003/0.001/min 5), so the
// epoch-6 pin is a no-op; the OVERRIDE replaces PriceRelatedSlippage(0.00246) with FixedSlippage(0)
// (as epoch 2 did) and order_volume_ratio 0.25 with 0.05 (epoch 4; 5 large ChiNext names at
// ~11–26% deployment of 1M, so no fill should be capped). baseline-e6 is the anchor regardless —
// the ledger holds only epoch-2 rows for this family.
// Every variant = py2to3(source) + asserted edit(s) + the live OVERRIDE.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');

const ROOT = path.join(__dirname, '../..');
const SRC = path.join(ROOT, 'strategies/2026-06-03_策略研发_三进兵策略与研究报告-7d1012a5.py');
const src = py2to3(fs.readFileSync(SRC, 'utf8'));

function editLine(s, needle, make) {
  const lines = s.split('\n');
  const hits = lines.map((l, i) => (l.includes(needle) ? i : -1)).filter(i => i >= 0);
  if (hits.length !== 1) throw new Error(`expected exactly 1 line containing ${JSON.stringify(needle)}, got ${hits.length}`);
  const i = hits[0];
  const indent = lines[i].match(/^[ \t]*/)[0];
  const out = make(indent, lines[i]);
  lines.splice(i, 1, ...(Array.isArray(out) ? out : [out]));
  return lines.join('\n');
}

const POOL_LINE = "g.stokcs_pool = ['300014.XSHE', '300059.XSHE', '300168.XSHE', '300253.XSHE', '300274.XSHE']";

// u-1 — edge test 趋势择时 (transfer): the author writes 「发现本策略并不是适合所有的股票的」 and
// hand-picked the 5 names, and q-1 measured that basket as a hindsight loser (B&H −48% on TRAIN,
// worse than the index). Same overlay, same 5-name scarcity, on a pool fixed by a RULE from data
// that ends before TRAIN: the 5 largest 创业板指 constituents by market cap on 2021-12-31.
// If the overlay's timing information is a property of the pattern it should show up here too
// (overlay ≫ this pool's own B&H); if it was the names, it will not.
const poolRule = (n, tag) => s => editLine(s, POOL_LINE, ind => [
  `${ind}__pool = get_index_stocks('399006.XSHE', date='2021-12-31')  # ${tag}: pre-registered pool rule, data ends before TRAIN`,
  `${ind}__pool_df = get_fundamentals(query(valuation.code, valuation.market_cap).filter(valuation.code.in_(__pool)).order_by(valuation.market_cap.desc()).limit(${n}), date='2021-12-31')`,
  `${ind}g.stokcs_pool = list(__pool_df['code'])`,
]);
const poolTransfer = poolRule(5, 'u-1');

// u-1c — the control u-1 is read against: the SAME rule-picked 5 names, bought once at equal
// weight on the first bar and held (the q-1 hold control's exact form, on the u-1 pool). The
// overlay's Δ vs this book is what "timing information" means here.
const HOLD_BODY = [
  'def trade_func(context):',
  '    # u-1c: buy-and-hold control on the u-1 pool (q-1 hold form: equal weight on the first bar, never trade again)',
  '    if getattr(g, \'bought\', False):',
  '        return',
  '    for stock in g.stokcs_pool:',
  '        order_target_value(stock, context.portfolio.total_value / len(g.stokcs_pool))',
  '    g.bought = True',
  '',
  '',
];
const holdOnPool = s => {
  const lines = poolTransfer(s).split('\n');
  const start = lines.findIndex(l => l.startsWith('def trade_func('));
  const end = lines.findIndex((l, i) => i > start && l.startsWith('def '));
  if (start < 0 || end < 0) throw new Error('u-1c: trade_func not found');
  lines.splice(start, end - start, ...HOLD_BODY);
  return lines.join('\n').replace('# u-1: pre-registered', '# u-1c: pre-registered');
};

// u-3 — q-1 merged the three exits (is_sell / is_loss) into one ablation and could not split the
// +0.56 sharpe between them; q-4 showed the (inverted) is_sell is an accidental take-profit that
// helps. This isolates the third rule: the close < EMA20 (while EMA20 < EMA60) stop, off.
const noStop = s => editLine(s, 're_loss = is_loss(stock, yesterday, g.ma_min,g.ma_med,g.ma_max)', ind => `${ind}re_loss = False  # u-3: EMA20 stop off`);

// u-2 — q-3 read the entry as a bottom-reversal pattern (EMA5 crosses above EMA60 WHILE EMA20 is
// still below EMA60) that pays only in V-shaped bear rebounds (2022 P/L 2.64) and loses in a
// grinding year (2023, 1W/12L). Drop the EMA20 < EMA60 clause: the entry becomes a plain
// EMA5/EMA60 golden cross in any phase. If 2023 stops losing, the bottom-only filter is the cost.
const noBottomFilter = s => editLine(s,
  'if (y_ma_min_value > y_ma_max_value) and (by_ma_min_value < by_ma_max_value) and (y_ma_med_value < y_ma_max_value):',
  ind => `${ind}if (y_ma_min_value > y_ma_max_value) and (by_ma_min_value < by_ma_max_value):  # u-2: bottom-only clause (EMA20 < EMA60) dropped`);

// u-1b — u-1 refuted on ONE pool; a refutation from a single 5-name pool can be a fluke of those
// names just as the author's result was of his. Second, disjoint rule pool: ranks 6–10 by the
// same 2021-12-31 market-cap rule (same overlay), with its own hold control (u-1bc).
// u-1d / u-1e — pools 1 and 2 disagree (−1.8pp vs +16pp at equal exposure), so two more disjoint
// slices of the same rule (ranks 11–15, 16–20), each with its hold control, give four unbiased
// five-name pools to read the sign of the overlay's timing information on.
const poolSlice = (tag, lo, hi) => s => editLine(s, POOL_LINE, ind => [
  `${ind}__pool = get_index_stocks('399006.XSHE', date='2021-12-31')  # ${tag}: pre-registered pool rule, ranks ${lo + 1}-${hi} by cap, data ends before TRAIN`,
  `${ind}__pool_df = get_fundamentals(query(valuation.code, valuation.market_cap).filter(valuation.code.in_(__pool)).order_by(valuation.market_cap.desc()).limit(${hi}), date='2021-12-31')`,
  `${ind}g.stokcs_pool = list(__pool_df['code'])[${lo}:${hi}]`,
]);
const holdOn = (tag, fn) => s => {
  const lines = fn(s).split('\n');
  const start = lines.findIndex(l => l.startsWith('def trade_func('));
  const end = lines.findIndex((l, i) => i > start && l.startsWith('def '));
  if (start < 0 || end < 0) throw new Error(`${tag}: trade_func not found`);
  lines.splice(start, end - start, ...HOLD_BODY.map(l => l.replace('u-1c:', `${tag}:`)));
  return lines.join('\n').replace(/# u-1[a-z]?: pre-registered/, `# ${tag}: pre-registered`);
};
const poolTransfer2 = poolSlice('u-1b', 5, 10);
const holdOnPool2 = holdOn('u-1bc', poolTransfer2);
const poolTransfer4 = poolSlice('u-1d', 10, 15);
const holdOnPool4 = holdOn('u-1dc', poolTransfer4);
const poolTransfer5 = poolSlice('u-1e', 15, 20);
const holdOnPool5 = holdOn('u-1ec', poolTransfer5);

// u-0c — q-1's hold control (the author's 5 names, equal weight on the first bar, never traded
// again) re-run on the epoch-6 bench so the baseline, u-2 and u-3 can be read at equal exposure
// against a curve on the same bench. Same body as u-1c, on the untouched pool line.
const holdAuthorBasket = s => {
  const lines = s.split('\n');
  const start = lines.findIndex(l => l.startsWith('def trade_func('));
  const end = lines.findIndex((l, i) => i > start && l.startsWith('def '));
  if (start < 0 || end < 0) throw new Error('u-0c: trade_func not found');
  lines.splice(start, end - start, ...HOLD_BODY.map(l => l.replace('u-1c: buy-and-hold control on the u-1 pool', 'u-0c: buy-and-hold control on the author\'s basket')));
  return lines.join('\n');
};

const V = {
  'u-0c_hold-author-basket': holdAuthorBasket,
  'u-1_pool-transfer': poolTransfer,
  'u-1c_hold-on-pool': holdOnPool,
  'u-1b_pool-transfer-6-10': poolTransfer2,
  'u-1bc_hold-on-pool-6-10': holdOnPool2,
  'u-1d_pool-transfer-11-15': poolTransfer4,
  'u-1dc_hold-on-pool-11-15': holdOnPool4,
  'u-1e_pool-transfer-16-20': poolTransfer5,
  'u-1ec_hold-on-pool-16-20': holdOnPool5,
  'u-3_no-stop': noStop,
  'u-2_no-bottom-filter': noBottomFilter,
};

// imp-1 — q-2: the book is 11–26% deployed because signals are scarce (27 trades / 2 years on 5
// names), and sizing is scale-invariant so it cannot be fixed by leverage. The one on-mechanism
// lever is more names under the same rule: the 20 largest by the u-1 rule, hold_count unchanged
// at 5. Only meaningful if u-1 shows the overlay transfers; queued after it.
const widePool = poolRule(20, 'imp-1');
const CANDIDATES = { 'sjb-imp-1': widePool };

for (const [id, fn] of Object.entries({ ...V, ...CANDIDATES })) {
  if (fn(src) === src) throw new Error(`${id}: variant is byte-identical to the source`);
}
if (!holdOnPool(src).includes("g.bought = True")) throw new Error('u-1c: hold body missing');
if (holdOnPool(src).includes('re_value = is_buy(')) throw new Error('u-1c: signal path still present');

const dir = __dirname;
fs.mkdirSync(path.join(dir, 'variants'), { recursive: true });
fs.writeFileSync(path.join(dir, 'baseline-e6.py'), src + OVERRIDE);
for (const [id, fn] of Object.entries(V)) fs.writeFileSync(path.join(dir, 'variants', `${id}.py`), fn(src) + OVERRIDE);
fs.mkdirSync(path.join(ROOT, 'enhance/candidates'), { recursive: true });
for (const [id, fn] of Object.entries(CANDIDATES)) fs.writeFileSync(path.join(ROOT, 'enhance/candidates', `${id}.py`), fn(src) + OVERRIDE);
console.log('built baseline-e6 +', Object.keys(V).join(', '), '| candidates:', Object.keys(CANDIDATES).join(', '));
