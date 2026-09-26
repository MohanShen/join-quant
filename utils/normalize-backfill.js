/**
 * normalize-backfill.js — queue the strategies we HOLD but have never measured,
 * ordered by screening priority.
 *
 * The gap this closes
 * -------------------
 * Screening ranked what to DOWNLOAD (`data/copy-queue.json`). Normalization measures
 * what we have already downloaded. Nothing connected them: `normalize-daily.js` only ever
 * enqueued strategies fetched on that same run and explicitly refused to touch the backlog,
 * so 77 files sat on disk that nothing would ever pick up.
 *
 * This writes the backlog into `data/pending-normalize.json` — the queue the daily
 * normalizer already drains and already carries over between runs — so the connection needs
 * no new plumbing downstream. Order is the screening `priority`, highest first.
 *
 * Unrunnable files are EXCLUDED, not ranked last. A screener that marked S=0 is saying the
 * frozen harness cannot produce a valid result for this file at all (futures-only, Python 2,
 * needs minute bars or external data). Queuing those would burn the 60 backtest-minutes/day
 * on a guaranteed failure. They are listed in the report so the decision stays visible.
 *
 * Identity: files map to screening verdicts through `copy-queue.json.copied[key].sourceFile`,
 * which is the only durable link between a uniqueKey-keyed record and a postId-named file.
 *
 * Usage:
 *   node utils/normalize-backfill.js --dry      # show the queue, write nothing
 *   node utils/normalize-backfill.js            # write data/pending-normalize.json
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const STRAT_DIR = path.join(ROOT, 'strategies');
const PENDING = path.join(ROOT, 'data/pending-normalize.json');

/** Mirrors strategy-normalize.js — a file with one of these is done, not backlog. */
const TERMINAL = new Set(['normalized', 'incompatible-futures', 'incompatible-notrunnable',
                          'failed-final', 'slow-skipped', 'compile-error', 'no-trades']);

const readJson = (f, d) => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch { return d; } };

/**
 * Files that need no further attempt.
 *
 * ⚠ EPOCH-AWARE, and it was not. A terminal row from a SUPERSEDED bench is not a result for the
 * active one — `harness.measurementValid()` is the same rule the normalizer's own done-check uses.
 *
 * What the old version did, measured 2026-09-23: eight strategies were re-measured for epoch 6,
 * crashed when JQ dropped the session, and then became UNREACHABLE. `crash` is retriable
 * everywhere (strategy-normalize, normalize-sync, normalize-daily all exclude it from TERMINAL),
 * but every one of them also carried an epoch-2 `normalized` or `slow-skipped` row — so this
 * function called them done and the backfill never re-offered them. They were not in the pending
 * queue either. Silently stranded, with no path back at any cap.
 *
 * The same bug hid the whole epoch-6 re-measurement set: any strategy with a stale terminal row
 * was excluded from the backlog by construction.
 */
function ledgerStatus(window = 'train') {
  const file = path.join(ROOT, `harness/normalize-${window}.tsv`);
  const harness = require('./harness-config');
  const done = new Set();
  const stale = new Set();
  for (const line of (readFileSafe(file) || '').split('\n').slice(1)) {
    const c = line.split('\t');
    if (!c[0] || !TERMINAL.has(c[3])) continue;
    if (harness.measurementValid(c[13] || '2')) done.add(c[0]);
    else stale.add(c[0]);
  }
  // A row valid at the active epoch wins over any stale one for the same file.
  for (const f of done) stale.delete(f);
  done.staleOnly = stale;
  return done;
}

function readFileSafe(f) { try { return fs.readFileSync(f, 'utf8'); } catch { return null; } }

/** sourceFile -> stable key, from the fetch record. */
function fileToKey() {
  const copied = readJson(path.join(ROOT, 'data/copy-queue.json'), {}).copied || {};
  const out = {};
  for (const [k, c] of Object.entries(copied)) if (c && c.sourceFile) out[c.sourceFile] = k;
  return out;
}

