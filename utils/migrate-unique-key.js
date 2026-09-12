/**
 * migrate-unique-key.js — re-key the discovery stores from `postId` to the
 * stable post identity, and collapse the duplicates postId-keying created.
 *
 * Background
 * ----------
 * JoinQuant regenerates `postId` and `backtestId` on every request: the same
 * post comes back under new ids each time listV2 is called, and the old ids
 * still dereference, so nothing ever failed loudly. Keying the stores on
 * `postId` meant:
 *
 *   - `data/discovered.json` re-added the same post on every crawl
 *     (549 entries for 492 distinct titles = 10% redundant), and
 *   - `data/copy-queue.json`'s `copied` map could never match again, so already
 *     cloned strategies were re-queued forever. Only the SHA256 content hash in
 *     strategy-fetch.js was catching that, one wasted fetch at a time.
 *
 * `uniqueKey` is stable. Rows written before it was captured get a deterministic
 * fallback digest of title+author (see postKey()), which also merges the
 * historical duplicates.
 *
 * The migration is idempotent: running it twice changes nothing the second time.
 * Every file is backed up next to itself as <name>.pre-uniquekey.bak.
 *
 * Usage:
 *   node utils/migrate-unique-key.js --dry     # report only, write nothing
 *   node utils/migrate-unique-key.js           # migrate in place (with backups)
 */

const fs = require('fs');
const path = require('path');
const { postKey } = require('./strategy-discover');

const DATA_DIR = path.join(__dirname, '..', 'data');
const F = {
  discovered: path.join(DATA_DIR, 'discovered.json'),
  copyQueue: path.join(DATA_DIR, 'copy-queue.json'),
  resources: path.join(DATA_DIR, 'resources.json'),
  resourceQueue: path.join(DATA_DIR, 'resource-queue.json'),
};

const readJson = (f, d) => {
  if (!fs.existsSync(f)) return d;
  try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch { return d; }
};

function backupAndWrite(file, obj, dry) {
  if (dry) return;
  if (fs.existsSync(file)) {
    const bak = file.replace(/\.json$/, '.pre-uniquekey.bak');
    if (!fs.existsSync(bak)) fs.copyFileSync(file, bak);
  }
  fs.writeFileSync(file, JSON.stringify(obj, null, 2));
}

/** Composite score, matching strategy-discover. */
const scoreOf = s => (s.likes || 0) + (s.clones || 0) * 0.5;

/**
 * Collapse a postId-keyed map into a stable-key map, keeping the best row per
 * key. "Best" = highest composite score, tie-broken by clone count, so the
 * richest snapshot of a post survives the merge.
 */
function rekeyMap(map, pickBetter) {
  const out = {};
  let collapsed = 0;
  for (const row of Object.values(map || {})) {
    const k = postKey(row);
    if (!out[k]) { out[k] = row; continue; }
    collapsed++;
    if (pickBetter(row, out[k])) out[k] = row;
  }
  return { out, collapsed };
}

function migrate({ dry = false } = {}) {
  const report = [];

  // ── discovered.json ────────────────────────────────────────────────────────
  const store = readJson(F.discovered, { strategies: {}, scrapedPostIds: [] });
  const before = Object.keys(store.strategies || {}).length;
  const { out: strategies, collapsed } = rekeyMap(
    store.strategies,
    (a, b) => scoreOf(a) > scoreOf(b) || (scoreOf(a) === scoreOf(b) && (a.clones || 0) > (b.clones || 0))
  );
  store.strategies = strategies;
  store.scrapedPostIds = Object.keys(strategies);   // now stable keys, not postIds
  store.migratedAt = new Date().toISOString();
  report.push(`discovered.json   ${before} -> ${Object.keys(strategies).length} (merged ${collapsed})`);

  // ── resources.json ─────────────────────────────────────────────────────────
  const res = readJson(F.resources, { resources: {} });
  const rBefore = Object.keys(res.resources || {}).length;
  const { out: resources, collapsed: rCollapsed } = rekeyMap(
    res.resources,
    (a, b) => (a.notebookClones || 0) + (a.fileDownloads || 0) > (b.notebookClones || 0) + (b.fileDownloads || 0)
  );
  res.resources = resources;
  res.migratedAt = new Date().toISOString();
  report.push(`resources.json    ${rBefore} -> ${Object.keys(resources).length} (merged ${rCollapsed})`);

  // ── copy-queue.json ────────────────────────────────────────────────────────
  // The `copied` map is the one that actually mattered: its postId keys can
  // never match a fresh crawl. Re-key it so previously fetched strategies stay
  // suppressed. Entries whose rows we no longer hold keep their old key — they
  // are harmless, just inert.
  const cq = readJson(F.copyQueue, { queue: [], copied: {} });
  const byPostId = {};
  for (const row of Object.values(store.strategies)) if (row.postId) byPostId[row.postId] = row;

  const copied = {};
  let remapped = 0;
  let orphaned = 0;
  for (const [oldKey, val] of Object.entries(cq.copied || {})) {
    const row = byPostId[oldKey];
    if (row) { copied[postKey(row)] = { ...val, migratedFromPostId: oldKey }; remapped++; }
    else { copied[oldKey] = val; orphaned++; }
  }
  cq.copied = copied;
  // Queue rows get their stable key stamped so markFetched can match them.
  cq.queue = (cq.queue || []).map(q => ({ ...q, key: q.key || postKey(q) }));
  // Drop anything already copied under its new key.
  const qBefore = cq.queue.length;
  cq.queue = cq.queue.filter(q => !copied[q.key]);
  cq.migratedAt = new Date().toISOString();
  report.push(`copy-queue.json   copied: ${remapped} remapped, ${orphaned} left as-is; ` +
              `queue ${qBefore} -> ${cq.queue.length}`);

  // ── resource-queue.json ────────────────────────────────────────────────────
  const rq = readJson(F.resourceQueue, { queue: [], ingested: {} });
  const rqBefore = (rq.queue || []).length;
  const seen = new Set();
  rq.queue = (rq.queue || [])
    .map(r => ({ ...r, key: r.key || postKey(r) }))
    .filter(r => !(rq.ingested || {})[r.key])
    .filter(r => (seen.has(r.key) ? false : (seen.add(r.key), true)))
    .map((r, i) => ({ ...r, rank: i + 1 }));
  rq.migratedAt = new Date().toISOString();
  report.push(`resource-queue.json queue ${rqBefore} -> ${rq.queue.length}`);

  if (!dry) {
    backupAndWrite(F.discovered, store, dry);
    backupAndWrite(F.resources, res, dry);
    backupAndWrite(F.copyQueue, cq, dry);
    backupAndWrite(F.resourceQueue, rq, dry);
  }
  return report;
}

if (require.main === module) {
  const dry = process.argv.includes('--dry');
  console.log(`=== uniqueKey migration${dry ? ' (dry run — nothing written)' : ''} ===`);
  migrate({ dry }).forEach(l => console.log('  ' + l));
  console.log(dry ? '  (re-run without --dry to apply)' : '  done — backups at data/*.pre-uniquekey.bak');
}

module.exports = { migrate, rekeyMap };
