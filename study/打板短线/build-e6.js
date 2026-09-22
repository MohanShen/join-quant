// Builds the epoch-6 baseline and one-change variants for the 打板短线 round.
// Base = 439385b4 (首板高开-低开-弱转强混合策略, 子匀). It is the family's researched base
// (epoch-2 study: baseline / q-1..q-5), but the ledger holds NO row for it on any epoch — it
// sits in data/pending-normalize.json — and the 2026-08 findings were measured on the pre-pin
// bench. The source never calls set_slippage / set_commission / set_order_cost and already sets
// avoid_future_data, so the only epoch-4/6 pin that can bind is order_volume_ratio=0.05 (a
// ¥1M book split across the day's candidates, against names filtered to ≥¥5.5e8 / ≥¥3e8 of
// previous-day turnover — expected non-binding). baseline-e6 is the anchor under the live
// OVERRIDE regardless; if it reproduces the epoch-2 digits (total 424.33 / annual 129.24 /
// sharpe 2.58 / maxDD 32.56), q-1..q-5 become same-bench readings.
// Every variant = py2to3(source) + asserted edit(s) + the live OVERRIDE.
//   node -e "require('./study/打板短线/build-e6.js')"
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');

const ROOT = path.join(__dirname, '../..');
const SRC = path.join(ROOT, 'strategies/2026-05-27_首板高开-低开-弱转强混合策略_今年收益1138_61-439385b4.py');
const src = py2to3(fs.readFileSync(SRC, 'utf8'));

// Edits are matched on a unique substring of ONE line; the line's own indentation is preserved.
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

// u-rzq-deconf — q-4's de-confounded rerun. q-4 dropped rzq_stocks from the pool, which ALSO
// raised every surviving name's position (line 46 splits cash by len(qualified_stocks)). Here the
// 弱转强 names stay in the count and are only skipped in the order loop, so the sizing of the
// other two legs is byte-identical to the base and the Δ is the leg's own contribution.
const rzqDeconf = s => editLine(
  editLine(s, 'qualified_stocks=sbgk_stocks+sbdk_stocks+rzq_stocks',
    (ind, line) => [line, `${ind}g.rzq_skip = set(rzq_stocks)  # u-rzq-deconf: counted for sizing, not ordered`]),
  'for s in qualified_stocks:',
  (ind, line) => [line, `${ind}    if s in getattr(g, 'rzq_skip', set()):  # u-rzq-deconf`, `${ind}        continue`]);

// imp-1 — rzq-only book. q-4: the 弱转强 leg is ~17% of closed trades and ~half of terminal
// wealth (fat right tail). On-mechanism for 涨停动量延续 if that is where the edge lives. Must be
// read together with u-rzq-deconf (position-size confound) and per year (q-3: 2023 ≈ −3%).
const rzqOnly = s => editLine(s, 'qualified_stocks=sbgk_stocks+sbdk_stocks+rzq_stocks',
  ind => `${ind}qualified_stocks=rzq_stocks  # imp-1: 弱转强 leg only`);

// u-nolimit — the edge test for 涨停动量延续. Same book, same filters, but the two candidate
// tables are built from NEAR-MISS movers instead of limit-up events:
//   get_hl_stock       (昨日首板)        -> closed ≥ +7% vs pre_close but BELOW the limit
//   get_ever_hl_stock2 (昨日曾涨停未封板) -> high reached ≥ +7% but closed below +7%
// Both helpers feed prepare_stock_list AND the "was it also strong the day before" exclusion
// (g.n_days_limit_up_list), so the control is symmetric. If this book earns ≥ half of the base,
// the return is the filter set, not the limit-up event.
const nearMiss = s => {
  let out = editLine(s, "h_s = get_price(stock_list, end_date=date1, frequency='daily', fields=['close', 'high_limit', 'paused'],",
    ind => `${ind}h_s = get_price(stock_list, end_date=date1, frequency='daily', fields=['close', 'high_limit', 'pre_close', 'paused'],  # u-nolimit`);
  out = editLine(out, ").query('close==high_limit and paused==0').groupby('code').size()",
    ind => `${ind}).query('close < high_limit and close >= 1.07*pre_close and paused==0').groupby('code').size()  # u-nolimit: +7% but not limit-up`);
  out = editLine(out, "h_s = get_price(stock_list, end_date=date1, frequency='daily', fields=['close', 'high', 'high_limit', 'paused'],",
    ind => `${ind}h_s = get_price(stock_list, end_date=date1, frequency='daily', fields=['close', 'high', 'high_limit', 'pre_close', 'paused'],  # u-nolimit`);
  out = editLine(out, ").query('close!=high_limit and high==high_limit and paused==0').groupby('code').size()",
    ind => `${ind}).query('high >= 1.07*pre_close and close < 1.07*pre_close and paused==0').groupby('code').size()  # u-nolimit: touched +7%, closed below`);
  return out;
};

