// q-e9-bench-lastprice — BENCH-SEMANTICS probe (observation only) on the 小市值 family's epoch-9
// champion `strategies/2026-10-30_今天多个策略告警_这是什么意思_怎么解决-02fdafaa.py`
// (control: objective 3.0172 / sharpe 8.22 / annual 320.35 / maxDD 18.63, 365 days, curve on disk).
//
// ## The question (pre-registered in study/小市值/queue.json, rank 27)
//
// On a `costs.frequency: "daily"` bench, does `get_current_data()[s].last_price` read inside an
// INTRADAY-scheduled `run_daily` handler return the CURRENT price, or the DAY'S CLOSE? If it is the
// close, then 「keep it if it is 涨停」 (L297, L449) and 「exit if it is down 7%」 are decisions made
// with that day's answer already in hand.
//
// PRE-REGISTERED FALSIFICATION (verbatim from the queue entry, not restated):
//   * the timepoints give DIFFERENT last_price values, or any one differs from that stock's own
//     daily `close`  =>  semantics are CLEAN, the item closes, the family's levels are not impeached
//     on this ground;
//   * all timepoints are IDENTICAL **and** equal the day's `close`  =>  the level must be re-read as
//     lookahead, and the conclusion generalises to every library member calling get_current_data
//     intraday.
//
// ## Retarget (orchestrator, 2026-10-30)
//
// The entry was written against 0a7de9fa (handlers 9:00 / 10:30 / 14:00). That book is no longer the
// champion. 02fdafaa's own schedule supplies the same three timepoints and one extra:
//   prepare_stock_list 9:05  (PRE-OPEN) | sell_stocks 10:00 | trade_afternoon 14:25 AND 14:55
// `trade_afternoon` is scheduled TWICE (L67/L68), so THREE insertions yield FOUR timepoints.
// This is a question about the BENCH, not about a book, so the target moves and the thresholds
// above do not.
//
// ## Why 02fdafaa rather than 0a7de9fa, and why STEP 0 could not settle it
//
// STEP 0 (free: the stored runs' own logs, paged to exhaustion) was run first and FAILED to settle
// the question, for a reason specific to the API being asked about:
//   * 0a7de9fa's only `get_current_data().last_price` branch is inside `dapan`'s 顶背离 clause, which
//     NEVER FIRED in 2024 (242/242 days 「未检测到大盘顶背离」) — so the API under test was never
//     exercised. Its 「当前价」 logs come from `pos.price` (止盈/止损) and from
//     `get_price(frequency='1m')` (涨停打开) — two DIFFERENT channels.
//   * 02fdafaa's two `get_current_data().last_price` sites (L297, L449) log no values.
// Hence a probe, and hence the champion: the finding should attach to the live book.
//
// ## Insertion sites — THREE call lines + ONE helper, zero trading logic
//
//   after L77  `def prepare_stock_list(context):`   -> `    _benchsem(context, 'prepare_stock_list')`
//   after L247 `def sell_stocks(context):`          -> `    _benchsem(context, 'sell_stocks')`
//   after L232 `def trade_afternoon(context):`      -> `    _benchsem(context, 'trade_afternoon')`
//   + `_benchsem` appended to the module body (before OVERRIDE).
//
// Each call is the handler's FIRST statement, so the line is emitted even on days the handler
// early-returns — the design's 「one line per handler per day」. The helper reads
// `context.portfolio.positions` directly (never `g.hold_list`), so it is independent of the book's
// own state, places NO order, mutates NO `g.` field, and is wrapped so a data refusal can only
// print `BENCHSEM-FAIL`, never abort the run. The measured objective must therefore equal the
// control's 3.0172 exactly; if it does not, the insertion changed behaviour and the run is void.

const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const harness = require('../../utils/harness-config');

const ROOT = path.join(__dirname, '../..');
const OUT = __dirname;
const TAG = 'benchsem';

