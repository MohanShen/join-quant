/**
 * harness-config.js — the ONE place the frozen bench's constants are read from.
 *
 * Before this, the windows appeared in seven files and the cost line in four
 * (strategy-post-backtest.js, strategy-normalize.js, enhance/strategy_template.py,
 * harness/harness.md, docs/enhance-schema.md, docs/study-schema.md, study/program.md).
 * They had already drifted: study-schema still said dissection may use any sub-window through
 * 2024-12-31, which the epoch-3 window change silently contradicts. Bumping an epoch meant
 * editing prose in several places and hoping.
 *
 * Now: `harness/config/epoch-<n>.json` holds the VALUES, `harness/config/active.json` says which
 * epoch is in force, and `harness/harness.md` explains the INTENT. Prior epochs are kept so a
 * result stays attached to the rules that produced it.
 *
 * One thing cannot read this file: `enhance/strategy_template.py`'s frozen block and
 * `strategy-normalize.js`'s injected OVERRIDE are Python executed on JoinQuant's servers, so
 * they must stay literal. `--verify` exists for exactly that gap: it checks the literals still
 * match the active config and fails loudly when they do not.
 *
 * Usage:
 *   const h = require('./harness-config');
 *   h.window('train')            // { name, start, end }
 *   h.gate(sharpe)               // boolean
 *   h.objective(annualPct, maxddPct, sharpe)   // number | 'DQ'
 *
 *   node utils/harness-config.js           # print the active config
 *   node utils/harness-config.js --verify  # check the Python literals agree
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const DIR = path.join(ROOT, 'harness/config');

let _cfg = null;

const todayISO = () => new Date().toISOString().slice(0, 10);

/** The epoch currently in force. */
function config() {
  if (_cfg) return _cfg;
  const active = JSON.parse(fs.readFileSync(path.join(DIR, 'active.json'), 'utf8'));
  const file = path.join(DIR, `epoch-${active.activeEpoch}.json`);
  if (!fs.existsSync(file)) throw new Error(`active epoch ${active.activeEpoch} has no config at ${file}`);
  _cfg = JSON.parse(fs.readFileSync(file, 'utf8'));
  if (_cfg.status !== 'active') throw new Error(`epoch ${_cfg.epoch} is marked "${_cfg.status}", not active`);
  return _cfg;
}

/**
 * The most recent WEEKDAY strictly before today, as JQ requires.
 *
 * ⚠⚠ Why this is not just `todayISO()`. A window whose `end` is `"today"` was resolved to today's
 * date and handed to JoinQuant, which refuses it outright:
 *   「编译失败:结束时间不能大于前一个交易日」 — the end may not be LATER than the previous trading day.
 * Measured 2026-10-17 (a Saturday): the first real OOS run compile-failed on exactly this, so the
 * rolling holdout end was unrunnable by construction. It cost nothing — a failed run produces no
 * number and `oos-budget` charges only a COMPLETED one, which is the rule working as designed —
 * but it would have failed on every weekend and every Monday too.
 *
 * ⚠ Weekends only; this has no holiday calendar, and it cannot have one — `harness-config.js` is
 * read outside any JQ session. In a run adjacent to a long closure (Spring Festival, National Day)
 * the previous weekday may itself be a holiday and JQ will refuse again. That is safe rather than
 * silent: the refusal is loud, it charges nothing, and the fix is to step back another day.
 */
function previousWeekdayISO() {
  const d = new Date(`${todayISO()}T00:00:00Z`);
  do { d.setUTCDate(d.getUTCDate() - 1); } while (d.getUTCDay() === 0 || d.getUTCDay() === 6);
  return d.toISOString().slice(0, 10);
}

/**
 * A named window with `today` resolved. Unknown name -> null, so callers can error properly.
 *
 * ⚠ `end: "today"` means "as much of the reserve as exists", so the holdout window LENGTHENS with
 * the calendar. Consequence worth knowing: two OOS tests taken on different days in the same epoch
 * do NOT cover the same window, so their numbers are not strictly comparable to each other — only
 * each to its own stated span. Record the resolved dates with any OOS result.
 */
