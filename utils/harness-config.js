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

/** A named window with `today` resolved. Unknown name -> null, so callers can error properly. */
function window(name) {
  const w = config().windows[name];
  if (!w) return null;
  return { name, start: w.start, end: w.end === 'today' ? todayISO() : w.end };
}

/** First date of the reserved out-of-sample period — the code guard's cutoff. */
function oosCutoff() { return config().windows.holdout.start; }

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
function comparableEpochs() {
  const active = config().epoch;
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
  return lit;
}

/**
 * Check the two places that must hold literal Python still agree with the active config.
 * @returns {string[]} problems; empty means consistent
 */
function verify() {
  const lit = pythonLiterals();
  const problems = [];
  const optional = ['avoidFutureData', 'orderVolumeRatio', 'fundOrderCost'].filter(k => lit[k]);
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

module.exports = { config, window, oosCutoff, gate, objective, score, stageGate, stageThreshold,
                   comparableEpochs, measurementValid,
                   pythonLiterals, verify, todayISO };
