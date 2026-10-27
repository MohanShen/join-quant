// q-e9-champ-breadth — CONCENTRATION test on the 小市值 family's epoch-9 champion
// `strategies/2026-10-26_中小盘趋势策略_年化_85-0a7de9fa.py`
// (control: objective 2.6282 / sharpe 7.07 / annual 276.82 / maxDD 14.00, 365 days, curve on disk).
//
// ## What is being tested
//
// This is the LAST untested explanation of the champion's TRAIN magnitude. Already eliminated:
//   * 规模 (q-e9-champ-size) explains the DIRECTION but not the level — one cap notch up retains
//     only 29.5%, yet every other 规模 book in the family sits an order of magnitude lower;
//   * the BBI band is REFUTED (q-e9-champ-bbi-off: removing it RAISES annual);
//   * the MACD 顶背离 overlay fired ONCE in 2024, is worth 0.2963 and has ΔmaxDD 0.00
//     (q-e9-champ-dbl) — a return event, not a risk device;
//   * realized vol is mid-pack at 41.0%, so the margin is not plain leverage.
// If holding only TWO names does not bear the weight either, the correct conclusion is
// 「量级 = 一次十二月事件 + 2 仓的尾部运气」 — a RESULT, not a failure.
//
// The family prior points the other way round: both of its independently-tested knobs
// (`g.choice` 500/800/1000/1200/1500 and the low-open threshold −0.5/−1/−2, q-e6-6..9) peak
// exactly on the author's value and lose ~half on either side. That is the fingerprint of a knob
// tuned ex post, so the claim under test is that the author's `2` is another such 驼峰顶.
//
// ## The ONE edit — L111
//
//   `    g.target_stock_count = 2  # 目标持仓数量`  ->  `… = 4 …`
//
// `g.target_stock_count` is READ at five places and all five move with it. That is the intended
// behaviour of a single-knob test, not a second edit:
//   L270  the logged target list `g.target_list[:g.target_stock_count]`
//   L276  the sell rule "not in the first N of the target list"
//   L286  the weekly buy `buy_security(context, g.target_list[:g.target_stock_count])`
//   L573  `need_buy = g.target_stock_count - len(g.hold_list)` (limit-up-reopen refill)
//   L727  `if len(context.portfolio.positions) >= g.target_stock_count: break`
// Everything else is verbatim: the 399101 pool, the 10–80亿 cap filter, both head() stages, the
// BBI band, the 顶背离 overlay, the stop-loss block, EMPTY_MONTHS=[1,4] and the frozen cost block.
//
// Why 4 and not 5: 4 has a mechanism anchor — 1,000,000 / 4 / 0.05 = 5e6, exactly half the ¥1e7
// feasibility floor the champion was measured at (q-e9-champ-liq). 5 has none.
//
// ## THE CASH ETF OCCUPIES A SLOT — why the probe below is mandatory, not decoration
//
// `g.etf` (511880.XSHG, 华宝添益) is a real POSITION, not a cash sleeve, and `buy_security` breaks
// on the position COUNT:
//   L727  `if len(context.portfolio.positions) >= g.target_stock_count:`
// and the ETF is bought in two places:
//   L258  empty months (EMPTY_MONTHS = [1, 4]) — `buy_security(context, [g.etf])`
//   L587  after any stoploss / market-stoploss — `buy_security(context, [g.etf])`
// L301/L345/L373/L653 all exempt it from selling. So while the ETF is held, the count of STOCK
// names is `g.target_stock_count − 1`: at 2 the book can be reduced to a SINGLE stock, at 4 to
// three. 2 -> 4 therefore changes the ETF's share of the book as well as the stock breadth, and
// the Δ is unattributable without the per-rebalance holding split. Hence:
//
//   inserted at the END of `prepare_stock_list` (daily 9:05, immediately after L156):
//   `    log.error('HOLDCOUNT date=%s n=%d etf=%d tradable=%d names=%s' % (…))`
//
// `g.hold_list` is read straight off `context.portfolio.positions` at L134, so this is the
// portfolio actually carried into each session — the day after each Tuesday 10:45 rebalance is the
// post-rebalance state. `log.error` (not `log.info`) so it lands in the 错误 tab as well as the
// 日志 tab: this book's 日志 runs ~7,000 lines and pages 100 at a time, while the 错误 tab holds
// only these markers. Verified route — q-e9-champ-size read its 41 POOLDEPTH lines exactly this
// way. It is INSTRUMENTATION, not a second edit: it places no order, reads no price, and changes
// no selection, ordering or sizing. The undo assertion restores L111 AND removes this line, and
// must reproduce `py2to3(raw)` byte-for-byte.
//
// ## Free reads already in the book (no probe needed)
//
//   L259  「空仓月份（[1, 4]），切换至持有现金ETF: 511880.XSHG」   <- ETF takes a slot
//   L270  「本周目标持仓列表（前N只）: [...]」                     <- N and the names, per rebalance
//   L283  「调仓完成，共卖出 N 只股票」
//   L581  「因涨停打开卖出，需补仓 N 只，候选列表: [...]」          <- the L573 refill path
//   L586  「因止损操作，剩余资金 … 转入现金ETF」                    <- ETF takes a slot mid-month
//   L719  「共需买入 N 只股票，每只分配资金 …」                     <- per-name capital = cash / N
//   L724  「买入成功 <code>，金额 …」 / L731「买入失败 …」
//   L728  「已达到目标持仓数量 N，停止买入」                        <- the L727 break firing
// `init` sets `log.set_level('strategy', 'debug')` (L96), so all of them are retrievable.
//
// ## Pre-registered three-way read (do not interpret beyond it)
//
//   (a) objective  < 1.6     => the advantage is specifically top-2 concentration
//   (b) objective 2.1–2.68   => partial; a plateau rather than a peak
//   (c) objective >= 2.68    => the 驼峰顶 reading is REFUTED and the author's 2 is a knob tuned
//                               on 2024, so the 2.6282 level itself has to be discounted
// Secondary, free, from the saved curve: the Jan–Nov 2024 objective (control 1.6888, annualized
// over the SLICE'S calendar span 335/365 — never over the curve's own trading-day count), and
// December's share of the year's LOG-growth (control 28.1%; q-e9-champ-size saw a tranche shift
// drop it to 10.3%). A ROBUSTNESS FALSIFIER, never the adoption metric.
//
// ⚠ ONE POINT ONLY. Neighbours (3, 6) are spawned BY this result, never pre-queued — laying three
// points down to fit a hump is exactly what q-e6-6..9 warns against.
// ⚠ This must not be merged with any other delta on this book (q-e6-18: two deltas do not add).
// ⚠ VAL is BLOCKED for this family (already-validated; xsz-e9-champ 0.83 FAIL). TRAIN only.