function window(name) {
  const w = config().windows[name];
  if (!w) return null;
  return { name, start: w.start, end: w.end === 'today' ? previousWeekdayISO() : w.end };
}

/** First date of the reserved out-of-sample period — the code guard's cutoff. */
function oosCutoff() { return config().windows.holdout.start; }

/**
 * The calendar years a named window spans, each clipped to the window and carrying its own
 * CALENDAR day count.
 *
 * The day count is what a per-year metric annualizes over, and it is derived from the window
 * rather than from whatever curve is being measured — the same convention the ledger uses for
 * the whole window, and for the same reason: a curve spans the trading days that happened to
 * occur, so self-annualizing each slice injects a gap that scales with the return level
 * (measured at 0.27pp median but 0.80pp on an 85.9% book, which made healthy rows look broken).
 */
function windowYears(name) {
  const w = window(name);
  if (!w) return [];
  const out = [];
  for (let y = Number(w.start.slice(0, 4)); y <= Number(w.end.slice(0, 4)); y++) {
    const start = w.start > `${y}-01-01` ? w.start : `${y}-01-01`;
    const end = w.end < `${y}-12-31` ? w.end : `${y}-12-31`;
    if (start > end) continue;
    out.push({ year: y, start, end, days: Math.round((Date.parse(end) - Date.parse(start)) / 86400000) + 1 });
  }
  return out;
}

function gate(sharpe) {
  const o = config().objective;
  const s = parseFloat(sharpe);
  return Number.isFinite(s) && s >= o.gateMin;
}

/**
 * score = annualReturn - maxDrawdown. Inputs are PERCENTAGES (as the SUMMARY line reports
 * them); the result is a fraction. Returns null only when the inputs are unusable.
 */
function score(annualPct, maxddPct) {
  const a = parseFloat(annualPct), d = parseFloat(maxddPct);
  if (!Number.isFinite(a) || !Number.isFinite(d)) return null;
  return Number(((a - d) / 100).toFixed(4));
}

/**
 * The objective as the ACTIVE epoch defines it.
 *
 * Epoch 5 keeps the score even when the gate fails. Before that, failing set it to 'DQ'
 * (-inf), which threw away the difference between a sharpe of 2.4 and one of -1.8 and left
 * five of fourteen families with no comparable number at all. The gate is now a label
 * carried alongside the score, not an eraser.
 */
function objective(annualPct, maxddPct, sharpe) {
  const s = score(annualPct, maxddPct);
  if (config().objective.keepScoreOnGateFail) return s == null ? 'DQ' : s;
  if (!gate(sharpe)) return 'DQ';
  return s == null ? 'DQ' : s;
}

/**
 * The sharpe bar a given STAGE requires. Same measurement everywhere — only the standard
 * differs, which is a decision rule rather than a different bench.
 */
function stageGate(stage, sharpe) {
  const t = (config().objective.stageThresholds || {})[stage];
  const min = t == null ? config().objective.gateMin : t;
  const v = parseFloat(sharpe);
  return Number.isFinite(v) && v >= min;
}

/** The threshold a stage applies, for reporting. */
function stageThreshold(stage) {
  const t = (config().objective.stageThresholds || {})[stage];
  return t == null ? config().objective.gateMin : t;
}

/**
 * How the ACTIVE epoch defines the bar an integration candidate must clear.
 *
 * Epoch 7 moved it from the pooled TRAIN objective to the WORST TRAIN YEAR. The pooled
 * objective is almost purely annual return — measured over 60 epoch-6 rows, r(annual, objective)
 * = 0.9698 and maxDrawdown supplies 24% of the spread — and annual return over TRAIN is
 * substantially a 2022 measurement: across the 13 stored TRAIN curves, 2022 supplies a median
 * 62% of total log-growth and 63-71% for every top-8 book. So a merge whose payoff is
 * robustness rather than level had no channel to register, which is exactly what both
 * 2026-10 merge rounds reported.
 *
 * Epochs before 7 declare no bar, and default to the pooled rule they actually ran under — an
 * old result must keep being judged by the rule that produced it.
 */