// ⚠ `%` formatting (not f-strings) so the line is identical in shape whatever the runtime, and
// `log.error` because the book sets log.set_level('strategy','debug') but filters order/system at
// 'error' — error is the one level nothing can suppress.
const HELPER = [
  '',
  '',
  '# ===== q-e9-bench-lastprice PROBE — OBSERVATION ONLY =====',
  '# Emits one line per handler per day. Places no order, mutates no g. field, reads nothing the',
  '# book does not already read. `prev_close` is the UNIMPEACHABLE reference: queried at',
  '# end_date=context.previous_date, so last_price on day D is compared with prev_close as logged',
  '# on day D+1 for the same code. `day_close` is the same quantity asked for directly and may be',
  '# refused by avoid_future_data — that refusal is itself information, so it is caught, not raised.',
  'def _benchsem(context, tag):',
  '    try:',
  '        d = str(context.current_dt)[:10]',
  '        codes = sorted(context.portfolio.positions.keys())',
  '        if len(codes) == 0:',
  "            log.error('BENCHSEM t=%s date=%s code=NONE last=NA high_limit=NA open=NA prev_close=NA day_close=NA' % (tag, d))",
  '            return',
  '        s = codes[0]',
  '        cd = get_current_data()[s]',
  '        last = cd.last_price',
  '        hl = cd.high_limit',
  '        dop = cd.day_open',
  '        try:',
  "            pc = get_price(s, end_date=context.previous_date, frequency='daily', fields=['close'], count=1, fq=None, panel=False)['close'].iloc[0]",
  '        except:',
  "            pc = float('nan')",
  '        try:',
  "            dc = get_price(s, end_date=context.current_dt, frequency='daily', fields=['close'], count=1, fq=None, panel=False)['close'].iloc[0]",
  '        except:',
  "            dc = float('nan')",
  "        log.error('BENCHSEM t=%s date=%s code=%s last=%.4f high_limit=%.4f open=%.4f prev_close=%.4f day_close=%.4f'",
  '                  % (tag, d, s, last, hl, dop, pc, dc))',
  '    except Exception as e:',
  "        log.error('BENCHSEM-FAIL t=%s err=%s' % (tag, e))",
].join('\n');

// Line-exact insertion sites, both directions.
const SITES = [
  ['def prepare_stock_list(context):', "    _benchsem(context, 'prepare_stock_list')  # q-e9-bench-lastprice probe"],
  ['def sell_stocks(context):', "    _benchsem(context, 'sell_stocks')  # q-e9-bench-lastprice probe"],
  ['def trade_afternoon(context):', "    _benchsem(context, 'trade_afternoon')  # q-e9-bench-lastprice probe"],
];

const src = fs.readdirSync(path.join(ROOT, 'strategies')).find(f => /02fdafaa/.test(f));
if (!src) throw new Error('02fdafaa not found in strategies/');

// ⚠ The comparison baseline is py2to3(raw), NOT the on-disk file: the normalizer measured the
// control on the py2to3 output, so that is what the variant must differ from by the probe alone.
const raw = py2to3(fs.readFileSync(path.join(ROOT, 'strategies', src), 'utf8'));
const lines = raw.split('\n');

for (const [site] of SITES) {
  const n = lines.filter(l => l === site).length;
  if (n !== 1) throw new Error(`expected exactly 1 insertion site, got ${n}: ${site}`);
}

// The schedule is what makes three insertions four timepoints — assert it rather than assume it.
const codeOf = (l) => { const i = l.indexOf('#'); return (i === -1 ? l : l.slice(0, i)).trimEnd(); };
const SCHEDULE = [
  "    run_daily(prepare_stock_list, '9:05')",
  "    run_daily(sell_stocks, time='10:00')",
  "    run_daily(trade_afternoon, time='14:25')",
  "    run_daily(trade_afternoon, time='14:55')",
];
for (const a of SCHEDULE) {
  const n = lines.filter(l => codeOf(l) === a).length;
  if (n !== 1) throw new Error(`schedule line not where the design says it is (${n} matches): ${a}`);
}
// The two decision sites this probe exists to characterise must still be there.
for (const a of ['        if current_data[stock].last_price == current_data[stock].high_limit:',
                 '        if current_data[stock].last_price >= current_data[stock].high_limit*0.97:']) {
  if (!lines.some(l => l === a)) throw new Error(`the get_current_data().last_price decision site moved: ${a}`);
}

