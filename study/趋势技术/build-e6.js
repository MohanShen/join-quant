// Builds the epoch-6 baseline and one-change variants for the 趋势技术 round.
// Base = 33b1b1e3 (开盘前输出当日交易计划的趋势跟踪策略) — the family's only gate-passing member on
// epoch 2 (sharpe 1.94, obj 0.2936) and the epoch-2 study base (study/趋势技术/baseline.py, old
// OVERRIDE). On epoch 6 the normalizer returned `no-trades` for it (harness/normalize-train.tsv,
// epoch 6 row): the epoch-4 pin `avoid_future_data=True` is the only bench change that can empty
// a book, and the epoch-2 audit (q-struct) had already flagged that calculate_signals runs at 08:00
// with every get_price end_date=today and a `day_open > 0` pool filter — i.e. the epoch-2 number
// was produced with today's close and today's open visible before the open.
// Every variant = py2to3(source) + asserted edit(s) + the live OVERRIDE.
const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');

const ROOT = path.join(__dirname, '../..');
const SRC = path.join(ROOT, 'strategies/2026-06-29_开盘前输出当日交易计划的趋势跟踪策略-33b1b1e3.py');
const src = py2to3(fs.readFileSync(SRC, 'utf8'));

function edit(s, from, to) {
  const n = s.split(from).length - 1;
  if (n !== 1) throw new Error(`expected exactly 1 match, got ${n}: ${from}`);
  return s.replace(from, to);
}

// The four places the 08:00 signal pass reads today's data. `context.previous_date` is what an
// honest 08:00 trader has: yesterday's close for RPS / slope / MA20; the pool keeps ST / paused /
// 次新 but drops "has an open today", which cannot be known before 09:30. The 09:30 execution
// path (order at day_open) is untouched — it is legal at 09:30.
const TREND = '        g.market_trend_bull = check_market_trend(current_date)\n';
const CLOSES = '        df_close = get_batch_close_prices(stock_pool, current_date, total_days_needed)\n';
const DAYOPEN = '                current_data[stock].day_open > 0 and\n';
const FALLBACK = '        rps = day_rps.get(stock, calculate_single_rps(stock, current_date, g.N))\n';

const TREND_CLEAN = TREND.replace('current_date', 'context.previous_date');
const poolOnly = s => edit(s, DAYOPEN, '');
const clean = s => edit(edit(edit(poolOnly(s),
  TREND, TREND_CLEAN),
  CLOSES, CLOSES.replace('current_date', 'context.previous_date')),
  FALLBACK, FALLBACK.replace('current_date', 'context.previous_date'));

// Entry band 85<day<92 & week>80 & month>75, exit day>96 or <80 — mirrored to the weak end.
const BAND = [
  ['    g.day_rps_low = 85\n', '    g.day_rps_low = 8\n'],
  ['    g.day_rps_high = 92\n', '    g.day_rps_high = 15\n'],
  ['    g.week_rps_threshold = 80\n', '    g.week_rps_threshold = 20\n'],
  ['    g.month_rps_threshold = 75\n', '    g.month_rps_threshold = 25\n'],
  ['    g.sell_rps_high = 96\n', '    g.sell_rps_high = 20\n'],
  ['    g.sell_rps_low = 80\n', '    g.sell_rps_low = 4\n'],
];
const BUYLIST = '        g.buy_list = candidates[:g.M]\n';
const OPEN_MARK = '    # 开仓\n';
const WEEK = '                    w_rps > g.week_rps_threshold and \n';
const MONTH = '                    m_rps > g.month_rps_threshold):\n';