const fs = require('fs');
const path = require('path');
const { OVERRIDE, py2to3 } = require('../../utils/strategy-normalize');
const harness = require('../../utils/harness-config');

const ROOT = path.join(__dirname, '../..');
const OUT = __dirname;

const TAG = 'breadth-4';

// Line-exact, both directions. Matching whole lines (never substrings) is what keeps the undo
// assertion below a real check rather than a tautology.
const SITE = '    g.target_stock_count = 2  # 目标持仓数量';
const EDITED = '    g.target_stock_count = 4  # 目标持仓数量'
             + '  # q-e9-champ-breadth: 2 -> 4 — ONLY change vs the raw book';

// The probe anchor: the last statement of `prepare_stock_list`, where both `g.hold_list` (L134,
// read off the real portfolio) and `g.trading_signal` (L155) are already set.
const ANCHOR = '    log.info(f"今日交易状态: {\'可交易\' if g.trading_signal else \'空仓月份，暂停交易\'}")';
const PROBE = "    log.error('HOLDCOUNT date=%s n=%d etf=%d tradable=%d names=%s' % "
            + "(str(context.current_dt.date()), len(g.hold_list), int(g.etf in g.hold_list), "
            + "int(g.trading_signal), '|'.join(g.hold_list)))"
            + '  # q-e9-champ-breadth instrumentation: per-session holdings split (stocks vs cash ETF)';

const src = fs.readdirSync(path.join(ROOT, 'strategies')).find(f => /0a7de9fa/.test(f));
if (!src) throw new Error('0a7de9fa not found in strategies/');

// ⚠ The comparison baseline is py2to3(raw), NOT the on-disk file: the variant is built on the
// py2to3 output, which is also what the normalizer measured the control on.
const raw = py2to3(fs.readFileSync(path.join(ROOT, 'strategies', src), 'utf8'));
const rawLines = raw.split('\n');

if (rawLines.filter(l => l === SITE).length !== 1) {
  throw new Error(`expected exactly 1 edit site (${SITE.trim()}) — refusing`);
}
if (rawLines.filter(l => l === ANCHOR).length !== 1) {
  throw new Error('expected exactly 1 probe anchor line — refusing');
}
if (rawLines.includes(PROBE) || rawLines.includes(EDITED)) {
  throw new Error('the variant lines are already present — refusing');
}

