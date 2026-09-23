// Builds the epoch-6 baseline and one-change variants for the ETF溢价 round.
//   node -e "require('./study/ETF溢价/build-e6.js')"
// Base = 15c36e0c (etf基金溢价-改进版). 09:20: every LOF + ETF whose previous-day SHARE volume
// exceeds 2e6, take the T−1 unit NAV. 09:30: premium = last_price/NAV − 1 (daily bench: last_price at
// 09:30 is the open), keep premium < 0, take the 5 deepest discounts EQUAL weight, sell anything that
// left the set; a hard-coded pre-holiday list flattens the book. No stop, no timing.
// The source sets fund costs (0.00025, min 0) and no slippage; the OVERRIDE pins both. It never sets
// order_volume_ratio, so the epoch-4 5% participation cap is the pin that bites — the only ledger row
// is epoch 2 (obj 1.5642 / annual 177.88 / sharpe 8.87 / maxDD 21.46) and the sibling family
// PT多策略 lost half its annual to that cap alone (369 -> 196).
// Every variant = py2to3(source) + asserted edit(s) + the live OVERRIDE.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');

const ROOT = path.join(__dirname, '../..');
const SRC = path.join(ROOT, 'strategies/2026-06-01_etf基金溢价-改进版-高收益低回撤-速度已最优-15c36e0c.py');
const src = py2to3(fs.readFileSync(SRC, 'utf8'));

function editLine(s, needle, make, { exact = false } = {}) {
  const lines = s.split('\n');
  const hits = lines.map((l, i) => ((exact ? l.trim() === needle.trim() : l.includes(needle)) ? i : -1)).filter(i => i >= 0);
  if (hits.length !== 1) throw new Error(`expected exactly 1 line matching ${JSON.stringify(needle)}, got ${hits.length}`);
  const i = hits[0];
  const indent = lines[i].match(/^[ \t]*/)[0];
  const out = make(indent, lines[i]);
  lines.splice(i, 1, ...(Array.isArray(out) ? out : [out]));
  return lines.join('\n');
}

const UNIV = "fund_list = get_all_securities(['lof', 'etf'], context.previous_date).index.tolist()";
const VOL = 'df = df[df.volume > 2e6]';
const SORT_OLD = "df = df.sort(['premium'], ascending = True)";
const SORT = "df = df.sort_values(['premium'], ascending = True)";
const FILTER = 'df = df[(df.premium < 0)]';
const TOPN = 'order_fund = df[:5].index.tolist()';
const EXEC = "run_daily(market_open, '09:30', reference_security='000300.XSHG')";
const SELL_COMMENT = '    # 卖出';

// u-1 — realizability (the PT多策略 u-7 design): the signal stays where it is (09:30, i.e. the open
// on the daily bench) but the sells and buys move to 14:50, where a daily-mode order fills at the
// close. What is left is the part of the open-vs-NAV gap that survives past the auction.
const exec1450 = s => editLine(
  editLine(s, EXEC, (ind, line) => [line, `${ind}run_daily(market_exec, '14:50', reference_security='000300.XSHG')  # u-1: execute at 14:50`]),
  SELL_COMMENT, ind => [
    `${ind}g.order_fund = order_fund  # u-1: signal fixed at 09:30 (open), executed at 14:50`,
    '',
    'def market_exec(context):',
    `${ind}order_fund = g.order_fund`,
    `${ind}g.max_position = len(order_fund)`,
    `${ind}# 卖出`,
  ], { exact: true });

// u-2 — universe: drop LOF, keep ETF only (edd94ebc's universe). LOF/QDII NAV publication lag is the
// open question CLAUDE.md records for the discount families: if the return lives in LOFs whose T−1
// NAV is stale, "discount" is an artefact of the NAV, not a mispricing.
const etfOnly = s => editLine(s, UNIV, ind => `${ind}fund_list = get_all_securities(['etf'], context.previous_date).index.tolist()  # u-2: ETF only`);

