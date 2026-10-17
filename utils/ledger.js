/**
 * ledger.js — the ONE place that knows the shape of `harness/normalize-*.tsv`.
 *
 * ## Why this exists
 *
 * The ledger is what every family table, the integration bar, the `/run-family` exit gate and the
 * champion resolution are computed from — and **eight files hard-coded numeric column indices**
 * into it (measured 2026-10-17):
 *
 *   family-queue      c[0] c[2] c[3] c[9] c[11] c[12] c[13]
 *   integrate-eligible c[0] c[3] c[8] c[9] c[10] c[11] c[13]
 *   component-scan    c[0] c[2] c[3] c[6] c[8] c[9] c[10] c[11] c[12] c[13]
 *   wiki-family-build c[0] c[3] c[7] c[8] c[9] c[10] c[11] c[12] c[13]
 *   normalize-daily   c[1] c[13]
 *   stockcost-affected / wiki-type-build / daily-summary   c[0] c[3]
 *
 * So a column inserted anywhere but the end silently shifts the meaning of every one of them —
 * `sharpe` becomes `annual_pct`, `gate` becomes `objective` — and nothing fails. Exactly the
 * hazard CLAUDE.md records for the harness constants ("duplicated across seven files and had
 * already drifted"), on the data this repo trusts most.
 *
 * ⚠ It has already drifted once: `normalize-ledger-rebuild.js` emits **13** columns while the
 * ledger carries **14**, so a rebuild after a regression would have produced rows whose `epoch` is
 * absent — and `measurementValid(undefined)` then decides what is current.
 *
 * ## What this module is, and is not
 *
 * It owns the **schema**: the column order, the names, and the row→object parse. It deliberately
 * does **not** own the iteration policy, because the readers genuinely differ — `family-queue`
 * wants the newest epoch per file, `component-scan` wants every row with a curve,
 * `integrate-eligible` wants the best objective among measurement-valid rows. Unifying those would
 * replace eight correct, legible loops with one function full of flags. The indices were the
 * hazard; the loops were not.
 *
 * `COLS` is asserted against the live header by a test, so a column added to the writer without
 * being added here fails loudly in one place instead of quietly in eight.
 *
 * Usage:
 *   const ledger = require('./ledger');
 *   for (const r of ledger.rows()) { … }            // parsed objects, status unfiltered
 *   for (const r of ledger.normalized()) { … }       // status === 'normalized' only
 *   ledger.parse(line)                               // one TSV line -> object (null if unusable)
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');

/**
 * Column order of `harness/normalize-*.tsv`, as written by `strategy-normalize.js`.
 * ⚠ Append only, and update the writer in the same commit — a test compares this to the live
 * header precisely so the two cannot diverge silently.
 */
const COLS = [
  'sourceFile', 'postId', 'title', 'status', 'start', 'end', 'days',
  'total_pct', 'annual_pct', 'sharpe', 'maxdd_pct', 'objective', 'gate', 'epoch',
];

/**
 * Name -> column index, for a reader that wants the RAW STRING rather than a number.
 *
 * `wiki-family-build.js` is the case: it renders `sharpe`/`annual`/`maxdd` straight into the §3
 * tables, so parsing and re-stringifying them would silently reformat the wiki (a stored "1.460"
 * becoming "1.46"). `r.raw[IDX.sharpe]` keeps the exact text and is still named, which is the
 * whole point — `c[9]` is what this module exists to remove.
 */
const IDX = Object.fromEntries(COLS.map((n, i) => [n, i]));

/** Columns parsed as numbers. `objective` carries the literal 'DQ' for a disqualified row. */
const NUMERIC = new Set(['days', 'total_pct', 'annual_pct', 'sharpe', 'maxdd_pct', 'objective']);

const FILE = (window = 'train') =>
  process.env.JQ_LEDGER || path.join(ROOT, 'harness', `normalize-${window}.tsv`);

/**
 * Parse one TSV line into a named object.
 *
 * `num` fields are `null` when blank or unparseable rather than `NaN`, because `NaN` propagates
 * through a comparison as `false` and makes a missing measurement look like a losing one.
 * `objective: 'DQ'` is preserved as the string — it is a verdict, not a number.
 *
 * @returns {object|null} null for a blank line or one with no sourceFile.
 */
function parse(line) {
  if (!line || !line.trim()) return null;
  const c = line.split('\t');
  if (!c[0]) return null;
  const r = { raw: c };
  COLS.forEach((name, i) => {
    const v = c[i] === undefined ? '' : c[i];
    if (!NUMERIC.has(name)) { r[name] = v; return; }
    if (name === 'objective' && v === 'DQ') { r[name] = 'DQ'; return; }
    const n = parseFloat(v);
    r[name] = Number.isFinite(n) ? n : null;
  });
  // ⚠ An unstamped row predates the epoch column. It is reported as null rather than defaulted,
  // because `measurementValid(null)` and `measurementValid('2')` are different questions and the
  // callers that care already handle the first. (family-queue defaults it to '2' itself, which is
  // its own policy and stays there.)
  r.epoch = c[IDX.epoch] || null;
  return r;
}

/** Every parseable row of one window's ledger, in file order. */
function rows(window = 'train') {
  let text;
  try { text = fs.readFileSync(FILE(window), 'utf8'); } catch { return []; }
  return text.split('\n').slice(1).map(parse).filter(Boolean);
}

/** Rows whose `status` is `normalized` — i.e. a real measurement, not a failure mode. */
function normalized(window = 'train') {
  return rows(window).filter(r => r.status === 'normalized');
}

/** The live header, for the schema test and for a reader that wants to check before trusting. */
function header(window = 'train') {
  try {
    return fs.readFileSync(FILE(window), 'utf8').split('\n')[0].split('\t');
  } catch { return []; }
}

module.exports = { COLS, IDX, NUMERIC, FILE, parse, rows, normalized, header };
