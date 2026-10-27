// q-e9-champ-universe — INDEX MEMBERSHIP vs 规模 on the 小市值 family's epoch-9 champion
// `strategies/2026-10-26_中小盘趋势策略_年化_85-0a7de9fa.py`
// (control: objective 2.6282 / sharpe 7.07 / annual 276.82 / maxDD 14.00, 365 days, curve on disk).
//
// ## What is being tested
//
// The family's 规模 edge has THREE confirmations and all three are rank-TRANCHE shifts WITHIN one
// index (q-e6-1 bottom-1000 -> 1001-2000, 40% retained; q-e6-17, 5%; q-e9-champ-size head(200) ->
// .iloc[200:400], 29.5%). MEMBERSHIP has never been tested. So the family page can say 「越小越好」
// but not 「最小的哪些」. This swaps the STOCK POOL from 399101 (中小板综指) to 000985 (中证全指),
// an all-A superset direction that CONTAINS the 沪市/深主板 small caps 399101 excludes, leaving the
// ranking rule verbatim: is the edge 「取最小的」, or specifically 「中小板这一段」?
//
// The value is NOT ours: today's new member `ba87029c` (a fork of member 94d9f1ce) carries four
// index values written by a THIRD-PARTY author at L44-47, with 399101 active and
// 000985 / 000001 / 399106 commented out. That is what makes this one pre-declared point rather
// than a parameter sweep. ONE value only — 399106 深证综指 is spawned BY this result if it lands
// in the no-verdict band, never pre-queued.
//
// ## THE EDIT IS AT L165, NOT L28 — this is the load-bearing correction
//
// `MARKET_INDEX = '399101.XSHE'` (L28) is READ AT THREE PLACES, line-verified on py2to3(raw):
//   L165  `initial_list = get_index_stocks(MARKET_INDEX)`          <- the stock pool. THE ONLY TARGET.
//   L330  `get_price(MARKET_INDEX, end_date=context.previous_date, …)` <- the MARKET-WIDE stop-loss
//         reference, and it is LIVE: L113 `g.stoploss_strategy = STOPLOSS_COMBINED`, while L327
//         fires on `g.stoploss_strategy in (STOPLOSS_MARKET, STOPLOSS_COMBINED)`.
//   L366  `if detect_divergence(MARKET_INDEX, context):`            <- the MACD 顶背离 timing input,
//         ALREADY MEASURED at 0.2963 objective by q-e9-champ-dbl.
// Editing L28 would swap the pool, the stop-loss benchmark and the timing signal in one stroke, and
// one of those three has a known magnitude large enough to swallow this entry's whole reading.
// So the edit ADDS a constant `POOL_INDEX` and changes the L165 ARGUMENT ONLY; L28 keeps
// '399101.XSHE' verbatim, and L330 / L366 therefore keep control behaviour exactly.
//
// ## Kept verbatim, deliberately
//
//   * `filter_kcbj_stock` (L170) — 000985 itself contains 创业板/科创板/北交所; dropping the filter
//     would make this 「换池 + 换板块制度」, two changes.
//   * `filter_new_stock` — excludes names listed under 1 year, which incidentally gives this entry
//     a point-in-time guard: the ETF families' 「池子里有窗口后才上市的名字」 problem cannot arise.
//   * the 10-80亿 cap filter, both head() stages, the BBI band, the 顶背离 overlay, the stop-loss
//     block, EMPTY_MONTHS=[1,4], g.target_stock_count=2, and the frozen cost block (from OVERRIDE).
//
// ## VALIDITY GATE — the confound this entry cannot remove, and the three probes that expose it
//
// q-e9-champ-size measured 399101's post-`market_cap.between(10, 80)` depth at min 580 / mean 642 /
// max 705, with `市值筛选后数量` exactly 200 on all 41 rebalances. A 000985 pool is likely several
// times deeper, which pushes `head(200)` DOWN toward the 10亿 floor — so this swap moves
// (i) membership AND (ii) where head(200) lands on the size ladder. One edit cannot separate them.
// The 10亿 lower bound of `between(10, 80)` bounds (ii): no depth takes the slice into true 微盘.
// Therefore the report must carry, and the three instrumentation lines below produce:
//   P2  `POOLDEPTH`  per rebalance: len(fund_df) before head(200), plus the cap at the slice edge
//   P3  `CANDMC`     per rebalance: the market_cap of every one of the 80 selected candidates
// plus the book's own free `市值筛选后数量` log (L191), so a reader can judge 「did it simply go
// smaller?」 without another backtest.
// !! ANY rebalance with POOLDEPTH n < 200 => the measurement is INVALID and reports as
//    「cannot execute」, never 「no effect」.
//
// P1 is a probe-only global (`g.probe_mc`) and exists because `fund_df` is REASSIGNED at L203 by
// the second query, which selects `valuation.code` ONLY — so at the candidate stage the market caps
// are gone. Capturing them at L190 costs no extra data call. Nothing in the strategy ever reads
// `g.probe_mc`; the builder asserts that.
//
// All three probes use `log.error`, not `log.info`: this book's 日志 runs thousands of lines and
// pages 100 at a time, while the 错误 tab holds only these markers. Verified route — q-e9-champ-size
// read its 41 POOLDEPTH lines exactly this way. They are INSTRUMENTATION, not edits: they place no
// order, read no price, and change no selection, ordering or sizing. The undo assertion removes all
// three plus the added constant, restores L165, and must reproduce `py2to3(raw)` byte-for-byte.
//
// ## Pre-registered three-way read (do not interpret beyond it)
//
//   (a) annual >= 193.8%  (70% of 276.82)  => the edge is 「取最小的」; 规模 generalises beyond
//                                             中小板 and this branch stays redundant for integration
//   (b) annual <  110.7%  (40%)            => 中小板 MEMBERSHIP is load-bearing; the champion's pool
//                                             is an UNDECLARED SEGMENT CHOICE and must be read beside
//                                             ETF动量 / 七星高照's 「2026 年事后写的池子」 argument
//   (c) 110.7% - 193.8%                    => NO VERDICT, 「成员籍部分承重」; spawns 399106 only
// Secondary, free, from the saved curve: the Jan-Nov 2024 objective (control 1.6888, annualized over
// the SLICE'S CALENDAR SPAN 335/365 — never over the curve's own trading-day count) and December's
// share of the year's LOG-growth (control 28.1%; q-e9-champ-size's tranche shift took it to 10.3%,
// so the December spike is a smallest-cap phenomenon). If 000985 holds ~28% the spike travels with
// 「最小」; if it collapses, this entry cannot separate the two and must say so.
//
// ⚠ This must not be merged with any other delta on this book (q-e6-18: two deltas do not add).
// ⚠ VAL is BLOCKED for this family (already-validated; xsz-e9-champ 0.83 FAIL). TRAIN only.
// ⚠ This entry opens no improve: there is no validation left to spend, so both branches are writing.