const V = {};
Object.assign(V, {
  // the whole lookahead removed at once (4 edits, one concept). The epoch-6 anchor.
  'e6-1_clean': clean,
  // platform-semantics probe: only the 08:00 day_open pool filter removed, get_price end_date=today
  // kept. Trades => avoid_future_data truncates get_price to yesterday (then == e6-1); no-trades =>
  // it raises (caught by calculate_signals' try/except, which empties the book).
  'e6-1a_pool-only': poolOnly,
  // edge test 趋势择时: clean book, index MA20 gate always open
  'u-2_clean-no-gate': s => edit(clean(s), TREND_CLEAN, '        g.market_trend_bull = True  # u-2: market MA20 gate off\n'),
  // edge test 动量: clean book, entry/exit bands mirrored to the weak end (6 constants, one concept)
  'u-3_clean-mirror': s => BAND.reduce((acc, [f, t]) => edit(acc, f, t), clean(s))
    .replace(WEEK, WEEK.replace('w_rps > g.week_rps_threshold', 'w_rps < g.week_rps_threshold'))
    .replace(MONTH, MONTH.replace('m_rps > g.month_rps_threshold', 'm_rps < g.month_rps_threshold')),
  // what the multi-period confirmation is worth: clean book, week/month thresholds dropped
  'u-4_clean-day-only': s => edit(edit(clean(s), WEEK, '                    True and \n'),
    MONTH, '                    True):\n'),
  // u-2 control: the same MA20 gate as an explicit index timer — long 510300 when close > MA20,
  // cash otherwise. Two edits, one concept: the RPS leg replaced by the index. (The base's gate
  // only blocks ENTRIES; exits are RPS-only, which an ETF never triggers, so the timer needs its
  // own exit.) If this beats the clean book, the selection leg is net negative.
  'u-5_clean-index-timer': s => edit(edit(clean(s), BUYLIST,
    BUYLIST + "        g.buy_list = [{'stock': '510300.XSHG', 'day_rps': 0.0, 'week_rps': 0.0, 'month_rps': 0.0, 'slope': 0.0}]  # u-5: index ETF control\n"),
    OPEN_MARK, '    if not g.market_trend_bull:  # u-5: explicit timer, cash when close <= MA20\n'
      + '        for __s in list(context.portfolio.positions.keys()):\n'
      + '            if not current_data[__s].paused:\n'
      + '                order_target(__s, 0)\n' + OPEN_MARK),
});
// u-4 follow-up: given the week/month confirmation, does the 20-day band's tightness matter?
// Lower edge 85 -> 50 and the exit floor 80 -> 50 move together (the exit floor must sit below
// the entry floor or every new entry is sold the next day): one concept, "how much 20-day
// strength is required".
Object.assign(V, {
  'u-6_clean-loose-day-band': s => edit(edit(clean(s),
    '    g.day_rps_low = 85\n', '    g.day_rps_low = 50\n'),
    '    g.sell_rps_low = 80\n', '    g.sell_rps_low = 50\n'),
});
const TIMER_EXIT ='    if not g.market_trend_bull:  # gate as EXIT too: cash when close <= MA20\n'
  + '        for __s in list(context.portfolio.positions.keys()):\n'
  + '            if not current_data[__s].paused:\n'
  + '                order_target(__s, 0)\n';
// improve, on-mechanism for the measured 趋势择时 edge (u-2): the base's gate only blocks entries;
// make it an exit as well, on the RPS stock book (one edit on the clean book).
const CANDIDATES = {
  'qsjs-imp-1': s => edit(clean(s), OPEN_MARK, TIMER_EXIT + OPEN_MARK),
};
// the mirror must have flipped the two comparison lines too (no silent no-op)
for (const id of ['u-3_clean-mirror']) {
  const body = V[id](src);
  if (!body.includes('w_rps < g.week_rps_threshold') || !body.includes('m_rps < g.month_rps_threshold')) {
    throw new Error(`${id}: week/month comparisons were not mirrored`);
  }
}

const dir = __dirname;
fs.mkdirSync(path.join(dir, 'variants'), { recursive: true });
fs.writeFileSync(path.join(dir, 'baseline-e6.py'), src + OVERRIDE);
for (const [id, fn] of Object.entries(V)) fs.writeFileSync(path.join(dir, 'variants', `${id}.py`), fn(src) + OVERRIDE);
fs.mkdirSync(path.join(ROOT, 'enhance/candidates'), { recursive: true });
for (const [id, fn] of Object.entries(CANDIDATES)) fs.writeFileSync(path.join(ROOT, 'enhance/candidates', `${id}.py`), fn(src) + OVERRIDE);
console.log('built baseline-e6 +', Object.keys(V).join(', '), '| candidates:', Object.keys(CANDIDATES).join(', '));
