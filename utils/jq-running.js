/**
 * jq-running.js — how many backtests the JoinQuant account currently has in flight, and
 * optionally block until that reaches zero.
 *
 * ## Why this exists
 *
 * The completion signal for a backtest is the account-wide running count (see
 * `pollUntilComplete`), so `concurrencyGate` refuses to start a second one. That is correct — two
 * concurrent runs once returned byte-identical metrics for different strategies — but it has a
 * self-inflicted failure mode:
 *
 *   a slow-skipped strategy is cancelled locally at the cap, JQ does NOT always honour the cancel
 *   (「在此状态不能取消」), the backtest lingers in running[], and the very next batch is refused
 *   by our own leftover.
 *
 * Measured 2026-09-26: the daily pipeline normalized 2 strategies, slow-skipped a third, and its
 * next normalize stage hit CONCURRENT STOP immediately. The chain then read that as no progress
 * and ended with ~130 of 180 budget minutes unspent.
 *
 * The blocker is almost always ours and clears in minutes, so the right response is to WAIT, not
 * to stop. This is the waiter. It exits 0 when the account is clear and 1 when it is still busy
 * after the timeout, so a synchronous caller (`strategy-normalize.js` uses execFileSync) can just
 * check the exit code.
 *
 * ⚠ It ignores entries older than JQ_CONCURRENT_STALE_MIN, matching `concurrencyGate`. A phantom
 * that JQ will never reap — one reached 701 minutes while billing nothing — must not make this
 * block forever.
 *
 * Usage:
 *   node utils/jq-running.js                       # print the count, exit 0 if clear
 *   node utils/jq-running.js --wait --timeout-min 50 --cap-min 45 [--poll-sec 45]
 *     exit 0 = clear, 1 = still busy after the wait (a LIVE run — real contention),
 *     exit 2 = blocker is past the cap: dead, tolerated by the executor, safe to proceed
 */

const { chromium } = require('playwright');

const CDP = process.env.JQ_CDP_URL || 'http://localhost:9225';
const STALE_MIN = (() => {
  const n = parseInt(process.env.JQ_CONCURRENT_STALE_MIN || '', 10);
  return Number.isFinite(n) && n > 0 ? n : 120;
})();

/** "701分34秒" -> 701.57 (minutes). Mirrors parseCnDuration in the executor. */
function cnMinutes(s) {
  if (!s) return 0;
  const t = String(s);
  const h = (t.match(/(\d+)\s*(?:时|小时)/) || [])[1];
  const m = (t.match(/(\d+)\s*分/) || [])[1];
  const sec = (t.match(/(\d+)\s*秒/) || [])[1];
  return (parseInt(h || 0, 10) * 60) + parseInt(m || 0, 10) + (parseInt(sec || 0, 10) / 60);
}

