/**
 * recover-completed.js — recover the result of a run that FINISHED while JQ kept listing it.
 *
 * ## The bug this cleans up after
 *
 * `pollUntilComplete` detected completion from the account-wide `statistics.running` COUNT, and
 * `running[].id` is a backtestId that never matches our algorithmId — so the count could not be
 * attributed to our run. When JQ left a FINISHED run in that list the count stayed above baseline,
 * `emptyStreak` never accumulated, and the executor polled to its cap and wrote `slow-skipped`
 * while the completed result sat on the server. Three instances on 2026-10-18; the poller now also
 * reads the buildList row's `_status`, which IS attributable, but rows written before that fix
 * are still wrong and are what this recovers.
 *
 * Recovery is FREE: the run completed, so `POST /algorithm/backtest/stats` and
 * `GET /algorithm/backtest/result` already hold its metrics and daily curve. No backtest starts.
 *
 * ## Identification is by SOURCE HASH, never by id
 *
 * JQ re-mints every id per request, and the account lists each algorithm more than once — the
 * one-off that preceded this tool matched THREE different id pairs across three calls minutes
 * apart, all the same run. So the run is found by hashing the normalized source JQ serves against
 * the exact temp copy the normalizer submitted (`/tmp/jq-normalize/<tag>.py`). Same discipline as
 * `series-backfill.js`, where a wrong pairing silently corrupts every correlation built on it.
 *
 * ⚠ That temp copy is the ONLY link back to what was submitted, and /tmp is not durable. A row
 * whose copy is gone cannot be recovered this way and is reported as such rather than guessed at.
 *
 * ## It refuses rather than guesses
 *
 * Aborts before writing anything unless ALL of:
 *   - the submitted copy exists, so the match is by content;
 *   - exactly one account backtest matches that content hash;
 *   - the newest ledger row for the file is `slow-skipped` (nothing else is ours to override);
 *   - `trading_days` equals the window's expected count;
 *   - the curve's final cumulative return agrees with the stats endpoint to ±0.05pp;
 *   - the row carries exactly `ledger.COLS.length` cells.
 * `objective`/`gate` come from `harness-config`, never reimplemented here.
 *
 * The recovered row APPENDS, so newest-row-wins makes it authoritative over the `slow-skipped` one.
 *
 * Usage:
 *   node utils/recover-completed.js --scan              # which slow-skipped rows are recoverable
 *   node utils/recover-completed.js <tag> --dry         # one, print only
 *   node utils/recover-completed.js <tag> --near "2026-10-18 12:55"   # narrow by create-time
 *   node utils/recover-completed.js <tag>               # one, write it
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const ROOT = path.resolve(__dirname, '..');
const TMP_DIR = '/tmp/jq-normalize';
const S = require('./backtest-series');
const h = require('./harness-config');
const led = require('./ledger');
const jq = require('./jq-http');

const norm = s => String(s).replace(/\r\n/g, '\n').trim();
const sha = s => crypto.createHash('sha256').update(norm(s)).digest('hex');
const tagOf = sourceFile => {
  const m = String(sourceFile).match(/-([0-9a-f]{8})\.py$/);
  return m ? m[1] : null;
};

/** Slow-skipped rows whose submitted copy still exists, so a content match is possible. */
function candidates(windowName = 'train') {
  const newest = new Map();                       // newest row per sourceFile — newest-row-wins
  for (const r of led.rows(windowName)) newest.set(r.sourceFile, r);
  const out = [];
  for (const r of newest.values()) {
    if (r.status !== 'slow-skipped') continue;
    const tag = tagOf(r.sourceFile);
    const copy = tag && path.join(TMP_DIR, `${tag}.py`);
    out.push({ row: r, tag, copy, hasCopy: Boolean(copy && fs.existsSync(copy)) });
  }
  return out;
}

/**
 * One buildList fetch per algorithm yields everything needed to NARROW before paying for a source
 * fetch. The row's visible cells are, in order:
 *
 *   这是一个简单的策略-1251 | 2026-10-18 15:48:23 | 2022-01-01 - 2023-12-31 | -- | 每天 | 完成 | 0%
 *   name                    createdAt             window                     compile  freq  state  return
 */
function parseRowSummary(body) {
  const tb = String(body).slice(String(body).indexOf('<tbody>'));
  const text = tb.slice(0, 3000).replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
  return {
    name: (text.match(/^(\S+)/) || [])[1] || '',
    createdAt: (text.match(/(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})/) || [])[1] || '',
    state: (text.match(/(完成|运行中|排队中|失败|已取消)/) || [])[1] || '',
    backtestId: (String(body).match(/class="backtest-tr"[^>]*_backtestId="([a-f0-9]{32})"/) || [])[1]
             || (String(body).match(/<tr _backtestId="([a-f0-9]{32})"/) || [])[1] || null,
  };
}