// The structural facts the design and the report rest on. Each is CHECKED, not assumed: if any has
// moved, the one-line edit no longer means "breadth 2 -> 4" and the result is uninterpretable.
const READ_SITES = [
  '    log.info(f"本周目标持仓列表（前{min(g.target_stock_count, len(g.target_list))}只）: {g.target_list[:g.target_stock_count]}")',
  '        if stock not in g.target_list[:g.target_stock_count]  # 不在目标列表前N只',
  '    buy_security(context, g.target_list[:g.target_stock_count])',
  '        need_buy = g.target_stock_count - len(g.hold_list)  # 需要补仓的数量',
  '            if len(context.portfolio.positions) >= g.target_stock_count:',
  '                log.info(f"已达到目标持仓数量 {g.target_stock_count}，停止买入")',
];
const facts = {
  // Exactly one assignment, so the knob has a single owner and the edit cannot be shadowed.
  'one assignment to the knob':
    rawLines.filter(l => /^\s*g\.target_stock_count\s*=/.test(l)).length === 1,
  // Declaration + the six read sites below = 7 textual occurrences. A different count means a
  // reader was added or removed and the blast radius of the edit is not what the design says.
  'exactly 7 occurrences of the knob':
    rawLines.filter(l => /g\.target_stock_count/.test(l)).length === 7,
  'all six read sites present': READ_SITES.every(s => rawLines.filter(l => l === s).length === 1),
  // The cash-ETF-occupies-a-slot facts, which requirement (1) of the dispatch is about.
  // Both call sites sit at the same indentation, so the line is asserted to appear exactly TWICE
  // and each is anchored to the branch it belongs to (empty month / after a stoploss).
  'ETF is a real position, bought in exactly two places':
    rawLines.filter(l => l === '        buy_security(context, [g.etf])').length === 2,
  'ETF buy #1 is the empty-month path (weekly_adjustment)':
    rawLines[rawLines.indexOf('    if not g.trading_signal:') + 1] === '        buy_security(context, [g.etf])',
  'ETF buy #2 is the post-stoploss path (check_remain_amount)':
    rawLines[rawLines.indexOf('        log.info(f"因止损操作，剩余资金 {cash:.2f} 元转入现金ETF: {g.etf}")') + 1]
      === '        buy_security(context, [g.etf])',
  'ETF exempt from selling in all four places':
    rawLines.filter(l => /stock\s*[=!]=\s*g\.etf/.test(l)).length === 4,
  'ETF is the cash tool declared at module scope':
    rawLines.filter(l => l === "CASH_ETF = '511880.XSHG'  # 现金替代工具（华宝添益，低风险流动性工具）").length === 1
    && rawLines.filter(l => l === '    g.etf = CASH_ETF           # 现金替代工具').length === 1,
  'empty months are Jan and Apr':
    rawLines.filter(l => l === 'EMPTY_MONTHS = [1,4,]  # 空仓月份（1月、4月，基于历史数据统计的风险较高月份）').length === 1,
  // `g.hold_list` must be the REAL portfolio at the probe site, or the probe reports a stale list.
  'hold_list is read off the portfolio at L134':
    rawLines.filter(l => l === '    g.hold_list = [pos.security for pos in context.portfolio.positions.values()]').length === 1,
  'probe anchor sits inside prepare_stock_list, after trading_signal is set':
    rawLines.indexOf(ANCHOR) > rawLines.indexOf('    g.trading_signal = today_is_tradable(context)')
    && rawLines.indexOf('    g.trading_signal = today_is_tradable(context)')
       > rawLines.indexOf('    g.hold_list = [pos.security for pos in context.portfolio.positions.values()]'),
  'the daily 9:05 hook is prepare_stock_list':
    rawLines.filter(l => l === "    run_daily(prepare_stock_list, '9:05')       # 每日开盘前初始化").length === 1,
  'the weekly rebalance is Tuesday 10:45':
    rawLines.filter(l => l === "    run_weekly(weekly_adjustment, 2, '10:45')   # 每周二10:00调仓").length === 1,
  // Capital per name is cash / len(need_buy), which is what makes 4 -> a 5e6 feasibility floor.
  'equal-weight sizing by need_buy':
    rawLines.filter(l => l === '    per_stock = cash / len(need_buy)').length === 1,
  'strategy logs at debug so the free reads survive':
    rawLines.filter(l => l === "    log.set_level('strategy', 'debug')  # 保留策略调试日志").length === 1,
};
for (const [k, ok] of Object.entries(facts)) {
  if (!ok) throw new Error(`structural precondition failed: ${k} — refusing`);
}

// The log lines the report is read from must survive, or the run cannot be attributed.
const LOGS = [
  'f"空仓月份（{g.pass_months}），切换至持有现金ETF: {g.etf}"',
  'f"调仓完成，共卖出 {len(sell_list)} 只股票"',
  'f"因涨停打开卖出，需补仓 {need_buy} 只，候选列表: {buy_list}"',
  'f"因止损操作，剩余资金 {cash:.2f} 元转入现金ETF: {g.etf}"',
  'f"共需买入 {len(need_buy)} 只股票，每只分配资金 {per_stock:.2f}元，总资金 {cash:.2f}元"',
  'f"买入成功 {stock}，金额 {per_stock:.2f}元"',
  'f"买入失败 {stock}，金额 {per_stock:.2f}元"',
];