function integrateBar() {
  const o = config().objective;
  return o.integrateBar || { basis: 'pooled', metric: o.score, pooledIsVeto: true, fallback: 'pooled' };
}

/**
 * Is a result MEASURED under `rowEpoch` still valid under the active one?
 *
 * Not every epoch bump invalidates a measurement. Epoch 5 changed only the SCORING rule — the
 * bench (windows, costs, pins, slippage, capital, frequency) is byte-identical to epoch 4, and
 * `epoch-5.json` says so in a machine-readable `comparability.unchangedFromEpoch4`. But the
 * normalizer's done-check was a strict `rowEpoch === ACTIVE_EPOCH`, so it treated epoch-4 rows
 * as unmeasured and would have re-run them for nothing. Left alone, EVERY future scoring-only
 * bump would re-measure the whole library — at 60 backtest-minutes a day, that is the most
 * expensive kind of silent bug this repo has.
 *
 * Conservative by construction: an epoch is comparable only if each bump between it and the
 * active one explicitly declared itself measurement-preserving. Anything unstated is NOT
 * comparable, so a real cost change can never be mistaken for a scoring tweak.
 *
 * ⚠ The flag is `comparability.measurementPreservedFromPrevious`, an explicit boolean — NOT
 * the `unchangedFromEpoch<n>` list. That list enumerates what STAYED the same, which is a
 * different question: epoch 4 lists seven unchanged items and its own prose still says "NOT
 * comparable", because the two things it DID change (the participation cap and fund costs)
 * alter fills and fees. Reading the list as an equivalence marked epoch 3 comparable and would
 * have silently accepted pre-pin measurements as current.
 */
function comparableEpochs(from) {
  const active = from == null ? config().epoch : Number(from);
  const ok = new Set([active]);
  // Walk back while each epoch declares that it preserved the previous one's measurements.
  for (let e = active; e > 1; e--) {
    let cfg;
    try { cfg = JSON.parse(fs.readFileSync(path.join(DIR, `epoch-${e}.json`), 'utf8')); }
    catch { break; }
    if ((cfg.comparability || {}).measurementPreservedFromPrevious !== true) break;
    ok.add(e - 1);
  }
  return ok;
}

/**
 * Are two epochs the SAME BENCH — i.e. was the measurement preserved across every bump between
 * them? Order-independent: comparability is walked back from the later of the two.
 *
 * ⚠ This is the question the VAL budget has to ask, and it used to ask epoch EQUALITY instead.
 * Epochs 7 and 8 were scoring-only, so an epoch-6 validation is still a current result — but
 * under equality every family read "first-of-epoch" at epoch 8, including all six that had
 * already validated. A bump that measured nothing silently re-granted the most protected
 * resource in the repo.
 */
function sameBench(a, b) {
  const x = Number(a), y = Number(b);
  if (!Number.isFinite(x) || !Number.isFinite(y)) return false;
  if (x === y) return true;
  const later = Math.max(x, y), earlier = Math.min(x, y);
  return comparableEpochs(later).has(earlier);
}

/** Does a ledger row's `epoch` column still count as a result for the active epoch? */
function measurementValid(rowEpoch) {
  const n = typeof rowEpoch === 'string' ? parseInt(rowEpoch, 10) : rowEpoch;
  return Number.isFinite(n) && comparableEpochs().has(n);
}

