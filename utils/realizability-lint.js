/**
 * realizability-lint.js — free, static flags for KNOWN unrealizability patterns.
 *
 * ## What this is, and emphatically is not
 *
 * It is a **reporter**, run at zero cost over source. It is **not** a gate, and it must never
 * become one. Two reasons, both of them things this repo has already measured:
 *
 *   1. **Realizability cannot be scored from source.** It needs measurement — turnover, holdings
 *      thinning, whether a fill is feasible at the book's own position size. 大小盘轮动's R=2 took
 *      the `liq-1` liquidity-floor experiment across three declared floors (31 JQ minutes) and the
 *      answer was counter-intuitive: the floor removed **zero** names on 31/31 rebalances and the
 *      curve was bit-identical. A static rule would have guessed the opposite.
 *   2. **A pre-measurement reject must be a known fact, never a guess** (CLAUDE.md). An early
 *      screening rule dropping "titles with no mechanism keyword" discarded **287 of 549**
 *      strategies, including a held family with four gate-passes. Wrong drops are permanent.
 *
 * And a third, specific to this: **the measurement is what EXPOSES the unrealizability.**
 * 7a1c225f's 100× unit bug was found by studying a book that had already been measured. A filter
 * that dropped it before normalize would have hidden the finding, and with it the discovery that
 * the same defect sat in two of §3's top five.
 *
 * So the value is TIMING, not vetoing: a flag stamped at the moment the number is created, because
 * that number immediately enters §3, `wiki/types/` and the champion resolution, and the reader
 * who needs the caveat is the one looking at the table — not someone who later reads §4.
 *
 * ## Every pattern is grounded, and PRECISE — or it is not here
 *
 * `severity: 'measured'` cites the experiment that measured its cost. `severity: 'info'` is a
 * property worth knowing that was never isolated as a cause, and says so.
 *
 * ⚠ Precision is the other bar, and it removed a pattern: see the note where `limit-up-entry`
 * used to be. A flag with many false positives is worse than no flag, because it teaches the
 * reader to skip the column — including the row that mattered.
 *
 * Usage:
 *   node utils/realizability-lint.js                       # the whole raw layer
 *   node utils/realizability-lint.js strategies/foo.py     # one file
 *   require('./realizability-lint').lint(source)            // -> [{id, severity, why, evidence}]
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const code = line => String(line).split('#')[0];

/** Any JQ order call — the thing a scheduled handler's NAME is only ever a proxy for. */
const ORDER_CALL = /\border_value\s*\(|\border_target\w*\s*\(|\border_shares\s*\(|\border\s*\(/;

/**
 * Does the `def <fn>` in this file place an order?
 *
 * Used by `call-auction-entry` as the second arm of its test: a handler scheduled inside the
 * auction window counts if its NAME looks like an order OR its BODY actually places one. That
 * is what catches `auction_trade` (fac28838), whose name matches no order keyword.
 *
 * ⚠ Deliberately SHALLOW — it reads the function's own lines, not its callees. A handler that
 * delegates (`st_buy`, `check_emergency_buy`: 3–5 line bodies) is therefore invisible here, which
 * is exactly why the name arm has to stay. Measured: every scheduled handler in the corpus is
 * defined in its own file, so this never returns a "cannot tell" that the caller must handle.
 * ⚠ Returns false, not null, for a function defined elsewhere: the name arm is the fallback, and
 * a flag that fires on "I could not parse this" is worse than one that stays quiet.
 */
function scheduledBodyOrders(lines, fn) {
  const start = lines.findIndex(l => new RegExp(`^\\s*def\\s+${fn}\\s*\\(`).test(l));
  if (start < 0) return false;
  const outer = (lines[start].match(/^\s*/) || [''])[0].length;
  for (let i = start + 1; i < lines.length; i++) {
    const l = lines[i];
    if (!l.trim()) continue;
    const indent = (l.match(/^\s*/) || [''])[0].length;
    if (indent <= outer && /^\s*(def|class)\s/.test(l)) break;   // next sibling definition
    if (ORDER_CALL.test(code(l))) return true;
  }
  return false;
}

/**
 * @typedef {{id:string, severity:'measured'|'info', why:string, test:(lines:string[])=>string|null}} Pattern
 */
const PATTERNS = [
  {
    id: 'tick-depth-x100',
    severity: 'measured',
    why: 'Reads tick depth (a*_v/b*_v) and scales it by 100 as if it were LOTS. JQ quotes it in ' +
         'SHARES, so a depth gate reads 100× its real value and admits names it was written to ' +
         'reject. MEASURED cost: objective 1.3861→0.6539 on 7a1c225f (q-e6-13), 1.2637→0.2867 on ' +
         '8dbd994c and 0.8577→0.2858 on 5e874b5b (q-e8-1/2) — and drawdown WORSENS in all three. ' +
         'Corroborated by two unrelated authors who compute depth money with no ×100.',
    test: lines => {
      const hit = lines.findIndex(l => /\b[ab][1-5]_v\b/.test(code(l)) && /\*\s*100\b|100\s*\*/.test(code(l)));
      return hit < 0 ? null : `line ${hit + 1}: ${code(lines[hit]).trim().slice(0, 90)}`;
    },
  },
  {
    id: 'uncapped-position-size',
    severity: 'measured',
    why: 'Divides all available cash by however many candidates appeared, with no per-name cap — ' +
         'so one candidate means a 100% single-name book. MEASURED: capping it at the ' +
         "strategy's own implied reserve took 7a1c225f from objective 1.3861 to 0.1606 combined " +
         'with the units fix (q-e6-15 / q-e6-18); the two are not additive because the fully-' +
         'weighted name is often the thinnest one.',
    test: lines => {
      const hit = lines.findIndex(l => /cash_per_stock\s*=\s*available_cash\s*\/\s*len\(/.test(code(l)));
      return hit < 0 ? null : `line ${hit + 1}: ${code(lines[hit]).trim().slice(0, 90)}`;
    },
  },
  // ⚠⚠ REMOVED: `limit-up-entry`. Two attempts, both worse than nothing.
  //
  // The intent was sound — buying a sealed 一字板 is the MEASURED basis for 打板短线's R=1, since
  // such a name cannot be bought at any price. But it is not separable at line granularity:
  //   attempt 1 (`high_limit` near a buy/sell word): 37 files, and both samples inspected were
  //             code that AVOIDS limit-ups — `s not in g.high_limit_list` excludes them from
  //             selling, `price < high_limit` requires being below the limit;
  //   attempt 2 (require >= / == against high_limit, exclude negations): **140** files, dominated
  //             by `day_open == high_limit`, which is a 一字板 DETECTOR used to exclude unbuyable
  //             names — the opposite behaviour again.
  // "Buys them" and "screens them out" both read `high_limit` with an equality, and the difference
  // lives in surrounding control flow a line regex cannot see. A flag that fires on the opposite
  // of what it claims trains a reader to ignore every flag, so the honest move is to not ship it.
  // If this is wanted, it needs an AST walk or a measured probe, not a third regex.
  {
    id: 'call-auction-entry',
    severity: 'info',
    why: 'Places orders inside the 9:15–9:25 call auction, or in the 9:26–9:29 gap after the ' +
         'auction price publishes and before continuous trading opens. Part of the stated basis ' +
         "for a30641fb's R=1 (min-500 market cap / 9:26 auction entry / ~100% daily turnover). " +
         'INFO rather than measured: the auction itself was never isolated as the cause.',
    // ⚠ NARROWED after its first run flagged 73 files, almost all on
    // `'09:25' < current_time < '11:30'` — a CONTINUOUS-TRADING window guard, which is the
    // opposite of an auction order. It requires a scheduled call INSIDE the window whose target
    // name looks like an order, not a check. That requirement is what killed the false positives
    // and it is unchanged.
    //
    // ⚠⚠ WIDENED 9:25 -> 9:29 (2026-10-21), because the ORIGINAL WINDOW MISSED ITS OWN
    // DOCUMENTED EXAMPLE. `a30641fb` schedules `run_daily(buy, time='9:26')` and CLAUDE.md
    // attributes its R=1 partly to "9:26 auction entry" — yet the 9:15–9:25 window reported
    // `0 of 1 file(s) flagged` on it. Found when `96fb1ca0` (竞价擒龙, `run_daily(buy, '09:26')`)
    // normalized at objective **7.8535 / sharpe 11.95**, 3.7x the next book on the bench, and the
    // realizability column that a §3 reader is supposed to weigh against it said nothing.
    //
    // 9:26–9:29 is the gap between the auction match price being PUBLISHED (9:25) and continuous
    // trading OPENING (9:30): an order scheduled there is placed knowing the opening print. The
    // book being measured says so itself, in a line its author commented out —
    //   `# run_daily(buy2, '09:27') #9:25分知道开盘价后可以提前下单`
    //   ("after knowing the opening price at 9:25 you can place the order early")
    // ⚠ It deliberately STOPS AT 9:29. 9:30 is the open of continuous trading — an ordinary
    // at-the-open entry, nominally fillable, and implicated by nothing in this repo. 12 of the 20
    // files scheduling an order in 9:26–9:30 sit on 9:30 exactly, so including it would have
    // doubled the hits on no evidence. The rule stays grounded in what was measured, which is the
    // standard `limit-up-entry` was DELETED for failing.
    test: lines => {
      const hit = lines.findIndex(l => {
        const c = code(l);
        // ⚠ `(?::[0-9]{2})?` — SECONDS-PRECISION times, a second false negative of the same
        // pattern, found the same night. The #3 book on the epoch-9 bench
        // (`38ca196e` 一进二v3.0, objective 5.2937 / sharpe 11.48) schedules
        // `run_daily(buy, '09:25:41')`, and a regex demanding the closing quote right after the
        // MINUTES cannot see it. Seconds precision is not incidental here — it is what you use to
        // time the auction, and every `HH:MM:SS` in the corpus clusters in 9:24–9:28 apart from
        // two at 09:30:00. Requiring HH:MM exactly meant the most aggressively timed entries in
        // the library were the ones the flag could not read.
        const m = c.match(/run_daily\(\s*([A-Za-z_][\w]*)\s*,\s*(?:time\s*=\s*)?['"]0?9:(1[5-9]|2[0-9])(?::[0-9]{2})?['"]/);
        // ⚠ `before_market_open` / `after_market_open` are JQ's PREPARATION hooks, not orders,
        // and they matched on the word "open" — 4 of the first 6 hits. Excluded by name, which
        // leaves the two real ones (`st_buy` at 09:23, `check_emergency_buy` at 9:15).
        if (!m || /_market_open$/.test(m[1])) return false;
        const fn = m[1];
        // ⚠ An EXIT inside the window is not what this flag claims. The union below otherwise
        // pulls in four sell handlers (`sell_check_open` x2, `process_pending_sells`,
        // `dapan_macd_check`), which would stretch the flag past its own name and past the
        // a30641fb basis it is grounded in ("9:26 auction ENTRY").
        if (/sell|卖|清仓|平仓/i.test(fn)) return false;
        // ⚠⚠ THE NAME ALLOWLIST WAS A THIRD FALSE NEGATIVE OF THIS SAME PATTERN (2026-11-05),
        // after the window being too narrow and the regex demanding HH:MM. `fac28838`
        // (战法三 双创恐慌低吸, sharpe 15.58 / implied vol 86%, #5 on the epoch-9 bench) schedules
        // `run_daily(auction_trade, '09:27')` — dead inside the documented window — and
        // `auction_trade` calls `order_value(target, buy_value, _mkt(target, True, _auc))` with an
        // auction order style. The window matched; the NAME rejected it, because `auction_trade`
        // contains none of buy/order/entry/建仓/买. So the realizability column said nothing about
        // it, which is the "reads as evidence of absence" failure, again.
        //
        // The name is only ever a PROXY for "this handler places orders", so ask the body too.
        // ⚠ Measured over all 891 files before changing anything, because a loose flag is what
        // got `limit-up-entry` deleted:
        //   name only (old)      32  (0.036)  — misses fac28838
        //   + `trade|交易`        38  (0.043)  — catches it, but 3 FALSE POSITIVES
        //                                        (before_trading_start / before_trading /
        //                                         generate_trade_time are prep hooks & helpers)
        //   body only            29  (0.033)  — 0 false positives, but DROPS `st_buy` and
        //                                        `check_emergency_buy`, whose 3–5 line bodies
        //                                        delegate the order to a helper
        //   name OR body, no sells  28 (0.031) — catches fac28838, keeps both delegators, 0 FPs
        // So the union is TIGHTER than the rule it replaces (0.031 vs 0.036, guard 0.25) while
        // strictly covering more. Keep both arms: neither alone is correct.
        if (/buy|order|entry|建仓|买/i.test(fn)) return true;
        return scheduledBodyOrders(lines, fn);
      });
      return hit < 0 ? null : `line ${hit + 1}: ${code(lines[hit]).trim().slice(0, 90)}`;
    },
  },
  {
    id: 'depth-gated',
    severity: 'info',
    why: "Gates entries on order-book depth. Informative, not a defect — it is the author's own " +
         'tradeability standard, and worth knowing because a 100× unit error turns such a gate ' +
         'inert (q-e6-14: switching it off moved objective +0.0107, correlation 0.9986).',
    test: lines => {
      const hit = lines.findIndex(l => /\b[ab][1-5]_[pv]\b/.test(code(l)) && /if\s|>\s*\d/.test(code(l)));
      return hit < 0 ? null : `line ${hit + 1}: ${code(lines[hit]).trim().slice(0, 90)}`;
    },
  },
];

/** @returns {Array<{id:string, severity:string, why:string, evidence:string}>} */
function lint(source) {
  const lines = String(source || '').split('\n');
  const out = [];
  for (const p of PATTERNS) {
    const evidence = p.test(lines);
    if (evidence) out.push({ id: p.id, severity: p.severity, why: p.why, evidence });
  }
  return out;
}

/** Lint one repo-relative file. */
function lintFile(rel) {
  try { return lint(fs.readFileSync(path.join(ROOT, rel), 'utf8')); }
  catch { return []; }
}

module.exports = { lint, lintFile, PATTERNS };

if (require.main === module) {
  const argv = process.argv.slice(2);
  const files = argv.filter(a => !a.startsWith('--'));
  const targets = files.length
    ? files
    : fs.readdirSync(path.join(ROOT, 'strategies')).filter(f => f.endsWith('.py')).map(f => `strategies/${f}`);

  console.log('[rlint] ⚠ REPORTS ONLY — never a veto. Realizability needs MEASUREMENT (liq-1 took');
  console.log('[rlint]   31 JQ min and found the floor inert), and a pre-measurement reject must be');
  console.log('[rlint]   a known fact: one guess-based screening rule discarded 287 of 549.\n');

  const tally = {};
  let flagged = 0;
  for (const t of targets) {
    const rs = lintFile(t);
    if (!rs.length) continue;
    flagged++;
    console.log(`  ${t.replace(/^strategies\//, '')}`);
    for (const r of rs) {
      console.log(`     ${r.severity === 'measured' ? '⚠ ' : '  '}${r.id.padEnd(22)} ${r.evidence}`);
      tally[r.id] = (tally[r.id] || 0) + 1;
    }
  }
  console.log(`\n[rlint] ${flagged} of ${targets.length} file(s) flagged`);
  for (const [id, n] of Object.entries(tally).sort((a, b) => b[1] - a[1])) {
    const p = PATTERNS.find(x => x.id === id);
    console.log(`   ${String(n).padStart(3)}  ${id}  [${p.severity}]`);
  }
}
