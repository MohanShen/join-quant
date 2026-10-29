/**
 * postedat-backfill.js — fill the missing `postedAt` on discovery records.
 *
 * ## Why this exists
 *
 * `postedAt` is the post's OWN publication date (listV2's `addTime`), and it is the only thing
 * that can say whether a harness window is out-of-sample FOR THE AUTHOR. The discoverer maps it
 * (`postedAt: item.addTime`), but it was added after the first crawls, so the pre-`uniqueKey`
 * records never got one.
 *
 * Measured 2026-10-27: 826 of 1239 strategy records carry a real `uniqueKey` and ALL of them have
 * `postedAt`; the other 413 are legacy-keyed (`lk_<sha1(title|author)>`) and only 59 do. The 354
 * without it include EVERY book this repo has actually measured, promoted or validated — so the
 * question "is TRAIN 2024 / VAL 2025 inside the author's own sample?" was unanswerable for exactly
 * the books where it matters.
 *
 * ⚠ Why it matters concretely: the library's known post dates run 2015-10-13 .. 2026-09-15 with a
 * MEDIAN of 2019-08-02, so most books predate the windows and their TRAIN/VAL numbers are honest
 * out-of-sample readings. But a book published in 2026 has TRAIN 2024 and VAL 2025 entirely inside
 * what its author could see, and then only the post-publication part of the 2026 reserve is clean.
 * 五福闹新春's OOS curve splits exactly that way (+47.14% before its source date, −29.56% after).
 * Guessing which case a book is in is not acceptable — this fetches the fact.
 *
 * ## Keying
 *
 * Records are stored under `postKey(item)`: the real `uniqueKey` when the crawl supplied one, else
 * `legacyKey(item)` = `lk_` + sha1(title|author). A backfill therefore has to try BOTH, because
 * the target rows are precisely the ones stored under the legacy form. Both helpers are imported
 * from `strategy-discover` rather than restated — the key rule has one owner, like `ledger.COLS`.
 *
 * ⚠ Never keyed on `postId`/`backtestId`: JoinQuant re-mints those on every request.
 *
 * ## Cost
 *
 * HTTP only, through `jq-http` (so inside the CDP Chrome, right region, logged-in cookies). No
 * backtest minutes. One request per page.
 *
 *   node utils/postedat-backfill.js --dry
 *   node utils/postedat-backfill.js --pages 60
 *   node utils/postedat-backfill.js --pages 40 --cates 0,3,14
 */

const fs = require('fs');
const path = require('path');
const jq = require('./jq-http');
const sd = require('./strategy-discover');

const ROOT = path.resolve(__dirname, '..');
const STORE = () => process.env.JQ_DISCOVERED || path.join(ROOT, 'data/discovered.json');

/** Normalise listV2's "YYYY-MM-DD HH:MM:SS" to a date, keeping the raw value. */
function dayOf(v) {
  const m = String(v || '').match(/^(\d{4}-\d{2}-\d{2})/);
  return m ? m[1] : null;
}

async function backfill({ pages = 40, cates = [0], limit = 200, dry = false, log = console.log } = {}) {
  const store = JSON.parse(fs.readFileSync(STORE(), 'utf8'));
  const S = store.strategies || {};
  const keys = Object.keys(S);

  // Targets: records with no postedAt. Keep the key so the fill is a direct assignment.
  const missing = new Set(keys.filter(k => S[k] && !S[k].postedAt));
  const before = keys.length - missing.size;
  log(`[pa] ${keys.length} strategy records | ${before} already dated | ${missing.size} missing`);
  if (!missing.size) { log('[pa] nothing to do'); return { filled: 0, missing: 0, pagesRead: 0 }; }

  let filled = 0, pagesRead = 0, seen = 0;
  outer:
  for (const cate of cates) {
    for (let page = 1; page <= pages; page++) {
      let p;
      try {
        p = await sd.fetchListPage({ cate, type: 'isNew', limit, page });
      } catch (e) {
        // Loud, not silent: a geo-block or a session drop must not read as "no more pages".
        log(`[pa] cate=${cate} page=${page} FAILED: ${e.message.slice(0, 90)}`);
        break;
      }
      pagesRead++;
      const rows = [...(p.strategies || []), ...(p.resources || [])];
      if (!rows.length) { log(`[pa] cate=${cate} page=${page} empty — end of this slice`); break; }
      seen += rows.length;
      for (const r of rows) {
        if (!r.postedAt) continue;
        // Try BOTH identities: the row may be stored under its uniqueKey or under the legacy hash.
        for (const k of [sd.postKey(r), sd.legacyKey(r)]) {
          if (!missing.has(k)) continue;
          S[k].postedAt = r.postedAt;          // fill only; an existing value is never touched
          missing.delete(k);
          filled++;
        }
      }
      if (filled && page % 10 === 0) {
        log(`[pa] cate=${cate} page=${page}: filled ${filled}, ${missing.size} still missing`);
      }
      if (!missing.size) { log('[pa] every target filled — stopping early'); break outer; }
    }
  }

  if (!dry && filled) {
    fs.writeFileSync(STORE(), JSON.stringify(store, null, 2));
  }
  log(`[pa] ${dry ? '[dry] would fill' : 'filled'} ${filled} | ${missing.size} still missing | ` +
      `${pagesRead} page(s), ${seen} row(s) read`);
  return { filled, missing: missing.size, pagesRead, seen };
}

/** Date-coverage summary over the whole store, for reporting. */
function coverage() {
  const S = JSON.parse(fs.readFileSync(STORE(), 'utf8')).strategies || {};
  const dates = Object.values(S).map(r => r && dayOf(r.postedAt)).filter(Boolean).sort();
  const n = Object.keys(S).length;
  const q = f => dates[Math.floor((dates.length - 1) * f)];
  return { records: n, dated: dates.length, undated: n - dates.length,
           min: dates[0], median: q(0.5), max: dates[dates.length - 1],
           pre2024: dates.filter(d => d < '2024-01-01').length,
           pre2025: dates.filter(d => d < '2025-01-01').length,
           pre2026: dates.filter(d => d < '2026-01-01').length };
}

module.exports = { backfill, coverage, dayOf };

if (require.main === module) {
  const argv = process.argv.slice(2);
  const arg = (n, d) => { const i = argv.indexOf(n); return i >= 0 ? argv[i + 1] : d; };
  const dry = argv.includes('--dry');
  const pages = parseInt(arg('--pages', '40'), 10);
  const cates = String(arg('--cates', '0')).split(',').map(x => parseInt(x, 10));

  backfill({ pages, cates, dry })
    .then(() => {
      const c = coverage();
      console.log(`[pa] coverage: ${c.dated}/${c.records} dated (${c.undated} undated)`);
      if (c.dated) {
        console.log(`[pa] post dates ${c.min} .. ${c.max}, median ${c.median}`);
        console.log(`[pa] pre-2024 ${c.pre2024} | pre-2025 ${c.pre2025} | pre-2026 ${c.pre2026}`);
      }
    })
    .catch(e => { console.error('[pa] ' + e.stack); process.exitCode = 1; })
    // ⚠ Required: jq-http holds a Playwright CDP connection, and an entry point that opens it must
    // close it or the open socket keeps Node's event loop alive to the stage timeout. Use
    // process.exitCode, never process.exit(), or this finally is skipped.
    .finally(() => jq.close());
}