const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const harness = require('../../utils/harness-config');

const ROOT = path.join(__dirname, '../..');
const OUT = __dirname;

const TAG = 'universe-000985';

// Line-exact, both directions. Matching whole lines (never substrings) is what keeps the undo
// assertion below a real check rather than a tautology.
const DECL = "MARKET_INDEX = '399101.XSHE'  # 市场参考指数（中小板综指，用于趋势判断）";
const ADDED = "POOL_INDEX = '000985.XSHG'  # q-e9-champ-universe: 选股池改为中证全指（全A）"
            + '；趋势/市场止损参考仍为 MARKET_INDEX=399101';

const SITE = '    initial_list = get_index_stocks(MARKET_INDEX)';
const EDITED = '    initial_list = get_index_stocks(POOL_INDEX)'
             + '  # q-e9-champ-universe: 399101 -> 000985, the ONLY change vs the raw book';

// Probe anchors, both unique whole lines.
const A1 = "    initial_list = fund_df['code'].head(200).tolist()";
const P1 = "    g.probe_mc = dict(zip(fund_df['code'].tolist(), fund_df['market_cap'].tolist()))"
         + '  # q-e9-champ-universe instrumentation: market_cap snapshot, probe-only, never read by the strategy';
const P2 = "    log.error('POOLDEPTH date=%s n=%d mc_first=%.2f mc_at200=%.2f' % "
         + "(str(context.previous_date), len(fund_df), float(fund_df['market_cap'].iloc[0]), "
         + "float(fund_df['market_cap'].iloc[min(199, len(fund_df) - 1)])))"
         + '  # q-e9-champ-universe instrumentation: pool depth before head(200) + the slice edge';

