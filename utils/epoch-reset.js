/**
 * epoch-reset.js — clear the output a MEASUREMENT-breaking epoch bump invalidated.
 *
 * Epoch 9 moved TRAIN to 2024 and VAL to 2025, so `measurementValid()` rejects every row at epoch
 * <= 8 and nothing measured before it is a result for this bench. The pipeline is already CORRECT
 * without this tool — stale rows are filtered, not believed — so this is about making the repo say
 * what is true rather than about avoiding a wrong answer.
 *
 * ## The distinction that decides everything: GENERATED vs HAND-WRITTEN
 *
 * "Remove the generated output" is easy to over-apply. Measured before writing a line of this:
 *
 *   wiki/strategies/*.md   248 pages, **228 carrying a HAND-ASSIGNED `family:`**. The matcher
 *                          abstains on 82% of pages by design (a wrong assignment corrupts §3,
 *                          memberCount and the whole type layer), so that label is human work and
 *                          is NOT regenerable. Deleting these pages would destroy the family ->
 *                          member mapping the entire family layer is built on.
 *   wiki/families/*.md     13 pages, 656K, 78 sections of mechanism analysis, realism blocks, edge
 *                          claims and §4 gaps. The NUMBERS in them are stale; the understanding is
 *                          not, and no builder can reproduce it.
 *   study/<fam>/findings.tsv   248 findings, each already stamped with the window it was measured on.
 *
 * So this tool clears MEASUREMENTS and leaves LABELS AND PROSE alone. What it removes, a builder
 * reproduces from a re-measured ledger; what it keeps, nothing can.
 *
 * ## What it deliberately does NOT touch
 *
 *   strategies/              the immutable raw layer — the input, not an output.
 *   data/consumption.tsv     append-only AUDIT TRAIL. Deleting it would erase the record that two
 *                            OOS tests were already spent on the 2026 reserve. The budgets already
 *                            reset correctly via `sameBench`, and `oos-budget` still reports
 *                            "2 test(s) charged to EARLIER benches (not restored)" — that sentence
 *                            only exists because these rows do.
 *   validated_strategies/    the product shelf. The .py files are SOURCE, re-measurable, and
 *                            `integrate-eligible` already ignores them on a non-comparable epoch.
 *   screen/, data/discovered.json, data/copy-queue.json, data/post-bodies.json
 *                            screening and discovery are bench-independent: which post is worth
 *                            fetching does not change because the backtest window moved.
 *   wiki/families/*.md       kept whole. `wiki-family-build` regenerates §3 and the derived
 *                            frontmatter from the ledger on the next run.
 *
 * Usage:
 *   node utils/epoch-reset.js --dry     # print exactly what would change
 *   node utils/epoch-reset.js           # do it
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const harness = require('./harness-config');
const DRY = process.argv.includes('--dry');

const log = (...a) => console.log('[reset]', ...a);
const rel = p => path.relative(ROOT, p);

/** Truncate a TSV to its header, so the schema survives and the rows do not. */
function truncateTsv(p) {
  if (!fs.existsSync(p)) return null;
  const lines = fs.readFileSync(p, 'utf8').split('\n').filter(Boolean);
  if (!lines.length) return 0;
  const removed = lines.length - 1;
  if (!DRY) fs.writeFileSync(p, lines[0] + '\n');
  return removed;
}