// ---- build ----
// ⚠ Track inserted POSITIONS, not inserted TEXT. Filtering the undo by a set of added strings
// also deletes every pre-existing line that happens to equal one of them — and HELPER's own blank
// separator lines match the book's blanks, which is exactly how the first version of this builder
// reported a false "difference at line 616 of 615".
const outLines = lines.slice();
const inserted = new Set();
for (const [site, call] of SITES) {
  const i = outLines.indexOf(site);
  outLines.splice(i + 1, 0, call);
  // every previously-recorded index at or after the insertion point shifts by one
  for (const k of [...inserted]) { if (k >= i + 1) { inserted.delete(k); inserted.add(k + 1); } }
  inserted.add(i + 1);
}
const helperLines = HELPER.split('\n');
for (const hl of helperLines) { inserted.add(outLines.length); outLines.push(hl); }
const body = outLines.join('\n');

// ---- the probe must be INERT by construction ----
// Every line the build ADDED, checked one by one: no order, no assignment to g, no set_* call.
const added = [...inserted].sort((a, b) => a - b).map(i => outLines[i]);
if (added.length !== SITES.length + helperLines.length) throw new Error('insertion bookkeeping is wrong — refusing');
for (const l of added) {
  if (/\border_|open_position|close_position|set_option|set_order_cost|set_slippage|set_commission|set_benchmark/.test(l)) {
    throw new Error(`an added line touches execution: ${l.trim()}`);
  }
  if (/(^|[^\w.])g\.\w+\s*(=[^=]|\+=|-=|\.append|\.pop|\.remove)/.test(l)) {
    throw new Error(`an added line mutates g: ${l.trim()}`);
  }
}

// ---- undo must reproduce py2to3(raw) byte-for-byte ----
// Assert on the PRE-OVERRIDE text, never on a slice of the final file: cutting at a marker is
// ambiguous against trailing newlines, which is what gave build-liq-5a70adc1 a false diff.
const undone = outLines.filter((l, i) => !inserted.has(i)).join('\n');
if (undone !== raw) {
  const a = undone.split('\n'), b = raw.split('\n');
  const first = a.findIndex((l, i) => l !== b[i]);
  throw new Error('undoing the probe does not reproduce py2to3(raw) byte-for-byte '
                + `(first difference at line ${first + 1} of ${b.length}) — refusing`);
}

const file = path.join(OUT, `variants/02fdafaa-${TAG}.py`);
fs.writeFileSync(file, body + OVERRIDE);

console.log(`[benchsem] built variants/02fdafaa-${TAG}.py  (epoch ${harness.config().epoch})`);
console.log(`[benchsem] 3 call lines + 1 helper = ${added.length} added lines; 0 lines changed, 0 removed`);
console.log('[benchsem] timepoints: 9:05 prepare_stock_list (PRE-OPEN) / 10:00 sell_stocks / '
          + '14:25 + 14:55 trade_afternoon');
console.log('[benchsem] undo reproduces py2to3(raw) byte-for-byte (pre-OVERRIDE comparison)');
console.log('[benchsem] CONTROL = the champion\'s epoch-9 row: objective 3.0172 / sharpe 8.22 / '
          + 'annual 320.35 / maxDD 18.63. A probe that moves the result is NOT a probe — if the '
          + 'measured objective differs, the run is VOID, not a finding.');
console.log('[benchsem] PRE-REGISTERED: timepoints DIFFER or any one != that day\'s close => CLEAN, '
          + 'item closes. ALL IDENTICAL *and* == the day\'s close => LOOKAHEAD, generalises to every '
          + 'member calling get_current_data intraday.');
console.log('[benchsem] ⚠ absent BENCHSEM lines = INSTRUMENTATION FAILED, never "the prices agreed".');
