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
 * ⚠ NEWEST ROW WINS. The ledger is append-only, so a file's last row is its current state — and
 * matching on "has ANY terminal row" is what stranded eight strategies on 2026-09-23. Each of them
 * read `slow-skipped@e2 , normalized@e2 , crash@e6`: an old terminal row plus a NEWER failed
 * attempt. Keying on the old row called them done, so the backlog never re-offered them and the
 * pending queue no longer held them. `crash` is retriable everywhere else; only this function
 * disagreed.
 *
 * ⚠ Epoch is deliberately NOT a queueing trigger. A first attempt at this gated on
 * `measurementValid()`, which is correct for "is this number comparable to the active bench" and
 * wrong for "does this need normalizing": it turned 141 already-measured strategies into backlog
 * and took the queue from 53 to 175. Those have been through the family pipeline and have numbers;
 * re-measuring them in bulk is not what the epoch rule asks for. CLAUDE.md's policy is to
 * re-measure by screening priority, and only 23 of 215 actually change under epoch 6
 * (`utils/stockcost-affected.js`). A deliberate re-measurement is that tool's job, not the
 * backlog's.
 */
function ledgerStatus(window = 'train') {
  const file = path.join(ROOT, `harness/normalize-${window}.tsv`);
  const last = new Map();
  for (const line of (readFileSafe(file) || '').split('\n').slice(1)) {
    const c = line.split('\t');
    if (c[0] && c[3]) last.set(c[0], c[3]);   // append-only: the final write wins
  }
  const done = new Set();
  for (const [f, status] of last) if (TERMINAL.has(status)) done.add(f);
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
    queued.push({
      file: f,
      key,
      slow,
      priority: v ? v.priority : -1,       // unscreened sorts last, never first
      band: v ? v.band : 'unscreened',
      family: v ? v.family : null,
      mechanism: v ? v.mechanism : null,
    });
  }

  // known-slow last, then priority, then stable by name
  queued.sort((a, b) => (a.slow === b.slow ? 0 : a.slow ? 1 : -1)
                     || b.priority - a.priority
                     || a.file.localeCompare(b.file));
  return { queued, excluded };
}

if (require.main === module) {
  const dry = process.argv.includes('--dry');
  const { queued, excluded } = build();
  const scored = queued.filter(q => q.priority >= 0).length;

  console.log(`[backfill] ${queued.length} strategies need normalizing ` +
              `(never measured, or whose newest attempt failed)`);
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