// u-3 — edge test 均值回归 by mirror: same universe, same floor, same top-5 equal weight, but keep
// premium > 0 and take the 5 LARGEST premiums. Both sort branches flipped (only sort_values runs on
// modern pandas; the legacy branch is flipped for consistency).
const mirror = s => editLine(
  editLine(
    editLine(s, SORT, ind => `${ind}df = df.sort_values(['premium'], ascending = False)  # u-3: mirror`),
    SORT_OLD, ind => `${ind}df = df.sort(['premium'], ascending = False)  # u-3: mirror`),
  FILTER, ind => `${ind}df = df[(df.premium > 0)]  # u-3: mirror (premium > 0)`);

// u-4 — edge test 流动性溢价, liquid arm: share-volume floor 2e6 -> 1e8 (the epoch-2 q-1 DQ arm,
// sharpe 1.10 with no participation cap).
const floor1e8 = s => editLine(s, VOL, ind => `${ind}df = df[df.volume > 1e8]  # u-4: liquid floor 1e8`);

// ep-imp-1 — on-mechanism for 流动性溢价 in the realizable direction: floor 2e6 -> 1e7, the epoch-2
// q-1 sweet spot (obj +0.47, maxDD halved) measured with no participation cap.
const floor1e7 = s => editLine(s, VOL, ind => `${ind}df = df[df.volume > 1e7]  # ep-imp-1: floor 1e7`);

// ep-imp-2 — concentration top-5 -> top-2, the epoch-2 q-2 peak (obj +0.35, maxDD +2.9).
const top2 = s => editLine(s, TOPN, ind => `${ind}order_fund = df[:2].index.tolist()  # ep-imp-2: top-2`);

// ep-imp-3 — the REALIZABLE form: signal AND fill at 14:50 (premium from the 14:49 minute close vs
// T−1 NAV, bought at the close). Uses a 1m get_price read because last_price semantics at 14:50 on
// the daily bench are not documented; queued, run only if budget remains.
const closeSignal = s => editLine(
  editLine(s, EXEC, ind => `${ind}run_daily(market_open, '14:50', reference_security='000300.XSHG')  # ep-imp-3: signal + fill at 14:50`),
  "df['last_price'] = [current[c].last_price for c in df.index.tolist()]",
  ind => [
    `${ind}__px = get_price(df.index.tolist(), end_date=context.current_dt, frequency='1m', fields=['close'], count=1, panel=False)  # ep-imp-3: 14:49 minute close`,
    `${ind}__px = __px.set_index('code')['close'] if 'code' in __px.columns else __px['close']`,
    `${ind}df['last_price'] = [float(__px.get(c, float('nan'))) for c in df.index.tolist()]`,
  ]);

const V = {
  'u-1_exec-1450': exec1450,
  'u-2_etf-only': etfOnly,
  'u-3_mirror': mirror,
  'u-4_floor-1e8': floor1e8,
};
// After u-2 (ETF-only: obj 0.8607 -> 1.6193, the LOF leg is a drag), every improve candidate is
// built ON the ETF-only universe: one change from u-2, two from the base. Attribution of the
// second change is against u-2's numbers.
const CANDIDATES = {
  'ep-imp-1': s => floor1e7(etfOnly(s)),
  'ep-imp-2': s => top2(etfOnly(s)),
  'ep-imp-3': s => closeSignal(etfOnly(s)),
};

for (const [id, fn] of Object.entries({ ...V, ...CANDIDATES })) {
  if (fn(src) === src) throw new Error(`${id}: variant is byte-identical to the source`);
}
for (const a of [UNIV, VOL, SORT, FILTER, TOPN, EXEC]) if (!src.includes(a)) throw new Error(`anchor not found: ${a}`);

const dir = __dirname;
fs.mkdirSync(path.join(dir, 'variants'), { recursive: true });
fs.writeFileSync(path.join(dir, 'baseline-e6.py'), src + OVERRIDE);
for (const [id, fn] of Object.entries(V)) fs.writeFileSync(path.join(dir, 'variants', `${id}.py`), fn(src) + OVERRIDE);
fs.mkdirSync(path.join(ROOT, 'enhance/candidates'), { recursive: true });
for (const [id, fn] of Object.entries(CANDIDATES)) fs.writeFileSync(path.join(ROOT, 'enhance/candidates', `${id}.py`), fn(src) + OVERRIDE);
console.log('built baseline-e6 +', Object.keys(V).join(', '), '| candidates:', Object.keys(CANDIDATES).join(', '));