// u-barprice — q-1 proved the explicit MarketOrderStyle(day_open) is IGNORED (bit-identical
// without it); it did not locate the price the daily bench fills at. An absurd limit price:
// still bit-identical => the argument is discarded and fills are the bench's own rule (the
// day's open); no fills / errors => the argument IS read and q-1 needs re-reading. Repo-level.
const absurdPrice = s => editLine(s, 'order_value(s, value, MarketOrderStyle(current_data[s].day_open))',
  ind => `${ind}order_value(s, value, MarketOrderStyle(0.01))  # u-barprice: absurd fill price`);

const V = { 'u-rzq-deconf': rzqDeconf, 'u-nolimit': nearMiss, 'u-barprice': absurdPrice };
// imp-3 — sentiment gate on the breadth of yesterday's limit-up events. u-2023: in 2023 the
// machine still turned (94 trades, 61% win rate) but the fat tail vanished, so the gate targets
// the tail's regime, not the win rate. ONE prior form, no sweep: no new positions on a day whose
// raw limit-up count (before any leg filter) is below the MEDIAN of the trailing 20 days'.
// Two insertions, one concept: record the count where it is computed, gate where it is used.
const sentimentGate = s => editLine(
  editLine(s, 'g.n_days_limit_up_list.append(hl_list)',
    (ind, line) => [line, `${ind}g.hl_counts = (getattr(g, 'hl_counts', []) + [len(hl_list)])[-21:]  # imp-3: raw limit-up breadth`]),
  'target_list, target_list2=prepare_stock_list(context)',
  (ind, line) => [line,
    `${ind}if len(g.hl_counts) > 20:  # imp-3: sentiment gate`,
    `${ind}    __prior = sorted(g.hl_counts[:-1])`,
    `${ind}    if g.hl_counts[-1] < __prior[len(__prior) // 2]:`,
    `${ind}        return []`]);

// imp-4 — drop the 弱转强 leg outright (q-4's line, on TRAIN, cash re-split over the two legs
// that remain). u-rzq-deconf: that leg is the 2022-H1 fat tail AND the whole 2023-H2 loss, while
// 首板高开 + 首板低开 are positive in all four half-years. The on-mechanism candidate that
// u-rzq-deconf points at; TRAIN objective judges it against the base's 0.9668.
const noRzq = s => editLine(s, 'qualified_stocks=sbgk_stocks+sbdk_stocks+rzq_stocks',
  ind => `${ind}qualified_stocks=sbgk_stocks+sbdk_stocks  # imp-4: no 弱转强 leg`);

const CANDIDATES = { 'dbdx-imp-1': rzqOnly, 'dbdx-imp-3': sentimentGate, 'dbdx-imp-4': noRzq };

// no silent no-ops
for (const [id, fn] of Object.entries({ ...V, ...CANDIDATES })) {
  if (fn(src) === src) throw new Error(`${id}: variant is byte-identical to the source`);
}
if (!rzqDeconf(src).includes("if s in getattr(g, 'rzq_skip', set()):")) throw new Error('u-rzq-deconf: skip not inserted');
if (rzqOnly(src).includes('sbgk_stocks+sbdk_stocks+rzq_stocks')) throw new Error('imp-1: pool still mixed');

fs.mkdirSync(path.join(__dirname, 'variants'), { recursive: true });
fs.writeFileSync(path.join(__dirname, 'baseline-e6.py'), src + OVERRIDE);
for (const [id, fn] of Object.entries(V)) fs.writeFileSync(path.join(__dirname, 'variants', `${id}.py`), fn(src) + OVERRIDE);
fs.mkdirSync(path.join(ROOT, 'enhance/candidates'), { recursive: true });
for (const [id, fn] of Object.entries(CANDIDATES)) fs.writeFileSync(path.join(ROOT, 'enhance/candidates', `${id}.py`), fn(src) + OVERRIDE);
console.log('built baseline-e6 +', Object.keys(V).join(', '), '| candidates:', Object.keys(CANDIDATES).join(', '));