function run() {
  const epoch = harness.config().epoch;
  const valid = harness.comparableEpochs();
  log(`active epoch ${epoch}; comparable epochs [${[...valid].join(',')}]`);

  // ── 1. the ledgers ────────────────────────────────────────────────────────
  // ⚠ Truncated to the header, not deleted: `utils/ledger.js` reads COLS off the live header and a
  // test asserts the two agree, so removing the file would take the schema with it.
  for (const w of ['train', 'val', 'holdout']) {
    const p = path.join(ROOT, `harness/normalize-${w}.tsv`);
    const n = truncateTsv(p);
    if (n != null) log(`${DRY ? 'would clear' : 'cleared'} ${rel(p)}: ${n} row(s)`);
  }

  // ── 2. the stored curves ──────────────────────────────────────────────────
  // Every key embeds the measuring epoch, so a pre-9 curve can never be loaded for epoch 9
  // anyway (`loadComparable` walks comparableEpochs). They are dead weight, not a hazard.
  const sdir = path.join(ROOT, 'data/series');
  let curves = 0, kept = 0;
  if (fs.existsSync(sdir)) {
    for (const f of fs.readdirSync(sdir).filter(x => x.endsWith('.json'))) {
      const m = f.match(/__e(\d+)\.json$/);
      // Keep anything the active bench could actually use — none today, but the rule must be the
      // epoch, not the date, or a re-run mid-reset would lose a fresh curve.
      if (m && valid.has(Number(m[1]))) { kept++; continue; }
      curves++;
      if (!DRY) fs.unlinkSync(path.join(sdir, f));
    }
  }
  log(`${DRY ? 'would delete' : 'deleted'} ${curves} stale curve(s), kept ${kept} on a comparable epoch`);

  // ── 3. fully generated pages ──────────────────────────────────────────────
  const tdir = path.join(ROOT, 'wiki/types');
  let types = 0;
  if (fs.existsSync(tdir)) {
    for (const f of fs.readdirSync(tdir).filter(x => x.endsWith('.md'))) {
      types++;
      if (!DRY) fs.unlinkSync(path.join(tdir, f));
    }
  }
  log(`${DRY ? 'would delete' : 'deleted'} ${types} type page(s) — wiki-type-build regenerates them`);

  // ── 4. the measurement block on strategy pages, LABELS UNTOUCHED ──────────
  const pdir = path.join(ROOT, 'wiki/strategies');
  let stripped = 0, withFamily = 0;
  if (fs.existsSync(pdir)) {
    for (const f of fs.readdirSync(pdir).filter(x => x.endsWith('.md'))) {
      const p = path.join(pdir, f);
      const t = fs.readFileSync(p, 'utf8');
      if (/^family:/m.test(t)) withFamily++;
      if (!/^normalized:.*$/m.test(t)) continue;
      stripped++;
      if (!DRY) fs.writeFileSync(p, t.replace(/^normalized:.*\n/m, ''));
    }
  }
  log(`${DRY ? 'would strip' : 'stripped'} ${stripped} normalized: block(s); ` +
      `${withFamily} hand-assigned family: label(s) LEFT ALONE`);

  // ── 5. integration state ──────────────────────────────────────────────────
  // Promotions and refusals are judgements about measurements that no longer exist. A promoted
  // candidate is "what the universe would otherwise ship", which cannot be asserted from a bench
  // this epoch rejects.
  for (const f of ['data/promoted.tsv', 'data/integrate-refusals.tsv']) {
    const n = truncateTsv(path.join(ROOT, f));
    if (n != null) log(`${DRY ? 'would clear' : 'cleared'} ${f}: ${n} row(s)`);
  }

  // ── 6. work queues ────────────────────────────────────────────────────────
  // The deferred pool holds slow-skips with the cap they failed at — all pre-9, so re-offering
  // them says nothing about the new windows. The pending queue is rebuilt by normalize-backfill,
  // in screening-priority order, which this tool must not try to reproduce.
  const dp = path.join(ROOT, 'data/deferred.json');
  if (fs.existsSync(dp)) {
    const n = Object.keys(JSON.parse(fs.readFileSync(dp, 'utf8'))).length;
    if (!DRY) fs.writeFileSync(dp, '{}\n');
    log(`${DRY ? 'would empty' : 'emptied'} data/deferred.json: ${n} parked entr(ies)`);
  }

  log('');
  log('KEPT, deliberately: strategies/ (raw input), data/consumption.tsv (audit trail — it is');
  log('  what still reports the 2 OOS tests spent on the 2026 reserve), validated_strategies/*.py');
  log('  (source, already ignored on a stale epoch), wiki/families/*.md (hand-written analysis),');
  log('  study/*/findings.tsv (each stamped with its own window), screen/ + discovery (bench-');
  log('  independent).');
  log('');
  log('NEXT: node utils/normalize-backfill.js   # rebuild the queue in screening-priority order');
  log('      node utils/wiki-family-build.js    # regenerate §3 from the now-empty ledger');
  if (DRY) log('(--dry — nothing written)');
}

module.exports = { run };
if (require.main === module) run();