/** @returns {{live:number, stale:number, rows:Array}|null} null when the read itself failed. */
async function running() {
  let browser;
  try {
    browser = await chromium.connectOverCDP(CDP);
    const ctx = browser.contexts()[0];
    const page = ctx.pages().find(p => p.url().includes('joinquant')) || ctx.pages()[0];
    const rows = await page.evaluate(async () => {
      const j = await (await fetch('/algorithm/index/statistics', { credentials: 'include' })).json();
      return ((j && j.data && j.data.running) || []).map(r => ({ usedSec: r.usedSec, time: r.time }));
    });
    const live = rows.filter(r => cnMinutes(r.usedSec) <= STALE_MIN);
    // Oldest LIVE age is what distinguishes "ours, still legitimately running" from "ours, already
    // cancelled at the cap and never reaped". Computed, not read off rows[0] — the endpoint's order
    // is not documented and a wrong oldest flips the verdict.
    const oldestLiveMin = live.reduce((mx, r) => Math.max(mx, cnMinutes(r.usedSec)), 0);
    return { live: live.length, stale: rows.length - live.length, rows, oldestLiveMin };
  } catch (e) {
    return null;
  } finally {
    // Detach only — closing the page would destroy the CDP cookie context.
    if (browser) { try { await browser.close(); } catch { /* best effort */ } }
  }
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

/**
 * Block until the account has no live backtest, or the timeout expires.
 *
 * ## The age-vs-cap rule
 *
 * The blocker is almost always ours, but there are TWO kinds of ours and they want opposite
 * responses. Both appeared in consecutive unattended runs:
 *
 *   2026-10-02  oldest 18分42秒 — a backtest with 26min of LEGITIMATE runtime left under the
 *               45min slow-skip cap. The flat 10min wait was simply shorter than the work, so
 *               the stage recorded no progress and the chain ended with 136 of 180 budget
 *               minutes unspent. Waiting longer was all it needed.
 *   2026-10-03  oldest 63分49秒 — PAST the cap, i.e. already cancelled locally and not reaped by
 *               JQ (「在此状态不能取消」). Nothing will clear it before STALE_MIN. The 10min wait
 *               was pure loss.
 *
 * So the deadline cannot be one number. `capMin` splits the cases:
 *
 *   age <= capMin  ->  ours, still running. WAIT (the caller's timeout should exceed capMin).
 *   age >  capMin  ->  phantom. Do not wait at all; report it and let the caller stop cleanly.
 *
 * ⚠ What a phantom MEANS changed once `pollUntilComplete` learned to measure completion against
 * a baseline instead of against zero. It used to be fatal: the detector counted unreapable
 * entries, so with one present `runningCount > 0` forever, its `resultsRendered` fallback was
 * unreachable, and any run that bypassed the gate spun to its cap and slow-skipped. Proceeding
 * could not succeed, so a phantom had to stop the batch.
 *
 * It is now tolerable — the gate admits a past-cap entry and hands its count over as the
 * baseline. So exit 2 reports "the blocker is dead, proceeding is safe", and a caller should
 * RETRY rather than stop. The waiter still exists for the case that genuinely needs it: a run
 * younger than the cap, which can still finish and is real contention.
 *
 * @returns {{cleared:boolean, phantom:boolean, ageMin:number, live:number}}
 */
async function waitClear({ timeoutMin = 10, pollSec = 45, capMin = 0, quiet = false } = {}) {
  const deadline = Date.now() + timeoutMin * 60000;
  let first = true;
  for (;;) {
    const r = await running();
    if (r == null) {
      if (!quiet) console.log('[running] could not read the account — treating as clear (the gate will re-check)');
      return { cleared: true, phantom: false, ageMin: 0, live: 0 };  // never wedge the batch
    }
    if (r.live === 0) {
      if (!quiet && !first) console.log('[running] account is clear — resuming');
      else if (!quiet) console.log(`[running] clear${r.stale ? ` (${r.stale} stale entr(y/ies) ignored)` : ''}`);
      return { cleared: true, phantom: false, ageMin: 0, live: 0 };
    }

    const age = r.oldestLiveMin;
    if (capMin > 0 && age > capMin) {
      if (!quiet) {
        console.log(`[running] ${r.live} in flight and the oldest is ${age.toFixed(0)}min — PAST the ` +
                    `${capMin}min cap, so it was already cancelled and JQ has not reaped it. It ` +
                    `will never finish, so waiting is pointless; the executor tolerates it as a ` +
                    `completion baseline, so proceeding is safe.`);
      }
      return { cleared: false, phantom: true, ageMin: age, live: r.live };
    }

    if (Date.now() >= deadline) {
      if (!quiet) console.log(`[running] still ${r.live} in flight after ${timeoutMin}min ` +
                              `(oldest ${age.toFixed(0)}min) — giving up`);
      return { cleared: false, phantom: false, ageMin: age, live: r.live };
    }
    if (!quiet) {
      const left = Math.round((deadline - Date.now()) / 60000);
      console.log(`[running] ${r.live} backtest(s) in flight (oldest ${age.toFixed(0)}min` +
                  `${capMin > 0 ? ` of ${capMin}min cap` : ''}) — waiting, ${left}min left`);
    }
    first = false;
    await sleep(pollSec * 1000);
  }
}

module.exports = { running, waitClear, cnMinutes };

if (require.main === module) {
  const argv = process.argv.slice(2);
  const num = (flag, d) => {
    const i = argv.indexOf(flag);
    if (i < 0) return d;
    const v = parseInt(argv[i + 1], 10);
    return Number.isFinite(v) ? v : d;
  };
  (async () => {
    if (argv.includes('--wait')) {
      // Exit codes are the contract: 0 clear, 1 still busy after the wait, 2 phantom (past cap).
      // The caller needs the distinction — 1 may be worth retrying later, 2 never is.
      const v = await waitClear({ timeoutMin: num('--timeout-min', 10),
                                  pollSec: num('--poll-sec', 45),
                                  capMin: num('--cap-min', 0) });
      process.exit(v.cleared ? 0 : (v.phantom ? 2 : 1));
    }
    const r = await running();
    if (r == null) { console.log('[running] unreadable'); process.exit(0); }
    console.log(`[running] live=${r.live} stale=${r.stale}`);
    for (const x of r.rows) console.log(`   ${x.usedSec} old, started ${x.time}`);
    process.exit(r.live === 0 ? 0 : 1);
  })().catch(e => { console.error('FATAL', e.message); process.exit(0); });
}
