/**
 * One-off: recover the result of a run that FINISHED while JQ kept listing it as running.
 *
 * ## What happened
 *
 * `pollUntilComplete` detects completion from the account-wide `statistics.running` COUNT, because
 * `running[].id` is a backtestId that never matches our algorithmId — so the count cannot be
 * attributed to our run. On 2026-10-18 JQ left a FINISHED run in that list: the count stayed above
 * baseline, `emptyStreak` never accumulated, and the executor polled to its 45-minute cap and wrote
 * `slow-skipped` for `strategies/2026-10-18_优化了半个月的ETF动量轮动策略-c5d20393.py` while the
 * completed result sat on the server. The human spotted it — the UI showed 「完成」 for
 * 这是一个简单的策略-1249 while the poller was 33 minutes in.
 *
 * (The poller now also reads the buildList row's `_status`, which IS attributable because we pass
 * our own algorithmId. This script recovers the one run that predates that fix.)
 *
 * ## Why this is free
 *
 * The run completed, so its result and curve are already on JQ's servers:
 * `POST /algorithm/backtest/stats` and `GET /algorithm/backtest/result`. No backtest is started.
 *
 * ## Identification is by SOURCE HASH, never by id
 *
 * JQ re-mints every id per request (CLAUDE.md), and the account holds two listings per algorithm.
 * So the run is identified by hashing the normalized source JQ serves against the exact temp copy
 * the normalizer submitted (`/tmp/jq-normalize/c5d20393.py`) — the same discipline
 * `series-backfill.js` uses, where a wrong pairing silently corrupts every correlation built on it.
 *
 * ## Two cross-checks before anything is written
 *
 *   1. the curve's final cumulative return must agree with the stats endpoint (±0.05pp);
 *   2. the row must have exactly `ledger.COLS.length` cells.
 * Either failing aborts without writing.
 *
 * The appended row is `normalized` and APPENDS after the `slow-skipped` one, so newest-row-wins
 * makes the real measurement authoritative. Numbers come from `harness-config`'s own
 * `objective()`/`gate()`, not a reimplementation of the formula.
 *
 *   node study/_recover/recover-c5d20393.js --dry     # print, write nothing
 *   node study/_recover/recover-c5d20393.js
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const ROOT = path.join(__dirname, '../..');
const S = require('../../utils/backtest-series');
const h = require('../../utils/harness-config');
const led = require('../../utils/ledger');
const { jqText, jqPostJson } = require('../../utils/jq-http');

const SRC = 'strategies/2026-10-18_优化了半个月的ETF动量轮动策略-c5d20393.py';
const TITLE = '优化了半个月的ETF动量轮动策略';
const SUBMITTED = '/tmp/jq-normalize/c5d20393.py';
const DRY = process.argv.includes('--dry');

const norm = s => String(s).replace(/\r\n/g, '\n').trim();
const sha = s => crypto.createHash('sha256').update(norm(s)).digest('hex');

async function findBacktestBySource(wantHash, limit = 8) {
  const list = await jqText('/algorithm/index/list?page=1');
  const algs = [...new Set((list.match(/algorithmId=([a-f0-9]{32})/g) || []).map(s => s.split('=')[1]))];
  for (const a of algs.slice(0, limit)) {
    const b = await jqText(`/algorithm/backtest/buildList?algorithmId=${a}`);
    const bt = (b.match(/class="backtest-tr"[^>]*_backtestId="([a-f0-9]{32})"/) || [])[1]
            || (b.match(/<tr _backtestId="([a-f0-9]{32})"/) || [])[1];
    if (!bt) continue;
    const raw = await jqText(`/algorithm/backtest/source?backtestId=${bt}&ajax=1`);
    let code = raw;
    try { const j = JSON.parse(raw); code = (j.data && (j.data.source || j.data.code)) || raw; } catch { /* plain text */ }
    if (sha(code) === wantHash) return { algorithmId: a, backtestId: bt };
  }
  return null;
}

(async () => {
  if (!fs.existsSync(SUBMITTED)) throw new Error(`the submitted copy is gone (${SUBMITTED}) — cannot hash-match`);
  const want = sha(fs.readFileSync(SUBMITTED, 'utf8'));

  const found = await findBacktestBySource(want);
  if (!found) throw new Error('no backtest on the account matches the submitted source — refusing to guess');
  console.log(`[recover] source-matched algorithm ${found.algorithmId.slice(0, 8)} backtest ${found.backtestId.slice(0, 8)}`);

  const s = await jqPostJson(`/algorithm/backtest/stats?backtestId=${found.backtestId}&ajax=1`, {});
  const d = (s && s.data) ? s.data : s;
  const fx = (v, n = 2) => (Number(v) * 100).toFixed(n);
  const total = fx(d.algorithm_return), annual = fx(d.annual_algo_return);
  const maxdd = fx(d.max_drawdown), sharpe = Number(d.sharpe).toFixed(2);
  console.log(`[recover] stats: days=${d.trading_days} total=${total}% annual=${annual}% sharpe=${sharpe} maxdd=${maxdd}%`);
  if (Number(d.trading_days) !== 484) throw new Error(`expected 484 TRAIN trading days, got ${d.trading_days}`);

  const raw = await S.fetchViaHttp(found.backtestId);
  const rec = S.toRecord(raw, { sourceFile: SRC, backtestId: found.backtestId, window: 'train', epoch: 8 });
  const curveTotal = rec.cum[rec.cum.length - 1];
  console.log(`[recover] curve: ${rec.points} points ${rec.start}..${rec.end} final cum ${curveTotal.toFixed(2)}%`);
  // CROSS-CHECK 1 — a curve that disagrees with the stats means the wrong run was matched.
  if (Math.abs(curveTotal - Number(total)) > 0.05) {
    throw new Error(`curve ${curveTotal.toFixed(2)}% disagrees with stats ${total}% — refusing to record`);
  }

  const obj = h.objective(Number(annual), Number(maxdd), Number(sharpe));
  const gate = h.gate(Number(sharpe)) ? 'pass' : 'fail';
  const prior = led.rows().find(r => String(r.sourceFile).includes('c5d20393'));
  if (!prior) throw new Error('no existing row for c5d20393 — expected the slow-skipped one');
  if (prior.status !== 'slow-skipped') {
    throw new Error(`newest row is already '${prior.status}', not 'slow-skipped' — nothing to recover`);
  }
  const row = [SRC, prior.postId, TITLE, 'normalized',
               '2022-01-01', '2023-12-31', '729', total, annual, sharpe, maxdd, String(obj), gate,
               String(h.config().epoch)];
  // CROSS-CHECK 2 — the schema has one owner; a short row would shift every column after it.
  if (row.length !== led.COLS.length) throw new Error(`row has ${row.length} cells, COLS has ${led.COLS.length}`);

  console.log(`[recover] row: ${row.join(' | ')}`);
  if (DRY) { console.log('[recover] --dry: nothing written'); return; }

  console.log(`[recover] saved curve: ${S.save(S.seriesKey(SRC, 'train', 8), rec)}`);
  fs.appendFileSync(path.join(ROOT, 'harness/normalize-train.tsv'), row.join('\t') + '\n');
  console.log(`[recover] appended to harness/normalize-train.tsv — newest-row-wins makes it authoritative`);
})().then(() => { try { require('../../utils/jq-http').close(); } catch {} })
    .catch(e => { console.error('[recover] ABORTED:', e.message); process.exitCode = 1; });