const A3 = "    candidate_list = fund_df['code'].head(80).tolist()";
const P3 = "    log.error('CANDMC date=%s n=%d mc=%s' % (str(context.previous_date), "
         + "len(candidate_list), '|'.join(['%.2f' % float(g.probe_mc.get(c, float('nan'))) "
         + 'for c in candidate_list])))'
         + '  # q-e9-champ-universe instrumentation: market_cap of every selected candidate';

// ⚠ Every MARKET_INDEX / POOL_INDEX count below runs on the CODE SIDE of a line, never the whole
// line. `ADDED`'s own comment names MARKET_INDEX (to say it is deliberately untouched), and the
// first version of this builder counted that comment and REFUSED a correct build — precisely the
// failure CLAUDE.md records for build-siblings' stray-`*100` guard: a check that reads prose as
// code fails on the right answer.
const codeOf = l => l.split('#')[0];

const src = fs.readdirSync(path.join(ROOT, 'strategies')).find(f => /0a7de9fa/.test(f));
if (!src) throw new Error('0a7de9fa not found in strategies/');

// ⚠ The comparison baseline is py2to3(raw), NOT the on-disk file: the variant is built on the
// py2to3 output, which is also what the normalizer measured the control on.
const raw = py2to3(fs.readFileSync(path.join(ROOT, 'strategies', src), 'utf8'));
const rawLines = raw.split('\n');

for (const [name, line] of [['DECL', DECL], ['SITE', SITE], ['A1', A1], ['A3', A3]]) {
  if (rawLines.filter(l => l === line).length !== 1) {
    throw new Error(`expected exactly 1 ${name} line (${line.trim()}) — refusing`);
  }
}
for (const [name, line] of [['ADDED', ADDED], ['EDITED', EDITED], ['P1', P1], ['P2', P2], ['P3', P3]]) {
  if (rawLines.includes(line)) throw new Error(`${name} is already present — refusing`);
}