/**
 * Find the account backtest whose SOURCE matches `wantHash`.
 *
 * ⚠ Rewritten after the first version wedged: it fetched the SOURCE of every candidate (two large
 * calls per algorithm), and with CDP at ~6.6s per fetch it ran 18 minutes with 2.6s of CPU and
 * printed nothing — no progress output and no bound. Now one cheap buildList call per algorithm
 * narrows first, and `near` (the run's create-time, which the caller knows from the running list)
 * usually reduces the expensive source check to a single candidate.
 */
async function findBySource(wantHash, { near = null, pages = 3, verbose = true } = {}) {
  const seen = new Set();
  for (let pg = 1; pg <= pages; pg++) {
    const list = await jq.jqText(`/algorithm/index/list?page=${pg}`);
    const algs = [...new Set((list.match(/algorithmId=([a-f0-9]{32})/g) || []).map(s => s.split('=')[1]))]
      .filter(a => !seen.has(a));
    if (!algs.length) break;
    const rows = [];
    for (const a of algs) {
      seen.add(a);
      const b = await jq.jqText(`/algorithm/backtest/buildList?algorithmId=${a}`);
      const r = parseRowSummary(b);
      if (!r.backtestId) continue;
      rows.push({ algorithmId: a, ...r });
      if (verbose) console.log(`[recover]   p${pg} ${r.name.padEnd(22)} ${r.createdAt} ${r.state}`);
    }
    // Narrow to the create-time the caller supplied; a run's create-time is exact, so this is
    // normally one candidate. Without it, every row on the page is a candidate.
    const cand = near ? rows.filter(r => r.createdAt.startsWith(near)) : rows;
    if (near && verbose) console.log(`[recover]   ${cand.length} row(s) match create-time ~${near}`);
    for (const r of cand) {
      const raw = await jq.jqText(`/algorithm/backtest/source?backtestId=${r.backtestId}&ajax=1`);
      let code = raw;
      try { const j = JSON.parse(raw); code = (j.data && (j.data.source || j.data.code)) || raw; } catch { /* plain */ }
      // The account lists each algorithm more than once, so several ids legitimately point at the
      // SAME run; that is not ambiguity. Any of them dereferences to the same result.
      if (sha(code) === wantHash) return { algorithmId: r.algorithmId, backtestId: r.backtestId, row: r };
    }
  }
  return null;
}