/** The exact Python literals the frozen block must contain, generated from the config. */
function pythonLiterals() {
  const c = config().costs;
  const lit = {
    slippage: `set_slippage(${c.slippage.kind}(${c.slippage.value}))`,
    commission: `set_commission(PerTrade(buy_cost=${c.commission.buy}, ` +
                `sell_cost=${c.commission.sell}, min_cost=${c.commission.minCost}))`,
    benchmark: `set_benchmark('${c.benchmark}')`,
    useRealPrice: `set_option('use_real_price', ${c.useRealPrice ? 'True' : 'False'})`,
  };
  // epoch 4 pins: only emitted when the active config actually declares them, so the
  // verifier keeps working against an older epoch without demanding literals it never had.
  if (c.avoidFutureData != null) {
    lit.avoidFutureData = `set_option('avoid_future_data', ${c.avoidFutureData ? 'True' : 'False'})`;
  }
  if (c.orderVolumeRatio != null) {
    lit.orderVolumeRatio = `set_option('order_volume_ratio', ${c.orderVolumeRatio})`;
  }
  if (c.fundOrderCost) {
    const f = c.fundOrderCost;
    lit.fundOrderCost = `set_order_cost(OrderCost(open_commission=${f.openCommission}, `
      + `close_commission=${f.closeCommission}, close_tax=${f.closeTax}, `
      + `min_commission=${f.minCommission}), type='fund')`;
  }
  // epoch 6: the stock leg. set_commission(PerTrade) never governed it — JQ deprecated that
  // API in favour of set_order_cost, so a strategy's own type='stock' call won outright.
  // Measured: a 5%/side stock commission injected into int-001 moved total return
  // +64.44% -> -11.33%, proving the bench was not in control of stock fees at all.
  if (c.stockOrderCost) {
    const s = c.stockOrderCost;
    lit.stockOrderCost = `set_order_cost(OrderCost(open_commission=${s.openCommission}, `
      + `close_commission=${s.closeCommission}, close_tax=${s.closeTax}, `
      + `min_commission=${s.minCommission}), type='stock')`;
  }
  return lit;
}

/**
 * Check the two places that must hold literal Python still agree with the active config.
 * @returns {string[]} problems; empty means consistent
 */
function verify() {
  const lit = pythonLiterals();
  const problems = [];
  const optional = ['avoidFutureData', 'orderVolumeRatio', 'fundOrderCost', 'stockOrderCost'].filter(k => lit[k]);
  const files = [
    ['enhance/strategy_template.py', ['slippage', 'commission', 'benchmark', 'useRealPrice', ...optional]],
    ['utils/strategy-normalize.js', ['slippage', 'commission', ...optional]],
  ];
  for (const [rel, keys] of files) {
    const p = path.join(ROOT, rel);
    if (!fs.existsSync(p)) { problems.push(`${rel}: missing`); continue; }
    const text = fs.readFileSync(p, 'utf8');
    for (const k of keys) {
      if (!text.includes(lit[k])) problems.push(`${rel}: does not contain the epoch-${config().epoch} literal  ${lit[k]}`);
    }
  }
  return problems;
}

if (require.main === module) {
  const c = config();
  if (process.argv.includes('--verify')) {
    const problems = verify();
    if (!problems.length) {
      console.log(`[harness] epoch ${c.epoch}: Python literals match the config`);
    } else {
      console.error(`[harness] ⚠ epoch ${c.epoch}: ${problems.length} mismatch(es)`);
      problems.forEach(p => console.error(`   ${p}`));
      process.exitCode = 1;
    }
  } else {
    console.log(`harness epoch ${c.epoch} (set ${c.setAt}) — ${c.status}`);
    for (const n of Object.keys(c.windows)) {
      const w = window(n);
      console.log(`  ${n.padEnd(8)} ${w.start} .. ${w.end}${c.windows[n].end === 'today' ? '  (rolling)' : ''}`);
    }
    console.log(`  gate     ${c.objective.gateMetric} >= ${c.objective.gateMin}`);
    console.log(`  score    ${c.objective.score}`);
    console.log(`  costs    slippage ${c.costs.slippage.kind}(${c.costs.slippage.value}), ` +
                `commission ${c.costs.commission.buy}/${c.costs.commission.sell} min ${c.costs.commission.minCost}`);
    console.log(`  OOS      <= ${c.oosPolicy.maxTestsPerCandidate} test/candidate, <= ${c.oosPolicy.maxTestsPerEpoch}/epoch`);
    if (c.changedFromPreviousEpoch) {
      console.log('  changed from the previous epoch:');
      c.changedFromPreviousEpoch.forEach(x => console.log(`     ${x}`));
    }
  }
}

module.exports = { config, window, windowYears, previousWeekdayISO, oosCutoff, gate, objective, score,
                   stageGate, stageThreshold, integrateBar,
                   comparableEpochs, sameBench, measurementValid,
                   pythonLiterals, verify, todayISO };
