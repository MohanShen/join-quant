/**
 * series-rekey.js — recover curves saved under a mangled TEMP-PATH key.
 *
 * ## The bug this repairs
 *
 * `strategy-post-backtest.js` derives the series key from the file it was handed:
 *
 *     const sourceFile = path.relative(path.resolve(__dirname, '..'), strategyPath);
 *
 * That is right when a caller passes a real repo path (`enhance/candidates/x.py`,
 * `study/<fam>/baseline.py`). But `strategy-normalize.js` writes a NORMALIZED COPY to
 * `/tmp/jq-normalize/<tag>.py` and runs the child on that, so `path.relative` produced
 * `../../../tmp/jq-normalize/<tag>.py` and `seriesKey()` turned it into
 *
 *     .._.._.._tmp_jq-normalize_<tag>__train__e<N>.json
 *
 * Two things then hid the damage completely:
 *
 *   1. the key starts with a DOT, so every `ls data/series/` in this repo's history listed
 *      none of them — the files are hidden;
 *   2. nothing could ever read them back, because every reader builds its key from the real
 *      `sourceFile`, so `loadComparable()` reported "no curve" for a curve sitting on disk.
 *
 * Measured 2026-10-16: **63 curves** were stranded this way — every strategy normalized since
 * series capture was added. It is also why four family champions looked curveless and why
 * `series-backfill.js` found zero matches for them: the backfill matches the ACCOUNT's retained
 * runs, and JQ had reaped those, while the local capture had been saved all along under a name
 * nothing looks up. Under epoch 8 this silently downgrades the integration bar to the pooled
 * fallback, which is how it finally surfaced.
 *
 * ## How a stranded file is mapped back
 *
 * The normalizer's tag is `(postId || basename).slice(0, 8)` (strategy-normalize.js), and the
 * ledger stores `postId` beside `sourceFile`. So the tag is recomputed for every ledger row and
 * matched against the filename's tag.
 *
 * ⚠ Eight hex characters can collide, and a wrong curve silently corrupts every correlation and
 * every per-year bar computed from it. A tag claimed by more than one sourceFile is therefore
 * SKIPPED and reported, never guessed — the same rule `series-backfill.js` applies to an
 * ambiguous match. A target key that already exists is also skipped rather than overwritten.
 *
 * Usage:
 *   node utils/series-rekey.js --dry     # what would move, and what cannot be mapped
 *   node utils/series-rekey.js           # move them (originals are RENAMED, not copied)
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const DIR = () => process.env.JQ_SERIES_DIR || path.join(ROOT, 'data/series');
const LEDGER_DIR = () => process.env.JQ_HARNESS_DIR || path.join(ROOT, 'harness');

/** Mangled names look like `.._.._.._tmp_jq-normalize_<tag>__<window>__e<N>.json`. */
const MANGLED = /^\.[._]*tmp_jq-normalize_([0-9a-zA-Z]+)__([a-z]+)__e(\d+)\.json$/;

/**
 * tag -> [sourceFile…] across every ledger window. A tag with more than one sourceFile is
 * ambiguous and gets skipped; the list is kept so the report can name the rivals.
 */
function tagMap() {
  const byTag = new Map();
  let files = [];
  try { files = fs.readdirSync(LEDGER_DIR()).filter(f => /^normalize-.*\.tsv$/.test(f)); } catch { return byTag; }
  for (const f of files) {
    const lines = fs.readFileSync(path.join(LEDGER_DIR(), f), 'utf8').split('\n');
    for (const l of lines.slice(1)) {
      if (!l.trim()) continue;
      const c = l.split('\t');
      const sourceFile = c[0];
      if (!sourceFile) continue;
      // Mirrors strategy-normalize.js: `(postId || f).slice(0, 8)`, where `f` is the BASENAME.
      const basename = sourceFile.replace(/^strategies\//, '');
      const tag = String(c[1] || basename).slice(0, 8);
      const seen = byTag.get(tag) || new Set();
      seen.add(sourceFile);
      byTag.set(tag, seen);
    }
  }
  return byTag;
}

function plan() {
  const series = require('./backtest-series');
  const byTag = tagMap();
  let names = [];
  try { names = fs.readdirSync(DIR()); } catch { return { moves: [], skipped: [] }; }

  const moves = [], skipped = [];
  for (const name of names) {
    const m = name.match(MANGLED);
    if (!m) continue;
    const [, tag, windowName, epoch] = m;
    const owners = byTag.get(tag);
    if (!owners || owners.size === 0) {
      skipped.push({ name, tag, why: 'no ledger row carries this tag' });
      continue;
    }
    if (owners.size > 1) {
      // Never guess: a wrong curve corrupts every correlation and per-year bar built on it.
      skipped.push({ name, tag, why: `tag claimed by ${owners.size} sourceFiles: ${[...owners].join(', ')}` });
      continue;
    }
    const sourceFile = [...owners][0];
    const key = series.seriesKey(sourceFile, windowName, epoch);
    const to = `${key}.json`;
    if (to === name) continue;
    if (fs.existsSync(path.join(DIR(), to))) {
      skipped.push({ name, tag, why: `target already exists (${to}) — not overwritten` });
      continue;
    }
    moves.push({ from: name, to, sourceFile, windowName, epoch });
  }
  return { moves, skipped };
}

/**
 * Rewrite the record's own `sourceFile` as well as its filename. The stored record carries the
 * meta it was captured with, and leaving `../../../tmp/...` inside it would keep a second,
 * stale copy of the identity that a later reader could trust.
 */
function apply(moves) {
  let done = 0;
  for (const mv of moves) {
    const from = path.join(DIR(), mv.from), to = path.join(DIR(), mv.to);
    const rec = JSON.parse(fs.readFileSync(from, 'utf8'));
    rec.sourceFile = mv.sourceFile;
    rec.rekeyedFrom = mv.from;
    fs.writeFileSync(to, JSON.stringify(rec));
    fs.unlinkSync(from);
    done++;
  }
  return done;
}

if (require.main === module) {
  const dry = process.argv.includes('--dry');
  const { moves, skipped } = plan();
  console.log(`[rekey] ${moves.length} stranded curve(s) can be re-keyed, ${skipped.length} cannot`);
  for (const mv of moves) console.log(`   ${mv.from}\n     -> ${mv.to}`);
  for (const s of skipped) console.log(`   ⚠ SKIP ${s.name} — ${s.why}`);
  if (dry) { console.log('[rekey] (--dry — nothing moved)'); process.exit(0); }
  const n = apply(moves);
  console.log(`[rekey] moved ${n}`);
}

module.exports = { MANGLED, tagMap, plan, apply };