// Build: swap the knob, and insert the probe immediately after the anchor.
const body = rawLines
  .map(l => (l === SITE ? EDITED : l))
  .flatMap(l => (l === ANCHOR ? [l, PROBE] : [l]))
  .join('\n');

if (!body.includes(EDITED)) throw new Error('the edit did not land');
if (!body.includes(PROBE)) throw new Error('the HOLDCOUNT probe did not land');
if (body.includes(SITE)) throw new Error('the original `= 2` line survived the edit — refusing');
if (/g\.target_stock_count\s*=\s*2/.test(body)) {
  throw new Error('a `g.target_stock_count = 2` assignment is still present — refusing');
}
if (body.split('\n').filter(l => /^\s*g\.target_stock_count\s*=/.test(l)).length !== 1) {
  throw new Error('the edit produced more or fewer than one assignment — refusing');
}
if (body.split('\n').length !== rawLines.length + 1) {
  throw new Error('the build changed more than the one edit plus the one probe — refusing');
}
for (const s of READ_SITES) {
  if (!body.includes(s)) throw new Error(`a read site of the knob was lost: ${s.trim()}`);
}
for (const need of LOGS) {
  if (!body.includes(need)) throw new Error(`missing log line needed for the report: ${need}`);
}
// The frozen cost block must be the OVERRIDE's, appended below — never hand-copied into the body.
if (!OVERRIDE.includes('set_order_cost')) {
  throw new Error('OVERRIDE does not look like the frozen cost block — refusing');
}

// ⚠⚠ The ONLY differences from py2to3(raw) must be the swapped line and the inserted probe.
// Assert on `body` — the PRE-OVERRIDE text — never on a slice of the final file: cutting the
// output at a marker is ambiguous against the file's own trailing newlines, and that is exactly
// what made build-liq-5a70adc1 report a false "first difference at line 840" of an 839-line file.
const undone = body.split('\n')
  .filter(l => l !== PROBE)
  .map(l => (l === EDITED ? SITE : l))
  .join('\n');
if (undone !== raw) {
  const a = undone.split('\n'), b = rawLines;
  const first = a.findIndex((l, i) => l !== b[i]);
  throw new Error('undoing the edit does not reproduce py2to3(raw) byte-for-byte '
                + `(first difference at line ${first + 1} of ${b.length}) — refusing`);
}

const out = body + OVERRIDE;
const file = path.join(OUT, `variants/0a7de9fa-${TAG}.py`);
fs.writeFileSync(file, out);

console.log(`[breadth] built variants/0a7de9fa-${TAG}.py  (epoch ${harness.config().epoch})`);
console.log(`[breadth] ONE edit at L${rawLines.indexOf(SITE) + 1}: g.target_stock_count 2 -> 4`);
console.log(`[breadth] + 1 instrumentation line (HOLDCOUNT, log.error) at L${rawLines.indexOf(ANCHOR) + 2}, `
          + 'end of prepare_stock_list (daily 9:05)');
console.log('[breadth] verified: 1 assignment, 6 read sites (L270/276/286/573/727/728) all intact; '
          + 'the cash ETF is a real position bought in 2 places and sell-exempt in 4, so it '
          + 'occupies one of the N slots via the L727 position-count break');
console.log('[breadth] kept verbatim: the 399101 pool, the 10-80亿 cap filter, both head() stages, '
          + 'the BBI band, the 顶背离 overlay, the stop-loss block, EMPTY_MONTHS=[1,4], the frozen '
          + 'cost block (from OVERRIDE, never hand-copied)');
console.log('[breadth] undo (restore L111 + drop the probe) reproduces py2to3(raw) byte-for-byte');
console.log("[breadth] control = the champion's own epoch-9 ledger row: objective 2.6282 / "
          + 'sharpe 7.07 / annual 276.82 / maxDD 14.00 (365 days); Jan-Nov objective 1.6888, '
          + 'December = 28.1% of the year\'s log-growth');
console.log('[breadth] PRE-REGISTERED, THREE BRANCHES:');
console.log('[breadth]   (a) objective <  1.60      => the advantage is specifically top-2 concentration');
console.log('[breadth]   (b) objective 2.10-2.68    => partial; a plateau, not a peak');
console.log('[breadth]   (c) objective >= 2.68      => the 驼峰顶 reading is REFUTED; the author\'s 2 '
          + 'is a knob tuned on 2024');
console.log('[breadth] ONE POINT ONLY — 3 and 6 are spawned by this result, never pre-queued');