function build({ window = 'train' } = {}) {
  const done = ledgerStatus(window);
  const keyOf = fileToKey();
  const verdicts = readJson(path.join(ROOT, 'screen/verdicts.json'), {}).verdicts || {};

  const queued = [];
  const excluded = [];
  for (const f of fs.readdirSync(STRAT_DIR).filter(f => f.endsWith('.py')).sort()) {
    if (done.has(`strategies/${f}`)) continue;
    const key = keyOf[f] || keyOf[f.replace(/^\d{4}-\d{2}-\d{2}_/, '')] || null;
    const v = key ? verdicts[key] : null;

    // A screener that measured the author's own runtime ("one year takes ~3 hours",
    // "14h backtest") is reporting something the normalizer cannot discover until it has
    // already spent the minutes: its slow-skip cap cancels at 20 min, so each such file
    // burns a third of the daily budget to learn nothing. Queue them last, behind
    // everything that can finish.
    const slow = v && (v.flags || []).some(f => /slow-backtest|backtest-cost|\b\d+\s*h\b/i.test(f));

    if (v && v.S === 0) {
      excluded.push({ file: f, key, reason: 'screened S=0 — harness cannot produce a valid result',
                      flags: v.flags || [] });
      continue;
    }
    // ⚠ Two different kinds of backlog, and they must not be interleaved.
    //   NEW      — never measured on any bench. Every minute buys a number we do not have.
    //   RESTALE  — has a terminal row from a superseded epoch. Re-measuring buys a number we
    //              already have an older version of, and CLAUDE.md's policy is to re-measure
    //              these by screening priority rather than in bulk (the epoch-6 set that
    //              actually CHANGES is 23 of 215, per utils/stockcost-affected.js).
    // Making them one pool would put 121 re-measurements ahead of genuinely unmeasured work.
    const restale = (done.staleOnly || new Set()).has(`strategies/${f}`);
    queued.push({
      file: f,
      key,
      slow,
      restale,
      priority: v ? v.priority : -1,       // unscreened sorts last, never first
      band: v ? v.band : 'unscreened',
      family: v ? v.family : null,
      mechanism: v ? v.mechanism : null,
    });
  }

  // never-measured first, then known-slow last within each tier, then priority, then by name.
  // The restale tier sits behind everything genuinely unmeasured — see the note above.
  queued.sort((a, b) => (a.restale === b.restale ? 0 : a.restale ? 1 : -1)
                     || (a.slow === b.slow ? 0 : a.slow ? 1 : -1)
                     || b.priority - a.priority
                     || a.file.localeCompare(b.file));
  return { queued, excluded };
}

if (require.main === module) {
  const dry = process.argv.includes('--dry');
  const { queued, excluded } = build();
  const scored = queued.filter(q => q.priority >= 0).length;

  const fresh = queued.filter(q => !q.restale).length;
  const restale = queued.length - fresh;
  console.log(`[backfill] ${queued.length} strategies in the backlog: ${fresh} never measured, ` +
              `${restale} measured on a superseded epoch (queued behind the fresh ones)`);
  console.log(`[backfill]   ${scored} carry a screening priority, ${queued.length - scored} unscreened (queued last)`);
  const slowN = queued.filter(q => q.slow).length;
  console.log(`[backfill]   ${excluded.length} EXCLUDED as unrunnable (S=0) — would waste backtest minutes`);
  if (slowN) console.log(`[backfill]   ${slowN} deferred to the tail: screener recorded a multi-hour backtest`);
  for (const e of excluded.slice(0, 8)) console.log(`      ${e.file.slice(0, 54)}  ${e.flags.join(',')}`);

  console.log('[backfill] head of the queue:');
  for (const q of queued.slice(0, 12)) {
    console.log(`   ${String(q.priority).padStart(3)} ${String(q.band).padEnd(10)} ${String(q.family || '').slice(0, 14).padEnd(14)} ${q.file.slice(0, 50)}`);
  }

  if (!dry) {
    // The daily normalizer drains this file and carries unfinished entries over,
    // so writing it here is the whole connection — no downstream change needed.
    const existing = readJson(PENDING, []);
    const merged = [...new Set([...queued.map(q => q.file), ...existing])];
    fs.writeFileSync(PENDING, JSON.stringify(merged, null, 1));
    console.log(`[backfill] wrote ${path.relative(ROOT, PENDING)} (${merged.length} entries, priority order)`);
    console.log('[backfill] drain it with: node utils/strategy-normalize.js --window train');
  } else {
    console.log('[backfill] (dry run — nothing written)');
  }
}

module.exports = { build, TERMINAL };