// The structural facts the design and the report rest on. Each is CHECKED, not assumed: if any has
// moved, the one-line edit no longer means "pool membership 399101 -> 000985" and the result is
// uninterpretable.
const facts = {
  // THE core precondition: MARKET_INDEX is read at exactly 3 places (+1 declaration = 4 lines).
  // If a fourth reader appeared, changing only L165 no longer isolates the pool.
  'MARKET_INDEX appears on exactly 4 lines (1 declaration + 3 reads)':
    rawLines.filter(l => /MARKET_INDEX/.test(codeOf(l))).length === 4,
  'MARKET_INDEX read #1 is the pool (the edit site)':
    rawLines.filter(l => l === SITE).length === 1,
  'MARKET_INDEX read #2 is the market stop-loss get_price argument':
    rawLines.filter(l => l === '            MARKET_INDEX,').length === 1
    && rawLines[rawLines.indexOf('            MARKET_INDEX,') - 1] === '        index_data = get_price(',
  'MARKET_INDEX read #3 is the 顶背离 timing input':
    rawLines.filter(l => l === '    if detect_divergence(MARKET_INDEX, context):').length === 1,
  // The market stop-loss leg must be LIVE, or "L330 kept verbatim" is a claim about dead code.
  'the market stop-loss leg is live (STOPLOSS_COMBINED)':
    rawLines.filter(l => l === '    g.stoploss_strategy = STOPLOSS_COMBINED  # 采用联合止损模式').length === 1
    && rawLines.filter(l => l === '    if g.stoploss_strategy in (STOPLOSS_MARKET, STOPLOSS_COMBINED):').length === 1,
  // No POOL_INDEX-shaped name already exists, so the added constant shadows nothing.
  'no pre-existing POOL_INDEX / probe_mc symbol':
    rawLines.filter(l => /POOL_INDEX|probe_mc|POOLDEPTH|CANDMC/.test(codeOf(l))).length === 0,
  // The selection chain this entry's confound is about, asserted in order.
  'the cap filter is market_cap.between(10, 80) ascending':
    rawLines.filter(l => l === '        valuation.market_cap.between(10, 80)  # 市值范围：5亿-50亿').length === 1
    && rawLines.filter(l => l === '    ).order_by(valuation.market_cap.asc())  # 从小到大排序').length === 1,
  'the first query selects market_cap (so P1 can snapshot it)':
    rawLines.filter(l => l === '        valuation.market_cap  # 总市值').length === 1,
  'the second query selects code ONLY (which is why P1 exists)':
    rawLines.filter(l => l === '    q = query(valuation.code).filter(valuation.code.in_(initial_list)).order_by(valuation.market_cap.asc())').length === 1,
  'fund_df is reassigned between the two head() stages':
    rawLines.filter(l => /^\s*fund_df = get_fundamentals\(q\)/.test(l)).length === 2,
  'the chain runs head(200) -> secondary filters -> head(80)':
    rawLines.indexOf(A1) < rawLines.indexOf(A3)
    && rawLines.indexOf('    initial_list = filter_limitup_stock(context, initial_list)    # 排除非持仓的昨日涨停股（避免追高）') > rawLines.indexOf(A1)
    && rawLines.indexOf('    initial_list = filter_limitup_stock(context, initial_list)    # 排除非持仓的昨日涨停股（避免追高）') < rawLines.indexOf(A3),
  // The two filters deliberately kept — see the header.
  'filter_new_stock and filter_kcbj_stock are both applied to the pool':
    rawLines.filter(l => l === '    initial_list = filter_new_stock(context, initial_list)        # 排除次新股（上市不足1年）').length === 1
    && rawLines.filter(l => l === '    initial_list = filter_kcbj_stock(initial_list)                # 排除科创板、创业板、北交所（风险较高）').length === 1,
  // Breadth, empty months and the benchmark are untouched knobs other entries own.
  'breadth is still the author\'s 2':
    rawLines.filter(l => l === '    g.target_stock_count = 2  # 目标持仓数量').length === 1,
  'empty months are Jan and Apr':
    rawLines.filter(l => l === 'EMPTY_MONTHS = [1,4,]  # 空仓月份（1月、4月，基于历史数据统计的风险较高月份）').length === 1,
  'the benchmark constant is untouched':
    rawLines.filter(l => l === "BENCHMARK = '000001.XSHG'  # 业绩基准指数（上证综指）").length === 1,
  'strategy logs at debug so the free reads survive':
    rawLines.filter(l => l === "    log.set_level('strategy', 'debug')  # 保留策略调试日志").length === 1,
  'the weekly rebalance is Tuesday 10:45':
    rawLines.filter(l => l === "    run_weekly(weekly_adjustment, 2, '10:45')   # 每周二10:00调仓").length === 1,
};
for (const [k, ok] of Object.entries(facts)) {
  if (!ok) throw new Error(`structural precondition failed: ${k} — refusing`);
}

