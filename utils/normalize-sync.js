/**
 * normalize-sync.js — the bookkeeping that OWNS a normalization result.
 *
 * Two leaks of the same shape motivated this (docs/consolidation-plan.md §6 piece 1):
 * both side effects of "a strategy was measured" lived inside ONE caller,
 * `normalize-daily.js`, instead of beside the ledger write. Run the normalizer any other
 * way — as the 2026-09-18 priority backfill did — and both silently did not happen:
 *
 *   1. no wiki page was created, so 3 of 122 measured strategies had a ledger row and
 *      nothing in `wiki/strategies/`;
 *   2. `data/pending-normalize.json` was never pruned, so it listed 65 entries when only
 *      54 were still unmeasured.
 *
 * Both are now derived from the ledger rather than from what one caller happens to remember,
 * so every entry point converges on the same truth and running sync twice is a no-op.
 *
 * Usage:
 *   node utils/normalize-sync.js            # reconcile pages + queue against the ledger
 *   node utils/normalize-sync.js --dry
 */

const fs = require('fs');
const path = require('path');
const { createStub, regenConceptTables } = require('./kb-stub');

const ROOT = path.resolve(__dirname, '..');
const STRAT_DIR = path.join(ROOT, 'strategies');
const PAGES_DIR = path.join(ROOT, 'wiki/strategies');
const PENDING = path.join(ROOT, 'data/pending-normalize.json');

/** Mirrors strategy-normalize.js: a file with one of these needs no further attempt. */
const TERMINAL = new Set(['normalized', 'incompatible-futures', 'incompatible-notrunnable',
                          'failed-final', 'slow-skipped', 'compile-error', 'no-trades']);

const readJson = (f, d) => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch { return d; } };

/** Every ledger row, newest-wins per sourceFile. */
function ledgerRows(window = 'train') {
  const file = path.join(ROOT, `harness/normalize-${window}.tsv`);
  let text;
  try { text = fs.readFileSync(file, 'utf8'); } catch { return new Map(); }
  const rows = new Map();
  for (const line of text.split('\n').slice(1)) {
    const c = line.split('\t');
    if (!c[0]) continue;
    rows.set(c[0], { file: c[0], status: c[3], annual: c[8], sharpe: c[9], maxdd: c[10],
                     objective: c[11], gate: c[12], epoch: c[13] || null });
  }
  return rows;
}

/** sourceFile values already covered by a wiki page. */
function pagedSourceFiles() {
  const out = new Set();
  if (!fs.existsSync(PAGES_DIR)) return out;
  for (const f of fs.readdirSync(PAGES_DIR).filter(f => f.endsWith('.md'))) {
    const m = fs.readFileSync(path.join(PAGES_DIR, f), 'utf8').match(/^sourceFile:\s*(\S+)/m);
    if (m) out.add(m[1]);
  }
  return out;
}

/**
 * Reconcile the knowledge base and the pending queue against the ledger.
 * @returns {{stubbed:string[], pruned:string[], missingSource:string[]}}
 */
function sync({ window = 'train', dry = false } = {}) {
  const rows = ledgerRows(window);
  const paged = pagedSourceFiles();

  // 1. a measured strategy with no page — the leak that lost 3 results
  const stubbed = [];
  const missingSource = [];
  for (const [srcFile, r] of rows) {
    if (r.status !== 'normalized' || paged.has(srcFile)) continue;
    const abs = path.join(ROOT, srcFile);
    if (!fs.existsSync(abs)) { missingSource.push(srcFile); continue; }
    if (!dry) {
      createStub(srcFile, fs.readFileSync(abs, 'utf8'), {
        annual: parseFloat(r.annual), sharpe: r.sharpe, maxdd: parseFloat(r.maxdd),
        obj: r.objective, gate: r.gate, epoch: r.epoch,
      });
    }
    stubbed.push(srcFile);
  }
  if (stubbed.length && !dry) regenConceptTables();

  // 2. queue entries the ledger says are finished — the leak that left 11 stale entries
  const pending = readJson(PENDING, []);
  const keep = pending.filter(entry => {
    const key = entry.endsWith('.py') ? `strategies/${entry}` : null;
    const r = key ? rows.get(key) : null;
    return !(r && TERMINAL.has(r.status));
  });
  const pruned = pending.filter(e => !keep.includes(e));
  if (pruned.length && !dry) fs.writeFileSync(PENDING, JSON.stringify(keep, null, 1));

  return { stubbed, pruned, missingSource };
}

/**
 * Refresh the family pages' generated half (§3 横评, memberCount, bestVariant) after new
 * members have been stubbed.
 *
 * This was the third leak of the same shape as the two above: the bookkeeping existed but
 * belonged to no step, so §3 only moved when a human happened to run the builder. A member
 * could be measured, paged and still missing from its family's table indefinitely.
 *
 * ⚠ Spawned, not required. `wiki-family-build.js` is top-level script code with no
 * `module.exports` and no `require.main` guard — requiring it would execute it as a side
 * effect and let its `process.exit()` take this process down with it. That is the same trap
 * that once made a bare `require()` of strategy-normalize.js spend 42 backtest minutes.
 *
 * A non-zero exit means BLOCKED (regenerating would delete metric rows the gitignored ledger
 * no longer has) or stale — informational here, never a failure of the sync. It is reported
 * and deliberately not escalated, and `--force` is never passed.
 */
function refreshFamilies({ dry = false } = {}) {
  if (dry) return { ran: false, blocked: false, out: '(dry — family build not run)' };
  const { spawnSync } = require('child_process');
  const r = spawnSync(process.execPath, [path.join(__dirname, 'wiki-family-build.js')],
                      { encoding: 'utf8', cwd: ROOT });
  const out = `${r.stdout || ''}${r.stderr || ''}`.trim();
  return { ran: true, blocked: r.status !== 0, out };
}

if (require.main === module) {
  const dry = process.argv.includes('--dry');
  const { stubbed, pruned, missingSource } = sync({ dry });
  console.log(`[sync] wiki pages created for measured strategies : ${stubbed.length}`);
  stubbed.slice(0, 8).forEach(f => console.log(`   + ${f.replace('strategies/', '').slice(0, 58)}`));
  console.log(`[sync] finished entries pruned from the queue     : ${pruned.length}`);
  if (missingSource.length) {
    console.log(`[sync] ⚠ ledger rows whose .py is gone            : ${missingSource.length}`);
    missingSource.slice(0, 5).forEach(f => console.log(`   ? ${f}`));
  }
  // Only worth the spawn when something actually changed.
  if (stubbed.length) {
    const fb = refreshFamilies({ dry });
    if (fb.ran) {
      const tail = fb.out.split('\n').filter(l => /done:|BLOCKED|blocked/.test(l)).slice(-4);
      console.log(`[sync] family pages refreshed${fb.blocked ? ' (some BLOCKED — see below)' : ''}`);
      tail.forEach(l => console.log(`   ${l.trim().slice(0, 100)}`));
      if (fb.blocked) {
        console.log('   ⚠ BLOCKED means the ledger is incomplete, not the pages. Never --force.');
      }
    }
  }
  if (dry) console.log('[sync] (dry run — nothing written)');
}

module.exports = { sync, refreshFamilies, ledgerRows, TERMINAL };
