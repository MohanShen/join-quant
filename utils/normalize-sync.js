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
 * Stamp every page's `realizabilityFlags:` line from its source.
 *
 * ⚠⚠ The FOURTH leak of the same shape as the three already recorded here: the bookkeeping
 * existed but belonged to no step. `kb-stub.realizabilityLine()` was written, CLAUDE.md recorded
 * why the flag belongs beside the measurement, the 18-of-259 figure was taken from the lint's
 * CLI — and the function was **never called by anything**. Measured 2026-10-22: 0 of 256 pages
 * carried a flag line, so the column a §3 reader is supposed to weigh against a score did not
 * exist on any page.
 *
 * It belongs here for the same reason stub creation and queue pruning do: this is the step that
 * reconciles the knowledge base against the ledger, and it runs at the end of every batch, so the
 * flag cannot drift away from the lint again. A direct normalizer run gets it too.
 *
 * ⚠ It walks EVERY page, not just the ones this batch touched. The flag is a function of the
 * source and the lint's current patterns, so a lint change (the auction window moved twice on
 * 2026-10-22, taking `call-auction-entry` from 2 hits to 20) must propagate to pages measured
 * long ago. A batch-scoped refresh would have left the top four books on the bench unflagged.
 *
 * @returns {{added:string[], updated:string[], removed:string[], unchanged:number, noSource:string[]}}
 */
function syncRealizability({ dry = false } = {}) {
  const kb = require('./kb-stub');
  const out = { added: [], updated: [], removed: [], unchanged: 0, noSource: [] };
  if (!fs.existsSync(PAGES_DIR)) return out;
  for (const f of fs.readdirSync(PAGES_DIR).filter(x => x.endsWith('.md'))) {
    const fp = path.join(PAGES_DIR, f);
    const m = fs.readFileSync(fp, 'utf8').match(/^sourceFile:\s*(\S+)/m);
    if (!m) continue;
    const src = m[1];
    if (!fs.existsSync(path.join(ROOT, src))) { out.noSource.push(f); continue; }
    if (dry) {
      // Decide without writing, using the same two inputs stampRealizability compares.
      const want = kb.realizabilityLine(src);
      const have = (fs.readFileSync(fp, 'utf8').match(/^realizabilityFlags:.*$/m) || [])[0] || null;
      if (want === have) { if (want) out.unchanged++; }
      else if (want && !have) out.added.push(f);
      else if (!want && have) out.removed.push(f);
      else out.updated.push(f);
      continue;
    }
    const r = kb.stampRealizability(fp, src);   // repo-relative — stampRealizability throws on absolute
    if (r === 'added') out.added.push(f);
    else if (r === 'updated') out.updated.push(f);
    else if (r === 'removed') out.removed.push(f);
    else if (r === 'unchanged') out.unchanged++;
    else if (r === 'no-source') out.noSource.push(f);
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
  //
  // ⚠⚠ The lookup was `entry.endsWith('.py') ? 'strategies/'+entry : null`, which could not prune
  // exactly the entries that most needed it. A bare id (`lk_c985985e…`, a re-minted postId that
  // matches no file) yielded `null`, so `r` was null and the entry was KEPT — forever. An entry
  // already carrying the `strategies/` prefix became `strategies/strategies/x.py`, matched
  // nothing, and was also kept. Measured 2026-10-17: 5 immortal entries (1 prefixed, 4 bare ids)
  // inflating the queue that drives stage selection.
  //
  // Normalise to a basename first, then prune on two grounds: the ledger says it is finished, OR
  // it resolves to no file on disk at all. The second is the one that was missing — an entry
  // nothing can ever run is not a queue item, it is noise, and CLAUDE.md's rule says why it
  // accumulated: never key a store on an id.
  const pending = readJson(PENDING, []);
  const onDisk = (() => {
    try { return new Set(fs.readdirSync(path.join(ROOT, 'strategies')).filter(f => f.endsWith('.py'))); }
    catch { return new Set(); }
  })();
  const basenameOf = e => {
    const b = String(e).replace(/^strategies\//, '');
    if (onDisk.has(b)) return b;
    // A legacy id: match the 8-char suffix saveStrategyFile puts in the filename. Same rule as
    // normalize-daily.pidToFile, so the two agree about what an entry means.
    if (!b.endsWith('.py')) return [...onDisk].find(f => f.includes('-' + b.slice(0, 8) + '.py')) || null;
    return null;
  };
  const unresolvable = [];
  const keep = pending.filter(entry => {
    const base = basenameOf(entry);
    if (!base) { unresolvable.push(entry); return false; }
    const r = rows.get(`strategies/${base}`);
    return !(r && TERMINAL.has(r.status));
  });
  const pruned = pending.filter(e => !keep.includes(e));
  if (pruned.length && !dry) fs.writeFileSync(PENDING, JSON.stringify(keep, null, 1));

  // 3. deferred-pool entries the ledger says are FINISHED.
  //
  // ⚠⚠ `dueForRetry()` filters on attempts and cap only, never on whether the strategy has since
  // succeeded. Measured 2026-10-17: 9 of the 10 pooled entries carry `normalized` at epoch 6 —
  // which epoch 8 accepts, so they are done — and the pool re-offered all 10 every single day,
  // the normalizer skipped every one as terminal, and the planner reported them as queue depth.
  // The pool was seeded from the ledger's slow-skipped rows and nothing ever resolved an entry
  // when that strategy later measured cleanly.
  //
  // Only a CAP-related status stays retriable: a bigger cap can change `slow-skipped` or a crash,
  // and cannot change `normalized`, `compile-error`, `no-trades` or `incompatible-*`.
  const RETRIABLE = new Set(['slow-skipped', 'crash']);
  const resolvedDeferred = [];
  try {
    const state = require('./daily-state');
    for (const [file, v] of Object.entries(state.deferred())) {
      const base = basenameOf(file);
      const r = base ? rows.get(`strategies/${base}`) : null;
      const finished = !base || (r && !RETRIABLE.has(r.status));
      if (!finished) continue;
      resolvedDeferred.push({ file, why: !base ? 'resolves to no file' : `ledger says ${r.status}`,
                              attempts: v.attempts });
      if (!dry) state.resolve(file, 'ledger-finished');
    }
  } catch { /* state module unavailable — reported as none */ }

  // ⚠ Runs on EVERY page, after the stubs exist, so a page created a moment ago gets its flag
  // in the same pass. See syncRealizability for why it is not scoped to this batch.
  const realizability = syncRealizability({ dry });

  return { stubbed, pruned, unresolvable, resolvedDeferred, missingSource, realizability };
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
 * A non-zero exit means BLOCKED (regenerating would delete metric rows the ledger
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

module.exports = { sync, refreshFamilies, syncRealizability, ledgerRows, TERMINAL };