// The log lines the report is read from must survive, or the run cannot be attributed.
const LOGS = [
  'f"初始股票池数量: {len(initial_list)}"',
  'f"初步过滤后数量: {len(initial_list)}"',
  'f"市值筛选后数量: {len(initial_list)}"',
  'f"二次过滤后数量: {len(initial_list)}"',
  'f"精选市值后数量: {len(candidate_list)}"',
  'f"本周目标持仓列表（前{min(g.target_stock_count, len(g.target_list))}只）: {g.target_list[:g.target_stock_count]}"',
];

// Build: swap the L165 argument, declare POOL_INDEX under MARKET_INDEX, insert the three probes.
const body = rawLines
  .flatMap((l) => {
    if (l === DECL) return [l, ADDED];
    if (l === SITE) return [EDITED];
    if (l === A1) return [l, P1, P2];
    if (l === A3) return [l, P3];
    return [l];
  })
  .join('\n');
const bodyLines = body.split('\n');

if (!bodyLines.includes(EDITED)) throw new Error('the edit did not land');
if (!bodyLines.includes(ADDED)) throw new Error('the POOL_INDEX declaration did not land');
for (const [n, p] of [['P1', P1], ['P2', P2], ['P3', P3]]) {
  if (!bodyLines.includes(p)) throw new Error(`${n} did not land`);
}
if (bodyLines.includes(SITE)) throw new Error('the original pool line survived the edit — refusing');
// The pool is now read from POOL_INDEX and NOWHERE else reads it.
if (bodyLines.filter(l => /get_index_stocks\(/.test(l)).length !== 1) {
  throw new Error('expected exactly one get_index_stocks call — refusing');
}
if (bodyLines.filter(l => /POOL_INDEX/.test(codeOf(l))).length !== 2) {
  throw new Error('POOL_INDEX must appear exactly twice (declaration + the one read) — refusing');
}
// ⚠⚠ THE WHOLE POINT: L330 and L366 must still reference MARKET_INDEX, and MARKET_INDEX must still
// be 399101. If either moved, the Δ mixes in the stop-loss benchmark and/or the 顶背离 signal whose
// own magnitude is already measured at 0.2963 — the reading would be unattributable.
if (bodyLines.filter(l => /MARKET_INDEX/.test(codeOf(l))).length !== 3) {
  throw new Error('MARKET_INDEX must survive on exactly 3 lines (declaration + stop-loss + 顶背离) — refusing');
}
if (!bodyLines.includes(DECL)) throw new Error('MARKET_INDEX is no longer 399101.XSHE — refusing');
if (!bodyLines.includes('            MARKET_INDEX,')) {
  throw new Error('the market stop-loss no longer references MARKET_INDEX — refusing');
}
if (!bodyLines.includes('    if detect_divergence(MARKET_INDEX, context):')) {
  throw new Error('the 顶背离 timing input no longer references MARKET_INDEX — refusing');
}
// `g.probe_mc` is written once and read once, both inside the instrumentation.
if (bodyLines.filter(l => /g\.probe_mc/.test(l)).length !== 2
    || bodyLines.filter(l => /g\.probe_mc/.test(l)).some(l => l !== P1 && l !== P3)) {
  throw new Error('g.probe_mc must be touched only by the two instrumentation lines — refusing');
}
if (bodyLines.length !== rawLines.length + 4) {
  throw new Error('the build changed more than the one edit plus one declaration plus three probes — refusing');
}
for (const need of LOGS) {
  if (!body.includes(need)) throw new Error(`missing log line needed for the report: ${need}`);
}
// The frozen cost block must be the OVERRIDE's, appended below — never hand-copied into the body.
if (!OVERRIDE.includes('set_order_cost')) {
  throw new Error('OVERRIDE does not look like the frozen cost block — refusing');
}

// ⚠⚠ The ONLY differences from py2to3(raw) must be the swapped argument, the added constant and the
// three probes. Assert on `body` — the PRE-OVERRIDE text — never on a slice of the final file:
// cutting the output at a marker is ambiguous against the file's own trailing newlines, and that is
// exactly what made build-liq-5a70adc1 report a false "first difference at line 840" of 839.
const undone = bodyLines
  .filter(l => l !== ADDED && l !== P1 && l !== P2 && l !== P3)
  .map(l => (l === EDITED ? SITE : l))
  .join('\n');
if (undone !== raw) {
  const a = undone.split('\n');
  const first = a.findIndex((l, i) => l !== rawLines[i]);
  throw new Error('undoing the edit does not reproduce py2to3(raw) byte-for-byte '
                + `(first difference at line ${first + 1} of ${rawLines.length}) — refusing`);
}

const out = body + OVERRIDE;
const file = path.join(OUT, `variants/0a7de9fa-${TAG}.py`);
fs.writeFileSync(file, out);

console.log(`[universe] built variants/0a7de9fa-${TAG}.py  (epoch ${harness.config().epoch})`);
console.log(`[universe] ONE edit at L${rawLines.indexOf(SITE) + 1}: get_index_stocks(MARKET_INDEX) -> `
          + 'get_index_stocks(POOL_INDEX), POOL_INDEX = 000985.XSHG (中证全指), declared under L28');
console.log('[universe] ⚠ L28 MARKET_INDEX stays 399101.XSHE, so L330 (market stop-loss reference, '
          + 'LIVE via STOPLOSS_COMBINED) and L366 (MACD 顶背离 input, already worth 0.2963 per '
          + 'q-e9-champ-dbl) are VERBATIM — asserted: MARKET_INDEX survives on exactly 3 lines');
console.log(`[universe] + 3 instrumentation lines: g.probe_mc at L${rawLines.indexOf(A1) + 2}, `
          + `POOLDEPTH at L${rawLines.indexOf(A1) + 3}, CANDMC at L${rawLines.indexOf(A3) + 4} `
          + '(all log.error -> the 错误 tab; probe-only global read by nothing else)');
console.log('[universe] kept verbatim: filter_new_stock (point-in-time guard), filter_kcbj_stock '
          + '(no board-regime change), the 10-80亿 cap filter, head(200)/head(80), the BBI band, '
          + 'the 顶背离 overlay, the stop-loss block, EMPTY_MONTHS=[1,4], g.target_stock_count=2, '
          + 'the frozen cost block (from OVERRIDE, never hand-copied)');
console.log('[universe] undo (restore L165 + drop the constant + drop 3 probes) reproduces '
          + 'py2to3(raw) byte-for-byte');
console.log("[universe] control = the champion's own epoch-9 ledger row: objective 2.6282 / "
          + 'sharpe 7.07 / annual 276.82 / maxDD 14.00 (365 days); Jan-Nov objective 1.6888, '
          + "December = 28.1% of the year's log-growth");
console.log('[universe] VALIDITY GATE — report POOLDEPTH min/mean/max, 市值筛选后数量 per rebalance '
          + '(control: exactly 200 on all 41), and the market_cap distribution of the 80 candidates. '
          + 'ANY rebalance with POOLDEPTH n < 200 => INVALID / "cannot execute", never "no effect".');
console.log('[universe] PRE-REGISTERED, THREE BRANCHES (on ANNUAL, control 276.82):');
console.log('[universe]   (a) annual >= 193.8% (70%)  => the edge is 「取最小的」; 规模 generalises beyond 中小板');
console.log('[universe]   (b) annual <  110.7% (40%)  => 中小板 MEMBERSHIP is load-bearing; the pool is '
          + 'an undeclared SEGMENT CHOICE, to be read beside the ETF families\' hindsight-pool argument');
console.log('[universe]   (c) 110.7%-193.8%           => NO VERDICT, 「成员籍部分承重」; spawns 399106 only');
console.log('[universe] ONE VALUE ONLY — 000985 was pre-declared by a third-party author (ba87029c '
          + 'L44-47); 399106/000001 are spawned by this result, never pre-queued');
console.log('[universe] ⚠ VAL is BLOCKED for this family (already-validated, xsz-e9-champ 0.83 FAIL) — TRAIN only');
