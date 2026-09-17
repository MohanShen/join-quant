/**
 * screen-merge.js — merge screener batch verdicts into screen/verdicts.json and
 * rebuild the fetch queues from them (run-screen skill, steps 3–5).
 *
 * Every verdict is machine-checked against the rubric formula (screen-score.js
 * validateVerdict). A verdict whose priority or band disagrees with its own four axes
 * is REJECTED, not silently corrected — it is a screener bug and must be visible.
 *
 * Queue effect: the queue builders in strategy-discover.js read screen/verdicts.json, so
 * the ordering survives every later discovery run instead of being wiped by it:
 *   fetch-now, then fetch (by priority)  ->  unscreened (old popularity order)
 *   hold and drop are kept out of the queue; drop is never re-screened.
 *
 * Usage:
 *   node utils/screen-merge.js                     # merge screen/batches/verdicts-*.json
 *   node utils/screen-merge.js a.json b.json       # explicit files
 */

const fs = require('fs');
const path = require('path');
const { validateVerdict } = require('./screen-score');

const ROOT = path.resolve(__dirname, '..');
const VERDICTS = path.join(ROOT, 'screen/verdicts.json');
const BATCH_DIR = path.join(ROOT, 'screen/batches');
const RUBRIC = 'screen/screen.md';

const readJson = (f, d) => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch { return d; } };

function rubricEpoch() {
  const t = fs.readFileSync(path.join(ROOT, RUBRIC), 'utf8');
  return parseInt((t.match(/- \*\*epoch\*\*:\s*(\d+)/) || [])[1] || '0', 10);
}

function merge(files) {
  const epoch = rubricEpoch();
  const store = readJson(VERDICTS, { rubric: `${RUBRIC} epoch ${epoch}`, verdicts: {} });
  if (!store.verdicts) store.verdicts = {};

  let added = 0;
  const rejected = [];
  for (const f of files) {
    const batch = readJson(f, null);
    if (!batch) { rejected.push(`${path.basename(f)}: unreadable`); continue; }
    for (const [ref, v] of Object.entries(batch)) {
      const errs = validateVerdict({ ...v, key: v.key || ref });
      if (errs.length) { rejected.push(`${ref}: ${errs.join('; ')}`); continue; }
      store.verdicts[ref] = { ...v, key: ref, epoch, screenedAt: new Date().toISOString(),
                              batch: path.basename(f) };
      added++;
    }
  }
  store.rubric = `${RUBRIC} epoch ${epoch}`;
  store.updatedAt = new Date().toISOString();
  fs.writeFileSync(VERDICTS, JSON.stringify(store, null, 1));
  return { store, added, rejected };
}

/** Rubric §7 guard: >50% of the fetch-now band in one family means M is not working. */
function concentration(verdicts) {
  const top = Object.values(verdicts).filter(v => v.band === 'fetch-now');
  const byFam = {};
  for (const v of top) byFam[v.family] = (byFam[v.family] || 0) + 1;
  const worst = Object.entries(byFam).sort((a, b) => b[1] - a[1])[0];
  return {
    fetchNow: top.length,
    byFamily: byFam,
    worst,
    tripped: Boolean(worst && top.length >= 4 && worst[1] / top.length > 0.5),
  };
}

if (require.main === module) {
  const args = process.argv.slice(2);
  const files = args.length ? args
    : fs.readdirSync(BATCH_DIR).filter(f => /^verdicts-.*\.json$/.test(f)).map(f => path.join(BATCH_DIR, f));

  const { store, added, rejected } = merge(files);
  const all = Object.values(store.verdicts);
  const hist = {};
  for (const v of all) hist[v.band] = (hist[v.band] || 0) + 1;

  console.log(`[merge] ${files.length} batch file(s): +${added} verdicts, ${rejected.length} rejected; ` +
              `total ${all.length} in ${path.relative(ROOT, VERDICTS)}`);
  for (const r of rejected) console.log(`  REJECTED ${r}`);
  console.log(`[merge] bands: ${['fetch-now', 'fetch', 'hold', 'drop'].map(b => `${b}=${hist[b] || 0}`).join('  ')}`);

  const c = concentration(store.verdicts);
  console.log(`[merge] fetch-now by family: ${JSON.stringify(c.byFamily)}`);
  console.log(c.tripped
    ? `[merge] ⚠ CONCENTRATION GUARD TRIPPED: ${c.worst[0]} is ${c.worst[1]}/${c.fetchNow} of fetch-now (rubric §7)`
    : '[merge] concentration guard: ok');

  // Rebuild both queues so the new ordering takes effect immediately.
  const discover = require('./strategy-discover');
  discover.buildCopyQueue();
  discover.buildResourceQueue();
}

module.exports = { merge, concentration };