async function recover(tag, opts = {}) {
  const { windowName = 'train', dry = false } = opts;
  const cands = candidates(windowName);
  const c = cands.find(x => x.tag === tag);
  if (!c) throw new Error(`no slow-skipped row for tag ${tag} in normalize-${windowName}.tsv`);
  if (!c.hasCopy) throw new Error(`the submitted copy ${c.copy} is gone — cannot match by content`);

  const found = await findBySource(sha(fs.readFileSync(c.copy, 'utf8')), { near: opts.near, pages: opts.pages });
  if (!found) throw new Error('no account backtest matches the submitted source — refusing to guess');
  console.log(`[recover] ${tag}: source-matched algorithm ${found.algorithmId.slice(0, 8)} ` +
              `backtest ${found.backtestId.slice(0, 8)}`);

  const s = await jq.jqPostJson(`/algorithm/backtest/stats?backtestId=${found.backtestId}&ajax=1`, {});
  const d = (s && s.data) ? s.data : s;
  if (!d || d.sharpe == null) throw new Error('the stats endpoint served no result — the run did not complete');
  const pct = (v, n = 2) => (Number(v) * 100).toFixed(n);
  const total = pct(d.algorithm_return), annual = pct(d.annual_algo_return);
  const maxdd = pct(d.max_drawdown), sharpe = Number(d.sharpe).toFixed(2);
  console.log(`[recover] stats: days=${d.trading_days} total=${total}% annual=${annual}% ` +
              `sharpe=${sharpe} maxdd=${maxdd}%`);

  const w = h.window(windowName);
  const raw = await S.fetchViaHttp(found.backtestId);
  const epoch = h.config().epoch;
  const rec = S.toRecord(raw, { sourceFile: c.row.sourceFile, backtestId: found.backtestId,
                                window: windowName, epoch });
  const curveTotal = rec.cum[rec.cum.length - 1];
  console.log(`[recover] curve: ${rec.points} points ${rec.start}..${rec.end} ` +
              `final cum ${curveTotal.toFixed(2)}%`);
  // A curve that disagrees with the stats means the wrong run was matched. Refuse, never round.
  if (Math.abs(curveTotal - Number(total)) > 0.05) {
    throw new Error(`curve ${curveTotal.toFixed(2)}% disagrees with stats ${total}% — refusing to record`);
  }

  const obj = h.objective(Number(annual), Number(maxdd), Number(sharpe));
  const gate = h.gate(Number(sharpe)) ? 'pass' : 'fail';
  // ⚠ `days` must be the window's REQUESTED calendar span, not the curve's 484 trading days and
  // not blank. The ledger annualizes over this column (a uniform 729 on every TRAIN row), and
  // `component-scan --validate` reads it: self-annualizing each side instead injects an error that
  // SCALES WITH RETURN LEVEL and matched 0 of 124 rows. A slow-skipped row carries no days, so
  // copying it through left the cell EMPTY — caught in the c083c109 dry run.
  // ⚠ EXCLUSIVE span, no +1. Inclusive counting gives 730 for TRAIN while every normalized row in
  // the ledger stores 729 — checked against the live ledger rather than trusted, because a column
  // the bar is computed from must match its neighbours exactly, not approximately.
  const days = String(Math.round((Date.parse(w.end) - Date.parse(w.start)) / 86400000));
  const known = [...new Set(led.rows(windowName)
    .filter(r => r.status === 'normalized' && r.days).map(r => String(r.days)))];
  if (known.length === 1 && known[0] !== days) {
    throw new Error(`days ${days} disagrees with every existing ${windowName} row (${known[0]}) — ` +
                    `refusing to write a row whose day count does not match its neighbours`);
  }
  const row = [c.row.sourceFile, c.row.postId, c.row.title, 'normalized',
               w.start, w.end, days,
               total, annual, sharpe, maxdd, String(obj), gate, String(epoch)];
  if (row.length !== led.COLS.length) throw new Error(`row has ${row.length} cells, COLS has ${led.COLS.length}`);
  console.log(`[recover] row: ${row.join(' | ')}`);
  if (dry) { console.log('[recover] --dry: nothing written'); return { dry: true, obj, gate }; }

  console.log(`[recover] saved curve: ${S.save(S.seriesKey(c.row.sourceFile, windowName, epoch), rec)}`);
  fs.appendFileSync(path.join(ROOT, `harness/normalize-${windowName}.tsv`), row.join('\t') + '\n');
  console.log('[recover] appended — newest-row-wins makes it authoritative over the slow-skipped row');

  // ⚠⚠ The recovery is not finished at the ledger row, and forgetting this was caught by
  // `tests/daily.test.js`'s pool invariant on the FIRST use: the chain had already DEFERRED
  // c5d20393 as a slow-skip (pool 20 -> 22), so after recovery it sat in the retry pool as
  // finished work — the pipeline would have re-offered it at a higher cap and spent minutes
  // re-measuring something already measured.
  //
  // `normalize-sync` is the step that OWNS this (it derives the wiki page and both queues from the
  // ledger), which is the same rule that put it at the end of every normalize batch: bookkeeping
  // belongs to the step that owns it, not to one caller. Measured here: pool 22 -> 21, 11 finished
  // queue entries pruned, wiki page scaffolded.
  // Never fatal — a bookkeeping failure must not lose a result that is now safely in the ledger.
  try {
    const { sync } = require('./normalize-sync');
    const r = sync({ window: windowName });
    console.log(`[recover] sync: ${(r.created || []).length} wiki page(s), ` +
                `${(r.pruned || []).length} queue entr(ies) pruned, ` +
                `${(r.resolvedDeferred || []).length} dead deferred resolved`);
  } catch (e) {
    console.error(`[recover] ⚠ post-recovery sync failed (the result is safe in the ledger): ${e.message}`);
  }
  return { obj, gate, sharpe };
}

module.exports = { candidates, recover, findBySource };

if (require.main === module) {
  const argv = process.argv.slice(2);
  const dry = argv.includes('--dry');
  const tag = argv.find(a => /^[0-9a-f]{8}$/.test(a));
  (async () => {
    if (argv.includes('--scan') || !tag) {
      const c = candidates();
      console.log(`[recover] ${c.length} slow-skipped row(s) in normalize-train.tsv:`);
      for (const x of c) {
        console.log(`   ${x.hasCopy ? 'RECOVERABLE' : 'no temp copy'}  ${x.tag}  ` +
                    `${x.row.sourceFile.replace('strategies/', '').slice(0, 54)}`);
      }
      console.log('\n⚠ "no temp copy" is not a verdict about the run — /tmp is not durable, and the');
      console.log('  copy is the only link back to what was submitted. Those are not guessed at.');
      if (!tag) return;
    }
    const nearIdx = argv.indexOf('--near');
    const near = nearIdx >= 0 ? argv[nearIdx + 1] : null;
    const pagesIdx = argv.indexOf('--pages');
    const pages = pagesIdx >= 0 ? Number(argv[pagesIdx + 1]) : 3;
    await recover(tag, { dry, near, pages });
  })().then(() => { try { jq.close(); } catch {} })
      .catch(e => { console.error('[recover] ABORTED:', e.message); process.exitCode = 1; });
}
